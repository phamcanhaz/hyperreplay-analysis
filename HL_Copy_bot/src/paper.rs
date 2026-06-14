use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tracing::info;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaperPosition {
    pub coin: String,
    pub side: String,
    pub size: f64,
    pub entry_px: f64,
    pub opened_at: u64,
    pub realized_pnl: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaperPortfolio {
    pub initial_equity: f64,
    pub cash: f64,
    pub positions: HashMap<String, PaperPosition>,
    pub total_realized_pnl: f64,
    #[serde(skip)]
    pub file_path: String,
}

impl PaperPortfolio {
    pub fn new(initial_equity: f64, file_path: &str) -> Self {
        Self::load(file_path).unwrap_or(Self {
            initial_equity,
            cash: initial_equity,
            positions: HashMap::new(),
            total_realized_pnl: 0.0,
            file_path: file_path.to_string(),
        })
    }

    pub fn open(&mut self, coin: &str, side: &str, size: f64, entry_px: f64, now: u64) {
        let notional = size * entry_px;
        self.cash -= notional;
        self.positions.insert(
            coin.to_string(),
            PaperPosition {
                coin: coin.to_string(),
                side: side.to_string(),
                size,
                entry_px,
                opened_at: now,
                realized_pnl: 0.0,
            },
        );
        self.save();
        info!(
            "[PAPER] OPEN {} {} sz={:.4} @${:.2} notional=${:.0} cash=${:.2}",
            coin, side, size, entry_px, notional, self.cash
        );
    }

    pub fn close(&mut self, coin: &str, close_px: f64) -> Option<f64> {
        let pos = self.positions.remove(coin)?;
        let side_mult = if pos.side == "LONG" { 1.0 } else { -1.0 };
        let pnl = (close_px - pos.entry_px) * side_mult * pos.size;
        let locked = pos.size * pos.entry_px;
        self.cash += locked + pnl;
        self.total_realized_pnl += pnl;
        info!(
            "[PAPER] CLOSE {} {} sz={:.4} entry=${:.2} exit=${:.2} PnL=${:.2} cash=${:.2}",
            coin, pos.side, pos.size, pos.entry_px, close_px, pnl, self.cash
        );
        self.save();
        Some(pnl)
    }

    pub fn get_equity(&self, prices: &HashMap<String, f64>, _default_px: f64) -> f64 {
        let mut total = self.cash;
        for pos in self.positions.values() {
            let px = prices.get(&pos.coin).copied().unwrap_or(pos.entry_px);
            total += pos.size * pos.entry_px; // locked margin
            let side_mult = if pos.side == "LONG" { 1.0 } else { -1.0 };
            total += (px - pos.entry_px) * side_mult * pos.size; // unrealized PnL
        }
        total
    }

    pub fn locked_notional(&self) -> f64 {
        let mut total = 0.0;
        for pos in self.positions.values() {
            let px = pos.entry_px;
            total += pos.size * px;
        }
        total
    }

    pub fn get_free_equity(&self, prices: &HashMap<String, f64>, default_px: f64) -> f64 {
        self.get_equity(prices, default_px) - self.locked_notional()
    }

    pub fn unserialized_positions(
        &self,
        prices: &HashMap<String, f64>,
        _default_px: f64,
    ) -> HashMap<String, super::types::OurPosition> {
        let mut result = HashMap::new();
        for pos in self.positions.values() {
            let px = prices.get(&pos.coin).copied().unwrap_or(pos.entry_px);
            result.insert(
                pos.coin.clone(),
                super::types::OurPosition {
                    side: pos.side.clone(),
                    size: pos.size,
                    notional: pos.size * px,
                },
            );
        }
        result
    }

    pub fn save(&self) {
        if let Ok(s) = serde_json::to_string_pretty(self) {
            let tmp = format!("{}.tmp", self.file_path);
            let _ = std::fs::write(&tmp, &s);
            let _ = std::fs::rename(&tmp, &self.file_path);
        }
    }

    fn load(path: &str) -> Option<Self> {
        let content = std::fs::read_to_string(path).ok()?;
        let mut pf: Self = serde_json::from_str(&content).ok()?;
        pf.file_path = path.to_string();
        Some(pf)
    }

    pub fn reset(&mut self) {
        self.cash = self.initial_equity;
        self.positions.clear();
        self.total_realized_pnl = 0.0;
        self.save();
        info!(
            "[PAPER] RESET — portfolio restored to ${:.0} initial equity",
            self.initial_equity
        );
    }

    pub fn report(&self, prices: &HashMap<String, f64>, default_px: f64) -> String {
        let eq = self.get_equity(prices, default_px);
        let pnl = eq - self.initial_equity;
        let ret = if self.initial_equity > 0.0 {
            (pnl / self.initial_equity) * 100.0
        } else {
            0.0
        };
        let mut lines = vec![
            format!("📊 PAPER PORTFOLIO"),
            format!("  Initial equity: ${:.2}", self.initial_equity),
            format!("  Current equity: ${:.2}", eq),
            format!("  Total PnL: ${:.2} ({:+.2}%)", pnl, ret),
            format!(
                "  Free collateral: ${:.2}",
                self.get_free_equity(prices, default_px)
            ),
            format!("  Locked notional: ${:.2}", self.locked_notional()),
            format!("  Positions: {}", self.positions.len()),
        ];
        for pos in self.positions.values() {
            let px = prices.get(&pos.coin).copied().unwrap_or(pos.entry_px);
            let side_mult = if pos.side == "LONG" { 1.0 } else { -1.0 };
            let u_pnl = (px - pos.entry_px) * side_mult * pos.size;
            lines.push(format!(
                "    {} {} sz={:.4} entry=${:.2} mtx=${:.2} uPnL=${:.2}",
                pos.coin, pos.side, pos.size, pos.entry_px, px, u_pnl
            ));
        }
        lines.join("\n")
    }
}
