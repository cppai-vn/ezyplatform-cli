"""`ezy init`: set up this computer for EzyPlatform work.

1. find the coding agents installed here
2. install the ezyplatform plugin into the ones you pick
3. offer skill copies for agents without plugin support (never where a plugin already loads them)
4. validate what was installed, then run `ezy doctor`

Creating a site project is `ezy new <dir> --admin-url URL`.
"""
import argparse
import sys

from . import agents, doctor, skills_install
from .status_output import print_status


def ask(question, assume_yes, default=True):
    if assume_yes:
        print(f'{question} {"yes" if default else "no"} (--yes)')
        return default
    if not sys.stdin.isatty():
        print(f'{question} {"yes" if default else "no"} (no terminal, default)')
        return default
    answer = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    return default if not answer else answer in ('y', 'yes')


def main(args):
    parser = argparse.ArgumentParser(prog='ezy init', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--yes', '-y', action='store_true', help='accept the defaults without asking')
    parser.add_argument('--target', default='all', help=f"agents for the plugin: all or {','.join(agents.NAMES)}")
    skills = parser.add_mutually_exclusive_group()
    skills.add_argument('--skills', dest='skills', action='store_true', default=None, help='copy skills without asking')
    skills.add_argument('--no-skills', dest='skills', action='store_false', help='do not copy skills')
    parser.add_argument('--dry-run', action='store_true', help='show what would be done')
    opts, extra = parser.parse_known_args(args)
    if extra:
        # a folder or --admin-url: the old `ezy init <dir>`, which is now `ezy new`
        print('ezy init now sets up this computer (plugins, skills, doctor).\n'
              'To create a site project use: ezy new ' + ' '.join(extra), file=sys.stderr)
        return 2

    print('1. Coding agents on this computer')
    names = agents.parse_targets(opts.target)
    rows = agents.status_rows(names, progress=True)
    found = [r[0] for r in rows if r[2]]

    print('\n2. Plugin ezyplatform@cppai')
    todo = [r[0] for r in rows if r[2] and r[3] is not True and not agents.AGENTS[r[0]].get('manual')]
    for name in [n for n in found if agents.AGENTS[n].get('manual')]:
        print(f'  - {agents.AGENTS[name]["label"]}: {agents.CURSOR_STEPS}')
    installed = []
    if not found:
        print('  no supported coding agent found (Claude Code, Codex, Copilot CLI, oh-my-pi, Cursor)')
    elif not todo:
        print('  already installed everywhere it can be')
    elif ask('  Install it for ' + ', '.join(agents.AGENTS[n]['label'] for n in todo) + '?', opts.yes):
        installed = [n for n in todo if agents.install(n, opts.dry_run) == 'new']

    print('\n3. Skill copies (only for agents without plugin support)')
    dests = skills_install.default_dests()
    copied = []
    if not dests:
        print('  not needed: no agent without plugin support was found (OpenCode)')
    else:
        labels = ', '.join(t['label'] for t in skills_install.TARGETS.values() if skills_install.expand(t['dir']) in dests)
        want = opts.skills if opts.skills is not None else ask(f'  Copy the ezy skills for {labels}?', opts.yes)
        for dest in dests if want else []:
            if opts.dry_run:
                print(f'  would copy the skills to {dest}')
            elif skills_install.install_to(dest):
                copied.append(dest)

    if opts.dry_run:
        print('\ndry run: nothing was changed')
        return 0
    print('\n4. Validate')
    ok = True
    for name in installed:
        state = agents.plugin_installed(name)
        ok &= bool(state)
        print_status(f"{agents.AGENTS[name]['label']}: plugin {'listed' if state else 'not listed'}", bool(state))
    for dest in copied:
        result = skills_install.verify(dest)
        ok &= result == 'ok'
        print_status(f'{dest}: {result}', result == 'ok')
    if not installed and not copied:
        print('  nothing new was installed')

    print('\n5. Doctor\n')
    code = doctor.main([])
    if installed or copied:
        print('\nStart a new session in your agents to load the skills. Create a site project with: '
              'ezy new my-site --admin-url https://admin.example.com')
    return 0 if ok and code == 0 else 1
