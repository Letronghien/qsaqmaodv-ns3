#!/usr/bin/env python3
"""
plot-qsaqmaodv.py
=================
Plot 7 figures for QS-QMAODV paper.
4 protocols: AODV, PMAODV, QMAODV, QSAQMAODV

Usage:
  python3 plot-qsaqmaodv.py <results-dir> <output-dir>

  results-dir must contain: family_N.csv, family_S.csv,
                             family_L.csv, family_E.csv, family_W.csv
"""
import sys, os, csv, math
from collections import defaultdict

# ── matplotlib setup ─────────────────────────────────────────────────────────
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

if len(sys.argv) < 3:
    print("Usage: python3 plot-qsaqmaodv.py <results-dir> <output-dir>")
    sys.exit(1)

RESULTS_DIR = sys.argv[1]
OUT_DIR     = sys.argv[2]
os.makedirs(OUT_DIR, exist_ok=True)

# ── Protocol config ───────────────────────────────────────────────────────────
PROTOCOLS   = ["AODV", "PMAODV", "QMAODV", "QSAQMAODV"]
COLORS      = {"AODV": "#888888", "PMAODV": "#2196F3",
               "QMAODV": "#FF9800", "QSAQMAODV": "#E91E63"}
MARKERS     = {"AODV": "o", "PMAODV": "s", "QMAODV": "^", "QSAQMAODV": "D"}
LABELS      = {"AODV": "AODV", "PMAODV": "PMAODV",
               "QMAODV": "QMAODV", "QSAQMAODV": "QS-QMAODV"}
LINE_STYLES = {"AODV": "--", "PMAODV": "-.", "QMAODV": ":", "QSAQMAODV": "-"}

# ── CSV loader ────────────────────────────────────────────────────────────────
def load_csv(fname):
    path = os.path.join(RESULTS_DIR, fname)
    if not os.path.exists(path):
        print(f"  WARNING: {path} not found — skipping")
        return []
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows

def safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

# ── Aggregation helper ────────────────────────────────────────────────────────
# Returns dict: key → {metric: (mean, std)}
def aggregate(rows, key_col, metrics, scenario_prefix=None):
    """
    key_col: column name OR None (use scenario_prefix to parse from scenario tag)
    scenario_prefix: e.g. "E" → parse float from scenario tag "E20" → 20.0
    metrics: list of column names
    """
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        proto = r.get("protocol","").strip()
        if proto not in PROTOCOLS:
            continue
        # Get key value
        if scenario_prefix is not None:
            tag = r.get("scenario","").strip()
            if not tag.startswith(scenario_prefix):
                continue
            try:
                key = float(tag[len(scenario_prefix):])
            except ValueError:
                continue
        else:
            try:
                key = float(r[key_col])
            except (KeyError, ValueError):
                continue
        for m in metrics:
            v = safe_float(r.get(m, None))
            if v is not None:
                data[key][proto][m].append(v)

    result = {}
    for key, protos in data.items():
        result[key] = {}
        for proto, mets in protos.items():
            result[key][proto] = {}
            for m, vals in mets.items():
                if vals:
                    result[key][proto][m] = (np.mean(vals), np.std(vals))
                else:
                    result[key][proto][m] = (0.0, 0.0)
    return dict(sorted(result.items()))

# ── Plot helpers ──────────────────────────────────────────────────────────────
def plot_metric(ax, agg, metric, ylabel, title, proto_list=None):
    if proto_list is None:
        proto_list = PROTOCOLS
    xs = sorted(agg.keys())
    for proto in proto_list:
        ys    = [agg[x].get(proto, {}).get(metric, (0,0))[0] for x in xs]
        yerrs = [agg[x].get(proto, {}).get(metric, (0,0))[1] for x in xs]
        ax.errorbar(xs, ys, yerr=yerrs,
                    label=LABELS[proto],
                    color=COLORS[proto],
                    marker=MARKERS[proto],
                    linestyle=LINE_STYLES[proto],
                    linewidth=1.8, markersize=6,
                    capsize=3)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.legend(fontsize=8, loc='best')
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.1f'))

def finalize(fig, fname):
    fig.tight_layout()
    path = os.path.join(OUT_DIR, fname)
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {path}")

