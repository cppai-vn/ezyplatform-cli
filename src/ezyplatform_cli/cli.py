"""`ezy`: set up EzyPlatform projects and manage coding-agent plugins and skills.

Site content operations belong to the installed plugin. Bundled scripts remain
available for project setup and for copying the full skill set into agents.
"""
import importlib
import json
import os
import sys

from . import __version__
from .status_output import print_status

SKILLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills')

NEW = 'ezy-new/scripts/ezy_new.py'
CLIENT = 'ezy-shared/ezy_client.py'

# command -> (script, fixed leading arguments, program name shown in usage)
COMMANDS = {
    'check': (NEW, ['check'], 'ezy check'),
    'token': (NEW, ['token-help'], 'ezy token'),
    'whoami': (CLIENT, ['whoami'], 'ezy whoami'),
}

# Give users of previous versions a useful handoff without executing site work.
PLUGIN_COMMANDS = {
    'get': 'ezy-guide',
    'content': 'ezy-guide',
    'sync': 'ezy-sync',
    'status': 'ezy-sync',
    'pull': 'ezy-sync',
    'pull-all': 'ezy-sync',
    'publish': 'ezy-publish',
    'media': 'ezy-media',
    'i18n': 'ezy-i18n',
    'verify': 'ezy-verify',
    'mail': 'ezy-mail',
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

HELP = """ezy — project setup and agent management (ezyplatform skills {skills})

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

Tool
  update                         latest ezy release, then refresh plugins and skill copies
  uninstall [--yes]              remove ezy (site projects are kept)
  --version

For content, sync, publishing, media, translations, mail and previews, use the
ezyplatform plugin in your coding agent. Run ezy init to set up the agent.
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
    print_status(exc.code, False, file=sys.stderr)
    return 1


def safe_output():
    """Never crash on ✓ and other non-ASCII output in a cp1252 Windows console or pipe."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace')
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    safe_output()
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
    if argv[0] == 'whoami' and argv[1:] in (['-h'], ['--help']):
        print('usage: ezy whoami\n\nShow the configured environment, admin URL and token owner roles (JSON).')
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
        if argv[0] in PLUGIN_COMMANDS:
            print_status(f"ezy: '{argv[0]}' is handled by the ezyplatform plugin. "
                         f"Use the {PLUGIN_COMMANDS[argv[0]]} skill in your coding agent; "
                         "run 'ezy init' to set it up.", False, file=sys.stderr)
            return 2
        print(f"ezy: unknown command '{argv[0]}'. Run 'ezy --help'.", file=sys.stderr)
        return 2
    script, fixed, prog = COMMANDS[argv[0]]
    try:
        return run_script(script, fixed + argv[1:], prog)
    except KeyboardInterrupt:
        return 130
    except OSError as err:
        # URLError and socket errors: the scripts only catch HTTP errors from the server
        print_status(f"ezy: cannot reach the admin server: {getattr(err, 'reason', err)}", False, file=sys.stderr)
        print("  check admin_url in environment.json, then run 'ezy check'", file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
