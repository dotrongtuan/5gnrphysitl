# 90-Minute Instructor Demo for 5G NR PHY STL

## Role of This Document

This document is the **instructor-led live demo script**.

It is intentionally different from:

- [TEACHING_LABS_6_SESSION_SERIES.md](TEACHING_LABS_6_SESSION_SERIES.md), which is the hands-on lab plan for students
- [TEACHING_LABS_MATRIX.md](TEACHING_LABS_MATRIX.md), which is the compact reference matrix

Use this file when you want to **present the project in one class meeting** without turning the session into a full lab.

## What This Project Can Reliably Demo Today

With the current codebase, this project is strongest for teaching:

- end-to-end 5G NR PHY link-level processing
- downlink vs uplink PHY roles
- `PDSCH`, `PDCCH/CORESET`, `PBCH/SSB`, `PRACH`
- `DM-RS`, `PT-RS`, `CSI-RS`, `SRS`
- synchronization, channel estimation, equalization, soft LLRs
- file transfer over PHY as an application-level outcome
- P3 baseline HARQ:
  - process state
  - `NDI`
  - `RV`
  - soft combining
  - DCI-like scheduler replay
  - `VRB -> PRB` resource allocation
- SU-MIMO baseline:
  - `1-2 codewords`
  - `1-4 layers`
  - `2x2` and `4x4`
  - `ZF`, `MMSE`, `OSIC`
  - `CQI / PMI / RI` baseline loop

It is **not** yet the right tool to claim:

- full MAC-layer HARQ conformance behavior
- MU-MIMO
- Massive MIMO
- beam management / TCI / beam failure recovery
- full MAC/RLC/RRC procedures

## Audience

Recommended for:

- undergraduate telecom / electronics students
- graduate PHY or wireless systems courses
- a first lecture introducing link-level 5G NR processing

## Demo Goal

At the end of 90 minutes, students should be able to:

- describe the PHY chain from bits to waveform and back
- explain the difference between data, control, broadcast, and random access
- read constellation, grid, channel, and LLR artifacts
- understand the difference between idealized and realistic receiver assumptions
- explain why HARQ and scheduler grants make PHY behavior multi-slot
- see why SU-MIMO adds `codeword -> layer -> port -> detector` domains

## Pre-Class Setup

Project root:

```powershell
cd <path-to-5gnr_phy_stl>
```

Replace `<path-to-5gnr_phy_stl>` with the local checkout path on the classroom machine.

Absolute-path examples:

- Windows: `D:\Projects\5gnr_phy_stl`
- Ubuntu/Linux: `/home/<user>/projects/5gnr_phy_stl`
- macOS: `/Users/<user>/projects/5gnr_phy_stl`

Recommended GUI launch:

```powershell
<radioconda-python> main.py --config configs/default.yaml --gui
```

`<radioconda-python>` means the `python.exe` inside your local Radioconda installation.

Explicit interpreter examples:

- Windows Radioconda: `C:\Users\<user>\AppData\Local\radioconda\python.exe`
- Ubuntu/Linux Conda environment: `/home/<user>/miniforge3/envs/5gnr-phy/bin/python`
- macOS Conda environment: `/Users/<user>/miniforge3/envs/5gnr-phy/bin/python`

Fallback if GNU Radio is not needed:

```powershell
.\.venv\Scripts\python.exe main.py --config configs/default.yaml --gui
```

## Demo Structure

| Segment | Time | Topic | Primary outcome |
| --- | --- | --- | --- |
| `D1` | `0-8 min` | Orientation | Students know what the project is and is not |
| `D2` | `8-25 min` | End-to-end PHY walk | Students understand the TX -> channel -> RX chain |
| `D3` | `25-40 min` | Grid and reference signals | Students see how NR occupies time-frequency resources |
| `D4` | `40-52 min` | Uplink, PRACH, PBCH | Students separate PHY roles clearly |
| `D5` | `52-65 min` | Realism and impairments | Students understand why receiver assumptions matter |
| `D6` | `65-78 min` | P3 HARQ and scheduler | Students see multi-slot retransmission and grant replay |
| `D7` | `78-90 min` | SU-MIMO and file-transfer outcome | Students connect PHY details to spatial processing and application success |

