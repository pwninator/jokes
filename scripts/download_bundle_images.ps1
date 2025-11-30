param(
  [string]$BundlePath = "assets\data_bundles\firestore_bundle.txt",
  [string]$OutputDir = "assets\data_bundles\images",
  [string]$ManifestPath = "assets\data_bundles\image_manifest.json"
)

$ErrorActionPreference = 'Stop'

function Write-Info($message) {
  Write-Host "[bundle-images] $message"
}

if (-not (Test-Path $BundlePath)) {
  throw "Bundle file not found: $BundlePath"
}

$cdnPrefix = "https://images.quillsstorybook.com/cdn-cgi/image/"
$normalizedParams = "width=512,format=jpg,quality=40"

Write-Info "Parsing bundle: $BundlePath"
$content = Get-Content -Raw -Path $BundlePath
# Only pull image URLs from specific fields: image_url, setup_image_url, punchline_image_url
$pattern = '"(?:image_url|setup_image_url|punchline_image_url)"\s*:\s*\{"stringValue"\s*:\s*"(https://images\.quillsstorybook\.com/cdn-cgi/image/[^\"]+)"'
$regex = [regex]$pattern
$matches = $regex.Matches($content) | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique

if ($matches.Count -eq 0) {
  throw "No matching image URLs found in bundle."
}

if (-not (Test-Path $OutputDir)) {
  Write-Info "Creating output directory: $OutputDir"
  New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
}

$tails = New-Object System.Collections.Generic.HashSet[string]

foreach ($url in $matches) {
  if (-not $url.StartsWith($cdnPrefix)) {
    throw "Invalid image URL (wrong prefix): $url"
  }

  $remainder = $url.Substring($cdnPrefix.Length)
  $firstSlash = $remainder.IndexOf("/")
  if ($firstSlash -lt 0 -or $firstSlash -ge ($remainder.Length - 1)) {
    throw "Malformed CDN URL (missing tail path): $url"
  }

  $tail = $remainder.Substring($firstSlash + 1)
  if ($tails.Contains($tail)) {
    continue
  }

  $tails.Add($tail) | Out-Null
  $downloadUrl = "$cdnPrefix$normalizedParams/$tail"
  $destination = Join-Path $OutputDir $tail
  $destinationDir = Split-Path -Parent $destination
  if (-not (Test-Path $destinationDir)) {
    New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
  }

  if (Test-Path $destination) {
    Write-Info "Skipping existing file: $destination"
  } else {
    Write-Info "Downloading $downloadUrl -> $destination"
    $response = Invoke-WebRequest -Uri $downloadUrl -OutFile $destination -ErrorAction Stop
    if ($response.StatusCode -ne 200 -and $response.StatusCode -ne $null) {
      throw "Download failed for $downloadUrl with status $($response.StatusCode)"
    }
  }
}

$sortedTails = $tails | Sort-Object
Write-Info "Writing manifest: $ManifestPath"
$json = $sortedTails | ConvertTo-Json -Depth 2
Set-Content -Path $ManifestPath -Value $json -Encoding UTF8

Write-Info "Done. Downloaded $($tails.Count) assets."
