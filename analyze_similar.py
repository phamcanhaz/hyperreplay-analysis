"""
Deep analysis of wallets similar to Wallet #3
Fetches fills from API, reconstructs trades, estimates capital, active dates
"""
import json, urllib.request, time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

WALLETS = [
    ("0x6dbbefad3d24da625fa233c070678ab1938fcd38", "Wallet #3 (benchmark)"),
    ("0xb69ccb3ad06300fefe1c551e285de4a3c6a1a5da", "SHORT scalper, PnL=$6,372"),
    ("0x77a4b936667e6f10dc70b676d269e9df7deb2759", "SHORT, WR=87%, hold=720s"),
    ("0xf8d2f7cd63a40b9a2cb5c6c4e7d61c95f30302d3", "STRONG SHORT, WR=80%, PnL=$2,755"),
    ("0x8f63e3fa11518aa93ee865d5e9aae5a28e5dd74", "SHORT, PnL=$3,673"),
    ("0x2cb2e06cfbb927388a5efd3818760b5c9b813f19", "STRONG SHORT, 9 coins"),
    ("0x6e14c05d8ea92154a4ba5b8f7b84fc9c7db59f0d", "STRONG LONG, WR=94%, 48 coins"),
    ("0xb1edfeccf03f35d2268f5dc4013508a6eb52c702", "BTC scalper, PnL=$2,647"),
    ("0x5f6070a14f15b5493163f539ab4ae6594ff36738", "SHORT, hold=432s siêu tốc"),
    ("0x04dbc5c154c1491fe20cfc3a7c64a8bef1e4c605", "LONG, PnL=$2,186"),
    ("0x2ddea64b4a933d4bdb3c8030ea1a1f88e283958c", "LONG, WR=76%, hold=477s"),
]

