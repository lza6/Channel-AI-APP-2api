"""Probe own vCard retrieval variants to obtain PUBLICTOKEN."""
import time
import uuid

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

variants = [
    ("no-to", f"<iq type='get' id='v1'><vcard xmlns='vcard-temp'/></iq>"),
    ("to-self", f"<iq type='get' id='v2' to='{me}'><vcard xmlns='vcard-temp'/></iq>"),
    ("to-server", "<iq type='get' id='v3' to='x.siki.ai'><vcard xmlns='vcard-temp'/></iq>"),
    ("vcardlookup", f"<iq type='get' id='v4'><query xmlns='proximity:vcardlookup'><jid>{me}</jid></query></iq>"),
    ("users-lookup", f"<iq type='get' id='v5'><query xmlns='proximity:users:lookup'><jid>{me}</jid></query></iq>"),
]
for name, pkt in variants:
    c.buf = ""
    c.send(pkt)
    print(f"\n### {name}\n{read(c, 8)[:900]}")
