/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */

#include "aomdv-multipath-table.h"

#include "ns3/log.h"

#include <algorithm>
#include <numeric>

namespace ns3
{

NS_LOG_COMPONENT_DEFINE("AomdvMultipathTable");

namespace aomdv
{

MultipathTable::MultipathTable(uint32_t maxPaths)
    : m_maxPaths(maxPaths)
{
}

void
MultipathTable::SetMaxPaths(uint32_t mp)
{
    NS_ASSERT_MSG(mp >= 1, "MaxPaths must be >= 1");
    m_maxPaths = mp;
}

uint32_t
MultipathTable::GetMaxPaths() const
{
    return m_maxPaths;
}

std::vector<RoutingTableEntry>::iterator
MultipathTable::FindWorst(std::vector<RoutingTableEntry>& vec)
{
    if (vec.empty())
    {
        return vec.end();
    }
    auto worst = vec.begin();
    for (auto it = vec.begin() + 1; it != vec.end(); ++it)
    {
        if (it->GetHop() > worst->GetHop())
        {
            worst = it;
        }
    }
    return worst;
}

bool
MultipathTable::AddRoute(const RoutingTableEntry& rt)
{
    Ipv4Address dst = rt.GetDestination();
    Ipv4Address nh = rt.GetNextHop();

    if (m_maxPaths <= 1)
    {
        return false;
    }

    auto& vec = m_routes[dst];

    // Reject duplicate (dst, nextHop) -- link-disjoint check
    for (auto& existing : vec)
    {
        if (existing.GetNextHop() == nh)
        {
            return false;
        }
    }

    uint32_t altCapacity = m_maxPaths - 1;

    if (vec.size() < altCapacity)
    {
        vec.push_back(rt);
        return true;
    }

    auto worst = FindWorst(vec);
    if (worst != vec.end() && rt.GetHop() < worst->GetHop())
    {
        *worst = rt;
        return true;
    }

    return false;
}

uint32_t
MultipathTable::GetRoutes(Ipv4Address dst, std::vector<RoutingTableEntry>& routes) const
{
    auto it = m_routes.find(dst);
    if (it == m_routes.end())
    {
        return 0;
    }

    uint32_t added = 0;
    for (const auto& e : it->second)
    {
        if (e.GetFlag() == VALID)
        {
            routes.push_back(e);
            ++added;
        }
    }
    return added;
}

bool
MultipathTable::SelectBestAlternate(Ipv4Address dst, RoutingTableEntry& out) const
{
    std::vector<RoutingTableEntry> routes;
    GetRoutes(dst, routes);
    if (routes.empty())
    {
        return false;
    }

    // Best = lowest hop count
    auto best = routes.begin();
    for (auto it = routes.begin() + 1; it != routes.end(); ++it)
    {
        if (it->GetHop() < best->GetHop())
        {
            best = it;
        }
    }
    out = *best;
    return true;
}

void
MultipathTable::DeleteRoutes(Ipv4Address dst)
{
    m_routes.erase(dst);
}

void
MultipathTable::DeleteRoute(Ipv4Address dst, Ipv4Address nextHop)
{
    auto it = m_routes.find(dst);
    if (it == m_routes.end())
    {
        return;
    }
    auto& vec = it->second;
    vec.erase(std::remove_if(vec.begin(), vec.end(),
                             [&](const RoutingTableEntry& e) {
                                 return e.GetNextHop() == nextHop;
                             }),
              vec.end());
    if (vec.empty())
    {
        m_routes.erase(it);
    }
}

uint32_t
MultipathTable::Size() const
{
    return std::accumulate(m_routes.begin(), m_routes.end(), uint32_t{0},
                           [](uint32_t a, const auto& kv) {
                               return a + kv.second.size();
                           });
}

uint32_t
MultipathTable::CountFor(Ipv4Address dst) const
{
    auto it = m_routes.find(dst);
    return (it == m_routes.end()) ? 0 : static_cast<uint32_t>(it->second.size());
}

bool
MultipathTable::IsFull(Ipv4Address dst) const
{
    if (m_maxPaths <= 1)
    {
        return true;
    }
    return CountFor(dst) >= (m_maxPaths - 1);
}

void
MultipathTable::Clear()
{
    m_routes.clear();
}

void
MultipathTable::Print(std::ostream& os) const
{
    os << "AOMDV MultipathTable (" << Size() << " entries, MaxPaths=" << m_maxPaths << "):\n";
    for (const auto& kv : m_routes)
    {
        os << "  dst=" << kv.first << " alternates=" << kv.second.size() << "\n";
        for (const auto& e : kv.second)
        {
            os << "    via " << e.GetNextHop()
               << " HC=" << (uint32_t)e.GetHop() << "\n";
        }
    }
}

} // namespace aomdv
} // namespace ns3
