# Phân Tích Sâu — Wallet b1ed

> `0xb1edfeccf03f35d2268f5dc4013508a6eb52c702`
> **DAY_TRADER | LONG bias | WR 67.2% | PnL +$2,647 | BTC PURE SCALPER**

---

## I. TỔNG QUAN

| Field              | Giá trị                                |
| ------------------ | -------------------------------------- |
| **Strategy**       | DAY_TRADER — BTC Pure Scalping         |
| **Bias**           | LONG (51% long) — nhưng 75.8% WR short |
| **Period**         | **2 ngày** (validation)                |
| **Fills**          | 2000 (API max — ~900 fills/ngày)       |
| **Trades**         | **67** (validation)                    |
| **Win Rate**       | **67.2%**                              |
| **Total PnL**      | **+$2,647** (validation)               |
| **Gross PnL**      | +$3,164 / -$517                        |
| **Profit Factor**  | **6.1** (rất cao)                      |
| **Max DD**         | 8% (rất thấp)                          |
| **Capital**        | ~$141k (max notional $423k / 3)        |
| **Đòn bẩy**        | ~3x-4x                                 |
| **Coins**          | **1 — BTC DUY NHẤT**                   |
| **Avg Trades/Day** | ~33                                    |
| **Avg Hold**       | **1,617s (~27 phút)**                  |
| **Peak Hour**      | 15:00 VN (EUROPE session)              |
| **Copyability**    | 45%                                    |

> ⚠️ **Chú ý**: Dữ liệu gần đây (12-14/06) cho thấy wallet ĐANG LỖ nặng. Xem mục VII.

---

## II. COIN BREAKDOWN

| Coin    | Fills | Long | Short | Long% | Volume     | Ghi chú              |
| ------- | ----- | ---- | ----- | ----- | ---------- | -------------------- |
| **BTC** | 2000  | 917  | 1083  | 46%   | **$17.8M** | 100% — coin duy nhất |

**Điểm đặc biệt**: Đây là wallet **BTC pure scalper** duy nhất trong danh sách top 10. Chỉ giao dịch 1 coin nhưng volume $17.8M trong 2.2 ngày.

---

## III. TRADES — PHÂN TÍCH CHI TIẾT

### Long vs Short (từ validation)

|              | LONG        | SHORT             |
| ------------ | ----------- | ----------------- |
| **Trades**   | 34 (51%)    | 33 (49%)          |
| **Win Rate** | 58.8%       | **75.8%**         |
| **PnL**      | +$493 (19%) | **+$2,154 (81%)** |
| **Avg PnL**  | +$14.50     | **+$65.27**       |

> Mặc dù bias là LONG, **shorts mang lại 81% lợi nhuận** với WR 75.8% — cao hơn hẳn longs (58.8%).

### Top ngày (từ fill analysis)

| Ngày      | Trades | PnL         | WR% |
| --------- | ------ | ----------- | --- |
| **12/06** | 34     | -$234       | 35% |
| **13/06** | 17     | -$417       | 29% |
| **14/06** | 8      | **-$2,848** | 25% |

> 3 ngày liên tiếp lỗ với WR cực thấp (25-35%).

---

## IV. HOLD TIME

| Metric       | Giá trị      |
| ------------ | ------------ |
| **Min hold** | ~1 phút      |
| **P25**      | ~5 phút      |
| **Median**   | **~27 phút** |
| **P75**      | ~1 giờ       |
| **Max hold** | ~16 giờ      |
| **Avg hold** | **~27 phút** |

> Hold time phù hợp với DAY_TRADER — giao dịch nhanh trong vòng 30 phút. Không phải scalper siêu nhanh như wallet #3 (12 giây) hay f8d2.

---

## V. GIỜ GIAO DỊCH (VN)

```
00:00 █████████ 45
01:00 ██████ 30
02:00 ████ 24
03:00 ███████████ 55
04:00 █████ 28
05:00 ████████████████████████ 124
06:00 █████████████████ 86
07:00 ████████████████████████ 124
08:00 █████████████████████ 106
09:00 ████████████████ 84
10:00 █████████████████████████ 127
11:00 █████████ 46
12:00 ██████████████████ 90
13:00 ████████████████████████████████████████████ 223 ← PEAK
14:00 ████████████████████████ 121
15:00 ███████████████████████ 119
16:00 ████████ 44
17:00 ███████ 38
18:00 ██████ 30
19:00 ██████ 31
20:00 █████ 29
21:00 █████████████████████████████ 149
22:00 ████████████████████████████████ 162
23:00 █████████████████ 85
```

**Peak**: 13:00-15:00 VN (giờ châu Âu — trùng với `session: EUROPE`)
**Secondary**: 21:00-22:00 VN

**Khác Wallet #3**:

- Wallet #3: peak 22:00-00:00 (đêm) và 11:00-13:00 (trưa)
- Wallet b1ed: peak 13:00-15:00 (chiều) — **EUROPE session**

---

## VI. VỐN VÀ ĐÒN BẨY

| Metric                | Giá trị       |
| --------------------- | ------------- |
| Avg position notional | **$112,692**  |
| Max position notional | **$423,245**  |
| Est capital (max/3)   | **~$141,000** |
| Fill size median      | **$3,852**    |
| Fill size P25-P75     | $77 → $10,769 |
| Fill size max         | $218,827      |

