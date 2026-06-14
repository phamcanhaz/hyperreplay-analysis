# Phân tích chuyên sâu: hl_copy_bot

## 1. TỔNG QUAN LUỒNG HOẠT ĐỘNG

hl_copy_bot là hệ thống copy-trade trên Hyperliquid Mainnet, chạy ở chế độ **paper trading** với $10,000 vốn ảo. Rust orchestration + Python deep analysis.

Kiến trúc gồm 3 vòng lặp song song:

```
main.rs (tick 15s)
├── Scanner: phát hiện ví mới từ recentTrades + leaderboard
├── [mỗi 5 tick ~75s] Copy management:
│   ├── load_and_apply_validations() ← Python deep analyzer
│   ├── Evict stale + không còn copy_worthy
│   └── Auto-add: chọn top wallet theo selection_score
│
ws.rs (WebSocket)
└── subscribe userFills → fill_trigger → đánh thức poll loop

copier.rs (poll loop 60s)
├── fetch_all_mids, target positions, our positions
├── sync_positions() → reconcile
└── BTC crisis detection (ring buffer 5 phút)
```

**Luồng main loop (main.rs:241-247)**:

```
loop {
    tokio::select! {
        rx.changed() => break,                    // Ctrl+C
        tick() => {}                               // scan + copy mgmt
    }
}
```

Hàm `tick()` (main.rs:40-150) chạy mỗi `MAIN_TICK_SECS=15s`:

1. `scan_new_wallets()` — quét recentTrades cho 10 coin + leaderboard top 100
2. `save_db()` — ghi seen_wallets.json
3. Mỗi 5 lần: `load_and_apply_validations()`, evict, auto-add, save snapshot
4. In bảng trạng thái

**Vòng lặp reconcile (copier.rs:452-545)**:

```
poll_targets_loop()
loop {
    tokio::select! {
        shutdown => break,
        poll_once() => { }                         // mỗi 60s
        fill_trigger.changed() => { }              // WS fill → đánh thức
    }
    // BTC crisis detection
    // health_check mỗi 300s
}
```

`poll_once()` (copier.rs:547-633) — một chu kỳ reconcile:

- Fetch allMids (giá)
- Fetch our positions (từ PaperPortfolio nếu paper mode, hoặc HL API)
- Fetch target positions (clearinghouseState cho mỗi target)
- `sync_positions()` — tính desired, reconcile
- Paper report + save

---

## 2. PHÂN TÍCH CHỌN VÍ

### Pipeline chọn ví

Pipeline gồm 3 giai đoạn:

#### Giai đoạn 1: Phát hiện (scanner.rs:9-99)

`scan_new_wallets()` quét từ 2 nguồn:

- **recentTrades**: 10 coin (BTC, ETH, SOL, HYPE, ARB, OP, DOGE, PEPE, SUI, APT) — trích xuất `user`, `buyer`, `seller` fields
- **Leaderboard**: top 100 từ `stats-data.hyperliquid.xyz`

Lọc: `seen[addr] >= 2 && !db.contains(addr)` — một ví phải xuất hiện ít nhất 2 lần. Leaderboard entries được cộng 3 điểm.

#### Giai đoạn 2: Validation (scanner.rs:141-226)

`load_and_apply_validations()` được gọi:

- Tại startup (main.rs:170)
- Mỗi `COPY_MGMT_EVERY_N_SCANS=5` tick (main.rs:55)

Quy trình:

1. **Reset tất cả**: `copy_worthy = false, validated_30d = false`
2. Đọc `validation_results.json` (do Python `analyzer_deep.py` ghi)
3. Parse từng entry: score, pnl, wr, pf, dd, bias, strategy, copyability, warnings
4. `copy_worthy = valid` nếu Python analyzer đánh giá `valid: true`
5. **Block warnings** (scanner.rs:190-196) — buộc `copy_worthy = false` nếu warnings chứa:
   - `SCALPER`
   - `ALPHA_DECAYING`
   - `CRISIS_REGIME`
   - `REGIME_MISMATCH`
6. **Stale check** (scanner.rs:215-219): `now - last_updated > 86400s` → thêm `STALE_DATA`, `copy_worthy = false`

