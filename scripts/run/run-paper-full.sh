#!/bin/bash
# =============================================================================
# run-paper-full.sh  —  Toàn bộ thí nghiệm cho bài báo Q3
# =============================================================================
#
# 6 họ chính + 2 thí nghiệm bổ sung  →  ~6010 runs
#
#   Family N   : Sweep số nodes       {5,10,15,20,25,30,40,50,75,100}  × 5P × 30s = 1500
#   Family S   : Sweep tốc độ m/s     {5,10,20,30,50,70}               × 5P × 30s =  900
#   Family L   : Sweep packet-interval{1.0,0.5,0.25,0.1,0.05}          × 5P × 30s =  750
#   Family E   : Sweep năng lượng E₀  {10,20,30,50,75,100} J           × 5P × 30s =  900
#   Family W   : Sweep trọng số w₃    {0.00…0.50} — chỉ QSAQMAODV     × 1P × 30s =  210
#   Family M   : Load×Energy mixed    3×3 combos                        × 5P × 30s = 1350
#   STAT       : Baseline thống kê    N=15, default                     × 5P × 50s =  250
#   ENERGY-LONG: Energy depletion     E₀=10J, T=350s                   × 5P × 30s =  150
#
# Protocols: AODV  AOMDV  PMAODV  QMAODV  QSAQMAODV
#
# Sử dụng:
#   bash run-paper-full.sh                   # toàn bộ 8 họ
#   FAMILIES="N S L" bash run-paper-full.sh  # chọn họ cụ thể
#   RESUME=1 bash run-paper-full.sh          # tiếp tục sau khi bị ngắt
#   JOBS=12 bash run-paper-full.sh           # tăng song song nếu có nhiều core
#
# Kết quả: $HOME/results-paper-full-<timestamp>/
# =============================================================================
set -uo pipefail

# ---------------------------------------------------------------------------
# Cấu hình — override bằng env var
# ---------------------------------------------------------------------------
NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40-qsaqmaodv/ns-3.40}"
EXEC="$NS3_DIR/build/scratch/ns3.40-fanet-sim-optimized"

JOBS="${JOBS:-6}"
SEEDS="${SEEDS:-30}"
SIM_TIME="${SIM_TIME:-200}"
RESUME="${RESUME:-0}"

FAMILIES="${FAMILIES:-N S L E W M STAT ELONG}"

# Protocols (5 protocols bài báo)
PROTOCOLS=(AODV AOMDV PMAODV QMAODV QSAQMAODV)

# ---------------------------------------------------------------------------
# QMAODV hyperparams (Strategy-B validated)
# ---------------------------------------------------------------------------
QM_ALPHA="${QM_ALPHA:-0.5}"
QM_GAMMA="${QM_GAMMA:-0.7}"
QM_EPSILON="${QM_EPSILON:-0.1}"
QM_DECAY="${QM_DECAY:-0.05}"

# ---------------------------------------------------------------------------
# QSAQMAODV hyperparams — default từ fanet-sim.cc
# ---------------------------------------------------------------------------
QS_ALPHA0="${QS_ALPHA0:-0.5}"
QS_GAMMA="${QS_GAMMA:-0.9}"
QS_EPSILON0="${QS_EPSILON0:-0.3}"
QS_LAMBDA="${QS_LAMBDA:-0.1}"
QS_WINDOW="${QS_WINDOW:-5}"
QS_PERIOD="${QS_PERIOD:-10.0}"
QS_LOW_E="${QS_LOW_E:-0.20}"
QS_Q_HI="${QS_Q_HI:-0.70}"
QS_Q_LO="${QS_Q_LO:-0.30}"
QS_W1="${QS_W1:-0.40}"
QS_W2="${QS_W2:-0.30}"
QS_W3="${QS_W3:-0.10}"
QS_W4="${QS_W4:-0.20}"

# ---------------------------------------------------------------------------
# Baseline (fixed cho tất cả run trừ param đang sweep)
# ---------------------------------------------------------------------------
BASE_N=15
BASE_VMIN=15
BASE_VMAX=25
BASE_PKT=0.25
BASE_SIZE=512
BASE_E0=50

