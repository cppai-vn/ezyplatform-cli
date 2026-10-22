"""Make sure Docker and Docker Compose are installed and running, installing them when missing.

macOS: OrbStack through Homebrew (what the team uses for ezyplatform-docker).
Linux: Docker Engine + Compose plugin from the official get.docker.com script (sudo).
Windows: Docker Desktop through winget; the user starts it and accepts its terms.
Every install asks first unless --yes was given.
"""
import os
import platform
import shutil
import subprocess
import sys
import time

DAEMON_WAIT_SECONDS = 180


def _ok(argv):
    exe = shutil.which(argv[0])
    if not exe:
        return False
    try:
        return subprocess.run([exe] + argv[1:], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def state():
    """'missing' (no docker CLI), 'no-compose', 'stopped' (daemon not reachable) or 'ready'."""
    if not shutil.which('docker'):
        return 'missing'
    if not _ok(['docker', 'compose', 'version']):
        return 'no-compose'
    if not _ok(['docker', 'info']):
        return 'stopped'
    return 'ready'


def _system():
    return {'Darwin': 'mac', 'Windows': 'windows'}.get(platform.system(), 'linux')


def install_commands(system=None):
    """Shell steps that install Docker + Compose on this OS (None when they cannot be automated)."""
    system = system or _system()
    if system == 'mac':
        return [['brew', 'install', '--cask', 'orbstack']] if shutil.which('brew') else None
    if system == 'windows':
        return [['winget', 'install', '-e', '--id', 'Docker.DockerDesktop']] if shutil.which('winget') else None
    if not shutil.which('curl'):
        return None
    return [['sh', '-c', 'curl -fsSL https://get.docker.com | sudo sh'],
            ['sudo', 'systemctl', 'enable', '--now', 'docker']]


def start_commands(system=None):
    system = system or _system()
    if system == 'mac':
        app = 'OrbStack' if os.path.isdir('/Applications/OrbStack.app') else 'Docker'
        return [['open', '-a', app]]
    if system == 'windows':
        desktop = os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'Docker', 'Docker', 'Docker Desktop.exe')
        return [[desktop]] if os.path.isfile(desktop) else []
    return [['sudo', 'systemctl', 'start', 'docker']]


MANUAL = {
    'mac': 'Install OrbStack (https://orbstack.dev/download) or Docker Desktop, start it, then run this again.',
    'windows': 'Install Docker Desktop (https://docs.docker.com/desktop/setup/install/windows-install/), '
               'start it and accept its terms, then run this again.',
    'linux': 'Install Docker Engine with the Compose plugin (https://docs.docker.com/engine/install/), then run this again.',
}


def _run_steps(steps):
    for argv in steps:
        print('  $ ' + ' '.join(argv), flush=True)
        try:
            if subprocess.call(argv) != 0:
                return False
        except OSError as err:
            print(f'  x {err}')
            return False
    return True


def _wait_ready():
    deadline = time.time() + DAEMON_WAIT_SECONDS
    while time.time() < deadline:
        if state() == 'ready':
            return True
        time.sleep(3)
    return False


def ensure(ask):
    """True when Docker + Compose are ready; installs or starts them after `ask(question)` agrees."""
    current = state()
    if current == 'ready':
        return True
    system = _system()
    if current in ('missing', 'no-compose'):
        steps = install_commands(system)
        what = 'Docker' if current == 'missing' else 'Docker Compose'
        if not steps:
            print(f'  x {what} is not installed and cannot be installed automatically here. {MANUAL[system]}')
            return False
        if not ask(f'  {what} is not installed. Install it now ({" && ".join(" ".join(s) for s in steps)})?'):
            print(f'  {MANUAL[system]}')
            return False
        if not _run_steps(steps):
            print(f'  x install failed. {MANUAL[system]}')
            return False
        current = state()
        if current in ('missing', 'no-compose'):
            print('  ! installed; open a new terminal so docker is on your PATH, then run this again')
            return False
    if current == 'stopped':
        print('  Docker is installed but not running; starting it...', flush=True)
        _run_steps(start_commands(system))
        if system == 'windows':
            print('  Docker Desktop: accept its terms in its window if it asks; waiting for it to start...')
        if not _wait_ready():
            hint = ('if docker needs sudo, run: sudo usermod -aG docker $USER, then log out and in'
                    if system == 'linux' else 'start Docker (OrbStack / Docker Desktop) yourself')
            print(f'  x Docker did not become ready within {DAEMON_WAIT_SECONDS}s; {hint}, then run this again')
            return False
    print('  ✓ Docker and Docker Compose are ready')
    return True


if __name__ == '__main__':
    print(state())
    sys.exit(0)
