# Hyperliquid Wallet Registry

> Danh sách ví đang copy, đã phân tích, và đang theo dõi
> Cập nhật: 14/06/2026

---

## I. ĐANG COPY (5 ví)

5 ví đang được copy bot chạy real-time:

| #   | Địa chỉ                                      | Strategy   | 15d PnL | Score | Notes                                               |
| --- | -------------------------------------------- | ---------- | ------- | ----- | --------------------------------------------------- |
| 1   | `0xc4cda69c9354eb77bce1d70c349b2de691be80b8` | SWING      | $1,434  | 73.1  | STRONG LONG, 190 trades                             |
| 2   | `0x8faf84cfba2fded55c8c21c149fc33be79e2b7ba` | SWING      | $1,112  | 53.9  | LONG, 151 trades                                    |
| 3   | `0x6dbbefad3d24da625fa233c070678ab1938fcd38` | DAY_TRADER | $615    | 66.3  | **Wallet #3** — scalper, LONG bias, 9 coins, WR=96% |
| 4   | `0x2ae64d3a931805d91614df81621727594a509887` | DAY_TRADER | $2,502  | 55.5  | STRONG LONG, 66 trades                              |
| 5   | `0x6dbe56e426651ab64c1ad5e552484fae54e0f9fe` | SWING      | $1,655  | 50.9  | STRONG LONG, 26 trades                              |

**Config file:** `/home/bot/hl_copy_bot/copy_wallets.json`

---

## II. PHÂN TÍCH CHI TIẾT — Wallet #3

### Thông tin

| Field           | Value                                        |
| --------------- | -------------------------------------------- |
| Address         | `0x6dbbefad3d24da625fa233c070678ab1938fcd38` |
| Strategy        | DAY_TRADER (scalping bot)                    |
| Bias            | LONG (73% long / 27% short)                  |
| Vốn ước tính    | ~$50-100k (đòn bẩy ~1x)                      |
| Fills phân tích | 1,227 (3.6 ngày, 10-14/06/2026)              |
| Trades tái tạo  | 55                                           |

### Hiệu suất

| Metric        | Giá trị                                             |
| ------------- | --------------------------------------------------- |
| Win rate      | 96.4%                                               |
| Profit Factor | 31,127                                              |
| Max DD        | 0%                                                  |
| Avg hold      | 725s (~12 phút)                                     |
| Copyability   | 85%                                                 |
| Score         | 66.3                                                |
| Coin active   | 9 (HYPE chính, SPCX, BTC, LIT, VVV, TRUMP, XMR, CL) |

### PnL theo coin

| Coin     | PnL      | %   |
| -------- | -------- | --- |
| HYPE     | +$484.11 | 77% |
| xyz:SPCX | +$54.48  | 9%  |
| TRUMP    | +$28.89  | 5%  |
| VVV      | +$27.77  | 4%  |
| BTC      | +$2.68   | —   |

### Kết quả Copy Simulation ($50 USDT x20)

| Metric             | Giá trị          |
| ------------------ | ---------------- |
| Lợi nhuận 3.6 ngày | +$29.55 (+59.1%) |
| Win rate           | 93.9%            |
| Sharpe             | 18.49            |
| Max DD             | 0%               |

### Giờ giao dịch (VN)

| Giờ         | Mức độ              |
| ----------- | ------------------- |
| 22:00-00:00 | **CAO** (306 fills) |
| 11:00-13:00 | **CAO** (221 fills) |
| 19:00-20:00 | TRUNG BÌNH (134)    |
| 00:00-01:00 | TRUNG BÌNH (83)     |
| 03:00-11:00 | THẤP (ngủ)          |

### Phân tích hành vi

- **Scalping TWAP**: Mở/vị thế theo từng chunk nhỏ (2-5s) để giảm slippage
- **Pair trading**: Long altcoin (HYPE, SPCX, XMR, CL), short BTC + small cap (LIT, VVV, TRUMP)
- **Exit pattern**: TWAP chốt lời từ từ, KHÔNG trailing stop
- **Win rate 94% là thật** vì họ chỉ giao dịch khi có lợi thế nhỏ, hold rất ngắn

---

## III. ĐANG PHÂN TÍCH (30 ví giống wallet #3)

Các ví có pattern DAY_TRADER/SCALPER, win rate cao, hold ngắn, nhiều coin.
Source: `validation_results.json` (1,502 wallets analyzed, 70 đạt chuẩn)

### Top giống Wallet #3 nhất

