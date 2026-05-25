#!/bin/bash
# tune-saqmaodv-stage3.sh
# Stage 3: Verify Winner A của Stage 1+2 ở các mật độ network khác nhau.
#
# Winner A: λ=0.5, W=10, P=1.0, γ=0.9
#
# Sweep N ∈ {10, 15, 20, 25, 30} × 5 seeds = 25 runs cho A
# So sánh với 2 cấu hình alternative để confirm A vẫn tốt nhất:
#   - Winner B: λ=0.5, W=5, P=2.0  (balance)
#   - Winner C: λ=0.2, W=5, P=1.0  (low-delay)
# Tổng: 3 winners × 5 N × 5 seeds = 75 runs ≈ 12 phút
#
# Usage: bash tune-saqmaodv-stage3.sh
#        SEEDS=10 bash tune-saqmaodv-stage3.sh    # tăng độ tin cậy

set -u

# ---- Auto-detect ns-3 ----
NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40/ns-3.40}"
EXEC=$(find "$NS3_DIR/build" -maxdepth 2 -name "*fanet-sim*" -executable -type f 2>/dev/null | head -1)
[ -z "$EXEC" ] && { echo "ERROR: fanet-sim not found"; exit 1; }

NPROC=$(nproc 2>/dev/null || echo 4)
JOBS="${JOBS:-$((NPROC * 3 / 4))}"
[ "$JOBS" -lt 1 ] && JOBS=1

SEEDS="${SEEDS:-5}"
SIM_TIME="${SIM_TIME:-200}"
N_VALUES=(10 15 20 25 30)

# ---- Output ----
TS=$(date +%Y%m%d-%H%M%S)
OUT_DIR="$HOME/results-saqmaodv-tune-stage3-${TS}"
JOB_DIR="$OUT_DIR/jobs"
mkdir -p "$JOB_DIR"
MERGED="$OUT_DIR/merged.csv"
LOG="$OUT_DIR/run.log"

# ---- Winners: "name lambda window period" ----
WINNERS=(
    "A 0.5 10 1.0"
    "B 0.5 5  2.0"
    "C 0.2 5  1.0"
)

# ---- Generate jobs ----
JOB_FILE="$JOB_DIR/jobs.txt"
> "$JOB_FILE"
for w in "${WINNERS[@]}"; do
    read -r wname lam win per <<< "$w"
    for N in "${N_VALUES[@]}"; do
        for seed in $(seq 1 "$SEEDS"); do
            echo "$wname $lam $win $per $N $seed" >> "$JOB_FILE"
        done
    done
done
TOTAL=$(wc -l < "$JOB_FILE")

# ---- Print config ----
{
echo "==========================================="
echo " SA-QMAODV Stage 3 Verification Across N"
echo "==========================================="
echo " Winners:       A(λ=0.5,W=10,P=1.0) B(λ=0.5,W=5,P=2.0) C(λ=0.2,W=5,P=1.0)"
echo " N values:      ${N_VALUES[*]}"
echo " Seeds:         $SEEDS"
echo " Sim time:      ${SIM_TIME}s"
echo " Parallel jobs: $JOBS"
echo " Total runs:    $TOTAL"
echo " Output:        $OUT_DIR"
echo " Started:       $(date)"
echo "==========================================="
} | tee "$LOG"

# ---- Worker ----
run_job() {
    local wname=$1 lam=$2 win=$3 per=$4 N=$5 seed=$6
    local CSV="$JOB_DIR/job-${wname}-N${N}-seed${seed}.csv"
    local START=$(date +%s)

    "$EXEC" \
        --protocol=SAQMAODV --maxPaths=3 \
        --numNodes="$N" --simTime="$SIM_TIME" --seed="$seed" \
        --mobility=GAUSS --enableEnergy=1 \
        --meanVelMin=15 --meanVelMax=25 --alpha=0.85 \
        --pktInterval=0.25 --pktSize=512 --numFlows=0 \
        --saAlpha0=0.5 --saGamma=0.9 --saEpsilon0=0.3 \
        --saLambda="$lam" --saSeqNoWin="$win" \
        --saAdaptPeriod="$per" \
        --saLowEThresh=0.20 \
        --saW1=0.5 --saW2=0.4 --saW3=0.1 \
        --scenario="winner-$wname-N$N" \
        --csvFile="$CSV" >/dev/null 2>&1
    local rc=$?
    local DUR=$(( $(date +%s) - START ))
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 139 ]; then
        echo "OK   $wname N=$N seed=$seed (${DUR}s)"
    else
        echo "FAIL $wname N=$N seed=$seed rc=$rc"
    fi
}
export -f run_job
export EXEC SIM_TIME JOB_DIR

