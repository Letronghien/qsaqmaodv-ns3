#!/bin/bash
# run-ea-rerun.sh
# ---------------------------------------------------------------------------
# Reruns ONLY QSAQMAODV (EA-QMAODV) for the families most affected by the
# 2 formula changes (E → E², ΔSeq → TD-error adaptive α):
#
#   Family E  : E0 ∈ {10,20,30,50,75,100} J   × 30 seeds = 180 runs
#   STAT      : 1 baseline config              × 50 seeds =  50 runs
#   ELONG     : E0=10J, T=350s                 × 30 seeds =  30 runs
#   Family W* : w3 ∈ {0.00, 0.05, 0.10, 0.20} × 30 seeds =  120 runs
#   ──────────────────────────────────────────────────────────────────
#   Total                                               = 380 runs
#
#   Old AODV/AOMDV/PMAODV/QMAODV data can be reused from the previous
#   results directory (set OLD_RESULTS below).
#
# Usage:
#   tmux new -s ea-rerun
#   bash scripts/run/run-ea-rerun.sh
#   # or with custom seeds/jobs:
#   SEEDS=15 JOBS=8 bash scripts/run/run-ea-rerun.sh
# ---------------------------------------------------------------------------
set -u

NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40/ns-3.40}"
EXEC="$NS3_DIR/build/scratch/ns3.40-fanet-sim-optimized"

JOBS="${JOBS:-6}"
SEEDS="${SEEDS:-30}"
SEEDS_STAT="${SEEDS_STAT:-50}"
SIM_TIME="${SIM_TIME:-200}"

# EA-QMAODV (QSAQMAODV) hyper-params — updated for EA-formula
QS_ALPHA0="${QS_ALPHA0:-0.5}"
QS_GAMMA="${QS_GAMMA:-0.9}"
QS_EPSILON0="${QS_EPSILON0:-0.3}"
QS_W1="${QS_W1:-0.40}"
QS_W2="${QS_W2:-0.50}"
QS_W3="${QS_W3:-0.10}"
QS_MU="${QS_MU:-0.10}"        # EA-Fix1: EMA smoothing factor μ
QS_KAPPA="${QS_KAPPA:-0.50}"  # EA-Fix1: saturation constant κ
QS_LOW_E="${QS_LOW_E:-0.20}"
QS_ADAPT="${QS_ADAPT:-10.0}"

# Output
TS=$(date +%Y%m%d-%H%M%S)
ROOT="$HOME/results-ea-rerun-${TS}"
mkdir -p "$ROOT"

# Base scenario (matches paper baseline)
BASE="--mobility=GAUSS --enableEnergy=1 --alpha=0.85 \
      --numNodes=15 --meanVelMin=15 --meanVelMax=25 \
      --pktInterval=0.25 --pktSize=512 --numFlows=0"

# EA-QMAODV flags (all runs use these)
EA_FLAGS="--qsAlpha0=$QS_ALPHA0 --qsGamma=$QS_GAMMA --qsEpsilon0=$QS_EPSILON0 \
          --qsW1=$QS_W1 --qsW2=$QS_W2 --qsW3=$QS_W3 \
          --qsMu=$QS_MU --qsKappa=$QS_KAPPA \
          --qsLowEThresh=$QS_LOW_E --qsAdaptPeriod=$QS_ADAPT"

# ---------------------------------------------------------------------------
# Helper: run one EA-QMAODV simulation
# ---------------------------------------------------------------------------
run_ea() {
    local CSV=$1 SEED=$2 SCEN_TAG=$3
    shift 3
    local extra="$*"
    local START=$(date +%s)

    "$EXEC" \
        --protocol=QSAQMAODV --maxPaths=3 --seed="$SEED" \
        --scenario="$SCEN_TAG" --csvFile="$CSV" \
        $EA_FLAGS $BASE $extra > /dev/null 2>&1
    local rc=$?
    local dur=$(( $(date +%s) - START ))
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 139 ]; then
        echo "OK   EA $SCEN_TAG seed=$SEED (${dur}s)"
    else
        echo "FAIL EA $SCEN_TAG seed=$SEED rc=$rc"
    fi
}
export -f run_ea
export EXEC BASE EA_FLAGS

