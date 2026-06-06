#!/bin/bash
# Build PMAODV + AOMDV modules from scratch trên Cloud VM với fresh ns-3.40.
# Sử dụng AODV stock của ns-3.40 + tất cả patches của project.
#
# Usage trên Cloud VM:
#   tar xzf pmaodv-fanet-cloud.tar.gz
#   cd pmaodv-fanet-cloud-*/
#   bash setup-from-scratch.sh
#
# Yêu cầu:
#   - ns-3.40 đã cài đặt
#   - python3, gcc, ninja-build, cmake
#   - matplotlib (cho plot, optional)

set -e

# Auto-detect ns-3.40 (check cả directory tồn tại VÀ file ns3 + thư mục src)
if [ -z "${NS3_DIR:-}" ]; then
    for cand in \
        "$HOME/ns-allinone-3.40/ns-3.40" \
        "$HOME/ns-3-allinone/ns-3.40" \
        "$HOME/workspace/ns-allinone-3.40/ns-3.40" \
        "$HOME/ns-3.40"; do
        if [ -d "$cand" ] && [ -f "$cand/ns3" ] && [ -d "$cand/src" ] && [ -d "$cand/src/aodv" ]; then
            NS3_DIR="$cand"
            break
        fi
    done
fi
if [ -z "${NS3_DIR:-}" ]; then
    echo "ERROR: ns-3.40 không tìm thấy. Set thủ công:"
    echo "  NS3_DIR=/path/to/ns-3.40 bash $0"
    echo ""
    echo "Tìm path ns-3.40 trên máy:"
    echo "  find \$HOME -maxdepth 5 -type d -name 'ns-3.40' 2>/dev/null"
    exit 1
fi
# Validate explicit NS3_DIR (nếu user pass qua env var)
if [ ! -d "$NS3_DIR" ] || [ ! -f "$NS3_DIR/ns3" ] || [ ! -d "$NS3_DIR/src/aodv" ]; then
    echo "ERROR: NS3_DIR=$NS3_DIR không hợp lệ."
    echo "  Cần: directory chứa file 'ns3' và folder 'src/aodv/'"
    [ -d "$NS3_DIR" ] || echo "  - $NS3_DIR không tồn tại"
    [ -f "$NS3_DIR/ns3" ] || echo "  - $NS3_DIR/ns3 không tồn tại"
    [ -d "$NS3_DIR/src/aodv" ] || echo "  - $NS3_DIR/src/aodv không tồn tại"
    exit 1
fi

PKG_DIR=$(cd "$(dirname "$0")" && pwd)
# PROJECT_ROOT is two levels up from scripts/setup/ (i.e. the repo root)
PROJECT_ROOT=$(cd "$PKG_DIR/../.." && pwd)

# Export so all child Python patch scripts can read NS3_DIR
export NS3_DIR
export PROJECT_ROOT

echo "========================================"
echo "  Setup PMAODV + AOMDV trên ns-3.40"
echo "========================================"
echo "NS3_DIR:      $NS3_DIR"
echo "PKG_DIR:      $PKG_DIR"
echo "PROJECT_ROOT: $PROJECT_ROOT"
echo ""

# ===== Step 1: Backup any existing custom modules =====
echo "[1/10] Backup existing custom modules (if any)..."
TS=$(date +%Y%m%d-%H%M%S)
BAK="$HOME/ns3-backup-${TS}"
mkdir -p "$BAK"
for m in pmaodv aomdv qmaodv saqmaodv; do
    if [ -d "$NS3_DIR/src/$m" ]; then
        mv "$NS3_DIR/src/$m" "$BAK/"
        echo "  Backed up src/$m"
    fi
done

# ===== Step 2: Create PMAODV skeleton (clone from AODV) =====
echo ""
echo "[2/9] Create PMAODV skeleton (clone src/aodv -> src/pmaodv)..."
cd "$NS3_DIR"
SRC=src/aodv
DST=src/pmaodv
cp -r "$SRC" "$DST"
cd "$DST"

# Rename file pattern aodv -> pmaodv
find . -depth -name "aodv*" | while read -r f; do
    new=$(echo "$f" | sed 's|/aodv|/pmaodv|; s|^aodv|pmaodv|')
    [ "$f" != "$new" ] && mv "$f" "$new"
done

