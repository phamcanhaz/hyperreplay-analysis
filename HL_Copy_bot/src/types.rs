pub type WalletDb = std::collections::HashMap<String, WalletInfo>;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct WalletInfo {
    pub address: String,
    pub first_seen: u64,
    pub last_updated: u64,
    pub last_trade_ts: u64,
    pub total_trades_all: u64,
    pub total_pnl_all: f64,
    pub trades_15d: u64,
    pub pnl_15d: f64,
    pub wr_15d: f64,
    pub pf_15d: f64,
    pub dd_15d: f64,
    pub bias_15d: String,
    pub long_pct_15d: f64,
    pub avg_hold_secs_15d: f64,
    pub copy_worthy: bool,
    pub being_copied: bool,
    pub score: f64,
    #[serde(default)]
    pub validated_30d: bool,
    #[serde(default)]
    pub consistent_wins_30d: u8,
    #[serde(default)]
    pub strategy_15d: String,
    #[serde(default)]
    pub copyability: f64,
    #[serde(default)]
    pub active_days_15d: u64,
    #[serde(default)]
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct CopyState {
    pub target_address: String,
    pub target_pnl_15d: f64,
    pub started_at: u64,
    pub active: bool,
}

#[derive(Debug, Clone)]
pub struct TargetPosition {
    pub coin: String,
    pub side: String,
    pub size: f64,
    pub entry_px: f64,
}

#[derive(Debug, Clone)]
pub struct OurPosition {
    pub side: String,
    pub size: f64,
    pub notional: f64,
}
