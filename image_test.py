"""Try welcome/image bots: plain text and <imagerequest/> packets."""
import re
import time
import uuid

from xmpp_client import XmppClient

WELCOME = [
    ("0_febd3c8d-a862-4d0b-ab5e-7438c26f7aea", "Real Amateur Photos", "pt_1adc9b95-f361-4763-b4b5-9aae6935ef5c@x.siki.ai"),
    ("0_77932319-ce40-40fd-8b69-de2561b659da", "Illustrious XL", "pt_81a8b9dc-0ffb-4079-a024-250e0ae8f992@x.siki.ai"),
]


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
pt = re.search(r"<PUBLICTOKEN>([^<]+)</PUBLICTOKEN>", drain(c, 6))
mine = pt.group(1) if pt else ""
c.send("<presence/>")
drain(c, 2)
print("me:", me, "pt:", mine)

for user, name, ptok in WELCOME:
    jid = f"{user}@x.siki.ai"
    # (a) plain text
    c.buf = ""
    c.send(
        f"<message id='p-{uuid.uuid4().hex[:6]}' to='{jid}' type='chat'>"
        f"<publictoken xmlns='proximity:publictoken'>{mine}</publictoken>"
        "<body>a cat sitting on a windowsill, cinematic light</body>"
        "<request xmlns='urn:xmpp:receipts'/>"
        "</message>"
    )
    got = drain(c, 30)
    print(f"\n[{name}] text -> {got[:600]}")

    # (b) imagerequest
    c.buf = ""
    c.send(
        f"<message id='i-{uuid.uuid4().hex[:6]}' to='{jid}' type='chat'>"
        "<body/><noread/><imagerequest/>"
        f"<publictoken xmlns='proximity:publictoken'>{mine}</publictoken>"
        "</message>"
    )
    got = drain(c, 30)
    print(f"[{name}] imagerequest -> {got[:800]}")
