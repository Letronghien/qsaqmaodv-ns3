# QS-QMAODV Paper Outline
## "QS-QMAODV: A Queue-State-Aware Self-Adaptive Q-Learning Routing Protocol for FANETs"

*Style: IEEE conference (như PMAODV / QMAODV của nhóm)*
*Target: ICIT 2026 hoặc IEEE Access / Ad Hoc Networks*
*Protocols so sánh: AODV · PMAODV · QMAODV · QS-QMAODV*

---

## I. INTRODUCTION (~1 trang)

**¶1 — Bối cảnh FANET**
- UAV ngày càng được triển khai rộng: giám sát, cứu nạn, smart agriculture, IoT trên không
- Topology thay đổi liên tục (high mobility), năng lượng pin hạn chế, link failure thường xuyên
- Routing là nút cổ chai: quyết định chất lượng PDR, delay, network lifetime

**¶2 — Hành trình tiến hóa giao thức (câu chuyện dẫn dắt)**
- **AODV**: nền tảng reactive, đơn đường — không tối ưu trong môi trường động cao
- **PMAODV**: đa đường giảm re-discovery overhead — nhưng chọn đường theo hop-count, không học từ trải nghiệm
- **QMAODV**: bước đột phá — Q-learning 2-term (ACK + delay) để đánh giá chất lượng đường — nhưng bỏ qua năng lượng và trạng thái tải mạng
- **Gap còn lại**: (i) trọng số reward cố định không thích ứng, (ii) không xét năng lượng residual, (iii) không xét congestion — dẫn đến routing vào các node đang quá tải

**¶3 — Phân tích các nghiên cứu Q-learning liên quan**
- QL-AODV (Future Internet 2025): thêm buffer-state vào reward — dùng global buffer occupancy, trọng số tĩnh
- AQR-FANET (2024): anticipatory queue reward — không adaptive weights, không per-neighbor
- **Nhận xét chung**: các công trình hiện tại hoặc dùng global buffer (không phân biệt next-hop), hoặc dùng trọng số cố định — chưa giải quyết đồng thời cả hai

**¶4 — Đóng góp**
1. **4-term reward**: r = w1·ACK + w2·1/(d+1) + w3·E + w4·1/(q+1) — tích hợp đầy đủ delivery, delay, energy, queue
2. **Per-neighbor RERR congestion score**: proxy động cho trạng thái tải từng next-hop (thay vì global buffer), đảm bảo w4 thực sự phân biệt route
3. **4-mode Self-Adaptive FSM**: tự động điều chỉnh (w1,w2,w3,w4) theo trạng thái năng lượng + tải mạng — NORMAL / LOW_ENERGY / HIGH_LOAD / LOAD_COMBINED
4. Đánh giá trên NS-3.40: 5 sweeps tham số, so sánh AODV / PMAODV / QMAODV / QS-QMAODV

---

## II. RELATED WORK (~1 trang)

**A. Reactive Routing cho FANETs**
- AODV [RFC 3561]: on-demand RREQ/RREP/RERR, single-path
- PMAODV [nhóm tác giả]: multipath extension — giảm route discovery, cân bằng tải theo hop-count
- Hạn chế chung: không học từ kinh nghiệm mạng, không xét energy/congestion

**B. Q-Learning Routing — Phân tích chi tiết**

*B1. Reward function design*
- QMAODV [nhóm tác giả]: r = w1·ACK + w2·1/(d+1) — 2-term, hiệu quả nhưng chưa đủ tín hiệu
- QL-AODV [Future Internet 2025]: thêm buffer-state — r = f(ACK, delay, buffer_ratio) — trọng số tĩnh, buffer là global
- AQR-FANET [2024]: r = f(ACK, delay, anticipated_queue) — static weights

*B2. Adaptive weight mechanisms*
- Các công trình trên đều dùng trọng số cố định → không tối ưu khi điều kiện thay đổi (battery low ↔ high load)
- Một số công trình MANET dùng fuzzy weights — phức tạp, không lightweight

*B3. Queue/Congestion proxy*
- Global buffer occupancy (QL-AODV): m_queue.GetSize()/maxQueue — gần 0 trong steady-state → w_queue vô nghĩa
- **Vấn đề cốt lõi**: cần signal phân biệt được giữa các next-hop, không phải global signal