| #   | Địa chỉ                                      | Strategy    | Bias         | Trades | WR%      | Hold(s) | PnL         | Coins  | Copy% |
| --- | -------------------------------------------- | ----------- | ------------ | ------ | -------- | ------- | ----------- | ------ | ----- |
| 1   | `0xb69ccb3ad06300fefe1c551e285de4a3c6a1a5da` | DAY_TRADER  | SHORT        | 92     | 69.6     | 1,018   | **+$6,372** | 5      | 45%   |
| 2   | `0x6dbbefad3d24da625fa233c070678ab1938fcd38` | DAY_TRADER  | LONG         | 55     | 96.4     | 725     | +$622       | 9      | 85%   |
| 3   | `0xf8d2f7cd63a40b9a2cb5c6c4e7d61c95f30302d3` | DAY_TRADER  | STRONG SHORT | 77     | 80.5     | 6,443   | +$2,755     | 5      | 100%  |
| 4   | `0x77a4b936667e6f10dc70b676d269e9df7deb2759` | DAY_TRADER  | SHORT        | 179    | 87.2     | **720** | +$36        | 3      | 95%   |
| 5   | `0x2ae64d3a931805d91614df81621727594a509887` | DAY_TRADER  | STRONG LONG  | 66     | 63.6     | 10,482  | +$2,502     | 5      | 100%  |
| 6   | `0x388d6c0326abe88a6603f7c8b28a7eeb8f9a6c03` | **SCALPER** | NEUTRAL      | 162    | 60.5     | **269** | +$64        | 12     | 0%    |
| 7   | `0x8f63e3fa11518aa93ee865d5e9aae5a28e5dd74`  | DAY_TRADER  | SHORT        | 105    | 66.7     | 2,297   | **+$3,673** | 3      | 50%   |
| 8   | `0x6653f563e39c065b572e91d4be3d451264fc8d0c` | DAY_TRADER  | LONG         | 87     | 69.0     | 1,512   | +$54        | 6      | 45%   |
| 9   | `0x2ddea64b4a933d4bdb3c8030ea1a1f88e283958c` | DAY_TRADER  | LONG         | 70     | 75.7     | **477** | +$131       | 2      | 30%   |
| 10  | `0xc82627a8ef6b8c1168cc7b44d24a5e2ab2379755` | DAY_TRADER  | NEUTRAL      | 118    | 63.6     | 413     | +$944       | 1      | 30%   |
| 11  | `0x2cb2e06cfbb927388a5efd3818760b5c9b813f19` | DAY_TRADER  | STRONG SHORT | 51     | 76.5     | 4,037   | +$1,359     | **9**  | 100%  |
| 12  | `0x658b9c5593fc2da4dfaed7ef6b50ff5d24143f00` | DAY_TRADER  | STRONG LONG  | 93     | 61.3     | 7,182   | +$312       | 17     | 100%  |
| 13  | `0x1b1af29d00fd7e7a755c8de7f8a7c4a5cc638d7`  | DAY_TRADER  | LONG         | 323    | 61.6     | 11,906  | +$270       | 18     | 75%   |
| 14  | `0x6e14c05d8ea92154a4ba5b8f7b84fc9c7db59f0d` | DAY_TRADER  | STRONG LONG  | 567    | **94.4** | 3,619   | +$125       | **48** | 50%   |
| 15  | `0x80f6932fc8339e5f0315f591dce932e9ae2678a1` | DAY_TRADER  | LONG         | 79     | 60.8     | 8,745   | +$114       | 19     | 100%  |
| 16  | `0x4230c19d1c03772cfad369a193213a9e1a16c19d` | **SCALPER** | NEUTRAL      | 146    | 62.3     | **85**  | +$51        | 4      | 0%    |
| 17  | `0x034e4ce0ba7e61169ffd8f42baf75c81f092c619` | DAY_TRADER  | SHORT        | 114    | 81.6     | 10,353  | +$76        | 28     | 90%   |
| 18  | `0xb438de0a23829eaa0b6c727fb9a2cc9ac1090995` | DAY_TRADER  | STRONG SHORT | 445    | 74.6     | 6,098   | +$35        | 49     | 50%   |
| 19  | `0x39d8544e87b8c70fbd12dca27545817c098aeb9`  | DAY_TRADER  | LONG         | 170    | 68.2     | 8,158   | +$42        | 47     | 100%  |
| 20  | `0x899d3f9b59e8ab0eaa8ec6bae03b859ea5620117` | DAY_TRADER  | LONG         | 264    | 72.3     | 8,714   | +$18        | 59     | 75%   |
| 21  | `0x5f6070a14f15b5493163f539ab4ae6594ff36738` | DAY_TRADER  | SHORT        | 164    | 73.2     | **432** | +$656       | 1      | 30%   |
| 22  | `0x6a9e55afab1eef92858acea5778db409e4735870` | DAY_TRADER  | NEUTRAL      | 120    | 68.3     | **416** | +$626       | 1      | 30%   |
| 23  | `0xb1edfeccf03f35d2268f5dc4013508a6eb52c702` | DAY_TRADER  | LONG         | 67     | 67.2     | 1,617   | **+$2,647** | 1      | 45%   |
| 24  | `0x04dbc5c154c1491fe20cfc3a7c64a8bef1e4c605` | DAY_TRADER  | LONG         | 92     | 64.1     | 1,787   | **+$2,186** | 1      | 70%   |
| 25  | `0xe5e045fad7d4b75609b8ad9e832d2d14399b4d70` | DAY_TRADER  | SHORT        | 112    | 55.4     | 11,959  | +$1,034     | 29     | 100%  |

