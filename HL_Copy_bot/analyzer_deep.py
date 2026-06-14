#!/usr/bin/env python3
"""Deep wallet analyzer — trade reconstruction from fills.

Replaces Rust 15d analysis + old validator.py.
Uses HyperReplay-style reconstruction (chronological fills → individual trades).
"""
import json
import os
import time
import sys
import warnings
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any
import urllib.request
import urllib.error

warnings.filterwarnings("ignore", category=UserWarning, module="pandas")
warnings.filterwarnings("ignore", message="Model is not converging")
warnings.filterwarnings("ignore", message="Some rows of transmat_")

HL_INFO = "https://api.hyperliquid.xyz/info"
BASE = "/home/bot/hl_copy_bot"
DB_FILE = f"{BASE}/seen_wallets.json"
VALIDATION_FILE = f"{BASE}/validation_results.json"
ANALYSIS_REPORT = f"{BASE}/analysis_report.txt"
SLEEP_SECS = 300
MAX_WORKERS = 8
MIN_TRADES = 15
MIN_WR = 35.0
MIN_PF = 1.1
MIN_PNL = 500.0
MAX_DD = 50.0
FILL_CAP = 2000

# RIFT integration modules
import sys
sys.path.insert(0, BASE)
from rift_modules.montecarlo import mc_simulate_daily
from rift_modules.decay import compute_trader_alpha_decay
from rift_modules.regime import HMMRegimeDetector

# Global HMM regime detector — trained once per cycle on BTC price
_regime_detector = HMMRegimeDetector(n_states=3, n_restarts=5, vol_window=24)
_last_closes: list[float] = []
_last_funding: list[float] = []
_current_regime: str = "unknown"

ANALYSIS_DAYS = 30
FETCH_TIMEOUT = 15
MAX_TRADES_PER_DAY = 20
MAX_LOSING_DAYS_STREAK = 5
MIN_ACTIVE_DAYS = 3


def now_ts() -> int:
    return int(time.time())


def fetch_fills(addr: str, start_time: int) -> list[dict] | None:
    payload = json.dumps({
        "type": "userFillsByTime",
        "user": addr,
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
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        return None


# ─── Trade Reconstruction (port from analysis/replay.rs) ───

def reconstruct_trades(fills: list[dict]) -> tuple[list[dict], list[dict]]:
    sorted_fills = sorted(fills, key=lambda f: f["time"])
    trades = []
    open_pos: dict[str, dict] = {}

    for f in sorted_fills:
        coin = f["coin"]
        prev_sz = f["start_position"]
        new_sz = prev_sz - f["sz"] if f["side"] == "A" else prev_sz + f["sz"]
        closed = (prev_sz > 0 and new_sz <= 0) or (prev_sz < 0 and new_sz >= 0)

        if prev_sz == 0:
            # Opening a new position
            open_pos[coin] = {
                "coin": coin,
                "size": new_sz,
                "entry_px": f["px"],
                "entry_time": f["time"],
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
                    "coin": coin,
                    "side": direction,
                    "entry_px": ot["entry_px"],
                    "exit_px": f["px"],
                    "entry_time": ot["entry_time"],
                    "exit_time": f["time"],
                    "hold_secs": hold,
                    "net_pnl": round(net_pnl, 2),
                    "roi_pct": round(roi, 2),
                    "closed": True,
                })
            if abs(new_sz) > 0.0001:
                open_pos[coin] = {
                    "coin": coin,
                    "size": new_sz,
                    "entry_px": f["px"],
                    "entry_time": f["time"],
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
                "coin": coin,
                "size": abs(ot["size"]),
                "entry_px": ot["entry_px"],
                "side": "LONG" if ot["size"] > 0 else "SHORT",
            })

    return trades, end_positions


# ─── Metrics ───

def calc_max_dd(curve: list[float]) -> float:
    if not curve:
        return 0.0
    peak = curve[0]
    mdd = 0.0
    for v in curve:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak * 100
            if dd > mdd:
                mdd = dd
    return mdd


