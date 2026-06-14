#!/bin/bash
# Long-run monitor: runs 30-min monitor.sh every hour for 8 hours
# Also captures summary at the end
LOGFILE=/home/bot/hl_copy_bot/bot.log
MONITOR=/home/bot/hl_copy_bot/monitor.sh
OUTDIR=/home/bot/hl_copy_bot/monitor_reports
mkdir -p $OUTDIR

echo "=== LONG MONITOR START $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "Bot PID: $(pgrep -f hl-copy-bot)"
echo "Target: 8 hours (8 x 60min = 480 min total)"
echo ""

for i in $(seq 1 8); do
  echo "--- Round $i/8: starting 30min monitor at $(date -u +%H:%M:%S) ---"
  bash $MONITOR
  REPORT="$OUTDIR/report_round${i}_$(date -u +%H%M).txt"
  cp /home/bot/hl_copy_bot/monitor_report.txt "$REPORT"
  
  # Quick stats
  FILLS=$(grep -c "\[ws\] FILL" $LOGFILE)
  ERROR=$(grep -ci "error\|fail" $LOGFILE | head -1)
  RECON=$(grep -c "RECONCILE" $LOGFILE)
  echo "  Round $i done: ${FILLS}f ${ERROR}e ${RECON}r" >> $OUTDIR/round_summary.txt
  
  echo "  Saved to $REPORT"
  echo "  Current stats: FILL=$FILLS ERROR=$ERROR RECONCILE=$RECON"
  echo ""
  
  # Wait remaining time (monitor.sh runs for 30min, wait 30min more)
  sleep 1800
done

echo "=== LONG MONITOR END $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "Final stats:" 
grep -c "\[ws\] FILL" $LOGFILE
grep -c "RECONCILE" $LOGFILE
grep -c "disconnected" $LOGFILE
