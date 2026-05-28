#!/usr/bin/env python3
"""
apply-qsaqmaodv-module.py
Creates the NS-3 'qsaqmaodv' routing module by:
  1. Cloning src/saqmaodv -> src/qsaqmaodv (renaming all identifiers)
  2. Replacing qtable files with the 4-term reward versions (impl/)
  3. Registering qtable in CMakeLists.txt
  4. Patching routing-protocol.{h,cc} to add:
       - m_qsW4{0.20}, m_queueHighThreshold, m_queueLowThreshold
       - GetQueueOccupancy() via m_queue (routing queue proxy)
       - RewardW4, QueueHighThreshold, QueueLowThreshold attributes
       - Pass queueOcc to RecomputeAdaptiveRewardWeights() in PeriodicAdaptiveTick
  5. Does NOT rebuild (use apply-qsaqmaodv-all.sh for full build).

Usage:
  python3 qsaqmaodv/patches/apply-qsaqmaodv-module.py
  NS3_DIR=/custom/path python3 qsaqmaodv/patches/apply-qsaqmaodv-module.py
"""
import os
import re
import shutil
import sys

NS3_DIR      = os.environ.get("NS3_DIR", os.path.expanduser(
                   "~/ns-allinone-3.40-qsaqmaodv/ns-3.40"))
PROJECT_ROOT = os.environ.get("PROJECT_ROOT",
                   os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SRC_SAQMAODV  = os.path.join(NS3_DIR, "src", "saqmaodv")
DST_QSAQMAODV = os.path.join(NS3_DIR, "src", "qsaqmaodv")
_impl_candidate = os.path.join(PROJECT_ROOT, "impl")
_impl_script    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "impl")
IMPL_DIR = _impl_candidate if os.path.isdir(_impl_candidate) else os.path.normpath(_impl_script)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rename_content(text):
    text = text.replace("saqmaodv", "qsaqmaodv")
    text = text.replace("SAQMAODV", "QSAQMAODV")
    text = text.replace("Saqmaodv", "Qsaqmaodv")
    return text


def rename_path(path):
    return path.replace("saqmaodv", "qsaqmaodv").replace("SAQMAODV", "QSAQMAODV")


def find_addattr_end(text, start):
    """
    Given text and a position inside an .AddAttribute( call (after the opening
    paren), walk forward counting parens until we find the matching closing paren.
    Returns the index AFTER the closing ')'.
    """
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
        i += 1
    return i  # points one past the closing ')'


# ---------------------------------------------------------------------------
# Step 1 -- Clone saqmaodv -> qsaqmaodv
# ---------------------------------------------------------------------------

def clone_module():
    print("=== Step 1: Clone saqmaodv -> qsaqmaodv ===")
    if not os.path.isdir(SRC_SAQMAODV):
        sys.exit("  ERROR: {} not found. Install SA-QMAODV first.".format(SRC_SAQMAODV))

    if os.path.isdir(DST_QSAQMAODV):
        model_dir = os.path.join(DST_QSAQMAODV, "model")
        routing_h = os.path.join(model_dir, "qsaqmaodv-routing-protocol.h")
        if os.path.isdir(model_dir) and os.path.exists(routing_h):
            print("  Module already exists and looks complete -- skipping clone.")
            return
        else:
            print("  Module dir exists but incomplete -- removing and re-cloning...")
            shutil.rmtree(DST_QSAQMAODV)

    for root, dirs, files in os.walk(SRC_SAQMAODV):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
        rel_root = os.path.relpath(root, SRC_SAQMAODV)
        dst_root = os.path.join(DST_QSAQMAODV, rename_path(rel_root))
        os.makedirs(dst_root, exist_ok=True)
        for fname in files:
            if fname.endswith((".bak", ".bak-sa23a", ".bak-qsaqs")):
                continue
            src_f = os.path.join(root, fname)
            dst_f = os.path.join(dst_root, rename_path(fname))
            with open(src_f, "r", errors="replace") as f:
                content = f.read()
            with open(dst_f, "w") as f:
                f.write(rename_content(content))

    print("  Cloned -> {}".format(DST_QSAQMAODV))


# ---------------------------------------------------------------------------
# Step 2 -- Install 4-term qtable files from impl/
# ---------------------------------------------------------------------------

