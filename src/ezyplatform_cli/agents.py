"""`ezy plugins`: scan coding agents and manage the ezyplatform plugin.

Status checks read each agent's local plugin registry on disk first (< 1ms per
agent, zero network calls) and fall back to bounded, parallel CLI probes only
when local state is absent. Mutations (install/update) always call the agent's
own CLI so the agent keeps managing the plugin.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import shutil
import subprocess
import sys

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover - Python 3.9/3.10 fallback
    tomllib = None

from .agent_process import probe
from .status_output import print_status as status_line

STATUS_TIMEOUT = 10
MARKETPLACE = 'cppai'
SOURCE = 'cppai-vn/agents-plugins'
PLUGIN = 'ezyplatform'
PLUGIN_ID = f'{PLUGIN}@{MARKETPLACE}'
CURSOR_STEPS = (f'In Cursor: Customize -> From GitHub Repository -> https://github.com/{SOURCE} '
                f'-> install "{PLUGIN}" (or run: ezy skills install --dir ~/.cursor/skills).')

# name -> commands and detection metadata
AGENTS = {
    'claude': {
        'label': 'Claude Code',
        'bins': ('claude',),
        'apps': ('/Applications/Claude.app', '~/Applications/Claude.app'),
        'app_dirs': ('~/.claude',),
        'list': ['claude', 'plugin', 'list', '--json'],
        'marketplaces': ['claude', 'plugin', 'marketplace', 'list'],
        'add_marketplace': ['claude', 'plugin', 'marketplace', 'add', SOURCE],
        'install': [['claude', 'plugin', 'install', PLUGIN_ID]],
        'update': [['claude', 'plugin', 'marketplace', 'update', MARKETPLACE], ['claude', 'plugin', 'update', PLUGIN_ID]],
    },
    'codex': {
        'label': 'Codex',
        'bins': ('codex',),
        'apps': ('/Applications/Codex.app', '~/Applications/Codex.app'),
        'app_dirs': ('~/.codex',),
        # Scope to the cppai marketplace so Codex never hangs querying remote OpenAI marketplaces.
        'list': ['codex', 'plugin', 'list', '--marketplace', MARKETPLACE, '--json'],
        'marketplaces': ['codex', 'plugin', 'marketplace', 'list'],
        'add_marketplace': ['codex', 'plugin', 'marketplace', 'add', SOURCE],
        'install': [['codex', 'plugin', 'add', PLUGIN_ID]],
        'update': [['codex', 'plugin', 'marketplace', 'upgrade', MARKETPLACE]],
    },
    'copilot': {
        'label': 'GitHub Copilot CLI',
        'bins': ('copilot',),
        'apps': (),
        'app_dirs': (),
        'list': ['copilot', 'plugin', 'list'],
        'marketplaces': ['copilot', 'plugin', 'marketplace', 'list'],
        'add_marketplace': ['copilot', 'plugin', 'marketplace', 'add', SOURCE],
        'install': [['copilot', 'plugin', 'install', PLUGIN_ID]],
        'update': [['copilot', 'plugin', 'marketplace', 'update', MARKETPLACE], ['copilot', 'plugin', 'update', PLUGIN]],
    },
    'omp': {
        'label': 'oh-my-pi',
        'bins': ('omp',),
        'apps': (),
        'app_dirs': (),
        'list': ['omp', 'plugin', 'list', '--json'],
        'marketplaces': ['omp', 'plugin', 'marketplace', 'list'],
        'add_marketplace': ['omp', 'plugin', 'marketplace', 'add', SOURCE],
        'install': [['omp', 'plugin', 'install', PLUGIN_ID]],
        'update': [['omp', 'plugin', 'marketplace', 'update', MARKETPLACE], ['omp', 'plugin', 'upgrade', PLUGIN_ID]],
    },
    'cursor': {
        'label': 'Cursor',
        'manual': True,
        'bins': ('cursor', 'cursor-agent'),
        'apps': ('/Applications/Cursor.app', '~/Applications/Cursor.app'),
        'app_dirs': ('~/.cursor',),
    },
}
NAMES = list(AGENTS)
_DEFAULT_LIST_COMMANDS = {k: list(v['list']) for k, v in AGENTS.items() if 'list' in v}


def run(argv, *, timeout=300, non_interactive=False):
    """Run an agent command with its resolved executable (a .cmd shim on Windows too).

    Returns (exit code, output): stdout on success, so warnings on stderr never
    break JSON parsing; stdout + stderr on failure, for the error message.
    """
    exe = shutil.which(argv[0])
    if not exe:
        return 127, f'{argv[0]} not found'
    try:
        if non_interactive:
            proc = probe([exe] + argv[1:], timeout)
        else:
            proc = subprocess.run([exe] + argv[1:], capture_output=True, text=True, encoding='utf-8',
                                  errors='replace', timeout=timeout)
    except (OSError, subprocess.SubprocessError) as err:
        return 1, str(err)
    out = proc.stdout or ''
    return proc.returncode, out if proc.returncode == 0 else out + (proc.stderr or '')


_DEFAULT_RUN = run


def _has_app_bundle(apps, app_dirs):
    """True on macOS when a GUI app bundle exists and the user has its home config dir."""
    if sys.platform != 'darwin' or not apps:
        return False
    if not any(os.path.exists(os.path.expanduser(app)) for app in apps):
        return False
    if not app_dirs:
        return True
    return any(os.path.exists(os.path.expanduser(d)) for d in app_dirs)


def detected(name):
    """True when the coding agent is installed on this computer."""
    agent = AGENTS[name]
    bins = agent.get('bins') or ((agent['list'][0],) if 'list' in agent else ())
    if any(shutil.which(b) for b in bins):
        return True
    if _has_app_bundle(agent.get('apps', ()), agent.get('app_dirs', ())):
        return True
    if agent.get('manual'):
        # Cursor without CLI on PATH (Linux/Windows): check active Cursor config markers.
        return any(os.path.exists(os.path.expanduser(p))
                   for p in ('~/.cursor/plugins', '~/.cursor/cli-config.json', '~/.cursor/extensions'))
    return False


def _read_json(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _dir_nonempty(path):
    try:
        if not os.path.isdir(path):
            return False
        with os.scandir(path) as it:
            return any(True for _ in it)
    except OSError:
        return False


def _entries_have_valid_install(entries):
    """Extract (installed, version) from v2 installed_plugins.json entry list."""
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list) or not entries:
        return False, None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        install_path = entry.get('installPath')
        if install_path and not os.path.exists(install_path):
            continue
        return True, entry.get('version')
    return False, None


def _read_installed_plugins_json(path, settings_path=None):
    """Fast local check for Claude Code and oh-my-pi installed_plugins.json (v2)."""
    if not os.path.isfile(path):
        return None, None, None
    data = _read_json(path)
    if not isinstance(data, dict):
        return None, None, None
    plugins = data.get('plugins')
    if isinstance(plugins, dict):
        entries = plugins.get(PLUGIN_ID)
        if not entries:
            return False, None, 'local'
        ok, version = _entries_have_valid_install(entries)
        if not ok:
            return False, None, 'local'
        if settings_path and os.path.isfile(settings_path):
            settings = _read_json(settings_path)
            if isinstance(settings, dict):
                enabled = settings.get('enabledPlugins')
                if isinstance(enabled, dict) and enabled.get(PLUGIN_ID) is False:
                    return False, version, 'disabled'
        return True, version, 'plugin'
    if is_listed(data):
        return True, None, 'plugin'
    return False, None, 'local'


def _parse_codex_plugin_enabled(text):
    """Return True, False, or None for [plugins."ezyplatform@cppai"].enabled in config.toml."""
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except ValueError:
            return None
        plugins = data.get('plugins')
        if not isinstance(plugins, dict):
            return False
        entry = plugins.get(PLUGIN_ID)
        if not isinstance(entry, dict):
            return False
        return entry.get('enabled', True) is not False

    # Minimal TOML section scanner for Python 3.9/3.10
    header_re = re.compile(r'^\s*\[([^\]]+)\]\s*$')
    target_headers = {f'plugins."{PLUGIN_ID}"', f"plugins.'{PLUGIN_ID}'"}
    in_section = False
    found_section = False
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        match = header_re.match(line)
        if match:
            in_section = match.group(1).strip() in target_headers
            if in_section:
                found_section = True
            continue
        if in_section and re.match(r'^enabled\s*=\s*false\b', line, re.IGNORECASE):
            return False
        if in_section and re.match(r'^enabled\s*=\s*true\b', line, re.IGNORECASE):
            return True
    return True if found_section else False


def _codex_cached_version(codex_home):
    cache_dir = os.path.join(codex_home, 'plugins', 'cache', MARKETPLACE, PLUGIN)
    if not os.path.isdir(cache_dir):
        return None
    try:
        with os.scandir(cache_dir) as it:
            versions = sorted(
                (e.name for e in it if e.is_dir() and not e.name.startswith('.')),
                reverse=True,
            )
    except OSError:
        return None
    for ver in versions:
        if _dir_nonempty(os.path.join(cache_dir, ver)):
            return ver
    return None


def _local_codex_status():
    codex_home = os.path.expanduser(os.environ.get('CODEX_HOME') or '~/.codex')
    config_path = os.path.join(codex_home, 'config.toml')
    if not os.path.isfile(config_path):
        return None, None, None
    try:
        with open(config_path, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except OSError:
        return None, None, None
    enabled = _parse_codex_plugin_enabled(text)
    if enabled is None:
        return None, None, None
    version = _codex_cached_version(codex_home)
    if enabled:
        if version is not None:
            return True, version, 'plugin'
        # Enabled in config.toml but not in expected cache path: verify with CLI.
        return None, None, None
    return False, version, 'local'


def _local_cursor_status():
    cursor_home = os.path.expanduser('~/.cursor')
    # 1. Check marketplace plugin cache (~/.cursor/plugins/cache/<marketplace>/ezyplatform/...)
    cache_root = os.path.join(cursor_home, 'plugins', 'cache')
    if os.path.isdir(cache_root):
        try:
            with os.scandir(cache_root) as it:
                for mp in it:
                    if not mp.is_dir():
                        continue
                    plug = os.path.join(mp.path, PLUGIN)
                    if _dir_nonempty(plug):
                        return True, None, 'plugin'
        except OSError:
            pass
    # 2. Check local plugin (~/.cursor/plugins/local/ezyplatform)
    if _dir_nonempty(os.path.join(cursor_home, 'plugins', 'local', PLUGIN)):
        return True, None, 'plugin'
    # 3. Check skill copies read by Cursor
    for skill_dir in ('~/.cursor/skills', '~/.agents/skills'):
        if os.path.isfile(os.path.join(os.path.expanduser(skill_dir), 'ezy-guide', 'SKILL.md')):
            return True, None, 'skills'
    if os.path.isdir(cursor_home):
        return False, None, 'local'
    return None, None, None


def _local_copilot_status():
    copilot_home = os.path.expanduser('~/.copilot')
    for candidate in (
        os.path.join(copilot_home, 'installed-plugins', MARKETPLACE, PLUGIN),
        os.path.join(copilot_home, 'plugins', MARKETPLACE, PLUGIN),
    ):
        if _dir_nonempty(candidate):
            return True, None, 'plugin'
    return None, None, None


def local_plugin_status(name):
    """Fast (< 1ms) on-disk check returning (installed: bool|None, version: str|None, source: str|None)."""
    if name == 'claude':
        base = os.path.expanduser(os.environ.get('CLAUDE_CONFIG_DIR') or '~/.claude')
        return _read_installed_plugins_json(
            os.path.join(base, 'plugins', 'installed_plugins.json'),
            os.path.join(base, 'settings.json'),
        )
    if name == 'omp':
        base = os.path.expanduser('~/.omp')
        return _read_installed_plugins_json(os.path.join(base, 'plugins', 'installed_plugins.json'))
    if name == 'codex':
        return _local_codex_status()
    if name == 'cursor':
        return _local_cursor_status()
    if name == 'copilot':
        return _local_copilot_status()
    return None, None, None


def _can_use_local(name):
    """Only short-circuit via on-disk state when neither run() nor the list command was overridden."""
    agent = AGENTS[name]
    if agent.get('manual'):
        return True
    if run is not _DEFAULT_RUN:
        return False
    return agent.get('list') == _DEFAULT_LIST_COMMANDS.get(name)


def _probe_plugin_cli(name, timeout):
    agent = AGENTS[name]
    code, out = run(agent['list'], timeout=STATUS_TIMEOUT if timeout is None else timeout,
                    non_interactive=True)
    if code != 0:
        return None, None, None
    try:
        data = json.loads(out)
    except ValueError:
        # plain-text list (Copilot): a line naming the plugin from this marketplace
        listed = any(PLUGIN_ID in line or (line.split() or [''])[0] == PLUGIN and MARKETPLACE in line
                     for line in out.splitlines())
        return listed, None, 'cli'
    if isinstance(data, dict) and 'installed' in data:
        data = data['installed']  # Codex also lists marketplace plugins that are only available
    return is_listed(data), _extract_version(data), 'cli'


def _extract_version(data):
    if isinstance(data, list):
        for item in data:
            v = _extract_version(item)
            if v:
                return v
        return None
    if not isinstance(data, dict):
        return None
    if PLUGIN_ID in (data.get('id'), data.get('pluginId')):
        if data.get('version'):
            return str(data['version'])
        entries = data.get('entries')
        if isinstance(entries, list) and entries and isinstance(entries[0], dict) and entries[0].get('version'):
            return str(entries[0]['version'])
    if data.get('name') == PLUGIN and MARKETPLACE in json.dumps(data) and data.get('version'):
        return str(data['version'])
    for v in data.values():
        if isinstance(v, (list, dict)):
            found = _extract_version(v)
            if found:
                return found
    return None


def plugin_status_detail(name, *, timeout=None, prefer_local=True):
    """Return (installed: bool|None, version: str|None, source: str|None) for one agent."""
    if not detected(name):
        return None, None, None
    if prefer_local and _can_use_local(name):
        installed, version, source = local_plugin_status(name)
        if installed is not None:
            return installed, version, source
    if AGENTS[name].get('manual'):
        return None, None, None
    return _probe_plugin_cli(name, timeout)


def plugin_installed(name, *, timeout=None, prefer_local=True):
    """True / False from local registry or agent's plugin list, None when it cannot be told."""
    installed, _, _ = plugin_status_detail(name, timeout=timeout, prefer_local=prefer_local)
    return installed


