#!/usr/bin/env python3
"""
Fix Level 2 — Validate alternate's nextHop against current routing table at USE time.

Problem (sau Fix Level 1):
  Lifetime filter chỉ catch alts > 3s tuổi. Nhưng ở mobility cao, link break
  trong 1-2s. Alt vừa add cũng có thể có nextHop đã ra khỏi range.
  → Forward qua nextHop dead → packet drop.

Fix Level 2:
  Khi SelectProbabilistic/SelectBestAlternate xử lý alt, check NextHop của alt
  có còn entry VALID trong m_routingTable (như 1-hop neighbor) không.
  Nếu không → skip alt đó.

Implementation:
  1. MultipathTable::GetRoutes() và SelectProbabilisticWithPrimary thêm optional
     parameter `const RoutingTable* mainTable`. Khi != null, validate.
  2. RoutingProtocol::RouteOutput pass &m_routingTable khi gọi.

Apply cho cả pmaodv và aomdv.
"""

import os
import re
import shutil
import sys

NS3 = os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40")


def patch_mt_header(module):
    """Add overload signatures with optional mainTable parameter."""
    h = os.path.join(NS3, f"src/{module}/model/{module}-multipath-table.h")
    label = f"[{module}-mt.h]"
    if not os.path.exists(h):
        print(f"  {label} SKIP")
        return False
    if not os.path.exists(h + ".bak-fix2"):
        shutil.copy(h, h + ".bak-fix2")
    with open(h) as f:
        c = f.read()
    if "Fix Level 2: validate by mainTable" in c:
        print(f"  {label} already applied")
        return True

    # Modify GetRoutes signature
    old = "uint32_t GetRoutes(Ipv4Address dst, std::vector<RoutingTableEntry>& routes) const;"
    new = ("// Fix Level 2: validate by mainTable (optional). Khi mainTable != nullptr,\n"
           "    // skip alts có nextHop không còn VALID trong mainTable.\n"
           "    uint32_t GetRoutes(Ipv4Address dst, std::vector<RoutingTableEntry>& routes,\n"
           "                      const RoutingTable* mainTable = nullptr) const;")
    if old in c:
        c = c.replace(old, new, 1)
    else:
        print(f"  {label} ! GetRoutes signature pattern không match — skip header patch")
        return False

    # For pmaodv, also modify SelectProbabilisticWithPrimary
    if module == "pmaodv":
        old_p = ("bool SelectProbabilisticWithPrimary(const RoutingTableEntry& primary,\n"
                 "                                        RoutingTableEntry& out);")
        new_p = ("bool SelectProbabilisticWithPrimary(const RoutingTableEntry& primary,\n"
                 "                                        RoutingTableEntry& out,\n"
                 "                                        const RoutingTable* mainTable = nullptr);")
        if old_p in c:
            c = c.replace(old_p, new_p, 1)
        else:
            # Try alternate format
            print(f"  {label} ! SelectProbabilistic signature không match exact, thử regex")
            c = re.sub(
                r"bool SelectProbabilisticWithPrimary\(const RoutingTableEntry& primary,\s*\n"
                r"\s*RoutingTableEntry& out\);",
                "bool SelectProbabilisticWithPrimary(const RoutingTableEntry& primary,\n"
                "                                        RoutingTableEntry& out,\n"
                "                                        const RoutingTable* mainTable = nullptr);",
                c, count=1)

    if module == "aomdv":
        old_p = "bool SelectBestAlternate(Ipv4Address dst, RoutingTableEntry& out) const;"
        new_p = ("bool SelectBestAlternate(Ipv4Address dst, RoutingTableEntry& out,\n"
                 "                             const RoutingTable* mainTable = nullptr) const;")
        if old_p in c:
            c = c.replace(old_p, new_p, 1)

    with open(h, "w") as f:
        f.write(c)
    print(f"  {label} OK")
    return True