## D1. Orientation

### What to say

- This repository is a **software-only, link-level, visually inspectable NR PHY simulator**
- It is ideal for PHY teaching and debugging
- It is not a full 5G system simulator

### What to show

- GUI left panel
- central tabs
- right-hand KPI/status panel

### Key UI concepts

- `Run`: execute and inspect final outputs
- `Step Mode`: execute and jump into stage-by-stage PHY playback
- `Capture slots`: how many slots to retain for scrubbing

## D2. End-to-End PHY Walk

### Scenario

Use the default downlink data run.

### Suggested settings

- `Direction = downlink`
- `Mode = data`
- `Modulation = QPSK`
- `Channel model = awgn`
- `SNR = 20 dB`
- `Capture slots = 1`
- `Perfect sync = On`
- `Perfect CE = On`

### Instructor steps

1. Click `Step Mode`
2. Open `PHY Pipeline`
3. Walk students through:
   - `Traffic / transport block`
   - `TB CRC attachment`
   - `Code block segmentation + CB CRC`
   - `Channel coding`
   - `Rate matching`
   - `Scrambling`
   - `QAM mapping`
   - `Codeword Split`
   - `Layer Mapping`
   - `Precoding / Port Mapping`
   - `Resource Grid + RS`
   - `OFDM / IFFT + CP`
   - `Channel / Impairments`
   - `Timing / CFO correction`
   - `Remove CP`
   - `FFT`
   - `Resource element extraction`
   - `Channel estimation`
   - `Equalization`
   - `MIMO Detection`
   - `Layer Recovery / De-precoding`
   - `Soft demapping`
   - `Descrambling`
   - `Rate recovery`
   - `Soft LLR before decoding`
   - `Decoding`
   - `CRC check`

### Questions to ask

- Which stage first leaves the bit domain?
- Which stage first leaves the symbol domain?
- Why does the decoder consume soft information rather than just hard decisions?

## D3. Resource Grid and Reference Signals

### Goal

Show that 5G NR is not “just OFDM + QAM”; it is structured by **channels and reference signals**.

### Demo sequence

#### Downlink control

```powershell
python main.py --config configs/default.yaml --channel-type control --gui
```

Highlight:

- `CORESET / SearchSpace`
- control mapping vs data mapping

#### PBCH / SSB

```powershell
python main.py --config configs/default.yaml --override configs/scenario_pbch_baseline.yaml --gui
```

Highlight:

- `SSB / PBCH Broadcast Layout`
- `PSS`, `SSS`, `PBCH-DMRS`

#### Reference signals to mention

- `DM-RS`: main estimator input
- `CSI-RS`: sounding / CSI baseline
- `SRS`: uplink sounding
- `PT-RS`: phase-tracking baseline

### Student takeaway

Different PHY procedures occupy the grid differently and expose different pilot structures.

## D4. Uplink, PRACH, and PBCH Roles

### Uplink data

```powershell
python main.py --config configs/default.yaml --override configs/scenario_uplink_baseline.yaml --gui
```

Highlight:

- `PUSCH-style` path
- optional `Transform precoding`

### Uplink control

```powershell
python main.py --config configs/default.yaml --override configs/scenario_uplink_control_baseline.yaml --gui
```

Highlight:

- control payload path
- shorter payload and different coding assumptions

### PRACH

```powershell
python main.py --config configs/default.yaml --override configs/scenario_uplink_prach_baseline.yaml --gui
```

Highlight:

- preamble generation
- correlation detection
- random access is a detection problem, not a data-transfer problem

## D5. Realism and Impairments

### Goal

Show the difference between:

- ideal assumptions
- more realistic PHY behavior

