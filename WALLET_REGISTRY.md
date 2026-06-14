# Hyperliquid Wallet Registry

> Wallet đang copy, đã phân tích, và đang theo dõi
> Cập nhật: 14/06/2026

---

## I. ĐANG COPY (5 ví)

| #     | Địa chỉ                                          | Strategy       | 15d PnL  | Score    | Notes                              |
| ----- | ------------------------------------------------ | -------------- | -------- | -------- | ---------------------------------- |
| 1     | `0xc4cda69c9354eb77bce1d70c349b2de691be80b8`     | SWING          | $1,434   | 73.1     | STRONG LONG, 190 trades            |
| 2     | `0x8faf84cfba2fded55c8c21c149fc33be79e2b7ba`     | SWING          | $1,112   | 53.9     | LONG, 151 trades                   |
| **3** | **`0x6dbbefad3d24da625fa233c070678ab1938fcd38`** | **DAY_TRADER** | **$615** | **66.3** | **Scalper, LONG, 9 coins, WR=96%** |
| 4     | `0x2ae64d3a931805d91614df81621727594a509887`     | DAY_TRADER     | $2,502   | 55.5     | STRONG LONG, 66 trades             |
| 5     | `0x6dbe56e426651ab64c1ad5e552484fae54e0f9fe`     | SWING          | $1,655   | 50.9     | STRONG LONG, 26 trades             |

Config: `/home/bot/hl_copy_bot/copy_wallets.json`

---

## II. WALLET #3 — PHÂN TÍCH CHI TIẾT

### Thông tin cơ bản

| Field                 | Value                                        |
| --------------------- | -------------------------------------------- |
| **Address**           | `0x6dbbefad3d24da625fa233c070678ab1938fcd38` |
| **Strategy**          | DAY_TRADER — TWAP Scalping Bot               |
| **Bias**              | LONG (73% long fills / 27% short fills)      |
| **Vốn ước tính**      | ~$50k-100k (đòn bẩy thực ~1x)                |
| **Fills thu thập**    | 1,227 fills (3.6 ngày: 10-14/06/2026)        |
| **Trades tái tạo**    | 55 trades (fill → position → close)          |
| **Số coin giao dịch** | 9 coins                                      |

### Hiệu suất giao dịch

| Metric              | Giá trị                                   |
| ------------------- | ----------------------------------------- |
| **Win Rate**        | **96.4%** — 53 wins / 55 trades           |
| **Profit Factor**   | 31,127 (tổng lãi $622.55 / tổng lỗ $0.02) |
| **Max Drawdown**    | **0.0%**                                  |
| **Avg Hold Time**   | 725 giây (~12 phút)                       |
| **Copyability**     | 85.0%                                     |
| **Score**           | 66.3                                      |
| **Peak Hour**       | 15:00 UTC (22:00-23:00 VN)                |
| **Session**         | US (giờ Mỹ)                               |
| **Alpha Decay**     | Không phát hiện                           |
| **Regime Mismatch** | Không                                     |

### PnL theo coin

| Coin     | Trades | Win Rate | PnL          | % Tổng PnL |
| -------- | ------ | -------- | ------------ | ---------- |
| **HYPE** | 26     | 96.2%    | **+$484.11** | **77.8%**  |
| xyz:SPCX | 13     | 100%     | +$54.48      | 8.8%       |
| TRUMP    | 2      | 100%     | +$28.89      | 4.6%       |
| VVV      | 3      | 100%     | +$27.77      | 4.5%       |
| BTC      | 3      | 100%     | +$2.68       | 0.4%       |
| LIT      | 4      | 100%     | +$7.89       | 1.3%       |
| XMR      | 1      | 100%     | +$7.08       | 1.1%       |
| xyz:CL   | 2      | 100%     | +$9.65       | 1.5%       |
| #2310    | 1      | 0%       | -$0.02       | 0.0%       |

### Hướng giao dịch (Per-Coin Bias)

| Coin     | LONG fills | SHORT fills | Bias      |
| -------- | ---------- | ----------- | --------- |
| HYPE     | 24         | 2           | **LONG**  |
| xyz:SPCX | 13         | 0           | **LONG**  |
| XMR      | 1          | 0           | **LONG**  |
| xyz:CL   | 2          | 0           | **LONG**  |
| BTC      | 0          | 3           | **SHORT** |
| LIT      | 0          | 4           | **SHORT** |
| VVV      | 0          | 3           | **SHORT** |
| TRUMP    | 0          | 2           | **SHORT** |

