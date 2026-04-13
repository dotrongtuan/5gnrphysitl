# 5G NR PHY STL Research Platform

Software-in-the-loop, software-only prototype for a 5G NR-inspired PHY link simulator built with Python, GNU Radio integration hooks, NumPy/SciPy, Matplotlib, PyQtGraph, Dash, and PyQt5.

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

## Installation Automation

The repository includes OS-specific installation workflows and reusable installer scripts under [`install/`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/install).

Recommended entry point:

- installation workflow guide: [`docs/INSTALLATION_WORKFLOWS.md`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/docs/INSTALLATION_WORKFLOWS.md)

Provided installer scripts:

- Windows Python-only: [`install/windows-python-only.ps1`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/install/windows-python-only.ps1)
- Windows Radioconda + GNU Radio: [`install/windows-radioconda.ps1`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/install/windows-radioconda.ps1)
- Ubuntu Python-only: [`install/ubuntu-python-only.sh`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/install/ubuntu-python-only.sh)
- Ubuntu GNU Radio: [`install/ubuntu-gnuradio.sh`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/install/ubuntu-gnuradio.sh)
- macOS Python-only: [`install/macos-python-only.sh`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/install/macos-python-only.sh)
- macOS GNU Radio: [`install/macos-gnuradio.sh`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/install/macos-gnuradio.sh)

## Package Build

The repository now supports standard Python packaging via `pyproject.toml`.

Build wheel and sdist:

```bash
python -m pip install --upgrade pip build
python -m build
```

Artifacts are generated in:

- `dist/*.whl`
- `dist/*.tar.gz`

Install locally from source:

```bash
python -m pip install .
```

Install with development dependencies:

```bash
python -m pip install .[dev]
```

Installed console commands:

- `fivegnr-phy-stl`
- `fivegnr-phy-stl-gui`
- `fivegnr-phy-stl-experiments`
- `fivegnr-phy-stl-student-cases`
- `fivegnr-phy-stl-showcases`

## CI/CD

GitHub Actions workflows are included under [`.github/workflows`](D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/.github/workflows):

- `ci.yml`
  - runs on push to `main` and on pull requests
  - installs the package with dev dependencies
  - runs `pytest`
  - runs `compileall` on the core modules
  - runs CLI smoke checks
  - builds wheel and sdist
  - uploads the `dist/` artifacts from the main Linux build job
- `release.yml`
  - runs on tag pushes matching `v*`
  - builds wheel and sdist
  - uploads them as workflow artifacts
  - attaches them to the GitHub release automatically
- `container.yml`
  - runs on pushes to `main`, on tag pushes matching `v*`, and on manual dispatch
  - builds a Docker image from [`Dockerfile`](D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/Dockerfile)
  - publishes the image to GitHub Container Registry (`ghcr.io`)
  - is the workflow that populates the repository `Packages` tab

This means each commit can be validated and packaged automatically, tagged releases publish build artifacts to GitHub Releases, and successful container publishing creates an actual package entry under GitHub `Packages`.

## GitHub Packages vs Build Artifacts

The repository now exposes two different delivery channels:

- `Actions artifacts` and `Release assets`
  - produced by `ci.yml` and `release.yml`
  - contain `dist/*.whl` and `dist/*.tar.gz`
  - visible from workflow runs and GitHub Releases
- `GitHub Packages`
  - produced by `container.yml`
  - contain a container image in GitHub Container Registry
  - visible from the repository `Packages` tab only after the container publish job succeeds

If the `Packages` tab is empty, the usual reason is that only Python build artifacts were uploaded, while no package registry publication happened yet.

## Container Image

The project now includes a container image path for headless and CI use:

- image name: `ghcr.io/aselab-uni/5gnrphysitl`

Typical commands:

```bash
docker pull ghcr.io/aselab-uni/5gnrphysitl:latest
docker run --rm ghcr.io/aselab-uni/5gnrphysitl:latest --help
```

