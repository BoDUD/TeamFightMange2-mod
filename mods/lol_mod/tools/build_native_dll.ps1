[CmdletBinding()]
param(
    [string]$SdkDir = "",
    [string]$OutDll = ""
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

$baseVersion = (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $sdk "base_version.txt")).Trim()
if ($baseVersion -ne "0.5.1") {
    throw "Teamfight Manager 2 SDK 0.5.1 / Mod API 0.8 is required; found base version $baseVersion at $sdk"
}

$toolchainFile = Join-Path $sdk "rust-toolchain.toml"
$pinned = Select-String -LiteralPath $toolchainFile -Pattern '^\s*channel\s*=\s*"([^"]+)"' | ForEach-Object {
    $_.Matches[0].Groups[1].Value
} | Select-Object -First 1
if ($pinned -ne "nightly-2026-05-24") {
    throw "Official 0.5.1 toolchain nightly-2026-05-24 is required; found $pinned"
}

$modApi = Get-ChildItem -LiteralPath $depsDir -Filter "libmod_api-*.rlib"
$gameView = Get-ChildItem -LiteralPath $depsDir -Filter "libgame_view-*.rlib"
$engineCore = Get-ChildItem -LiteralPath $depsDir -Filter "libengine_core-*.rlib"
if (
    $modApi.Count -ne 1 -or
    $gameView.Count -ne 1 -or
    $engineCore.Count -ne 1
) {
    throw "The SDK must contain exactly one mod_api, game_view, and engine_core rlib"
}

$expectedModApiHash = "9EBB4FBC406C7348886F5F9DE251ACF37907C510E25CD8839E5EE38A78B5ADAC"
$expectedGameViewHash = "BF1B953B00C65197A200A02BA7087BE81F970CB3893DE4967E4C146B6D07335C"
$expectedEngineCoreHash = "5275DE1221836C5C25C309CE9438F2E08DF3AFEA61541B85B2C2A8822A8107ED"
$actualModApiHash = Get-Sha256Hex -Path $modApi.FullName
$actualGameViewHash = Get-Sha256Hex -Path $gameView.FullName
$actualEngineCoreHash = Get-Sha256Hex -Path $engineCore.FullName
if (
    $actualModApiHash -ne $expectedModApiHash -or
    $actualGameViewHash -ne $expectedGameViewHash -or
    $actualEngineCoreHash -ne $expectedEngineCoreHash
) {
    throw "SDK fingerprint does not match the official Teamfight Manager 2 0.5.1 package"
}

$manifest = Join-Path $modRoot "Cargo.toml"
$targetDir = Join-Path $modRoot "target"
$oldToolchain = $env:RUSTUP_TOOLCHAIN
$oldFlags = $env:CARGO_ENCODED_RUSTFLAGS
try {
    $env:RUSTUP_TOOLCHAIN = $pinned
    $flags = @(
        "-L", "dependency=$depsDir",
        "--extern", "mod_api=$($modApi.FullName)",
        "--extern", "game_view=$($gameView.FullName)",
        "--extern", "engine_core=$($engineCore.FullName)",
        "-L", "native=$nativeDir"
    )
    $env:CARGO_ENCODED_RUSTFLAGS = $flags -join [char]31
    cargo rustc --release --manifest-path $manifest --target-dir $targetDir --lib -- --crate-type cdylib
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $builtDll = Join-Path $targetDir "release\lol_mod.dll"
    if (-not $OutDll) {
        $outDll = Join-Path $modRoot "lol_mod.dll"
    } else {
        $outDll = [System.IO.Path]::GetFullPath($OutDll)
        $outParent = Split-Path -Parent $outDll
        New-Item -ItemType Directory -Force -Path $outParent | Out-Null
    }
    Copy-Item -LiteralPath $builtDll -Destination $outDll -Force

    $env:LOL_MOD_DLL_TO_VERIFY = $outDll
    $exported = @'
import ctypes
import os

library = ctypes.WinDLL(os.environ["LOL_MOD_DLL_TO_VERIFY"])
api_version = library.tfm2_mod_api_version
api_version.restype = ctypes.c_uint32
print(api_version())
'@ | python -
    if ($LASTEXITCODE -ne 0 -or $exported.Trim() -ne "8") {
        throw "Built DLL did not export Teamfight Manager 2 Mod API 0.8 (raw 8)"
    }
    Write-Host "Build successful: $outDll (Mod API 0.8)"
} finally {
    $env:RUSTUP_TOOLCHAIN = $oldToolchain
    $env:CARGO_ENCODED_RUSTFLAGS = $oldFlags
    Remove-Item Env:LOL_MOD_DLL_TO_VERIFY -ErrorAction SilentlyContinue
}