=> **Pair Trading Strategy**: Long altcoin (HYPE, SPCX, XMR, CL) + Short BTC/small cap (LIT, VVV, TRUMP)

### Kết quả Copy Simulation ($50 USDT x20)

| Metric                 | Giá trị                         |
| ---------------------- | ------------------------------- |
| **Lợi nhuận 3.6 ngày** | **+$29.55 (+59.1%)**            |
| Win rate               | 93.9%                           |
| Profit Factor          | 139,071                         |
| Sharpe Ratio           | 18.49                           |
| Max Drawdown           | 0.0%                            |
| Mirror trades          | 509                             |
| HYPE chiếm             | ~70% lợi nhuận                  |
| Rủi ro chính           | Không stop loss, tập trung HYPE |

### PnL theo ngày (Copy Sim)

| Ngày       | PnL                 |
| ---------- | ------------------- |
| 2026-06-10 | +$5.11              |
| 2026-06-11 | +$0.12 (ngày yếu)   |
| 2026-06-12 | +$13.58 (ngày mạnh) |
| 2026-06-13 | +$8.73              |
| 2026-06-14 | +$0.27              |

### Giờ giao dịch (giờ VN)

| Giờ VN          | Fills   | Mức độ           |
| --------------- | ------- | ---------------- |
| **22:00-00:00** | **306** | **🔥 Peak tối**  |
| **11:00-13:00** | **221** | **🔥 Peak trưa** |
| 19:00-20:00     | 134     | ⚡ Trung bình    |
| 00:00-01:00     | 83      | ⚡ Trung bình    |
| 04:00-05:00     | 74      | Thấp             |
| 01:00-03:00     | 66-71   | Thấp             |
| 05:00-11:00     | 0-47    | Ngủ              |

### Mô hình giao dịch

1. **Scalping TWAP**: Mở vị thế theo từng chunk nhỏ (2-5 giây) để giảm slippage
2. **Pair Trading**: Luôn LONG 1 số coin + SHORT 1 số coin khác (hedge)
3. **Exit Pattern**: TWAP chốt lời từ từ, KHÔNG trailing stop
4. **Win rate 94% có thật**: Họ chỉ giao dịch khi có lợi thế nhỏ (micro-moves), hold rất ngắn
5. **Vốn thực ~1x leverage**: Giao dịch gần như spot, không dùng margin nhiều

---

## III. WALLET GIỐNG WALLET #3

Từ `validation_results.json` (1,082 wallets analyzed). Tiêu chí: DAY_TRADER/SCALPER, WR cao, hold ngắn.

### Top Scalper giống nhất

| #     | Address                                          | Bias         | WR%       | Hold(s)    | Trades  | PnL         | Coins  | Ghi chú                    |
| ----- | ------------------------------------------------ | ------------ | --------- | ---------- | ------- | ----------- | ------ | -------------------------- |
| 1     | `0xb69ccb3ad06300fefe1c551e285de4a3c6a1a5da`     | SHORT        | 69.6%     | 1,018      | 92      | **+$6,372** | 5      | Lợi nhuận scalper cao nhất |
| **→** | **`0x6dbbefad3d24da625fa233c070678ab1938fcd38`** | **LONG**     | **96.4%** | **725**    | **55**  | **+$622**   | **9**  | **Wallet #3 benchmark**    |
| 2     | `0x77a4b936667e6f10dc70b676d269e9df7deb2759`     | SHORT        | **87.2%** | **720** ⏱ | 179     | +$35.93     | 3      | Hold gần bằng #3!          |
| 3     | `0xf8d2f7cd63a40b9a2cb5c6c4e7d61c95f30302d3`     | STRONG SHORT | 80.5%     | 6,443      | 77      | +$2,755     | 5      | WR cao, lời lớn            |
| 4     | `0x8f63e3fa11518aa93ee865d5e9aae5a28e5dd74`      | SHORT        | 66.7%     | 2,297      | 105     | **+$3,673** | 3      |                            |
| 5     | `0x2cb2e06cfbb927388a5efd3818760b5c9b813f19`     | STRONG SHORT | 76.5%     | 4,037      | 51      | +$1,359     | **9**  | Cùng 9 coins như #3!       |
| 6     | `0x6e14c05d8ea92154a4ba5b8f7b84fc9c7db59f0d`     | STRONG LONG  | **94.4%** | 3,619      | **567** | +$125.53    | **48** | WR cực cao, đa dạng        |
| 7     | `0xb1edfeccf03f35d2268f5dc4013508a6eb52c702`     | LONG         | 67.2%     | 1,617      | 67      | **+$2,647** | 1      | BTC scalper                |
| 8     | `0x04dbc5c154c1491fe20cfc3a7c64a8bef1e4c605`     | LONG         | 64.1%     | 1,787      | 92      | **+$2,186** | 1      |                            |
| 9     | `0x5f6070a14f15b5493163f539ab4ae6594ff36738`     | SHORT        | 73.2%     | **432** ⚡ | 164     | +$655.7     | 1      | Scalper siêu tốc           |
| 10    | `0x2ddea64b4a933d4bdb3c8030ea1a1f88e283958c`     | LONG         | 75.7%     | **477** ⚡ | 70      | +$131.19    | 2      | Scalper nhanh              |

