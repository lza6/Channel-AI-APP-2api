"""Experiment: fetch own vCard, then try several message variants to get an AI reply."""
import re
import time
import uuid

from xmpp_client import XmppClient

BOT = "0_4d27b766-64c0-4bf2-aeb8-a6f838ef4f2d@x.siki.ai"  # Chichi - AI Companion


def collect(c, seconds):
    out = ""
    t0 = time.time()
    while time.time() - t0 < seconds:
        c.sock.settimeout(2)
        try:
            chunk = c.sock.recv(65536)
        except Exception:
            continue
        if not chunk:
            break
        out += chunk.decode("utf-8", "replace")
    c.buf += out
    return out


def main():
    c = XmppClient(verbose=False)
    c.connect()
    _, username, password, _ = c.register_guest(country="US")
    c.sasl_plain(username, password)
    c.open_stream_again()
    c.bind("android")
    me = f"{username}@x.siki.ai"
    print("me:", me, "| jwt len", len(c.jwt))

    # presence available (app does this on connect)
    c.buf = ""
    c.send("<presence><show>online</show></presence>")
    print("\n--- presence ---")
    print(collect(c, 4)[:500])

    # own vCard
    vid = "vc-" + uuid.uuid4().hex[:8]
    c.buf = ""
    c.send(f"<iq type='get' id='{vid}'><vcard xmlns='vcard-temp'/></iq>")
    vcard = collect(c, 8)
    print("\n--- vcard ---")
    print(vcard[:1500])
    pt = re.search(r"<PUBLICTOKEN>([^<]+)</PUBLICTOKEN>", vcard)
    publictoken = pt.group(1) if pt else None
    print("PUBLICTOKEN =", publictoken)

    # variant A: chat to bot jid + my publictoken element
    print("\n--- variant A: 0_ jid + publictoken ---")
    c.buf = ""
    mid = "a-" + uuid.uuid4().hex[:8]
    tok_elem = (
        f"<publictoken xmlns='proximity:publictoken'>{publictoken}</publictoken>" if publictoken else ""
    )
    c.send(
        f"<message id='{mid}' to='{BOT}' type='chat'>{tok_elem}"
        "<body>Hello! Say hi back in one short sentence.</body>"
        "<request xmlns='urn:xmpp:receipts'/>"
        "<active xmlns='http://jabber.org/protocol/chatstates'/>"
        "</message>"
    )
    print(collect(c, 35)[:2500])

    print("\n--- variant B: subscribe presence ---")
    c.buf = ""
    c.send(f"<presence to='{BOT}' type='subscribe'/>")
    print(collect(c, 6)[:800])


if __name__ == "__main__":
    main()
