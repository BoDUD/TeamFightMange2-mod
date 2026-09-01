[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ChampionPath,
    [string]$SdkDir = ""
)

$ErrorActionPreference = "Stop"

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)

    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            return ([System.BitConverter]::ToString($sha256.ComputeHash($stream))).Replace("-", "")
        } finally {
            $sha256.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
}

$modRoot = Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not $SdkDir) {
    $gameRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $modRoot))
    $packagedSdk = Join-Path $gameRoot "mod-sdk-0.5.1-package\mod-sdk"
    $SdkDir = if (Test-Path -LiteralPath $packagedSdk -PathType Container) {
        $packagedSdk
    } else {
        Join-Path $gameRoot "mod-sdk"
    }
}
$sdk = Resolve-Path -LiteralPath $SdkDir
$depsDir = Join-Path $sdk "deps"
$nativeDir = Join-Path $sdk "native"
$source = Join-Path $PSScriptRoot "shen_data_champion_sdk_gate.rs"
$champion = Resolve-Path -LiteralPath $ChampionPath

$baseVersion = (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $sdk "base_version.txt")).Trim()
if ($baseVersion -ne "0.5.1") {
    throw "Teamfight Manager 2 SDK 0.5.1 is required; found $baseVersion"
}
$toolchain = (Select-String -LiteralPath (Join-Path $sdk "rust-toolchain.toml") -Pattern '^\s*channel\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
if ($toolchain -ne "nightly-2026-05-24") {
    throw "Official SDK toolchain nightly-2026-05-24 is required; found $toolchain"
}

$gameCore = Get-ChildItem -LiteralPath $depsDir -Filter "libgame_core-*.rlib"
if ($gameCore.Count -ne 1) {
    throw "The official SDK must contain exactly one game_core rlib"
}
$expectedGameCoreHash = "A024FB595B909D2BF05D42ABD940A31825BF41B155262D22FD5A9E494CE2D13E"
if ((Get-Sha256Hex -Path $gameCore.FullName) -ne $expectedGameCoreHash) {
    throw "game_core fingerprint does not match the official 0.5.1 SDK"
}

# This is the serde_json build used by game_core's DataChampionInfo derive.
$serdeJson = Join-Path $depsDir "libserde_json-aa3421a9f0eb33d2.rlib"
if (-not (Test-Path -LiteralPath $serdeJson)) {
    throw "The official SDK serde_json dependency is missing"
}
$expectedSerdeJsonHash = "816FE7E9198F083D37939E0FC60331E62284FB2DCFA4579473A44D53D51B8839"
if ((Get-Sha256Hex -Path $serdeJson) -ne $expectedSerdeJsonHash) {
    throw "serde_json fingerprint does not match the official 0.5.1 SDK"
}

$tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$tempRoot = [System.IO.Path]::GetFullPath((Join-Path $tempBase ("lol_mod_shen_sdk_gate_" + [System.Guid]::NewGuid().ToString("N"))))
if (-not $tempRoot.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to create SDK gate outside the system temp directory: $tempRoot"
}
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
try {
    $output = Join-Path $tempRoot "shen_data_champion_sdk_gate.exe"
    & rustup run $toolchain rustc $source `
        --edition 2021 `
        -L "dependency=$depsDir" `
        -L "native=$nativeDir" `
        --extern "game_core=$($gameCore.FullName)" `
        --extern "serde_json=$serdeJson" `
        -o $output
    if ($LASTEXITCODE -ne 0) {
        throw "SDK DataChampionInfo gate compilation failed with exit code $LASTEXITCODE"
    }
    & $output $champion
    if ($LASTEXITCODE -ne 0) {
        throw "SDK DataChampionInfo gate rejected the generated champion with exit code $LASTEXITCODE"
    }
} finally {
    if ((Test-Path -LiteralPath $tempRoot) -and $tempRoot.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
