"""`ezy`: one command for the ezy-* EzyPlatform skills.

Each command runs the matching skill script bundled in `skills/` with the same
arguments, so behaviour, dry runs and safety checks are exactly the plugin's.
"""
import importlib
import json
import os
import sys
from collections import namedtuple

from . import __version__

SKILLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills')

NEW = 'ezy-new/scripts/ezy_new.py'
CLIENT = 'ezy-shared/ezy_client.py'
SYNC = 'ezy-sync/scripts/ezy_sync.py'
PUBLISH = 'ezy-publish/scripts/ezy_publish.py'

Command = namedtuple('Command', 'names usage summary run')

HEADER = """ezy — EzyPlatform / EzyArticle site tools (ezyplatform skills {skills})

Usage: ezy <command> [args]      ezy <command> --help for details
"""

FOOTER = """Targets: page:<slug> | fragment:<page_name>/<fragment_name>
Docs: https://github.com/cppai-vn/ezyplatform-cli
"""

USAGE_WIDTH = 31


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


def safe_output():
    """Never crash on ✓ and other non-ASCII output in a cp1252 Windows console or pipe."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace')
        except (AttributeError, ValueError):
            pass


def script(path, *fixed, prog):
    def run(args):
        try:
            return run_script(path, list(fixed) + args, prog)
        except OSError as err:
            # URLError and socket errors: the scripts only catch HTTP errors from the server
            print(f"ezy: cannot reach the admin server: {getattr(err, 'reason', err)}\n"
                  "     check admin_url in environment.json, then run 'ezy check'", file=sys.stderr)
            return 2
    run.script = path
    return run


def tool(module, func):
    def run(args):
        return getattr(importlib.import_module('.' + module, __package__), func)(args)
    return run


def show_help(args):
    print(help_text())
    return 0


def show_version(args):
    info = skills_info()
    print(f"ezy {__version__} (ezyplatform skills {info.get('version', '?')}"
          f"{', ' + info['commit'] if info.get('commit') else ''})")
    return 0


def show_skills_path(args):
    print(SKILLS)
    return 0


GROUPS = [
    ('Setup (this computer)', [
        Command(('init',), 'init [--yes] [--target ...]',
                'install the plugin into your coding agents, optional skills, then doctor', tool('setup_wizard', 'main')),
        Command(('plugins',), 'plugins status|install|update',
                'the ezyplatform plugin per agent (claude, codex, copilot, omp, cursor)', tool('agents', 'main')),
        Command(('skills',), 'skills status|install|verify|remove',
                'skill copies for agents without plugins (opencode, --dir)', tool('skills_install', 'main')),
        Command(('doctor',), 'doctor',
                'check ezy, agents, plugin/skill duplicates and the current project', tool('doctor', 'main')),
    ]),
    ('Project', [
        Command(('new',), 'new [dir] [--mode live|local|both] [--admin-url URL]',
                'create a site project; local runs EzyPlatform + MySQL in Docker', tool('project_new', 'main')),
        Command(('token',), 'token [admin_url]',
                'how to get the admin access token', script(NEW, 'token-help', prog='ezy token')),
        Command(('check',), 'check [dir]',
                'validate environment.json and the connection', script(NEW, 'check', prog='ezy check')),
        Command(('whoami',), 'whoami', 'roles of the token owner', script(CLIENT, 'whoami', prog='ezy whoami')),
        Command(('get',), 'get <api-path>',
                'GET an admin API path (redacted JSON)', script(CLIENT, 'get', prog='ezy get')),
    ]),
    ('Content (server -> local)', [
        Command(('sync',), 'sync status|pull|pull-all|discover-pages', '', script(SYNC, prog='ezy sync')),
        Command(('status',), 'status [target ...]',
                'shortcut for: sync status', script(SYNC, 'status', prog='ezy sync')),
        Command(('pull',), 'pull <target> [--lang L] [--write]', '', script(SYNC, 'pull', prog='ezy sync')),
        Command(('pull-all',), 'pull-all [--langs en,vi] [--write]', '', script(SYNC, 'pull-all', prog='ezy sync')),
    ]),
    ('Publish (local -> server, dry run unless --yes)', [
        Command(('publish',), 'publish plan|apply|restore|remove', '', script(PUBLISH, prog='ezy publish')),
        Command(('media',), 'media status|upload|public|unpublic|url', '',
                script('ezy-media/scripts/ezy_media.py', prog='ezy media')),
        Command(('i18n',), 'i18n diff|push <web|admin>', '',
                script('ezy-i18n/scripts/ezy_messages.py', prog='ezy i18n')),
        Command(('mail',), 'mail status|templates|pull|push|contact-settings|test-contact', '',
                script('ezy-mail/scripts/ezy_mail.py', prog='ezy mail')),
    ]),
    ('Check', [
        Command(('verify',), 'verify preview <slug> | verify live [path] [--expect TEXT]', '',
                script('ezy-verify/scripts/ezy_verify.py', prog='ezy verify')),
    ]),
    ('Tool', [
        Command(('update', 'upgrade'), 'update',
                'latest ezy release, then refresh plugins and skill copies', tool('self_update', 'update')),
        Command(('uninstall',), 'uninstall [--yes]',
                'remove ezy (site projects are kept)', tool('self_update', 'uninstall')),
        Command(('--version', '-V', 'version'), '--version', '', show_version),
    ]),
    (None, [
        Command(('--help', '-h', 'help'), '', '', show_help),
        Command(('skills-path',), '', '', show_skills_path),
    ]),
]

COMMANDS = {name: command for _, commands in GROUPS for command in commands for name in command.names}


def help_line(command):
    if not command.summary:
        return f'  {command.usage}'
    if len(command.usage) >= USAGE_WIDTH:
        return f"  {command.usage}\n  {'':{USAGE_WIDTH}}{command.summary}"
    return f'  {command.usage:{USAGE_WIDTH}}{command.summary}'


def help_text():
    sections = [HEADER.format(skills=skills_info().get('version', '?'))]
    for title, commands in GROUPS:
        if title:
            sections.append('\n'.join([title] + [help_line(c) for c in commands if c.usage]) + '\n')
    sections.append(FOOTER)
    return '\n'.join(sections)


def main(argv=None):
    safe_output()
    argv = sys.argv[1:] if argv is None else argv
    command = COMMANDS.get(argv[0] if argv else '--help')
    if command is None:
        print(f"ezy: unknown command '{argv[0]}'. Run 'ezy --help'.", file=sys.stderr)
        return 2
    try:
        return command.run(argv[1:])
    except SystemExit as exc:
        return exit_code(exc)
    except KeyboardInterrupt:
        return 130
    except OSError as err:
        print(f'ezy: {err}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
