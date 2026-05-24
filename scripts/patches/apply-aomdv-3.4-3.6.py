#!/usr/bin/env python3
"""
AOMDV Phase 3.4 + 3.5 + 3.6:
  3.4: Modify RouteOutput → fallback to alternate khi primary invalid
       (KHÔNG probabilistic như PMAODV — AOMDV dùng primary-first + fallback)
  3.5: Modify RecvRequest → store alternate reverse routes từ duplicate RREQ
  3.6: Modify RecvReply  → store alternate forward routes từ duplicate RREP
"""

import os
import shutil
import sys

NS3 = os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40")
CC = os.path.join(NS3, "src/aomdv/model/aomdv-routing-protocol.cc")

shutil.copy(CC, CC + ".bak-3.4-3.6")
with open(CC) as f:
    c = f.read()


# ============================================================
# Phase 3.4: RouteOutput — fallback to alternate khi primary fail
# ============================================================
print("=== Phase 3.4: RouteOutput fallback ===")

if "AOMDV: fallback to alternate route" in c:
    print("  Already applied, skip.")
else:
    # AODV: when LookupValidRoute fails → goes to LoopbackRoute (triggers discovery)
    # AOMDV: when primary fails → try alternate first, then fallback to discovery
    old_ro = """    // Valid route not found, in this case we return loopback.
    // Actual route request will be deferred until packet will be fully formed,
    // routed to loopback, received from loopback and passed to RouteInput (see below)
    uint32_t iif = (oif ? m_ipv4->GetInterfaceForDevice(oif) : -1);"""

    new_ro = """    // AOMDV: fallback to alternate route trong MultipathTable trước khi discovery.
    {
        RoutingTableEntry alt;
        if (m_multipathTable.SelectBestAlternate(dst, alt))
        {
            Ptr<Ipv4Route> altRoute = alt.GetRoute();
            if (altRoute && (!oif || altRoute->GetOutputDevice() == oif))
            {
                NS_LOG_DEBUG("AOMDV: primary down, dùng alternate via "
                             << alt.GetNextHop() << " HC=" << (uint32_t)alt.GetHop());
                // Promote alternate lên primary cho subsequent calls
                m_routingTable.AddRoute(alt);
                m_multipathTable.DeleteRoute(dst, alt.GetNextHop());
                UpdateRouteLifeTime(dst, m_activeRouteTimeout);
                UpdateRouteLifeTime(altRoute->GetGateway(), m_activeRouteTimeout);
                return altRoute;
            }
        }
    }

    // Valid route not found, in this case we return loopback.
    // Actual route request will be deferred until packet will be fully formed,
    // routed to loopback, received from loopback and passed to RouteInput (see below)
    uint32_t iif = (oif ? m_ipv4->GetInterfaceForDevice(oif) : -1);"""

    if old_ro not in c:
        print("  ERROR: Pattern RouteOutput loopback fallback không tìm thấy.")
        sys.exit(1)
    c = c.replace(old_ro, new_ro, 1)
    print("  + RouteOutput fallback to alternate OK")


# ============================================================
# Phase 3.5: RecvRequest — store alternate reverse route từ duplicate RREQ
# ============================================================
print("=== Phase 3.5: RecvRequest alternate reverse routes ===")

if "AOMDV: store alternate reverse route" in c:
    print("  Already applied, skip.")
else:
    old_rq = """    if (m_rreqIdCache.IsDuplicate(origin, id))
    {
        NS_LOG_DEBUG("Ignoring RREQ due to duplicate");
        return;
    }"""

    new_rq = """    if (m_rreqIdCache.IsDuplicate(origin, id))
    {
        // AOMDV: store alternate reverse route từ duplicate RREQ (link-disjoint dedup).
        if (!m_multipathTable.IsFull(origin))
        {
            uint8_t altHop = rreqHeader.GetHopCount() + 1;
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
                /*lifetime=*/Time((2 * m_netTraversalTime - 2 * altHop * m_nodeTraversalTime)));
            alt.SetFlag(VALID);
            m_multipathTable.AddRoute(alt);
        }
        NS_LOG_DEBUG("Ignoring RREQ due to duplicate (alt path saved if room)");
        return;
    }"""

    if old_rq not in c:
        print("  ERROR: Pattern duplicate-RREQ check không tìm thấy.")
        sys.exit(1)
    c = c.replace(old_rq, new_rq, 1)
    print("  + RecvRequest alternate reverse routes OK")


# ============================================================
# Phase 3.6: RecvReply — store alternate forward route từ duplicate RREP
# ============================================================
print("=== Phase 3.6: RecvReply alternate forward routes ===")

if "AOMDV: store alternate forward route" in c:
    print("  Already applied, skip.")
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

    // AOMDV: store alternate forward route nếu next-hop khác primary.
    // Different sender → different forward path → load-balancing/fallback candidate.
    {
        RoutingTableEntry curPrim;
        if (m_routingTable.LookupRoute(dst, curPrim) &&
            curPrim.GetNextHop() != newEntry.GetNextHop())
        {
            m_multipathTable.AddRoute(newEntry);
        }
    }

    // Acknowledge receipt of the RREP by sending a RREP-ACK message back"""

    if old_rp not in c:
        print("  ERROR: Pattern AddRoute(newEntry) trong RecvReply không tìm thấy.")
        sys.exit(1)
    c = c.replace(old_rp, new_rp, 1)
    print("  + RecvReply alternate forward routes OK")


with open(CC, "w") as f:
    f.write(c)

print()
print("Done. Run: ./ns3 build")
