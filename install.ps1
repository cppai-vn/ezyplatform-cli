# Install or upgrade the `ezy` command (EzyPlatform CLI) on Windows.
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/itsddvn/ezyplatform-cli/main/install.ps1 | iex"
# Uses uv (https://docs.astral.sh/uv), installing it first when missing; uv also
# downloads Python when the machine has no Python 3.9+. Installs from PyPI, or
# from the latest GitHub release while the package is not on PyPI (set $env:EZY_SOURCE
# to force a source, e.g. git+https://github.com/itsddvn/ezyplatform-cli for main).
# $env:EZY_NO_MODIFY_PATH = 1 leaves the user PATH untouched.
$ErrorActionPreference = 'Stop'

$Pkg = 'ezyplatform-cli'
$Releases = 'https://api.github.com/repos/itsddvn/ezyplatform-cli/releases/latest'

$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
    Write-Host 'Installing uv (Python tool manager)...'
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    foreach ($dir in @($env:UV_INSTALL_DIR, $env:XDG_BIN_HOME, "$HOME\.local\bin", "$HOME\.cargo\bin")) {
        if ($dir -and (Test-Path "$dir\uv.exe")) { $uv = "$dir\uv.exe"; break }
    }
    if (-not $uv) { throw 'uv was installed but not found; open a new terminal and run this again.' }
}

$source = $env:EZY_SOURCE
if (-not $source) {
    try {
        Invoke-WebRequest "https://pypi.org/pypi/$Pkg/json" -UseBasicParsing -Method Head | Out-Null
        $source = $Pkg
    } catch {
        $wheel = (Invoke-RestMethod $Releases).assets | Where-Object { $_.name -like '*.whl' } | Select-Object -First 1
        if (-not $wheel) { throw 'no ezy release found on GitHub' }
        $source = $wheel.browser_download_url
    }
}

Write-Host "Installing ezy from $source..."
& $uv tool install --force --python '>=3.9' $source
if ($LASTEXITCODE -ne 0) { throw "uv tool install failed ($LASTEXITCODE)" }
if (-not $env:EZY_NO_MODIFY_PATH) { & $uv tool update-shell 2>$null | Out-Null }

$bin = (& $uv tool dir --bin).Trim()
Write-Host ''
& "$bin\ezy.exe" --version
if (Get-Command ezy -ErrorAction SilentlyContinue) {
    Write-Host 'Done. Start with: ezy init my-site --admin-url https://admin.example.com'
} else {
    Write-Host "Done. Open a new terminal so 'ezy' is on your PATH, then: ezy init my-site --admin-url https://admin.example.com"
}