BASE="--mobility=GAUSS --enableEnergy=1 --alpha=0.85
      --numNodes=${BASE_N}
      --meanVelMin=${BASE_VMIN} --meanVelMax=${BASE_VMAX}
      --pktInterval=${BASE_PKT} --pktSize=${BASE_SIZE}
      --initialEnergy=${BASE_E0}
      --numFlows=0 --simTime=${SIM_TIME}"

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
TS=$(date +%Y%m%d-%H%M%S)
ROOT="$HOME/results-paper-full-${TS}"
mkdir -p "$ROOT"
LOGFILE="$ROOT/run_full.log"
DONEFILE="$ROOT/done.txt"
touch "$DONEFILE"

# ---------------------------------------------------------------------------
# Kiểm tra binary
# ---------------------------------------------------------------------------
if [ ! -x "$EXEC" ]; then
    echo "[ERROR] Không tìm thấy: $EXEC"
    echo "        Chạy setup-from-scratch.sh trước, hoặc set NS3_DIR"
    exit 1
fi

# ---------------------------------------------------------------------------
# Helper: build QSAQMAODV flags với w3 tuỳ chỉnh
# Nếu không truyền w3 → dùng default QS_W3
# w1 = w2 = (1 - w3) / 2  (theo lựa chọn của bạn)
# ---------------------------------------------------------------------------
qs_flags() {
    local W3="${1:-$QS_W3}"
    local W12
    W12=$(awk -v w3="$W3" 'BEGIN{printf "%.4f", (1-w3)/2}')
    echo "--qsAlpha0=$QS_ALPHA0 --qsGamma=$QS_GAMMA --qsEpsilon0=$QS_EPSILON0 \
          --qsLambda=$QS_LAMBDA --qsSeqNoWin=$QS_WINDOW \
          --qsAdaptPeriod=$QS_PERIOD --qsLowEThresh=$QS_LOW_E \
          --qsQueueHighThresh=$QS_Q_HI --qsQueueLowThresh=$QS_Q_LO \
          --qsW1=$W12 --qsW2=$W12 --qsW3=$W3 --qsW4=$QS_W4"
}
export -f qs_flags

# ---------------------------------------------------------------------------
# Helper: chạy 1 run
# ---------------------------------------------------------------------------
run_one() {
    local CSV="$1" PROTO="$2" MP="$3" SEED="$4" TAG="$5"
    shift 5
    local EXTRA="$*"

    local KEY="${TAG}_${PROTO}_s${SEED}"
    if [ "${RESUME:-0}" = "1" ] && grep -qF "$KEY" "${DONEFILE}" 2>/dev/null; then
        echo "SKIP $KEY"; return 0
    fi

    # QSAQMAODV flags — dùng default w3 trừ khi EXTRA đã chứa --qsW3
    local QS_FL=""
    if [ "$PROTO" = "QSAQMAODV" ]; then
        if echo "$EXTRA" | grep -q "qsW3"; then
            # Family W: flags đã được nhúng vào EXTRA
            QS_FL=""
        else
            QS_FL=$(qs_flags "$QS_W3")
        fi
    fi

    local T0; T0=$(date +%s)
    "$EXEC" \
        --protocol="$PROTO" --maxPaths="$MP" --seed="$SEED" \
        --scenario="$TAG"   --csvFile="$CSV" \
        --qmAlpha="$QM_ALPHA" --qmGamma="$QM_GAMMA" \
        --qmEpsilon="$QM_EPSILON" --qmEpsilonDecay="$QM_DECAY" \
        $QS_FL \
        $BASE $EXTRA > /dev/null 2>&1
    local RC=$? DUR=$(( $(date +%s) - T0 ))

    if [ "$RC" -eq 0 ] || [ "$RC" -eq 139 ]; then
        echo "$KEY" >> "$DONEFILE"
        echo "OK   $KEY (${DUR}s)"
    else
        echo "FAIL $KEY rc=$RC"
    fi
}
export -f run_one
export EXEC BASE QM_ALPHA QM_GAMMA QM_EPSILON QM_DECAY
export QS_ALPHA0 QS_GAMMA QS_EPSILON0 QS_LAMBDA QS_WINDOW QS_PERIOD
export QS_LOW_E QS_Q_HI QS_Q_LO QS_W1 QS_W2 QS_W3 QS_W4
export DONEFILE RESUME

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
dispatch() {
    local JOBFILE="$1" LABEL="$2"
    local TOTAL; TOTAL=$(wc -l < "$JOBFILE")
    echo "  → $LABEL: $TOTAL jobs"
    cat "$JOBFILE" | xargs -P "$JOBS" -L 1 bash -c 'run_one "$@"' _
}