# ─────────────────────────────────────────────────────────────────────────────
# Fig 2 — Family N: PDR vs Node count
# ─────────────────────────────────────────────────────────────────────────────
def fig_N():
    rows = load_csv("family_N.csv")
    if not rows: return
    agg = aggregate(rows, None,
                    ["deliveryRatio","avgDelayMs","routingOverhead"],
                    scenario_prefix="N")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    plot_metric(axes[0], agg, "deliveryRatio",
                "PDR (%)", "PDR vs Node Count")
    axes[0].set_xlabel("Number of Nodes", fontsize=10)
    plot_metric(axes[1], agg, "routingOverhead",
                "Routing Overhead (pkts)", "Overhead vs Node Count")
    axes[1].set_xlabel("Number of Nodes", fontsize=10)
    fig.suptitle("Fig. 2 — Effect of Node Density", fontsize=12)
    finalize(fig, "fig2_family_N.png")

# ─────────────────────────────────────────────────────────────────────────────
# Fig 3 — Family S: PDR vs UAV Speed
# ─────────────────────────────────────────────────────────────────────────────
def fig_S():
    rows = load_csv("family_S.csv")
    if not rows: return
    agg = aggregate(rows, None,
                    ["deliveryRatio","avgDelayMs","routingOverhead"],
                    scenario_prefix="V")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    plot_metric(axes[0], agg, "deliveryRatio",
                "PDR (%)", "PDR vs UAV Max Speed")
    axes[0].set_xlabel("Max Speed (m/s)", fontsize=10)
    plot_metric(axes[1], agg, "avgDelayMs",
                "E2E Delay (ms)", "Delay vs UAV Max Speed")
    axes[1].set_xlabel("Max Speed (m/s)", fontsize=10)
    fig.suptitle("Fig. 3 — Effect of UAV Mobility", fontsize=12)
    finalize(fig, "fig3_family_S.png")

# ─────────────────────────────────────────────────────────────────────────────
# Fig 4 — Family L: PDR & Delay vs Traffic Load
# ─────────────────────────────────────────────────────────────────────────────
def fig_L():
    rows = load_csv("family_L.csv")
    if not rows: return
    agg = aggregate(rows, None,
                    ["deliveryRatio","avgDelayMs","throughputMbps"],
                    scenario_prefix="I")
    # Convert pktInterval → pps for readability
    agg_pps = {}
    for interval, v in agg.items():
        pps = round(1.0 / interval, 2) if interval > 0 else 0
        agg_pps[pps] = v
    agg_pps = dict(sorted(agg_pps.items()))

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    plot_metric(axes[0], agg_pps, "deliveryRatio",
                "PDR (%)", "PDR vs Traffic Load")
    axes[0].set_xlabel("Packet Rate (pps)", fontsize=10)
    plot_metric(axes[1], agg_pps, "avgDelayMs",
                "E2E Delay (ms)", "Delay vs Traffic Load")
    axes[1].set_xlabel("Packet Rate (pps)", fontsize=10)
    fig.suptitle("Fig. 4 — Effect of Traffic Load", fontsize=12)
    finalize(fig, "fig4_family_L.png")

# ─────────────────────────────────────────────────────────────────────────────
# Fig 5 — Family E: PDR & Residual Energy vs Initial Energy
# ─────────────────────────────────────────────────────────────────────────────
def fig_E():
    rows = load_csv("family_E.csv")
    if not rows: return
    agg = aggregate(rows, None,
                    ["deliveryRatio","totalEnergyJ","nodesDead"],
                    scenario_prefix="E")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    plot_metric(axes[0], agg, "deliveryRatio",
                "PDR (%)", "PDR vs Initial Energy")
    axes[0].set_xlabel("Initial Energy (J)", fontsize=10)
    plot_metric(axes[1], agg, "totalEnergyJ",
                "Total Energy Consumed (J)", "Energy Consumption vs E₀")
    axes[1].set_xlabel("Initial Energy (J)", fontsize=10)
    fig.suptitle("Fig. 5 — Effect of Initial Energy", fontsize=12)
    finalize(fig, "fig5_family_E.png")

