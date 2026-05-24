#!/usr/bin/env python3
"""
analyze-family-H.py
===================

Đọc family_H_hyper.csv (Family H — hyperparameter sweep cho QMAODV)
và in ra:
  1. Top-15 cấu hình theo PDR
  2. Top-10 cấu hình theo Delay (lọc PDR ≥ ngưỡng)
  3. Per-parameter marginal analysis (PDR trung bình khi cố định 1 param)

Usage:
    python3 analyze-family-H.py <family_H_hyper.csv>
"""

import sys, csv
from collections import defaultdict

if len(sys.argv) < 2:
    print("Usage: python3 analyze-family-H.py <family_H_hyper.csv>")
    sys.exit(1)

CSV = sys.argv[1]
rows = list(csv.DictReader(open(CSV)))
if not rows:
    sys.exit("Empty CSV")

# Aggregate by scenario tag (= hyperparam config)
agg = defaultdict(list)
for r in rows:
    cfg = r['scenario'].replace('tune-', '')
    try:
        agg[cfg].append({
            'pdr':   float(r['deliveryRatio']),
            'delay': float(r['avgDelayMs']),
            'thr':   float(r['throughputMbps']),
            'over':  int(float(r['routingOverhead'])),
        })
    except (KeyError, ValueError):
        continue

# Compute means
ranked = []
for cfg, vals in agg.items():
    n = len(vals)
    ranked.append({
        'cfg':   cfg,
        'pdr':   sum(v['pdr']   for v in vals)/n,
        'delay': sum(v['delay'] for v in vals)/n,
        'thr':   sum(v['thr']   for v in vals)/n,
        'over':  sum(v['over']  for v in vals)/n,
        'n':     n,
    })

# Parse cfg into params
def parse_cfg(cfg):
    out = {}
    for part in cfg.split('-'):
        if part.startswith('a'): out['alpha']   = float(part[1:])
        if part.startswith('g'): out['gamma']   = float(part[1:])
        if part.startswith('e'): out['epsilon'] = float(part[1:])
        if part.startswith('d'): out['decay']   = float(part[1:])
    return out

for r in ranked:
    r.update(parse_cfg(r['cfg']))

# === 1. Top-15 by PDR ===
ranked.sort(key=lambda x: -x['pdr'])
print()
print("=" * 80)
print(" Top-15 cấu hình theo PDR")
print("=" * 80)
print(f"{'rank':<5} {'α':>5} {'γ':>5} {'ε':>5} {'decay':>6}   {'PDR(%)':>8} {'delay':>8} {'thr':>8} {'overhead':>10}")
print('-' * 80)
for i, r in enumerate(ranked[:15], 1):
    print(f"{i:<5} {r['alpha']:>5.2f} {r['gamma']:>5.2f} {r['epsilon']:>5.2f} "
          f"{r['decay']:>6.3f}   {r['pdr']:>8.2f} {r['delay']:>8.1f} "
          f"{r['thr']:>8.4f} {r['over']:>10.0f}")

# === 2. Top-10 by Delay (filter PDR ≥ 30%) ===
ranked_delay = [r for r in ranked if r['pdr'] >= 30.0]
ranked_delay.sort(key=lambda x: x['delay'])
print()
print("=" * 80)
print(" Top-10 cấu hình theo Delay (lọc PDR ≥ 30%)")
print("=" * 80)
print(f"{'rank':<5} {'α':>5} {'γ':>5} {'ε':>5} {'decay':>6}   {'PDR(%)':>8} {'delay':>8} {'thr':>8} {'overhead':>10}")
print('-' * 80)
for i, r in enumerate(ranked_delay[:10], 1):
    print(f"{i:<5} {r['alpha']:>5.2f} {r['gamma']:>5.2f} {r['epsilon']:>5.2f} "
          f"{r['decay']:>6.3f}   {r['pdr']:>8.2f} {r['delay']:>8.1f} "
          f"{r['thr']:>8.4f} {r['over']:>10.0f}")

# === 3. Marginal analysis — PDR averaged per param value ===
def marginal(param):
    by_val = defaultdict(list)
    for r in ranked:
        by_val[r.get(param)].append(r['pdr'])
    return [(v, sum(p)/len(p), len(p)) for v, p in sorted(by_val.items()) if v is not None]

print()
print("=" * 80)
print(" Phân tích marginal (PDR trung bình khi cố định 1 param)")
print("=" * 80)
for param in ['alpha', 'gamma', 'epsilon', 'decay']:
    print(f"\n{param}:")
    for val, mean_pdr, n in marginal(param):
        bar = '█' * int(mean_pdr / 1.5)
        print(f"  {val:>6.3f}  PDR={mean_pdr:>5.2f}%  (n={n})  {bar}")

# === 4. Best per param value combo ===
print()
print("=" * 80)
print(" Giá trị TỐT NHẤT mỗi tham số (theo marginal)")
print("=" * 80)
best = {}
for param in ['alpha', 'gamma', 'epsilon', 'decay']:
    m = marginal(param)
    best_v = max(m, key=lambda x: x[1])
    best[param] = best_v[0]
    print(f"  {param}: {best_v[0]} (avg PDR {best_v[1]:.2f}%)")

print()
print(f"=> Đề xuất cấu hình mới: α={best['alpha']}, γ={best['gamma']}, ε={best['epsilon']}, decay={best['decay']}")

# Kiểm tra cấu hình đề xuất có trong top-15 không
suggested_cfg = f"a{best['alpha']}-g{best['gamma']}-e{best['epsilon']}-d{best['decay']}"
match = next((r for r in ranked if r['cfg'] == suggested_cfg), None)
if match:
    rank = ranked.index(match) + 1
    print(f"   Cấu hình này hạng #{rank}/{len(ranked)}, PDR thực = {match['pdr']:.2f}%")
else:
    print(f"   (cấu hình '{suggested_cfg}' không có trong grid sweep)")
