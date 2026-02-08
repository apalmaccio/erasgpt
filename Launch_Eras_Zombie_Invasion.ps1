$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonDir = Join-Path $scriptDir ".python"
$pythonExe = Join-Path $pythonDir "python.exe"

function Get-EmbeddablePython {
    param (
        [string]$DestinationDir
    )

    $version = "3.11.9"
    $zipName = "python-$version-embed-amd64.zip"
    $zipUrl = "https://www.python.org/ftp/python/$version/$zipName"
    $tempZip = Join-Path $env:TEMP $zipName

    Write-Host "Downloading Python $version..."
    Invoke-WebRequest -Uri $zipUrl -OutFile $tempZip

    if (Test-Path $DestinationDir) {
        Remove-Item -Recurse -Force $DestinationDir
    }
    New-Item -ItemType Directory -Path $DestinationDir | Out-Null
    Expand-Archive -Path $tempZip -DestinationPath $DestinationDir -Force
    Remove-Item $tempZip

    $pthFile = Get-ChildItem -Path $DestinationDir -Filter "python*._pth" | Select-Object -First 1
    if ($null -ne $pthFile) {
        $lines = Get-Content $pthFile.FullName
        $updated = $lines | ForEach-Object {
            if ($_ -match "^#\s*import site") { "import site" } else { $_ }
        }
        Set-Content -Path $pthFile.FullName -Value $updated
    }
}

function Ensure-Pip {
    param (
        [string]$PythonPath
    )

    $getPipPath = Join-Path $scriptDir "get-pip.py"
    if (-not (Test-Path $getPipPath)) {
        Write-Host "Downloading pip bootstrap..."
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPipPath
    }
    & $PythonPath $getPipPath
}

if (-not (Test-Path $pythonExe)) {
    Get-EmbeddablePython -DestinationDir $pythonDir
}

Ensure-Pip -PythonPath $pythonExe

Write-Host "Installing game dependencies..."
& $pythonExe -m pip install -e $scriptDir

Write-Host "Launching Eras Zombie Invasion..."
& $pythonExe (Join-Path $scriptDir "launch_eras_zombie_invasion.py")
