import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import numpy as np, os

CSV = os.path.expanduser("~/ns-allinone-3.40/ns-3.40/results.csv")
OUT = os.path.expanduser("~/plots"); os.makedirs(OUT, exist_ok=True)

cols = ["scenario","protocol","mobility","seed","nodes","flows",
        "velMin","velMax","pktInterval","simTime","pktSize",
        "pdr","delay","thr","overhead","energy","dead"]
df = pd.read_csv(CSV, names=cols)
df["pdr"]   = pd.to_numeric(df["pdr"],   errors="coerce")
df["delay"] = pd.to_numeric(df["delay"], errors="coerce")
df["thr"]   = pd.to_numeric(df["thr"],   errors="coerce")
df["energy"]= pd.to_numeric(df["energy"],errors="coerce")
df["nodes"] = pd.to_numeric(df["nodes"], errors="coerce")

COLORS = {"AODV":"#1f77b4","AOMDV":"#ff7f0e","PMAODV":"#2ca02c",
          "QMAODV":"#d62728","QSAQMAODV":"#9467bd"}
LABELS = {"QSAQMAODV":"EA-QMAODV"}
def lbl(p): return LABELS.get(p, p)

def save_fig(name):
    p = f"{OUT}/{name}.pdf"
    plt.tight_layout(); plt.savefig(p, dpi=150); plt.close()
    print(f"  → {p}")

# ── E family: 5 metrics vs Nodes ──────────────────────────────────────
print("Plotting E family...")
e = df[df.scenario=="default"].groupby(["protocol","nodes"]).agg(
    pdr=("pdr","mean"), delay=("delay","mean"),
    thr=("thr","mean"), energy=("energy","mean")).reset_index()

protos = [p for p in ["AODV","AOMDV","PMAODV","QMAODV","QSAQMAODV"] if p in e.protocol.unique()]
fig, axes = plt.subplots(1, 4, figsize=(18,4))
metrics = [("pdr","PDR (%)"),("delay","E2E Delay (ms)"),
           ("thr","Throughput (Mbps)"),("energy","Residual Energy (J)")]
for ax, (m, ylabel) in zip(axes, metrics):
    for p in protos:
        d = e[e.protocol==p].sort_values("nodes")
        ax.plot(d.nodes, d[m], marker="o", label=lbl(p),
                color=COLORS.get(p,"gray"), linewidth=2)
    ax.set_xlabel("Number of Nodes"); ax.set_ylabel(ylabel)
    ax.set_title(ylabel); ax.legend(fontsize=8); ax.grid(alpha=0.3)
plt.suptitle("E Family — Standard GAUSS Topology", fontweight="bold")
save_fig("E_vs_nodes")

# ── W family: ablation weights ─────────────────────────────────────────
print("Plotting W family (ablation)...")
w_tags = [f"ablw{i}" for i in range(1,7)]
w_labels = ["(0.5,0.2,0.2,0.1)","(0.3,0.3,0.3,0.1)","(0.4,0.3,0.2,0.1)",
            "(0.4,0.2,0.1,0.3)","(0.5,0.1,0.1,0.3)","(0.3,0.2,0.4,0.1)"]
wdf = df[df.scenario.isin(w_tags) & (df.protocol=="QSAQMAODV")].groupby("scenario").agg(
    pdr=("pdr","mean"), delay=("delay","mean"),
    thr=("thr","mean"), energy=("energy","mean")).reindex(w_tags)

if not wdf.empty:
    fig, axes = plt.subplots(1, 4, figsize=(18,4))
    x = np.arange(len(w_tags)); w = 0.5
    for ax, (m, ylabel) in zip(axes, metrics):
        ax.bar(x, wdf[m].values, color="#9467bd", alpha=0.8, width=w)
        ax.set_xticks(x); ax.set_xticklabels([f"W{i+1}" for i in range(6)], rotation=45, fontsize=8)
        ax.set_ylabel(ylabel); ax.set_title(ylabel); ax.grid(axis="y", alpha=0.3)
    plt.suptitle("W Family — EA-QMAODV Weight Ablation (N=20)", fontweight="bold")
    save_fig("W_ablation")
    # Print table
    print("\n  Weight ablation summary:")
    wdf["label"] = w_labels
    print(wdf[["label","pdr","delay","thr","energy"]].to_string())

# ── ELONG + STAT: bar chart ────────────────────────────────────────────
for scen, title in [("elong","ELONG — Elongated Topology"),("stat","STAT — Static Nodes")]:
    sdf = df[(df.scenario==scen)].groupby("protocol").agg(
        pdr=("pdr","mean"), delay=("delay","mean"),
        thr=("thr","mean"), energy=("energy","mean")).reset_index()
    if sdf.empty: print(f"  {scen}: no data yet, skip"); continue
    print(f"Plotting {scen}...")
    sdf = sdf[sdf.protocol.isin(protos)].set_index("protocol").reindex(
        [p for p in protos if p in sdf.protocol.values])
    fig, axes = plt.subplots(1, 4, figsize=(18,4))
    x = np.arange(len(sdf)); colors = [COLORS.get(p,"gray") for p in sdf.index]
    for ax, (m, ylabel) in zip(axes, metrics):
        ax.bar(x, sdf[m].values, color=colors, alpha=0.85)
        ax.set_xticks(x); ax.set_xticklabels([lbl(p) for p in sdf.index], rotation=30, fontsize=9)
        ax.set_ylabel(ylabel); ax.set_title(ylabel); ax.grid(axis="y", alpha=0.3)
    plt.suptitle(f"{title} (N=20)", fontweight="bold")
    save_fig(f"{scen}_bar")

print(f"\nAll plots saved to {OUT}/")
print("Download: scp user@vm-ip:~/plots/*.pdf .")
