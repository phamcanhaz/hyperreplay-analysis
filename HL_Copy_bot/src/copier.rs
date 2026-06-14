use std::collections::HashMap;
use std::sync::Arc;
use ethers::signers::{LocalWallet, Signer};
use hyperliquid_rust_sdk::{BaseUrl, ExchangeClient, MarketCloseParams, MarketOrderParams};
use reqwest::Client;
use serde_json::{json, Value};
use std::sync::Mutex as StdMutex;
use tokio::sync::Mutex as TokioMutex;
use tokio::time::{sleep, Duration};
use tracing::{info, warn};

use crate::config::{
    HL_INFO, MIN_NOTIONAL_USD,
    MAX_COPY_WALLETS,
    HEALTH_CHECK_INTERVAL_SECS, RECONCILE_SECS,
    RECONCILE_COOLDOWN_SECS,
    PAPER_TRADING, PAPER_INITIAL_EQUITY, PAPER_FILE, DEFAULT_PX,
};
use crate::error::{AppError, retry, RetryConfig};
use crate::paper::PaperPortfolio;
use crate::scanner::now_ts;
use crate::types::*;

pub struct Copier {
    pub http: Client,
    pub wallet: String,
    pub exchange: Option<ExchangeClient>,
    pub has_wallet: bool,
    pub paper: StdMutex<Option<PaperPortfolio>>,
}

impl Copier {
    pub async fn new() -> Self {
        let pk = std::env::var("PRIVATE_KEY").unwrap_or_default();
        let addr = std::env::var("WALLET_ADDRESS").unwrap_or_default();
        let dry_run = std::env::var("DRY_RUN").unwrap_or_default() == "true";

        let http = Client::builder().timeout(std::time::Duration::from_secs(20)).build().unwrap();

        if pk.is_empty() || addr.is_empty() || dry_run {
            if PAPER_TRADING {
                let paper = PaperPortfolio::new(PAPER_INITIAL_EQUITY, PAPER_FILE);
                info!("[Copier] Paper mode — tracking paper portfolio (${:.0})", PAPER_INITIAL_EQUITY);
                return Self {
                    http, wallet: crate::config::PAPER_WALLET.into(), exchange: None,
                    has_wallet: false, paper: StdMutex::new(Some(paper)),
                };
            }
            info!("[Copier] Dry-run mode — no real orders");
            return Self { http, wallet: addr, exchange: None, has_wallet: false, paper: StdMutex::new(None) };
        }

        let wallet: LocalWallet = match pk.parse() {
            Ok(w) => w,
            Err(e) => {
                warn!("[Copier] Invalid private key: {e} — dry-run fallback");
                return Self { http, wallet: addr, exchange: None, has_wallet: false, paper: StdMutex::new(None) };
            }
        };

        let address = if !addr.is_empty() { addr } else { format!("{:#x}", wallet.address()) };
        let tag = if address.len() >= 10 { &address[..10] } else { &address };

        match ExchangeClient::new(None, wallet, Some(BaseUrl::Mainnet), None, None).await {
            Ok(exchange) => {
                info!("[Copier] Connected to Hyperliquid MAINNET ({tag})");
                Self { http, wallet: address, exchange: Some(exchange), has_wallet: true, paper: StdMutex::new(None) }
            }
            Err(e) => {
                warn!("[Copier] Failed to connect: {e} — dry-run fallback");
                Self { http, wallet: address, exchange: None, has_wallet: false, paper: StdMutex::new(None) }
            }
        }
    }

