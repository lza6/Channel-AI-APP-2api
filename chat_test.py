"""Full guest flow test: register -> auth -> bind -> JWT -> send chat message to a bot."""
import json
import urllib.request
import uuid

from xmpp_client import XmppClient, md5

PUBLIC_API = "https://d11absfiaqzcnz.cloudfront.net"


def pick_bot():
    url = f"{PUBLIC_API}/v2/sidekick/search?search_term=waifu&include_nsfw=false&limit=5"
    req = urllib.request.Request(url, headers={"client": "android"})
    data = json.loads(urllib.request.urlopen(req, timeout=25).read())
    for item in data:
        print("bot:", item.get("username"), "|", item.get("display_name"))
    return data[0]


def main():
    bot = pick_bot()
    bot_jid = f"{bot['username']}@x.siki.ai"
    print("target bot jid:", bot_jid)

    c = XmppClient(verbose=False)
    print("\n--- connect ---")
    c.connect()
    print("\n--- guest register ---")
    _, username, password, resp = c.register_guest(country="US")
    print("registered:", username)

    print("\n--- sasl ---")
    out = c.sasl_plain(username, password)
    print(out[-400:])

    print("\n--- stream restart ---")
    print(c.open_stream_again()[-400:])

    print("\n--- bind ---")
    print(c.bind()[-400:])

    print("\n--- jwt ---")
    print(c.get_jwt()[-900:])

    print("\n--- send message ---")
    from xmpp_client import XmppClient as C  # noqa: F401
    msg_id = "msg-" + uuid.uuid4().hex[:10]
    my_jid = f"{username}@x.siki.ai"
    packet = (
        f"<message id='{msg_id}' to='{bot_jid}' type='chat'>"
        "<body>Hey, who are you? One short sentence.</body>"
        "<request xmlns='urn:xmpp:receipts'/>"
        "<active xmlns='http://jabber.org/protocol/chatstates'/>"
        "<nick xmlns='http://jabber.org/protocol/nick'>Guest</nick>"
        "</message>"
    )
    c.buf = ""
    c.send(packet)
    print("sent as", my_jid)
    try:
        c.read_until("</message>", timeout=90)
    except Exception as exc:
        print("wait failed:", type(exc).__name__, exc)
    print("\n=== transcript tail ===")
    print(c.buf[-4000:])


if __name__ == "__main__":
    main()
