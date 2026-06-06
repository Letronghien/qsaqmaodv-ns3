#!/bin/bash
# =============================================================================
# run-sequential.sh — Chạy tuần tự từng họ kịch bản, nhẹ trước nặng sau
# =============================================================================
# Thứ tự chạy (có kết quả sớm nhất trước):
#   Batch 1  W     (210 runs, JOBS=6, ~10 phút)
#   Batch 2  STAT  (250 runs, JOBS=6, ~15 phút)
#   Batch 3  L     (750 runs, JOBS=6, ~35 phút)
#   Batch 4  S     (900 runs, JOBS=6, ~40 phút)
#   Batch 5  E     (900 runs, JOBS=4, ~1 giờ)
#   Batch 6  ELONG (150 runs, JOBS=4, ~40 phút)
#   Batch 7  M     (1350 runs,JOBS=4, ~2 giờ)
#   Batch 8  N-S   N={5..30}   (900 runs, JOBS=3, ~3 giờ)
#   Batch 9  N-M   N={40,50}   (300 runs, JOBS=2, ~8 giờ)
#   Batch 10 N-L   N={75,100}  (300 runs, JOBS=1, ~40-60 giờ) ← chạy đêm
#
# Sử dụng:
#   bash run-sequential.sh              # chạy tất cả
#   STOP_AFTER=7 bash run-sequential.sh # dừng sau batch 7 (trước N lớn)
#   START_FROM=8 bash run-sequential.sh # bắt đầu từ batch 8
# =============================================================================
set -uo pipefail

NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40-qsaqmaodv/ns-3.40}"
EXEC="$NS3_DIR/build/scratch/ns3.40-fanet-sim-optimized"
SEEDS="${SEEDS:-30}"
SIM_TIME="${SIM_TIME:-200}"
RESUME="${RESUME:-0}"
STOP_AFTER="${STOP_AFTER:-10}"
START_FROM="${START_FROM:-1}"

PROTOCOLS=(AODV AOMDV PMAODV QMAODV QSAQMAODV)

QM_ALPHA="0.5"; QM_GAMMA="0.7"; QM_EPSILON="0.1"; QM_DECAY="0.05"
QS_ALPHA0="0.5"; QS_GAMMA="0.9"; QS_EPSILON0="0.3"
QS_LAMBDA="0.1"; QS_WINDOW="5"; QS_PERIOD="10.0"
QS_LOW_E="0.20"; QS_Q_HI="0.70"; QS_Q_LO="0.30"
QS_W1="0.40"; QS_W2="0.30"; QS_W3="0.10"; QS_W4="0.20"

BASE_FLAGS="--mobility=GAUSS --enableEnergy=1 --alpha=0.85 --numNodes=15 --meanVelMin=15 --meanVelMax=25 --pktInterval=0.25 --pktSize=512 --initialEnergy=50 --numFlows=0 --simTime=${SIM_TIME}"
QM_FLAGS="--qmAlpha=${QM_ALPHA} --qmGamma=${QM_GAMMA} --qmEpsilon=${QM_EPSILON} --qmEpsilonDecay=${QM_DECAY}"
QS_FLAGS="--qsAlpha0=${QS_ALPHA0} --qsGamma=${QS_GAMMA} --qsEpsilon0=${QS_EPSILON0} --qsLambda=${QS_LAMBDA} --qsSeqNoWin=${QS_WINDOW} --qsAdaptPeriod=${QS_PERIOD} --qsLowEThresh=${QS_LOW_E} --qsQueueHighThresh=${QS_Q_HI} --qsQueueLowThresh=${QS_Q_LO} --qsW1=${QS_W1} --qsW2=${QS_W2} --qsW3=${QS_W3} --qsW4=${QS_W4}"

# Output dir dùng chung cho tất cả batch
TS=$(date +%Y%m%d-%H%M%S)
ROOT="$HOME/results-sequential-${TS}"
mkdir -p "$ROOT"
DONEFILE="$ROOT/done.txt"; touch "$DONEFILE"
LOGFILE="$ROOT/run_sequential.log"

[ ! -x "$EXEC" ] && echo "[ERROR] Binary không tìm thấy: $EXEC" && exit 1

mp_for() { case "$1" in AODV|DSDV) echo 1;; *) echo 3;; esac; }

qs_flags_for() {
    [ "$1" != "QSAQMAODV" ] && return
    local W3="${2:-${QS_W3}}"
    local W12; W12=$(awk -v w="$W3" 'BEGIN{printf "%.4f",(1-w)/2}')
    echo "--qsAlpha0=${QS_ALPHA0} --qsGamma=${QS_GAMMA} --qsEpsilon0=${QS_EPSILON0} --qsLambda=${QS_LAMBDA} --qsSeqNoWin=${QS_WINDOW} --qsAdaptPeriod=${QS_PERIOD} --qsLowEThresh=${QS_LOW_E} --qsQueueHighThresh=${QS_Q_HI} --qsQueueLowThresh=${QS_Q_LO} --qsW1=${W12} --qsW2=${W12} --qsW3=${W3} --qsW4=${QS_W4}"
}

