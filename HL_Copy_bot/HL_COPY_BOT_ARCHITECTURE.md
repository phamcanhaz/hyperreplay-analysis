# HL Copy Bot — Architecture & Bug Analysis

## Tổng quan

HL Copy Bot là hệ thống copy-trade trên Hyperliquid Mainnet. **Paper trading** với $10,000 vốn ảo. Rust orchestration (Rust 0%) + Python deep analysis (analyzer_deep.py).

Kiến trúc: **5 slot cố định**, mỗi slot có $2,000 capital (PAPER_INITIAL_EQUITY / MAX_COPY_WALLETS). Mỗi slot copy độc lập một target wallet. Tuy nhiên do chỉ có 1 wallet, các slot's desired positions được aggregate vào 1 portfolio duy nhất.

```
                         ┌─────────────┐
                         │ Hyperliquid │
                         │   Mainnet   │
                         └──────┬──────┘
            ┌───────────────────┼───────────────────┐
            │                   │                   │
       ┌────┴────┐       ┌─────┴─────┐       ┌─────┴──────┐
       │ Scanner │       │  Analyzer │       │  WebSocket  │
       │  (Rust) │       │ (Python)  │       │ fill listen │
       └────┬────┘       └─────┬─────┘       └─────┬──────┘
            │                  │                   │
            └──────────────────┼───────────────────┘
                               │
                          ┌────┴──────┐
                          │ Copy Mgmt │
                          │ poll loop │
                          └────┬──────┘
                               │
                     ┌─────────┴─────────┐
                     │ PaperPortfolio    │
                     │ (1 portfolio duy  │
                     │  nhất cho 5 slot) │
                     └───────────────────┘
```

## File map

| File               | Vai trò                                                       | Dòng code |
| ------------------ | ------------------------------------------------------------- | --------- |
| `src/main.rs`      | Orchestration loop (tick 15s) + target selection              | 1-255     |
| `src/scanner.rs`   | Wallet discovery, validation loading, stale checks            | ~300      |
| `src/copier.rs`    | Core reconcile engine: sync_positions, poll loop              | 1-684     |
| `src/ws.rs`        | WebSocket fill listener (JSON ping, resub every 60s)          | 1-182     |
| `src/paper.rs`     | Paper portfolio (1 portfolio, margin model)                   | 1-168     |
| `src/config.rs`    | Constants: COPY_RATIO, SLOT config, timing                    | 1-27      |
| `src/types.rs`     | Structs: WalletInfo, TargetPosition, OurPosition              | 1-70      |
| `src/error.rs`     | AppError enum + retry utility                                 | 1-86      |
| `src/analyzer.rs`  | Rust report generator (reads db)                              | ~100      |
| `analyzer_deep.py` | Python deep analyzer (HMM, Monte Carlo, trade reconstruction) | ~600      |

## Module details

### src/main.rs — Orchestration

```rust
main()
├── Init
│   ├── load_db()                              → seen_wallets.json
│   ├── load_and_apply_validations()            → validation_results.json
│   ├── Copier::new() (paper mode or real)
│   ├── load_snapshot() (restore active copies) → copy_wallets.json
│   └── Spawn 3 tasks:
│       ├── ws::ws_fill_loop()                 [WS listener]
│       ├── copier::poll_targets_loop()        [Reconcile every 60s]
│       └── signal handler (Ctrl+C)
│
└── Loop tick() every MAIN_TICK_SECS (15s)
    ├── scanner::scan_new_wallets()
    ├── scanner::save_db()
    │
    └── [every COPY_MGMT_EVERY_N_SCANS = 5 ticks ≈ 75s]:
        ├── scanner::load_and_apply_validations()
        ├── scanner::evict_stale_wallets()
        ├── Evict not-copy-worthy from active copies
        ├── Auto-add: pick top N wallets by selection_score()
        │   └── Filters: copy_worthy && validated_30d && copyability >= 5.0 && !being_copied
        │   └── Max: MAX_COPY_WALLETS = 5
        │   └── Diversity: MAX_PER_STRATEGY = 2 per strategy
        ├── save_db() + save_snapshot()
        └── analyzer::generate_report()
```

**selection_score() logic** (main.rs:20):

```rust
w.score * penalty * (w.copyability / 100.0) * stale_penalty
```

