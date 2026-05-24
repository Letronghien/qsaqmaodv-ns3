# QS-QMAODV — Queue-State Self-Adaptive Q-Learning Multipath AODV

[![NS-3](https://img.shields.io/badge/NS--3-3.40-blue)](https://www.nsnam.org/)
[![Status](https://img.shields.io/badge/status-in--development-yellow)]()
[![Based on](https://img.shields.io/badge/extends-SA--QMAODV-green)]()

## Tóm tắt

**QS-QMAODV** (Queue-State Self-Adaptive Q-learning Multipath AODV) mở rộng SA-QMAODV bằng cách
bổ sung **thành phần thứ tư vào hàm phần thưởng**: trạng thái hàng đợi tại next-hop (queue occupancy).

Cải tiến cốt lõi: Q-learning hiện tại của SA-QMAODV chỉ quan tâm đến độ trễ end-to-end, tỷ lệ
nhận ACK và năng lượng — nhưng **không nhận biết tắc nghẽn cục bộ** tại next-hop. QS-QMAODV thêm
một tín hiệu feedback về queue-state, giúp giao thức tránh các next-hop đang bị nghẽn.

### So sánh hàm phần thưởng

| Giao thức    | Hàm phần thưởng |
|---|---|
| SA-QMAODV    | `r = w1·ACK + w2·1/(delay+1) + w3·Energy` |
| **QS-QMAODV**| `r = w1·ACK + w2·1/(delay+1) + w3·Energy + w4·1/(queue+1)` |

### Cơ chế thích nghi mới — High-Load Mode

```
Queue ratio > QueueHighThresh  →  HIGH_LOAD:  w4 tăng mạnh (queue dominate)
Queue ratio < QueueLowThresh   →  NORMAL:     trọng số bình thường
```

Tương tự Low-Energy Mode trong SA-QMAODV nhưng dành cho tình huống tắc nghẽn.

### Cảm hứng từ

- **QL-AODV** (Future Internet 2025): dùng buffer-state làm thành phần reward
- **AQR-FANET** (2024): anticipatory reward với queue prediction
- QS-QMAODV đơn giản hóa: dùng **queue occupancy trực tiếp** (không cần prediction)

---

## Cấu trúc project

```
paper2-qsaqmaodv/
├── README.md                          # File này
├── PAPER-OUTLINE.md                   # Cấu trúc bài báo
├── files/
│   ├── qsaqmaodv-qtable.h             # Extended QTable với 4-term reward
│   └── qsaqmaodv-qtable.cc            # Implementation
├── scripts/
│   ├── patches/
│   │   ├── apply-qsaqmaodv-all.sh
│   │   ├── apply-qsaqmaodv-module.py
│   │   └── apply-qsaqmaodv-fanet.py
│   ├── run/
│   │   └── run-paper2-experiments.sh
│   └── plot/
│       └── plot-paper2.py
└── notes/
    └── implementation-guide.md
```

## Base project

Kế thừa từ: `../` (saqmaodv-ns3) — reuse toàn bộ setup SA-QMAODV.
Module `qsaqmaodv` thay thế `saqmaodv`, chỉ thay đổi Q-table và reward function.

## Setup

```bash
# Sau khi đã setup saqmaodv-ns3 thành công:
cd paper2-qsaqmaodv
bash scripts/patches/apply-qsaqmaodv-all.sh
# Build lại NS-3
cd $NS3_DIR && ./ns3 build
```

## Experiments

```bash
bash scripts/run/run-paper2-experiments.sh
```

## Target venue

IEEE Communications Letters / Sensors (MDPI) / Ad Hoc Networks — 2026