# Replace text trong files (lowercase trước, vì 'pmaodv' chứa 'aodv')
find . -type f \( -name "*.h" -o -name "*.cc" -o -name "CMakeLists.txt" \) -print0 | \
    xargs -0 sed -i \
        -e 's/aodv/pmaodv/g' \
        -e 's/Aodv/Pmaodv/g' \
        -e 's/AODV/PMAODV/g'

cd "$NS3_DIR"

# ===== Step 3: Create AOMDV skeleton (clone from AODV) =====
echo "[3/9] Create AOMDV skeleton (clone src/aodv -> src/aomdv)..."
SRC=src/aodv
DST=src/aomdv
cp -r "$SRC" "$DST"
cd "$DST"

find . -depth -name "aodv*" | while read -r f; do
    new=$(echo "$f" | sed 's|/aodv|/aomdv|; s|^aodv|aomdv|')
    [ "$f" != "$new" ] && mv "$f" "$new"
done

find . -type f \( -name "*.h" -o -name "*.cc" -o -name "CMakeLists.txt" \) -print0 | \
    xargs -0 sed -i \
        -e 's/aodv/aomdv/g' \
        -e 's/Aodv/Aomdv/g' \
        -e 's/AODV/AOMDV/g'

cd "$NS3_DIR"

# ===== Step 3b: Create QMAODV skeleton (clone from AODV) =====
echo "[3b/10] Create QMAODV skeleton (clone src/aodv -> src/qmaodv)..."
SRC=src/aodv
DST=src/qmaodv
cp -r "$SRC" "$DST"
cd "$DST"

find . -depth -name "aodv*" | while read -r f; do
    new=$(echo "$f" | sed 's|/aodv|/qmaodv|; s|^aodv|qmaodv|')
    [ "$f" != "$new" ] && mv "$f" "$new"
done

find . -type f \( -name "*.h" -o -name "*.cc" -o -name "CMakeLists.txt" \) -print0 | \
    xargs -0 sed -i \
        -e 's/aodv/qmaodv/g' \
        -e 's/Aodv/Qmaodv/g' \
        -e 's/AODV/QMAODV/g'

cd "$NS3_DIR"

# ===== Step 3c: Create SA-QMAODV skeleton (clone from AODV) =====
echo "[3c/10] Create SA-QMAODV skeleton (clone src/aodv -> src/saqmaodv)..."
SRC=src/aodv
DST=src/saqmaodv
cp -r "$SRC" "$DST"
cd "$DST"

find . -depth -name "aodv*" | while read -r f; do
    new=$(echo "$f" | sed 's|/aodv|/saqmaodv|; s|^aodv|saqmaodv|')
    [ "$f" != "$new" ] && mv "$f" "$new"
done

find . -type f \( -name "*.h" -o -name "*.cc" -o -name "CMakeLists.txt" \) -print0 | \
    xargs -0 sed -i \
        -e 's/aodv/saqmaodv/g' \
        -e 's/Aodv/Saqmaodv/g' \
        -e 's/AODV/SAQMAODV/g'

cd "$NS3_DIR"

# ===== Step 4: Copy multipath-table / q-table / sa-q-table files + add to CMakeLists =====
echo "[4/10] Copy multipath-table.{h,cc} + q-table.{h,cc} + sa-q-table.{h,cc} + update CMakeLists..."
cp "$PROJECT_ROOT/files/pmaodv-multipath-table.h"  "$NS3_DIR/src/pmaodv/model/"
cp "$PROJECT_ROOT/files/pmaodv-multipath-table.cc" "$NS3_DIR/src/pmaodv/model/"
cp "$PROJECT_ROOT/files/aomdv-multipath-table.h"   "$NS3_DIR/src/aomdv/model/"
cp "$PROJECT_ROOT/files/aomdv-multipath-table.cc"  "$NS3_DIR/src/aomdv/model/"
cp "$PROJECT_ROOT/files/qmaodv-qtable.h"           "$NS3_DIR/src/qmaodv/model/"
cp "$PROJECT_ROOT/files/qmaodv-qtable.cc"          "$NS3_DIR/src/qmaodv/model/"
cp "$PROJECT_ROOT/files/saqmaodv-qtable.h"         "$NS3_DIR/src/saqmaodv/model/"
cp "$PROJECT_ROOT/files/saqmaodv-qtable.cc"        "$NS3_DIR/src/saqmaodv/model/"