#### Giai đoạn 3: Auto-add (main.rs:72-111)

Chạy mỗi 5 tick. Pipeline lọc:

```
db.iter()
├── copy_worthy == true
├── validated_30d == true
├── being_copied == false
├── copyability >= 5.0
└── Sort by selection_score() DESC

→ Pick top N:
├── copy_state.len() < MAX_COPY_WALLETS (5)
├── MAX_PER_STRATEGY (2) per strategy class
└── Push vào active_targets + copy_state
```

### Công thức selection_score (main.rs:20-38)

```rust
fn selection_score(w: Option<&WalletInfo>) -> f64 {
    let mut penalty = 1.0;
    for warn in &w.warnings {
        match warn.as_str() {
            "REGIME_MISMATCH" => penalty *= 0.5,
            "ALPHA_DECAYING"  => penalty *= 0.3,
            "CRISIS_REGIME"   => penalty *= 0.1,
            "STALE_DATA"      => penalty *= 0.3,
            "INACTIVE"        => penalty *= 0.5,
            _ => {}
        }
    }
    w.score * penalty * (w.copyability / 100.0)
        * stale_penalty  // 0.7 nếu last_updated > 600s
}
```

**Công thức đầy đủ**:

```
selection_score = score × penalty_product × (copyability / 100) × stale_factor

penalty_product = Π(multiplier cho mỗi warning)
stale_factor = 0.7 nếu (now - last_updated) > 600, else 1.0
```

### Ví dụ tính selection_score

Dưới đây là các wallet copy-worthy với calculation thực tế:

| Wallet                | Score | Copyability | Warnings            | Penalty | Stale | Sel Score | Trạng thái    |
| --------------------- | ----- | ----------- | ------------------- | ------- | ----- | --------- | ------------- |
| 0x18d103 (SWING)      | 85.1  | 100%        | insufficient_trades | 1.0     | 0.7   | **59.6**  | ✅ Copy       |
| 0x931153 (DAY_TRADER) | 65.8  | 100%        | insufficient_trades | 1.0     | 0.7   | **46.1**  | ✅ Copy       |
| 0x9da9cc (SWING)      | 52.2  | 100%        | insufficient_trades | 1.0     | 0.7   | **36.5**  | ✅ Copy       |
| 0x76fe28 (DAY_TRADER) | 51.0  | 100%        | insufficient_trades | 1.0     | 0.7   | **35.7**  | ✅ Copy       |
| 0x6e6f2c (SWING)      | 45.7  | 100%        | insufficient_trades | 1.0     | 0.7   | **32.0**  | ✅ Copy       |
| 0xb69ccb (DAY_TRADER) | 63.6  | 45%         | —                   | 1.0     | 0.7   | **20.0**  | ❌ Not copied |
| 0x7aa11a (SWING)      | 55.8  | 50%         | —                   | 1.0     | 0.7   | **19.5**  | ❌ Not copied |
| 0xc4cda6 (SWING)      | 73.4  | 100%        | —                   | 1.0     | —     | **73.4**  | ❌ Not in DB? |
| 0xb1edfe (DAY_TRADER) | 51.6  | 45%         | —                   | 1.0     | 0.7   | **16.3**  | ❌ Not copied |

Ví dụ tính cho `0x18d103`:

```
score = 85.1
penalty = 1.0 (chỉ có warning "insufficient_trades" — không có multiplier)
copyability = 100.0 → 100.0 / 100 = 1.0
stale = checked_at = 1781322342, now ~1781343784 → diff = 21442s > 600 → 0.7
selection_score = 85.1 × 1.0 × 1.0 × 0.7 = 59.57
```

### ⚠️ Vấn đề: Wallet chất lượng cao bị bỏ qua

**0xc4cda69c (score=73.4)** — đây là wallet TIỀM NĂNG NHẤT trong danh sách copy-worthy nhưng KHÔNG có trong 5 slot active. Các chỉ số:

- Score: 73.4 (cao thứ 2 trong copy-worthy)
- Win rate: 84.3%, 197 trades, PnL $1,502
- Copyability: 100% (không rõ vì sao)
- Warnings: không có blocking warnings
- **Tại sao không được copy?** — Kiểm tra `seen_wallets.json`:

