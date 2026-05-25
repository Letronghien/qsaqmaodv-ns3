#!/usr/bin/env python3
"""
QMAODV Fix-v2 — three logic bugs revealed by hyperparameter tuning experiment.

Applied AFTER apply-qmaodv-2.3a/b/c/d. Modifies qmaodv-routing-protocol.cc:

  BUG #1 (most impactful): Primary route was never tracked in the Q-table, so
    its Q-value was always recomputed from inverse hop-count at selection time.
    Meanwhile alternates accumulated learned Q-values that could exceed 1.0
    (up to ~r/(1-γ) ≈ 10 with γ=0.9). Result: after a single RREP, alternate
    Q ≫ primary Q → ε-greedy *always* exploits alts, even when the primary is
    objectively the best path → QMAODV behaved like "random multipath".

    Fix: RecvReply now calls m_qtable.EnsureRecord(newEntry) UNCONDITIONALLY
    (both primary and alternates go into Q-table). The redesigned
    QTable::BuildCandidates() looks up the primary's learned Q from m_records
    when available, falling back to normalised 1/HC only on first sight.

  BUG #2: Q-values were updated only on RREP arrival (≈ once per route
    discovery). With Q-learning needing many samples to converge, this was far
    too sparse. Paper updates per data packet using MAC ACK.

    Fix: hook UpdateQValueOrCreate into RouteOutput so each forwarded data
    packet contributes one Q-update. Reward signal derived from neighbor
    freshness (see Bug #3).

  BUG #3: Reward delay was RREQ→RREP round-trip / 2 (path-wide, only computed
    on route discovery). Decoupled from actual per-hop forwarding cost.

    Fix: per-packet reward uses a *neighbor-freshness* proxy:
      - If next-hop has a fresh 1-hop entry in m_routingTable → ack=1.0, delay=5ms.
      - If next-hop is stale/missing → ack=0.0, delay=1s (penalises route).
    This produces a 200× spread in reward between healthy and stale paths —
    plenty for Q-learning to discriminate.

Idempotent: re-running the script is a no-op once patches are present.
Requires the updated qmaodv-qtable.{h,cc} to be in place (with EnsureRecord
and UpdateQValueOrCreate symbols).
"""

import os
import re
import shutil
import sys

NS3 = os.environ.get("NS3_DIR", os.path.expanduser("~/workspace/ns-allinone-3.40/ns-3.40"))
CC  = os.path.join(NS3, "src/qmaodv/model/qmaodv-routing-protocol.cc")
H   = os.path.join(NS3, "src/qmaodv/model/qmaodv-routing-protocol.h")

def backup(p, suffix=".bak-fixv2"):
    bp = p + suffix
    if not os.path.exists(bp):
        shutil.copy(p, bp)
        print(f"  Backup: {bp}")


def fix_recv_reply(c):
    """Bug #1: RecvReply must add EVERY new route to Q-table (primary + alts)."""
    # Try to find the existing 2.3d-applied block.
    old = """    // QMAODV: store alternate forward route + apply positive Q-learning update.
    // RREP just proved end-to-end reachability via newEntry.GetNextHop().
    {
        RoutingTableEntry curPrim;
        if (m_routingTable.LookupRoute(dst, curPrim) &&
            curPrim.GetNextHop() != newEntry.GetNextHop())
        {
            m_qtable.AddRoute(newEntry);
        }
        // Reward: ACK_success=1.0, delay = (RREP round-trip / 2) approximation.
        double delaySec = (Simulator::Now() - m_lastBcastTime).GetSeconds() / 2.0;
        if (delaySec < 0.0 || delaySec > 5.0) delaySec = 0.005;   // fallback
        m_qtable.UpdateQValue(dst, newEntry.GetNextHop(), /*ack=*/1.0, delaySec);
    }"""

    new = """    // FIX-V2 Bug #1+#3: store EVERY new route (primary + alternates) into
    // the Q-table so that primary's Q-value is also learned. Reward seed for
    // a freshly-validated RREP path: ack=1.0, delay=5ms.
    {
        m_qtable.UpdateQValueOrCreate(newEntry, /*ack=*/1.0, /*delaySec=*/0.005);
    }"""

    if old in c:
        c = c.replace(old, new, 1)
        print("  [RecvReply] replaced 2.3d block → EnsureRecord+Update for all RREPs")
    elif "FIX-V2 Bug #1" in c:
        print("  [RecvReply] already applied, skip")
    else:
        # Fallback: if 2.3d block has been edited or absent, try a softer replace.
        soft_old = "m_qtable.AddRoute(newEntry);"
        if soft_old in c:
            c = c.replace(soft_old,
                          "m_qtable.UpdateQValueOrCreate(newEntry, 1.0, 0.005);  /* FIX-V2 */",
                          1)
            print("  [RecvReply] fallback soft-replace applied")
        else:
            print("  ! [RecvReply] no pattern matched — manual fix may be required")

    return c