- penalty: product of warning multipliers (REGIME_MISMATCH=0.5, ALPHA_DECAYING=0.3, CRISIS=0.1, STALE=0.3, INACTIVE=0.5)
- stale_penalty: if last_updated > 10min ago → 0.7, else 1.0

### src/scanner.rs — Wallet discovery

```rust
scan_new_wallets()
├── recentTrades API (BTC, ETH, SOL, HYPE, ...)
│   └── extract users[] from each trade
├── leaderboard API → top 100 rows (sorted by volume/return)
├── Filter: seen[addr] >= 2 && !db.contains(addr)
│   └── new WalletInfo inserted into db
└── Cleanup: seen.retain(|a| !db.contains_key(a))

load_and_apply_validations()
├── Reset ALL wallets: copy_worthy=false, validated_30d=false
├── Read validation_results.json
├── For each wallet in JSON:
│   ├── Parse fields: score, pnl, wr, pf, dd, bias, strategy, copyability
│   ├── checked_at = info["checked_at"] ?? now_ts()
│   ├── Set warnings: REGIME_MISMATCH, ALPHA_DECAYING, CRISIS, STALE_DATA, INACTIVE
│   └── Set copy_worthy = true (nếu pass tất cả thresholds)
├── stale check: per-wallet last_updated > 86400s (24h) → STALE_DATA warning
└── Save via atomic write

evict_stale_wallets()
├── TTL = 30 days
├── Skip wallets being copied
├── age = now - last_updated (or first_seen if last_updated = 0)
└── age > TTL → remove from db
```

### src/copier.rs — Core reconcile engine

#### poll_targets_loop() (main loop)

```rust
poll_targets_loop()
├── Loop:
│   ├── tokio::select!:
│   │   ├── shutdown signal → break
│   │   ├── fill_trigger (WS fill) → wake immediately
│   │   └── poll_once() every RECONCILE_SECS (60s)
│   ├── first_poll: populate last_action for all existing positions
│   ├── BTC crisis detection:
│   │   ├── Ring buffer 6 samples (~5min window)
│   │   ├── BTC drop > 3% → override regime.json → "crisis"
│   │   └── BTC recover to > 98.5% → clear crisis
│   └── health_check_positions() every 300s
```

#### poll_once() (one reconcile cycle)

```rust
poll_once()
├── Fetch prices (allMids)
├── Fetch our positions:
│   ├── Paper mode: unserialized_positions() + get_free_equity()
│   │   └── If bankrupt (eq < 100): reset paper portfolio
│   └── Real mode: HL API clearinghouseState + retry
├── Fetch target positions:
│   └── For each active target: clearinghouseState API
├── sync_positions()  ← CORE
└── Paper report + save
```

#### sync_positions() — 5-slot aggregate copy

Đây là hàm quan trọng nhất. Chi tiết luồng:

```rust
sync_positions()
│
├── slot_cap = PAPER_INITIAL_EQUITY / MAX_COPY_WALLETS  // $2000 — CỐ ĐỊNH
│   (KHÔNG dùng equity động — tránh churn khi equity biến động)
│
├── pos_cap = slot_cap * MAX_POSITION_PCT_EQUITY          // $800 — max per position
│
├── PER-SLOT PROCESSING (mỗi target = 1 slot):
│   for positions in tp.values():
│   │   // Tính total notional của target
│   │   total = sum(pos.size * coin_price)
│   │   if total < $0.01: skip
│   │   // Phân bổ slot_cap ($2000) theo tỷ lệ
│   │   for each position in target:
│   │   │   proportion = position_notional / total_target_notional
│   │   │   n = min(slot_cap * proportion, pos_cap)
│   │   │   if n < $0.01: skip
│   │   │   AGGREGATE into desired{ coin -> (side, notional) }
│   │   │   ├── Same coin, same side:     sum notional
│   │   │   ├── Same coin, opposite side: net (larger wins)
│   │   │   └── New coin:                 insert
│
├── CLOSE: coins in our_positions but NOT in desired
│
├── COOLDOWN: based on regime (crisis=60s, volatile=120s, normal=300s)
│
└── RECONCILE: for each coin in desired:
    ├── Our position exists:
    │   ├── Different side → FLIP (if cooldown expired)
    │   ├── Same side, diff > 30% → RESIZE (if cooldown expired)
    │   ├── Desired < MIN_NOTIONAL ($10) && our >= $10 → CLOSE (too small)
    │   └── Else → SKIP (within tolerance)
    └── No position → OPEN (if desired >= $10)
```

