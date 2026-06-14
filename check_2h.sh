#!/bin/bash
LOG=/home/bot/hyperreplay-analysis/paper_trade_output.log
SNAP=/home/bot/hyperreplay-analysis/snapshot.txt
REPORT=/home/bot/hyperreplay-analysis/report_2h.txt

{
  echo "=============================================="
  echo "BÁO CÁO SAU 2 GIỜ"
  echo "Thời gian: $(date '+%Y-%m-%d %H:%M:%S VN')"
  echo "=============================================="
  
  if ps aux | grep -q "[p]aper_trade.py"; then
    echo "✅ Bot còn sống"
  else
    echo "❌ Bot đã chết"
  fi
  
  total_lines=$(wc -l < "$LOG")
  echo ""
  echo "Tổng dòng log: $total_lines"
  
  # Đếm số giao dịch
  trades=$(grep -c "PnL=" "$LOG" 2>/dev/null || echo 0)
  echo "Giao dịch đã xử lý: $trades"
  
  # Tính tổng PnL
  pnl_sum=$(grep -oP 'PnL=\K[+-]?\d+\.?\d*' "$LOG" 2>/dev/null | paste -sd+ | bc 2>/dev/null || echo 0)
  echo "Tổng PnL: \$$pnl_sum"
  
  lines_before=$(head -1 "$SNAP" 2>/dev/null | grep -oP '\d+' || echo 0)
  echo ""
  echo "20 dòng cuối:"
  echo "----------------"
  tail -20 "$LOG"
  echo "----------------"
  
  echo ""
  echo "Status lines:"
  grep -a "STATUS" "$LOG" | tail -5
  
} > "$REPORT" 2>&1

cat "$REPORT"
