#!/usr/bin/env python3
import json

with open('validation_results.json') as f:
    data = json.load(f)

worthy = [(a, v) for a, v in data.items() if a != '__meta__' and v.get('valid') and v.get('worthy')]
worthy.sort(key=lambda x: x[1].get('score', 0), reverse=True)

print('=' * 120)
print('PHÂN TÍCH 22 VÍ WORTHY — Deep Dive')
print('=' * 120)

high_quality = []
medium_quality = []
low_quality = []

for addr, v in worthy:
    trades = v.get('total_trades', 0)
    pnl = v.get('total_pnl', 0)
    score = v.get('score', 0)
    warns = v.get('warnings', [])
    has_alpha_decay = 'ALPHA_DECAYING' in warns
    has_regime = 'REGIME_MISMATCH' in warns

    if has_alpha_decay or has_regime:
        low_quality.append((addr, v, 'ALPHA_DECAY hoac REGIME_MISMATCH'))
    elif trades < 20:
        low_quality.append((addr, v, f'chi co {trades} trades - khong du du lieu'))
    elif pnl < -100:
        low_quality.append((addr, v, f'lo ${pnl:.0f}'))
    elif score >= 40 and trades >= 50:
        high_quality.append((addr, v, 'chat luong cao'))
    else:
        medium_quality.append((addr, v, 'trung binh'))

print(f'''
TONG QUAN:
  Cao (score>=40, trades>=50): {len(high_quality)}
  Trung binh: {len(medium_quality)}
  Thap (thieu du lieu/lo/thoai hoa): {len(low_quality)}
  Tong: {len(worthy)}
''')

print('--- NHOM CAO (thuc su copy duoc) ---')
for addr, v, note in high_quality:
    hold_h = v.get('avg_hold_secs', 0) / 3600
    print(f'''
  {addr}
     Strategy={v.get('strategy','?')}  Score={v.get('score',0):.0f}  Copy={v.get('copyability',0):.0f}%
     PnL=${v.get('total_pnl',0):>8,.0f} | WR={v.get('win_rate',0):.1f}% | PF={v.get('profit_factor',0):.1f}
     Trades={v.get('total_trades',0)} | DD={v.get('max_dd',0):.1f}% | Bias={v.get('bias','?')}
     AvgHold={hold_h:.1f}h
     Warnings: {v.get('warnings', [])}
''')

print('--- NHOM THAP (ly do) ---')
for addr, v, reason in low_quality:
    print(f'  {addr} | {reason} | PnL=${v.get("total_pnl",0):>8,.0f} | trades={v.get("total_trades",0)} | {v.get("strategy","?")} | score={v.get("score",0):.0f}')

print()
print('--- NHOM TRUNG BINH ---')
for addr, v, reason in medium_quality:
    print(f'  {addr} | {reason} | PnL=${v.get("total_pnl",0):>8,.0f} | WR={v.get("win_rate",0):.1f}% | trades={v.get("total_trades",0)} | {v.get("strategy","?")} | score={v.get("score",0):.0f}')

# Stats
total_losing = sum(1 for _, v in worthy if v.get('total_pnl', 0) < 0)
total_winning = sum(1 for _, v in worthy if v.get('total_pnl', 0) >= 0)
total_pnl = sum(v.get('total_pnl', 0) for _, v in worthy)
total_trades = sum(v.get('total_trades', 0) for _, v in worthy)
avg_trades = total_trades / len(worthy) if worthy else 0

print()
print('--- THONG KE ---')
print(f'  Vi loi: {total_winning}/{len(worthy)} ({total_winning/len(worthy)*100:.0f}%)')
print(f'  Vi lo:  {total_losing}/{len(worthy)} ({total_losing/len(worthy)*100:.0f}%)')
print(f'  Tong PnL 22 vi: ${total_pnl:,.0f}')
print(f'  Tong trades: {total_trades}')
print(f'  Trades TB/vi: {avg_trades:.0f}')
print(f'  Vi copy duoc thuc su (score>=40, trades>=50, khong warning): {len(high_quality)}')
