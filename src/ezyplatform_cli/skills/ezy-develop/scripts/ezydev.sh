#!/usr/bin/env bash
set -eo pipefail

MARKET_URL="${EZY_MARKET_URL:-https://ezyplatform.com}"
INSTALL_SKILL_URL="$MARKET_URL/api/v1/skill-library/skills/1627/download"
DEV_REPO_ZIP="https://github.com/youngmonkeys/ezyplatform-development/archive/refs/heads/master.zip"
MAVEN_REPO_URL="https://repo.maven.apache.org/maven2"
MAVEN_SERIES="3.9"
CFR_VERSION="0.152"
MODULE_TYPES="admin-plugin web-plugin theme socket-plugin socket-app"

usage() {
    cat <<'EOF'
usage: ezy dev <command> [arguments] [options]

environment
  check                         show EzyPlatform, JDK 8, Maven, SDK and dev libraries state (changes nothing)
  setup                         install what is missing: JDK 8, Maven, EzyPlatform SDK, ezyplatform-parent + sdk libraries,
                                and the environment variables (EZYPLATFORM_HOME, EZYPLATFORM_SDK, PATH)
  env                           print the shell exports used by every command
  run <command...>              run a command with JDK 8, Maven, ezy.sh and EZYPLATFORM_HOME set (for example: run ./export.sh)

project
  create <name>                 create a project with the SDK (options: --group, --package, --modules, --out)
  link <plugin...>              install the plugins if needed, ezy.sh link them, add them to module.properties
                                dependencies and sync their versions (option: -m admin-plugin,web-plugin,theme)
  sync-versions                 ezy.sh sdv: sync <plugin>.version properties with the installed plugins
  export                        build (./export.sh), export to EzyPlatform, activate the project modules, restart

marketplace
  market search [keyword]       search plugins and themes (options: --category, --limit)
  market info <name>            details of one project (price, modules, latest version, description)
  market docs <name>            list the docs of a project (option: --lang)
  market doc <name> <slug>      print one doc as markdown (option: --lang)

local EzyPlatform
  install-plugin <name...>      install plugins from the market with their dependencies, activate them, restart
                                (options: --activate-theme, --no-restart)
  activate <name>               activate every installed module of a project (theme: deactivate the other themes)
  restart                       restart admin and web (starts MySQL first when installed by ezyplatform-install)
  status                        admin and web state, URLs, active modules
  tables [plugin|core]          list the tables a plugin (or the platform core) creates, with their SQL file
  find-class <name>             find which installed jar contains a class (simple or full name)
  decompile <class|jar>         decompile a class or a jar of the installed platform/plugins with CFR

options
  --dir <folder>                folder of an install made by ezyplatform-install (default: $EZY_DIR or ~/ezyplatform)
  --home <folder>               EzyPlatform home when it was not installed by ezyplatform-install
  --dev-dir <folder>            where dev tools go (default: <dir>/dev, or ~/ezyplatform-dev)
  --no-profile                  setup: do not add the environment variables to the shell profile

exit codes: 0 ok, 1 error, 3 a requirement is missing (see the NEED line)
EOF
}

log() { printf '[ezydev] %s\n' "$*" >&2; }
die() { printf '[ezydev] ERROR: %s\n' "$*" >&2; exit 1; }
need() { printf 'NEED %s: %s\n' "$1" "$2"; exit 3; }

COMMAND="${1:-help}"
[ $# -gt 0 ] && shift

OPT_DIR=""; OPT_HOME=""; OPT_DEV_DIR=""; OPT_NO_PROFILE=""; OPT_GROUP=""; OPT_PACKAGE=""
OPT_MODULES=""; OPT_OUT=""; OPT_CATEGORY=""; OPT_LIMIT="20"; OPT_LANG=""; OPT_LINK_TYPES=""
OPT_ACTIVATE_THEME=""; OPT_NO_RESTART=""
ARGS=()
if [ "$COMMAND" = "run" ]; then
    while [ $# -gt 0 ]; do
        case "$1" in
            --dir) OPT_DIR="$2"; shift 2 ;;
            --home) OPT_HOME="$2"; shift 2 ;;
            --dev-dir) OPT_DEV_DIR="$2"; shift 2 ;;
            --) shift; break ;;
            *) break ;;
        esac
    done
    ARGS=("$@")
else
    while [ $# -gt 0 ]; do
        case "$1" in
            --dir) OPT_DIR="$2"; shift 2 ;;
            --home) OPT_HOME="$2"; shift 2 ;;
            --dev-dir) OPT_DEV_DIR="$2"; shift 2 ;;
            --no-profile) OPT_NO_PROFILE="true"; shift ;;
            --group|-g) OPT_GROUP="$2"; shift 2 ;;
            --package|-p) OPT_PACKAGE="$2"; shift 2 ;;
            --modules|-i) OPT_MODULES="$2"; shift 2 ;;
            --out|-o) OPT_OUT="$2"; shift 2 ;;
            --category) OPT_CATEGORY="$2"; shift 2 ;;
            --limit) OPT_LIMIT="$2"; shift 2 ;;
            --lang) OPT_LANG="$2"; shift 2 ;;
            -m) OPT_LINK_TYPES="$2"; shift 2 ;;
            --activate-theme) OPT_ACTIVATE_THEME="true"; shift ;;
            --no-restart) OPT_NO_RESTART="true"; shift ;;
            -h|--help) usage; exit 0 ;;
            --*) die "unknown option: $1" ;;
            *) ARGS+=("$1"); shift ;;
        esac
    done
fi

