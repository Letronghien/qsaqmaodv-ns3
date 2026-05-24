#!/bin/bash
# =============================================================================
# run-full-eval.sh — Đánh giá toàn diện SA-QMAODV
# =============================================================================
# So sánh 5 giao thức: AODV, AOMDV-3, PMAODV-3, QMAODV-3, SAQMAODV-3
#
# Các kịch bản (families):
#   N  — Node density:   N ∈ {5,8,10,15,20,25,30}       (SA thắng ở N nào?)
#   S  — Speed:          V ∈ {5,10,15,20,25,30,50} m/s   (SA thắng ở speed nào?)
#   E  — Energy (proper):E₀∈ {2,5,10,20,50} J, T=600s   (kích hoạt Low-Energy mode)
#   T  — SimTime:        T ∈ {200,600,900,1200} s        (Q hội tụ theo thời gian)
#   L  — Traffic load:   pkt∈{1.0,0.5,0.25,0.1,0.05} s  (tải cao → explore overhead)
#
# Tổng: ~1300 runs | song song JOBS=8 ≈ 30-50 phút
#
# Chạy trong tmux:
#   tmux new -s eval
#   bash scripts/run/run-full-eval.sh 2>&1 | tee ~/eval.log
#
# Tuỳ chỉnh:
#   FAMILIES="N S" SEEDS=5 JOBS=4 bash run-full-eval.sh   (chạy nhanh thử)
# =============================================================================
set -u

# ──── Cấu hình ───────────────────────────────────────────────────────────────
NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40/ns-3.40}"
EXEC=$(find "$NS3_DIR/build" -maxdepth 2 -name "*fanet-sim*" -executable -type f 2>/dev/null | head -1)
[ -z "$EXEC" ] && { echo "ERROR: fanet-sim not found"; exit 1; }

JOBS="${JOBS:-8}"
SEEDS="${SEEDS:-10}"
FAMILIES="${FAMILIES:-N S E T L}"   # chạy tất cả nếu không override

# ──── Hyper-parameters cố định ───────────────────────────────────────────────
QM_ALPHA=0.7; QM_GAMMA=0.6; QM_EPSILON=0.3; QM_DECAY=0.1

SA_ALPHA0=0.5; SA_GAMMA=0.9; SA_EPSILON0=0.3
SA_LAMBDA=0.01; SA_WINDOW=10; SA_PERIOD=1.0; SA_LOWE=0.20
SA_W1=0.5; SA_W2=0.4; SA_W3=0.1

# ──── Output ─────────────────────────────────────────────────────────────────
TS=$(date +%Y%m%d-%H%M%S)
RESULTS_DIR="$HOME/results-full-eval-${TS}"
JOB_DIR="$RESULTS_DIR/jobs"
mkdir -p "$JOB_DIR"
LOG="$RESULTS_DIR/run.log"
MERGED="$RESULTS_DIR/merged.csv"

echo "============================================================" | tee "$LOG"
echo " SA-QMAODV Full Evaluation"                                  | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"
echo " Protocols: AODV, AOMDV-3, PMAODV-3, QMAODV-3, SAQMAODV-3" | tee -a "$LOG"
echo " Families:  $FAMILIES"                                        | tee -a "$LOG"
echo " Seeds:     $SEEDS  |  Jobs: $JOBS"                          | tee -a "$LOG"
echo " Output:    $RESULTS_DIR"                                     | tee -a "$LOG"
echo " Started:   $(date)"                                          | tee -a "$LOG"
echo "============================================================" | tee -a "$LOG"

# ──── Sinh job list ───────────────────────────────────────────────────────────
JOB_FILE="$JOB_DIR/jobs.txt"
> "$JOB_FILE"

PROTOCOLS=("AODV:1" "AOMDV:3" "PMAODV:3" "QMAODV:3" "SAQMAODV:3")

add_jobs() {
    local FAM=$1 N=$2 V=$3 T=$4 E0=$5 PKT=$6
    for SEED in $(seq 1 "$SEEDS"); do
        for PE in "${PROTOCOLS[@]}"; do
            local PROTO="${PE%%:*}" MP="${PE##*:}"
            echo "$FAM $PROTO $MP $SEED $N $V $T $E0 $PKT" >> "$JOB_FILE"
        done
    done
}

# Family N — node density  (V=20 m/s, T=200s, E=50J, pkt=0.25)
if echo "$FAMILIES" | grep -qw N; then
    echo "  [jobs] Family N: node density" | tee -a "$LOG"
    for N in 5 8 10 15 20 25 30; do
        add_jobs N $N 20 200 50 0.25
    done
fi

