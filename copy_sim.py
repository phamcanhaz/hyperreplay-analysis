"""Copy simulation for wallet #3 — fill-level mirroring with $50 USDT x20"""
import json, math, statistics
from collections import defaultdict
from datetime import datetime, timezone

FILLS = "/home/bot/hl_copy_bot/deep_analysis.json"
CAPITAL = 50.0
MAX_LEV = 20.0

with open(FILLS) as f:
    fills = json.load(f)

# ─── helpers ───
def fmt(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%m/%d %H:%M")

def std(vals):
    if len(vals) < 2: return 0
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m)**2 for v in vals) / (len(vals) - 1))

# ─── compute scale from target max position ───
max_targ_notional = 0
for f in fills:
    sp = abs(float(f.get("startPosition", "0")))
    px = float(f["px"])
    notional = sp * px
    if notional > max_targ_notional:
        max_targ_notional = notional

scale = min(CAPITAL * MAX_LEV / max_targ_notional, 1.0) if max_targ_notional > 0 else 0

# ─── fill-level copy ───
sf = sorted(fills, key=lambda f: int(f["time"]))
pos = {}  # coin -> {"size": float, "entry_px": float}
cash = CAPITAL
trades = []  # each close/reduce event
daily_pnl = defaultdict(float)
coin_pnl = defaultdict(float)
max_concurrent = 0

for f in sf:
    coin = f["coin"]
    if coin.startswith("@"):
        continue
    side = f["side"]
    sz = float(f["sz"])
    px = float(f["px"])
    fee = float(f.get("fee", "0"))
    ts = int(f["time"])

    our_sz = sz * scale
    if abs(our_sz) < 0.00001:
        continue

    our_delta = our_sz if side == "B" else -our_sz
    old_sz = pos.get(coin, {}).get("size", 0)
    new_sz = old_sz + our_delta

    # Is this a reduction?
    reducing = (old_sz > 0 and our_delta < 0) or (old_sz < 0 and our_delta > 0)

    pnl = 0.0
    if reducing:
        reduce_sz = min(abs(our_delta), abs(old_sz))
        entry = pos[coin]["entry_px"]
        if old_sz > 0:
            pnl = (px - entry) * reduce_sz
        else:
            pnl = (entry - px) * reduce_sz
        cash += pnl
        trades.append({"coin": coin, "pnl": round(pnl, 4), "time": ts,
                       "side": "CLOSE" if abs(new_sz) < 0.00001 else "REDUCE",
                       "sz": reduce_sz, "entry": entry, "exit": px})
        day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        daily_pnl[day] += pnl
        coin_pnl[coin] += pnl

    # Update position
    flip = reducing and (old_sz > 0 and new_sz < 0) or (old_sz < 0 and new_sz > 0)
    if flip:
        pos[coin] = {"size": new_sz, "entry_px": px}
    elif abs(new_sz) < 0.00001:
        pos.pop(coin, None)
    elif reducing:
        pos[coin]["size"] = new_sz
    else:
        if coin in pos:
            old_abs = abs(old_sz)
            pos[coin]["entry_px"] = (pos[coin]["entry_px"] * old_abs + px * abs(our_delta)) / (old_abs + abs(our_delta))
            pos[coin]["size"] = new_sz
        else:
            pos[coin] = {"size": new_sz, "entry_px": px}

    if len(pos) > max_concurrent:
        max_concurrent = len(pos)

# ─── open position PnL ───
open_pnl = 0.0
for coin, p in pos.items():
    last = [f for f in sf if f["coin"] == coin]
    if last:
        cur = float(last[-1]["px"])
        if p["size"] > 0:
            open_pnl += (cur - p["entry_px"]) * p["size"]
        else:
            open_pnl += (p["entry_px"] - cur) * abs(p["size"])

# ─── metrics ───
pnls = [t["pnl"] for t in trades]
wins = [p for p in pnls if p > 0]
losses = [p for p in pnls if p < 0]
n = len(trades)
total_pnl = sum(pnls)
wr = len(wins) / n * 100 if n else 0
avg_w = sum(wins) / len(wins) if wins else 0
avg_l = sum(losses) / len(losses) if losses else 0
pf = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else float("inf")

# Daily returns for Sharpe
if len(daily_pnl) > 1:
    daily_rets = [v / CAPITAL for v in daily_pnl.values()]
    sharpe = (statistics.mean(daily_rets) / (statistics.stdev(daily_rets) + 1e-9)) * math.sqrt(365)
