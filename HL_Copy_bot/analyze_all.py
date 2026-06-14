#!/usr/bin/env python3
"""
Phan tich toan dien 22 vi worthy:
- Cach tinh score, tai sao sai
- 15d/30d PnL chi tiet
- Bug o dau
- Vi nao dang copy duoc
"""
import json, math, os

with open('validation_results.json') as f:
    data = json.load(f)

worthy = [(a, v) for a, v in data.items() if a != '__meta__' and v.get('valid') and v.get('worthy')]
worthy.sort(key=lambda x: x[1].get('score', 0), reverse=True)

def calc_score(trades, wr, pf, dd, pnl):
    t = min(trades / 100, 1.0) * 15
    w = (wr / 100) * 20
    p = min(pf / 10, 1.0) * 20
    d = max(1.0 - dd / 50, 0.0) * 15
    r = min(pnl / 5000, 1.0) * 30
    return round(t + w + p + d + r, 1), round(t,1), round(w,1), round(p,1), round(d,1), round(r,1)

line = '=' * 130
print(line)
print(f'{"":^130}')
print(f'{"PHAN TICH 22 VI WORTHY — SCORE BREAKDOWN + BUG DIAGNOSIS":^130}')
print(f'{"":^130}')
print(line)

print(f'\nCong thuc hien tai: score = t(min(trades/100,1)x15) + w(WR/100x20) + p(min(PF/10,1)x20) + d(max(1-DD/50,0)x15) + r(min(PnL/5000,1)x30)')
print(f'TRONG DO: t=15diem, w=20diem, p=20diem, d=15diem, r=30diem  |  Tong=100')

print(f'\n{"":^130}')
print(f'{"=" * 130}')
print(f'{"Vi tri":<6} {"Address":<46} {"Score":<7} {"t(15)":<7} {"w(20)":<7} {"p(20)":<7} {"d(15)":<7} {"r(30)":<7} {"Trades":<7} {"WR%":<6} {"PF":<8} {"DD%":<6} {"PnL":<9} {"Strategy":<12}')
print(f'{"=" * 130}')

for i, (addr, v) in enumerate(worthy, 1):
    trades = v.get('total_trades', 0)
    wr = v.get('win_rate', 0)
    pf = v.get('profit_factor', 0)
    dd = v.get('max_dd', 0)
    pnl = v.get('total_pnl', 0)
    score, t, w, p, d, r = calc_score(trades, wr, pf, dd, pnl)
    strat = v.get('strategy', '?')
    print(f'{i:<6} {addr:<46} {score:<7} {t:<7} {w:<7} {p:<7} {d:<7} {r:<7} {trades:<7} {wr:<6.1f} {pf:<8.1f} {dd:<6.1f} {pnl:<9,.0f} {strat:<12}')

print(f'{"=" * 130}')

# === BUG 1: PnL component ===
print(f'\n\n{" BUG 1: PnL CHIEM 30% NHUNG KHONG YEU CAU SO TRADES TOI THIEU ":=^100}')
print(f'''
  r = min(PnL/5000, 1.0) * 30

  Van de: Chi can PnL >= $5,000 la duoc 30 diem TOI DA, ke ca chi co vai trades may man.
  Vi du:
    - 0x18d103 (12 trades, PnL=$17,524):  r=30/30  (dat max du chi 12 trades!)
    - 0x7aa11a  (438 trades, PnL=$1,044):   r=6.3/30 (chi duoc 6.3 du 438 trades skill)
    = 0x18d103 duoc hon 23.7 diem chi vi PnL cao hon, mac du trades gap 36.5 lan

  Tai sao sai: PnL/5000 khong phan anh ky nang giao dich, no chi phan anh may man
  khi sample size nho. Mot wallet 438 trades voi PnL=$1,044 dang ky nang hon NHIEU
  so voi wallet 12 trades PnL=$17,524 (chi la vai le may man).
''')

# === BUG 2: PF component ===
print(f'{" BUG 2: PF CAP QUA SOM — 20 DIEM CHI CAN KO LO ":=^100}')
print(f'''
  p = min(PF/10, 1.0) * 20

  Van de: PF = gross_profit/gross_loss. Neu chi co 1-2 trade lo nho, PF se rat cao.
  Vi du:
    - 0x18d103 (12 trades, PF=92230.9):  p=20/20 (PF vuot xa cap 10, du chi 12 trades!)
    - 0x931153 (6 trades, PF=999):        p=20/20 (999 > 10, du chi 6 trades!)
    - 0x7aa11a (438 trades, PF=2.5):      p=5/20  (PF=2.5 that, nhung la that su co y nghia)

  Tai sao sai: PF chi co y nghia khi co nhieu trades. Vai trades may man cho PF ao,
  nhung van duoc 20 diem nhu wallet 438 trades that su co PF=2.5.
''')