```
grep "0xc4cda6" seen_wallets.json → không tồn tại
```

Wallet này có thể đã bị xóa khỏi DB do stale TTL (30 ngày), hoặc chưa được scanner phát hiện kịp. Mặc dù Python analyzer có data cho ví này (trong validation_results.json), nhưng nếu ví không còn trong `seen_wallets.json` thì Rust bot không thể copy.

**0x42080203 (score=86.0)** — wallet với PnL $102k:

```
valid: false (worthy: false)
copyability: 60.0
warnings: ["FEW_ACTIVE_DAYS", "insufficient_trades"]
```

Wallet này bị từ chối vì `FEW_ACTIVE_DAYS` và `insufficient_trades`. Mặc dù score 86 (cao hơn tất cả active copies), nó không pass `is_worthy()` của Python analyzer. `insufficient_trades` không phải blocking warning trong Rust code, nhưng `valid: false` → `copy_worthy = false` → không được chọn.

**SCALPER wallets** (score 100, 91.3, 90.2, 89.7...) bị chặn bởi `warnings.contains("SCALPER")` tại scanner.rs:190. Hoàn toàn đúng — scalpers không thể copy do vào lệnh quá nhanh.

### Khoảnh khắc đáng chú ý

**Tất cả 5 active copies đều có `insufficient_trades` warning**. Đây là warning nhẹ (không block copy_worthy) nhưng phản ánh vấn đề: cả 5 wallet đều có trade count rất thấp (2-12 trades). Điều này có nghĩa:

1. Bot đang copy các wallet chưa được kiểm chứng đủ thống kê
2. `insufficient_trades` được Python analyzer thêm vào khi `trades < MIN_TRADES (20)`
3. Wallet tốt nhất (`0x7aa11a` với 438 trades, 94% WR) KHÔNG được copy vì copyability=50% → sel_score=19.5

**Giải pháp**: Cân nhắc tăng trọng số `trades` trong selection_score, hoặc thêm minimum trade threshold ở cấp Rust (không chỉ dựa vào copyability).

---

## 3. PHÂN TÍCH THỜI GIAN VÀO LỆNH (ENTRY TIMING)

### Luồng normal (không có WS trigger)

1. `poll_once()` chạy mỗi `RECONCILE_SECS=60s` (copier.rs:632)
2. Fetch target positions qua REST API `clearinghouseState` (copier.rs:244-266)
3. `sync_positions()` tính desired positions
4. `market_open()` fetch price + execute

**Tổng delay**: **lên đến 60s + ~2-3s API time**

Timeline chi tiết:

```
T+0s:   poll_once bắt đầu
T+0.5s: fetch_all_mids
T+1s:   fetch our positions (paper → unserialized_positions)
T+1-2s: fetch target positions (1 API call mỗi target, 200ms间隔)
T+2-3s: sync_positions + market_open (nếu cần)
T+63s:  poll_once kết thúc (sau sleep 60s)
```

Entry của bot sau entry của target: **60-63s** (worst case ngay sau khi poll_once sleep).

### Luồng nhanh (WS trigger)

1. WS nhận fill event → `fill_trigger.send(counter)` (ws.rs:131)
2. `poll_targets_loop()` `select!` thức dậy từ `fill_trigger.changed()` (copier.rs:483-486)
3. Vòng lặp tiếp theo chạy `poll_once()` ngay lập tức

**Expected delay**: **~2-5 giây** (WS latency + reconcile).

### ⚠️ VẤN ĐỀ QUAN TRỌNG: WS userFills KHÔNG HOẠT ĐỘNG

**Bằng chứng từ monitor report**: `FILL events: 0` trong suốt thời gian chạy.

**Phân tích code** (ws.rs:62-65):

```rust
let sub = serde_json::json!({
    "method": "subscribe",
    "subscription": { "type": "userFills", "user": addr }
});
```

Bot đăng ký `userFills` cho **địa chỉ của target wallet** (không phải địa chỉ của bot). Theo tài liệu Hyperliquid WebSocket API:

