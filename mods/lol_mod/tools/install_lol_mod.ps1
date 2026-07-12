param(
    [string]$GameRoot = ""
)

$ErrorActionPreference = "Stop"

$sourceMod = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if ([string]::IsNullOrWhiteSpace($GameRoot)) {
    $GameRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
} else {
    $GameRoot = [System.IO.Path]::GetFullPath($GameRoot)
}

$modsRoot = [System.IO.Path]::GetFullPath((Join-Path $GameRoot "mods"))
$targetMod = [System.IO.Path]::GetFullPath((Join-Path $modsRoot "lol_mod"))
$expectedPrefix = $modsRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if (-not $targetMod.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to sync outside the game mods directory: $targetMod"
}
if ([System.IO.Path]::GetFileName($targetMod) -ne "lol_mod") {
    throw "Refusing to replace an unexpected target: $targetMod"
}

$runtimeEntries = @(
    "mod.mod_info",
    "mod.override_info",
    "champion",
    "icons",
    "aseprite_resources",
    "BanPickIllust",
    "ui",
    "style",
    "text",
    "sound",
    "lol_mod.dll"
)

$manifestPath = Join-Path $sourceMod "build_manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Missing source build manifest: $manifestPath"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($row in $manifest.files) {
    $source = Join-Path $sourceMod ($row.path -replace '/', [System.IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Source runtime file missing before install: $source"
    }
    if ((Get-Item -LiteralPath $source).Length -ne $row.size) {
        throw "Source runtime size mismatch before install: $($row.path)"
    }
    $hash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $row.sha256) {
        throw "Source runtime hash mismatch before install: $($row.path)"
    }
}

$sourceDll = Join-Path $sourceMod "lol_mod.dll"
$escapedDll = $sourceDll.Replace('"', '""')
$probeSource = @"
using System.Runtime.InteropServices;

public static class LolModApiVersionProbe
{
    [DllImport(@"$escapedDll", EntryPoint = "tfm2_mod_api_version", CallingConvention = CallingConvention.Cdecl)]
    public static extern uint GetVersion();
}
"@
Add-Type -TypeDefinition $probeSource
$apiVersion = [LolModApiVersionProbe]::GetVersion()
if ($apiVersion -ne 8) {
    throw "Source lol_mod.dll must export Teamfight Manager 2 Mod API 0.8; got raw version 0x$($apiVersion.ToString('x8'))"
}

New-Item -ItemType Directory -Force -Path $modsRoot | Out-Null
if (Test-Path -LiteralPath $targetMod) {
    $resolvedTarget = (Resolve-Path -LiteralPath $targetMod).Path
    if ($resolvedTarget -ne $targetMod) {
        throw "Resolved target differs from the verified target: $resolvedTarget"
    }
    Remove-Item -LiteralPath $targetMod -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $targetMod | Out-Null

foreach ($entry in $runtimeEntries) {
    $source = Join-Path $sourceMod $entry
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Missing runtime entry: $source"
    }
    Copy-Item -LiteralPath $source -Destination $targetMod -Recurse -Force
}

# A release may deliberately publish a small provenance file outside the
# standard runtime directories (for example the pinned Xayah ImageGen/audio
# audits). Copy any such manifest-owned file to its exact relative path rather
# than widening the install to the entire development-only qa directory.
foreach ($row in $manifest.files) {
    $relative = $row.path -replace '/', [System.IO.Path]::DirectorySeparatorChar
    $source = Join-Path $sourceMod $relative
    $installed = Join-Path $targetMod $relative
    if (-not (Test-Path -LiteralPath $installed -PathType Leaf)) {
        $installedParent = Split-Path -Parent $installed
        New-Item -ItemType Directory -Force -Path $installedParent | Out-Null
        Copy-Item -LiteralPath $source -Destination $installed -Force
    }
}

foreach ($row in $manifest.files) {
    $installed = Join-Path $targetMod ($row.path -replace '/', [System.IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath $installed -PathType Leaf)) {
        throw "Installed runtime file missing: $installed"
    }
    $hash = (Get-FileHash -LiteralPath $installed -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $row.sha256) {
        throw "Installed runtime hash mismatch: $($row.path)"
    }
}

$configPath = Join-Path $GameRoot "config\game\mods.json"
if (Test-Path -LiteralPath $configPath) {
    $config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
} else {
    $config = [pscustomobject]@{}
}
if ($config.PSObject.Properties.Name -contains "enabled_mods") {
    $config.enabled_mods = @("lol_mod")
} else {
    $config | Add-Member -NotePropertyName enabled_mods -NotePropertyValue @("lol_mod")
}
$configJson = $config | ConvertTo-Json -Depth 20 -Compress
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($configPath, $configJson, $utf8NoBom)

Write-Output "Installed lol_mod to $targetMod"
Write-Output "Enabled mods: lol_mod"
