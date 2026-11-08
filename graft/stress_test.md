# stress_test.py

- _headers · function · L22-L26 — def _headers() -> dict
- call · function · L29-L44 — def call(base: str, path: str, payload=None, timeout: float = 240.0, raw: bool = False)
- check · function · L47-L50 — def check(name: str, ok: bool, detail: str = "") -> bool
- scenario_health · function · L53-L62 — def scenario_health(base)
- scenario_catalog · function · L65-L72 — def scenario_catalog(base)
- _energy · function · L75-L78 — def _energy(balances)
- scenario_account · function · L81-L90 — def scenario_account(base)
- scenario_chat · function · L93-L117 — def scenario_chat(base, bots, turns=2)
- scenario_concurrency · function · L120-L152 — def scenario_concurrency(base, bots, concurrency)
- worker · function · L129-L138 — def worker(index)
- scenario_stream · function · L155-L175 — def scenario_stream(base, bots)
- scenario_errors · function · L178-L190 — def scenario_errors(base)
- scenario_stats · function · L193-L204 — def scenario_stats(base, expected_ok)
- main · function · L207-L231 — def main() -> int