**Đòn bẩy**: ~3x-4x (thấp hơn f8d2 ~3.5x, cao hơn #3 ~1x)

**Vốn lớn nhất** trong tất cả các scalper:

- Wallet #3: ~$100k
- Wallet f8d2: ~$57k
- Wallet b1ed: **~$141k**

---

## VII. PHONG CÁCH & ĐÁNH GIÁ RỦI RO

### Phong cách

1. **BTC pure scalper** — chỉ 1 coin, không diversification
2. **Long/Short đều có** — 51% long / 49% short, nhưng short hiệu quả hơn (75.8% WR)
3. **Volume cực lớn** — $17.8M trong 2.2 ngày, ~$8M/ngày
4. **Hold time ~27 phút** — day trading, không scalper siêu tốc
5. **Giao dịch giờ châu Âu** — peak 13:00-15:00 VN

### Rủi ro

| Rủi ro                 | Mức     | Giải thích                                 |
| ---------------------- | ------- | ------------------------------------------ |
| **Lỗ gần đây**         | 🔴 CAO  | 3 ngày lỗ liên tiếp, WR 25-35%             |
| **Tập trung 1 coin**   | 🔴 CAO  | BTC 100% — không diversification           |
| **Có open short**      | 🟡 TB   | Validation: đang hold short 1.326 BTC      |
| **Alpha decay**        | 🔴 CAO  | PnL từ +$2,647 → -$3,190 chỉ trong 3.5 giờ |
| **Copyability**        | 🟡 TB   | 45% — thấp hơn #3 (100%) và f8d2 (100%)    |
| **Tuổi đời**           | 🔴 THẤP | Chỉ 2 ngày active (validation)             |
| **FEW_ACTIVE_DAYS**    | 🔴 CẢNH | Cảnh báo từ validation system              |
| **CONCENTRATION_100%** | 🔴 CẢNH | Cảnh báo từ validation system              |

---

## VIII. SO SÁNH VỚI WALLET #3 VÀ f8d2

| Tiêu chí        | Wallet #3          | Wallet f8d2          | **Wallet b1ed**          |
| --------------- | ------------------ | -------------------- | ------------------------ |
| **Strategy**    | LONG scalper (73%) | STRONG SHORT (81%)   | DAY_TRADER (LONG bias)   |
| **WR**          | **96.4%**          | 71.7%                | 67.2%                    |
| **Hold**        | **725s (12ph)**    | longer (~107ph)      | **1,617s (27ph)**        |
| **PnL**         | +$622 (3.6 ngày)   | +$2,355 (132 ngày)   | +$2,647 (2 ngày)         |
| **Capital**     | ~$100k             | ~$57k                | **~$141k**               |
| **Đòn bẩy**     | ~1x                | ~3.5x                | ~3-4x                    |
| **Coins**       | 9 (HYPE chính)     | 7 (BTC, ZEC, SILVER) | **1 (BTC duy nhất)**     |
| **Volume/ngày** | —                  | —                    | **~$8M/ngày**            |
| **Giờ peak**    | 22-00, 11-13 VN    | 5-6, 18-21 VN        | **13-15 VN (EUROPE)**    |
| **Tuổi**        | 3.6 ngày           | **132 ngày**         | 2 ngày                   |
| **Copyability** | 100%               | 100%                 | 45%                      |
| **Gần đây**     | Ngừng từ 09:20     | Đang lỗ 3 ngày       | **Đang lỗ nặng, WR 25%** |

---

## IX. LƯU Ý QUAN TRỌNG

### Dữ liệu validation vs dữ liệu gần đây

Có sự khác biệt LỚN giữa 2 bộ dữ liệu:

| Metric     | Validation (11:01 VN) | Fill Analysis (14:33 VN) |
| ---------- | --------------------- | ------------------------ |
| **Trades** | 67                    | 59 (3.5h sau)            |
| **PnL**    | **+$2,647**           | **-$3,190**              |
| **WR**     | 67.2%                 | 41.3%                    |

> Wallet đã **mất $5,837** chỉ trong ~3.5 giờ — từ +$2,647 xuống -$3,190. Đây là dấu hiệu **alpha decay** hoặc stop hunting.

### Khả năng copy

- **45%** — thấp hơn nhiều so với #3 (100%) và f8d2 (100%)
- Lý do: FEW_ACTIVE_DAYS (chỉ 2 ngày), CONCENTRATION_100% (BTC only)
- **KHÔNG khuyến nghị copy** cho đến khi có dữ liệu dài hạn hơn

---

## X. KẾT LUẬN

**Wallet b1ed** là BTC pure scalper với:

- ✅ PnL $2,647 cao trong 2 ngày
- ✅ Profit factor 6.1 (rất tốt)
- ✅ Max DD chỉ 8%
- ✅ Short WR 75.8% — chuyên nghiệp short BTC

- ❌ **Chỉ 2 ngày active** — chưa đủ dữ liệu
- ❌ **100% BTC** — không diversification, rủi ro cao
- ❌ **Đang lỗ nặng** — PnL từ +$2,647 → -$3,190 chỉ trong 3.5 giờ
- ❌ Copyability 45%
- ❌ Không rõ tuổi thật của wallet (API chỉ trả về 2000 fills gần nhất)

**Kết luận**: KHÔNG NÊN COPY ở thời điểm hiện tại. Cần theo dõi thêm 1-2 tuần để:

1. Xác nhận wallet có ổn định không
2. Thấy rõ xu hướng dài hạn
3. Chờ wallet hồi phục từ đợt lỗ gần đây