def compute_metrics(trades: list[dict], fills: list[dict], initial_equity: float = 0.0) -> dict:
    total_pnl = gp = gl = 0.0
    wins = total_trades = 0
    equity_curve = []
    equity = initial_equity
    coin_stats: dict[str, dict] = {}

    for t in trades:
        net = t["net_pnl"]
        total_pnl += net
        equity += net
        equity_curve.append(equity)
        total_trades += 1
        if net > 0.001:
            wins += 1
            gp += net
        elif net < -0.001:
            gl += abs(net)

        cs = coin_stats.setdefault(t["coin"], {"trades": 0, "wins": 0, "pnl": 0.0})
        cs["trades"] += 1
        cs["pnl"] += net
        if net > 0.001:
            cs["wins"] += 1

    # Fallback: use raw fills if no reconstructed trades
    if total_trades == 0 and fills:
        for f in fills:
            net = f["closed_pnl"] - f["fee"]
            total_pnl += net
            equity += net
            equity_curve.append(equity)
            if net > 0.001:
                wins += 1
                total_trades += 1
                gp += net
            elif net < -0.001:
                total_trades += 1
                gl += abs(net)

    wr = (wins / total_trades * 100) if total_trades > 0 else 0
    pf = (gp / gl) if gl > 0 else (999 if gp > 0 else 0)
    dd = calc_max_dd(equity_curve) if equity_curve else 0

    # Win rate per coin
    coin_wr = {}
    for c, cs in coin_stats.items():
        coin_wr[c] = round(cs["wins"] / cs["trades"] * 100, 1) if cs["trades"] > 0 else 0

    # Hold time stats
    hold_times = [t["hold_secs"] for t in trades if t["closed"]]
    avg_hold = sum(hold_times) / len(hold_times) if hold_times else 0

    return {
        "total_pnl": round(total_pnl, 2),
        "gross_profit": round(gp, 2),
        "gross_loss": round(gl, 2),
        "total_trades": total_trades,
        "win_trades": wins,
        "win_rate": round(wr, 2),
        "profit_factor": round(pf, 2),
        "max_dd": round(dd, 2),
        "avg_hold_secs": round(avg_hold, 1),
        "coin_win_rates": coin_wr,
    }


def calc_score(trades: int, wr: float, pf: float, dd: float, pnl: float, active_days: int = 5) -> float:
    tc = min(trades / 30, 1.0)
    t = min(trades / 100, 1.0) * 15
    w = (wr / 100) * 20
    p = min(pf / 10, 1.0) * 20 * tc
    d = max(1 - min(dd, 50) / 50, 0) * 15 * tc
    r = min(pnl / 5000, 1.0) * 30 * tc
    score = t + w + p + d + r
    dc = min(active_days / 5, 1.0)
    return max(min(score * dc, 100), 0)


def is_worthy(m: dict, daily: dict, ls: dict, strategy: str, bias: str,
              mc_prob: float | None = None) -> bool:
    if strategy == "SCALPER":
        return False
    if daily["active_days"] < MIN_ACTIVE_DAYS:
        return False
    if daily["max_losing_streak"] >= MAX_LOSING_DAYS_STREAK:
        return False
    if m["total_trades"] < MIN_TRADES:
        return False
    if m["win_rate"] < MIN_WR:
        return False
    if m["total_pnl"] < MIN_PNL:
        return False
    if m["max_dd"] > MAX_DD:
        return False
    if m["profit_factor"] < MIN_PF:
        return False
    if ls.get("long") and ls["long"]["count"] >= 5:
        min_lw = 45 if bias in ("STRONG LONG", "LONG") else 30
        if ls["long"]["wr"] < min_lw:
            return False
    if ls.get("short") and ls["short"]["count"] >= 5:
        min_sw = 45 if bias in ("STRONG SHORT", "SHORT") else 30
        if ls["short"]["wr"] < min_sw:
            return False
    if mc_prob is not None and mc_prob >= 0.30:
        return False
    return True