- `userFills` subscription thường yêu cầu **xác thực** (connected user)
- Subscription cho địa chỉ khác có thể được chấp nhận (không có lỗi) nhưng **không bao giờ gửi event**

Code kiểm tra subscription acknowledgment (ws.rs:73-109):

```rust
for _ in 0..addrs.len() {
    if let Some(msg) = read.next().await {
        match msg {
            Ok(Message::Text(text)) => {
                if data.get("error").is_some() {
                    subs_fail += 1;
                } else {
                    subs_ok += 1;  // Không có "error" → считаем успешным
                }
            }
        }
    }
}
if subs_fail > 0 && subs_ok == 0 {
    return Some("permanent");  // Tất cả đều reject → dừng
}
```

Vì không có `"error"` field trong response, tất cả subscription được tính là `subs_ok = 5`, `subs_fail = 0`. Bot tiếp tục chạy với trạng thái "WS connected, listening for fills..." nhưng **không bao giờ nhận được event**.

**Kết luận**: **WS fill listener là một no-op**. Bot hoàn toàn phụ thuộc vào poll 60s. Entry timing luôn ở worst case.

### Tác động

| Metric        | Hiện tại (WS không hoạt động)     | Kỳ vọng (WS hoạt động) |
| ------------- | --------------------------------- | ---------------------- |
| Entry delay   | 0-60s                             | 2-5s                   |
| Exit delay    | 0-60s                             | 2-5s                   |
| Slippage risk | Cao (60s là rất lâu trong crypto) | Thấp                   |
| Flip timing   | Chậm 60s → giá đã thay đổi        | Gần real-time          |

**Đề xuất**:

1. Kiểm tra Hyperliquid WS API docs — `userFills` chỉ dành cho connected user
2. Thay thế bằng `webData2` (subscription type mới cho phép theo dõi địa chỉ khác?) hoặc `orderUpdates`
3. Nếu không thể subscribe target fills, dùng `allMids` subscription + check position changes (polling nhẹ hơn)

---

## 4. GIÁ VÀO LỆNH

### Luồng tính giá

Khi `sync_positions()` quyết định OPEN một position:

1. **Allocation** (copier.rs:324-325):

   ```rust
   let px = prices.get(&pos.coin).copied().unwrap_or(pos.entry_px);
   let n = pos.size * px;  // notional của target position
   ```

   Dùng mid-price từ `fetch_all_mids()` tại thời điểm fetch.

2. **Slot allocation** (copier.rs:334-335):

   ```rust
   let n = slot_cap * (notional / total);  // phân bổ slot_cap $2000
   ```

3. **Market open** (copier.rs:119-156):
   ```rust
   let px = self.fetch_coin_price(coin).await?;  // giá TẠI THỜI ĐIỂM OPEN
   let size = notional / px;                      // size = notional / current_price
   paper.open(coin, side, size, px, now);
   ```

**Entry price của bot = mid-price Hyperliquid tại thời điểm `market_open()`.** Giá này KHÁC với entry price của target.

### Vấn đề timing

```
T1: fetch_all_mids()    → price_P1
T1: desired = P1-based  → desired_notional

                    ... ~2s ...

T2: market_open()       → price_P2
T2: size = desired_notional / P2
T2: entry_price = P2
```

- `desired_notional` được tính tại T1
- Position mở tại T2 với `price_P2`
- Nếu `price_P2` khác `price_P1`, kích thước position có thể lệch
- Trong thị trường biến động mạnh, chênh lệch 2s có thể ~0.1-0.5%

### Paper trading

Cash accounting (paper.rs:37-39):

```rust
let notional = size * entry_px;
self.cash -= notional;
```

Bot trừ `cash` khi mở position và cộng lại `locked + pnl` khi đóng. `get_free_equity()` trả về `equity - locked_notional()` (paper.rs:92-94). Đây là mô hình đúng sau khi fix.

### Đề xuất

Không có vấn đề lớn với entry price logic hiện tại cho paper trading. Entry price = market price, khớp với mô phỏng thực tế.

---

## 5. THOÁT LỆNH (EXIT)

### Luồng exit

Khi target đóng position:

