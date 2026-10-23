"""`ezy doctor`: what is installed where, and what to fix.

Checks ezy itself (version, latest release, Python, uv), the ezyplatform
plugin in each coding agent, the ezy skill copies, agents that would see the
skills twice (plugin plus a copy, or two copies), and the site project in the
current folder when there is one.
"""
import os
import platform
import sys

from . import __version__, agents, self_update, skills_install
from .status_output import print_status


def project_root(start):
    path = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(path, 'environment.json')):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def duplicates(rows, copies):
    """Agents that load the ezy skills from more than one place."""
    found = []
    with_copy = {d for d, _ in copies}
    for name, dirs in skills_install.READS.items():
        sources = [d for d in (skills_install.expand(p) for p in dirs) if d in with_copy]
        has_plugin = any(r[0] == name and r[3] for r in rows)
        label = agents.AGENTS[name]['label'] if name in agents.AGENTS else skills_install.TARGETS[name]['label']
        if has_plugin and sources:
            found.append(f'{label}: plugin + copy in {", ".join(sources)}')
        elif len(sources) > 1:
            found.append(f'{label}: copies in {", ".join(sources)}')
    return found


def main(args):
    if args and args[0] in ('-h', '--help'):
        print('usage: ezy doctor\n\n' + __doc__)
        return 0
    problems = []
    print('ezy', flush=True)
    try:
        latest = self_update.latest_version(timeout=10)
        newer = self_update.parse(latest) > self_update.parse(__version__)
        print_status(f'version   {__version__}' + (f'  (update available: {latest}, run: ezy update)' if newer else '  (latest)'),
                     None if newer else True)
    except OSError:
        print_status(f'version   {__version__}  (could not check for updates)', False)
    skills_version = skills_install.bundled_info().get('version')
    print_status(f"skills    ezyplatform {skills_version or '?'}", bool(skills_version))
    print_status(f'python    {platform.python_version()}  ({sys.executable})', True)
    uv = self_update.find_uv()
    print_status(f"uv        {uv or 'not found'}   installed with: {self_update.installer()}", bool(uv))

    print('\nCoding agents (plugin ezyplatform@cppai)', flush=True)
    rows = agents.status_rows(progress=True)
    unknown = [r[0] for r in rows if r[2] and r[3] is None and not agents.AGENTS[r[0]].get('manual')]
    if unknown:
        problems.append('could not check plugins for ' + ', '.join(unknown)
                        + ': retry ezy plugins status --target ' + ','.join(unknown))
    if not unknown and not any(r[2] and r[3] for r in rows):
        problems.append('no agent has the ezyplatform plugin: ezy plugins install')
    missing = [r[0] for r in rows if r[2] and r[3] is False]
    if missing:
        print(f"  tip: add the plugin there too with: ezy plugins install --target {','.join(missing)}")

    print('\nSkill copies')
    copies = skills_install.copies()
    for dest, result in copies:
        print_status(f'{dest:50} {result}', result == 'ok')
        if result != 'ok':
            problems.append(f'skill copy {dest} is {result}: ezy skills install --dir {dest}')
    if not copies:
        print_status('none')
    for target in skills_install.TARGETS.values():
        dest = skills_install.expand(target['dir'])
        if skills_install.shutil.which(target['exe']) and dest not in {d for d, _ in copies}:
            problems.append(f"{target['label']} has no plugin support and no skill copy: ezy skills install")

    dupes = duplicates(rows, copies)
    for line in dupes:
        problems.append('skills loaded twice — ' + line + ' (keep one: ezy skills remove --dir <folder>)')

    root = project_root(os.getcwd())
    if root:
        print(f'\nProject {root}')
        from .cli import NEW, run_script
        if run_script(NEW, ['check', root], 'ezy check') != 0:
            problems.append('the site project is not ready (see above)')

    print()
    if problems:
        print_status(f'{len(problems)} thing(s) to fix:', False)
        for problem in problems:
            print_status(problem, False)
        return 1
    print_status('All good.', True)
    return 0
