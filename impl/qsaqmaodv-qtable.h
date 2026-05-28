/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/**
 * QS-QMAODV Self-Adaptive Q-Table with Queue-State awareness.
 *
 * Extends SA-QMAODV (ICIT 2026) with a FOURTH reward term: local queue occupancy.
 *
 *   SA-QMAODV (3-term): r = w1·ACK + w2·1/(d+1) + w3·E
 *   QS-QMAODV (4-term): r = w1·ACK + w2·1/(d+1) + w3·E + w4·1/(q+1)
 *
 * Three primary operating modes (Paper §4.2):
 *
 *   NORMAL      (w1,w2,w3,w4) = (0.40, 0.30, 0.10, 0.20)  balanced
 *   LOW_ENERGY  (w1,w2,w3,w4) = (0.20, 0.10, 0.50, 0.20)  energy conserving
 *   HIGH_LOAD   (w1,w2,w3,w4) = (0.30, 0.20, 0.10, 0.40)  congestion avoiding
 *
 * LOAD_COMBINED — both constraints active simultaneously (Paper §4.3):
 *   Computes combined weights that balance energy + queue signals.
 *   w3_combined = w3(NORMAL) + w3(LOW_ENERGY_delta)/2
 *   w4_combined = w4(NORMAL) + w4(HIGH_LOAD_delta)/2
 *
 * Mode transitions (Paper §4.3):
 *   LOW_ENERGY  on: energyFraction < lowEnergyThresh (0.20)
 *   HIGH_LOAD   on: queueRatio > queueHighThresh (0.70)  [hysteresis]
 *   HIGH_LOAD  off: queueRatio < queueLowThresh  (0.30)
 *   LOAD_COMBINED: both conditions hold simultaneously
 *
 * Inherited adaptive mechanisms from SA-QMAODV:
 *   epsilon-bump on RERR, periodic epsilon-decay, adaptive alpha via Delta_Seq.
 *
 * Reference:
 *   QL-AODV  (Future Internet 2025): buffer-state reward
 *   AQR-FANET (2024)               : anticipatory queue reward
 *   SA-QMAODV (ICIT 2026)          : adaptive 3-term base
 */

#ifndef QSAQMAODV_QTABLE_H
#define QSAQMAODV_QTABLE_H

#include "qsaqmaodv-rtable.h"

#include "ns3/ipv4-address.h"
#include "ns3/nstime.h"
#include "ns3/random-variable-stream.h"

#include <deque>
#include <map>
#include <vector>

namespace ns3
{
namespace qsaqmaodv
{

/// One Q-learning record per (destination, next-hop) pair.
struct QRecord
{
    RoutingTableEntry rt;
    double            qValue;
    uint32_t          txCount;
    uint32_t          ackCount;
    Time              lastUpd;

    QRecord() : qValue(0.0), txCount(0), ackCount(0), lastUpd(Seconds(0)) {}
    QRecord(const RoutingTableEntry& e, double q)
        : rt(e), qValue(q), txCount(0), ackCount(0), lastUpd(Seconds(0)) {}
};

/// Operating mode of the adaptive reward controller (Paper §4.3).
enum AdaptMode
{
    ADAPT_NORMAL         = 0, ///< Balanced: (0.40, 0.30, 0.10, 0.20)
    ADAPT_LOW_ENERGY     = 1, ///< Battery low: (0.20, 0.10, 0.50, 0.20)
    ADAPT_HIGH_LOAD      = 2, ///< Congested: (0.30, 0.20, 0.10, 0.40)
    ADAPT_LOAD_COMBINED  = 3  ///< Both constraints: average of Low-E and High-Load
};

/**
 * \brief QS-QMAODV Self-Adaptive Q-Table with 4-term reward.
 *
 * Drop-in superset of SA-QMAODV QTable.
 * UpdateQValue/UpdateQValueOrCreate accept two extra optional params
 * (energyFraction and queueRatio) with backward-compatible defaults.
 */
class QTable
{
  public:
    explicit QTable(uint32_t maxPaths = 3);

    void     SetMaxPaths(uint32_t mp);
    uint32_t GetMaxPaths() const;