def is_listed(data):
    """True when a JSON plugin list holds ezyplatform from the cppai marketplace."""
    if isinstance(data, list):
        return any(is_listed(item) for item in data)
    if not isinstance(data, dict):
        return False
    if PLUGIN_ID in (data.get('id'), data.get('pluginId')):
        return True
    if data.get('name') == PLUGIN and MARKETPLACE in json.dumps(data):
        return True
    return any(is_listed(v) for v in data.values() if isinstance(v, (list, dict)))


def parse_targets(value):
    names = NAMES if value in (None, 'all') else [t.strip() for t in value.split(',') if t.strip()]
    unknown = [n for n in names if n not in AGENTS]
    if unknown:
        raise SystemExit(f"ezy: unknown agent {', '.join(unknown)}; use all or {','.join(NAMES)}")
    return names


def show(argv):
    return ' '.join(argv)


def install(name, dry_run=False):
    """Install the plugin into one agent: 'new', 'already', or None when it is not installed."""
    agent = AGENTS[name]
    if agent.get('manual'):
        status_line(f'{agent["label"]}: no plugin CLI. {CURSOR_STEPS}')
        return None
    if plugin_installed(name):
        status_line(f'{agent["label"]}: {PLUGIN_ID} already installed', True)
        return 'already'
    steps = list(agent['install'])
    code, out = run(agent['marketplaces'], timeout=STATUS_TIMEOUT, non_interactive=True)
    if code != 0 or MARKETPLACE not in out:
        steps.insert(0, agent['add_marketplace'])
    for argv in steps:
        if dry_run:
            status_line(f'would run: {show(argv)}')
            continue
        code, out = run(argv)
        if code != 0:
            status_line(f'{agent["label"]}: {show(argv)} failed\n  {out.strip()[-400:]}', False)
            return None
    if dry_run:
        return None
    ok = plugin_installed(name)
    status_line(f'{agent["label"]}: {PLUGIN_ID} '
                + ('installed' if ok else 'install ran but the plugin list does not show it yet'), bool(ok))
    return 'new' if ok else None


