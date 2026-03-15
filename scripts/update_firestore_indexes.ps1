$repoRoot = Split-Path -Parent $PSScriptRoot
$outputPath = Join-Path $repoRoot 'firestore.indexes.json'
$output = firebase firestore:indexes

if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

[System.IO.File]::WriteAllText(
  $outputPath,
  ($output -join [Environment]::NewLine) + [Environment]::NewLine,
  [System.Text.UTF8Encoding]::new($false)
)