add_job() {
    local JF="$1" CSV="$2" P="$3" S="$4" TAG="$5" SW="${6:-}"
    local MP; MP=$(mp_for "$P")
    local PF; PF=$(qs_flags_for "$P" "${7:-}")
    printf '%s\n' "$CSV $P $MP $S $TAG $BASE_FLAGS $QM_FLAGS $SW $PF" | tr -s ' ' >> "$JF"
}

run_one() {
    local CSV="$1" PROTO="$2" MP="$3" SEED="$4" TAG="$5"; shift 5
    local EXTRA="$*"
    local KEY="${TAG}_${PROTO}_s${SEED}"
    if [ "${RESUME:-0}" = "1" ] && grep -qF "$KEY" "${DONEFILE}" 2>/dev/null; then
        echo "SKIP $KEY"; return 0
    fi
    local T0; T0=$(date +%s)
    "$EXEC" --protocol="$PROTO" --maxPaths="$MP" --seed="$SEED" \
            --scenario="$TAG" --csvFile="$CSV" $EXTRA > /dev/null 2>&1
    local RC=$? DUR=$(( $(date +%s) - T0 ))
    if [ "$RC" -eq 0 ] || [ "$RC" -eq 139 ]; then
        echo "$KEY" >> "$DONEFILE"; echo "OK   $KEY (${DUR}s)"
    else
        echo "FAIL $KEY rc=$RC"
    fi
}
export -f run_one mp_for
export EXEC DONEFILE RESUME

run_batch() {
    local BATCH_NUM="$1" LABEL="$2" JOBS="$3" JF="$4" CSV="$5"
    [ "$BATCH_NUM" -lt "$START_FROM" ] && echo "--- Skip batch $BATCH_NUM ($LABEL)" && return
    [ "$BATCH_NUM" -gt "$STOP_AFTER" ] && echo "--- Stop after batch $((BATCH_NUM-1))" && exit 0
    local T0; T0=$(date +%s)
    local TOTAL; TOTAL=$(wc -l < "$JF")
    echo ""
    echo "╔══════════════════════════════════════════════"
    echo "║ Batch $BATCH_NUM — $LABEL  ($TOTAL runs, JOBS=$JOBS)"
    echo "╚══════════════════════════════════════════════"
    cat "$JF" | xargs -P "$JOBS" -L 1 bash -c 'run_one "$@"' _
    local WALL=$(( $(date +%s) - T0 ))
    local OK_N; OK_N=$(grep -c "^OK" "$LOGFILE" 2>/dev/null || echo "?")
    printf "  ✓ Done in %dh %dm %ds | CSV: %s\n" \
        $((WALL/3600)) $(((WALL%3600)/60)) $((WALL%60)) "$CSV"
}

# ---------------------------------------------------------------------------
# Build job files cho tất cả batch
# ---------------------------------------------------------------------------
echo "=== Building job files ===" | tee "$LOGFILE"

# --- Batch 1: W (QSAQMAODV only, sweep w3) ---
JF_W="$ROOT/jobs_W.txt"; CSV_W="$ROOT/family_W_weight.csv"; > "$JF_W"; rm -f "$CSV_W"
for W3 in 0.00 0.05 0.10 0.20 0.30 0.40 0.50; do
    local_W12=$(awk -v w="$W3" 'BEGIN{printf "%.4f",(1-w)/2}')
    MP=$(mp_for "QSAQMAODV")
    for S in $(seq 1 "$SEEDS"); do
        printf '%s\n' "$CSV_W QSAQMAODV $MP $S W${W3} $BASE_FLAGS $QM_FLAGS $(qs_flags_for QSAQMAODV $W3)" | tr -s ' ' >> "$JF_W"
    done
done

# --- Batch 2: STAT ---
JF_STAT="$ROOT/jobs_STAT.txt"; CSV_STAT="$ROOT/stat_baseline.csv"; > "$JF_STAT"; rm -f "$CSV_STAT"
for P in "${PROTOCOLS[@]}"; do
    for S in $(seq 1 50); do add_job "$JF_STAT" "$CSV_STAT" "$P" "$S" "STAT" ""; done
done

# --- Batch 3: L ---
JF_L="$ROOT/jobs_L.txt"; CSV_L="$ROOT/family_L_load.csv"; > "$JF_L"; rm -f "$CSV_L"
for PI in 1.0 0.5 0.25 0.1 0.05; do
    for P in "${PROTOCOLS[@]}"; do
        for S in $(seq 1 "$SEEDS"); do add_job "$JF_L" "$CSV_L" "$P" "$S" "I${PI}" "--pktInterval=${PI}"; done
    done
done

# --- Batch 4: S ---
JF_S="$ROOT/jobs_S.txt"; CSV_S="$ROOT/family_S_speed.csv"; > "$JF_S"; rm -f "$CSV_S"
for VMAX in 5 10 20 30 50 70; do
    VMIN=$(awk -v v="$VMAX" 'BEGIN{printf "%.1f",v/2}')
    for P in "${PROTOCOLS[@]}"; do
        for S in $(seq 1 "$SEEDS"); do add_job "$JF_S" "$CSV_S" "$P" "$S" "V${VMAX}" "--meanVelMin=${VMIN} --meanVelMax=${VMAX}"; done
    done