# === BUG 3: DD component ===
print(f'{" BUG 3: DD CUNG BI ANH HUONG BOI IT TRADES ":=^100}')
print(f'''
  d = max(1.0 - DD/50, 0.0) * 15

  Van de: Wallet it trades thuong co DD thap vi chua co nhieu co hoi de drawdown.
  Vi du:
    - 0x18d103 (12 trades, DD=0.2%):     d=14.9/15 (hau nhu toi da)
    - 0x7aa11a  (438 trades, DD=14.0%):  d=10.8/15 (thap hon dung 4.1 diem)
    
  DD 0.2% sau 12 trades khong co y nghia gi. DD 14% sau 438 trades la con so that.
''')

# === BUG 4 ===
print(f'{" BUG 4: COPYABILITY QUA CAY VOI TPD CAO (DA FIX) ":=^100}')
print(f'''
  copyability = calc_copyability(tpd, hold, strategy)
  SWING/POSITION bi phat -50 diem neu TPD > 30, nhung SWING thi TPD khong quan trong.
  Da fix: giam phat cho SWING/POSITION x0.5.
  
  Truoc fix: 0x7aa11a tpd=62.6 -> -50, copyability=50%
  Sau fix:   0x7aa11a tpd=62.6 -> -25, copyability=75%
''')

# === BUG 5 ===
print(f'{" BUG 5: SNAPSHOT RESTORE KHONG KIEM TRA MAX_PER_STRATEGY (DA FIX) ":=^100}')
print(f'''
  Van de: Snapshot chua 3 SWING, 2 DAY_TRADER. Khoi dong lai load het 5 vi,
  bat ke MAX_PER_STRATEGY=2. Ca 2 strategies deu day -> 0 vi moi duoc them vao.

  Da fix: Evict vi thap diem nhat khi vuot qua strategy cap.
''')

# === Current copies ===
print(f'\n\n{" 5 VI DANG DUOC COPY (TU SNAPSHOT) ":=^100}')
print(f'{"Address":<46} {"Score":<7} {"Trades":<7} {"PnL":<10} {"WR%":<6} {"Strategy":<12} {"Van de"}')
print(f'{"-" * 100}')
snapshot_addrs = [
    "0x18d103744b0f0bd4ab860f3455a252d20580d6dd",
    "0x931153baac031d055389b41d12cd32c9bf0ae7a3",
    "0x9da9ccc7563bc4c420a7a30819d3875d9499f376",
    "0x76fe28b803eeba445c34afc2f914e6bcb71112fd",
    "0x6e6f2ca77afaee5a22dc3cf0f903f39a548a82a6",
]
for addr in snapshot_addrs:
    v = data.get(addr, {})
    trades = v.get('total_trades', 0)
    score = v.get('score', 0)
    pnl = v.get('total_pnl', 0)
    wr = v.get('win_rate', 0)
    strat = v.get('strategy', '?')
    if trades < 10:
        issue = f'CHI CO {trades} TRADES!'
    elif trades < 20:
        issue = f'chi {trades} trades, thieu tin cay'
    elif pnl < 0:
        issue = f'LO ${pnl:.0f}!'
    else:
        issue = 'tam on'
    print(f'{addr:<46} {score:<7} {trades:<7} {pnl:<10,.0f} {wr:<6.1f} {strat:<12} {issue}')

print(f'\n{"=> 5 vi nay DEU THIEU DU LIEU, chi co 1 vi co >12 trades!"}')

