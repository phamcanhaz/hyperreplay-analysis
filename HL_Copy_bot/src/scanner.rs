use std::collections::HashMap;
use reqwest::Client;
use serde_json::{json, Value};
use tracing::info;

use crate::config::HL_INFO;
use crate::types::WalletInfo;

pub async fn scan_new_wallets(client: &Client, db: &mut WalletDb, seen: &mut HashMap<String, u32>) {
    let mut found = HashSet::new();

    // Recent trades
    for coin in &["BTC", "ETH", "SOL", "HYPE", "ARB", "OP", "DOGE", "PEPE", "SUI", "APT"] {
        let payload = json!({"type": "recentTrades", "coin": coin});
        if let Ok(res) = client.post(HL_INFO).json(&payload).send().await {
            if let Ok(data) = res.json::<Value>().await {
                if let Some(trades) = data.as_array() {
                    for t in trades {
                        for field in &["user", "buyer", "seller"] {
                            if let Some(addr) = t[*field].as_str() {
                                if addr.starts_with("0x") && addr.len() == 42 {
                                    *seen.entry(addr.to_string()).or_insert(0) += 1;
                                    found.insert(addr.to_string());
                                }
                            }
                        }
                        if let Some(users) = t["users"].as_array() {
                            for u in users {
                                if let Some(addr) = u.as_str() {
                                    if addr.starts_with("0x") && addr.len() == 42 {
                                        *seen.entry(addr.to_string()).or_insert(0) += 1;
                                        found.insert(addr.to_string());
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Leaderboard
    if let Ok(res) = client.get("https://stats-data.hyperliquid.xyz/Mainnet/leaderboard").send().await {
        if let Ok(data) = res.json::<Value>().await {
            if let Some(rows) = data["leaderboardRows"].as_array().or_else(|| data.as_array()) {
                for row in rows.iter().take(100) {
                    for field in &["ethAddress", "address"] {
                        if let Some(addr) = row[*field].as_str() {
                            if addr.starts_with("0x") && addr.len() == 42 {
                                *seen.entry(addr.to_string()).or_insert(0) += 3;
                                found.insert(addr.to_string());
                            }
                        }
                    }
                }
            }
        }
    }

    // New wallets in seen but not in db
    let new: Vec<String> = seen.iter()
        .filter(|(a, &c)| c >= 2 && !db.contains_key(*a))
        .map(|(a, _)| a.clone())
        .collect();

    if !new.is_empty() {
        info!("📡 Found {} new wallet candidates", new.len());
        for addr in &new {
                db.insert(addr.clone(), WalletInfo {
                address: addr.clone(),
                first_seen: now_ts(),
                last_updated: 0,
                last_trade_ts: 0,
                total_trades_all: 0,
                total_pnl_all: 0.0,
                trades_15d: 0,
                pnl_15d: 0.0,
                wr_15d: 0.0,
                pf_15d: 0.0,
                dd_15d: 0.0,
                bias_15d: "N/A".into(),
                long_pct_15d: 0.0,
                avg_hold_secs_15d: 0.0,
                copy_worthy: false,
                being_copied: false,
                score: 0.0,
                validated_30d: false,
                consistent_wins_30d: 0,
                strategy_15d: String::new(),
                copyability: 0.0,
                active_days_15d: 0,
                warnings: Vec::new(),
            });
        }
    }

    // Clean up seen entries already in db
    seen.retain(|a, _| !db.contains_key(a));
}

use std::collections::HashSet;
use crate::types::WalletDb;

pub fn load_db() -> WalletDb {
    let path = crate::config::DB_FILE;
    std::fs::read_to_string(path).ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

pub fn atomic_write(path: &str, content: &str) -> bool {
    let tmp = format!("{}.tmp", path);
    if std::fs::write(&tmp, content).is_err() { return false; }
    std::fs::rename(&tmp, path).is_ok()
}

pub fn save_db(db: &WalletDb) {
    let path = crate::config::DB_FILE;
    if let Ok(s) = serde_json::to_string(db) {
        let _ = atomic_write(path, &s);
    }
}

pub fn read_regime() -> String {
    // Try dedicated regime.json first
    let path = crate::config::REGIME_FILE;
    if let Some(regime) = std::fs::read_to_string(path).ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
        .and_then(|v| v["regime"].as_str().map(String::from))
    {
        return regime;
    }
    // Fallback: read __meta__ from validation_results.json
    let vpath = crate::config::VALIDATION_FILE;
    std::fs::read_to_string(vpath).ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
        .and_then(|v| v["__meta__"]["regime"].as_str().map(String::from))
        .unwrap_or_else(|| "unknown".into())
}

pub fn load_and_apply_validations(db: &mut WalletDb) {
    // Reset all wallets first — only validated wallets get set back below
    for w in db.values_mut() {
        w.copy_worthy = false;
        w.validated_30d = false;
    }

    let path = crate::config::VALIDATION_FILE;

    let content = match std::fs::read_to_string(path) {
        Ok(c) => c,
        Err(_) => return,
    };
    let validations: serde_json::Value = match serde_json::from_str(&content) {
        Ok(v) => v,
        Err(_) => return,
    };
    let obj = match validations.as_object() {
        Some(o) => o,
        None => return,
    };
    for (addr, info) in obj {
        if addr == "__meta__" { continue; }
        if let Some(w) = db.get_mut(addr) {
            let checked_at = info.get("checked_at").and_then(|v| v.as_u64()).unwrap_or(now_ts());
            w.last_updated = checked_at;
            let valid = info["valid"].as_bool().unwrap_or(false);
            let cw = info["consistent_wins"].as_u64().unwrap_or(0) as u8;
            w.validated_30d = valid;
            w.consistent_wins_30d = cw;
            w.copy_worthy = valid;

            // Try new format (flat keys from analyzer_deep.py)
            if info.get("score").and_then(|v| v.as_f64()).is_some() {
                if let Some(pnl) = info["total_pnl"].as_f64() { w.pnl_15d = pnl; }
                if let Some(wr) = info["win_rate"].as_f64() { w.wr_15d = wr; }
                if let Some(pf) = info["profit_factor"].as_f64() { w.pf_15d = pf; }
                if let Some(dd) = info["max_dd"].as_f64() { w.dd_15d = dd; }
                if let Some(tr) = info["total_trades"].as_u64() { w.trades_15d = tr; }
                if let Some(score) = info["score"].as_f64() { w.score = score; }
                if let Some(bias) = info["bias"].as_str() { w.bias_15d = bias.to_string(); }
                if let Some(hold) = info["avg_hold_secs"].as_f64() { w.avg_hold_secs_15d = hold; }
                if let Some(strategy) = info["strategy"].as_str() { w.strategy_15d = strategy.to_string(); }
                if let Some(copyability) = info["copyability"].as_f64() { w.copyability = copyability; }
                if let Some(days) = info["daily"]["active_days"].as_u64() { w.active_days_15d = days; }
                if let Some(warnings) = info["warnings"].as_array() {
                    w.warnings = warnings.iter()
                        .filter_map(|v| v.as_str().map(String::from))
                        .collect();
                    // Evict copies with high-risk warnings
                    if w.warnings.contains(&"SCALPER".to_string())
                        || w.warnings.contains(&"ALPHA_DECAYING".to_string())
                        || w.warnings.contains(&"CRISIS_REGIME".to_string())
                        || w.warnings.contains(&"REGIME_MISMATCH".to_string())
                    {
                        w.copy_worthy = false;
                    }
                }
            // Fallback: old validator.py format (nested under "total")
            } else if let Some(tot) = info["total"].as_object() {
                if let Some(pnl) = tot["pnl"].as_f64() { w.pnl_15d = pnl; }
                if let Some(wr) = tot["wr"].as_f64() { w.wr_15d = wr; }
                if let Some(pf) = tot["pf"].as_f64() { w.pf_15d = pf; }
                if let Some(dd) = tot["dd"].as_f64() { w.dd_15d = dd; }
                if let Some(tr) = tot["trades"].as_u64() { w.trades_15d = tr; }
                // Old format has no score/bias/hold, derive score from metrics
                let tc = (w.trades_15d as f64 / 30.0).min(1.0);
                let t = (w.trades_15d as f64 / 100.0).min(1.0) * 15.0;
                let w2 = (w.wr_15d / 100.0) * 20.0;
                let p = (w.pf_15d / 10.0).min(1.0) * 20.0 * tc;
                let d = (1.0 - w.dd_15d.min(50.0) / 50.0).max(0.0) * 15.0 * tc;
                let r = (w.pnl_15d / 5000.0).min(1.0) * 30.0 * tc;
                w.score = (t + w2 + p + d + r).clamp(0.0, 100.0);
                w.bias_15d = "N/A".into();
            }

            // Override score with new formula (trade-count weighted)
            let tc = (w.trades_15d as f64 / 30.0).min(1.0);
            w.score = ((w.trades_15d as f64 / 100.0).min(1.0) * 15.0
                + (w.wr_15d / 100.0) * 20.0
                + (w.pf_15d / 10.0).min(1.0) * 20.0 * tc
                + (1.0 - w.dd_15d.min(50.0) / 50.0).max(0.0) * 15.0 * tc
                + (w.pnl_15d / 5000.0).min(1.0) * 30.0 * tc)
                .clamp(0.0, 100.0);
            // Active days penalty — require >=5 active days for full score
            let dc = (w.active_days_15d as f64 / 5.0).min(1.0);
            w.score *= dc;

            // Override copyability (in case Python analyzer hasn't run with new formula)
            let tpd = if w.trades_15d > 0 && w.active_days_15d > 0 { w.trades_15d as f64 / w.active_days_15d as f64 } else if w.trades_15d > 0 { w.trades_15d as f64 / 30.0 } else { 0.0 };
            let mut copy = 100.0_f64;
            let tp = if w.strategy_15d == "SWING" || w.strategy_15d == "POSITION" { 0.5 } else { 1.0 };
            if tpd > 30.0 { copy -= 50.0 * tp; }
            else if tpd > 15.0 { copy -= 25.0 * tp; }
            else if tpd > 10.0 { copy -= 10.0 * tp; }
            if w.avg_hold_secs_15d > 0.0 {
                if w.avg_hold_secs_15d < 120.0 { copy -= 40.0; }
                else if w.avg_hold_secs_15d < 600.0 { copy -= 20.0; }
                else if w.avg_hold_secs_15d < 1800.0 { copy -= 5.0; }
            }
            w.copyability = copy.max(0.0);

            let stale_age = now_ts().saturating_sub(w.last_updated);
            if stale_age > 86400 {
                if !w.warnings.contains(&"STALE_DATA".to_string()) {
                    w.warnings.push("STALE_DATA".to_string());
                }
                w.copy_worthy = false;
            }

            if w.trades_15d < 2 && w.score > 0.0 && !w.warnings.contains(&"INACTIVE".to_string()) {
                w.warnings.push("INACTIVE".to_string());
            }
        }
    }
}

pub fn evict_stale_wallets(db: &mut WalletDb, copied: &[String]) -> usize {
    const TTL_SECS: u64 = 30 * 86400;
    let now = now_ts();
    let mut to_remove = Vec::new();
    for (addr, w) in db.iter() {
        if copied.contains(addr) { continue; }
        let age = if w.last_updated > 0 { now - w.last_updated } else { now - w.first_seen };
        if age > TTL_SECS {
            to_remove.push(addr.clone());
        }
    }
    for addr in &to_remove {
        db.remove(addr);
    }
    if !to_remove.is_empty() {
        info!("🧹 Evicted {} stale wallets (TTL >30d)", to_remove.len());
    }
    to_remove.len()
}

pub fn now_ts() -> u64 {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs()
}
