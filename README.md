# HyperReplay Analysis

Hyperliquid wallet analysis — focus on scalping bot patterns.

## Contents

| File                                       | Description                                         |
| ------------------------------------------ | --------------------------------------------------- |
| [`WALLET_REGISTRY.md`](WALLET_REGISTRY.md) | All wallets: đang copy, đã phân tích, đang theo dõi |
| [`BAO_CAO.md`](BAO_CAO.md)                 | Copy simulation report — Wallet #3 ($50 x20, +59%)  |
| [`copy_sim.py`](copy_sim.py)               | Fill-level copy simulation engine                   |
| [`copy_real.py`](copy_real.py)             | Final simulation with all metrics                   |
| [`paper_trade.py`](paper_trade.py)         | Real-time WebSocket paper trading monitor           |
| [`fetch_fills.py`](fetch_fills.py)         | Fetch fills from Hyperliquid API                    |
| [`trace_fills.py`](trace_fills.py)         | Trace fill sequences to detect TWAP patterns        |

## Data

| File                                                             | Description                         |
| ---------------------------------------------------------------- | ----------------------------------- |
| [`similar_wallets_detailed.json`](similar_wallets_detailed.json) | Top 30 wallets similar to Wallet #3 |
| [`data/fills_dedup.json`](data/fills_dedup.json)                 | 1,227 unique fills for Wallet #3    |

## Live Monitor

`paper_trade.py` subscribes via WebSocket to Wallet #3's fills in real-time (no auth needed).