**Bảng I — So sánh các giao thức (Table I)**:

| Protocol | Multi-path | Q-learning | Energy | Queue-aware | Adaptive-W | Per-neighbor |
|----------|:---:|:---:|:---:|:---:|:---:|:---:|
| AODV | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| PMAODV | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| QMAODV | ✓ | ✓ (2-term) | ✗ | ✗ | ✗ | ✗ |
| QL-AODV | ✗ | ✓ (3-term) | ✗ | Global | ✗ | ✗ |
| AQR-FANET | ✓ | ✓ (3-term) | ✗ | Global | ✗ | ✗ |
| **QS-QMAODV** | ✓ | ✓ **(4-term)** | ✓ | **Per-neighbor** | ✓ **(4-mode)** | ✓ |

---

## III. SYSTEM MODEL & PROBLEM FORMULATION (~0.5 trang)

**A. Network Model**
- N UAV nodes di chuyển theo Gauss-Markov mobility (tham số: meanVelMin, meanVelMax, α_GM)
- IEEE 802.11b, 2 Mbps, ad hoc mode, omni-directional
- CBR/UDP traffic, single-source multi-sink
- Energy model: tuyến tính (P_tx, P_rx, P_idle) — node "dead" khi E < threshold

**B. Q-Learning Framework**
- State: (source_node, destination) — implicit qua routing table
- Action: chọn next-hop từ tập multipath candidates
- Reward: r_t (Eq. 1 bên dưới)
- Q-value update: Q(s,a) ← (1−α)·Q(s,a) + α·[r_t + γ·max Q(s',a')]
- Selection: ε-greedy trên tập candidates

**C. Bài toán tối ưu hóa**
Mục tiêu: tối đa hóa tổng reward kỳ vọng:
```
J = E[Σ γ^t · r_t]
với r_t = w1·ACK_t + w2·1/(d_t+1) + w3·E_t + w4·1/(q_t+1)
và  w1+w2+w3+w4 = 1, w_i ≥ 0
```

Thách thức: w* tối ưu phụ thuộc vào trạng thái mạng (energy, load) — cần **adaptive weights**

---

## IV. QS-QMAODV DESIGN (~2 trang) ← **PHẦN CHÍNH**

**A. 4-Term Reward Function**

```
r_t = w1·ACK + w2·1/(d+1) + w3·E_frac + w4·1/(q+1)       (Eq. 1)
```

| Term | Signal | Ý nghĩa |
|------|--------|---------|
| w1·ACK | Binary (0/1) | Xác nhận delivery thực tế |
| w2·1/(d+1) | d = delay (s) | Ưu tiên path có trễ thấp |
| w3·E_frac | ∈ [0,1] | Ưu tiên node còn nhiều năng lượng |
| w4·1/(q+1) | q ∈ [0,1] | Tránh next-hop đang bị congested |

**Tại sao cần cả 4 term?**
- Bỏ w3: route vào node sắp cạn pin → link failure tăng đột biến cuối sim
- Bỏ w4: route vào congested node → tăng delay, tăng drop → PDR giảm ở tải cao
- Chỉ w4 không đủ: cần adaptive weights để ưu tiên đúng term theo điều kiện thực tế

**B. Per-Neighbor RERR Congestion Score** ← *Đóng góp kỹ thuật cốt lõi*

*Vấn đề với global buffer occupancy:*
- Trong FANETs, RREQ buffer (m_queue) gần như luôn trống trong steady-state
- q = m_queue.GetSize() / maxQueueLen ≈ 0 cho mọi node
- → 1/(q+1) ≈ 1.0 cho mọi next-hop → w4 không phân biệt được route

*Giải pháp: RERR làm congestion proxy*

Khi node X gửi RERR về next-hop v (do link failure hoặc queue overflow):
```
congestion[v] ← min(1.0, congestion[v] + δ)    δ = 0.25       (Eq. 2)
```

Mỗi periodic tick (ε-decay period):
```
congestion[v] ← λ_decay · congestion[v]         λ = 0.90       (Eq. 3)
// Xóa entry khi congestion[v] < 0.01 (tránh map bloat)
```