# ---- Run parallel ----
START_TS=$(date +%s)
cat "$JOB_FILE" | xargs -P "$JOBS" -L 1 bash -c 'run_job "$@"' _ \
    | tee -a "$LOG"
END_TS=$(date +%s)
TOTAL_SEC=$(( END_TS - START_TS ))

# ---- Merge CSVs ----
FIRST_CSV=$(ls "$JOB_DIR"/job-*.csv 2>/dev/null | head -1)
if [ -n "$FIRST_CSV" ]; then
    head -1 "$FIRST_CSV" > "$MERGED"
    for f in "$JOB_DIR"/job-*.csv; do
        tail -n +2 "$f" >> "$MERGED"
    done
    ROWS=$(($(wc -l < "$MERGED") - 1))
    echo "Merged: $MERGED ($ROWS rows)" | tee -a "$LOG"
fi

{
echo ""
echo "==========================================="
echo " Done: $(date)"
echo " Total: $((TOTAL_SEC/60))m $((TOTAL_SEC%60))s"
echo "==========================================="
} | tee -a "$LOG"

# ---- Summary table: winner × N ----
if command -v python3 >/dev/null && [ -s "$MERGED" ]; then
    python3 - "$MERGED" <<'PYEOF' | tee -a "$LOG"
import csv, sys
from collections import defaultdict
rows = list(csv.DictReader(open(sys.argv[1])))
agg = defaultdict(list)
for r in rows:
    # scenario = "winner-A-N15"  →  parse winner and N
    parts = r['scenario'].split('-')
    if len(parts) != 3: continue
    _, wname, nstr = parts
    N = int(nstr.replace('N',''))
    agg[(wname, N)].append({
        'pdr':   float(r['deliveryRatio']),
        'delay': float(r['avgDelayMs']),
        'thr':   float(r['throughputMbps']),
        'over':  int(float(r['routingOverhead'])),
    })

means = {}
for (w, N), vals in agg.items():
    n = len(vals)
    means[(w, N)] = {
        'pdr':   sum(v['pdr']   for v in vals)/n,
        'delay': sum(v['delay'] for v in vals)/n,
        'thr':   sum(v['thr']   for v in vals)/n,
        'over':  sum(v['over']  for v in vals)/n,
    }

winners = sorted(set(w for (w, _) in means.keys()))
ns      = sorted(set(N for (_, N) in means.keys()))

# PDR table
print()
print("=" * 60)
print(" PDR (%) — Winner × N")
print("=" * 60)
print(f"{'N':>5} | " + " | ".join(f"{w:>10}" for w in winners))
print("-" * 60)
for N in ns:
    cells = [f"{means.get((w,N),{}).get('pdr',0):>10.2f}" for w in winners]
    print(f"{N:>5} | " + " | ".join(cells))

# Delay table
print()
print("=" * 60)
print(" Delay (ms) — Winner × N")
print("=" * 60)
print(f"{'N':>5} | " + " | ".join(f"{w:>10}" for w in winners))
print("-" * 60)
for N in ns:
    cells = [f"{means.get((w,N),{}).get('delay',0):>10.1f}" for w in winners]
    print(f"{N:>5} | " + " | ".join(cells))

# Winner per N
print()
print("=" * 60)
print(" Winner per N (theo PDR)")
print("=" * 60)
for N in ns:
    best_w = max(winners, key=lambda w: means.get((w,N),{}).get('pdr',0))
    best_pdr = means[(best_w, N)]['pdr']
    print(f"  N={N}: {best_w} (PDR={best_pdr:.2f}%)")
PYEOF
fi
