#!/usr/bin/env bash
# =============================================================================
# fix-queue-and-rebuild.sh
# Run this on Linux after: git pull
#
# Fixes:
#   1. Revert QosSupported=true  →  wifiMac.SetType("ns3::AdhocWifiMac")
#      (QosSupported crashes 802.11b/AdhocWifiMac in NS-3.40)
#   2. Nuke the broken qsaqmaodv module dir and re-apply fresh from scratch
#   3. Rebuild NS-3
#   4. Smoke test: w4=0.0 vs w4=0.4 must give DIFFERENT PDR
# =============================================================================
set -euo pipefail

NS3_DIR="${NS3_DIR:-$HOME/ns-allinone-3.40-qsaqmaodv/ns-3.40}"
PROJ="${PROJECT_ROOT:-$HOME/saqmaodv-ns3/qsaqmaodv}"
SCRATCH="$NS3_DIR/scratch/fanet-sim.cc"
QSAQ_DIR="$NS3_DIR/src/qsaqmaodv"
CC_FILE="$QSAQ_DIR/model/qsaqmaodv-routing-protocol.cc"
H_FILE="$QSAQ_DIR/model/qsaqmaodv-routing-protocol.h"

echo "================================================================"
echo " fix-queue-and-rebuild.sh"
echo " NS3_DIR = $NS3_DIR"
echo " PROJ    = $PROJ"
echo "================================================================"
echo ""

# ── STEP 1: Revert QosSupported in scratch/fanet-sim.cc ─────────────────────
echo "=== STEP 1: Revert QosSupported in fanet-sim.cc ==="
if grep -q 'QosSupported' "$SCRATCH" 2>/dev/null; then
    python3 - "$SCRATCH" <<'PYEOF'
import sys, re
path = sys.argv[1]
with open(path) as f:
    txt = f.read()
# Remove QosSupported line(s) after AdhocWifiMac
txt = re.sub(
    r'(wifiMac\.SetType\("ns3::AdhocWifiMac"\s*),\s*\n\s*"QosSupported"[^\n]*\n',
    r'\1);\n',
    txt
)
# Also handle single-line form
txt = re.sub(
    r'wifiMac\.SetType\("ns3::AdhocWifiMac"\s*,\s*"QosSupported"[^\)]*\)\s*;',
    'wifiMac.SetType("ns3::AdhocWifiMac");',
    txt
)
# Fix trailing comma (SetType with comma but no second arg)
txt = re.sub(
    r'wifiMac\.SetType\("ns3::AdhocWifiMac",\s*\)\s*;',
    'wifiMac.SetType("ns3::AdhocWifiMac");',
    txt
)
with open(path, 'w') as f:
    f.write(txt)
print("  Done.")
PYEOF
else
    echo "  Already clean — no QosSupported found."
fi

# Verify
if grep -q 'QosSupported' "$SCRATCH" 2>/dev/null; then
    echo "  ERROR: QosSupported still present!"
    grep -n 'QosSupported' "$SCRATCH"
    exit 1
fi
echo "  Verified: QosSupported absent."

# ── STEP 2: Sync fanet-sim.cc from git repo (if available) ──────────────────
echo ""
echo "=== STEP 2: Copy fanet-sim.cc from git repo ==="
GIT_CC="$HOME/saqmaodv-ns3/src/fanet-sim.cc"
if [[ -f "$GIT_CC" ]]; then
    if ! grep -q 'QosSupported' "$GIT_CC" 2>/dev/null; then
        cp "$GIT_CC" "$SCRATCH"
        echo "  Copied from $GIT_CC"
    else
        echo "  WARNING: git repo fanet-sim.cc still has QosSupported — skipping copy."
        echo "  Run: git pull  then rerun this script."
    fi
else
    echo "  Git repo fanet-sim.cc not found at $GIT_CC — using scratch version."
fi

