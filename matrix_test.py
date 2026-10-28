"""Matrix test: which addressing/naming produces an AI reply?"""
import json
import re
import time
import urllib.request
import uuid

from xmpp_client import XmppClient

PUB = "https://d11absfiaqzcnz.cloudfront.net"


def api(path):
    req = urllib.request.Request(PUB + path, headers={"client": "android"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        return {"__err__": str(exc), "__body__": getattr(exc, "read", lambda: b"")()[:300].decode("utf-8", "replace")}


def watch(c, seconds):
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
print("me:", me)

print("\n### /welcome?username=")
w = api(f"/welcome?username={username}")
print(json.dumps(w)[:800])

bot_full = api("/v2/category/newexplore?limit=3")["sidekicks"][0]
chat_bot = api("/v2/category/newexplore?limit=200")["sidekicks"]
chat_bot = [b for b in chat_bot if b["config_type"] == "character"][0]
print("\nchat bot:", chat_bot["display_name"], chat_bot["username"], chat_bot["publictoken"])

bot_jid = f"{chat_bot['username']}@x.siki.ai"
bot_pt = chat_bot["publictoken"]
body = "Hi! Introduce yourself in one short sentence please."

vars = [
    ("chat-to-barejid", bot_jid, "chat"),
    ("publicchat-to-pt", bot_pt, "publicchat"),
    ("systemchat-to-barejid", bot_jid, "systemchat"),
]
for name, to, mtype in vars:
    c.buf = ""
    mid = f"{name[:4]}-{uuid.uuid4().hex[:6]}"
    c.send(
        f"<message id='{mid}' to='{to}' type='{mtype}'>"
        f"<body>{body}</body>"
        "<request xmlns='urn:xmpp:receipts'/>"
        "<active xmlns='http://jabber.org/protocol/chatstates'/>"
        "</message>"
    )
    got = watch(c, 40)
    bodies = re.findall(r"<body[^>]*>(.*?)</body>", got, re.S)
    print(f"\n### {name} to={to} -> bodies={bodies[:3]}")
    print(got[:1200])
    if bodies:
        break
