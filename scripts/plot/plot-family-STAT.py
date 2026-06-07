#!/usr/bin/env python3
"""
plot-family-STAT.py  —  Statistical validation: bar chart mean ± std (50 seeds)
Usage: python3 plot-family-STAT.py <stat_baseline.csv> <output-dir>
"""
import sys, csv, os, math
from collections import defaultdict

if len(sys.argv) < 3:
    print("Usage: python3 plot-family-STAT.py <csv> <out-dir>")
    sys.exit(1)

CSV_FILE, OUT_DIR = sys.argv[1], sys.argv[2]
os.makedirs(OUT_DIR, exist_ok=True)

import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

rows = list(csv.DictReader(open(CSV_FILE)))
if not rows: print(f"[ERROR] CSV rỗng: {CSV_FILE}"); sys.exit(1)

agg = defaultdict(lambda: defaultdict(list))
for r in rows:
    proto = r["protocol"]
    mp    = r.get("maxPaths", "1")
    label = f"{proto}-{mp}" if proto in ("PMAODV","AOMDV","QMAODV","QSAQMAODV") else proto
    for m in ("deliveryRatio","avgDelayMs","throughputMbps","routingOverhead","totalEnergyJ"):
        try: agg[label][m].append(float(r[m]))
        except: pass

PROTOCOLS = ["AODV","AOMDV-3","PMAODV-3","QMAODV-3","QSAQMAODV-3"]
COLORS    = {"AODV":"#e41a1c","AOMDV-3":"#984ea3","PMAODV-3":"#377eb8","QMAODV-3":"#1b9e77","QSAQMAODV-3":"#ff7f00"}

available = [p for p in PROTOCOLS if p in agg]
print(f"Protocols: {available}\nSeeds per protocol: {[len(agg[p]['deliveryRatio']) for p in available]}\n")

METRICS = [
    ("deliveryRatio",   "Delivery Ratio (%)",        "Fig_STAT_1_PDR.png"),
    ("avgDelayMs",      "End-to-end Delay (ms)",     "Fig_STAT_2_Delay.png"),
    ("throughputMbps",  "Throughput (Mbps)",         "Fig_STAT_3_Throughput.png"),
    ("routingOverhead", "Routing Overhead (pkts)",   "Fig_STAT_4_Overhead.png"),
    ("totalEnergyJ",    "Total Energy Consumed (J)", "Fig_STAT_5_Energy.png"),
]

x = np.arange(len(available))
width = 0.6

for metric_key, ylabel, fname in METRICS:
    means = [np.mean(agg[p][metric_key]) if agg[p][metric_key] else 0 for p in available]
    stds  = [np.std(agg[p][metric_key])  if agg[p][metric_key] else 0 for p in available]
    colors = [COLORS.get(p, "gray") for p in available]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    bars = ax.bar(x, means, width, yerr=stds, capsize=5,
                  color=colors, alpha=0.85, edgecolor="black", linewidth=0.7)

    # Ghi giá trị lên mỗi cột
    for bar, mean in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(stds)*0.05,
                f"{mean:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_xlabel("Protocol", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(f"{ylabel} — Statistical Validation (mean ± std)", fontsize=13)
    ax.set_xticks(x); ax.set_xticklabels(available, fontsize=11)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, fname), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")

# Summary table
print("\nStatistical Summary:")
print(f"{'Protocol':<16} {'PDR mean':>10} {'PDR std':>9} {'Delay mean':>11} {'Thr mean':>10}")
print("-" * 60)
for p in available:
    pdr  = agg[p]["deliveryRatio"]
    dly  = agg[p]["avgDelayMs"]
    thr  = agg[p]["throughputMbps"]
    print(f"{p:<16} {np.mean(pdr):>10.3f} {np.std(pdr):>9.3f} {np.mean(dly):>11.3f} {np.mean(thr):>10.5f}")