# ── STEP 3: Nuke broken qsaqmaodv module and re-apply from scratch ───────────
echo ""
echo "=== STEP 3: Nuke and re-clone qsaqmaodv module ==="
if [[ -d "$QSAQ_DIR" ]]; then
    echo "  Removing $QSAQ_DIR ..."
    rm -rf "$QSAQ_DIR"
    echo "  Removed."
fi

echo "  Re-applying module patcher..."
cd "$PROJ"
NS3_DIR="$NS3_DIR" PROJECT_ROOT="$PROJ" python3 patches/apply-qsaqmaodv-module.py

# ── STEP 4: Verify GetQueueOccupancy in .cc and .h ─────────────────────────
echo ""
echo "=== STEP 4: Verify GetQueueOccupancy ==="

# Check NOT const, uses m_queue
if grep -q "RoutingProtocol::GetQueueOccupancy()" "$CC_FILE" 2>/dev/null; then
    echo "  OK  .cc has GetQueueOccupancy()"
    grep -A8 "RoutingProtocol::GetQueueOccupancy" "$CC_FILE" | head -10
else
    echo "  MISSING in .cc — check apply-qsaqmaodv-module.py"
    exit 1
fi

# Must use m_queue, not m_rqueue
if grep -q "m_rqueue" "$CC_FILE" 2>/dev/null; then
    echo "  ERROR: m_rqueue still present — fixing..."
    sed -i 's/m_rqueue\.GetSize()/m_queue.GetSize()/g' "$CC_FILE"
    sed -i 's/m_rqueue\.GetMaxQueueLen()/m_queue.GetMaxQueueLen()/g' "$CC_FILE"
    echo "  Fixed: m_rqueue -> m_queue"
fi

# Must NOT be const
if grep -q "GetQueueOccupancy() const" "$CC_FILE" 2>/dev/null; then
    echo "  ERROR: 'const' on GetQueueOccupancy in .cc — fixing..."
    sed -i 's/RoutingProtocol::GetQueueOccupancy() const/RoutingProtocol::GetQueueOccupancy()/g' "$CC_FILE"
fi
if grep -q "GetQueueOccupancy() const" "$H_FILE" 2>/dev/null; then
    echo "  ERROR: 'const' on GetQueueOccupancy in .h — fixing..."
    sed -i 's/GetQueueOccupancy() const/GetQueueOccupancy()/g' "$H_FILE"
fi

# Check .h declaration
if grep -q "GetQueueOccupancy" "$H_FILE" 2>/dev/null; then
    echo "  OK  .h has GetQueueOccupancy() declaration"
else
    echo "  MISSING in .h — check apply-qsaqmaodv-module.py"
    exit 1
fi

# ── STEP 5: Verify RewardW4 attribute ───────────────────────────────────────
echo ""
echo "=== STEP 5: Verify RewardW4 attribute ==="
if grep -q '"RewardW4"' "$CC_FILE" 2>/dev/null; then
    echo "  OK  RewardW4 attribute present"
else
    echo "  MISSING — check apply-qsaqmaodv-module.py RewardW3 anchor"
    exit 1
fi

# ── STEP 6: Verify PeriodicAdaptiveTick passes queueOcc ─────────────────────
echo ""
echo "=== STEP 6: Verify PeriodicAdaptiveTick ==="
if grep -q "queueOcc\|GetQueueOccupancy" "$CC_FILE" 2>/dev/null; then
    echo "  OK  queueOcc present in routing-protocol.cc"
    grep -n "queueOcc\|RecomputeAdaptive" "$CC_FILE" | head -8
else
    echo "  MISSING — check PeriodicAdaptiveTick in apply-qsaqmaodv-module.py"
    exit 1
fi

# ── STEP 6b: Verify per-neighbor RERR congestion hooks ──────────────────────
echo ""
echo "=== STEP 6b: Verify RERR congestion hooks ==="
if grep -q "RecordNeighborRerr" "$CC_FILE" 2>/dev/null; then
    echo "  OK  RecordNeighborRerr present (RecvError hook)"
    grep -n "RecordNeighborRerr\|DecayNeighborCongestion" "$CC_FILE"
