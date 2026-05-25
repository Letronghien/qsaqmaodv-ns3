#!/usr/bin/env python3
"""
aggregate-for-paper.py
======================

Emits all numerical tables the QMAODV paper needs, in Vietnamese-ready
markdown format. Read the resulting `paper-tables.md` and paste the cells
into the corresponding sections of the paper draft.

Tables produced:
  - Bảng 1: PDR/Delay/Throughput/Overhead per scenario (big-batch v3)
  - Bảng 2: Top-15 hyperparameter configs (Family H)
  - Bảng 3: Per-N density sweep (Family N)
  - Bảng 4: Per-speed sweep (Family S)
  - Bảng 5: Per-load sweep (Family L)
  - Bảng 6: Per-pktsize sweep (Family P)
  - Bảng 7: Per-flow-count sweep (Family F)
  - Bảng 8: Cross-regime winner summary

Usage:
  python3 aggregate-for-paper.py \
      --bigbatch ~/results-stress-<TS>/merged.csv \
      --paper-dir ~/results-paper-merged \
      --hyper-csv ~/results-paper-<TS>/family_H_hyper.csv \
      --outfile paper-tables.md
"""
import argparse
import csv
import os
import sys
from collections import defaultdict

try:
    import pandas as pd
except ImportError:
    sys.exit("pip install pandas")


def label_of(row):
    p  = row["protocol"]
    mp = row.get("maxPaths", "1")
    return f"{p}-{mp}" if p in ("PMAODV", "AOMDV", "QMAODV", "SAQMAODV") else p


def fmt(v, dec=2):
    try:
        return f"{float(v):.{dec}f}"
    except (ValueError, TypeError):
        return "—"


def table_bigbatch(csv_path, out):
    if not csv_path or not os.path.exists(csv_path):
        out.write("> [missing big-batch CSV]\n\n"); return
    df = pd.read_csv(csv_path)
    df["variant"] = df.apply(label_of, axis=1)
    scenarios = sorted(df["scenario"].unique())
    protos = ["AODV", "DSDV", "AOMDV-3", "PMAODV-3", "QMAODV-3", "SAQMAODV-3"]

    out.write("## Bảng 1. Hiệu năng trung bình theo từng kịch bản\n\n")
    out.write("Trung bình trên N ∈ [5, 20] × 5 seeds = 80 simulation runs / cell.\n\n")
    out.write("| Kịch bản | Giao thức | PDR (%) | Delay (ms) | Throughput (Mbps) | Overhead |\n")
    out.write("|---|---|---|---|---|---|\n")
    for s in scenarios:
        for p in protos:
            sub = df[(df["scenario"] == s) & (df["variant"] == p)]
            if sub.empty: continue
            out.write(f"| {s} | {p} | {fmt(sub['deliveryRatio'].mean())} | "
                      f"{fmt(sub['avgDelayMs'].mean(), 1)} | "
                      f"{fmt(sub['throughputMbps'].mean(), 4)} | "
                      f"{int(sub['routingOverhead'].astype(float).mean())} |\n")
    out.write("\n")


def table_hyper(csv_path, out):
    if not csv_path or not os.path.exists(csv_path):
        out.write("> [missing hyper CSV]\n\n"); return
    df = pd.read_csv(csv_path)
    agg = defaultdict(list)
    for _, r in df.iterrows():
        agg[r["scenario"]].append({
            "pdr":   float(r["deliveryRatio"]),
            "delay": float(r["avgDelayMs"]),
            "thr":   float(r["throughputMbps"]),
            "over":  int(r["routingOverhead"]),
        })
    rows = []
    for cfg, vals in agg.items():
        n = len(vals)
        rows.append((
            cfg,
            sum(v["pdr"]   for v in vals)/n,
            sum(v["delay"] for v in vals)/n,
            sum(v["thr"]   for v in vals)/n,
            sum(v["over"]  for v in vals)/n,
        ))
    rows.sort(key=lambda x: -x[1])
    out.write("## Bảng 2. Top-15 cấu hình siêu tham số QMAODV (Family H)\n\n")
    out.write("Trung bình trên 3 seeds tại N=15, T=200s.\n\n")
    out.write("| Hạng | α | γ | ε | decay | PDR (%) | Delay (ms) | Thr (Mbps) | Overhead |\n")
    out.write("|---|---|---|---|---|---|---|---|---|\n")
    for i, (cfg, pdr, delay, thr, over) in enumerate(rows[:15], 1):
        # parse cfg = "a0.5-g0.7-e0.1-d0.05" or "tune-..."
        parts = cfg.replace("tune-", "").split("-")
        d = {}
        for p in parts:
            if not p: continue
            k, v = p[0], p[1:]
            d[k] = v
        out.write(f"| {i} | {d.get('a','—')} | {d.get('g','—')} | "
                  f"{d.get('e','—')} | {d.get('d','—')} | "
                  f"{fmt(pdr)} | {fmt(delay, 1)} | {fmt(thr, 4)} | {int(over)} |\n")
    out.write("\n")


