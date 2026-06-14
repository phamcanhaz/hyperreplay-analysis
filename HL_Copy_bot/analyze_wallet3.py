#!/usr/bin/env python3
"""Deep analysis of wallet #3 — 0x6dbbefad"""
import json, os, sys, urllib.request, urllib.error
from collections import defaultdict, Counter
from datetime import datetime, timezone
import math

HL_INFO = "https://api.hyperliquid.xyz/info"
FETCH_TIMEOUT = 20
ANALYSIS_DAYS = 30
BASE = "/home/bot/hl_copy_bot"
ADDR = "0x6dbbefad3d24da625fa233c070678ab1938fcd38"

def now_ts():
    return int(datetime.now(timezone.utc).timestamp())

def fetch_fills(addr, start_time):
    payload = json.dumps({
        "type": "userFillsByTime", "user": addr,
        "startTime": start_time * 1000,
    }).encode()
    req = urllib.request.Request(HL_INFO, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            data = json.loads(resp.read())
        if not isinstance(data, list):
            return None
        fills = []
        for f in data:
            ts_ms = f.get("time", 0)
            if ts_ms < start_time * 1000:
                continue
            fills.append({
                "coin": f.get("coin", ""),
                "side": f.get("side", ""),
                "px": float(f.get("px", "0") or "0"),
                "sz": float(f.get("sz", "0") or "0"),
                "closed_pnl": float(f.get("closedPnl", "0") or "0"),
                "fee": float(f.get("fee", "0") or "0"),
                "time": ts_ms // 1000,
                "start_position": float(f.get("startPosition", "0") or "0"),
                "dir": f.get("dir", ""),
            })
        return fills
    except Exception as e:
        print(f"  API error: {e}")
        return None

def reconstruct_trades(fills):
    sorted_fills = sorted(fills, key=lambda f: f["time"])
    trades = []
    open_pos = {}
    for f in sorted_fills:
        coin = f["coin"]
        prev_sz = f["start_position"]
        new_sz = prev_sz - f["sz"] if f["side"] == "A" else prev_sz + f["sz"]
        closed = (prev_sz > 0 and new_sz <= 0) or (prev_sz < 0 and new_sz >= 0)
        if prev_sz == 0:
            open_pos[coin] = {"coin": coin, "size": new_sz, "entry_px": f["px"], "entry_time": f["time"]}
        elif closed:
            ot = open_pos.get(coin)
            if ot:
                direction = "LONG" if ot["size"] > 0 else "SHORT"
                net_pnl = f["closed_pnl"] - f["fee"]
                hold = f["time"] - ot["entry_time"]
                entry_val = abs(ot["size"]) * ot["entry_px"]
                roi = (net_pnl / entry_val * 100) if entry_val > 0 else 0
                trades.append({
                    "coin": coin, "side": direction,
                    "entry_px": ot["entry_px"], "exit_px": f["px"],
                    "entry_time": ot["entry_time"], "exit_time": f["time"],
                    "hold_secs": hold, "net_pnl": round(net_pnl, 2),
                    "roi_pct": round(roi, 2), "entry_val": round(entry_val, 2),
                })
            if abs(new_sz) > 0.0001:
                open_pos[coin] = {"coin": coin, "size": new_sz, "entry_px": f["px"], "entry_time": f["time"]}
            else:
                open_pos.pop(coin, None)
        else:
            ot = open_pos.get(coin)
            if ot:
                old_abs = abs(prev_sz)
                adding = (prev_sz > 0 and f["side"] == "B") or (prev_sz < 0 and f["side"] == "A")
                ot["size"] = new_sz
                if adding:
                    ot["entry_px"] = (ot["entry_px"] * old_abs + f["px"] * f["sz"]) / (old_abs + f["sz"])
    return trades

def main():
    cutoff = now_ts() - ANALYSIS_DAYS * 86400
    print(f"Fetching fills for {ADDR[:16]}...")
    sys.stdout.flush()
    fills = fetch_fills(ADDR, cutoff)
    if not fills:
        print("No fills or API failed")
        return
    trades = reconstruct_trades(fills)

    # Filter to actual closed trades (not partial closes)
    closed = [t for t in trades if t["hold_secs"] > 10]  # filter out flash fills

    print(f"\n{'='*70}")
    print(f"PHÂN TÍCH SÂU VÍ #3: {ADDR}")
    print(f"{'='*70}")
    print(f"Tổng fills (30 ngày): {len(fills)}")
    print(f"Trades tái tạo: {len(trades)}")
    print(f"Closed trades (>10s): {len(closed)}")

    # ─── 1. Trading hours heatmap ───
    hour_cnt = Counter()
    for t in closed:
        h = datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).hour
        hour_cnt[h] += 1
    print(f"\n📅 Hoạt động theo giờ (UTC):")
    print(f"   Giờ:  ", " ".join(f"{h:2d}" for h in range(24)))
    print(f"   Số lượng:", " ".join(f"{hour_cnt.get(h, 0):2d}" for h in range(24)))

    session_map = {"ASIA": range(0,8), "EUROPE": range(8,16), "US": range(16,24)}
    for s, hrs in session_map.items():
        cnt = sum(hour_cnt.get(h,0) for h in hrs)
        print(f"   {s:>8}: {cnt} trades ({cnt/len(closed)*100:.0f}%)")

    # ─── 2. PnL distribution ───
    pnls = [t["net_pnl"] for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    total_pnl = sum(pnls)
    gross_pnl = sum(wins)
    gross_loss = abs(sum(losses))
    print(f"\n💰 PnL Distribution:")
    print(f"   Total: ${total_pnl:.2f}")
    print(f"   Gross profit: ${gross_pnl:.2f}")
    print(f"   Gross loss: ${gross_loss:.2f}")
    print(f"   Profit factor: {gross_pnl/gross_loss:.2f}" if gross_loss > 0 else "   Profit factor: ∞")
    print(f"   Avg win: ${(sum(wins)/len(wins)):.2f}" if wins else "   Avg win: N/A")
    print(f"   Avg loss: ${(sum(losses)/len(losses)):.2f}" if losses else "   Avg loss: N/A")
    print(f"   Best trade: ${max(pnls):.2f}")
    print(f"   Worst trade: ${min(pnls):.2f}")
    print(f"   Median PnL: ${sorted(pnls)[len(pnls)//2]:.2f}")

    # Histogram buckets
    buckets = [(-100, -10), (-10, -5), (-5, -1), (-1, -0.1), (-0.1, 0),
               (0, 0.1), (0.1, 1), (1, 5), (5, 10), (10, 100)]
    print(f"\n📊 PnL Histogram:")
    for lo, hi in buckets:
        cnt = sum(1 for p in pnls if lo < p <= hi)
        bar = "█" * cnt
        print(f"   ${lo:>5} to ${hi:>5}: {cnt:>3} {bar}")

    # ─── 3. Hold time analysis ───
    holds = [t["hold_secs"] for t in closed]
    print(f"\n⏱ Hold Time Analysis:")
    print(f"   Min: {min(holds)/60:.1f}m")
    print(f"   Max: {max(holds)/60:.1f}m")
    print(f"   Avg: {sum(holds)/len(holds)/60:.1f}m")
    print(f"   Median: {sorted(holds)[len(holds)//2]/60:.1f}m")
    hold_buckets = [(0, 60), (60, 300), (300, 600), (600, 1800), (1800, 3600), (3600, 86400)]
    print(f"   Distribution:")
    for lo, hi in hold_buckets:
        cnt = sum(1 for h in holds if lo <= h < hi)
        pct = cnt/len(holds)*100
        label = f"{lo//60}m-{hi//60}m" if hi < 3600 else f"{lo//3600}h-{hi//3600}h"
        print(f"     {label:>12}: {cnt:>3} trades ({pct:.0f}%)")

    # ─── 4. Position size analysis ───
    entry_vals = [t["entry_val"] for t in closed]
    print(f"\n📐 Position Size:")
    print(f"   Avg entry notional: ${sum(entry_vals)/len(entry_vals):.2f}")
    print(f"   Median: ${sorted(entry_vals)[len(entry_vals)//2]:.2f}")
    print(f"   Min: ${min(entry_vals):.2f}")
    print(f"   Max: ${max(entry_vals):.2f}")

    size_buckets = [(0,1000), (1000,5000), (5000,10000), (10000,50000), (50000,999999)]
    print(f"   Position size distribution:")
    for lo, hi in size_buckets:
        cnt = sum(1 for v in entry_vals if lo <= v < hi)
        pct = cnt/len(entry_vals)*100
        print(f"     ${lo:>5}-${hi:>5}: {cnt:>3} trades ({pct:.0f}%)")

    # ─── 5. ROI analysis ───
    rois = [t["roi_pct"] for t in closed]
    avg_roi = sum(rois)/len(rois)
    print(f"\n📈 ROI Analysis:")
    print(f"   Avg ROI per trade: {avg_roi:.2f}%")
    print(f"   Best ROI: {max(rois):.2f}%")
    print(f"   Worst ROI: {min(rois):.2f}%")
    # R multiple: avg win / avg loss
    win_rois = [r for r in rois if r > 0]
    loss_rois = [r for r in rois if r < 0]
    if loss_rois:
        r_multiple = abs(sum(win_rois)/len(win_rois) / (sum(loss_rois)/len(loss_rois))) if loss_rois and win_rois else 0
        print(f"   R-multiple (avg win ROI / avg loss ROI): {r_multiple:.2f}x")

    # ─── 6. Win/Loss streaks ───
    results = [1 if t["net_pnl"] > 0 else 0 for t in sorted(closed, key=lambda x: x["entry_time"])]
    current_streak = 1
    max_win = max_loss = 0
    streak_type = results[0]
    for i in range(1, len(results)):
        if results[i] == results[i-1]:
            current_streak += 1
        else:
            if streak_type == 1: max_win = max(max_win, current_streak)
            else: max_loss = max(max_loss, current_streak)
            current_streak = 1
            streak_type = results[i]
    if streak_type == 1: max_win = max(max_win, current_streak)
    else: max_loss = max(max_loss, current_streak)
    print(f"\n🔴🟢 Streaks:")
    print(f"   Max win streak: {max_win}")
    print(f"   Max loss streak: {max_loss}")
    print(f"   Current streak: {'WIN' if results[-1] == 1 else 'LOSS'} x{current_streak}")

    # ─── 7. Per-coin deep dive ───
    print(f"\n🪙 Per-Coin Deep Dive:")
    by_coin = defaultdict(list)
    for t in closed:
        by_coin[t["coin"]].append(t)
    for coin, ts in sorted(by_coin.items(), key=lambda x: abs(sum(t["net_pnl"] for t in x[1])), reverse=True):
        n = len(ts)
        w = sum(1 for t in ts if t["net_pnl"] > 0)
        pnl = sum(t["net_pnl"] for t in ts)
        avg_hold = sum(t["hold_secs"] for t in ts)/n/60
        avg_val = sum(t["entry_val"] for t in ts)/n
        trades_str = " ".join(f"${t['net_pnl']:+.1f}" for t in sorted(ts, key=lambda x: x["entry_time"]))
        print(f"   {coin:>8}: {n:>2} trades WR={w/n*100:.0f}% PnL=${pnl:+.1f} avg_val=${avg_val:.0f} avg_hold={avg_hold:.0f}m")
        print(f"           PnL sequence: {trades_str}")

    # ─── 8. Time decay (PnL by session) ───
    print(f"\n📅 PnL theo ngày giao dịch:")
    by_day = defaultdict(list)
    for t in closed:
        day = datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).strftime("%Y-%m-%d")
        by_day[day].append(t)
    for day in sorted(by_day):
        ts = by_day[day]
        n = len(ts)
        day_pnl = sum(t["net_pnl"] for t in ts)
        w = sum(1 for t in ts if t["net_pnl"] > 0)
        l = n - w
        print(f"   {day}: {n:>2} trades PnL=${day_pnl:+.2f} W:{w} L:{l}")

    # ─── 9. Copyability score (from Rust formula) ───
    tpd = len(closed) / max(len(by_day), 1)
    avg_hold = sum(holds)/len(holds)
    strategy = "DAY_TRADER"  # known from bot
    print(f"\n📋 Copyability Assessment:")
    print(f"   TPD (trades/day): {tpd:.1f}")
    print(f"   Avg hold: {avg_hold:.0f}s ({avg_hold/60:.1f}m)")
    copy = 100.0
    tp = 1.0  # DAY_TRADER
    if tpd > 30: copy -= 50 * tp
    elif tpd > 15: copy -= 25 * tp
    elif tpd > 10: copy -= 10 * tp
    if avg_hold < 120: copy -= 40
    elif avg_hold < 600: copy -= 20
    elif avg_hold < 1800: copy -= 5
    print(f"   Copyability score: {max(copy,0):.0f}/100")

    # ─── 10. Risk metrics ───
    sharpe = (sum(pnls)/len(pnls)) / (std(pnls) + 0.0001) * math.sqrt(len(pnls)) if len(pnls) > 1 else 0
    print(f"\n⚠️ Risk Metrics:")
    print(f"   Sharpe ratio (trade level): {sharpe:.2f}")
    print(f"   Win/Loss ratio: {len(wins)/max(len(losses),1):.2f}")
    print(f"   Avg Risk/Reward: {sum(wins)/len(wins)/abs(sum(losses)/len(losses)):.2f}" if wins and losses else "   Avg Risk/Reward: N/A")
    print(f"   % Profitable days: {sum(1 for d in by_day.values() if sum(t['net_pnl'] for t in d) > 0)/len(by_day)*100:.0f}%")

    # ─── 11. Fill data analysis ───
    print(f"\n📋 Fill-level Analysis:")
    fill_pnls = [f["closed_pnl"] - f["fee"] for f in fills if abs(f["closed_pnl"] - f["fee"]) > 0.001]
    print(f"   Total fills with PnL: {len(fill_pnls)}")
    print(f"   Fill-based PnL: ${sum(fill_pnls):.2f}")
    fill_wins = sum(1 for p in fill_pnls if p > 0)
    print(f"   Fill win rate: {fill_wins/len(fill_pnls)*100:.1f}%")
    # Net vs gross
    print(f"   Trade PnL / Fill PnL ratio: {total_pnl/max(sum(fill_pnls), 0.01):.2f}x")

    # Sequence consistency check — are profits clustered?
    print(f"\n🎯 Sequence Analysis:")
    # Sort chronologically
    sorted_closed = sorted(closed, key=lambda x: x["entry_time"])
    # Running equity curve
    eq = 0
    dd_peak = 0
    max_dd = 0
    for t in sorted_closed:
        eq += t["net_pnl"]
        if eq > dd_peak: dd_peak = eq
        dd = (dd_peak - eq) / dd_peak * 100 if dd_peak > 0 else 0
        if dd > max_dd: max_dd = dd
    print(f"   Max drawdown (equity curve): {max_dd:.1f}%")
    print(f"   Final equity (PnL only): ${eq:.2f}")

    # Consecutive trades test
    print(f"   Last 5 trades:")
    for t in sorted_closed[-5:]:
        ts = datetime.fromtimestamp(t["exit_time"], tz=timezone.utc).strftime("%m/%d %H:%M")
        print(f"     {ts} {t['side']} {t['coin']:>8} PnL=${t['net_pnl']:+6.2f} ROI={t['roi_pct']:+.2f}% hold={t['hold_secs']/60:.0f}m")

def std(vals):
    if len(vals) < 2: return 0
    m = sum(vals)/len(vals)
    return math.sqrt(sum((v-m)**2 for v in vals)/(len(vals)-1))

if __name__ == "__main__":
    main()