#### health_check_positions()

```rust
health_check_positions()
└── For each target:
    ├── Fetch target positions (clearinghouseState)
    ├── Fetch our positions
    ├── For each coin: diff = |our_size - target_size|
    │   └── if diff > 0.01: log DRIFT
    └── For each coin we have but target doesn't:
        └── log ORPHAN
```

### src/ws.rs — WebSocket fill listener

```rust
ws_fill_loop()  [infinite retry loop]
├── backoff = 1s (reset on non-connect-failure disconnect)
│
├── subscribe_and_stream():
│   ├── connect_async(WS_URL)
│   ├── Subscribe userFills for each active target
│   ├── Verify subscription acknowledgments
│   │   └── All rejected → "permanent" stop
│   ├── Streaming loop:
│   │   ├── read.next() → parse userFills channel
│   │   │   └── fill_trigger.send(counter) → wake poll loop
│   │   ├── ping_interval: every 30s → {"method":"ping"} (JSON text)
│   │   └── resub_interval: every 60s → subscribe new targets
│   └── On Close/Pong/Error → return
│
└── If reason != connect_failed && != no_subscriptions:
    └── backoff = 1s (reset)
  sleep(backoff), backoff = min(backoff*2, 30)
  loop forever (except "permanent" stop)
```

**Ping format** (ws.rs:157): `Message::Text(r#"{"method":"ping"}"#)` — **JSON text ping**, NOT binary `Message::Ping(vec![])`. Bug A: binary ping gây server disconnect mỗi ~60s.

### src/paper.rs — Paper Portfolio

```rust
PaperPortfolio
├── initial_equity: f64 = 10000 (từ PAPER_INITIAL_EQUITY)
├── cash: f64 (tiền mặt — margin model, không đổi khi OPEN)
├── positions: HashMap<coin, PaperPosition>
│   └── PaperPosition: coin, side, size, entry_px, opened_at, realized_pnl
│
├── open(coin, side, size, entry_px, now)
│   └── INSERT position (không deduct cash — margin model)
│
├── close(coin, close_px)
│   ├── REMOVE position
│   └── cash += realized PnL = (close_px - entry_px) * direction * size
│
├── get_equity(prices, _) → cash + Σ unrealized PnL
│   └── Fallback price: pos.entry_px (nếu price fetch fail)
│
├── locked_notional() → Σ (pos.size * pos.entry_px)  // total margin locked
│
├── get_free_equity(prices, _) → equity - locked_notional
│
├── unserialized_positions(prices, _) → HashMap<coin, OurPosition>
│   └── Chuyển PaperPosition → OurPosition (notional = size * current_price)
│
├── save() / load() → paper_portfolio.json (atomic write)
├── reset() → cash = initial_equity, clear positions
└── report() → human-readable portfolio summary
```

### analyzer_deep.py — Python deep analyzer

```python
main()
├── Train HMM regime: 3-state HMM trên BTC price (1h/lần)
├── Lấy top 50 wallets: 30 top score + 20 pending
├── For each wallet:
│   ├── fetch_fills(): 30 ngày từ HL API
│   ├── reconstruct_trades(): chronological fills → trades
│   ├── compute_metrics(): PnL, WR, PF, DD, Score
│   ├── classify_strategy(): SCALPER/DAY_TRADER/SWING/POSITION
│   ├── is_worthy(): threshold checks (skip SCALPER)
│   ├── RIFT analysis:
│   │   ├── montecarlo.py: Monte Carlo simulation
│   │   ├── decay.py: alpha decay detection
│   │   └── regime.py: HMMRegimeDetector
│   └── capped fallback: if is_worthy=False but fill-level pass
│       → recalc worthy (except SCALPER)
├── Write validation_results.json (atomic)
├── Write regime.json (atomic)
└── sleep(300s)
```

### src/config.rs — Constants

