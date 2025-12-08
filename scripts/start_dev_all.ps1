# Start backend, frontend, and quick Cloudflare tunnels. If you paste the tunnel URLs after they appear,
# the script will also run configure_tunnel.ps1 to wire env/callbacks for remote testing.
# Usage: ./scripts/start_dev_all.ps1 [-BackendPort 8000] [-FrontendPort 5173]

param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$backendPath = Join-Path $repoRoot "backend"
$frontendPath = Join-Path $repoRoot "frontend"
$venvPython = Join-Path (Join-Path (Join-Path $repoRoot ".venv") "Scripts") "python.exe"
$configureScript = Join-Path $scriptDir "configure_tunnel.ps1"

if (Test-Path $venvPython) { $pythonCmd = $venvPython } else { $pythonCmd = "python" }

if (-not (Test-Path $backendPath)) { throw "Backend path not found: $backendPath" }
if (-not (Test-Path $frontendPath)) { throw "Frontend path not found: $frontendPath" }
if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Warning "cloudflared not found on PATH. Install it before running tunnels."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Warning "npm not found on PATH. Frontend may fail to start."
}

function Start-Window($title, $workingDir, $command) {
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "Write-Host '$title'; Set-Location `"$workingDir`"; $command"
    ) -WorkingDirectory $workingDir
}

$wt = Get-Command wt.exe -ErrorAction SilentlyContinue

if ($wt) {
    $tabs = @(
        "new-tab --title backend --startingDirectory `"$backendPath`" cmd /c `"`"cd /d `"`"$backendPath`"`" && `"`"$pythonCmd`"`" manage.py runserver 0.0.0.0:$BackendPort`"`"`"",
        "new-tab --title frontend --startingDirectory `"$frontendPath`" cmd /c `"`"cd /d `"`"$frontendPath`"`" && npm run dev -- --host 0.0.0.0 --port $FrontendPort`"`"`"",
        "new-tab --title tunnel-be --startingDirectory `"$repoRoot`" cmd /c `"`"cd /d `"`"$repoRoot`"`" && cloudflared tunnel --url http://localhost:$BackendPort`"`"`"",
        "new-tab --title tunnel-fe --startingDirectory `"$repoRoot`" cmd /c `"`"cd /d `"`"$repoRoot`"`" && cloudflared tunnel --url http://localhost:$FrontendPort`"`"`""
    ) -join " ; "

    Start-Process wt.exe -ArgumentList $tabs
    Write-Host "Started backend, frontend, and two cloudflared tunnels in Windows Terminal tabs."
} else {
    Start-Window "backend" $backendPath "`"$pythonCmd`" manage.py runserver 0.0.0.0:$BackendPort"
    Start-Window "frontend" $frontendPath "npm run dev -- --host 0.0.0.0 --port $FrontendPort"
    Start-Window "tunnel-be" $repoRoot "cloudflared tunnel --url http://localhost:$BackendPort"
    Start-Window "tunnel-fe" $repoRoot "cloudflared tunnel --url http://localhost:$FrontendPort"
    Write-Host "wt.exe not found; started processes in separate PowerShell windows."
}

Write-Host ""
Write-Host "When the tunnels print their public URLs, paste them here to auto-configure env (Enter to skip)."
$backendTunnelUrl = Read-Host "Backend tunnel URL (e.g., https://....trycloudflare.com)"
$frontendTunnelUrl = Read-Host "Frontend tunnel URL (optional)"

if ($backendTunnelUrl -and (Test-Path $configureScript)) {
    Write-Host "Running configure_tunnel.ps1..."
    & $configureScript -BackendTunnelUrl $backendTunnelUrl -FrontendTunnelUrl $frontendTunnelUrl
} elseif ($backendTunnelUrl -and -not (Test-Path $configureScript)) {
    Write-Warning "configure_tunnel.ps1 not found; cannot auto-configure env."
} else {
    Write-Host "Skipped env configuration. You can run configure_tunnel.ps1 manually later."
}

Write-Host ""
Write-Host "Tip: If a tab looks idle, press Enter inside it to refresh output. Keep these tabs open for live logs."