---

## IV. HIGH-QUALITY WALLETS (đang không được copy)

Các ví có data tốt nhưng chưa nằm trong danh sách copy:

| Địa chỉ                                      | Strategy   | Trades | WR%   | PnL     | Score | Ghi chú                               |
| -------------------------------------------- | ---------- | ------ | ----- | ------- | ----- | ------------------------------------- |
| `0xb69ccb3ad06300fefe1c551e285de4a3c6a1a5da` | DAY_TRADER | 99     | 75.8% | +$2,260 | 63.6  | Scalper SHORT, 5 coins, lợi nhuận cao |
| `0x7aa11aafdfc46ebedbb3adabea180cce3607e8c2` | SWING      | 438    | 94.3% | +$1,044 | 59.7  | WR cực cao, 165 coins                 |
| `0xb1edfeccf03f35d2268f5dc4013508a6eb52c702` | DAY_TRADER | 67     | 67.2% | +$2,647 | 51.6  | BTC scalper lợi nhuận cao             |

---

## V. SNAPSHOT WALLETS (có data nhưng chưa đủ)

Các ví từng được copy nhưng data chưa đủ:

| Địa chỉ                                      | Trades | Score | Ghi chú                   |
| -------------------------------------------- | ------ | ----- | ------------------------- |
| `0x18d103744b0f0bd4ab860f3455a252d20580d6dd` | 12     | 85.1  | Score cao nhưng ít trades |
| `0x931153baac031d055389b41d12cd32c9bf0ae7a3` | 6      | 65.8  | Quá ít data               |
| `0x9da9ccc7563bc4c420a7a30819d3875d9499f376` | 12     | 52.2  | Cần thêm thời gian        |
| `0x76fe28b803eeba445c34afc2f914e6bcb71112fd` | 4      | 51.0  | Không đủ để đánh giá      |
| `0x6e6f2ca77afaee5a22dc3cf0f903f39a548a82a6` | 2      | 45.7  | Quá ít                    |

---

## VI. NINJA WALLETS (từ hl_sniper_bot)

2076 wallets từ sniper bot, có metrics Sharpe/Sortino/Kelly.
Top profitable:

| #   | Địa chỉ                                      | Trades | WR%   | PnL      | Sharpe |
| --- | -------------------------------------------- | ------ | ----- | -------- | ------ |
| 1   | `0x5b5d6d6b2c6cf39938bc781137a1c3c58c3c060`  | 1,961  | 100%  | $790,535 | 17.5   |
| 2   | `0xa2e822bcf531b75f3bad9579b4869530c8311468` | 2,000  | 100%  | $725,830 | 5.9    |
| 3   | `0xfdf8ce5e0c0a4d9b97b6e13a28c053029a81e381` | 766    | 100%  | $679,089 | 5.9    |
| 4   | `0x0fac48773e61643d603c230180b63d5c027e7a0a` | 833    | 75.8% | $332,258 | 2.5    |
| 5   | `0x5ae7ae63d17c5fa5e430e6cafba9f60e8cc2c8b8` | 1,504  | 59.6% | $311,632 | 3.2    |

---

## VII. NGUỒN DỮ LIỆU

| File                                                           | Nội dung                          |
| -------------------------------------------------------------- | --------------------------------- |
| `/home/bot/hl_copy_bot/copy_wallets.json`                      | 5 ví đang copy                    |
| `/home/bot/hl_copy_bot/validation_results.json`                | 1,502 ví phân tích (70 worthy)    |
| `/home/bot/hl_copy_bot/seen_wallets.json`                      | 11,184 ví đã thấy                 |
| `/home/bot/hl_copy_bot/deep_analysis.json`                     | Raw fills wallet #3 (1,227 fills) |
| `/home/bot/hl_copy_bot/analysis_report.txt`                    | Báo cáo text (1,564 dòng)         |
| `/home/bot/hyperreplay-analysis/BAO_CAO.md`                    | Phân tích copy sim wallet #3      |
| `/home/bot/hyperreplay-analysis/similar_wallets_detailed.json` | 30 ví giống wallet #3             |
| `/home/bot/hl_sniper_bot/ninja_wallets.json`                   | 2,076 ví với metrics              |
