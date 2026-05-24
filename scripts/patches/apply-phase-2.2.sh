#!/bin/bash
# Phase 2.2: Add MultipathTable class to pmaodv module.
# Usage: cd ~/workspace/ns-allinone-3.40/ns-3.40 && bash apply-phase-2.2.sh

set -e

NS3_DIR="${NS3_DIR:-$HOME/workspace/ns-allinone-3.40/ns-3.40}"
SRC_DIR="${SRC_DIR:-/mnt/e/CODE}"

cd "$NS3_DIR"

echo "=== 1. Copy multipath-table files into src/pmaodv/model/ ==="
cp "$SRC_DIR/pmaodv-multipath-table.h" src/pmaodv/model/
cp "$SRC_DIR/pmaodv-multipath-table.cc" src/pmaodv/model/
echo "  Copied."

echo ""
echo "=== 2. Add to src/pmaodv/CMakeLists.txt ==="
CMAKE=src/pmaodv/CMakeLists.txt

# Check if already added
if grep -q "pmaodv-multipath-table" "$CMAKE"; then
    echo "  Đã có sẵn trong CMakeLists.txt, skip."
else
    # Insert pmaodv-multipath-table.cc after pmaodv-rtable.cc in SOURCE_FILES
    sed -i 's|model/pmaodv-rtable.cc|model/pmaodv-rtable.cc\n    model/pmaodv-multipath-table.cc|' "$CMAKE"
    # Insert pmaodv-multipath-table.h after pmaodv-rtable.h in HEADER_FILES
    sed -i 's|model/pmaodv-rtable.h|model/pmaodv-rtable.h\n    model/pmaodv-multipath-table.h|' "$CMAKE"
    echo "  Added to CMakeLists.txt."
fi

echo ""
echo "=== 3. Verify CMakeLists.txt ==="
grep -E "multipath-table" "$CMAKE" || echo "  WARNING: not found in CMakeLists!"

echo ""
echo "=== 4. Reconfigure + build ==="
./ns3 configure --enable-examples --enable-tests --build-profile=debug 2>&1 | tail -5
./ns3 build 2>&1 | tail -10

echo ""
echo "=== 5. Verify multipath-table.h exposed ==="
ls -la build/include/ns3/pmaodv-multipath-table.h 2>&1

echo ""
echo "=========================================="
echo "  Phase 2.2 done. PMAODV vẫn chạy như AODV"
echo "  (multipath table tồn tại nhưng chưa wire vào routing logic)"
echo "  Test: bash test-pmaodv-skeleton.sh"
echo "=========================================="
