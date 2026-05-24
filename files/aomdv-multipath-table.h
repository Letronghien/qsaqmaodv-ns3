/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/**
 * MultipathTable for AOMDV (Ad-hoc On-demand Multipath Distance Vector).
 *
 * Stores ALTERNATE routes (link-disjoint qua nextHop dedup) alongside primary
 * route trong m_routingTable. Khác PMAODV ở selection strategy:
 *   - PMAODV: probabilistic p_i = (1/HC_i)/Σ(1/HC_k)
 *   - AOMDV:  best-first (lowest hop count) với fallback khi primary dead
 */

#ifndef AOMDV_MULTIPATH_TABLE_H
#define AOMDV_MULTIPATH_TABLE_H

#include "aomdv-rtable.h"

#include "ns3/ipv4-address.h"

#include <map>
#include <vector>

namespace ns3
{
namespace aomdv
{

/**
 * \brief Stores alternate routes per destination for AOMDV multipath fallback.
 */
class MultipathTable
{
  public:
    MultipathTable(uint32_t maxPaths = 3);

    void SetMaxPaths(uint32_t mp);
    uint32_t GetMaxPaths() const;

    /**
     * Try to add an alternate route for rt.GetDestination().
     * Reject if (dst, nextHop) duplicate (link-disjoint check).
     * If at capacity, replace worst (highest HC) if rt is better.
     */
    bool AddRoute(const RoutingTableEntry& rt);

    /**
     * Get all VALID alternate routes for `dst`.
     */
    uint32_t GetRoutes(Ipv4Address dst, std::vector<RoutingTableEntry>& routes) const;

    /**
     * Select best (lowest HC) valid alternate route.
     * Used as fallback khi primary route invalid.
     */
    bool SelectBestAlternate(Ipv4Address dst, RoutingTableEntry& out) const;

    /**
     * Remove all alternate routes to `dst`.
     */
    void DeleteRoutes(Ipv4Address dst);

    /**
     * Remove a specific (dst, nextHop) alternate.
     */
    void DeleteRoute(Ipv4Address dst, Ipv4Address nextHop);

    uint32_t Size() const;
    uint32_t CountFor(Ipv4Address dst) const;
    bool IsFull(Ipv4Address dst) const;
    void Clear();
    void Print(std::ostream& os) const;

  private:
    std::vector<RoutingTableEntry>::iterator FindWorst(
        std::vector<RoutingTableEntry>& vec);

    std::map<Ipv4Address, std::vector<RoutingTableEntry>> m_routes;
    uint32_t m_maxPaths;
};

} // namespace aomdv
} // namespace ns3

#endif /* AOMDV_MULTIPATH_TABLE_H */