def install_qtable():
    print("=== Step 2: Install QS-QMAODV qtable (4-term reward) ===")
    model_dir = os.path.join(DST_QSAQMAODV, "model")
    os.makedirs(model_dir, exist_ok=True)

    for fname in ("qsaqmaodv-qtable.h", "qsaqmaodv-qtable.cc"):
        src = os.path.join(IMPL_DIR, fname)
        if not os.path.exists(src):
            sys.exit("  ERROR: {} not found. Run from qsaqmaodv/ project root.".format(src))
        dst = os.path.join(model_dir, fname)
        shutil.copy(src, dst)
        print("  Copied {}".format(fname))


# ---------------------------------------------------------------------------
# Step 3 -- Register qtable in CMakeLists.txt
# ---------------------------------------------------------------------------

def patch_cmake():
    print("=== Step 3: Patch CMakeLists.txt ===")
    cmake = os.path.join(DST_QSAQMAODV, "CMakeLists.txt")
    if not os.path.exists(cmake):
        sys.exit("  ERROR: {} not found.".format(cmake))

    with open(cmake) as f:
        c = f.read()
    changed = False

    if "qsaqmaodv-qtable.cc" not in c:
        c = c.replace(
            "model/qsaqmaodv-rtable.cc",
            "model/qsaqmaodv-rtable.cc\n    model/qsaqmaodv-qtable.cc", 1)
        changed = True
        print("  + qsaqmaodv-qtable.cc")

    if "qsaqmaodv-qtable.h" not in c:
        c = c.replace(
            "model/qsaqmaodv-rtable.h",
            "model/qsaqmaodv-rtable.h\n    model/qsaqmaodv-qtable.h", 1)
        changed = True
        print("  + qsaqmaodv-qtable.h")

    if changed:
        with open(cmake, "w") as f:
            f.write(c)
    else:
        print("  Already up to date.")


# ---------------------------------------------------------------------------
# Step 4 -- Patch routing-protocol.h
# ---------------------------------------------------------------------------

HEADER_MEMBERS = """\
  // === QS-QMAODV: queue-state adaptive mode ===
  double m_qsW4{0.20};              ///< queue-state reward weight (w4)
  double m_queueHighThreshold{0.70}; ///< enter HIGH_LOAD when q > this
  double m_queueLowThreshold{0.30};  ///< exit  HIGH_LOAD when q < this
"""

HEADER_METHOD = """\
  /// QS-QMAODV: routing queue occupancy proxy in [0,1]
  double GetQueueOccupancy();
"""


def patch_header(h_file):
    with open(h_file) as f:
        h = f.read()

    changed = False

    # Add queue-state members after existing member
    if "m_queueHighThreshold" not in h:
        for anchor in ("m_periodicAdaptInterval", "m_lowEnergyThreshold", "m_w3"):
            idx = h.find(anchor)
            if idx != -1:
                eol = h.find(";", idx)
                eol = h.find("\n", eol)
                h = h[:eol + 1] + HEADER_MEMBERS + h[eol + 1:]
                changed = True
                print("  + m_qsW4 / m_queueHighThreshold / m_queueLowThreshold members")
                break

    # Add GetQueueOccupancy() declaration (NOT const — RequestQueue methods are non-const)
    if "GetQueueOccupancy" not in h:
        for anchor in ("GetEnergyFraction", "GetAlpha", "GetEpsilon"):
            idx = h.find(anchor)
            if idx != -1:
                eol = h.find(";", idx)
                eol = h.find("\n", eol)
                h = h[:eol + 1] + HEADER_METHOD + h[eol + 1:]
                changed = True
                print("  + GetQueueOccupancy() declaration")
                break

    # Ensure existing declaration is NOT const (fix if const was added previously)
    if "GetQueueOccupancy() const" in h:
        h = h.replace("GetQueueOccupancy() const", "GetQueueOccupancy()")
        changed = True
        print("  Fixed: removed 'const' from GetQueueOccupancy() declaration")

    if changed:
        with open(h_file, "w") as f:
            f.write(h)
    else:
        print("  Header already up to date.")


# ---------------------------------------------------------------------------
# Step 4b -- Patch routing-protocol.cc
# ---------------------------------------------------------------------------