# Add to CMakeLists for PMAODV/AOMDV
for m in pmaodv aomdv; do
    CM="$NS3_DIR/src/$m/CMakeLists.txt"
    if ! grep -q "${m}-multipath-table" "$CM"; then
        sed -i "s|model/${m}-rtable.cc|model/${m}-rtable.cc\n    model/${m}-multipath-table.cc|" "$CM"
        sed -i "s|model/${m}-rtable.h|model/${m}-rtable.h\n    model/${m}-multipath-table.h|" "$CM"
    fi
done
# QMAODV adds qmaodv-qtable.{h,cc}
CM="$NS3_DIR/src/qmaodv/CMakeLists.txt"
if ! grep -q "qmaodv-qtable" "$CM"; then
    sed -i "s|model/qmaodv-rtable.cc|model/qmaodv-rtable.cc\n    model/qmaodv-qtable.cc|" "$CM"
    sed -i "s|model/qmaodv-rtable.h|model/qmaodv-rtable.h\n    model/qmaodv-qtable.h|" "$CM"
fi
# SAQMAODV adds saqmaodv-qtable.{h,cc}
CM="$NS3_DIR/src/saqmaodv/CMakeLists.txt"
if ! grep -q "saqmaodv-qtable" "$CM"; then
    sed -i "s|model/saqmaodv-rtable.cc|model/saqmaodv-rtable.cc\n    model/saqmaodv-qtable.cc|" "$CM"
    sed -i "s|model/saqmaodv-rtable.h|model/saqmaodv-rtable.h\n    model/saqmaodv-qtable.h|" "$CM"
fi
# Add energy module dependency to qmaodv + saqmaodv (for residual-energy reward)
for m in qmaodv saqmaodv; do
    CM="$NS3_DIR/src/$m/CMakeLists.txt"
    if ! grep -q "energy" "$CM"; then
        sed -i 's|libcore|libcore\n  libenergy|' "$CM" 2>/dev/null || true
    fi
done

# ===== Step 5: Apply PMAODV patches (Phase 2.3.a/b/c/d) =====
echo "[5/9] Apply PMAODV patches (Phase 2.3.a/b/c/d)..."
for p in apply-phase-2.3a.py apply-phase-2.3b.py apply-phase-2.3c.py apply-phase-2.3d.py; do
    echo "  $p"
    python3 "$PROJECT_ROOT/scripts/patches/$p"
done

# Run fix for 2.3a (the SetMaxPaths definition placement bug)
if [ -f "$PROJECT_ROOT/scripts/patches/fix-2.3a.py" ]; then
    echo "  fix-2.3a.py (định vị correct cho method definitions)"
    python3 "$PROJECT_ROOT/scripts/patches/fix-2.3a.py"
fi

# ===== Step 6: Apply AOMDV patches (Phase 3.2-3.6) =====
echo "[6/9] Apply AOMDV patches (Phase 3.2-3.3, 3.4-3.6)..."
python3 "$PROJECT_ROOT/scripts/patches/apply-aomdv-3.2-3.3.py"
python3 "$PROJECT_ROOT/scripts/patches/apply-aomdv-3.4-3.6.py"

# ===== Step 6b: Apply QMAODV patches (Phase Q-2.3.a/b/c/d) =====
echo "[6b/10] Apply QMAODV patches (Q-learning hooks)..."
for p in apply-qmaodv-2.3a.py apply-qmaodv-2.3b.py \
         apply-qmaodv-2.3c.py apply-qmaodv-2.3d.py apply-qmaodv-fix-v2.py; do
    echo "  $p"
    python3 "$PROJECT_ROOT/scripts/patches/$p"
done

# ===== Step 6c: Apply SA-QMAODV patches (Self-Adaptive hooks) =====
echo "[6c/10] Apply SA-QMAODV patches (Self-Adaptive Q-learning hooks)..."
for p in apply-saqmaodv-2.3a.py apply-saqmaodv-2.3b.py \
         apply-saqmaodv-2.3c.py apply-saqmaodv-2.3d.py apply-saqmaodv-fix-v2.py; do
    echo "  $p"
    python3 "$PROJECT_ROOT/scripts/patches/$p"
done

