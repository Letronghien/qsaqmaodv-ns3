#!/usr/bin/env python3
"""
Fix Level 1 — Validate alternates by lifetime + extend alternate lifetime.

Bug 2 (stale alternates):
  MultipathTable lưu copy RoutingTableEntry tại thời điểm AddRoute.
  Lifetime field trong copy không update sau khi added → tích lũy stale alts.
  Khi SelectProbabilistic/SelectBestAlternate pick stale alt → packet drop.

Fix Level 1 áp dụng 3 thay đổi:
  (a) MultipathTable::GetRoutes() filter: chỉ trả về alts có
      flag==VALID VÀ GetLifeTime() > 0 (chưa expired).
  (b) RecvRequest add alternate với lifetime = m_activeRouteTimeout (~3s)
      thay vì lifetime ngắn từ RREQ formula. Cho window load-balancing dài hơn.
  (c) Thêm #include "ns3/simulator.h" vào multipath-table.cc nếu thiếu.

Apply cho cả pmaodv và aomdv modules.
"""

import os
import shutil
import sys

NS3 = os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40")


def patch_multipath_table(module):
    """Patch (a) + (c): GetRoutes filter by lifetime."""
    cc = os.path.join(NS3, f"src/{module}/model/{module}-multipath-table.cc")
    label = f"[{module}-mt]"
    if not os.path.exists(cc):
        print(f"  {label} SKIP (not found): {cc}")
        return False

    if not os.path.exists(cc + ".bak-fix1"):
        shutil.copy(cc, cc + ".bak-fix1")

    with open(cc) as f:
        c = f.read()

    if "Fix Level 1: lifetime filter" in c:
        print(f"  {label} already applied, skip")
        return True

    # (c) Add #include simulator.h
    if '#include "ns3/simulator.h"' not in c:
        c = c.replace(
            '#include "ns3/log.h"',
            '#include "ns3/log.h"\n#include "ns3/simulator.h"',
            1,
        )

    # (a) Patch GetRoutes
    old = """    for (const auto& e : it->second)
    {
        if (e.GetFlag() == VALID)
        {
            routes.push_back(e);
            ++added;
        }
    }"""
    new = """    for (const auto& e : it->second)
    {
        // Fix Level 1: lifetime filter — bỏ qua alternates đã expired.
        // GetLifeTime() = (m_lifeTime - Simulator::Now()) → positive = còn hiệu lực.
        if (e.GetFlag() == VALID && e.GetLifeTime() > Time(0))
        {
            routes.push_back(e);
            ++added;
        }
    }"""
    if old not in c:
        print(f"  {label} ! GetRoutes pattern not found")
        return False
    c = c.replace(old, new, 1)

    with open(cc, "w") as f:
        f.write(c)
    print(f"  {label} OK — lifetime filter + simulator.h include")
    return True


def patch_routing_protocol(module):
    """Patch (b): extend alternate lifetime in RecvRequest."""
    cc = os.path.join(NS3, f"src/{module}/model/{module}-routing-protocol.cc")
    label = f"[{module}-rp]"
    if not os.path.exists(cc):
        print(f"  {label} SKIP (not found): {cc}")
        return False

    if not os.path.exists(cc + ".bak-fix1"):
        shutil.copy(cc, cc + ".bak-fix1")

    with open(cc) as f:
        c = f.read()

    if "Fix Level 1: extended alt lifetime" in c:
        print(f"  {label} already applied, skip")
        return True

    old = """            uint8_t altHop = rreqHeader.GetHopCount() + 1;
            Ptr<NetDevice> dev =
                m_ipv4->GetNetDevice(m_ipv4->GetInterfaceForAddress(receiver));
            RoutingTableEntry alt(
                /*dev=*/dev,
                /*dst=*/origin,
                /*vSeqNo=*/true,
                /*seqNo=*/rreqHeader.GetOriginSeqno(),
                /*iface=*/m_ipv4->GetAddress(m_ipv4->GetInterfaceForAddress(receiver), 0),
                /*hops=*/altHop,
                /*nextHop=*/src,
                /*lifetime=*/Time((2 * m_netTraversalTime - 2 * altHop * m_nodeTraversalTime)));"""

    new = """            uint8_t altHop = rreqHeader.GetHopCount() + 1;
            Ptr<NetDevice> dev =
                m_ipv4->GetNetDevice(m_ipv4->GetInterfaceForAddress(receiver));
            // Fix Level 1: extended alt lifetime — dùng m_activeRouteTimeout (~3s)
            // thay vì RREQ-derived lifetime ngắn → window load-balance đủ dài.
            RoutingTableEntry alt(
                /*dev=*/dev,
                /*dst=*/origin,
                /*vSeqNo=*/true,
                /*seqNo=*/rreqHeader.GetOriginSeqno(),
                /*iface=*/m_ipv4->GetAddress(m_ipv4->GetInterfaceForAddress(receiver), 0),
                /*hops=*/altHop,
                /*nextHop=*/src,
                /*lifetime=*/m_activeRouteTimeout);"""

    if old not in c:
        print(f"  {label} ! RecvRequest alt-add pattern not found")
        return False
    c = c.replace(old, new, 1)

    with open(cc, "w") as f:
        f.write(c)
    print(f"  {label} OK — alt lifetime → m_activeRouteTimeout")
    return True


def main():
    print("=" * 60)
    print(" Fix Level 1 — Validate alternates by lifetime")
    print("=" * 60)

    total = 0
    passed = 0
    for module in ("pmaodv", "aomdv"):
        print(f"\n[{module}]")
        for fn in (patch_multipath_table, patch_routing_protocol):
            total += 1
            if fn(module):
                passed += 1

    print()
    print("=" * 60)
    print(f" Patched {passed}/{total} files")
    print("=" * 60)

    if passed == total:
        print("\nNext: ./ns3 build")
        print("Then re-run a quick test:")
        print("  bash run-final-4protocols.sh quick")
    else:
        print("\nMột số patch không apply — kiểm tra log ở trên.")
        sys.exit(1)


if __name__ == "__main__":
    main()
