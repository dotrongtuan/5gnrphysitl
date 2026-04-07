# 5G NR PHY STL Research Platform

Software-in-the-loop, software-only prototype for a 5G NR-inspired PHY link simulator built with Python, GNU Radio integration hooks, NumPy/SciPy, Matplotlib, and PyQt5.

This codebase targets research, teaching, quick what-if studies, and progressive expansion toward a richer NR PHY platform. It intentionally prioritizes a clean architecture and runnable end-to-end prototype over full 3GPP compliance.

## Platform Support

The project is designed to be cross-platform, but the effective support level depends on whether you run the Python-only simulator or the optional GNU Radio integration layer.

| Operating System | Python-only PHY/Core | PyQt GUI | GNU Radio Integration | Recommended Level |
| --- | --- | --- | --- | --- |
| Windows 10/11 | Supported | Supported | Supported with environment-specific setup | Good for development and teaching |
| Ubuntu 22.04/24.04 | Supported | Supported | Supported and recommended | Best overall platform |
| macOS | Supported | Supported if PyQt installs cleanly | Possible but may require manual setup | Acceptable for Python-first use |

Notes:

- The codebase was smoke-tested in this workspace on Windows using PowerShell and Python 3.13.
- Ubuntu/Linux is the preferred target for full GNU Radio + Qt usage.
- Windows works well for the Python simulator, GUI, and batch experiments, but GNU Radio installation is usually less predictable than on Linux.
- macOS is best treated as a Python-core platform unless your local GNU Radio and Qt toolchain is already stable.

## Recommended Deployment Environments

Choose the target environment based on what you want to do with the platform.

| Use Case | Recommended OS | Recommended Stack |
| --- | --- | --- |
| Classroom demo, PHY algorithm study, batch plots | Windows 10/11 or Ubuntu | Python-only mode with `venv` |
| Full research workflow with GNU Radio and GUI sinks | Ubuntu 22.04/24.04 | Conda environment with GNU Radio + project dependencies |
| Software-only development on a personal laptop | Windows, Ubuntu, or macOS | Python-only mode |
| Most stable full-stack setup | Ubuntu 22.04/24.04 | Conda + GNU Radio + PyQt |

Practical recommendation:

- If you only need the simulator core, GUI dashboard, and experiment scripts, start with Python-only mode.
- If you need GNU Radio flowgraphs and QT sinks, prefer Ubuntu first.
- On Windows, prefer running the full GNU Radio path inside one Conda environment instead of mixing system Python and external GNU Radio installs.

## Quick Start

Use one of these two paths depending on your goal.

### Quick Start A: Python-only mode

Best for:

- first run
- lecture/demo use
- algorithm study
- batch experiments

1. Create and activate an environment.

Windows PowerShell:

```powershell
cd C:\path\to\5gnr_phy_stl
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If `python` works but `py` does not, that is normal on some Windows setups. Use `python -m venv .venv`.

If PowerShell blocks `.venv\Scripts\Activate.ps1`, use one of these alternatives:

```cmd
.venv\Scripts\activate.bat
```

or run the virtual-environment Python directly without activation:

```powershell
.venv\Scripts\python.exe main.py --config configs/default.yaml
```

Ubuntu/macOS:

```bash
cd /path/to/5gnr_phy_stl
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

2. Run a single link simulation.

Where to run this command:

- On Windows: run it in the same `PowerShell`, `cmd.exe`, or `Anaconda Prompt` where the environment is already active.
- If you did not activate the virtual environment, use `.venv\Scripts\python.exe` instead of `python`.
- On Linux/macOS: run it in the terminal where `.venv` is already activated.

```bash
python main.py --config configs/default.yaml
```

Windows without activation:

```powershell
.venv\Scripts\python.exe main.py --config configs/default.yaml
```

3. Launch the research GUI.

Where to run this command:

- On Windows: use the same shell where the environment is active.
- If activation is blocked, call `.venv\Scripts\python.exe` directly.
- On Linux/macOS: use the terminal where `.venv` is active.