# Uses m_queue (SA-QMAODV routing queue) as congestion proxy.
# AdhocWifiMac (802.11b) has no EDCA/BE_Txop queues.
# NOTE: GetQueueOccupancy() must NOT be const because RequestQueue::GetSize()
#       and GetMaxQueueLen() are non-const methods in SA-QMAODV.
GET_QUEUE_OCC_IMPL = (
    "double\n"
    "RoutingProtocol::GetQueueOccupancy()\n"
    "{\n"
    "    // Routing queue occupancy as congestion proxy in [0.0, 1.0].\n"
    "    // Uses m_queue (SA-QMAODV request queue) -- valid for AdhocWifiMac.\n"
    "    uint32_t cur = m_queue.GetSize();\n"
    "    uint32_t cap = m_queue.GetMaxQueueLen();\n"
    "    if (cap == 0) { return 0.0; }\n"
    "    return std::min(1.0, static_cast<double>(cur) / static_cast<double>(cap));\n"
    "}\n\n"
)

REWARD_W4_ATTR = (
    '\n    .AddAttribute("RewardW4",\n'
    '                  "Queue-state reward weight w4 (Normal mode)",\n'
    '                  DoubleValue(0.20),\n'
    '                  MakeDoubleAccessor(&RoutingProtocol::m_qsW4),\n'
    '                  MakeDoubleChecker<double>(0.0, 1.0))'
)

QUEUE_HIGH_LOW_ATTRS = (
    '    .AddAttribute("QueueHighThreshold",\n'
    '                  "Queue occupancy to enter HIGH_LOAD mode",\n'
    '                  DoubleValue(0.70),\n'
    '                  MakeDoubleAccessor(&RoutingProtocol::m_queueHighThreshold),\n'
    '                  MakeDoubleChecker<double>(0.0, 1.0))\n'
    '    .AddAttribute("QueueLowThreshold",\n'
    '                  "Queue occupancy to exit HIGH_LOAD mode",\n'
    '                  DoubleValue(0.30),\n'
    '                  MakeDoubleAccessor(&RoutingProtocol::m_queueLowThreshold),\n'
    '                  MakeDoubleChecker<double>(0.0, 1.0))\n'
    '    '
)


