#!/bin/bash
# =============================================================================
# run-family-N.sh  —  Family N: Sweep số nodes (chính)
# =============================================================================
#
# Mô tả:
#   Sweep N ∈ {5, 10, 15, 20, 25, 30}  ×  5 protocols  ×  20 seeds = 600 runs
#   Baseline: GAUSS mobility, 512B/0.25s, N cố định (vary), simTime=200s
#
# Sử dụng:
#   # Chạy toàn bộ (600 runs, ~1-2 giờ với JOBS=6)
#   bash run-family-N.sh
#
#   # Chỉ một số protocols
#   PROTOCOLS="AODV QMAODV" bash run-family-N.sh
#
#   # Điều chỉnh song song / seeds
#   JOBS=12 SEEDS=20 bash run-family-N.sh
#
#   # Resume sau khi bị ngắt (bỏ qua run đã có trong CSV)
#   RESUME=1 bash run-family-N.sh
#
# Kết quả:
#   $HOME/results-family-N-<timestamp>/
#     family_N_nodes.csv   ← file chính để plot
#     jobs_N.txt           ← danh sách job (để debug)
#     run_N.log            ← log đầy đủ
#     done_N.txt           ← checkpoint (seed/proto/N đã chạy xong)
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Cấu hình — override bằng env var
# ---------------------------------------------------------------------------
NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40/ns-3.40}"
EXEC="$NS3_DIR/build/scratch/ns3.40-fanet-sim-optimized"

JOBS="${JOBS:-6}"            # Số luồng song song
SEEDS="${SEEDS:-20}"         # Seeds per config  (default 20 = paper quality)
SIM_TIME="${SIM_TIME:-200}"  # Simulation time (s)
RESUME="${RESUME:-0}"        # 1 = bỏ qua run đã có trong done_N.txt

# 5 protocols — đúng theo paper
PROTOCOLS=(${PROTOCOLS:-AODV AOMDV PMAODV QMAODV QSAQMAODV})

# Node counts để sweep
NODE_VALS=(5 10 15 20 25 30)

# ---------------------------------------------------------------------------
# QMAODV hyperparams (Strategy-B, validated)
# ---------------------------------------------------------------------------
QM_ALPHA="${QM_ALPHA:-0.5}"
QM_GAMMA="${QM_GAMMA:-0.7}"
QM_EPSILON="${QM_EPSILON:-0.1}"
QM_DECAY="${QM_DECAY:-0.05}"

# ---------------------------------------------------------------------------
# QS-QMAODV hyperparams (Queue-State Self-Adaptive — protocol mới)
#   Dùng default từ fanet-sim.cc; override bằng env var nếu cần
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
# Baseline (fixed cho tất cả run trong Family N)
# ---------------------------------------------------------------------------
BASE="--mobility=GAUSS --enableEnergy=1 --alpha=0.85 \
      --meanVelMin=15 --meanVelMax=25 \
      --pktInterval=0.25 --pktSize=512 --numFlows=0 \
      --simTime=$SIM_TIME"

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------
TS=$(date +%Y%m%d-%H%M%S)
ROOT="$HOME/results-family-N-${TS}"
mkdir -p "$ROOT"

CSV="$ROOT/family_N_nodes.csv"
JOBFILE="$ROOT/jobs_N.txt"
LOGFILE="$ROOT/run_N.log"
DONEFILE="$ROOT/done_N.txt"

# ---------------------------------------------------------------------------
# Kiểm tra binary tồn tại
# ---------------------------------------------------------------------------
if [ ! -x "$EXEC" ]; then
    echo "[ERROR] Không tìm thấy binary: $EXEC"
    echo "        Chạy: bash scripts/setup/setup-from-scratch.sh trước"
    exit 1
fi

