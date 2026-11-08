"""Probe x.siki.ai XMPP stream features (direct + via local proxy CONNECT)."""
import socket, ssl, sys, time

HOST = "x.siki.ai"
PORT = 443
PROXY = ("127.0.0.1", 10808)

STREAM = (
    "<?xml version='1.0'?>"
    f"<stream:stream to='{HOST}' xmlns='jabber:client' "
    "xmlns:stream='http://etherx.jabber.org/streams' version='1.0'>"
)


def connect_direct():
    s = socket.create_connection((HOST, PORT), timeout=15)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx.wrap_socket(s, server_hostname=HOST)


def connect_via_proxy():
    s = socket.create_connection(PROXY, timeout=15)
    s.sendall(f"CONNECT {HOST}:{PORT} HTTP/1.1\r\nHost: {HOST}:{PORT}\r\n\r\n".encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = s.recv(4096)
        if not chunk:
            raise RuntimeError("proxy closed")
        buf += chunk
    if b" 200 " not in buf.split(b"\r\n")[0]:
        raise RuntimeError("proxy CONNECT failed: " + buf[:120].decode("latin1"))
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx.wrap_socket(s, server_hostname=HOST)


def main():
    for name, fn in (("direct", connect_direct), ("proxy", connect_via_proxy)):
        try:
            sock = fn()
            print(f"[{name}] TCP+TLS ok, cipher={sock.cipher()[0]}")
            sock.sendall(STREAM.encode())
            sock.settimeout(10)
            data = b""
            deadline = time.time() + 10
            while time.time() < deadline:
                try:
                    chunk = sock.recv(8192)
                except socket.timeout:
                    break
                if not chunk:
                    break
                data += chunk
                if b"</stream:features>" in data:
                    break
            print(f"[{name}] received {len(data)} bytes")
            print(data.decode("utf-8", "replace")[:3000])
            sock.close()
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] FAILED: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
