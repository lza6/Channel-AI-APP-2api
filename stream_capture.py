"""Capture complete reply stream (structure of streaming / multi-part bodies)."""
import re
import time
import uuid

from xmpp_client import XmppClient

BOT = "0_b2cf4ea3-b728-4112-be3d-9829d950bcea@x.siki.ai"


def pump(c, seconds, quiet=3.0):
    out, chunks = "", []
    t0 = last = time.time()
    while time.time() - t0 < seconds:
        c.sock.settimeout(1)
        try:
            chunk = c.sock.recv(65536)
        except Exception:
            if time.time() - last > quiet and out:
                break
            continue
        if not chunk:
            break
        text = chunk.decode("utf-8", "replace")
        out += text
        chunks.append((round(time.time() - t0, 2), text))
        last = time.time()
    return out, chunks


device_id = uuid.uuid4().hex
resource = f"android-1.6.1.3330-14-US-China Standard Time-{uuid.uuid4().hex[:20]}"
c = XmppClient(verbose=False)
c.connect()
_, username, password, _ = c.register_guest(country="US", device_id=device_id, resource=resource)
c.sasl_plain(username, password)
c.open_stream_again()
c.bind(resource)
me = f"{username}@x.siki.ai"
c.buf = ""
c.send("<iq type='get' id='g1'><vCard xmlns='vcard-temp'/></iq>")
mine = re.search(r"<PUBLICTOKEN>([^<]+)</PUBLICTOKEN>", pump(c, 6, 1)[0]).group(1)
c.send("<presence/>")
pump(c, 1, 0.5)
print("me:", me, "| jwt:", (c.jwt or "")[:20], "| pt:", mine)

for turn, text in enumerate(["Hi! Introduce yourself in one short sentence.",
                             "What is your name and where do you live?",
                             "Tell me a one-line joke."], 1):
    c.buf = ""
    c.send(
        f"<message id='{uuid.uuid4()}' to='{BOT}' type='chat'>"
        f"<publictoken xmlns='proximity:publictoken'>{mine}</publictoken>"
        f"<body>{text}</body>"
        "<request xmlns='urn:xmpp:receipts'/>"
        "<active xmlns='http://jabber.org/protocol/chatstates'/>"
        "<nick xmlns='http://jabber.org/protocol/nick'>Guest</nick>"
        "</message>"
    )
    out, chunks = pump(c, 60, 3)
    bodies = re.findall(r"<body[^>]*>(.*?)</body>", out, re.S)
    print(f"\n=== turn {turn} ({len(chunks)} chunks) ===")
    for delta, chunk in chunks:
        print(f"[{delta:5.2f}s] {chunk[:400]}")
    print("bodies:", bodies)
    open(f"artifacts/turn{turn}.xml", "w", encoding="utf-8").write(out)

import json
import urllib.request
req = urllib.request.Request("https://admin-api-prod.shroom.gg/api/v2/currency/balances",
                            headers={"Authorization": f"Bearer {c.jwt}", "jid": me, "client": "android"})
print("\nbalances after:", urllib.request.urlopen(req, timeout=20).read().decode())
