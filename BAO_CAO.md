# Báo Cáo Copy Simulation — Ví #3 (0x6dbbefad)

## Dữ liệu

- **Khung thời gian**: 3.6 ngày (10-14/06/2026)
- **Tổng fills**: 1,227 (bỏ qua 101 fills @107 — airdrop/sell)
- **Giới hạn API**: Chỉ lấy được 3.6 ngày gần nhất, không có data cũ hơn

## Hành Vi Ví #3

| Metric                  | Giá trị                                                      |
| ----------------------- | ------------------------------------------------------------ |
| Số lệnh cùng lúc tối đa | **7** (trung bình 3.7)                                       |
| Đòn bẩy ước tính        | **~1x** (giao dịch như spot)                                 |
| Coin active             | 9 coin, **HYPE chiếm 58%**                                   |
| Exit pattern            | **Ladder TP** (chốt lời từng phần), KHÔNG phải trailing stop |
| Win rate (fill-level)   | **94.1%**                                                    |
| Số lần mirror giao dịch | **509** trong 3.6 ngày                                       |

## Kết Quả Copy ($50 USDT x20)

| Metric                | Giá trị                            |
| --------------------- | ---------------------------------- |
| Vốn                   | $50                                |
| Đòn bẩy tối đa        | 20x                                |
| Scale                 | ~1% (ví dùng $100k → ta dùng $1k)  |
| **Lợi nhuận thực tế** | **+$27.81 (+55.63%)**              |
| **Ngoại suy tháng**   | **~+$232 (+464%)**                 |
| Win rate              | 94.1%                              |
| Profit Factor         | 139,071 (gần như không có lệnh lỗ) |
| Sharpe                | 18.49                              |
| Drawdown tối đa       | **0.00%**                          |
| Số lệnh cùng lúc (ta) | 6                                  |

### PnL Theo Ngày

```
2026-06-10: +$5.11
2026-06-11: +$0.12 (ngày yếu)
2026-06-12: +$13.58 (ngày mạnh)
2026-06-13: +$8.73
2026-06-14: +$0.27
```

### PnL Theo Coin

```
HYPE:     +$19.33 (69%)
xyz:SPCX: +$4.90 (18%)
BTC:      +$1.18
VVV:      +$1.00
LIT:      +$0.75
TRUMP:    +$0.32
xyz:CL:   +$0.17
XMR:      +$0.15
```

## Phân Tích Chi Tiết

### 1. Đòn bẩy

Đòn bẩy thực tế của ví này rất thấp (~1x). Điều này có nghĩa:

- Họ đánh với số lượng lớn nhưng không dùng margin nhiều
- Position value lên tới $100k nhưng capital ước tính cũng ~$50-100k
- Nếu bạn copy với $50 x20, bạn đang dùng đòn bẩy CAO HƠN họ rất nhiều

### 2. Exit Pattern (cách thoát lệnh)

- KHÔNG phải trailing stop
- **Ladder TP**: Họ chốt lời từ từ, bán từng phần nhỏ khi giá chạy theo hướng có lợi
- Điều này giải thích win rate gần như 100% — họ luôn chốt phần có lời trước, phần còn lại để đó
- Nhưng rủi ro: phần còn lại có thể thua lỗ nếu giá đảo chiều mạnh

### 3. Rủi Ro Khi Copy

| Rủi ro             | Mức độ  | Giải thích                              |
| ------------------ | ------- | --------------------------------------- |
| Data quá ngắn      | 🔴 CAO  | Chỉ 3.6 ngày, không đủ đánh giá         |
| Win rate ảo        | 🔴 CAO  | 94% là do ladder TP, không phải thực tế |
| Tập trung HYPE     | 🟡 TB   | 69% lợi nhuận từ 1 coin                 |
| PnL ngày không đều | 🟡 TB   | Có ngày $0.12, ngày $13.58              |
| Residual positions | 🟢 THẤP | Residual rất nhỏ (vài cent)             |

### 4. Kết Luận

- Ví #3 là một **scalper bot** chuyên nghiệp, chốt lời từ từ
- **Có thể copy được** với $50 x20, nhưng cần thêm data để confirm
- **Win rate 94% là không bền vững** — kỳ vọng thực tế 60-70%
- Rủi ro lớn nhất: HYPE dump mạnh (chiếm 69% PnL)
- Nên theo dõi thêm 2-4 tuần trước khi copy thật

## Files

- Script: `/home/bot/hyperreplay-analysis/copy_sim.py`
- Data: `/home/bot/hl_copy_bot/deep_analysis.json`
- Raw analysis: `/home/bot/hyperreplay-analysis/report.json`
