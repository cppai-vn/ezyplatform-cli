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

# Agents without native cppai plugin CLI support -> their skill folder & detection rules.
# Antigravity (CLI + IDE) and Gemini CLI both read ~/.gemini/skills natively, so sharing
# that folder installs once for both without duplicate skill loading.
TARGETS = {
    'antigravity': {
        'label': 'Antigravity',
        'exe': 'agy',
        'exes': ('agy', 'antigravity'),
        'apps': ('/Applications/Antigravity.app', '~/Applications/Antigravity.app'),
        'app_dirs': ('~/.gemini/antigravity-cli', '~/.gemini/antigravity'),
        'dir': '~/.gemini/skills',
    },
    'gemini': {
        'label': 'Gemini CLI',
        'exe': 'gemini',
        'exes': ('gemini',),
        'apps': (),
        'app_dirs': (),
        'dir': '~/.gemini/skills',
    },
    'opencode': {
        'label': 'OpenCode',
        'exe': 'opencode',
        'exes': ('opencode',),
        'apps': ('/Applications/OpenCode.app', '~/Applications/OpenCode.app'),
        'app_dirs': ('~/.config/opencode', '~/.opencode'),
        'dir': '~/.config/opencode/skills',
    },
    'windsurf': {
        'label': 'Windsurf',
        'exe': 'windsurf',
        'exes': ('windsurf',),
        'apps': ('/Applications/Windsurf.app', '~/Applications/Windsurf.app'),
        'app_dirs': ('~/.codeium/windsurf',),
        'dir': '~/.codeium/windsurf/skills',
    },
    'kiro': {
        'label': 'Kiro',
        'exe': 'kiro',
        'exes': ('kiro', 'kiro-cli'),
        'apps': ('/Applications/Kiro.app', '~/Applications/Kiro.app'),
        'app_dirs': ('~/.kiro',),
        'dir': '~/.kiro/skills',
    },
    'droid': {
        'label': 'Factory Droid',
        'exe': 'droid',
        'exes': ('droid',),
        'apps': (),
        'app_dirs': (),
        'dir': '~/.factory/skills',
    },
    'pi': {
        'label': 'Pi',
        'exe': 'pi',
        'exes': ('pi',),
        'apps': (),
        'app_dirs': (),
        'dir': '~/.pi/agent/skills',
    },
}

# skill folders each agent reads (from the agents' docs), used to find installations & duplicates
READS = {
    'claude': ['~/.claude/skills'],
    'codex': ['~/.agents/skills', '~/.codex/skills'],
    'copilot': ['~/.copilot/skills', '~/.claude/skills', '~/.agents/skills'],
    'cursor': ['~/.cursor/skills', '~/.agents/skills'],
    'omp': ['~/.omp/agent/skills', '~/.agents/skills'],
    'antigravity': ['~/.gemini/skills', '~/.gemini/antigravity-cli/skills', '~/.gemini/antigravity/skills', '~/.agents/skills'],
    'gemini': ['~/.gemini/skills', '~/.agents/skills'],
    'opencode': ['~/.config/opencode/skills', '~/.claude/skills', '~/.agents/skills'],
    'windsurf': ['~/.codeium/windsurf/skills'],
    'kiro': ['~/.kiro/skills'],
    'droid': ['~/.factory/skills'],
    'pi': ['~/.pi/agent/skills'],
}


def expand(path):
    """Comparable absolute path: symlinks resolved, case folded where the OS ignores case."""
    return os.path.normcase(os.path.realpath(os.path.expanduser(path)))


def target_detected(target):
    """True when a skill-based coding agent is installed on this computer."""
    exes = target.get('exes') or ((target['exe'],) if target.get('exe') else ())
    if any(shutil.which(e) for e in exes):
        return True
    apps = target.get('apps', ())
    if sys.platform == 'darwin' and apps and any(os.path.exists(os.path.expanduser(a)) for a in apps):
        app_dirs = target.get('app_dirs', ())
        return not app_dirs or any(os.path.exists(os.path.expanduser(d)) for d in app_dirs)
    return False


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


def agent_skill_status(name):
    """Return (installed_dir, verify_result) for the first folder read by `name` containing ezy-* skills."""
    for raw in READS.get(name, []):
        dest = expand(raw)
        if has_skills(dest):
            return dest, verify(dest)
    return None, None


def target_status_rows():
    """[(name, label, detected, installed_dir, verify_result)] for all skill-based coding agents."""
    rows = []
    for name, target in TARGETS.items():
        found = target_detected(target)
        installed_dir, result = agent_skill_status(name) if found else (None, None)
        rows.append((name, target['label'], found, installed_dir, result))
    return rows


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
        print_status(f'{dest}: no skills installed by ezy', False)
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
    """Deduplicated skill install folders for all detected skill-based coding agents."""
    dests = []
    seen = set()
    for target in TARGETS.values():
        if not target_detected(target):
            continue
        dest = expand(target['dir'])
        if dest not in seen:
            seen.add(dest)
            dests.append(dest)
    return dests


def resolve_dests(opts):
    if opts.dir:
        return [expand(opts.dir)]
    if opts.target:
        names = list(TARGETS) if opts.target == 'all' else [t.strip() for t in opts.target.split(',') if t.strip()]
        unknown = [n for n in names if n not in TARGETS]
        if unknown:
            raise SystemExit(f"ezy: skills target must be {', '.join(TARGETS)} or --dir PATH "
                             f"(agents with plugins use: ezy plugins install); got {', '.join(unknown)}")
        dests = []
        for n in names:
            d = expand(TARGETS[n]['dir'])
            if d not in dests:
                dests.append(d)
        return dests
    return None


def main(args):
    parser = argparse.ArgumentParser(prog='ezy skills', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=['status', 'install', 'verify', 'remove'])
    parser.add_argument('--target', help=f"{', '.join(TARGETS)} or all (default: those found on this computer)")
    parser.add_argument('--dir', help='another skills folder, for agents not listed')
    parser.add_argument('--force', action='store_true', help='copy even where it would duplicate a plugin')
    opts = parser.parse_args(args)
    dests = resolve_dests(opts)
    if opts.action in ('status', 'verify'):
        found = [(d, verify(d)) for d in dests] if dests else copies()
        detected_agents = [row for row in target_status_rows() if row[2]] if not dests else []
        if not found and not detected_agents:
            print_status('no ezy skill copies on this computer (agents with plugins do not need them)')
            return 0
        ok = True
        for dest, result in found:
            print_status(f'{dest:50} {result}', result == 'ok')
            ok &= result == 'ok'
        if detected_agents and opts.action == 'status':
            for _, label, _, installed_dir, result in detected_agents:
                if installed_dir:
                    print_status(f'{label:20} ezy-* skills {result} ({installed_dir})', result == 'ok')
                    ok &= result == 'ok'
                else:
                    print_status(f'{label:20} ezy-* skills not installed (ezy skills install)', False)
                    ok = False
        return 0 if ok else 1
    if opts.action == 'remove':
        targets = dests or [d for d, _ in copies() if read_manifest(d)]
        return 0 if all([remove_from(d) for d in targets]) else 1
    dests = dests or default_dests()
    if not dests:
        print_status('No agent without plugin support was found (' + ', '.join(t['label'] for t in TARGETS.values())
                     + '). Agents with plugins: ezy plugins install. Another agent: ezy skills install --dir <its skills folder>')
        return 0
    return 0 if all([install_to(d, opts.force) for d in dests]) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