# ─── Bias detection ───

def detect_bias(trades: list[dict], fills: list[dict]) -> str:
    lc = sum(1 for t in trades if t["side"] == "LONG")
    sc = sum(1 for t in trades if t["side"] == "SHORT")
    if lc == 0 and sc == 0:
        # fallback to fill sides
        for f in fills:
            if f["side"] == "A":
                sc += 1
            else:
                lc += 1
    if sc > lc * 3:
        return "STRONG SHORT"
    if sc > lc:
        return "SHORT"
    if lc > sc * 3:
        return "STRONG LONG"
    if lc > sc:
        return "LONG"
    return "NEUTRAL"


# ─── Strategy classification ───

def classify_strategy(trades: list[dict], active_days: int = 30) -> str:
    hold_times = [t["hold_secs"] for t in trades if t["closed"]]
    if not hold_times:
        return "UNKNOWN"
    avg_hold = sum(hold_times) / len(hold_times)
    days = max(active_days, 1)

    if avg_hold < 300:
        return "SCALPER"
    if avg_hold < 14400:
        return "DAY_TRADER"
    if avg_hold < 86400 * 3:
        return "SWING"
    return "POSITION"


def daily_stats(trades: list[dict]) -> dict:
    by_day: dict[str, list[float]] = {}
    for t in trades:
        day = datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).strftime("%Y-%m-%d")
        by_day.setdefault(day, []).append(t["net_pnl"])

    if not by_day:
        return {"active_days": 0, "avg_pnl_per_day": 0, "losing_days": 0,
                "max_losing_streak": 0, "max_winning_streak": 0,
                "best_day": 0, "worst_day": 0}

    day_pnls = {day: sum(pnls) for day, pnls in by_day.items()}
    losing_streak = max_streak = 0
    win_streak = max_win = 0
    for day in sorted(day_pnls):
        p = day_pnls[day]
        if p < 0:
            losing_streak += 1
            win_streak = 0
        else:
            max_streak = max(max_streak, losing_streak)
            losing_streak = 0
            win_streak += 1
            max_win = max(max_win, win_streak)
    max_streak = max(max_streak, losing_streak)

    losing_days = sum(1 for p in day_pnls.values() if p < 0)
    vals = list(day_pnls.values())

    return {
        "active_days": len(day_pnls),
        "avg_pnl_per_day": round(sum(vals) / len(vals), 2),
        "best_day": round(max(vals), 2),
        "worst_day": round(min(vals), 2),
        "losing_days": losing_days,
        "max_losing_streak": max_streak,
        "max_winning_streak": max_win,
        "_day_pnls": list(vals),  # for Monte Carlo
    }


def long_short_breakdown(trades: list[dict]) -> dict:
    long_trades = [t for t in trades if t["side"] == "LONG"]
    short_trades = [t for t in trades if t["side"] == "SHORT"]

    def stats(group):
        if not group:
            return None
        wins = sum(1 for t in group if t["net_pnl"] > 0)
        pnl = sum(t["net_pnl"] for t in group)
        return {
            "count": len(group),
            "wr": round(wins / len(group) * 100, 1),
            "pnl": round(pnl, 2),
            "avg_pnl": round(pnl / len(group), 2),
        }

    return {
        "long": stats(long_trades),
        "short": stats(short_trades),
    }


def per_coin_breakdown(trades: list[dict]) -> dict:
    by_coin: dict[str, list[float]] = {}
    for t in trades:
        by_coin.setdefault(t["coin"], []).append(t["net_pnl"])

    result = {}
    total = len(trades)
    for coin, pnls in by_coin.items():
        wins = sum(1 for p in pnls if p > 0)
        result[coin] = {
            "trades": len(pnls),
            "pnl": round(sum(pnls), 2),
            "wr": round(wins / len(pnls) * 100, 1) if pnls else 0,
            "weight": round(len(pnls) / total * 100, 1) if total else 0,
        }
    return result


