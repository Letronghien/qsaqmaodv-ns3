#!/bin/bash
# run-paper-experiments.sh
# ----------------------------------------------------------------------------
# Comprehensive parametric study for the QMAODV paper.
#
# Goal: identify the operating regime where QMAODV outperforms the
# AODV/DSDV/AOMDV/PMAODV baselines, by sweeping over:
#   - Q-learning hyperparameters (α, γ, ε, decay)        — Family H
#   - Number of UAV nodes (density)                       — Family N
#   - UAV maximum speed (mobility)                        — Family S
#   - CBR traffic rate (load)                             — Family L
#   - Packet size                                         — Family P
#   - Number of concurrent flows                          — Family F
#
# Each family is a 1-D sweep over one variable while others stay at the
# "baseline" (default scenario) values. Results land in separate CSVs so
# plot-paper-figures.py can pick the right one for each figure.
#
# Compute estimate on JOBS=6 (n2-standard-8): ~2.5 hours total.
#
# Usage:
#   tmux new -s qm-paper
#   bash run-paper-experiments.sh                # all families
#   FAMILIES="N S" bash run-paper-experiments.sh # only Family N and S
# ----------------------------------------------------------------------------
set -u

NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40/ns-3.40}"
EXEC="$NS3_DIR/build/scratch/ns3.40-fanet-sim-optimized"
JOBS="${JOBS:-6}"
SEEDS="${SEEDS:-5}"
SIM_TIME="${SIM_TIME:-200}"

# Strategy-A hyperparams (winners from tuning)
QM_ALPHA="${QM_ALPHA:-0.5}"
QM_GAMMA="${QM_GAMMA:-0.7}"
QM_EPSILON="${QM_EPSILON:-0.1}"
QM_DECAY="${QM_DECAY:-0.05}"

# SA-QMAODV hyperparams — Winner A from tune-saqmaodv stage1+stage2 (PDR=49.05% at N=15)
#   λ=0.5, W=10s, P=1.0s, γ=0.9 (paper default), α₀/ε₀ trivial (adapt nhanh)
SA_LAMBDA="${SA_LAMBDA:-0.5}"
SA_WINDOW="${SA_WINDOW:-10}"
SA_PERIOD="${SA_PERIOD:-1.0}"
SA_GAMMA="${SA_GAMMA:-0.9}"
SA_ALPHA0="${SA_ALPHA0:-0.5}"
SA_EPSILON0="${SA_EPSILON0:-0.3}"

# Output
TS=$(date +%Y%m%d-%H%M%S)
ROOT="$HOME/results-paper-${TS}"
mkdir -p "$ROOT"

FAMILIES="${FAMILIES:-H N S L P F}"

# Baseline (used in every family except the one being swept)
BASE="--mobility=GAUSS --enableEnergy=1 --alpha=0.85 \
      --numNodes=15 --meanVelMin=15 --meanVelMax=25 \
      --pktInterval=0.25 --pktSize=512 --numFlows=0 \
      --simTime=$SIM_TIME"

# 5 protocols cho saqmaodv-ns3 (paper SA-QMAODV extended evaluation)
# Override: PROTOCOLS="AODV AOMDV PMAODV QMAODV" để bỏ SAQMAODV
PROTOCOLS=(${PROTOCOLS:-AODV AOMDV PMAODV QMAODV SAQMAODV})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
run_one() {
    local CSV=$1 PROTO=$2 MP=$3 SEED=$4 SCEN_TAG=$5
    shift 5
    local extra_args="$*"
    local START=$(date +%s)

    # SA-QMAODV winner-A flags (no-op cho protocol khác vì driver chỉ đọc khi --protocol=SAQMAODV)
    local SA_FLAGS=""
    if [ "$PROTO" = "SAQMAODV" ]; then
        SA_FLAGS="--saAlpha0=$SA_ALPHA0 --saGamma=$SA_GAMMA --saEpsilon0=$SA_EPSILON0 \
                  --saLambda=$SA_LAMBDA --saSeqNoWin=$SA_WINDOW \
                  --saAdaptPeriod=$SA_PERIOD --saLowEThresh=0.20 \
                  --saW1=0.5 --saW2=0.4 --saW3=0.1"
    fi

    "$EXEC" \
        --protocol="$PROTO" --maxPaths="$MP" --seed="$SEED" \
        --scenario="$SCEN_TAG" --csvFile="$CSV" \
        --qmAlpha="$QM_ALPHA" --qmGamma="$QM_GAMMA" \
        --qmEpsilon="$QM_EPSILON" --qmEpsilonDecay="$QM_DECAY" \
        $SA_FLAGS \
        $BASE $extra_args > /dev/null 2>&1
    local rc=$?
    local dur=$(( $(date +%s) - START ))
    if [ "$rc" -eq 0 ] || [ "$rc" -eq 139 ]; then
        echo "OK   $SCEN_TAG $PROTO seed=$SEED (${dur}s)"
    else
        echo "FAIL $SCEN_TAG $PROTO seed=$SEED rc=$rc"
    fi
}
export -f run_one
export EXEC BASE QM_ALPHA QM_GAMMA QM_EPSILON QM_DECAY
export SA_LAMBDA SA_WINDOW SA_PERIOD SA_GAMMA SA_ALPHA0 SA_EPSILON0