def patch_mt_impl(module):
    """Add implementation of mainTable validation in GetRoutes/SelectProbabilistic."""
    cc = os.path.join(NS3, f"src/{module}/model/{module}-multipath-table.cc")
    label = f"[{module}-mt.cc]"
    if not os.path.exists(cc):
        return False
    if not os.path.exists(cc + ".bak-fix2"):
        shutil.copy(cc, cc + ".bak-fix2")
    with open(cc) as f:
        c = f.read()
    if "Fix Level 2: validate by mainTable" in c:
        print(f"  {label} already applied")
        return True

    # Modify GetRoutes signature in .cc and add validation
    old_sig = ("uint32_t\n"
               f"MultipathTable::GetRoutes(Ipv4Address dst, std::vector<RoutingTableEntry>& routes) const")
    new_sig = ("uint32_t\n"
               f"MultipathTable::GetRoutes(Ipv4Address dst, std::vector<RoutingTableEntry>& routes,\n"
               f"                          const RoutingTable* mainTable) const")
    if old_sig not in c:
        print(f"  {label} ! GetRoutes def signature không match")
        return False
    c = c.replace(old_sig, new_sig, 1)

    # Modify the loop to also check mainTable
    old_loop = """    for (const auto& e : it->second)
    {
        // Fix Level 1: lifetime filter — bỏ qua alternates đã expired.
        // GetLifeTime() = (m_lifeTime - Simulator::Now()) → positive = còn hiệu lực.
        if (e.GetFlag() == VALID && e.GetLifeTime() > Time(0))
        {
            routes.push_back(e);
            ++added;
        }
    }"""
    new_loop = """    for (const auto& e : it->second)
    {
        // Fix Level 1: lifetime filter
        if (e.GetFlag() != VALID || e.GetLifeTime() <= Time(0))
        {
            continue;
        }
        // Fix Level 2: validate by mainTable — alt's nextHop phải còn 1-hop reachable
        // (tức có entry VALID trong mainTable) tại thời điểm SỬ DỤNG.
        if (mainTable != nullptr)
        {
            RoutingTableEntry nbr;
            if (!const_cast<RoutingTable*>(mainTable)->LookupRoute(e.GetNextHop(), nbr) ||
                nbr.GetFlag() != VALID)
            {
                continue;
            }
        }
        routes.push_back(e);
        ++added;
    }"""
    if old_loop not in c:
        print(f"  {label} ! GetRoutes loop pattern không match")
        return False
    c = c.replace(old_loop, new_loop, 1)

    # For pmaodv, modify SelectProbabilisticWithPrimary signature + propagate
    if module == "pmaodv":
        old = ("bool\n"
               "MultipathTable::SelectProbabilisticWithPrimary(const RoutingTableEntry& primary,\n"
               "                                               RoutingTableEntry& out)\n"
               "{")
        new = ("bool\n"
               "MultipathTable::SelectProbabilisticWithPrimary(const RoutingTableEntry& primary,\n"
               "                                               RoutingTableEntry& out,\n"
               "                                               const RoutingTable* mainTable)\n"
               "{")
        if old in c:
            c = c.replace(old, new, 1)
        # Propagate mainTable in body — find the GetRoutes call and add parameter
        old2 = "GetRoutes(dst, alts);"
        new2 = "GetRoutes(dst, alts, mainTable);"
        c = c.replace(old2, new2, 1)

    if module == "aomdv":
        old = ("bool\n"
               "MultipathTable::SelectBestAlternate(Ipv4Address dst, RoutingTableEntry& out) const\n"
               "{")
        new = ("bool\n"
               "MultipathTable::SelectBestAlternate(Ipv4Address dst, RoutingTableEntry& out,\n"
               "                                    const RoutingTable* mainTable) const\n"
               "{")
        if old in c:
            c = c.replace(old, new, 1)
        old2 = "GetRoutes(dst, routes);"
        new2 = "GetRoutes(dst, routes, mainTable);"
        c = c.replace(old2, new2, 1)

    with open(cc, "w") as f:
        f.write(c)
    print(f"  {label} OK")
    return True


def patch_routing_protocol(module):
    """Pass &m_routingTable when calling MultipathTable selection."""
    cc = os.path.join(NS3, f"src/{module}/model/{module}-routing-protocol.cc")
    label = f"[{module}-rp.cc]"
    if not os.path.exists(cc):
        return False
    if not os.path.exists(cc + ".bak-fix2"):
        shutil.copy(cc, cc + ".bak-fix2")
    with open(cc) as f:
        c = f.read()
    if "// Fix Level 2: pass &m_routingTable" in c:
        print(f"  {label} already applied")
        return True

    if module == "pmaodv":
        old = "m_multipathTable.SelectProbabilisticWithPrimary(rt, chosenRt);"
        new = ("// Fix Level 2: pass &m_routingTable để validate nextHop của alt\n"
               "        m_multipathTable.SelectProbabilisticWithPrimary(rt, chosenRt, &m_routingTable);")
        if old not in c:
            print(f"  {label} ! pattern không match")
            return False
        c = c.replace(old, new, 1)

    if module == "aomdv":
        old = "if (m_multipathTable.SelectBestAlternate(dst, alt))"
        new = ("// Fix Level 2: pass &m_routingTable để validate nextHop của alt\n"
               "        if (m_multipathTable.SelectBestAlternate(dst, alt, &m_routingTable))")
        if old not in c:
            print(f"  {label} ! pattern không match")
            return False
        c = c.replace(old, new, 1)

    with open(cc, "w") as f:
        f.write(c)
    print(f"  {label} OK")
    return True


def main():
    print("=" * 60)
    print(" Fix Level 2 — Validate alt's nextHop at use time")
    print("=" * 60)

    total = 0
    passed = 0
    for module in ("pmaodv", "aomdv"):
        print(f"\n[{module}]")
        for fn in (patch_mt_header, patch_mt_impl, patch_routing_protocol):
            total += 1
            if fn(module):
                passed += 1

    print()
    print(f"Patched {passed}/{total} sections")
    if passed == total:
        print("\nNext: ./ns3 build")
    else:
        print("\nMột số patch fail. Restore từ .bak-fix2 nếu cần.")
        sys.exit(1)


if __name__ == "__main__":
    main()
