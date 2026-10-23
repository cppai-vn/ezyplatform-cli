"""`ezy plugins`: install and update the ezyplatform plugin in each coding agent.

Every action calls the agent's own CLI (claude, codex, copilot, omp), so the
agent keeps managing the plugin; Cursor has no plugin CLI and gets UI steps.
Whether the plugin is installed is read from the agent's plugin list.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

from .agent_process import probe
from .status_output import print_status as status_line

STATUS_TIMEOUT = 10
MARKETPLACE = 'cppai'
SOURCE = 'cppai-vn/agents-plugins'
PLUGIN = 'ezyplatform'
PLUGIN_ID = f'{PLUGIN}@{MARKETPLACE}'
CURSOR_STEPS = (f'In Cursor: Customize -> From GitHub Repository -> https://github.com/{SOURCE} '
                f'-> install "{PLUGIN}" (project or user scope).')

# name -> commands, each a list of argv lists run in order
AGENTS = {
    'claude': {
        'label': 'Claude Code',
        'list': ['claude', 'plugin', 'list', '--json'],
        'marketplaces': ['claude', 'plugin', 'marketplace', 'list'],
        'add_marketplace': ['claude', 'plugin', 'marketplace', 'add', SOURCE],
        'install': [['claude', 'plugin', 'install', PLUGIN_ID]],
        'update': [['claude', 'plugin', 'marketplace', 'update', MARKETPLACE], ['claude', 'plugin', 'update', PLUGIN_ID]],
    },
    'codex': {
        'label': 'Codex',
        'list': ['codex', 'plugin', 'list', '--json'],
        'marketplaces': ['codex', 'plugin', 'marketplace', 'list'],
        'add_marketplace': ['codex', 'plugin', 'marketplace', 'add', SOURCE],
        'install': [['codex', 'plugin', 'add', PLUGIN_ID]],
        'update': [['codex', 'plugin', 'marketplace', 'upgrade', MARKETPLACE]],
    },
    'copilot': {
        'label': 'GitHub Copilot CLI',
        'list': ['copilot', 'plugin', 'list'],
        'marketplaces': ['copilot', 'plugin', 'marketplace', 'list'],
        'add_marketplace': ['copilot', 'plugin', 'marketplace', 'add', SOURCE],
        'install': [['copilot', 'plugin', 'install', PLUGIN_ID]],
        'update': [['copilot', 'plugin', 'marketplace', 'update', MARKETPLACE], ['copilot', 'plugin', 'update', PLUGIN]],
    },
    'omp': {
        'label': 'oh-my-pi',
        'list': ['omp', 'plugin', 'list', '--json'],
        'marketplaces': ['omp', 'plugin', 'marketplace', 'list'],
        'add_marketplace': ['omp', 'plugin', 'marketplace', 'add', SOURCE],
        'install': [['omp', 'plugin', 'install', PLUGIN_ID]],
        'update': [['omp', 'plugin', 'marketplace', 'update', MARKETPLACE], ['omp', 'plugin', 'upgrade', PLUGIN_ID]],
    },
    'cursor': {'label': 'Cursor', 'manual': True},
}
NAMES = list(AGENTS)


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


def detected(name):
    if AGENTS[name].get('manual'):
        return bool(shutil.which('cursor') or os.path.isdir(os.path.expanduser('~/.cursor')))
    return bool(shutil.which(AGENTS[name]['list'][0]))


def plugin_installed(name, *, timeout=None):
    """True / False from the agent's plugin list, None when it cannot be told (Cursor, list failed)."""
    agent = AGENTS[name]
    if agent.get('manual') or not detected(name):
        return None
    code, out = run(agent['list'], timeout=STATUS_TIMEOUT if timeout is None else timeout,
                    non_interactive=True)
    if code != 0:
        return None
    try:
        data = json.loads(out)
    except ValueError:
        # plain-text list (Copilot): a line naming the plugin from this marketplace
        return any(PLUGIN_ID in line or (line.split() or [''])[0] == PLUGIN and MARKETPLACE in line
                   for line in out.splitlines())
    if isinstance(data, dict) and 'installed' in data:
        data = data['installed']  # Codex also lists marketplace plugins that are only available
    return is_listed(data)


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
        print(f'  - {agent["label"]}: no plugin CLI. {CURSOR_STEPS}')
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
            print(f'  would run: {show(argv)}')
            continue
        code, out = run(argv)
        if code != 0:
            status_line(f'{agent["label"]}: {show(argv)} failed', False)
            print(f'    {out.strip()[-400:]}')
            return None
    if dry_run:
        return None
    ok = plugin_installed(name)
    status_line(f'{agent["label"]}: {PLUGIN_ID} ' + ('installed' if ok else 'install ran but the plugin list does not show it yet'), bool(ok))
    return 'new' if ok else None


def update(name, dry_run=False):
    agent = AGENTS[name]
    for argv in agent['update']:
        if dry_run:
            print(f'  would run: {show(argv)}')
            continue
        code, out = run(argv)
        if code != 0:
            status_line(f'{agent["label"]}: {show(argv)} failed', False)
            print(f'    {out.strip()[-400:]}')
            return False
    if not dry_run:
        status_line(f'{agent["label"]}: {PLUGIN_ID} updated', True)
    return True


def status_rows(names=NAMES, *, progress=False):
    """Collect status rows, optionally printing each completed result immediately."""
    rows = []
    for name in names:
        label = AGENTS[name]['label']
        found = detected(name)
        installed = plugin_installed(name, timeout=STATUS_TIMEOUT) if found else None
        row = (name, label, found, installed)
        rows.append(row)
        if progress:
            print_status(rows=[row])
    return rows


def print_status(names=NAMES, rows=None):
    if rows is None:
        status_rows(names, progress=True)
        return
    for name, label, found, installed in rows:
        ok = False
        if not found:
            state = 'not found on this computer'
        elif AGENTS[name].get('manual'):
            state = 'found; check Customize -> Plugins in Cursor'
            ok = None
        elif installed is None:
            state = 'found; plugin list could not be read (failed or timed out)'
        else:
            state = f'{PLUGIN_ID} installed' if installed else 'plugin not installed'
            ok = installed
        status_line(f'{label:20} {state}', ok)


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
            print(f'  - {AGENTS[name]["label"]}: update from Cursor (reinstall, or Auto Refresh on a team marketplace)')
        elif plugin_installed(name):
            failed += not update(name, opts.dry_run)
        else:
            print(f'  - {AGENTS[name]["label"]}: plugin not installed (ezy plugins install --target {name})')
    if new:
        print('Start a new session in each agent to load the skills.')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
