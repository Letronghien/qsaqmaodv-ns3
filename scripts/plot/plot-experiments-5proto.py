#!/usr/bin/env python3
"""
plot-experiments-5proto.py
==========================

Phiên bản 5-protocol cho paper SA-QMAODV final.
Vẽ AODV, AOMDV-3, PMAODV-3, QMAODV-3, SAQMAODV-3.

Usage: python3 plot-experiments-5proto.py <csv-file> <output-dir>
"""

import sys, csv, os
from collections import defaultdict

if len(sys.argv) < 3:
    print("Usage: python3 plot-experiments-5proto.py <csv> <out-dir>")
    sys.exit(1)

CSV     = sys.argv[1]
OUT_DIR = sys.argv[2]
os.makedirs(OUT_DIR, exist_ok=True)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    print("pip install matplotlib --break-system-packages")
    sys.exit(1)

rows = list(csv.DictReader(open(CSV)))
if not rows:
    print(f"CSV empty: {CSV}")
    sys.exit(1)

agg = defaultdict(lambda: defaultdict(list))
for r in rows:
    proto = r["protocol"]
    mp    = r.get("maxPaths", "1")
    label = f"{proto}-{mp}" if proto in ("PMAODV", "AOMDV", "QMAODV", "SAQMAODV") else proto
    key = (label, int(r["numNodes"]))
    for m in ("deliveryRatio", "avgDelayMs", "throughputMbps",
              "routingOverhead", "totalEnergyJ"):
        try:
            agg[key][m].append(float(r[m]))
        except (KeyError, ValueError):
            pass

data = defaultdict(dict)
for (label, n), metrics in agg.items():
    data[label][n] = {m: sum(v) / len(v) for m, v in metrics.items()}

# 5 protocols paper
PROTOCOLS = ["AODV", "AOMDV-3", "PMAODV-3", "QMAODV-3", "SAQMAODV-3"]

COLORS = {
    "AODV":       "#e41a1c",   # red
    "AOMDV-3":    "#984ea3",   # purple
    "PMAODV-3":   "#377eb8",   # blue
    "QMAODV-3":   "#1b9e77",   # dark teal
    "SAQMAODV-3": "#ff7f00",   # orange (highlight)
}
MARKERS = {
    "AODV":       "o",
    "AOMDV-3":    "D",
    "PMAODV-3":   "s",
    "QMAODV-3":   "8",
    "SAQMAODV-3": "*",
}
LINEWIDTHS = {
    "AODV":       1.5,
    "AOMDV-3":    1.5,
    "PMAODV-3":   1.5,
    "QMAODV-3":   1.5,
    "SAQMAODV-3": 2.5,    # SA dày hơn
}
SIZES = {
    "AODV":       6,
    "AOMDV-3":    6,
    "PMAODV-3":   6,
    "QMAODV-3":   6,
    "SAQMAODV-3": 11,     # SA marker to hơn
}

METRICS = [
    ("deliveryRatio",   "Delivery Ratio (%)",       "Fig.5_DeliveryRatio.png",  "Delivery Ratio"),
    ("avgDelayMs",      "End-to-end Delay (ms)",    "Fig.6_EndToEndDelay.png",  "End-to-end Delay"),
    ("throughputMbps",  "Throughput (Mbps)",        "Fig.7_Throughput.png",     "Throughput"),
    ("routingOverhead", "Routing Overhead (pkts)",  "Fig.8_RoutingOverhead.png","Routing Overhead"),
    ("totalEnergyJ",    "Total Energy Consumed (J)","Fig.9_Energy.png",         "Total Energy"),
]

available = [p for p in PROTOCOLS if p in data]
if not available:
    print(f"Không có protocol nào trong {PROTOCOLS} có data. Available: {list(data.keys())}")
    sys.exit(1)

print(f"Plotting {len(available)} protocols: {available}")
print(f"Output: {OUT_DIR}")

for metric_key, ylabel, fname, title in METRICS:
    fig, ax = plt.subplots(figsize=(8.5, 5.2))

    for label in available:
        ns = sorted(data[label].keys())
        if not ns:
            continue
        ys = [data[label][n].get(metric_key, 0) for n in ns]
        ax.plot(ns, ys,
                marker=MARKERS.get(label, "o"),
                color=COLORS.get(label, "gray"),
                label=label,
                linewidth=LINEWIDTHS.get(label, 1.5),
                markersize=SIZES.get(label, 6))

    ax.set_xlabel("Number of UAVs", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(f"{title} vs Number of UAVs", fontsize=13)
    ax.legend(loc="best", fontsize=11)
    ax.grid(True, alpha=0.3)
    if ns:
        ax.set_xticks(range(min(ns), max(ns) + 1, max(1, (max(ns)-min(ns))//8)))

    out_path = os.path.join(OUT_DIR, fname)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out_path}")

print("\nDone. 5 charts saved (5 protocols: paper full set).")

# Print summary table
print()
print("=" * 70)
print(" Summary: PDR (%) by N")
print("=" * 70)
ns_all = sorted({n for p in available for n in data[p].keys()})
print(f"{'proto':<14} " + " ".join(f"N={n:>3}" for n in ns_all))
print("-" * 70)
for p in available:
    cells = []
    for n in ns_all:
        v = data[p].get(n, {}).get("deliveryRatio")
        cells.append(f"{v:>6.2f}" if v is not None else f"{'—':>6}")
    print(f"{p:<14} " + " ".join(cells))
