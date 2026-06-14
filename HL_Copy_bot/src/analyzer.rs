use crate::scanner::now_ts;
use crate::types::*;

pub fn generate_report(db: &WalletDb, path: &str) {
    let mut sorted: Vec<&WalletInfo> = db.values().collect();
    sorted.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    let now = now_ts();
    let (sec, min, hour, day, mon, year) = {
        let s = now % 86400;
        let h = s / 3600;
        let m = (s % 3600) / 60;
        let sec = s % 60;
        let d = now / 86400;
        let y = 1970 + (d as f64 / 365.25) as u64;
        let mo = 1 + ((d as f64 / 30.44) as u64 % 12);
        (sec, m, h, d, mo, y)
    };

    let header = format!(
        "╔══════════════════════════════════════════════════════════════════════════════════════════════════════╗\n\
         ║  HL COPY BOT — Analysis Report @ {:04}-{:02}-{:02} {:02}:{:02}:{:02} UTC{:>33}║\n\
         ╚══════════════════════════════════════════════════════════════════════════════════════════════════════╝",
        year, mon, day, hour, min, sec, ""
    );

    let mut lines = Vec::new();
    lines.push(String::new());
    lines.push(header);
    lines.push(String::new());

    let total = sorted.len();
    let analyzed = sorted.iter().filter(|w| w.last_updated != 0).count();
    let worthy = sorted.iter().filter(|w| w.copy_worthy).count();
    let copied = sorted.iter().filter(|w| w.being_copied).count();

    lines.push(format!(
        "  Total wallets: {}  |  Analyzed: {}  |  Copy-worthy: {}  |  Being copied: {}",
        total, analyzed, worthy, copied
    ));
    lines.push(String::new());

    // ─── Copy-worthy wallets ───
    let worthy_wallets: Vec<&&WalletInfo> = sorted.iter().filter(|w| w.copy_worthy).collect();
    if !worthy_wallets.is_empty() {
        lines.push("  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐".into());
        lines.push("  │  ★ COPY-WORTHY WALLETS                                                                                     │".into());
        lines.push("  ├──────────────────────────────────┬───────────┬────────┬───────┬───────┬──────────────┬────────┬─────────────┬──────────┤".into());
        lines.push("  │  Address                         │  15d PnL  │  WR%   │  PF   │  DD%  │  Bias        │ Trades │  Score      │ Strategy │".into());
        lines.push("  ├──────────────────────────────────┼───────────┼────────┼───────┼───────┼──────────────┼────────┼─────────────┼──────────┤".into());
        for w in worthy_wallets {
            let strategy_display = if w.strategy_15d.is_empty() {
                "N/A"
            } else {
                &w.strategy_15d
            };
            lines.push(format!(
                "  │  {} │ ${:>8.0} │ {:>5.1}% │ {:>5.2} │ {:>5.1}% │ {:>12} │ {:>5} │ {:>7.2} │ {:>8} │",
                w.address,
                w.pnl_15d,
                w.wr_15d,
                w.pf_15d,
                w.dd_15d,
                w.bias_15d,
                w.trades_15d,
                w.score,
                strategy_display,
            ));
        }
        lines.push("  └──────────────────────────────────┴───────────┴────────┴───────┴───────┴──────────────┴────────┴─────────────┴──────────┘".into());
        lines.push(String::new());
    }

    // ─── All analyzed wallets sorted by score ───
    let analyzed_wallets: Vec<&&WalletInfo> =
        sorted.iter().filter(|w| w.last_updated != 0).collect();
    if !analyzed_wallets.is_empty() {
        lines.push("  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐".into());
        lines.push("  │  ALL ANALYZED WALLETS (sorted by score)                                                                   │".into());
        lines.push("  ├──────────────────────────────────┬───────────┬────────┬───────┬───────┬──────────────┬────────┬─────────────┬──────────┤".into());
        lines.push("  │  Address                         │  15d PnL  │  WR%   │  PF   │  DD%  │  Bias        │ Trades │  Score      │ Strategy │".into());
        lines.push("  ├──────────────────────────────────┼───────────┼────────┼───────┼───────┼──────────────┼────────┼─────────────┼──────────┤".into());
        for w in analyzed_wallets {
            let mark = if w.copy_worthy { "★ " } else { "  " };
            let strategy_display = if w.strategy_15d.is_empty() {
                "N/A"
            } else {
                &w.strategy_15d
            };
            lines.push(format!(
                "  │ {}{} │ ${:>8.0} │ {:>5.1}% │ {:>5.2} │ {:>5.1}% │ {:>12} │ {:>5} │ {:>7.2} │ {:>8} │",
                mark,
                w.address,
                w.pnl_15d,
                w.wr_15d,
                w.pf_15d,
                w.dd_15d,
                w.bias_15d,
                w.trades_15d,
                w.score,
                strategy_display,
            ));
        }
        lines.push("  └──────────────────────────────────┴───────────┴────────┴───────┴───────┴──────────────┴────────┴─────────────┴──────────┘".into());
        lines.push(String::new());
    }

    // ─── Pending wallets ───
    let pending: Vec<&&WalletInfo> = sorted.iter().filter(|w| w.last_updated == 0).collect();
    if !pending.is_empty() {
        lines.push(format!(
            "  ─── Pending analysis: {} wallets ───",
            pending.len()
        ));
        lines.push(String::new());
    }

    // ─── Active copies ───
    let active: Vec<&&WalletInfo> = sorted.iter().filter(|w| w.being_copied).collect();
    if !active.is_empty() {
        lines.push("  ─── Currently being copied ───".into());
        for w in &active {
            lines.push(format!(
                "    {} → PnL=${:.0} WR={:.1}% Score={:.1}",
                &w.address[..10],
                w.pnl_15d,
                w.wr_15d,
                w.score
            ));
        }
        lines.push(String::new());
    }

    lines.push(format!("  Report generated at timestamp {}", now));
    lines.push(String::new());

    let content = lines.join("\n");
    let _ = std::fs::write(path, &content);
}
