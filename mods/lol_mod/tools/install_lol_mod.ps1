param(
    [string]$GameRoot = ""
)

$ErrorActionPreference = "Stop"

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$LiteralPath)

    $stream = [System.IO.File]::OpenRead($LiteralPath)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $sha256.ComputeHash($stream)
        return ([System.BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha256.Dispose()
        $stream.Dispose()
    }
}

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

$manifestPath = Join-Path $sourceMod "runtime_manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Missing source runtime manifest: $manifestPath"
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
    $hash = Get-Sha256Hex -LiteralPath $source
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
    [DllImport(@"$escapedDll", EntryPoint = "tfm2_mod_required_abi_level", CallingConvention = CallingConvention.Cdecl)]
    public static extern uint GetRequiredAbiLevel();

    [DllImport(@"$escapedDll", EntryPoint = "tfm2_mod_entry_stable", CallingConvention = CallingConvention.Cdecl)]
    public static extern System.IntPtr StableEntry(System.IntPtr host);
}
"@
Add-Type -TypeDefinition $probeSource
$requiredAbiLevel = [LolModApiVersionProbe]::GetRequiredAbiLevel()
$nullHostResult = [LolModApiVersionProbe]::StableEntry([System.IntPtr]::Zero)
if ($requiredAbiLevel -ne 1 -or $nullHostResult -ne [System.IntPtr]::Zero) {
    throw "Source lol_mod.dll must export the baseline Teamfight Manager 2 stable ABI entry points"
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

# Copy each manifest-owned file from the exact stable-ABI runtime closure.
# Development QA, source art and retired classic-render assets must never
# leak into the active game mod.
foreach ($row in $manifest.files) {
    $relative = $row.path -replace '/', [System.IO.Path]::DirectorySeparatorChar
    $source = Join-Path $sourceMod $relative
    $installed = Join-Path $targetMod $relative
    $installedParent = Split-Path -Parent $installed
    New-Item -ItemType Directory -Force -Path $installedParent | Out-Null
    Copy-Item -LiteralPath $source -Destination $installed -Force
}

foreach ($row in $manifest.files) {
    $installed = Join-Path $targetMod ($row.path -replace '/', [System.IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath $installed -PathType Leaf)) {
        throw "Installed runtime file missing: $installed"
    }
    $hash = Get-Sha256Hex -LiteralPath $installed
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
