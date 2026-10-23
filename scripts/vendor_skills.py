#!/usr/bin/env python3
"""Copy the ezy-* skills from the ezyplatform plugin into the CLI package.

Usage:
    python3 scripts/vendor_skills.py [plugin_dir]

`plugin_dir` is the `ezyplatform/` folder of a cppai-vn/agents-plugins checkout
(default: ../cppai/agents-plugins/ezyplatform next to this repo). The skills are
copied with explicit rewrites for setup hints, status markers and read
timeouts. Content operations retain their standalone plugin script commands.
Every rewrite must match, so an upstream change that breaks one fails here
instead of silently losing the CLI behavior.
"""
import json
import os
import re
import shutil
import subprocess
import sys

from status_rewrites import rewrite_status

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, 'src', 'ezyplatform_cli', 'skills')
DEFAULT_SOURCE = os.path.join(os.path.dirname(ROOT), 'cppai', 'agents-plugins', 'ezyplatform')

# Only setup and connection commands have CLI routes; content scripts stay standalone.
USAGE = [
    ('python3 ezy_new.py create', 'ezy new'),
    ('python3 ezy_new.py token-help', 'ezy token'),
    ('python3 ezy_new.py check', 'ezy check'),
    ('python3 ezy_client.py whoami', 'ezy whoami'),
]
# Hints printed at run time: (file, old, new, expected count).
HINTS = [
    ('ezy-publish/scripts/ezy_publish.py', 'import re\nimport sys', 'import re\nimport shlex\nimport sys', 1),
    ('ezy-publish/scripts/ezy_publish.py',
     "SENT = ('content', 'additionalHead', 'additionalFoot', 'title')",
     "SENT = ('content', 'additionalHead', 'additionalFoot', 'title')\n\n\n"
     "def restore_command(backup, root):\n"
     "    return shlex.join(['python3', os.path.relpath(__file__, root), 'restore',\n"
     "                       os.path.relpath(backup, root), '--yes'])", 1),
    ('ezy-publish/scripts/ezy_publish.py',
     'restore with: restore {os.path.relpath(backup, root)} --yes',
     'restore with: {restore_command(backup, root)}', 1),
    ('ezy-publish/scripts/ezy_publish.py',
     'python3 {os.path.relpath(__file__, root)} restore {os.path.relpath(backup, root)} --yes',
     '{restore_command(backup, root)}', 2),
    ('ezy-new/scripts/ezy_new.py', 'python3 {os.path.abspath(__file__)} check', 'ezy check', 1),
    ('ezy-new/scripts/ezy_new.py',
     '  4. Validate: ezy check{\' \' + shlex.quote(root) if root else \'\'}""")',
     '  4. Validate: ezy check{\' \' + shlex.quote(root) if root else \'\'}\n'
     '  5. Open this project in your coding agent and use the installed ezy-guide skill for content work.""")', 1),
    ('ezy-new/scripts/ezy_new.py',
     "    print('\\nNext: pull content with ezy-sync (pull-all --langs <langs>, then pull page:<slug> --write for each page), '\n"
     "          'then follow ezy-guide.')",
     "    print('\\nNext: open this project in your coding agent and use the installed ezy-guide skill. '\n"
     "          'It routes content work to ezy-sync, ezy-author, ezy-publish and the other installed skills.')", 1),
]


def rewrite(path, text):
    rel = os.path.relpath(path, DEST).replace(os.sep, '/')
    for file, old, new, count in HINTS:
        if rel == file:
            found = text.count(old)
            if found != count:
                raise SystemExit(f'{rel}: expected {count} x {old!r}, found {found}; update HINTS')
            text = text.replace(old, new)
    for old, new in USAGE:
        text = re.sub(re.escape(old) + r'\b', new, text)
    return rewrite_status(rel, text)


def main():
    source = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SOURCE)
    skills = os.path.join(source, 'skills')
    manifest = os.path.join(source, '.claude-plugin', 'plugin.json')
    if not os.path.isdir(skills) or not os.path.isfile(manifest):
        raise SystemExit(f'{source} is not the ezyplatform plugin folder (needs skills/ and .claude-plugin/plugin.json)')
    if os.path.exists(DEST):
        shutil.rmtree(DEST)
    shutil.copytree(skills, DEST, ignore=shutil.ignore_patterns('*.pyc', '__pycache__', '.DS_Store'))
    for folder, _, files in os.walk(DEST):
        for name in files:
            if name.endswith('.py'):
                path = os.path.join(folder, name)
                text = open(path, encoding='utf-8').read()
                new = rewrite(path, text)
                if new != text:
                    with open(path, 'w', encoding='utf-8') as fh:
                        fh.write(new)
    shutil.copyfile(os.path.join(ROOT, 'src', 'ezyplatform_cli', 'status_output.py'),
                    os.path.join(DEST, 'ezy-shared', 'ezy_output.py'))
    try:
        commit = subprocess.run(['git', '-C', source, 'rev-parse', '--short', 'HEAD'],
                                capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    info = {'plugin': 'ezyplatform', 'version': json.load(open(manifest, encoding='utf-8'))['version'],
            'commit': commit, 'source': 'https://github.com/cppai-vn/agents-plugins/tree/main/ezyplatform'}
    with open(os.path.join(DEST, 'VENDORED.json'), 'w', encoding='utf-8') as fh:
        json.dump(info, fh, indent=2)
        fh.write('\n')
    print(f"vendored ezyplatform skills {info['version']} ({commit or 'unknown commit'}) into {os.path.relpath(DEST, ROOT)}")


if __name__ == '__main__':
    main()