def update(name, dry_run=False):
    agent = AGENTS[name]
    for argv in agent['update']:
        if dry_run:
            status_line(f'would run: {show(argv)}')
            continue
        code, out = run(argv)
        if code != 0:
            status_line(f'{agent["label"]}: {show(argv)} failed\n  {out.strip()[-400:]}', False)
            return False
    if not dry_run:
        status_line(f'{agent["label"]}: {PLUGIN_ID} updated', True)
    return True


def format_status(name, label, found, installed, *, version=None, source=None):
    """Return (text, ok) for one agent status line."""
    if not found:
        return f'{label:20} not found on this computer', False
    if AGENTS[name].get('manual'):
        if installed is True:
            if source == 'skills':
                return f'{label:20} ezy-* skills installed', True
            suffix = f' ({version})' if version else ''
            return f'{label:20} {PLUGIN_ID} installed{suffix}', True
        if installed is False:
            return f'{label:20} not installed (Customize -> Plugins, or: ezy skills install --dir ~/.cursor/skills)', False
        return f'{label:20} found; check Customize -> Plugins in Cursor', None
    if installed is None:
        return f'{label:20} found; plugin list could not be read (failed or timed out)', False
    if installed:
        suffix = f' ({version})' if version else ''
        return f'{label:20} {PLUGIN_ID} installed{suffix}', True
    if source == 'disabled':
        return f'{label:20} {PLUGIN_ID} installed but disabled', False
    return f'{label:20} plugin not installed', False


