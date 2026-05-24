/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/**
 * Q-Table for QMAODV (Q-learning Multipath AODV).
 *
 * Drop-in replacement for PMAODV's MultipathTable: stores ALTERNATE routes
 * (besides the primary in m_routingTable) per destination, link-disjoint
 * by next-hop dedup. The KEY DIFFERENCE from PMAODV's MultipathTable is the
 * selection rule:
 *
 *   PMAODV → static probability p_i = (1/HC_i) / Σ(1/HC_k)   (paper §3.2)
 *   QMAODV → Q-learning ε-greedy over Q(s, a), with:
 *
 *       Initial Q-value (from RREP hop count, Eq. 1 of QMAODV paper):
 *                            (1 / HC_i)
 *           Q_0(s, a_i) = ─────────────────────
 *                         Σ_k (1 / HC_k)
 *
 *       Online update (Eq. 2):
 *           Q(s,a) ← (1 − α)·Q(s,a) + α·[r + γ · max_a' Q(s,a')]
 *
 *       Reward (paper §3.3 with w1=0.6, w2=0.4):
 *           r = w1 · ACK_success  +  w2 · 1 / (delay + 1)
 *
 *       Action selection (ε-greedy with decay):
 *           with prob. ε  : pick random next-hop  (exploration)
 *           with prob. 1−ε: pick argmax_a Q(s,a)  (exploitation)
 *
 * Class API mirrors pmaodv::MultipathTable so that integration into the
 * (cloned) AODV routing protocol can re-use the same patch surface.
 */

#ifndef QMAODV_QTABLE_H
#define QMAODV_QTABLE_H

#include "qmaodv-rtable.h"

#include "ns3/ipv4-address.h"
#include "ns3/nstime.h"
#include "ns3/random-variable-stream.h"

#include <map>
#include <vector>

namespace ns3
{
namespace qmaodv
{

/// One Q-learning record per (destination, next-hop) pair.
/// Wraps a RoutingTableEntry (so it can be returned just like an alternate
/// route) plus the Q-value and running statistics needed for reward shaping.
struct QRecord
{
    RoutingTableEntry rt;       //!< The full routing-table entry (for forwarding).
    double            qValue;   //!< Current Q(s, a).
    uint32_t          txCount;  //!< Times this action was taken.
    uint32_t          ackCount; //!< Times feedback was positive (route fresh / ACK observed).
    Time              lastUpd;  //!< Last time Q was updated.

    QRecord()
        : qValue(0.0), txCount(0), ackCount(0), lastUpd(Seconds(0))
    {}

    QRecord(const RoutingTableEntry& e, double q)
        : rt(e), qValue(q), txCount(0), ackCount(0), lastUpd(Seconds(0))
    {}
};

/**
 * \brief Per-node Q-table storing alternate routes plus learned Q-values.
 */
class QTable
{
  public:
    QTable(uint32_t maxPaths = 3);

    // -------- Multipath capacity (same surface as PMAODV::MultipathTable) ----
    void SetMaxPaths(uint32_t mp);
    uint32_t GetMaxPaths() const;

    // -------- RL hyper-parameters -------------------------------------------
    /// Set Q-learning hyper-parameters (paper Table 3).
    void SetLearningParameters(double alpha, double gamma, double epsilon);
    /// Set reward weights for r = w1·ACK + w2·1/(delay+1).
    void SetRewardWeights(double w1, double w2);
    /// Set ε-decay: ε ← max(εMin, ε − decay) every `period` seconds.
    void SetEpsilonDecay(double decay, double epsilonMin = 0.05);

    double GetAlpha()   const { return m_alpha; }
    double GetGamma()   const { return m_gamma; }
    double GetEpsilon() const { return m_epsilon; }

    /// Apply one decay step (call from a periodic timer in the routing protocol).
    void DecayEpsilon();

    // -------- Multipath table operations ------------------------------------
    /**
     * Try to add an alternate (dst, nextHop, hopCount) entry.
     *   - Reject if (dst, nextHop) already present.
     *   - If at capacity, evict the worst (largest HC) entry only when `rt` is
     *     strictly better.
     *   - Initial Q-value is *not* set here directly; instead, after each
     *     successful add for a given destination, ReinitQValues(dst) is called
     *     to redistribute Q values according to Eq. 1.
     * \return true if added.
     */
    bool AddRoute(const RoutingTableEntry& rt);