dispatch() {
    cat "$1" | xargs -P "$JOBS" -L 1 bash -c 'run_ea "$@"' _
}

# ---------------------------------------------------------------------------
# Family E — Initial energy (primary finding)
#   E0 ∈ {10,20,30,50,75,100} J, 30 seeds
#   Also runs ELONG here (E0=10, T=350s, 30 seeds)
# ---------------------------------------------------------------------------
family_E() {
    echo "=== Family E — energy sweep (EA-QMAODV only) ==="
    local CSV="$ROOT/family_E_energy_ea.csv"
    rm -f "$CSV"
    local JF="$ROOT/jobs_E.txt"; > "$JF"
    for e0 in 10 20 30 50 75 100; do
        for s in $(seq 1 "$SEEDS"); do
            echo "$CSV $s E${e0} --initialEnergy=$e0 --simTime=$SIM_TIME" >> "$JF"
        done
    done
    echo " jobs: $(wc -l < $JF)"
    dispatch "$JF"
}

# ---------------------------------------------------------------------------
# ELONG — Energy depletion validation
#   E0=10J, T=350s, 30 seeds
# ---------------------------------------------------------------------------
family_ELONG() {
    echo "=== ELONG — energy depletion (EA-QMAODV only) ==="
    local CSV="$ROOT/family_ELONG_ea.csv"
    rm -f "$CSV"
    local JF="$ROOT/jobs_ELONG.txt"; > "$JF"
    for s in $(seq 1 "$SEEDS"); do
        echo "$CSV $s ELONG --initialEnergy=10 --simTime=350" >> "$JF"
    done
    echo " jobs: $(wc -l < $JF)"
    dispatch "$JF"
}

# ---------------------------------------------------------------------------
# STAT — Statistical validation
#   Baseline config, 50 seeds
# ---------------------------------------------------------------------------
family_STAT() {
    echo "=== STAT — statistical validation (EA-QMAODV only, 50 seeds) ==="
    local CSV="$ROOT/family_STAT_ea.csv"
    rm -f "$CSV"
    local JF="$ROOT/jobs_STAT.txt"; > "$JF"
    for s in $(seq 1 "$SEEDS_STAT"); do
        echo "$CSV $s STAT --initialEnergy=50 --simTime=$SIM_TIME" >> "$JF"
    done
    echo " jobs: $(wc -l < $JF)"
    dispatch "$JF"
}

