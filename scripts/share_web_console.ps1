param(
  [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot "run_web.ps1"
$stateDir = Join-Path $root "data\web_console"
$logDir = Join-Path $root "data\logs"
$tokenPath = Join-Path $stateDir "public_access_token.txt"
$accessPath = Join-Path $stateDir "PUBLIC_ACCESS.txt"
$tunnelLog = Join-Path $logDir "web-public-tunnel.log"
$port = 8788
$localUrl = "http://127.0.0.1:$port"

New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path -LiteralPath $tokenPath)) {
  $bytes = New-Object byte[] 24
  $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $generator.GetBytes($bytes)
  } finally {
    $generator.Dispose()
  }
  $token = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
  [System.IO.File]::WriteAllText($tokenPath, $token, [System.Text.UTF8Encoding]::new($false))
} else {
  $token = [System.IO.File]::ReadAllText($tokenPath).Trim()
}

$basic = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("memetrader:$token"))
$headers = @{ Authorization = "Basic $basic" }

function Test-ProtectedConsole {
  try {
    $result = Invoke-RestMethod -Uri "$localUrl/api/health" -Headers $headers -TimeoutSec 2
    return [bool]$result.ok
  } catch {
    return $false
  }
}

if (-not (Test-ProtectedConsole)) {
  Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -Port $port -AccessTokenFile `"$tokenPath`"" `
    -WorkingDirectory $root `
    -WindowStyle Hidden

  $ready = $false
  for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    if (Test-ProtectedConsole) {
      $ready = $true
      break
    }
  }
  if (-not $ready) {
    throw "Protected memeTrader Web Console did not become ready at $localUrl"
  }
}

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
  throw "cloudflared is required for the protected public URL. The local console remains available at http://127.0.0.1:8787/."
}

$existingTunnel = Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match "127\.0\.0\.1:$port" } |
  Select-Object -First 1

if (-not $existingTunnel) {
  Start-Process `
    -FilePath $cloudflared.Source `
    -ArgumentList @(
      "tunnel", "--no-autoupdate",
      "--url", $localUrl,
      "--loglevel", "info",
      "--logfile", $tunnelLog
    ) `
    -WorkingDirectory $root `
    -WindowStyle Hidden
}

$publicUrl = ""
for ($attempt = 0; $attempt -lt 30; $attempt++) {
  Start-Sleep -Milliseconds 500
  if (Test-Path -LiteralPath $tunnelLog) {
    $matches = Select-String -LiteralPath $tunnelLog -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -AllMatches
    if ($matches) {
      $publicUrl = $matches[-1].Matches[-1].Value
      break
    }
  }
}
if (-not $publicUrl) {
  throw "The public tunnel started, but its HTTPS URL was not found in $tunnelLog"
}

$summary = @"
memeTrader Protected Public Console

URL: $publicUrl
Username: memetrader
Password: $token

This is a temporary Cloudflare Quick Tunnel URL. It changes when the tunnel is recreated.
The origin remains bound to 127.0.0.1 and Live trading remains unavailable.
"@
[System.IO.File]::WriteAllText($accessPath, $summary, [System.Text.UTF8Encoding]::new($false))

Write-Output "Protected public URL: $publicUrl"
Write-Output "Login details were saved locally to: $accessPath"
if (-not $NoOpen) {
  Start-Process -FilePath "notepad.exe" -ArgumentList "`"$accessPath`""
  Start-Process $publicUrl
}
