mod config;
mod types;
mod scanner;
mod analyzer;
mod copier;
mod error;
mod ws;
mod paper;

use std::collections::HashMap;
use std::sync::Arc;
use reqwest::Client;
use tokio::sync::Mutex;
use tokio::time::{sleep, Duration};
use tracing::info;

use types::*;
use scanner::now_ts;

fn selection_score(w: Option<&WalletInfo>) -> f64 {
    let w = match w {
        Some(x) => x,
        None => return 0.0,
    };
    let mut penalty = 1.0f64;
    for warn in &w.warnings {
        match warn.as_str() {
            "INACTIVE" => penalty *= 0.5,
            _ => {}
        }
    }
    w.score * penalty * (w.copyability / 100.0)
        * if w.last_updated > 0 && now_ts().saturating_sub(w.last_updated) > 86400 { 0.7 } else { 1.0 }
}

async fn tick(
    client: &Client,
    db: &mut WalletDb,
    seen: &mut HashMap<String, u32>,
    copy_state: &mut Vec<CopyState>,
    active_targets: &Arc<Mutex<Vec<String>>>,
    scan_count: &mut u64,
) {
    *scan_count += 1;

    info!("\n━━━ [Scan #{}] ━━━", scan_count);
    scanner::scan_new_wallets(client, db, seen).await;
    scanner::save_db(db);

    if *scan_count % config::COPY_MGMT_EVERY_N_SCANS == 0 {
        scanner::load_and_apply_validations(db);
        let copied: Vec<String> = copy_state.iter().map(|c| c.target_address.clone()).collect();
        scanner::evict_stale_wallets(db, &copied);

        // Evict wallets that are no longer copy-worthy
        let to_evict: Vec<String> = copy_state.iter()
            .filter(|c| !db.get(&c.target_address).map(|w| w.copy_worthy).unwrap_or(false))
            .map(|c| c.target_address.clone())
            .collect();
        for addr in &to_evict {
            info!("🔄 EVICT {} (not copy-worthy)", &addr[..10]);
            if let Some(w) = db.get_mut(addr) { w.being_copied = false; }
            active_targets.lock().await.retain(|x| x != addr);
            copy_state.retain(|c| c.target_address != *addr);
        }

        // Add validated wallets from Python deep analyzer
        let mut candidates: Vec<String> = db.iter()
            .filter(|(_, w)| w.copy_worthy && w.validated_30d && !w.being_copied && w.copyability >= 5.0)
            .map(|(a, _)| a.clone())
            .collect();
        candidates.sort_by(|a, b| {
            let sa = selection_score(db.get(a));
            let sb = selection_score(db.get(b));
            sb.partial_cmp(&sa).unwrap_or(std::cmp::Ordering::Equal)
        });

        // Count per-strategy copies for diversity constraint
        let mut strat_count: HashMap<String, usize> = HashMap::new();
        for cs in copy_state.iter() {
            let s = db.get(&cs.target_address).map(|w| w.strategy_15d.clone()).unwrap_or_default();
            *strat_count.entry(s).or_insert(0) += 1;
        }

        for addr in &candidates {
            if copy_state.iter().any(|c| c.target_address == *addr) { continue; }
            let (w_pnl, w_score, w_copy, w_strat) = match db.get(addr) {
                Some(w) => {
                    if w.copyability < 5.0 { continue; }
                    (w.pnl_15d, w.score, w.copyability, w.strategy_15d.clone())
                }
                None => continue,
            };
            let cscore = selection_score(db.get(addr));

            if copy_state.len() < config::MAX_COPY_WALLETS
                && strat_count.get(&w_strat).copied().unwrap_or(0) < config::MAX_PER_STRATEGY
            {
                *strat_count.entry(w_strat).or_insert(0) += 1;
                info!("✅ AUTO-ADD {} (score={:.0}, copy={:.0}%)", &addr[..10], w_score, w_copy);
                copy_state.push(CopyState {
                    target_address: addr.clone(),
                    target_pnl_15d: w_pnl,
                    started_at: now_ts(),
                    active: true,
                });
                active_targets.lock().await.push(addr.clone());
                if let Some(w) = db.get_mut(addr) { w.being_copied = true; }
            } else {
                let replace = {
                    let lowest = copy_state.iter()
                        .filter(|cs| db.get(&cs.target_address).map(|w2| w2.strategy_15d == w_strat).unwrap_or(false))
                        .min_by(|a, b| {
                            let sa = selection_score(db.get(&a.target_address));
                            let sb = selection_score(db.get(&b.target_address));
                            sa.partial_cmp(&sb).unwrap_or(std::cmp::Ordering::Equal)
                        });
                    lowest.and_then(|low| {
                        let low_score = selection_score(db.get(&low.target_address));
                        if cscore > low_score { Some((low.target_address.clone(), low_score)) } else { None }
                    })
                };
                if let Some((old, old_score)) = replace {
                    info!("🔄 REPLACE {} (score={:.0}) → {} (score={:.0}) [{}]", &old[..10], old_score, &addr[..10], cscore, w_strat);
                    if let Some(w) = db.get_mut(&old) { w.being_copied = false; }
                    active_targets.lock().await.retain(|x| x != &old);
                    copy_state.retain(|c| c.target_address != old);
                    copy_state.push(CopyState {
                        target_address: addr.clone(),
                        target_pnl_15d: w_pnl,
                        started_at: now_ts(),
                        active: true,
                    });
                    active_targets.lock().await.push(addr.clone());
                    if let Some(w) = db.get_mut(addr) { w.being_copied = true; }
                }
            }
        }
        scanner::save_db(db);
        copier::save_snapshot(copy_state);
        analyzer::generate_report(db, config::REPORT_FILE);
    }

    let copy_count = active_targets.lock().await.len();
    let worthy_count = db.values().filter(|w| w.copy_worthy).count();
    let pending_count = db.values().filter(|w| !w.copy_worthy && w.last_updated == 0).count();
    let regime = scanner::read_regime();
    info!("📊 Status: {} DB | {} worthy | {} pending | {} copied | regime={}",
        db.len(), worthy_count, pending_count, copy_count, regime);

    let mut sorted: Vec<&WalletInfo> = db.values().filter(|w| w.copy_worthy).collect();
    sorted.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
    println!("\n┌──────────┬──────────┬────────┬──────┬──────┬──────┬─────┬─────────┬───────┬───────┬──────────────────────────┐");
    println!("│ Wallet   │ 15d PnL  │  WR%   │  PF  │  DD% │ Bias │Days│ Strategy│ Score │ Copy │ Warnings                 │");
    println!("├──────────┼──────────┼────────┼──────┼──────┼──────┼─────┼─────────┼───────┼───────┼──────────────────────────┤");
    for w in sorted.iter().take(10) {
        let copy = if w.being_copied { "★" } else { " " };
        let strategy_display = if w.strategy_15d.is_empty() { "N/A" } else { &w.strategy_15d };
        let copy_display = format!("{:>3.0}%", w.copyability);
        let warn_display = w.warnings.join(",");
        println!("│ {}{:.8}│ ${:>7.0}│ {:>5.1}%│ {:>4.1}│ {:>4.1}%│ {:>5}│ {:>3}│ {:>7}│ {:>5.0}│ {:>5}│ {:>24}│",
            copy, w.address, w.pnl_15d, w.wr_15d, w.pf_15d, w.dd_15d, w.bias_15d, w.active_days_15d, strategy_display, w.score, copy_display, warn_display);
    }
    println!("└──────────┴──────────┴────────┴──────┴──────┴──────┴─────┴─────────┴───────┴───────┴──────────────────────────┘");

    if copy_count > 0 {
        let targets = active_targets.lock().await.clone();
        println!("\n📡 ACTIVE COPIES:");
        for addr in &targets {
            let info = db.get(addr).map(|w| format!("PnL=${:.0} WR={:.1}%", w.pnl_15d, w.wr_15d))
                .unwrap_or("?".into());
            println!("  {} → {}", &addr[..10], info);
        }
    }

    sleep(Duration::from_secs(config::MAIN_TICK_SECS)).await;
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(std::env::var("RUST_LOG").unwrap_or("info".into()))
        .init();
    let _ = dotenvy::dotenv();

    println!("╔════════════════════════════════════════════════════════════════╗");
    println!("║  📡 HL COPY BOT — Scan → Python Deep Analysis → Copy        ║");
    println!("║  Scanner discovers wallets, Python analyzes, bot copies      ║");
    println!("╚════════════════════════════════════════════════════════════════╝");

    let client = Client::builder().timeout(Duration::from_secs(8)).build().unwrap();

    // Load state
    let mut db = scanner::load_db();
    let mut seen: HashMap<String, u32> = HashMap::new();
    info!("📂 Loaded {} known wallets", db.len());
    scanner::load_and_apply_validations(&mut db);
    let validated_count = db.values().filter(|w| w.validated_30d).count();
    info!("✅ Loaded validation data: {} wallets validated", validated_count);

    let copier = Arc::new(copier::Copier::new().await);
    let our_positions: Arc<Mutex<HashMap<String, OurPosition>>> = Arc::new(Mutex::new(HashMap::new()));
    let target_positions: Arc<Mutex<HashMap<String, HashMap<String, TargetPosition>>>> = Arc::new(Mutex::new(HashMap::new()));
    let active_targets: Arc<Mutex<Vec<String>>> = Arc::new(Mutex::new(Vec::new()));

    // Load existing copy state (only restore wallets still deemed copy-worthy)
    let snapshot = copier::load_snapshot();
    for cs in &snapshot {
        if cs.active {
            let is_ok = db.get(&cs.target_address).map(|w| w.copy_worthy).unwrap_or(false);
            if !is_ok {
                info!("⏸️  Skip restore {} (no longer copy-worthy, PnL: ${:.0})", &cs.target_address[..10], cs.target_pnl_15d);
                if let Some(w) = db.get_mut(&cs.target_address) {
                    w.being_copied = false;
                }
            }
        }
    }
    let mut copy_state: Vec<CopyState> = snapshot.into_iter()
        .filter(|cs| {
            if !cs.active { return false; }
            db.get(&cs.target_address).map(|w| w.copy_worthy).unwrap_or(false)
        })
        .collect();

    // Enforce MAX_PER_STRATEGY on restore — evict lowest-scored excess wallets
    let mut strat_count: HashMap<String, usize> = HashMap::new();
    for cs in &copy_state {
        let s = db.get(&cs.target_address).map(|w| w.strategy_15d.clone()).unwrap_or_default();
        *strat_count.entry(s).or_insert(0) += 1;
    }
    for (s, cnt) in strat_count.clone().iter() {
        if *cnt > config::MAX_PER_STRATEGY {
            let excess = cnt - config::MAX_PER_STRATEGY;
            let mut addrs: Vec<String> = copy_state.iter()
                .filter(|cs| db.get(&cs.target_address).map(|w| w.strategy_15d == *s).unwrap_or(false))
                .map(|cs| cs.target_address.clone())
                .collect();
            addrs.sort_by(|a, b| {
                let sa = selection_score(db.get(a));
                let sb = selection_score(db.get(b));
                sa.partial_cmp(&sb).unwrap_or(std::cmp::Ordering::Equal)
            });
            for addr in addrs.iter().take(excess) {
                info!("⏸️  Evict {} from snapshot (excess {s}, {cnt} > MAX_PER_STRATEGY)", &addr[..10]);
                if let Some(w) = db.get_mut(addr) { w.being_copied = false; }
                copy_state.retain(|c| c.target_address != *addr);
            }
        }
    }

    for cs in &copy_state {
        if cs.active {
            active_targets.lock().await.push(cs.target_address.clone());
            if let Some(w) = db.get_mut(&cs.target_address) {
                w.being_copied = true;
            }
            info!("🔄 Resuming copy: {} (15d PnL: ${:.0})", &cs.target_address[..10], cs.target_pnl_15d);
        }
    }

    // Shutdown signal
    let (tx, mut rx) = tokio::sync::watch::channel(false);
    let tx2 = tx.clone();
    tokio::spawn(async move {
        tokio::signal::ctrl_c().await.ok();
        info!("⏹️  Ctrl+C received, shutting down...");
        let _ = tx2.send(true);
    });

    // Fill trigger — WebSocket notifies poll loop to sync immediately
    let (fill_tx, fill_rx) = tokio::sync::watch::channel(0u64);

    // Start WebSocket fill listener
    let at_ws = active_targets.clone();
    let ft_ws = fill_tx.clone();
    let sd_ws = tx.subscribe();
    tokio::spawn(async move {
        ws::ws_fill_loop(at_ws, ft_ws, sd_ws).await;
    });

    // Start polling monitor (also checks fill trigger)
    let at = active_targets.clone();
    let op = our_positions.clone();
    let tp = target_positions.clone();
    let cp = copier.clone();
    let sd = tx.subscribe();
    let fr = fill_rx.clone();
    tokio::spawn(async move {
        copier::poll_targets_loop(at, op, tp, cp, sd, fr).await;
    });

    // Main orchestration loop
    let mut scan_count = 0u64;
    loop {
        tokio::select! {
            _ = rx.changed() => break,
            _ = tick(&client, &mut db, &mut seen, &mut copy_state, &active_targets, &mut scan_count) => {}
        }
        if *rx.borrow() { break; }
    }

    // Save state on exit
    info!("💾 Saving state before exit...");
    scanner::save_db(&db);
    copier::save_snapshot(&copy_state);
    analyzer::generate_report(&db, config::REPORT_FILE);
    info!("👋 Goodbye!");
}
