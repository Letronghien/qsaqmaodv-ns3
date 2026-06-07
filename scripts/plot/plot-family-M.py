#!/usr/bin/env python3
"""
plot-family-M.py  —  Family M: mixed Load×Energy (3×3 heatmap + grouped lines)
Usage: python3 plot-family-M.py <family_M_mixed.csv> <output-dir>
"""
import sys, csv, os, re
from collections import defaultdict

if len(sys.argv) < 3:
    print("Usage: python3 plot-family-M.py <csv> <out-dir>")
    sys.exit(1)

CSV_FILE, OUT_DIR = sys.argv[1], sys.argv[2]
os.makedirs(OUT_DIR, exist_ok=True)

import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

rows = list(csv.DictReader(open(CSV_FILE)))
if not rows: print(f"[ERROR] CSV rỗng: {CSV_FILE}"); sys.exit(1)

# Parse scenario "M_I{pi}_E{e0}"
agg = defaultdict(lambda: defaultdict(list))
for r in rows:
    proto = r["protocol"]
    mp    = r.get("maxPaths","1")
    label = f"{proto}-{mp}" if proto in ("PMAODV","AOMDV","QMAODV","QSAQMAODV") else proto
    m = re.match(r"M_I([\d.]+)_E(\d+)", r.get("scenario",""))
    if not m: continue
    pi, e0 = float(m.group(1)), float(m.group(2))
    for metric in ("deliveryRatio","avgDelayMs","throughputMbps","routingOverhead","totalEnergyJ"):
        try: agg[(label, pi, e0)][metric].append(float(r[metric]))
        except: pass

data = defaultdict(dict)
for (label, pi, e0), metrics in agg.items():
    data[label][(pi, e0)] = {m: sum(v)/len(v) for m, v in metrics.items()}

PROTOCOLS  = ["AODV","AOMDV-3","PMAODV-3","QMAODV-3","QSAQMAODV-3"]
COLORS     = {"AODV":"#e41a1c","AOMDV-3":"#984ea3","PMAODV-3":"#377eb8","QMAODV-3":"#1b9e77","QSAQMAODV-3":"#ff7f00"}
MARKERS    = {"AODV":"o","AOMDV-3":"D","PMAODV-3":"s","QMAODV-3":"8","QSAQMAODV-3":"*"}
LINEWIDTHS = {k:1.5 for k in PROTOCOLS}; LINEWIDTHS["QSAQMAODV-3"] = 2.5
SIZES      = {k:6 for k in PROTOCOLS};   SIZES["QSAQMAODV-3"] = 11

available = [p for p in PROTOCOLS if p in data]
all_keys  = sorted({k for p in available for k in data[p].keys()})
pis  = sorted({k[0] for k in all_keys})
e0s  = sorted({k[1] for k in all_keys})

print(f"Protocols: {available}\npktIntervals: {pis}\nEnergies: {e0s}\nOutput: {OUT_DIR}\n")

METRICS = [
    ("deliveryRatio",   "Delivery Ratio (%)",        "Fig_M"),
    ("avgDelayMs",      "End-to-end Delay (ms)",     "Fig_M"),
    ("throughputMbps",  "Throughput (Mbps)",         "Fig_M"),
]

# ── Plot 1: Grouped lines per energy level (PDR vs pktInterval) ──
for metric_key, ylabel, _ in METRICS:
    fig, axes = plt.subplots(1, len(e0s), figsize=(5*len(e0s), 5), sharey=True)
    if len(e0s) == 1: axes = [axes]
    for ax, e0 in zip(axes, e0s):
        for label in available:
            ys = [data[label].get((pi, e0), {}).get(metric_key, None) for pi in pis]
            valid = [(x, y) for x, y in zip(pis, ys) if y is not None]
            if not valid: continue
            xs_, ys_ = zip(*valid)
            ax.plot(xs_, ys_, marker=MARKERS.get(label,"o"), color=COLORS.get(label,"gray"),
                    label=label, linewidth=LINEWIDTHS.get(label,1.5), markersize=SIZES.get(label,6))
        ax.set_title(f"E₀={int(e0)}J", fontsize=12)
        ax.set_xlabel("pktInterval (s)", fontsize=10)
        if ax == axes[0]: ax.set_ylabel(ylabel, fontsize=11)
        ax.set_xticks(pis); ax.grid(True, alpha=0.3)
    axes[-1].legend(loc="best", fontsize=9)
    fig.suptitle(f"{ylabel} — Mixed Load×Energy", fontsize=13)
    fig.tight_layout()
    safe = metric_key.replace("Ratio","PDR").replace("Mbps","Thr").replace("Ms","Delay").replace("routingOverhead","Overhead")
    fname = f"Fig_M_{safe}.png"
    fig.savefig(os.path.join(OUT_DIR, fname), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fname}")

# ── Plot 2: Heatmap PDR — QSAQMAODV vs AODV ──
if "QSAQMAODV-3" in available and "AODV" in available and pis and e0s:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, proto in zip(axes, ["AODV", "QSAQMAODV-3"]):
        mat = np.array([[data[proto].get((pi,e0),{}).get("deliveryRatio",0)
                         for e0 in e0s] for pi in pis])
        im = ax.imshow(mat, aspect="auto", cmap="YlGn", vmin=40, vmax=100)
        ax.set_xticks(range(len(e0s))); ax.set_xticklabels([f"{int(e)}J" for e in e0s])
        ax.set_yticks(range(len(pis)));  ax.set_yticklabels([f"{pi}s" for pi in pis])
        ax.set_xlabel("Initial Energy (J)"); ax.set_ylabel("pktInterval (s)")
        ax.set_title(f"PDR (%) — {proto}")
        for i in range(len(pis)):
            for j in range(len(e0s)):
                ax.text(j, i, f"{mat[i,j]:.1f}", ha="center", va="center", fontsize=8)
        plt.colorbar(im, ax=ax)
    fig.suptitle("Heatmap PDR: AODV vs QSAQMAODV-3", fontsize=13)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "Fig_M_Heatmap_PDR.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved: Fig_M_Heatmap_PDR.png")
