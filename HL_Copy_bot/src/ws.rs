use std::sync::Arc;
use std::collections::HashSet;
use futures_util::SinkExt;
use futures_util::StreamExt;
use serde_json::Value;
use tokio::sync::Mutex;
use tokio::time::{sleep, Duration};
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::{info, warn, error, debug};

const WS_URL: &str = "wss://api.hyperliquid.xyz/ws";

pub async fn ws_fill_loop(
    targets: Arc<Mutex<Vec<String>>>,
    fill_trigger: tokio::sync::watch::Sender<u64>,
    mut shutdown: tokio::sync::watch::Receiver<bool>,
) {
    let mut backoff = 1u64;
    let mut reconnect_count = 0u64;

    loop {
        tokio::select! {
            _ = shutdown.changed() => {
                info!("[ws] shutting down");
                break;
            }
            reason = subscribe_and_stream(&targets, &fill_trigger) => {
                let reason = reason.unwrap_or("unknown");
                if reason == "permanent" {
                    info!("[ws] permanent stop (subscription rejected)");
                    break;
                }
                if reason != "connect_failed" && reason != "no_subscriptions" {
                    backoff = 1;
                }
                reconnect_count += 1;
                warn!("[ws] disconnected (reason={}, reconnect_count={}), reconnect in {backoff}s...", reason, reconnect_count);
                sleep(Duration::from_secs(backoff)).await;
                backoff = (backoff * 2).min(30);
            }
        }
    }
}