### Chi tiết Wallet giống #3 nhất

#### #1 `0xb69c..a5da` — SHORT Scalper, PnL=$6,372 ⭐

| Field           | Value                                                              |
| --------------- | ------------------------------------------------------------------ |
| Address         | `0xb69ccb3ad06300fefe1c551e285de4a3c6a1a5da`                       |
| Strategy        | DAY_TRADER                                                         |
| Bias            | SHORT (gần 50-50 directional)                                      |
| Trades          | 92                                                                 |
| WR              | 69.6%                                                              |
| Hold            | 1,018s (17 phút)                                                   |
| PnL             | **+$6,372.48**                                                     |
| Max DD          | 0.04%                                                              |
| Copyability     | 45.0%                                                              |
| Score           | 18.5 (thấp do PnL threshold)                                       |
| Peak Hour       | 7:00 UTC (Europe session)                                          |
| **Coins**       | **ZEC ($5,285)** → BTC ($765) → SOL ($325) → ETH (-$7) → HYPE ($4) |
| Warnings        | FEW_ACTIVE_DAYS, REGIME_MISMATCH                                   |
| **Copy status** | **KHÔNG được copy** — high-quality wallet bị bỏ qua                |

**Điểm mạnh**: Lợi nhuận scalper cao nhất tìm thấy ($6,372). Giao dịch 5 coin có thanh khoản. DD gần 0%.
**Điểm yếu**: Score thấp vì threshold, copyability 45%. Cảnh báo REGIME_MISMATCH.

#### #2 `0x77a4..2759` — SHORT Scalper, WR=87.2%, hold=720s ⏱

| Field           | Value                                        |
| --------------- | -------------------------------------------- |
| Address         | `0x77a4b936667e6f10dc70b676d269e9df7deb2759` |
| Strategy        | DAY_TRADER                                   |
| Bias            | SHORT (58 short / 42 long fills)             |
| Trades          | 179                                          |
| WR              | **87.2%**                                    |
| Hold            | **720s (12 phút)** ← giống hệt #3!           |
| PnL             | +$35.93                                      |
| Max DD          | —                                            |
| Copyability     | **95.0%** ← cao nhất                         |
| Score           | 48.2                                         |
| Coins           | 3                                            |
| **Copy status** | **KHÔNG được copy**                          |

**Điểm mạnh**: Hold time gần như bằng wallet #3 (720s vs 725s). WR rất cao (87.2%). Copyability 95%.
**Điểm yếu**: PnL thấp ($35.93), ít coin (3).

#### #3 `0xf8d2..02d3` — STRONG SHORT, WR=80.5%, PnL=$2,755

| Field       | Value                                        |
| ----------- | -------------------------------------------- |
| Address     | `0xf8d2f7cd63a40b9a2cb5c6c4e7d61c95f30302d3` |
| Strategy    | DAY_TRADER                                   |
| Bias        | STRONG SHORT (59 short / 18 long)            |
| Trades      | 77                                           |
| WR          | 80.5%                                        |
| Hold        | 6,443s (107 phút)                            |
| PnL         | **+$2,755.46**                               |
| Copyability | 100.0%                                       |
| Score       | 65.1                                         |
| Coins       | 5                                            |

#### #5 `0x2cb2..3f19` — STRONG SHORT, 9 coins

