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

function Assert-StableSdkParity {
    param(
        [Parameter(Mandatory = $true)][string]$VendoredApi,
        [Parameter(Mandatory = $true)][string]$ExternalSdk
    )

    $externalRoot = [System.IO.Path]::GetFullPath($ExternalSdk)
    $externalApi = if (Test-Path -LiteralPath (Join-Path $externalRoot "mod-api-stable") -PathType Container) {
        Join-Path $externalRoot "mod-api-stable"
    } else {
        $externalRoot
    }
    if (-not (Test-Path -LiteralPath (Join-Path $externalApi "Cargo.toml") -PathType Leaf)) {
        throw "Stable SDK does not contain mod-api-stable: $externalRoot"
    }

    $baseVersionPath = Join-Path $externalRoot "base_version.txt"
    if (Test-Path -LiteralPath $baseVersionPath -PathType Leaf) {
        $baseVersion = (Get-Content -LiteralPath $baseVersionPath -Raw -Encoding UTF8).Trim()
        if ([version]$baseVersion -lt [version]"0.5.8") {
            throw "Teamfight Manager 2 stable SDK 0.5.8 or newer is required; found $baseVersion"
        }
    }

    $vendorFiles = Get-ChildItem -LiteralPath $VendoredApi -File -Recurse | ForEach-Object {
        $_.FullName.Substring($VendoredApi.Length).TrimStart('\', '/') -replace '\\', '/'
    } | Sort-Object
    $externalFiles = Get-ChildItem -LiteralPath $externalApi -File -Recurse | ForEach-Object {
        $_.FullName.Substring($externalApi.Length).TrimStart('\', '/') -replace '\\', '/'
    } | Sort-Object
    $exactFileSet = ($vendorFiles -join "`n") -eq ($externalFiles -join "`n")
    if ($exactFileSet) {
        foreach ($relative in $vendorFiles) {
            $vendorFile = Join-Path $VendoredApi ($relative -replace '/', [System.IO.Path]::DirectorySeparatorChar)
            $externalFile = Join-Path $externalApi ($relative -replace '/', [System.IO.Path]::DirectorySeparatorChar)
            if ((Get-Sha256Hex -Path $vendorFile) -ne (Get-Sha256Hex -Path $externalFile)) {
                throw "Vendored stable API differs from the supplied SDK: $relative"
            }
        }
        return
    }

    # A newer game may ship additional append-only ABI slots and files.  Keep
    # this mod compiled against its declared required ABI so one DLL remains
    # loadable on its base 0.5.8 baseline and later hosts.  The newer SDK publishes the
    # exact frozen contract for every supported older level; matching that
    # contract is the authoritative compatibility check.
    $vendorLib = Join-Path $VendoredApi "src\lib.rs"
    $vendorLibText = Get-Content -LiteralPath $vendorLib -Raw -Encoding UTF8
    $abiMatch = [regex]::Match($vendorLibText, 'pub const ABI_LEVEL:\s*u32\s*=\s*(\d+);')
    if (-not $abiMatch.Success) {
        throw "Vendored stable API does not declare ABI_LEVEL"
    }
    $vendorAbi = [int]$abiMatch.Groups[1].Value
    $vendorContract = Join-Path $VendoredApi "contract\abi_v1.txt"
    $externalFrozenContract = Join-Path $externalApi "contract\frozen\abi_level_$vendorAbi.txt"
    if (-not (Test-Path -LiteralPath $externalFrozenContract -PathType Leaf)) {
        throw "Supplied SDK does not publish the vendored ABI level $vendorAbi frozen contract"
    }
    if ((Get-Sha256Hex -Path $vendorContract) -ne (Get-Sha256Hex -Path $externalFrozenContract)) {
        throw "Vendored ABI level $vendorAbi differs from the supplied SDK frozen contract"
    }
    Write-Host "Verified vendored ABI level $vendorAbi against the supplied newer SDK frozen contract"
}

$modRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$vendorApi = (Resolve-Path -LiteralPath (Join-Path $modRoot "vendor\mod-api-stable")).Path
if (-not $SdkDir) {
    $gameRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $modRoot))
    $bundledStableSdk = Join-Path $gameRoot "mod-sdk-stable"
    if (Test-Path -LiteralPath $bundledStableSdk -PathType Container) {
        $SdkDir = $bundledStableSdk
    }
}
if ($SdkDir) {
    Assert-StableSdkParity -VendoredApi $vendorApi -ExternalSdk $SdkDir
}

$manifest = Join-Path $modRoot "Cargo.toml"
$targetDir = Join-Path $modRoot "target"
cargo build --release --manifest-path $manifest --target-dir $targetDir
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$builtDll = Join-Path $targetDir "release\lol_mod.dll"
if (-not $OutDll) {
    $OutDll = Join-Path $modRoot "lol_mod.dll"
} else {
    $OutDll = [System.IO.Path]::GetFullPath($OutDll)
    $outParent = Split-Path -Parent $OutDll
    New-Item -ItemType Directory -Force -Path $outParent | Out-Null
}
Copy-Item -LiteralPath $builtDll -Destination $OutDll -Force

$env:LOL_MOD_DLL_TO_VERIFY = $OutDll
$exported = @'
import ctypes
import os

library = ctypes.WinDLL(os.environ["LOL_MOD_DLL_TO_VERIFY"])
entry = library.tfm2_mod_entry_stable
entry.restype = ctypes.c_void_p
required = library.tfm2_mod_required_abi_level
required.restype = ctypes.c_uint32
print(required())
'@ | python -
$probeExitCode = $LASTEXITCODE
Remove-Item Env:LOL_MOD_DLL_TO_VERIFY -ErrorAction SilentlyContinue
if ($probeExitCode -ne 0 -or $exported.Trim() -ne "8") {
    throw "Built DLL did not export the required Teamfight Manager 2 stable ABI level 8 entry points"
}

Write-Output "Build successful: $OutDll (stable ABI, requires level 8)"