```bash
python main.py --config configs/default.yaml --gui
```

Windows without activation:

```powershell
.venv\Scripts\python.exe main.py --config configs/default.yaml --gui
```

4. Run a quick batch sweep.

Where to run this command:

- On Windows: use the same shell where the environment is active.
- If activation is blocked, call `.venv\Scripts\python.exe` directly.
- On Linux/macOS: use the terminal where `.venv` is active.

```bash
python run_experiments.py --experiment ber_vs_snr --config configs/default.yaml --output-dir outputs
```

Windows without activation:

```powershell
.venv\Scripts\python.exe run_experiments.py --experiment ber_vs_snr --config configs/default.yaml --output-dir outputs
```

### Quick Start B: Full GNU Radio mode

Best for:

- GNU Radio QT sinks
- software loopback through GNU Radio blocks
- research setups that need both PHY modules and flowgraph inspection

1. Create one Conda environment for everything.

Where to run these commands:

- On Windows: use `Anaconda Prompt`, `Miniconda Prompt`, or `PowerShell` only after running `conda init powershell` and reopening the shell.
- On Linux/macOS: use a normal terminal where Conda is already initialized.

```bash
conda create -n 5gnr-phy python=3.10 -y
conda activate 5gnr-phy
conda install -c conda-forge gnuradio -y
pip install -r requirements.txt
```

2. Check that GNU Radio imports correctly.

Where to run this command:

- On Windows: use the same `Anaconda Prompt`, `Miniconda Prompt`, or initialized `PowerShell` where `conda activate 5gnr-phy` was executed.
- On Linux/macOS: use the terminal where the Conda environment is active.

```bash
python -c "import gnuradio; print('GNU Radio import OK')"
```

3. Run the simulator with the GNU Radio loopback override.

Where to run this command:

- Use the same shell where `conda activate 5gnr-phy` is already active.
- If `python` points to the wrong interpreter, verify with `python -c "import sys; print(sys.executable)"` before running.

```bash
python main.py --config configs/default.yaml --override configs/scenario_gnuradio.yaml
```

4. If you want the dashboard as well, launch:

Where to run this command:

- Use the same active Conda shell as in steps 2 and 3.
- On Windows, this usually means `Anaconda Prompt`, `Miniconda Prompt`, or `PowerShell` after `conda init powershell`.

```bash
python main.py --config configs/default.yaml --override configs/scenario_gnuradio.yaml --gui
```

Notes:

- `configs/scenario_gnuradio.yaml` enables `simulation.use_gnuradio: true`.
- If GNU Radio is not available, the project falls back to the Python-only path.
- For the most stable GNU Radio experience, prefer Ubuntu.

## Convenience Commands

The repository also includes one-command launchers for common workflows.

### Windows `.bat`

Where to run these commands:

- Run them from the project root directory.
- You can use `cmd.exe`, `PowerShell`, `Anaconda Prompt`, or `Miniconda Prompt`.
- In `PowerShell`, you must prefix scripts in the current directory with `.\` because PowerShell does not load the current directory by default.

```powershell
.\run_python_only.bat
```

- If you are in `cmd.exe`, you can run them directly:

```cmd
run_python_only.bat
```

PowerShell examples:

```powershell
.\run_python_only.bat
.\run_gui.bat
.\run_batch_ber.bat
.\run_gnuradio.bat
.\run_vehicular.bat
.\run_student_testcases.bat
.\run_showcases.bat
```

`cmd.exe` examples:

```cmd
run_python_only.bat
run_gui.bat
run_batch_ber.bat
run_gnuradio.bat
run_vehicular.bat
run_student_testcases.bat
run_showcases.bat
```

### Linux/macOS `.sh`

Where to run these commands:

- Run them from the project root directory.
- Use a normal shell such as `bash`, `zsh`, or another POSIX-compatible terminal.
- If you created `.venv`, activate it first, or let the scripts auto-detect `.venv/bin/python`.

```bash
chmod +x run_python_only.sh run_gui.sh run_batch_ber.sh run_gnuradio.sh run_vehicular.sh run_student_testcases.sh run_showcases.sh
./run_python_only.sh
./run_gui.sh
./run_batch_ber.sh
./run_gnuradio.sh
./run_vehicular.sh
./run_student_testcases.sh
./run_showcases.sh
```

### `Makefile` targets

Where to run these commands:

- On Linux/macOS: run them in a terminal from the project root.
- On Windows: use `Git Bash`, `MSYS2`, `WSL`, or another environment where `make` is available.
- If you are using plain `PowerShell` or `cmd.exe` on Windows and do not have `make`, prefer the `.bat` launchers instead.

```bash
make run
make gui
make batch-ber
make gnuradio
make vehicular
make student-cases
make showcases
make test
make compile
```

Notes:

- The `.bat` and `.sh` launchers automatically prefer the local `.venv` interpreter if it exists.
- Extra command-line arguments are passed through to the underlying Python command.
- `make test` requires `pytest` to be installed in the active environment.
- For a classroom-oriented walkthrough, see `docs/STUDENT_TESTCASES.md`.
- For deeper 3GPP-inspired teaching demos, see `docs/SHOWCASES_3GPP_PHY.md`.
- `docs/SHOWCASES_3GPP_PHY.md` also includes a checklist to distinguish a teaching model from a conformance-grade NR PHY.

## 1. Problem Analysis

The platform models a downlink NR-like PHY chain from gNB to UE with:

- PDSCH and PDCCH-style payload modes.
- CRC, coding, scrambling, modulation, resource-grid mapping, DMRS insertion, OFDM TX/RX, channel impairment, channel estimation, equalization, soft demapping, decoding, and KPI extraction.
- Batch experiments for BER, BLER, EVM, fading, Doppler, and impairment sensitivity.
- A PyQt research dashboard for interactive parameter tuning and visualization.
- Optional GNU Radio flowgraphs that wrap the Python-generated waveform for real-time inspection or loopback channel processing.

The core design principle is to keep each PHY processing stage explicit and replaceable so later phases can swap simplified models for more standard-faithful ones.

## 2. System Architecture Diagram

```text
                +-------------------+
                | YAML Configs / UI |
                +---------+---------+
                          |
                          v
                 +--------+---------+
                 | Simulation Core  |
                 | main.py / GUI /  |
                 | experiment runner|
                 +--------+---------+
                          |
          +---------------+----------------+
          |                                |
          v                                v
 +--------+---------+              +-------+--------+
 | PHY Transmitter  |              | GNU Radio      |
 | TB/CRC/Coding    |<-----------> | TX/RX/Loopback |
 | Scramble/Map/    |              | Visualization  |
 | DMRS/OFDM        |              +----------------+
 +--------+---------+
          |
          v
 +--------+---------+
 | Channel Models   |
 | AWGN / Fading /  |
 | TDL / Doppler /  |
 | CFO / STO / PN   |
 +--------+---------+
          |
          v
 +--------+---------+
 | PHY Receiver     |
 | Sync / CFO /     |
 | OFDM / CE / EQ / |
 | Demap / Decode   |
 +--------+---------+
          |
          v
 +--------+---------+
 | KPI + Reporting  |
 | BER/BLER/EVM/TP  |
 | CSV/PNG/Markdown |
 +------------------+