### Suggested sequence

1. Run with:
   - `Perfect sync = On`
   - `Perfect CE = On`
2. Run again with both off
3. Increase:
   - `CFO`
   - `STO`
   - `phase noise`
4. Switch to a more challenging channel:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_vehicular.yaml --gui
```

### What to point out

- timing metric changes first
- channel estimate quality degrades
- constellation spreads after channel and before decoder failure
- LLR histogram becomes less confident before CRC failure

## D6. P3 HARQ and Scheduler Baseline

### Goal

Show that PHY behavior is not only a one-slot waveform problem. In practical NR operation, a scheduler chooses what to transmit, and HARQ controls retransmission attempts through process state, `NDI`, `RV`, and soft combining.

### HARQ baseline

Use:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_harq_baseline.yaml --gui
```

Focus on:

- `HARQ Process Timeline`
- RV sequence
- soft observations
- ACK/NACK
- `HARQ soft combining` stage after rate recovery

### DCI-like scheduler replay

Use:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_scheduler_grant_replay.yaml --gui
```

Focus on:

- `DCI-like Grant Timeline`
- scheduled modulation
- scheduled layers
- scheduled precoding mode
- allocated RE/PRB summary

### Coupled scheduler + HARQ

Use:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_p3_harq_scheduler_loop.yaml --gui
```

Focus on:

- two HARQ processes
- repeated `NDI`
- RV changes across retransmissions
- soft-buffer accumulation per process

### VRB to PRB resource allocation

In the GUI, set:

- `VRB map = interleaved`
- `BWP size PRB = 24`
- `Start VRB = 6`
- `VRB count = 4`

Then run the default GUI and inspect:

- `VRB -> PRB Mapping`
- `Resource Grid + RS`

Message to students:

- HARQ is the reliability bridge between PHY decoding and MAC retransmission control
- DCI-like grants are scheduling decisions, not modulation blocks
- VRB/PRB allocation decides where the payload can occupy the frequency grid
- this is still a P3 teaching baseline, not full MAC HARQ conformance

## D7. SU-MIMO and File-Transfer Outcome

### Part A. SU-MIMO baseline

Use:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_su_mimo_two_codeword.yaml --gui
```

Focus on:

- `Codeword Split`
- `Layer Mapping`
- `Precoding / Port Mapping`
- `MIMO Detection`
- `Layer Recovery / De-precoding`
- `CSI Feedback`

Message to students:

- SISO has one dominant logical stream
- SU-MIMO introduces `codeword`, `layer`, `port`, and detector structure

### Part B. File transfer as application outcome

Use:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_text_transfer.yaml --gui
python main.py --config configs/default.yaml --override configs/scenario_image_transfer.yaml --gui
```

Highlight:

- file packaging
- chunking
- PHY transport
- RX reconstruction

Message to students:

- BER/BLER are not abstract numbers only
- PHY degradation can directly decide whether an application payload is usable

## Recommended Questions for the Last 5 Minutes

- Which artifact best explains why a run passes or fails?
- Why is PBCH not “just another data channel”?
- Why does HARQ need both `process_id` and `NDI`?
- Why is `VRB -> PRB` a scheduler/resource-allocation concept rather than a QAM concept?
- Why can a large image fail even when many chunks decode correctly?
- Why does SU-MIMO require new domains beyond the classic SISO chain?

## Suggested Follow-Up

After this live demo, the natural next step is to assign:

- [TEACHING_LABS_6_SESSION_SERIES.md](TEACHING_LABS_6_SESSION_SERIES.md) for structured student labs
- [TEACHING_LABS_MATRIX.md](TEACHING_LABS_MATRIX.md) for quick lab lookup

## Instructor Notes

Keep the framing precise:

- say “SU-MIMO baseline” rather than “full real-world MIMO stack”
- say “software-only PHY simulator” rather than “complete 5G system”
- use the visual strengths of the repo instead of overselling unimplemented procedures