abs_path() {
    case "$1" in
        /*) printf '%s' "$1" ;;
        *) printf '%s/%s' "$(pwd)" "$1" ;;
    esac
}

OS_NAME="$(uname -s)"
case "$(uname -m)" in
    x86_64|amd64) ARCH="x64" ;;
    arm64|aarch64) ARCH="aarch64" ;;
    *) ARCH="$(uname -m)" ;;
esac

INSTALL_DIR=""
INSTALL_MODE=""
JAVA_HOME_DIR=""
CANDIDATE_DIR="$(abs_path "${OPT_DIR:-${EZY_DIR:-$HOME/ezyplatform}}")"
if [ -f "$CANDIDATE_DIR/.ezy/state.env" ]; then
    INSTALL_MODE="$(sed -n 's/^MODE=//p' "$CANDIDATE_DIR/.ezy/state.env" | head -1)"
    INSTALL_DIR="$CANDIDATE_DIR"
    JAVA_HOME_DIR="$(sed -n 's/^JAVA_HOME_DIR=//p' "$CANDIDATE_DIR/.ezy/state.env" | head -1)"
    JAVA_HOME_DIR="${JAVA_HOME_DIR#\'}"; JAVA_HOME_DIR="${JAVA_HOME_DIR%\'}"
fi

EZ_HOME=""
if [ -n "$OPT_HOME" ]; then
    EZ_HOME="$(abs_path "$OPT_HOME")"
elif [ -n "$OPT_DIR" ] && [ "$INSTALL_MODE" = "native" ]; then
    EZ_HOME="$INSTALL_DIR/ezyplatform"
elif [ -n "${EZYPLATFORM_HOME:-}" ] && [ -f "$EZYPLATFORM_HOME/cli.sh" ]; then
    EZ_HOME="$EZYPLATFORM_HOME"
elif [ "$INSTALL_MODE" = "native" ]; then
    EZ_HOME="$INSTALL_DIR/ezyplatform"
fi
EZ_HOME="${EZ_HOME%/}"

if [ -n "$OPT_DEV_DIR" ]; then
    DEV_DIR="$(abs_path "$OPT_DEV_DIR")"
elif [ -n "$INSTALL_DIR" ] && [ "$INSTALL_MODE" = "native" ] && [ "$EZ_HOME" = "$INSTALL_DIR/ezyplatform" ]; then
    DEV_DIR="$INSTALL_DIR/dev"
else
    DEV_DIR="$HOME/ezyplatform-dev"
fi
DEV_STATE="$DEV_DIR/dev.env"
CTL=""
if [ -n "$INSTALL_DIR" ] && [ "$EZ_HOME" = "$INSTALL_DIR/ezyplatform" ] && [ -f "$INSTALL_DIR/ezyplatform-ctl.sh" ]; then
    CTL="$INSTALL_DIR/ezyplatform-ctl.sh"
fi

MAVEN_HOME_DIR=""; SDK_HOME=""
if [ -f "$DEV_STATE" ]; then
    . "$DEV_STATE"
fi

download() {
    local url="$1" out="$2"
    log "downloading $url"
    command -v curl >/dev/null 2>&1 || need curl "install curl"
    curl -fsSL --retry 3 --retry-delay 3 --connect-timeout 30 -o "$out.part" "$url" || return 1
    mv "$out.part" "$out"
}

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

sha_of() {
    local algo="$1" file="$2"
    if command -v "sha${algo}sum" >/dev/null 2>&1; then "sha${algo}sum" "$file" | cut -d' ' -f1; else shasum -a "$algo" "$file" | cut -d' ' -f1; fi
}

http_get() {
    curl -fsSL --retry 2 --connect-timeout 20 "$1"
}

http_code() {
    curl -s -o /dev/null -m 10 -w '%{http_code}' "$1" 2>/dev/null || true
}

has_python() {
    command -v python3 >/dev/null 2>&1
}

save_dev_state() {
    mkdir -p "$DEV_DIR"
    {
        printf 'JAVA_HOME_DIR=%q\n' "$JAVA_HOME_DIR"
        printf 'MAVEN_HOME_DIR=%q\n' "$MAVEN_HOME_DIR"
        printf 'SDK_HOME=%q\n' "$SDK_HOME"
    } > "$DEV_STATE"
}

java_is_8() {
    [ -x "$1/bin/java" ] && "$1/bin/java" -version 2>&1 | grep -q '"1\.8' && [ -x "$1/bin/javac" ]
}

resolve_java() {
    if [ -n "$JAVA_HOME_DIR" ] && java_is_8 "$JAVA_HOME_DIR"; then
        return 0
    fi
    local candidate
    for candidate in "$INSTALL_DIR/jdk" "$DEV_DIR/jdk"; do
        [ -n "$candidate" ] && [ -d "$candidate" ] || continue
        candidate="$(find "$candidate" -path '*/bin/javac' -type f 2>/dev/null | head -1)"
        if [ -n "$candidate" ] && java_is_8 "$(dirname "$(dirname "$candidate")")"; then
            JAVA_HOME_DIR="$(dirname "$(dirname "$candidate")")"
            return 0
        fi
    done
    if [ -n "${JAVA_HOME:-}" ] && java_is_8 "$JAVA_HOME"; then
        JAVA_HOME_DIR="$JAVA_HOME"
        return 0
    fi
    if [ "$OS_NAME" = "Darwin" ] && [ -x /usr/libexec/java_home ]; then
        candidate="$(/usr/libexec/java_home -v 1.8 2>/dev/null || true)"
        if [ -n "$candidate" ] && java_is_8 "$candidate"; then
            JAVA_HOME_DIR="$candidate"
            return 0
        fi
    fi
    JAVA_HOME_DIR=""
    return 1
}

