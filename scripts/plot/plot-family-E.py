#!/usr/bin/env python3
"""
plot-family-E.py  —  Family E: sweep initial energy (J)
Usage: python3 plot-family-E.py <family_E_energy.csv> <output-dir>
"""
import sys, csv, os, re
from collections import defaultdict

if len(sys.argv) < 3:
    print("Usage: python3 plot-family-E.py <csv> <out-dir>")
    sys.exit(1)

CSV_FILE, OUT_DIR = sys.argv[1], sys.argv[2]
os.makedirs(OUT_DIR, exist_ok=True)

import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

rows = list(csv.DictReader(open(CSV_FILE)))
if not rows: print(f"[ERROR] CSV rỗng: {CSV_FILE}"); sys.exit(1)

agg = defaultdict(lambda: defaultdict(list))
for r in rows:
    proto = r["protocol"]
    mp    = r.get("maxPaths", "1")
    label = f"{proto}-{mp}" if proto in ("PMAODV","AOMDV","QMAODV","QSAQMAODV") else proto
    # Lấy E0 từ scenario tag: "E10" → 10, "E50" → 50
    m = re.match(r"E(\d+(?:\.\d+)?)", r.get("scenario",""))
    if not m: continue
    e0 = float(m.group(1))
    for metric in ("deliveryRatio","avgDelayMs","throughputMbps","routingOverhead","totalEnergyJ","nodesDead"):
        try: agg[(label, e0)][metric].append(float(r[metric]))
        except: pass

data = defaultdict(dict)
for (label, e0), metrics in agg.items():
    data[label][e0] = {m: sum(v)/len(v) for m, v in metrics.items()}

PROTOCOLS  = ["AODV","AOMDV-3","PMAODV-3","QMAODV-3","QSAQMAODV-3"]
COLORS     = {"AODV":"#e41a1c","AOMDV-3":"#984ea3","PMAODV-3":"#377eb8","QMAODV-3":"#1b9e77","QSAQMAODV-3":"#ff7f00"}
MARKERS    = {"AODV":"o","AOMDV-3":"D","PMAODV-3":"s","QMAODV-3":"8","QSAQMAODV-3":"*"}
LINEWIDTHS = {k:1.5 for k in PROTOCOLS}; LINEWIDTHS["QSAQMAODV-3"] = 2.5
SIZES      = {k:6 for k in PROTOCOLS};   SIZES["QSAQMAODV-3"] = 11

METRICS = [
    ("deliveryRatio",   "Delivery Ratio (%)",        "Fig_E_1_DeliveryRatio.png"),
    ("avgDelayMs",      "End-to-end Delay (ms)",     "Fig_E_2_Delay.png"),
    ("throughputMbps",  "Throughput (Mbps)",         "Fig_E_3_Throughput.png"),
    ("routingOverhead", "Routing Overhead (pkts)",   "Fig_E_4_Overhead.png"),
    ("totalEnergyJ",    "Total Energy Consumed (J)", "Fig_E_5_Energy.png"),
    ("nodesDead",       "Dead Nodes",                "Fig_E_6_DeadNodes.png"),
]

available = [p for p in PROTOCOLS if p in data]
print(f"Protocols: {available}\nOutput:    {OUT_DIR}\n")

for metric_key, ylabel, fname in METRICS:
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for label in available:
        xs = sorted(data[label].keys())
        ys = [data[label][x].get(metric_key, 0) for x in xs]
        ax.plot(xs, ys, marker=MARKERS.get(label,"o"), color=COLORS.get(label,"gray"),
                label=label, linewidth=LINEWIDTHS.get(label,1.5), markersize=SIZES.get(label,6))
    ax.set_xlabel("Initial Energy per Node (J)", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(f"{ylabel} vs Initial Energy", fontsize=13)
    ax.legend(loc="best", fontsize=11); ax.grid(True, alpha=0.3)
    xs_all = sorted({x for p in available for x in data[p].keys()})
    if xs_all: ax.set_xticks(xs_all)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, fname), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")

print("\nPDR (%) by Energy:")
xs_all = sorted({x for p in available for x in data[p].keys()})
print(f"{'Protocol':<16} " + "  ".join(f"E={int(x)}J" for x in xs_all))
for p in available:
    cells = [f"{data[p].get(x,{}).get('deliveryRatio',0):>7.2f}" for x in xs_all]
    print(f"{p:<16} " + "  ".join(cells))
