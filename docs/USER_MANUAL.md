# 5G NR PHY STL User Manual

## 1. Purpose

This manual explains how to install, run, and operate the project as of the current `main` branch.

The current scope is:

- software-only, link-level 5G NR PHY simulation
- visual introspection through a multi-panel GUI
- standard-faithful SISO baseline
- SU-MIMO baseline up to `2x2` and `4x4`
- CSI feedback baseline with `CQI / PMI / RI`
- `P3` HARQ and DCI-like scheduler baseline
- end-to-end file transfer over the PHY chain

The current scope does **not** include conformance-grade MAC `HARQ`, `MU-MIMO`, `Massive MIMO`, full beam management, or `FR2` hybrid beamforming. Those belong to later phases in the V2 roadmap.

## 2. System Overview

The project can be used in three operating styles:

1. `CLI single-run`
2. `GUI interactive exploration`
3. `Batch experiments`

At runtime, the main PHY chain is:

```mermaid
flowchart LR
    A["Payload / TB"] --> B["CRC + Segmentation + Coding"]
    B --> C["Rate Matching + Scrambling"]
    C --> D["QAM Mapping"]
    D --> E["Codeword -> Layer Mapping"]
    E --> F["Precoding / Port Mapping"]
    F --> G["VRB -> PRB Mapping"]
    G --> H["Resource Grid + RS"]
    H --> I["OFDM / CP"]
    I --> J["Channel + Impairments"]
    J --> K["Sync + Remove CP + FFT"]
    K --> L["RE Extraction + CE + EQ + MIMO Detection"]
    L --> M["Descrambling + Rate Recovery + Decode"]
    M --> N["CRC / KPIs / GUI Artifacts"]
```

## 3. Supported Feature Set

### 3.1 PHY Modes

- Downlink data baseline
- Downlink control baseline
- Uplink data baseline
- Uplink control baseline
- `PRACH` baseline
- `PBCH / SSB` baseline
- file transfer over PHY

### 3.2 Spatial Features

- `1-2 codewords`
- `1-4 layers`
- `2x2` and `4x4` SU-MIMO baseline
- linear precoding:
  - `identity`
  - `dft`
  - `type1_sp` baseline
- MIMO detectors:
  - `zf`
  - `mmse`
  - `osic`

### 3.3 Reference Signals

- `DM-RS`
- `PT-RS`
- `CSI-RS`
- `SRS`
- `PBCH-DMRS`

### 3.4 Resource Allocation

- baseline `VRB -> PRB` mapping for data-channel `PDSCH/PUSCH`
- non-interleaved mapping by default
- teaching-oriented interleaved mapping for visualizing distributed PRB allocation
- configurable BWP start/size, start VRB, and number of allocated VRBs
- GUI fields `BWP size PRB = 0` and `VRB count = 0` mean "use the remaining available bandwidth"

### 3.5 GUI Capabilities

- end-to-end `PHY Pipeline`
- stage-by-stage playback
- frame / slot / symbol scrubbers
- signal-domain and grid-domain plots
- per-layer, per-port, and detector-domain artifacts
- file transfer inspection
- CSI feedback stage visualization

## 4. Environment and Prerequisites

### 4.1 Recommended Python

- `Python 3.10` or `Python 3.11`

### 4.2 Required Python Packages

Core dependencies are declared in [pyproject.toml](../pyproject.toml) and [requirements.txt](../requirements.txt).

Main runtime stack:

- `numpy`
- `scipy`
- `matplotlib`
- `pandas`
- `PyYAML`
- `PyQt5`
- `pyqtgraph`
- `dash`
- `plotly`

### 4.3 GNU Radio

GNU Radio is optional.

Use it only if you need:

- `TX sink`
- `RX sink`
- GNU Radio loopback integration

For the GUI itself, GNU Radio is not required.

## 5. Installation

### 5.1 Python-Only Setup on Windows

