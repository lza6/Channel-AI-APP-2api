"""Debug SASL: raw dump every stage."""
import base64
import time
import uuid

from xmpp_client import XmppClient, md5

c = XmppClient(verbose=False)
c.connect()
print("[features ok]")

_, username, password, resp = c.register_guest(country="US")
print("[register resp]", resp[-300:].replace("\n", " "))

# drain anything pending
c.sock.settimeout(3)
try:
    while True:
        d = c.sock.recv(65536)
        if not d:
            break
        print("[pending]", d.decode("utf-8", "replace")[:500])
except Exception:
    pass

for label, authcid in (("localpart", username), ("barejid", f"{username}@x.siki.ai")):
    token = base64.b64encode(f"\x00{authcid}\x00{password}".encode()).decode()
    print(f"\n=== auth as {label}: {authcid} ===")
    c.send(f"<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='PLAIN'>{token}</auth>")
    c.sock.settimeout(25)
    got = b""
    t0 = time.time()
    while time.time() - t0 < 25:
        try:
            d = c.sock.recv(65536)
        except Exception as exc:
            print("[recv]", type(exc).__name__)
            break
        if not d:
            print("[closed]")
            break
        got += d
        print("[data]", d.decode("utf-8", "replace")[:800])

print("\n=== re-register same username (existence probe) ===")
c2 = XmppClient(verbose=False)
c2.connect()
iq = (
    f"<iq id='{uuid.uuid4()}' type='set'><query xmlns='jabber:iq:register'>"
    f"<username>{username}</username><password>{password}</password>"
    f"<verificationcode>sc:{uuid.uuid4().hex}</verificationcode><resource>android</resource>"
    "</query></iq>"
)
c2.buf = ""
c2.send(iq)
c2.sock.settimeout(20)
try:
    print(c2.read_until("</iq>", timeout=20)[-600:])
except Exception as exc:
    print("probe failed:", type(exc).__name__, exc, c2.buf[-300:])