install_jdk() {
    resolve_java && return 0
    local os_param
    case "$OS_NAME" in
        Darwin) os_param="macos" ;;
        Linux) if ldd --version 2>&1 | grep -qi musl; then os_param="linux_musl"; else os_param="linux"; fi ;;
        *) die "unsupported OS $OS_NAME" ;;
    esac
    local api="https://api.azul.com/metadata/v1/zulu/packages/?java_version=8&os=$os_param&arch=$ARCH&archive_type=tar.gz&java_package_type=jdk&javafx_bundled=false&crac_supported=false&latest=true&release_status=ga&availability_types=CA&certifications=tck&page=1&page_size=1"
    local json url uuid sha tmp="$DEV_DIR/tmp/jdk"
    json="$(http_get "$api")" || die "cannot reach api.azul.com to find JDK 8"
    url="$(printf '%s' "$json" | grep -oE '"download_url":"[^"]+"' | head -1 | cut -d'"' -f4)"
    uuid="$(printf '%s' "$json" | grep -oE '"package_uuid":"[^"]+"' | head -1 | cut -d'"' -f4)"
    [ -n "$url" ] || die "no JDK 8 build for $os_param/$ARCH"
    sha="$(http_get "https://api.azul.com/metadata/v1/zulu/packages/$uuid" | grep -oE '"sha256_hash":"[^"]+"' | head -1 | cut -d'"' -f4 || true)"
    rm -rf "$tmp"; mkdir -p "$tmp"
    download "$url" "$tmp/jdk.tar.gz" || die "JDK download failed"
    if [ -n "$sha" ] && [ "$(sha256_of "$tmp/jdk.tar.gz")" != "$sha" ]; then
        die "JDK checksum mismatch, run setup again"
    fi
    tar -xzf "$tmp/jdk.tar.gz" -C "$tmp"
    rm -f "$tmp/jdk.tar.gz"
    rm -rf "$DEV_DIR/jdk"
    mv "$(find "$tmp" -mindepth 1 -maxdepth 1 -type d | head -1)" "$DEV_DIR/jdk"
    rm -rf "$tmp"
    JAVA_HOME_DIR=""
    resolve_java || die "the downloaded JDK is not a Java 8 JDK"
    log "JDK 8 installed at $JAVA_HOME_DIR"
}

resolve_maven() {
    if [ -n "$MAVEN_HOME_DIR" ] && [ -x "$MAVEN_HOME_DIR/bin/mvn" ]; then
        return 0
    fi
    if [ -x "$DEV_DIR/maven/bin/mvn" ]; then
        MAVEN_HOME_DIR="$DEV_DIR/maven"
        return 0
    fi
    local mvn_path
    mvn_path="$(command -v mvn 2>/dev/null || true)"
    if [ -n "$mvn_path" ]; then
        mvn_path="$(cd "$(dirname "$mvn_path")" && pwd -P)/$(basename "$mvn_path")"
        if [ -L "$mvn_path" ]; then
            mvn_path="$(readlink "$mvn_path")"
        fi
        local home
        home="$(cd "$(dirname "$mvn_path")/.." 2>/dev/null && pwd -P || true)"
        if [ -n "$home" ] && [ -x "$home/bin/mvn" ]; then
            MAVEN_HOME_DIR="$home"
            return 0
        fi
    fi
    MAVEN_HOME_DIR=""
    return 1
}

install_maven() {
    resolve_maven && return 0
    local version tmp="$DEV_DIR/tmp/maven" base expected
    version="$(http_get "$MAVEN_REPO_URL/org/apache/maven/apache-maven/maven-metadata.xml" \
        | grep -oE "<version>${MAVEN_SERIES//./\\.}\.[0-9]+</version>" | sed 's/<[^>]*>//g' | sort -t. -k3 -n | tail -1)"
    [ -n "$version" ] || die "cannot find the latest Maven $MAVEN_SERIES"
    base="$MAVEN_REPO_URL/org/apache/maven/apache-maven/$version/apache-maven-$version-bin.tar.gz"
    rm -rf "$tmp"; mkdir -p "$tmp"
    download "$base" "$tmp/maven.tar.gz" || die "Maven download failed"
    expected="$(http_get "$base.sha512" | cut -d' ' -f1)"
    [ -n "$expected" ] && [ "$(sha_of 512 "$tmp/maven.tar.gz")" = "$expected" ] || die "Maven checksum mismatch, run setup again"
    tar -xzf "$tmp/maven.tar.gz" -C "$tmp"
    rm -rf "$DEV_DIR/maven"
    mv "$tmp/apache-maven-$version" "$DEV_DIR/maven"
    rm -rf "$tmp"
    MAVEN_HOME_DIR="$DEV_DIR/maven"
    log "Maven $version installed at $MAVEN_HOME_DIR"
}

sdk_version_of() {
    sed -n 's/^sdk\.version=//p' "$1/sdk.properties" 2>/dev/null | tr -d '\r ' | head -1
}

resolve_sdk() {
    local candidate
    for candidate in "$SDK_HOME" "${EZYPLATFORM_SDK:-}" "$DEV_DIR/ezyplatform-sdk"; do
        if [ -n "$candidate" ] && [ -f "$candidate/bin/ezy.sh" ] && [ -f "$candidate/sdk.properties" ]; then
            SDK_HOME="${candidate%/}"
            return 0
        fi
    done
    SDK_HOME=""
    return 1
}

latest_sdk_json() {
    http_get "$MARKET_URL/api/v1/platform-sdks/latest-version" 2>/dev/null || true
}

install_sdk() {
    resolve_sdk && return 0
    local json version sha tmp="$DEV_DIR/tmp/sdk"
    json="$(latest_sdk_json)"
    version="$(printf '%s' "$json" | grep -oE '"version":"[^"]+"' | head -1 | cut -d'"' -f4)"
    sha="$(printf '%s' "$json" | grep -oE '"sha256":"[^"]+"' | head -1 | cut -d'"' -f4)"
    [ -n "$version" ] || die "cannot read the latest SDK version from $MARKET_URL"
    rm -rf "$tmp"; mkdir -p "$tmp"
    download "$MARKET_URL/api/v1/platform-sdks/$version/download" "$tmp/sdk.zip" || die "SDK download failed"
    if [ -n "$sha" ] && [ "$(sha256_of "$tmp/sdk.zip")" != "$sha" ]; then
        die "SDK checksum mismatch, run setup again"
    fi
    unzip_to "$tmp/sdk.zip" "$tmp"
    [ -f "$tmp/ezyplatform-sdk/bin/ezy.sh" ] || die "unexpected SDK archive layout"
    rm -rf "$DEV_DIR/ezyplatform-sdk"
    mv "$tmp/ezyplatform-sdk" "$DEV_DIR/ezyplatform-sdk"
    chmod +x "$DEV_DIR/ezyplatform-sdk/bin/ezy.sh"
    rm -rf "$tmp"
    SDK_HOME="$DEV_DIR/ezyplatform-sdk"
    log "EzyPlatform SDK $version installed at $SDK_HOME"
}

unzip_to() {
    if command -v unzip >/dev/null 2>&1; then
        unzip -q -o "$1" -d "$2"
    elif resolve_java; then
        (cd "$2" && "$JAVA_HOME_DIR/bin/jar" xf "$1")
    else
        need unzip "install the unzip package"
    fi
}

m2_repo() {
    printf '%s' "${MAVEN_LOCAL_REPO:-$HOME/.m2/repository}"
}

required_parent_version() {
    local pom="$SDK_HOME/templates/project-template/pom.xml"
    [ -f "$pom" ] || { printf ''; return; }
    awk '/<parent>/{p=1} p&&/<version>/{gsub(/.*<version>|<\/version>.*/,""); print; exit}' "$pom" | tr -d ' \r'
}

dev_libs_ok() {
    local version repo
    version="$(required_parent_version)"
    [ -n "$version" ] || return 1
    repo="$(m2_repo)/org/youngmonkeys"
    [ -f "$repo/ezyplatform-parent/$version/ezyplatform-parent-$version.pom" ] \
        && [ -d "$repo/ezyplatform-test-sdk/$version" ] \
        && [ -d "$repo/ezyplatform-devtools" ]
}

dev_env_exports() {
    resolve_java || true
    resolve_maven || true
    resolve_sdk || true
    local path_prefix=""
    [ -n "$JAVA_HOME_DIR" ] && path_prefix="$JAVA_HOME_DIR/bin:"
    [ -n "$MAVEN_HOME_DIR" ] && path_prefix="$path_prefix$MAVEN_HOME_DIR/bin:"
    [ -n "$SDK_HOME" ] && path_prefix="$path_prefix$SDK_HOME/bin:"
    [ -n "$JAVA_HOME_DIR" ] && printf 'export JAVA_HOME=%q\n' "$JAVA_HOME_DIR"
    [ -n "$EZ_HOME" ] && printf 'export EZYPLATFORM_HOME=%q\n' "$EZ_HOME"
    [ -n "$SDK_HOME" ] && printf 'export EZYPLATFORM_SDK=%q\n' "$SDK_HOME"
    [ -n "$MAVEN_HOME_DIR" ] && printf 'export MAVEN_HOME=%q\n' "$MAVEN_HOME_DIR"
    printf 'export PATH=%q"$PATH"\n' "$path_prefix"
}

apply_env() {
    eval "$(dev_env_exports)"
}

install_dev_libs() {
    if dev_libs_ok && [ -d "$DEV_DIR/ezyplatform-development/ezyplatform-sdk" ]; then
        return 0
    fi
    apply_env
    local tmp="$DEV_DIR/tmp/dev-libs" src log_file="$DEV_DIR/logs/dev-libs-build.log"
    rm -rf "$tmp"; mkdir -p "$tmp" "$DEV_DIR/logs"
    download "$DEV_REPO_ZIP" "$tmp/dev.zip" || die "cannot download ezyplatform-development from GitHub"
    unzip_to "$tmp/dev.zip" "$tmp"
    src="$(find "$tmp" -mindepth 1 -maxdepth 1 -type d | head -1)"
    [ -d "$src/ezyplatform-parent" ] || die "unexpected ezyplatform-development archive layout"
    log "building ezyplatform-devtools, ezyplatform-parent and ezyplatform-sdk into $(m2_repo) (a few minutes the first time)"
    : > "$log_file"
    local module
    for module in ezyplatform-devtools ezyplatform-parent ezyplatform-sdk; do
        if ! (cd "$src/$module" && mvn -B clean install -Dmaven.test.skip=true -Dcheckstyle.skip=true) >> "$log_file" 2>&1; then
            tail -n 60 "$log_file" >&2
            die "building $module failed, full log: $log_file"
        fi
    done
    (cd "$src" && find . -name target -type d -prune -exec rm -rf {} +) 2>/dev/null || true
    rm -rf "$DEV_DIR/ezyplatform-development"
    mv "$src" "$DEV_DIR/ezyplatform-development"
    rm -rf "$tmp"
    dev_libs_ok || die "ezyplatform-parent $(required_parent_version) is still missing in $(m2_repo), see $log_file"
    log "EzyPlatform development libraries installed"
}

PROFILE_BEGIN="# >>> ezyplatform dev >>>"
PROFILE_END="# <<< ezyplatform dev <<<"

write_env_file() {
    local file="$DEV_DIR/ezy-dev-env.sh" set_java=""
    if ! command -v java >/dev/null 2>&1 || [ -z "${JAVA_HOME:-}" ]; then
        set_java="true"
    fi
    {
        echo "export EZYPLATFORM_HOME=$(printf '%q' "$EZ_HOME")"
        echo "export EZYPLATFORM_SDK=$(printf '%q' "$SDK_HOME")"
        if [ -n "$set_java" ]; then
            echo "export JAVA_HOME=$(printf '%q' "$JAVA_HOME_DIR")"
            echo "export PATH=$(printf '%q' "$JAVA_HOME_DIR/bin"):\"\$PATH\""
        fi
        echo "export PATH=$(printf '%q' "$SDK_HOME/bin"):$(printf '%q' "$MAVEN_HOME_DIR/bin"):\"\$PATH\""
    } > "$file"
    printf '%s' "$file"
}

add_to_profiles() {
    local env_file="$1" profile added=""
    local profiles=("$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.profile")
    if [ "$OS_NAME" = "Darwin" ] && [ ! -f "$HOME/.zshrc" ]; then
        touch "$HOME/.zshrc"
    fi
    if [ "$OS_NAME" = "Linux" ] && [ ! -f "$HOME/.bashrc" ]; then
        touch "$HOME/.bashrc"
    fi
    for profile in "${profiles[@]}"; do
        [ -f "$profile" ] || continue
        if grep -qF "$PROFILE_BEGIN" "$profile"; then
            local tmp_profile="$profile.ezydev.tmp"
            awk -v b="$PROFILE_BEGIN" -v e="$PROFILE_END" '$0==b{skip=1} !skip{print} $0==e{skip=0}' "$profile" > "$tmp_profile"
            cat "$tmp_profile" > "$profile"
            rm -f "$tmp_profile"
        fi
        {
            echo "$PROFILE_BEGIN"
            echo "[ -f $(printf '%q' "$env_file") ] && . $(printf '%q' "$env_file")"
            echo "$PROFILE_END"
        } >> "$profile"
        added="$added $profile"
    done
    printf '%s' "$added"
}

require_home() {
    if [ -z "$EZ_HOME" ] || [ ! -f "$EZ_HOME/cli.sh" ]; then
        if [ "$INSTALL_MODE" = "docker" ]; then
            need native_install "EzyPlatform at $INSTALL_DIR runs in Docker; development needs a native install: run ezyplatform-install with --dir <another folder> (without --docker), then pass --dir <that folder>"
        fi
        need ezyplatform_not_installed "EzyPlatform is not installed: run the ezyplatform-install skill ($INSTALL_SKILL_URL) first, or pass --home <EzyPlatform folder>"
    fi
}

require_java() {
    resolve_java || need jdk8 "JDK 8 not found: run setup"
}

require_dev() {
    require_home
    require_java
    resolve_maven || need dev_setup "Maven not found: run setup"
    resolve_sdk || need dev_setup "EzyPlatform SDK not found: run setup"
    apply_env
}

check_command() {
    echo "os=$OS_NAME arch=$ARCH"
    if [ -n "$INSTALL_DIR" ]; then
        echo "install_dir=$INSTALL_DIR install_mode=$INSTALL_MODE"
    else
        echo "install_dir=none"
    fi
    if [ -n "$EZ_HOME" ] && [ -f "$EZ_HOME/cli.sh" ]; then
        echo "ezyplatform_home=$EZ_HOME"
        echo "ezyplatform_version=$(sed -n 's/^ezyplatform\.version=//p' "$EZ_HOME/settings/platform.properties" 2>/dev/null | tr -d '\r' | head -1)"
        echo "admin_url=http://localhost:$(admin_port) admin_http=$(http_code "http://127.0.0.1:$(admin_port)/")"
        echo "web_url=http://localhost:$(web_port) web_http=$(http_code "http://127.0.0.1:$(web_port)/")"
    else
        echo "ezyplatform_home=missing"
    fi
    echo "dev_dir=$DEV_DIR"
    if resolve_java; then echo "jdk8=$JAVA_HOME_DIR"; else echo "jdk8=missing"; fi
    if resolve_maven; then echo "maven=$MAVEN_HOME_DIR"; else echo "maven=missing"; fi
    local latest
    latest="$(latest_sdk_json | grep -oE '"version":"[^"]+"' | head -1 | cut -d'"' -f4)"
    if resolve_sdk; then
        echo "sdk=$SDK_HOME sdk_version=$(sdk_version_of "$SDK_HOME") sdk_latest=${latest:-unknown}"
        if dev_libs_ok; then echo "dev_libs=ok parent=$(required_parent_version)"; else echo "dev_libs=missing parent=$(required_parent_version)"; fi
    else
        echo "sdk=missing sdk_latest=${latest:-unknown}"
        echo "dev_libs=unknown"
    fi
    if [ -d "$DEV_DIR/ezyplatform-development/ezyplatform-sdk" ]; then echo "platform_sdk_sources=$DEV_DIR/ezyplatform-development/ezyplatform-sdk"; else echo "platform_sdk_sources=missing"; fi
    if [ -f "$DEV_DIR/ezy-dev-env.sh" ]; then echo "env_file=$DEV_DIR/ezy-dev-env.sh"; else echo "env_file=missing"; fi
}

setup_command() {
    require_home
    mkdir -p "$DEV_DIR"
    install_jdk
    install_maven
    install_sdk
    save_dev_state
    install_dev_libs
    save_dev_state
    ensure_web_language || log "could not set the web default language now (MySQL stopped?), it is set again at the next restart"
    local env_file profiles=""
    env_file="$(write_env_file)"
    if [ -z "$OPT_NO_PROFILE" ]; then
        profiles="$(add_to_profiles "$env_file")"
    fi
    echo "RESULT_EZYPLATFORM_HOME=$EZ_HOME"
    echo "RESULT_JAVA_HOME=$JAVA_HOME_DIR"
    echo "RESULT_MAVEN_HOME=$MAVEN_HOME_DIR"
    echo "RESULT_EZYPLATFORM_SDK=$SDK_HOME"
    echo "RESULT_SDK_VERSION=$(sdk_version_of "$SDK_HOME")"
    echo "RESULT_PLATFORM_SDK_SOURCES=$DEV_DIR/ezyplatform-development/ezyplatform-sdk"
    echo "RESULT_ENV_FILE=$env_file"
    echo "RESULT_PROFILES=${profiles# }"
}

run_command() {
    [ ${#ARGS[@]} -gt 0 ] || die "usage: ezy dev run <command...>"
    require_dev
    exec "${ARGS[@]}"
}

prop_of() {
    sed -n "s/^$2=//p" "$1" 2>/dev/null | tr -d '\r' | head -1
}

admin_port() {
    local port
    port="$(prop_of "$EZ_HOME/admin/settings/config.properties" 'server\.port' | tr -d ' ')"
    printf '%s' "${port:-9090}"
}

web_port() {
    local port
    port="$(prop_of "$EZ_HOME/web/settings/config.properties" 'server\.port' | tr -d ' ')"
    printf '%s' "${port:-8080}"
}

cli() {
    (cd "$EZ_HOME" && JAVA_HOME="$JAVA_HOME_DIR" PATH="$JAVA_HOME_DIR/bin:$PATH" sh cli.sh "$1")
}

type_folder() {
    case "$1" in
        admin-plugin) echo "admin/plugins" ;;
        web-plugin) echo "web/plugins" ;;
        theme) echo "web/themes" ;;
        socket-plugin) echo "socket/plugins" ;;
        socket-app) echo "socket/apps" ;;
    esac
}

installed_types() {
    local name="$1" type out=""
    for type in $MODULE_TYPES; do
        [ -f "$EZ_HOME/$(type_folder "$type")/$name/module.properties" ] && out="$out $type"
    done
    printf '%s' "${out# }"
}

module_dependencies() {
    local name="$1" type deps=""
    for type in $MODULE_TYPES; do
        local file="$EZ_HOME/$(type_folder "$type")/$name/module.properties"
        [ -f "$file" ] || continue
        deps="$deps,$(prop_of "$file" dependencies)"
    done
    printf '%s' "$deps" | tr ',' '\n' | tr -d ' ' | grep -v '^$' | sort -u | tr '\n' ' '
}

runtime_file() {
    case "$1" in
        admin-plugin) echo "$EZ_HOME/.runtime/admin/plugins.txt" ;;
        web-plugin) echo "$EZ_HOME/.runtime/web/plugins.txt" ;;
        theme) echo "$EZ_HOME/.runtime/web/themes.txt" ;;
        socket-plugin) echo "$EZ_HOME/.runtime/socket/plugins.txt" ;;
        socket-app) echo "$EZ_HOME/.runtime/socket/apps.txt" ;;
    esac
}