Important notes:

- This image is intended for CLI/headless execution, batch experiments, and CI validation.
- The desktop GUI is not the primary target inside the container.
- The repository `Packages` tab will show this image only after `container.yml` completes successfully on GitHub.

## Python Version Requirements

This project requires Python 3.10 or newer.

Recommended versions by use case:

| Use Case | Recommended Python | Status |
| --- | --- | --- |
| Python-only simulator, GUI, batch experiments | 3.10 or 3.11 | Recommended |
| GNU Radio integration | 3.10 | Strongly recommended |
| Python 3.12/3.13 | Usually fine for Python-only mode | Acceptable, but verify local packages |
| Python 3.9 and older | Unsupported | Will fail on project features such as `dataclass(slots=True)` |

Practical notes:

- Ubuntu 22.04 normally ships with Python 3.10, which is a good default for this project.
- If you change Python versions after creating `.venv`, delete `.venv` and create it again with the intended interpreter.
- The launcher scripts reuse `.venv` automatically if it exists, so an old `.venv` created with the wrong Python version will keep causing the same error until recreated.

## Quick Start

Use one of these two paths depending on your goal.

## Detailed Run Guide

This section is the recommended execution path for the current codebase, especially after the GUI visualization update to `PyQtGraph`.

Follow the steps in order.

### 1. Check Python version first

This project currently requires Python 3.10 or newer.

Windows PowerShell:

```powershell
python --version
```

Ubuntu/macOS:

```bash
python3 --version
```

If the reported version is below 3.10, do not reuse an old `.venv`.

### 2. Recreate `.venv` with the correct interpreter

If you previously created `.venv` with an older Python version, remove it and recreate it.

Windows PowerShell:

```powershell
cd C:\path\to\5gnr_phy_stl
Remove-Item -Recurse -Force .venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If activation is blocked, install packages with the local interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Ubuntu 22.04 / Ubuntu 24.04:

```bash
cd /path/to/5gnr_phy_stl
rm -rf .venv
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If `python3` already points to 3.10+:

```bash
cd /path/to/5gnr_phy_stl
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

macOS:

```bash
cd /path/to/5gnr_phy_stl
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Verify GUI dependencies

The current GUI uses `PyQt5`, `pyqtgraph`, `matplotlib`, and `dash`.

Windows PowerShell:

```powershell
python -c "import PyQt5, pyqtgraph, matplotlib, dash, plotly; print('GUI deps OK')"
```

Ubuntu/macOS:

```bash
python -c "import PyQt5, pyqtgraph, matplotlib, dash, plotly; print('GUI deps OK')"
```

If you are not activating `.venv`, use the local interpreter path instead.

### 4. Run a CLI sanity check before opening the GUI

Run a single-link simulation first:

```bash
python main.py --config configs/default.yaml
```

Expected behavior:

- the simulation completes without import errors
- KPI output is printed as JSON
- there is no startup error related to `dataclass(slots=True)`

### 5. Launch the GUI

After the CLI check succeeds, launch the dashboard:

```bash
python main.py --config configs/default.yaml --gui
```

Windows PowerShell without activation:

```powershell
.\.venv\Scripts\python.exe main.py --config configs/default.yaml --gui
```

### 6. What the current GUI shows

The current runtime plot workspace includes:

- `PHY Pipeline` tab
  - clickable block-by-block PHY flow from `Bits` through `CRC Check`
  - explicit TX, channel, and RX sections arranged as a central processing chain
  - animation controls: `Play`, `Pause`, `Prev`, `Next`, `Reset`
  - timeline scrubber for PHY stages plus frame / slot / symbol controls
  - per-stage artifact switching for bitstreams, LLRs, constellations, grids, waveforms, spectra, and KPI bars
  - symbol-aware secondary preview for grid / waveform / constellation artifacts
- `Signal Domain` tab
  - reference / pre-EQ / post-EQ constellation
  - TX/RX waveform overlay
  - TX/RX spectrum overlay
  - RX waterfall
