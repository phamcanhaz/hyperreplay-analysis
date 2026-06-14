# So Sánh Chi Tiết — Wallet #3 vs Các Ví Giống

> Dữ liệu từ `validation_results.json` (trade reconstruction) + API fetch (capital, coins, active period)
> Ngày: 14/06/2026

---

## I. BẢNG SO SÁNH TỔNG QUAN

| #   | Ví             | Strategy   | Bias         | Vốn ~     | Ngày bắt đầu | Số ngày | Fills | Trades | WR%         | PnL         | Coins  | Copy%    |
| --- | -------------- | ---------- | ------------ | --------- | ------------ | ------- | ----- | ------ | ----------- | ----------- | ------ | -------- |
| 🏆  | **Wallet #3**  | DAY_TRADER | **LONG**     | **$100k** | **10/06**    | **3.6** | 1,227 | **55** | **96.4%**   | **+$622**   | **9**  | **85%**  |
| 1   | `0xb69c..a5da` | DAY_TRADER | SHORT        | **$252k** | 11/06        | 3.0     | 2,000 | 92     | 69.6%       | **+$6,372** | 7      | 45%      |
| 2   | `0x77a4..2759` | DAY_TRADER | SHORT        | **$62k**  | **27/03** 🗓️ | **444** | 2,000 | 179    | **87.2%**   | +$36        | 5      | **95%**  |
| 3   | `0xf8d2..02d3` | DAY_TRADER | STRONG SHORT | **$173k** | **02/02** 🗓️ | **132** | 879   | 77     | 80.5%       | **+$2,755** | 7      | **100%** |
| 4   | `0x6e14..9f0d` | DAY_TRADER | STRONG LONG  | **$2k**   | 10/06        | 4.2     | 2,000 | 567    | **94.4%**   | +$125       | **48** | 50%      |
| 5   | `0xb1ed..c702` | DAY_TRADER | LONG         | **$423k** | 12/06        | 2.3     | 2,000 | 67     | 67.2%       | **+$2,647** | 1      | 45%      |
| 6   | `0x8f63..dd74` | DAY_TRADER | SHORT        | —         | —            | —       | —     | 105    | 66.7%       | **+$3,673** | 3      | 50%      |
| 7   | `0x2cb2..3f19` | DAY_TRADER | STRONG SHORT | —         | —            | —       | —     | 51     | 76.5%       | **+$1,359** | **9**  | **100%** |
| 8   | `0x5f60..6738` | DAY_TRADER | SHORT        | —         | —            | —       | 164   | 73.2%  | +$656       | 1           | 30%    |
| 9   | `0x04db..c605` | DAY_TRADER | LONG         | —         | —            | —       | 92    | 64.1%  | **+$2,186** | 1           | 70%    |
| 10  | `0x2dde..958c` | DAY_TRADER | LONG         | —         | —            | —       | 70    | 75.7%  | +$131       | 2           | 30%    |

> **Ghi chú**: Vốn ước tính = max position notional. Ví #6-10 không fetch được fills từ API (dữ liệu cũ).

---

## II. PHÂN TÍCH CHI TIẾT TỪNG VÍ

### 🏆 Wallet #3 — `0x6dbbefad3d24da625fa233c070678ab1938fcd38`

**Benchmark — DAY_TRADER Scalping Bot**

| Metric                 | API Fetch                | validation_results       |
| ---------------------- | ------------------------ | ------------------------ |
| Fills                  | 1,227                    | 1,227                    |
| Trades (reconstructed) | 488 (fill-level)         | **55** (proper position) |
| WR                     | 99.8%                    | **96.4%**                |
| PnL                    | +$2,780                  | **+$622.53**             |
| Capital                | ~$100k                   | —                        |
| Coins                  | 9                        | 9                        |
| Period                 | 10/06 → 14/06 (3.6 days) | 5 active days            |
| Direction              | 49% L / 51% S            | **73% L / 27% S**        |
| Max PnL coin           | HYPE: +$1,932 (69%)      | HYPE: +$484 (77%)        |

**Kết luận**: Wallet #3 là scalper TWAP chuyên nghiệp. Vốn ~$100k, giao dịch 9 coin, LONG bias (73%). HYPE chiếm 70%+ lợi nhuận. **Rủi ro tập trung HYPE.**

---

### #1 `0xb69ccb3ad06300fefe1c551e285de4a3c6a1a5da`

**DAY_TRADER SHORT — Lợi nhuận scalper cao nhất tìm thấy!**

