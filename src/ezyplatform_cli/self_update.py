"""`ezy update`: install the latest GitHub release over the current one with uv.

The latest tag comes from the redirect of /releases/latest (no GitHub API call,
so no rate limit). uv replaces the tool in place; on Windows the running
ezy.exe is locked, so the install runs in a new console window after ezy exits.
"""
import os
import shutil
import subprocess
import sys
import urllib.request

from . import __version__

REPO = 'https://github.com/itsddvn/ezyplatform-cli'
WHEEL = REPO + '/releases/download/v{v}/ezyplatform_cli-{v}-py3-none-any.whl'
INSTALL_HINT = ('  macOS / Linux: curl -LsSf https://raw.githubusercontent.com/itsddvn/ezyplatform-cli/main/install.sh | sh\n'
                '  Windows:       powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/itsddvn/ezyplatform-cli/main/install.ps1 | iex"')


def latest_version():
    """Version of the latest release, e.g. '0.1.1', from the releases/latest redirect."""
    req = urllib.request.Request(REPO + '/releases/latest', method='HEAD', headers={'User-Agent': 'ezy/' + __version__})
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


def main(args):
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
    if os.name == 'nt':
        line = subprocess.list2cmdline(command)
        subprocess.Popen(['cmd', '/c', f'timeout /t 2 /nobreak >nul & {line} & pause'],
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
        print('The update continues in a new window; open a new terminal when it is done.')
        return 0
    code = subprocess.call(command)
    if code == 0:
        print(f'ezy updated to {latest}')
    return code
