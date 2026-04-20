# NR PHY Simulator V2 Backlog

## 1. Purpose

This backlog converts the V2 architecture into an execution plan. It is organized by epics and uses acceptance-oriented language so the project can move from a teaching-oriented SISO simulator to a more realistic NR PHY simulator.

## 2. Delivery Strategy

The backlog is intentionally phased:

- finish the backbone before adding visible MIMO features
- finish standard-faithful SISO before scaling to SU-MIMO
- finish SU-MIMO before attempting MU-MIMO or massive MIMO

That order is mandatory if technical debt is to remain bounded.

## 3. Epic Map

| Epic | Goal | Outcome |
| --- | --- | --- |
| `P0` | Refactor backbone | tensor-aware PHY interfaces |
| `P1` | Standard-faithful SISO | realistic DL/UL base chain |
| `P2` | SU-MIMO | 2x2 and 4x4 single-user MIMO |
| `P3` | HARQ + CSI coupling | link adaptation realism |
| `P4` | MU-MIMO / Massive MIMO | spatial multiplexing beyond single user |
| `P5` | FR2 / hybrid beamforming | beam-centric high-frequency realism |

## 4. Detailed Backlog

## P0. Backbone Refactor

### P0-1 Tensorized PHY state model

**Problem**

Current TX/RX/channel paths are single-stream abstractions.

**Work**

- define canonical tensor types for `codeword`, `layer`, `port`, `tx_ant`, `rx_ant`
- refactor TX/RX metadata objects to carry shapes and indexing domains
- standardize slot/frame bookkeeping for all runtime paths

**Target modules**

- `phy/types.py`
- `phy/context.py`
- `experiments/common.py`
- `phy/transmitter.py`
- `phy/receiver.py`

**Acceptance**

- a single runtime object can represent both SISO and MIMO without changing API shape
- GUI can query tensor dimensions from metadata without special casing SISO

### P0-2 Resource grid decomposition

**Work**

- split current grid into `layer grid`, `port grid`, and `rx grid`
- add explicit RE mask objects for data and each reference signal type
- separate mapping from extraction

**Acceptance**

- RE extraction becomes a first-class block
- grid inspection can be done at layer, port, and RX-antenna levels

### P0-3 Artifact contract

**Work**

- define a stable artifact schema for GUI and batch export
- make every stage declare `input_shape`, `output_shape`, `artifact_type`, `notes`

**Acceptance**

- GUI does not infer artifact meaning from ad hoc keys
- stage playback works for future MIMO blocks without custom patches

## P1. Standard-Faithful SISO

### P1-1 Coding pipeline upgrade

**Work**

- replace `LDPC-inspired` behavior with more standard-faithful LDPC pipeline
- replace `polar-like` behavior with more standard-faithful NR control coding
- add code block segmentation and code block CRC
- add explicit `rate recovery`
- expose `soft LLR before decoding`

**Acceptance**

- TX and RX each have explicit `CRC`, `segmentation`, `coding`, `rate matching`, `rate recovery`, `soft LLR` stages
- GUI shows all these blocks separately

### P1-2 Uplink completion

**Work**

- implement `PUSCH`
- implement `PUCCH` for ACK/CSI-style payloads
- implement `PRACH`
- add `transform precoding` for uplink where applicable

**Acceptance**

- repo supports both DL and UL link-level chains
- GUI can switch between DL and UL stage graphs

### P1-3 Reference signals expansion

**Work**

- retain `DM-RS`
- add `PT-RS`
- add `CSI-RS`
- add `SRS`
- strengthen `SSB/PBCH`

**Acceptance**

- grid visualizations can independently highlight each RS family
- channel estimation and CSI workflows can consume proper RS masks

### P1-4 Control procedures realism

**Work**

- improve `PDCCH`, `CORESET`, and `SearchSpace`
- add stronger `SSB/PBCH` path
- add random-access-oriented flow for `PRACH`

**Acceptance**

- control-side mapping is no longer treated as a thin data-path variant

## P2. SU-MIMO

### P2-1 Layer mapping

**Work**

- support `1-2 codewords`
- support `1-4 layers`
- add layer-domain artifacts

**Acceptance**

- simulator can emit and recover symbols per layer
- GUI shows per-layer constellation and occupancy

### P2-2 Precoding and port mapping

**Work**

- implement linear precoders
- support antenna-port mapping consistent with selected transmission mode
- define initial codebook abstraction

**Acceptance**

- layer symbols are converted to port-domain grids through a documented precoder
- GUI can show per-port power and effective channel

### P2-3 MIMO channel and detection

**Work**

- introduce `H[rx,tx,symbol,subcarrier]`
- add `ZF`, `MMSE`, and `OSIC` detectors
- add post-detection layer recovery stage

**Acceptance**

- 2x2 and 4x4 SU-MIMO runs complete end-to-end
- detector choice changes observable performance and artifacts