| Metric       | API Fetch                                | validation_results     |
| ------------ | ---------------------------------------- | ---------------------- |
| Fills        | **2,000+**                               | —                      |
| Trades       | 1,470 (fill-level)                       | **92** (proper)        |
| WR           | 44.8% (fill)                             | **69.6%** (trade)      |
| PnL          | -$3,255 (fill)                           | **+$6,372.48** ✅      |
| Capital      | **~$252k**                               | —                      |
| Coins        | 7 (BTC, ETH, HYPE, SOL, XRP, ZEC, TRUMP) | 5                      |
| Period       | 11/06 → 14/06 (3 days)                   | —                      |
| Direction    | 56% L / 44% S                            | **~50/50**             |
| Max PnL coin | —                                        | **ZEC: +$5,285 (83%)** |

**Điểm mạnh**: PnL cao nhất ($6,372). Giao dịch đa coin có thanh khoản. Vốn lớn ($252k).
**Điểm yếu**: Score thấp (18.5). Copyability 45%. Cảnh báo REGIME_MISMATCH.
**Khác biệt với #3**: SHORT bias, vốn gấp 2.5x, ZEC chứ không phải HYPE.

**TRẠNG THÁI: KHÔNG được copy** — đáng để thêm vào!

---

### #2 `0x77a44b15d5ad00fc7b8d6fea6ec1fa61a3be2759`

**DAY_TRADER SHORT — Hold time gần bằng Wallet #3! (720s vs 725s)**

| Metric    | API Fetch                         | validation_results    |
| --------- | --------------------------------- | --------------------- |
| Fills     | **2,000+**                        | —                     |
| Trades    | 707 (fill-level)                  | **179** (proper)      |
| WR        | 81.2% (fill)                      | **87.2%** ✅          |
| PnL       | -$1,669 (fill)                    | **+$35.93**           |
| Capital   | **~$62k**                         | —                     |
| Coins     | 5 (BTC, ETH, HYPE, SOL, FARTCOIN) | 3                     |
| Period    | **27/03 → 14/06 (444 ngày!)** 🗓️  | —                     |
| Direction | 41.5% L / 58.5% S                 | SHORT bias            |
| Avg Hold  | —                                 | **720s (12 phút)** ⏱ |

**Điểm mạnh**:

- **Hold time gần như bằng Wallet #3** (720s vs 725s) — cùng phong cách scalping!
- **Đã hoạt động 444 ngày** — ổn định nhất trong tất cả
- **WR 87.2%** — rất cao
- **Copyability 95%** — cao nhất trong danh sách
- Vốn $62k — phù hợp để copy

**Điểm yếu**: PnL thấp ($35.93). API shows negative PnL gần đây.

**TRẠNG THÁI: KHÔNG được copy** — Ứng viên sáng giá!

---

### #3 `0xf8d2fded7432cd648200553dfcbca504aa3402d3`

**DAY_TRADER STRONG SHORT — Win rate cao, lợi nhuận lớn**

| Metric      | API Fetch                                    | validation_results |
| ----------- | -------------------------------------------- | ------------------ |
| Fills       | 879                                          | —                  |
| Trades      | 396 (fill-level)                             | **77** (proper)    |
| WR          | 71.7% (fill)                                 | **80.5%** ✅       |
| PnL         | **+$2,355** (fill)                           | **+$2,755.46** ✅  |
| Capital     | **~$173k**                                   | —                  |
| Coins       | 7 (BTC, ETH, SOL, ZEC, xyz:CL, GOLD, SILVER) | 5                  |
| Period      | **02/02 → 14/06 (132 ngày)** 🗓️              | —                  |
| Copyability | —                                            | **100%**           |

**Điểm mạnh**:

- Hoạt động từ tháng 2 (132 ngày) — dài hạn
- WR 80.5%, PnL +$2,755
- Copyability 100% — sẵn sàng copy
- Đa coin (7 coins, bao gồm cả hàng hóa GOLD/SILVER)

