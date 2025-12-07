# Starts HTTP file server (port 8000) and autosave sync server (port 3323).
# Use from anywhere: powershell -ExecutionPolicy Bypass -File scripts/start_autosave.ps1

$repoRoot = Resolve-Path "$PSScriptRoot\.."
Write-Host "Repo root:" $repoRoot
Set-Location $repoRoot
Write-Host "Current working dir:" (Get-Location)

Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m http.server 8001" -WorkingDirectory $repoRoot
Start-Process -NoNewWindow -FilePath "node" -ArgumentList "scripts/progress_sync_server.js" -WorkingDirectory $repoRoot

Write-Host "Tracker: http://localhost:8001/ProgressTracker.html"