| Field       | Value                                        |
| ----------- | -------------------------------------------- |
| Address     | `0x2cb2e06cfbb927388a5efd3818760b5c9b813f19` |
| Strategy    | DAY_TRADER                                   |
| Bias        | STRONG SHORT                                 |
| Trades      | 51                                           |
| WR          | 76.5%                                        |
| Hold        | 4,037s (67 phút)                             |
| PnL         | **+$1,359.47**                               |
| Copyability | 100.0%                                       |
| Score       | 66.1                                         |
| **Coins**   | **9** ← cùng số coin với #3                  |

#### #6 `0x6e14..9f0d` — STRONG LONG, WR=94.4%, 48 coins

| Field       | Value                                        |
| ----------- | -------------------------------------------- |
| Address     | `0x6e14c05d8ea92154a4ba5b8f7b84fc9c7db59f0d` |
| Strategy    | DAY_TRADER                                   |
| Bias        | **100% LONG** (0 shorts)                     |
| Trades      | **567**                                      |
| WR          | **94.4%**                                    |
| Hold        | 3,619s (60 phút)                             |
| PnL         | +$125.53                                     |
| Copyability | 50.0%                                        |
| Score       | 69.6                                         |
| **Coins**   | **48** ← đa dạng nhất                        |

---

## IV. HIGH-QUALITY — ĐANG KHÔNG ĐƯỢC COPY

| Address                                      | Strategy   | Trades | WR%       | PnL         | Score | Lý do                     |
| -------------------------------------------- | ---------- | ------ | --------- | ----------- | ----- | ------------------------- |
| `0xb69ccb3ad06300fefe1c551e285de4a3c6a1a5da` | DAY_TRADER | 92     | 69.6%     | **+$6,372** | 63.6  | Copy còn chỗ không?       |
| `0x7aa11aafdfc46ebedbb3adabea180cce3607e8c2` | SWING      | 438    | **94.3%** | +$1,044     | 59.7  | 165 coins, cực kỳ đa dạng |
| `0xb1edfeccf03f35d2268f5dc4013508a6eb52c702` | DAY_TRADER | 67     | 67.2%     | +$2,647     | 51.6  | BTC pure scalper          |

---

## V. HL_COPY_BOT — WALLET DISCOVERY ENGINE

Hệ thống quét + phân tích ví tự động: [`HL_Copy_bot/`](HL_Copy_bot/)

> ⚠️ **Hiện tại**: Chủ yếu tìm ví (scanner + analyzer). Chưa giao dịch thật — paper mode.

| Module    | Tech   | Chức năng                                                  |
| --------- | ------ | ---------------------------------------------------------- |
| Scanner   | Rust   | Quét 10 coin recentTrades + leaderboard → 11,184 wallets   |
| Analyzer  | Python | Deep analysis fills → scoring → copyability                |
| Validator | Python | Kiểm tra điều kiện (trades≥15, WR≥35%, PnL≥$500, DD≤50%)   |
| Copier    | Rust   | Mirror giao dịch (paper mode, $10k giả)                    |
| RIFT      | Python | Monte Carlo (5000 sim), alpha decay, HMM regime (3 states) |

**Luồng**: Scanner → `seen_wallets.json` → Analyzer → `validation_results.json` → Copy/Paper

**Chi tiết**: [`HL_Copy_bot/README.md`](HL_Copy_bot/README.md)

---

## VI. NGUỒN DỮ LIỆU

| File                                            | Nội dung                          |
| ----------------------------------------------- | --------------------------------- |
| `/home/bot/hl_copy_bot/copy_wallets.json`       | 5 ví đang copy                    |
| `/home/bot/hl_copy_bot/validation_results.json` | 1,082 ví phân tích                |
| `/home/bot/hl_copy_bot/seen_wallets.json`       | 11,184 ví đã thấy                 |
| `/home/bot/hl_copy_bot/deep_analysis.json`      | Raw 1,227 fills wallet #3         |
| `/home/bot/hl_copy_bot/analysis_report.txt`     | Báo cáo text (1,564 dòng)         |
| `/home/bot/hl_sniper_bot/ninja_wallets.json`    | 2,076 ví với Sharpe/Sortino/Kelly |
| `/home/bot/hyperreplay-analysis/copy_real.py`   | Kết quả copy simulation           |
| `/home/bot/hyperreplay-analysis/paper_trade.py` | Monitor real-time WebSocket       |

---

## VII. LINKS

- **GitHub repo này**: `https://github.com/phamcanhaz/hyperreplay-analysis`
- **Wallet #3 on Hyperliquid**: https://app.hyperliquid.xyz/address/0x6dbbefad3d24da625fa233c070678ab1938fcd38
