"""Deep analysis for wallet 0x6dbbefad3d24da625fa233c070678ab1938fcd38"""
import json, requests, sys
from collections import defaultdict
from datetime import datetime, timezone

ADDR = "0x6dbbefad3d24da625fa233c070678ab1938fcd38"

def fetch_fills(addr: str, start_time: int = 0) -> list[dict]:
    all_fills = []
    cursor = None
    while True:
        payload = {"type": "userFills", "user": addr}
        if cursor:
            payload["cursor"] = cursor
        resp = requests.post("https://api.hyperliquid.xyz/info", json=payload, timeout=15)
        data = resp.json()
        if not data:
            break
        all_fills.extend(data)
        if len(data) < 100:
            break
        cursor = data[-1].get("time")
    return all_fills

fills = fetch_fills(ADDR)
print(f"Total fills: {len(fills)}")

# Save raw data
with open("/home/bot/hl_copy_bot/deep_analysis.json", "w") as f:
    json.dump(fills, f, indent=2)

# Summary
total_cp = sum(float(f.get("closedPnl", 0)) for f in fills)
total_fees = sum(float(f.get("fee", 0)) for f in fills)
print(f"Total closedPnl: ${total_cp:.2f}")
print(f"Total fees: ${total_fees:.2f}")
print(f"Net: ${total_cp - total_fees:.2f}")

# Per coin
by_coin = defaultdict(list)
for f in fills:
    by_coin[f["coin"]].append(f)

print(f"\n{'Coin':>12} {'Fills':>6} {'Orders':>6} {'FillPnL':>10} {'Fees':>8} {'Net':>10}")
print("-" * 56)
for coin in sorted(by_coin.keys()):
    fs = by_coin[coin]
    orders = len(set(f["oid"] for f in fs))
    cp = sum(float(f.get("closedPnl", 0)) for f in fs)
    fees = sum(float(f.get("fee", 0)) for f in fs)
    print(f"{coin:>12} {len(fs):>6} {orders:>6} ${cp:>+8.2f} ${fees:>7.2f} ${cp-fees:>+8.2f}")

# Time range
times = [int(f["time"]) / 1000 for f in fills if f.get("time")]
if times:
    print(f"\nFrom: {datetime.fromtimestamp(min(times), tz=timezone.utc)}")
    print(f"To:   {datetime.fromtimestamp(max(times), tz=timezone.utc)}")
    print(f"Span: {(max(times)-min(times))/86400:.1f} days")

# Per day
by_day = defaultdict(list)
for f in fills:
    day = datetime.fromtimestamp(int(f["time"])/1000, tz=timezone.utc).strftime("%Y-%m-%d")
    by_day[day].append(f)
print(f"\n{'Day':<12} {'Fills':>6} {'Orders':>6} {'FillPnL':>10} {'Fees':>8} {'Net':>10}")
print("-" * 56)
for day in sorted(by_day.keys()):
    fs = by_day[day]
    orders = len(set(f["oid"] for f in fs))
    cp = sum(float(f.get("closedPnl", 0)) for f in fs)
    fees = sum(float(f.get("fee", 0)) for f in fs)
    print(f"{day:<12} {len(fs):>6} {orders:>6} ${cp:>+8.2f} ${fees:>7.2f} ${cp-fees:>+8.2f}")

print(f"\nSaved to deep_analysis.json")