# ===== Step 6d: Fix ns-3.40 energy namespace in SA-QMAODV routing protocol =====
# apply-saqmaodv-2.3a.py injects GetEnergyFraction() using ns3::energy:: (ns-3.42 layout).
# On ns-3.40 the energy types live directly in ns3::, so we strip the sub-namespace.
if [ -d "$NS3_DIR/src/energy" ] && \
   ! grep -q "namespace energy" "$NS3_DIR/src/energy/model/basic-energy-source.h" 2>/dev/null; then
    echo "[6d/10] ns-3.40 detected — fixing energy:: namespace in saqmaodv-routing-protocol.cc..."
    sed -i 's/ns3::energy::/ns3::/g' \
        "$NS3_DIR/src/saqmaodv/model/saqmaodv-routing-protocol.cc"
fi

# ===== Step 7: Apply Fix Level 1 + 2 (PMAODV/AOMDV — QMAODV has fixes baked into q-table) =====
echo "[7/9] Apply Fix Level 1 + 2 (validate stale alternates)..."
python3 "$PROJECT_ROOT/scripts/patches/apply-fix-level-1.py"
python3 "$PROJECT_ROOT/scripts/patches/apply-fix-level-2.py"

# ===== Step 8: Copy fanet-sim.cc + Build =====
echo "[8/9] Copy fanet-sim.cc + Configure + Build..."
cp "$PROJECT_ROOT/src/fanet-sim.cc" "$NS3_DIR/scratch/"

# Auto-detect NS-3 version: ns-3.40 keeps energy types in ns3:: directly,
# while ns-3.42+ moved them to ns3::energy. The shipped fanet-sim.cc targets
# ns-3.42; on ns-3.40 we strip the namespace qualifier.
if [ -d "$NS3_DIR/src/energy" ] && \
   ! grep -q "namespace energy" "$NS3_DIR/src/energy/model/basic-energy-source.h" 2>/dev/null; then
    echo "  Detected ns-3.40 layout — removing 'energy::' qualifiers from scratch/fanet-sim.cc"
    sed -i '/^namespace energy = ns3::energy;/d; s/energy:://g' \
        "$NS3_DIR/scratch/fanet-sim.cc"
fi

cd "$NS3_DIR"
./ns3 configure --enable-examples --enable-tests --build-profile=optimized 2>&1 | tail -5
./ns3 build 2>&1 | tail -10

# Verify
EXEC=$(find build -maxdepth 2 -name "*fanet-sim*" -executable -type f 2>/dev/null | head -1)
if [ -z "$EXEC" ]; then
    echo "ERROR: build failed"
    exit 1
fi

echo ""
echo "========================================"
echo "  Build OK"
echo "========================================"
echo "EXEC: $NS3_DIR/$EXEC"
echo ""
echo "Smoke test (6 protocols):"
"$EXEC" --protocol=AODV     --numNodes=5 --simTime=10 --csvFile=/tmp/s.csv 2>&1 | tail -1
"$EXEC" --protocol=DSDV     --numNodes=5 --simTime=10 --csvFile=/tmp/s.csv 2>&1 | tail -1
"$EXEC" --protocol=PMAODV   --numNodes=5 --simTime=10 --maxPaths=3 --csvFile=/tmp/s.csv 2>&1 | tail -1
"$EXEC" --protocol=AOMDV    --numNodes=5 --simTime=10 --maxPaths=3 --csvFile=/tmp/s.csv 2>&1 | tail -1
"$EXEC" --protocol=QMAODV   --numNodes=5 --simTime=10 --maxPaths=3 --csvFile=/tmp/s.csv 2>&1 | tail -1
"$EXEC" --protocol=SAQMAODV --numNodes=5 --simTime=10 --maxPaths=3 --csvFile=/tmp/s.csv 2>&1 | tail -1

echo ""
echo "Next: bash $PKG_DIR/scripts/cloud-run-parallel.sh"

# ===== Step 6e: Install QSAQMAODV module =====
echo "[6e/10] Install QSAQMAODV module (Queue-State Self-Adaptive)..."
if [ -d "$NS3_DIR/src/qsaqmaodv" ]; then
    rm -rf "$NS3_DIR/src/qsaqmaodv"
fi
cp -r "$PROJECT_ROOT/files/qsaqmaodv-module" "$NS3_DIR/src/qsaqmaodv"
echo "  Installed: $NS3_DIR/src/qsaqmaodv"
