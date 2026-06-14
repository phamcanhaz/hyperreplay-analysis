"""
Deep analysis v2 — wallets similar to Wallet #3
Uses correct addresses, fetches fills via API, computes metrics
"""
import json, urllib.request, time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

VN = timezone(timedelta(hours=7))

# Wallets with available fill data
WALLETS = [
    ("0x6dbbefad3d24da625fa233c070678ab1938fcd38", "Wallet #3 — benchmark"),
    ("0xb69ccb3ad06300fefe1c551e285de4a3c6a1a5da", "SHORT scalper, PnL=$6,372"),
    ("0x77a44b15d5ad00fc7b8d6fea6ec1fa61a3be2759", "SHORT, WR=87%, hold=720s ⏱"),
    ("0xf8d2fded7432cd648200553dfcbca504aa3402d3", "STRONG SHORT, WR=80%, PnL=$2,755"),
    ("0x6e1402f1a16642da68336205c2231c7a45dc9f0d", "STRONG LONG, WR=94%, 48 coins"),
    ("0xb1edfeccf03f35d2268f5dc4013508a6eb52c702", "BTC scalper, PnL=$2,647"),
]

def fetch_fills(addr):
    url = "https://api.hyperliquid.xyz/info"
    data = json.dumps({"type": "userFills", "user": addr}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        return resp if isinstance(resp, list) else []
    except:
        return []

def analyze(addr, label):
    fills = fetch_fills(addr)
    if not fills:
        return {"addr": addr, "label": label, "error": "No fills from API"}

    fills.sort(key=lambda f: int(f.get("time", 0)))
    n = len(fills)

    # Time range
    def ts_to_dt(ts):
        if ts > 1e12: ts //= 1000
        return datetime.fromtimestamp(ts, tz=VN)

    t0 = int(fills[0]["time"])
    t1 = int(fills[-1]["time"])
    days = max((t1 - t0) / 86400 / 1000, 0.1)
    start_str = ts_to_dt(t0).strftime("%m/%d %H:%M")
    end_str = ts_to_dt(t1).strftime("%m/%d %H:%M")

    # Coins
    coins_set = set(f.get("coin", "") for f in fills if not f.get("coin", "").startswith("@"))
    coins_list = sorted(coins_set)

    # Directional count
    long_fills = sum(1 for f in fills if f.get("side") == "B")
    short_fills = sum(1 for f in fills if f.get("side") == "A")
    long_pct = round(long_fills / n * 100, 1)

    # Max notional (capital estimate)
    max_notional = 0
    total_notional = 0
    notional_count = 0
    for f in fills:
        sp = abs(float(f.get("startPosition", "0")))
        px = float(f.get("px", "0"))
        ntl = sp * px
        if ntl > max_notional:
            max_notional = ntl
        if sp > 0:
            total_notional += ntl
            notional_count += 1
    avg_notional = total_notional / max(notional_count, 1)
    est_capital = int(max_notional)

    # Reconstruct trades
    pos = {}
    trades = []
    for f in fills:
        coin = f.get("coin", "")
        if coin.startswith("@"): continue
        side = f.get("side", "")
        sz = float(f.get("sz", 0))
        px = float(f.get("px", 0))

        delta = sz if side == "B" else -sz
        old = pos.get(coin, {}).get("size", 0)
        new = old + delta
        reducing = (old > 0 and delta < 0) or (old < 0 and delta > 0)

        if reducing:
            reduce_sz = min(abs(delta), abs(old))
            entry = pos[coin].get("entry_px", px)
            pnl = (px - entry) * reduce_sz if old > 0 else (entry - px) * reduce_sz
            trades.append({"coin": coin, "pnl": pnl, "ts": int(f.get("time", 0))})

        if abs(new) < 0.00001:
            pos.pop(coin, None)
        elif reducing:
            pos[coin]["size"] = new
        else:
            if coin in pos:
                old_abs = abs(old)
                pos[coin]["entry_px"] = (pos[coin]["entry_px"] * old_abs + px * abs(delta)) / (old_abs + abs(delta))
                pos[coin]["size"] = new
            else:
                pos[coin] = {"size": new, "entry_px": px}

    total_pnl = sum(t["pnl"] for t in trades)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] <= 0)
    wr = round(wins / max(len(trades), 1) * 100, 1)

    # PnL per coin
    coin_pnl = defaultdict(float)
    for t in trades:
        coin_pnl[t["coin"]] += t["pnl"]

    # Hold time estimation: look at trade clusters
    coin_holds = defaultdict(list)
    for i, f in enumerate(fills):
        coin = f.get("coin", "")
        if coin.startswith("@"): continue
        side = f.get("side", "")
        t = int(f.get("time", 0))
        coin_holds[coin].append((t, side))

    return {
        "addr": addr,
        "label": label,
        "fills": n,
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "wr": wr,
        "total_pnl": round(total_pnl, 2),
        "est_capital": est_capital,
        "coins": len(coins_list),
        "coin_list": coins_list,
        "coin_pnl": {k: round(v, 2) for k, v in sorted(coin_pnl.items(), key=lambda x: -abs(x[1]))},
        "long_pct": long_pct,
        "short_pct": round(short_fills / n * 100, 1),
        "start": start_str,
        "end": end_str,
        "days": round(days, 1),
        "avg_notional": round(avg_notional, 0),
        "max_notional": round(max_notional, 0),
    }