else
    echo "  WARNING: RecordNeighborRerr not found in .cc"
    echo "  Check patch_rerr_congestion() in apply-qsaqmaodv-module.py"
    echo "  You may need to add manually:"
    echo "    m_qtable.RecordNeighborRerr(src); // after m_qtable.OnRouteError();"
    echo "    m_qtable.DecayNeighborCongestion(); // after m_qtable.PeriodicEpsilonDecay();"
fi

# ── STEP 7: Build ────────────────────────────────────────────────────────────
echo ""
echo "=== STEP 7: Build NS-3 ==="
cd "$NS3_DIR"
./ns3 build 2>&1 | tee /tmp/qsaq-rebuild.log | grep -E "error:|Finished|Build" | head -30
echo ""
ERR=$(grep -c " error:" /tmp/qsaq-rebuild.log 2>/dev/null || echo 0)
if [[ "$ERR" -eq 0 ]]; then
    echo "  BUILD OK (0 errors)"
else
    echo "  BUILD FAILED ($ERR errors):"
    grep " error:" /tmp/qsaq-rebuild.log | head -15
    exit 1
fi

# ── STEP 8: Smoke test — w4=0.0 vs w4=0.4 must differ ──────────────────────
echo ""
echo "=== STEP 8: Smoke test — w4 sweep check ==="
BIN="./build/scratch/ns3.40-fanet-sim-optimized"
COMMON="--protocol=QSAQMAODV --numNodes=15 --pktInterval=0.05 --simTime=30 --seed=1"

echo -n "  w4=0.0 ... "
$BIN $COMMON --qsW4=0.0 --csvFile=/tmp/smoke_w4_00.csv 2>/dev/null \
  && PDR0=$(awk -F, 'NR>1{pdr=$5} END{print pdr}' /tmp/smoke_w4_00.csv) \
  && echo "PDR=$PDR0" || { echo "CRASHED"; exit 1; }

echo -n "  w4=0.4 ... "
$BIN $COMMON --qsW4=0.4 --csvFile=/tmp/smoke_w4_04.csv 2>/dev/null \
  && PDR4=$(awk -F, 'NR>1{pdr=$5} END{print pdr}' /tmp/smoke_w4_04.csv) \
  && echo "PDR=$PDR4" || { echo "CRASHED"; exit 1; }

echo ""
if [[ "$PDR0" == "$PDR4" ]]; then
    echo "  FAIL: w4=0.0 and w4=0.4 give identical PDR=$PDR0"
    echo "        Queue-awareness is still broken — check GetQueueOccupancy()"
    exit 1
else
    echo "  PASS: w4=0.0 → PDR=$PDR0  vs  w4=0.4 → PDR=$PDR4  (different ✓)"
fi

# ── STEP 9: Quick protocol sanity (15 nodes, 30s) ───────────────────────────
echo ""
echo "=== STEP 9: Protocol sanity (15 nodes, pktInterval=0.5, 30s) ==="
for proto in AODV PMAODV QMAODV QSAQMAODV; do
    OUT="/tmp/smoke_${proto}.csv"
    echo -n "  $proto ... "
    if ./ns3 run "fanet-sim --protocol=$proto --numNodes=15 --simTime=30 \
            --pktInterval=0.5 --csvFile=$OUT" > /tmp/smoke_${proto}.log 2>&1; then
        PDR=$(awk -F, 'NR>1{pdr=$5} END{print pdr}' "$OUT" 2>/dev/null || echo "?")
        echo "PASS (PDR=$PDR)"
    else
        echo "FAIL"
        grep -i "error\|abort\|assert" /tmp/smoke_${proto}.log | head -5
    fi
done

echo ""
echo "================================================================"
echo " ALL DONE — if all PASS, run the full experiments:"
echo "   cd $PROJ"
echo "   bash run/run-qsaqmaodv-experiments.sh"
echo "================================================================"
