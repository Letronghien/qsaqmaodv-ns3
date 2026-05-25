#!/usr/bin/env python3
"""
Vẽ 5 chart từ CSV experiment results:
  Fig. 5: Delivery Ratio vs # nodes
  Fig. 6: End-to-end Delay vs # nodes
  Fig. 7: Throughput vs # nodes
  Fig. 8: Routing Overhead vs # nodes
  Fig. 9: Total Energy Consumed vs # nodes (BONUS, không có trong paper gốc)

Usage: python3 plot-experiments.py <csv-file> <output-dir>
"""

import sys
import csv
import os
from collections import defaultdict

if len(sys.argv) < 3:
    print("Usage: python3 plot-experiments.py <csv> <out-dir>")
    sys.exit(1)

CSV = sys.argv[1]
OUT_DIR = sys.argv[2]

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    print("matplotlib chưa cài. Cài bằng: pip install matplotlib --break-system-packages")
    sys.exit(1)

# Read CSV
rows = list(csv.DictReader(open(CSV)))
if not rows:
    print(f"CSV rỗng: {CSV}")
    sys.exit(1)

# Aggregate: (variant, numNodes) -> list of values per metric
agg = defaultdict(lambda: defaultdict(list))
for r in rows:
    proto = r["protocol"]
    mp = r["maxPaths"]
    label = f"{proto}-{mp}" if proto in ("PMAODV", "AOMDV", "QMAODV", "SAQMAODV") else proto
    key = (label, int(r["numNodes"]))
    for m in ("deliveryRatio", "avgDelayMs", "throughputMbps",
              "routingOverhead", "totalEnergyJ"):
        agg[key][m].append(float(r[m]))

# Compute means: variant -> {numNodes: {metric: mean}}
data = defaultdict(dict)
for (label, n), metrics in agg.items():
    data[label][n] = {m: sum(v) / len(v) for m, v in metrics.items()}

# Plot config — 14 variants (added SAQMAODV-2/3/4; DSR off by default).
INCLUDE_DSR = False
PROTOCOLS_ORDER = ["AODV", "DSDV",
                   "AOMDV-2", "AOMDV-3", "AOMDV-4",
                   "PMAODV-2", "PMAODV-3", "PMAODV-4",
                   "QMAODV-2", "QMAODV-3", "QMAODV-4",
                   "SAQMAODV-2", "SAQMAODV-3", "SAQMAODV-4"]
if INCLUDE_DSR:
    PROTOCOLS_ORDER.insert(2, "DSR")
COLORS = {
    "AODV":         "#e41a1c",   # red
    "DSDV":         "#377eb8",   # blue
    "DSR":          "#4daf4a",   # green
    "AOMDV-2":      "#cab2d6",   # light purple
    "AOMDV-3":      "#984ea3",   # purple
    "AOMDV-4":      "#6a3d9a",   # dark purple
    "PMAODV-2":     "#ff7f00",   # orange
    "PMAODV-3":     "#000000",   # black
    "PMAODV-4":     "#a65628",   # brown
    "QMAODV-2":     "#66c2a5",   # teal
    "QMAODV-3":     "#1b9e77",   # dark teal
    "QMAODV-4":     "#005824",   # forest
    "SAQMAODV-2":   "#fee08b",   # gold
    "SAQMAODV-3":   "#f46d43",   # bright orange-red (★ highlight)
    "SAQMAODV-4":   "#a50026",   # dark crimson
}
MARKERS = {
    "AODV":       "o", "DSDV": "s", "DSR": "^",
    "AOMDV-2":    "X", "AOMDV-3":    "D", "AOMDV-4":    "p",
    "PMAODV-2":   "v", "PMAODV-3":   "*", "PMAODV-4":   "P",
    "QMAODV-2":   "h", "QMAODV-3":   "8", "QMAODV-4":   "H",
    "SAQMAODV-2": "<", "SAQMAODV-3": ">", "SAQMAODV-4": "d",
}

METRICS = [
    ("deliveryRatio",   "Delivery Ratio (%)",       "Fig.5_DeliveryRatio.png",  "Delivery Ratio"),
    ("avgDelayMs",      "End-to-end Delay (ms)",    "Fig.6_EndToEndDelay.png",  "End-to-end Delay"),
    ("throughputMbps",  "Throughput (Mbps)",        "Fig.7_Throughput.png",     "Throughput"),
    ("routingOverhead", "Routing Overhead (pkts)",  "Fig.8_RoutingOverhead.png","Routing Overhead"),
    ("totalEnergyJ",    "Total Energy Consumed (J)","Fig.9_Energy.png",         "Total Energy"),
]

available = [v for v in PROTOCOLS_ORDER if v in data]
if not available:
    print(f"Không có protocol nào có data. Available labels: {list(data.keys())}")
    sys.exit(1)

print(f"Plotting {len(available)} variants: {available}")
print(f"Output directory: {OUT_DIR}")

for metric_key, ylabel, fname, title in METRICS:
    fig, ax = plt.subplots(figsize=(8, 5))

    for label in available:
        ns = sorted(data[label].keys())
        if not ns:
            continue
        ys = [data[label][n][metric_key] for n in ns]
        ax.plot(ns, ys,
                marker=MARKERS.get(label, "o"),
                color=COLORS.get(label, "gray"),
                label=label,
                linewidth=1.5, markersize=6)

    ax.set_xlabel("Number of UAVs", fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(f"{title} vs Number of UAVs", fontsize=12)
    ax.legend(loc="best", fontsize=9, ncol=2)
    ax.grid(True, alpha=0.3)
    if data and ns:
        ax.set_xticks(range(min(ns), max(ns) + 1, max(1, (max(ns)-min(ns))//8)))

    out_path = os.path.join(OUT_DIR, fname)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out_path}")

print("\nDone. 5 charts saved.")
