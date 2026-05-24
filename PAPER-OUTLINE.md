# Paper 2 — QS-QMAODV: Outline

**Tên đề xuất:**
> "QS-QMAODV: Queue-State Aware Self-Adaptive Q-Learning Routing for Congestion-Resilient FANETs"

**Target:** IEEE Communications Letters / Sensors (MDPI) / Ad Hoc Networks

---

## Abstract (draft)

Q-learning routing protocols for FANETs optimize for delay and energy but
ignore local congestion at intermediate nodes. Under high traffic loads,
packet queues at next-hop nodes cause unpredictable delays that the Q-table
cannot capture from end-to-end feedback alone. We propose QS-QMAODV, which
extends SA-QMAODV with a four-term reward function incorporating queue-state
occupancy as a fourth feedback signal. A High-Load adaptive mode dynamically
amplifies the queue-state reward weight when congestion is detected. NS-3.40
simulations show QS-QMAODV achieves X% improvement in PDR and Y% reduction
in average delay under high traffic loads (pktInterval ≤ 0.1 s) compared to
SA-QMAODV, while maintaining comparable performance at low-to-medium loads.

---

## 1. Introduction

- FANET congestion challenge: UAV queues fill rapidly under high traffic
- Limitation of 3-term reward: delay measured end-to-end misses local bottlenecks
- Q-learning routing with queue feedback: prior work (QL-AODV, AQR-FANET)
- Contribution: minimal extension — one new reward term + one adaptive mode
- Seamless integration into SA-QMAODV framework

## 2. Related Work

### 2.1 Q-learning routing with local state
- QL-AODV (Future Internet 2025): buffer-state reward term
- AQR-FANET (2024): anticipatory queue reward with prediction
- QLR-FANET (2024): rate control loop with queue feedback

### 2.2 Congestion control in MANETs/FANETs
- Passive queue monitoring (ETX, WCETT variants)
- Cross-layer approaches

### 2.3 Gap
- Prior work uses complex queue models or prediction
- QS-QMAODV: direct queue occupancy, no prediction overhead
- Tight integration with SA adaptive mechanisms (vs. independent modules)

## 3. System Model

### 3.1 Network and traffic model
- 3D FANET, Gauss-Markov mobility
- CBR traffic, multiple flows
- Queue model: NS-3 DropTailQueue at each node

### 3.2 Queue-State as congestion indicator
- Queue occupancy ratio: q = current_size / max_size ∈ [0, 1]
- Why q is a better local indicator than end-to-end delay
- How to measure: next-hop queue depth from routing protocol context

### 3.3 Extended reward function
```
r = w1·ACK + w2·1/(delay+1) + w3·EnergyFrac + w4·1/(q+1)
```
- w4 penalizes congested next-hops
- Normalization: 1/(q+1) ∈ (0.5, 1] for q ∈ [0, 1]

## 4. QS-QMAODV Protocol Design

### 4.1 SA-QMAODV background (brief recap)
- Adaptive ε, α, reward weights (3-term)
- Two operating modes: Normal / Low-Energy

### 4.2 Queue-State Reward Term (core contribution)

**Definition:**
- q(h) = queue_occupancy(next_hop h) at time of ACK/timeout feedback
- Measured by cross-layer callback from NS-3 DropTailQueue

**Reward formula:**
```
r = w1·ACK + w2·1/(delay+1) + w3·EnergyFrac + w4·1/(q+1)
```

**Weight defaults:**
- Normal mode:    (w1=0.4, w2=0.3, w3=0.1, w4=0.2)
- Low-Energy:     (w1=0.2, w2=0.1, w3=0.5, w4=0.2)
- High-Load:      (w1=0.3, w2=0.2, w3=0.1, w4=0.4)  ← new mode

### 4.3 High-Load Adaptive Mode (second contribution)

**Trigger:** mean queue occupancy across recent routes > q_high_thresh (default 0.7)
**Action:** amplify w4 → High-Load preset
**Recovery:** mean q < q_low_thresh (default 0.3) → return to Normal

**Integration with SA mechanisms:**
- ε adaptation: bump on RERR still active (congestion ≡ implicit route failure)
- α adaptation: ΔSeq still drives α (topology change orthogonal to congestion)
- Low-Energy mode: if both low-energy AND high-load, use combined weights

### 4.4 Queue Measurement Architecture
- Routing protocol registers callback on DropTailQueue at next-hop NetDevice
- Callback fires on PacketDropped → updates per-next-hop q estimate
- Lightweight: O(1) per packet, no flooding of queue state

### 4.5 Complexity
- Memory: +1 float per next-hop entry in Q-table (negligible)
- CPU: +1 callback lookup per Q-update (O(1))
- No protocol overhead: queue info is local, not transmitted

## 5. Performance Evaluation

### 5.1 Simulation setup
- NS-3.40, Gauss-Markov 3D, IEEE 802.11
- Area: 1000×1000×300 m³
- Parameters: Table I

### 5.2 Protocols compared
| Protocol | Description |
|---|---|
| AODV | Baseline reactive |
| AOMDV-3 | Deterministic multipath |
| QMAODV-3 | Q-learning multipath |
| SAQMAODV-3 | Self-adaptive Q (prior work) |
| **QSAQMAODV-3** | **Proposed** |

### 5.3 Weight sensitivity (Family W)
- Sweep w4 ∈ {0.0, 0.1, 0.2, 0.3, 0.4} under high load
- Verify w4 > 0 consistently beats w4 = 0 (= SA-QMAODV)

### 5.4 Effect of traffic load (Family L) — key scenario
- pktInterval ∈ {1.0, 0.5, 0.25, 0.1, 0.05}
- Key result: QS-QMAODV should win where SA-QMAODV degrades (pkt ≤ 0.1)

### 5.5 Effect of node density (Family N)
- N ∈ {5, 10, 15, 20, 25, 30}
- Higher N → more flows → more congestion → larger QS gain

### 5.6 Effect of mobility (Family S)
- Speed ∈ {5, 15, 25, 50} m/s
- QS gain should be load-driven, speed-independent (unlike H-SAQMAODV)

### 5.7 Heterogeneous battery (Family E)
- E0 ∈ {10, 20, 30, 50} J
- QS-QMAODV inherits Low-Energy mode; should match SA-QMAODV

### 5.8 Queue distribution analysis
- Mean queue occupancy over time for each protocol
- Show QS-QMAODV actively avoids high-queue next-hops

### 5.9 Discussion
- Orthogonality with H-SAQMAODV: can combine (Paper 3?)
- Overhead analysis: queue callback cost
- Limitations: requires queue depth access (routing-MAC coupling)

## 6. Conclusion

- 4-term reward with queue state: simple but effective
- High-Load mode: second adaptive mechanism complements Low-Energy
- Future: combine with H-SAQMAODV topology-switching (Paper 3)

---

## Key Figures (planned)

1. Fig 1: System architecture — reward components + High-Load mode FSM
2. Fig 2: Weight sensitivity (w4 sweep, PDR vs w4 at pktInterval=0.1)
3. Fig 3: PDR vs Traffic Load — all protocols
4. Fig 4: Average Delay vs Traffic Load
5. Fig 5: PDR vs N (high load scenario)
6. Fig 6: Queue occupancy distribution comparison (CDF or time-series)
7. Fig 7: PDR vs E0 (verify energy-aware behaviour preserved)

---

## Key Tables

- Table I: Simulation parameters
- Table II: Reward weight configurations per mode
- Table III: Protocol comparison summary (PDR, delay, overhead)