active_names() {
    local file
    file="$(runtime_file "$1")"
    [ -f "$file" ] || return 0
    tr -d ' \r\n' < "$file" | grep -oE '"name":"[^"]+","active":true' | cut -d'"' -f4
}

is_active() {
    active_names "$1" | grep -qx "$2"
}

activate_project() {
    local name="$1" with_theme="$2" type out
    for type in $(installed_types "$name"); do
        if [ "$type" = "theme" ]; then
            [ "$with_theme" = "true" ] || continue
            is_active theme "$name" && continue
            local other
            for other in $(active_names theme); do
                [ "$other" = "$name" ] && continue
                cli "deactivate theme $other" >/dev/null 2>&1 || true
                log "deactivated theme $other"
            done
        fi
        is_active "$type" "$name" && continue
        out="$(cli "activate $type $name" 2>&1 || true)"
        if is_active "$type" "$name"; then
            log "activated $name ($type)"
        else
            printf '%s\n' "$out" >&2
            die "cannot activate $name ($type)"
        fi
    done
}

pid_of_target() {
    local file="$EZ_HOME/$1/.runtime/$1_server_instance.pid"
    [ -f "$file" ] && cat "$file"
}

target_running() {
    local pid
    pid="$(pid_of_target "$1" || true)"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

stop_target() {
    local target="$1" pid waited=0
    target_running "$target" || return 0
    pid="$(pid_of_target "$target")"
    log "stopping $target"
    kill -15 "$pid" 2>/dev/null || true
    while kill -0 "$pid" 2>/dev/null && [ "$waited" -lt 40 ]; do
        sleep 2
        waited=$((waited + 2))
    done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    rm -f "$EZ_HOME/$target/.runtime/${target}_server_instance.pid"
}

wait_http() {
    local url="$1" seconds="$2" name="$3" code waited=0
    while [ "$waited" -lt "$seconds" ]; do
        code="$(http_code "$url")"
        case "$code" in
            2*|3*|4*) log "$name is up (HTTP $code)"; return 0 ;;
        esac
        if ! target_running "$name" && [ "$waited" -gt 20 ]; then
            tail -n 80 "$EZ_HOME/logs/$name-server.log" >&2 2>/dev/null || true
            die "$name stopped while starting, see $EZ_HOME/logs/$name-server.log"
        fi
        sleep 3
        waited=$((waited + 3))
    done
    tail -n 80 "$EZ_HOME/logs/$name-server.log" >&2 2>/dev/null || true
    die "$name did not answer at $url after ${seconds}s"
}

