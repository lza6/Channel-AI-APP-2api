"""Full guest flow: register -> SASL (JWT in success) -> bind -> REST check -> XMPP chat."""
import json
import time
import urllib.request
import uuid

from xmpp_client import XmppClient

PUBLIC_API = "https://d11absfiaqzcnz.cloudfront.net"
PRIVATE_API = "https://admin-api-prod.shroom.gg"


def pick_bot():
    req = urllib.request.Request(
        f"{PUBLIC_API}/v2/sidekick/search?search_term=waifu&include_nsfw=false&limit=3",
        headers={"client": "android"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=25).read())[0]


def rest(path, jwt, jid, base=PRIVATE_API):
    req = urllib.request.Request(
        f"{base}/{path}",
        headers={"Authorization": f"Bearer {jwt}", "jid": jid, "client": "android",
                 "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status, resp.read()[:600].decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()[:600].decode("utf-8", "replace")


def main():
    bot = pick_bot()
    bot_jid = f"{bot['username']}@x.siki.ai"
    print("bot:", bot["display_name"], bot_jid)

    c = XmppClient(verbose=False)
    c.connect()
    _, username, password, _ = c.register_guest(country="US")
    print("registered:", username)
    c.sasl_plain(username, password)
    print("jwt len:", len(c.jwt or ""))
    c.open_stream_again()
    print("bind:", c.bind("android")[-200:].replace("\n", " "))
    print("jwt iq:", c.get_jwt()[-200:].replace("\n", " "))

    my_jid = f"{username}@x.siki.ai"
    print("\n=== REST with SASL jwt ===")
    print("balances:", rest("api/v2/currency/balances", c.jwt, my_jid))
    print("conversations:", rest("api/v2/chat/conversations?limit=3", c.jwt, my_jid))

    print("\n=== XMPP message ===")
    c.buf = ""
    c.send(
        f"<message id='msg-{uuid.uuid4().hex[:10]}' to='{bot_jid}' type='chat'>"
        "<body>Hey! Who are you? Reply in one short sentence.</body>"
        "<request xmlns='urn:xmpp:receipts'/>"
        "<active xmlns='http://jabber.org/protocol/chatstates'/>"
        "</message>"
    )
    t0 = time.time()
    try:
        c.read_until("</message>", timeout=120)
    except Exception as exc:
        print("wait:", type(exc).__name__, exc)
    print(f"elapsed {time.time()-t0:.1f}s")
    print("\n=== transcript ===")
    print(c.buf[-5000:])
    open("artifacts/first_chat_transcript.txt", "w", encoding="utf-8").write(c.buf)


if __name__ == "__main__":
    main()