# Family S — speed  (N=15, T=200s, E=50J, pkt=0.25)
if echo "$FAMILIES" | grep -qw S; then
    echo "  [jobs] Family S: speed"        | tee -a "$LOG"
    for V in 5 10 15 20 25 30 50; do
        add_jobs S 15 $V 200 50 0.25
    done
fi

# Family E — energy (proper)  (N=15, V=20 m/s, T=600s — cần T dài để node chết)
if echo "$FAMILIES" | grep -qw E; then
    echo "  [jobs] Family E: energy"       | tee -a "$LOG"
    for E0 in 2 5 10 20 50; do
        add_jobs E 15 20 600 $E0 0.25
    done
fi

# Family T — simtime  (N=15, V=20 m/s, E=50J, pkt=0.25)
if echo "$FAMILIES" | grep -qw T; then
    echo "  [jobs] Family T: sim time"     | tee -a "$LOG"
    for T in 200 600 900 1200; do
        add_jobs T 15 20 $T 50 0.25
    done
fi

# Family L — traffic load  (N=15, V=20 m/s, T=200s, E=50J)
if echo "$FAMILIES" | grep -qw L; then
    echo "  [jobs] Family L: traffic load" | tee -a "$LOG"
    for PKT in 1.0 0.5 0.25 0.1 0.05; do
        add_jobs L 15 20 200 50 $PKT
    done
fi

TOTAL=$(wc -l < "$JOB_FILE")
echo "  Total runs: $TOTAL" | tee -a "$LOG"
echo "" | tee -a "$LOG"

# ──── Hàm chạy 1 job ─────────────────────────────────────────────────────────
run_job() {
    local FAM=$1 PROTO=$2 MP=$3 SEED=$4 N=$5 V=$6 T=$7 E0=$8 PKT=$9

    local LABEL="$PROTO"
    [ "$PROTO" != "AODV" ] && LABEL="${PROTO}-${MP}"

    local SCENARIO="${FAM}-N${N}-V${V}-T${T}-E${E0}-pkt${PKT}"
    local CSV="$JOB_DIR/${FAM}-${LABEL}-N${N}-V${V}-T${T}-E${E0}-p${PKT}-s${SEED}.csv"
    local START_T=$(date +%s)

    local SA_FLAGS=""
    if [ "$PROTO" = "SAQMAODV" ]; then
        SA_FLAGS="--saAlpha0=$SA_ALPHA0 --saGamma=$SA_GAMMA \
                  --saEpsilon0=$SA_EPSILON0 --saLambda=$SA_LAMBDA \
                  --saSeqNoWin=$SA_WINDOW --saAdaptPeriod=$SA_PERIOD \
                  --saLowEThresh=$SA_LOWE \
                  --saW1=$SA_W1 --saW2=$SA_W2 --saW3=$SA_W3"
    fi

    "$EXEC" \
        --scenario="$SCENARIO" \
        --protocol="$PROTO" --maxPaths="$MP" \
        --mobility=GAUSS --enableEnergy=1 --initialEnergy="$E0" \
        --numNodes="$N" --simTime="$T" --seed="$SEED" \
        --meanVelMin="$V" --meanVelMax="$V" --alpha=0.85 \
        --pktInterval="$PKT" --pktSize=512 --numFlows=0 \
        --qmAlpha="$QM_ALPHA" --qmGamma="$QM_GAMMA" \
        --qmEpsilon="$QM_EPSILON" --qmEpsilonDecay="$QM_DECAY" \
        $SA_FLAGS \
        --csvFile="$CSV" >/dev/null 2>&1

    local RC=$? DUR=$(( $(date +%s) - START_T ))
    if [ "$RC" -eq 0 ] || [ "$RC" -eq 139 ]; then
        echo "OK   [$FAM] $LABEL  N=$N V=$V T=$T E=$E0 pkt=$PKT seed=$SEED  (${DUR}s)"
    else
        echo "FAIL [$FAM] $LABEL  rc=$RC"
    fi
}

export -f run_job
export EXEC JOB_DIR
export QM_ALPHA QM_GAMMA QM_EPSILON QM_DECAY
export SA_ALPHA0 SA_GAMMA SA_EPSILON0 SA_LAMBDA SA_WINDOW SA_PERIOD SA_LOWE SA_W1 SA_W2 SA_W3

# ──── Chạy song song ──────────────────────────────────────────────────────────
START_TS=$(date +%s)
cat "$JOB_FILE" | xargs -P "$JOBS" -L 1 bash -c 'run_job "$@"' _ 2>&1 | tee -a "$LOG"
END_TS=$(date +%s)
WALL=$(( END_TS - START_TS ))

