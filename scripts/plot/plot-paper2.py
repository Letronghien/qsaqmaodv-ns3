#!/usr/bin/env python3
"""
plot-paper2.py — Generate all figures for QS-QMAODV Paper 2.

Usage:
    python3 plot-paper2.py <merged.csv> [--outdir ./figures]

Produces:
    fig2_w4_sensitivity.pdf      — w4 weight sweep (PDR vs w4 at high load)
    fig3_pdr_vs_load.pdf         — PDR vs traffic load (KEY figure)
    fig4_delay_vs_load.pdf       — Delay vs traffic load
    fig5_pdr_vs_n.pdf            — PDR vs node density (high load)
    fig6_queue_distribution.pdf  — Queue occupancy CDF comparison
    fig7_pdr_vs_energy.pdf       — PDR vs battery (verify energy preserved)
"""

import sys
import os
import csv
import argparse
import warnings
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
warnings.filterwarnings('ignore')

plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 11,
    'axes.titlesize': 12,
    'axes.labelsize': 11,
    'legend.fontsize': 9,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'figure.dpi': 150,
    'savefig.bbox': 'tight',
    'savefig.dpi': 300,
})

PROTO_STYLE = {
    'AODV':          {'color': '#555555', 'marker': 's', 'ls': '-',  'lw': 1.5, 'label': 'AODV'},
    'AOMDV-3':       {'color': '#E67E22', 'marker': '^', 'ls': '--', 'lw': 1.5, 'label': 'AOMDV-3'},
    'QMAODV-3':      {'color': '#2980B9', 'marker': 'o', 'ls': '--', 'lw': 1.5, 'label': 'QMAODV-3'},
    'SAQMAODV-3':    {'color': '#27AE60', 'marker': 'D', 'ls': '-.',  'lw': 1.5, 'label': 'SA-QMAODV-3'},
    'QSAQMAODV-3':   {'color': '#8E44AD', 'marker': '*', 'ls': '-',  'lw': 2.0, 'label': 'QS-QMAODV-3 (Proposed)'},
}
PROTO_ORDER = list(PROTO_STYLE.keys())


def load_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def label_of(proto, mp):
    return proto if proto == 'AODV' else f"{proto}-{mp}"


def parse_scenario(scenario):
    parts = scenario.split('-')
    d = {'family': parts[0]}
    for p in parts[1:]:
        for prefix, key in [('N','numNodes'),('V','speed'),('T','simTime'),
                             ('E','energy'),('pkt','pktInterval')]:
            if p.startswith(prefix):
                try: d[key] = float(p[len(prefix):])
                except ValueError: pass
    return d


def aggregate(rows, key_fn, val='deliveryRatio'):
    groups = defaultdict(list)
    for r in rows:
        try: v = float(r[val])
        except (KeyError, ValueError): continue
        k = key_fn(r)
        if k is not None: groups[k].append(v)
    return {k: (np.mean(v), np.std(v), len(v)) for k, v in groups.items()}


def filter_family(rows, family):
    return [r for r in rows
            if r.get('scenario','').split('-')[0].upper() == family.upper()]