- `Resource Grid` tab
  - TX allocation map with DMRS highlighting
  - TX grid magnitude
  - RX grid magnitude
  - estimated channel magnitude
- `Channel / Sync / EQ` tab
  - channel impulse response
  - average channel frequency response
  - approximate equalizer gain
  - sync / impairment summary
  - EVM by OFDM symbol
  - relative error by subcarrier
- `Batch Analytics` tab
  - embedded Matplotlib views for sweep results

Auxiliary instrumentation from the control panel:

- `TX sink` opens GNU Radio QT time/frequency/waterfall sinks when GNU Radio is installed
- `RX sink` opens GNU Radio QT time/constellation/frequency/waterfall sinks when GNU Radio is installed
- `Open Dash` launches a browser-based batch analytics dashboard from the latest batch CSV
- `Step Mode` runs one simulation and jumps directly into block-by-block playback inside `PHY Pipeline`

Configuration controls remain on the left, and KPI / environment status / warnings / logs remain on the right.

### 6a. How to enable `TX sink` and `RX sink` on Windows

If the `TX sink` and `RX sink` buttons are greyed out, the GUI did not detect GNU Radio in the active Python interpreter.

The GUI now shows this explicitly in the `Environment Status` panel:

- `GNU Radio bindings`
- `TX sink button`
- `RX sink button`
- `GNU Radio reason`
- `How to enable sinks`

Recommended Windows procedure:

1. Install Miniconda or Anaconda.
2. Open `Anaconda Prompt`, `Miniconda Prompt`, or `PowerShell` after `conda init powershell`.
3. Create one environment for Python, GNU Radio, and the project dependencies:

```powershell
conda create -n 5gnr-phy python=3.10 -y
conda activate 5gnr-phy
conda install -c conda-forge gnuradio -y
pip install -r requirements.txt
```

4. Verify the same interpreter can import GNU Radio:

```powershell
python -c "import sys; print(sys.executable)"
python -c "import gnuradio; print('GNU Radio import OK')"
```

5. Launch the GUI from that same shell:

```powershell
python main.py --config configs/default.yaml --gui
```

Important notes:

- You must close and reopen the GUI after installing GNU Radio.
- The `Use GNU Radio loopback` checkbox does not enable the buttons by itself.
- The buttons are enabled only when `import gnuradio` succeeds in the interpreter that launched the GUI.

### 7. Run common scenarios

Default GUI:

```bash
python main.py --config configs/default.yaml --gui
```

Vehicular scenario:

```bash
python main.py --config configs/default.yaml --override configs/scenario_vehicular.yaml --gui
```

Python-only CLI:

```bash
python main.py --config configs/default.yaml
```

Batch BER sweep:

```bash
python run_experiments.py --experiment ber_vs_snr --config configs/default.yaml --output-dir outputs
```

Student testcase bundle:

```bash
python run_student_testcases.py --config configs/default.yaml --output-dir outputs/student_testcases
```

Run individual student testcases:

```bash
python run_student_testcases.py --config configs/default.yaml --case-id TC2 --output-dir outputs/student_testcases_tc2
python run_student_testcases.py --config configs/default.yaml --case-id TC3 --output-dir outputs/student_testcases_tc3
python run_student_testcases.py --config configs/default.yaml --case-id TC5 --output-dir outputs/student_testcases_tc5
```

Showcase bundle:

```bash
python run_showcases.py --config configs/default.yaml --output-dir outputs/showcases
```

Windows PowerShell launcher examples:

```powershell
.\run_python_only.bat
.\run_gui.bat
.\run_student_testcases.bat
.\run_showcases.bat
```

### 8. Common failure modes

`TypeError: dataclass() got an unexpected keyword argument 'slots'`

- You are using Python 3.9 or older.
- Or `.venv` was created with an older interpreter and is still being reused.
- Fix: delete `.venv`, recreate it with Python 3.10+, then reinstall dependencies.

