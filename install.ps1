# Install or upgrade the `ezy` command (EzyPlatform CLI) on Windows.
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/itsddvn/ezyplatform-cli/main/install.ps1 | iex"
# Uses uv (https://docs.astral.sh/uv), installing it first when missing; uv also
# downloads Python when the machine has no Python 3.9+. Installs from PyPI, or
# from the latest GitHub release while the package is not on PyPI (set $env:EZY_SOURCE
# to force a source, e.g. git+https://github.com/itsddvn/ezyplatform-cli for main).
# $env:EZY_NO_MODIFY_PATH = 1 leaves the user PATH untouched.
$ErrorActionPreference = 'Stop'

$Pkg = 'ezyplatform-cli'
$Repo = 'https://github.com/itsddvn/ezyplatform-cli'

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
        # releases/latest redirects to .../tag/vX.Y.Z (no API call, so no rate limit);
        # send Accept: the cached redirect for requests without one can be stale
        $resp = Invoke-WebRequest "$Repo/releases/latest" -UseBasicParsing -Method Head -Headers @{ Accept = "*/*" }
        $final = if ($resp.BaseResponse.ResponseUri) { $resp.BaseResponse.ResponseUri.AbsoluteUri } else { $resp.BaseResponse.RequestMessage.RequestUri.AbsoluteUri }
        $tag = ($final -split '/tag/')[-1]
        if ($tag -notmatch '^v\d') { throw 'no ezy release found on GitHub' }
        $source = "$Repo/releases/download/$tag/ezyplatform_cli-$($tag.Substring(1))-py3-none-any.whl"
    }
}

Write-Host "Installing ezy from $source..."
& $uv tool install --force --python '>=3.9' $source
if ($LASTEXITCODE -ne 0) { throw "uv tool install failed ($LASTEXITCODE)" }
# update-shell writes notes to stderr, which Windows PowerShell 5 turns into errors under 'Stop'
if (-not $env:EZY_NO_MODIFY_PATH) { try { & $uv tool update-shell *> $null } catch {} }

$bin = (& $uv tool dir --bin).Trim()
Write-Host ''
& "$bin\ezy.exe" --version
if (Get-Command ezy -ErrorAction SilentlyContinue) {
    Write-Host 'Done. Start with: ezy init my-site --admin-url https://admin.example.com'
} else {
    Write-Host "Done. Open a new terminal so 'ezy' is on your PATH, then: ezy init my-site --admin-url https://admin.example.com"
}
