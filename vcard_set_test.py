"""Upload a vCard (as the app does at registration) then send a chat message."""
import re
import time
import uuid

from xmpp_client import XmppClient

BOT = "0_b2cf4ea3-b728-4112-be3d-9829d950bcea@x.siki.ai"


def drain(c, seconds):
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
    return out


c = XmppClient(verbose=False)
c.connect()
_, username, password, _ = c.register_guest(country="US")
c.sasl_plain(username, password)
c.open_stream_again()
c.bind("android")
me = f"{username}@x.siki.ai"
c.buf = ""
c.send("<iq type='get' id='g1'><vCard xmlns='vcard-temp'/></iq>")
vc = drain(c, 6)
pt = re.search(r"<PUBLICTOKEN>([^<]+)</PUBLICTOKEN>", vc)
mine = pt.group(1) if pt else ""
print("me:", me, "pt:", mine)

vcard = (
    "<vCard xmlns='vcard-temp'>"
    f"<JABBERID>{me}</JABBERID>"
    f"<PUBLICTOKEN>{mine}</PUBLICTOKEN>"
    "<FN>Guest</FN><NICKNAME>Guest</NICKNAME>"
    "<N><GIVEN>Guest</GIVEN></N>"
    "</vCard>"
)
c.buf = ""
c.send(f"<iq type='set' id='s1'>{vcard}</iq>")
print("\n[vcard set]", drain(c, 8)[:600])

c.send("<presence/>")
drain(c, 2)

c.buf = ""
c.send(
    f"<message id='q-{uuid.uuid4().hex[:6]}' to='{BOT}' type='chat'>"
    f"<publictoken xmlns='proximity:publictoken'>{mine}</publictoken>"
    "<body>Hi there! Say hello back in one short sentence.</body>"
    "<request xmlns='urn:xmpp:receipts'/>"
    "<active xmlns='http://jabber.org/protocol/chatstates'/>"
    "<nick xmlns='http://jabber.org/protocol/nick'>Guest</nick>"
    "</message>"
)
got = drain(c, 50)
print("\n=== raw ===\n", got[:2500])
print("\nbodies:", [b for b in re.findall(r"<body[^>]*>(.*?)</body>", got, re.S) if "hello back" not in b])
