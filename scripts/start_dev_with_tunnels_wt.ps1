# Launch backend, frontend, and quick Cloudflare tunnels in separate PowerShell windows.
# This version does not depend on Windows Terminal's new-tab command (previous approach failed when WT wasn't on PATH).
# Usage: ./scripts/start_dev_with_tunnels_wt.ps1 [-BackendPort 8000] [-FrontendPort 5173]

param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$backendPath = Join-Path $repoRoot "backend"
$frontendPath = Join-Path $repoRoot "frontend"
$venvPython = Join-Path (Join-Path (Join-Path $repoRoot ".venv") "Scripts") "python.exe"
if (Test-Path $venvPython) {
    $pythonCmd = $venvPython
} else {
    $pythonCmd = "python"
}

if (-not (Test-Path $backendPath)) { throw "Backend path not found: $backendPath" }
if (-not (Test-Path $frontendPath)) { throw "Frontend path not found: $frontendPath" }

function Start-Window($title, $workingDir, $command) {
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "Write-Host '$title'; Set-Location `"$workingDir`"; $command"
    ) -WorkingDirectory $workingDir
}

$wt = Get-Command wt.exe -ErrorAction SilentlyContinue

if ($wt) {
    # Build a single wt command string to open four tabs; uses cmd /c to avoid quoting pitfalls
    $tabs = @(
        "new-tab --title backend --startingDirectory `"$backendPath`" cmd /c `"`"cd /d `"`"$backendPath`"`" && `"`"$pythonCmd`"`" manage.py runserver 0.0.0.0:$BackendPort`"`"`"",
        "new-tab --title frontend --startingDirectory `"$frontendPath`" cmd /c `"`"cd /d `"`"$frontendPath`"`" && npm run dev -- --host 0.0.0.0 --port $FrontendPort`"`"`"",
        "new-tab --title tunnel-be --startingDirectory `"$repoRoot`" cmd /c `"`"cd /d `"`"$repoRoot`"`" && cloudflared tunnel --url http://localhost:$BackendPort`"`"`"",
        "new-tab --title tunnel-fe --startingDirectory `"$repoRoot`" cmd /c `"`"cd /d `"`"$repoRoot`"`" && cloudflared tunnel --url http://localhost:$FrontendPort`"`"`""
    ) -join " ; "

    Start-Process wt.exe -ArgumentList $tabs
    Write-Host "Started backend, frontend, and two cloudflared tunnels in separate Windows Terminal tabs (wt)."
} else {
    Start-Window "backend" $backendPath "`"$pythonCmd`" manage.py runserver 0.0.0.0:$BackendPort"
    Start-Window "frontend" $frontendPath "npm run dev -- --host 0.0.0.0 --port $FrontendPort"
    Start-Window "tunnel-be" $repoRoot "cloudflared tunnel --url http://localhost:$BackendPort"
    Start-Window "tunnel-fe" $repoRoot "cloudflared tunnel --url http://localhost:$FrontendPort"
    Write-Host "Windows Terminal (wt) not found on PATH; started processes in separate PowerShell windows instead."
}

Write-Host "Ensure python/npm/cloudflared are on PATH. When backend tunnel prints its URL, run configure_tunnel.ps1 -BackendTunnelUrl <url> (and optional -FrontendTunnelUrl)."