# ---------------------------------------------------------------------------
# Helper: chạy 1 run
# ---------------------------------------------------------------------------
run_one() {
    local CSV=$1 PROTO=$2 MP=$3 SEED=$4 SCEN_TAG=$5
    shift 5
    local EXTRA_ARGS="$*"

    # Resume: kiểm tra xem run này đã xong chưa
    local KEY="${SCEN_TAG}_${PROTO}_s${SEED}"
    if [ "${RESUME:-0}" = "1" ] && grep -qF "$KEY" "${DONEFILE:-/dev/null}" 2>/dev/null; then
        echo "SKIP $KEY"
        return 0
    fi

    # QS-QMAODV flags (no-op cho protocol khác)
    local QS_FLAGS=""
    if [ "$PROTO" = "QSAQMAODV" ]; then
        QS_FLAGS="--qsAlpha0=$QS_ALPHA0 --qsGamma=$QS_GAMMA --qsEpsilon0=$QS_EPSILON0 \
                  --qsLambda=$QS_LAMBDA --qsSeqNoWin=$QS_WINDOW \
                  --qsAdaptPeriod=$QS_PERIOD --qsLowEThresh=$QS_LOW_E \
                  --qsQueueHighThresh=$QS_Q_HI --qsQueueLowThresh=$QS_Q_LO \
                  --qsW1=$QS_W1 --qsW2=$QS_W2 --qsW3=$QS_W3 --qsW4=$QS_W4"
    fi

    local START_T
    START_T=$(date +%s)

    "$EXEC" \
        --protocol="$PROTO" --maxPaths="$MP" --seed="$SEED" \
        --scenario="$SCEN_TAG" --csvFile="$CSV" \
        --qmAlpha="$QM_ALPHA" --qmGamma="$QM_GAMMA" \
        --qmEpsilon="$QM_EPSILON" --qmEpsilonDecay="$QM_DECAY" \
        $QS_FLAGS \
        $BASE $EXTRA_ARGS > /dev/null 2>&1
    local RC=$?
    local DUR=$(( $(date +%s) - START_T ))

    if [ "$RC" -eq 0 ] || [ "$RC" -eq 139 ]; then
        # Ghi checkpoint
        echo "$KEY" >> "${DONEFILE}"
        echo "OK   $KEY  (${DUR}s)"
    else
        echo "FAIL $KEY  rc=$RC"
    fi
}
export -f run_one
export EXEC BASE QM_ALPHA QM_GAMMA QM_EPSILON QM_DECAY
export QS_ALPHA0 QS_GAMMA QS_EPSILON0 QS_LAMBDA QS_WINDOW QS_PERIOD
export QS_LOW_E QS_Q_HI QS_Q_LO QS_W1 QS_W2 QS_W3 QS_W4
export DONEFILE RESUME

# ---------------------------------------------------------------------------
# Xây dựng job list
# ---------------------------------------------------------------------------
> "$JOBFILE"
> "$CSV"    # tạo file CSV rỗng (header sẽ được ghi bởi run đầu tiên)

TOTAL_RUNS=0
for N in "${NODE_VALS[@]}"; do
    for PROTO in "${PROTOCOLS[@]}"; do
        # maxPaths: AODV dùng 1 path (single-path), còn lại dùng 3
        MP=3
        if [ "$PROTO" = "AODV" ] || [ "$PROTO" = "DSDV" ]; then
            MP=1
        fi
        for S in $(seq 1 "$SEEDS"); do
            echo "$CSV $PROTO $MP $S N${N} --numNodes=$N" >> "$JOBFILE"
            TOTAL_RUNS=$(( TOTAL_RUNS + 1 ))
        done
    done
done

# ---------------------------------------------------------------------------
# Ước tính thời gian
# ---------------------------------------------------------------------------
# ~2s/run với simTime=200 trên máy thường; 600 runs / JOBS=6 = ~200s ≈ 3.3 phút
# Thực tế ns-3 có overhead: ~5-10s/run → 600 runs / 6 jobs = ~8-17 phút
EST_PER_RUN=8  # giây / run (ước tính thận trọng)
EST_TOTAL=$(( TOTAL_RUNS * EST_PER_RUN / JOBS ))
EST_MIN=$(( EST_TOTAL / 60 ))
EST_SEC=$(( EST_TOTAL % 60 ))

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
{
echo "================================================================="
echo "  Family N — Sweep số nodes (chính)"
echo "================================================================="
echo "  NS3:      $NS3_DIR"
echo "  Output:   $ROOT"
echo "  Node vals: ${NODE_VALS[*]}"
echo "  Protocols: ${PROTOCOLS[*]}"
echo "  Seeds:    $SEEDS"
echo "  SimTime:  ${SIM_TIME}s"
echo "  Jobs:     $JOBS (parallel)"
echo "  Total:    $TOTAL_RUNS runs"
echo "  Ước tính: ~${EST_MIN}m ${EST_SEC}s (${EST_PER_RUN}s/run est.)"
echo "  QMAODV:   α=$QM_ALPHA γ=$QM_GAMMA ε=$QM_EPSILON decay=$QM_DECAY"
echo "  QSAQMAODV: λ=$QS_LAMBDA win=${QS_WINDOW}s period=${QS_PERIOD}s Qhi=$QS_Q_HI Qlo=$QS_Q_LO"
echo "  Resume:   $RESUME"
echo "  Started:  $(date)"
echo "================================================================="
} | tee "$LOGFILE"

