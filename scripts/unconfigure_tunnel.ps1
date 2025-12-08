# Remove tunnel hosts from backend/frontend configs and reset URLs to localhost defaults.
# Usage: ./unconfigure_tunnel.ps1 -BackendTunnelUrl "https://backend-tunnel.example.com" [-FrontendTunnelUrl "https://frontend-tunnel.example.com"]

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

$secretsPath = Join-Path -Path "backend" -ChildPath "secrets.env"
if (-not (Test-Path $secretsPath)) {
    throw "secrets.env not found at $secretsPath"
}

# Remove host from ALLOWED_HOSTS
$secretsLines = Get-Content $secretsPath
$newSecrets = @()
$handledAllowed = $false
foreach ($line in $secretsLines) {
    if ($line -match "^\s*ALLOWED_HOSTS\s*=") {
        $parts = $line.Split("=")
        $values = $parts[1].Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
        $values = $values | Where-Object { $_ -ne $backendHost -and $_ -ne $frontendHost }
        $newSecrets += "ALLOWED_HOSTS=" + ($values -join ",")
        $handledAllowed = $true
    } else {
        $newSecrets += $line
    }
}
if (-not $handledAllowed) {
    $newSecrets += "ALLOWED_HOSTS=127.0.0.1,localhost"
}
Set-Content -Path $secretsPath -Value $newSecrets

# Reset URLs to localhost defaults
Set-EnvFileValue -Path $secretsPath -Key "GOOGLE_WEBHOOK_CALLBACK_URL" -Value "http://localhost:8000/api/calendar/google/webhook/"
Set-EnvFileValue -Path $secretsPath -Key "GOOGLE_OAUTH_REDIRECT_URI" -Value "http://localhost:8000/api/calendar/google/callback/"
Set-EnvFileValue -Path $secretsPath -Key "FRONTEND_APP_URL" -Value "http://localhost:5173"
Set-EnvFileValue -Path $secretsPath -Key "CSRF_TRUSTED_ORIGINS" -Value "http://localhost:5173,http://127.0.0.1:5173"
Set-EnvFileValue -Path $secretsPath -Key "CORS_ALLOWED_ORIGINS" -Value "http://localhost:5173,http://127.0.0.1:5173"

# Frontend .env reset
$frontendEnvPath = Join-Path -Path "frontend" -ChildPath ".env"
if (Test-Path $frontendEnvPath) {
    Set-EnvFileValue -Path $frontendEnvPath -Key "VITE_API_BASE_URL" -Value "http://localhost:8000"
    Set-EnvFileValue -Path $frontendEnvPath -Key "VITE_ALLOWED_HOSTS" -Value "localhost,127.0.0.1"
}

Write-Host "Removed tunnel hosts and reset URLs to localhost defaults. Restart Django/Vite."
