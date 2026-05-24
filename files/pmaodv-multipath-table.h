/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/**
 * MultipathTable for PMAODV (Probabilistic Multipath AODV).
 *
 * Stores ALTERNATE routes alongside the primary route in PMAODV's main routing table.
 * Each destination can have up to MaxPaths alternate (next-hop, hop-count) entries.
 *
 * Selection formula (per paper, Section 3.2):
 *
 *               (1 / HC_i)
 *      p_i = ─────────────────────────
 *            Σ_{k ∈ available} (1 / HC_k)
 *
 * Routes with smaller HC are preferred but longer routes still get a chance,
 * giving load-balancing across multiple paths.
 */

#ifndef PMAODV_MULTIPATH_TABLE_H
#define PMAODV_MULTIPATH_TABLE_H

#include "pmaodv-rtable.h"

#include "ns3/ipv4-address.h"
#include "ns3/random-variable-stream.h"

#include <map>
#include <vector>

namespace ns3
{
namespace pmaodv
{

/**
 * \brief Stores alternate routes per destination for PMAODV multipath.
 */
class MultipathTable
{
  public:
    MultipathTable(uint32_t maxPaths = 3);

    void SetMaxPaths(uint32_t mp);
    uint32_t GetMaxPaths() const;

    /**
     * Try to add an alternate route for rt.GetDestination().
     * Rules:
     *   - Reject if (dst, nextHop) duplicate already in table.
     *   - If size < MaxPaths: append.
     *   - Else if rt.HopCount < worst route's HopCount: evict worst, insert rt.
     *   - Else: reject.
     * \return true if added; false if rejected.
     */
    bool AddRoute(const RoutingTableEntry& rt);

    /**
     * Fetch all VALID alternate routes for `dst`.
     * Note: routes with state INVALID/IN_SEARCH are skipped (only VALID returned).
     * \return number of valid routes added to `routes`.
     */
    uint32_t GetRoutes(Ipv4Address dst, std::vector<RoutingTableEntry>& routes) const;

    /**
     * Pick one route probabilistically using paper formula
     *     p_i = (1/HC_i) / Σ_k (1/HC_k)
     * The caller is expected to combine this with the PRIMARY route from
     * the main RoutingTable; this function only operates on alternates.
     *
     * \return true if at least one valid alternate exists; `out` filled.
     */
    bool SelectProbabilistic(Ipv4Address dst, RoutingTableEntry& out);

    /**
     * Variant that includes a primary route alongside alternates and
     * selects probabilistically from the combined set.
     * Use this from RouteOutput in pmaodv-routing-protocol.cc.
     */
    bool SelectProbabilisticWithPrimary(const RoutingTableEntry& primary,
                                        RoutingTableEntry& out);

    /**
     * Remove all alternate routes to `dst`. Called when route invalidated
     * or during link failure handling.
     */
    void DeleteRoutes(Ipv4Address dst);

    /**
     * Remove a specific (dst, nextHop) alternate.
     */
    void DeleteRoute(Ipv4Address dst, Ipv4Address nextHop);

    /**
     * Number of (dst, nextHop) pairs stored across all destinations.
     */
    uint32_t Size() const;

    /**
     * Total alternates currently stored for a destination.
     */
    uint32_t CountFor(Ipv4Address dst) const;

    /**
     * Whether table has reached MaxPaths capacity for a destination.
     * Useful to decide whether to keep processing duplicate RREQs.
     */
    bool IsFull(Ipv4Address dst) const;

    /**
     * Clear all entries.
     */
    void Clear();

    /**
     * Debug print.
     */
    void Print(std::ostream& os) const;

  private:
    /**
     * \return iterator to entry with the highest hop count for `dst`,
     *         or end() if no entries.
     */
    std::vector<RoutingTableEntry>::iterator FindWorst(
        std::vector<RoutingTableEntry>& vec);

    /// Map: destination -> list of alternate routes (excluding primary).
    std::map<Ipv4Address, std::vector<RoutingTableEntry>> m_routes;

    uint32_t m_maxPaths;

    /// RNG for probabilistic selection.
    Ptr<UniformRandomVariable> m_uniform;
};

} // namespace pmaodv
} // namespace ns3

#endif /* PMAODV_MULTIPATH_TABLE_H */
