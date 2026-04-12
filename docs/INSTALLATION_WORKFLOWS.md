# Installation Workflows

This document consolidates installation workflows for the supported operating systems and maps them to reusable installer scripts under [`install/`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/install).

## Goals

- provide reproducible setup steps for classroom and research use
- separate `Python-only` and `GNU Radio` workflows
- make Windows, Ubuntu, and macOS setup paths explicit
- keep the final runtime interpreter obvious for GUI and GNU Radio sink usage

## Official Reference Points

Use these upstream documents as the authoritative reference when local platform behavior changes:

- GNU Radio installation overview: [InstallingGR](https://wiki.gnuradio.org/index.php/InstallingGR)
- GNU Radio conda-based install: [CondaInstall](https://wiki.gnuradio.org/index.php/CondaInstall)
- GNU Radio Linux install notes: [LinuxInstall](https://wiki.gnuradio.org/index.php/LinuxInstall)
- GNU Radio macOS install notes: [MacInstall](https://wiki.gnuradio.org/index.php/MacInstall)
- Radioconda project: [radioconda](https://github.com/ryanvolz/radioconda)

## Workflow Matrix

| OS | Profile | External resources installed | Script |
| --- | --- | --- | --- |
| Windows 10/11 | Python-only | Python 3.10+, `venv`, project Python packages | [`install/windows-python-only.ps1`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/install/windows-python-only.ps1) |
| Windows 10/11 | Radioconda + GNU Radio | Radioconda interpreter, GNU Radio QT bindings, project Python packages | [`install/windows-radioconda.ps1`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/install/windows-radioconda.ps1) |
| Ubuntu 22.04/24.04 | Python-only | `apt` Python packages, `venv`, project Python packages | [`install/ubuntu-python-only.sh`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/install/ubuntu-python-only.sh) |
| Ubuntu 22.04/24.04 | GNU Radio + `venv` | `apt` GNU Radio, `venv --system-site-packages`, project Python packages | [`install/ubuntu-gnuradio.sh`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/install/ubuntu-gnuradio.sh) |
| macOS | Python-only | Homebrew Python 3.11, `venv`, project Python packages | [`install/macos-python-only.sh`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/install/macos-python-only.sh) |
| macOS | GNU Radio + `venv` | Homebrew GNU Radio, `venv --system-site-packages`, project Python packages | [`install/macos-gnuradio.sh`](/D:/Data/Lectures/20252/MobiCom/Codex/5GNRPHYSITL/5gnr_phy_stl/install/macos-gnuradio.sh) |

## Windows 10/11

### Python-only profile

Use when you need:

- the simulator core
- the PyQt GUI
- batch experiments
- teaching demos without GNU Radio sinks

Run from PowerShell:

```powershell
cd D:\path\to\5gnr_phy_stl
.\install\windows-python-only.ps1
```

Useful options:

```powershell
.\install\windows-python-only.ps1 -Force
.\install\windows-python-only.ps1 -DryRun
.\install\windows-python-only.ps1 -PythonCommand py
```

### Radioconda + GNU Radio profile

Use when you need:

- `TX sink`
- `RX sink`
- GNU Radio loopback
- the GUI to run with actual GNU Radio QT bindings

Prerequisite:

- Radioconda must already be installed on the machine

Run from PowerShell:

```powershell
cd D:\path\to\5gnr_phy_stl
.\install\windows-radioconda.ps1 -InstallRequirements
```

To immediately launch the GUI:

```powershell
.\install\windows-radioconda.ps1 -InstallRequirements -LaunchGui
```

To launch with the GNU Radio loopback override:

```powershell
.\install\windows-radioconda.ps1 -InstallRequirements -LaunchGui -UseGnuRadioLoopback
```

If the script cannot find Radioconda automatically, pass the interpreter explicitly:

```powershell
.\install\windows-radioconda.ps1 -PythonPath C:\Users\<user>\AppData\Local\radioconda\python.exe -InstallRequirements
```

## Ubuntu 22.04 / 24.04

### Python-only profile

```bash
cd /path/to/5gnr_phy_stl
chmod +x install/ubuntu-python-only.sh
./install/ubuntu-python-only.sh
```

Dry-run:

```bash
./install/ubuntu-python-only.sh --dry-run
```

### GNU Radio profile

This workflow installs GNU Radio from `apt`, then creates `.venv-gr` with `--system-site-packages` so the project environment can still see the system GNU Radio packages.

```bash
cd /path/to/5gnr_phy_stl
chmod +x install/ubuntu-gnuradio.sh
./install/ubuntu-gnuradio.sh
```

Dry-run:

```bash
./install/ubuntu-gnuradio.sh --dry-run
```

Recommended runtime:

```bash
./.venv-gr/bin/python main.py --config configs/default.yaml --gui
```

## macOS

### Python-only profile

```bash
cd /path/to/5gnr_phy_stl
chmod +x install/macos-python-only.sh
./install/macos-python-only.sh
```

Dry-run:

```bash
./install/macos-python-only.sh --dry-run
```

### GNU Radio profile

This workflow is best-effort because Homebrew Python / GNU Radio combinations can vary over time.

```bash
cd /path/to/5gnr_phy_stl
chmod +x install/macos-gnuradio.sh
./install/macos-gnuradio.sh
```

If Homebrew installed GNU Radio against a different Python than the current `python3`, override `PYTHON_BIN`:

```bash
PYTHON_BIN="$(brew --prefix python@3.11)/bin/python3.11" ./install/macos-gnuradio.sh
```

Dry-run:

```bash
./install/macos-gnuradio.sh --dry-run
```

## Post-install Verification

### Python-only verification

```bash
python main.py --config configs/default.yaml
python main.py --config configs/default.yaml --gui
```

### GNU Radio verification

Verify the exact import path used by the GUI:

```bash
python -c "import sys; print(sys.executable)"
python -c "from gnuradio import blocks, gr, qtgui; from gnuradio.fft import window; print('GNU Radio QT import OK')"
```

If the second command fails, do not expect `TX sink` / `RX sink` to be enabled.

## Practical Recommendations

- Windows:
  use `Python-only` for the simplest classroom workflow, or `Radioconda + GNU Radio` if you need QT sinks
- Ubuntu:
  use the `apt + .venv-gr` path for the most predictable GNU Radio setup
- macOS:
  treat GNU Radio support as best-effort and verify imports explicitly before relying on QT sinks
