"""纯协议最小复现 —— 不装 APK、不跑模拟器、不用 Frida，只用 socket + XML 报文。

用一个人造 device_id（不是任何真机的 android_id）走完：
    游客注册 IQ -> SASL PLAIN(拿 JWT) -> bind -> vCard(拿 publictoken) -> 发消息 -> 收到 AI 回复

运行：python -X utf8 pure_protocol_demo.py [bot_username]
依赖：仅 Python 标准库。
"""
from __future__ import annotations

import base64
import hashlib
import re
import socket
import ssl
import sys
import time
import uuid

HOST = "x.siki.ai"
PORT = 443
DOH = "https://1.1.1.1/dns-query?name={host}&type=A"


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def resolve(host: str = HOST) -> str:
    """本机 DNS 偶尔把域名指到 127.0.0.1，所以用 DoH 兜底。"""
    try:
        addr = socket.getaddrinfo(host, PORT, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
        if not addr.startswith(("127.", "0.")):
            return addr
    except OSError:
        pass
    import json
    import urllib.request

    req = urllib.request.Request(DOH.format(host=host), headers={"accept": "application/dns-json"})
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    for answer in data.get("Answer") or []:
        if answer.get("type") == 1:
            return answer["data"]
    raise RuntimeError("cannot resolve " + host)


class Conn:
    def __init__(self) -> None:
        raw = socket.create_connection((resolve(), PORT), timeout=20)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.sock = ctx.wrap_socket(raw, server_hostname=HOST)
        self.buf = ""

    def open_stream(self) -> str:
        self.sock.sendall(
            ("<?xml version='1.0'?><stream:stream to='%s' xmlns='jabber:client' "
             "xmlns:stream='http://etherx.jabber.org/streams' version='1.0'>" % HOST).encode())
        return self.read_until("</stream:features>")

    def send(self, xml: str) -> None:
        print(">>", xml[:160].replace("\n", " "))
        self.sock.sendall(xml.encode())

    def read_until(self, marker: str, timeout: float = 25.0) -> str:
        deadline = time.time() + timeout
        while marker not in self.buf:
            left = deadline - time.time()
            if left <= 0:
                raise TimeoutError(marker)
            self.sock.settimeout(left)
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("stream closed")
            self.buf += chunk.decode("utf-8", "replace")
        out, self.buf = self.buf, ""
        return out


def main() -> None:
    bot = (sys.argv[1] if len(sys.argv) > 1 else "0_b2cf4ea3-b728-4112-be3d-9829d950bcea")
    bot_jid = bot if bot.endswith("@" + HOST) else f"{bot}@{HOST}"

    # ① 造一个人工 device_id —— 没有任何真机参与
    device_id = uuid.uuid4().hex
    country = "US"
    resource = f"android-1.6.1.3330-14-en-{country}-cli-{uuid.uuid4().hex[:20]}"
    nonce = str(uuid.uuid4())
    digits = "".join(ch for ch in device_id + nonce if ch.isdigit())
    username = f"tmp_{country}_{md5(f'{country}.{digits}')}".lower()
    password = md5(device_id)
    print(f"[1] device_id={device_id}  username={username}")

    conn = Conn()
    conn.open_stream()

    # ② 游客注册（SASL 之前就能发）
    reg_id = str(uuid.uuid4())
    conn.send(
        f"<iq id='{reg_id}' type='set'><query xmlns='jabber:iq:register'>"
        f"<username>{username}</username><password>{password}</password>"
        f"<verificationcode>sc:{device_id}</verificationcode>"
        f"<resource>{resource}</resource></query></iq>")
    reply = conn.read_until("</iq>")
    print("[2] 注册结果:", "成功" if "type='result'" in reply else reply[-200:])
    if "type='result'" not in reply:
        raise SystemExit("register failed")

    # ③ SASL PLAIN：success 里直接带 REST 用的 JWT
    token = base64.b64encode(f"\x00{username}\x00{password}".encode()).decode()
    conn.send(f"<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='PLAIN'>{token}</auth>")
    success = conn.read_until("<success")
    jwt = re.search(r"jwt='([^']+)'", success)
    print("[3] SASL 成功，JWT:", (jwt.group(1)[:32] + "…") if jwt else "（无）")

    # ④ 重开流 + bind
    conn.open_stream()
    bind_id = "bind-" + uuid.uuid4().hex[:8]
    conn.send(f"<iq id='{bind_id}' type='set'><bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'>"
              f"<resource>{resource}</resource></bind></iq>")
    conn.read_until("</iq>")

    # ⑤ vCard 取自己的 publictoken
    conn.send("<iq type='get' id='vc1'><vCard xmlns='vcard-temp'/></iq>")
    vcard = conn.read_until("</iq>")
    publictoken = (re.search(r"<PUBLICTOKEN>([^<]+)</PUBLICTOKEN>", vcard) or [None, ""])[1]
    print("[4] publictoken:", publictoken)
    conn.send("<presence/>")

    # ⑥ 发一条消息，等 AI 回复
    mid = str(uuid.uuid4())
    conn.send(
        f"<message id='{mid}' to='{bot_jid}' type='chat'>"
        f"<publictoken xmlns='proximity:publictoken'>{publictoken}</publictoken>"
        "<body>用一句话介绍你自己。</body>"
        "<request xmlns='urn:xmpp:receipts'/>"
        "<active xmlns='http://jabber.org/protocol/chatstates'/>"
        "<nick xmlns='http://jabber.org/protocol/nick'>Guest</nick></message>")

    started = time.time()
    bodies: list[str] = []
    while time.time() - started < 90:
        conn.sock.settimeout(3)
        try:
            chunk = conn.sock.recv(65536)
        except socket.timeout:
            continue
        if not chunk:
            break
        text = chunk.decode("utf-8", "replace")
        for ping_id in re.findall(r"<iq[^>]*id='([^']+)'[^>]*>\s*<ping ", text):
            conn.sock.sendall(f"<iq type='result' id='{ping_id}'/>".encode())
        for body in re.findall(r"<body[^>]*>(.*?)</body>", text, re.S):
            if "介绍你自己" not in body:
                bodies.append(body)
        if bodies and time.time() - started > 1:
            break

    print(f"[5] AI 回复（{time.time()-started:.1f}s）:")
    for body in bodies:
        print("    ", body[:300])


if __name__ == "__main__":
    main()