ensure_web_language() {
    [ -n "$INSTALL_DIR" ] && [ "$EZ_HOME" = "$INSTALL_DIR/ezyplatform" ] || return 0
    local root_cnf="$INSTALL_DIR/.ezy/mysql-root.cnf" values mysql_home ld_path lang db_url
    [ -f "$root_cnf" ] || return 0
    values="$(. "$INSTALL_DIR/.ezy/state.env" 2>/dev/null; printf '%s\n%s\n%s\n%s' "$MYSQL_HOME" "$MYSQL_LD_PATH" "$LANG_CODE" "$DB_URL")"
    mysql_home="$(printf '%s\n' "$values" | sed -n 1p)"
    ld_path="$(printf '%s\n' "$values" | sed -n 2p)"
    lang="$(printf '%s\n' "$values" | sed -n 3p)"
    db_url="$(printf '%s\n' "$values" | sed -n 4p)"
    [ -z "$db_url" ] && [ -x "$mysql_home/bin/mysql" ] || return 0
    printf '%s' "$lang" | grep -qE '^[a-zA-Z_-]{2,10}$' || lang="en"
    local sql="INSERT INTO ezy_settings (setting_name, data_type, setting_value, created_at, updated_at) VALUES ('web_default_language', 'STRING', '$lang', NOW(), NOW()) ON DUPLICATE KEY UPDATE setting_value = IF(setting_value = '', VALUES(setting_value), setting_value);"
    if env ${ld_path:+LD_LIBRARY_PATH="$ld_path"} "$mysql_home/bin/mysql" --defaults-extra-file="$root_cnf" -D ezyplatform -e "$sql" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

restart_command() {
    require_home
    require_java
    ensure_web_language || true
    stop_target web
    stop_target admin
    if [ -n "$CTL" ]; then
        log "starting EzyPlatform (MySQL, admin, web)"
        bash "$CTL" start >&2 || die "start failed, see $INSTALL_DIR/logs and $EZ_HOME/logs"
    else
        log "starting admin"
        cli "start admin" >/dev/null 2>&1 || die "cli.sh start admin failed"
        wait_http "http://127.0.0.1:$(admin_port)/" 420 admin
        log "starting web"
        cli "start web" >/dev/null 2>&1 || die "cli.sh start web failed"
        wait_http "http://127.0.0.1:$(web_port)/" 300 web
    fi
    ensure_web_language || true
    echo "RESULT_ADMIN_URL=http://localhost:$(admin_port)"
    echo "RESULT_WEB_URL=http://localhost:$(web_port)"
    echo "RESULT_WEB_HOME_HTTP=$(http_code "http://127.0.0.1:$(web_port)/")"
}

status_command() {
    require_home
    local target
    for target in admin web; do
        if target_running "$target"; then echo "$target=running"; else echo "$target=stopped"; fi
    done
    echo "admin_url=http://localhost:$(admin_port) admin_http=$(http_code "http://127.0.0.1:$(admin_port)/")"
    echo "web_url=http://localhost:$(web_port) web_http=$(http_code "http://127.0.0.1:$(web_port)/")"
    local type
    for type in $MODULE_TYPES; do
        echo "active_${type//-/_}=$(active_names "$type" | tr '\n' ',' | sed 's/,$//')"
    done
}

market_get() {
    http_get "$MARKET_URL$1" || die "cannot reach $MARKET_URL$1"
}

urlencode() {
    local s="$1" out="" c i
    for ((i = 0; i < ${#s}; i++)); do
        c="${s:i:1}"
        case "$c" in
            [a-zA-Z0-9.~_-]) out="$out$c" ;;
            *) out="$out$(printf '%%%02X' "'$c")" ;;
        esac
    done
    printf '%s' "$out"
}

market_command() {
    local sub="${ARGS[0]:-}"
    case "$sub" in
        search)
            local keyword="${ARGS[1]:-}" json
            json="$(market_get "/api/v1/market/items?limit=$OPT_LIMIT&keyword=$(urlencode "$keyword")&category=$(urlencode "$OPT_CATEGORY")")"
            if has_python; then
                printf '%s' "$json" | python3 -I -c '
import json, sys
d = json.load(sys.stdin)
print("total=%s" % d.get("total"))
for i in d.get("items", []):
    v = (i.get("latestVersion") or {}).get("name", "")
    c = (i.get("category") or {}).get("name", "")
    price = i.get("price") or 0
    print("%s | %s | %s | %s | %s | %s | %s" % (i.get("name"), i.get("displayName"), c, "free" if not price else "$%s" % price, ",".join(i.get("includeModuleTypes") or []), v, (i.get("shortDescription") or "").strip()))
'
            else
                printf '%s\n' "$json"
            fi
            ;;
        info)
            local name="${ARGS[1]:-}" json
            [ -n "$name" ] || die "usage: market info <name>"
            json="$(market_get "/api/v1/released-projects/$name")"
            if has_python; then
                printf '%s' "$json" | python3 -I -c '
import json, re, sys, html
d = json.load(sys.stdin)
desc = html.unescape(re.sub(r"<[^>]+>", " ", d.get("description") or ""))
desc = re.sub(r"\s+", " ", desc).strip()
price = d.get("price") or 0
print("name=%s" % d.get("name"))
print("display_name=%s" % d.get("displayName"))
print("package=%s" % d.get("packageName"))
print("price=%s" % ("free" if not price else "$%s" % price))
print("modules=%s" % ",".join(d.get("includeModuleTypes") or []))
print("latest_version=%s java=%s" % ((d.get("latestVersion") or {}).get("name"), (d.get("latestVersion") or {}).get("javaVersion")))
print("category=%s" % (d.get("category") or {}).get("name"))
print("short_description=%s" % (d.get("shortDescription") or "").strip())
print("description=%s" % desc[:4000])
'
            else
                printf '%s\n' "$json"
            fi
            if [ -n "$EZ_HOME" ] && [ -f "$EZ_HOME/cli.sh" ]; then
                echo "installed_types=$(installed_types "$name")"
            fi
            ;;
        docs)
            local name="${ARGS[1]:-}" json
            [ -n "$name" ] || die "usage: market docs <name>"
            json="$(market_get "/api/v1/projects/$name/docs?limit=100&lang=$OPT_LANG")"
            if has_python; then
                printf '%s' "$json" | python3 -I -c '