`ModuleNotFoundError: No module named 'pyqtgraph'`

- The updated GUI dependency is not installed.
- Fix:

```bash
pip install -r requirements.txt
```

`ModuleNotFoundError: No module named 'PyQt5'`

- GUI dependencies are missing from the active environment.
- Fix:

```bash
pip install -r requirements.txt
```

`ModuleNotFoundError: No module named 'dash'` or `No module named 'plotly'`

- Batch analytics dependencies are missing from the active environment.
- Fix:

```bash
pip install -r requirements.txt
```

`ERROR: Could not open requirements file: [Errno 2] No such file or directory: 'requirements.txt'`

- You are not running the command from the project root directory.
- PowerShell is looking for `requirements.txt` in the current directory, and it is not there.

Check the current directory:

```powershell
Get-Location
```

Move to the project root:

```powershell
cd D:\Data\Lectures\20252\MobiCom\Codex\5GNRPHYSITL\5gnr_phy_stl
```

Verify the file exists:

```powershell
Test-Path .\requirements.txt
```

Then rerun:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If you do not want to rely on the current directory, use an absolute path:

```powershell
.\.venv\Scripts\python.exe -m pip install -r D:\Data\Lectures\20252\MobiCom\Codex\5GNRPHYSITL\5gnr_phy_stl\requirements.txt
```

`run_*.bat` is not recognized in PowerShell

- PowerShell does not execute scripts from the current directory unless prefixed.
- Fix:

```powershell
.\run_showcases.bat
.\run_student_testcases.bat
.\run_gui.bat
```

### 9. Suggested operating sequence

For a clean run, use this order:

1. Check Python version.
2. Recreate `.venv` if needed.
3. Install requirements.
4. Run `python main.py --config configs/default.yaml`.
5. Launch `python main.py --config configs/default.yaml --gui`.

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
python --version
# expect Python 3.10 or newer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If `python` works but `py` does not, that is normal on some Windows setups. Use `python -m venv .venv`.

If PowerShell blocks `.\.venv\Scripts\Activate.ps1`, use one of these alternatives:

```powershell
.\.venv\Scripts\activate.bat
```

If you are using `cmd.exe` instead of PowerShell:

```cmd
.venv\Scripts\activate.bat
```

or run the virtual-environment Python directly without activation:

```powershell
.\.venv\Scripts\python.exe main.py --config configs/default.yaml
```

Ubuntu 22.04 / Ubuntu 24.04:

```bash
cd /path/to/5gnr_phy_stl
python3 --version
# on Ubuntu 22.04 this should normally be Python 3.10.x
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If `python3 --version` is older than 3.10, use a newer interpreter explicitly:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

macOS:

```bash
cd /path/to/5gnr_phy_stl
python3 --version
# expect Python 3.10 or newer
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If macOS still points `python3` to an older version, install a newer interpreter first, for example with Homebrew, then recreate `.venv` with that interpreter.

2. Run a single link simulation.

Where to run this command:

- On Windows: run it in the same `PowerShell`, `cmd.exe`, or `Anaconda Prompt` where the environment is already active.
- If you did not activate the virtual environment, use the local interpreter path instead of `python`, for example `.\.venv\Scripts\python.exe` in PowerShell.
- On Linux/macOS: run it in the terminal where `.venv` is already activated.

```bash
python main.py --config configs/default.yaml
```

Windows without activation:

```powershell
.\.venv\Scripts\python.exe main.py --config configs/default.yaml
```

3. Launch the research GUI.

Where to run this command:

- On Windows: use the same shell where the environment is active.
- If activation is blocked, call `.\.venv\Scripts\python.exe` directly in PowerShell.
- On Linux/macOS: use the terminal where `.venv` is active.

```bash
python main.py --config configs/default.yaml --gui
```

Windows without activation:

