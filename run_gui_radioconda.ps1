param(
    [string]$PythonPath = "",
    [switch]$InstallRequirements,
    [switch]$UseGnuRadioLoopback,
    [switch]$PrintOnly,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AppArgs
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$importSnippet = "from gnuradio import blocks, gr, qtgui; from gnuradio.fft import window; print('GNU Radio QT import OK')"

function Add-Candidate {
    param(
        [System.Collections.Generic.List[string]]$List,
        [string]$PathValue
    )
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return
    }
    if (Test-Path $PathValue) {
        $resolved = (Resolve-Path $PathValue).Path
        if (-not $List.Contains($resolved)) {
            $List.Add($resolved)
        }
    }
}

function Test-GnuRadioPython {
    param([string]$Candidate)
    try {
        $output = & $Candidate -c $importSnippet 2>&1
        return ($LASTEXITCODE -eq 0) -and (($output | Out-String) -match "GNU Radio QT import OK")
    }
    catch {
        return $false
    }
}

$candidates = [System.Collections.Generic.List[string]]::new()

if ($PythonPath) {
    Add-Candidate -List $candidates -PathValue $PythonPath
}

try {
    Add-Candidate -List $candidates -PathValue (Get-Command python -ErrorAction Stop).Source
}
catch {
}

$roots = @(
    "$env:USERPROFILE\radioconda",
    "$env:LOCALAPPDATA\radioconda",
    "C:\radioconda",
    "$env:USERPROFILE\miniforge3",
    "$env:USERPROFILE\mambaforge"
)

foreach ($root in $roots) {
    Add-Candidate -List $candidates -PathValue (Join-Path $root "python.exe")
    $envRoot = Join-Path $root "envs"
    if (Test-Path $envRoot) {
        Get-ChildItem $envRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            Add-Candidate -List $candidates -PathValue (Join-Path $_.FullName "python.exe")
        }
    }
}

$selected = $null
foreach ($candidate in $candidates) {
    Write-Host "Checking GNU Radio interpreter candidate: $candidate"
    if (Test-GnuRadioPython -Candidate $candidate) {
        $selected = $candidate
        break
    }
}

if (-not $selected) {
    Write-Error @"
No Python interpreter with GNU Radio QT bindings was found.

What to do next:
1. Open Radioconda Prompt or install Radioconda if it is not present.
2. Verify GNU Radio with:
   python -c "from gnuradio import blocks, gr, qtgui; from gnuradio.fft import window; print('GNU Radio QT import OK')"
3. Re-run this launcher, or pass the interpreter explicitly:
   .\run_gui_radioconda.ps1 -PythonPath C:\path\to\radioconda\python.exe
"@
    exit 1
}

if ($PrintOnly) {
    Write-Output $selected
    exit 0
}

Push-Location $projectRoot
try {
    if ($InstallRequirements) {
        & $selected -m pip install --upgrade pip
        & $selected -m pip install -r requirements.txt
    }

    $commandArgs = @("main.py", "--config", "configs/default.yaml", "--gui")
    if ($UseGnuRadioLoopback) {
        $commandArgs += @("--override", "configs/scenario_gnuradio.yaml")
    }
    if ($AppArgs) {
        $commandArgs += $AppArgs
    }

    Write-Host "Launching GUI with GNU Radio interpreter: $selected"
    & $selected @commandArgs
}
finally {
    Pop-Location
}
