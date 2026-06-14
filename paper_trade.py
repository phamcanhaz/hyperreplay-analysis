"""
Real-time paper trading monitor for wallet #3
Subscribes to userFills via WebSocket (no auth needed)
Simulates copy with $50 USDT x20 — logs everything, no real orders
"""
import json, asyncio, os
from collections import defaultdict
from datetime import datetime, timezone
import math

TARGET = "0x6dbbefad3d24da625fa233c070678ab1938fcd38"
WS = "wss://api.hyperliquid.xyz/ws"
CAPITAL = 50.0
MAX_LEV = 20.0
LOG_FILE = "/home/bot/hyperreplay-analysis/paper_trade.log"

# Load fills to compute scale
fills_file = "/home/bot/hl_copy_bot/deep_analysis.json"
max_notional = 0
try:
    with open(fills_file) as f:
        for fill in json.load(f):
            sp = abs(float(fill.get("startPosition", "0")))
            px = float(fill["px"])
            if sp * px > max_notional:
                max_notional = sp * px
except:
    max_notional = 100000  # fallback

scale = min(CAPITAL * MAX_LEV / max_notional, 1.0) if max_notional > 0 else 0

class PaperTrader:
    def __init__(self):
        self.cash = CAPITAL
        self.pos = {}  # coin -> {"size": float, "entry_px": float, "entry_time": int}
        self.trades = []
        self.start_time = None
        self.log_lines = []
        self.coin_pnl = defaultdict(float)
        self.daily_pnl = defaultdict(float)
        self.seen = set()  # dedup hashes

    def log(self, msg, also_print=True):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.log_lines.append(line)
        if also_print:
            print(line, flush=True)

    def handle(self, fill):
        hash_ = fill.get("hash", "")
        if hash_ and hash_ in self.seen:
            return
        if hash_:
            self.seen.add(hash_)

        coin = fill["coin"]
        side = fill["side"]
        sz = float(fill["sz"])
        px = float(fill["px"])
        fee = float(fill.get("fee", "0"))
        ts = int(fill["time"])

        if self.start_time is None:
            self.start_time = ts
            self.log(f"Bắt đầu paper trade — vốn ${CAPITAL} x{MAX_LEV}, scale={scale:.6f}x")

        if coin.startswith("@"):
            return

        our_sz = sz * scale
        if abs(our_sz) < 0.00001:
            return

        our_delta = our_sz if side == "B" else -our_sz
        old = self.pos.get(coin, {}).get("size", 0)
        new = old + our_delta
        reducing = (old > 0 and our_delta < 0) or (old < 0 and our_delta > 0)

        pnl = 0.0
        if reducing:
            reduce_sz = min(abs(our_delta), abs(old))
            entry = self.pos[coin]["entry_px"]
            if old > 0:
                pnl = (px - entry) * reduce_sz
            else:
                pnl = (entry - px) * reduce_sz
            self.cash += pnl
            label = "ĐÓNG" if abs(new) < 0.00001 else "GIẢM"
            self.log(f"{label:6} {coin:>8} sz={our_sz:.4f} entry={entry:.2f} exit={px:.2f} PnL=${pnl:+.2f}")

            self.trades.append({"coin": coin, "pnl": round(pnl, 2), "ts": ts})
            day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            self.daily_pnl[day] += pnl
            self.coin_pnl[coin] += pnl

            # Check DD
            peak = CAPITAL + sum(t["pnl"] for t in self.trades if t != self.trades[-1])
            dd = (CAPITAL - self.cash) / CAPITAL * 100 if self.cash < CAPITAL else 0
            if dd > 5:
                self.log(f"⚠️  DD vượt 5%: {dd:.1f}%")

        flip = reducing and ((old > 0 and new < 0) or (old < 0 and new > 0))
        if flip:
            self.pos[coin] = {"size": new, "entry_px": px, "entry_time": ts}
        elif abs(new) < 0.00001:
            self.pos.pop(coin, None)
        elif reducing:
            self.pos[coin]["size"] = new
        else:
            if coin in self.pos:
                old_abs = abs(old)
                self.pos[coin]["entry_px"] = (self.pos[coin]["entry_px"] * old_abs + px * abs(our_delta)) / (old_abs + abs(our_delta))
                self.pos[coin]["size"] = new
                self.pos[coin]["entry_time"] = ts
            else:
                self.pos[coin] = {"size": new, "entry_px": px, "entry_time": ts}

        # Print status every 10 trades
        if len(self.trades) % 10 == 0 and len(self.trades) > 0:
            self.show_status()

    def show_status(self):
        total_pnl = sum(t["pnl"] for t in self.trades)
        n = len(self.trades)
        wins = sum(1 for t in self.trades if t["pnl"] > 0)
        wr = wins / n * 100 if n else 0
        print(f"\n{'='*55}")
        print(f"  STATUS: {n} trades | PnL=${total_pnl:+.2f} | Cash=${self.cash:.2f} | WR={wr:.1f}% | Pos={len(self.pos)}")
        print(f"  Daily: ", end="")
        for d in sorted(self.daily_pnl):
            print(f"{d}=${self.daily_pnl[d]:+.2f} ", end="")
        print()
        print(f"{'='*55}\n", flush=True)

    def print_summary(self):
        total_pnl = sum(t["pnl"] for t in self.trades)
        n = len(self.trades)
        wins = [t["pnl"] for t in self.trades if t["pnl"] > 0]
        losses = [t["pnl"] for t in self.trades if t["pnl"] < 0]
        wr = len(wins) / n * 100 if n else 0

        print(f"\n{'='*55}")
        print(f"  KẾT THÚC PAPER TRADING")
        print(f"{'='*55}")
        print(f"  Vốn:          ${CAPITAL:.0f}")
        print(f"  Đòn bẩy:      {MAX_LEV}x")
        print(f"  Scale:        {scale:.6f}x")
        print(f"  Tổng trades:  {n}")
        print(f"  Lợi nhuận:    ${total_pnl:+.2f}")
        print(f"  Vốn cuối:     ${self.cash:.2f}")
        print(f"  Return:       {total_pnl/CAPITAL*100:+.2f}%")
        print(f"  Win rate:     {wr:.1f}%")
        print(f"  PnL/ngày:     ${total_pnl/max(len(self.daily_pnl),1):+.2f}")
        print()
        print("  PnL theo coin:")
        for coin, pnl in sorted(self.coin_pnl.items(), key=lambda x: abs(x[1]), reverse=True):
            print(f"    {coin:>10}: ${pnl:+.2f}")
        print()
        if self.pos:
            print("  Vị thế đang mở:")
            for coin, p in sorted(self.pos.items()):
                print(f"    {coin}: size={p['size']:.4f} entry={p['entry_px']:.2f}")
        print(f"{'='*55}")

    def save_log(self):
        with open(LOG_FILE, "w") as f:
            f.write("\n".join(self.log_lines))
        print(f"\nLog saved to {LOG_FILE}")

