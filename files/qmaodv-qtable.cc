/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/**
 * QMAODV Q-table — implementation.
 * See qmaodv-qtable.h for the design discussion.
 */

#include "qmaodv-qtable.h"

#include "ns3/log.h"
#include "ns3/simulator.h"

#include <algorithm>
#include <cmath>
#include <numeric>

namespace ns3
{

NS_LOG_COMPONENT_DEFINE("QmaodvQTable");

namespace qmaodv
{

QTable::QTable(uint32_t maxPaths)
    : m_maxPaths(maxPaths),
      m_alpha(0.5),
      m_gamma(0.9),
      m_epsilon(0.5),
      m_epsilonMin(0.05),
      m_epsilonDecay(0.02),
      m_w1(0.6),
      m_w2(0.4)
{
    m_uniform = CreateObject<UniformRandomVariable>();
}

void
QTable::SetMaxPaths(uint32_t mp)
{
    NS_ASSERT_MSG(mp >= 1, "MaxPaths must be >= 1");
    m_maxPaths = mp;
}

uint32_t
QTable::GetMaxPaths() const
{
    return m_maxPaths;
}

void
QTable::SetLearningParameters(double alpha, double gamma, double epsilon)
{
    NS_ASSERT_MSG(alpha >= 0.0 && alpha <= 1.0, "alpha must be in [0,1]");
    NS_ASSERT_MSG(gamma >= 0.0 && gamma <= 1.0, "gamma must be in [0,1]");
    NS_ASSERT_MSG(epsilon >= 0.0 && epsilon <= 1.0, "epsilon must be in [0,1]");
    m_alpha = alpha;
    m_gamma = gamma;
    m_epsilon = epsilon;
}

void
QTable::SetRewardWeights(double w1, double w2)
{
    m_w1 = w1;
    m_w2 = w2;
}

void
QTable::SetEpsilonDecay(double decay, double epsilonMin)
{
    m_epsilonDecay = decay;
    m_epsilonMin = epsilonMin;
}

void
QTable::DecayEpsilon()
{
    m_epsilon = std::max(m_epsilonMin, m_epsilon - m_epsilonDecay);
    NS_LOG_DEBUG("QMAODV ε decayed to " << m_epsilon);
}

std::vector<QRecord>::iterator
QTable::FindWorst(std::vector<QRecord>& vec)
{
    if (vec.empty()) return vec.end();
    auto worst = vec.begin();
    for (auto it = vec.begin() + 1; it != vec.end(); ++it)
    {
        if (it->rt.GetHop() > worst->rt.GetHop()) worst = it;
    }
    return worst;
}

bool
QTable::AddRoute(const RoutingTableEntry& rt)
{
    Ipv4Address dst = rt.GetDestination();
    Ipv4Address nh = rt.GetNextHop();

    auto& vec = m_records[dst];

    // Dedup (dst, nextHop): refresh entry but preserve learning.
    for (auto& existing : vec)
    {
        if (existing.rt.GetNextHop() == nh)
        {
            existing.rt = rt;
            NS_LOG_DEBUG("Refresh route: " << dst << " via " << nh);
            return false;
        }
    }

    // FIX-V2 Bug #1: capacity now includes primary (m_maxPaths total,
    // not m_maxPaths - 1). Primary route is tracked here too so its
    // Q-value can be learned online instead of always being reset to 1/HC.
    uint32_t capacity = m_maxPaths;

    if (vec.size() < capacity)
    {
        vec.push_back(QRecord(rt, /*init*/0.0));
        NS_LOG_DEBUG("Added route " << dst << " via " << nh
                     << " HC=" << (uint32_t)rt.GetHop()
                     << " (" << vec.size() << "/" << capacity << ")");
        ReinitQValues(dst);
        return true;
    }

    // At capacity: evict worst if rt is strictly better.
    auto worst = FindWorst(vec);
    if (worst != vec.end() && rt.GetHop() < worst->rt.GetHop())
    {
        NS_LOG_DEBUG("Evict " << dst << " via " << worst->rt.GetNextHop()
                     << " HC=" << (uint32_t)worst->rt.GetHop()
                     << " for new HC=" << (uint32_t)rt.GetHop());
        *worst = QRecord(rt, 0.0);
        ReinitQValues(dst);
        return true;
    }

    return false;
}

bool
QTable::EnsureRecord(const RoutingTableEntry& rt)
{
    Ipv4Address dst = rt.GetDestination();
    Ipv4Address nh = rt.GetNextHop();
    auto& vec = m_records[dst];

    for (auto& existing : vec)
    {
        if (existing.rt.GetNextHop() == nh)
        {
            existing.rt = rt;          // refresh metadata
            return false;              // not newly inserted
        }
    }

    // Bypass capacity check — primary route must always be tracked.
    vec.push_back(QRecord(rt, 0.0));
    ReinitQValues(dst);
    NS_LOG_DEBUG("EnsureRecord added " << dst << " via " << nh);
    return true;
}

void
QTable::UpdateQValueOrCreate(const RoutingTableEntry& rt,
                             double ackSuccess, double delaySec)
{
    EnsureRecord(rt);
    UpdateQValue(rt.GetDestination(), rt.GetNextHop(), ackSuccess, delaySec);
}

void
QTable::ReinitQValues(Ipv4Address dst)
{
    auto it = m_records.find(dst);
    if (it == m_records.end()) return;

    // Equation 1: Q_0(s, a_i) = (1/HC_i) / Σ_k (1/HC_k)
    // Only seed entries that haven't been updated by experience yet.
    double sumInv = 0.0;
    for (const auto& r : it->second)
    {
        uint32_t hc = std::max<uint32_t>(1, r.rt.GetHop());
        sumInv += 1.0 / static_cast<double>(hc);
    }
    if (sumInv <= 0.0) return;

    for (auto& r : it->second)
    {
        if (r.txCount > 0) continue;       // already learned, keep
        uint32_t hc = std::max<uint32_t>(1, r.rt.GetHop());
        r.qValue = (1.0 / hc) / sumInv;
    }
}

uint32_t
QTable::GetRoutes(Ipv4Address dst,
                  std::vector<RoutingTableEntry>& routes,
                  const RoutingTable* mainTable) const
{
    auto it = m_records.find(dst);
    if (it == m_records.end()) return 0;

    uint32_t added = 0;
    for (const auto& r : it->second)
    {
        // Fix Level 1: lifetime filter — bỏ qua alts đã expired.
        if (r.rt.GetFlag() != VALID || r.rt.GetLifeTime() <= Time(0)) continue;

        // Fix Level 2: validate by mainTable — alt's nextHop phải còn 1-hop reachable.
        if (mainTable != nullptr)
        {
            RoutingTableEntry nbr;
            if (!const_cast<RoutingTable*>(mainTable)->LookupRoute(r.rt.GetNextHop(), nbr) ||
                nbr.GetFlag() != VALID)
            {
                continue;
            }
        }

        routes.push_back(r.rt);
        ++added;
    }
    return added;
}

std::vector<QRecord>
QTable::BuildCandidates(const RoutingTableEntry& primary,
                        const RoutingTable* mainTable) const
{
    Ipv4Address dst = primary.GetDestination();
    Ipv4Address primNh = primary.GetNextHop();
    std::vector<QRecord> cands;

    auto it = m_records.find(dst);

    // FIX-V2 Bug #1: look up primary's LEARNED Q from m_records first.
    // If found, use that — primary is no longer disadvantaged with stale
    // initial Q while alternates accrue large learned Q from online updates.
    double primQ = 0.0;
    bool primFound = false;
    if (it != m_records.end())
    {
        for (const auto& r : it->second)
        {
            if (r.rt.GetNextHop() == primNh)
            {
                primQ = r.qValue;
                primFound = true;
                break;
            }
        }
    }

    // Collect alternates (everything in m_records except the primary's next-hop).
    if (it != m_records.end())
    {
        for (const auto& r : it->second)
        {
            if (r.rt.GetNextHop() == primNh) continue;
            if (r.rt.GetFlag() != VALID || r.rt.GetLifeTime() <= Time(0)) continue;
            if (mainTable != nullptr)
            {
                RoutingTableEntry nbr;
                if (!const_cast<RoutingTable*>(mainTable)->LookupRoute(r.rt.GetNextHop(), nbr) ||
                    nbr.GetFlag() != VALID)
                {
                    continue;
                }
            }
            cands.push_back(r);
        }
    }

    // Build primary's QRecord. Use learned Q if available; otherwise seed
    // with normalised (1/HC) across the candidate set.
    uint32_t hcP = std::max<uint32_t>(1, primary.GetHop());
    double primQValue;
    if (primFound)
    {
        primQValue = primQ;
    }
    else
    {
        double sumInv = 1.0 / hcP;
        for (const auto& c : cands)
        {
            sumInv += 1.0 / std::max<uint32_t>(1, c.rt.GetHop());
        }
        primQValue = (sumInv > 0.0) ? (1.0 / hcP) / sumInv : 0.5;
    }
    cands.insert(cands.begin(), QRecord(primary, primQValue));
    return cands;
}

bool
QTable::SelectEpsilonGreedy(const RoutingTableEntry& primary,
                            RoutingTableEntry& out,
                            const RoutingTable* mainTable)
{
    auto cands = BuildCandidates(primary, mainTable);
    if (cands.empty())
    {
        out = primary;
        return false;
    }
    if (cands.size() == 1)
    {
        out = cands[0].rt;
        return true;
    }

    // ε-greedy
    double u = m_uniform->GetValue(0.0, 1.0);
    if (u < m_epsilon)
    {
        // EXPLORE: uniform random over candidates
        uint32_t idx = static_cast<uint32_t>(m_uniform->GetValue(0.0, static_cast<double>(cands.size())));
        if (idx >= cands.size()) idx = cands.size() - 1;
        out = cands[idx].rt;
        NS_LOG_DEBUG("QMAODV EXPLORE select " << out.GetDestination()
                     << " via " << out.GetNextHop()
                     << " (idx=" << idx << "/" << cands.size() << ")");
        return true;
    }

    // EXPLOIT: argmax Q. Ties broken by lower HC.
    size_t bestIdx = 0;
    double bestQ = -std::numeric_limits<double>::infinity();
    uint32_t bestHC = std::numeric_limits<uint32_t>::max();
    for (size_t i = 0; i < cands.size(); ++i)
    {
        double q = cands[i].qValue;
        uint32_t hc = cands[i].rt.GetHop();
        if (q > bestQ || (std::fabs(q - bestQ) < 1e-9 && hc < bestHC))
        {
            bestQ = q; bestHC = hc; bestIdx = i;
        }
    }
    out = cands[bestIdx].rt;
    NS_LOG_DEBUG("QMAODV EXPLOIT select " << out.GetDestination()
                 << " via " << out.GetNextHop()
                 << " Q=" << bestQ << " HC=" << bestHC);
    return true;
}

void
QTable::UpdateQValue(Ipv4Address dst,
                     Ipv4Address nextHop,
                     double ackSuccess,
                     double delaySec)
{
    // Reward: r = w1 · ACK_success + w2 · 1/(delay + 1)
    if (delaySec < 0.0) delaySec = 0.0;
    double reward = m_w1 * ackSuccess + m_w2 * (1.0 / (delaySec + 1.0));

    auto it = m_records.find(dst);
    if (it == m_records.end()) return;

    // Find the (dst, nextHop) record (alt slot only — primary's Q is not persisted,
    // so primary-action feedback is essentially discarded here, which is acceptable
    // for the paper's setup since the primary is also seeded from 1/HC each RREP).
    QRecord* target = nullptr;
    double maxFuture = 0.0;
    for (auto& r : it->second)
    {
        if (r.qValue > maxFuture) maxFuture = r.qValue;
        if (r.rt.GetNextHop() == nextHop) target = &r;
    }
    if (target == nullptr) return;

    // Equation 2: Q ← (1-α)·Q + α·[r + γ · max_a' Q]
    double oldQ = target->qValue;
    target->qValue = (1.0 - m_alpha) * oldQ + m_alpha * (reward + m_gamma * maxFuture);
    target->txCount += 1;
    if (ackSuccess > 0.5) target->ackCount += 1;
    target->lastUpd = Simulator::Now();

    NS_LOG_DEBUG("Q-update dst=" << dst << " nh=" << nextHop
                 << " r=" << reward << " Q: " << oldQ << " -> " << target->qValue);
}

void
QTable::DeleteRoutes(Ipv4Address dst)
{
    m_records.erase(dst);
}

void
QTable::DeleteRoute(Ipv4Address dst, Ipv4Address nextHop)
{
    auto it = m_records.find(dst);
    if (it == m_records.end()) return;
    auto& vec = it->second;
    vec.erase(std::remove_if(vec.begin(), vec.end(),
                             [&](const QRecord& r) { return r.rt.GetNextHop() == nextHop; }),
              vec.end());
    if (vec.empty()) m_records.erase(it);
}

void
QTable::RemoveNextHopGlobally(Ipv4Address nextHop)
{
    for (auto it = m_records.begin(); it != m_records.end(); )
    {
        auto& vec = it->second;
        vec.erase(std::remove_if(vec.begin(), vec.end(),
                                 [&](const QRecord& r) { return r.rt.GetNextHop() == nextHop; }),
                  vec.end());
        if (vec.empty()) it = m_records.erase(it); else ++it;
    }
}

uint32_t
QTable::Size() const
{
    return std::accumulate(m_records.begin(), m_records.end(), uint32_t{0},
                           [](uint32_t a, const auto& kv) { return a + kv.second.size(); });
}

uint32_t
QTable::CountFor(Ipv4Address dst) const
{
    auto it = m_records.find(dst);
    return (it == m_records.end()) ? 0 : static_cast<uint32_t>(it->second.size());
}

bool
QTable::IsFull(Ipv4Address dst) const
{
    // FIX-V2 Bug #1: capacity is m_maxPaths (primary tracked here too).
    return CountFor(dst) >= m_maxPaths;
}

void
QTable::Clear()
{
    m_records.clear();
}

double
QTable::GetQValue(Ipv4Address dst, Ipv4Address nextHop) const
{
    auto it = m_records.find(dst);
    if (it == m_records.end()) return 0.0;
    for (const auto& r : it->second)
    {
        if (r.rt.GetNextHop() == nextHop) return r.qValue;
    }
    return 0.0;
}

void
QTable::Print(std::ostream& os) const
{
    os << "QTable (" << Size() << " entries, MaxPaths=" << m_maxPaths
       << ", α=" << m_alpha << " γ=" << m_gamma << " ε=" << m_epsilon
       << " w1=" << m_w1 << " w2=" << m_w2 << "):\n";
    for (const auto& kv : m_records)
    {
        os << "  dst=" << kv.first << " alts=" << kv.second.size() << "\n";
        for (const auto& r : kv.second)
        {
            os << "    via " << r.rt.GetNextHop()
               << " HC=" << (uint32_t)r.rt.GetHop()
               << " Q=" << r.qValue
               << " tx=" << r.txCount << " ack=" << r.ackCount << "\n";
        }
    }
}

} // namespace qmaodv
} // namespace ns3
