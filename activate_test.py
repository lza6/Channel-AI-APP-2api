"""Try activation steps: REST sidekick fetch, roster add, presence, then message."""
import json
import re
import time
import urllib.request
import uuid

from xmpp_client import XmppClient

PUB = "https://d11absfiaqzcnz.cloudfront.net"
PRIV = "https://admin-api-prod.shroom.gg"
BOT = {
    "username": "0_b2cf4ea3-b728-4112-be3d-9829d950bcea",
    "display_name": "Stranger",
    "publictoken": "pt_4bd2f3b1-8aee-4667-be77-32ae8418cf13@x.siki.ai",
    "bare_jid": "0_b2cf4ea3-b728-4112-be3d-9829d950bcea@x.siki.ai",
}


def drain(c, seconds, until_body=False):
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
        if until_body and re.search(r"<body[^>]*>", out):
            break
    return out


def rest(url, jwt, jid, data=None):
    headers = {"Authorization": f"Bearer {jwt}", "jid": jid, "client": "android",
               "Content-Type": "application/json", "Accept": "application/json"}
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers,
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()[:400].decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()[:400].decode("utf-8", "replace")


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
print("me:", me, "pt:", mine, "jwt:", len(c.jwt or ""))

print("\n[REST] get sidekick by username:", rest(f"{PRIV}/api/v2/sidekick/{BOT['username']}", c.jwt, me))
print("[REST] onboarding save:", rest(f"{PRIV}/api/v2/onboarding/save", c.jwt, me,
                                     {"username": username, "onboarding_data": []}))

print("\n[IQ] roster add")
c.buf = ""
c.send(f"<iq type='set' id='r1'><query xmlns='jabber:iq:roster'><item jid='{BOT['bare_jid']}'/></query></iq>")
print(drain(c, 6)[:300])

print("[presence] available + subscribe")
c.send("<presence/>")
c.send(f"<presence to='{BOT['bare_jid']}' type='subscribe'/>")
print(drain(c, 6)[:500])

print("\n[message] after activation")
c.buf = ""
c.send(
    f"<message id='z-{uuid.uuid4().hex[:6]}' to='{BOT['bare_jid']}' type='chat'>"
    f"<publictoken xmlns='proximity:publictoken'>{mine}</publictoken>"
    "<body>Hello! Please say hi back in one sentence.</body>"
    "<request xmlns='urn:xmpp:receipts'/>"
    "<active xmlns='http://jabber.org/protocol/chatstates'/>"
    "<nick xmlns='http://jabber.org/protocol/nick'>Guest</nick>"
    "</message>"
)
got = drain(c, 45)
print(got[:2500])
bodies = [b for b in re.findall(r"<body[^>]*>(.*?)</body>", got, re.S) if "say hi back" not in b]
print("\nREAL BODIES:", bodies[:3])
