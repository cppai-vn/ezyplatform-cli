param(
    [Parameter(Position = 0)] [string] $Command = "help",
    [string] $Dir = "",
    [string] $EzyHome = "",
    [string] $DevDir = "",
    [switch] $SkipProfile,
    [string] $Group = "",
    [string] $Package = "",
    [string] $Modules = "",
    [string] $Out = "",
    [string] $Category = "",
    [int] $Limit = 20,
    [string] $Lang = "",
    [string] $Types = "",
    [switch] $ActivateTheme,
    [switch] $NoRestart,
    [Parameter(ValueFromRemainingArguments = $true)] [string[]] $Rest = @()
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$MarketUrl = if ($env:EZY_MARKET_URL) { $env:EZY_MARKET_URL } else { "https://ezyplatform.com" }
$InstallSkillUrl = "$MarketUrl/api/v1/skill-library/skills/1627/download"
$DevRepoZip = "https://github.com/youngmonkeys/ezyplatform-development/archive/refs/heads/master.zip"
$MavenRepoUrl = "https://repo.maven.apache.org/maven2"
$MavenSeries = "3.9"
$CfrVersion = "0.152"
$ModuleTypes = @("admin-plugin", "web-plugin", "theme", "socket-plugin", "socket-app")
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Show-Usage {
    @"
usage: ezy dev <command> [arguments] [options]

environment
  check                        show EzyPlatform, JDK 8, Maven, SDK and dev libraries state (changes nothing)
  setup                        install what is missing: JDK 8, Maven, EzyPlatform SDK, ezyplatform-parent + sdk libraries,
                               and the user environment variables (EZYPLATFORM_HOME, EZYPLATFORM_SDK, PATH)
  run "<command line>"         run a command line with JDK 8, Maven, ezy.bat and EZYPLATFORM_HOME set

project (run from the project root)
  create <name>                create a project with the SDK (options: -Group, -Package, -Modules, -Out)
  link <plugin...>             install the plugins if needed, ezy.bat link them, add them to module.properties
                               dependencies and sync their versions (option: -Types admin-plugin,web-plugin,theme)
  sync-versions                ezy.bat sdv: sync <plugin>.version properties with the installed plugins
  export                       build (the steps of export.bat), export, activate the project modules, restart

marketplace
  market search [keyword]      search plugins and themes (options: -Category, -Limit)
  market info <name>           details of one project
  market docs <name>           list the docs of a project (option: -Lang)
  market doc <name> <slug>     print one doc as markdown (option: -Lang)

local EzyPlatform
  install-plugin <name...>     install plugins from the market with their dependencies, activate them, restart
                               (options: -ActivateTheme, -NoRestart)
  activate <name>              activate every installed module of a project (theme: deactivate the other themes)
  restart                      restart admin and web (starts MySQL first when installed by ezyplatform-install)
  status                       admin and web state, URLs, active modules
  tables [plugin|core]         list the tables a plugin (or the platform core) creates, with their SQL file
  find-class <name>            find which installed jar contains a class
  decompile <class|jar>        decompile a class or a jar of the installed platform/plugins with CFR

options
  -Dir <folder>                folder of an install made by ezyplatform-install (default: `$env:EZY_DIR or C:\ezyplatform)
  -EzyHome <folder>            EzyPlatform home when it was not installed by ezyplatform-install
  -DevDir <folder>             where dev tools go (default: <dir>\dev, or %USERPROFILE%\ezyplatform-dev)
  -SkipProfile                 setup: do not change the user environment variables

exit codes: 0 ok, 1 error, 3 a requirement is missing (see the NEED line)
"@ | Write-Output
}

function Log([string] $Message) { Write-Host "[ezydev] $Message" }
function Fail([string] $Message) { [Console]::Error.WriteLine("[ezydev] ERROR: $Message"); exit 1 }
function Need([string] $Code, [string] $Message) { Write-Host "NEED ${Code}: $Message"; exit 3 }

function Write-TextFile([string] $Path, [string] $Text) {
    $parent = Split-Path $Path -Parent
    if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    [System.IO.File]::WriteAllText($Path, $Text, $Utf8NoBom)
}

$Arch = $env:PROCESSOR_ARCHITECTURE
if ($env:PROCESSOR_ARCHITEW6432) { $Arch = $env:PROCESSOR_ARCHITEW6432 }

$InstallDir = ""
$InstallMode = ""
$InstallState = $null
$CandidateDir = if ($Dir) { $Dir } elseif ($env:EZY_DIR) { $env:EZY_DIR } else { "C:\ezyplatform" }
$CandidateDir = [System.IO.Path]::GetFullPath($CandidateDir)
$InstallStateFile = Join-Path $CandidateDir ".ezy\state.json"
if (Test-Path $InstallStateFile) {
    $InstallState = Get-Content $InstallStateFile -Raw | ConvertFrom-Json
    $InstallDir = $CandidateDir
    $InstallMode = [string]$InstallState.Mode
}

$EzHome = ""
if ($EzyHome) {
    $EzHome = [System.IO.Path]::GetFullPath($EzyHome)
} elseif ($Dir -and $InstallMode -eq "native") {
    $EzHome = Join-Path $InstallDir "ezyplatform"
} elseif ($env:EZYPLATFORM_HOME -and (Test-Path (Join-Path $env:EZYPLATFORM_HOME "cli.bat"))) {
    $EzHome = [System.IO.Path]::GetFullPath($env:EZYPLATFORM_HOME)
} elseif ($InstallMode -eq "native") {
    $EzHome = Join-Path $InstallDir "ezyplatform"
}
$EzHome = $EzHome.TrimEnd("\")

$IsSkillInstall = $InstallDir -and ($InstallMode -eq "native") -and ($EzHome -eq (Join-Path $InstallDir "ezyplatform"))
if ($DevDir) {
    $DevRoot = [System.IO.Path]::GetFullPath($DevDir)
} elseif ($IsSkillInstall) {
    $DevRoot = Join-Path $InstallDir "dev"
} else {
    $DevRoot = Join-Path $env:USERPROFILE "ezyplatform-dev"
}
$DevStateFile = Join-Path $DevRoot "dev.json"
$Ctl = ""
if ($IsSkillInstall -and (Test-Path (Join-Path $InstallDir "ezyplatform-ctl.ps1"))) { $Ctl = Join-Path $InstallDir "ezyplatform-ctl.ps1" }

$Dev = [ordered]@{ JavaHome = ""; MavenHome = ""; SdkHome = "" }
if (Test-Path $DevStateFile) {
    $loaded = Get-Content $DevStateFile -Raw | ConvertFrom-Json
    foreach ($p in $loaded.PSObject.Properties) { $Dev[$p.Name] = [string]$p.Value }
}

function Save-DevState {
    New-Item -ItemType Directory -Force -Path $DevRoot | Out-Null
    Write-TextFile $DevStateFile ($Dev | ConvertTo-Json)
}

function Get-Curl {
    $curl = Join-Path $env:WINDIR "System32\curl.exe"
    if (Test-Path $curl) { return $curl }
    $found = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($found) { return $found.Source }
    return $null
}

function Get-HttpCode([string] $Url) {
    $curl = Get-Curl
    if ($curl) {
        $code = & $curl -s -o NUL -m 10 -w "%{http_code}" $Url 2>$null
        if ($code) { return [string]$code }
        return "000"
    }
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -MaximumRedirection 0 -TimeoutSec 10 -ErrorAction Stop
        return [string][int]$response.StatusCode
    } catch {
        if ($_.Exception.Response) { return [string][int]$_.Exception.Response.StatusCode }
        return "000"
    }
}

function Get-Text([string] $Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 60 -ErrorAction Stop
        if ($response.Content -is [byte[]]) { return [System.Text.Encoding]::UTF8.GetString($response.Content) }
        return [System.Text.Encoding]::UTF8.GetString($response.RawContentStream.ToArray())
    } catch {
        return $null
    }
}

function Get-Json([string] $Url) {
    $text = Get-Text $Url
    if ($null -eq $text) { return $null }
    return $text | ConvertFrom-Json
}

function Invoke-Download([string] $Url, [string] $OutFile) {
    Log "downloading $Url"
    $part = "$OutFile.part"
    $curl = Get-Curl
    if ($curl) {
        & $curl -fsSL --retry 3 --retry-delay 3 --connect-timeout 30 -o $part $Url
        if ($LASTEXITCODE -ne 0) { return $false }
    } else {
        try { Invoke-WebRequest -Uri $Url -OutFile $part -UseBasicParsing -ErrorAction Stop } catch { return $false }
    }
    Move-Item -Force $part $OutFile
    return $true
}

function Expand-Zip([string] $Zip, [string] $Destination) {
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $tar = Join-Path $env:WINDIR "System32\tar.exe"
    if (Test-Path $tar) {
        & $tar -xf $Zip -C $Destination
        if ($LASTEXITCODE -eq 0) { return }
    }
    Expand-Archive -Path $Zip -DestinationPath $Destination -Force -ErrorAction Stop
}

function Get-FileHashHex([string] $Algorithm, [string] $Path) {
    return (Get-FileHash -Algorithm $Algorithm $Path).Hash.ToLower()
}

function New-TempDir([string] $Name) {
    $tmp = Join-Path $DevRoot "tmp\$Name"
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    return $tmp
}

function Test-Jdk8([string] $JavaHome) {
    if (-not $JavaHome) { return $false }
    $java = Join-Path $JavaHome "bin\java.exe"
    if (-not (Test-Path $java) -or -not (Test-Path (Join-Path $JavaHome "bin\javac.exe"))) { return $false }
    $output = & cmd.exe /c "`"$java`" -version 2>&1"
    return (($output -join "`n") -match '"1\.8')
}

function Resolve-Java {
    if (Test-Jdk8 $Dev.JavaHome) { return $true }
    $candidates = @()
    if ($InstallState -and $InstallState.JavaHome) { $candidates += [string]$InstallState.JavaHome }
    $roots = @(Join-Path $DevRoot "jdk")
    if ($InstallDir) { $roots = @(Join-Path $InstallDir "jdk") + $roots }
    foreach ($root in $roots) {
        if (Test-Path $root) {
            $javac = Get-ChildItem -Path $root -Recurse -Filter javac.exe -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($javac) { $candidates += $javac.Directory.Parent.FullName }
        }
    }
    if ($env:JAVA_HOME) { $candidates += $env:JAVA_HOME }
    foreach ($candidate in $candidates) {
        if (Test-Jdk8 $candidate) { $Dev.JavaHome = $candidate; return $true }
    }
    $Dev.JavaHome = ""
    return $false
}

function Install-Jdk {
    if (Resolve-Java) { return }
    $api = "https://api.azul.com/metadata/v1/zulu/packages/?java_version=8&os=windows&arch=x64&archive_type=zip&java_package_type=jdk&javafx_bundled=false&crac_supported=false&latest=true&release_status=ga&availability_types=CA&certifications=tck&page=1&page_size=1"
    $package = @(Get-Json $api)[0]
    if (-not $package) { Fail "cannot find JDK 8 on api.azul.com" }
    $sha = ""
    $details = Get-Json "https://api.azul.com/metadata/v1/zulu/packages/$($package.package_uuid)"
    if ($details) { $sha = [string]$details.sha256_hash }
    $tmp = New-TempDir "jdk"
    $zip = Join-Path $tmp "jdk.zip"
    if (-not (Invoke-Download $package.download_url $zip)) { Fail "JDK download failed" }
    if ($sha -and ((Get-FileHashHex SHA256 $zip) -ne $sha.ToLower())) { Fail "JDK checksum mismatch, run setup again" }
    Expand-Zip $zip $tmp
    Remove-Item -Force $zip
    $target = Join-Path $DevRoot "jdk"
    if (Test-Path $target) { Remove-Item -Recurse -Force $target }
    Move-Item (Get-ChildItem -Path $tmp -Directory | Select-Object -First 1).FullName $target
    Remove-Item -Recurse -Force $tmp
    $Dev.JavaHome = ""
    if (-not (Resolve-Java)) { Fail "the downloaded JDK is not a Java 8 JDK" }
    Log "JDK 8 installed at $($Dev.JavaHome)"
}

function Resolve-Maven {
    if ($Dev.MavenHome -and (Test-Path (Join-Path $Dev.MavenHome "bin\mvn.cmd"))) { return $true }
    $local = Join-Path $DevRoot "maven"
    if (Test-Path (Join-Path $local "bin\mvn.cmd")) { $Dev.MavenHome = $local; return $true }
    $found = Get-Command mvn.cmd -ErrorAction SilentlyContinue
    if ($found) {
        $mavenRoot = Split-Path (Split-Path $found.Source -Parent) -Parent
        if (Test-Path (Join-Path $mavenRoot "bin\mvn.cmd")) { $Dev.MavenHome = $mavenRoot; return $true }
    }
    $Dev.MavenHome = ""
    return $false
}

function Install-Maven {
    if (Resolve-Maven) { return }
    $metadata = Get-Text "$MavenRepoUrl/org/apache/maven/apache-maven/maven-metadata.xml"
    if (-not $metadata) { Fail "cannot reach Maven Central" }
    $version = ([regex]::Matches($metadata, "<version>($([regex]::Escape($MavenSeries))\.\d+)</version>") | ForEach-Object { $_.Groups[1].Value } |
        Sort-Object { [int]($_.Split(".")[2]) } | Select-Object -Last 1)
    if (-not $version) { Fail "cannot find the latest Maven $MavenSeries" }
    $url = "$MavenRepoUrl/org/apache/maven/apache-maven/$version/apache-maven-$version-bin.zip"
    $tmp = New-TempDir "maven"
    $zip = Join-Path $tmp "maven.zip"
    if (-not (Invoke-Download $url $zip)) { Fail "Maven download failed" }
    $expected = ((Get-Text "$url.sha512") -split '\s+')[0]
    if (-not $expected -or (Get-FileHashHex SHA512 $zip) -ne $expected.ToLower()) { Fail "Maven checksum mismatch, run setup again" }
    Expand-Zip $zip $tmp
    $target = Join-Path $DevRoot "maven"
    if (Test-Path $target) { Remove-Item -Recurse -Force $target }
    Move-Item (Join-Path $tmp "apache-maven-$version") $target
    Remove-Item -Recurse -Force $tmp
    $Dev.MavenHome = $target
    Log "Maven $version installed at $target"
}

function Get-SdkVersion([string] $SdkHome) {
    $file = Join-Path $SdkHome "sdk.properties"
    if (-not (Test-Path $file)) { return "" }
    return (Get-PropertyValue $file "sdk.version")
}

function Resolve-Sdk {
    foreach ($candidate in @($Dev.SdkHome, $env:EZYPLATFORM_SDK, (Join-Path $DevRoot "ezyplatform-sdk"))) {
        if ($candidate -and (Test-Path (Join-Path $candidate "bin\ezy.bat")) -and (Test-Path (Join-Path $candidate "sdk.properties"))) {
            $Dev.SdkHome = $candidate.TrimEnd("\")
            return $true
        }
    }
    $Dev.SdkHome = ""
    return $false
}

function Install-Sdk {
    if (Resolve-Sdk) { return }
    $latest = Get-Json "$MarketUrl/api/v1/platform-sdks/latest-version"
    if (-not $latest -or -not $latest.version) { Fail "cannot read the latest SDK version from $MarketUrl" }
    $tmp = New-TempDir "sdk"
    $zip = Join-Path $tmp "sdk.zip"
    if (-not (Invoke-Download "$MarketUrl/api/v1/platform-sdks/$($latest.version)/download" $zip)) { Fail "SDK download failed" }
    if ($latest.sha256 -and (Get-FileHashHex SHA256 $zip) -ne ([string]$latest.sha256).ToLower()) { Fail "SDK checksum mismatch, run setup again" }
    Expand-Zip $zip $tmp
    $source = Join-Path $tmp "ezyplatform-sdk"
    if (-not (Test-Path (Join-Path $source "bin\ezy.bat"))) { Fail "unexpected SDK archive layout" }
    $target = Join-Path $DevRoot "ezyplatform-sdk"
    if (Test-Path $target) { Remove-Item -Recurse -Force $target }
    Move-Item $source $target
    Remove-Item -Recurse -Force $tmp
    $Dev.SdkHome = $target
    Log "EzyPlatform SDK $($latest.version) installed at $target"
}

function Get-M2Repo {
    if ($env:MAVEN_LOCAL_REPO) { return $env:MAVEN_LOCAL_REPO }
    return (Join-Path $env:USERPROFILE ".m2\repository")
}

function Get-RequiredParentVersion {
    $pom = Join-Path $Dev.SdkHome "templates\project-template\pom.xml"
    if (-not (Test-Path $pom)) { return "" }
    $text = Get-Content $pom -Raw
    $match = [regex]::Match($text, "<parent>[\s\S]*?<version>([^<]+)</version>")
    if ($match.Success) { return $match.Groups[1].Value.Trim() }
    return ""
}

function Test-DevLibs {
    $version = Get-RequiredParentVersion
    if (-not $version) { return $false }
    $repo = Join-Path (Get-M2Repo) "org\youngmonkeys"
    return (Test-Path (Join-Path $repo "ezyplatform-parent\$version\ezyplatform-parent-$version.pom")) -and
        (Test-Path (Join-Path $repo "ezyplatform-test-sdk\$version")) -and
        (Test-Path (Join-Path $repo "ezyplatform-devtools"))
}

function Set-DevEnvironment {
    [void](Resolve-Java)
    [void](Resolve-Maven)
    [void](Resolve-Sdk)
    $prefix = @()
    if ($Dev.JavaHome) { $env:JAVA_HOME = $Dev.JavaHome; $prefix += (Join-Path $Dev.JavaHome "bin") }
    if ($Dev.MavenHome) { $env:MAVEN_HOME = $Dev.MavenHome; $prefix += (Join-Path $Dev.MavenHome "bin") }
    if ($Dev.SdkHome) { $env:EZYPLATFORM_SDK = $Dev.SdkHome; $prefix += (Join-Path $Dev.SdkHome "bin") }
    if ($EzHome) { $env:EZYPLATFORM_HOME = $EzHome }
    $env:PATH = (($prefix + @($env:PATH)) -join ";")
}

function Invoke-Logged([string] $CommandLine, [string] $WorkDir, [string] $LogFile) {
    Add-Content -Path $LogFile -Value "> $CommandLine" -Encoding UTF8
    Push-Location $WorkDir
    try {
        & cmd.exe /c "$CommandLine >> `"$LogFile`" 2>&1"
        return $LASTEXITCODE
    } finally {
        Pop-Location
    }
}

function Install-DevLibs {
    if ((Test-DevLibs) -and (Test-Path (Join-Path $DevRoot "ezyplatform-development\ezyplatform-sdk"))) { return }
    Set-DevEnvironment
    $tmp = New-TempDir "dev-libs"
    $logs = Join-Path $DevRoot "logs"
    New-Item -ItemType Directory -Force -Path $logs | Out-Null
    $logFile = Join-Path $logs "dev-libs-build.log"
    Set-Content -Path $logFile -Value "" -Encoding UTF8
    $zip = Join-Path $tmp "dev.zip"
    if (-not (Invoke-Download $DevRepoZip $zip)) { Fail "cannot download ezyplatform-development from GitHub" }
    Expand-Zip $zip $tmp
    $src = (Get-ChildItem -Path $tmp -Directory | Select-Object -First 1).FullName
    if (-not (Test-Path (Join-Path $src "ezyplatform-parent"))) { Fail "unexpected ezyplatform-development archive layout" }
    Log "building ezyplatform-devtools, ezyplatform-parent and ezyplatform-sdk into $(Get-M2Repo) (a few minutes the first time)"
    foreach ($module in @("ezyplatform-devtools", "ezyplatform-parent", "ezyplatform-sdk")) {
        $code = Invoke-Logged "mvn -B clean install -Dmaven.test.skip=true -Dcheckstyle.skip=true" (Join-Path $src $module) $logFile
        if ($code -ne 0) {
            Get-Content $logFile -Tail 60 | Out-Host
            Fail "building $module failed, full log: $logFile"
        }
    }
    Get-ChildItem -Path $src -Recurse -Directory -Filter target -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    $sources = Join-Path $DevRoot "ezyplatform-development"
    if (Test-Path $sources) { Remove-Item -Recurse -Force $sources }
    Move-Item $src $sources
    Remove-Item -Recurse -Force $tmp
    if (-not (Test-DevLibs)) { Fail "ezyplatform-parent $(Get-RequiredParentVersion) is still missing in $(Get-M2Repo), see $logFile" }
    Log "EzyPlatform development libraries installed"
}

function Add-UserPath([string] $Folder) {
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($current) { $parts = $current.Split(";") | Where-Object { $_ } }
    if ($parts -notcontains $Folder) {
        [Environment]::SetEnvironmentVariable("Path", (($parts + $Folder) -join ";"), "User")
    }
}

function Set-UserEnvironment {
    [Environment]::SetEnvironmentVariable("EZYPLATFORM_HOME", $EzHome, "User")
    [Environment]::SetEnvironmentVariable("EZYPLATFORM_SDK", $Dev.SdkHome, "User")
    Add-UserPath (Join-Path $Dev.SdkHome "bin")
    Add-UserPath (Join-Path $Dev.MavenHome "bin")
    $userJava = [Environment]::GetEnvironmentVariable("JAVA_HOME", "User")
    $machineJava = [Environment]::GetEnvironmentVariable("JAVA_HOME", "Machine")
    if (-not $userJava -and -not $machineJava) {
        [Environment]::SetEnvironmentVariable("JAVA_HOME", $Dev.JavaHome, "User")
        Add-UserPath (Join-Path $Dev.JavaHome "bin")
    }
}

function Assert-Home {
    if (-not $EzHome -or -not (Test-Path (Join-Path $EzHome "cli.bat"))) {
        if ($InstallMode -eq "docker") {
            Need "native_install" "EzyPlatform at $InstallDir runs in Docker; development needs a native install: run ezyplatform-install with -Dir <another folder> (without -Docker), then pass -Dir <that folder>"
        }
        Need "ezyplatform_not_installed" "EzyPlatform is not installed: run the ezyplatform-install skill ($InstallSkillUrl) first, or pass -EzyHome <EzyPlatform folder>"
    }
}

function Assert-Java { if (-not (Resolve-Java)) { Need "jdk8" "JDK 8 not found: run setup" } }

function Assert-Dev {
    Assert-Home
    Assert-Java
    if (-not (Resolve-Maven)) { Need "dev_setup" "Maven not found: run setup" }
    if (-not (Resolve-Sdk)) { Need "dev_setup" "EzyPlatform SDK not found: run setup" }
    Set-DevEnvironment
}

function Get-PropertyValue([string] $File, [string] $Key) {
    if (-not (Test-Path $File)) { return "" }
    foreach ($line in Get-Content $File) {
        if ($line.StartsWith("$Key=")) { return $line.Substring($Key.Length + 1).Trim() }
    }
    return ""
}

function Get-AdminPort {
    $port = Get-PropertyValue (Join-Path $EzHome "admin\settings\config.properties") "server.port"
    if ($port) { return $port }
    return "9090"
}

function Get-WebPort {
    $port = Get-PropertyValue (Join-Path $EzHome "web\settings\config.properties") "server.port"
    if ($port) { return $port }
    return "8080"
}

function Invoke-Cli([string] $Arguments) {
    $env:JAVA_HOME = $Dev.JavaHome
    $env:PATH = (Join-Path $Dev.JavaHome "bin") + ";" + $env:PATH
    Push-Location $EzHome
    try {
        $output = & cmd.exe /c "cli.bat `"$Arguments`" 2>&1"
        return ($output -join "`n")
    } finally {
        Pop-Location
    }
}

function Get-TypeFolder([string] $Type) {
    switch ($Type) {
        "admin-plugin" { return "admin\plugins" }
        "web-plugin" { return "web\plugins" }
        "theme" { return "web\themes" }
        "socket-plugin" { return "socket\plugins" }
        "socket-app" { return "socket\apps" }
    }
}

function Get-InstalledTypes([string] $Name) {
    $result = @()
    foreach ($type in $ModuleTypes) {
        if (Test-Path (Join-Path $EzHome "$(Get-TypeFolder $type)\$Name\module.properties")) { $result += $type }
    }
    return ,$result
}

function Get-ModuleDependencies([string] $Name) {
    $deps = @()
    foreach ($type in $ModuleTypes) {
        $file = Join-Path $EzHome "$(Get-TypeFolder $type)\$Name\module.properties"
        if (Test-Path $file) {
            $deps += (Get-PropertyValue $file "dependencies").Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
        }
    }
    return ,@($deps | Sort-Object -Unique)
}

function Get-RuntimeFile([string] $Type) {
    switch ($Type) {
        "admin-plugin" { return Join-Path $EzHome ".runtime\admin\plugins.txt" }
        "web-plugin" { return Join-Path $EzHome ".runtime\web\plugins.txt" }
        "theme" { return Join-Path $EzHome ".runtime\web\themes.txt" }
        "socket-plugin" { return Join-Path $EzHome ".runtime\socket\plugins.txt" }
        "socket-app" { return Join-Path $EzHome ".runtime\socket\apps.txt" }
    }
}

function Get-ActiveNames([string] $Type) {
    $file = Get-RuntimeFile $Type
    if (-not (Test-Path $file)) { return ,@() }
    try {
        $items = Get-Content $file -Raw | ConvertFrom-Json
        return ,@($items | Where-Object { $_.active } | ForEach-Object { [string]$_.name })
    } catch {
        return ,@()
    }
}

function Test-Active([string] $Type, [string] $Name) {
    return (Get-ActiveNames $Type) -contains $Name
}

function Enable-Project([string] $Name, [bool] $WithTheme) {
    foreach ($type in (Get-InstalledTypes $Name)) {
        if ($type -eq "theme") {
            if (-not $WithTheme) { continue }
            if (Test-Active "theme" $Name) { continue }
            foreach ($other in (Get-ActiveNames "theme")) {
                if ($other -ne $Name) {
                    [void](Invoke-Cli "deactivate theme $other")
                    Log "deactivated theme $other"
                }
            }
        }
        if (Test-Active $type $Name) { continue }
        $output = Invoke-Cli "activate $type $Name"
        if (Test-Active $type $Name) {
            Log "activated $Name ($type)"
        } else {
            Write-Host $output
            Fail "cannot activate $Name ($type)"
        }
    }
}

function Get-TargetProcess([string] $Target) {
    $class = if ($Target -eq "admin") { "ezyplatform.admin.AdminStartup" } elseif ($Target -eq "web") { "ezyplatform.web.WebStartup" } else { "ezyplatform.socket" }
    $javaHome = $Dev.JavaHome
    Get-CimInstance Win32_Process -Filter "Name='java.exe'" | Where-Object {
        $_.CommandLine -and $_.CommandLine.Contains($class) -and (
            ($_.ExecutablePath -and $javaHome -and $_.ExecutablePath.StartsWith($javaHome, [System.StringComparison]::OrdinalIgnoreCase)) -or
            ($InstallDir -and $_.ExecutablePath -and $_.ExecutablePath.StartsWith($InstallDir, [System.StringComparison]::OrdinalIgnoreCase))
        )
    }
}

function Stop-Target([string] $Target) {
    $processes = @(Get-TargetProcess $Target)
    if ($processes.Count -eq 0) { return }
    Log "stopping $Target"
    foreach ($process in $processes) { Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

function Start-Target([string] $Target) {
    $logs = Join-Path $DevRoot "logs"
    New-Item -ItemType Directory -Force -Path $logs | Out-Null
    $consoleLog = Join-Path $logs "$Target-console.log"
    $env:JAVA_HOME = $Dev.JavaHome
    $env:PATH = (Join-Path $Dev.JavaHome "bin") + ";" + $env:PATH
    Log "starting $Target"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c cli.bat `"console $Target`" > `"$consoleLog`" 2>&1" -WorkingDirectory $EzHome -WindowStyle Hidden | Out-Null
}

function Wait-Http([string] $Url, [int] $Seconds, [string] $Target) {
    $waited = 0
    while ($waited -lt $Seconds) {
        $code = Get-HttpCode $Url
        if ($code -match '^[234]\d\d$') { Log "$Target is up (HTTP $code)"; return }
        if ($waited -ge 30 -and -not (Get-TargetProcess $Target)) {
            $serverLog = Join-Path $EzHome "logs\$Target-server.log"
            if (Test-Path $serverLog) { Get-Content $serverLog -Tail 80 | Out-Host }
            Fail "$Target stopped while starting, see $serverLog"
        }
        Start-Sleep -Seconds 3
        $waited += 3
    }
    Fail "$Target did not answer at $Url after ${Seconds}s"
}

function Set-WebDefaultLanguage {
    if (-not $IsSkillInstall -or -not $InstallState) { return $true }
    $rootCnf = Join-Path $InstallDir ".ezy\mysql-root.cnf"
    if (-not (Test-Path $rootCnf) -or $InstallState.DbUrl) { return $true }
    $mysql = Join-Path ([string]$InstallState.MysqlHome) "bin\mysql.exe"
    if (-not (Test-Path $mysql)) { return $true }
    $lang = [string]$InstallState.Lang
    if ($lang -notmatch '^[a-zA-Z_-]{2,10}$') { $lang = "en" }
    $sql = "INSERT INTO ezy_settings (setting_name, data_type, setting_value, created_at, updated_at) VALUES ('web_default_language', 'STRING', '$lang', NOW(), NOW()) ON DUPLICATE KEY UPDATE setting_value = IF(setting_value = '', VALUES(setting_value), setting_value);"
    & $mysql "--defaults-extra-file=$rootCnf" -D ezyplatform -e $sql 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Invoke-Restart {
    Assert-Home
    Assert-Java
    [void](Set-WebDefaultLanguage)
    Stop-Target "web"
    Stop-Target "admin"
    if ($Ctl) {
        Log "starting EzyPlatform (MySQL, admin, web)"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Ctl start 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) { Fail "start failed, see $InstallDir\logs and $EzHome\logs" }
    } else {
        Start-Target "admin"
        Start-Sleep -Seconds 5
        Wait-Http "http://127.0.0.1:$(Get-AdminPort)/" 420 "admin"
        Start-Target "web"
        Start-Sleep -Seconds 5
        Wait-Http "http://127.0.0.1:$(Get-WebPort)/" 300 "web"
    }
    [void](Set-WebDefaultLanguage)
    Write-Output "RESULT_ADMIN_URL=http://localhost:$(Get-AdminPort)"
    Write-Output "RESULT_WEB_URL=http://localhost:$(Get-WebPort)"
    Write-Output "RESULT_WEB_HOME_HTTP=$(Get-HttpCode "http://127.0.0.1:$(Get-WebPort)/")"
}

function Invoke-Check {
    Write-Output "os=Windows arch=$Arch"
    if ($InstallDir) { Write-Output "install_dir=$InstallDir install_mode=$InstallMode" } else { Write-Output "install_dir=none" }
    if ($EzHome -and (Test-Path (Join-Path $EzHome "cli.bat"))) {
        Write-Output "ezyplatform_home=$EzHome"
        Write-Output "ezyplatform_version=$(Get-PropertyValue (Join-Path $EzHome 'settings\platform.properties') 'ezyplatform.version')"
        Write-Output "admin_url=http://localhost:$(Get-AdminPort) admin_http=$(Get-HttpCode "http://127.0.0.1:$(Get-AdminPort)/")"
        Write-Output "web_url=http://localhost:$(Get-WebPort) web_http=$(Get-HttpCode "http://127.0.0.1:$(Get-WebPort)/")"
    } else {
        Write-Output "ezyplatform_home=missing"
    }
    Write-Output "dev_dir=$DevRoot"
    if (Resolve-Java) { Write-Output "jdk8=$($Dev.JavaHome)" } else { Write-Output "jdk8=missing" }
    if (Resolve-Maven) { Write-Output "maven=$($Dev.MavenHome)" } else { Write-Output "maven=missing" }
    $latest = Get-Json "$MarketUrl/api/v1/platform-sdks/latest-version"
    $latestVersion = if ($latest) { $latest.version } else { "unknown" }
    if (Resolve-Sdk) {
        Write-Output "sdk=$($Dev.SdkHome) sdk_version=$(Get-SdkVersion $Dev.SdkHome) sdk_latest=$latestVersion"
        if (Test-DevLibs) { Write-Output "dev_libs=ok parent=$(Get-RequiredParentVersion)" } else { Write-Output "dev_libs=missing parent=$(Get-RequiredParentVersion)" }
    } else {
        Write-Output "sdk=missing sdk_latest=$latestVersion"
        Write-Output "dev_libs=unknown"
    }
    $sdkSources = Join-Path $DevRoot "ezyplatform-development\ezyplatform-sdk"
    if (Test-Path $sdkSources) { Write-Output "platform_sdk_sources=$sdkSources" } else { Write-Output "platform_sdk_sources=missing" }
    $userHome = [Environment]::GetEnvironmentVariable("EZYPLATFORM_HOME", "User")
    if ($userHome) { Write-Output "user_env=EZYPLATFORM_HOME=$userHome" } else { Write-Output "user_env=missing" }
}

function Invoke-Setup {
    Assert-Home
    New-Item -ItemType Directory -Force -Path $DevRoot | Out-Null
    Install-Jdk
    Install-Maven
    Install-Sdk
    Save-DevState
    Install-DevLibs
    Save-DevState
    if (-not (Set-WebDefaultLanguage)) { Log "could not set the web default language now (MySQL stopped?), it is set again at the next restart" }
    if (-not $SkipProfile) { Set-UserEnvironment }
    Write-Output "RESULT_EZYPLATFORM_HOME=$EzHome"
    Write-Output "RESULT_JAVA_HOME=$($Dev.JavaHome)"
    Write-Output "RESULT_MAVEN_HOME=$($Dev.MavenHome)"
    Write-Output "RESULT_EZYPLATFORM_SDK=$($Dev.SdkHome)"
    Write-Output "RESULT_SDK_VERSION=$(Get-SdkVersion $Dev.SdkHome)"
    Write-Output "RESULT_PLATFORM_SDK_SOURCES=$(Join-Path $DevRoot 'ezyplatform-development\ezyplatform-sdk')"
    if ($SkipProfile) { Write-Output "RESULT_USER_ENV=unchanged" } else { Write-Output "RESULT_USER_ENV=updated (open a new terminal to use it)" }
}

function Invoke-Run {
    if ($Rest.Count -eq 0) { Fail "usage: ezy dev run `"<command line>`"" }
    Assert-Dev
    & cmd.exe /c ($Rest -join " ")
    exit $LASTEXITCODE
}

function Assert-Project {
    if (-not (Test-Path "pom.xml")) { Fail "run this command from the project root (the folder with pom.xml and export.bat)" }
    if (-not (Get-ChildItem -Path . -Directory | Where-Object { Test-Path (Join-Path $_.FullName "module.properties") })) {
        Fail "no module.properties found: this is not an EzyPlatform project root"
    }
}

function Get-ProjectModules {
    Get-ChildItem -Path . -Directory | Where-Object { Test-Path (Join-Path $_.FullName "module.properties") } | ForEach-Object {
        [pscustomobject]@{ Dir = $_.FullName; Type = Get-PropertyValue (Join-Path $_.FullName "module.properties") "type" }
    }
}

function Test-PluginHasTarget([string] $Plugin, [string] $Type) {
    $types = Get-InstalledTypes $Plugin
    switch ($Type) {
        "admin-plugin" { return $types -contains "admin-plugin" }
        { $_ -in @("web-plugin", "theme") } { return ($types -contains "web-plugin") -or ($types -contains "theme") }
        { $_ -in @("socket-plugin", "socket-app") } { return ($types -contains "socket-plugin") -or ($types -contains "socket-app") }
    }
    return $false
}

function Add-ModuleDependency([string] $File, [string] $Plugin) {
    $lines = @(Get-Content $File)
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].StartsWith("dependencies=")) {
            $found = $true
            $current = @($lines[$i].Substring(13).Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
            if ($current -contains $Plugin) { return }
            $lines[$i] = "dependencies=" + (($current + $Plugin) -join ",")
        }
    }
    if (-not $found) { $lines += "dependencies=$Plugin" }
    Write-TextFile $File (($lines -join "`n") + "`n")
    Log "added $Plugin to $File dependencies"
}

$script:InstalledPlugins = @()

function Install-OnePlugin([string] $Name) {
    if ((Get-InstalledTypes $Name).Count -gt 0) {
        Log "$Name is already installed ($((Get-InstalledTypes $Name) -join ','))"
        return
    }
    $code = Get-HttpCode "$MarketUrl/api/v1/released-projects/$Name"
    if ($code -ne "200") { Fail "$Name is not on the market ($MarketUrl, HTTP $code); check the name with: market search" }
    Log "installing $Name from the market"
    $output = Invoke-Cli "install $Name -v"
    if ((Get-InstalledTypes $Name).Count -eq 0) {
        Write-Host $output
        if ($output -match 'paidProject|403|[Ff]orbidden') {
            Need "paid_plugin" "$Name is a paid project: the user must buy it on $MarketUrl/market and connect the market account in the EzyPlatform admin (Market / Modules), or choose a free plugin"
        }
        Fail "installing $Name failed"
    }
    Log "$Name installed ($((Get-InstalledTypes $Name) -join ','))"
}

function Install-Plugins([string[]] $Names) {
    $queue = New-Object System.Collections.Generic.Queue[string]
    foreach ($name in $Names) { $queue.Enqueue($name) }
    $done = @{}
    $installed = @()
    while ($queue.Count -gt 0) {
        $name = $queue.Dequeue()
        if ($done.ContainsKey($name)) { continue }
        Install-OnePlugin $name
        $done[$name] = $true
        $installed += $name
        foreach ($dep in (Get-ModuleDependencies $name)) {
            if (-not $done.ContainsKey($dep)) { $queue.Enqueue($dep) }
        }
    }
    foreach ($name in $installed) { Enable-Project $name ([bool]$ActivateTheme) }
    $script:InstalledPlugins = $installed
}

function Invoke-InstallPlugin {
    if ($Rest.Count -eq 0) { Fail "usage: install-plugin <name...>" }
    Assert-Home
    Assert-Java
    Install-Plugins $Rest
    Write-Output "RESULT_INSTALLED=$($script:InstalledPlugins -join ' ')"
    if ($NoRestart) { Write-Output "RESULT_RESTART_NEEDED=true" } else { Invoke-Restart }
}

function Invoke-Activate {
    $name = if ($Rest.Count -gt 0) { $Rest[0] } else { "" }
    if (-not $name) { Fail "usage: activate <name>" }
    Assert-Home
    Assert-Java
    if ((Get-InstalledTypes $name).Count -eq 0) { Fail "$name is not installed in $EzHome" }
    Enable-Project $name $true
    Write-Output "RESULT_ACTIVATED=$name ($((Get-InstalledTypes $name) -join ','))"
}

function Invoke-Ezy([string] $Arguments) {
    & cmd.exe /c "ezy.bat $Arguments" 2>&1 | Out-Host
    return $LASTEXITCODE
}

function Invoke-Link {
    if ($Rest.Count -eq 0) { Fail "usage: link <plugin...> [-Types admin-plugin,web-plugin,theme]" }
    Assert-Project
    Assert-Dev
    Install-Plugins $Rest
    foreach ($plugin in $Rest) {
        $arguments = "link $plugin"
        if ($Types) { $arguments += " -m $Types" }
        Log "ezy.bat $arguments"
        if ((Invoke-Ezy $arguments) -ne 0) { Fail "ezy.bat $arguments failed" }
        foreach ($module in (Get-ProjectModules)) {
            if (-not $module.Type) { continue }
            if ($Types -and $Types -ne "all" -and ($Types.Split(",") -notcontains $module.Type)) { continue }
            if (-not (Test-PluginHasTarget $plugin $module.Type)) { continue }
            Add-ModuleDependency (Join-Path $module.Dir "module.properties") $plugin
        }
    }
    if ((Invoke-Ezy "sdv") -ne 0) { Fail "ezy.bat sdv failed" }
    Write-Output "RESULT_LINKED=$($Rest -join ' ')"
    Write-Output "RESULT_INSTALLED=$($script:InstalledPlugins -join ' ')"
    Write-Output "RESULT_RESTART_NEEDED=true"
}

function Invoke-SyncVersions {
    Assert-Project
    Assert-Dev
    if ((Invoke-Ezy "sdv") -ne 0) { Fail "ezy.bat sdv failed" }
}

function Invoke-Create {
    $name = if ($Rest.Count -gt 0) { $Rest[0] } else { "" }
    if (-not $name) { Fail "usage: create <name> [-Group com.mycompany] [-Modules theme,web-plugin,admin-plugin] [-Out <folder>]" }
    if ($name -cnotmatch '^[a-z][a-z0-9-]{1,59}$') { Fail "project name must be lowercase letters, digits and '-', 2-60 characters, starting with a letter (for example: my-shop)" }
    $groupName = if ($Group) { $Group } else { "com.mycompany" }
    if ($groupName -cnotmatch '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$') { Fail "group must look like com.mycompany" }
    $outDir = if ($Out) { [System.IO.Path]::GetFullPath($Out) } else { (Get-Location).Path }
    if ($outDir -match '\s') { Fail "the project folder must not contain spaces: $outDir" }
    if (Test-Path (Join-Path $outDir $name)) { Fail "$outDir\$name already exists, choose another name or folder" }
    Assert-Dev
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $arguments = "create $name -g $groupName -o `"$outDir`""
    if ($Package) { $arguments += " -p $Package" }
    if ($Modules) { $arguments += " -i $Modules" }
    Log "ezy.bat $arguments"
    & cmd.exe /c "ezy.bat $arguments < NUL" 2>&1 | Out-Host
    $project = Join-Path $outDir $name
    if (-not (Test-Path (Join-Path $project "pom.xml"))) { Fail "project was not created" }
    Write-Output "RESULT_PROJECT_DIR=$project"
    Push-Location $project
    try { Write-Output "RESULT_MODULES=$((Get-ProjectModules | ForEach-Object { $_.Type }) -join ',')" } finally { Pop-Location }
}

function Invoke-Export {
    Assert-Project
    Assert-Dev
    $exportFile = if (Test-Path "export.bat") { "export.bat" } else { Fail "export.bat not found in $((Get-Location).Path)" }
    $logs = Join-Path $DevRoot "logs"
    New-Item -ItemType Directory -Force -Path $logs | Out-Null
    $projectDir = (Get-Location).Path
    $logFile = Join-Path $logs "export-$(Split-Path -Leaf $projectDir).log"
    Set-Content -Path $logFile -Value "" -Encoding UTF8
    Log "building and exporting $(Split-Path -Leaf $projectDir) (log: $logFile)"
    $steps = Get-Content $exportFile | ForEach-Object { ($_ -replace '\s*&\s*\^\s*$', '').Trim() } | Where-Object { $_ -and -not $_.StartsWith("rem ") -and -not $_.StartsWith("@") }
    foreach ($step in $steps) {
        $step = $step.Replace('\!', '!')
        if ($step -match '^ezy\.bat\s+export') {
            Log "stopping admin and web so Windows can replace their files"
            Stop-Target "web"
            Stop-Target "admin"
        }
        $code = Invoke-Logged $step $projectDir $logFile
        if ($code -ne 0) {
            Get-Content $logFile | Select-String -Pattern '\[ERROR\]|Exception|error:' | Select-Object -First 60 | ForEach-Object { $_.Line } | Out-Host
            Get-Content $logFile -Tail 40 | Out-Host
            Fail "build/export failed at '$step', full log: $logFile"
        }
    }
    $names = @(Select-String -Path $logFile -Pattern 'export successfully (\S+) to ' | ForEach-Object { $_.Matches[0].Groups[1].Value } | Sort-Object -Unique)
    if ($names.Count -eq 0) { Fail "export finished but nothing was exported, see $logFile" }
    foreach ($name in $names) { Enable-Project $name $true }
    Write-Output "RESULT_EXPORTED=$($names -join ' ')"
    if ($NoRestart) { Write-Output "RESULT_RESTART_NEEDED=true" } else { Invoke-Restart }
}

function Invoke-Status {
    Assert-Home
    [void](Resolve-Java)
    foreach ($target in @("admin", "web")) {
        if (Get-TargetProcess $target) { Write-Output "$target=running" } else { Write-Output "$target=stopped" }
    }
    Write-Output "admin_url=http://localhost:$(Get-AdminPort) admin_http=$(Get-HttpCode "http://127.0.0.1:$(Get-AdminPort)/")"
    Write-Output "web_url=http://localhost:$(Get-WebPort) web_http=$(Get-HttpCode "http://127.0.0.1:$(Get-WebPort)/")"
    foreach ($type in $ModuleTypes) {
        Write-Output "active_$($type.Replace('-', '_'))=$((Get-ActiveNames $type) -join ',')"
    }
}

function Remove-Html([string] $Html) {
    $text = [regex]::Replace($Html, '<[^>]+>', ' ')
    $text = [System.Net.WebUtility]::HtmlDecode($text)
    return ([regex]::Replace($text, '\s+', ' ')).Trim()
}

function Invoke-Market {
    $sub = if ($Rest.Count -gt 0) { $Rest[0] } else { "" }
    switch ($sub) {
        "search" {
            $keyword = if ($Rest.Count -gt 1) { $Rest[1] } else { "" }
            $url = "$MarketUrl/api/v1/market/items?limit=$Limit&keyword=$([uri]::EscapeDataString($keyword))&category=$([uri]::EscapeDataString($Category))"
            $data = Get-Json $url
            if (-not $data) { Fail "cannot reach $url" }
            Write-Output "total=$($data.total)"
            foreach ($item in $data.items) {
                $price = if ($item.price) { "`$$($item.price)" } else { "free" }
                Write-Output ("{0} | {1} | {2} | {3} | {4} | {5} | {6}" -f $item.name, $item.displayName, $item.category.name, $price, ($item.includeModuleTypes -join ","), $item.latestVersion.name, ([string]$item.shortDescription).Trim())
            }
        }
        "info" {
            $name = if ($Rest.Count -gt 1) { $Rest[1] } else { Fail "usage: market info <name>" }
            $item = Get-Json "$MarketUrl/api/v1/released-projects/$name"
            if (-not $item) { Fail "$name is not on the market" }
            $price = if ($item.price) { "`$$($item.price)" } else { "free" }
            $description = Remove-Html ([string]$item.description)
            if ($description.Length -gt 4000) { $description = $description.Substring(0, 4000) }
            Write-Output "name=$($item.name)"
            Write-Output "display_name=$($item.displayName)"
            Write-Output "package=$($item.packageName)"
            Write-Output "price=$price"
            Write-Output "modules=$($item.includeModuleTypes -join ',')"
            Write-Output "latest_version=$($item.latestVersion.name) java=$($item.latestVersion.javaVersion)"
            Write-Output "category=$($item.category.name)"
            Write-Output "short_description=$(([string]$item.shortDescription).Trim())"
            Write-Output "description=$description"
            if ($EzHome -and (Test-Path (Join-Path $EzHome "cli.bat"))) { Write-Output "installed_types=$((Get-InstalledTypes $name) -join ',')" }
        }
        "docs" {
            $name = if ($Rest.Count -gt 1) { $Rest[1] } else { Fail "usage: market docs <name>" }
            $data = Get-Json "$MarketUrl/api/v1/projects/$name/docs?limit=100&lang=$Lang"
            if (-not $data) { Fail "cannot read the docs of $name" }
            foreach ($item in $data.items) { Write-Output "$($item.slug) | $($item.title)" }
        }
        "doc" {
            if ($Rest.Count -lt 3) { Fail "usage: market doc <name> <slug>" }
            $data = Get-Json "$MarketUrl/api/v1/projects/$($Rest[1])/docs/$($Rest[2])/markdown?lang=$Lang"
            if (-not $data) { Fail "doc $($Rest[2]) of $($Rest[1]) not found" }
            Write-Output "# $($data.title)"
            Write-Output ""
            Write-Output $data.content
        }
        default { Fail "usage: market search|info|docs|doc ..." }
    }
}