results = []
for addr, label in WALLETS:
    print(f"  {addr[:10]}... ", end="", flush=True)
    r = analyze(addr, label)
    results.append(r)
    print(f"fills={r.get('fills',0)} trades={r.get('trades',0)} PnL={r.get('total_pnl','?')}")
    time.sleep(0.3)

# Print comparison
print()
print("=" * 170)
print("COMPARISON: WALLETS SIMILAR TO WALLET #3")
print("=" * 170)
h = f"{'#':<3} {'Address':<48} {'Fills':<6} {'T':<5} {'WR%':<5} {'PnL':<10} {'Capital':<12} {'C':<3} {'Long%':<6} {'Days':<5} {'Start':<13}"
print(h)
print("-" * 170)
for i, r in enumerate(results):
    if "error" in r:
        print(f"{i+1:<3} {r['addr'][:6]+'..'+r['addr'][-4:]:<48} ERROR")
        continue
    a = r['addr'][:6] + '..' + r['addr'][-4:]
    cap = f"${r['est_capital']:>9,.0f}" if r['est_capital'] else "?"
    print(f"{i+1:<3} {a:<48} {r['fills']:<6} {r['trades']:<5} {r['wr']:<5} {r['total_pnl']:<10} {cap:<12} {r['coins']:<3} {r['long_pct']:<6} {r['days']:<5} {r['start']:<13}")
print("=" * 170)

# Detailed per-wallet
for r in results:
    if "error" in r:
        continue
    print()
    print(f"── {r['addr'][:6]}..{r['addr'][-4:]} — {r['label']} ──")
    print(f"  Fills: {r['fills']} | Trades: {r['trades']} | WR: {r['wr']}% | PnL: ${r['total_pnl']}")
    print(f"  Capital ~${r['est_capital']:,} | Coins: {r['coins']} ({', '.join(r['coin_list'][:8])}{'...' if r['coins'] > 8 else ''})")
    print(f"  Period: {r['start']} → {r['end']} ({r['days']} days)")
    print(f"  Direction: {r['long_pct']}% LONG / {r['short_pct']}% SHORT")
    print(f"  Avg Notional: ${r['avg_notional']:,.0f} | Max Notional: ${r['max_notional']:,.0f}")
    top_coins = list(r['coin_pnl'].items())[:5]
    print(f"  PnL by coin: {' | '.join(f'{c}: ${v}' for c,v in top_coins)}")

# Save
with open("/home/bot/hyperreplay-analysis/similar_deep_v2.json", "w") as f:
    json.dump(results, f, indent=2, default=str)

print("\nSaved to similar_deep_v2.json")
