# GUI Architecture for 5G NR PHY STL

This document proposes a more suitable GUI architecture for the project and defines the PHY-oriented screens that should exist in a research and teaching workbench.

## Design Goals

The GUI should support four use cases:

- configure and run a single PHY link quickly
- inspect signal behavior at each major PHY stage
- compare impairments and channel effects visually
- support classroom demonstration and guided lab work

The current repository already has the foundations for this:

- control/configuration panel
- result/KPI panel
- optional GNU Radio flowgraph hooks

The missing part is a stronger PHY visualization workspace.

## Recommended GUI Architecture

Use a three-layer GUI model.

```text
+---------------------------------------------------------------+
| 1. Session / Control Layer                                    |
|    - scenario setup                                           |
|    - numerology / modulation / coding / impairment controls   |
|    - run / stop / reset / save / load / batch                 |
+---------------------------------------------------------------+
| 2. PHY Visualization Workspace                                |
|    - signal-domain views                                      |
|    - resource-grid views                                      |
|    - channel / sync / equalization views                      |
|    - experiment comparison views                              |
+---------------------------------------------------------------+
| 3. Analysis / Status Layer                                    |
|    - KPI table                                                |
|    - runtime logs                                             |
|    - warnings / assumptions / simplification notes            |
+---------------------------------------------------------------+
```

## Rendering Stack Recommendation

Use the following tools by role:

- `PyQt5`: application shell, controls, layout, dialogs
- `PyQtGraph`: realtime desktop visualization for PHY runtime views
- `Matplotlib`: static plots and exported experiment figures
- `GNU Radio QT sinks`: optional live IQ/spectrum/constellation instrumentation
- `Dash` or notebook tooling later: batch analytics and teaching dashboards

Rationale:

- `PyQtGraph` is better suited than embedded `Matplotlib` for responsive Qt-native signal and heatmap views.
- `Matplotlib` remains useful for offline reports and experiment exports.
- GNU Radio sinks remain useful as an auxiliary live instrumentation path, not as the main GUI shell.

## Recommended GUI Modules

The project should move toward the following module split:

- `gui/controls.py`
  - scenario, numerology, channel, impairment controls
- `gui/plots.py`
  - realtime signal/PHY visualization workspace
- `gui/dashboard.py`
  - KPI table, experiment status, log view
- `gui/config_editor.py`
  - save/load YAML scenarios
- future: `gui/workspaces/`
  - dedicated reusable plot widgets per PHY view

Suggested future package structure:

```text
gui/
├── app.py
├── controls.py
├── dashboard.py
├── config_editor.py
├── plots.py
└── workspaces/
    ├── signal_views.py
    ├── resource_grid_views.py
    ├── channel_views.py
    ├── sync_views.py
    └── experiment_views.py
```

## PHY Screens That Should Exist

These are the screens the project should expose as it matures.

### 1. Link Setup Screen

Purpose:

- choose channel type
- choose numerology
- choose modulation/coding/MCS-like operating point
- choose channel profile and impairment settings

Primary widgets:

- control form
- scenario presets
- validation warnings

### 2. Signal Domain Screen

Purpose:

- inspect the waveform directly in time and frequency

Primary plots:

- TX waveform I/Q
- RX waveform I/Q
- spectrum
- waterfall / spectrogram

### 3. Resource Grid Screen

Purpose:

- show how control/data/DMRS occupy the slot grid

Primary plots:

- TX resource grid allocation
- TX resource grid magnitude
- RX resource grid magnitude
- DMRS overlay

### 4. Synchronization Screen

Purpose:

- study timing and frequency synchronization behavior

Primary plots:

- timing metric over search window
- CFO estimate trend
- STO estimate vs configured STO
- CP correlation view

### 5. Channel Estimation and Equalization Screen

Purpose:

- inspect channel response and equalizer behavior

Primary plots:

- channel impulse response
- channel frequency response
- estimated channel heatmap
- channel estimation error heatmap
- equalizer gain magnitude

### 6. Constellation / EVM Screen

Purpose:

- evaluate demodulation quality before and after equalization

Primary plots:

- pre-equalization constellation
- post-equalization constellation
- reference constellation overlay
- EVM per RE / symbol / subcarrier

### 7. KPI / Throughput Screen

Purpose:

- summarize PHY success or failure

Primary plots and tables:

- BER
- BLER
- EVM
- throughput
- estimated SNR
- channel estimation MSE
- synchronization error

### 8. Batch Experiment Screen

Purpose:

- compare sweeps visually without leaving the GUI

Primary plots:

- BER vs SNR
- BLER vs SNR
- EVM vs SNR
- throughput vs SNR
- fading / Doppler / impairment sweeps

### 9. GNU Radio Instrumentation Screen

Purpose:

- optional bridge to GNU Radio sinks for live IQ observation

Primary elements:

- TX sink launcher
- RX sink launcher
- loopback instrumentation status

## What the Current Patch Implements

The current GUI patch upgrades the central plot workspace to a `PyQtGraph`-based PHY dashboard and provides:

- `Signal Domain` tab
  - pre/post/reference constellation overlay
  - TX/RX waveform overlay
  - TX/RX spectrum overlay
  - RX waterfall
- `Resource Grid` tab
  - TX allocation map with DMRS highlighting
  - TX grid magnitude
  - RX grid magnitude
  - estimated channel magnitude heatmap
- `Channel / Sync / EQ` tab
  - channel impulse response
  - average channel frequency response
  - approximate equalizer gain
  - sync summary
  - EVM by OFDM symbol
  - relative error by subcarrier
- `Batch Analytics` tab
  - embedded Matplotlib analytics for batch runs
- auxiliary tools
  - GNU Radio TX/RX QT sink launchers
  - Dash launcher for browser-based batch dashboards
  - warnings / assumptions panel in the dashboard

This is still not a final conformance-grade PHY workbench, but it is now aligned with the recommended GUI direction in this document.
