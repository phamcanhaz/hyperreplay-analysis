#!/usr/bin/env python3
"""Detailed day-by-day analysis of currently copied wallets."""
import json
import os
import sys
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone

HL_INFO = "https://api.hyperliquid.xyz/info"
FETCH_TIMEOUT = 20
ANALYSIS_DAYS = 30
BASE = "/home/bot/hl_copy_bot"
REPORT = f"{BASE}/copies_detailed_report.txt"

WALLETS = [
    "0xc4cda69c9354eb77bce1d70c349b2de691be80b8",
    "0x8faf84cfba2fded55c8c21c149fc33be79e2b7ba",
    "0x6dbbefad3d24da625fa233c070678ab1938fcd38",
    "0x373b036b4b2128c578e6695f9ee76bdb5e75a387",
    "0x7d65ea6c187d6219ab6a1335cd2fe09f12e818fa",
]


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
    except Exception:
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
            open_pos[coin] = {
                "coin": coin, "size": new_sz,
                "entry_px": f["px"], "entry_time": f["time"],
            }
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
                    "roi_pct": round(roi, 2), "closed": True,
                })
            if abs(new_sz) > 0.0001:
                open_pos[coin] = {
                    "coin": coin, "size": new_sz,
                    "entry_px": f["px"], "entry_time": f["time"],
                }
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

    end_positions = []
    for coin, ot in open_pos.items():
        if abs(ot["size"]) > 0.0001:
            end_positions.append({
                "coin": coin, "size": abs(ot["size"]),
                "entry_px": ot["entry_px"],
                "side": "LONG" if ot["size"] > 0 else "SHORT",
            })
    return trades, end_positions


def classify_strategy(trades):
    hold_times = [t["hold_secs"] for t in trades if t["closed"]]
    if not hold_times:
        return "UNKNOWN"
    avg_hold = sum(hold_times) / len(hold_times)
    if avg_hold < 300: return "SCALPER"
    if avg_hold < 14400: return "DAY_TRADER"
    if avg_hold < 86400 * 3: return "SWING"
    return "POSITION"


def daily_breakdown(trades):
    by_day = defaultdict(list)
    for t in trades:
        day = datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).strftime("%Y-%m-%d")
        by_day[day].append(t)
    return dict(sorted(by_day.items()))


def coin_breakdown(trades):
    by_coin = defaultdict(list)
    for t in trades:
        by_coin[t["coin"]].append(t)
    result = {}
    for coin, ts in by_coin.items():
        wins = sum(1 for t in ts if t["net_pnl"] > 0)
        pnl = sum(t["net_pnl"] for t in ts)
        result[coin] = {"trades": len(ts), "wins": wins, "pnl": round(pnl, 2),
                        "wr": round(wins / len(ts) * 100, 1)}
    return result


def analyze_wallet(addr):
    cutoff = now_ts() - ANALYSIS_DAYS * 86400
    fills = fetch_fills(addr, cutoff)
    if fills is None:
        return {"error": "API fail"}
    trades, end_pos = reconstruct_trades(fills)

    meta = {}
    if fills:
        pnl = sum(f["closed_pnl"] - f["fee"] for f in fills)
        meta["fill_pnl"] = round(pnl, 2)
    meta["fills"] = len(fills)
    meta["trades"] = len(trades)
    meta["strategy"] = classify_strategy(trades) if trades else "N/A"
    meta["open_positions"] = end_pos

    # Per-day
    days = daily_breakdown(trades)
    day_lines = []
    for day, ts in days.items():
        day_pnl = sum(t["net_pnl"] for t in ts)
        wins = sum(1 for t in ts if t["net_pnl"] > 0)
        losses = sum(1 for t in ts if t["net_pnl"] <= 0)
        avg_hold = sum(t["hold_secs"] for t in ts) / len(ts) if ts else 0
        day_lines.append(f"  {day} | {len(ts):>3} trades | PnL=${day_pnl:>8,.2f} | W:{wins} L:{losses} | avg_hold={avg_hold/3600:.1f}h")
        for t in ts:
            entry_str = datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).strftime("%H:%M")
            exit_str = datetime.fromtimestamp(t["exit_time"], tz=timezone.utc).strftime("%H:%M")
            day_lines.append(f"    {entry_str}-{exit_str} {t['side']:>5} {t['coin']:>8} sz=1x entry=${t['entry_px']:<8.2f} exit=${t['exit_px']:<8.2f} PnL=${t['net_pnl']:<8,.2f} ROI={t['roi_pct']:.2f}%")
    meta["daily_breakdown"] = "\n".join(day_lines)

    # Per-coin
    coins = coin_breakdown(trades)
    meta["coin_breakdown"] = coins

    # Total metrics
    total_pnl = sum(t["net_pnl"] for t in trades)
    wins = sum(1 for t in trades if t["net_pnl"] > 0)
    meta["total_pnl"] = round(total_pnl, 2)
    meta["win_rate"] = round(wins / len(trades) * 100, 1) if trades else 0
    meta["avg_hold_hours"] = round(sum(t["hold_secs"] for t in trades) / len(trades) / 3600, 1) if trades else 0

    return meta


def main():
    out = []
    out.append("=" * 100)
    out.append("PHÂN TÍCH CHI TIẾT 5 VÍ ĐANG COPY")
    out.append(f"Thời gian: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    out.append(f"Cửa sổ phân tích: {ANALYSIS_DAYS} ngày gần nhất")
    out.append("=" * 100)

    for i, addr in enumerate(WALLETS, 1):
        print(f"\n[{i}/5] Analyzing {addr[:12]}...")
        sys.stdout.flush()
        meta = analyze_wallet(addr)

        short = addr[:12]
        out.append(f"\n{'─' * 100}")
        out.append(f"VÍ #{i}: {addr}")

        if "error" in meta:
            out.append(f"  ❌ {meta['error']}")
            continue

        out.append(f"  📊 Tổng quan:")
        out.append(f"     Số fills: {meta['fills']}")
        out.append(f"     Số trades tái tạo: {meta['trades']}")
        out.append(f"     Strategy: {meta['strategy']}")
        out.append(f"     Total PnL: ${meta['total_pnl']:,.2f}")
        out.append(f"     Win rate: {meta['win_rate']}%")
        out.append(f"     Avg hold: {meta['avg_hold_hours']}h")
        out.append(f"     Fill PnL (thuần): ${meta['fill_pnl']:,.2f}")

        if meta["open_positions"]:
            out.append(f"  📌 Positions đang mở:")
            for p in meta["open_positions"]:
                out.append(f"     {p['side']} {p['coin']} size={p['size']:.2f} entry=${p['entry_px']:.2f}")

        out.append(f"\n  📅 Nhật ký giao dịch theo ngày:")
        if meta["daily_breakdown"]:
            out.append(meta["daily_breakdown"])
        else:
            out.append("     (không có trade nào trong 30 ngày)")

        out.append(f"\n  📈 Thống kê theo coin:")
        for coin, c in meta["coin_breakdown"].items():
            out.append(f"     {coin:>10}: {c['trades']} trades, WR={c['wr']}%, PnL=${c['pnl']:,.2f}")

        print(f"  Done — {meta['trades']} trades, ${meta['total_pnl']:,.2f} PnL")

    out.append(f"\n{'=' * 100}")
    out.append("HẾT BÁO CÁO")
    out.append(f"{'=' * 100}")

    with open(REPORT, "w") as f:
        f.write("\n".join(out) + "\n")
    print(f"\n✅ Report saved to {REPORT}")


if __name__ == "__main__":
    main()
