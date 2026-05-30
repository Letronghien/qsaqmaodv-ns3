#!/bin/bash
# =============================================================================
# run-qsaqmaodv-experiments.sh  —  QS-QMAODV Full Parametric Study
#
# 7 Experiment Families:
#   N  — node density      N ∈ {5,10,15,20,30,50,75,100}
#   S  — UAV speed         v ∈ {5,10,20,30,50,70} m/s
#   L  — traffic load      pktInterval ∈ {1.0,0.5,0.25,0.10,0.05}
#   E  — initial energy    E0 ∈ {10,20,30,50,70,100} J  (uniform)
#   H  — heterogeneous E   stdDev ∈ {0,10,20,30,40} J   (mean=50J fixed)
#   W  — w4 sensitivity    w4 ∈ {0.00..0.50}  (QSAQMAODV only)
#   M  — mixed stress      high-load + low-energy combined (LOAD_COMBINED trigger)
#
# Protocols: AODV | PMAODV | QMAODV | QSAQMAODV
#
# Usage (in tmux):
#   tmux new -s qsaq
#   NS3_DIR=~/ns-allinone-3.40-qsaqmaodv/ns-3.40 \
#   JOBS=7 bash scripts/run/run-qsaqmaodv-experiments.sh
# =============================================================================
set -u

NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40-qsaqmaodv/ns-3.40}"
EXEC="$NS3_DIR/build/scratch/ns3.40-fanet-sim-optimized"

JOBS="${JOBS:-7}"
SEEDS="${SEEDS:-5}"
SIM_TIME="${SIM_TIME:-150}"

# QS-QMAODV NORMAL-mode weights (Paper Table II)
QS_W1="${QS_W1:-0.40}"
QS_W2="${QS_W2:-0.30}"
QS_W3="${QS_W3:-0.10}"
QS_W4="${QS_W4:-0.20}"

# Baseline scenario (fixed across all families)
BASE="--mobility=GAUSS --enableEnergy=1 \
      --numNodes=15 --meanVelMin=10 --meanVelMax=25 \
      --pktInterval=0.25 --pktSize=512 --numFlows=0 \
      --initialEnergy=50 --energyStdDev=0 \
      --simTime=$SIM_TIME"

PROTOCOLS=(${PROTOCOLS:-AODV PMAODV QMAODV QSAQMAODV})

# Output directory
TS=$(date +%Y%m%d-%H%M%S)
ROOT="${RESULTS_DIR:-$HOME/results-qsaqmaodv-${TS}}"
mkdir -p "$ROOT"

# =============================================================================
run_one() {
    local CSV=$1 PROTO=$2 MP=$3 SEED=$4 TAG=$5
    shift 5
    local EXTRA="$*"
    local START=$(date +%s)

    local QS_FLAGS=""
    if [ "$PROTO" = "QSAQMAODV" ]; then
        QS_FLAGS="--qsW1=$QS_W1 --qsW2=$QS_W2 --qsW3=$QS_W3 --qsW4=$QS_W4"
    fi

    "$EXEC" \
        --protocol="$PROTO" --maxPaths="$MP" --seed="$SEED" \
        --scenario="$TAG" --csvFile="$CSV" \
        $QS_FLAGS $BASE $EXTRA > /dev/null 2>&1
    local rc=$?
    local dur=$(( $(date +%s) - START ))

    if [ "$rc" -eq 0 ] || [ "$rc" -eq 139 ]; then
        echo "OK   $TAG $PROTO seed=$SEED (${dur}s)"
    else
        echo "FAIL $TAG $PROTO seed=$SEED rc=$rc"
    fi
}
export -f run_one
export EXEC BASE QS_W1 QS_W2 QS_W3 QS_W4

dispatch() {
    local JOBFILE=$1
    local TOTAL=$(wc -l < "$JOBFILE")
    echo "  Dispatching $TOTAL jobs (JOBS=$JOBS)..."
    cat "$JOBFILE" | xargs -P "$JOBS" -L 1 bash -c 'run_one "$@"' _
}

maxpaths_for() {
    local p=$1
    [ "$p" = "AODV" ] && echo 1 || echo 3
}

# =============================================================================
# Family N — Node density (extended to 100 nodes)
# =============================================================================
family_N() {
    echo "=== Family N — node density ==="
    local CSV="$ROOT/family_N.csv"
    local JF="$ROOT/jobs_N.txt"; > "$JF"
    for n in 5 10 15 20 30 50 75 100; do
        for p in "${PROTOCOLS[@]}"; do
            local mp=$(maxpaths_for "$p")
            for s in $(seq 1 "$SEEDS"); do
                echo "$CSV $p $mp $s N${n} --numNodes=$n" >> "$JF"
            done
        done
    done
    dispatch "$JF"
    echo "  → $CSV"
}

# =============================================================================
# Family S — UAV speed
# =============================================================================
family_S() {
    echo "=== Family S — UAV speed ==="
    local CSV="$ROOT/family_S.csv"
    local JF="$ROOT/jobs_S.txt"; > "$JF"
    for v in 5 10 20 30 50 70; do
        local vmin=$(awk -v v="$v" 'BEGIN{printf "%.0f", v/2}')
        for p in "${PROTOCOLS[@]}"; do
            local mp=$(maxpaths_for "$p")
            for s in $(seq 1 "$SEEDS"); do
                echo "$CSV $p $mp $s V${v} \
                    --meanVelMin=${vmin} --meanVelMax=${v}" >> "$JF"
            done
        done
    done
    dispatch "$JF"
    echo "  → $CSV"
}