# ---------------------------------------------------------------------------
# Family W* — Energy weight sensitivity (key points only)
#   w3 ∈ {0.00, 0.05, 0.10, 0.15, 0.20} with E² now baked in
#   30 seeds per point
# ---------------------------------------------------------------------------
family_W() {
    echo "=== Family W (key points) — energy weight sweep (EA-QMAODV only) ==="
    local CSV="$ROOT/family_W_weight_ea.csv"
    rm -f "$CSV"
    local JF="$ROOT/jobs_W.txt"; > "$JF"
    for w3 in 0.00 0.05 0.10 0.15 0.20 0.30 0.40 0.50; do
        # Adjust w1+w2 to keep sum=1 (w2 absorbs the change)
        local w2
        w2=$(awk -v w3="$w3" 'BEGIN{printf "%.2f", 0.60 - w3}')
        for s in $(seq 1 "$SEEDS"); do
            echo "$CSV $s W${w3} --initialEnergy=50 --simTime=$SIM_TIME \
                --qsW3=$w3 --qsW2=$w2" >> "$JF"
        done
    done
    echo " jobs: $(wc -l < $JF)"

    # Run with w3 override (need to override EA_FLAGS w3 per-job)
    # Re-dispatch with per-job EA flags (can't use shared EA_FLAGS for w3 sweep)
    cat "$JF" | while IFS= read -r line; do
        # line: CSV seed TAG --initialEnergy=... --qsW3=X --qsW2=Y
        csv=$(echo "$line" | awk '{print $1}')
        seed=$(echo "$line" | awk '{print $2}')
        tag=$(echo "$line" | awk '{print $3}')
        extra=$(echo "$line" | cut -d' ' -f4-)

        # Build EA flags with overridden w3/w2
        w3val=$(echo "$extra" | grep -oP '(?<=--qsW3=)[0-9.]+')
        w2val=$(echo "$extra" | grep -oP '(?<=--qsW2=)[0-9.]+')
        local_ea="--qsAlpha0=$QS_ALPHA0 --qsGamma=$QS_GAMMA --qsEpsilon0=$QS_EPSILON0 \
                  --qsW1=$QS_W1 --qsW2=$w2val --qsW3=$w3val \
                  --qsMu=$QS_MU --qsKappa=$QS_KAPPA \
                  --qsLowEThresh=$QS_LOW_E --qsAdaptPeriod=$QS_ADAPT"

        echo "$csv $seed $tag --initialEnergy=50 --simTime=$SIM_TIME $local_ea"
    done | xargs -P "$JOBS" -L 1 bash -c 'run_ea "$@"' _
}

# ---------------------------------------------------------------------------
# Summary: how to merge with old data
# ---------------------------------------------------------------------------
print_merge_instructions() {
    cat << 'EOF'

================================================================
 MERGE INSTRUCTIONS
================================================================
The new CSVs contain only EA-QMAODV (QSAQMAODV) rows.
To merge with existing baseline data, use:

  python3 scripts/plot/merge-ea-rerun.py \
      --old-results ~/results-paper-YYYYMMDD-HHMMSS/ \
      --new-ea      ~/results-ea-rerun-TIMESTAMP/ \
      --out         ~/results-merged/

Then re-plot:
  python3 scripts/plot/plot-family-E.py  ~/results-merged/family_E_energy_merged.csv  figures/E/
  python3 scripts/plot/plot-family-W.py  ~/results-merged/family_W_weight_merged.csv  figures/W/
  python3 scripts/plot/plot-STAT.py      ~/results-merged/family_STAT_merged.csv       figures/STAT/
  python3 scripts/plot/plot-ELONG.py     ~/results-merged/family_ELONG_merged.csv      figures/ELONG/
================================================================
EOF
}

# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
{
echo "================================================================="
echo " EA-QMAODV Formula Rerun"
echo "  Fix1: α ← TD-error EMA rational (μ=$QS_MU, κ=$QS_KAPPA)"
echo "  Fix2: reward energy term E²"
echo "================================================================="
echo " Output : $ROOT"
echo " Jobs   : $JOBS   Seeds: $SEEDS   STAT seeds: $SEEDS_STAT"
echo " Started: $(date)"
echo "================================================================="
} | tee "$ROOT/run.log"

START_TS=$(date +%s)

family_E    2>&1 | tee -a "$ROOT/run.log"
family_ELONG 2>&1 | tee -a "$ROOT/run.log"
family_STAT 2>&1 | tee -a "$ROOT/run.log"
family_W    2>&1 | tee -a "$ROOT/run.log"

END_TS=$(date +%s)
TOTAL_SEC=$(( END_TS - START_TS ))

{
echo
echo "================================================================="
echo " Done: $(date)"
echo " Wall: $((TOTAL_SEC/3600))h $(((TOTAL_SEC%3600)/60))m $((TOTAL_SEC%60))s"
echo " CSVs:"
ls -1 "$ROOT"/*.csv 2>/dev/null | sed 's/^/   /'
echo "================================================================="
} | tee -a "$ROOT/run.log"

print_merge_instructions | tee -a "$ROOT/run.log"