# ──── Merge tất cả CSV ────────────────────────────────────────────────────────
FIRST=$(ls "$JOB_DIR"/*.csv 2>/dev/null | head -1)
if [ -n "$FIRST" ]; then
    head -1 "$FIRST" > "$MERGED"
    for f in "$JOB_DIR"/*.csv; do
        tail -n +2 "$f" >> "$MERGED"
    done
    NROWS=$(wc -l < "$MERGED")
    echo "" | tee -a "$LOG"
    echo "Merged: $MERGED  ($((NROWS-1)) rows)" | tee -a "$LOG"
fi

echo "Finished: $(date)  wall=$((WALL/3600))h $(((WALL%3600)/60))m $((WALL%60))s" | tee -a "$LOG"

# ──── Quick summary table ─────────────────────────────────────────────────────
[ -s "$MERGED" ] && python3 - "$MERGED" "$FAMILIES" << 'PYEOF' | tee -a "$LOG"
import csv, sys, numpy as np
from collections import defaultdict

rows = list(csv.DictReader(open(sys.argv[1])))
fams = sys.argv[2].split() if len(sys.argv) > 2 else []

def lb(r): return r['protocol'] if r['protocol']=='AODV' else f"{r['protocol']}-{r['maxPaths']}"
def sc_key(r):
    sc = r['scenario']  # e.g. N-N15-V20-T200-E50-pkt0.25
    parts = sc.split('-')
    return parts[0], sc

PROTOS = ['AODV','AOMDV-3','PMAODV-3','QMAODV-3','SAQMAODV-3']

agg = defaultdict(list)
for r in rows:
    fam = r['scenario'].split('-')[0]
    try: agg[(fam, lb(r))].append(float(r['deliveryRatio']))
    except: pass

FAM_NAMES = {'N':'Node density','S':'Speed','E':'Energy','T':'SimTime','L':'Load'}
FAM_XKEY  = {'N':'numNodes','S':'meanVelMin','E':'initialEnergy','T':'simTime','L':'pktInterval'}

print()
for fam in ['N','S','E','T','L']:
    if fam not in sys.argv[2]: continue
    print(f"{'='*62}")
    print(f" [{fam}] {FAM_NAMES.get(fam,fam)} — PDR mean (%)")
    print(f"{'='*62}")

    # group by x-value
    xagg = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if not r['scenario'].startswith(fam+'-'): continue
        try:
            xk = FAM_XKEY.get(fam)
            xv = r.get(xk, '?')
            xagg[xv][lb(r)].append(float(r['deliveryRatio']))
        except: pass

    xs = sorted(xagg.keys(), key=lambda v: float(v) if v.replace('.','').isdigit() else 0)
    print(f"{'Protocol':<14} " + " ".join(f"{x:>8}" for x in xs) + "  | Best x")
    print('-'*62)
    for p in PROTOS:
        vals = [np.mean(xagg[x][p]) if xagg[x].get(p) else None for x in xs]
        row_str = " ".join(f"{v:>7.1f}%" if v else f"{'—':>8}" for v in vals)
        best = xs[np.nanargmax([v if v else -1 for v in vals])] if any(vals) else '?'
        print(f"{p:<14} {row_str}  | {best}")
    print()

    # SA vs AODV
    print(f"  SA-QMAODV vs AODV Δ:")
    for x in xs:
        sa = np.mean(xagg[x].get('SAQMAODV-3',[])) if xagg[x].get('SAQMAODV-3') else None
        ao = np.mean(xagg[x].get('AODV',[])) if xagg[x].get('AODV') else None
        qm = np.mean(xagg[x].get('QMAODV-3',[])) if xagg[x].get('QMAODV-3') else None
        if sa and ao and qm:
            winner = "SA>ALL ✓" if sa>qm else ("SA>AODV" if sa>ao else "SA loses")
            print(f"    x={x:>6}: SA={sa:.1f}% QMAODV={qm:.1f}% AODV={ao:.1f}% Δ_AODV={sa-ao:+.1f}% Δ_QMAODV={sa-qm:+.1f}%  [{winner}]")
    print()
PYEOF

echo ""
echo "═══════════════════════════════════════════════════════"
echo " Để copy kết quả về Windows:"
echo "   mkdir -p ~/saqmaodv-ns3/results"
echo "   cp $MERGED ~/saqmaodv-ns3/results/full-eval.csv"
echo "   cd ~/saqmaodv-ns3&& git add results/full-eval.csv"
echo "   git commit -m 'results: full evaluation' && git push"
echo "═══════════════════════════════════════════════════════"
