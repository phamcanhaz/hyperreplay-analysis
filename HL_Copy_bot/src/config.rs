pub const HL_INFO: &str = "https://api.hyperliquid.xyz/info";

pub const COPY_MGMT_EVERY_N_SCANS: u64 = 5;
pub const RECONCILE_SECS: u64 = 60;
pub const MAIN_TICK_SECS: u64 = 15;

pub const MAX_COPY_WALLETS: usize = 5;
pub const MAX_PER_STRATEGY: usize = 3;
pub const MIN_NOTIONAL_USD: f64 = 10.0;
pub const HEALTH_CHECK_INTERVAL_SECS: u64 = 300;
pub const RECONCILE_COOLDOWN_SECS: u64 = 300;

pub const SNAPSHOT_FILE: &str = "/home/bot/hl_copy_bot/copy_wallets.json";
pub const DB_FILE: &str = "/home/bot/hl_copy_bot/seen_wallets.json";
pub const REPORT_FILE: &str = "/home/bot/hl_copy_bot/analysis_report.txt";
pub const VALIDATION_FILE: &str = "/home/bot/hl_copy_bot/validation_results.json";
pub const REGIME_FILE: &str = "/home/bot/hl_copy_bot/regime.json";

// Paper trading
pub const PAPER_TRADING: bool = true;
pub const PAPER_INITIAL_EQUITY: f64 = 10000.0;
pub const PAPER_WALLET: &str = "0xpaper000000000000000000000000000000000001";
pub const PAPER_FILE: &str = "/home/bot/hl_copy_bot/paper_portfolio.json";
pub const DEFAULT_PX: f64 = 50000.0;