# ---------------------------------------------------------------------------
# Chạy với progress counter (dùng FIFO pipe để đếm)
# ---------------------------------------------------------------------------
PIPE="$ROOT/.progress_pipe"
mkfifo "$PIPE" 2>/dev/null || true

# Background counter process
(
    DONE=0
    while IFS= read -r LINE; do
        DONE=$(( DONE + 1 ))
        PCT=$(( DONE * 100 / TOTAL_RUNS ))
        ELAPSED=$(( $(date +%s) - START_TS ))
        if [ "$DONE" -gt 0 ] && [ "$ELAPSED" -gt 0 ]; then
            RATE=$(awk -v d=$DONE -v e=$ELAPSED 'BEGIN{printf "%.1f", d/e}')
            ETA=$(awk -v rem=$((TOTAL_RUNS - DONE)) -v r=$DONE -v e=$ELAPSED \
                      'BEGIN{ if(r>0){printf "%dm%ds", int(rem*e/r/60), int(rem*e/r)%60} else print "?"}')
        else
            RATE="?"
            ETA="?"
        fi
        printf "\r  [%3d%%] %d/%d done  |  %.1f runs/s  |  ETA %s   " \
               "$PCT" "$DONE" "$TOTAL_RUNS" "${RATE:-0}" "${ETA:-?}"
    done
    echo ""
) < "$PIPE" &
COUNTER_PID=$!

START_TS=$(date +%s)

# Chạy jobs song song, mỗi OK/FAIL/SKIP được tee vào pipe để đếm
cat "$JOBFILE" \
    | xargs -P "$JOBS" -L 1 bash -c 'run_one "$@"' _ \
    | tee -a "$LOGFILE" \
    | grep -E "^(OK|FAIL|SKIP)" > "$PIPE" &
XARGS_PID=$!

wait $XARGS_PID
wait $COUNTER_PID 2>/dev/null || true
rm -f "$PIPE"

# ---------------------------------------------------------------------------
# Tổng kết
# ---------------------------------------------------------------------------
END_TS=$(date +%s)
WALL=$(( END_TS - START_TS ))
WALL_MIN=$(( WALL / 60 ))
WALL_SEC=$(( WALL % 60 ))

OK_COUNT=$(grep -c "^OK"   "$LOGFILE" 2>/dev/null || echo 0)
FAIL_COUNT=$(grep -c "^FAIL" "$LOGFILE" 2>/dev/null || echo 0)
SKIP_COUNT=$(grep -c "^SKIP" "$LOGFILE" 2>/dev/null || echo 0)

{
echo ""
echo "================================================================="
echo "  Xong: $(date)"
echo "  Wall time: ${WALL_MIN}m ${WALL_SEC}s"
echo "  OK:   $OK_COUNT  |  FAIL: $FAIL_COUNT  |  SKIP: $SKIP_COUNT"
echo "================================================================="
echo ""
echo "  CSV:  $CSV"
echo "  Log:  $LOGFILE"
if [ "$FAIL_COUNT" -gt 0 ]; then
    echo ""
    echo "  [!] Các run FAIL:"
    grep "^FAIL" "$LOGFILE" | head -20
fi
echo ""
echo "  Bước tiếp theo — plot:"
echo "    python3 scripts/plot/plot-experiments-5proto.py \\"
echo "        $CSV figures/N/"
echo "================================================================="
} | tee -a "$LOGFILE"