def fetch_fills(addr, limit=500):
    url = "https://api.hyperliquid.xyz/info"
    try:
        # Try userFillsByTime (last 30 days)
        now_ms = int(time.time() * 1000)
        start_ms = now_ms - 30 * 24 * 3600_000
        data = json.dumps({"type": "userFillsByTime", "user": addr, "startTime": start_ms, "endTime": now_ms}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        if isinstance(resp, list) and len(resp) > 0:
            return resp
    except: pass
    # Fallback to userFills
    try:
        data = json.dumps({"type": "userFills", "user": addr}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        if isinstance(resp, list):
            return resp
    except: pass
    return []

def analyze_wallet(addr, label):
    fills = fetch_fills(addr)
    if not fills:
        return {"addr": addr, "label": label, "error": "No fills", "fills": 0, "trades": 0}
    
    # Sort by time
    fills.sort(key=lambda f: int(f.get("time", 0)))
    
    # Basic stats
    n = len(fills)
    coins = set(f.get("coin", "") for f in fills)
    sides = [f.get("side", "") for f in fills]
    
    # Time range
    ts0 = int(fills[0].get("time", 0))
    ts1 = int(fills[-1].get("time", 0))
    if ts0 > 1e12: ts0 //= 1000
    if ts1 > 1e12: ts1 //= 1000
    
    vn = timezone(timedelta(hours=7))
    start = datetime.fromtimestamp(ts0, tz=vn)
    end = datetime.fromtimestamp(ts1, tz=vn)
    days = max((ts1 - ts0) / 86400, 0.1)
    
    # Estimate max notional from startPosition
    max_notional = 0
    for f in fills:
        sp = abs(float(f.get("startPosition", "0")))
        px = float(f.get("px", "0"))
        if sp * px > max_notional:
            max_notional = sp * px
    
    # Estimate capital (using startPosition as proxy)
    sps = [abs(float(f.get("startPosition", "0"))) for f in fills if float(f.get("px", "0")) > 0]
    avg_notional = sum(sps[i] * float(fills[i].get("px", 0)) for i in range(len(sps))) / max(len(sps), 1)
    est_capital = max_notional / 3  # rough: 3x max pos = capital
    
    # Reconstruct trades (simplified)
    pos = {}
    trades = []
    for f in fills:
        coin = f.get("coin", "")
        if coin.startswith("@"): continue
        side = f.get("side", "")
        sz = float(f.get("sz", 0))
        px = float(f.get("px", 0))
        fee = float(f.get("fee", "0"))
        
        delta = sz if side == "B" else -sz
        old = pos.get(coin, {}).get("size", 0)
        new = old + delta
        
        reducing = (old > 0 and delta < 0) or (old < 0 and delta > 0)
        
        if reducing:
            reduce_sz = min(abs(delta), abs(old))
            entry = pos[coin].get("entry_px", px)
            pnl = (px - entry) * reduce_sz if old > 0 else (entry - px) * reduce_sz
            trades.append({"coin": coin, "pnl": pnl, "sz": reduce_sz, "ts": int(f.get("time", 0))})
        
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
    wr = wins / max(len(trades), 1) * 100
    
    # Directional bias
    long_fills = sum(1 for s in sides if s == "B")
    short_fills = sum(1 for s in sides if s == "S")
    
    return {
        "addr": addr,
        "label": label,
        "fills": n,
        "trades": len(trades),
        "wr": round(wr, 1),
        "wins": wins,
        "losses": losses,
        "pnl": round(total_pnl, 2),
        "coins": len(coins),
        "coin_list": sorted(coins),
        "avg_notional": round(avg_notional, 0),
        "max_notional": round(max_notional, 0),
        "est_capital": round(max_notional, 0),
        "start": start.strftime("%m/%d %H:%M"),
        "end": end.strftime("%m/%d %H:%M"),
        "days": round(days, 1),
        "long_pct": round(long_fills / max(n, 1) * 100, 1),
        "short_pct": round(short_fills / max(n, 1) * 100, 1),
    }

results = []
for addr, label in WALLETS:
    print(f"Fetching {addr[:10]}... {label}")
    r = analyze_wallet(addr, label)
    results.append(r)
    print(f"  Fills={r.get('fills',0)} Trades={r.get('trades',0)} PnL={r.get('pnl','?')}")
    time.sleep(0.3)

# Print comparison table
print("\n" + "=" * 180)
print("COMPARISON TABLE — WALLETS SIMILAR TO WALLET #3")
print("=" * 180)
header = f"{'#':<3} {'Address':<48} {'Fills':<6} {'Trades':<7} {'WR%':<6} {'PnL':<10} {'Capital':<10} {'Coins':<5} {'Start':<14} {'Days':<6} {'Long%':<6} {'Note':<40}"
print(header)
print("-" * 180)
for i, r in enumerate(results):
    if "error" in r:
        print(f"{i+1:<3} {r['addr'][:6]+'..'+r['addr'][-4:]:<48} {'ERROR':<6} {r['error']:<56}")
        continue
    addr_s = r['addr'][:6] + '..' + r['addr'][-4:]
    cap = f"${r['est_capital']:,.0f}" if r['est_capital'] > 0 else "?"
    start = r['start']
    note = r['label'][:38]
    print(f"{i+1:<3} {addr_s:<48} {r['fills']:<6} {r['trades']:<7} {r['wr']:<6} {r['pnl']:<10} {cap:<10} {r['coins']:<5} {start:<14} {r['days']:<6} {r['long_pct']:<6} {note:<40}")
print("=" * 180)

# Save
with open("/home/bot/hyperreplay-analysis/similar_deep_analysis.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nSaved to similar_deep_analysis.json")

# Also save readable report
with open("/home/bot/hyperreplay-analysis/similar_deep_analysis.txt", "w") as f:
    f.write("DEEP ANALYSIS — WALLETS SIMILAR TO WALLET #3\n")
    f.write(f"Generated: {datetime.now(timezone(timedelta(hours=7))).strftime('%Y-%m-%d %H:%M VN')}\n")
    f.write("=" * 120 + "\n\n")
    for r in results:
        if "error" in r:
            f.write(f"\n--- {r['addr'][:6]}..{r['addr'][-4:]} — {r['label']} ---\nERROR: {r['error']}\n")
            continue
        f.write(f"\n--- {r['addr'][:6]}..{r['addr'][-4:]} — {r['label']} ---\n")
        f.write(f"  Fills: {r['fills']} | Trades: {r['trades']} | WR: {r['wr']}% | PnL: ${r['pnl']}\n")
        f.write(f"  Capital: ${r['est_capital']:,.0f} | Coins: {r['coins']} ({', '.join(r['coin_list'])})\n")
        f.write(f"  Active: {r['start']} → {r['end']} ({r['days']} days)\n")
        f.write(f"  Direction: {r['long_pct']}% LONG / {r['short_pct']}% SHORT\n")
    f.write("\n" + "=" * 120 + "\n")

print("Done!")
