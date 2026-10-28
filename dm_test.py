"""Validate message delivery between two guest accounts (rules out routing issues)."""
import re
import time
import uuid

from xmpp_client import XmppClient


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


def login():
    c = XmppClient(verbose=False)
    c.connect()
    _, username, password, _ = c.register_guest(country="US")
    c.sasl_plain(username, password)
    c.open_stream_again()
    c.bind("mobile")
    return c, username


a, ua = login()
b, ub = login()
print("A:", ua, "\nB:", ub)

a.send("<presence/>")
b.send("<presence/>")
drain(a, 2)
drain(b, 2)

a.buf = ""
a.send(
    f"<message id='dm-{uuid.uuid4().hex[:6]}' to='{ub}@x.siki.ai' type='chat'>"
    "<body>hello from A</body>"
    "<request xmlns='urn:xmpp:receipts'/>"
    "</message>"
)
got = drain(b, 12)
print("\n=== B received ===\n", got[:1200])
print("\nbodies:", re.findall(r"<body[^>]*>(.*?)</body>", got, re.S))

print("\n=== welcome endpoint ===")
import json
import urllib.request
for q in (f"?username={ua}", f"?username={ua}@x.siki.ai"):
    try:
        req = urllib.request.Request("https://d11absfiaqzcnz.cloudfront.net/welcome" + q,
                                     headers={"client": "android"})
        print(q, "->", json.loads(urllib.request.urlopen(req, timeout=20).read()))
    except Exception as exc:
        print(q, "-> ERR", exc)