def hourly_activity(trades: list[dict]) -> dict:
    hours = [datetime.fromtimestamp(t["entry_time"], tz=timezone.utc).hour for t in trades]
    if not hours:
        return {"active_hours": [], "peak_hour": -1, "session": "UNKNOWN"}
    cnt = Counter(hours)
    peak = cnt.most_common(1)[0][0]
    asia = sum(cnt[h] for h in range(0, 8))
    europe = sum(cnt[h] for h in range(8, 16))
    us = sum(cnt[h] for h in range(16, 24))
    session = max([("ASIA", asia), ("EUROPE", europe), ("US", us)], key=lambda x: x[1])[0]
    return {
        "active_hours": sorted(cnt.keys()),
        "peak_hour": peak,
        "session": session,
    }


def calc_copyability(avg_tpd: float, avg_hold_secs: float, strategy: str) -> float:
    if strategy == "SCALPER":
        return 0.0
    score = 100.0
    # Long-term strategies (SWING/POSITION) should not be penalized as harshly for high TPD
    tpd_penalty = 0.5 if strategy in ("SWING", "POSITION") else 1.0
    if avg_tpd > 30: score -= 50 * tpd_penalty
    elif avg_tpd > 15: score -= 25 * tpd_penalty
    elif avg_tpd > 10: score -= 10 * tpd_penalty
    if avg_hold_secs < 120: score -= 40
    elif avg_hold_secs < 600: score -= 20
    elif avg_hold_secs < 1800: score -= 5
    return max(score, 0)


def collect_warnings(m: dict, daily: dict, ls: dict, strategy: str, pc: dict) -> list[str]:
    w = []
    if strategy == "SCALPER":
        w.append("SCALPER")
    if daily["max_losing_streak"] >= MAX_LOSING_DAYS_STREAK:
        w.append(f"LOSING_STREAK_{daily['max_losing_streak']}")
    if ls.get("long") and ls["long"]["wr"] < 30:
        w.append("POOR_LONG_WR")
    if ls.get("short") and ls["short"]["wr"] < 30:
        w.append("POOR_SHORT_WR")
    if daily["active_days"] < MIN_ACTIVE_DAYS:
        w.append("FEW_ACTIVE_DAYS")
    if pc:
        top = max(c["weight"] for c in pc.values())
        if top > 70:
            w.append(f"CONCENTRATION_{top:.0f}%")
    return w


# ─── IO ───