**Điểm yếu**: SHORT bias (đi ngược với #3), vốn $173k (gấp 1.7x #3)

---

### #4 `0x6e1402f1a16642da68336205c2231c7a45dc9f0d`

**DAY_TRADER STRONG LONG — Đa dạng nhất (48 coins!), WR 94.4%**

| Metric      | API Fetch                | validation_results |
| ----------- | ------------------------ | ------------------ |
| Fills       | **2,000+**               | —                  |
| Trades      | 966 (fill-level)         | **567** (proper)   |
| WR          | 58.5% (fill)             | **94.4%** ✅       |
| PnL         | -$388 (fill)             | **+$125.53**       |
| Capital     | **~$2k**                 | —                  |
| Coins       | **48 (!)**               | **48**             |
| Period      | 10/06 → 14/06 (4.2 days) | —                  |
| Copyability | —                        | 50%                |

**Điểm mạnh**:

- **567 trades** — nhiều nhất
- **WR 94.4%** — cao nhất
- **48 coins** — đa dạng nhất, spread risk tốt

**Điểm yếu**:

- PnL thấp (+$125 trên 567 trades = $0.22/trade)
- Vốn rất nhỏ ($2k) — khó copy với $50
- 100% LONG (không short bao giờ)

---

### #5 `0xb1edfeccf03f35d2268f5dc4013508a6eb52c702`

**DAY_TRADER LONG — BTC pure scalper, PnL +$2,647**

| Metric  | API Fetch                | validation_results |
| ------- | ------------------------ | ------------------ |
| Fills   | **2,000+**               | —                  |
| Trades  | 1,126 (fill-level)       | **67** (proper)    |
| WR      | 37.7% (fill)             | **67.2%**          |
| PnL     | -$237 (fill)             | **+$2,647.08** ✅  |
| Capital | **~$423k**               | —                  |
| Coins   | **1 (BTC)**              | 1                  |
| Period  | 12/06 → 14/06 (2.3 days) | —                  |

**Điểm mạnh**: PnL $2,647 trên BTC scalping. Vốn lớn $423k.
**Điểm yếu**: Chỉ 1 coin (BTC). WR 67%. Copyability 45%. Score thấp vì threshold.

---

### #6 `0x8f63e3fa11518aa93ee865d5e9aae5a28e5dd74`

**DAY_TRADER SHORT — PnL +$3,673 (chỉ từ validation_results)**

| Metric      | Giá trị          |
| ----------- | ---------------- |
| Trades      | 105              |
| WR          | 66.7%            |
| PnL         | **+$3,673.50**   |
| Coins       | 3                |
| Hold        | 2,297s (38 phút) |
| Copyability | 50%              |
| Score       | 27.9             |

> Không fetch được fills từ API — dữ liệu cũ

---

### #7 `0x2cb2e06cfbb927388a5efd3818760b5c9b813f19`

**DAY_TRADER STRONG SHORT — 9 coins (bằng #3!)**

| Metric      | Giá trị          |
| ----------- | ---------------- |
| Trades      | 51               |
| WR          | 76.5%            |
| PnL         | **+$1,359.47**   |
| Coins       | **9**            |
| Hold        | 4,037s (67 phút) |
| Copyability | **100%**         |
| Score       | 66.1             |

> Cùng số coin với Wallet #3 (9). Copyability 100%.

---

## III. SO SÁNH NHANH VỚI WALLET #3

| Tiêu chí  | Wallet #3 | #1 b69c    | #2 77a4      | #3 f8d2  | #4 6e14  | #5 b1ed  |
| --------- | --------- | ---------- | ------------ | -------- | -------- | -------- |
| **WR**    | **96.4%** | 69.6%      | 87.2%        | 80.5%    | 94.4%    | 67.2%    |
| **Hold**  | **725s**  | 1,018s     | **720s**     | 6,443s   | 3,619s   | 1,617s   |
| **PnL**   | $622      | **$6,372** | $36          | $2,755   | $125     | $2,647   |
| **Coins** | 9         | 7          | 5            | 7        | **48**   | 1        |
| **Vốn**   | $100k     | $252k      | $62k         | $173k    | $2k      | $423k    |
| **Copy%** | 85%       | 45%        | **95%**      | **100%** | 50%      | 45%      |
| **Tuổi**  | 3.6 ngày  | 3 ngày     | **444 ngày** | 132 ngày | 4.2 ngày | 2.3 ngày |

---

## IV. TOP VÍ NÊN THEO DÕI / COPY

| Hạng | Ví                           | Lý do                                                    |
| ---- | ---------------------------- | -------------------------------------------------------- |
| ⭐   | **Wallet #3** `0x6dbb..cd38` | **Đang copy.** Benchmark — cần thêm data                 |
| 🥇   | **#1 b69c** `0xb69c..a5da`   | PnL cao nhất ($6,372), 7 coins. **Nên thêm vào copy!**   |
| 🥈   | **#2 77a4** `0x77a4..2759`   | Hold = #3 (720s), WR 87%, copy 95%, **444 ngày** ổn định |
| 🥉   | **#3 f8d2** `0xf8d2..02d3`   | WR 80%, PnL $2,755, copy 100%, 132 ngày                  |
| 4    | **#6 8f63** `0x8f63..dd74`   | PnL $3,673 nếu còn active                                |
| 5    | **#7 2cb2** `0x2cb2..3f19`   | 9 coins (= #3), WR 76%, copy 100%                        |

---

## V. FILE DỮ LIỆU

| File                            | Nội dung                              |
| ------------------------------- | ------------------------------------- |
| `similar_deep_v2.json`          | API fetch results (6 wallets)         |
| `similar_wallets_detailed.json` | 30 wallets từ validation_results      |
| `correct_addresses.json`        | Danh sách địa chỉ đầy đủ (20 wallets) |