1. `fetch_target_positions()` (copier.rs:244-266) không còn coin đó
2. `sync_positions()` (copier.rs:347-358): `desired` không còn coin
3. `to_close` = coins trong `our_positions` nhưng không trong `desired`
4. `market_close()` được gọi

```rust
let to_close: Vec<String> = op.keys()
    .filter(|coin| !desired.contains_key(*coin))
    .cloned()
    .collect();

for coin in &to_close {
    let _ = copier.market_close(coin, None).await;
    op.remove(coin);
    last_action.insert(coin.clone(), now);
}
```

### Timing exit

Giống entry: **lên đến 60s delay** (vì WS không hoạt động).

Khi target close position:

```
T+0:   target closes position
T+60:  poll_once chạy → phát hiện target không còn position
T+62:  market_close() → exit
```

Target có thể đã đóng position từ 60s trước. Trong 60s đó, nếu thị trường đi ngược hướng, bot sẽ lỗ thêm.

### Cooldown (copier.rs:360-365)

```rust
let regime = read_regime();
let cooldown = match regime.as_str() {
    "crisis" => 60u64,
    "volatile" => 120u64,
    _ => RECONCILE_COOLDOWN_SECS,  // 300s
};
```

Áp dụng cho FLIP và RESIZE. KHÔNG có cooldown cho CLOSE hoặc OPEN.

**Kịch bản rủi ro**:

- Target đóng BTC LONG, ngay lập tức mở BTC SHORT (trong 60s)
- Bot đóng BTC LONG (không cooldown)
- Bot mở BTC SHORT (không cooldown)
- 2 trade trong vòng 60s → gấp đôi phí giao dịch

### Đề xuất

- Thêm cooldown cho CLOSE+OPEN sequence trên cùng coin
- Hiện tại không có vấn đề với paper trading, nhưng với real trading sẽ tốn phí

---

## 6. AGGREGATION LOGIC (desired HashMap)

### Cách hoạt động

`sync_positions()` (copier.rs:314-345) aggregate tất cả slot vào 1 HashMap:

```rust
let mut desired: HashMap<String, (String, f64)> = HashMap::new();

for positions in tp.values() {  // mỗi slot = 1 target
    // Tính phân bổ slot_cap
    for (coin, side, notional) in &slot_positions {
        let entry = desired.entry(coin.clone()).or_insert((side.clone(), 0.0));
        if entry.0 != *side {
            // Opposite side → net
            if n > entry.1 { entry.0 = side.clone(); entry.1 = n - entry.1; }
            else { entry.1 -= n; }
        } else {
            // Same side → sum
            entry.1 += n;
        }
    }
}
```

### Hạn chế kiến trúc

**Vấn đề cốt lõi**: 5 slot × $2,000 = $10,000, nhưng chỉ có **1 Hyperliquid wallet**. Mỗi coin chỉ có thể có 1 position (LONG hoặc SHORT).

| Kịch bản                         | Slot A         | Slot B          | desired            | Kết quả |
| -------------------------------- | -------------- | --------------- | ------------------ | ------- |
| Cùng coin, cùng hướng            | LONG BTC $500  | LONG BTC $1000  | LONG BTC $1500     | ✅ Gộp  |
| Cùng coin, khác hướng            | LONG BTC $1000 | SHORT BTC $800  | LONG BTC $200      | ⚠️ Net  |
| Cùng coin, khác hướng (cân bằng) | LONG BTC $1000 | SHORT BTC $1000 | ∅                  | ❌ Về 0 |
| Coin khác nhau                   | LONG SOL $500  | LONG ETH $800   | SOL $500, ETH $800 | ✅ OK   |

**Hậu quả**:

- Nếu 2 slot LONG và SHORT cùng coin (ví dụ 0x18d103 SHORT HYPE và 0x931153 LONG coin nào đó → net)
- Bot thường deployed ít hơn nhiều so với $10,000
- Không thể track PnL theo từng slot riêng biệt
- Mất thông tin về target nào đang được copy

**Bằng chứng từ paper_portfolio.json**: Chỉ có 4 positions mở (BTC SHORT $1,666, ETH LONG $2,007, SOL LONG $171, HYPE LONG $2,137), với tổng locked notional ~$5,981 — chỉ ~60% của $10,000.

