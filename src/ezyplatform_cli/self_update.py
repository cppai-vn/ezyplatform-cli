"""`ezy update` and `ezy uninstall`: manage the ezy installation itself.

update installs the latest GitHub release over the current one with uv.
uninstall removes ezy with the tool that installed it (uv,
pipx or pip); site projects are never touched. On Windows the running ezy.exe
is locked, so uv runs in a new console window after ezy exits.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request

from . import __version__

REPO = 'https://github.com/cppai-vn/ezyplatform-cli'
API = 'https://api.github.com/repos/cppai-vn/ezyplatform-cli'
WHEEL = REPO + '/releases/download/v{v}/ezyplatform_cli-{v}-py3-none-any.whl'
INSTALL_HINT = ('  macOS / Linux: curl -LsSf https://raw.githubusercontent.com/cppai-vn/ezyplatform-cli/main/install.sh | sh\n'
                '  Windows:       powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/cppai-vn/ezyplatform-cli/main/install.ps1 | iex"')


def latest_version():
    """Version of the latest release, e.g. '0.1.1'.

    The API answer is current; when it is rate limited, fall back to the
    releases/latest redirect. That redirect is cached per Accept header, and the
    variant without one (urllib's default) can point at an old release for hours,
    so Accept is always sent.
    """
    headers = {'User-Agent': 'ezy/' + __version__}
    try:
        req = urllib.request.Request(API + '/releases/latest', headers=dict(headers, Accept='application/vnd.github+json'))
        with urllib.request.urlopen(req, timeout=30) as resp:
            tag = json.load(resp).get('tag_name') or ''
    except (OSError, ValueError):
        req = urllib.request.Request(REPO + '/releases/latest', method='HEAD', headers=dict(headers, Accept='*/*'))
        with urllib.request.urlopen(req, timeout=30) as resp:
            tag = resp.geturl().rstrip('/').rsplit('/tag/', 1)[-1]
    if not tag.startswith('v'):
        raise OSError('no release found on GitHub')
    return tag[1:]


def parse(version):
    return tuple(int(p) if p.isdigit() else 0 for p in version.split('.'))


def find_uv():
    found = shutil.which('uv')
    if found:
        return found
    name = 'uv.exe' if os.name == 'nt' else 'uv'
    for folder in (os.environ.get('UV_INSTALL_DIR'), os.environ.get('XDG_BIN_HOME'),
                   os.path.expanduser('~/.local/bin'), os.path.expanduser('~/.cargo/bin')):
        if folder and os.path.isfile(os.path.join(folder, name)):
            return os.path.join(folder, name)
    return None


def installer():
    """'uv', 'pipx' or 'pip', from where this ezy's Python environment lives."""
    parts = os.path.normpath(sys.prefix).split(os.sep)
    if parts[-1:] == ['ezyplatform-cli'] and parts[-2:-1] == ['tools']:
        return 'uv'
    if parts[-1:] == ['ezyplatform-cli'] and parts[-2:-1] == ['venvs']:
        return 'pipx'
    return 'pip'


def ezy_command():
    """argv that starts the installed ezy (the new one after uv replaced it)."""
    if os.path.basename(sys.argv[0]).lower().startswith('ezy'):
        return [os.path.abspath(sys.argv[0])]
    found = shutil.which('ezy')
    return [found] if found else [sys.executable, '-m', 'ezyplatform_cli']


def cmd_line(argv):
    """One batch-file line; every argument double-quoted (none of ours contain quotes)."""
    return ' '.join('"' + a.replace('%', '%%') + '"' for a in argv)


def run_uv(command, done_message, then=None):
    """Run a uv command that replaces or removes this ezy; on Windows after ezy has exited.

    `then` is run after a successful command (on Windows in the same new window).
    """
    if os.name == 'nt':
        # a batch file, because cmd /c "..." mangles quoted paths and reads '>=3.9' as a redirect
        lines = ['@echo off', 'timeout /t 2 /nobreak >nul', cmd_line(command), 'if errorlevel 1 goto end']
        if then:
            lines.append(cmd_line(then))
        lines += [':end', 'pause', '(goto) 2>nul & del "%~f0"']
        fd, script = tempfile.mkstemp(suffix='.cmd', prefix='ezy-')
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write('\r\n'.join(lines) + '\r\n')
        subprocess.Popen(['cmd', '/c', script], creationflags=subprocess.CREATE_NEW_CONSOLE)
        print('This continues in a new window; open a new terminal when it is done.')
        return 0
    code = subprocess.call(command)
    if code == 0:
        print(done_message)
        if then:
            code = subprocess.call(then)
    return code


def refresh():
    """Update the plugin in every agent that has it and refresh ezy's skill copies."""
    from . import agents, skills_install
    print('Plugins')
    states = {n: agents.plugin_installed(n) for n in agents.NAMES if agents.detected(n) and not agents.AGENTS[n].get('manual')}
    for name in [n for n, s in states.items() if s is None]:
        print(f"  ? {agents.AGENTS[name]['label']}: plugin list could not be read, skipped")
    names = [n for n, s in states.items() if s]
    ok = all([agents.update(n) for n in names])
    if not names:
        print('  no agent has the ezyplatform plugin')
    print('Skill copies')
    copies = [(d, r) for d, r in skills_install.copies() if skills_install.read_manifest(d)]
    for dest, result in copies:
        if result == 'ok':
            print(f'  = {dest}: up to date')
        elif result.startswith('modified'):
            print(f'  ! {dest}: {result}, kept; replace with: ezy skills install --dir {dest} --force')
            ok = False
        else:
            ok &= skills_install.install_to(dest, force=True)
    if not copies:
        print('  none')
    return 0 if ok else 1


def update(args):
    if args and args[0] in ('-h', '--help'):
        print('usage: ezy update [--cli-only]\n\nInstall the latest ezy release from GitHub (uses uv), then update '
              'the ezyplatform plugin in your agents and the skill copies made by ezy.')
        return 0
    if '--refresh' in args:
        return refresh()
    cli_only = '--cli-only' in args
    try:
        latest = latest_version()
    except OSError as err:
        print(f"ezy: cannot check for updates: {getattr(err, 'reason', err)}", file=sys.stderr)
        return 2
    if parse(latest) <= parse(__version__):
        print(f'ezy {__version__} is the latest version')
        return 0 if cli_only else refresh()
    uv = find_uv()
    if not uv:
        print(f'ezy {latest} is available (installed: {__version__}). uv was not found; upgrade with:\n{INSTALL_HINT}')
        return 1
    command = [uv, 'tool', 'install', '--force', '--python', '>=3.9', WHEEL.format(v=latest)]
    print(f'Updating ezy {__version__} -> {latest}', flush=True)
    # the new ezy refreshes plugins and skills, so the copies match the new bundle
    then = None if cli_only else ezy_command() + ['update', '--refresh']
    return run_uv(command, f'ezy updated to {latest}', then)


def uninstall(args):
    if args and args[0] in ('-h', '--help'):
        print('usage: ezy uninstall [--yes]\n\nRemove ezy from this computer. '
              'Site projects (environment.json, pages/ ...) are kept.')
        return 0
    if '--yes' not in args and '-y' not in args:
        if not sys.stdin.isatty():
            print('ezy: run "ezy uninstall --yes" to confirm', file=sys.stderr)
            return 1
        if input(f'Remove ezy {__version__} from this computer? Site projects are kept. [y/N] ').strip().lower() not in ('y', 'yes'):
            print('cancelled')
            return 1
    how = installer()
    if how == 'pipx':
        return subprocess.call(['pipx', 'uninstall', 'ezyplatform-cli'])
    if how == 'pip':
        return subprocess.call([sys.executable, '-m', 'pip', 'uninstall', '-y', 'ezyplatform-cli'])
    uv = find_uv()
    if not uv:
        print(f'ezy: uv was not found; delete {sys.prefix} and the ezy command next to uv\'s tools', file=sys.stderr)
        return 1
    print(f'Removing ezy {__version__}', flush=True)
    return run_uv([uv, 'tool', 'uninstall', 'ezyplatform-cli'], 'ezy was removed. Reinstall any time with the install line in the README.')
