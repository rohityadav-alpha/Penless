# Penless — Build & Publish Script
# Usage: .\publish.ps1
# Produces a self-contained single-file Windows executable in .\publish\

$ErrorActionPreference = "Stop"

$project = "src\Penless.Desktop\Penless.Desktop.csproj"
$output  = "publish"
$rid     = "win-x64"

Write-Host ""
Write-Host "Penless — Publishing Release Build" -ForegroundColor Cyan
Write-Host ""

Write-Host "Cleaning previous output..." -ForegroundColor Yellow
if (Test-Path $output) { Remove-Item $output -Recurse -Force }

Write-Host "Building and publishing..." -ForegroundColor Yellow
dotnet publish $project `
    --configuration Release `
    --runtime $rid `
    --self-contained true `
    --output $output `
    -p:PublishSingleFile=true `
    -p:EnableCompressionInSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:PublishReadyToRun=true

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Publish failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

# Create default SharedFiles folder next to the exe
$sharedDir = Join-Path $output "SharedFiles"
if (-not (Test-Path $sharedDir)) {
    New-Item -ItemType Directory -Path $sharedDir | Out-Null
}

Write-Host ""
Write-Host "Done! Executable is at: $output\Penless.exe" -ForegroundColor Green
Write-Host ""
