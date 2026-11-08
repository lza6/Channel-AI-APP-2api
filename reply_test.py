"""Capture the full reply stream from a bot over XMPP."""
import re
import sys
import time
import uuid

from xmpp_client import XmppClient

PUBLIC_API = "https://d11absfiaqzcnz.cloudfront.net"
import json
import urllib.request

req = urllib.request.Request(
    f"{PUBLIC_API}/v2/sidekick/search?search_term=companion&include_nsfw=false&limit=5",
    headers={"client": "android"},
)
bots = json.loads(urllib.request.urlopen(req, timeout=25).read())
bot = bots[0]
bot_jid = f"{bot['username']}@x.siki.ai"
print("bot:", bot["display_name"], bot_jid)

c = XmppClient(verbose=False)
c.connect()
_, username, password, _ = c.register_guest(country="US")
c.sasl_plain(username, password)
c.open_stream_again()
c.bind("android")
my_jid = f"{username}@x.siki.ai"
print("me:", my_jid)

c.buf = ""
mid = "msg-" + uuid.uuid4().hex[:10]
c.send(
    f"<message id='{mid}' to='{bot_jid}' type='chat'>"
    "<body>Hi! Introduce yourself in two short sentences.</body>"
    "<request xmlns='urn:xmpp:receipts'/>"
    "<active xmlns='http://jabber.org/protocol/chatstates'/>"
    "</message>"
)
print("sent", mid)

t0 = time.time()
last = time.time()
seen = ""
while time.time() - t0 < 90:
    c.sock.settimeout(5)
    try:
        chunk = c.sock.recv(65536)
    except Exception:
        if time.time() - last > 20:
            print("idle 20s, stop")
            break
        continue
    if not chunk:
        print("closed")
        break
    text = chunk.decode("utf-8", "replace")
    seen += text
    last = time.time()
    print(f"[{time.time()-t0:6.2f}s] {text[:600]}")
    if "</message>" in seen and ("<body" in seen or "<composing" in seen):
        pass

open("artifacts/reply_stream.txt", "w", encoding="utf-8").write(seen)
print("\n--- bodies ---")
for body in re.findall(r"<body[^>]*>(.*?)</body>", seen, re.S):
    print("*", body[:500])
