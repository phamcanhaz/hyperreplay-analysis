# Phân Tích Sâu — Wallet f8d2

> `0xf8d2fded7432cd648200553dfcbca504aa3402d3`
> **DAY_TRADER | STRONG SHORT | WR 80.5% | PnL +$2,755 | 132 ngày**

---

## I. TỔNG QUAN

| Field              | Giá trị                            |
| ------------------ | ---------------------------------- |
| **Strategy**       | DAY_TRADER — Short Scalping        |
| **Bias**           | STRONG SHORT (81% trades là short) |
| **Period**         | **02/02 → 14/06 (132 ngày)**       |
| **Fills**          | 879 (API)                          |
| **Trades**         | 396 (reconstructed)                |
| **Win Rate**       | 71.7%                              |
| **Total PnL**      | **+$2,355**                        |
| **Profit Factor**  | 1.5                                |
| **Capital**        | ~$57k (max notional $172k / 3)     |
| **Đòn bẩy**        | ~3.5x                              |
| **Coins**          | 7                                  |
| **Avg Trades/Day** | 16.5                               |
| **Peak Hour**      | 5:00-6:00 VN (sáng sớm)            |

---

## II. COIN BREAKDOWN

| Coin           | Fills | Long | Short | Long%   | Volume    | Ghi chú                     |
| -------------- | ----- | ---- | ----- | ------- | --------- | --------------------------- |
| **BTC**        | 336   | 145  | 191   | 43%     | **$2.1M** | Volume lớn nhất (38% fills) |
| ZEC            | 187   | 78   | 109   | 42%     | $358k     | Short bias                  |
| **xyz:SILVER** | 168   | 84   | 84    | 50%     | **$584k** | 50/50, hàng hóa             |
| ETH            | 127   | 71   | 56    | 56%     | $267k     | Hơi LONG                    |
| xyz:CL         | 52    | 39   | 13    | **75%** | $139k     | LONG nhất                   |
| xyz:GOLD       | 7     | 3    | 4     | 43%     | $14k      | Ít                          |
| SOL            | 2     | 1    | 1     | 50%     | $2k       | Không đáng kể               |

**Khác biệt với Wallet #3**:

- Wallet #3 có **per-coin directional bias** (long coin A, short coin B)
- Wallet f8d2 gần như **NEUTRAL trên từng coin** — vào lệnh cả 2 chiều trên cùng 1 coin

---

## III. TRADES — PHÂN TÍCH CHI TIẾT

### Long vs Short

|              | LONG         | SHORT                |
| ------------ | ------------ | -------------------- |
| **Trades**   | 74 (19%)     | **322 (81%)**        |
| **Win Rate** | 78.4%        | 70.2%                |
| **PnL**      | +$14.66 (1%) | **+$2,340.52 (99%)** |

=> **Đây là SHORT SCALPER thuần túy.** 99% lợi nhuận từ short trades.

### Lệnh/ngày

| Metric             | Giá trị  |
| ------------------ | -------- |
| Active days        | 24       |
| **Avg trades/day** | **16.5** |
| Min/day            | 1        |
| Max/day            | 57       |

### Top ngày

| Ngày      | Trades | PnL         | WR%  | Ghi chú                            |
| --------- | ------ | ----------- | ---- | ---------------------------------- |
| **06/06** | 18     | **+$519**   | 100% |                                    |
| **06/05** | 14     | **+$2,813** | 100% | Ngày đẹp nhất!                     |
| 06/08     | **57** | -$1,862     | 79%  | Giao dịch nhiều nhất nhưng lỗ nặng |
| 06/12     | 48     | -$591       | 52%  | Ngày xấu                           |
| 06/14     | 9      | -$242       | 0%   |                                    |

### Win/Loss Size

| Metric         | Giá trị               |
| -------------- | --------------------- |
| **Avg Win**    | +$26.26               |
| **Avg Loss**   | -$45.55               |
| Win/Loss ratio | 0.58 (lỗ lớn hơn lãi) |
| Profit Factor  | 1.5                   |

> ⚠️ Avg loss gần gấp đôi avg win. WR 71.7% bù đắp cho điều này.

---

## IV. GIỜ GIAO DỊCH (VN)