    // -------- Initial hyper-parameters --------------------------------------

    void SetLearningParameters(double alpha0, double gamma, double epsilon0);

    /// Set initial reward weights; w4 is the new queue-state weight.
    /// Defaults match Paper §4.2 NORMAL mode.
    void SetRewardWeights(double w1, double w2, double w3, double w4 = 0.20);

    // -------- Self-Adaptive controller (inherited from SA-QMAODV) -----------

    void OnRouteError();           ///< RERR: eps = min(0.50, eps+0.20)
    void PeriodicEpsilonDecay();   ///< Tick:  eps = max(0.10, eps-0.02)
    void RecordSeqNoUpdate();      ///< For Delta_Seq window (drives alpha_t)
    void RecomputeAdaptiveAlpha(); ///< alpha_t = 0.1+0.8*(1-exp(-lambda*DSeq))

    /**
     * \brief Update reward-weights from energy AND queue state (Paper §4.3).
     *
     * Mode selection:
     *   LOAD_COMBINED  if both low-energy and high-load conditions
     *   LOW_ENERGY     if only energy is low
     *   HIGH_LOAD      if only queue is high (hysteresis applies)
     *   NORMAL         otherwise
     *
     * \param energyFraction  Residual energy in [0,1].
     * \param queueRatio      Output queue occupancy in [0,1] (default 0).
     */
    void RecomputeAdaptiveRewardWeights(double energyFraction,
                                        double queueRatio = 0.0);

    // -------- Queue-state knobs ---------------------------------------------

    void SetQueueHighThreshold(double frac); ///< HIGH_LOAD entry  (default 0.70)
    void SetQueueLowThreshold(double frac);  ///< HIGH_LOAD exit   (default 0.30)

    // -------- Per-neighbor RERR-based congestion ----------------------------

    /**
     * \brief Record congestion at a neighbor (called when RERR received from it).
     *
     * Congestion score is clamped to [0,1].  Each RERR bumps the score by
     * \p increment (default 0.25).  Repeated RERRs saturate at 1.0.
     *
     * \param neighbor  Address of the node that sent the RERR.
     * \param increment Amount to add (default 0.25).
     */
    void RecordNeighborRerr(Ipv4Address neighbor, double increment = 0.25);

    /**
     * \brief Exponential decay of all per-neighbor congestion scores.
     *
     * Called periodically (same tick as PeriodicEpsilonDecay).
     * \p factor=0.90 → half-life ≈ 6.6 ticks.
     *
     * \param factor  Multiplicative decay factor in (0,1].
     */
    void DecayNeighborCongestion(double factor = 0.90);

    /**
     * \brief Return the current congestion estimate for a neighbor in [0,1].
     *
     * Returns 0.0 if the neighbor has never generated a RERR.
     */
    double GetNeighborCongestion(Ipv4Address neighbor) const;

    // -------- Energy / alpha knobs ------------------------------------------

    void SetLowEnergyThreshold(double frac); ///< LOW_ENERGY entry (default 0.20)
    void SetSensitivityLambda(double lambda); ///< alpha_t formula  (default 0.10)
    void SetSeqNoWindow(Time window);         ///< Delta_Seq window (default 5 s)

    // -------- Read accessors ------------------------------------------------

    double    GetAlpha()    const { return m_alpha;    }
    double    GetGamma()    const { return m_gamma;    }
    double    GetEpsilon()  const { return m_epsilon;  }
    double    GetW1()       const { return m_w1; }
    double    GetW2()       const { return m_w2; }
    double    GetW3()       const { return m_w3; }
    double    GetW4()       const { return m_w4; }
    AdaptMode GetMode()     const { return m_adaptMode; }
    uint32_t  GetDeltaSeq() const;

    // -------- Standard QTable operations ------------------------------------

    bool AddRoute(const RoutingTableEntry& rt);
    void ReinitQValues(Ipv4Address dst);

    uint32_t GetRoutes(Ipv4Address dst,
                       std::vector<RoutingTableEntry>& routes,
                       const RoutingTable* mainTable = nullptr) const;