### Giải pháp

Cần 5 sub-wallet riêng biệt, mỗi wallet $2,000. Đây là thay đổi kiến trúc lớn, yêu cầu 5 private keys riêng.

---

## 7. CÁC VẤN ĐỀ KHÁC

### a) Cash accounting — ĐÃ FIX

Paper portfolio (paper.rs:37-39, 57-63):

```rust
// OPEN
self.cash -= notional;  // size * entry_px

// CLOSE
let pnl = (close_px - entry_px) * side_mult * size;
let locked = size * entry_px;
self.cash += locked + pnl;
```

Logic đúng. Cash giảm khi mở, tăng khi đóng (locked margin + PnL).

### b) pos_cap đã loại bỏ

Trong code hiện tại, `MAX_POSITION_PCT_EQUITY=0.4` VÀ `pos_cap` đã bị loại bỏ khỏi sync_positions. Tuy nhiên, `MAX_POSITION_PCT_EQUITY` vẫn tồn tại trong config.rs và architecture doc đề cập đến nó. **Kiểm tra**: copier.rs không còn dùng pos_cap.

### c) Tất cả 5 active copies có `insufficient_trades`

| Wallet   | Trades | Score | Warnings            |
| -------- | ------ | ----- | ------------------- |
| 0x18d103 | 12     | 85.1  | insufficient_trades |
| 0x931153 | 6      | 65.8  | insufficient_trades |
| 0x9da9cc | 12     | 52.2  | insufficient_trades |
| 0x76fe28 | 4      | 51.0  | insufficient_trades |
| 0x6e6f2c | 2      | 45.7  | insufficient_trades |

Đây là rủi ro lớn nhất: **không đủ dữ liệu thống kê**. Với 2-12 trades, không thể đánh giá chính xác chất lượng của trader. Wallet 0x6e6f2c chỉ có 2 trades (1 win, 1 loss) — hoàn toàn không đáng tin cậy.

### d) Wallet 0x7aa11aaf bị bỏ qua

**Wallet này là ứng viên xuất sắc nhất**:

- 438 trades, 94.3% WR, PnL $1,044
- Strategy: SWING (2 slot đã dùng)
- KHÔNG có warnings (không insufficient_trades, không SCALPER, không FEW_ACTIVE_DAYS)
- Copyability: 50%

**Tại sao không được copy?** `copyability = 50%` → `sel_score = 55.8 × 1.0 × 0.5 × 0.7 = 19.5`. Trong khi các wallet khác có copyability=100% → sel_score cao hơn.

copyability do Python analyzer tính. Giá trị 50% có thể do:

- Position size quá lớn so với slot_cap $2,000
- Quá nhiều coin cùng lúc
- Volatility quá cao

**Đề xuất**: Copyability 50% vẫn đáng để copy. Wallet với 438 trades, 94% WR là vàng. Cân nhắc giảm trọng số copyability trong selection_score, hoặc tăng threshold cho min trades.

### e) Stale data check

`last_updated` được set từ `checked_at` của Python analyzer (sau Bug 1 fix). Nếu analyzer không chạy trong 24h, wallet bị STALE_DATA. `checked_at` hiển thị:

- 1781322342 — một số wallet có `checked_at` ~10 tiếng trước
- 1781322651-1781322654 — một số khác

Python analyzer chạy mỗi `SLEEP_SECS=300s` (5 phút). Nếu analyzer bị treo hoặc crash, stale check sẽ kích hoạt sau 24h và loại bỏ tất cả copy-worthy wallets.

### f) FEW_ACTIVE_DAYS và insufficient_trades

Cả 2 warnings đều penalize wallet mới. `FEW_ACTIVE_DAYS` (Python analyzer, `<5 ngày active`) và `insufficient_trades` (Python analyzer, `<20 trades`). Wallet mới không thể đạt được đủ active days hay trades → không bao giờ được đánh giá copy_worthy.

Điều này tạo ra **catch-22**: wallet mới không có lịch sử → không được copy → không thể có lịch sử.

### g) `being_copied` flag edge case

