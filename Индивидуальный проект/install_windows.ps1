Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceEditor = Join-Path $scriptDir "editor.py"

if (-not (Test-Path -LiteralPath $sourceEditor)) {
    throw "editor.py not found next to installer: $sourceEditor"
}

$installDir = Join-Path $env:LOCALAPPDATA "pop-editor"
$binDir = Join-Path $env:USERPROFILE "bin"
$launcherPath = Join-Path $binDir "pop.cmd"
$targetEditor = Join-Path $installDir "editor.py"

New-Item -ItemType Directory -Path $installDir -Force | Out-Null
New-Item -ItemType Directory -Path $binDir -Force | Out-Null
Copy-Item -LiteralPath $sourceEditor -Destination $targetEditor -Force

$launcher = @'
@echo off
setlocal

set "SCRIPT=%LOCALAPPDATA%\pop-editor\editor.py"

if not exist "%SCRIPT%" (
    echo error: "%SCRIPT%" not found. Re-run install_windows.ps1.
    exit /b 1
)

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%SCRIPT%" %*
    exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%SCRIPT%" %*
    exit /b %errorlevel%
)

echo error: Python is not installed or not in PATH.
exit /b 1
'@

Set-Content -LiteralPath $launcherPath -Value $launcher -Encoding Ascii

$userPathRaw = [Environment]::GetEnvironmentVariable("Path", "User")
$pathItems = @()
if (-not [string]::IsNullOrWhiteSpace($userPathRaw)) {
    $pathItems = $userPathRaw -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
}

$pathChanged = $false
if ($pathItems -notcontains $binDir) {
    $newPath = (($pathItems + $binDir) -join ";").Trim(";")
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    $pathChanged = $true
}

$pythonCommand = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = "py"
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = "python"
}

if ($pythonCommand -eq "py") {
    & py -3 -c "import blessed" *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing Python dependency: blessed"
        & py -3 -m pip install --user blessed
    }
}
elseif ($pythonCommand -eq "python") {
    & python -c "import blessed" *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing Python dependency: blessed"
        & python -m pip install --user blessed
    }
}
else {
    Write-Warning "Python not found during install. 'pop' will work after Python is installed."
}

Write-Host "Installation complete."
if ($pathChanged) {
    Write-Host "Open a new terminal to refresh PATH."
}
Write-Host "Usage:"
Write-Host "  pop C:\Users\user\1.txt"
