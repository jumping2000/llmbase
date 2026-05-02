param(
    [string]$Username = "admin",
    [Parameter(Mandatory = $true)]
    [string]$Password,
    [string]$OutputPath = (Join-Path $PSScriptRoot ".htpasswd")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker is required to generate the htpasswd file."
}

$outputDir = Split-Path -Parent $OutputPath
if ($outputDir -and -not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$htpasswdLine = docker run --rm --entrypoint htpasswd httpd:2.4-alpine -nbB $Username $Password
if (-not $htpasswdLine) {
    throw "htpasswd generation failed."
}

Set-Content -Path $OutputPath -Value $htpasswdLine -NoNewline
Write-Host "Wrote htpasswd file to $OutputPath"