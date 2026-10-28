"""Minimal XMPP client for x.siki.ai (Channel app backend).

Flow mirrored from the APK (_legacy/xmpp/*.java):
  TLS(443, direct TLS) -> guest registration IQ (jabber:iq:register) -> SASL PLAIN
  -> bind -> IQ proximity:jwt:token -> message to bot JID
"""
import base64
import hashlib
import socket
import ssl
import time
import uuid

HOST = "x.siki.ai"
PORT = 443
NS_STREAM = "http://etherx.jabber.org/streams"


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


class XmppClient:
    def __init__(self, host=HOST, port=PORT, verbose=True):
        self.host = host
        self.port = port
        self.verbose = verbose
        self.buf = ""
        self.log = []

    # ---------------- transport ----------------
    def connect(self):
        raw = socket.create_connection((self.host, self.port), timeout=20)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.sock = ctx.wrap_socket(raw, server_hostname=self.host)
        self.sock.settimeout(30)
        self.send(
            "<?xml version='1.0'?>"
            f"<stream:stream to='{self.host}' xmlns='jabber:client' "
            f"xmlns:stream='{NS_STREAM}' version='1.0'>"
        )
        return self.read_until("</stream:features>", timeout=15)

    def send(self, xml):
        self.log.append((">>", xml))
        if self.verbose:
            print(">>", xml[:400])
        self.sock.sendall(xml.encode())

    def read_until(self, marker, timeout=30):
        deadline = time.time() + timeout
        while marker not in self.buf:
            left = deadline - time.time()
            if left <= 0:
                raise TimeoutError(f"timeout waiting {marker!r}; buffer={self.buf[-800:]}")
            self.sock.settimeout(left)
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("stream closed; buffer=" + self.buf[-800:])
            text = chunk.decode("utf-8", "replace")
            self.buf += text
            self.log.append(("<<", text))
            if self.verbose:
                print("<<", text[:400])
        return self.buf

    def take(self, marker="__never__"):
        """Return and clear the buffer (optionally up to marker)."""
        out, self.buf = self.buf, ""
        return out

    # ---------------- protocol ----------------
    def register_guest(self, country="US", device_id=None, resource="android"):
        """Guest in-band registration, per RegistrationActivity.initGuestRegistration()."""
        device_id = device_id or uuid.uuid4().hex
        nonce = str(uuid.uuid4())
        formatted = f"{country}.{''.join(ch for ch in (device_id + nonce) if ch.isdigit())}"
        username = f"tmp_{country}_{md5(formatted)}".lower()
        # device_id + uuid may contain letters; app keeps only digits via Regex("[^\\d.]")
        password = md5(device_id)
        iq_id = str(uuid.uuid4())
        packet = (
            f"<iq id='{iq_id}' type='set'>"
            "<query xmlns='jabber:iq:register'>"
            f"<username>{username}</username>"
            f"<password>{password}</password>"
            f"<verificationcode>sc:{device_id}</verificationcode>"
            f"<resource>{resource}</resource>"
            "</query></iq>"
        )
        self.send(packet)
        return iq_id, username, password, self.read_until("</iq>", timeout=25)

    def sasl_plain(self, username, password):
        """SASL PLAIN; the success element may carry the API JWT in a `jwt` attribute."""
        import re

        token = base64.b64encode(f"\x00{username}\x00{password}".encode()).decode()
        self.buf = ""
        self.send(f"<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='PLAIN'>{token}</auth>")
        self.read_until("<success", timeout=20)
        match = re.search(r"jwt='([^']+)'", self.buf)
        self.jwt = match.group(1) if match else None
        if self.verbose and self.jwt:
            print("<< jwt:", self.jwt[:60], "...")
        return self.buf

    def open_stream_again(self):
        self.buf = ""
        self.send(
            "<?xml version='1.0'?>"
            f"<stream:stream to='{self.host}' xmlns='jabber:client' "
            f"xmlns:stream='{NS_STREAM}' version='1.0'>"
        )
        return self.read_until("</stream:features>", timeout=15)

    def bind(self, resource="android"):
        iq_id = "bind-" + uuid.uuid4().hex[:8]
        self.buf = ""
        self.send(
            f"<iq id='{iq_id}' type='set'><bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'>"
            f"<resource>{resource}</resource></bind></iq>"
        )
        return self.read_until(f"id='{iq_id}'", timeout=20)

    def get_jwt(self):
        iq_id = "jwt-" + uuid.uuid4().hex[:8]
        self.buf = ""
        self.send(
            f"<iq type='get' id='{iq_id}'><query xmlns='proximity:jwt:token'/></iq>"
        )
        return self.read_until(f"id='{iq_id}'", timeout=20)


if __name__ == "__main__":
    c = XmppClient()
    try:
        print("=== stream features ===")
        c.connect()
        print("\n=== guest registration ===")
        iq_id, username, password, resp = c.register_guest(country="US")
        print("\nRESULT:", resp[-600:])
        print("username:", username, "password:", password)
    finally:
        try:
            c.sock.close()
        except Exception:
            pass
