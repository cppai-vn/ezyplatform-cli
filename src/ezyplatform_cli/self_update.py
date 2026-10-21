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
import urllib.request

from . import __version__

REPO = 'https://github.com/itsddvn/ezyplatform-cli'
API = 'https://api.github.com/repos/itsddvn/ezyplatform-cli'
WHEEL = REPO + '/releases/download/v{v}/ezyplatform_cli-{v}-py3-none-any.whl'
INSTALL_HINT = ('  macOS / Linux: curl -LsSf https://raw.githubusercontent.com/itsddvn/ezyplatform-cli/main/install.sh | sh\n'
                '  Windows:       powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/itsddvn/ezyplatform-cli/main/install.ps1 | iex"')


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


def run_uv(command, done_message):
    """Run a uv command that replaces or removes this ezy; on Windows after ezy has exited."""
    if os.name == 'nt':
        line = subprocess.list2cmdline(command)
        subprocess.Popen(['cmd', '/c', f'timeout /t 2 /nobreak >nul & {line} & pause'],
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
        print('This continues in a new window; open a new terminal when it is done.')
        return 0
    code = subprocess.call(command)
    if code == 0:
        print(done_message)
    return code


def update(args):
    if args and args[0] in ('-h', '--help'):
        print('usage: ezy update\n\nInstall the latest ezy release from GitHub (uses uv).')
        return 0
    try:
        latest = latest_version()
    except OSError as err:
        print(f"ezy: cannot check for updates: {getattr(err, 'reason', err)}", file=sys.stderr)
        return 2
    if parse(latest) <= parse(__version__):
        print(f'ezy {__version__} is the latest version')
        return 0
    uv = find_uv()
    if not uv:
        print(f'ezy {latest} is available (installed: {__version__}). uv was not found; upgrade with:\n{INSTALL_HINT}')
        return 1
    command = [uv, 'tool', 'install', '--force', '--python', '>=3.9', WHEEL.format(v=latest)]
    print(f'Updating ezy {__version__} -> {latest}', flush=True)
    return run_uv(command, f'ezy updated to {latest}')


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