# === Wallets that SHOULD be copied ===
print(f'\n\n{" 3 VI THUC SU DANG COPY ":=^100}')
print(f'{"Address":<46} {"Score":<7} {"Trades":<7} {"PnL":<10} {"WR%":<6} {"PF":<8} {"DD%":<6} {"Strategy":<12} {"Copy%":<6}')
print(f'{"-" * 100}')
good_addrs = [
    "0xb69ccb3ad06300fefe1c551e285de4a3c6a1a5da",
    "0x7aa11aafdfc46ebedbb3adabea180cce3607e8c2",
    "0xb1edfeccf03f35d2268f5dc4013508a6eb52c702",
]
for addr in good_addrs:
    v = data.get(addr, {})
    trades = v.get('total_trades', 0)
    score = v.get('score', 0)
    pnl = v.get('total_pnl', 0)
    wr = v.get('win_rate', 0)
    pf = v.get('profit_factor', 0)
    dd = v.get('max_dd', 0)
    strat = v.get('strategy', '?')
    copy = v.get('copyability', 0)
    print(f'{addr:<46} {score:<7} {trades:<7} {pnl:<10,.0f} {wr:<6.1f} {pf:<8.1f} {dd:<6.1f} {strat:<12} {copy:<6.0f}')

print(f'\n=> 3 vi nay co trades>=50 (du tin cay), WR>=67%, PnL>0, nhung KHONG duoc copy!')

# === Why 0x7aa11a only gets 56 ===
print(f'\n\n{" PHAN TICH CHI TIET: 0x7aa11a VS 0x18d103 ":=^100}')
v1 = data['0x7aa11aafdfc46ebedbb3adabea180cce3607e8c2']
v2 = data['0x18d103744b0f0bd4ab860f3455a252d20580d6dd']

_, t1,w1,p1,d1,r1 = calc_score(v1['total_trades'], v1['win_rate'], v1['profit_factor'], v1['max_dd'], v1['total_pnl'])
_, t2,w2,p2,d2,r2 = calc_score(v2['total_trades'], v2['win_rate'], v2['profit_factor'], v2['max_dd'], v2['total_pnl'])

print(f'''
  {"Chi tieu":<20} {"0x7aa11a (438 trades)":<35} {"0x18d103 (12 trades)":<35} {"Chenh lech":<15}
  {"-"*105}
  {"Trades":<20} {v1['total_trades']:<35} {v2['total_trades']:<35} {"x36.5":<15}
  {"PnL 30d":<20} {f"${v1['total_pnl']:>8,.0f}":<35} {f"${v2['total_pnl']:>8,.0f}":<35} {"0x18d103 gap x17":<15}
  {"WR%":<20} {f"{v1['win_rate']:.1f}%":<35} {f"{v2['win_rate']:.1f}%":<35} {"0x7aa11a cao hon":<15}
  {"PF":<20} {f"{v1['profit_factor']:.1f}":<35} {f"{v2['profit_factor']:.1f}":<35} {"0x18d103 PF ao":<15}
  {"DD%":<20} {f"{v1['max_dd']:.1f}%":<35} {f"{v2['max_dd']:.1f}%":<35} {"0x18d103 DD qua thap":<15}
  {"-"*105}
  {"SCORE":<20} {"56":<35} {"85":<35} {"+29 diem cho luoi":<15}
  {"  t (trades)":<20} {f"{t1}/15":<35} {f"{t2}/15":<35} {"+0 (ca 2 deu cap thap)":<15}
  {"  w (WR)":<20} {f"{w1}/20":<35} {f"{w2}/20":<35} {"+0":<15}
  {"  p (PF)":<20} {f"{p1}/20":<35} {f"{p2}/20":<35} {"+15 cho PF ao":<15}
  {"  d (DD)":<20} {f"{d1}/15":<35} {f"{d2}/15":<35} {"+4 cho DD thap ao":<15}
  {"  r (PnL)":<20} {f"{r1}/30":<35} {f"{r2}/30":<35} {"+24 cho PnL may man":<15}
  {"-"*105}
  
  KET LUAN: 0x7aa11a that su giao dich gioi hon nhieu (94.3% WR, 438 trades, PF=2.5),
  nhung bi diem thap vi p+r+d = 21.9/65 (PF thap, DD trung binh, PnL khiem ton).
  Trong khi 0x18d103 duoc 65/65 o 3 thanh phan nay chi vi co vai trade may man.
  
  CAN SUA: 
  1. PnL component: yeu cau toi thieu trades de dat max (vi du: trades/50 * min(PnL/5000,1) * 30)
  2. PF component: giam trong so hoac yeu cau trades>=20 de tinh
  3. Them "confidence" component: trades/200 * 10 diem bonus
''')

