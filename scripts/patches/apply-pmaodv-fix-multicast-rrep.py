#!/usr/bin/env python3
"""
PMAODV Multicast-RREP Fix
=========================

The PMAODV paper (IAAA 2025, Section 3.1 + Fig. 2) explicitly states that
the destination node should respond with **multiple RREPs** — one per
established reverse path — so that the source ends up with multiple
distinct forward routes.

The current ns-3 implementation (apply-phase-2.3c.py) drops every duplicate
RREQ at every node, INCLUDING at the destination. This means:

  - Multiple reverse paths ARE stored at intermediate nodes ✓
  - But the destination only sends ONE RREP (via the first-arrived RREQ)
  - The source therefore ends up with just ONE forward route
  - Forward multipath is effectively empty → PMAODV ≈ AODV in practice

Empirical confirmation: in our 1950-run big-batch, PMAODV's PDR was within
±1.5 % of AODV across every scenario — consistent with the missing
multicast.

This patch modifies the duplicate-RREQ branch in pmaodv-routing-protocol.cc:
when the duplicate RREQ arrives AT the destination, the node also sends an
additional RREP back along the freshly-stored alternate reverse path. Other
nodes (non-destination) still simply store the alt and drop the RREQ — no
broadcast storm.

After applying this fix:
  - Source receives ≥1 RREP per (origin, dst) discovery — typically K_paths
  - Forward multipath table fills up → probabilistic selection works as
    described in the paper
  - PDR should improve relative to AODV (paper's claim)

The patch is idempotent and backs up the .cc file to .bak-multicast-rrep.

Usage:
  NS3_DIR=~/ns-allinone-3.40/ns-3.40 python3 apply-pmaodv-fix-multicast-rrep.py
"""

import os
import re
import shutil
import sys

NS3 = os.environ.get(
    "NS3_DIR",
    os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40"),
)
CC = os.path.join(NS3, "src/pmaodv/model/pmaodv-routing-protocol.cc")


def backup(p, suffix=".bak-multicast-rrep"):
    bp = p + suffix
    if not os.path.exists(bp):
        shutil.copy(p, bp)
        print(f"  Backup: {bp}")


def patch():
    if not os.path.exists(CC):
        print(f"ERROR: {CC} not found"); sys.exit(1)
    backup(CC)

    with open(CC) as f:
        c = f.read()

    if "PMAODV-MULTICAST-FIX" in c:
        print("Already applied, skip.")
        return

    # The 2.3c block we need to wrap. Use a flexible regex because the
    # exact whitespace may vary.
    old = """    if (m_rreqIdCache.IsDuplicate(origin, id))
    {
        // PMAODV: store alternate reverse route from duplicate RREQ."""

    new = """    if (m_rreqIdCache.IsDuplicate(origin, id))
    {
        // PMAODV-MULTICAST-FIX: store alt reverse + (if I am the destination)
        // send an additional RREP via the new reverse path so that the source
        // ends up with multiple forward routes (paper §3.1 + Fig. 2).
        // NB: only the destination sends extra RREPs; intermediate nodes still
        // just store and drop, so no broadcast storm.
        // PMAODV: store alternate reverse route from duplicate RREQ."""

    if old not in c:
        print("ERROR: anchor not found — did you apply apply-phase-2.3c.py first?")
        sys.exit(1)
    c = c.replace(old, new, 1)
    print("  + comment marker placed")

    # Now inject the SendReply call right after the AddRoute(alt) and before
    # the NS_LOG_DEBUG/return that ends the duplicate branch.
    old_end = """            m_multipathTable.AddRoute(alt);
        }
        NS_LOG_DEBUG("Ignoring RREQ due to duplicate (alt path saved if room)");
        return;
    }"""

    new_end = """            m_multipathTable.AddRoute(alt);

            // PMAODV-MULTICAST-FIX: if this is the destination, fire an extra
            // RREP back along the new reverse path. The first RREP is already
            // out (from the original RREQ); each subsequent duplicate RREQ
            // produces one more RREP, giving the source K_paths forward routes.
            if (IsMyOwnAddress(rreqHeader.GetDst()))
            {
                SendReply(rreqHeader, alt);
            }
        }
        NS_LOG_DEBUG("Ignoring RREQ due to duplicate (alt path saved if room)");
        return;
    }"""

    if old_end not in c:
        # 2.3c may have used slightly different formatting; try a softer anchor.
        anchor = "m_multipathTable.AddRoute(alt);"
        if anchor in c and "PMAODV-MULTICAST-FIX: if this is the destination" not in c:
            inject = anchor + "\n\n" + (
                "            // PMAODV-MULTICAST-FIX: if this is the destination,\n"
                "            // send an extra RREP back along the new reverse path so\n"
                "            // that the source accumulates multiple forward routes\n"
                "            // (paper §3.1).\n"
                "            if (IsMyOwnAddress(rreqHeader.GetDst()))\n"
                "            {\n"
                "                SendReply(rreqHeader, alt);\n"
                "            }"
            )
            c = c.replace(anchor, inject, 1)
            print("  + injected SendReply via soft anchor (m_multipathTable.AddRoute)")
        else:
            print("ERROR: end anchor not found.")
            sys.exit(1)
    else:
        c = c.replace(old_end, new_end, 1)
        print("  + injected SendReply via exact anchor")

    with open(CC, "w") as f:
        f.write(c)
    print("\nPatch applied. Re-build:")
    print("  cd $NS3_DIR && ./ns3 build")


if __name__ == "__main__":
    patch()
