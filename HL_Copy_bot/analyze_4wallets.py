#!/usr/bin/env python3
"""Phân tích chi tiết 4 ví được chọn — từ ngày đầu giao dịch"""
import json, os, time, urllib.request, urllib.error
from datetime import datetime, timezone
from collections import Counter
from typing import Any

HL_INFO = "https://api.hyperliquid.xyz/info"
FETCH_TIMEOUT = 15
BASE = "/home/bot/hl_copy_bot"

def now_ts():
    return int(time.time())

def fetch_all_fills(addr, start_time=1700000000):
    payload = json.dumps({"type": "userFillsByTime", "user": addr,
                          "startTime": start_time * 1000}).encode()
    req = urllib.request.Request(HL_INFO, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            data = json.loads(resp.read())
        if not isinstance(data, list):
            return []
        fills = []
        for f in data:
            fills.append({
                "coin": f.get("coin", ""),
                "side": f.get("side", ""),
                "px": float(f.get("px", "0") or "0"),
                "sz": float(f.get("sz", "0") or "0"),
                "closed_pnl": float(f.get("closedPnl", "0") or "0"),
                "fee": float(f.get("fee", "0") or "0"),
                "time": f.get("time", 0) // 1000,
                "start_position": float(f.get("startPosition", "0") or "0"),
            })
        return fills
    except Exception as e:
        return []

def detect_bias(trades, fills):
    lc = sc = 0
    for t in trades:
        if t["side"] == "LONG": lc += 1
        else: sc += 1
    if lc == 0 and sc == 0:
        for f in fills:
            if f["side"] == "A": sc += 1
            else: lc += 1
    if sc > lc * 3: return "STRONG SHORT"
    if sc > lc: return "SHORT"
    if lc > sc * 3: return "STRONG LONG"
    if lc > sc: return "LONG"
    return "NEUTRAL"

def classify_strategy(trades):
    hold = [t["hold_secs"] for t in trades if t.get("closed")]
    if not hold: return "UNKNOWN"
    avg = sum(hold) / len(hold)
    if avg < 300: return "SCALPER"
    if avg < 14400: return "DAY_TRADER"
    if avg < 86400*3: return "SWING"
    return "POSITION"

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
            open_pos[coin] = {"coin": coin, "size": new_sz, "entry_px": f["px"],
                              "entry_time": f["time"]}
        elif closed:
            ot = open_pos.get(coin)
            if ot:
                direction = "LONG" if ot["size"] > 0 else "SHORT"
                net_pnl = f["closed_pnl"] - f["fee"]
                hold = f["time"] - ot["entry_time"]
                entry_val = abs(ot["size"]) * ot["entry_px"]
                roi = (net_pnl / entry_val * 100) if entry_val > 0 else 0
                trades.append({
                    "coin": coin, "side": direction, "entry_px": ot["entry_px"],
                    "exit_px": f["px"], "entry_time": ot["entry_time"],
                    "exit_time": f["time"], "hold_secs": hold,
                    "net_pnl": round(net_pnl, 2), "roi_pct": round(roi, 2), "closed": True,
                })
            if abs(new_sz) > 0.0001:
                open_pos[coin] = {"coin": coin, "size": new_sz, "entry_px": f["px"],
                                  "entry_time": f["time"]}
            else:
                open_pos.pop(coin, None)
        else:
            ot = open_pos.get(coin)
            if ot:
                adding = (prev_sz > 0 and f["side"] == "B") or (prev_sz < 0 and f["side"] == "A")
                ot["size"] = new_sz
                if adding:
                    ot["entry_px"] = (ot["entry_px"] * abs(prev_sz) + f["px"] * f["sz"]) / (abs(prev_sz) + f["sz"])
    return trades

# === MAIN ===
WALLETS = [
    ("0xb69ccb3ad06300fefe1c551e285de4a3c6a1a5da", "DAY_TRADER"),
    ("0x7aa11aafdfc46ebedbb3adabea180cce3607e8c2", "SWING"),
    ("0xb1edfeccf03f35d2268f5dc4013508a6eb52c702", "DAY_TRADER"),
    ("0x18d103744b0f0bd4ab860f3455a252d20580d6dd", "SWING"),
]

line = "=" * 130
print(line)
print(f'{"PHAN TICH CHI TIET 4 VI DUOC CHON":^130}')
print(f'{"(Fetch fills tu API Hyperliquid)":^130}')
print(line)

for addr, strat_label in WALLETS:
    tag = addr[:12]
    print(f'\n\n{line}')
    print(f'  VI: {addr}')
    print(f'  Strategy: {strat_label}')
    print(f'{line}\n')
    print(f"  Dang fetch fills tu API...", end=" ", flush=True)
    
    fills = fetch_all_fills(addr, start_time=1700000000)
    if not fills:
        print("KHONG CO DU LIEU")
        continue
    
    print(f"{len(fills)} fills")
    trades = reconstruct_trades(fills)
    closed_trades = [t for t in trades if t.get("closed")]
    open_trades = [t for t in trades if not t.get("closed")]
    
    # Time range
    ts_min = min(f["time"] for f in fills)
    ts_max = max(f["time"] for f in fills)
    days = (ts_max - ts_min) / 86400
    dt_min = datetime.fromtimestamp(ts_min, tz=timezone.utc).strftime("%Y-%m-%d")
    dt_max = datetime.fromtimestamp(ts_max, tz=timezone.utc).strftime("%Y-%m-%d")
    
    print(f"\n  ── THONG TIN CO BAN ──")
    print(f"    Tu: {dt_min}  -->  {dt_max}  ({days:.0f} ngay)")
    print(f"    Tong fills: {len(fills)}")
    print(f"    Trades reconstruct: {len(closed_trades)} closed + {len(open_trades)} open")
    
    # PnL analysis
    total_pnl = sum(t["net_pnl"] for t in closed_trades)
    wins = [t for t in closed_trades if t["net_pnl"] > 0]
    losses = [t for t in closed_trades if t["net_pnl"] <= 0]
    wr = len(wins) / len(closed_trades) * 100 if closed_trades else 0
    gp = sum(t["net_pnl"] for t in wins)
    gl = abs(sum(t["net_pnl"] for t in losses))
    pf = gp / gl if gl > 0 else 999.0
    avg_win = gp / len(wins) if wins else 0
    avg_loss = gl / len(losses) if losses else 0
    max_win = max((t["net_pnl"] for t in wins), default=0)
    max_loss = min((t["net_pnl"] for t in losses), default=0)
    
    print(f"\n  ── PnL & TRADES ──")
    print(f"    Tong PnL: ${total_pnl:>8,.2f}")
    print(f"    Win: {len(wins)} trade, Loss: {len(losses)} trade")
    print(f"    Win rate: {wr:.1f}%")
    print(f"    Profit Factor: {pf:.2f}")
    print(f"    Avg Win: ${avg_win:.2f}  |  Avg Loss: ${avg_loss:.2f}")
    print(f"    Max Win: ${max_win:.2f}  |  Max Loss: ${max_loss:.2f}")
    print(f"    Avg PnL/trade: ${total_pnl/len(closed_trades):.2f}" if closed_trades else "")
    
    # PnL by coin
    print(f"\n  ── PnL THEO COIN ──")
    by_coin = {}
    for t in closed_trades:
        c = t["coin"]
        if c not in by_coin:
            by_coin[c] = {"trades": 0, "wins": 0, "pnl": 0.0}
        by_coin[c]["trades"] += 1
        by_coin[c]["pnl"] += t["net_pnl"]
        if t["net_pnl"] > 0:
            by_coin[c]["wins"] += 1
    sorted_coins = sorted(by_coin.items(), key=lambda x: abs(x[1]["pnl"]), reverse=True)
    print(f"    {'Coin':<8} {'Trades':<8} {'PnL':<12} {'WR%':<7} {'AvgPnl':<10}")
    print(f"    {'-'*45}")
    for coin, c in sorted_coins[:8]:
        cwr = c["wins"] / c["trades"] * 100 if c["trades"] else 0
        cavg = c["pnl"] / c["trades"]
        print(f"    {coin:<8} {c['trades']:<8} ${c['pnl']:<9,.0f} {cwr:<6.1f}% ${cavg:<7,.0f}")
    if len(sorted_coins) > 8:
        rest = sorted_coins[8:]
        rest_pnl = sum(c["pnl"] for _, c in rest)
        rest_trades = sum(c["trades"] for _, c in rest)
        print(f"    {'(khac)':<8} {rest_trades:<8} ${rest_pnl:<9,.0f} {'':<7} {'':<10}")
    
    # Time analysis
    print(f"\n  ── PHAN TICH THOI GIAN ──")
    hold_times = [t["hold_secs"] for t in closed_trades]
    avg_hold = sum(hold_times) / len(hold_times) if hold_times else 0
    print(f"    Avg hold time: {avg_hold/3600:.1f}h" if avg_hold > 3600 else f"    Avg hold time: {avg_hold/60:.0f}m")
    if hold_times:
        print(f"    Hold min: {min(hold_times)/60:.0f}m  |  max: {max(hold_times)/3600:.1f}h" if max(hold_times) > 3600 else f"    Hold min: {min(hold_times)/60:.0f}m  |  max: {max(hold_times)/60:.0f}m")
    
    # By hour
    hours = [datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).hour for t in closed_trades]
    if hours:
        cnt = Counter(hours)
        peak = cnt.most_common(1)[0][0]
        asia = sum(cnt[h] for h in range(0, 8))
        europe = sum(cnt[h] for h in range(8, 16))
        us = sum(cnt[h] for h in range(16, 24))
        session = max([("ASIA",asia),("EUROPE",europe),("US",us)], key=lambda x:x[1])[0]
        print(f"    Peak trading hour: UTC {peak}:00")
        print(f"    Session: {session}")
    
    # Monthly breakdown
    print(f"\n  ── PnL THEO THANG ──")
    months = {}
    for t in closed_trades:
        m = datetime.fromtimestamp(t["exit_time"], tz=timezone.utc).strftime("%Y-%m")
        months.setdefault(m, {"trades": 0, "pnl": 0.0, "wins": 0})
        months[m]["trades"] += 1
        months[m]["pnl"] += t["net_pnl"]
        if t["net_pnl"] > 0:
            months[m]["wins"] += 1
    for m in sorted(months):
        c = months[m]
        print(f"    {m}: {c['trades']:>3} trades, PnL=${c['pnl']:>8,.0f}, WR={c['wins']/c['trades']*100:.0f}%" if c['trades'] else "")
    
    # Losing streak
    print(f"\n  ── LOSING STREAK ──")
    streak = best_streak = 0
    worst_streak = 0
    for t in sorted(closed_trades, key=lambda x: x["exit_time"]):
        if t["net_pnl"] <= 0:
            streak += 1
            best_streak = max(best_streak, streak)
        else:
            streak = 0
    # Winning streak
    streak = 0
    for t in sorted(closed_trades, key=lambda x: x["exit_time"]):
        if t["net_pnl"] > 0:
            streak += 1
            worst_streak = max(worst_streak, streak)
        else:
            streak = 0
    print(f"    Max losing streak: {best_streak} trades")
    print(f"    Max winning streak: {worst_streak} trades")
    
    # BIGGEST trades
    print(f"\n  ── 5 TRADE LOI NHIEU NHAT ──")
    top_wins = sorted(closed_trades, key=lambda t: -t["net_pnl"])[:5]
    for t in top_wins:
        dt = datetime.fromtimestamp(t["exit_time"], tz=timezone.utc).strftime("%m/%d %H:%M")
        if t["net_pnl"] > 0:
            print(f"    +${t['net_pnl']:>7,.2f} | {t['coin']:<7} {t['side']:<6} | exit={t['exit_px']:.2f} | hold={t['hold_secs']/3600:.1f}h | {dt}")
    
    print(f"\n  ── 5 TRADE LO NHIEU NHAT ──")
    top_losses = sorted(closed_trades, key=lambda t: t["net_pnl"])[:5]
    for t in top_losses:
        dt = datetime.fromtimestamp(t["exit_time"], tz=timezone.utc).strftime("%m/%d %H:%M")
        if t["net_pnl"] < 0:
            print(f"    {t['net_pnl']:>8,.2f} | {t['coin']:<7} {t['side']:<6} | exit={t['exit_px']:.2f} | hold={t['hold_secs']/3600:.1f}h | {dt}")
    
    # Risk metrics
    print(f"\n  ── RISK METRICS ──")
    equity = 0
    peak = 0
    dd = 0
    for t in sorted(closed_trades, key=lambda x: x["exit_time"]):
        equity += t["net_pnl"]
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = max(dd, (peak - equity) / peak * 100)
    print(f"    Max drawdown: {dd:.1f}%")
    print(f"    Sharpe-like (avg/stdev): ", end="")
    pnls = [t["net_pnl"] for t in sorted(closed_trades, key=lambda x: x["exit_time"])]
    if len(pnls) > 1:
        avg = sum(pnls) / len(pnls)
        var = sum((p - avg)**2 for p in pnls) / len(pnls)
        std = var**0.5
        sharpe = avg / std * (365/days*24*60*60)**0.5 if std > 0 and days > 0 else 0
        print(f"{sharpe:.2f} (annualized)")
    else:
        print("N/A")
    
    print(f"\n  >> {'TOT' if total_pnl > 0 else 'TE'}: ${total_pnl:,.2f} sau {len(closed_trades)} trades trong {days:.0f} ngay")
    print(f"{line}")

print(f'\n\n{line}')
print(f'{"HOAN THANH PHAN TICH 4 VI":^130}')
print(f'{line}')