    bool SelectEpsilonGreedy(const RoutingTableEntry& primary,
                             RoutingTableEntry& out,
                             const RoutingTable* mainTable = nullptr);

    /**
     * \brief Update Q-value using the 4-term reward r_t (Paper Eq. 5).
     *
     * \param dst             Destination.
     * \param nextHop         Next-hop address.
     * \param ackSuccess      1.0 = ACK received, 0.0 = lost.
     * \param delaySec        One-way delay estimate (seconds).
     * \param energyFraction  Residual energy [0,1]  (default 1.0).
     * \param queueRatio      Queue occupancy [0,1]  (default 0.0).
     */
    void UpdateQValue(Ipv4Address dst,
                      Ipv4Address nextHop,
                      double ackSuccess,
                      double delaySec,
                      double energyFraction = 1.0,
                      double queueRatio     = 0.0);

    bool EnsureRecord(const RoutingTableEntry& rt);

    void UpdateQValueOrCreate(const RoutingTableEntry& rt,
                              double ackSuccess,
                              double delaySec,
                              double energyFraction = 1.0,
                              double queueRatio     = 0.0);

    void DeleteRoutes(Ipv4Address dst);
    void DeleteRoute(Ipv4Address dst, Ipv4Address nextHop);
    void RemoveNextHopGlobally(Ipv4Address nextHop);

    uint32_t Size()                  const;
    uint32_t CountFor(Ipv4Address dst) const;
    bool     IsFull(Ipv4Address dst)   const;
    void     Clear();
    void     Print(std::ostream& os)   const;
    double   GetQValue(Ipv4Address dst, Ipv4Address nextHop) const;

  private:
    std::vector<QRecord>::iterator FindWorst(std::vector<QRecord>& vec);
    std::vector<QRecord> BuildCandidates(const RoutingTableEntry& primary,
                                          const RoutingTable* mainTable) const;
    double ComputeReward(double ackSuccess, double delaySec,
                         double energyFrac, double queueRatio) const;
    void PurgeSeqNoEvents();
    void ApplyModeWeights(AdaptMode mode);

    // ---- Storage -----------------------------------------------------------
    std::map<Ipv4Address, std::vector<QRecord>> m_records;
    uint32_t m_maxPaths;

    // ---- Live adaptive state -----------------------------------------------
    double    m_alpha;
    double    m_gamma;
    double    m_epsilon;
    double    m_w1, m_w2, m_w3, m_w4;
    AdaptMode m_adaptMode;
    bool      m_lowEnergyActive;
    bool      m_highLoadActive;

    // ---- Adaptation knobs --------------------------------------------------
    double m_epsilonMin;       ///< 0.10
    double m_epsilonMax;       ///< 0.50
    double m_epsilonStep;      ///< 0.02
    double m_epsilonBump;      ///< 0.20
    double m_lambda;           ///< 0.10
    Time   m_seqNoWindow;      ///< 5 s
    double m_lowEnergyThresh;  ///< 0.20
    double m_queueHighThresh;  ///< 0.70  (Paper §4.3)
    double m_queueLowThresh;   ///< 0.30

    // ---- Weight presets (Paper §4.2 Table II) ------------------------------
    double m_w1Normal,   m_w2Normal,   m_w3Normal,   m_w4Normal;    // 0.40 0.30 0.10 0.20
    double m_w1LowE,     m_w2LowE,     m_w3LowE,     m_w4LowE;      // 0.20 0.10 0.50 0.20
    double m_w1HiLoad,   m_w2HiLoad,   m_w3HiLoad,   m_w4HiLoad;    // 0.30 0.20 0.10 0.40
    double m_w1Combined, m_w2Combined, m_w3Combined, m_w4Combined;  // computed

    mutable std::deque<Time>   m_seqEvents;
    Ptr<UniformRandomVariable> m_uniform;

    /// Per-neighbor RERR-based congestion score in [0,1].
    /// Key = neighbor address; value decays over time, bumped on each RERR.
    std::map<Ipv4Address, double> m_neighborCongestion;
};

} // namespace qsaqmaodv
} // namespace ns3

#endif /* QSAQMAODV_QTABLE_H */