else:
    sharpe = 0

# Max DD from equity curve
peak = CAPITAL
max_dd = 0
eq = CAPITAL
for t in trades:
    eq += t["pnl"]
    if eq > peak:
        peak = eq
    dd = (peak - eq) / peak * 100
    if dd > max_dd:
        max_dd = dd

# ─── REPORT ───
print("=" * 65)
print("  COPY SIMULATION — Wallet #3 (0x6dbbefad)")
print("=" * 65)
print(f"  Capital:      \${CAPITAL:.0f} USDT")
print(f"  Max leverage:  {MAX_LEV:.0f}x")
print(f"  Scale:         {scale:.6f}x (max target position \${max_targ_notional:.0f})")
print(f"  Data span:     3.6 days (Jun 10-14, 2026)")
print(f"  Total fills:   {len(fills)} ({sum(1 for f in fills if f['coin'].startswith('@'))} skipped @ coins)")
print()

print(f"  {'Trades':>12}: {n}")
print(f"  {'Realized PnL':>12}: \${total_pnl:+.2f}")
print(f"  {'Open PnL':>12}: \${open_pnl:+.2f}")
print(f"  {'Total PnL':>12}: \${total_pnl + open_pnl:+.2f}")
print(f"  {'Final cash':>12}: \${cash:.2f}")
print(f"  {'Return':>12}: {(cash - CAPITAL) / CAPITAL * 100:+.2f}%")
print(f"  {'Extrap. monthly':>12}: \${total_pnl / 3.6 * 30:+.2f}")
print()

print(f"  {'Win rate':>12}: {wr:.1f}%")
print(f"  {'Avg win':>12}: \${avg_w:.4f}")
print(f"  {'Avg loss':>12}: \${avg_l:.4f}")
print(f"  {'PF':>12}: {pf:.2f}")
print(f"  {'Sharpe':>12}: {sharpe:.2f}")
print(f"  {'Max DD':>12}: {max_dd:.2f}%")
print(f"  {'Max concurrent':>12}: {max_concurrent}")
print()

print("  Daily PnL:")
for d in sorted(daily_pnl):
    print(f"    {d}: \${daily_pnl[d]:+8.2f}")
print()

print("  Per-coin PnL:")
for coin, pnl in sorted(coin_pnl.items(), key=lambda x: abs(x[1]), reverse=True):
    cnt = sum(1 for t in trades if t["coin"] == coin)
    print(f"    {coin:>10}: \${pnl:+8.2f} ({cnt} trades)")
print()

if pos:
    print("  Open positions (residual):")
    for coin, p in sorted(pos.items()):
        last = [f for f in sf if f["coin"] == coin]
        cur = float(last[-1]["px"]) if last else 0
        print(f"    {coin}: size={p['size']:.4f} entry={p['entry_px']:.2f} cur={cur:.2f}")

# ─── trailing stop detection ───
# Check: does this wallet use trailing stops?
# Pattern: clusters of small reducing fills at increasingly better prices
print()
print("-" * 65)
print("  EXIT PATTERN ANALYSIS")
print("-" * 65)

# Group reduce/close trades per coin per position cycle
cycles = defaultdict(list)
for t in trades:
    if t["side"] in ("REDUCE", "CLOSE"):
        cycles[t["coin"]].append(t)
        
trailing_clues = []
for coin, ts in cycles.items():
    if len(ts) < 2:
        continue
    # Sort by time
    ts.sort(key=lambda x: x["time"])
    # Check if exits happen in chunks at improving prices
    prices = [(t["exit"], t["time"]) for t in ts]
    for i in range(1, len(prices)):
        px_prev, t_prev = prices[i-1]
        px_cur, t_cur = prices[i]
        delta_h = (t_cur - t_prev) / 3600000  # hours
        if delta_h > 6:  # new cycle
            continue
        px_chg = (px_cur - px_prev) / px_prev * 100
        # If we see small sells at better prices, could be trailing or TP ladder
        if len(ts) >= 3:
            trailing_clues.append((coin, px_prev, px_cur, px_chg, delta_h))

