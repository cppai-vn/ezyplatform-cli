"""`ezy`: one command for the ezy-* EzyPlatform skills.

Each command runs the matching skill script bundled in `skills/` with the same
arguments, so behaviour, dry runs and safety checks are exactly the plugin's.
"""
import importlib
import json
import os
import sys

from . import __version__

SKILLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills')

NEW = 'ezy-new/scripts/ezy_new.py'
CLIENT = 'ezy-shared/ezy_client.py'
SYNC = 'ezy-sync/scripts/ezy_sync.py'
PUBLISH = 'ezy-publish/scripts/ezy_publish.py'

# command -> (script, fixed leading arguments, program name shown in usage)
COMMANDS = {
    'check': (NEW, ['check'], 'ezy check'),
    'token': (NEW, ['token-help'], 'ezy token'),
    'whoami': (CLIENT, ['whoami'], 'ezy whoami'),
    'get': (CLIENT, ['get'], 'ezy get'),
    'sync': (SYNC, [], 'ezy sync'),
    'status': (SYNC, ['status'], 'ezy sync'),
    'pull': (SYNC, ['pull'], 'ezy sync'),
    'pull-all': (SYNC, ['pull-all'], 'ezy sync'),
    'publish': (PUBLISH, [], 'ezy publish'),
    'media': ('ezy-media/scripts/ezy_media.py', [], 'ezy media'),
    'i18n': ('ezy-i18n/scripts/ezy_messages.py', [], 'ezy i18n'),
    'verify': ('ezy-verify/scripts/ezy_verify.py', [], 'ezy verify'),
    'mail': ('ezy-mail/scripts/ezy_mail.py', [], 'ezy mail'),
}

# command -> (module, function) for commands that manage ezy and the agents
TOOLS = {
    'init': ('setup_wizard', 'main'),
    'new': ('project_new', 'main'),
    'plugins': ('agents', 'main'),
    'skills': ('skills_install', 'main'),
    'doctor': ('doctor', 'main'),
    'update': ('self_update', 'update'),
    'upgrade': ('self_update', 'update'),
    'uninstall': ('self_update', 'uninstall'),
}

HELP = """ezy — EzyPlatform / EzyArticle site tools (ezyplatform skills {skills})

Usage: ezy <command> [args]      ezy <command> --help for details

Setup (this computer)
  init [--yes] [--target ...]    install the plugin into your coding agents, optional skills, then doctor
  plugins status|install|update  the ezyplatform plugin per agent (claude, codex, copilot, omp, cursor)
  skills status|install|verify|remove   skill copies for agents without plugins (opencode, --dir)
  doctor                         check ezy, agents, plugin/skill duplicates and the current project

Project
  new [dir] [--mode live|local|both] [--admin-url URL]
                                 create a site project; local runs EzyPlatform + MySQL in Docker
  token [admin_url]              how to get the admin access token
  check [dir]                    validate environment.json and the connection
  whoami                         roles of the token owner
  get <api-path>                 GET an admin API path (redacted JSON)

Content (server -> local)
  sync status|pull|pull-all|discover-pages
  status [target ...]            shortcut for: sync status
  pull <target> [--lang L] [--write]
  pull-all [--langs en,vi] [--write]

Publish (local -> server, dry run unless --yes)
  publish plan|apply|restore|remove
  media status|upload|public|unpublic|url
  i18n diff|push <web|admin>
  mail status|templates|pull|push|contact-settings|test-contact

Check
  verify preview <slug> | verify live [path] [--expect TEXT]

Tool
  update                         latest ezy release, then refresh plugins and skill copies
  uninstall [--yes]              remove ezy (site projects are kept)
  --version

Targets: page:<slug> | fragment:<page_name>/<fragment_name>
Docs: https://github.com/cppai-vn/ezyplatform-cli
"""


def skills_info():
    try:
        with open(os.path.join(SKILLS, 'VENDORED.json'), encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def run_script(script, args, prog):
    """Run a bundled script as __main__ so its own argparse, output and exit codes are used."""
    path = os.path.join(SKILLS, script)
    saved = sys.argv[:]
    sys.argv = [prog] + args
    with open(path, encoding='utf-8') as fh:
        compiled = compile(fh.read(), path, 'exec')
    try:
        # exec instead of runpy.run_path, which would reset argv[0] to the script path
        exec(compiled, {'__name__': '__main__', '__file__': path, '__builtins__': __builtins__})
    except SystemExit as exc:
        return exit_code(exc)
    finally:
        sys.argv = saved
    return 0


def exit_code(exc):
    """Exit status of a SystemExit; a message is printed and counts as 1."""
    if exc.code is None or isinstance(exc.code, int):
        return exc.code or 0
    print(exc.code, file=sys.stderr)
    return 1


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    info = skills_info()
    if not argv or argv[0] in ('-h', '--help', 'help'):
        print(HELP.format(skills=info.get('version', '?')))
        return 0
    if argv[0] in ('-V', '--version', 'version'):
        print(f"ezy {__version__} (ezyplatform skills {info.get('version', '?')}"
              f"{', ' + info['commit'] if info.get('commit') else ''})")
        return 0
    if argv[0] == 'skills-path':
        print(SKILLS)
        return 0
    if argv[0] in TOOLS:
        module, func = TOOLS[argv[0]]
        try:
            return getattr(importlib.import_module('.' + module, __package__), func)(argv[1:])
        except SystemExit as exc:
            return exit_code(exc)
        except KeyboardInterrupt:
            return 130
    if argv[0] not in COMMANDS:
        print(f"ezy: unknown command '{argv[0]}'. Run 'ezy --help'.", file=sys.stderr)
        return 2
    script, fixed, prog = COMMANDS[argv[0]]
    try:
        return run_script(script, fixed + argv[1:], prog)
    except KeyboardInterrupt:
        return 130
    except OSError as err:
        # URLError and socket errors: the scripts only catch HTTP errors from the server
        print(f"ezy: cannot reach the admin server: {getattr(err, 'reason', err)}\n"
              "     check admin_url in environment.json, then run 'ezy check'", file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