function Invoke-Tables {
    Assert-Home
    $target = if ($Rest.Count -gt 0) { $Rest[0] } else { "core" }
    $dir = if ($target -eq "core") { Join-Path $EzHome "admin\resources\scripts" } else { Join-Path $EzHome "admin\plugins\$target\resources\scripts" }
    if (-not (Test-Path $dir)) { Fail "no SQL scripts in $dir (is $target installed? its admin plugin owns the tables)" }
    Write-Output "scripts_dir=$dir"
    $rows = foreach ($file in Get-ChildItem -Path $dir -Filter *.sql) {
        foreach ($match in [regex]::Matches((Get-Content $file.FullName -Raw), '(?i)create\s+table\s+(if\s+not\s+exists\s+)?`?([a-z0-9_]+)`?')) {
            "$($match.Groups[2].Value) | $($file.Name)"
        }
    }
    $rows | Sort-Object -Unique | Write-Output
}

function Get-ProjectJars {
    $roots = @("lib", "admin", "web", "socket") | ForEach-Object { Join-Path $EzHome $_ } | Where-Object { Test-Path $_ }
    Get-ChildItem -Path $roots -Recurse -Filter *.jar -ErrorAction SilentlyContinue | Where-Object {
        $_.Directory.Name -eq "lib" -and (
            $_.Name.StartsWith("ezyplatform-") -or $_.Name.StartsWith("$($_.Directory.Parent.Name)-")
        )
    }
}