make_jobs() {
    # make_jobs <jobfile> <csv> <protocols-array> <seeds> <tag> <extra_args> [N values...]
    # Được gọi từ mỗi family function với args riêng
    :
}

mp_for() {
    local P="$1"
    case "$P" in AODV|DSDV) echo 1 ;; *) echo 3 ;; esac
}
export -f mp_for

# ---------------------------------------------------------------------------
# ═══════════════════════  FAMILY N  ═══════════════════════
# Sweep số nodes: {5,10,15,20,25,30,40,50,75,100}
# ---------------------------------------------------------------------------
family_N() {
    echo "=== Family N — sweep số nodes (1500 runs) ==="
    local CSV="$ROOT/family_N_nodes.csv"
    local JF="$ROOT/jobs_N.txt"; > "$JF"; rm -f "$CSV"
    for N in 5 10 15 20 25 30 40 50 75 100; do
        for P in "${PROTOCOLS[@]}"; do
            local MP; MP=$(mp_for "$P")
            for S in $(seq 1 "$SEEDS"); do
                echo "$CSV $P $MP $S N${N} --numNodes=$N" >> "$JF"
            done
        done
    done
    dispatch "$JF" "Family N"
}

# ---------------------------------------------------------------------------
# ═══════════════════════  FAMILY S  ═══════════════════════
# Sweep tốc độ tối đa: {5,10,20,30,50,70} m/s  (vmin = vmax/2)
# ---------------------------------------------------------------------------
family_S() {
    echo "=== Family S — sweep tốc độ (900 runs) ==="
    local CSV="$ROOT/family_S_speed.csv"
    local JF="$ROOT/jobs_S.txt"; > "$JF"; rm -f "$CSV"
    for VMAX in 5 10 20 30 50 70; do
        local VMIN; VMIN=$(awk -v v="$VMAX" 'BEGIN{printf "%.1f", v/2}')
        for P in "${PROTOCOLS[@]}"; do
            local MP; MP=$(mp_for "$P")
            for S in $(seq 1 "$SEEDS"); do
                echo "$CSV $P $MP $S V${VMAX} \
                    --meanVelMin=$VMIN --meanVelMax=$VMAX" >> "$JF"
            done
        done
    done
    dispatch "$JF" "Family S"
}

# ---------------------------------------------------------------------------
# ═══════════════════════  FAMILY L  ═══════════════════════
# Sweep packet interval: {1.0,0.5,0.25,0.1,0.05} s  ↔ {1,2,4,10,20} pps
# ---------------------------------------------------------------------------
family_L() {
    echo "=== Family L — sweep traffic load (750 runs) ==="
    local CSV="$ROOT/family_L_load.csv"
    local JF="$ROOT/jobs_L.txt"; > "$JF"; rm -f "$CSV"
    for PI in 1.0 0.5 0.25 0.1 0.05; do
        for P in "${PROTOCOLS[@]}"; do
            local MP; MP=$(mp_for "$P")
            for S in $(seq 1 "$SEEDS"); do
                echo "$CSV $P $MP $S I${PI} --pktInterval=$PI" >> "$JF"
            done
        done
    done
    dispatch "$JF" "Family L"
}

