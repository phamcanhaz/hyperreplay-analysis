#!/bin/bash
LOG=/home/bot/hyperreplay-analysis/paper_trade_output.log
if ps aux | grep -q "[p]aper_trade.py"; then
  echo "✅ Bot đang chạy"
  echo "=== 10 dòng cuối ==="
  tail -10 "$LOG"
  echo "=== Tổng số dòng ==="
  wc -l "$LOG"
else
  echo "❌ Bot không chạy"
fi
