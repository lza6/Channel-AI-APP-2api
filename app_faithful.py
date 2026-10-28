"""App-faithful attempt: realistic login resource, UUID message ids, two messages."""
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


device_id = uuid.uuid4().hex
resource = f"android-1.6.1.3330-14-US-China Standard Time-{uuid.uuid4().hex[:20]}"
print("resource:", resource)

c = XmppClient(verbose=False)
c.connect()
_, username, password, resp = c.register_guest(country="US", device_id=device_id, resource=resource)
c.sasl_plain(username, password)
c.open_stream_again()
c.bind(resource)
me = f"{username}@x.siki.ai"
print("me:", me)

c.buf = ""
c.send("<iq type='get' id='g1'><vCard xmlns='vcard-temp'/></iq>")
pt = re.search(r"<PUBLICTOKEN>([^<]+)</PUBLICTOKEN>", drain(c, 6))
mine = pt.group(1) if pt else ""
print("publictoken:", mine)

c.send("<presence/>")
drain(c, 2)

for i in range(2):
    c.buf = ""
    c.send(
        f"<message id='{uuid.uuid4()}' to='{BOT}' type='chat'>"
        f"<publictoken xmlns='proximity:publictoken'>{mine}</publictoken>"
        f"<body>Hello number {i+1}, please reply in one sentence.</body>"
        "<request xmlns='urn:xmpp:receipts'/>"
        "<active xmlns='http://jabber.org/protocol/chatstates'/>"
        "<nick xmlns='http://jabber.org/protocol/nick'>Guest</nick>"
        "</message>"
    )
    got = drain(c, 35)
    print(f"\n=== attempt {i+1} ===\n{got[:1500]}")
    bodies = [b for b in re.findall(r"<body[^>]*>(.*?)</body>", got, re.S) if "reply in one sentence" not in b]
    if bodies:
        print("REPLY:", bodies)
        break