async fn subscribe_and_stream(
    targets: &Arc<Mutex<Vec<String>>>,
    fill_trigger: &tokio::sync::watch::Sender<u64>,
) -> Option<&'static str> {
    let (ws_stream, _) = match connect_async(WS_URL).await {
        Ok(c) => c,
        Err(e) => {
            error!("[ws] connect failed: {e}");
            return Some("connect_failed");
        }
    };

    info!("[ws] connected");

    let (mut write, mut read) = ws_stream.split();

    let addrs = targets.lock().await.clone();
    let mut subscribed: HashSet<String> = HashSet::new();
    for addr in &addrs {
        let sub = serde_json::json!({
            "method": "subscribe",
            "subscription": { "type": "userFills", "user": addr }
        });
        if write.send(Message::Text(sub.to_string())).await.is_err() {
            return Some("write_failed");
        }
        subscribed.insert(addr.clone());
    }

    // Check first response for subscription acknowledgment
    let mut subs_ok = 0;
    let mut subs_fail = 0;

    for _ in 0..addrs.len() {
        if let Some(msg) = read.next().await {
            match msg {
                Ok(Message::Text(text)) => {
                    if let Ok(data) = serde_json::from_str::<Value>(&text) {
                        if data.get("error").is_some() {
                            subs_fail += 1;
                            warn!("[ws] subscription rejected: {}", data["error"]);
                        } else {
                            subs_ok += 1;
                        }
                    }
                }
                Ok(Message::Close(_)) => return Some("server_closed"),
                Err(e) => {
                    error!("[ws] read error: {e}");
                    return Some("read_error");
                }
                _ => {}
            }
        }
    }

    if subs_fail > 0 && subs_ok == 0 {
        warn!("[ws] all subscriptions rejected (auth required?), disabling WS");
        return Some("permanent");
    }

    if subs_ok > 0 {
        let total = subs_ok + subs_fail;
        info!("[ws] {subs_ok}/{total} subscriptions active");
    } else {
        return Some("no_subscriptions");
    }

    info!("[ws] listening for fills...");
    let mut counter = 0u64;
    let mut last_msg_ts = std::time::Instant::now();
    let mut ping_interval = tokio::time::interval(Duration::from_secs(30));
    let mut resub_interval = tokio::time::interval(Duration::from_secs(60));
    let mut health_interval = tokio::time::interval(Duration::from_secs(120));

    loop {
        tokio::select! {
            biased;
            msg = read.next() => {
                last_msg_ts = std::time::Instant::now();
                let msg = match msg {
                    Some(m) => m,
                    None => break,
                };
                match msg {
                    Ok(Message::Text(text)) => {
                        debug!("[ws] RAW: {}", &text[..text.len().min(500)]);
                        if let Ok(data) = serde_json::from_str::<Value>(&text) {
                            if data["channel"] == "userFills" {
                                let fills_arr = data["data"]["fills"].as_array()
                                    .or_else(|| data["data"].as_array());
                                let count = fills_arr.map(|a| a.len()).unwrap_or(0);
                                let event_user = data["data"]["user"].as_str().unwrap_or("?").to_string();
                                if count > 0 {
                                    counter += count as u64;
                                    let _ = fill_trigger.send(counter);
                                    for fill in fills_arr.unwrap_or(&vec![]) {
                                        let coin = fill["coin"].as_str().unwrap_or("?");
                                        let dir = fill["dir"].as_str().unwrap_or("?");
                                        let sz = fill["sz"].as_str().unwrap_or("?");
                                        let px = fill["px"].as_str().unwrap_or("?");
                                        let is_snap = data["data"]["isSnapshot"].as_bool().unwrap_or(false);
                                        let user_tag = if event_user.len() >= 10 { &event_user[..10] } else { &event_user };
                                        if is_snap {
                                            debug!("[ws] snapshot fill {} {} {} @{} user={}", coin, dir, sz, px, user_tag);
                                        } else {
                                            info!("[ws] FILL {} {} {} @{} user={}", coin, dir, sz, px, user_tag);
                                        }
                                    }
                                } else {
                                    let is_snap = data["data"]["isSnapshot"].as_bool().unwrap_or(false);
                                    if is_snap {
                                        debug!("[ws] userFills snapshot (0 fills)");
                                    } else {
                                        debug!("[ws] userFills heartbeat");
                                    }
                                }
                            } else if data["channel"] == "subscriptionResponse" {
                                debug!("[ws] sub response: {}", &text[..text.len().min(300)]);
                            } else if data.get("channel").is_none() {
                                if data.get("error").is_some() {
                                    warn!("[ws] error: {}", data["error"]);
                                } else {
                                    info!("[ws] untyped msg: {}", &text[..text.len().min(300)]);
                                }
                            } else {
                                debug!("[ws] channel {}: {}", data["channel"], &text[..text.len().min(200)]);
                            }
                        } else {
                            warn!("[ws] unparseable: {}", &text[..text.len().min(200)]);
                        }
                    }
                    Ok(Message::Ping(_)) => {
                        debug!("[ws] ping received");
                    }
                    Ok(Message::Close(_)) => {
                        info!("[ws] server closed");
                        break;
                    }
                    Ok(Message::Pong(_)) => {}
                    Err(e) => {
                        error!("[ws] error: {e}");
                        break;
                    }
                    _ => {
                        debug!("[ws] other msg type");
                    }
                }
            }
            _ = ping_interval.tick() => {
                if write.send(Message::Text(r#"{"method":"ping"}"#.into())).await.is_err() {
                    warn!("[ws] ping failed");
                    break;
                }
            }
            _ = resub_interval.tick() => {
                let current = targets.lock().await.clone();
                for addr in &current {
                    if subscribed.contains(addr) { continue; }
                    info!("[ws] subscribing to new target {}", &addr[..10]);
                    let sub = serde_json::json!({
                        "method": "subscribe",
                        "subscription": { "type": "userFills", "user": addr }
                    });
                    if write.send(Message::Text(sub.to_string())).await.is_err() {
                        warn!("[ws] re-subscribe write failed");
                        break;
                    }
                    subscribed.insert(addr.clone());
                }
            }
            _ = health_interval.tick() => {
                let elapsed = last_msg_ts.elapsed().as_secs();
                if elapsed > 60 {
                    warn!("[ws] HEALTH: {}s since last msg (no fill data for >1min)", elapsed);
                } else {
                    debug!("[ws] HEALTH: OK — last msg {}s ago", elapsed);
                }
            }
        }
    }

    None
}
