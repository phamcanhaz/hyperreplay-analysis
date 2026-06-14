#!/bin/bash
# Monitor bot for 30 minutes, capture detailed diagnostics
LOGFILE=/home/bot/hl_copy_bot/bot.log
OUTFILE=/home/bot/hl_copy_bot/monitor_report.txt
END=$((SECONDS+1800))
SCAN_COUNT=0

echo "=== MONITOR START $(date -u +%H:%M:%S) ===" > $OUTFILE

while [ $SECONDS -lt $END ]; do
  sleep 60
  ELAPSED=$((1800 - (END - SECONDS)))
  MIN=$((ELAPSED / 60))
  echo "" >> $OUTFILE
  echo "--- T+${MIN}min @ $(date -u +%H:%M:%S) ---" >> $OUTFILE

  # Count scans
  SCANS=$(grep -c "Scan #" $OUTFILE 2>/dev/null || true)
  NEW_SCANS=$(tail -20 $LOGFILE | grep -c "Scan #")
  echo "  Scans: +${NEW_SCANS} (total ~$(grep -c 'Scan #' $LOGFILE))" >> $OUTFILE

  # Reconcile events
  echo "  RECONCILE events (last 5min):" >> $OUTFILE
  tail -200 $LOGFILE | grep "RECONCILE" | grep -v "summary" | tail -10 | sed 's/^/    /' >> $OUTFILE

  # Reconcile summary (acted/skipped/in-range)
  echo "  RECONCILE summary:" >> $OUTFILE
  tail -200 $LOGFILE | grep "RECONCILE.*summary" | tail -1 | sed 's/^/    /' >> $OUTFILE

  # Fills (with user field now showing wallet)
  echo "  FILL events:" >> $OUTFILE
  tail -200 $LOGFILE | grep "FILL\|PAPER.*BUY\|PAPER.*SELL" | tail -5 | sed 's/^/    /' >> $OUTFILE

  # Errors/warnings
  echo "  ERRORS:" >> $OUTFILE
  tail -200 $LOGFILE | grep -i "error\|fail\|retry\|timeout\|panic\|BANKRUPT" | tail -5 | sed 's/^/    /' >> $OUTFILE

  # Auto-add / evict
  echo "  AUTO-ADD / EVICT:" >> $OUTFILE
  tail -500 $LOGFILE | grep "AUTO-ADD\|EVICT" | tail -5 | sed 's/^/    /' >> $OUTFILE

  # SKIP events (cooldown working?)
  echo "  SKIP (cooldown):" >> $OUTFILE
  tail -200 $LOGFILE | grep "SKIP" | tail -5 | sed 's/^/    /' >> $OUTFILE

  # WS health
  echo "  WS health:" >> $OUTFILE
  tail -200 $LOGFILE | grep "\[ws\] HEALTH" | tail -1 | sed 's/^/    /' >> $OUTFILE
  tail -200 $LOGFILE | grep "\[ws\] disconnected" | tail -1 | sed 's/^/    /' >> $OUTFILE

  # Status line (copy count, regime)
  echo "  Status:" >> $OUTFILE
  tail -20 $LOGFILE | grep "Status:" | tail -1 | sed 's/^/    /' >> $OUTFILE

  # Price fetch failures
  echo "  Price fetch:" >> $OUTFILE
  tail -200 $LOGFILE | grep "fetch_coin_price\|FAILED.*price\|retry.*price\|orderbook.*fallback" | tail -3 | sed 's/^/    /' >> $OUTFILE

  # Poll timing
  echo "  Poll timing:" >> $OUTFILE
  tail -100 $LOGFILE | grep "\[poll\] done" | tail -1 | sed 's/^/    /' >> $OUTFILE

  # Target fetch failures
  echo "  Target fetch:" >> $OUTFILE
  tail -100 $LOGFILE | grep "target fetch:" | tail -1 | sed 's/^/    /' >> $OUTFILE

  # Last 3 log lines for context
  echo "  Tail:" >> $OUTFILE
  tail -3 $LOGFILE | sed 's/^/    /' >> $OUTFILE
done

echo "" >> $OUTFILE
echo "=== MONITOR END @ $(date -u +%H:%M:%S) ===" >> $OUTFILE
echo "=== SUMMARY ===" >> $OUTFILE
echo "Total scans: $(grep -c 'Scan #' $LOGFILE)" >> $OUTFILE
echo "Total RECONCILE: $(grep -c 'RECONCILE' $LOGFILE)" >> $OUTFILE
echo "  SKIP: $(grep -c 'SKIP' $LOGFILE)" >> $OUTFILE
echo "Total FILL: $(grep -c 'FILL' $LOGFILE)" >> $OUTFILE
echo "Total AUTO-ADD: $(grep -c 'AUTO-ADD' $LOGFILE)" >> $OUTFILE
echo "Total EVICT: $(grep -c 'EVICT' $LOGFILE)" >> $OUTFILE
echo "Total ERROR: $(grep -ci 'error\|fail\|timeout' $LOGFILE)" >> $OUTFILE
echo "Price fetch issues: $(grep -c 'fetch_coin_price\|FAILED.*price\|retry.*price' $LOGFILE)" >> $OUTFILE
echo "WS disconnects: $(grep -c 'disconnected' $LOGFILE)" >> $OUTFILE
echo "Target fetch fails: $(grep -c 'fetch FAILED' $LOGFILE)" >> $OUTFILE
echo "BANKRUPT events: $(grep -c 'BANKRUPT' $LOGFILE)" >> $OUTFILE
echo "" >> $OUTFILE
echo "=== FULL RECONCILE LOG ===" >> $OUTFILE
grep "RECONCILE" $LOGFILE >> $OUTFILE
echo "" >> $OUTFILE
echo "=== FULL AUTO-ADD/EVICT LOG ===" >> $OUTFILE
grep -E "AUTO-ADD|EVICT" $LOGFILE >> $OUTFILE
echo "" >> $OUTFILE
echo "=== FULL ERROR LOG ===" >> $OUTFILE
grep -in -E "error|fail|retry|timeout|panic|BANKRUPT|fetch FAILED|FAILED" $LOGFILE >> $OUTFILE
echo "" >> $OUTFILE
echo "=== WS DISCONNECT LOG ===" >> $OUTFILE
grep "disconnected" $LOGFILE >> $OUTFILE