def patch_cc(cc_file):
    with open(cc_file) as f:
        cc = f.read()

    changed = False

    # ---- 1. Add m_qsW4 member initializer ----
    if "m_qsW4" not in cc:
        cc = cc.replace(
            "m_queueHighThreshold{0.70}",
            "m_qsW4{0.20}, m_queueHighThreshold{0.70}"
        )
        if "m_qsW4" in cc:
            changed = True
            print("  + m_qsW4{0.20} initializer")

    # ---- 2. Add RewardW4 attribute (paren-counting approach) ----
    if '"RewardW4"' not in cc:
        # Find the RewardW3 attribute call and its end
        marker = '"RewardW3"'
        idx = cc.find(marker)
        if idx == -1:
            print("  WARNING: 'RewardW3' not found — skipping RewardW4 attribute insertion")
        else:
            # Find the opening paren of .AddAttribute( before "RewardW3"
            dot_attr = cc.rfind('.AddAttribute', 0, idx)
            open_paren = cc.find('(', dot_attr)
            # Walk forward to find the matching closing paren
            end = find_addattr_end(cc, open_paren + 1)
            # Insert REWARD_W4_ATTR right after end
            cc = cc[:end] + REWARD_W4_ATTR + cc[end:]
            changed = True
            print("  + RewardW4 attribute (0.20)")

    # ---- 3. Add QueueHighThreshold / QueueLowThreshold attributes ----
    if '"QueueHighThreshold"' not in cc:
        # Insert before LowEnergyThreshold attribute
        marker = '.AddAttribute("LowEnergyThreshold"'
        idx = cc.find(marker)
        if idx == -1:
            # Try alternate spacing
            idx = cc.find('.AddAttribute( "LowEnergyThreshold"')
        if idx == -1:
            print("  WARNING: 'LowEnergyThreshold' not found — skipping QueueHighThreshold insertion")
        else:
            cc = cc[:idx] + QUEUE_HIGH_LOW_ATTRS + cc[idx:]
            changed = True
            print("  + QueueHighThreshold / QueueLowThreshold attributes")

    # ---- 4. Add GetQueueOccupancy() implementation ----
    if "GetQueueOccupancy" not in cc:
        for ns_close in ("} // namespace qsaqmaodv\n} // namespace ns3",
                         "} // namespace qsaqmaodv\n"):
            idx = cc.rfind(ns_close)
            if idx != -1:
                cc = cc[:idx] + GET_QUEUE_OCC_IMPL + cc[idx:]
                changed = True
                print("  + GetQueueOccupancy() implementation")
                break
    else:
        # Fix: ensure implementation uses m_queue (not m_rqueue) and is not const
        if "RoutingProtocol::GetQueueOccupancy() const" in cc:
            cc = cc.replace(
                "RoutingProtocol::GetQueueOccupancy() const",
                "RoutingProtocol::GetQueueOccupancy()"
            )
            changed = True
            print("  Fixed: removed 'const' from GetQueueOccupancy() implementation")
        if "m_rqueue.GetSize()" in cc:
            cc = cc.replace("m_rqueue.GetSize()", "m_queue.GetSize()")
            cc = cc.replace("m_rqueue.GetMaxQueueLen()", "m_queue.GetMaxQueueLen()")
            changed = True
            print("  Fixed: m_rqueue -> m_queue in GetQueueOccupancy()")

    # ---- 5. Patch PeriodicAdaptiveTick: 1-arg -> 2-arg RecomputeAdaptiveRewardWeights ----
    if "RecomputeAdaptiveRewardWeights(energyFrac)" in cc:
        cc = cc.replace(
            "m_qtable.RecomputeAdaptiveRewardWeights(energyFrac);",
            "double queueOcc = GetQueueOccupancy();\n"
            "    m_qtable.SetQueueHighThreshold(m_queueHighThreshold);\n"
            "    m_qtable.SetQueueLowThreshold(m_queueLowThreshold);\n"
            "    m_qtable.RecomputeAdaptiveRewardWeights(energyFrac, queueOcc);"
        )
        changed = True
        print("  + PeriodicAdaptiveTick passes queueOcc")

    if "RecomputeAdaptiveRewardWeights(GetEnergyFraction())" in cc:
        cc = cc.replace(
            "m_qtable.RecomputeAdaptiveRewardWeights(GetEnergyFraction());",
            "double queueOcc = GetQueueOccupancy();\n"
            "    m_qtable.RecomputeAdaptiveRewardWeights(GetEnergyFraction(), queueOcc);"
        )
        changed = True
        print("  + PeriodicAdaptiveTick (GetEnergyFraction form) passes queueOcc")

    if changed:
        with open(cc_file, "w") as f:
            f.write(cc)
    else:
        print("  .cc already up to date.")


