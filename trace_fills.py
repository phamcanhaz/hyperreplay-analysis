"""Trace thực tế giao dịch ví #3 từ dữ liệu fills"""
import json
from collections import defaultdict
from datetime import datetime, timezone

with open("/home/bot/hl_copy_bot/deep_analysis.json") as f:
    fills = json.load(f)

sf = sorted(fills, key=lambda f: int(f["time"]))
pos = {}  # coin -> {"size": float, "entry_px": float, "fills": [fill]}
cycles = {}  # coin -> [cycle_index, ...]
cycle_detail = defaultdict(list)  # coin -> [(cycle#, time, side, sp, new_sp, px, sz, cp, action)]

for f in sf:
    coin = f["coin"]
    if coin.startswith("@"):
        continue
    side = f["side"]
    sz = float(f["sz"])
    px = float(f["px"])
    cp = float(f.get("closedPnl", "0"))
    fee = float(f.get("fee", "0"))
    sp = float(f.get("startPosition", "0"))
    ts = int(f["time"])
    new_sp = sp - sz if side == "A" else sp + sz

    closed = (sp > 0 and new_sp <= 0) or (sp < 0 and new_sp >= 0)
    flipping = (sp > 0 and new_sp < 0) or (sp < 0 and new_sp > 0)

    if abs(sp) < 0.001:
        # New cycle
        cycle_detail[coin].append((f"{ts}_{len(cycle_detail[coin])}", ts, f["dir"], "OPEN", sp, new_sp, px, sz, 0, 0))
        pos[coin] = {"size": new_sp, "entry": px, "entry_time": ts}
    elif closed or flipping:
        prev = pos.get(coin, {})
        prev_sz = prev.get("size", 0) if prev else 0
        cycle_detail[coin].append((f"{ts}_{len(cycle_detail[coin])}", ts, f["dir"], "CLOSE" if closed else "FLIP", sp, new_sp, px, sz, cp, fee))
        if flipping:
            pos[coin] = {"size": new_sp, "entry": px, "entry_time": ts}
        elif abs(new_sp) < 0.001:
            pos.pop(coin, None)
        else:
            pos[coin] = {"size": new_sp, "entry": prev.get("entry", 0)} if prev else None
    else:
        # Partial close or add
        prev = pos.get(coin, {})
        # Determine if adding or reducing
        reducing = (sp > 0 and side == "A") or (sp < 0 and side == "B")
        action = "REDUCE" if abs(cp) > 0.001 else "ADD"
        cycle_detail[coin].append((f"{ts}_{len(cycle_detail[coin])}", ts, f["dir"], action, sp, new_sp, px, sz, cp, fee))
        if coin in pos:
            old_sz = pos[coin]["size"]
            if action == "ADD":
                old_entry = pos[coin]["entry"]
                pos[coin]["entry"] = (old_entry * abs(old_sz) + px * sz) / (abs(old_sz) + sz)
            pos[coin]["size"] = new_sp

# Print detailed trace for each coin
for coin in sorted(cycle_detail.keys()):
    entries = sorted(cycle_detail[coin], key=lambda x: x[1])
    print(f"\n{'='*80}")
    print(f"  {coin} — {len(entries)} fills")
    print(f"{'='*80}")
    print(f"{'TIME':<18} {'DIR':<20} {'ACTION':<8} {'START_POS':>10} {'NEW_POS':>10} {'PX':>8} {'SZ':>8} {'PnL':>10} {'FEE':>8}")
    print("-" * 80)

    total_pnl = 0
    cycle_id = 0
    last_action = None
    for e in entries:
        uid, ts, dir, action, sp, new_sp, px, sz, cp, fee = e
        t = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%m/%d %H:%M:%S")
        net = cp - fee
        total_pnl += net
        print(f"{t:<18} {dir:<20} {action:<8} {sp:>10.2f} {new_sp:>10.2f} {px:>8.2f} {sz:>8.2f} {cp:>+9.2f} {fee:>8.2f}")

    # Show only first 50 entries per coin to avoid overflow
    if len(entries) > 50:
        print(f"  ... ({len(entries) - 50} more entries)")
    print(f"  Total PnL for {coin}: ${total_pnl:.2f}")