```powershell
.\.venv\Scripts\python.exe main.py --config configs/default.yaml --gui
```

4. Run a quick batch sweep.

Where to run this command:

- On Windows: use the same shell where the environment is active.
- If activation is blocked, call `.\.venv\Scripts\python.exe` directly in PowerShell.
- On Linux/macOS: use the terminal where `.venv` is active.

```bash
python run_experiments.py --experiment ber_vs_snr --config configs/default.yaml --output-dir outputs
```

Windows without activation:

```powershell
.\.venv\Scripts\python.exe run_experiments.py --experiment ber_vs_snr --config configs/default.yaml --output-dir outputs
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
- Before creating a GNU Radio Conda environment, check the interpreter version with `python --version` or `conda run -n 5gnr-phy python --version`.
- In the GUI, `TX sink` and `RX sink` are enabled only when the `Environment Status` panel reports `GNU Radio bindings: Available`.

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
.\run_gui_radioconda.bat
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
run_gui_radioconda.bat
run_batch_ber.bat
run_gnuradio.bat
run_vehicular.bat
run_student_testcases.bat
run_showcases.bat
```

### Windows PowerShell Radioconda launcher

If you already installed Radioconda and want `TX sink` / `RX sink` to work, use the dedicated launcher:

```powershell
.\run_gui_radioconda.ps1
```

If PowerShell blocks local scripts, use:

```powershell
.\run_gui_radioconda.bat
```

Useful options:

```powershell
.\run_gui_radioconda.ps1 -PrintOnly
.\run_gui_radioconda.ps1 -InstallRequirements
.\run_gui_radioconda.ps1 -UseGnuRadioLoopback
.\run_gui_radioconda.ps1 -PythonPath C:\path\to\radioconda\python.exe
```

What it does:

- searches common Radioconda and Forge-style Windows install locations
- tests candidate interpreters with the exact GNU Radio QT import used by the GUI
- launches `main.py --gui` with the first interpreter that passes
- optionally enables the GNU Radio loopback override

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
- If `.venv` was created with the wrong Python version, remove it and recreate it before relying on the launchers.
- Extra command-line arguments are passed through to the underlying Python command.
- `make test` requires `pytest` to be installed in the active environment.
- For end-to-end installation procedures and automation scripts, see [`docs/INSTALLATION_WORKFLOWS.md`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/docs/INSTALLATION_WORKFLOWS.md).
- For a classroom-oriented walkthrough, see `docs/STUDENT_TESTCASES.md`.
- For deeper 3GPP-inspired teaching demos, see `docs/SHOWCASES_3GPP_PHY.md`.
- For GUI parameter meanings, ranges, units, and symbols, see `docs/SIMULATION_PARAMETER_REFERENCE.md`.
- For the proposed GUI architecture and PHY screen inventory, see `docs/GUI_ARCHITECTURE.md`.
- For a deep comparison between this simulator and real-world 5G systems, see `docs/REAL_5G_SYSTEM_VS_PROJECT.md`.
- For a stage-by-stage technical explanation of the PHY chain aligned with the GUI pipeline, see `docs/TECHDOC_5G_NR_PHY_TRACE.md`.
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
â”œâ”€â”€ README.md
â”œâ”€â”€ requirements.txt
â”œâ”€â”€ main.py
â”œâ”€â”€ run_experiments.py
â”œâ”€â”€ configs/
â”œâ”€â”€ phy/
â”œâ”€â”€ channel/
â”œâ”€â”€ grc/
â”œâ”€â”€ gui/
â”œâ”€â”€ experiments/
â”œâ”€â”€ utils/
â””â”€â”€ tests/
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
- Dedicated `PHY Pipeline` tab that shows the full stage sequence:
  - traffic / transport block
  - CRC + channel coding
  - scrambling
  - modulation mapping
  - resource-grid mapping
  - DMRS insertion
  - OFDM modulation
  - impairments / fading / AWGN
  - timing and CFO correction
  - OFDM demodulation
  - channel estimation
  - equalization
  - soft demapping / descrambling
  - decoding + CRC