def status_rows(names=NAMES, *, progress=False):
    """[(name, label, detected, installed)] for display and doctor.

    Uses fast on-disk checks first; any agents requiring a CLI probe are run in
    parallel so total latency is bounded by the slowest single probe rather than
    their sum. Results are printed in canonical order when `progress=True`.
    """
    names = list(names)
    found_map = {n: detected(n) for n in names}
    details = {}
    need_cli = []

    # If callers monkeypatched plugin_installed(), honour it directly so tests
    # that intercept plugin_installed keep working identically.
    patched_pi = plugin_installed is not _DEFAULT_PLUGIN_INSTALLED

    for n in names:
        if not found_map[n]:
            details[n] = (None, None, None)
            continue
        if patched_pi:
            need_cli.append(n)
            continue
        if _can_use_local(n):
            inst, ver, src = local_plugin_status(n)
            if inst is not None:
                details[n] = (inst, ver, src)
                continue
        if AGENTS[n].get('manual'):
            details[n] = (None, None, None)
            continue
        need_cli.append(n)

    futures = {}
    executor = ThreadPoolExecutor(max_workers=len(need_cli)) if len(need_cli) > 1 and not patched_pi else None
    try:
        if executor is not None:
            for n in need_cli:
                futures[n] = executor.submit(_probe_plugin_cli, n, STATUS_TIMEOUT)
        rows = []
        for n in names:
            label = AGENTS[n]['label']
            found = found_map[n]
            if n in details:
                installed, version, source = details[n]
            elif n in futures:
                installed, version, source = futures[n].result()
            elif patched_pi:
                installed = plugin_installed(n)
                version, source = None, None
            else:
                installed, version, source = _probe_plugin_cli(n, STATUS_TIMEOUT)
            row = (n, label, found, installed)
            rows.append(row)
            if progress:
                text, ok = format_status(n, label, found, installed, version=version, source=source)
                status_line(text, ok)
        return rows
    finally:
        if executor is not None:
            executor.shutdown(wait=False)


