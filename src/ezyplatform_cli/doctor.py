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
    print('ezy')
    try:
        latest = self_update.latest_version()
        newer = self_update.parse(latest) > self_update.parse(__version__)
        print(f'  version   {__version__}' + (f'  (update available: {latest}, run: ezy update)' if newer else '  (latest)'))
    except OSError:
        print(f'  version   {__version__}  (could not check for updates)')
    print(f"  skills    ezyplatform {skills_install.bundled_info().get('version', '?')}")
    print(f'  python    {platform.python_version()}  ({sys.executable})')
    print(f"  uv        {self_update.find_uv() or 'not found'}   installed with: {self_update.installer()}")

    print('\nCoding agents (plugin ezyplatform@cppai)')
    rows = agents.status_rows()
    agents.print_status(rows=rows)
    if not any(r[2] and r[3] for r in rows):
        problems.append('no agent has the ezyplatform plugin: ezy plugins install')
    missing = [r[0] for r in rows if r[2] and r[3] is False]
    if missing:
        print(f"  tip: add the plugin there too with: ezy plugins install --target {','.join(missing)}")

    print('\nSkill copies')
    copies = skills_install.copies()
    for dest, result in copies:
        print(f'  {dest:50} {result}')
        if result != 'ok':
            problems.append(f'skill copy {dest} is {result}: ezy skills install --dir {dest}')
    if not copies:
        print('  none')
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
        print(f'{len(problems)} thing(s) to fix:\n  - ' + '\n  - '.join(problems))
        return 1
    print('All good.')
    return 0