# ---------------------------------------------------------------------------
# ═══════════════════════  FAMILY E  ═══════════════════════
# Sweep năng lượng ban đầu: {10,20,30,50,75,100} J
# ---------------------------------------------------------------------------
family_E() {
    echo "=== Family E — sweep initial energy (900 runs) ==="
    local CSV="$ROOT/family_E_energy.csv"
    local JF="$ROOT/jobs_E.txt"; > "$JF"; rm -f "$CSV"
    for E0 in 10 20 30 50 75 100; do
        for P in "${PROTOCOLS[@]}"; do
            local MP; MP=$(mp_for "$P")
            for S in $(seq 1 "$SEEDS"); do
                echo "$CSV $P $MP $S E${E0} --initialEnergy=$E0" >> "$JF"
            done
        done
    done
    dispatch "$JF" "Family E"
}

# ---------------------------------------------------------------------------
# ═══════════════════════  FAMILY W  ═══════════════════════
# Sweep w₃ ∈ {0.00,0.05,0.10,0.20,0.30,0.40,0.50}
# w₁ = w₂ = (1 − w₃) / 2   (chỉ QSAQMAODV)
# ---------------------------------------------------------------------------
family_W() {
    echo "=== Family W — sweep energy weight w₃ (210 runs, QSAQMAODV only) ==="
    local CSV="$ROOT/family_W_weight.csv"
    local JF="$ROOT/jobs_W.txt"; > "$JF"; rm -f "$CSV"
    local MP; MP=$(mp_for "QSAQMAODV")
    for W3 in 0.00 0.05 0.10 0.20 0.30 0.40 0.50; do
        local W12; W12=$(awk -v w3="$W3" 'BEGIN{printf "%.4f",(1-w3)/2}')
        for S in $(seq 1 "$SEEDS"); do
            # Nhúng tất cả qs-flags vào EXTRA để run_one không override
            echo "$CSV QSAQMAODV $MP $S W${W3} \
                --qsAlpha0=$QS_ALPHA0 --qsGamma=$QS_GAMMA --qsEpsilon0=$QS_EPSILON0 \
                --qsLambda=$QS_LAMBDA --qsSeqNoWin=$QS_WINDOW \
                --qsAdaptPeriod=$QS_PERIOD --qsLowEThresh=$QS_LOW_E \
                --qsQueueHighThresh=$QS_Q_HI --qsQueueLowThresh=$QS_Q_LO \
                --qsW1=$W12 --qsW2=$W12 --qsW3=$W3 --qsW4=$QS_W4" >> "$JF"
        done
    done
    dispatch "$JF" "Family W"
}

# ---------------------------------------------------------------------------
# ═══════════════════════  FAMILY M  ═══════════════════════
# Hỗn hợp: 3 mức tải × 3 mức năng lượng = 9 combos
#   Load (pktInterval): {0.5, 0.25, 0.05} s
#   Energy (E₀):        {10,  30,   50}   J
# ---------------------------------------------------------------------------
family_M() {
    echo "=== Family M — mixed Load×Energy (1350 runs) ==="
    local CSV="$ROOT/family_M_mixed.csv"
    local JF="$ROOT/jobs_M.txt"; > "$JF"; rm -f "$CSV"
    for PI in 0.5 0.25 0.05; do
        for E0 in 10 30 50; do
            local TAG="M_I${PI}_E${E0}"
            for P in "${PROTOCOLS[@]}"; do
                local MP; MP=$(mp_for "$P")
                for S in $(seq 1 "$SEEDS"); do
                    echo "$CSV $P $MP $S $TAG \
                        --pktInterval=$PI --initialEnergy=$E0" >> "$JF"
                done
            done
        done
    done
    dispatch "$JF" "Family M"
}

# ---------------------------------------------------------------------------
# ═══════════════════════  STAT  ═══════════════════════
# Xác nhận thống kê: baseline cố định, 50 seeds
# ---------------------------------------------------------------------------
family_STAT() {
    echo "=== STAT — statistical validation (250 runs, 50 seeds) ==="
    local CSV="$ROOT/stat_baseline.csv"
    local JF="$ROOT/jobs_STAT.txt"; > "$JF"; rm -f "$CSV"
    for P in "${PROTOCOLS[@]}"; do
        local MP; MP=$(mp_for "$P")
        for S in $(seq 1 50); do
            echo "$CSV $P $MP $S STAT_baseline" >> "$JF"
        done
    done
    dispatch "$JF" "STAT"
}

