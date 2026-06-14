"""Mô phỏng copy chính xác: $50 USDT x20, mirror từng fill"""
import json, math, statistics
from collections import defaultdict
from datetime import datetime, timezone

with open("/home/bot/hl_copy_bot/deep_analysis.json") as f:
    fills = json.load(f)

CAPITAL = 50.0
MAX_LEV = 20.0

# ─── compute scale ───
max_notional = 0
for f in fills:
    if f["coin"].startswith("@"):
        continue
    sp = abs(float(f.get("startPosition", "0")))
    px = float(f["px"])
    val = sp * px
    if val > max_notional:
        max_notional = val

scale = min(CAPITAL * MAX_LEV / max_notional, 1.0)
print(f"Max target position: \${max_notional:,.0f}")
print(f"Scale: {scale:.6f}x (chúng ta = target × {scale:.6f})")
print(f"Position tối đa của ta: \${max_notional * scale:,.2f}")
print()

# ─── mirror từng fill ───
sf = sorted(fills, key=lambda f: int(f["time"]))
pos = {}   # coin -> {"size": float, "entry_px": float}
cash = CAPITAL
trades = []
coin_pnl = defaultdict(float)
daily_pnl = defaultdict(float)

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

    # our_delta: positive = buy/long, negative = sell/short
    our_delta = our_sz if side == "B" else -our_sz
    old = pos.get(coin, {}).get("size", 0)
    new = old + our_delta

    reducing = (old > 0 and our_delta < 0) or (old < 0 and our_delta > 0)

    pnl = 0.0
    if reducing:
        reduce_sz = min(abs(our_delta), abs(old))
        entry = pos[coin]["entry_px"]
        if old > 0:  # long → sell
            pnl = (px - entry) * reduce_sz
        else:        # short → buy back
            pnl = (entry - px) * reduce_sz
        cash += pnl
        trades.append({
            "coin": coin, "pnl": round(pnl, 4), "ts": ts,
            "close": abs(new) < 0.00001,
            "sz": reduce_sz, "entry": entry, "exit": px,
        })
        day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        daily_pnl[day] += pnl
        coin_pnl[coin] += pnl

    flip = reducing and ((old > 0 and new < 0) or (old < 0 and new > 0))
    if flip:
        pos[coin] = {"size": new, "entry_px": px}
    elif abs(new) < 0.00001:
        pos.pop(coin, None)
    elif reducing:
        pos[coin]["size"] = new
    else:
        # adding or opening
        if coin in pos:
            old_abs = abs(old)
            pos[coin]["entry_px"] = (pos[coin]["entry_px"] * old_abs + px * abs(our_delta)) / (old_abs + abs(our_delta))
            pos[coin]["size"] = new
        else:
            pos[coin] = {"size": new, "entry_px": px}

# ─── thống kê ───
pnls = [t["pnl"] for t in trades]
wins = [p for p in pnls if p > 0]
losses = [p for p in pnls if p < 0]
n = len(trades)
total = sum(pnls)
wr = len(wins) / n * 100 if n else 0
avg_w = sum(wins) / len(wins) if wins else 0
avg_l = sum(losses) / len(losses) if losses else 0
pf = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else float("inf")

if len(daily_pnl) > 1:
    daily_ret = [v / CAPITAL for v in daily_pnl.values()]
    sharpe = (statistics.mean(daily_ret) / max(statistics.stdev(daily_ret), 1e-9)) * math.sqrt(365)
else:
    sharpe = 0

# max DD
eq = CAPITAL
peak = CAPITAL
max_dd = 0
for t in trades:
    eq += t["pnl"]
    if eq > peak:
        peak = eq
    dd = (peak - eq) / peak * 100
    if dd > max_dd:
        max_dd = dd

# ─── BÁO CÁO ───
print("=" * 62)
print("  KẾT QUẢ COPY: $50 USDT x20")
print("=" * 62)
print(f"  Vốn:                \${CAPITAL:.0f}")
print(f"  Đòn bẩy tối đa:      {MAX_LEV:.0f}x")
print(f"  Số lần mirror:       {n}")
print(f"  Thời gian:           3.6 ngày (10-14/06/2026)")
print()
print(f"  Lợi nhuận thực tế:   \${total:>+8.2f}")
print(f"  Vốn cuối:            \${cash:>8.2f}")
print(f"  Tỷ suất lợi nhuận:   {total/CAPITAL*100:>+8.2f}%")
print(f"  Trung bình ngày:     \${total/3.6:>+8.2f}")
print(f"  Ngoại suy tháng:     \${total/3.6*30:>+8.2f}")
print()
print(f"  Win rate:            {wr:.1f}%")
print(f"  Avg win:             \${avg_w:.4f}")
print(f"  Avg loss:            \${avg_l:.4f}")
print(f"  Profit Factor:       {pf:.1f}")
print(f"  Sharpe:              {sharpe:.2f}")
print(f"  Max DD:              {max_dd:.2f}%")
print(f"  Lệnh cùng lúc (ta):  {len(pos)} (đang mở)")

# Mấy giao dịch thật
print(f"\n{'=' * 62}")
print(f"  VÍ DỤ GIAO DỊCH THẬT")
print(f"{'=' * 62}")
for t in trades[:8]:
    ts = datetime.fromtimestamp(t["ts"] / 1000, tz=timezone.utc).strftime("%m/%d %H:%M")
    label = "ĐÓNG" if t["close"] else "GIẢM"
    print(f"  {ts} {label:6} {t['coin']:>8} entry={t['entry']:>8.2f} exit={t['exit']:>8.2f} PnL=\${t['pnl']:>+7.4f}")

# PnL theo coin
print(f"\n{'=' * 62}")
print(f"  PnL THEO COIN")
print(f"{'=' * 62}")
for coin, pnl in sorted(coin_pnl.items(), key=lambda x: abs(x[1]), reverse=True):
    cnt = sum(1 for t in trades if t["coin"] == coin)
    print(f"  {coin:>10}: \${pnl:>+8.2f} ({cnt} lần, {pnl/total*100:.0f}%)")

# PnL theo ngày
print(f"\n{'=' * 62}")
print(f"  PnL THEO NGÀY")
print(f"{'=' * 62}")
for d in sorted(daily_pnl):
    print(f"  {d}: \${daily_pnl[d]:>+8.2f}")

# Risk analysis
print(f"\n{'=' * 62}")
print(f"  PHÂN TÍCH RỦI RO")
print(f"{'=' * 62}")
print(f"  1. Data chỉ 3.6 ngày — chưa đại diện")
print(f"  2. Win rate 94% trong thị trường thuận lợi")
print(f"  3. HYPE chiếm {coin_pnl.get('HYPE', 0)/total*100:.0f}% lợi nhuận")
print(f"  4. Họ không dùng stop loss — nếu crash, lỗ lớn")
print(f"  5. Mỗi lệnh lời rất nhỏ (\${avg_w:.4f}) — đủ 1 lần lỗ lớn là mất hết")
print(f"  6. Vị thế đang mở: {len(pos)} coin — nếu gap ngược, lỗ thêm")
for coin, p in pos.items():
    last = [f for f in sf if f["coin"] == coin]
    cur = float(last[-1]["px"]) if last else 0
    if p["size"] > 0:
        open_pnl = (cur - p["entry_px"]) * p["size"]
    else:
        open_pnl = (p["entry_px"] - cur) * abs(p["size"])
    print(f"     {coin}: size={p['size']:.4f} entry={p['entry_px']:.2f} cur={cur:.2f} openPnL=\${open_pnl:+.4f}")
