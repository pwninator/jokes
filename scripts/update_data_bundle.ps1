param(
  [string]$SecretPath = "$PSScriptRoot\\.bundle_secret.local",
  [string]$BundleEndpoint = "https://snickerdoodlejokes.com/get_joke_bundle",
  [string]$BundleDir = "assets/data_bundles",
  [string]$DartBundleFile = "lib/src/startup/offline_bundle_loader.dart",
  [string]$BackupDir = "scripts/data_bundle_backups",
  [switch]$SkipImageDownload
)

$ErrorActionPreference = 'Stop'

function Write-Info($message) {
  Write-Host "[bundle-update] $message"
}

function Get-UniquePath($path) {
  if (-not (Test-Path $path)) {
    return $path
  }

  $dir = Split-Path -Parent $path
  $name = [System.IO.Path]::GetFileNameWithoutExtension($path)
  $ext = [System.IO.Path]::GetExtension($path)
  $suffix = Get-Date -Format "yyyyMMdd_HHmmss"
  return Join-Path $dir "$name`_$suffix$ext"
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

if (-not (Test-Path $SecretPath)) {
  throw "Secret file not found: $SecretPath"
}

$secret = (Get-Content -Raw -Path $SecretPath).Trim()
if ([string]::IsNullOrWhiteSpace($secret)) {
  throw "Secret file is empty: $SecretPath"
}

Write-Info "Requesting bundle URL..."
$response = Invoke-WebRequest `
  -Method Post `
  -Uri $BundleEndpoint `
  -Headers @{ "X-Bundle-Secret" = $secret } `
  -UseBasicParsing `
  -ErrorAction Stop

if ($response.StatusCode -ne 200) {
  throw "Bundle request failed with status $($response.StatusCode)"
}

$payload = $response.Content | ConvertFrom-Json
$bundleUrl = $payload.data.bundle_url
if (-not $bundleUrl) {
  throw "Bundle URL missing from response."
}

$remoteFileName = [System.IO.Path]::GetFileName($bundleUrl)
if ([string]::IsNullOrWhiteSpace($remoteFileName)) {
  $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $remoteFileName = "firestore_bundle_$timestamp.txt"
}

$bundleDirFull = Join-Path $repoRoot $BundleDir
if (-not (Test-Path $bundleDirFull)) {
  Write-Info "Creating bundle directory: $bundleDirFull"
  New-Item -ItemType Directory -Force -Path $bundleDirFull | Out-Null
}

$newBundlePath = Get-UniquePath (Join-Path $bundleDirFull $remoteFileName)
$bundleDirForDart = $BundleDir -replace '\\', '/'
$newBundleRelative = "$bundleDirForDart/$([System.IO.Path]::GetFileName($newBundlePath))"

Write-Info "Downloading bundle to $newBundlePath"
Invoke-WebRequest -Uri $bundleUrl -OutFile $newBundlePath -ErrorAction Stop

$dartPath = Join-Path $repoRoot $DartBundleFile
if (-not (Test-Path $dartPath)) {
  throw "Dart file not found: $dartPath"
}

$dartContent = Get-Content -Raw -Path $dartPath
$pattern = "bundlePath\s*=\s*'([^']+)'"
$match = [regex]::Match($dartContent, $pattern)
if (-not $match.Success) {
  throw "bundlePath constant not found in $dartPath"
}

$oldRelative = $match.Groups[1].Value.Trim()

$oldBundlePath = Join-Path $repoRoot ($oldRelative -replace '/', '\')
if ((Test-Path $oldBundlePath) -and ($oldBundlePath -ne $newBundlePath)) {
  $backupDirFull = Join-Path $repoRoot $BackupDir
  if (-not (Test-Path $backupDirFull)) {
    Write-Info "Creating backup directory: $backupDirFull"
    New-Item -ItemType Directory -Force -Path $backupDirFull | Out-Null
  }

  $backupPath = Join-Path $backupDirFull (Split-Path -Leaf $oldBundlePath)
  $backupPath = Get-UniquePath $backupPath
  Write-Info "Archiving previous bundle to $backupPath"
  Move-Item -Path $oldBundlePath -Destination $backupPath -Force
}

$regex = [regex]$pattern
$updatedContent = $regex.Replace(
  $dartContent,
  "bundlePath = '$newBundleRelative'",
  1
)

[System.IO.File]::WriteAllText(
  $dartPath,
  $updatedContent,
  [System.Text.UTF8Encoding]::new($false)
)

Write-Info "Updated bundle path in $DartBundleFile"

if (-not $SkipImageDownload) {
  $imageScript = Join-Path $PSScriptRoot "download_bundle_images.ps1"
  $imageOutputDir = Join-Path $bundleDirFull "images"
  $manifestPath = Join-Path $bundleDirFull "image_manifest.json"

  Write-Info "Refreshing bundled images and manifest..."
  & $imageScript `
    -BundlePath $newBundlePath `
    -OutputDir $imageOutputDir `
    -ManifestPath $manifestPath
}

Write-Info "Done."