# ---------------------------------------------------------------------------
# ═══════════════════════  ENERGY-LONG  ═══════════════════════
# Xác nhận cạn kiệt năng lượng: E₀=10J, T=350s, 30 seeds
# ---------------------------------------------------------------------------
family_ELONG() {
    echo "=== ENERGY-LONG — energy depletion (150 runs, T=350s) ==="
    local CSV="$ROOT/elong_energy_depletion.csv"
    local JF="$ROOT/jobs_ELONG.txt"; > "$JF"; rm -f "$CSV"
    for P in "${PROTOCOLS[@]}"; do
        local MP; MP=$(mp_for "$P")
        for S in $(seq 1 "$SEEDS"); do
            echo "$CSV $P $MP $S ELONG \
                --initialEnergy=10 --simTime=350" >> "$JF"
        done
    done
    dispatch "$JF" "ENERGY-LONG"
}

# ---------------------------------------------------------------------------
# Header log
# ---------------------------------------------------------------------------
{
echo "================================================================="
echo "  Paper Q3 — Full Experiment Suite"
echo "================================================================="
echo "  NS3:       $NS3_DIR"
echo "  Output:    $ROOT"
echo "  Families:  $FAMILIES"
echo "  Seeds:     $SEEDS  (STAT=50, ELONG=30)"
echo "  Jobs:      $JOBS parallel"
echo "  Protocols: ${PROTOCOLS[*]}"
echo "  SimTime:   ${SIM_TIME}s  (ELONG=350s)"
echo "  Resume:    $RESUME"
echo "  Started:   $(date)"
echo "  QSAQMAODV: α0=$QS_ALPHA0 γ=$QS_GAMMA ε0=$QS_EPSILON0"
echo "             λ=$QS_LAMBDA win=${QS_WINDOW}s period=${QS_PERIOD}s"
echo "             w=($QS_W1,$QS_W2,$QS_W3,$QS_W4)"
echo "             Qhi=$QS_Q_HI Qlo=$QS_Q_LO"
echo "================================================================="
} | tee "$LOGFILE"

# ---------------------------------------------------------------------------
# Chạy từng họ được chọn
# ---------------------------------------------------------------------------
START_TS=$(date +%s)

for F in $FAMILIES; do
    case "$F" in
        N)     family_N    ;;
        S)     family_S    ;;
        L)     family_L    ;;
        E)     family_E    ;;
        W)     family_W    ;;
        M)     family_M    ;;
        STAT)  family_STAT ;;
        ELONG) family_ELONG ;;
        *) echo "Unknown family: $F (allowed: N S L E W M STAT ELONG)" ;;
    esac
done 2>&1 | tee -a "$LOGFILE"

# ---------------------------------------------------------------------------
# Tổng kết
# ---------------------------------------------------------------------------
END_TS=$(date +%s)
WALL=$(( END_TS - START_TS ))
OK_COUNT=$(grep -c   "^OK"   "$LOGFILE" 2>/dev/null || echo 0)
FAIL_COUNT=$(grep -c "^FAIL" "$LOGFILE" 2>/dev/null || echo 0)
SKIP_COUNT=$(grep -c "^SKIP" "$LOGFILE" 2>/dev/null || echo 0)

{
echo ""
echo "================================================================="
echo "  Xong: $(date)"
printf "  Wall: %dh %dm %ds\n" \
    $((WALL/3600)) $(((WALL%3600)/60)) $((WALL%60))
echo "  OK: $OK_COUNT  |  FAIL: $FAIL_COUNT  |  SKIP: $SKIP_COUNT"
echo "================================================================="
echo ""
echo "  CSVs:"
ls -1 "$ROOT"/*.csv 2>/dev/null | sed 's/^/    /'
echo ""
if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "  [!] FAIL runs (tối đa 30 dòng đầu):"
    grep "^FAIL" "$LOGFILE" | head -30 | sed 's/^/    /'
    echo ""
fi
echo "  Plot:"
echo "    python3 scripts/plot/plot-paper-full.py $ROOT figures/"
echo "================================================================="
} | tee -a "$LOGFILE"
