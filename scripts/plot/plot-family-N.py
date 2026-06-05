#!/usr/bin/env python3
"""
plot-family-N.py  —  Family N: 5 protocols AODV / AOMDV-3 / PMAODV-3 / QMAODV-3 / QSAQMAODV-3
Usage:
    python3 plot-family-N.py <family_N_nodes.csv> <output-dir>
"""
import sys, csv, os
from collections import defaultdict

if len(sys.argv) < 3:
    print("Usage: python3 plot-family-N.py <csv> <out-dir>")
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
# Đọc CSV, aggregate theo (label, numNodes)
# ---------------------------------------------------------------------------
rows = list(csv.DictReader(open(CSV_FILE)))
if not rows:
    print(f"[ERROR] CSV rỗng: {CSV_FILE}")
    sys.exit(1)

agg = defaultdict(lambda: defaultdict(list))
for r in rows:
    proto = r["protocol"]
    mp    = r.get("maxPaths", "1")
    # Label theo paper: đa đường thêm hậu tố -3
    if proto in ("PMAODV", "AOMDV", "QMAODV", "QSAQMAODV"):
        label = f"{proto}-{mp}"
    else:
        label = proto   # AODV, DSDV

    try:
        n = int(r["numNodes"])
    except (KeyError, ValueError):
        continue

    for m in ("deliveryRatio", "avgDelayMs", "throughputMbps",
              "routingOverhead", "totalEnergyJ"):
        try:
            agg[(label, n)][m].append(float(r[m]))
        except (KeyError, ValueError):
            pass

# Tính trung bình
data = defaultdict(dict)
for (label, n), metrics in agg.items():
    data[label][n] = {m: sum(v) / len(v) for m, v in metrics.items()}

# ---------------------------------------------------------------------------
# Style — QSAQMAODV-3 là protocol chính, highlight đậm hơn
# ---------------------------------------------------------------------------
PROTOCOLS = ["AODV", "AOMDV-3", "PMAODV-3", "QMAODV-3", "QSAQMAODV-3"]

COLORS = {
    "AODV":          "#e41a1c",   # đỏ
    "AOMDV-3":       "#984ea3",   # tím
    "PMAODV-3":      "#377eb8",   # xanh dương
    "QMAODV-3":      "#1b9e77",   # xanh ngọc
    "QSAQMAODV-3":   "#ff7f00",   # cam — protocol mới, highlight
}
MARKERS = {
    "AODV":          "o",
    "AOMDV-3":       "D",
    "PMAODV-3":      "s",
    "QMAODV-3":      "8",
    "QSAQMAODV-3":   "*",
}
LINEWIDTHS = {k: 1.5 for k in PROTOCOLS}
LINEWIDTHS["QSAQMAODV-3"] = 2.5
SIZES = {k: 6 for k in PROTOCOLS}
SIZES["QSAQMAODV-3"] = 11

METRICS = [
    ("deliveryRatio",   "Delivery Ratio (%)",        "Fig_N_1_DeliveryRatio.png"),
    ("avgDelayMs",      "End-to-end Delay (ms)",     "Fig_N_2_Delay.png"),
    ("throughputMbps",  "Throughput (Mbps)",         "Fig_N_3_Throughput.png"),
    ("routingOverhead", "Routing Overhead (pkts)",   "Fig_N_4_Overhead.png"),
    ("totalEnergyJ",    "Total Energy Consumed (J)", "Fig_N_5_Energy.png"),
]

# ---------------------------------------------------------------------------
# Vẽ
# ---------------------------------------------------------------------------
available = [p for p in PROTOCOLS if p in data]
if not available:
    print(f"[ERROR] Không tìm thấy protocol nào. Có trong CSV: {list(data.keys())}")
    sys.exit(1)

print(f"Protocols có data: {available}")
print(f"Output: {OUT_DIR}\n")

for metric_key, ylabel, fname in METRICS:
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for label in available:
        ns = sorted(data[label].keys())
        ys = [data[label][n].get(metric_key, 0) for n in ns]
        ax.plot(ns, ys,
                marker=MARKERS.get(label, "o"),
                color=COLORS.get(label, "gray"),
                label=label,
                linewidth=LINEWIDTHS.get(label, 1.5),
                markersize=SIZES.get(label, 6))

    ax.set_xlabel("Number of UAVs (N)", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(f"{ylabel} vs Number of UAVs", fontsize=13)
    ax.legend(loc="best", fontsize=11)
    ax.grid(True, alpha=0.3)

    # X-ticks đúng với N={5,10,15,20,25,30}
    ns_all = sorted({n for p in available for n in data[p].keys()})
    if ns_all:
        ax.set_xticks(ns_all)

    fig.tight_layout()
    out_path = os.path.join(OUT_DIR, fname)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------
ns_all = sorted({n for p in available for n in data[p].keys()})
print()
print("=" * 72)
print(" PDR (%) by N")
print("=" * 72)
print(f"{'Protocol':<16} " + "  ".join(f"N={n:>2}" for n in ns_all))
print("-" * 72)
for p in available:
    cells = []
    for n in ns_all:
        v = data[p].get(n, {}).get("deliveryRatio")
        cells.append(f"{v:>6.2f}" if v is not None else f"{'—':>6}")
    print(f"{p:<16} " + "  ".join(cells))

# Cảnh báo nếu có protocol thiếu data
missing = [p for p in PROTOCOLS if p not in available]
if missing:
    print(f"\n[!] Không có data cho: {missing}")
    print("    Kiểm tra segfault trong run_N.log")
