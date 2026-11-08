"""Fetch own vCard (correct Smack element casing) to read PUBLICTOKEN."""
import time
from xmpp_client import XmppClient


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
        if "</iq>" in out:
            break
    return out


c = XmppClient(verbose=False)
c.connect()
_, username, password, _ = c.register_guest(country="US")
c.sasl_plain(username, password)
c.open_stream_again()
c.bind("android")
me = f"{username}@x.siki.ai"
print("me:", me)

for name, pkt in [
    ("get-vCard", "<iq type='get' id='v10'><vCard xmlns='vcard-temp'/></iq>"),
    ("get-vCard-to-self", f"<iq type='get' id='v11' to='{me}'><vCard xmlns='vcard-temp'/></iq>"),
]:
    c.buf = ""
    c.send(pkt)
    print(f"\n### {name}\n{read(c, 8)[:1500]}")