Trong UpdateQValue(dst, next_hop, ...):
```
if congestion[next_hop] exists:
    q ← congestion[next_hop]    // override global buffer
else:
    q ← GetQueueOccupancy()     // fallback
```

**Tại sao RERR là proxy tốt cho congestion?**
- RERR được gửi khi link fail hoặc node overloaded — đây chính là dấu hiệu congestion
- Per-neighbor: mỗi next-hop có score riêng → Q-learning phân biệt được route
- Exponential decay: congestion cũ mờ dần (half-life ≈ 6.6 ticks) → thích ứng với cải thiện mạng
- δ=0.25: sau 4 RERR liên tiếp → congestion = 1.0 (saturate), tránh chọn node đó

**C. 4-Mode Self-Adaptive FSM**

*Motivation*: NORMAL weights tối ưu cho môi trường cân bằng, nhưng:
- Khi E_frac < 0.20: ưu tiên tiết kiệm năng lượng (w3 ↑)
- Khi q_ratio > 0.70: ưu tiên tránh congestion (w4 ↑)
- Khi cả hai: cân bằng cả hai ràng buộc

**Bảng II — Weight Presets (Paper Table II):**

| Mode | Condition | w1 | w2 | w3 | w4 | Tổng |
|------|-----------|:---:|:---:|:---:|:---:|:---:|
| NORMAL | Default | 0.40 | 0.30 | 0.10 | 0.20 | 1.00 |
| LOW_ENERGY | E < 0.20 | 0.20 | 0.10 | 0.50 | 0.20 | 1.00 |
| HIGH_LOAD | q > 0.70 | 0.30 | 0.20 | 0.10 | 0.40 | 1.00 |
| LOAD_COMBINED | cả hai | 0.25 | 0.15 | 0.30 | 0.30 | 1.00 |

**FSM Transitions (Fig. 1):**
```
NORMAL ──(E<0.20)──→ LOW_ENERGY
NORMAL ──(q>0.70)──→ HIGH_LOAD
LOW_ENERGY ──(q>0.70)──→ LOAD_COMBINED
HIGH_LOAD  ──(E<0.20)──→ LOAD_COMBINED
LOAD_COMBINED ──(E≥0.20 AND q<0.30)──→ NORMAL
HIGH_LOAD  ──(q<0.30)──→ NORMAL  [hysteresis]
```

**D. Adaptive Learning Parameters (kế thừa và mở rộng từ QMAODV)**

*Adaptive α via ΔSeq (sequence number velocity):*
```
α_t = 0.1 + 0.8·(1 − e^{−λ·ΔSeq})              (Eq. 4)
```
- ΔSeq = số seq-no updates trong cửa sổ W giây
- Topology thay đổi nhanh → ΔSeq cao → α_t cao → học nhanh hơn

*Adaptive ε (epsilon-bump on RERR):*
```
ε ← min(0.50, ε + 0.20)    // khi nhận RERR → tăng exploration
ε ← max(0.10, ε − 0.02)    // mỗi periodic tick → hội tụ dần
```

**E. Full Algorithm (Algorithm 1)**
```
OnDataPacketTx(dst):
  next_hop ← SelectEpsilonGreedy(candidates, ε)
  Forward(packet, next_hop)

OnACKReceived(dst, next_hop, delay):
  E_frac ← GetEnergyFraction()
  q      ← congestion[next_hop] or GetQueueOccupancy()
  r ← w1·1 + w2·1/(delay+1) + w3·E_frac + w4·1/(q+1)
  UpdateQValue(dst, next_hop, r)
  RecomputeAdaptiveAlpha(ΔSeq)
  RecomputeAdaptiveWeights(E_frac, q_ratio)

OnTimeoutOrDrop(dst, next_hop):
  r ← w1·0 + w2·0 + w3·E_frac + w4·1/(q+1)
  UpdateQValue(dst, next_hop, r)

OnRERR(src, breaking_hop):
  ε ← min(0.50, ε + 0.20)
  congestion[src]          ← min(1.0, congestion[src] + 0.25)
  congestion[breaking_hop] ← min(1.0, congestion[breaking_hop] + 0.25)

PeriodicTick():
  ε ← max(0.10, ε − 0.02)
  ∀v: congestion[v] ← 0.90·congestion[v]
  RecomputeAdaptiveWeights(E_frac, q_ratio)
```

