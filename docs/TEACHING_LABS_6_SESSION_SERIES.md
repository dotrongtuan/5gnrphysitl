# 6-Session Teaching Lab Series for 5G NR PHY STL

## Role of This Document

This document is the **student-facing lab sequence**.

It is intentionally different from:

- [TEACHING_DEMO_90_MINUTE.md](TEACHING_DEMO_90_MINUTE.md), which is the instructor-led live demo plan
- [TEACHING_LABS_MATRIX.md](TEACHING_LABS_MATRIX.md), which is the compact lab lookup sheet

Use this file when you want a **multi-week or multi-session lab progression** with deliverables and discussion prompts.

## What This Lab Series Is Good For

This series is a good fit for teaching:

- link-level PHY processing
- resource grid and reference-signal reasoning
- downlink vs uplink behavior
- synchronization and channel-estimation sensitivity
- PRACH and PBCH roles
- file transfer over PHY
- P3 baseline HARQ and DCI-like scheduler replay
- SU-MIMO baseline and CSI loop concepts

It is not designed to teach:

- full MAC-layer HARQ conformance behavior
- MU-MIMO scheduling
- Massive MIMO beam management
- complete 5G protocol stack procedures

## Common Setup

Project root:

```powershell
cd <path-to-5gnr_phy_stl>
```

Replace `<path-to-5gnr_phy_stl>` with the local checkout path on the student machine.

Absolute-path examples:

- Windows: `D:\Projects\5gnr_phy_stl`
- Ubuntu/Linux: `/home/<user>/projects/5gnr_phy_stl`
- macOS: `/Users/<user>/projects/5gnr_phy_stl`

Recommended GUI launch:

```powershell
<radioconda-python> main.py --config configs/default.yaml --gui
```

`<radioconda-python>` means the `python.exe` inside the local Radioconda installation.

Explicit interpreter examples:

- Windows Radioconda: `C:\Users\<user>\AppData\Local\radioconda\python.exe`
- Ubuntu/Linux Conda environment: `/home/<user>/miniforge3/envs/5gnr-phy/bin/python`
- macOS Conda environment: `/Users/<user>/miniforge3/envs/5gnr-phy/bin/python`

Fallback without GNU Radio:

```powershell
.\.venv\Scripts\python.exe main.py --config configs/default.yaml --gui
```

## Suggested Sequence

| Session | Theme | Main output |
| --- | --- | --- |
| `L1` | End-to-end PHY chain | stage/domain map |
| `L2` | Resource grid and reference signals | annotated grid comparison |
| `L3` | Uplink, PRACH, PBCH | role comparison sheet |
| `L4` | Receiver realism and impairments | degradation analysis |
| `L5` | File transfer over PHY | file success vs SNR study |
| `L6` | SU-MIMO and CSI baseline | spatial-domain analysis report |

Optional extension after `L5` or `L6`: `P3 HARQ and scheduler baseline`, when the course needs to connect PHY decoding quality to retransmission and grant control.

---

## Lab 1. End-to-End PHY Chain

### Objective

- identify the main TX, channel, and RX stages
- understand how data changes domain:
  - bits
  - symbols
  - grid
  - waveform
  - soft information

### Run

```powershell
python main.py --config configs/default.yaml --gui
```

### GUI Settings

- `Direction = downlink`
- `Mode = data`
- `Modulation = QPSK`
- `Channel model = awgn`
- `SNR = 20 dB`
- `Capture slots = 1`
- `Perfect sync = On`
- `Perfect CE = On`

### Student Tasks

1. Click `Step Mode`
2. Walk through the `PHY Pipeline`
3. Record at least 10 stages
4. For each selected stage, state:
   - input domain
   - output domain
   - purpose

### Expected Outcome

- `BER = 0`
- `BLER = 0`
- clean post-EQ constellation
- all major stages visible in order

### Deliverable

A table with columns:

- `Stage`
- `Input domain`
- `Output domain`
- `Purpose`

### Discussion Prompt

Why is `Soft LLR before decoding` more informative than just checking the final CRC?

---

## Lab 2. Resource Grid and Reference Signals

### Objective

- compare `data`, `control`, and `broadcast` mapping
- identify where `DM-RS`, `PT-RS`, `CSI-RS`, `SRS`, and `PBCH-DMRS` appear

### Runs

Downlink control:

