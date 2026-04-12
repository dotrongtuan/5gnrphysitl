param(
    [string]$ProjectRoot = "",
    [string]$PythonCommand = "python",
    [string]$VenvName = ".venv",
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
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

$python = (Get-Command $PythonCommand -ErrorAction Stop).Source
$versionText = & $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if (-not $DryRun -and [version]$versionText -lt [version]"3.10") {
    throw "Python 3.10+ is required. Active interpreter: $python ($versionText)"
}

$venvPath = Join-Path $ProjectRoot $VenvName
$venvPython = Join-Path $venvPath "Scripts\python.exe"

Push-Location $ProjectRoot
try {
    if ((Test-Path $venvPath) -and $Force) {
        Write-Host "+ Remove-Item -Recurse -Force $venvPath"
        if (-not $DryRun) {
            Remove-Item -Recurse -Force $venvPath
        }
    }

    Invoke-Step -FilePath $python -Arguments @("-m", "venv", $VenvName)
    Invoke-Step -FilePath $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-Step -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", "requirements.txt")
    Invoke-Step -FilePath $venvPython -Arguments @(
        "-c",
        "import PyQt5, pyqtgraph, matplotlib, dash, plotly, numpy, scipy, pandas, yaml; print('Python-only environment OK')"
    )
}
finally {
    Pop-Location
}
