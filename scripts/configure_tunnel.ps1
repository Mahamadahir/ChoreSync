# Configure temporary tunnel hosts for backend and frontend.
# Usage: ./configure_tunnel.ps1 -BackendTunnelUrl "https://backend-tunnel.example.com" [-FrontendTunnelUrl "https://frontend-tunnel.example.com"]

param(
    [Parameter(Mandatory = $true)]
    [string]$BackendTunnelUrl,
    [string]$FrontendTunnelUrl
)

function Normalize-Url {
    param([string]$Url)
    if ($Url.EndsWith("/")) { return $Url.TrimEnd("/") }
    return $Url
}

function Set-EnvFileValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Value
    )
    if (-not (Test-Path $Path)) {
        throw "File not found: $Path"
    }
    $lines = Get-Content $Path
    $found = $false
    for ($i = 0; $i -lt $lines.Length; $i++) {
        $line = $lines[$i]
        if ($line -match "^\s*$Key\s*=") {
            $lines[$i] = "$Key=$Value"
            $found = $true
            break
        }
    }
    if (-not $found) {
        $lines += "$Key=$Value"
    }
    Set-Content -Path $Path -Value $lines
}

$backendUrl = Normalize-Url $BackendTunnelUrl
$frontendUrl = if ($FrontendTunnelUrl) { Normalize-Url $FrontendTunnelUrl } else { $backendUrl }
$backendHost = ([System.Uri]$backendUrl).Host
$frontendHost = ([System.Uri]$frontendUrl).Host

# Backend secrets.env updates
$secretsPath = Join-Path -Path "backend" -ChildPath "secrets.env"
if (-not (Test-Path $secretsPath)) {
    throw "secrets.env not found at $secretsPath"
}
$secretsLines = Get-Content $secretsPath
$updatedSecrets = @()
$updatedAllowedHosts = $false
foreach ($line in $secretsLines) {
    if ($line -match "^\s*ALLOWED_HOSTS\s*=") {
        $parts = $line.Split("=")
        $values = $parts[1].Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
        foreach ($h in @($backendHost, $frontendHost)) {
            if ($values -notcontains $h) { $values += $h }
        }
        $updatedSecrets += "ALLOWED_HOSTS=" + ($values -join ",")
        $updatedAllowedHosts = $true
    } else {
        $updatedSecrets += $line
    }
}
if (-not $updatedAllowedHosts) {
    $updatedSecrets += "ALLOWED_HOSTS=127.0.0.1,localhost,$backendHost,$frontendHost"
}
Set-Content -Path $secretsPath -Value $updatedSecrets

Set-EnvFileValue -Path $secretsPath -Key "GOOGLE_WEBHOOK_CALLBACK_URL" -Value "$backendUrl/api/calendar/google/webhook/"
Set-EnvFileValue -Path $secretsPath -Key "GOOGLE_OAUTH_REDIRECT_URI" -Value "$backendUrl/api/calendar/google/callback/"
Set-EnvFileValue -Path $secretsPath -Key "FRONTEND_APP_URL" -Value $frontendUrl
Set-EnvFileValue -Path $secretsPath -Key "CSRF_TRUSTED_ORIGINS" -Value "http://localhost:5173,http://127.0.0.1:5173,$frontendUrl"
Set-EnvFileValue -Path $secretsPath -Key "CORS_ALLOWED_ORIGINS" -Value "http://localhost:5173,http://127.0.0.1:5173,$frontendUrl"

# Frontend .env update for API base URL
$frontendEnvPath = Join-Path -Path "frontend" -ChildPath ".env"
if (Test-Path $frontendEnvPath) {
    Set-EnvFileValue -Path $frontendEnvPath -Key "VITE_API_BASE_URL" -Value $backendUrl
    Set-EnvFileValue -Path $frontendEnvPath -Key "VITE_ALLOWED_HOSTS" -Value "localhost,127.0.0.1,$frontendHost,$backendHost"
}

Write-Host "Updated tunnel configuration for backend host $backendHost and frontend host $frontendHost."
Write-Host "Restart Django/Vite to pick up changes. Re-run Google connect/selection to recreate watch channels."
