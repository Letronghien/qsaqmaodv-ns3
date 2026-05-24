#!/usr/bin/env python3
"""
Phase 2.3.a — Add MultipathTable infrastructure to PmaodvRoutingProtocol.

Modifications:
  pmaodv-routing-protocol.h:
    - #include "pmaodv-multipath-table.h"
    - private members: MultipathTable m_multipathTable; uint32_t m_maxPaths{3};
    - public method declarations: SetMaxPaths, GetMaxPaths

  pmaodv-routing-protocol.cc:
    - .AddAttribute("MaxPaths", ...) inside TypeId()
    - SetMaxPaths/GetMaxPaths method implementations (appended at end)

Idempotent: re-running won't double-apply.
"""

import os
import re
import shutil
import sys

NS3_DIR = os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40")
H_PATH = os.path.join(NS3_DIR, "src/pmaodv/model/pmaodv-routing-protocol.h")
CC_PATH = os.path.join(NS3_DIR, "src/pmaodv/model/pmaodv-routing-protocol.cc")


def backup(p):
    bp = p + ".bak-23a"
    if not os.path.exists(bp):
        shutil.copy(p, bp)
        print(f"  Backup: {bp}")


def patch_header():
    with open(H_PATH) as f:
        c = f.read()
    orig = c

    # 1. Add include
    if "pmaodv-multipath-table.h" not in c:
        c = c.replace(
            '#include "pmaodv-rtable.h"',
            '#include "pmaodv-rtable.h"\n#include "pmaodv-multipath-table.h"',
            1,
        )
        print("  + #include pmaodv-multipath-table.h")

    # 2. Add private members after RoutingTable m_routingTable;
    if "MultipathTable m_multipathTable" not in c:
        c = re.sub(
            r"(RoutingTable\s+m_routingTable;)",
            r"\1\n"
            r"  /// PMAODV: alternate routes (besides primary in m_routingTable)\n"
            r"  MultipathTable m_multipathTable;\n"
            r"  /// PMAODV: max routes per dst (set via 'MaxPaths' attribute)\n"
            r"  uint32_t m_maxPaths{3};",
            c,
            count=1,
        )
        print("  + private members m_multipathTable, m_maxPaths")

    # 3. Add public method decls right before the first "private:" inside class RoutingProtocol
    if "SetMaxPaths" not in c:
        # Match: class RoutingProtocol ... { ... [first private:]
        pat = re.compile(
            r"(class\s+RoutingProtocol\b[^{]*\{.*?)(\n\s*private:)",
            re.DOTALL,
        )
        m = pat.search(c)
        if m:
            inject = (
                "\n"
                "  /// PMAODV: setter that also propagates to MultipathTable\n"
                "  void SetMaxPaths(uint32_t mp);\n"
                "  uint32_t GetMaxPaths() const;\n"
            )
            c = c[: m.end(1)] + inject + c[m.end(1):]
            print("  + public decl SetMaxPaths/GetMaxPaths")
        else:
            print("  ! WARN: 'class RoutingProtocol ... private:' anchor not found in .h")
            return False

    if c != orig:
        with open(H_PATH, "w") as f:
            f.write(c)
    else:
        print("  (no header change)")
    return True


def patch_impl():
    with open(CC_PATH) as f:
        c = f.read()
    orig = c

    # 4. Add MaxPaths attribute after AddConstructor<RoutingProtocol>()
    if '"MaxPaths"' not in c:
        pat = re.compile(r"(\.AddConstructor<RoutingProtocol>\(\))")
        m = pat.search(c)
        if m:
            inject = (
                "\n            "
                '.AddAttribute("MaxPaths",\n'
                '                          "Maximum routes per destination for PMAODV multipath",\n'
                "                          UintegerValue(3),\n"
                "                          MakeUintegerAccessor(&RoutingProtocol::SetMaxPaths,\n"
                "                                               &RoutingProtocol::GetMaxPaths),\n"
                "                          MakeUintegerChecker<uint32_t>(1))"
            )
            c = c[: m.end(1)] + inject + c[m.end(1):]
            print("  + .AddAttribute MaxPaths in TypeId")
        else:
            print("  ! WARN: AddConstructor<RoutingProtocol>() not found in .cc")
            return False

    # 5. Append SetMaxPaths/GetMaxPaths definitions
    if "RoutingProtocol::SetMaxPaths" not in c:
        c += (
            "\n"
            "namespace ns3\n"
            "{\n"
            "namespace pmaodv\n"
            "{\n"
            "\n"
            "void\n"
            "RoutingProtocol::SetMaxPaths(uint32_t mp)\n"
            "{\n"
            "  m_maxPaths = mp;\n"
            "  m_multipathTable.SetMaxPaths(mp);\n"
            "}\n"
            "\n"
            "uint32_t\n"
            "RoutingProtocol::GetMaxPaths() const\n"
            "{\n"
            "  return m_maxPaths;\n"
            "}\n"
            "\n"
            "} // namespace pmaodv\n"
            "} // namespace ns3\n"
        )
        print("  + Appended SetMaxPaths/GetMaxPaths definitions")

    if c != orig:
        with open(CC_PATH, "w") as f:
            f.write(c)
    else:
        print("  (no impl change)")
    return True


def main():
    if not os.path.exists(H_PATH) or not os.path.exists(CC_PATH):
        print(f"ERROR: pmaodv files not found. Expected:\n  {H_PATH}\n  {CC_PATH}")
        sys.exit(1)

    print("=== Phase 2.3.a: Add MultipathTable infrastructure ===")
    print()
    print("Backing up...")
    backup(H_PATH)
    backup(CC_PATH)
    print()

    print("Patching header...")
    if not patch_header():
        print("FAILED. Restore from .bak-23a if needed.")
        sys.exit(1)
    print()

    print("Patching implementation...")
    if not patch_impl():
        print("FAILED. Restore from .bak-23a if needed.")
        sys.exit(1)

    print()
    print("=== Done. Run: ./ns3 build && bash test-pmaodv-skeleton.sh ===")


if __name__ == "__main__":
    main()
