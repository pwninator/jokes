$ErrorActionPreference = "Stop"

# Configuration
$bucket = "gs://firestore_jokes_backup"
$localDir = "firestore_backup"
$archiveDir = Join-Path $localDir "archive"

Write-Host "----------------------------------------------------------------"
Write-Host "          Snickerdoodle Firestore Backup Automation             "
Write-Host "----------------------------------------------------------------"

# -----------------------------------------------------------------------------
# 1. Archive Current Backup
# -----------------------------------------------------------------------------
Write-Host "`n[Step 1/6] Checking for existing local backup to archive..."

if (-not (Test-Path $localDir)) {
    New-Item -ItemType Directory -Path $localDir | Out-Null
}

# Find the metadata file which contains the date (e.g., 2025_11_23.overall_export_metadata)
$metadataFiles = Get-ChildItem -Path $localDir -Filter "*.overall_export_metadata" -File

if ($metadataFiles.Count -gt 0) {
    $currentMetadata = $metadataFiles[0]
    $dateName = $currentMetadata.BaseName # e.g. 2025_11_23
    Write-Host "Found current backup metadata: $($currentMetadata.Name)"
    Write-Host "Target archive date: $dateName"

    $tempArchiveDir = Join-Path $localDir $dateName

    # Ensure the temp directory exists (it should be there as an empty dir from last run, but ensure it)
    if (-not (Test-Path $tempArchiveDir)) {
        Write-Host "Creating temporary directory for archiving: $tempArchiveDir"
        New-Item -ItemType Directory -Path $tempArchiveDir | Out-Null
    }

    # Move files into the temp directory
    $namespacesDir = Join-Path $localDir "all_namespaces"
    if (Test-Path $namespacesDir) {
        Write-Host "Moving 'all_namespaces' to $tempArchiveDir"
        Move-Item -Path $namespacesDir -Destination $tempArchiveDir -Force
    }
    
    Write-Host "Moving metadata file to $tempArchiveDir"
    Move-Item -Path $currentMetadata.FullName -Destination $tempArchiveDir -Force

    # Ensure archive root exists
    if (-not (Test-Path $archiveDir)) {
        New-Item -ItemType Directory -Path $archiveDir | Out-Null
    }

    # Move to archive, handling collisions
    $finalDest = Join-Path $archiveDir $dateName
    if (Test-Path $finalDest) {
        $timestamp = Get-Date -Format "HHmmss"
        $newDateName = "${dateName}_${timestamp}"
        Write-Warning "Archive $dateName already exists. Renaming current backup to $newDateName"
        Rename-Item -Path $tempArchiveDir -NewName $newDateName
        $tempArchiveDir = Join-Path $localDir $newDateName
        $finalDest = Join-Path $archiveDir $newDateName
    }

    Write-Host "Moving backup folder to archive: $finalDest"
    Move-Item -Path $tempArchiveDir -Destination $archiveDir -Force
} else {
    Write-Host "No existing backup metadata found in $localDir. Skipping archive step."
}


# -----------------------------------------------------------------------------
# 2. Run Firestore Export
# -----------------------------------------------------------------------------
Write-Host "`n[Step 2/6] Triggering Cloud Firestore Export..."
# Use cmd /c to run gcloud to ensure it's picked up from PATH correctly
cmd /c "gcloud firestore export $bucket"
if ($LASTEXITCODE -ne 0) { 
    Write-Error "gcloud firestore export failed. Please check your permissions and network."
    exit 1 
}


# -----------------------------------------------------------------------------
# 3. Find Latest Export on Cloud
# -----------------------------------------------------------------------------
Write-Host "`n[Step 3/6] Finding the new export directory on Cloud Storage..."
$dirs = cmd /c "gsutil ls $bucket"
# Parse output to find the latest timestamped directory
# Cloud Firestore exports are named with ISO-like timestamps
$latestCloudDir = $dirs | Where-Object { $_ -match "T\d{2}:\d{2}:\d{2}" } | Sort-Object | Select-Object -Last 1

if (-not $latestCloudDir) {
    Write-Error "Could not find a recent timestamped export in $bucket. Found:`n$($dirs -join "`n")"
    exit 1
}
Write-Host "Found latest export: $latestCloudDir"


# -----------------------------------------------------------------------------
# 4. Rename Directory and File on Cloud
# -----------------------------------------------------------------------------
Write-Host "`n[Step 4/6] Renaming Cloud Storage files to Windows-safe format..."
$today = Get-Date -Format "yyyy_MM_dd"
$newCloudDir = "$bucket/$today"

# Check if today's backup dir already exists on cloud (e.g. multiple runs same day)
cmd /c "gsutil ls -d $newCloudDir 2>NUL" | Out-Null
if ($LASTEXITCODE -eq 0) {
    $timestamp = Get-Date -Format "HHmmss"
    $today = "${today}_${timestamp}"
    $newCloudDir = "$bucket/$today"
    Write-Warning "Directory for $today already exists. Using $newCloudDir"
}

Write-Host "Renaming directory:"
Write-Host "  From: $latestCloudDir"
Write-Host "  To:   $newCloudDir"
cmd /c "gsutil -m mv $latestCloudDir $newCloudDir"
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to rename directory."; exit 1 }

# Find the metadata file inside the new dir
$files = cmd /c "gsutil ls $newCloudDir"
$metadataCloudFile = $files | Where-Object { $_ -like "*.overall_export_metadata" }

if ($metadataCloudFile) {
    # Construct new metadata name: YYYY_MM_DD.overall_export_metadata
    $newMetadataName = "$newCloudDir/$today.overall_export_metadata"
    Write-Host "Renaming metadata file:"
    Write-Host "  From: $metadataCloudFile"
    Write-Host "  To:   $newMetadataName"
    cmd /c "gsutil -m mv $metadataCloudFile $newMetadataName"
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to rename metadata file."; exit 1 }
} else {
    Write-Warning "Could not find .overall_export_metadata file in $newCloudDir. Proceeding anyway."
}


# -----------------------------------------------------------------------------
# 5. Download Backup
# -----------------------------------------------------------------------------
Write-Host "`n[Step 5/6] Downloading backup to local disk..."
cmd /c "gsutil -m cp -r $newCloudDir $localDir"
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to download backup."; exit 1 }


# -----------------------------------------------------------------------------
# 6. Install Backup (Promote to root)
# -----------------------------------------------------------------------------
Write-Host "`n[Step 6/6] Installing new backup..."
$downloadedDir = Join-Path $localDir $today

if (Test-Path $downloadedDir) {
    $newNamespaces = Join-Path $downloadedDir "all_namespaces"
    $newMetadata = Join-Path $downloadedDir "$today.overall_export_metadata"

    if (Test-Path $newNamespaces) {
        Write-Host "Moving 'all_namespaces' to $localDir"
        Move-Item -Path $newNamespaces -Destination $localDir -Force
    } else {
        Write-Error "'all_namespaces' not found in downloaded backup."
    }

    if (Test-Path $newMetadata) {
        Write-Host "Moving metadata file to $localDir"
        Move-Item -Path $newMetadata -Destination $localDir -Force
    } else {
        Write-Error "Metadata file not found in downloaded backup."
    }

    Write-Host "Leaving empty directory: $downloadedDir"
} else {
    Write-Error "Downloaded directory $downloadedDir not found."
    exit 1
}

Write-Host "`n----------------------------------------------------------------"
Write-Host "Backup completed successfully!"
Write-Host "New active backup: $today"
Write-Host "Previous backup archived in: firestore_backup/archive/"
Write-Host "----------------------------------------------------------------"