- Interactive PHY flow controls:
  - clickable stage blocks in the main chain
  - play / pause / next / previous / reset animation controls
  - stage timeline scrubber
  - frame / slot / symbol scrubbers
  - artifact selector per stage
- Real-time plot areas for constellation, waveform, spectrum, TX resource-grid allocation, impulse response, and estimated channel.
- Batch analytics tab rendered with embedded Matplotlib.
- Dash launcher for browser-based analytics.
- GNU Radio TX/RX sink launchers for QT instrumentation when GNU Radio is installed.
- KPI table, warnings/assumptions panel, and log pane.

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
- Check the interpreter version before creating `.venv` or Conda environments.
- If an existing `.venv` was created with an unsupported Python version, delete it and recreate it.

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
python --version
# expect Python 3.10 or newer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If your system does not recognize `py`, use `python -m venv .venv` as shown above.

If PowerShell blocks `.\.venv\Scripts\Activate.ps1`, either use:

```powershell
.\.venv\Scripts\activate.bat
```

If you are using `cmd.exe` instead of PowerShell:

```cmd
.venv\Scripts\activate.bat
```

or call the interpreter directly:

```powershell
.\.venv\Scripts\python.exe main.py --config configs/default.yaml
```

Recommended verification after install:

```powershell
python --version
python -c "import numpy, scipy, matplotlib, pandas, yaml; print('core imports OK')"
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
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If `python3 --version` is below 3.10, install and use Python 3.10 explicitly:

```bash
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip
cd /path/to/5gnr_phy_stl
python3.10 -m venv .venv
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

#### `TypeError: dataclass() got an unexpected keyword argument 'slots'`

Typical symptom:

- startup fails very early while importing project modules
- traceback points to a line such as `@dataclass(slots=True)`

What it means:

- you are not running the project with Python 3.10 or newer
- or your current `.venv` was created with an older interpreter and is still being reused

What to do on Ubuntu 22.04/24.04:

```bash
python3 --version
rm -rf .venv
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python --version
```

What to do on macOS:

```bash
python3 --version
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python --version
```

If `python3 --version` is still below 3.10 on macOS, install a newer Python first, then recreate `.venv` with that interpreter.

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

#### `TX sink` and `RX sink` are greyed out in the GUI

Typical reason:

- the GUI was launched from a Python interpreter that cannot import `gnuradio`

What to do on Windows:

```powershell
python -c "import sys; print(sys.executable)"
python -c "import gnuradio; print('GNU Radio import OK')"
```

If the second command fails, do not use the current `.venv` for GNU Radio sinks. Instead:

```powershell
conda create -n 5gnr-phy python=3.10 -y
conda activate 5gnr-phy
conda install -c conda-forge gnuradio -y
pip install -r requirements.txt
python main.py --config configs/default.yaml --gui
```

Use the GUI `Environment Status` panel to confirm:

- `GNU Radio bindings: Available`
- `TX sink button: Enabled`
- `RX sink button: Enabled`

#### PowerShell execution policy blocks virtual environment activation

Typical symptom:

- `.\.venv\Scripts\Activate.ps1` is blocked by PowerShell

What to do:

- Use a per-user execution policy:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

- Then reopen PowerShell and activate the environment again.
- If you do not want to change PowerShell policy, run the batch activator in PowerShell:

```powershell
.\.venv\Scripts\activate.bat
```

- If you are using `cmd.exe`, run:

```cmd
.venv\Scripts\activate.bat
```

- You can also skip activation entirely and call the local interpreter directly:

```powershell
.\.venv\Scripts\python.exe main.py --config configs/default.yaml
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
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

- Then run the script with the same interpreter:

```powershell
.\.venv\Scripts\python.exe run_student_testcases.py --config configs/default.yaml --output-dir outputs/student_testcases
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


