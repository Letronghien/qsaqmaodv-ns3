#!/bin/bash
# tune-saqmaodv-stage2.sh
# Stage 2: Refine 3 winners của Stage 1 bằng sweep init params (α₀, ε₀, γ).
#
# Winners từ Stage 1:
#   A: λ=0.5, W=10, P=1.0  (best PDR)
#   B: λ=0.5, W=5,  P=2.0  (PDR/delay balance)
#   C: λ=0.2, W=5,  P=1.0  (best low-delay)
#
# Sweep:
#   α₀ ∈ {0.3, 0.5, 0.7}
#   ε₀ ∈ {0.1, 0.3, 0.5}
#   γ  ∈ {0.7, 0.9}
#
# Total: 3 winners × 3 × 3 × 2 × 3 seeds = 162 runs ≈ 10 phút
#
# Usage: bash tune-saqmaodv-stage2.sh

set -u

# ---- Auto-detect ns-3 ----
NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40/ns-3.40}"
EXEC=$(find "$NS3_DIR/build" -maxdepth 2 -name "*fanet-sim*" -executable -type f 2>/dev/null | head -1)
[ -z "$EXEC" ] && { echo "ERROR: fanet-sim not found"; exit 1; }

NPROC=$(nproc 2>/dev/null || echo 4)
JOBS="${JOBS:-$((NPROC * 3 / 4))}"
[ "$JOBS" -lt 1 ] && JOBS=1

SEEDS="${SEEDS:-3}"
N_NODES="${N_NODES:-15}"
SIM_TIME="${SIM_TIME:-200}"

# ---- Output ----
TS=$(date +%Y%m%d-%H%M%S)
OUT_DIR="$HOME/results-saqmaodv-tune-stage2-${TS}"
JOB_DIR="$OUT_DIR/jobs"
mkdir -p "$JOB_DIR"
MERGED="$OUT_DIR/merged.csv"
LOG="$OUT_DIR/run.log"

# ---- Winners from Stage 1: "name lambda window period" ----
WINNERS=(
    "A 0.5 10 1.0"
    "B 0.5 5  2.0"
    "C 0.2 5  1.0"
)

# ---- Stage-2 sweep grids ----
ALPHAS=(0.3 0.5 0.7)
EPSILONS=(0.1 0.3 0.5)
GAMMAS=(0.7 0.9)

# ---- Generate jobs ----
JOB_FILE="$JOB_DIR/jobs.txt"
> "$JOB_FILE"
for w in "${WINNERS[@]}"; do
    read -r wname lam win per <<< "$w"
    for a0 in "${ALPHAS[@]}"; do
        for e0 in "${EPSILONS[@]}"; do
            for g in "${GAMMAS[@]}"; do
                for seed in $(seq 1 "$SEEDS"); do
                    tag="${wname}-A${a0}-E${e0}-G${g}"
                    echo "$tag $lam $win $per $a0 $e0 $g $seed" >> "$JOB_FILE"
                done
            done
        done
    done
done
TOTAL=$(wc -l < "$JOB_FILE")

# ---- Print config ----
{
echo "==========================================="
echo " SA-QMAODV Stage 2 Refinement Sweep"
echo "==========================================="
echo " Winners:       A(λ=0.5,W=10,P=1.0) B(λ=0.5,W=5,P=2.0) C(λ=0.2,W=5,P=1.0)"
echo " Alpha0 grid:   ${ALPHAS[*]}"
echo " Epsilon0 grid: ${EPSILONS[*]}"
echo " Gamma grid:    ${GAMMAS[*]}"
echo " Seeds:         $SEEDS"
echo " N nodes:       $N_NODES"
echo " Sim time:      ${SIM_TIME}s"
echo " Parallel jobs: $JOBS"
echo " Total runs:    $TOTAL"
echo " Output:        $OUT_DIR"
echo " Started:       $(date)"
echo "==========================================="
} | tee "$LOG"

# ---- Worker ----
run_job() {
    local tag=$1 lam=$2 win=$3 per=$4 a0=$5 e0=$6 g=$7 seed=$8
    local CSV="$JOB_DIR/job-${tag}-seed${seed}.csv"
    local START=$(date +%s)

    "$EXEC" \
        --protocol=SAQMAODV --maxPaths=3 \
        --numNodes="$N_NODES" --simTime="$SIM_TIME" --seed="$seed" \
        --mobility=GAUSS --enableEnergy=1 \
        --meanVelMin=15 --meanVelMax=25 --alpha=0.85 \
        --pktInterval=0.25 --pktSize=512 --numFlows=0 \
        --saAlpha0="$a0" --saGamma="$g" --saEpsilon0="$e0" \
        --saLambda="$lam" --saSeqNoWin="$win" \
        --saAdaptPeriod="$per" \
        --saLowEThresh=0.20 \
        --saW1=0.5 --saW2=0.4 --saW3=0.1 \
        --scenario="tune-$tag" \
        --csvFile="$CSV" >/dev/null 2>&1
    local rc=$?
    local DUR=$(( $(date +%s) - START ))
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 139 ]; then
        echo "OK   $tag seed=$seed (${DUR}s)"
    else
        echo "FAIL $tag seed=$seed rc=$rc"
    fi
}
export -f run_job
export EXEC N_NODES SIM_TIME JOB_DIR

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

# ---- Top-15 summary, grouped by winner family ----
if command -v python3 >/dev/null && [ -s "$MERGED" ]; then
    python3 - "$MERGED" <<'PYEOF' | tee -a "$LOG"
import csv, sys
from collections import defaultdict
rows = list(csv.DictReader(open(sys.argv[1])))
agg = defaultdict(list)
for r in rows:
    cfg = r['scenario'].replace('tune-', '')
    agg[cfg].append({
        'pdr':   float(r['deliveryRatio']),
        'delay': float(r['avgDelayMs']),
        'thr':   float(r['throughputMbps']),
        'over':  int(float(r['routingOverhead'])),
    })
ranked = []
for cfg, vals in agg.items():
    n = len(vals)
    ranked.append((cfg,
        sum(v['pdr']   for v in vals)/n,
        sum(v['delay'] for v in vals)/n,
        sum(v['thr']   for v in vals)/n,
        sum(v['over']  for v in vals)/n))

# Sort by PDR
ranked.sort(key=lambda x: -x[1])
print()
print("=" * 75)
print(" Top-15 cấu hình theo PDR")
print("=" * 75)
print(f"{'rank':<5} {'config':<24} {'PDR(%)':>7} {'delay(ms)':>10} {'thr(Mbps)':>10} {'overhead':>10}")
print('-' * 75)
for i, (cfg, pdr, d, t, o) in enumerate(ranked[:15], 1):
    print(f"{i:<5} {cfg:<24} {pdr:>7.2f} {d:>10.1f} {t:>10.4f} {o:>10.0f}")

# Sort by delay (chỉ lấy cấu hình PDR >= 40%)
print()
print("=" * 75)
print(" Top-10 cấu hình theo delay (PDR >= 40%)")
print("=" * 75)
ranked_delay = [r for r in ranked if r[1] >= 40.0]
ranked_delay.sort(key=lambda x: x[2])
print(f"{'rank':<5} {'config':<24} {'PDR(%)':>7} {'delay(ms)':>10} {'thr(Mbps)':>10} {'overhead':>10}")
print('-' * 75)
for i, (cfg, pdr, d, t, o) in enumerate(ranked_delay[:10], 1):
    print(f"{i:<5} {cfg:<24} {pdr:>7.2f} {d:>10.1f} {t:>10.4f} {o:>10.0f}")
PYEOF
fi