Khi wallet được thêm vào `active_targets`, `being_copied` được set `true` (main.rs:107-109). Khi wallet bị evict, `being_copied` được set `false` (main.rs:66).

Tuy nhiên, nếu tiến trình crash giữa chừng, snapshot trên disk có thể có wallet với `active: true` nhưng DB có `being_copied: false`. Khi restore (main.rs:180-206), bot kiểm tra `copy_worthy` của wallet. Nếu wallet vẫn copy_worthy, nó được restore và `being_copied` được set lại.

**Vấn đề**: Nếu wallet bị xóa khỏi `active_targets` (evict) nhưng `being_copied` không được reset (do lỗi logic), wallet sẽ bị "khóa" vĩnh viễn — không bao giờ được chọn lại vì `!w.being_copied` filter. Cần ensure atomic update.

### h) Timing của load_and_apply_validations

`load_and_apply_validations()` được gọi:

- Tại startup (main.rs:170)
- Mỗi 5 tick ~75s (main.rs:55)

Python `analyzer_deep.py` chạy mỗi 300s.

**Vấn đề**: Nếu analyzer đang ghi validation_results.json (atomic write tạo file .tmp rồi rename) cùng lúc Rust đọc file, có race condition. Tuy nhiên atomic write (write to tmp → rename) giảm thiểu rủi ro.

**Timeline không đồng bộ**:

```
T+0s:   analyzer bắt đầu cycle mới (đọc DB cũ)
T+5s:   Rust tick #N → load_and_apply_validations (đọc validation cũ)
T+30s:  analyzer ghi validation mới
T+75s:  Rust tick #N+5 → load_and_apply_validations (đọc validation mới)
```

Độ trễ Rust đọc data mới: **tối đa 75s** (5 tick). OK.

### i) ERROR và PANIC

Monitor report: `ERROR: 0, PANIC: 0`. Bot chạy ổn định không crash. WS disconnect: 0 (sau fix ping format).

### j) FILL events = 0

Đã phân tích ở phần 3. WS userFills subscription cho địa chỉ khác không hoạt động.

### k) Monitor: scan count stuck

Monitor cho thấy scan count không tăng (stuck ở 7). Điều này có thể do bot đã bị restart hoặc monitor script không bắt được tín hiệu.

---

## TỔNG KẾT: CÁC VẤN ĐỀ CẦN ƯU TIÊN XỬ LÝ

| #   | Vấn đề                                                                          | Mức độ      | File       | Dòng    |
| --- | ------------------------------------------------------------------------------- | ----------- | ---------- | ------- |
| 1   | WS userFills không hoạt động cho địa chỉ khác                                   | 🔴 CRITICAL | ws.rs      | 62-65   |
| 2   | Chọn wallet chỉ dựa trên copyability 100% — bỏ qua wallet 0x7aa11a (438 trades) | 🟠 HIGH     | main.rs    | 72-111  |
| 3   | 5 wallets active đều có insufficient_trades (2-12 trades)                       | 🟠 HIGH     | —          | —       |
| 4   | Aggregate 5 slot vào 1 wallet — net positions khi khác hướng                    | 🟡 MEDIUM   | copier.rs  | 314-345 |
| 5   | Wallet 0xc4cda69c (score 73.4, 197 trades) không có trong DB                    | 🟡 MEDIUM   | scanner.rs | 104-109 |
| 6   | Không có cooldown cho CLOSE+OPEN sequence trên cùng coin                        | 🟢 LOW      | copier.rs  | 367-403 |
| 7   | `being_copied` flag không được reset nếu crash giữa chừng                       | 🟢 LOW      | main.rs    | 107-109 |

### Đề xuất hành động

1. **WS**: Kiểm tra Hyperliquid WS API — chuyển sang `webData2` hoặc dùng polling nhanh hơn (15s thay vì 60s)
2. **Wallet selection**: Thêm trade count threshold trong Rust (min 10 trades) và giảm trọng số copyability
3. **Kiến trúc**: Cân nhắc 5 sub-wallet riêng biệt để tránh aggregation issue
4. **Monitoring**: Thêm cảnh báo khi FILL=0 trong N phút (phát hiện WS chết)