```rust
// === Timing ===
pub const MAIN_TICK_SECS: u64 = 15;           // Orchestration loop
pub const RECONCILE_SECS: u64 = 60;            // Reconcile cycle
pub const HEALTH_CHECK_INTERVAL_SECS: u64 = 300;
pub const RECONCILE_COOLDOWN_SECS: u64 = 300;  // Cooldown sau FLIP/RESIZE
pub const COPY_MGMT_EVERY_N_SCANS: u64 = 5;    // Target re-evaluation

// === Copy sizing ===
pub const MAX_COPY_WALLETS: usize = 5;         // Số slot tối đa
pub const MAX_PER_STRATEGY: usize = 2;         // Max 2 targets cùng strategy
pub const COPY_RATIO: f64 = 0.1;               // Copy 10% target position
pub const MIN_NOTIONAL_USD: f64 = 10.0;        // Min position size
pub const MAX_POSITION_PCT_EQUITY: f64 = 0.4;  // Max 40% slot per position

// === File paths ===
pub const SNAPSHOT_FILE: &str = "...copy_wallets.json";
pub const DB_FILE: &str = "...seen_wallets.json";
pub const REGIME_FILE: &str = "...regime.json";
pub const PAPER_FILE: &str = "...paper_portfolio.json";

// === Paper trading ===
pub const PAPER_TRADING: bool = true;
pub const PAPER_INITIAL_EQUITY: f64 = 10000.0;
```

## Data flow — dependency graph

```
                        ┌──────────────────┐
                        │  seen_wallets    │ (scanner saves/loads)
                        │   .json          │
                        └────────┬─────────┘
                                 │
main.rs:tick (15s)              │
  ├── scan_new_wallets ─────────┤
  ├── [every 75s]:              │
  │   ├── load_and_apply_ ──────┤──────────────────┐
  │   │   validations           │                  │
  │   │                         │       ┌──────────┴──────────┐
  │   │                         │       │ validation_results  │
  │   │                         │       │  .json ← Python     │
  │   │                         │       │ analyzer (300s)     │
  │   │                         │       └─────────────────────┘
  │   ├── read_regime ──────────┤───────┐
  │   │                         │       │ regime.json ← Python
  │   ├── auto-add ──────── push ──→ active_targets (Arc<Mutex>)
  │   └── save_snapshot ────────→ copy_wallets.json
  │
ws:ws_fill_loop (async)
  ├── subscribe targets ──── reads ──→ active_targets
  └── fill_trigger ────────── wake ──→ poll_targets_loop

copier:poll_targets_loop (60s + fill trigger)
  ├── fetch_all_mids ─────── POST ──→ HL API allMids
  ├── fetch_target_positions ──→ HL API (clearinghouseState)
  ├── our_positions ──────── reads ──→ PaperPortfolio
  ├── sync_positions ──────── reconcile ──→ PaperPortfolio open/close
  │                           saves ──→ paper_portfolio.json
  └── health_check (300s)

Python (loop 300s):
  ├── fetch fills (30 days) ──→ HL API
  ├── reconstruct_trades
  ├── compute metrics
  ├── is_worthy check
  └── write ──→ validation_results.json, regime.json
```

## Bug history

### Bug 1 — Stale penalty: `checked_at` từ Python

**File**: `scanner.rs` (load_and_apply_validations)
**Status**: ✅ Fixed

**Problem**: `load_and_apply_validations()` dùng `now_ts()` cho `last_updated`. Khi stale check ở `main.rs:37` so sánh `now - last_updated > 600`, tất cả wallets đều "fresh" vì vừa được set. Stale penalty (×0.7) không bao giờ kích hoạt.

**Fix**: Dùng `info["checked_at"]` từ Python thay vì `now_ts()`:

```rust
let checked_at = info.get("checked_at")
    .and_then(|v| v.as_u64())
    .unwrap_or(now_ts());
w.last_updated = checked_at;
```

### Bug 2 — DEFAULT_PX fallback (50000 → entry_px)

**File**: `paper.rs:70-78, 84-97`
**Status**: ✅ Fixed

**Problem**: `get_equity()` và `unserialized_positions()` dùng `DEFAULT_PX=50000` làm fallback khi price fetch fail. Nếu coin giá $60, dùng $50000 → sai notional, sai unrealized PnL, sai position cap.

**Fix**: Dùng `entry_px` của position làm fallback:

```rust
let px = prices.get(&pos.coin).copied().unwrap_or(pos.entry_px);
```

### Bug 3 — WS resubscribe target mới