# =============================================================================
# Family L — Traffic load
# =============================================================================
family_L() {
    echo "=== Family L — traffic load ==="
    local CSV="$ROOT/family_L.csv"
    local JF="$ROOT/jobs_L.txt"; > "$JF"
    for pi in 1.0 0.5 0.25 0.10 0.05; do
        for p in "${PROTOCOLS[@]}"; do
            local mp=$(maxpaths_for "$p")
            for s in $(seq 1 "$SEEDS"); do
                echo "$CSV $p $mp $s I${pi} --pktInterval=$pi" >> "$JF"
            done
        done
    done
    dispatch "$JF"
    echo "  → $CSV"
}

# =============================================================================
# Family E — Initial energy (uniform, extended range)
# =============================================================================
family_E() {
    echo "=== Family E — initial energy (uniform) ==="
    local CSV="$ROOT/family_E.csv"
    local JF="$ROOT/jobs_E.txt"; > "$JF"
    for e0 in 10 20 30 50 70 100; do
        for p in "${PROTOCOLS[@]}"; do
            local mp=$(maxpaths_for "$p")
            for s in $(seq 1 "$SEEDS"); do
                echo "$CSV $p $mp $s E${e0} \
                    --initialEnergy=$e0 --energyStdDev=0" >> "$JF"
            done
        done
    done
    dispatch "$JF"
    echo "  → $CSV"
}

# =============================================================================
# Family H — Heterogeneous energy (stdDev sweep, mean=50J fixed)
# Highlights QS-QMAODV LOW_ENERGY mode: routes around depleted nodes
# =============================================================================
family_H() {
    echo "=== Family H — heterogeneous energy ==="
    local CSV="$ROOT/family_H.csv"
    local JF="$ROOT/jobs_H.txt"; > "$JF"
    for sd in 0 10 20 30 40; do
        for p in "${PROTOCOLS[@]}"; do
            local mp=$(maxpaths_for "$p")
            for s in $(seq 1 "$SEEDS"); do
                echo "$CSV $p $mp $s H${sd} \
                    --initialEnergy=50 --energyStdDev=${sd}" >> "$JF"
            done
        done
    done
    dispatch "$JF"
    echo "  → $CSV"
}

# =============================================================================
# Family W — w4 sensitivity (QSAQMAODV only)
# =============================================================================
family_W() {
    echo "=== Family W — w4 weight sensitivity ==="
    local CSV="$ROOT/family_W.csv"
    local JF="$ROOT/jobs_W.txt"; > "$JF"
    for w4 in 0.00 0.05 0.10 0.15 0.20 0.25 0.30 0.35 0.40 0.45 0.50; do
        local w1=$(awk -v w4="$w4" 'BEGIN{printf "%.2f", 0.60-w4}')
        for s in $(seq 1 "$SEEDS"); do
            echo "$CSV QSAQMAODV 3 $s W${w4} \
                --qsW1=$w1 --qsW2=0.30 --qsW3=0.10 --qsW4=$w4" >> "$JF"
        done
    done
    dispatch "$JF"
    echo "  → $CSV"
}

# =============================================================================
# Family M — Mixed stress: high-load + low-energy (LOAD_COMBINED trigger)
# 3 load levels x 3 energy levels = 9 scenario combinations
# =============================================================================
family_M() {
    echo "=== Family M — mixed stress (load x energy) ==="
    local CSV="$ROOT/family_M.csv"
    local JF="$ROOT/jobs_M.txt"; > "$JF"
    for pi in 0.50 0.25 0.10; do
        for e0 in 20 50 100; do
            local tag="M_I${pi}_E${e0}"
            for p in "${PROTOCOLS[@]}"; do
                local mp=$(maxpaths_for "$p")
                for s in $(seq 1 "$SEEDS"); do
                    echo "$CSV $p $mp $s $tag \
                        --pktInterval=$pi --initialEnergy=$e0 --energyStdDev=0" >> "$JF"
                done
            done
        done
    done
    dispatch "$JF"
    echo "  → $CSV"
}

# =============================================================================
# Main
# =============================================================================
{
echo "============================================================"
echo " QS-QMAODV Full Parametric Study  (7 Families)"
echo "============================================================"
echo " NS3_DIR  : $NS3_DIR"
echo " Output   : $ROOT"
echo " Families : ${FAMILIES:-N S L E H W M}"
echo " Protocols: ${PROTOCOLS[*]}"
echo " Jobs     : $JOBS   Seeds: $SEEDS   SimTime: ${SIM_TIME}s"
echo " QS-W     : w1=$QS_W1 w2=$QS_W2 w3=$QS_W3 w4=$QS_W4"
echo " Started  : $(date)"
echo "============================================================"
} | tee "$ROOT/run.log"

T0=$(date +%s)
FAMILIES="${FAMILIES:-N S L E H W M}"
for F in $FAMILIES; do
    case $F in
        N) family_N ;;
        S) family_S ;;
        L) family_L ;;
        E) family_E ;;
        H) family_H ;;
        W) family_W ;;
        M) family_M ;;
        *) echo "Unknown family $F (allowed: N S L E H W M)" ;;
    esac
done 2>&1 | tee -a "$ROOT/run.log"
T1=$(date +%s)
DT=$(( T1 - T0 ))

{
echo ""
echo "============================================================"
echo " Done: $(date)"
echo " Wall: $((DT/3600))h $(((DT%3600)/60))m $((DT%60))s"
echo "============================================================"
echo "CSVs:"
ls -1 "$ROOT"/family_*.csv 2>/dev/null | sed 's/^/  /'
echo ""
echo "Plot:"
echo "  python3 ~/qsaqmaodv-ns3/scripts/plot/plot-qsaqmaodv.py \\"
echo "      $ROOT $ROOT/figs"
} | tee -a "$ROOT/run.log"
