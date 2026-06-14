#!/usr/bin/env python3
"""
Deep analysis tool for HyperLiquid wallets.
Usage: python3 deep_analyze.py <wallet_address> [--days N]
"""
import json, sys
from collections import defaultdict, OrderedDict
from datetime import datetime, timezone, timedelta

VN = timezone(timedelta(hours=7))

API = "https://api.hyperliquid.xyz/info"

def fetch_fills(addr: str, days: int | None = None) -> list[dict]:
    import urllib.request
    if days:
        start = int((datetime.now(timezone.utc).timestamp() - days * 86400) * 1000)
        payload = json.dumps({"type": "userFillsByTime", "user": addr, "startTime": start}).encode()
    else:
        payload = json.dumps({"type": "userFills", "user": addr}).encode()
    req = urllib.request.Request(API, data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read())

def ts_dt(ts: int) -> datetime:
    if ts > 1e12: ts //= 1000
    return datetime.fromtimestamp(ts, tz=VN)

def ts_str(ts: int) -> str:
    return ts_dt(ts).strftime("%Y-%m-%d %H:%M:%S")

def reconstruct_trades(fills: list[dict]):
    """
    Trade reconstruction matching analyzer_deep.py validation algorithm.

    1. Process fills chronologically
    2. Track position per coin using start_position + delta
    3. Record trade ONLY when position FULLY closes (goes to 0 or flips)
    4. PnL per trade = closedPnl - fee of the closing fill (NOT accumulated)
    5. Track open positions for entries and weighted avg entry price
    """
    fills.sort(key=lambda x: int(x.get("time", 0)))

    # OID-reduce count (secondary metric)
    oid_groups = OrderedDict()
    for f in fills:
        oid_groups.setdefault(str(f.get("oid", "")), []).append(f)
    oid_reduces = 0
    for oid, grp in oid_groups.items():
        sp = float(grp[0].get("startPosition", 0))
        delta = sum((1 if f.get("side") == "B" else -1) * float(f.get("sz", 0)) for f in grp)
        if abs(sp) > 0.00001 and sp * delta < 0:
            oid_reduces += 1

    # Trade reconstruction (exact match with analyzer_deep.py)
    trades = []
    open_pos: dict[str, dict] = {}

    for f in fills:
        coin = f.get("coin", "")
        prev_sz = float(f.get("startPosition", 0))
        sz = float(f.get("sz", 0))
        side = f.get("side", "")
        delta = -sz if side == "A" else sz
        new_sz = prev_sz + delta
        closed = (prev_sz > 0 and new_sz <= 0) or (prev_sz < 0 and new_sz >= 0)
        cp = float(f.get("closedPnl", 0))
        fee = float(f.get("fee", 0))
        ts = int(f.get("time", 0)) // 1000
        px = float(f.get("px", 0))

        if abs(prev_sz) < 0.00001:
            # Opening a new position
            open_pos[coin] = {"coin": coin, "size": new_sz, "entry_px": px, "entry_time": ts}

        elif closed:
            ot = open_pos.get(coin)
            if ot:
                direction = "LONG" if ot["size"] > 0 else "SHORT"
                net_pnl = cp - fee
                hold = ts - ot["entry_time"]
                trades.append({
                    "coin": coin, "dir": direction,
                    "entry_px": ot["entry_px"], "exit_px": px,
                    "entry_ts": ot["entry_time"], "exit_ts": ts,
                    "hold_s": hold, "pnl": round(net_pnl, 2),
                })
            if abs(new_sz) > 0.00001:
                # Flip: start new position in opposite direction
                open_pos[coin] = {"coin": coin, "size": new_sz, "entry_px": px, "entry_time": ts}
            else:
                open_pos.pop(coin, None)

        else:
            ot = open_pos.get(coin)
            if ot:
                ot["size"] = new_sz
                adding = (prev_sz > 0 and side == "B") or (prev_sz < 0 and side == "A")
                if adding:
                    old_abs = abs(prev_sz)
                    ot["entry_px"] = (ot["entry_px"] * old_abs + px * sz) / (old_abs + sz)

    # Open positions at end
    last_ts = int(fills[-1]["time"]) if fills else 0
    for coin, ot in open_pos.items():
        if abs(ot["size"]) > 0.00001:
            direction = "LONG" if ot["size"] > 0 else "SHORT"
            trades.append({
                "coin": coin, "dir": direction,
                "entry_px": ot["entry_px"], "exit_px": 0,
                "entry_ts": ot["entry_time"], "exit_ts": last_ts,
                "hold_s": last_ts - ot["entry_time"], "pnl": 0, "open": True,
            })

    return trades, oid_reduces