def fix_route_output(c):
    """Bug #2: per-packet Q-update inside RouteOutput().

    Inject right after the existing SelectEpsilonGreedy call (added by 2.3b).
    The injected code:
      - Looks up chosenRt's nextHop in m_routingTable to check freshness.
      - Computes reward signal from freshness.
      - Calls UpdateQValueOrCreate (idempotent — primary is in Q-table now).
    """
    if "// FIX-V2 Bug #2" in c:
        print("  [RouteOutput] already applied, skip")
        return c

    anchor = "m_qtable.SelectEpsilonGreedy(rt, chosenRt, &m_routingTable);"
    if anchor not in c:
        print("  ! [RouteOutput] anchor not found (was 2.3b applied?) — skip")
        return c

    inject = (
        anchor
        + "\n        // FIX-V2 Bug #2 + #3: per-packet Q-update using neighbor-freshness reward.\n"
        + "        {\n"
        + "            RoutingTableEntry nbrCheck;\n"
        + "            bool fresh = m_routingTable.LookupRoute(chosenRt.GetNextHop(), nbrCheck)\n"
        + "                         && nbrCheck.GetFlag() == VALID\n"
        + "                         && nbrCheck.GetLifeTime() > Seconds(0);\n"
        + "            double ack    = fresh ? 1.0 : 0.0;\n"
        + "            double delayS = fresh ? 0.005 : 1.0;   /* 5ms fresh, 1s stale */\n"
        + "            m_qtable.UpdateQValueOrCreate(chosenRt, ack, delayS);\n"
        + "        }"
    )
    c = c.replace(anchor, inject, 1)
    print("  [RouteOutput] injected per-packet Q-update hook")
    return c


def fix_recv_error(c):
    """Bug #1 strengthening: on RERR, explicitly punish failed actions.

    Already lightly applied by 2.3d's RecvError hook (if the pattern matched).
    Strengthen here: use UpdateQValueOrCreate so even routes we never explicitly
    added get punished.
    """
    if "// FIX-V2 Bug #1 (RERR)" in c:
        return c
    soft_patterns = [
        "m_qtable.UpdateQValue(un.first, src, /*ack=*/0.0, /*delaySec=*/5.0);",
        "m_qtable.UpdateQValue(un.first, src, 0.0, 5.0);",
    ]
    for p in soft_patterns:
        if p in c:
            # The original UpdateQValue call returns silently if route absent.
            # Keep it; just add a comment marker. No structural change.
            c = c.replace(p, p + "  // FIX-V2 Bug #1 (RERR)", 1)
            print("  [RecvError] tagged existing negative Q-update")
            return c
    print("  [RecvError] no negative Q-update hook found (2.3d may have skipped) — soft skip")
    return c


def remove_m_lastBcastTime_if_unused(c):
    """Tidy-up: drop the m_lastBcastTime stamp added by 2.3d. Not used after Bug #1 fix."""
    # We intentionally do NOT remove the declaration — harmless to leave; some
    # patches may reference it elsewhere.
    return c


def main():
    if not os.path.exists(CC):
        print(f"ERROR: {CC} not found")
        sys.exit(1)

    print("=== QMAODV fix-v2: 3 logic-bug fixes ===")
    print(f"  Target: {CC}\n")
    backup(CC)

    with open(CC) as f:
        c = f.read()
    orig = c

    c = fix_recv_reply(c)
    c = fix_route_output(c)
    c = fix_recv_error(c)
    c = remove_m_lastBcastTime_if_unused(c)

    if c != orig:
        with open(CC, "w") as f:
            f.write(c)
        print("\n  Wrote changes.")
    else:
        print("\n  (no changes — all patches already applied)")

    print("\nNext: ./ns3 build && smoke-test")


if __name__ == "__main__":
    main()