**File**: `ws.rs:162-177`
**Status**: ✅ Fixed

**Problem**: WS chỉ subscribe target lúc connect. Target mới được thêm vào `active_targets` sau đó không được subscribe → không nhận fill.

**Fix**: Thêm `resub_interval = 60s` trong streaming loop:

```rust
_ = resub_interval.tick() => {
    let current = targets.lock().await.clone();
    for addr in &current {
        if subscribed.contains(addr) { continue; }
        // subscribe addr
        subscribed.insert(addr.clone());
    }
}
```

### Bug 4 — Global exposure cap

**File**: `copier.rs:367-373` (old code)
**Status**: ✅ Đã thay thế bằng fixed-slot model

**Problem** (old equity-ratio code): `sync_positions()` không kiểm tra tổng desired. Nếu 5 targets đều LONG coins khác nhau, total desired > 100% equity → over-leverage.

**Old fix**: Proportional scaling với `MAX_TOTAL_EXPOSURE_PCT=0.8`.

**Current approach**: Fixed-slot model tự động giới hạn: mỗi slot max $2,000 → tổng max $10,000 = equity. Không cần global cap riêng.

### Bug 5 — WS backoff reset

**File**: `ws.rs:32-33`
**Status**: ✅ Fixed

**Problem**: Backoff exponential (×2, max 30s) không reset khi reconnect thành công. Sau 5 lần disconnect → stuck ở 30s.

**Fix**: Reset backoff khi disconnect không phải do connect_failed:

```rust
if reason != "connect_failed" && reason != "no_subscriptions" {
    backoff = 1;
}
```

### Bug 6 — `now_ts()` dùng chung

**File**: `scanner.rs:258`
**Status**: ✅ Fixed

**Problem**: Mỗi file định nghĩa `now_ts()` riêng → sai so sánh thời gian.

**Fix**: Định nghĩa duy nhất trong scanner.rs, các file khác import.

### Bug A — WS ping format (CRITICAL)

**File**: `ws.rs:157`
**Status**: ✅ Fixed

**Problem**: WebSocket gửi `Message::Ping(vec![])` (binary ping frame). Hyperliquid WS server không hiểu binary ping → tưởng client chết → đóng connection mỗi ~60s.

**Evidence**: 29 disconnects / 30 phút (trước fix).

**Fix**: Gửi JSON text ping:

```rust
// CŨ:
if write.send(Message::Ping(vec![])).await.is_err() {
// MỚI:
if write.send(Message::Text(r#"{"method":"ping"}"#.into())).await.is_err() {
```

**Kết quả**: 0 disconnects / 30 phút (sau fix).

### Bug B — Copyability guard quá thấp

**File**: `main.rs:73,93`
**Status**: ✅ Fixed

**Problem**: Auto-add filter `copyability > 1.0` cho phép wallet có copyability rất thấp (1-5%) được chọn. Những wallet này khó copy vì positions quá nhỏ hoặc quá biến động.

**Fix**: Tăng threshold lên `copyability >= 5.0`:

```rust
// main.rs:73 — auto-add filter
w.copy_worthy && w.validated_30d && !w.being_copied && w.copyability >= 5.0

// main.rs:93 — per-wallet guard
if w.copyability < 5.0 { continue; }
```

### Bug C — Stale check file-mtime không đúng

**File**: `scanner.rs:150-159` (old code)
**Status**: ✅ Fixed (đã xóa block này)

**Problem**: Stale data check dùng `File::metadata().modified()` với threshold 48h. File mtime thay đổi mỗi lần write atomic (rename), không phản ánh data freshness thật.

**Fix**: Xóa hoàn toàn file-mtime stale check. Dùng per-wallet `last_updated` với 24h threshold.

### Bug D — Paper equity không tính locked margin

**File**: `paper.rs:80-91`
**Status**: ✅ Fixed

**Problem**: `get_equity()` trả về total equity (cash + unrealized) không trừ locked notional. Khi có nhiều positions mở, equity trông cao hơn thực tế → position sizing sai.

**Fix**: Thêm `locked_notional()` và `get_free_equity()`:

```rust
pub fn locked_notional(&self) -> f64 {
    self.positions.values().map(|p| p.size * p.entry_px).sum()
}
pub fn get_free_equity(&self, ...) -> f64 {
    self.get_equity(...) - self.locked_notional()
}
```