def analyze(addr: str, days: int | None = None):
    print("=" * 72)
    print(f"  PHAN TICH SÂU — HyperLiquid Wallet")
    print(f"  {addr}")
    print("=" * 72)

    fills = fetch_fills(addr, days)
    n = len(fills)
    print(f"\n  Fills: {n}")
    if n == 0:
        print("  Không có dữ liệu.")
        return

    t0 = int(fills[-1]["time"])
    t1 = int(fills[0]["time"])
    days_span = max((t1 - t0) / 86400 / 1000, 0.1)
    print(f"  Period: {ts_str(t0)} -> {ts_str(t1)} ({days_span:.1f} days)")

    total_closed_pnl = sum(float(f.get("closedPnl", 0)) for f in fills)
    trades, oid_reduces = reconstruct_trades(fills)

    all_trades = trades
    n_trades = len(all_trades)
    total_pnl = sum(t["pnl"] for t in all_trades)
    wins = [t for t in all_trades if t["pnl"] > 0]
    losses = [t for t in all_trades if t["pnl"] <= 0]
    wr = len(wins) / max(n_trades, 1) * 100
    gp = sum(t["pnl"] for t in wins)
    gl = abs(sum(t["pnl"] for t in losses))
    pf = gp / max(gl, 0.01)
    avg_win = gp / max(len(wins), 1)
    avg_loss = gl / max(len(losses), 1)

    coins = sorted(set(t["coin"] for t in all_trades))
    peak_hour = primary = None

    print(f"\n  === I. TỔNG QUAN ===")
    print(f"  Coins: {len(coins)} -> {coins}")
    print(f"  Trades (position cycles): {n_trades}")
    print(f"  OID reduce events: {oid_reduces}")
    print(f"  Win Rate: {wr:.1f}% ({len(wins)}W / {len(losses)}L)")
    print(f"  Total PnL (trades): ${total_pnl:+.2f}")
    print(f"  Total closedPnl (all fills): ${total_closed_pnl:+.2f}")
    print(f"  Gross Profit: ${gp:.2f}")
    print(f"  Gross Loss: ${gl:.2f}")
    print(f"  Profit Factor: {pf:.1f}")
    print(f"  Avg Win: ${avg_win:.2f}")
    print(f"  Avg Loss: ${avg_loss:.2f}")
    print(f"  Win/Loss Ratio: {abs(avg_win/avg_loss) if avg_loss else 0:.2f}")

    coin_trades: dict[str, list[dict]] = defaultdict(list)
    for t in all_trades:
        coin_trades[t["coin"]].append(t)

    print(f"\n  === II. PER-COIN BREAKDOWN ===")
    hdr = f"  {'Coin':<12} {'Trades':<7} {'WR%':<6} {'PnL':<12} {'Long':<6} {'Short':<6} {'L%':<5} {'Weight':<7}"
    print(hdr)
    print(f"  {'-'*len(hdr)}")
    for coin in coins:
        ts = coin_trades[coin]
        ct_wins = [t for t in ts if t["pnl"] > 0]
        ct_wr = len(ct_wins) / max(len(ts), 1) * 100
        ct_pnl = sum(t["pnl"] for t in ts)
        long_t = sum(1 for t in ts if t["dir"] == "LONG")
        short_t = sum(1 for t in ts if t["dir"] == "SHORT")
        ct_weight = len(ts) / max(n_trades, 1) * 100
        long_pct = long_t / max(len(ts), 1) * 100
        print(f"  {coin:<12} {len(ts):<7} {ct_wr:<6.1f} ${ct_pnl:<+9.2f} {long_t:<6} {short_t:<6} {long_pct:<5.0f} {ct_weight:<7.0f}")

    print(f"\n  === III. DIRECTIONAL ===")
    long_trades = [t for t in all_trades if t["dir"] == "LONG"]
    short_trades = [t for t in all_trades if t["dir"] == "SHORT"]
    l_wr = l_pnl = l_avg = s_wr = s_pnl = s_avg = 0.0
    print(f"  LONG:  {len(long_trades)} trades")
    if long_trades:
        l_w = [t for t in long_trades if t["pnl"] > 0]
        l_pnl = sum(t["pnl"] for t in long_trades)
        l_wr = len(l_w) / max(len(long_trades), 1) * 100
        l_avg = l_pnl / max(len(long_trades), 1)
        print(f"    WR={l_wr:.1f}%  PnL=${l_pnl:+.2f}  Avg=${l_avg:+.2f}")
    print(f"  SHORT: {len(short_trades)} trades")
    if short_trades:
        s_w = [t for t in short_trades if t["pnl"] > 0]
        s_pnl = sum(t["pnl"] for t in short_trades)
        s_wr = len(s_w) / max(len(short_trades), 1) * 100
        s_avg = s_pnl / max(len(short_trades), 1)
        print(f"    WR={s_wr:.1f}%  PnL=${s_pnl:+.2f}  Avg=${s_avg:+.2f}")

    holds = [t["hold_s"] for t in all_trades if t["hold_s"] > 0 and not t.get("open")]
    if holds:
        holds.sort()
        print(f"\n  === IV. HOLD TIME ===")
        print(f"  Min:    {holds[0]:.0f}s ({holds[0]/60:.1f}ph)")
        print(f"  P25:    {holds[len(holds)//4]:.0f}s ({holds[len(holds)//4]/60:.1f}ph)")
        print(f"  Median: {holds[len(holds)//2]:.0f}s ({holds[len(holds)//2]/60:.1f}ph)")
        print(f"  P75:    {holds[3*len(holds)//4]:.0f}s ({holds[3*len(holds)//4]/60:.1f}ph)")
        print(f"  Max:    {holds[-1]:.0f}s ({holds[-1]/60:.1f}ph)")
        print(f"  Avg:    {sum(holds)/len(holds):.0f}s ({sum(holds)/len(holds)/60:.1f}ph)")

    trades_by_day = defaultdict(list)
    for t in all_trades:
        day = ts_dt(t.get("exit_ts", t.get("entry_ts", 0))).strftime("%Y-%m-%d")
        trades_by_day[day].append(t)

    print(f"\n  === V. TRADES PER DAY ===")
    active_days = len(trades_by_day)
    avg_per_day = n_trades / max(active_days, 1)
    print(f"  Active days: {active_days}")
    print(f"  Avg trades/day: {avg_per_day:.1f}")
    best_day = worst_day = ""
    best_pnl = -float("inf"); worst_pnl = float("inf")
    for day in sorted(trades_by_day.keys()):
        ts = trades_by_day[day]
        pnl = sum(t["pnl"] for t in ts)
        wins_d = sum(1 for t in ts if t["pnl"] > 0)
        wr_d = wins_d / max(len(ts), 1) * 100
        if pnl > best_pnl: best_pnl = pnl; best_day = day
        if pnl < worst_pnl: worst_pnl = pnl; worst_day = day
        print(f"    {day}: {len(ts):>3} trades  PnL=${pnl:<+9.2f}  WR={wr_d:.0f}%")
    print(f"  Best day:  {best_day} ${best_pnl:+.2f}")
    print(f"  Worst day: {worst_day} ${worst_pnl:+.2f}")

    losing_streak = max_losing_streak = 0
    for day in sorted(trades_by_day.keys()):
        pnl = sum(t["pnl"] for t in trades_by_day[day])
        if pnl < 0:
            losing_streak += 1
            max_losing_streak = max(max_losing_streak, losing_streak)
        else:
            losing_streak = 0
    print(f"  Max losing streak: {max_losing_streak} days")
    winning_streak = max_winning_streak = 0
    for day in sorted(trades_by_day.keys()):
        pnl = sum(t["pnl"] for t in trades_by_day[day])
        if pnl >= 0:
            winning_streak += 1
            max_winning_streak = max(max_winning_streak, winning_streak)
        else:
            winning_streak = 0
    print(f"  Max winning streak: {max_winning_streak} days")

    hourly = defaultdict(int)
    for f in fills:
        t = int(f.get("time", 0))
        if t > 1e12: t //= 1000
        h = datetime.fromtimestamp(t, tz=VN).hour
        hourly[h] += 1

    print(f"\n  === VI. HOURLY (VN time) ===")
    if hourly:
        max_count = max(hourly.values())
        peak_hour = sorted(hourly.items(), key=lambda x: -x[1])[0][0]
        for h in sorted(hourly):
            bar_len = int(hourly[h] / max(max_count, 1) * 30)
            print(f"  {h:02d}:00 {'█' * bar_len:<30} {hourly[h]}")
        print(f"  Peak hour: {peak_hour}:00 VN")
        asia = sum(hourly.get(h, 0) for h in range(7, 16))
        europe = sum(hourly.get(h, 0) for h in range(13, 22))
        us = sum(hourly.get(h, 0) for h in range(19, 24)) + sum(hourly.get(h, 0) for h in range(0, 5))
        primary = sorted({"ASIA": asia, "EUROPE": europe, "US": us}.items(), key=lambda x: -x[1])[0][0]
        print(f"  Primary session: {primary}")

    max_notional = 0; total_notional = 0; nc = 0
    for f in fills:
        sp = abs(float(f.get("startPosition", "0")))
        px = float(f.get("px", 0))
        ntl = sp * px
        if ntl > max_notional: max_notional = ntl
        if sp > 0: total_notional += ntl; nc += 1
    avg_notional = total_notional / max(nc, 1) if nc else 0
    est_capital = max_notional / 3 if max_notional > 0 else 0
    est_leverage = max_notional / max(est_capital, 1) if est_capital > 0 else 0

    print(f"\n  === VII. CAPITAL ===")
    print(f"  Avg position notional: ${avg_notional:,.0f}")
    print(f"  Max position notional: ${max_notional:,.0f}")
    print(f"  Est capital (max/3):   ${est_capital:,.0f}")
    print(f"  Est leverage:          {est_leverage:.1f}x")

    fill_sizes = sorted([abs(float(f.get("sz", 0)) * float(f.get("px", 0))) for f in fills])
    if fill_sizes:
        print(f"\n  === VIII. FILL SIZE ===")
        print(f"  Min:    ${fill_sizes[0]:,.2f}")
        print(f"  P25:    ${fill_sizes[len(fill_sizes)//4]:,.2f}")
        print(f"  Median: ${fill_sizes[len(fill_sizes)//2]:,.2f}")
        print(f"  P75:    ${fill_sizes[3*len(fill_sizes)//4]:,.2f}")
        print(f"  Max:    ${fill_sizes[-1]:,.2f}")

    print(f"\n  === IX. PER-COIN DIRECTIONAL ===")
    for coin in coins:
        ts = coin_trades[coin]
        if not ts: continue
        long_ct = [t for t in ts if t["dir"] == "LONG"]
        short_ct = [t for t in ts if t["dir"] == "SHORT"]
        print(f"  {coin}: {len(ts)} trades")
        if long_ct:
            l_w = [t for t in long_ct if t["pnl"] > 0]
            l_pnl = sum(t["pnl"] for t in long_ct)
            l_wr = len(l_w) / max(len(long_ct), 1) * 100
            print(f"    LONG:  {len(long_ct)}  WR={l_wr:.1f}%  PnL=${l_pnl:+.2f}")
        if short_ct:
            s_w = [t for t in short_ct if t["pnl"] > 0]
            s_pnl = sum(t["pnl"] for t in short_ct)
            s_wr = len(s_w) / max(len(short_ct), 1) * 100
            print(f"    SHORT: {len(short_ct)}  WR={s_wr:.1f}%  PnL=${s_pnl:+.2f}")
        coin_holds = [t["hold_s"] for t in ts if t["hold_s"] > 0 and not t.get("open")]
        if coin_holds:
            ch = sorted(coin_holds)
            print(f"    Hold: median={ch[len(ch)//2]:.0f}s  avg={sum(coin_holds)/len(coin_holds):.0f}s")

    sorted_trades = sorted(all_trades, key=lambda t: t["pnl"], reverse=True)
    print(f"\n  === X. TOP 5 TRADES ===")
    for t in sorted_trades[:5]:
        o = " [OPEN]" if t.get("open") else ""
        print(f"    ${t['pnl']:<+9.2f}  {t['dir']:<6}  hold={t['hold_s']:.0f}s{o}")
    print(f"  BOTTOM 5:")
    for t in sorted_trades[-5:]:
        o = " [OPEN]" if t.get("open") else ""
        print(f"    ${t['pnl']:<+9.2f}  {t['dir']:<6}  hold={t['hold_s']:.0f}s{o}")

    fill_px = [float(f.get("px", 0)) for f in fills]
    if fill_px:
        print(f"\n  === XI. FILL STATS ===")
        print(f"  Avg fill price: ${sum(fill_px)/len(fill_px):,.2f}")
        print(f"  Price range: ${min(fill_px):,.2f} - ${max(fill_px):,.2f}")

    open_positions = [t for t in all_trades if t.get("open")]
    if open_positions:
        print(f"\n  === XII. OPEN POSITIONS ===")
        for op in open_positions:
            print(f"    {op['coin']} ({op['dir']})")

    print("\n" + "=" * 72)

    result = {
        "address": addr,
        "fills": n,
        "days": round(days_span, 1),
        "trades": n_trades,
        "oid_reduces": oid_reduces,
        "wr": round(wr, 1),
        "pnl": round(total_pnl, 2),
        "total_closedpnl": round(total_closed_pnl, 2),
        "gross_profit": round(gp, 2),
        "gross_loss": round(gl, 2),
        "profit_factor": round(pf, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "coins": coins,
        "n_coins": len(coins),
        "hold_median": round(sorted(holds)[len(holds)//2], 0) if holds else 0,
        "capital": round(est_capital, 0),
        "leverage": round(est_leverage, 1),
        "active_days": active_days,
        "trades_per_day": round(avg_per_day, 1),
        "peak_hour": peak_hour if hourly else None,
        "session": primary if hourly else None,
        "long_trades": len(long_trades),
        "short_trades": len(short_trades),
        "best_day": {"date": best_day, "pnl": round(best_pnl, 2)} if best_day else None,
        "worst_day": {"date": worst_day, "pnl": round(worst_pnl, 2)} if worst_day else None,
        "max_losing_streak": max_losing_streak,
        "max_winning_streak": max_winning_streak,
        "per_coin": {},
        "directional": {
            "long": {"trades": len(long_trades), "wr": round(l_wr, 1) if long_trades else 0, "pnl": round(l_pnl, 2) if long_trades else 0},
            "short": {"trades": len(short_trades), "wr": round(s_wr, 1) if short_trades else 0, "pnl": round(s_pnl, 2) if short_trades else 0},
        },
    }
    for coin in coins:
        ts = coin_trades[coin]
        cw = [t for t in ts if t["pnl"] > 0]
        result["per_coin"][coin] = {
            "trades": len(ts),
            "pnl": round(sum(t["pnl"] for t in ts), 2),
            "wr": round(len(cw) / max(len(ts), 1) * 100, 1),
            "weight": round(len(ts) / max(n_trades, 1) * 100, 1),
        }

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 deep_analyze.py <wallet_address> [--days N]")
        sys.exit(1)
    addr = sys.argv[1]
    days = None
    for i, a in enumerate(sys.argv[2:], 2):
        if a == "--days" and i + 1 < len(sys.argv):
            days = int(sys.argv[i + 1])
    result = analyze(addr, days)
    outfile = f"data/analysis_{addr[:6]}.json"
    with open(outfile, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n  → Saved to {outfile}")