---

## V. IMPLEMENTATION (~0.5 trang)

- **Platform**: NS-3.40, C++17, module `src/qsaqmaodv/`
- **Base**: kế thừa kiến trúc QMAODV (nhóm tác giả) — thêm QTable layer
- **Key files**:
  - `qsaqmaodv-qtable.h/.cc`: 4-term reward, per-neighbor congestion map, 4-mode FSM
  - `qsaqmaodv-routing-protocol.h/.cc`: NS-3 attributes, hook points
- **Attributes NS-3** (có thể override qua command line):
  - `RewardW4` (default 0.20), `QueueHighThreshold` (0.70), `QueueLowThreshold` (0.30)
  - `LowEnergyThreshold` (0.20), `SensitivityLambda` (0.10)
- **Hook points trong routing-protocol.cc**:
  - `RecvError(src)` → `RecordNeighborRerr(src)`
  - `SendRerrWhenBreaksLinkToNextHop(nextHop)` → `RecordNeighborRerr(nextHop)`
  - `PeriodicAdaptiveTick()` → `DecayNeighborCongestion(0.90)`
- **Overhead bổ sung**: `std::map<Ipv4Address, double>` O(|neighbors|) — negligible

---

## VI. PERFORMANCE EVALUATION (~2 trang)

**A. Simulation Setup**

**Bảng III — Simulation Parameters:**

| Parameter | Value |
|-----------|-------|
| Simulator | NS-3.40 |
| MAC/PHY | IEEE 802.11b, 2 Mbps |
| Mobility | Gauss-Markov |
| Simulation area | 1000×1000 m |
| Baseline nodes | 15 |
| Baseline speed | 10–25 m/s |
| Traffic | CBR/UDP, interval=0.25s, 512B |
| Energy model | Linear, E₀=50J |
| **Protocols** | **AODV, PMAODV, QMAODV, QS-QMAODV** |
| Seeds/scenario | 3 |
| Simulation time | 100s |

