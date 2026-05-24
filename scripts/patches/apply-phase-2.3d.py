#!/usr/bin/env python3
"""
Phase 2.3.d — Modify RecvReply để store alternate FORWARD route từ duplicate RREP.
              Đồng thời dedupe nextHop trong SelectProbabilisticWithPrimary.

Logic:
  Sau khi AODV gốc đã update/add primary forward route:
    Lookup primary hiện tại. Nếu next-hop khác newEntry's next-hop
    → add newEntry vào m_multipathTable làm alternate.

Sau Phase 2.3.d, source và intermediate nodes đều có nhiều forward routes
→ probabilistic forwarding thực sự active.
"""

import os
import shutil
import sys

NS3 = os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40")
CC_RP = os.path.join(NS3, "src/pmaodv/model/pmaodv-routing-protocol.cc")
CC_MT = os.path.join(NS3, "src/pmaodv/model/pmaodv-multipath-table.cc")

shutil.copy(CC_RP, CC_RP + ".bak-23d")
shutil.copy(CC_MT, CC_MT + ".bak-23d")

# === 1. Patch RecvReply trong pmaodv-routing-protocol.cc ===
with open(CC_RP) as f:
    rp = f.read()

if "PMAODV: store alternate forward route" in rp:
    print("[RecvReply] Already applied.")
else:
    old_rp = """    else
    {
        // The forward route for this destination is created if it does not already exist.
        NS_LOG_LOGIC("add new route");
        m_routingTable.AddRoute(newEntry);
    }
    // Acknowledge receipt of the RREP by sending a RREP-ACK message back"""

    new_rp = """    else
    {
        // The forward route for this destination is created if it does not already exist.
        NS_LOG_LOGIC("add new route");
        m_routingTable.AddRoute(newEntry);
    }

    // PMAODV: store alternate forward route if next-hop differs from primary.
    // Cùng dst, qua sender khác → đường khác → load-balancing candidate.
    {
        RoutingTableEntry curPrim;
        if (m_routingTable.LookupRoute(dst, curPrim) &&
            curPrim.GetNextHop() != newEntry.GetNextHop())
        {
            m_multipathTable.AddRoute(newEntry);
        }
    }

    // Acknowledge receipt of the RREP by sending a RREP-ACK message back"""

    if old_rp not in rp:
        print("ERROR: Không tìm thấy pattern AddRoute(newEntry) trong RecvReply.")
        sys.exit(1)

    rp = rp.replace(old_rp, new_rp, 1)
    with open(CC_RP, "w") as f:
        f.write(rp)
    print("[RecvReply] Patched: alternate forward route logic added.")


# === 2. Patch SelectProbabilisticWithPrimary để dedupe nextHop ===
with open(CC_MT) as f:
    mt = f.read()

if "PMAODV: skip alternates with same nextHop as primary" in mt:
    print("[MultipathTable] Already applied.")
else:
    # Tìm chỗ build candidate list (push_back primary, then GetRoutes)
    old_mt = """    // Build candidate list: primary + valid alternates
    std::vector<RoutingTableEntry> cands;
    cands.push_back(primary);
    GetRoutes(dst, cands);"""

    new_mt = """    // Build candidate list: primary + valid alternates
    // PMAODV: skip alternates with same nextHop as primary (edge case khi primary
    // được update sau khi alternate đã thêm).
    std::vector<RoutingTableEntry> cands;
    cands.push_back(primary);
    std::vector<RoutingTableEntry> alts;
    GetRoutes(dst, alts);
    for (const auto& a : alts)
    {
        if (a.GetNextHop() != primary.GetNextHop())
        {
            cands.push_back(a);
        }
    }"""

    if old_mt not in mt:
        print("ERROR: Không tìm thấy pattern build candidate list trong MultipathTable.")
        sys.exit(1)

    mt = mt.replace(old_mt, new_mt, 1)
    with open(CC_MT, "w") as f:
        f.write(mt)
    print("[MultipathTable] Patched: dedupe nextHop in candidate list.")


print("\nDone. Run: ./ns3 build")