    async fn fetch_coin_price(&self, coin: &str) -> Result<f64, AppError> {
        for attempt in 0..2 {
            let resp = self.http.post(HL_INFO)
                .json(&json!({"type": "allMids"}))
                .send().await
                .map_err(|e| AppError::Network(format!("price fetch: {e}")))?;
            let data: Value = resp.json().await
                .map_err(|e| AppError::Network(format!("price parse: {e}")))?;
            if let Some(px_str) = data.get(coin).and_then(|v| v.as_str()) {
                if let Ok(px) = px_str.parse::<f64>() {
                    if px > 0.0 { return Ok(px); }
                }
            }
            // Retry once with delay
            if attempt == 0 {
                tokio::time::sleep(Duration::from_millis(500)).await;
            }
        }
        // Fallback: try orderbook
        let resp = self.http.post(HL_INFO)
            .json(&json!({"type": "orderbook", "coin": coin}))
            .send().await
            .map_err(|e| AppError::Network(format!("orderbook fetch: {e}")))?;
        let data: Value = resp.json().await
            .map_err(|e| AppError::Network(format!("orderbook parse: {e}")))?;
        let levels = data["levels"].as_array()
            .ok_or_else(|| AppError::Other(format!("no orderbook for {coin}")))?;
        let bid = levels.get(0).and_then(|a| a.get(0)).and_then(|l| l.get(0))
            .and_then(|v| v.as_str()).and_then(|s| s.parse::<f64>().ok()).unwrap_or(0.0);
        let ask = levels.get(1).and_then(|a| a.get(0)).and_then(|l| l.get(0))
            .and_then(|v| v.as_str()).and_then(|s| s.parse::<f64>().ok()).unwrap_or(0.0);
        if bid > 0.0 && ask > 0.0 {
            return Ok((bid + ask) / 2.0);
        }
        Err(AppError::Other(format!("no price for {coin}")))
    }

    async fn usd_to_units(&self, coin: &str, usd: f64) -> Result<f64, AppError> {
        let px = self.fetch_coin_price(coin).await?;
        Ok(usd / px)
    }

    pub async fn market_open(&self, coin: &str, is_long: bool, notional: f64) -> Result<(), AppError> {
        let side = if is_long { "LONG" } else { "SHORT" };
        if self.paper.lock().unwrap().is_some() {
            let px = match self.fetch_coin_price(coin).await {
                Ok(p) => p,
                Err(e) => {
                    warn!("[PAPER] SKIP OPEN {coin} — price fetch failed: {e}");
                    return Ok(());
                }
            };
            let size = notional / px;
            let now = now_ts();
            let mut guard = self.paper.lock().unwrap();
            if let Some(ref mut paper) = *guard {
                paper.open(coin, side, size, px, now);
            }
            return Ok(());
        }
        if !self.has_wallet {
            info!("[DRY] OPEN {} {} ${:.0}", coin, side, notional);
            return Ok(());
        }
        let exchange = self.exchange.as_ref().ok_or(AppError::Other("No exchange client".into()))?;
        let sz = self.usd_to_units(coin, notional).await?;
        info!("[ORDER] OPEN {} {} ${:.0} (~{:.4} {coin})", coin, if is_long{"LONG"}else{"SHORT"}, notional, sz);

        let params = MarketOrderParams {
            asset: coin,
            is_buy: is_long,
            sz,
            px: None,
            slippage: Some(0.05),
            cloid: None,
            wallet: None,
        };
        exchange.market_open(params).await.map_err(|e| AppError::Trading(format!("{e}")))?;
        Ok(())
    }

    pub async fn market_close(&self, coin: &str, _notional: Option<f64>) -> Result<(), AppError> {
        if self.paper.lock().unwrap().as_ref().map_or(false, |p| p.positions.contains_key(coin)) {
            let px = match self.fetch_coin_price(coin).await {
                Ok(p) => p,
                Err(e) => {
                    warn!("[PAPER] SKIP CLOSE {coin} — price fetch failed: {e}");
                    return Ok(());
                }
            };
            let mut guard = self.paper.lock().unwrap();
            if let Some(ref mut paper) = *guard {
                paper.close(coin, px);
            }
            return Ok(());
        }
        if !self.has_wallet {
            info!("[DRY] CLOSE {coin}");
            return Ok(());
        }
        let exchange = self.exchange.as_ref().ok_or(AppError::Other("No exchange client".into()))?;
        info!("[ORDER] CLOSE {coin}");

        let params = MarketCloseParams {
            asset: coin,
            sz: None,
            px: None,
            slippage: Some(0.05),
            cloid: None,
            wallet: None,
        };
        exchange.market_close(params).await.map_err(|e| AppError::Trading(format!("{e}")))?;
        Ok(())
    }
}