dispatch_jobs() {
    local JOBFILE=$1
    cat "$JOBFILE" | xargs -P "$JOBS" -L 1 bash -c 'run_one "$@"' _
}

# ---------------------------------------------------------------------------
# Family H — Hyperparameter sensitivity (only QMAODV)
#   α ∈ {0.1, 0.3, 0.5, 0.7}
#   γ ∈ {0.6, 0.7, 0.8, 0.9, 0.95}
#   ε ∈ {0.1, 0.3, 0.5}
#   decay ∈ {0.02, 0.05, 0.1}
#   Fixed N=15, baseline traffic. Seeds=3 (4×5×3×3×3 = 540 runs ≈ 30 min)
# ---------------------------------------------------------------------------
family_H() {
    echo "=== Family H — hyperparameter grid (~30 min) ==="
    local CSV="$ROOT/family_H_hyper.csv"
    rm -f "$CSV"
    local JOBFILE="$ROOT/jobs_H.txt"; > "$JOBFILE"
    for a in 0.1 0.3 0.5 0.7; do
        for g in 0.6 0.7 0.8 0.9 0.95; do
            for e in 0.1 0.3 0.5; do
                for d in 0.02 0.05 0.1; do
                    for s in 1 2 3; do
                        local tag="a${a}-g${g}-e${e}-d${d}"
                        echo "$CSV QMAODV 3 $s $tag \
                            --qmAlpha=$a --qmGamma=$g \
                            --qmEpsilon=$e --qmEpsilonDecay=$d" >> "$JOBFILE"
                    done
                done
            done
        done
    done
    local TOTAL=$(wc -l < "$JOBFILE")
    echo " jobs: $TOTAL"
    dispatch_jobs "$JOBFILE"
}

# ---------------------------------------------------------------------------
# Family N — Node count (density)
#   N ∈ {5, 8, 10, 12, 15, 18, 20, 25, 30}
#   Baseline traffic & mobility, all 5 protocols, 5 seeds (= 225 runs ≈ 15 min)
# ---------------------------------------------------------------------------
family_N() {
    echo "=== Family N — node count sweep ==="
    local CSV="$ROOT/family_N_nodes.csv"
    rm -f "$CSV"
    local JOBFILE="$ROOT/jobs_N.txt"; > "$JOBFILE"
    for n in 5 8 10 12 15 18 20 25 30; do
        for p in "${PROTOCOLS[@]}"; do
            local mp=3; [ "$p" = "AODV" ] || [ "$p" = "DSDV" ] && mp=1
            for s in $(seq 1 "$SEEDS"); do
                echo "$CSV $p $mp $s N${n} --numNodes=$n" >> "$JOBFILE"
            done
        done
    done
    echo " jobs: $(wc -l < $JOBFILE)"
    dispatch_jobs "$JOBFILE"
}

# ---------------------------------------------------------------------------
# Family S — UAV max speed
#   maxSpeed ∈ {5, 10, 20, 30, 50, 70} m/s
#   Fixed N=15, all 5 protocols, 5 seeds (= 150 runs ≈ 10 min)
# ---------------------------------------------------------------------------
family_S() {
    echo "=== Family S — speed sweep ==="
    local CSV="$ROOT/family_S_speed.csv"
    rm -f "$CSV"
    local JOBFILE="$ROOT/jobs_S.txt"; > "$JOBFILE"
    for v in 5 10 20 30 50 70; do
        local vmin=$(awk -v v=$v 'BEGIN{print v/2}')
        for p in "${PROTOCOLS[@]}"; do
            local mp=3; [ "$p" = "AODV" ] || [ "$p" = "DSDV" ] && mp=1
            for s in $(seq 1 "$SEEDS"); do
                echo "$CSV $p $mp $s V${v} \
                    --meanVelMin=$vmin --meanVelMax=$v" >> "$JOBFILE"
            done
        done
    done
    echo " jobs: $(wc -l < $JOBFILE)"
    dispatch_jobs "$JOBFILE"
}