def plot_line(agg_data, x_vals, x_label, title, figname, outdir,
              x_log=False, y_label='PDR (%)', val_scale=100):
    fig, ax = plt.subplots(figsize=(6, 4))
    for proto in PROTO_ORDER:
        style = PROTO_STYLE.get(proto, {})
        xs, ys, errs = [], [], []
        for x in x_vals:
            if (proto, x) in agg_data:
                mean, std, _ = agg_data[(proto, x)]
                xs.append(x); ys.append(mean*val_scale); errs.append(std*val_scale)
        if not xs: continue
        ax.errorbar(xs, ys, yerr=errs,
                    color=style.get('color','k'), marker=style.get('marker','o'),
                    linestyle=style.get('ls','-'), linewidth=style.get('lw',1.5),
                    markersize=6, capsize=3, label=style.get('label', proto))

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    if x_log: ax.set_xscale('log')
    if val_scale == 100: ax.set_ylim(0, 105)
    ax.legend(loc='best', framealpha=0.8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    path = os.path.join(outdir, figname)
    plt.savefig(path); plt.close()
    print(f"  Saved: {path}")


# ─── Fig 2: w4 Sensitivity ──────────────────────────────────────────────────
def plot_w4_sensitivity(rows, outdir):
    w_rows = filter_family(rows, 'W')
    if not w_rows:
        print("  [skip] No W family data"); return

    W4_VALS = [0.0, 0.1, 0.2, 0.3, 0.4]
    groups = defaultdict(list)
    for r in w_rows:
        if r.get('protocol','') != 'QSAQMAODV': continue
        try:
            w4  = float(r.get('qsW4', r.get('w4', 0.2)))
            pdr = float(r['deliveryRatio'])
        except (KeyError, ValueError): continue
        groups[w4].append(pdr)

    if not groups:
        print("  [skip] W family data found but missing qsW4/w4 column"); return

    xs = sorted(groups.keys())
    ys    = [np.mean(groups[x])*100 for x in xs]
    errs  = [np.std(groups[x])*100  for x in xs]

    # SAQMAODV baseline
    sa_rows = [r for r in w_rows if r.get('protocol','') == 'SAQMAODV']
    sa_pdr  = np.mean([float(r['deliveryRatio']) for r in sa_rows
                       if 'deliveryRatio' in r]) * 100 if sa_rows else None

    fig, ax = plt.subplots(figsize=(5, 4))
    ax.errorbar(xs, ys, yerr=errs, color='#8E44AD', marker='*',
                linewidth=2, markersize=8, capsize=3, label='QS-QMAODV-3')
    if sa_pdr:
        ax.axhline(sa_pdr, color='#27AE60', linestyle='-.', linewidth=1.5,
                   label=f'SA-QMAODV-3 ({sa_pdr:.1f}%)')
    ax.set_xlabel('Queue reward weight w4')
    ax.set_ylabel('PDR (%)')
    ax.set_title('Fig 2: PDR vs w4 (pktInterval=0.1 s)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 105)
    plt.tight_layout()
    path = os.path.join(outdir, 'fig2_w4_sensitivity.pdf')
    plt.savefig(path); plt.close()
    print(f"  Saved: {path}")


# ─── Fig 3: PDR vs Load ─────────────────────────────────────────────────────
def plot_pdr_vs_load(rows, outdir):
    l_rows = filter_family(rows, 'L')
    if not l_rows:
        print("  [skip] No L family data"); return

    PKT_VALS = [0.05, 0.1, 0.25, 0.5, 1.0]

    def key_fn(r):
        sc = parse_scenario(r.get('scenario',''))
        pkt = sc.get('pktInterval')
        if pkt is None:
            try: pkt = float(r.get('pktInterval', 0))
            except: return None
        return (label_of(r['protocol'], r['maxPaths']), pkt)

    agg = aggregate(l_rows, key_fn)
    plot_line(agg, sorted(PKT_VALS), 'Packet Interval (s)',
              'Fig 3: PDR vs Traffic Load',
              'fig3_pdr_vs_load.pdf', outdir, x_log=True)


# ─── Fig 4: Delay vs Load ───────────────────────────────────────────────────
def plot_delay_vs_load(rows, outdir):
    l_rows = filter_family(rows, 'L')
    if not l_rows:
        print("  [skip] No L family data (delay)"); return

    PKT_VALS = [0.05, 0.1, 0.25, 0.5, 1.0]

    def key_fn(r):
        sc = parse_scenario(r.get('scenario',''))
        pkt = sc.get('pktInterval')
        if pkt is None:
            try: pkt = float(r.get('pktInterval', 0))
            except: return None
        return (label_of(r['protocol'], r['maxPaths']), pkt)

    agg = aggregate(l_rows, key_fn, val='avgDelayMs')
    if not agg:
        print("  [skip] avgDelayMs column missing"); return
    plot_line(agg, sorted(PKT_VALS), 'Packet Interval (s)',
              'Fig 4: Average Delay vs Traffic Load',
              'fig4_delay_vs_load.pdf', outdir,
              x_log=True, y_label='Avg Delay (ms)', val_scale=1)


# ─── Fig 5: PDR vs N (high load) ────────────────────────────────────────────
def plot_pdr_vs_n(rows, outdir):
    n_rows = filter_family(rows, 'N')
    if not n_rows:
        print("  [skip] No N family data"); return

    N_VALS = [5, 10, 15, 20, 25, 30]

    def key_fn(r):
        sc = parse_scenario(r.get('scenario',''))
        n = sc.get('numNodes')
        if n is None: return None
        return (label_of(r['protocol'], r['maxPaths']), n)

    agg = aggregate(n_rows, key_fn)
    plot_line(agg, N_VALS, 'Number of Nodes',
              'Fig 5: PDR vs Node Density (high load)',
              'fig5_pdr_vs_n.pdf', outdir)


# ─── Fig 6: Queue Occupancy CDF ─────────────────────────────────────────────
def plot_queue_cdf(rows, outdir):
    """
    Requires CSV column 'meanQueueRatio' (per-run mean queue occupancy).
    """
    has_q = any('meanQueueRatio' in r for r in rows)
    if not has_q:
        print("  [skip] meanQueueRatio column missing"); return

    groups = defaultdict(list)
    for r in rows:
        try: q = float(r['meanQueueRatio'])
        except (KeyError, ValueError): continue
        lb = label_of(r.get('protocol',''), r.get('maxPaths','1'))
        groups[lb].append(q)

    fig, ax = plt.subplots(figsize=(5, 4))
    for proto in PROTO_ORDER:
        vals = sorted(groups.get(proto, []))
        if not vals: continue
        style = PROTO_STYLE.get(proto, {})
        ecdf = np.arange(1, len(vals)+1) / len(vals)
        ax.step(vals, ecdf, color=style.get('color','k'),
                linestyle=style.get('ls','-'), linewidth=style.get('lw',1.5),
                label=style.get('label', proto))

    ax.set_xlabel('Mean Queue Occupancy Ratio')
    ax.set_ylabel('CDF')
    ax.set_title('Fig 6: Queue Occupancy Distribution')
    ax.legend(loc='lower right')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 1)
    plt.tight_layout()
    path = os.path.join(outdir, 'fig6_queue_distribution.pdf')
    plt.savefig(path); plt.close()
    print(f"  Saved: {path}")


# ─── Fig 7: PDR vs Energy ───────────────────────────────────────────────────
def plot_pdr_vs_energy(rows, outdir):
    e_rows = filter_family(rows, 'E')
    if not e_rows:
        print("  [skip] No E family data"); return

    E_VALS = [10, 20, 30, 50]

    def key_fn(r):
        sc = parse_scenario(r.get('scenario',''))
        e = sc.get('energy')
        if e is None: return None
        return (label_of(r['protocol'], r['maxPaths']), e)

    agg = aggregate(e_rows, key_fn)
    plot_line(agg, E_VALS, 'Initial Energy (J)',
              'Fig 7: PDR vs Battery Capacity',
              'fig7_pdr_vs_energy.pdf', outdir)


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Plot QS-QMAODV Paper 2 figures')
    parser.add_argument('csv')
    parser.add_argument('--outdir', default='./figures')
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    rows = load_csv(args.csv)
    print(f"Loaded {len(rows)} rows from {args.csv}")

    print(f"\nGenerating figures → {args.outdir}/")
    plot_w4_sensitivity(rows, args.outdir)
    plot_pdr_vs_load(rows, args.outdir)
    plot_delay_vs_load(rows, args.outdir)
    plot_pdr_vs_n(rows, args.outdir)
    plot_queue_cdf(rows, args.outdir)
    plot_pdr_vs_energy(rows, args.outdir)
    print("\nDone.")


if __name__ == '__main__':
    main()