def table_per_x(csv_path, x_col, x_name, scenario_filter, title, out, extra_xform=None):
    if not csv_path or not os.path.exists(csv_path):
        out.write(f"> [missing {title} CSV]\n\n"); return
    df = pd.read_csv(csv_path)
    df["variant"] = df.apply(label_of, axis=1)
    if extra_xform:
        df = extra_xform(df)
    if scenario_filter is not None:
        df = df[df["scenario"].astype(str).str.startswith(scenario_filter)]
    if df.empty:
        out.write(f"> [no rows for {title}]\n\n"); return

    protos = ["AODV", "AOMDV-3", "PMAODV-3", "QMAODV-3", "SAQMAODV-3"]
    xs = sorted(df[x_col].unique())

    out.write(f"## {title}\n\n")
    out.write(f"| {x_name} | " + " | ".join([f"{p} PDR" for p in protos]) + " |\n")
    out.write("|---" * (len(protos)+1) + "|\n")
    for x in xs:
        row = [str(x)]
        for p in protos:
            sub = df[(df[x_col] == x) & (df["variant"] == p)]
            if sub.empty:
                row.append("—")
            else:
                row.append(fmt(sub["deliveryRatio"].mean()))
        out.write("| " + " | ".join(row) + " |\n")
    out.write("\n")

    # Bonus: delay table
    out.write(f"**Delay (ms) tại các điểm {x_name}:**\n\n")
    out.write(f"| {x_name} | " + " | ".join([f"{p} Delay" for p in protos]) + " |\n")
    out.write("|---" * (len(protos)+1) + "|\n")
    for x in xs:
        row = [str(x)]
        for p in protos:
            sub = df[(df[x_col] == x) & (df["variant"] == p)]
            if sub.empty:
                row.append("—")
            else:
                row.append(fmt(sub["avgDelayMs"].mean(), 1))
        out.write("| " + " | ".join(row) + " |\n")
    out.write("\n")


def cross_regime_winner(bigbatch, paper_dir, out):
    out.write("## Bảng 8. Bảng tổng hợp người thắng theo regime (PDR)\n\n")

    # From big-batch v3
    if bigbatch and os.path.exists(bigbatch):
        df = pd.read_csv(bigbatch)
        df["variant"] = df.apply(label_of, axis=1)
        scenarios = sorted(df["scenario"].unique())
        out.write("| Regime / Kịch bản | Giao thức thắng | PDR thắng (%) | Á quân | Cách biệt |\n")
        out.write("|---|---|---|---|---|\n")
        for s in scenarios:
            sub = df[df["scenario"] == s]
            avg = sub.groupby("variant")["deliveryRatio"].mean().sort_values(ascending=False)
            if len(avg) < 2: continue
            winner, second = avg.index[0], avg.index[1]
            out.write(f"| {s} | **{winner}** | {avg.iloc[0]:.2f} | "
                      f"{second} ({avg.iloc[1]:.2f}) | +{avg.iloc[0]-avg.iloc[1]:.2f} pp |\n")
    out.write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bigbatch",   help="big-batch v3 merged.csv (5 scenarios)")
    ap.add_argument("--paper-dir",  help="results-paper-merged directory")
    ap.add_argument("--hyper-csv",  help="family_H_hyper.csv")
    ap.add_argument("--outfile",    default="paper-tables.md")
    args = ap.parse_args()

    bigbatch = os.path.expanduser(args.bigbatch) if args.bigbatch else None
    paper    = os.path.expanduser(args.paper_dir) if args.paper_dir else None
    hyper    = os.path.expanduser(args.hyper_csv) if args.hyper_csv else None

    with open(args.outfile, "w") as f:
        f.write("# QMAODV Paper — Aggregated Tables (Vietnamese)\n\n")

        # Bảng 1
        table_bigbatch(bigbatch, f)

        # Bảng 2
        table_hyper(hyper, f)

        # Bảng 3 – Family N
        n_csv = os.path.join(paper, "family_N_nodes.csv") if paper else None
        table_per_x(n_csv, "numNodes", "Số UAV N",
                    "N", "Bảng 3. Quét mật độ — PDR theo số UAV (Family N)", f)

        # Bảng 4 – Family S
        s_csv = os.path.join(paper, "family_S_speed.csv") if paper else None
        table_per_x(s_csv, "meanVelMax", "Vận tốc tối đa (m/s)",
                    "V", "Bảng 4. Quét vận tốc — PDR theo tốc độ UAV (Family S)", f)

        # Bảng 5 – Family L (convert pktInterval → pps)
        def add_pps(df):
            df["pps"] = (1.0 / df["pktInterval"].astype(float)).round(2)
            return df
        l_csv = os.path.join(paper, "family_L_load.csv") if paper else None
        table_per_x(l_csv, "pps", "Tải (pps)",
                    "I", "Bảng 5. Quét tải lưu lượng — PDR theo pps (Family L)", f,
                    extra_xform=add_pps)

        # Bảng 6 – Family P
        # NB: fanet-sim.cc does not write `pktSize` as a CSV column, so we
        # derive it from the scenario tag (e.g. "S64", "S128", ...). This
        # transform sets df["pktSize"] = int(scenario[1:]) when scenario
        # starts with "S" followed by digits.
        def derive_pktsize(df):
            def parse(s):
                if isinstance(s, str) and s.startswith("S") and s[1:].isdigit():
                    return int(s[1:])
                return None
            df = df.copy()
            df["pktSize"] = df["scenario"].apply(parse)
            df = df.dropna(subset=["pktSize"])
            df["pktSize"] = df["pktSize"].astype(int)
            return df

        p_csv = os.path.join(paper, "family_P_pktsize.csv") if paper else None
        table_per_x(p_csv, "pktSize", "Kích thước gói (B)",
                    "S", "Bảng 6. Quét kích thước gói — PDR theo packet size (Family P)", f,
                    extra_xform=derive_pktsize)

        # Bảng 7 – Family F
        f_csv = os.path.join(paper, "family_F_flows.csv") if paper else None
        table_per_x(f_csv, "numFlows", "Số luồng",
                    "F", "Bảng 7. Quét đa luồng — PDR theo số flow (Family F)", f)

        # Bảng 8 – Cross-regime winner
        cross_regime_winner(bigbatch, paper, f)

    print(f"Wrote: {args.outfile}")
    print("Đính kèm file này khi paste cho tôi, tôi sẽ điền vào bài báo.")


if __name__ == "__main__":
    main()
