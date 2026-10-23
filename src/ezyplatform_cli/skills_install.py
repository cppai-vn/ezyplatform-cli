"""`ezy skills`: copy the bundled ezy-* skills for agents that cannot install plugins.

A copy goes only into a folder that no plugin-capable agent reads, so an agent
never sees the skills twice (~/.agents/skills is read by Codex, Cursor, Copilot
and oh-my-pi; ~/.claude/skills by Claude Code). Each copy gets a manifest
(ezy-shared/.ezy-install.json) with the version and file hashes, used by
verify, update and remove; copies are also recorded in ezy's state file.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

from . import __version__, agents
from .status_output import print_status

SKILLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills')
MANIFEST = os.path.join('ezy-shared', '.ezy-install.json')

# agents without plugin support -> their own skill folder
TARGETS = {'opencode': {'label': 'OpenCode', 'exe': 'opencode', 'dir': '~/.config/opencode/skills'}}
# skill folders each agent reads (from the agents' docs), used to find duplicates
READS = {
    'claude': ['~/.claude/skills'],
    'codex': ['~/.agents/skills', '~/.codex/skills'],
    'copilot': ['~/.copilot/skills', '~/.claude/skills', '~/.agents/skills'],
    'cursor': ['~/.cursor/skills', '~/.agents/skills'],
    'omp': ['~/.omp/agent/skills', '~/.agents/skills'],
    'opencode': ['~/.config/opencode/skills', '~/.claude/skills', '~/.agents/skills'],
}


def expand(path):
    """Comparable absolute path: symlinks resolved, case folded where the OS ignores case."""
    return os.path.normcase(os.path.realpath(os.path.expanduser(path)))


def state_path():
    base = os.environ.get('APPDATA') if os.name == 'nt' else os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
    return os.path.join(base or os.path.expanduser('~'), 'ezy', 'state.json')


def load_state():
    try:
        with open(state_path(), encoding='utf-8') as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def save_state(state):
    path = state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + '.tmp', 'w', encoding='utf-8') as fh:
        json.dump(state, fh, indent=2)
    os.replace(path + '.tmp', path)


def record_copy(dest, present):
    state = load_state()
    copies = set(state.get('skill_copies') or [])
    state['skill_copies'] = sorted(copies | {dest} if present else copies - {dest})
    save_state(state)


def bundled_info():
    try:
        with open(os.path.join(SKILLS, 'VENDORED.json'), encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def skill_names(root):
    return sorted(n for n in os.listdir(root) if n.startswith('ezy-') and os.path.isdir(os.path.join(root, n))) if os.path.isdir(root) else []


def file_hashes(root, names=None):
    hashes = {}
    for name in skill_names(root) if names is None else names:
        for folder, dirs, files in os.walk(os.path.join(root, name)):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for f in files:
                if f.endswith('.pyc') or f == '.ezy-install.json':
                    continue
                path = os.path.join(folder, f)
                with open(path, 'rb') as fh:
                    hashes[os.path.relpath(path, root).replace(os.sep, '/')] = hashlib.sha256(fh.read()).hexdigest()
    return hashes


def read_manifest(dest):
    try:
        with open(os.path.join(dest, MANIFEST), encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def installed_names(dest):
    """Skill folders that ezy copied into `dest`, from its manifest (never the user's own ezy-* skills)."""
    manifest = read_manifest(dest) or {}
    return sorted({f.split('/', 1)[0] for f in manifest.get('files', {})} | {'ezy-shared'} if manifest else set())


def remove_entry(path):
    if os.path.islink(path) or os.path.isfile(path):
        os.unlink(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


def has_skills(dest):
    return os.path.isfile(os.path.join(dest, 'ezy-guide', 'SKILL.md'))


def plugin_readers(dest):
    """Labels of agents that read `dest` and already have the plugin (installing there would duplicate)."""
    found = []
    for name, dirs in READS.items():
        if name in agents.AGENTS and dest in [expand(d) for d in dirs] and agents.plugin_installed(name):
            found.append(agents.AGENTS[name]['label'])
    return found


def verify(dest):
    """'ok', 'missing', 'not installed by ezy', 'outdated (x -> y)' or 'modified (n files)'."""
    if not has_skills(dest):
        return 'missing'
    manifest = read_manifest(dest)
    if not manifest:
        return 'not installed by ezy'
    current = file_hashes(dest, installed_names(dest))
    changed = [f for f, h in manifest.get('files', {}).items() if current.get(f) != h]
    if changed:
        return f'modified ({len(changed)} files)'
    bundled = bundled_info().get('version')
    if manifest.get('version') != bundled or manifest.get('files') != file_hashes(SKILLS):
        return f"outdated ({manifest.get('version')} -> {bundled})"
    return 'ok'


def install_to(dest, force=False):
    """Copy the bundled skills into `dest`; replaces only ezy's own earlier copy (or, with --force, same-named folders)."""
    if dest == expand(SKILLS):
        print_status(f'{dest} is the skills bundled with ezy itself', False)
        return False
    readers = plugin_readers(dest)
    if readers and not force:
        print_status(f'{dest}: also read by {", ".join(readers)}, which already has the plugin; '
                     'the skills would appear twice there (--force to copy anyway)', False)
        return False
    bundled = skill_names(SKILLS)
    ours = installed_names(dest)
    foreign = [n for n in bundled if os.path.lexists(os.path.join(dest, n)) and n not in ours]
    if foreign and not force:
        print_status(f'{dest}: has skills with the same names that ezy did not install ({", ".join(foreign)}); '
                     '--force to replace them', False)
        return False
    # copy next to the destination first, so a failed copy leaves the old skills in place
    staging = os.path.join(dest, '.ezy-staging')
    remove_entry(staging)
    os.makedirs(staging)
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc')
    try:
        for name in bundled:
            shutil.copytree(os.path.join(SKILLS, name), os.path.join(staging, name), ignore=ignore)
    except OSError as err:
        remove_entry(staging)
        print_status(f'{dest}: copy failed ({err}); the existing skills are unchanged', False)
        return False
    for name in sorted(set(ours) | set(foreign)):
        remove_entry(os.path.join(dest, name))
    for name in bundled:
        os.replace(os.path.join(staging, name), os.path.join(dest, name))
    remove_entry(staging)
    info = bundled_info()
    manifest = {'version': info.get('version'), 'commit': info.get('commit'), 'ezy': __version__,
                'files': file_hashes(dest, bundled)}
    with open(os.path.join(dest, MANIFEST), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, indent=1)
    record_copy(dest, True)
    result = verify(dest)
    print_status(f"{dest}: ezyplatform skills {info.get('version')} ({result})", result == 'ok')
    return result == 'ok'


def remove_from(dest):
    names = installed_names(dest)
    if not names:
        print_status(f'{dest}: no skills installed by ezy')
        return False
    for name in names:
        remove_entry(os.path.join(dest, name))
    record_copy(dest, False)
    print_status(f'{dest}: ezy-* skills removed', True)
    return True


def known_dirs():
    dirs = {expand(t['dir']) for t in TARGETS.values()}
    dirs |= {expand(d) for paths in READS.values() for d in paths}
    dirs |= set(load_state().get('skill_copies', []))
    return sorted(dirs)


def copies():
    """[(dir, verify result)] for every known folder that holds the ezy skills."""
    return [(d, verify(d)) for d in known_dirs() if has_skills(d)]


def default_dests():
    return [expand(t['dir']) for t in TARGETS.values() if shutil.which(t['exe'])]


def resolve_dests(opts):
    if opts.dir:
        return [expand(opts.dir)]
    if opts.target:
        names = list(TARGETS) if opts.target == 'all' else [t.strip() for t in opts.target.split(',')]
        unknown = [n for n in names if n not in TARGETS]
        if unknown:
            raise SystemExit(f"ezy: skills target must be {', '.join(TARGETS)} or --dir PATH "
                             f"(agents with plugins use: ezy plugins install); got {', '.join(unknown)}")
        return [expand(TARGETS[n]['dir']) for n in names]
    return None


def main(args):
    parser = argparse.ArgumentParser(prog='ezy skills', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=['status', 'install', 'verify', 'remove'])
    parser.add_argument('--target', help=f"{', '.join(TARGETS)} or all (default: those found on this computer)")
    parser.add_argument('--dir', help='another skills folder, for agents not listed (e.g. Windsurf, Kiro)')
    parser.add_argument('--force', action='store_true', help='copy even where it would duplicate a plugin')
    opts = parser.parse_args(args)
    dests = resolve_dests(opts)
    if opts.action in ('status', 'verify'):
        found = [(d, verify(d)) for d in dests] if dests else copies()
        if not found:
            print_status('no ezy skill copies on this computer (agents with plugins do not need them)')
            return 0
        for dest, result in found:
            print_status(f'{dest:50} {result}', result == 'ok')
        return 0 if all(r == 'ok' for _, r in found) else 1
    if opts.action == 'remove':
        targets = dests or [d for d, _ in copies() if read_manifest(d)]
        return 0 if all([remove_from(d) for d in targets]) else 1
    dests = dests or default_dests()
    if not dests:
        print('No agent without plugin support was found (' + ', '.join(t['label'] for t in TARGETS.values())
              + '). Agents with plugins: ezy plugins install. Another agent: ezy skills install --dir <its skills folder>')
        return 0
    return 0 if all([install_to(d, opts.force) for d in dests]) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