import json, sys
d = json.load(sys.stdin)
for i in d.get("items", []):
    print("%s | %s" % (i.get("slug"), i.get("title")))
'
            else
                printf '%s\n' "$json"
            fi
            ;;
        doc)
            local name="${ARGS[1]:-}" slug="${ARGS[2]:-}" json
            [ -n "$name" ] && [ -n "$slug" ] || die "usage: market doc <name> <slug>"
            json="$(market_get "/api/v1/projects/$name/docs/$slug/markdown?lang=$OPT_LANG")"
            if has_python; then
                printf '%s' "$json" | python3 -I -c '
import json, sys
d = json.load(sys.stdin)
print("# " + str(d.get("title") or ""))
print()
print(d.get("content") or d.get("markdown") or json.dumps(d, ensure_ascii=False))
'
            else
                printf '%s\n' "$json"
            fi
            ;;
        *) die "usage: market search|info|docs|doc ..." ;;
    esac
}

install_one_plugin() {
    local name="$1" out code
    if [ -n "$(installed_types "$name")" ]; then
        log "$name is already installed ($(installed_types "$name"))"
        return 0
    fi
    code="$(http_code "$MARKET_URL/api/v1/released-projects/$name")"
    [ "$code" = "200" ] || die "$name is not on the market ($MARKET_URL, HTTP $code); check the name with: market search"
    log "installing $name from the market"
    out="$(cli "install $name -v" 2>&1 || true)"
    if [ -z "$(installed_types "$name")" ]; then
        printf '%s\n' "$out" >&2
        if printf '%s' "$out" | grep -qiE 'paidProject|403|forbidden'; then
            need paid_plugin "$name is a paid project: the user must buy it on $MARKET_URL/market and connect the market account in the EzyPlatform admin (Market / Modules), or choose a free plugin"
        fi
        die "installing $name failed"
    fi
    log "$name installed ($(installed_types "$name"))"
}