function Get-ClassIndex {
    $index = Join-Path $DevRoot "class-index.txt"
    New-Item -ItemType Directory -Force -Path $DevRoot | Out-Null
    $jars = @(Get-ProjectJars)
    if ((Test-Path $index) -and -not ($jars | Where-Object { $_.LastWriteTime -gt (Get-Item $index).LastWriteTime })) { return $index }
    Log "indexing classes of the installed platform and plugins"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $lines = New-Object System.Collections.Generic.List[string]
    foreach ($jar in $jars) {
        try {
            $zip = [System.IO.Compression.ZipFile]::OpenRead($jar.FullName)
            try {
                foreach ($entry in $zip.Entries) {
                    if ($entry.FullName.EndsWith(".class") -and -not $entry.FullName.Contains('$')) { $lines.Add("$($jar.FullName)!$($entry.FullName)") }
                }
            } finally { $zip.Dispose() }
        } catch { }
    }
    [System.IO.File]::WriteAllLines($index, $lines, $Utf8NoBom)
    return $index
}

function Find-ClassInJars([string] $Name) {
    $path = $Name.Replace(".", "/")
    $pattern = "!(.*/)?" + [regex]::Escape($path) + "\.class$"
    return @(Get-Content (Get-ClassIndex) | Where-Object { $_ -match $pattern })
}