// ─── Price ───

async fn fetch_all_mids(http: &Client) -> HashMap<String, f64> {
    for attempt in 0..2 {
        let prices = fetch_all_mids_once(http).await;
        if !prices.is_empty() || attempt == 1 {
            return prices;
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
    }
    HashMap::new()
}

async fn fetch_all_mids_once(http: &Client) -> HashMap<String, f64> {
    let resp = match http.post(HL_INFO)
        .json(&json!({"type": "allMids"}))
        .send().await
    {
        Ok(r) => r,
        Err(_) => return HashMap::new(),
    };
    let data: Value = match resp.json().await {
        Ok(d) => d,
        Err(_) => return HashMap::new(),
    };
    let mut prices = HashMap::new();
    if let Some(obj) = data.as_object() {
        for (coin, v) in obj {
            if let Some(px) = v.as_str().and_then(|s| s.parse::<f64>().ok()) {
                if px > 0.0 {
                    prices.insert(coin.clone(), px);
                }
            }
        }
    }
    prices
}

// ─── Equity ───

// ─── Positions ───

async fn fetch_target_positions(client: &Client, addr: &str) -> Option<HashMap<String, TargetPosition>> {
    let payload = json!({"type": "clearinghouseState", "user": addr});
    let data: Value = client.post(HL_INFO).json(&payload).send().await.ok()?.json().await.ok()?;

    let positions = data["assetPositions"].as_array()?;
    let mut result = HashMap::new();

    for p in positions {
        let pos = &p["position"];
        let coin = pos["coin"].as_str()?;
        let szi: f64 = pos["szi"].as_str()?.parse().ok()?;
        if szi.abs() < 0.0001 { continue; }
        let entry: f64 = pos["entryPx"].as_str()?.parse().ok()?;
        result.insert(coin.to_string(), TargetPosition {
            coin: coin.to_string(),
            side: if szi > 0.0 { "LONG".into() } else { "SHORT".into() },
            size: szi.abs(),
            entry_px: entry,
        });
    }

    Some(result)
}

async fn fetch_our_positions(client: &Client, addr: &str) -> HashMap<String, OurPosition> {
    let mut result = HashMap::new();
    let payload = json!({"type": "clearinghouseState", "user": addr});
    if let Ok(data) = client.post(HL_INFO).json(&payload).send().await {
        if let Ok(data) = data.json::<Value>().await {
            if let Some(positions) = data["assetPositions"].as_array() {
                for p in positions {
                    let pos = &p["position"];
                    if let (Some(coin), Some(szi_str)) = (pos["coin"].as_str(), pos["szi"].as_str()) {
                        if let Ok(szi) = szi_str.parse::<f64>() {
                            if szi.abs() < 0.0001 { continue; }
                            let val: f64 = pos["positionValue"].as_str().unwrap_or("0").parse().unwrap_or(0.0);
                            result.insert(coin.to_string(), OurPosition {
                                side: if szi > 0.0 { "LONG".into() } else { "SHORT".into() },
                                size: szi.abs(),
                                notional: val,
                            });
                        }
                    }
                }
            }
        }
    }
    result
}

// ─── Sync (equity-ratio sizing) ───

pub async fn sync_positions(
    copier: &Copier,
    target_positions: &Arc<TokioMutex<HashMap<String, HashMap<String, TargetPosition>>>>,
    our_positions: &Arc<TokioMutex<HashMap<String, OurPosition>>>,
    prices: &HashMap<String, f64>,
    _our_equity: f64,
    last_action: &mut HashMap<String, u64>,
) {
    let tp = target_positions.lock().await;
    let mut op = our_positions.lock().await;

    let slot_cap = PAPER_INITIAL_EQUITY / MAX_COPY_WALLETS.max(1) as f64;

    // Each target gets one independent slot with fixed capital
    // No net aggregation — each slot copies its target independently
    let mut desired: HashMap<String, (String, f64)> = HashMap::new();

    for positions in tp.values() {
        if positions.is_empty() { continue; }

        // Calculate total target notional
        let mut total = 0.0;
        let mut slot_positions: Vec<(String, String, f64)> = Vec::new();

        for pos in positions.values() {
            let px = prices.get(&pos.coin).copied().unwrap_or(pos.entry_px);
            let n = pos.size * px;
            if n < 0.01 { continue; }
            total += n;
            slot_positions.push((pos.coin.clone(), pos.side.clone(), n));
        }

        if slot_positions.is_empty() || total < 0.01 { continue; }

        // Distribute slot_cap proportionally across target's positions
        for (coin, side, notional) in &slot_positions {
            let n = slot_cap * (notional / total);
            if n < 0.01 { continue; }
            let entry = desired.entry(coin.clone()).or_insert((side.clone(), 0.0));
            if entry.0 != *side {
                if n > entry.1 { entry.0 = side.clone(); entry.1 = n - entry.1; }
                else { entry.1 -= n; }
            } else {
                entry.1 += n;
            }
        }
    }

    info!("[RECONCILE] desired: {} coins across {} targets", desired.len(), tp.len());

    let to_close: Vec<String> = op.keys()
        .filter(|coin| !desired.contains_key(*coin))
        .cloned()
        .collect();

    let now = now_ts();
    for coin in &to_close {
        info!("[RECONCILE] CLOSE {} — no target has position (notional=${:.0})", coin, op.get(coin.as_str()).map(|p| p.notional).unwrap_or(0.0));
        let _ = copier.market_close(coin, None).await;
        op.remove(coin);
        last_action.insert(coin.clone(), now);
    }
    if !to_close.is_empty() {
        info!("[RECONCILE] closed {} orphaned positions", to_close.len());
    }

    let regime = crate::scanner::read_regime();
    let cooldown = match regime.as_str() {
        "crisis" => 60u64,
        "volatile" => 120u64,
        _ => RECONCILE_COOLDOWN_SECS,
    };

    let mut acted = 0u32;
    let mut skipped = 0u32;
    let mut in_range = 0u32;

    for (coin, (side, desired_notional)) in &desired {
        let is_cooling = last_action.get(coin.as_str()).map(|t| now - t < cooldown).unwrap_or(false);

        if let Some(our) = op.get(coin.as_str()) {
            if our.side != *side {
                // Hysteresis: skip flip if desired position on the new side is too small
                if *desired_notional < slot_cap * 0.15 {
                    info!("[RECONCILE] SKIP FLIP {} (hysteresis: desired=${:.0} < ${:.0})", coin, desired_notional, slot_cap * 0.15);
                    skipped += 1;
                    continue;
                }
                if is_cooling {
                    info!("[RECONCILE] SKIP FLIP {} (cooldown {}s, ${:.0})", coin, now - last_action.get(coin.as_str()).copied().unwrap_or(0), desired_notional);
                    skipped += 1;
                    continue;
                }
                info!("[RECONCILE] FLIP {} from {} to {} (${:.0})", coin, our.side, side, desired_notional);
                acted += 1;
                let _ = copier.market_close(coin, None).await;
                if *desired_notional >= MIN_NOTIONAL_USD {
                    let _ = copier.market_open(coin, side == "LONG", *desired_notional).await;
                }
                last_action.insert(coin.clone(), now);
            } else if (our.notional - desired_notional).abs() > desired_notional * 0.3 && *desired_notional >= MIN_NOTIONAL_USD {
                if is_cooling {
                    info!("[RECONCILE] SKIP RESIZE {} (cooldown {}s, our=${:.0} want=${:.0})", coin, now - last_action.get(coin.as_str()).copied().unwrap_or(0), our.notional, desired_notional);
                    skipped += 1;
                    continue;
                }
                info!("[RECONCILE] RESIZE {} from ${:.0} to ${:.0} (Δ={:.1}%)", coin, our.notional, desired_notional,
                    (our.notional - desired_notional).abs() / our.notional.max(1.0) * 100.0);
                acted += 1;
                let _ = copier.market_close(coin, None).await;
                let _ = copier.market_open(coin, side == "LONG", *desired_notional).await;
                last_action.insert(coin.clone(), now);
            } else if *desired_notional < MIN_NOTIONAL_USD && our.notional >= MIN_NOTIONAL_USD {
                info!("[RECONCILE] CLOSE {} (too small ${:.0})", coin, desired_notional);
                acted += 1;
                let _ = copier.market_close(coin, None).await;
                last_action.insert(coin.clone(), now);
            } else {
                in_range += 1;
            }
        } else {
            if *desired_notional >= MIN_NOTIONAL_USD {
                info!("[RECONCILE] OPEN {} {} ${:.0} (slot_cap=${:.0})", coin, side, desired_notional, slot_cap);
                acted += 1;
                let _ = copier.market_open(coin, side == "LONG", *desired_notional).await;
                last_action.insert(coin.clone(), now);
            }
        }
    }

    info!("[RECONCILE] summary: {} acted, {} skipped (cooldown), {} in-range (no change) — regime={}, cooldown={}s",
        acted, skipped, in_range, regime, cooldown);

    drop(op);
    drop(tp);
}

// ─── Health check ───

pub async fn health_check_positions(
    http: &Client,
    our_addr: &str,
    target_addrs: &[String],
) {
    let mut any_issue = false;
    let our = fetch_our_positions(http, our_addr).await;

    // Collect all target positions across all targets
    let mut all_target_coins: HashMap<String, String> = HashMap::new();
    for addr in target_addrs {
        if let Some(their) = fetch_target_positions(http, addr).await {
            for (coin, tpos) in &their {
                let entry = all_target_coins.entry(coin.clone()).or_insert(tpos.side.clone());
                if *entry != tpos.side {
                    // Mixed sides across targets — expected in aggregation
                }
            }
        }
    }

    // Check orphans: we have a position no target has
    for (coin, opos) in &our {
        if !all_target_coins.contains_key(coin) && opos.size > 0.001 {
            info!("[HEALTH] ORPHAN {}: we hold {:.4} {} but no target has it", coin, opos.size, opos.side);
            any_issue = true;
        }
    }

    if !any_issue {
        info!("[HEALTH] OK — {} positions, {} targets", our.len(), target_addrs.len());
    }
}

// ─── Main loop ───

pub async fn poll_targets_loop(
    targets: Arc<TokioMutex<Vec<String>>>,
    our_positions: Arc<TokioMutex<HashMap<String, OurPosition>>>,
    target_positions: Arc<TokioMutex<HashMap<String, HashMap<String, TargetPosition>>>>,
    copier: Arc<Copier>,
    mut shutdown: tokio::sync::watch::Receiver<bool>,
    mut fill_trigger: tokio::sync::watch::Receiver<u64>,
) {
    let mut health_ticks = 0u64;
    let mut last_fill_count = 0u64;
    let mut last_action: HashMap<String, u64> = HashMap::new();
    let mut first_poll = true;

    // BTC crisis detection ring buffer (5min window = 5 x 60s polls)
    let mut btc_prices: Vec<f64> = Vec::with_capacity(6);
    let mut crisis_override = false;

    loop {
        // Check if WebSocket notified new fills
        let fill_pending = *fill_trigger.borrow() > last_fill_count;
        if fill_pending {
            last_fill_count = *fill_trigger.borrow();
        }

        tokio::select! {
            _ = shutdown.changed() => {
                info!("[poll] shutting down");
                break;
            }
            _ = poll_once(&targets, &target_positions, &our_positions, &copier, &mut last_action) => {}
            // If a fill arrived, wake up immediately
            _ = fill_trigger.changed() => {
                last_fill_count = *fill_trigger.borrow();
                // Don't sleep — run poll_once on next loop iteration
            }
        }

        // After first poll, pre-populate last_action to avoid immediate flips on restart
        if first_poll {
            let op = our_positions.lock().await;
            let now = now_ts();
            for coin in op.keys() {
                last_action.entry(coin.clone()).or_insert(now);
            }
            drop(op);
            first_poll = false;
        }

        if fill_pending {
            info!("[poll] fill-triggered sync");
            // Run immediately — select! already ran poll_once or is about to
        }

        // ─── BTC realtime crisis detection ───
        if let Ok(btc_px) = copier.fetch_coin_price("BTC").await {
            btc_prices.push(btc_px);
            if btc_prices.len() > 6 { btc_prices.remove(0); }
            if btc_prices.len() >= 2 {
                let oldest = btc_prices[0];
                let current = btc_prices[btc_prices.len() - 1];
                let new_crisis = current < oldest * 0.97;
                if new_crisis && !crisis_override {
                    crisis_override = true;
                    warn!("[CRISIS] BTC dropped {:.1}% in ~5min ({:.0}→{:.0}) — overriding regime to CRISIS", 
                        (oldest - current) / oldest * 100.0, oldest, current);
                    let regime_path = crate::config::REGIME_FILE;
                    if let Ok(s) = serde_json::to_string(&serde_json::json!({
                        "regime": "crisis",
                        "updated_at": now_ts(),
                        "source": "btc_realtime"
                    })) {
                        let tmp = format!("{}.tmp", regime_path);
                        let _ = std::fs::write(&tmp, &s);
                        let _ = std::fs::rename(&tmp, &regime_path);
                    }
                } else if !new_crisis && crisis_override {
                    if current >= oldest * 0.985 {
                        crisis_override = false;
                        info!("[CRISIS] BTC recovered ({:.0}→{:.0}) — clearing crisis override", oldest, current);
                    }
                }
            }
        }

        health_ticks += 1;
        if health_ticks * RECONCILE_SECS >= HEALTH_CHECK_INTERVAL_SECS && copier.has_wallet {
            let addrs = targets.lock().await.clone();
            if !addrs.is_empty() {
                health_check_positions(&copier.http, &copier.wallet, &addrs).await;
            }
            health_ticks = 0;
        }
    }
}

async fn poll_once(
    targets: &Arc<TokioMutex<Vec<String>>>,
    target_positions: &Arc<TokioMutex<HashMap<String, HashMap<String, TargetPosition>>>>,
    our_positions: &Arc<TokioMutex<HashMap<String, OurPosition>>>,
    copier: &Arc<Copier>,
    last_action: &mut HashMap<String, u64>,
) {
    let poll_start = now_ts();
    let addrs = targets.lock().await.clone();
    if addrs.is_empty() {
        sleep(Duration::from_secs(5)).await;
        return;
    }

    let prices = fetch_all_mids(&copier.http).await;
    info!("[poll] start — {} targets, {} prices loaded", addrs.len(), prices.len());

    // Fetch our positions + equity
    let mut our_eq = 0.0_f64;
    let paper_positions = {
        let guard = copier.paper.lock().unwrap();
        guard.as_ref().map(|p| {
            let pos = p.unserialized_positions(&prices, DEFAULT_PX);
            let eq = p.get_free_equity(&prices, DEFAULT_PX);
            (pos, eq)
        })
    };
    if let Some((pos, eq)) = paper_positions {
        // Auto-reset paper portfolio if bankrupt (guard dropped before await)
        if eq < 100.0 {
            warn!("[PAPER] BANKRUPT — equity=${:.2}, resetting to initial state", eq);
            {
                let mut guard = copier.paper.lock().unwrap();
                if let Some(ref mut paper) = *guard {
                    paper.reset();
                }
            }
            // Re-fetch after reset (lock dropped before this block)
            let (pos2, eq2) = {
                let guard = copier.paper.lock().unwrap();
                guard.as_ref().map(|p| {
                    (p.unserialized_positions(&prices, DEFAULT_PX), p.get_free_equity(&prices, DEFAULT_PX))
                }).unwrap_or((HashMap::new(), 0.0))
            };
            *our_positions.lock().await = pos2;
            our_eq = eq2;
        } else {
            let mut op = our_positions.lock().await;
            *op = pos;
            our_eq = eq;
            drop(op);
        }
    } else if copier.has_wallet {
        let mut op = our_positions.lock().await;
        let retry_cfg = RetryConfig {
            max_retries: 3,
            initial_delay: Duration::from_secs(1),
            max_delay: Duration::from_secs(10),
            backoff_multiplier: 2.0,
        };
        match retry(|| fetch_our_positions_with_retry(&copier.http, &copier.wallet), retry_cfg).await {
            Ok(r) => { *op = r.0; our_eq = r.1; }
            Err(e) => warn!("[poll] failed to fetch our positions: {e}"),
        }
        drop(op);
    }

    let mut tp = target_positions.lock().await;
    // Remove stale entries (evicted wallets no longer active)
    tp.retain(|addr, _| addrs.contains(addr));
    let mut fetch_ok = 0u32;
    let mut fetch_fail = 0u32;
    for addr in &addrs {
        if let Some(positions) = fetch_target_positions(&copier.http, addr).await {
            tp.insert(addr.clone(), positions);
            fetch_ok += 1;
        } else {
            fetch_fail += 1;
            warn!("[poll] fetch FAILED for target {}", &addr[..10]);
        }
        sleep(Duration::from_millis(200)).await;
    }
    drop(tp);
    if fetch_fail > 0 {
        info!("[poll] target fetch: {}/{} OK, {} FAILED", fetch_ok, addrs.len(), fetch_fail);
    }

    sync_positions(copier, target_positions, our_positions, &prices, our_eq, last_action).await;

    // Paper portfolio report
    {
        let guard = copier.paper.lock().unwrap();
        if let Some(ref paper) = *guard {
            let eq = paper.get_equity(&prices, DEFAULT_PX);
            let dur = now_ts() - poll_start;
            info!("\n{}", paper.report(&prices, DEFAULT_PX));
            info!("[poll] done — {}s, equity=${:.2}", dur, eq);
            paper.save();
        }
    }

    sleep(Duration::from_secs(RECONCILE_SECS)).await;
}

async fn fetch_our_positions_with_retry(http: &Client, addr: &str) -> Result<(HashMap<String, OurPosition>, f64), AppError> {
    let payload = json!({"type": "clearinghouseState", "user": addr});
    let resp = http.post(HL_INFO).json(&payload).send().await
        .map_err(|e| AppError::Network(format!("fetch our pos: {e}")))?;
    let data: Value = resp.json().await
        .map_err(|e| AppError::Network(format!("parse our pos: {e}")))?;

    let equity = data["marginSummary"]["accountValue"].as_str()
        .and_then(|s| s.parse::<f64>().ok())
        .unwrap_or(0.0);

    let mut positions = HashMap::new();
    if let Some(arr) = data["assetPositions"].as_array() {
        for p in arr {
            let pos = &p["position"];
            if let (Some(coin), Some(szi_str)) = (pos["coin"].as_str(), pos["szi"].as_str()) {
                if let Ok(szi) = szi_str.parse::<f64>() {
                    if szi.abs() < 0.0001 { continue; }
                    let val: f64 = pos["positionValue"].as_str().unwrap_or("0").parse().unwrap_or(0.0);
                    positions.insert(coin.to_string(), OurPosition {
                        side: if szi > 0.0 { "LONG".into() } else { "SHORT".into() },
                        size: szi.abs(),
                        notional: val,
                    });
                }
            }
        }
    }

    Ok((positions, equity))
}

pub fn load_snapshot() -> Vec<CopyState> {
    std::fs::read_to_string(crate::config::SNAPSHOT_FILE).ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

pub fn save_snapshot(state: &[CopyState]) {
    if let Ok(s) = serde_json::to_string(state) {
        let path = crate::config::SNAPSHOT_FILE;
        let tmp = format!("{}.tmp", path);
        let _ = std::fs::write(&tmp, &s);
        let _ = std::fs::rename(&tmp, path);
    }
}