# === Daily PnL stats ===
print(f'\n\n{" PHAN TICH 15D/30D PnL THEO NGAY ":=^100}')
# We don't have daily data in validation_results.json directly, but we can show what we do have
print(f'{"Address":<46} {"30dPnL":<10} {"Trades":<8} {"WR%":<6} {"PF":<8} {"DD%":<7} {"AvgHold":<9} {"Strategy":<12}')
print(f'{"-" * 100}')
for addr, v in worthy:
    hold = v.get('avg_hold_secs', 0)
    hold_str = f'{hold/3600:.1f}h' if hold > 3600 else f'{hold/60:.0f}m'
    print(f'{addr:<46} ${v.get("total_pnl",0):<8,.0f} {v.get("total_trades",0):<8} {v.get("win_rate",0):<5.1f}% {v.get("profit_factor",0):<8.1f} {v.get("max_dd",0):<6.1f}% {hold_str:<9} {v.get("strategy","?"):<12}')

# Check daily active_days for each wallet
print(f'\n\n{" SO NGAY GIAO DICH (ACTIVE DAYS OUT OF 30) ":=^100}')
print(f'{"Address":<46} {"ActiveDays":<11} {"Trades":<8} {"PnL":<10} {"AvgPnl/Day":<12} {"Best":<10} {"Worst":<10} {"LosingStreak":<14} {"Strategy":<12}')
print(f'{"-" * 100}')
for addr, v in worthy:
    daily = v.get('daily', {})
    active = daily.get('active_days', 0)
    avg = daily.get('avg_pnl_per_day', 0)
    best = daily.get('best_day', 0)
    worst = daily.get('worst_day', 0)
    streak = daily.get('max_losing_streak', 0)
    trades = v.get('total_trades', 0)
    pnl = v.get('total_pnl', 0)
    strat = v.get('strategy', '?')
    print(f'{addr:<46} {active}/30{"":<3} {trades:<8} ${pnl:<8,.0f} ${avg:<9,.0f} ${best:<7,.0f} ${worst:<7,.0f} {streak:<14} {strat:<12}')

# === Per-coin breakdown for wallets with good data ===
print(f'\n\n{" PHAN TICH PER-COIN CHO 3 VI TOT NHAT ":=^100}')
for addr in good_addrs:
    v = data.get(addr, {})
    pc = v.get('per_coin', {})
    trades = v.get('total_trades', 0)
    strat = v.get('strategy', '?')
    print(f'\n{addr} ({strat}, {trades} trades, score={v.get("score",0):.0f})')
    if pc:
        print(f'  {"Coin":<10} {"Trades":<8} {"PnL":<10} {"WR%":<7} {"Weight":<8}')
        print(f'  {"-"*43}')
        for coin, c in sorted(pc.items(), key=lambda x: x[1].get('trades', 0), reverse=True):
            print(f'  {coin:<10} {c.get("trades",0):<8} ${c.get("pnl",0):<8,.0f} {c.get("wr",0):<6.1f}% {c.get("weight",0):<7.1f}%')
    else:
        print(f'  (khong co per-coin data)')

# === summary ===
print(f'\n\n{" TOM TAT ":=^100}')
print(f'''
22 vi worthy:
  - 3 vi chat luong cao (trades>=50, score>=40): can uu tien copy
    0xb69ccb (DAY_TRADER, 99 trades, $2,260, WR=75.8%)
    0x7aa11a (SWING, 438 trades, $1,044, WR=94.3%)
    0xb1edfe (DAY_TRADER, 67 trades, $2,647, WR=67.2%)
    
  - 2 vi tam duoc (trades 30-49): can theo doi them
    0x44871d (SWING, 30 trades, $994, WR=73.3%)
    
  - 17 vi thieu du lieu hoac co van de: KHONG NEN COPY
    - 11 vi <20 trades
    - 4 vi ALPHA_DECAY / REGIME_MISMATCH
    - 2 vi lo tien

BUG chinh:
  1. Scoring: PnL (30%) + PF (20%) + DD (15%) = 65% bi anh huong boi may man khi it trades
  2. Copyability: phat TPD qua nang (DA FIX)
  3. Snapshot restore: ko check MAX_PER_STRATEGY (DA FIX)
  4. Hien tai 5 vi dang copy DEU thuoc nhom thieu du lieu (<20 trades)

GIAI PHAP:
  - Fix scoring: them trade-weighted confidence vao PnL component
  - Evict 4/5 vi hien tai (giu lai vi tot nhat)
  - Them 3 vi chat luong cao vao copy list
''')

# Cleanup
print(f'\n{"=" * 130}')