# ---------------------------------------------------------------------------
# Family L — CBR traffic rate (load)
#   pktInterval ∈ {1.0, 0.5, 0.25, 0.1, 0.05} (= 1, 2, 4, 10, 20 pps)
#   Fixed N=15, baseline mobility, all 5 protocols, 5 seeds (= 125 runs ≈ 8 min)
# ---------------------------------------------------------------------------
family_L() {
    echo "=== Family L — load sweep ==="
    local CSV="$ROOT/family_L_load.csv"
    rm -f "$CSV"
    local JOBFILE="$ROOT/jobs_L.txt"; > "$JOBFILE"
    for pi in 1.0 0.5 0.25 0.1 0.05; do
        for p in "${PROTOCOLS[@]}"; do
            local mp=3; [ "$p" = "AODV" ] || [ "$p" = "DSDV" ] && mp=1
            for s in $(seq 1 "$SEEDS"); do
                echo "$CSV $p $mp $s I${pi} --pktInterval=$pi" >> "$JOBFILE"
            done
        done
    done
    echo " jobs: $(wc -l < $JOBFILE)"
    dispatch_jobs "$JOBFILE"
}

# ---------------------------------------------------------------------------
# Family P — Packet size
#   pktSize ∈ {64, 128, 256, 512, 1024, 1500} bytes
#   = 150 runs ≈ 10 min
# ---------------------------------------------------------------------------
family_P() {
    echo "=== Family P — packet size sweep ==="
    local CSV="$ROOT/family_P_pktsize.csv"
    rm -f "$CSV"
    local JOBFILE="$ROOT/jobs_P.txt"; > "$JOBFILE"
    for sz in 64 128 256 512 1024 1500; do
        for p in "${PROTOCOLS[@]}"; do
            local mp=3; [ "$p" = "AODV" ] || [ "$p" = "DSDV" ] && mp=1
            for s in $(seq 1 "$SEEDS"); do
                echo "$CSV $p $mp $s S${sz} --pktSize=$sz" >> "$JOBFILE"
            done
        done
    done
    echo " jobs: $(wc -l < $JOBFILE)"
    dispatch_jobs "$JOBFILE"
}

# ---------------------------------------------------------------------------
# Family F — Concurrent flow count
#   numFlows ∈ {1, 2, 3, 5, 7}
#   Fixed N=20 (need ≥ 2·numFlows nodes), = 125 runs ≈ 8 min
# ---------------------------------------------------------------------------
family_F() {
    echo "=== Family F — multi-flow sweep ==="
    local CSV="$ROOT/family_F_flows.csv"
    rm -f "$CSV"
    local JOBFILE="$ROOT/jobs_F.txt"; > "$JOBFILE"
    for nf in 1 2 3 5 7; do
        for p in "${PROTOCOLS[@]}"; do
            local mp=3; [ "$p" = "AODV" ] || [ "$p" = "DSDV" ] && mp=1
            for s in $(seq 1 "$SEEDS"); do
                echo "$CSV $p $mp $s F${nf} \
                    --numNodes=20 --numFlows=$nf" >> "$JOBFILE"
            done
        done
    done
    echo " jobs: $(wc -l < $JOBFILE)"
    dispatch_jobs "$JOBFILE"
}

# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
{
echo "================================================================="
echo " QMAODV Parametric Study"
echo "================================================================="
echo " NS3:        $NS3_DIR"
echo " Output:     $ROOT"
echo " Families:   $FAMILIES"
echo " Jobs:       $JOBS  Seeds: $SEEDS  SimTime: ${SIM_TIME}s"
echo " QMAODV cfg: α=$QM_ALPHA γ=$QM_GAMMA ε=$QM_EPSILON decay=$QM_DECAY"
echo " Started:    $(date)"
echo "================================================================="
} | tee "$ROOT/run.log"

START_TS=$(date +%s)
for F in $FAMILIES; do
    case $F in
        H) family_H ;;
        N) family_N ;;
        S) family_S ;;
        L) family_L ;;
        P) family_P ;;
        F) family_F ;;
        *) echo "Unknown family: $F (allowed: H N S L P F)"; continue ;;
    esac
done 2>&1 | tee -a "$ROOT/run.log"
END_TS=$(date +%s)
TOTAL_SEC=$(( END_TS - START_TS ))

{
echo
echo "================================================================="
echo " Done: $(date)"
echo " Wall: $((TOTAL_SEC/3600))h $(((TOTAL_SEC%3600)/60))m"
echo "================================================================="
echo
echo "CSVs:"
ls -1 "$ROOT"/family_*.csv 2>/dev/null
echo
echo "Next:"
echo "  python3 ~/fanet-multipath-ns3/scripts/plot/plot-paper-figures.py \\"
echo "      --nodes-csv \$BIGBATCH/merged.csv \\"
echo "      --speed-csv $ROOT/family_S_speed.csv \\"
echo "      --load-csv  $ROOT/family_L_load.csv \\"
echo "      --pktsize-csv $ROOT/family_P_pktsize.csv \\"
echo "      --flows-csv $ROOT/family_F_flows.csv \\"
echo "      --hyper-csv $ROOT/family_H_hyper.csv \\"
echo "      --outdir    $ROOT/figs"
} | tee -a "$ROOT/run.log"