    /// Re-compute initial Q-values for `dst` from current hop counts (Eq. 1).
    /// Preserves Q-values that have already been updated by experience
    /// (txCount > 0) so learning is not erased on every new RREP.
    void ReinitQValues(Ipv4Address dst);

    /**
     * \brief Idempotent add of a route record (used for PRIMARY route).
     *
     * Unlike AddRoute, this method:
     *   - Does NOT enforce m_maxPaths capacity (primary is always tracked).
     *   - If (dst, nextHop) already exists, refreshes the RoutingTableEntry but
     *     preserves the learned qValue/txCount/ackCount.
     *   - If new, initialises qValue via Eq. 1.
     *
     * This is the fix for Bug #1 of fix-v2: primary route must be in the Q-table
     * for its qValue to be updated by experience just like alternates.
     *
     * \return true if newly inserted, false if just refreshed.
     */
    bool EnsureRecord(const RoutingTableEntry& rt);

    /**
     * \brief Update Q for an action, automatically creating the record if it
     * does not exist (using `rt` to seed it).
     *
     * Used by the per-packet update hook in RouteOutput (Bug #2 fix).
     */
    void UpdateQValueOrCreate(const RoutingTableEntry& rt,
                              double ackSuccess, double delaySec);

    /**
     * Get all VALID (lifetime > 0) alternate routes for `dst`.
     * If `mainTable` != nullptr, also revalidate each alt's next-hop has a
     * VALID one-hop entry there (Fix Level 2 from PMAODV/AOMDV).
     */
    uint32_t GetRoutes(Ipv4Address dst,
                       std::vector<RoutingTableEntry>& routes,
                       const RoutingTable* mainTable = nullptr) const;

    // -------- Q-learning selection ------------------------------------------
    /**
     * ε-greedy selection over (primary + alternates) for forwarding.
     * \param primary Primary route from RoutingTable lookup.
     * \param out     Selected entry.
     * \param mainTable Optional revalidation hook (Fix Level 2).
     * \return false only if no candidate is usable.
     */
    bool SelectEpsilonGreedy(const RoutingTableEntry& primary,
                             RoutingTableEntry& out,
                             const RoutingTable* mainTable = nullptr);

    /**
     * Update Q(s, a) for the most recent forwarding decision.
     * Typically called from RecvReply (positive reward, route validated)
     * or RecvError / link-failure (negative reward).
     *
     * Reward formula:  r = w1·ackSuccess + w2·1/(delaySec + 1)
     */
    void UpdateQValue(Ipv4Address dst,
                      Ipv4Address nextHop,
                      double ackSuccess,
                      double delaySec);

    // -------- Lifecycle / inspection ----------------------------------------
    void DeleteRoutes(Ipv4Address dst);
    void DeleteRoute(Ipv4Address dst, Ipv4Address nextHop);
    void RemoveNextHopGlobally(Ipv4Address nextHop);   //!< on neighbor loss

    uint32_t Size() const;
    uint32_t CountFor(Ipv4Address dst) const;
    bool     IsFull(Ipv4Address dst) const;
    void     Clear();
    void     Print(std::ostream& os) const;

    /// Read-only Q-value lookup (returns 0 if unknown).
    double GetQValue(Ipv4Address dst, Ipv4Address nextHop) const;

  private:
    /// Locate the worst (highest-HC) alternate; returns end() on empty.
    std::vector<QRecord>::iterator FindWorst(std::vector<QRecord>& vec);

    /// Build a list of candidate records (primary + valid alts) for forwarding.
    std::vector<QRecord> BuildCandidates(const RoutingTableEntry& primary,
                                         const RoutingTable* mainTable) const;

    /// All alternates per destination (excluding primary).
    std::map<Ipv4Address, std::vector<QRecord>> m_records;

    // Capacity.
    uint32_t m_maxPaths;

    // Hyper-parameters.
    double m_alpha;
    double m_gamma;
    double m_epsilon;
    double m_epsilonMin;
    double m_epsilonDecay;
    double m_w1, m_w2;

    Ptr<UniformRandomVariable> m_uniform;
};

} // namespace qmaodv
} // namespace ns3

#endif /* QMAODV_QTABLE_H */