### Bug E — Allocations: Equity-ratio → Fixed slot (ARCHITECTURE)

**File**: `copier.rs:299-408`
**Status**: ✅ Implemented

**Problem**: Equity-ratio model `slot_cap = our_equity / num_targets`:

- slot_cap thay đổi theo equity mỗi cycle → RESIZE liên tục
- slot_cap thay đổi khi target count thay đổi
- Phụ thuộc vào `fetch_target_equities()` API

**Fix**: Fixed-slot model:

```rust
let slot_cap = PAPER_INITIAL_EQUITY / MAX_COPY_WALLETS;  // $2000 — CỐ ĐỊNH
```

- Slot_cap KHÔNG phụ thuộc equity động
- Slot_cap KHÔNG phụ thuộc target count
- Mỗi slot độc lập tính COPY_RATIO \* positions, scale vừa slot_cap
- Aggregate all desired → reconcile 1 portfolio

### Bug F — slot_cap dao động theo equity

**File**: `copier.rs:310` (intermediate version)
**Status**: ✅ Fixed

**Problem**: `slot_cap = our_equity / MAX_COPY_WALLETS` dùng `our_equity` là `get_free_equity()` — thay đổi mỗi cycle do unrealized PnL và locked notional. Gây resize liên tục ngay cả khi không có trade.

**Fix**: Dùng `PAPER_INITIAL_EQUITY` (hằng số $10,000):

```rust
let slot_cap = PAPER_INITIAL_EQUITY / MAX_COPY_WALLETS.max(1) as f64;
```

### Remaining — Single-portfolio aggregation (ARCHITECTURAL LIMITATION)

**File**: `copier.rs:315-346`
**Status**: ⚠️ Không thể fix với 1 wallet

**Problem**: 5 slot × $2,000 được aggregate vào 1 `desired: HashMap<coin, (side, notional)>`. Khi 2 slot muốn cùng coin khác hướng → net về 0. Khi 2 slot muốn cùng coin cùng hướng → sum lại. Mất identity của từng slot.

**Hậu quả**:

- Không thể biết position nào thuộc slot nào
- Nếu target A LONG BTC và target B SHORT BTC → net ~0 → không mở position nào
- Tổng deployed capital thường thấp hơn nhiều so với 5 × $2,000

**Giải pháp**: Cần 5 sub-wallet riêng biệt, mỗi wallet $2,000. Đây là thay đổi kiến trúc lớn.

## Monitor results

### Run 1 — Trước fix (equity-ratio model, binary WS ping)

**Duration**: 30 phút
**Date**: 2026-06-13 (early session)

| Metric             | Value                   |
| ------------------ | ----------------------- |
| WS disconnect      | **29** (mỗi ~62s)       |
| ERROR              | 0                       |
| RECONCILE          | 32                      |
| Equity (start→end) | $3,475 → $3,586 (+$111) |

Bot chưa được reset về $10,000. WS disconnect liên tục do binary ping.

### Run 2 — Sau WS ping fix + stale fix

**Duration**: 30 phút
**Date**: 2026-06-13 (mid session)

| Metric        | Value                      |
| ------------- | -------------------------- |
| WS disconnect | **0**                      |
| ERROR         | 0                          |
| RECONCILE     | 140 (mostly SKIP cooldown) |
| Equity        | $10,000 → $10,017 (+$17)   |

WS ping fix hoàn hảo (0 disconnect). RECONCILE actions cao do equity-ratio model còn bug.

### Run 3 — Sau fixed-allocation (equity/num_targets)

**Duration**: 30 phút
**Date**: 2026-06-13 (afternoon)

| Metric                      | Value                    |
| --------------------------- | ------------------------ |
| WS disconnect               | 0                        |
| ERROR                       | 0                        |
| RECONCILE (after 1st cycle) | 0                        |
| Equity                      | $10,017 → $10,018 (flat) |

3 positions: SOL $120, ETH $519, HYPE $859. 1x RESIZE HYPE (cooldown expiry).

### Run 4 — Sau fixed-slot_cap (PAPER_INITIAL_EQUITY/5)

**Duration**: 30 phút
**Date**: 2026-06-13 (latest — PID 217632)