install_plugins() {
    local queue=("$@") done_list=" " name dep installed=()
    while [ ${#queue[@]} -gt 0 ]; do
        name="${queue[0]}"
        queue=("${queue[@]:1}")
        case "$done_list" in *" $name "*) continue ;; esac
        install_one_plugin "$name"
        done_list="$done_list$name "
        installed+=("$name")
        for dep in $(module_dependencies "$name"); do
            case "$done_list" in *" $dep "*) ;; *) queue+=("$dep") ;; esac
        done
    done
    for name in "${installed[@]}"; do
        activate_project "$name" "$OPT_ACTIVATE_THEME"
    done
    INSTALLED_PLUGINS="${installed[*]}"
}

install_plugin_command() {
    [ ${#ARGS[@]} -gt 0 ] || die "usage: install-plugin <name...>"
    require_home
    require_java
    install_plugins "${ARGS[@]}"
    echo "RESULT_INSTALLED=$INSTALLED_PLUGINS"
    if [ -z "$OPT_NO_RESTART" ]; then
        restart_command
    else
        echo "RESULT_RESTART_NEEDED=true"
    fi
}

activate_command() {
    local name="${ARGS[0]:-}"
    [ -n "$name" ] || die "usage: activate <name>"
    require_home
    require_java
    [ -n "$(installed_types "$name")" ] || die "$name is not installed in $EZ_HOME"
    activate_project "$name" true
    echo "RESULT_ACTIVATED=$name ($(installed_types "$name"))"
}

require_project() {
    [ -f pom.xml ] || die "run this command from the project root (the folder with pom.xml and export.sh)"
    ls ./*/module.properties >/dev/null 2>&1 || die "no module.properties found: this is not an EzyPlatform project root"
}

project_modules() {
    local file
    for file in ./*/module.properties; do
        printf '%s|%s\n' "$(dirname "$file")" "$(prop_of "$file" type | tr -d ' ')"
    done
}

plugin_has_target() {
    local plugin="$1" type="$2" types
    types=" $(installed_types "$plugin") "
    case "$type" in
        admin-plugin) [[ "$types" == *" admin-plugin "* ]] ;;
        web-plugin|theme) [[ "$types" == *" web-plugin "* || "$types" == *" theme "* ]] ;;
        socket-plugin|socket-app) [[ "$types" == *" socket-plugin "* || "$types" == *" socket-app "* ]] ;;
        *) return 1 ;;
    esac
}

add_module_dependency() {
    local file="$1" plugin="$2" current
    current="$(prop_of "$file" dependencies | tr -d ' ')"
    case ",$current," in *",$plugin,"*) return 0 ;; esac
    if grep -q '^dependencies=' "$file"; then
        local tmp="$file.ezydev.tmp"
        if [ -n "$current" ]; then
            sed "s/^dependencies=.*/dependencies=$current,$plugin/" "$file" > "$tmp"
        else
            sed "s/^dependencies=.*/dependencies=$plugin/" "$file" > "$tmp"
        fi
        cat "$tmp" > "$file"
        rm -f "$tmp"
    else
        [ -z "$(tail -c 1 "$file")" ] || echo >> "$file"
        echo "dependencies=$plugin" >> "$file"
    fi
    log "added $plugin to $(dirname "$file")/module.properties dependencies"
}

link_command() {
    [ ${#ARGS[@]} -gt 0 ] || die "usage: link <plugin...> [-m admin-plugin,web-plugin,theme]"
    require_project
    require_dev
    install_plugins "${ARGS[@]}"
    local plugin line dir type
    for plugin in "${ARGS[@]}"; do
        log "ezy.sh link $plugin${OPT_LINK_TYPES:+ -m $OPT_LINK_TYPES}"
        if [ -n "$OPT_LINK_TYPES" ]; then
            ezy.sh link "$plugin" -m "$OPT_LINK_TYPES" >&2 || die "ezy.sh link $plugin failed"
        else
            ezy.sh link "$plugin" >&2 || die "ezy.sh link $plugin failed"
        fi
        while IFS='|' read -r dir type; do
            [ -n "$type" ] || continue
            if [ -n "$OPT_LINK_TYPES" ] && [ "$OPT_LINK_TYPES" != "all" ]; then
                case ",$OPT_LINK_TYPES," in *",$type,"*) ;; *) continue ;; esac
            fi
            plugin_has_target "$plugin" "$type" || continue
            add_module_dependency "$dir/module.properties" "$plugin"
        done < <(project_modules)
    done
    ezy.sh sdv >&2 || die "ezy.sh sdv failed"
    echo "RESULT_LINKED=${ARGS[*]}"
    echo "RESULT_INSTALLED=$INSTALLED_PLUGINS"
    echo "RESULT_RESTART_NEEDED=true"
}

sync_versions_command() {
    require_project
    require_dev
    ezy.sh sdv
}

create_command() {
    local name="${ARGS[0]:-}"
    [ -n "$name" ] || die "usage: create <name> [--group com.mycompany] [--modules theme,web-plugin,admin-plugin] [--out <folder>]"
    printf '%s' "$name" | grep -qE '^[a-z][a-z0-9-]{1,59}$' || die "project name must be lowercase letters, digits and '-', 2-60 characters, starting with a letter (for example: my-shop)"
    local group="${OPT_GROUP:-com.mycompany}" out
    printf '%s' "$group" | grep -qE '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$' || die "group must look like com.mycompany"
    out="$(abs_path "${OPT_OUT:-.}")"
    [ -e "$out/$name" ] && die "$out/$name already exists, choose another name or folder"
    require_dev
    mkdir -p "$out"
    local cmd=(ezy.sh create "$name" -g "$group" -o "$out")
    [ -n "$OPT_PACKAGE" ] && cmd+=(-p "$OPT_PACKAGE")
    [ -n "$OPT_MODULES" ] && cmd+=(-i "$OPT_MODULES")
    log "${cmd[*]}"
    "${cmd[@]}" < /dev/null >&2 || die "ezy.sh create failed"
    [ -f "$out/$name/pom.xml" ] || die "project was not created"
    chmod +x "$out/$name/export.sh" 2>/dev/null || true
    echo "RESULT_PROJECT_DIR=$out/$name"
    echo "RESULT_MODULES=$(cd "$out/$name" && project_modules | cut -d'|' -f2 | tr '\n' ',' | sed 's/,$//')"
}

