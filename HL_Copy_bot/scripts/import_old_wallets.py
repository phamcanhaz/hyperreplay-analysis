#!/usr/bin/env python3
"""Import old ninja_wallets.json into new copy bot's seen_wallets.json (merge)."""
import json, os, shutil

OLD = "/home/bot/hl_sniper_bot/ninja_wallets.json"
NEW_DB = "/home/bot/hl_copy_bot/seen_wallets.json"

# Backup existing DB
if os.path.exists(NEW_DB):
    bak = NEW_DB + ".bak"
    shutil.copy2(NEW_DB, bak)
    print(f"Backed up {NEW_DB} -> {bak}")

# Load existing new DB
existing = {}
if os.path.exists(NEW_DB):
    with open(NEW_DB) as f:
        existing = json.load(f)
print(f"Existing DB: {len(existing)} wallets")

# Load old DB
with open(OLD) as f:
    old_data = json.load(f)
print(f"Old DB: {len(old_data)} wallets")

added = 0
skipped = 0
for w in old_data:
    addr = w["address"]
    if addr in existing:
        skipped += 1
        continue
    
    # Calc bias from long/short
    lc = w.get("long_count", 0)
    sc = w.get("short_count", 0)
    if sc > lc * 3:
        bias = "STRONG SHORT"
    elif sc > lc:
        bias = "SHORT"
    elif lc > sc * 3:
        bias = "STRONG LONG"
    elif lc > sc:
        bias = "LONG"
    else:
        bias = "NEUTRAL"
    long_pct = (lc / (lc + sc) * 100) if (lc + sc) > 0 else 50.0

    existing[addr] = {
        "address": addr,
        "first_seen": w.get("first_seen", 0),
        "last_updated": 0,  # forces re-analysis
        "last_trade_ts": 0,
        "total_trades_all": w.get("total_trades", 0),
        "total_pnl_all": w.get("total_pnl", 0.0),
        "trades_15d": 0,
        "pnl_15d": 0.0,
        "wr_15d": 0.0,
        "pf_15d": 0.0,
        "dd_15d": 0.0,
        "bias_15d": "N/A",
        "long_pct_15d": 0.0,
        "avg_hold_secs_15d": 0.0,
        "copy_worthy": False,
        "being_copied": False,
        "score": 0.0,
    }
    added += 1

# Write merged DB
with open(NEW_DB, "w") as f:
    json.dump(existing, f, indent=2)

print(f"Added {added} new wallets, skipped {skipped} existing")
print(f"Total: {len(existing)} wallets in DB")
print(f"\nNote: new wallets have last_updated=0 so analyze_pending will pick them up")