```

## 3. Project Folder Structure

```text
5gnr_phy_stl/
├── README.md
├── requirements.txt
├── main.py
├── run_experiments.py
├── configs/
├── phy/
├── channel/
├── grc/
├── gui/
├── experiments/
├── utils/
└── tests/
```

## 4. Module Responsibilities

- `phy/`: NR PHY processing chain.
- `channel/`: software-only propagation and RF impairment models.
- `grc/`: GNU Radio Python flowgraphs for TX, RX, and loopback channel usage.
- `gui/`: research dashboard and controls.
- `experiments/`: reusable sweeps and batch report generation.
- `utils/`: YAML I/O, validation, logging, plotting.
- `configs/`: default settings, numerology presets, channel presets, scenarios.
- `tests/`: basic unit tests for modulation, grid mapping, channel wrappers, and KPI logic.

## 5. End-to-End Data Flow

1. Load and validate YAML configuration.
2. Generate transport/control payload bits.
3. Attach CRC and apply channel coding.
4. Perform rate matching, scrambling, and QAM mapping.
5. Map symbols into the resource grid and insert DMRS.
6. Convert the active grid to OFDM waveform with CP.
7. Apply impairments, fading, Doppler, path loss, and AWGN.
8. Synchronize, correct CFO, demodulate OFDM, estimate the channel, and equalize.
9. Soft demap, descramble, recover rate, decode, and check CRC.
10. Compute BER, BLER, EVM, throughput, spectral efficiency, SNR estimate, and optional CE/sync errors.

## 6. GNU Radio Flowgraph Design

- `grc/tx_flowgraph.py`: vector source + throttle + QT time/frequency sinks for the transmitter waveform.
- `grc/rx_flowgraph.py`: vector source + throttle + QT time/frequency/constellation sinks for received waveform observation.
- `grc/end_to_end_flowgraph.py`: vector source + FIR taps + GNU Radio `channels.channel_model` + vector sink for optional loopback processing.

Usage model:

- PHY algorithms remain in Python modules.
- GNU Radio acts as an executable signal-flow wrapper and visualization layer.
- If GNU Radio is unavailable, the prototype still runs entirely in Python.

## 7. Core Code Highlights

- `phy/modulation.py`: Gray-coded QPSK/16QAM/64QAM/256QAM mapper and max-log LLR demapper.
- `phy/coding.py`: simplified NR-inspired data coding plus a polar-like control coder.
- `phy/resource_grid.py`: active-subcarrier resource grid, PDCCH/PDSCH allocation, DMRS placement, FFT bin mapping.
- `phy/transmitter.py`: end-to-end downlink waveform generation.
- `phy/receiver.py`: synchronization, OFDM demod, DMRS-based CE, equalization, soft decoding, KPI packaging.
- `channel/fading_channel.py`: TDL-style tapped channel with Rayleigh/Rician options and Doppler/path-loss coupling.
- `experiments/common.py`: shared simulation orchestration between CLI, GUI, and batch experiments.

## 8. GUI

The dashboard supports:

- Mode selection: data, control, compare.
- Numerology and modulation controls.
- Channel and impairment controls.
- Run, stop, reset, save/load config, and batch experiment buttons.
- Real-time plot areas for constellation, waveform, spectrum, impulse response, estimated channel, and KPI snapshot.
- KPI table and log pane.

## 9. Batch Experiments

Included runners:

- `experiments/ber_vs_snr.py`
- `experiments/bler_vs_snr.py`
- `experiments/evm_vs_snr.py`
- `experiments/control_vs_data.py`
- `experiments/fading_sweep.py`
- `experiments/doppler_sweep.py`
- `experiments/impairment_sweep.py`

Outputs:

- CSV tables
- PNG plots
- Markdown summaries

## 10. Installation

### General guidance

- Python-only mode is the easiest path and does not require SDR hardware.
- For full GNU Radio integration, use a Python version that matches your GNU Radio build.
- The most reliable full-stack setup is usually one Conda environment containing Python, GNU Radio, and the project dependencies together.

### Python-only setup

```bash
pip install -r requirements.txt
```

### Windows 10/11 setup

Recommended for:

- Python-only simulation
- GUI dashboard
- Batch experiments
- Development and teaching

#### Option A: Python-only with `venv`

PowerShell:

```powershell
cd C:\path\to\5gnr_phy_stl
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If your system does not recognize `py`, use `python -m venv .venv` as shown above.

If PowerShell blocks `.venv\Scripts\Activate.ps1`, either use:

```cmd
.venv\Scripts\activate.bat
```