def load_db() -> dict:
    try:
        with open(DB_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_validations() -> dict:
    try:
        with open(VALIDATION_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_validations(v: dict):
    tmp = VALIDATION_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(v, f, indent=2)
    os.replace(tmp, VALIDATION_FILE)


# ─── Main analysis ───

def analyze_one(addr: str, cutoff: int) -> dict | None:
    fills = fetch_fills(addr, cutoff)
    if fills is None:
        return None
    if not fills:
        return {"valid": False, "reason": "no_fills"}

    # Estimate initial equity from max position notional (assume 2x leverage) for realistic DD
    max_notional = 0.0
    for f in fills:
        pos = abs(f.get("start_position", 0))
        notional = pos * f["px"]
        if notional > max_notional:
            max_notional = notional
    init_equity = max_notional / 2.0 if max_notional > 0 else 0.0

    trades, end_pos = reconstruct_trades(fills)
    m = compute_metrics(trades, fills, initial_equity=init_equity)
    bias = detect_bias(trades, fills)
    daily = daily_stats(trades)
    ls = long_short_breakdown(trades)
    pc = per_coin_breakdown(trades)
    ha = hourly_activity(trades)
    strategy = classify_strategy(trades, daily["active_days"])
    capped = len(fills) >= FILL_CAP

    # Estimate strategy from fill frequency when trades can't be reconstructed
    if strategy == "UNKNOWN" and fills:
        tpd_est = len(fills) / ANALYSIS_DAYS
        if tpd_est > 20:
            strategy = "SCALPER"
        elif tpd_est > 2:
            strategy = "DAY_TRADER"
        elif tpd_est > 0.5:
            strategy = "SWING"
        else:
            strategy = "POSITION"

    active = daily["active_days"] if daily["active_days"] > 0 else ANALYSIS_DAYS
    tpd = len(fills) / max(active, 1) if not trades else len(trades) / max(active, 1)
    hold = m["avg_hold_secs"]
    copyability = calc_copyability(tpd, hold, strategy)
    warnings = collect_warnings(m, daily, ls, strategy, pc)

    # Score (0-100) with active_days penalty
    sc = calc_score(m["total_trades"], m["win_rate"], m["profit_factor"], m["max_dd"], m["total_pnl"], active_days=daily["active_days"])

    # ─── RIFT: Alpha decay ───
    alpha = compute_trader_alpha_decay(trades)
    if alpha.get("decay_detected"):
        warnings.append("ALPHA_DECAYING")
    if alpha.get("warning") and alpha["warning"] not in warnings:
        warnings.append(alpha["warning"])

    # ─── RIFT: Monte Carlo ───
    mc = {"p50": 0, "prob_negative": 0.0, "expected_profit": 0, "num_simulations": 0}
    daily_pnl_list = [day_pnl for day_pnl in daily.get("_day_pnls", [])] if daily.get("_day_pnls") else []
    if len(daily_pnl_list) >= 3:
        mc = mc_simulate_daily(daily_pnl_list, n_simulations=5000, horizon_days=30)

    # ─── RIFT: Regime mismatch warning ───
    regime_warning = False
    crisis_regime = False
    if _regime_detector.trained:
        regime = _regime_detector.predict_regime(_last_closes, _last_funding)
        # Realtime vol override: BTC move >3% trong 6h → volatile
        if len(_last_closes) >= 6:
            recent_move = abs(_last_closes[-1] / _last_closes[-6] - 1)
            if recent_move > 0.03:
                regime = "volatile"
        if regime == "crisis":
            warnings.append("CRISIS_REGIME")
            regime_warning = True
            crisis_regime = True
        elif bias in ("STRONG LONG", "LONG") and regime == "volatile":
            warnings.append("REGIME_MISMATCH")
            regime_warning = True
        elif bias in ("STRONG SHORT", "SHORT") and regime == "calm":
            warnings.append("REGIME_MISMATCH")
            regime_warning = True

    worthy = is_worthy(m, daily, ls, strategy, bias, mc.get("prob_negative"))
    if crisis_regime:
        worthy = False

    # For capped wallets: use fill-level metrics with SAME thresholds
    if capped and not worthy and strategy not in ("SCALPER",):
        fill_pnl = sum(f["closed_pnl"] - f["fee"] for f in fills)
        fill_gp = sum(max(0, f["closed_pnl"] - f["fee"]) for f in fills)
        fill_gl = sum(max(0, -(f["closed_pnl"] - f["fee"])) for f in fills)
        fill_wins = sum(1 for f in fills if f["closed_pnl"] - f["fee"] > 0.001)
        fill_trades = sum(1 for f in fills if abs(f["closed_pnl"] - f["fee"]) > 0.001)
        fill_wr = fill_wins / fill_trades * 100 if fill_trades > 0 else 0
        fill_pf = fill_gp / fill_gl if fill_gl > 0 else 999.0
        worthy = (fill_trades >= MIN_TRADES and fill_wr >= MIN_WR
                  and fill_pf >= MIN_PF and fill_pnl >= MIN_PNL)

    return {
        "valid": worthy,
        "worthy": worthy,
        "bias": bias,
        "strategy": strategy,
        "capped": capped,
        "total_fills": len(fills),
        "trades_reconstructed": len(trades),
        "open_positions": end_pos,
        "consistent_wins": m["win_trades"],
        "total_pnl": m["total_pnl"],
        "gross_profit": m["gross_profit"],
        "gross_loss": m["gross_loss"],
        "total_trades": m["total_trades"],
        "win_trades": m["win_trades"],
        "win_rate": m["win_rate"],
        "profit_factor": m["profit_factor"],
        "max_dd": m["max_dd"],
        "score": sc,
        "avg_hold_secs": hold,
        "coin_win_rates": m["coin_win_rates"],
        "daily": daily,
        "hourly": ha,
        "directional": ls,
        "per_coin": pc,
        "copyability": copyability,
        "warnings": warnings,
        "checked_at": now_ts(),
        # RIFT fields
        "alpha_decay_detected": alpha.get("decay_detected", False),
        "alpha_early_sharpe": alpha.get("early_sharpe"),
        "alpha_late_sharpe": alpha.get("late_sharpe"),
        "mc_p10": round(mc.get("p10", 0), 2),
        "mc_p50": round(mc.get("p50", 0), 2),
        "mc_p90": round(mc.get("p90", 0), 2),
        "mc_prob_negative": round(mc.get("prob_negative", 0.5), 3),
        "mc_expected_profit": round(mc.get("expected_profit", 0), 2),
        "mc_median_max_dd": round(mc.get("median_max_dd", 0), 2),
        "mc_num_simulations": mc.get("num_simulations", 0),
        "regime_mismatch": regime_warning,
    }


def fetch_btc_market_data() -> tuple[list[float], list[float]]:
    """Fetch BTC 1h close prices + funding rates for HMM regime training.

    Returns (closes, funding_rates) aligned by hour, or ([], []) on failure.
    """
    now_ms = now_ts() * 1000
    start_ms = now_ms - 30 * 86400 * 1000

    # 1. Candle snapshots (1h) — req là nested object theo API HyperLiquid
    payload = json.dumps({
        "type": "candleSnapshot",
        "req": {"coin": "BTC", "interval": "1h", "startTime": start_ms, "endTime": now_ms},
    }).encode()
    req = urllib.request.Request(HL_INFO, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            candles = json.loads(resp.read())
    except Exception:
        return [], []
    if not isinstance(candles, list) or len(candles) < 50:
        return [], []

    closes = [float(c["c"]) for c in candles if isinstance(c, dict)]

    # 2. Funding history
    payload = json.dumps({
        "type": "fundingHistory", "coin": "BTC",
        "startTime": start_ms, "endTime": now_ms,
    }).encode()
    req = urllib.request.Request(HL_INFO, data=payload,
                                 headers={"Content-Type": "application/json"})
    funding_map = {}
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            fdata = json.loads(resp.read())
        if isinstance(fdata, list):
            for f in fdata:
                funding_map[f.get("time", 0)] = float(f.get("fundingRate", "0") or "0")
    except Exception:
        pass

    funding = []
    for c in candles:
        ts = c.get("T", 0)
        if ts in funding_map:
            funding.append(funding_map[ts])
        elif funding:
            funding.append(funding[-1])  # forward fill
        else:
            funding.append(0.0)

    return closes, funding


def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  🔬 HL DEEP ANALYZER — Trade Reconstruction + Scoring     ║")
    print("║  Replaces Rust 15d analysis + old validator                ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"  Thresholds: trades>={MIN_TRADES} WR>={MIN_WR}% PF>={MIN_PF} PnL>=${MIN_PNL} DD<={MAX_DD}% "
          f"TPD<={MAX_TRADES_PER_DAY} active_days>={MIN_ACTIVE_DAYS} max_losing_streak<{MAX_LOSING_DAYS_STREAK}")

    cycle = 0
    last_regime_train = 0
    while True:
        cycle += 1

        # Fetch BTC market data & train HMM regime detector (once per hour)
        if now_ts() - last_regime_train > 3600:
            closes, funding = fetch_btc_market_data()
            if len(closes) >= 100:
                ok = _regime_detector.fit(closes, funding)
                if ok:
                    global _last_closes, _last_funding
                    _last_closes = closes
                    _last_funding = funding
                    regime = _regime_detector.predict_regime(closes, funding)
                    _current_regime = regime
                    print(f"  HMM regime trained ({len(closes)} samples) → {regime}")
                    last_regime_train = now_ts()
                else:
                    print("  HMM regime training failed (insufficient data)")
            else:
                print(f"  HMM regime skipped: only {len(closes)} price samples")

        cutoff = now_ts() - ANALYSIS_DAYS * 86400
        db = load_db()
        validations = load_validations()

        wallets = sorted(
            [(a, w) for a, w in db.items() if isinstance(w, dict)],
            key=lambda x: x[1].get("score", 0) if x[1].get("score") else 0,
            reverse=True,
        )

        # Mix: top 30 re-analysis + up to 20 pending (new/unanalyzed wallets)
        to_analyze = []
        pending = []
        for addr, w in wallets:
            if addr in validations:
                v = validations[addr]
                ago = now_ts() - v.get("checked_at", 0)
                if ago < 3600:
                    continue
                if len(to_analyze) < 30:
                    to_analyze.append(addr)
            else:
                pending.append(addr)
        # Fill remaining slots with pending wallets
        for addr in pending:
            if len(to_analyze) >= 50:
                break
            to_analyze.append(addr)

        if not to_analyze:
            total_v = sum(1 for v in validations.values() if v.get("valid"))
            print(f"\n[{cycle}] Nothing to analyze. {total_v} valid wallets.")
        else:
            print(f"\n[{cycle}] Analyzing {len(to_analyze)} wallets ({MAX_WORKERS} workers)...")

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                fut_map = {pool.submit(analyze_one, addr, cutoff): addr for addr in to_analyze}
                done = 0
                for fut in as_completed(fut_map):
                    addr = fut_map[fut]
                    done += 1
                    try:
                        result = fut.result()
                    except Exception as e:
                        print(f"  ❌ {addr[:12]}... exception: {e}")
                        continue
                    if result is None:
                        print(f"  ❌ {addr[:12]}... API fail")
                        continue

                    validations[addr] = result
                    status = "✅ WORTHY" if result["valid"] else "⏳ WEAK"
                    pnl = result["total_pnl"]
                    wr = result["win_rate"]
                    pf = result["profit_factor"]
                    dd = result["max_dd"]
                    trades = result["total_trades"]
                    score = result["score"]
                    bias = result["bias"]
                    strategy = result.get("strategy", "?")
                    cap = "⚠️ CAPPED" if result.get("capped") else f"{result['total_fills']} fills"
                    rt = result["trades_reconstructed"]
                    hold = result["avg_hold_secs"]
                    hold_str = f"{hold/3600:.1f}h" if hold > 3600 else f"{hold/60:.0f}m"
                    copyability = result.get("copyability", 0)
                    warnings = result.get("warnings", [])
                    warn_str = f" ⚠️{','.join(warnings)}" if warnings else ""
                    print(f"  {status} {addr[:12]}... PnL=${pnl:>8,.0f} WR={wr:>5.1f}% PF={pf:.2f} "
                          f"DD={dd:.1f}% trades={trades} score={score:.0f} {bias} {strategy} "
                          f"copy={copyability:.0f}{warn_str} "
                          f"reconstructed={rt} avg_hold={hold_str} {cap}")
                    save_validations(validations)

            total_v = sum(1 for v in validations.values() if v.get("valid"))
            total_w = sum(1 for v in validations.values() if not v.get("valid"))
            print(f"  ├─ ✅ Worthy: {total_v}")
            print(f"  └─ ⏳ Weak: {total_w}")

        validations["__meta__"] = {
            "regime": _current_regime,
            "updated_at": now_ts(),
        }
        save_validations(validations)

        # Write lightweight regime.json for Rust to poll independently
        regime_file = f"{BASE}/regime.json"
        regime_tmp = regime_file + ".tmp"
        with open(regime_tmp, "w") as f:
            json.dump({"regime": _current_regime, "updated_at": now_ts()}, f)
        os.replace(regime_tmp, regime_file)

        print(f"  Sleep {SLEEP_SECS}s...")
        time.sleep(SLEEP_SECS)


if __name__ == "__main__":
    main()