```powershell
cd <path-to-5gnr_phy_stl>
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Replace `<path-to-5gnr_phy_stl>` with the local folder where this repository lives on your machine.

Absolute-path examples:

- Windows: `D:\Projects\5gnr_phy_stl`
- Ubuntu/Linux: `/home/<user>/projects/5gnr_phy_stl`
- macOS: `/Users/<user>/projects/5gnr_phy_stl`

### 5.2 Radioconda / GNU Radio Setup on Windows

If GNU Radio support is needed:

```powershell
cd <path-to-5gnr_phy_stl>
<radioconda-python> -m pip install -r requirements.txt
```

`<radioconda-python>` means the `python.exe` inside your local Radioconda installation.

Explicit interpreter examples:

- Windows Radioconda: `C:\Users\<user>\AppData\Local\radioconda\python.exe`
- Ubuntu/Linux Conda environment: `/home/<user>/miniforge3/envs/5gnr-phy/bin/python`
- macOS Conda environment: `/Users/<user>/miniforge3/envs/5gnr-phy/bin/python`

Then run the GUI with:

```powershell
.\run_gui_radioconda.bat
```

or:

```powershell
<radioconda-python> main.py --config configs/default.yaml --gui
```

### 5.3 Build the Package

If the virtual environment has `build` installed:

```powershell
.\.venv\Scripts\python.exe -m build
```

Expected outputs:

- `dist/fivegnr_phy_stl-2.3.0.tar.gz`
- `dist/fivegnr_phy_stl-2.3.0-py3-none-any.whl`

## 6. Running the Project

### 6.1 Default GUI

```powershell
cd <path-to-5gnr_phy_stl>
python main.py --config configs/default.yaml --gui
```

### 6.2 Default CLI

```powershell
python main.py --config configs/default.yaml
```

### 6.3 Ready-Made Scenarios

#### Vehicular

```powershell
python main.py --config configs/default.yaml --override configs/scenario_vehicular.yaml --gui
```

#### Uplink Data

```powershell
python main.py --config configs/default.yaml --override configs/scenario_uplink_baseline.yaml --gui
```

#### Uplink Control

```powershell
python main.py --config configs/default.yaml --override configs/scenario_uplink_control_baseline.yaml --gui
```

#### PRACH

```powershell
python main.py --config configs/default.yaml --override configs/scenario_uplink_prach_baseline.yaml --gui
```

#### PBCH / SSB

```powershell
python main.py --config configs/default.yaml --override configs/scenario_pbch_baseline.yaml --gui
```

#### SU-MIMO Layer Mapping

```powershell
python main.py --config configs/default.yaml --override configs/scenario_su_mimo_layer_mapping.yaml --gui
```

#### SU-MIMO CSI Loop

```powershell
python main.py --config configs/default.yaml --override configs/scenario_su_mimo_csi_loop.yaml --gui
```

#### SU-MIMO Two-Codeword

```powershell
python main.py --config configs/default.yaml --override configs/scenario_su_mimo_two_codeword.yaml --gui
```

#### P3 HARQ Baseline

```powershell
python main.py --config configs/default.yaml --override configs/scenario_harq_baseline.yaml --gui
```

#### P3 DCI-like Scheduler Replay

```powershell
python main.py --config configs/default.yaml --override configs/scenario_scheduler_grant_replay.yaml --gui
```

#### P3 Coupled HARQ + Scheduler Loop

```powershell
python main.py --config configs/default.yaml --override configs/scenario_p3_harq_scheduler_loop.yaml --gui
```

## 7. GUI Operating Guide

### 7.1 Main Controls

Key controls in the left panel:

- `Run`
- `Step Mode`
- `Batch`
- `Capture slots`
- `Direction`
- `Perfect sync`
- `Perfect CE`
- `CSI enabled`
- `CSI replay`
- `CSI max rank`

### 7.2 `Run` vs `Step Mode`

- `Run`
  - executes the current scenario
  - updates all plots and KPI views
  - does not force you into the stage-by-stage view

- `Step Mode`
  - executes the current scenario
  - automatically enters `PHY Pipeline`
  - resets playback to the first stage of the first captured slot

### 7.3 PHY Pipeline

The `PHY Pipeline` tab is the primary teaching and debugging view.

It supports:

- sequential stage playback
- direct stage selection
- frame / slot scrubbers
- symbol scrubber
- artifact selector per stage

For SU-MIMO runs, the most relevant stages are:

- `Codeword Split`
- `Layer Mapping`
- `Precoding / Port Mapping`
- `MIMO Detection`
- `Layer Recovery / De-precoding`
- `CSI Feedback`

### 7.4 Multi-Slot Scrubbing

Set `Capture slots > 1` before running. Then:

- the GUI stores a slot history
- `Frame` and `Slot` sliders become meaningful
- playback can cross slot boundaries automatically

## 8. File Transfer Workflow

### 8.1 TX Input Files

Sample files are available in [input](../input):

- [sample_message.txt](../input/sample_message.txt)
- [sample_image.png](../input/sample_image.png)

### 8.2 GUI Flow

1. Open the GUI.
2. Choose `TX file`.
3. Choose `RX output`.
4. Run the scenario.
5. Inspect:
   - `File Source + Packaging`
   - PHY stages
   - `File Reassembly + Write`

### 8.3 CLI Flow

```powershell
python main.py --config configs/default.yaml --tx-file input/sample_message.txt --rx-output-dir outputs/rx_files
python main.py --config configs/default.yaml --tx-file input/sample_image.png --rx-output-dir outputs/rx_files
```

RX filenames include:

- original filename
- SNR label
- RX timestamp

This avoids collisions across repeated runs.

## 9. Batch Experiments

### 9.1 Standard Batch Commands

```powershell
python run_experiments.py --experiment ber_vs_snr --config configs/default.yaml --output-dir outputs
python run_experiments.py --experiment bler_vs_snr --config configs/default.yaml --output-dir outputs
python run_experiments.py --experiment evm_vs_snr --config configs/default.yaml --output-dir outputs
python run_experiments.py --experiment fading_sweep --config configs/default.yaml --output-dir outputs
python run_experiments.py --experiment impairment_sweep --config configs/default.yaml --output-dir outputs
```

### 9.2 File Transfer Sweep

```powershell
python run_experiments.py --experiment sample_file_transfer_sweep --config configs/default.yaml --override configs/scenario_sample_file_transfer_sweep.yaml --output-dir outputs
```

### 9.3 CSI Loop Compare

```powershell
python run_experiments.py --experiment csi_loop_compare --config configs/default.yaml --override configs/scenario_su_mimo_csi_loop.yaml --output-dir outputs
```

This experiment compares:

- `open_loop`
- `closed_loop`

and exports:

- throughput vs SNR
- BLER vs SNR
- target-rate vs SNR

## 10. Interpreting Outputs

### 10.1 Core KPIs

- `ber`
- `bler`
- `evm`
- `throughput_bps`
- `spectral_efficiency_bps_hz`
- `estimated_snr_db`
- `crc_ok`

### 10.2 SU-MIMO-Specific Artifacts

Use these views to understand spatial behavior:

- `Per-codeword constellation`
- `Per-layer constellation`
- `Per-port constellation`
- `Effective channel magnitude`
- `MIMO Detection`
- `Layer Recovery / De-precoding`
- `CSI Feedback`

### 10.3 Closed-Loop CSI Behavior

In CSI replay mode, the selected transmission state can change across slots:

- rank
- precoding mode / PMI
- modulation
- target rate

This is visible in:

- `schedule_trace`
- `csi_trace`
- GUI `CSI Feedback` stage

## 11. Troubleshooting

### 11.1 `TX sink` / `RX sink` Disabled

Cause:

- GNU Radio is unavailable in the Python interpreter running the GUI

Recommended fix:

- run the GUI with the Radioconda interpreter or launcher

### 11.2 PowerShell Blocks `.ps1`

Use:

```powershell
.\run_gui_radioconda.bat
```

or call the interpreter directly.

### 11.3 `requirements.txt` Not Found

Check the working directory first:

```powershell
Get-Location
```

Then change into:

```powershell
cd <path-to-5gnr_phy_stl>
```

### 11.4 GUI Looks Fine but Results Never Change Much

Common reason:

- `Perfect sync = On`
- `Perfect CE = On`

For more realistic thresholds:

- turn both off
- lower SNR
- increase Doppler / impairments

### 11.5 File Transfer Appears “All or Nothing”

That is expected.

The current file-transfer path reconstructs the file only if all required chunks survive decoding well enough for reassembly.

## 12. Recommended Demo Paths

### 12.1 Teaching-Oriented PHY Walkthrough

Use:

```powershell
python main.py --config configs/default.yaml --gui
```

Then:

- set `Capture slots = 2`
- use `Step Mode`
- inspect `PHY Pipeline`

### 12.2 SU-MIMO Demonstration

Use:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_su_mimo_two_codeword.yaml --gui
```