# ─────────────────────────────────────────────────────────────────────────────
# Fig 6 — Family W: PDR vs w4 (QS-QMAODV only)
# ─────────────────────────────────────────────────────────────────────────────
def fig_W():
    rows = load_csv("family_W.csv")
    if not rows: return

    # Parse w4 from scenario tag "W0.20" → 0.20
    w4_data = defaultdict(list)
    for r in rows:
        if r.get("protocol","").strip() != "QSAQMAODV":
            continue
        tag = r.get("scenario", "")
        try:
            w4 = float(tag.lstrip("W"))
        except ValueError:
            continue
        w4_data[w4].append(safe_float(r.get("deliveryRatio")))

    if not w4_data:
        print("  WARNING: no QSAQMAODV data in family_W.csv")
        return

    xs  = sorted(w4_data.keys())
    ys  = [np.mean(w4_data[x]) for x in xs]
    err = [np.std(w4_data[x])  for x in xs]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.errorbar(xs, ys, yerr=err,
                color=COLORS["QSAQMAODV"], marker="D",
                linestyle="-", linewidth=2, markersize=7, capsize=4,
                label="QS-QMAODV")
    # Mark optimal w4=0.20
    if 0.20 in w4_data:
        opt_y = np.mean(w4_data[0.20])
        ax.axvline(0.20, color="gray", linestyle="--", alpha=0.6)
        ax.annotate(f"w4*=0.20\n({opt_y:.1f}%)",
                    xy=(0.20, opt_y), xytext=(0.27, opt_y-2),
                    fontsize=8, color="gray",
                    arrowprops=dict(arrowstyle="->", color="gray"))
    ax.set_xlabel("w4 (Queue Weight)", fontsize=10)
    ax.set_ylabel("PDR (%)", fontsize=10)
    ax.set_title("Fig. 6 — w4 Sensitivity Analysis", fontsize=11, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    finalize(fig, "fig6_family_W.png")

# ─────────────────────────────────────────────────────────────────────────────
# Fig 7 — Family H: PDR & nodesDead vs Energy StdDev (heterogeneous energy)
# ─────────────────────────────────────────────────────────────────────────────
def fig_H():
    rows = load_csv("family_H.csv")
    if not rows: return
    agg = aggregate(rows, None,
                    ["deliveryRatio","nodesDead","avgDelayMs"],
                    scenario_prefix="H")
    if not agg: return
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    plot_metric(axes[0], agg, "deliveryRatio",
                "PDR (%)", "PDR vs Energy Heterogeneity")
    axes[0].set_xlabel("Energy StdDev (J)", fontsize=10)
    plot_metric(axes[1], agg, "nodesDead",
                "Dead Nodes", "Dead Nodes vs Energy Heterogeneity")
    axes[1].set_xlabel("Energy StdDev (J)", fontsize=10)
    fig.suptitle("Fig. 7 — Effect of Heterogeneous Initial Energy", fontsize=12)
    finalize(fig, "fig7_family_H.png")

# ─────────────────────────────────────────────────────────────────────────────
# Fig 8 — Family M: Mixed stress heatmap — PDR across (load x energy)
# ─────────────────────────────────────────────────────────────────────────────
def fig_M():
    rows = load_csv("family_M.csv")
    if not rows: return

    # Parse scenario tag "M_I0.25_E50" → (pktInterval, E0)
    from collections import defaultdict
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        proto = r.get("protocol","").strip()
        if proto not in PROTOCOLS: continue
        tag = r.get("scenario","").strip()
        try:
            parts = tag.split("_")       # ['M', 'I0.25', 'E50']
            pi  = float(parts[1][1:])    # 0.25
            e0  = float(parts[2][1:])    # 50
            pps = round(1.0/pi, 2) if pi > 0 else 0
        except (IndexError, ValueError):
            continue
        data[pps][e0][proto].append(safe_float(r.get("deliveryRatio")))

    pps_vals = sorted(data.keys())
    e0_vals  = sorted(next(iter(data.values())).keys()) if data else []
    if not pps_vals or not e0_vals: return

    # One subplot per protocol pair: QSAQMAODV vs QMAODV — delay
    # Show PDR grouped bar for each (pps, e0) combination
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    x_labels = [f"{p}pps\nE={e}J" for p in pps_vals for e in e0_vals]
    x = np.arange(len(x_labels))
    width = 0.20
    for i, proto in enumerate(PROTOCOLS):
        vals = []
        for p in pps_vals:
            for e in e0_vals:
                v_list = data[p][e].get(proto, [])
                vals.append(np.mean(v_list) if v_list else 0.0)
        axes[0].bar(x + (i-1.5)*width, vals, width,
                    label=LABELS[proto], color=COLORS[proto], alpha=0.85)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(x_labels, fontsize=7)
    axes[0].set_ylabel("PDR (%)", fontsize=10)
    axes[0].set_title("PDR — Mixed Stress Scenarios", fontsize=11, fontweight='bold')
    axes[0].legend(fontsize=8)
    axes[0].grid(True, alpha=0.3, axis='y')

    # Delay subplot
    from collections import defaultdict as dd2
    delay_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        proto = r.get("protocol","").strip()
        if proto not in PROTOCOLS: continue
        tag = r.get("scenario","").strip()
        try:
            parts = tag.split("_")
            pi  = float(parts[1][1:])
            e0  = float(parts[2][1:])
            pps = round(1.0/pi, 2) if pi > 0 else 0
        except (IndexError, ValueError):
            continue
        delay_data[pps][e0][proto].append(safe_float(r.get("avgDelayMs")))

    for i, proto in enumerate(PROTOCOLS):
        vals = []
        for p in pps_vals:
            for e in e0_vals:
                v_list = delay_data[p][e].get(proto, [])
                vals.append(np.mean(v_list) if v_list else 0.0)
        axes[1].bar(x + (i-1.5)*width, vals, width,
                    label=LABELS[proto], color=COLORS[proto], alpha=0.85)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(x_labels, fontsize=7)
    axes[1].set_ylabel("E2E Delay (ms)", fontsize=10)
    axes[1].set_title("Delay — Mixed Stress Scenarios", fontsize=11, fontweight='bold')
    axes[1].legend(fontsize=8)
    axes[1].grid(True, alpha=0.3, axis='y')

    fig.suptitle("Fig. 8 — Mixed Stress: Load × Energy", fontsize=12)
    finalize(fig, "fig8_family_M.png")

# ─────────────────────────────────────────────────────────────────────────────
# Fig 9 — Summary bar chart: PDR & Delay at baseline across families
# ─────────────────────────────────────────────────────────────────────────────
def fig_summary():
    families = [
        ("N (Density)",  "family_N.csv", "N", 15),
        ("S (Speed)",    "family_S.csv", "V", 25),
        ("L (Load)",     "family_L.csv", "I", 0.25),
        ("E (Energy)",   "family_E.csv", "E", 50),
        ("H (Hetero-E)", "family_H.csv", "H", 0),
    ]

    baseline_pdr   = {proto: [] for proto in PROTOCOLS}
    baseline_delay = {proto: [] for proto in PROTOCOLS}

    for label, fname, prefix, baseline_val in families:
        rows = load_csv(fname)
        if not rows:
            for proto in PROTOCOLS:
                baseline_pdr[proto].append(0.0)
                baseline_delay[proto].append(0.0)
            continue
        agg = aggregate(rows, None, ["deliveryRatio","avgDelayMs"],
                        scenario_prefix=prefix)
        if not agg:
            for proto in PROTOCOLS:
                baseline_pdr[proto].append(0.0)
                baseline_delay[proto].append(0.0)
            continue
        keys = np.array(sorted(agg.keys()))
        closest = keys[np.argmin(np.abs(keys - baseline_val))]
        for proto in PROTOCOLS:
            baseline_pdr[proto].append(
                agg[closest].get(proto, {}).get("deliveryRatio", (0,0))[0])
            baseline_delay[proto].append(
                agg[closest].get(proto, {}).get("avgDelayMs", (0,0))[0])

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    fam_labels = [f[0] for f in families]
    x = np.arange(len(fam_labels))
    width = 0.18

    for i, proto in enumerate(PROTOCOLS):
        pdr_vals   = baseline_pdr[proto]
        delay_vals = baseline_delay[proto]
        if len(pdr_vals) == len(fam_labels):
            axes[0].bar(x + (i-1.5)*width, pdr_vals, width,
                        label=LABELS[proto], color=COLORS[proto], alpha=0.85)
            axes[1].bar(x + (i-1.5)*width, delay_vals, width,
                        label=LABELS[proto], color=COLORS[proto], alpha=0.85)

    for ax, ylabel, title in zip(axes,
            ["PDR (%) at Baseline", "E2E Delay (ms) at Baseline"],
            ["PDR Comparison", "Delay Comparison"]):
        ax.set_xticks(x)
        ax.set_xticklabels(fam_labels, fontsize=8)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(title, fontsize=11, fontweight='bold')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3, axis='y')

    fig.suptitle("Fig. 9 — Summary: PDR & Delay Across All Families", fontsize=12)
    finalize(fig, "fig9_summary.png")

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
print(f"Results dir : {RESULTS_DIR}")
print(f"Output dir  : {OUT_DIR}")
print()

fig_N()
fig_S()
fig_L()
fig_E()
fig_W()
fig_H()
fig_M()
fig_summary()

print()
print("Done.")