async def main():
    import websockets

    trader = PaperTrader()
    trader.log(f"Kết nối WebSocket: {WS}")
    trader.log(f"Target: {TARGET[:16]}...")
    trader.log(f"Scale: {scale:.6f}x (max target notional \${max_notional:,.0f})")
    trader.log(f"Ví sẽ chạy, Ctrl+C để dừng\n")

    reconnect_attempt = 0
    while True:
        try:
            async with websockets.connect(WS, ping_interval=30) as ws:
                reconnect_attempt = 0
                # Sub userFills + allMids (allMids giữ kết nối)
                await ws.send(json.dumps({
                    "method": "subscribe",
                    "subscription": {"type": "userFills", "user": TARGET},
                }))
                await ws.send(json.dumps({
                    "method": "subscribe",
                    "subscription": {"type": "allMids"},
                }))
                trader.log("✅ Đã kết nối, đang chờ fills...")

                async for msg in ws:
                    data = json.loads(msg)
                    if data.get("channel") != "userFills":
                        continue
                    payload = data.get("data", {})
                    fills = payload.get("fills", []) if isinstance(payload, dict) else payload
                    if not isinstance(fills, list):
                        fills = [fills]
                    for fill in fills:
                        if isinstance(fill, dict) and "coin" in fill:
                            trader.handle(fill)

        except (asyncio.CancelledError, KeyboardInterrupt):
            print("\n\nNhận tín hiệu dừng...")
            trader.print_summary()
            trader.save_log()
            break
        except Exception as e:
            reconnect_attempt += 1
            delay = min(30, 2 ** reconnect_attempt)
            trader.log(f"⚠️  Lỗi: {e} — thử lại sau {delay}s", also_print=True)
            await asyncio.sleep(delay)
            continue

if __name__ == "__main__":
    asyncio.run(main())