```powershell
python main.py --config configs/default.yaml --channel-type control --gui
```

PBCH / SSB:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_pbch_baseline.yaml --gui
```

Uplink data:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_uplink_baseline.yaml --gui
```

### Student Tasks

1. Capture one allocation map for:
   - downlink data
   - downlink control
   - PBCH / SSB
2. Mark which RE regions correspond to:
   - payload
   - control
   - broadcast
   - reference signals
3. State why `SRS` only appears in uplink data runs

### Expected Outcome

- control shows `CORESET / SearchSpace`
- PBCH is confined to the `SSB` region
- `CSI-RS` appears in downlink sounding contexts
- `SRS` appears in uplink data contexts

### Deliverable

- 3 screenshots
- 1 comparison table of reference-signal families

### Discussion Prompt

Why is `DM-RS` the main estimator input while `CSI-RS` and `SRS` play different roles?

---

## Lab 3. Uplink, PRACH, and PBCH Roles

### Objective

- distinguish:
  - `PUSCH-style`
  - `PUCCH-style`
  - `PRACH`
  - `PBCH`

### Runs

```powershell
python main.py --config configs/default.yaml --override configs/scenario_uplink_baseline.yaml --gui
python main.py --config configs/default.yaml --override configs/scenario_uplink_control_baseline.yaml --gui
python main.py --config configs/default.yaml --override configs/scenario_uplink_prach_baseline.yaml --gui
python main.py --config configs/default.yaml --override configs/scenario_pbch_baseline.yaml --gui
```

### Student Tasks

1. Identify one stage unique to PRACH
2. Identify one stage unique to PBCH / SSB
3. Explain why PRACH is not a normal data-transport chain
4. If enabled, compare uplink with and without `Transform precoding`

### Expected Outcome

- PRACH uses correlation-based detection logic
- PBCH is tied to a broadcast region
- uplink data and uplink control are not identical paths

### Deliverable

A one-page comparison:

- `PUSCH`
- `PUCCH`
- `PRACH`
- `PBCH`

### Discussion Prompt

Why is broadcast treated differently from scheduled data?

---

## Lab 4. Receiver Realism and Impairments

### Objective

- show how ideal assumptions hide difficulty
- explain how impairments propagate through the PHY chain

### Runs

Default GUI:

```powershell
python main.py --config configs/default.yaml --gui
```

Vehicular case:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_vehicular.yaml --gui
```

Batch impairment sweep:

```powershell
python run_experiments.py --experiment impairment_sweep --config configs/default.yaml --output-dir outputs
```

### Student Tasks

1. Run once with:
   - `Perfect sync = On`
   - `Perfect CE = On`
2. Run again with both off
3. Increase:
   - `CFO`
   - `STO`
   - `phase noise`
4. Compare to the vehicular channel case
5. Record which artifact degrades first

### Expected Outcome

- timing and CFO traces degrade before final failure
- channel-estimate quality affects EQ quality
- LLR confidence drops before CRC failure

### Deliverable

A table:

- `Condition`
- `First visibly degraded artifact`
- `Final KPI impact`

### Discussion Prompt

Why can two runs have similar constellations but very different decoder reliability?

---

## Lab 5. File Transfer Over PHY

### Objective

- connect link-level PHY behavior to application-level success
- compare a small text file and a larger image file

### Runs

GUI:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_text_transfer.yaml --gui
python main.py --config configs/default.yaml --override configs/scenario_image_transfer.yaml --gui
```

CLI:

```powershell
python main.py --config configs/default.yaml --tx-file input/sample_message.txt --rx-output-dir outputs/rx_files
python main.py --config configs/default.yaml --tx-file input/sample_image.png --rx-output-dir outputs/rx_files
```

### Student Tasks

1. Run text at high SNR
2. Run image at high SNR
3. Lower SNR step by step
4. Disable `Perfect sync` and `Perfect CE`
5. Record:
   - total chunks
   - chunks failed
   - whether the RX file is written

### Expected Outcome

- text survives lower SNR more easily
- image is more fragile because it spans more chunks
- one bad chunk can block successful reconstruction

### Deliverable

A plot or table:

- `File type`
- `SNR`
- `Success / fail`
- `chunks_failed`

### Discussion Prompt

Why is file transfer behavior effectively “all or nothing” in the current implementation?

---