print(f"  Multi-partial exit cycles: {len(cycles)}")
scalper_exits = [t for t in trades if t["side"] == "CLOSE" and t["pnl"] > 0]
print(f"  Winning full closes: {len(scalper_exits)}")
if scalper_exits:
    holds = []
    for t in scalper_exits:
        # estimate hold from fill history
        pass
    pcts = [t["pnl"] / CAPITAL * 100 for t in scalper_exits]
    print(f"  Avg return per close: {statistics.mean(pcts):.2f}%")
    print(f"  Median return per close: {statistics.median(pcts):.2f}%")

# ─── leverage analysis ───
print()
print("-" * 65)
print("  LEVERAGE ESTIMATION")
print("-" * 65)

lev_samples = []
for f in sf:
    coin = f["coin"]
    if coin.startswith("@"):
        continue
    cp = float(f.get("closedPnl", "0"))
    if abs(cp) < 0.01:
        continue
    sp = float(f.get("startPosition", "0"))
    sz = float(f["sz"])
    px = float(f["px"])
    if abs(sp) < 0.01 or abs(sz) < 0.01:
        continue
    # Estimate entry price from PnL formula
    # closedPnl = (entry_px - exit_px) * reduce_sz  (long)
    # For partial close: reduce_sz = sz, PnL = (entry - px) * sz  (long)
    # entry = px + closedPnl / sz  (if long)
    # entry = px - closedPnl / sz  (if short)
    cp_per = cp / sz
    for est_entry in [px + cp_per, px - cp_per]:
        if est_entry <= 0 or abs(est_entry - px) / px > 0.3:
            continue
        ret = abs(px - est_entry) / est_entry * 100
        if ret < 0.001:
            continue
        notional = abs(sp) * est_entry
        pnl_ret = abs(cp) / notional * 100
        implied_lev = pnl_ret / ret
        if 0.5 <= implied_lev <= 50:
            lev_samples.append(implied_lev)
            break

if lev_samples:
    print(f"  Samples: {len(lev_samples)}")
    print(f"  Median:  {statistics.median(lev_samples):.1f}x")
    print(f"  Mean:    {statistics.mean(lev_samples):.1f}x")
    print(f"  Range:   {min(lev_samples):.1f}x - {max(lev_samples):.1f}x")
    for lo, hi in [(0, 2), (2, 5), (5, 10), (10, 20), (20, 50)]:
        cnt = sum(1 for l in lev_samples if lo <= l < hi)
        if cnt:
            print(f"    {lo}x-{hi}x: {cnt} ({cnt/len(lev_samples)*100:.0f}%)")

# ─── concurrent analysis ───
print()
print("-" * 65)
print("  CONCURRENT POSITION ANALYSIS")
print("-" * 65)
# Track position count over time from source fills
src_pos = {}
conc_over_time = []
for f in sf:
    coin = f["coin"]
    if coin.startswith("@"):
        continue
    sp = float(f.get("startPosition", "0"))
    sz = float(f["sz"])
    side = f["side"]
    new_sp = sp - sz if side == "A" else sp + sz
    if abs(sp) < 0.01 and abs(new_sp) > 0.01:
        src_pos[coin] = True
    elif abs(new_sp) < 0.01:
        src_pos.pop(coin, None)
    else:
        src_pos[coin] = True
    conc_over_time.append((int(f["time"]), len(src_pos)))

if conc_over_time:
    max_conc_src = max(c for _, c in conc_over_time)
    avg_conc_src = sum(c for _, c in conc_over_time) / len(conc_over_time)
    print(f"  Max target concurrent: {max_conc_src}")
    print(f"  Avg target concurrent: {avg_conc_src:.1f}")

# Coin activity periods
print()
print("  Active coins:")
coin_first_last = {}
for f in sf:
    if f["coin"].startswith("@"):
        continue
    if f["coin"] not in coin_first_last:
        coin_first_last[f["coin"]] = [int(f["time"]), int(f["time"])]
    else:
        if int(f["time"]) < coin_first_last[f["coin"]][0]:
            coin_first_last[f["coin"]][0] = int(f["time"])
        if int(f["time"]) > coin_first_last[f["coin"]][1]:
            coin_first_last[f["coin"]][1] = int(f["time"])

for coin, (start, end) in sorted(coin_first_last.items()):
    span_h = (end - start) / 3600000
    cnt = sum(1 for f in sf if f["coin"] == coin and not f["coin"].startswith("@"))
    fills_day = cnt / max(span_h / 24, 0.01)
    print(f"  {coin:>10}: {cnt:>4} fills over {span_h:.0f}h ({fills_day:.0f}/day)")