**Metrics**: PDR (%), E2E Delay (ms), Throughput (Mbps), Routing Overhead (#pkts), Residual Energy (J)

**B. Family N — Node Density (Fig. 2)**
- Sweep: N ∈ {5, 8, 10, 12, 15, 18, 20, 25, 30}
- Giả thuyết: QS-QMAODV > QMAODV rõ rệt ở N ≥ 18 (congestion tăng → RERR nhiều hơn → w4 có tác dụng)
- PMAODV tốt hơn AODV nhưng không bằng QMAODV ở N cao

**C. Family S — UAV Speed (Fig. 3)**
- Sweep: v ∈ {5, 10, 20, 30, 50, 70} m/s
- Giả thuyết: v cao → nhiều link failure → nhiều RERR → congestion map active → QS-QMAODV duy trì PDR tốt hơn
- Ở v thấp (≤10): cả 4 giao thức tương đương

**D. Family L — Traffic Load (Fig. 4)**
- Sweep: pktInterval ∈ {1.0, 0.5, 0.25, 0.1, 0.05} (= 1→20 pps)
- Giả thuyết: HIGH_LOAD mode kích hoạt ở tải cao (≥10 pps) → w4↑ → tránh congested node → PDR gap lớn nhất ở đây
- Delay: QS-QMAODV thấp hơn QMAODV ở tải cao

**E. Family E — Initial Energy (Fig. 5)**
- Sweep: E₀ ∈ {20, 30, 50, 70, 100} J
- Giả thuyết: LOW_ENERGY mode ở E₀=20J → w3↑ → kéo dài network lifetime
- Residual energy QS-QMAODV > QMAODV ở E₀ thấp

**F. Family W — w4 Sensitivity Analysis (Fig. 6)** ← *Duy nhất trong paper*
- Sweep: w4 ∈ {0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50}
  - w1 = 0.60−w4 (giữ w2=0.30, w3=0.10, tổng=1)
- Mục đích: xác nhận w4=0.20 là optimal cho NORMAL preset
- w4=0: QS-QMAODV = QMAODV (baseline)
- w4>0.40: quá emphasis vào congestion avoidance → PDR giảm

**G. Routing Overhead (Fig. 7)**
- QS-QMAODV ≈ QMAODV (cùng multipath, không tăng control packets)
- PMAODV < QMAODV (ít re-discovery hơn nhờ multipath nhưng không có Q-learning)

**H. Discussion — Tổng hợp**
- **Khi nào QS-QMAODV thắng rõ nhất**: tải cao + mật độ cao + mobility cao — đúng với FANET thực tế
- **Per-neighbor RERR vs global buffer**: RERR xảy ra ~X lần/100s trong baseline → congestion map luôn có dữ liệu thực
- **4-mode FSM**: chứng minh qua Family E (LOW_ENERGY) và Family L (HIGH_LOAD) — không thể đạt bằng fixed weights
- **Overhead**: thêm map O(|neighbors|) ≈ 15 entries — negligible so với routing table

---

## VII. CONCLUSION (~0.3 trang)

QS-QMAODV đề xuất ba đóng góp chính:
1. Mở rộng Q-learning routing 4-term tích hợp queue-state awareness
2. Per-neighbor RERR congestion proxy giải quyết vấn đề global buffer = 0
3. 4-mode self-adaptive FSM cân bằng năng lượng và tải mạng đồng thời

Kết quả NS-3.40 cho thấy QS-QMAODV cải thiện PDR lên đến **X%** so với QMAODV ở tải cao, giảm delay **Y%**, và kéo dài network lifetime **Z%** trong môi trường năng lượng hạn chế.

**Future work**: deep Q-network (DQN) thay Q-table cho không gian state lớn; multi-objective Pareto optimization; thực nghiệm trên UAV thực.

---

## REFERENCES (~18 tài liệu)

1. AODV — Perkins et al., RFC 3561, 2003
2. PMAODV — [nhóm tác giả], IEEE ...
3. QMAODV — [nhóm tác giả], IEEE ...
4. QL-AODV — Future Internet 2025
5. AQR-FANET — 2024
6. Q-learning — Watkins & Dayan, 1992
7. Gauss-Markov mobility — Liang & Haas, 1999
8. NS-3 — Henderson et al.
9. FANET survey — Bekmezci et al., 2013
10. UAV routing survey — Chriki et al., 2019
11. Energy-aware MANET routing — 2020
12. Congestion control MANET — 2021
13. IEEE 802.11 standard
14. Multi-path routing MANET — 2018
15. Q-routing — Boyan & Littman, 1994
16. Reinforcement learning routing survey — 2022
17. RERR-based congestion detection — 2019
18. Adaptive weight RL routing — 2023

---

## FIGURES

1. **Fig. 1**: 4-mode FSM transition diagram
2. **Fig. 2**: PDR vs Node count (Family N)
3. **Fig. 3**: PDR & Overhead vs Speed (Family S)
4. **Fig. 4**: PDR & Delay vs Load (Family L)
5. **Fig. 5**: PDR & Residual Energy vs E₀ (Family E)
6. **Fig. 6**: PDR vs w4 weight (Family W — sensitivity)
7. **Fig. 7**: Routing overhead vs Node count

## TABLES

1. **Table I**: Protocol comparison (related work)
2. **Table II**: 4-mode weight presets
3. **Table III**: Simulation parameters
4. **Table IV**: Summary — peak PDR gain over QMAODV per family

---

## KEY EQUATIONS

```
(1)  r_t = w1·ACK + w2·1/(d+1) + w3·E_frac + w4·1/(q+1)

(2)  Q(s,a) ← (1−α_t)·Q(s,a) + α_t·[r_t + γ·max_a' Q(s',a')]

(3)  congestion[v] ← min(1.0, congestion[v] + δ)     on RERR from v
     congestion[v] ← λ · congestion[v]                periodic decay

(4)  α_t = 0.1 + 0.8·(1 − e^{−λ·ΔSeq})

(5)  ε ← min(0.50, ε + 0.20)    on RERR
     ε ← max(0.10, ε − 0.02)    periodic
```

---

*Ghi chú: Điền X%, Y%, Z% sau khi experiments hoàn tất.*
*Protocol evolution: AODV → PMAODV → QMAODV → QS-QMAODV*
*SA-QMAODV KHÔNG được nhắc đến trong paper này.*