_DEFAULT_PLUGIN_INSTALLED = plugin_installed


def print_status(names=NAMES, rows=None):
    if rows is None:
        return status_rows(names, progress=True)
    for name, label, found, installed in rows:
        version, source = None, None
        if found and _can_use_local(name):
            loc_inst, version, source = local_plugin_status(name)
            if loc_inst != installed:
                version, source = None, None
        text, ok = format_status(name, label, found, installed, version=version, source=source)
        status_line(text, ok)
    return rows


def print_other_agents_status():
    """Show any skill-based coding agents detected on this system."""
    from . import skills_install
    other = [row for row in skills_install.target_status_rows() if row[2]]
    if not other:
        return other
    print('\nOther coding agents on this computer (skills)')
    for _, label, _, installed_dir, result in other:
        if installed_dir and result == 'ok':
            status_line(f'{label:20} ezy-* skills installed ({installed_dir})', True)
        elif installed_dir:
            status_line(f'{label:20} ezy-* skills {result} ({installed_dir})', False)
        else:
            status_line(f'{label:20} ezy-* skills not installed (run: ezy skills install)', False)
    return other


def main(args):
    parser = argparse.ArgumentParser(prog='ezy plugins', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=['status', 'install', 'update'])
    parser.add_argument('--target', default='all', help=f"all (default: agents found here) or a comma list of {','.join(NAMES)}")
    parser.add_argument('--dry-run', action='store_true', help='print the agent commands without running them')
    opts = parser.parse_args(args)
    names = parse_targets(opts.target)
    if opts.action == 'status':
        print_status(names)
        if opts.target == 'all':
            print_other_agents_status()
        return 0
    found = [n for n in names if detected(n)]
    if not found:
        print('ezy: none of these agents was found on this computer: ' + ', '.join(names))
        return 1
    print(f"{'Installing' if opts.action == 'install' else 'Updating'} {PLUGIN_ID} for: "
          + ', '.join(AGENTS[n]['label'] for n in found))
    failed, new = 0, 0
    for name in found:
        if opts.action == 'install':
            result = install(name, opts.dry_run)
            new += result == 'new'
            failed += not result and not AGENTS[name].get('manual') and not opts.dry_run
        elif AGENTS[name].get('manual'):
            status_line(f'{AGENTS[name]["label"]}: update from Cursor (reinstall, or Auto Refresh on a team marketplace)')
        elif plugin_installed(name):
            failed += not update(name, opts.dry_run)
        else:
            status_line(f'{AGENTS[name]["label"]}: plugin not installed (ezy plugins install --target {name})', False)
    if new:
        print('Start a new session in each agent to load the skills.')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