function Invoke-FindClass {
    $name = if ($Rest.Count -gt 0) { $Rest[0] } else { Fail "usage: find-class <SimpleName|full.class.Name>" }
    Assert-Home
    $hits = @(Find-ClassInJars $name)
    if ($hits.Count -eq 0) { Fail "class $name not found in the installed platform and plugins" }
    $hits | Write-Output
}

function Get-Cfr {
    $jar = Join-Path $DevRoot "tools\cfr-$CfrVersion.jar"
    if (Test-Path $jar) { return $jar }
    New-Item -ItemType Directory -Force -Path (Split-Path $jar -Parent) | Out-Null
    $url = "https://repo1.maven.org/maven2/org/benf/cfr/$CfrVersion/cfr-$CfrVersion.jar"
    $download = "$jar.download"
    if (-not (Invoke-Download $url $download)) { Fail "cannot download CFR" }
    $expected = ((Get-Text "$url.sha1") -split '\s+')[0]
    if (-not $expected -or (Get-FileHashHex SHA1 $download) -ne $expected.ToLower()) {
        Remove-Item -Force $download
        Fail "CFR checksum mismatch"
    }
    Move-Item -Force $download $jar
    return $jar
}

function Invoke-Decompile {
    $target = if ($Rest.Count -gt 0) { $Rest[0] } else { Fail "usage: decompile <SimpleName|full.class.Name|path\to.jar>" }
    Assert-Home
    Assert-Java
    $classFile = ""
    if (Test-Path $target -PathType Leaf) {
        $jar = [System.IO.Path]::GetFullPath($target)
    } else {
        $hits = @(Find-ClassInJars $target)
        if ($hits.Count -eq 0) { Fail "class $target not found in the installed platform and plugins" }
        if ($hits.Count -gt 1) { $hits | Write-Output; Fail "several classes match $target, pass the full class name" }
        $jar = $hits[0].Substring(0, $hits[0].IndexOf("!"))
        $classFile = $hits[0].Substring($hits[0].IndexOf("!") + 1) -replace '\.class$', '.java'
    }
    $cfr = Get-Cfr
    $outDir = Join-Path $DevRoot ("decompiled\" + [System.IO.Path]::GetFileNameWithoutExtension($jar))
    if (-not (Test-Path $outDir) -or (Get-Item $jar).LastWriteTime -gt (Get-Item $outDir).LastWriteTime) {
        if (Test-Path $outDir) { Remove-Item -Recurse -Force $outDir }
        New-Item -ItemType Directory -Force -Path $outDir | Out-Null
        Log "decompiling $(Split-Path -Leaf $jar) into $outDir"
        & (Join-Path $Dev.JavaHome "bin\java.exe") -jar $cfr $jar --outputdir $outDir --silent true *> $null
        if ($LASTEXITCODE -ne 0) { Fail "CFR failed on $jar" }
    }
    Write-Output "RESULT_JAR=$jar"
    Write-Output "RESULT_SOURCES=$outDir"
    if ($classFile) { Write-Output "RESULT_FILE=$(Join-Path $outDir $classFile.Replace('/', '\'))" }
}

switch ($Command) {
    "check" { Invoke-Check }
    "setup" { Invoke-Setup }
    "run" { Invoke-Run }
    "create" { Invoke-Create }
    "link" { Invoke-Link }
    "sync-versions" { Invoke-SyncVersions }
    "sdv" { Invoke-SyncVersions }
    "export" { Invoke-Export }
    "market" { Invoke-Market }
    "install-plugin" { Invoke-InstallPlugin }
    "activate" { Invoke-Activate }
    "restart" { Invoke-Restart }
    "status" { Invoke-Status }
    "tables" { Invoke-Tables }
    "find-class" { Invoke-FindClass }
    "decompile" { Invoke-Decompile }
    default { Show-Usage }
}
