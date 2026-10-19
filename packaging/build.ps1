# Builds the standalone PS5HealthWarningEditor.exe and the release zip.
#
# Usage (from anywhere):
#   powershell -ExecutionPolicy Bypass -File A:\ps5-health-warning-editor\packaging\build.ps1
#   powershell ... -File ...\build.ps1 -SkipTests
[CmdletBinding()]
param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$match = Select-String -Path (Join-Path $root "src\ps5_health_warning_editor\version.py") `
    -Pattern '__version__\s*=\s*"([^"]+)"'
if (-not $match) { throw "Could not read __version__" }
$version = $match.Matches[0].Groups[1].Value
Write-Host "== PS5 Health Warning Editor $version ==" -ForegroundColor Cyan

if (-not $SkipTests) {
    Write-Host "Running tests..."
    python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed" }

    Write-Host "Running ruff..."
    python -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw "Lint failed" }
}

Write-Host "Building one-file windowed exe..."
python -m PyInstaller --noconfirm --clean (Join-Path $root "packaging\PS5HealthWarningEditor.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$exe = Join-Path $root "dist\PS5HealthWarningEditor.exe"
if (-not (Test-Path $exe)) { throw "Missing $exe" }

Write-Host "Smoke-testing the frozen build..."
$proc = Start-Process -FilePath $exe -ArgumentList "--smoke-test" -PassThru -Wait
if ($proc.ExitCode -ne 0) { throw "Smoke test failed with exit code $($proc.ExitCode)" }

$hash = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant()
$shaFile = "$exe.sha256"
"$hash *PS5HealthWarningEditor.exe" | Set-Content -Path $shaFile -Encoding ascii
Write-Host "SHA256: $hash"

# Release zip: exe + docs + checksum.
$release = Join-Path $root "release"
$stage = Join-Path $root "build\release-stage"
Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage | Out-Null
New-Item -ItemType Directory -Force -Path $release | Out-Null

Copy-Item $exe $stage
Copy-Item (Join-Path $root "README.md") $stage
Copy-Item (Join-Path $root "CHANGELOG.md") $stage
Copy-Item (Join-Path $root "LICENSE") $stage
Copy-Item (Join-Path $root "START-HERE.txt") $stage
Copy-Item (Join-Path $root "docs") $stage -Recurse
Copy-Item $shaFile $stage

Copy-Item $shaFile $release -Force
Copy-Item $exe $release -Force
$zip = Join-Path $release "PS5-Health-Warning-Editor-$version-win64.zip"
Remove-Item -Force $zip -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip

Write-Host ""
Write-Host "Release folder:" -ForegroundColor Green
Get-ChildItem $release | Select-Object Name, Length | Format-Table -AutoSize
Write-Host "Done."
