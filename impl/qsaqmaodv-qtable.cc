/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/**
 * QS-QMAODV Self-Adaptive Q-Table — implementation.
 * Weight presets per Paper §4.2 Table II.
 * See qsaqmaodv-qtable.h for design notes.
 */

#include "qsaqmaodv-qtable.h"

#include "ns3/log.h"
#include "ns3/simulator.h"

#include <algorithm>
#include <cmath>
#include <numeric>

namespace ns3
{

NS_LOG_COMPONENT_DEFINE("QsaqmaodvQTable");

namespace qsaqmaodv
{

// ============================================================================
// Constructor — Paper §4.2 Table II weight defaults
// ============================================================================
QTable::QTable(uint32_t maxPaths)
    : m_maxPaths(maxPaths),
      m_alpha(0.5), m_gamma(0.9), m_epsilon(0.3),
      // NORMAL mode initial weights
      m_w1(0.40), m_w2(0.30), m_w3(0.10), m_w4(0.20),
      m_adaptMode(ADAPT_NORMAL),
      m_lowEnergyActive(false),
      m_highLoadActive(false),
      // --- Adaptation knobs ---
      m_epsilonMin(0.10), m_epsilonMax(0.50),
      m_epsilonStep(0.02), m_epsilonBump(0.20),
      m_lambda(0.10),
      m_seqNoWindow(Seconds(5.0)),
      m_lowEnergyThresh(0.20),
      m_queueHighThresh(0.70),   // Paper §4.3
      m_queueLowThresh(0.30),
      // --- NORMAL mode (Paper Table II) ---
      m_w1Normal(0.40),   m_w2Normal(0.30),   m_w3Normal(0.10),   m_w4Normal(0.20),
      // --- LOW_ENERGY mode ---
      m_w1LowE(0.20),     m_w2LowE(0.10),     m_w3LowE(0.50),     m_w4LowE(0.20),
      // --- HIGH_LOAD mode ---
      m_w1HiLoad(0.30),   m_w2HiLoad(0.20),   m_w3HiLoad(0.10),   m_w4HiLoad(0.40),
      // --- LOAD_COMBINED: arithmetic mean of LOW_E and HIGH_LOAD ---
      m_w1Combined(0.25), m_w2Combined(0.15), m_w3Combined(0.30), m_w4Combined(0.30)
{
    m_uniform = CreateObject<UniformRandomVariable>();
}

// ============================================================================
// Configuration
// ============================================================================
void QTable::SetMaxPaths(uint32_t mp)
{
    NS_ASSERT_MSG(mp >= 1, "MaxPaths >= 1");
    m_maxPaths = mp;
}
uint32_t QTable::GetMaxPaths() const { return m_maxPaths; }

void QTable::SetLearningParameters(double a0, double g, double e0)
{
    NS_ASSERT(a0 >= 0 && a0 <= 1);
    NS_ASSERT(g  >= 0 && g  <= 1);
    NS_ASSERT(e0 >= 0 && e0 <= 1);
    m_alpha = a0; m_gamma = g; m_epsilon = e0;
}

void QTable::SetRewardWeights(double w1, double w2, double w3, double w4)
{
    m_w1 = w1; m_w2 = w2; m_w3 = w3; m_w4 = w4;
    m_w1Normal = w1; m_w2Normal = w2; m_w3Normal = w3; m_w4Normal = w4;
}

void QTable::SetQueueHighThreshold(double f) { m_queueHighThresh = f; }
void QTable::SetQueueLowThreshold(double f)  { m_queueLowThresh  = f; }
void QTable::SetLowEnergyThreshold(double f) { m_lowEnergyThresh = f; }
void QTable::SetSensitivityLambda(double l)  { m_lambda = l; }
void QTable::SetSeqNoWindow(Time w)          { m_seqNoWindow = w; }

// ============================================================================
// Self-Adaptive Controller
// ============================================================================

// --- Adaptive epsilon -------------------------------------------------------

void QTable::OnRouteError()
{
    double old = m_epsilon;
    m_epsilon = std::min(m_epsilonMax, m_epsilon + m_epsilonBump);
    NS_LOG_DEBUG("QSAQM eps RERR: " << old << " -> " << m_epsilon);
}

void QTable::PeriodicEpsilonDecay()
{
    double old = m_epsilon;
    m_epsilon = std::max(m_epsilonMin, m_epsilon - m_epsilonStep);
    NS_LOG_DEBUG("QSAQM eps decay: " << old << " -> " << m_epsilon);
}

// --- Adaptive alpha ---------------------------------------------------------

void QTable::RecordSeqNoUpdate()
{
    m_seqEvents.push_back(Simulator::Now());
    PurgeSeqNoEvents();
}

void QTable::PurgeSeqNoEvents()
{
    const Time thr = Simulator::Now() - m_seqNoWindow;
    while (!m_seqEvents.empty() && m_seqEvents.front() < thr)
        m_seqEvents.pop_front();
}

uint32_t QTable::GetDeltaSeq() const
{
    const Time thr = Simulator::Now() - m_seqNoWindow;
    while (!m_seqEvents.empty() && m_seqEvents.front() < thr)
        m_seqEvents.pop_front();
    return static_cast<uint32_t>(m_seqEvents.size());
}

void QTable::RecomputeAdaptiveAlpha()
{
    uint32_t dSeq = GetDeltaSeq();
    m_alpha = 0.1 + 0.8 * (1.0 - std::exp(-m_lambda * static_cast<double>(dSeq)));
    NS_LOG_DEBUG("QSAQM alpha: dSeq=" << dSeq << " alpha=" << m_alpha);
}

// --- Adaptive reward weights (Paper §4.3) -----------------------------------

void QTable::ApplyModeWeights(AdaptMode mode)
{
    switch (mode) {
    case ADAPT_NORMAL:
        m_w1 = m_w1Normal;   m_w2 = m_w2Normal;
        m_w3 = m_w3Normal;   m_w4 = m_w4Normal;   break;
    case ADAPT_LOW_ENERGY:
        m_w1 = m_w1LowE;     m_w2 = m_w2LowE;
        m_w3 = m_w3LowE;     m_w4 = m_w4LowE;     break;
    case ADAPT_HIGH_LOAD:
        m_w1 = m_w1HiLoad;   m_w2 = m_w2HiLoad;
        m_w3 = m_w3HiLoad;   m_w4 = m_w4HiLoad;   break;
    case ADAPT_LOAD_COMBINED:
        m_w1 = m_w1Combined; m_w2 = m_w2Combined;
        m_w3 = m_w3Combined; m_w4 = m_w4Combined;  break;
    }
}

void QTable::RecomputeAdaptiveRewardWeights(double energyFraction, double queueRatio)
{
    bool newLowE = (energyFraction < m_lowEnergyThresh);

    // HIGH_LOAD hysteresis
    bool newHiLoad = m_highLoadActive;
    if (!m_highLoadActive && queueRatio > m_queueHighThresh) newHiLoad = true;
    else if (m_highLoadActive && queueRatio < m_queueLowThresh) newHiLoad = false;

    AdaptMode newMode;
    if      (newLowE && newHiLoad) newMode = ADAPT_LOAD_COMBINED;
    else if (newLowE)              newMode = ADAPT_LOW_ENERGY;
    else if (newHiLoad)            newMode = ADAPT_HIGH_LOAD;
    else                           newMode = ADAPT_NORMAL;

    if (newMode != m_adaptMode || newLowE != m_lowEnergyActive || newHiLoad != m_highLoadActive)
    {
        const char* names[] = {"NORMAL","LOW_ENERGY","HIGH_LOAD","LOAD_COMBINED"};
        NS_LOG_INFO("QSAQM mode: " << names[m_adaptMode] << " -> " << names[newMode]
                    << " (E=" << energyFraction << " Q=" << queueRatio << ")");
        m_adaptMode       = newMode;
        m_lowEnergyActive = newLowE;
        m_highLoadActive  = newHiLoad;
        ApplyModeWeights(newMode);
    }
}

// --- Per-neighbor RERR congestion -------------------------------------------

void QTable::RecordNeighborRerr(Ipv4Address neighbor, double increment)
{
    double& score = m_neighborCongestion[neighbor];
    score = std::min(1.0, score + increment);
    NS_LOG_DEBUG("QSAQM RERR congestion " << neighbor << " -> " << score);
}

void QTable::DecayNeighborCongestion(double factor)
{
    NS_ASSERT(factor > 0.0 && factor <= 1.0);
    for (auto& kv : m_neighborCongestion)
        kv.second *= factor;
    // Remove entries that have fully decayed (< 0.01) to avoid map bloat
    for (auto it = m_neighborCongestion.begin(); it != m_neighborCongestion.end(); )
    {
        if (it->second < 0.01) it = m_neighborCongestion.erase(it);
        else                   ++it;
    }
}

double QTable::GetNeighborCongestion(Ipv4Address neighbor) const
{
    auto it = m_neighborCongestion.find(neighbor);
    return (it == m_neighborCongestion.end()) ? 0.0 : it->second;
}

// --- 4-term reward ----------------------------------------------------------

double QTable::ComputeReward(double ack, double delay, double energy, double queue) const
{
    if (delay  < 0) delay  = 0;
    if (energy < 0) energy = 0;
    if (queue  < 0) queue  = 0;
    if (queue  > 1) queue  = 1;
    return m_w1 * ack
         + m_w2 * (1.0 / (delay  + 1.0))
         + m_w3 * energy
         + m_w4 * (1.0 / (queue  + 1.0));
}

// ============================================================================
// Standard Q-table operations
// ============================================================================

std::vector<QRecord>::iterator QTable::FindWorst(std::vector<QRecord>& v)
{
    if (v.empty()) return v.end();
    auto worst = v.begin();
    for (auto it = v.begin()+1; it != v.end(); ++it)
        if (it->rt.GetHop() > worst->rt.GetHop()) worst = it;
    return worst;
}

bool QTable::AddRoute(const RoutingTableEntry& rt)
{
    Ipv4Address dst = rt.GetDestination(), nh = rt.GetNextHop();
    auto& vec = m_records[dst];
    for (auto& r : vec) if (r.rt.GetNextHop() == nh) { r.rt = rt; return false; }

    if (vec.size() < m_maxPaths)
    { vec.push_back(QRecord(rt,0.0)); ReinitQValues(dst); return true; }

    auto worst = FindWorst(vec);
    if (worst != vec.end() && rt.GetHop() < worst->rt.GetHop())
    { *worst = QRecord(rt,0.0); ReinitQValues(dst); return true; }
    return false;
}

bool QTable::EnsureRecord(const RoutingTableEntry& rt)
{
    auto& vec = m_records[rt.GetDestination()];
    for (auto& r : vec) if (r.rt.GetNextHop() == rt.GetNextHop()) { r.rt = rt; return false; }
    vec.push_back(QRecord(rt,0.0));
    ReinitQValues(rt.GetDestination());
    return true;
}

void QTable::ReinitQValues(Ipv4Address dst)
{
    auto it = m_records.find(dst);
    if (it == m_records.end()) return;
    double sumInv = 0;
    for (const auto& r : it->second) sumInv += 1.0/std::max<uint32_t>(1,r.rt.GetHop());
    if (sumInv <= 0) return;
    for (auto& r : it->second) {
        if (r.txCount > 0) continue;
        uint32_t hc = std::max<uint32_t>(1, r.rt.GetHop());
        r.qValue = (1.0/hc)/sumInv;
    }
}

uint32_t QTable::GetRoutes(Ipv4Address dst,
                            std::vector<RoutingTableEntry>& routes,
                            const RoutingTable* mainTable) const
{
    auto it = m_records.find(dst);
    if (it == m_records.end()) return 0;
    uint32_t added = 0;
    for (const auto& r : it->second) {
        if (r.rt.GetFlag() != VALID || r.rt.GetLifeTime() <= Time(0)) continue;
        if (mainTable) {
            RoutingTableEntry nbr;
            if (!const_cast<RoutingTable*>(mainTable)->LookupRoute(r.rt.GetNextHop(),nbr)
                || nbr.GetFlag()!=VALID) continue;
        }
        routes.push_back(r.rt); ++added;
    }
    return added;
}

std::vector<QRecord> QTable::BuildCandidates(const RoutingTableEntry& primary,
                                               const RoutingTable* mainTable) const
{
    Ipv4Address dst = primary.GetDestination(), primNh = primary.GetNextHop();
    std::vector<QRecord> cands;
    auto it = m_records.find(dst);
    double primQ = 0; bool primFound = false;

    if (it != m_records.end()) {
        for (const auto& r : it->second)
            if (r.rt.GetNextHop()==primNh) { primQ=r.qValue; primFound=true; break; }
        for (const auto& r : it->second) {
            if (r.rt.GetNextHop()==primNh) continue;
            if (r.rt.GetFlag()!=VALID || r.rt.GetLifeTime()<=Time(0)) continue;
            if (mainTable) {
                RoutingTableEntry nbr;
                if (!const_cast<RoutingTable*>(mainTable)->LookupRoute(r.rt.GetNextHop(),nbr)
                    || nbr.GetFlag()!=VALID) continue;
            }
            cands.push_back(r);
        }
    }
    uint32_t hcP = std::max<uint32_t>(1, primary.GetHop());
    double primQVal;
    if (primFound) primQVal = primQ;
    else {
        double sumInv = 1.0/hcP;
        for (const auto& c : cands) sumInv += 1.0/std::max<uint32_t>(1,c.rt.GetHop());
        primQVal = sumInv > 0 ? (1.0/hcP)/sumInv : 0.5;
    }
    cands.insert(cands.begin(), QRecord(primary, primQVal));
    return cands;
}

bool QTable::SelectEpsilonGreedy(const RoutingTableEntry& primary,
                                  RoutingTableEntry& out,
                                  const RoutingTable* mainTable)
{
    auto cands = BuildCandidates(primary, mainTable);
    if (cands.empty())     { out = primary;     return false; }
    if (cands.size() == 1) { out = cands[0].rt; return true;  }

    if (m_uniform->GetValue(0,1) < m_epsilon) {
        uint32_t idx = static_cast<uint32_t>(
            m_uniform->GetValue(0, static_cast<double>(cands.size())));
        if (idx >= cands.size()) idx = static_cast<uint32_t>(cands.size())-1;
        out = cands[idx].rt; return true;
    }
    size_t best = 0; double bestQ = -1e30; uint32_t bestHC = UINT32_MAX;
    for (size_t i = 0; i < cands.size(); ++i) {
        double q = cands[i].qValue; uint32_t hc = cands[i].rt.GetHop();
        if (q > bestQ || (std::fabs(q-bestQ)<1e-9 && hc<bestHC))
        { bestQ=q; bestHC=hc; best=i; }
    }
    out = cands[best].rt; return true;
}

void QTable::UpdateQValue(Ipv4Address dst, Ipv4Address nh,
                           double ack, double delay, double energy, double queue)
{
    // Override caller-supplied queue ratio with per-neighbor RERR congestion
    // if we have a measurement for this next-hop.  RERR-based congestion is
    // per-neighbor (NOT per-destination), so different next-hops for the same
    // destination receive different queue penalties → w4 actually differentiates
    // routes.  The caller's `queue` value (global buffer occupancy) is used as
    // a fallback when no RERR has been seen from this neighbor yet.
    auto congIt = m_neighborCongestion.find(nh);
    if (congIt != m_neighborCongestion.end())
        queue = congIt->second;

    double r = ComputeReward(ack, delay, energy, queue);
    auto it = m_records.find(dst);
    if (it == m_records.end()) return;

    QRecord* target = nullptr; double maxQ = 0;
    for (auto& rec : it->second) {
        if (rec.qValue > maxQ) maxQ = rec.qValue;
        if (rec.rt.GetNextHop() == nh) target = &rec;
    }
    if (!target) return;

    double oldQ = target->qValue;
    target->qValue  = (1-m_alpha)*oldQ + m_alpha*(r + m_gamma*maxQ);
    target->txCount += 1;
    if (ack > 0.5) target->ackCount += 1;
    target->lastUpd = Simulator::Now();

    NS_LOG_DEBUG("QSAQM Qupd dst=" << dst << " nh=" << nh
                 << " r=" << r << " Q:" << oldQ << "->" << target->qValue
                 << " mode=" << static_cast<int>(m_adaptMode));
}

void QTable::UpdateQValueOrCreate(const RoutingTableEntry& rt,
                                   double ack, double delay, double energy, double queue)
{
    EnsureRecord(rt);
    UpdateQValue(rt.GetDestination(), rt.GetNextHop(), ack, delay, energy, queue);
}

void QTable::DeleteRoutes(Ipv4Address dst) { m_records.erase(dst); }

void QTable::DeleteRoute(Ipv4Address dst, Ipv4Address nh)
{
    auto it = m_records.find(dst);
    if (it == m_records.end()) return;
    auto& v = it->second;
    v.erase(std::remove_if(v.begin(),v.end(),[&](const QRecord& r){ return r.rt.GetNextHop()==nh; }),v.end());
    if (v.empty()) m_records.erase(it);
}

void QTable::RemoveNextHopGlobally(Ipv4Address nh)
{
    for (auto it = m_records.begin(); it != m_records.end(); ) {
        auto& v = it->second;
        v.erase(std::remove_if(v.begin(),v.end(),[&](const QRecord& r){ return r.rt.GetNextHop()==nh; }),v.end());
        if (v.empty()) it = m_records.erase(it); else ++it;
    }
}

uint32_t QTable::Size() const
{
    return std::accumulate(m_records.begin(),m_records.end(),uint32_t{0},
        [](uint32_t a,const auto& kv){ return a+kv.second.size(); });
}
uint32_t QTable::CountFor(Ipv4Address dst) const
{
    auto it = m_records.find(dst);
    return it==m_records.end() ? 0 : static_cast<uint32_t>(it->second.size());
}
bool   QTable::IsFull(Ipv4Address dst) const { return CountFor(dst) >= m_maxPaths; }
void   QTable::Clear() { m_records.clear(); m_seqEvents.clear(); }
double QTable::GetQValue(Ipv4Address dst, Ipv4Address nh) const
{
    auto it = m_records.find(dst);
    if (it==m_records.end()) return 0;
    for (const auto& r : it->second) if (r.rt.GetNextHop()==nh) return r.qValue;
    return 0;
}

void QTable::Print(std::ostream& os) const
{
    const char* modeStr[] = {"NORMAL","LOW_ENERGY","HIGH_LOAD","LOAD_COMBINED"};
    os << "QS-Q-Table (" << Size() << " entries)"
       << " a=" << m_alpha << " g=" << m_gamma << " e=" << m_epsilon
       << " mode=" << modeStr[m_adaptMode]
       << " w=(" << m_w1 << "," << m_w2 << "," << m_w3 << "," << m_w4 << ")\n";
    for (const auto& kv : m_records) {
        os << "  dst=" << kv.first << "\n";
        for (const auto& r : kv.second)
            os << "    via " << r.rt.GetNextHop()
               << " HC=" << (uint32_t)r.rt.GetHop()
               << " Q=" << r.qValue
               << " tx=" << r.txCount << " ack=" << r.ackCount << "\n";
    }
}

} // namespace qsaqmaodv
} // namespace ns3
