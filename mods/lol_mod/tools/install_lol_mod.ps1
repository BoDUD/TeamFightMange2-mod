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
    "setting",
    "style",
    "text",
    "sound"
)

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

$manifestPath = Join-Path $sourceMod "build_manifest.json"
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
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
$config | ConvertTo-Json -Depth 20 -Compress | Set-Content -LiteralPath $configPath -Encoding UTF8

Write-Output "Installed lol_mod to $targetMod"
Write-Output "Enabled mods: lol_mod"
