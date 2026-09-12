#requires -Version 5.1
<#
  Launch a memeTrader entry script with a sanitized proxy environment.

  Why this exists (2026-09-12, new machine):
  This host defines HTTP_PROXY/HTTPS_PROXY and a NO_PROXY list that contains the
  bare/bracketed IPv6 loopback forms `::1` and `[::1]`. httpx 0.28 builds an
  environment proxy mount for every NO_PROXY entry and parses them as URLs, so
  `all://[::1]` raises `httpx.InvalidURL: Invalid port: ':1]'` inside
  `httpx.AsyncClient(...)`. memeTrader creates its HttpClient with trust_env
  defaulted to True (it only sets trust_env=False on the feed client), so the
  runtime crashed during Runtime.__init__ on every start.

  memeTrader's design is explicit here: feed traffic goes through the configured
  `sources.rss_proxy_url` (socks5://127.0.0.1:7890), and every other client is
  meant to talk to the public endpoint directly. So the correct environment for
  the runtime is: no HTTP(S)_PROXY, and a NO_PROXY list httpx can parse.

  Usage: powershell -ExecutionPolicy Bypass -File scripts\run_with_clean_env.ps1 run_paper.ps1
#>
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$EntryScript,

  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$EntryArgs
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$entry = Join-Path $PSScriptRoot $EntryScript
if (-not (Test-Path -LiteralPath $entry)) {
  throw "Entry script not found: $entry"
}

# Two facts about this host drive the environment set below.
#
# 1. NO_PROXY here contains the bare/bracketed IPv6 loopback forms `::1` and
#    `[::1]`. httpx 0.28 parses every NO_PROXY entry as a URL while building its
#    environment mounts, so `all://[::1]` raises
#        httpx.InvalidURL: Invalid port: ':1]'
#    inside httpx.AsyncClient(...) and the runtime dies in Runtime.__init__.
#    Every NO_PROXY value set here is therefore parseable.
# 2. The network is only partially open: direct DNS for api.dexscreener.com and
#    news.google.com is intercepted, so DexScreener's REST *and* websocket
#    surfaces are reachable only through the local mixed-port proxy. websockets
#    reads HTTP_PROXY/HTTPS_PROXY itself, so the proxy must stay in the
#    environment for those collectors to work at all.
#
# httpx clients inside memeTrader do not depend on these variables: they pass an
# explicit proxy from config (`sources.http_proxy_url`, defaulting to
# `sources.rss_proxy_url`) and set trust_env=False. The variables exist for the
# websocket collectors and for any child tooling that honours them.
foreach ($name in @("ALL_PROXY", "all_proxy")) {
  Remove-Item -Path ("Env:" + $name) -ErrorAction SilentlyContinue
}

$proxyUrl = "http://127.0.0.1:7890"
$env:HTTP_PROXY = $proxyUrl
$env:HTTPS_PROXY = $proxyUrl
$env:http_proxy = $proxyUrl
$env:https_proxy = $proxyUrl
# Loopback exemptions stay available for local tooling, but never the bare or
# bracketed IPv6 forms.
$env:NO_PROXY = "localhost,127.0.0.1"
$env:no_proxy = $env:NO_PROXY

Set-Location $root
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $entry @EntryArgs
exit $LASTEXITCODE