```
00:00 ██████████ 51
01:00 ██████████ 53
02:00 ████████ 43
03:00 █████████ 45
04:00 ██████████ 51
05:00 ███████████████ 78 ← PEAK
06:00 ███████████████ 79 ← PEAK
...
18:00 ██████████████ 70 ← Secondary peak
19:00 █████████████ 65
20:00 ████████████ 64
21:00 ████████████ 64
```

**Peak**: 5:00-6:00 VN (sáng sớm châu Á) + 18:00-21:00 VN (tối)

**Khác Wallet #3**:

- Wallet #3: peak 22:00-00:00 và 11:00-13:00 VN
- Wallet f8d2: peak 5:00-6:00 và 18:00-21:00

---

## V. VỐN VÀ ĐÒN BẨY

| Metric                | Giá trị       |
| --------------------- | ------------- |
| Avg position notional | $12,958       |
| Max position notional | **$172,561**  |
| Est capital (max/3)   | **~$57,520**  |
| Fill size median      | **$1,000**    |
| Fill size P25-P75     | $171 → $4,562 |
| Fill size max         | $75,000       |

**Đòn bẩy**: ~3.5x (cao hơn wallet #3 ~1x)

---

## VI. PHONG CÁCH GIAO DỊCH

1. **STRONG SHORT Scalper**: 81% trades là short, 99% PnL từ short
2. **Multi-coin**: 7 coins (BTC, ZEC, SILVER, ETH, CL, GOLD, SOL)
3. **Không directional bias per coin**: Vào cả 2 chiều trên cùng coin (khác #3)
4. **TWAP execution**: Fill size đa dạng ($10 → $75k) — vào/thoát theo chunk
5. **Giao dịch cả hàng hóa**: xyz:SILVER, xyz:GOLD, xyz:CL — độc đáo
6. **Volume lớn**: $2.1M BTC volume, $584k SILVER volume

---

## VII. RỦI RO

| Rủi ro                 | Mức     | Giải thích                               |
| ---------------------- | ------- | ---------------------------------------- |
| **Lỗ gần đây**         | 🔴 CAO  | 3 ngày liên tiếp lỗ (Jun 12-14): -$1,193 |
| **Avg Loss > Avg Win** | 🔴 CAO  | Lỗ $45 vs lãi $26 — cần WR cao để bù     |
| **Tập trung BTC**      | 🟡 TB   | 38% fills là BTC                         |
| **Alpha decay**        | 🟡 TB   | Tháng 5: 100% WR. Tháng 6: lỗ            |
| **Copyability**        | 🟢 THẤP | 100% — cao nhất                          |
| **Tuổi đời**           | 🟢 THẤP | 132 ngày — dài, đã kiểm chứng            |

---

## VIII. SO SÁNH VỚI WALLET #3

| Tiêu chí          | Wallet #3                     | Wallet f8d2                   |
| ----------------- | ----------------------------- | ----------------------------- |
| **Strategy**      | LONG scalper (73% L)          | **STRONG SHORT** (81% S)      |
| **WR**            | **96.4%**                     | 71.7%                         |
| **Hold**          | **725s (12ph)**               | longer (~107ph từ validation) |
| **PnL**           | +$622 / 3.6d                  | **+$2,355 / 132d**            |
| **Capital**       | ~$100k                        | ~$57k                         |
| **Đòn bẩy**       | ~1x                           | **~3.5x**                     |
| **Coins**         | 9 (HYPE chính)                | 7 (BTC, ZEC, SILVER)          |
| **Per-coin bias** | **CÓ** (long coin A, short B) | KHÔNG (neutral all coins)     |
| **Giờ peak**      | 22-00, 11-13 VN               | **5-6, 18-21 VN**             |
| **Tuổi**          | 3.6 ngày                      | **132 ngày** ✅               |
| **Gần đây**       | Ngừng từ 09:20 hôm nay        | Đang lỗ 3 ngày liên tiếp ⚠️   |

---

## IX. KẾT LUẬN

**Wallet f8d2** là short scalper chuyên nghiệp với:

- ✅ **132 ngày** hoạt động — đã kiểm chứng dài hạn
- ✅ Copyability **100%**
- ✅ Đa coin (7), volume lớn
- ❌ **Đang lỗ 3 ngày liên tiếp** (alpha decay?)
- ❌ Avg loss > avg win
- ❌ Khác bias với #3 (SHORT vs LONG)

**Có thể copy** nhưng cần theo dõi thêm 1-2 tuần xem có hồi phục không.