done

# --- Batch 5: E ---
JF_E="$ROOT/jobs_E.txt"; CSV_E="$ROOT/family_E_energy.csv"; > "$JF_E"; rm -f "$CSV_E"
for E0 in 10 20 30 50 75 100; do
    for P in "${PROTOCOLS[@]}"; do
        for S in $(seq 1 "$SEEDS"); do add_job "$JF_E" "$CSV_E" "$P" "$S" "E${E0}" "--initialEnergy=${E0}"; done
    done
done

# --- Batch 6: ELONG ---
JF_EL="$ROOT/jobs_ELONG.txt"; CSV_EL="$ROOT/elong_depletion.csv"; > "$JF_EL"; rm -f "$CSV_EL"
for P in "${PROTOCOLS[@]}"; do
    for S in $(seq 1 "$SEEDS"); do add_job "$JF_EL" "$CSV_EL" "$P" "$S" "ELONG" "--initialEnergy=10 --simTime=350"; done
done

# --- Batch 7: M ---
JF_M="$ROOT/jobs_M.txt"; CSV_M="$ROOT/family_M_mixed.csv"; > "$JF_M"; rm -f "$CSV_M"
for PI in 0.5 0.25 0.05; do
    for E0 in 10 30 50; do
        for P in "${PROTOCOLS[@]}"; do
            for S in $(seq 1 "$SEEDS"); do add_job "$JF_M" "$CSV_M" "$P" "$S" "M_I${PI}_E${E0}" "--pktInterval=${PI} --initialEnergy=${E0}"; done
        done
    done
done

# --- Batch 8: N-small (N=5..30) ---
JF_NS="$ROOT/jobs_N_small.txt"; CSV_NS="$ROOT/family_N_small.csv"; > "$JF_NS"; rm -f "$CSV_NS"
for N in 5 10 15 20 25 30; do
    for P in "${PROTOCOLS[@]}"; do
        for S in $(seq 1 "$SEEDS"); do add_job "$JF_NS" "$CSV_NS" "$P" "$S" "N${N}" "--numNodes=${N}"; done
    done
done

# --- Batch 9: N-medium (N=40,50) ---
JF_NM="$ROOT/jobs_N_medium.txt"; CSV_NM="$ROOT/family_N_medium.csv"; > "$JF_NM"; rm -f "$CSV_NM"
for N in 40 50; do
    for P in "${PROTOCOLS[@]}"; do
        for S in $(seq 1 "$SEEDS"); do add_job "$JF_NM" "$CSV_NM" "$P" "$S" "N${N}" "--numNodes=${N}"; done
    done
done

# --- Batch 10: N-large (N=75,100) ---
JF_NL="$ROOT/jobs_N_large.txt"; CSV_NL="$ROOT/family_N_large.csv"; > "$JF_NL"; rm -f "$CSV_NL"
for N in 75 100; do
    for P in "${PROTOCOLS[@]}"; do
        for S in $(seq 1 "$SEEDS"); do add_job "$JF_NL" "$CSV_NL" "$P" "$S" "N${N}" "--numNodes=${N}"; done
    done
done

echo "Job files built. Output: $ROOT" | tee -a "$LOGFILE"
echo "Started: $(date)" | tee -a "$LOGFILE"
echo ""

# ---------------------------------------------------------------------------
# Chạy tuần tự
# ---------------------------------------------------------------------------
{
run_batch  1 "W (w3 sweep)"      6 "$JF_W"  "$CSV_W"
run_batch  2 "STAT (baseline)"   6 "$JF_STAT" "$CSV_STAT"
run_batch  3 "L (load)"          6 "$JF_L"  "$CSV_L"
run_batch  4 "S (speed)"         6 "$JF_S"  "$CSV_S"
run_batch  5 "E (energy)"        4 "$JF_E"  "$CSV_E"
run_batch  6 "ELONG (T=350s)"    4 "$JF_EL" "$CSV_EL"
run_batch  7 "M (load×energy)"   4 "$JF_M"  "$CSV_M"
run_batch  8 "N-small N≤30"      3 "$JF_NS" "$CSV_NS"
run_batch  9 "N-medium N=40,50"  2 "$JF_NM" "$CSV_NM"
run_batch 10 "N-large N=75,100"  1 "$JF_NL" "$CSV_NL"
} 2>&1 | tee -a "$LOGFILE"

echo ""
echo "=== ALL DONE: $(date) ===" | tee -a "$LOGFILE"
echo "Results: $ROOT" | tee -a "$LOGFILE"
ls -1 "$ROOT"/*.csv 2>/dev/null | while read f; do
    printf "  %5d rows — %s\n" "$(( $(wc -l < "$f") - 1 ))" "$(basename $f)"
done | tee -a "$LOGFILE"
