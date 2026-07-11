[CmdletBinding()]
param(
    [string]$SdkDir = ""
)

$ErrorActionPreference = "Stop"

$modRoot = Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not $SdkDir) {
    $gameRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $modRoot))
    $SdkDir = Join-Path $gameRoot "mod-sdk"
}
$sdk = Resolve-Path -LiteralPath $SdkDir
$depsDir = Join-Path $sdk "deps"
$nativeDir = Join-Path $sdk "native"

$baseVersion = (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $sdk "base_version.txt")).Trim()
if ($baseVersion -ne "0.5.0") {
    throw "Teamfight Manager 2 SDK 0.5.0 / Mod API 0.8 is required; found base version $baseVersion at $sdk"
}

$toolchainFile = Join-Path $sdk "rust-toolchain.toml"
$pinned = Select-String -LiteralPath $toolchainFile -Pattern '^\s*channel\s*=\s*"([^"]+)"' | ForEach-Object {
    $_.Matches[0].Groups[1].Value
} | Select-Object -First 1
if ($pinned -ne "nightly-2026-05-24") {
    throw "Official 0.5.0_hotfix2 toolchain nightly-2026-05-24 is required; found $pinned"
}

$modApi = Get-ChildItem -LiteralPath $depsDir -Filter "libmod_api-*.rlib"
$gameView = Get-ChildItem -LiteralPath $depsDir -Filter "libgame_view-*.rlib"
if ($modApi.Count -ne 1 -or $gameView.Count -ne 1) {
    throw "The SDK must contain exactly one mod_api rlib and one game_view rlib"
}

$expectedModApiHash = "C99E9CC2B78D26093234B4749609332F512DAFDB4E34A82BF548EFDA6AA5E384"
$expectedGameViewHash = "6D8FCCB508697C4244038E97B0C66DA1F7DC2D699950FE06FF6415A795FBC719"
$actualModApiHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $modApi.FullName).Hash
$actualGameViewHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $gameView.FullName).Hash
if ($actualModApiHash -ne $expectedModApiHash -or $actualGameViewHash -ne $expectedGameViewHash) {
    throw "SDK fingerprint does not match the official Teamfight Manager 2 0.5.0_hotfix2 package"
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
        "-L", "native=$nativeDir"
    )
    $env:CARGO_ENCODED_RUSTFLAGS = $flags -join [char]31
    cargo rustc --release --manifest-path $manifest --target-dir $targetDir --lib -- --crate-type cdylib
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $builtDll = Join-Path $targetDir "release\lol_mod.dll"
    $outDll = Join-Path $modRoot "lol_mod.dll"
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