Focus on:

- `Codeword Split`
- `Layer Mapping`
- `Precoding / Port Mapping`
- `MIMO Detection`
- `CSI Feedback`

### 12.3 File Transfer Demonstration

Use:

```powershell
python main.py --config configs/default.yaml --override configs/scenario_image_transfer.yaml --gui
```

Then vary:

- SNR
- `Perfect sync`
- `Perfect CE`

## 13. Known Limits

The project is still a software-only PHY simulator, not a conformance-grade 3GPP implementation.

Current major limits:

- HARQ is a baseline process/soft-combining model, not a full 3GPP MAC HARQ implementation
- scheduler support is DCI-like grant replay, not a full dynamic MAC scheduler
- no MU-MIMO
- no Massive MIMO
- no FR2 hybrid beamforming
- CSI is baseline, not vendor-grade beam management

## 14. Related Documents

- [README.md](../README.md)
- [GUI_ARCHITECTURE.md](GUI_ARCHITECTURE.md)
- [TECHDOC_5G_NR_PHY_TRACE.md](TECHDOC_5G_NR_PHY_TRACE.md)
- [NR_PHY_SIMULATOR_V2_ARCHITECTURE.md](NR_PHY_SIMULATOR_V2_ARCHITECTURE.md)
- [NR_PHY_SIMULATOR_V2_BACKLOG.md](NR_PHY_SIMULATOR_V2_BACKLOG.md)
