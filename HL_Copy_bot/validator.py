#!/usr/bin/env python3
"""30-day validator chạy song song với Rust bot.

Đọc worthy wallets từ seen_wallets.json, fetch 30 ngày fills,
phân tích theo tuần, kiểm tra tính nhất quán.
"""
import json
import time
import sys
import os
from datetime import datetime, timezone
from typing import Any

import urllib.request
import urllib.error

HL_INFO = "https://api.hyperliquid.xyz/info"
DB_FILE = "seen_wallets.json"
VALIDATION_FILE = "validation_results.json"
ANALYSIS_DAYS = 30
SLEEP_SECS = 600  # 10 phút check 1 lần


def now_ts() -> int:
    return int(time.time())


def fetch_fills(addr: str, start_time: int) -> list[dict[str, Any]] | None:
    payload = json.dumps({
        "type": "userFillsByTime",
        "user": addr,
        "startTime": start_time * 1000,
    }).encode()
    req = urllib.request.Request(HL_INFO, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if not isinstance(data, list):
                return None
            fills = []
            for f in data:
                ts_ms = f.get("time", 0)
                if ts_ms < start_time * 1000:
                    continue
                cp = float(f.get("closedPnl", "0") or "0")
                fee = float(f.get("fee", "0") or "0")
                fills.append({
                    "coin": f.get("coin", ""),
                    "side": f.get("side", ""),
                    "px": float(f.get("px", "0") or "0"),
                    "sz": float(f.get("sz", "0") or "0"),
                    "closed_pnl": cp,
                    "fee": fee,
                    "net": cp - fee,
                    "time": ts_ms // 1000,
                })
            return fills
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None


def calc_metrics(fills: list[dict]) -> dict:
    if not fills:
        return {"pnl": 0, "trades": 0, "wins": 0, "wr": 0, "pf": 0, "dd": 0, "gp": 0, "gl": 0}

    pnl = gp = gl = wins = 0.0
    eq = []
    equity = 0.0

    for f in fills:
        net = f["net"]
        pnl += net
        equity += net
        eq.append(equity)
        if net > 0.001:
            wins += 1
            gp += net
        elif net < -0.001:
            gl += abs(net)

    total = len(fills)
    wr = (wins / total * 100) if total > 0 else 0
    pf = (gp / gl) if gl > 0 else (999 if gp > 0 else 0)
    dd = calc_max_dd(eq)
    return {"pnl": round(pnl, 2), "trades": total, "wins": int(wins),
            "wr": round(wr, 2), "pf": round(pf, 2), "dd": round(dd, 2),
            "gp": round(gp, 2), "gl": round(gl, 2)}


def calc_max_dd(curve: list[float]) -> float:
    peak = mdd = 0.0
    for v in curve:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak * 100
            if dd > mdd:
                mdd = dd
    return mdd


def split_weekly(fills: list[dict], cutoff: int) -> list[list[dict]]:
    """Chia fills thành 4 tuần (7 ngày mỗi tuần)."""
    weeks = [[] for _ in range(4)]
    for f in fills:
        offset = f["time"] - cutoff
        week = int(offset // (7 * 86400))
        if 0 <= week < 4:
            weeks[week].append(f)
    return weeks


def validate_wallet(addr: str, cutoff: int) -> dict | None:
    fills = fetch_fills(addr, cutoff)
    if fills is None:
        return None
    if not fills:
        return {"valid": False, "reason": "no_fills", "weeks": [], "total": calc_metrics([])}

    weeks = split_weekly(fills, cutoff)
    week_results = []
    consistent_wins = 0
    for i, wf in enumerate(weeks):
        m = calc_metrics(wf)
        m["week"] = i + 1
        week_results.append(m)
        if m["pnl"] > 0 and m["trades"] >= 5:
            consistent_wins += 1

    total = calc_metrics(fills)
    total_fills = len(fills)

    # API giới hạn 2000 fills → active traders bị trunc, weekly split vô nghĩa
    if total_fills >= 2000:
        # Fallback: overall 30d metrics thay vì weekly
        valid = total["pnl"] > 0 and total["wr"] >= 25.0 and total["trades"] >= 50
    else:
        # Normal: 2/4 tuần profitable (thay vì 3/4) vì nhiều trader có
        # weekly volume không đều
        valid = consistent_wins >= 2 and total["pnl"] > 0

    return {
        "valid": valid,
        "consistent_wins": consistent_wins,
        "total": total,
        "weeks": week_results,
        "total_fills": total_fills,
        "checked_at": now_ts(),
    }


def load_db() -> dict:
    try:
        with open(DB_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_validations(v: dict):
    with open(VALIDATION_FILE, "w") as f:
        json.dump(v, f, indent=2)


def load_validations() -> dict:
    try:
        with open(VALIDATION_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def main():
    print("╔════════════════════════════════════════════════════════╗")
    print("║  🔬 HL VALIDATOR — 30-day wallet consistency check   ║")
    print("║  Chạy song song với Rust bot                         ║")
    print("╚════════════════════════════════════════════════════════╝")

    cycle = 0
    while True:
        cycle += 1
        cutoff = now_ts() - ANALYSIS_DAYS * 86400
        db = load_db()
        validations = load_validations()

        worthy = [(a, w) for a, w in db.items()
                  if w.get("copy_worthy") or w.get("being_copied")]
        worthy.sort(key=lambda x: x[1].get("score", 0), reverse=True)

        if not worthy:
            print(f"\n[{cycle}] Không có worthy wallets để validate.")
        else:
            print(f"\n[{cycle}] Validating {len(worthy)} worthy wallets (30 ngày)...")
            for addr, w in worthy:
                if addr in validations:
                    v = validations[addr]
                    ago = now_ts() - v.get("checked_at", 0)
                    if ago < 3600:
                        continue

                result = validate_wallet(addr, cutoff)
                if result is None:
                    print(f"  ❌ {addr[:12]}... API fail")
                    continue

                validations[addr] = result
                t = result["total"]
                wrs = [wk["wr"] for wk in result["weeks"]]
                pnls = [wk["pnl"] for wk in result["weeks"]]

                status = "✅ VALID" if result["valid"] else "⏳ WEAK"
                cw = result["consistent_wins"]
                cap = "⚠️ CAPPED" if result.get("total_fills", 0) >= 2000 else f"{result['total_fills']:>4} fills"
                print(f"  {status} {addr[:12]}... PnL=${t['pnl']:>8.0f} WR={t['wr']:>5.1f}% "
                      f"PF={t['pf']:>6.2f} DD={t['dd']:>5.1f}% weeks_ok={cw}/4 {cap} | "
                      f"weekly_PnL=[{','.join(f'${p:,.0f}' for p in pnls)}]")

                save_validations(validations)

            total_valid = sum(1 for v in validations.values() if v.get("valid"))
            total_weak = sum(1 for v in validations.values() if not v.get("valid"))
            print(f"  Tổng validated: {len(validations)} | "
                  f"✅ Valid: {total_valid} | ⏳ Weak: {total_weak}")

        print(f"  Ngủ {SLEEP_SECS}s...")
        time.sleep(SLEEP_SECS)


if __name__ == "__main__":
    main()
