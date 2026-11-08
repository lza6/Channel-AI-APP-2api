"""Send a chat message exactly as the app does: with own publictoken element."""
import re
import sys
import time
import uuid

from xmpp_client import XmppClient

BOT_JID = sys.argv[1] if len(sys.argv) > 1 else "0_4825402c-5674-4b36-b6e5-a4b415622904@x.siki.ai"


def read(c, seconds):
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
        m = re.search(r"<body[^>]*>.*?</body>", out, re.S)
        if m and "from='x.siki.ai'" not in out:
            break
    return out


c = XmppClient(verbose=False)
c.connect()
_, username, password, _ = c.register_guest(country="US")
c.sasl_plain(username, password)
c.open_stream_again()
c.bind("android")
me = f"{username}@x.siki.ai"

c.buf = ""
c.send("<iq type='get' id='vc1'><vCard xmlns='vcard-temp'/></iq>")
vc = read(c, 8)
pt = re.search(r"<PUBLICTOKEN>([^<]+)</PUBLICTOKEN>", vc)
publictoken = pt.group(1) if pt else ""
print("me:", me, "| pt:", publictoken)

body = "Hi! Introduce yourself in one short sentence."
c.buf = ""
mid = "t-" + uuid.uuid4().hex[:8]
c.send(
    f"<message id='{mid}' to='{BOT_JID}' type='chat'>"
    f"<publictoken xmlns='proximity:publictoken'>{publictoken}</publictoken>"
    f"<body>{body}</body>"
    "<request xmlns='urn:xmpp:receipts'/>"
    "<active xmlns='http://jabber.org/protocol/chatstates'/>"
    "</message>"
)
got = read(c, 60)
print("\n=== raw ===")
print(got[:3000])
print("\n=== bodies ===")
for b in re.findall(r"<body[^>]*>(.*?)</body>", got, re.S):
    print("*", b[:800])
open("artifacts/publictoken_chat.txt", "w", encoding="utf-8").write(got)
