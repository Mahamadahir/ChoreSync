# Launch backend, frontend, and quick Cloudflare tunnels as background jobs in the current window.
# Logs are written to ./logs/*.log; tail them with Get-Content -Wait.
# Usage: ./scripts/start_dev_with_tunnels.ps1 [-BackendPort 8000] [-FrontendPort 5173]

param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$logDir = Join-Path $repoRoot "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$backendLog = Join-Path $logDir "backend.log"
$frontendLog = Join-Path $logDir "frontend.log"
$tunnelBackendLog = Join-Path $logDir "tunnel-backend.log"
$tunnelFrontendLog = Join-Path $logDir "tunnel-frontend.log"

$jobs = @()

# Backend job
$jobs += Start-Job -Name "backend" -ScriptBlock {
    param($repoRoot, $port, $logPath)
    Set-Location (Join-Path $repoRoot "backend")
    python manage.py runserver "0.0.0.0:$port" 2>&1 | Tee-Object -FilePath $logPath -Append
} -ArgumentList $repoRoot, $BackendPort, $backendLog

# Frontend job
$jobs += Start-Job -Name "frontend" -ScriptBlock {
    param($repoRoot, $port, $logPath)
    Set-Location (Join-Path $repoRoot "frontend")
    npm run dev -- --host "0.0.0.0" --port $port 2>&1 | Tee-Object -FilePath $logPath -Append
} -ArgumentList $repoRoot, $FrontendPort, $frontendLog

# Cloudflare backend tunnel job
$jobs += Start-Job -Name "tunnel-backend" -ScriptBlock {
    param($repoRoot, $port, $logPath)
    Set-Location $repoRoot
    cloudflared tunnel --url "http://localhost:$port" 2>&1 | Tee-Object -FilePath $logPath -Append
} -ArgumentList $repoRoot, $BackendPort, $tunnelBackendLog

# Cloudflare frontend tunnel job
$jobs += Start-Job -Name "tunnel-frontend" -ScriptBlock {
    param($repoRoot, $port, $logPath)
    Set-Location $repoRoot
    cloudflared tunnel --url "http://localhost:$port" 2>&1 | Tee-Object -FilePath $logPath -Append
} -ArgumentList $repoRoot, $FrontendPort, $tunnelFrontendLog

Write-Host "Started jobs: backend, frontend, tunnel-backend, tunnel-frontend."
Write-Host "Logs:"
Write-Host "  Backend:   $backendLog"
Write-Host "  Frontend:  $frontendLog"
Write-Host "  Tunnel BE: $tunnelBackendLog"
Write-Host "  Tunnel FE: $tunnelFrontendLog"
Write-Host ""
Write-Host "Tail a log with: Get-Content -Wait $backendLog"
Write-Host "When tunnels print URLs, copy the backend tunnel URL and run:"
Write-Host "  ./scripts/configure_tunnel.ps1 -TunnelUrl \"<backend-tunnel-url>\""
Write-Host "Stop jobs with: Get-Job | Stop-Job; Get-Job | Remove-Job"