### P2-4 CSI loop

**Work**

- add `CQI`, `PMI`, `RI`
- add Type-I single-panel codebook support
- connect CSI to MCS/layer/precoder selection

**Acceptance**

- batch runs can compare closed-loop and open-loop modes
- GUI shows CSI timeline and selected transmission state

## P3. HARQ and Minimal MAC Coupling

**Status:** complete at baseline level. The implementation is intentionally a link-level teaching/research model, not a full MAC scheduler or conformance-grade HARQ procedure.

### P3-1 HARQ process manager

**Status:** done.

**Work**

- model HARQ processes
- add RV sequence logic
- add soft combining buffer

**Acceptance**

- retransmissions improve BLER in expected conditions
- GUI shows HARQ process timeline and soft-buffer evolution

### P3-2 DCI-like scheduling abstraction

**Status:** done.

**Work**

- define a minimal scheduler-facing interface for DL/UL grants
- associate grants with codewords, layers, RV, and resource allocations

**Acceptance**

- PHY runs can replay a sequence of scheduled transmissions rather than isolated slots only

### P3-3 Coupled scheduler/HARQ replay

**Status:** done.

**Work**

- let DCI-like grants select `harq_process_id`, `NDI`, and `RV`
- expose scheduler and HARQ traces in the GUI `PHY Pipeline`
- add a coupled scenario for scheduler-driven retransmission observation

**Acceptance**

- configured grant sequences can drive HARQ process selection and retransmission RVs
- GUI shows both the grant timeline and HARQ process timeline

## P4. MU-MIMO and Massive MIMO

### P4-1 Array-aware channels

**Work**

- move from scalar TDL to TDL/CDL with array response
- add spatial correlation and spatial consistency
- add user-specific channels under shared array geometry

**Acceptance**

- channel generator emits user-dependent MIMO channel tensors

### P4-2 MU precoding and interference analysis

**Work**

- support user grouping
- support MU precoding
- expose interference matrix artifacts

**Acceptance**

- GUI shows inter-user coupling
- batch reports include sum-rate and fairness-oriented comparisons

### P4-3 Massive MIMO beam workflows

**Work**

- support `8T8R`, `16T16R`, `32T32R`, `64T64R`
- add CSI-RS beam sweep
- add TCI-state abstraction

**Acceptance**

- beam sweep and beam selection are visible and measurable in GUI and batch outputs

## P5. FR2 and Hybrid Beamforming

### P5-1 Panel and subarray modeling

**Work**

- model panels and subarrays
- distinguish digital and analog beamforming responsibilities

### P5-2 FR2-specific impairments

**Work**

- blockage
- beam failure recovery hooks
- stronger phase noise sensitivity
- PT-RS relevance in high-frequency scenarios

**Acceptance**

- FR2 scenarios produce meaningfully different behavior from FR1 scenarios

## 5. Cross-Cutting Workstreams

## X1. GUI Expansion

**Required additions**

- per-layer constellation
- per-port grid view
- CSI timeline
- beam heatmap
- HARQ process timeline
- detector diagnostics
- MU interference matrix

**Acceptance**

- every new PHY block has at least one meaningful visualization

## X2. Validation Harness

**Work**

- unit tests for invertible blocks
- golden-reference comparisons where practical
- regression suites for BLER-versus-SNR trends
- scenario packs for SISO, SU-MIMO, CSI, HARQ, and file transfer

**Acceptance**

- every epic ships with tests that prevent architectural regression

## X3. Performance and Acceleration

**Work**

- profile tensor-heavy paths
- isolate NumPy bottlenecks
- evaluate `PyTorch` or `JAX` backend for larger MIMO workloads

**Acceptance**

- project remains usable for interactive teaching mode even as fidelity rises

## 6. Prioritized First 12 Tasks

1. Introduce tensor-aware PHY type system
2. Split `ResourceGrid` into layer/port/RX views
3. Add explicit `Remove CP` stage
4. Add explicit `RE Extraction` stage
5. Add explicit `Rate Recovery` stage
6. Add explicit `Soft LLR` stage
7. Replace simplified coding path with more standard-faithful block structure
8. Add `HARQ soft buffer`
9. Add uplink `PUSCH` baseline
10. Add `Layer Mapping`
11. Add `Precoding`
12. Add `MIMO detector`

These are the first tasks that materially change the simulator from SISO teaching tool to realistic NR PHY foundation.

## 7. Definition of Done for V2.0

The project reaches `V2.0` only when:

- SISO is standard-faithful enough to support DL and UL consistently
- HARQ is implemented with soft combining
- SU-MIMO `2x2` and `4x4` are operational
- CSI (`CQI/PMI/RI`) affects transmission decisions
- GUI shows codeword/layer/port/array domains
- test suites lock down the new architecture

Before that point, the repository should be described as an evolving PHY research workbench, not as a realistic full NR PHY simulator.
