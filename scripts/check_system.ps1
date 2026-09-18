param([switch]$Json, [ValidateRange(1,30)][int]$TimeoutSeconds = 8)

# Diagnostic only: no Store constructor, startup, restart or database writes.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$baseUrl = 'http://127.0.0.1:8790'
$result = [ordered]@{
  checked_at_utc = [DateTime]::UtcNow.ToString('o')
  project_root = $root
  database = $null
  database_exists = $false
  configured_mode = $null
  api_base = $baseUrl
  api_ready = $false
  runtime_status = 'unknown'
  version = $null
  paper_only = $null
  live_locked = $null
  open_positions = $null
  unique_held_tokens = $null
  api_error = $null
  scope = 'Local config and console API; API process path is not independently attested.'
  note = 'Zero open positions is not zero historical trades. An API error is not proof the trader stopped.'
}
try {
  $config = Get-Content -LiteralPath (Join-Path $root 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
  $result.configured_mode = $config.mode
  $database = [string]$config.database
  if (-not [IO.Path]::IsPathRooted($database)) { $database = Join-Path $root $database }
  $result.database = [IO.Path]::GetFullPath($database)
  $result.database_exists = Test-Path -LiteralPath $result.database -PathType Leaf
  $health = Invoke-RestMethod "$baseUrl/health" -TimeoutSec $TimeoutSeconds
  $result.runtime_status = $health.runtime_status
  $result.version = $health.version
  $live = Invoke-RestMethod "$baseUrl/api/live?summary_only=1" -TimeoutSec $TimeoutSeconds
  $result.paper_only = $live.system.paper_only
  $result.live_locked = $live.system.live_locked
  $result.open_positions = $live.system.open_position_count
  $result.unique_held_tokens = $live.system.unique_held_token_count
  $result.api_ready = [bool]($health.ok -and $health.runtime_status -eq 'running' -and
    $live.system.runtime_status -eq 'running' -and $health.version -eq $live.version -and
    $result.database_exists -and $config.mode -eq 'paper' -and -not $config.live.enabled -and
    $live.system.paper_only -and $live.system.live_locked)
} catch {
  $result.api_error = $_.Exception.Message
}
if ($Json) { $result | ConvertTo-Json -Depth 4 } else { [pscustomobject]$result | Format-List }
if ($result.api_ready) { exit 0 } else { exit 3 }
