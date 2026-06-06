#!/usr/bin/env python3
"""
plot-family-W.py — Family W: sensitivity analysis w3 cho QSAQMAODV
Usage: python3 plot-family-W.py <family_W_weight.csv> <output-dir>
"""
import sys, csv, os
from collections import defaultdict

if len(sys.argv) < 3:
    print("Usage: python3 plot-family-W.py <csv> <out-dir>")
    sys.exit(1)

CSV_FILE, OUT_DIR = sys.argv[1], sys.argv[2]
os.makedirs(OUT_DIR, exist_ok=True)

try:
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    print("pip install matplotlib --break-system-packages"); sys.exit(1)

rows = list(csv.DictReader(open(CSV_FILE)))
if not rows:
    print(f"[ERROR] CSV rong: {CSV_FILE}"); sys.exit(1)

agg = defaultdict(lambda: defaultdict(list))
for r in rows:
    tag = r.get("scenario", "")
    if not tag.startswith("W"):
        continue
    try:
        w3 = float(tag[1:])
    except ValueError:
        continue
    for m in ("deliveryRatio","avgDelayMs","throughputMbps","routingOverhead","totalEnergyJ"):
        try:
            agg[w3][m].append(float(r[m]))
        except (KeyError, ValueError):
            pass

w3_vals = sorted(agg.keys())
if not w3_vals:
    print("[ERROR] Khong co data W trong CSV"); sys.exit(1)

def avg(lst): return sum(lst)/len(lst) if lst else 0

seeds = len(agg[w3_vals[0]].get("deliveryRatio", []))
print(f"w3 values: {w3_vals}")
print(f"Seeds per w3: {seeds}")

METRICS = [
    ("deliveryRatio",   "Delivery Ratio (%)",        "Fig_W_1_PDR.png"),
    ("avgDelayMs",      "End-to-end Delay (ms)",     "Fig_W_2_Delay.png"),
    ("throughputMbps",  "Throughput (Mbps)",         "Fig_W_3_Throughput.png"),
    ("routingOverhead", "Routing Overhead (pkts)",   "Fig_W_4_Overhead.png"),
    ("totalEnergyJ",    "Total Energy Consumed (J)", "Fig_W_5_Energy.png"),
]

for metric_key, ylabel, fname in METRICS:
    ys = [avg(agg[w3][metric_key]) for w3 in w3_vals]

    if metric_key in ("deliveryRatio", "throughputMbps"):
        best_i = ys.index(max(ys))
    else:
        best_i = ys.index(min(ys))

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(w3_vals, ys, marker="o", color="#ff7f00",
            linewidth=2.5, markersize=8, label="QSAQMAODV")
    ax.axvline(w3_vals[best_i], color="gray", linestyle="--", alpha=0.6,
               label=f"Best w3={w3_vals[best_i]:.2f}")
    ax.scatter([w3_vals[best_i]], [ys[best_i]],
               color="red", zorder=5, s=120)

    ax.set_xlabel("Energy weight w3", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(f"{ylabel} vs Energy Weight w3 (QSAQMAODV, N=15)", fontsize=12)
    ax.set_xticks(w3_vals)
    ax.set_xticklabels([f"{v:.2f}" for v in w3_vals])
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    out = os.path.join(OUT_DIR, fname)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")

# Summary table
print("\n" + "="*60)
print(f"{'w3':>6} {'PDR%':>8} {'Delay(ms)':>10} {'Thr(Mbps)':>10} {'Overhead':>10} {'Energy(J)':>10}")
print("-"*60)
for w3 in w3_vals:
    pdr = avg(agg[w3]["deliveryRatio"])
    dly = avg(agg[w3]["avgDelayMs"])
    thr = avg(agg[w3]["throughputMbps"])
    ovh = avg(agg[w3]["routingOverhead"])
    ene = avg(agg[w3]["totalEnergyJ"])
    marker = " <-- best PDR" if w3 == w3_vals[[avg(agg[v]["deliveryRatio"]) for v in w3_vals].index(max([avg(agg[v]["deliveryRatio"]) for v in w3_vals]))] else ""
    print(f"{w3:>6.2f} {pdr:>8.2f} {dly:>10.2f} {thr:>10.4f} {ovh:>10.1f} {ene:>10.2f}{marker}")
print("="*60)
print(f"\nChay xong. Bieu do: {OUT_DIR}")
