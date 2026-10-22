"""`ezy new`: create a site project connected to the live site, a local EzyPlatform, or both.

live   the project talks to an existing EzyPlatform admin (as before)
local  Docker Compose runs EzyPlatform + MySQL for this project; Docker and
       Docker Compose are checked first and installed when missing
both   both environments; `local` is the default, the live one is used with
       EZY_ENV=production (so nothing reaches the live site by accident)
"""
import argparse
import json
import os
import sys

from . import docker_setup, local_stack

MODES = ('live', 'local', 'both')
TOKEN_PLACEHOLDER = '<Your admin access token>'


def ask_yes(question, assume_yes):
    if assume_yes:
        print(f'{question} yes (--yes)')
        return True
    if not sys.stdin.isatty():
        print(f'{question} no (no terminal to ask; re-run with --yes to allow it)')
        return False
    answer = input(f'{question} [Y/n] ').strip().lower()
    return answer in ('', 'y', 'yes')


def ask_mode():
    if not sys.stdin.isatty():
        return 'live'
    print('Where should this project run?\n'
          '  1) live   connect to an existing EzyPlatform site\n'
          '  2) local  run EzyPlatform + MySQL on this computer with Docker\n'
          '  3) both   local for development, plus the live site')
    while True:
        answer = input('Choose 1, 2 or 3 [1]: ').strip().lower() or '1'
        choice = {'1': 'live', '2': 'local', '3': 'both'}.get(answer, answer)
        if choice in MODES:
            return choice


def set_environments(root, mode, admin_url):
    """Add the `local` entry to environment.json (default for local and both)."""
    path = os.path.join(root, 'environment.json')
    with open(path, encoding='utf-8') as fh:
        envs = json.load(fh)
    envs = [e for e in envs if e.get('name') != 'local']
    if mode == 'local':
        envs = []  # no live site: the production/beta placeholders would only confuse ezy check
    for env in envs:
        env['default'] = False
    envs.insert(0, {'name': 'local', 'default': True, 'admin_url': admin_url,
                    'admin_access_token': TOKEN_PLACEHOLDER,
                    'notes': 'Local EzyPlatform from docker-compose.yml. Live site: EZY_ENV=production ezy ...'})
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(envs, fh, indent=2)
        fh.write('\n')
    os.chmod(path, 0o600)


def main(args):
    from .cli import NEW, run_script
    parser = argparse.ArgumentParser(prog='ezy new', description=__doc__, add_help=False,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--mode', choices=MODES, help='live, local or both (asked when omitted)')
    parser.add_argument('--yes', '-y', action='store_true', help='install or start Docker without asking')
    parser.add_argument('--no-start', action='store_true', help='write docker-compose.yml but do not start it')
    opts, rest = parser.parse_known_args(args)
    if '-h' in rest or '--help' in rest:
        parser.print_help()
        print('\nProject options (all modes):')
        return run_script(NEW, ['create', '--help'], 'ezy new')
    project = argparse.ArgumentParser(add_help=False)
    project.add_argument('target', nargs='?', default='.')
    project.add_argument('--admin-url')
    target = project.parse_known_args(rest)[0]
    mode = opts.mode or ask_mode()
    root = os.path.abspath(target.target)
    if mode == 'live':
        return run_script(NEW, ['create'] + rest, 'ezy new')

    # ports and passwords first, so the project's instructions name the local admin
    os.makedirs(root, exist_ok=True)
    report = []
    env = local_stack.write_files(root, report)
    admin, web = local_stack.urls(env)
    if mode == 'local':
        print('Mode: local (EzyPlatform + MySQL in Docker on this computer)\n')
        if not target.admin_url:
            rest = rest + ['--admin-url', admin]
    else:
        print('Mode: both (local is the default environment; the live site with EZY_ENV=production)\n')
    code = run_script(NEW, ['create'] + rest, 'ezy new')
    if code != 0:
        return code

    print('\nLocal EzyPlatform')
    print('\n'.join(report))
    set_environments(root, mode, admin)
    print("  ~ environment.json ('local' environment is the default)")
    if opts.no_start:
        print(f'\nStart it later in {root}: docker compose up -d')
        return 0
    if not docker_setup.ensure(lambda q: ask_yes(q, opts.yes)) or not local_stack.start(root, env):
        print(f'\nWhen Docker is ready, start it in {root}: docker compose up -d')
        return 1
    print(f"""
Next: connect ezy to the local admin
  1. Open {admin}/setup-admin and create the first super admin account.
  2. Sign in, open {admin}/admins/me, reveal "Access Token" (confirm with your password).
  3. Paste it yourself into {os.path.join(root, 'environment.json')}
     -> the "local" entry -> "admin_access_token". Do not send it in chat.
  4. cd {target.target} && ezy check
Website: {web}   Stop: docker compose stop   Start again: docker compose up -d""")
    if mode == 'both':
        print('Live site: fill in the "production" entry the same way, then run commands with EZY_ENV=production.')
    return 0
