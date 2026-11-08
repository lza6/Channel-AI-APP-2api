# xmpp_client.py

- md5 · function · L19-L20 — def md5(text: str) -> str
- XmppClient · class · L23-L134 — class XmppClient
- __init__ · method · L24-L29 — def __init__(self, host=HOST, port=PORT, verbose=True)
- connect · method · L32-L44 — def connect(self)
- send · method · L46-L50 — def send(self, xml)
- read_until · method · L52-L67 — def read_until(self, marker, timeout=30)
- take · method · L69-L72 — def take(self, marker="__never__")
- register_guest · method · L75-L94 — def register_guest(self, country="US", device_id=None, resource="android")
- sasl_plain · method · L96-L108 — def sasl_plain(self, username, password)
- open_stream_again · method · L110-L117 — def open_stream_again(self)
- bind · method · L119-L126 — def bind(self, resource="android")
- get_jwt · method · L128-L134 — def get_jwt(self)
