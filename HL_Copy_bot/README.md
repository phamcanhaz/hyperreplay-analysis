# HL_Copy_bot — Hyperliquid Copy Bot

> ⚠️ **HIỆN TẠI: Wallet Discovery + Scanner**
> Chưa có giao dịch thật (paper trading mode). Chủ yếu quét ví, phân tích, và theo dõi.

## Trạng thái hiện tại

| Chức năng                   | Trạng thái                     |
| --------------------------- | ------------------------------ |
| 🔍 Quét ví mới (scanner)    | ✅ Hoạt động                   |
| 📊 Phân tích sâu (analyzer) | ✅ Hoạt động                   |
| 📋 Validation + scoring     | ✅ Hoạt động                   |
| 💰 Paper trading            | ✅ Chạy ($10k giả)             |
| 🚀 Giao dịch thật           | ❌ Chưa — cần thêm data + test |

## Luồng hoạt động

```
Scanner (Rust) → seen_wallets.json → Analyzer (Python) → validation_results.json → Copy decision
                                                                                        ↓
                                                                                 Copier (Rust)
                                                                                 Paper trading
```

1. **Scanner** (`src/scanner.rs`): Quét `recentTrades` + leaderboard → 11,184 wallets
2. **Analyzer** (`analyzer_deep.py`): Phân tích fills → scoring → copyability
3. **Validator** (`validator.py`): Kiểm tra điều kiện copy (WR, PnL, DD, v.v.)
4. **Copier** (`src/copier.rs`): Mirror giao dịch (hiện tại paper mode)

## File chính

| File                  | Mô tả                                |
| --------------------- | ------------------------------------ |
| `copy_wallets.json`   | 5 ví đang copy                       |
| `analysis_report.txt` | Báo cáo full                         |
| `deep_analyze.py`     | Fetch fills cho 1 ví                 |
| `analyze_wallet3.py`  | Phân tích wallet #3                  |
| `regime.json`         | Trạng thái thị trường                |
| `src/scanner.rs`      | Quét ví mới                          |
| `src/copier.rs`       | Copy engine                          |
| `rift_modules/`       | Monte Carlo, alpha decay, HMM regime |

## Cách chạy

```bash
# Scanner (Rust)
cargo run -- scan

# Analyzer (Python)
python3 analyzer_deep.py

# Fetch fills cho 1 ví
python3 deep_analyze.py <address>
```

## Lưu ý

- `PAPER_TRADING=true` trong `.env` — chạy thử, không giao dịch thật
- Cần `PRIVATE_KEY` để chạy live (chưa có)
- Max 5 ví copy / 2 per strategy
- SCALPER bị chặn, DAY_TRADER/SWING được copy
