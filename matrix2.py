"""Try several addressing modes against several bots; report any body received."""
import json
import re
import time
import urllib.request
import uuid

from xmpp_client import XmppClient

PUB = "https://d11absfiaqzcnz.cloudfront.net"


def api(path):
    req = urllib.request.Request(PUB + path, headers={"client": "android"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


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


bots = [b for b in api("/v2/category/newexplore?limit=200")["sidekicks"] if b["config_type"] == "character"]
targets = bots[:3] + [b for b in bots if b["display_name"] in ("Stranger",)][:1]
print("bots:", [(b["display_name"], b["username"]) for b in targets])

c = XmppClient(verbose=False)
c.connect()
_, username, password, _ = c.register_guest(country="US")
c.sasl_plain(username, password)
c.open_stream_again()
c.bind("android")
me = f"{username}@x.siki.ai"
c.buf = ""
c.send("<iq type='get' id='vc1'><vCard xmlns='vcard-temp'/></iq>")
vc = drain(c, 6)
pt = re.search(r"<PUBLICTOKEN>([^<]+)</PUBLICTOKEN>", vc)
mine = pt.group(1) if pt else ""
print("me:", me, "pt:", mine)

attempts = []
for bot in targets:
    for mode in ("chat-bare", "chat-pt", "chat-bare-pt-elem"):
        attempts.append((bot, mode))

for bot, mode in attempts:
    bare = f"{bot['username']}@x.siki.ai"
    ptj = bot["publictoken"]
    to = ptj if mode == "chat-pt" else bare
    elem = f"<publictoken xmlns='proximity:publictoken'>{mine}</publictoken>" if mode.endswith("pt-elem") else ""
    c.buf = ""
    c.send(
        f"<message id='x-{uuid.uuid4().hex[:6]}' to='{to}' type='chat'>{elem}"
        "<body>hey! say hi in one short sentence</body>"
        "<request xmlns='urn:xmpp:receipts'/>"
        "<active xmlns='http://jabber.org/protocol/chatstates'/>"
        "</message>"
    )
    got = drain(c, 30)
    bodies = re.findall(r"<body[^>]*>(.*?)</body>", got, re.S)
    print(f"\n[{bot['display_name']} | {mode}] bodies={len(bodies)}")
    for b in bodies:
        print("   *", b[:300])
    if bodies:
        open("artifacts/hit.txt", "w", encoding="utf-8").write(f"{bot}\n{mode}\n{got}")
        print("HIT! saved")
        break
