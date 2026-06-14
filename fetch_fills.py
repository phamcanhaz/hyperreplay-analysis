"""Fetch 60 days of fills for wallet #3 from Hyperliquid API"""
import json, requests, sys, time
from datetime import datetime, timezone

ADDR = "0x6dbbefad3d24da625fa233c070678ab1938fcd38"
OUT = "/home/bot/hyperreplay-analysis/data/fills_60d.json"

def fetch_all(addr):
    all_fills = []
    cursor = None
    batch = 0
    while True:
        payload = {"type": "userFills", "user": addr}
        if cursor:
            payload["cursor"] = cursor
        try:
            resp = requests.post("https://api.hyperliquid.xyz/info", json=payload, timeout=20)
            data = resp.json()
        except Exception as e:
            print(f"  Error at batch {batch}: {e}")
            break
        if not data or not isinstance(data, list):
            break
        all_fills.extend(data)
        batch += 1
        print(f"  Batch {batch}: {len(data)} fills (total: {len(all_fills)})", end="")
        if len(data) < 100:
            print(" — done")
            break
        cursor = data[-1].get("time")
        # Rate limit: 10 req/s
        if batch % 10 == 0:
            time.sleep(0.5)
        print(f" cursor={cursor}")
    return all_fills

print(f"Fetching fills for {ADDR[:16]}...")
fills = fetch_all(ADDR)
print(f"\nTotal: {len(fills)} fills")

if fills:
    import os
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(fills, f, indent=2)
    print(f"Saved to {OUT}")

    times = [int(f["time"])/1000 for f in fills if f.get("time")]
    from collections import defaultdict
    by_coin = defaultdict(list)
    for f in fills:
        by_coin[f["coin"]].append(f)
    print(f"From: {datetime.fromtimestamp(min(times), tz=timezone.utc)}")
    print(f"To:   {datetime.fromtimestamp(max(times), tz=timezone.utc)}")
    print(f"Span: {(max(times)-min(times))/86400:.1f} days")
    for coin, fs in sorted(by_coin.items()):
        cp = sum(float(f.get("closedPnl", 0)) for f in fs)
        fees = sum(float(f.get("fee", 0)) for f in fs)
        print(f"  {coin}: {len(fs)} fills, net=${cp-fees:.2f}")
