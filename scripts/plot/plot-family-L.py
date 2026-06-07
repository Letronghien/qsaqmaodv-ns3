#!/usr/bin/env python3
"""
plot-family-L.py  —  Family L: sweep pktInterval (traffic load)
5 protocols: AODV / AOMDV-3 / PMAODV-3 / QMAODV-3 / QSAQMAODV-3

Usage:
    python3 plot-family-L.py <family_L_load.csv> <output-dir>
"""
import sys, csv, os
from collections import defaultdict

if len(sys.argv) < 3:
    print("Usage: python3 plot-family-L.py <csv> <out-dir>")
    sys.exit(1)

CSV_FILE = sys.argv[1]
OUT_DIR  = sys.argv[2]
os.makedirs(OUT_DIR, exist_ok=True)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    print("pip install matplotlib --break-system-packages")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Đọc CSV, aggregate theo (label, pktInterval)
# ---------------------------------------------------------------------------
rows = list(csv.DictReader(open(CSV_FILE)))
if not rows:
    print(f"[ERROR] CSV rỗng: {CSV_FILE}")
    sys.exit(1)

agg = defaultdict(lambda: defaultdict(list))
for r in rows:
    proto = r["protocol"]
    mp    = r.get("maxPaths", "1")
    label = f"{proto}-{mp}" if proto in ("PMAODV", "AOMDV", "QMAODV", "QSAQMAODV") else proto

    try:
        pi = float(r["pktInterval"])
    except (KeyError, ValueError):
        continue

    for m in ("deliveryRatio", "avgDelayMs", "throughputMbps",
              "routingOverhead", "totalEnergyJ"):
        try:
            agg[(label, pi)][m].append(float(r[m]))
        except (KeyError, ValueError):
            pass

# Tính trung bình
data = defaultdict(dict)
for (label, pi), metrics in agg.items():
    data[label][pi] = {m: sum(v) / len(v) for m, v in metrics.items()}

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
PROTOCOLS = ["AODV", "AOMDV-3", "PMAODV-3", "QMAODV-3", "QSAQMAODV-3"]

COLORS = {
    "AODV":        "#e41a1c",
    "AOMDV-3":     "#984ea3",
    "PMAODV-3":    "#377eb8",
    "QMAODV-3":    "#1b9e77",
    "QSAQMAODV-3": "#ff7f00",
}
MARKERS = {
    "AODV":        "o",
    "AOMDV-3":     "D",
    "PMAODV-3":    "s",
    "QMAODV-3":    "8",
    "QSAQMAODV-3": "*",
}
LINEWIDTHS = {k: 1.5 for k in PROTOCOLS}
LINEWIDTHS["QSAQMAODV-3"] = 2.5
SIZES = {k: 6 for k in PROTOCOLS}
SIZES["QSAQMAODV-3"] = 11

METRICS = [
    ("deliveryRatio",   "Delivery Ratio (%)",        "Fig_L_1_DeliveryRatio.png"),
    ("avgDelayMs",      "End-to-end Delay (ms)",     "Fig_L_2_Delay.png"),
    ("throughputMbps",  "Throughput (Mbps)",         "Fig_L_3_Throughput.png"),
    ("routingOverhead", "Routing Overhead (pkts)",   "Fig_L_4_Overhead.png"),
    ("totalEnergyJ",    "Total Energy Consumed (J)", "Fig_L_5_Energy.png"),
]

# ---------------------------------------------------------------------------
# Vẽ
# ---------------------------------------------------------------------------
available = [p for p in PROTOCOLS if p in data]
if not available:
    print(f"[ERROR] Không tìm thấy protocol nào. Có trong CSV: {list(data.keys())}")
    sys.exit(1)

print(f"Protocols: {available}")
print(f"Output:    {OUT_DIR}\n")

for metric_key, ylabel, fname in METRICS:
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for label in available:
        # Sort theo pktInterval tăng dần (load giảm dần)
        pis = sorted(data[label].keys())
        ys  = [data[label][pi].get(metric_key, 0) for pi in pis]
        ax.plot(pis, ys,
                marker=MARKERS.get(label, "o"),
                color=COLORS.get(label, "gray"),
                label=label,
                linewidth=LINEWIDTHS.get(label, 1.5),
                markersize=SIZES.get(label, 6))

    ax.set_xlabel("Packet Interval (s)  [← higher load  |  lower load →]", fontsize=11)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(f"{ylabel} vs Traffic Load (pktInterval)", fontsize=13)
    ax.legend(loc="best", fontsize=11)
    ax.grid(True, alpha=0.3)

    pis_all = sorted({pi for p in available for pi in data[p].keys()})
    if pis_all:
        ax.set_xticks(pis_all)
        ax.set_xticklabels([str(pi) for pi in pis_all])

    fig.tight_layout()
    out_path = os.path.join(OUT_DIR, fname)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------
pis_all = sorted({pi for p in available for pi in data[p].keys()})
print()
print("=" * 72)
print(" PDR (%) by pktInterval")
print("=" * 72)
print(f"{'Protocol':<16} " + "  ".join(f"PI={pi}" for pi in pis_all))
print("-" * 72)
for p in available:
    cells = []
    for pi in pis_all:
        v = data[p].get(pi, {}).get("deliveryRatio")
        cells.append(f"{v:>7.2f}" if v is not None else f"{'—':>7}")
    print(f"{p:<16} " + "  ".join(cells))
