#!/usr/bin/env python3
"""
AOMDV Phase 3.2 + 3.3:
  - Copy aomdv-multipath-table.{h,cc} into src/aomdv/model/ (idempotent)
  - Add to src/aomdv/CMakeLists.txt
  - Patch aomdv-routing-protocol.h: add include, members, public method decls
  - Patch aomdv-routing-protocol.cc: add MaxPaths attribute, define methods
"""

import os
import re
import shutil
import sys

NS3 = os.environ.get("NS3_DIR") or os.path.expanduser("~/ns-allinone-3.42/ns-3.42")
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WS = (os.environ.get("WS_DIR")
      or (os.path.join(_SCRIPT_DIR, "..", "files")
          if os.path.isdir(os.path.join(_SCRIPT_DIR, "..", "files"))
          else "/mnt/e/CODE"))
MODEL_DIR = os.path.join(NS3, "src/aomdv/model")
CMAKE = os.path.join(NS3, "src/aomdv/CMakeLists.txt")
H = os.path.join(MODEL_DIR, "aomdv-routing-protocol.h")
CC = os.path.join(MODEL_DIR, "aomdv-routing-protocol.cc")


def step(label):
    print(f"\n=== {label} ===")


# Phase 3.2: copy multipath-table files (idempotent)
step("Phase 3.2: copy aomdv-multipath-table files")
for fname in ("aomdv-multipath-table.h", "aomdv-multipath-table.cc"):
    dst = os.path.join(MODEL_DIR, fname)
    if os.path.exists(dst):
        print(f"  {fname} already at destination, skip copy.")
        continue
    src = os.path.join(WS, fname)
    if not os.path.exists(src):
        print(f"  ERROR: source not found {src}")
        sys.exit(1)
    shutil.copy(src, dst)
    print(f"  Copied {fname} from {src}")

# Add to CMakeLists
with open(CMAKE) as f:
    cm = f.read()
if "aomdv-multipath-table" in cm:
    print("  CMakeLists already has aomdv-multipath-table, skip.")
else:
    cm = re.sub(
        r"(model/aomdv-rtable\.cc)",
        r"\1\n    model/aomdv-multipath-table.cc",
        cm,
        count=1,
    )
    cm = re.sub(
        r"(model/aomdv-rtable\.h)",
        r"\1\n    model/aomdv-multipath-table.h",
        cm,
        count=1,
    )
    with open(CMAKE, "w") as f:
        f.write(cm)
    print("  Added to CMakeLists.txt")


# Phase 3.3: patch routing-protocol.h
step("Phase 3.3: patch aomdv-routing-protocol.h")
shutil.copy(H, H + ".bak-3.3")
with open(H) as f:
    hc = f.read()

if "aomdv-multipath-table.h" not in hc:
    hc = hc.replace(
        '#include "aomdv-rtable.h"',
        '#include "aomdv-rtable.h"\n#include "aomdv-multipath-table.h"',
        1,
    )
    print("  + #include aomdv-multipath-table.h")

if "MultipathTable m_multipathTable" not in hc:
    hc = re.sub(
        r"(RoutingTable\s+m_routingTable;)",
        r"\1\n"
        r"  /// AOMDV: alternate routes (besides primary in m_routingTable)\n"
        r"  MultipathTable m_multipathTable;\n"
        r"  /// AOMDV: max routes per dst (set via 'MaxPaths' attribute)\n"
        r"  uint32_t m_maxPaths{3};",
        hc,
        count=1,
    )
    print("  + private members m_multipathTable, m_maxPaths")

if "SetMaxPaths" not in hc:
    pat = re.compile(
        r"(class\s+RoutingProtocol\b[^{]*\{.*?)(\n\s*private:)",
        re.DOTALL,
    )
    m = pat.search(hc)
    if m:
        inject = (
            "\n"
            "  /// AOMDV: setter that propagates to MultipathTable\n"
            "  void SetMaxPaths(uint32_t mp);\n"
            "  uint32_t GetMaxPaths() const;\n"
        )
        hc = hc[: m.end(1)] + inject + hc[m.end(1):]
        print("  + public decl SetMaxPaths/GetMaxPaths")
    else:
        print("  ! WARN: 'class RoutingProtocol private:' anchor not found")
        sys.exit(1)

with open(H, "w") as f:
    f.write(hc)


# Phase 3.3: patch routing-protocol.cc
step("Phase 3.3: patch aomdv-routing-protocol.cc")
shutil.copy(CC, CC + ".bak-3.3")
with open(CC) as f:
    cc = f.read()

if '"MaxPaths"' not in cc:
    pat = re.compile(r"(\.AddConstructor<RoutingProtocol>\(\))")
    m = pat.search(cc)
    if m:
        inject = (
            "\n            "
            '.AddAttribute("MaxPaths",\n'
            '                          "Maximum routes per destination for AOMDV multipath",\n'
            "                          UintegerValue(3),\n"
            "                          MakeUintegerAccessor(&RoutingProtocol::SetMaxPaths,\n"
            "                                               &RoutingProtocol::GetMaxPaths),\n"
            "                          MakeUintegerChecker<uint32_t>(1))"
        )
        cc = cc[: m.end(1)] + inject + cc[m.end(1):]
        print("  + .AddAttribute MaxPaths in TypeId")
    else:
        print("  ! WARN: AddConstructor<RoutingProtocol>() not found")
        sys.exit(1)

if "m_multipathTable.SetMaxPaths(mp);" not in cc:
    methods = (
        "\nvoid\n"
        "RoutingProtocol::SetMaxPaths(uint32_t mp)\n"
        "{\n"
        "    m_maxPaths = mp;\n"
        "    m_multipathTable.SetMaxPaths(mp);\n"
        "}\n"
        "\n"
        "uint32_t\n"
        "RoutingProtocol::GetMaxPaths() const\n"
        "{\n"
        "    return m_maxPaths;\n"
        "}\n"
        "\n"
    )
    matches = list(re.finditer(r"\}\s*//\s*namespace\s+aomdv\b[^\n]*\n", cc))
    if matches:
        m = matches[-1]
        cc = cc[: m.start()] + methods + cc[m.start():]
        print("  + Inserted SetMaxPaths/GetMaxPaths defs")
    else:
        cc = cc.rstrip() + (
            "\n\nnamespace ns3\n{\nnamespace aomdv\n{\n"
            + methods
            + "} // namespace aomdv\n} // namespace ns3\n"
        )
        print("  + Appended SetMaxPaths/GetMaxPaths (fallback re-open ns)")

with open(CC, "w") as f:
    f.write(cc)


step("Done — Build")
print("Run: ./ns3 build")