## Lab 6. SU-MIMO and CSI Baseline

### Objective

- introduce spatial domains beyond SISO
- show the role of:
  - `codeword`
  - `layer`
  - `port`
  - `MIMO detector`
  - `CSI feedback`

### Runs

Two-codeword SU-MIMO GUI:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_su_mimo_two_codeword.yaml --gui
```

CSI loop batch:

```powershell
python run_experiments.py --experiment csi_loop_compare --config configs/default.yaml --override configs/scenario_su_mimo_csi_loop.yaml --output-dir outputs
```

### Student Tasks

1. Inspect:
   - `Codeword Split`
   - `Layer Mapping`
   - `Precoding / Port Mapping`
   - `MIMO Detection`
   - `Layer Recovery / De-precoding`
   - `CSI Feedback`
2. Identify the selected:
   - `RI`
   - `PMI`
   - modulation
   - target rate
3. Compare open-loop vs closed-loop batch results

### Expected Outcome

- students see that SISO is not enough to explain MIMO processing
- CSI affects transmission-state selection
- detector choice and spatial structure become explicit artifacts

### Deliverable

A short technical note with:

- one annotated screenshot from `PHY Pipeline`
- one batch plot from `csi_loop_compare`
- one paragraph explaining `CQI / PMI / RI`

### Discussion Prompt

Why does SU-MIMO require separate codeword, layer, and port domains instead of only “more antennas”?

---

## Optional Extension Lab. P3 HARQ and DCI-like Scheduler

### Objective

- connect PHY decoding to retransmission behavior
- distinguish `HARQ process`, `NDI`, `RV`, `soft combining`, `DCI-like grant`, and `VRB -> PRB` resource allocation

### Runs

HARQ baseline:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_harq_baseline.yaml --gui
```

Scheduler replay:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_scheduler_grant_replay.yaml --gui
```

Coupled HARQ + scheduler:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_p3_harq_scheduler_loop.yaml --gui
```

### GUI Settings to Check

- `Capture slots >= 4`
- `Perfect sync = On`
- `Perfect CE = On`
- `PHY Pipeline` tab
- `DCI-like Grant Timeline`
- `HARQ Process Timeline`
- `VRB -> PRB Mapping`

### Student Tasks

1. In the HARQ baseline run, record the RV sequence across captured slots.
2. In the `HARQ Process Timeline`, record process ID, RV, NDI, new-data flag, soft observations, and ACK/NACK.
3. In the scheduler replay run, identify which fields change between grants: modulation, layers, precoding mode, and allocated RE/PRB count.
4. In the coupled run, explain why `process_id` and `NDI` are both needed.
5. Change GUI allocation fields to `VRB map = interleaved`, `BWP size PRB = 24`, `Start VRB = 6`, and `VRB count = 4`.
6. Inspect `VRB -> PRB Mapping` and explain how the allocation mask affects `Resource Grid + RS`.

### Expected Outcome

- HARQ retransmissions reuse the same payload when `NDI` does not toggle.
- RV changes across retransmission attempts.
- Soft observations accumulate in the HARQ process timeline.
- Scheduler grants can drive modulation, layers, precoding, HARQ process, RV, and resource allocation.
- VRB allocation visibly restricts the data/DMRS region in the resource grid.

### Deliverable

A two-page lab note:

- one table of `timeline_index`, `process_id`, `NDI`, `RV`, `new_data`, `soft_observations`, and `ACK`
- one screenshot of `DCI-like Grant Timeline`
- one screenshot of `HARQ Process Timeline`
- one screenshot of `VRB -> PRB Mapping`
- one paragraph explaining why this is still a baseline, not full MAC HARQ

### Discussion Prompt

Why is HARQ a bridge between PHY decoding quality and MAC scheduling behavior?

---

## Suggested Assessment Model

You can assess each lab with:

- `40%` correctness of observations
- `30%` interpretation quality
- `20%` use of artifact evidence
- `10%` clarity of reporting

## How This Series Avoids Overlap With the Demo Plan

- This file is for **student work and deliverables**
- [TEACHING_DEMO_90_MINUTE.md](TEACHING_DEMO_90_MINUTE.md) is for **instructor presentation flow**
- [TEACHING_LABS_MATRIX.md](TEACHING_LABS_MATRIX.md) remains the **quick lookup sheet**