def patch_rerr_congestion(cc_file):
    """
    Step 4c: Wire per-neighbor RERR congestion into routing-protocol.cc.

    Changes:
      1. After m_qtable.OnRouteError()  → add m_qtable.RecordNeighborRerr(src)
         (the RERR sender is the 'src' parameter of RecvError)
      2. After m_qtable.PeriodicEpsilonDecay() → add m_qtable.DecayNeighborCongestion()
      3. Upgrade SetRewardWeights(w1,w2,w3) calls to SetRewardWeights(w1,w2,w3,m_qsW4)
         so that --qsW4 command-line argument actually reaches the QTable.
    """
    print("=== Step 4c: Patch RERR congestion hooks ===")
    with open(cc_file) as f:
        cc = f.read()

    changed = False

    # ---- 1. RecordNeighborRerr after OnRouteError ----
    # RecvError(Ptr<Packet> p, Ipv4Address src) calls m_qtable.OnRouteError();
    # The RERR sender is the 'src' parameter — penalise it.
    if "RecordNeighborRerr" not in cc:
        # Try common indentation variants (2-space and 4-space)
        hooked = False
        for indent in ("    ", "  ", "\t"):
            anchor = "{indent}m_qtable.OnRouteError();\n".format(indent=indent)
            if anchor in cc:
                replacement = (
                    "{indent}m_qtable.OnRouteError();\n"
                    "{indent}m_qtable.RecordNeighborRerr(src); "
                    "// QS-QMAODV: per-neighbor RERR congestion\n"
                ).format(indent=indent)
                cc = cc.replace(anchor, replacement, 1)
                changed = True
                hooked = True
                print("  + RecordNeighborRerr(src) after OnRouteError()")
                break
        if not hooked:
            print("  WARNING: OnRouteError() anchor not found — "
                  "RecordNeighborRerr NOT patched. "
                  "Manually add: m_qtable.RecordNeighborRerr(src); "
                  "after m_qtable.OnRouteError(); in RecvError()")

    # ---- 2. DecayNeighborCongestion in periodic tick ----
    if "DecayNeighborCongestion" not in cc:
        hooked = False
        for indent in ("    ", "  ", "\t"):
            anchor = "{indent}m_qtable.PeriodicEpsilonDecay();\n".format(indent=indent)
            if anchor in cc:
                replacement = (
                    "{indent}m_qtable.PeriodicEpsilonDecay();\n"
                    "{indent}m_qtable.DecayNeighborCongestion(); "
                    "// QS-QMAODV: decay RERR congestion scores\n"
                ).format(indent=indent)
                cc = cc.replace(anchor, replacement, 1)
                changed = True
                hooked = True
                print("  + DecayNeighborCongestion() in periodic epsilon tick")
                break
        if not hooked:
            print("  WARNING: PeriodicEpsilonDecay() anchor not found — "
                  "DecayNeighborCongestion NOT patched. "
                  "Manually add: m_qtable.DecayNeighborCongestion(); "
                  "after m_qtable.PeriodicEpsilonDecay();")

    # ---- 3. Upgrade SetRewardWeights to 4-arg form with m_qsW4 ----
    # SA-QMAODV calls m_qtable.SetRewardWeights(m_w1, m_w2, m_w3) with 3 args.
    # We need to pass m_qsW4 as the 4th arg so --qsW4 actually reaches the QTable.
    if "m_qtable.SetRewardWeights" in cc and "m_qsW4" not in cc.split("SetRewardWeights")[1].split(")")[0]:
        # Replace 3-arg call with 4-arg call using regex
        new_cc = re.sub(
            r'm_qtable\.SetRewardWeights\(([^,)]+),\s*([^,)]+),\s*([^,)]+)\)',
            r'm_qtable.SetRewardWeights(\1, \2, \3, m_qsW4)',
            cc
        )
        if new_cc != cc:
            cc = new_cc
            changed = True
            print("  + SetRewardWeights upgraded to 4-arg (w1,w2,w3,m_qsW4)")
        else:
            print("  SetRewardWeights already 4-arg or not found.")
    else:
        if "m_qtable.SetRewardWeights" not in cc:
            print("  NOTE: SetRewardWeights not found in cc — QTable uses constructor defaults.")
            print("        Ensure m_qsW4 is passed to m_qtable.SetRewardWeights on DoInitialize.")

    if changed:
        with open(cc_file, "w") as f:
            f.write(cc)
    else:
        print("  RERR congestion already patched (or anchors not found).")


def patch_routing_protocol():
    print("=== Step 4: Patch routing-protocol.{h,cc} ===")
    model_dir = os.path.join(DST_QSAQMAODV, "model")
    h_file  = os.path.join(model_dir, "qsaqmaodv-routing-protocol.h")
    cc_file = os.path.join(model_dir, "qsaqmaodv-routing-protocol.cc")

    for p in (h_file, cc_file):
        if not os.path.exists(p):
            sys.exit("  ERROR: {} not found.".format(p))

    patch_header(h_file)
    patch_cc(cc_file)
    patch_rerr_congestion(cc_file)


# ---------------------------------------------------------------------------
# Step 5 -- Sanity-check helper
# ---------------------------------------------------------------------------

def check_helper():
    print("=== Step 5: Check helper ===")
    helper = os.path.join(DST_QSAQMAODV, "helper", "qsaqmaodv-helper.cc")
    if os.path.exists(helper):
        print("  Helper found -- attribute-based Set() needs no extra patching.")
    else:
        print("  WARNING: helper not found.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print(" apply-qsaqmaodv-module.py")
    print(" NS3_DIR      = {}".format(NS3_DIR))
    print(" PROJECT_ROOT = {}".format(PROJECT_ROOT))
    print(" IMPL_DIR     = {}".format(IMPL_DIR))
    print("=" * 60)

    clone_module()
    install_qtable()
    patch_cmake()
    patch_routing_protocol()
    check_helper()

    print()
    print("=" * 60)
    print(" Module patching complete.")
    print("  cd {}".format(NS3_DIR))
    print("  ./ns3 build 2>&1 | grep -E 'error:|warning:' | head -30")
    print("=" * 60)
