param(
    [string]$ProjectRoot = "",
    [string]$PythonPath = "",
    [switch]$InstallRequirements,
    [switch]$LaunchGui,
    [switch]$UseGnuRadioLoopback,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

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

function Invoke-Step {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )
    $rendered = @($FilePath) + $Arguments
    Write-Host "+ $($rendered -join ' ')"
    if (-not $DryRun) {
        & $FilePath @Arguments
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
    "$env:LOCALAPPDATA\radioconda",
    "$env:USERPROFILE\radioconda",
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
    throw @"
No Radioconda-style Python interpreter with GNU Radio QT bindings was found.

Install Radioconda first, or pass the interpreter explicitly:
install\windows-radioconda.ps1 -PythonPath C:\path\to\radioconda\python.exe
"@
}

Push-Location $ProjectRoot
try {
    if ($InstallRequirements) {
        Invoke-Step -FilePath $selected -Arguments @("-m", "pip", "install", "--upgrade", "pip")
        Invoke-Step -FilePath $selected -Arguments @("-m", "pip", "install", "-r", "requirements.txt")
    }

    Invoke-Step -FilePath $selected -Arguments @("-c", "import sys; print(sys.executable)")
    Invoke-Step -FilePath $selected -Arguments @("-c", $importSnippet)

    if ($LaunchGui) {
        $commandArgs = @("main.py", "--config", "configs/default.yaml", "--gui")
        if ($UseGnuRadioLoopback) {
            $commandArgs += @("--override", "configs/scenario_gnuradio.yaml")
        }
        Invoke-Step -FilePath $selected -Arguments $commandArgs
    }
    else {
        Write-Host "Selected GNU Radio interpreter: $selected"
        Write-Host "Next step:"
        Write-Host "  $selected main.py --config configs/default.yaml --gui"
    }
}
finally {
    Pop-Location
}