or call the interpreter directly:

```powershell
.venv\Scripts\python.exe main.py --config configs/default.yaml
```

#### Option B: Full stack with Conda and GNU Radio

Recommended when you want `grc/` flowgraphs and GNU Radio QT sinks:

Run these commands in:

- `Anaconda Prompt` or `Miniconda Prompt`
- or `PowerShell` after:

```powershell
conda init powershell
```

Then close and reopen PowerShell before continuing.

```powershell
conda create -n 5gnr-phy python=3.10 -y
conda activate 5gnr-phy
conda install -c conda-forge gnuradio -y
pip install -r requirements.txt
```

Windows notes:

- If PowerShell blocks virtual environment activation, enable script execution for your user profile or use `cmd.exe`.
- Keep GNU Radio and project dependencies in the same Conda environment when possible.
- Python-only mode is typically smoother on Windows than full GNU Radio integration.

### Ubuntu 22.04/24.04 setup

Recommended for:

- Full GNU Radio development
- GUI-based research workflows
- Long-running batch experiments
- Most stable end-to-end setup

#### Option A: Python-only with `venv`

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
cd /path/to/5gnr_phy_stl
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### Option B: Recommended full stack with Conda and GNU Radio

```bash
conda create -n 5gnr-phy python=3.10 -y
conda activate 5gnr-phy
conda install -c conda-forge gnuradio -y
pip install -r requirements.txt
```

Ubuntu notes:

- Ubuntu is the preferred platform for GNU Radio + Qt usage.
- Conda is usually the cleanest choice when you want GNU Radio Python bindings and project dependencies in one place.
- If you install GNU Radio from system packages instead, make sure you run the project with the matching Python interpreter.

### macOS setup

Recommended for:

- Python-only simulation
- Small-scale GUI use if PyQt installs correctly

Suggested approach:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

macOS notes:

- Treat GNU Radio as optional on macOS unless your local toolchain is already known to work.
- Python-only mode is the lowest-friction path.

### GNU Radio

GNU Radio 3.10+ is optional but recommended for the flowgraph wrappers.

- Windows: prefer Conda or a prebuilt GNU Radio distribution.
- Linux: use distro packages or Conda.
- Best practice: keep GNU Radio and the project in the same environment to avoid Python binding mismatches.
- Use `configs/scenario_gnuradio.yaml` for a ready-made loopback quick-start profile.

### Troubleshooting

#### PyQt install failed

Typical symptoms:

- `pip install PyQt5` fails
- GUI does not start
- Qt-related DLL or plugin errors appear at launch

What to do:

- Upgrade packaging tools first:

```bash
python -m pip install --upgrade pip setuptools wheel
```

- Reinstall dependencies:

```bash
pip install -r requirements.txt
```

- On Windows, prefer a clean `venv` or Conda environment instead of a system-wide Python install.
- On macOS, if PyQt remains problematic, use Python-only CLI and batch mode first.

#### GNU Radio import error

Typical symptoms:

- `ImportError: No module named gnuradio`
- GNU Radio flowgraphs fail while the Python-only simulator still works

What to do:

- Verify you are using the same Python interpreter that GNU Radio was installed into:

```bash
python -c "import sys; print(sys.executable)"
python -c "import gnuradio; print('GNU Radio import OK')"
```

- If GNU Radio is missing, install it in the active environment:

```bash
conda install -c conda-forge gnuradio -y
```

- Avoid mixing:
  system Python + Conda GNU Radio
- Prefer:
  one Conda environment containing both GNU Radio and project dependencies

#### PowerShell execution policy blocks virtual environment activation

Typical symptom:

- `.venv\Scripts\Activate.ps1` is blocked by PowerShell

What to do:

- Use a per-user execution policy:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

- Then reopen PowerShell and activate the environment again.
- If you do not want to change PowerShell policy, use `cmd.exe`:

```cmd
.venv\Scripts\activate.bat
```

#### Python interpreter mismatch

Typical symptoms:

- Packages install successfully but `python main.py` still cannot import them
- GUI works in one terminal but not another
- GNU Radio imports in Conda Python but not in system Python

What to do:

- Check the interpreter in the current shell:

```bash
python -c "import sys; print(sys.executable)"
```

- On Windows, also check:

```powershell
Get-Command python
```

- Make sure `pip` and `python` refer to the same environment:

```bash
python -m pip install -r requirements.txt
```

- If you use Conda, always run:

```bash
conda activate 5gnr-phy
python main.py --config configs/default.yaml
```

#### Tests do not run because `pytest` is missing

Typical symptom:

- `python -m pytest tests -q` reports that `pytest` is not installed

What to do:

```bash
python -m pip install -r requirements.txt
```

or:

```bash
python -m pip install pytest
```

#### `ModuleNotFoundError` for `pandas` or other Python packages

Typical symptoms:

- `ModuleNotFoundError: No module named 'pandas'`
- similar import errors for `numpy`, `scipy`, `matplotlib`, `yaml`, or `PyQt5`

What to do:

- Install the project dependencies into the same Python environment you are using to run the command:

```bash
python -m pip install -r requirements.txt
```

- On Windows, if you are using a local virtual environment, prefer:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

- Then run the script with the same interpreter:

```powershell
.venv\Scripts\python.exe run_student_testcases.py --config configs/default.yaml --output-dir outputs/student_testcases
```

- If needed, verify which interpreter is active:

```bash
python -c "import sys; print(sys.executable)"
```

#### GUI starts but no GNU Radio windows appear

Typical reason:

- The project GUI is separate from GNU Radio QT sinks.
- GNU Radio flowgraph wrappers are optional and are not required for the main PyQt dashboard.

What to do:

- Confirm whether you actually need GNU Radio sinks or only the built-in dashboard.
- If you need GNU Radio windows, verify that GNU Radio imports correctly in the active environment.
- Start with Python-only GUI first, then enable GNU Radio integration after the base environment is stable.

## 11. How To Run

### Single simulation from CLI

```bash
python main.py --config configs/default.yaml
```

### Launch GUI

```bash
python main.py --config configs/default.yaml --gui
```

### Run a batch experiment

```bash
python run_experiments.py --experiment ber_vs_snr --config configs/default.yaml --output-dir outputs
```

### Use a harsher scenario

```bash
python main.py --config configs/default.yaml --override configs/scenario_vehicular.yaml
```

## 12. Known Simplifications

- Data-channel coding is LDPC-inspired, not standards-compliant QC-LDPC.
- Control-channel coding is polar-like and small-block focused, not full NR polar coding.
- Resource allocation is slot-local and simplified; there is no full scheduler/DCI implementation.
- DMRS patterns are NR-inspired but simplified.
- Synchronization and CFO recovery are intentionally lightweight.
- Fading, Doppler, phase noise, and IQ imbalance models are suitable for study/prototyping, not conformance.
- SSB/PBCH, PUSCH, PUCCH, and PRACH are scaffold targets rather than complete implementations in this version.

## 13. Roadmap

### Phase 1

- Stable single-link downlink MVP
- PDSCH baseline
- AWGN and Rayleigh channels
- BER/EVM visualization
- Research GUI

### Phase 2

- Stronger PDCCH handling
- More faithful rate matching and coding
- Control-vs-data comparison workflows
- Batch exports and richer channel sweeps
- Better logging and reporting

### Phase 3

- Multi-numerology refinement
- Improved synchronization and CE algorithms
- Stronger impairment realism
- More flexible scheduler/resource mapping
- Higher test coverage
- Expansion toward uplink and access procedures

## 14. Recommended Next Extensions

- Replace the data coder with a proper QC-LDPC base graph implementation.
- Add realistic CORESET/PDCCH search space abstractions.
- Add HARQ combining and redundancy versions.
- Extend KPI reporting with BLER confidence intervals and latency.
- Add SSB/PBCH acquisition and synchronization experiments.