export_command() {
    require_project
    require_dev
    [ -f export.sh ] || die "export.sh not found in $(pwd)"
    mkdir -p "$DEV_DIR/logs"
    local log_file="$DEV_DIR/logs/export-$(basename "$(pwd)").log"
    log "building and exporting $(basename "$(pwd)") (log: $log_file)"
    if ! bash export.sh > "$log_file" 2>&1; then
        grep -E '\[ERROR\]|ERROR|Exception|error:' "$log_file" | head -n 60 >&2 || true
        tail -n 40 "$log_file" >&2
        die "build/export failed, full log: $log_file"
    fi
    local names
    names="$(grep -oE 'export successfully [^ ]+ to ' "$log_file" | awk '{print $3}' | sort -u | tr '\n' ' ')"
    [ -n "$names" ] || die "export.sh finished but nothing was exported, see $log_file"
    local name
    for name in $names; do
        activate_project "$name" true
    done
    echo "RESULT_EXPORTED=${names% }"
    if [ -z "$OPT_NO_RESTART" ]; then
        restart_command
    else
        echo "RESULT_RESTART_NEEDED=true"
    fi
}

tables_command() {
    require_home
    local target="${ARGS[0]:-core}" dir
    if [ "$target" = "core" ]; then
        dir="$EZ_HOME/admin/resources/scripts"
    else
        dir="$EZ_HOME/admin/plugins/$target/resources/scripts"
    fi
    [ -d "$dir" ] || die "no SQL scripts in $dir (is $target installed? its admin plugin owns the tables)"
    echo "scripts_dir=$dir"
    grep -HioE 'create table (if not exists )?`?[a-z0-9_]+`?' "$dir"/*.sql 2>/dev/null \
        | sed -E 's#^.*/([^/]+\.sql):.*[Tt][Aa][Bb][Ll][Ee] ([Ii][Ff] [Nn][Oo][Tt] [Ee][Xx][Ii][Ss][Tt][Ss] )?`?([a-zA-Z0-9_]+)`?#\3 | \1#' \
        | sort -u
}

all_jars() {
    find "$EZ_HOME/lib" "$EZ_HOME/admin" "$EZ_HOME/web" "$EZ_HOME/socket" -name '*.jar' -path '*/lib/*' 2>/dev/null
}

project_jars() {
    all_jars | awk -F/ '{
        base = $NF; module = $(NF - 2)
        if (index(base, "ezyplatform-") == 1 || index(base, module "-") == 1) print
    }'
}

class_index() {
    local index="$DEV_DIR/class-index.txt" jar
    mkdir -p "$DEV_DIR"
    if [ -f "$index" ] && [ -z "$(find "$EZ_HOME/lib" "$EZ_HOME/admin" "$EZ_HOME/web" "$EZ_HOME/socket" -name '*.jar' -newer "$index" 2>/dev/null | head -1)" ]; then
        printf '%s' "$index"
        return
    fi
    log "indexing classes of the installed platform and plugins"
    : > "$index.tmp"
    while read -r jar; do
        if command -v unzip >/dev/null 2>&1; then
            unzip -Z1 "$jar" 2>/dev/null | grep '\.class$' | grep -v '\$' | sed "s#^#$jar!#" >> "$index.tmp" || true
        else
            "$JAVA_HOME_DIR/bin/jar" tf "$jar" 2>/dev/null | grep '\.class$' | grep -v '\$' | sed "s#^#$jar!#" >> "$index.tmp" || true
        fi
    done < <(project_jars)
    mv "$index.tmp" "$index"
    printf '%s' "$index"
}

find_class_in_jars() {
    local pattern="$1" index
    pattern="${pattern//./\/}"
    index="$(class_index)"
    grep -E "!(.*/)?${pattern}\.class$" "$index" || true
}

find_class_command() {
    local name="${ARGS[0]:-}"
    [ -n "$name" ] || die "usage: find-class <SimpleName|full.class.Name>"
    require_home
    require_java
    local found
    found="$(find_class_in_jars "$name")"
    [ -n "$found" ] || die "class $name not found in the installed platform and plugins"
    printf '%s\n' "$found"
}

ensure_cfr() {
    local jar="$DEV_DIR/tools/cfr-$CFR_VERSION.jar" url expected
    if [ -f "$jar" ]; then
        printf '%s' "$jar"
        return
    fi
    mkdir -p "$DEV_DIR/tools"
    url="https://repo1.maven.org/maven2/org/benf/cfr/$CFR_VERSION/cfr-$CFR_VERSION.jar"
    download "$url" "$jar.download" || die "cannot download CFR"
    expected="$(http_get "$url.sha1" | cut -d' ' -f1)"
    if [ -z "$expected" ] || [ "$(sha_of 1 "$jar.download")" != "$expected" ]; then
        rm -f "$jar.download"
        die "CFR checksum mismatch"
    fi
    mv "$jar.download" "$jar"
    printf '%s' "$jar"
}

decompile_command() {
    local target="${ARGS[0]:-}" jar class_path=""
    [ -n "$target" ] || die "usage: decompile <SimpleName|full.class.Name|path/to.jar>"
    require_home
    require_java
    if [ -f "$target" ]; then
        jar="$(abs_path "$target")"
    else
        local hits
        hits="$(find_class_in_jars "$target")"
        [ -n "$hits" ] || die "class $target not found in the installed platform and plugins"
        if [ "$(printf '%s\n' "$hits" | wc -l | tr -d ' ')" -gt 1 ]; then
            printf '%s\n' "$hits"
            die "several classes match $target, pass the full class name"
        fi
        jar="${hits%%!*}"
        class_path="${hits#*!}"
        class_path="${class_path%.class}.java"
    fi
    local cfr out
    cfr="$(ensure_cfr)"
    out="$DEV_DIR/decompiled/$(basename "$jar" .jar)"
    if [ ! -d "$out" ] || [ "$jar" -nt "$out" ]; then
        rm -rf "$out"
        mkdir -p "$out"
        log "decompiling $(basename "$jar") into $out"
        "$JAVA_HOME_DIR/bin/java" -jar "$cfr" "$jar" --outputdir "$out" --silent true >/dev/null 2>&1 || die "CFR failed on $jar"
    fi
    echo "RESULT_JAR=$jar"
    echo "RESULT_SOURCES=$out"
    if [ -n "$class_path" ]; then
        echo "RESULT_FILE=$out/$class_path"
    fi
}

case "$COMMAND" in
    check) check_command ;;
    setup) setup_command ;;
    env) require_home; dev_env_exports ;;
    run) run_command ;;
    create) create_command ;;
    link) link_command ;;
    sync-versions|sdv) sync_versions_command ;;
    export) export_command ;;
    market) market_command ;;
    install-plugin) install_plugin_command ;;
    activate) activate_command ;;
    restart) restart_command ;;
    status) status_command ;;
    tables) tables_command ;;
    find-class) find_class_command ;;
    decompile) decompile_command ;;
    help|-h|--help) usage ;;
    *) usage; exit 1 ;;
esac