| Metric                      | Value                                      |
| --------------------------- | ------------------------------------------ |
| WS disconnect               | **0**                                      |
| ERROR                       | **0**                                      |
| PANIC                       | **0**                                      |
| RECONCILE (after 1st cycle) | **0**                                      |
| AUTO-ADD / EVICT            | **0**                                      |
| FILL events                 | 0                                          |
| Total scans                 | 75                                         |
| Equity                      | $10,000 → $9,999 (flat, -$0.82 unrealized) |
| Targets                     | Cố định 5 ví, không rotation               |

**Portfolio**: 3 positions — ETH $807, HYPE $964, SOL $169
**slot_cap**: $2,000 cố định ✅ (PAPER_INITIAL_EQUITY/5)

## Constant reference

| Constant                  | Value             | Use                            |
| ------------------------- | ----------------- | ------------------------------ |
| `MAIN_TICK_SECS`          | 15                | Orchestration loop interval    |
| `RECONCILE_SECS`          | 60                | Reconcile cycle interval       |
| `RECONCILE_COOLDOWN_SECS` | 300               | Cooldown for FLIP/RESIZE       |
| `COPY_MGMT_EVERY_N_SCANS` | 5                 | Target re-evaluation frequency |
| `MAX_COPY_WALLETS`        | 5                 | Max slots = max targets        |
| `MAX_PER_STRATEGY`        | 2                 | Max targets per strategy       |
| `MIN_NOTIONAL_USD`        | 10                | Min position size              |
| `MAX_POSITION_PCT_EQUITY` | 0.4               | Max 40% of slot per position   |
| `PAPER_INITIAL_EQUITY`    | 10000             | Initial paper capital          |
| `MAX_TOTAL_EXPOSURE_PCT`  | ~~0.8~~ (removed) | Không còn dùng                 |

## Key structs

```rust
// types.rs
struct TargetPosition { coin, side, size, entry_px }
struct OurPosition { coin, side, size, entry_px, notional }
struct WalletInfo { address, first_seen, last_updated, score, copyability,
                    copy_worthy, validated_30d, warnings, ... }
struct CopyState { target_address, target_pnl_15d, started_at, active }

// paper.rs
struct PaperPosition { coin, side, size, entry_px, opened_at, realized_pnl }

// config.rs
pub const SLOT_CAPITAL: f64 = 2000.0;  // PAPER_INITIAL_EQUITY / MAX_COPY_WALLETS
pub const POSITION_CAP: f64 = 800.0;   // SLOT_CAPITAL * MAX_POSITION_PCT_EQUITY
```

## Diagnostic guide

### "RECONCILE" không xuất hiện trong log

→ `active_targets` rỗng → không có target để reconcile
→ Kiểm tra copy_wallets.json, bot có snapshot không?
→ `grep "Status:" bot.log | grep "0 copied"`

### slot_cap không hiển thị $2000

→ `slot_cap = PAPER_INITIAL_EQUITY / MAX_COPY_WALLETS`
→ Kiểm tra PAPER_TRADING = true trong config.rs
→ Kiểm tra PAPER_INITIAL_EQUITY còn 10000 không

### WS disconnect liên tục

→ `grep "server closed\|connect_failed" bot.log`
→ server closed = Hyperliquid đóng (bth nếu ping sai)
→ connect_failed = network/DNS issue
→ Đếm: `grep -c "disconnected" bot.log`

### Chỉ có N positions với 5 targets (N < 5)

→ Nguyên nhân: COPY_RATIO \* target_position < MIN_NOTIONAL
→ Hoặc: same coin opposite sides → net ≈ 0
→ Hoặc: targets có quá ít positions
→ Kiểm tra: `copy_wallets.json` để xem target list

### FILL = 0 trong monitor

→ Có thể wallets không trade trong window
→ SWING strategy hold hàng giờ
→ DAY_TRADER cần thời gian dài hơn

### Equity giảm hoặc bankrup

→ Kiểm tra ở polling rồi reset:

```rust
if eq < 100.0 { paper.reset(); }
```

→ Paper portfolio tự reset về $10,000

### Target bị rotation liên tục

→ `grep "AUTO-ADD\|EVICT" bot.log`
→ Kiểm tra `selection_score()` của wallet bị thay thế
→ Có thể Python analyzer ghi validation mới với score thấp hơn
