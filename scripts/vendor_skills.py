#!/usr/bin/env python3
"""Copy the ezy-* skills from the ezyplatform plugin into the CLI package.

Usage:
    python3 scripts/vendor_skills.py [plugin_dir]

`plugin_dir` is the `ezyplatform/` folder of a cppai-vn/agents-plugins checkout
(default: ../cppai/agents-plugins/ezyplatform next to this repo). The skills are
copied unchanged except for the command hints the scripts print ("python3
ezy_sync.py ...", "rollback: python3 <path> restore ..."), which are rewritten
to the `ezy` commands so users can copy them as they are. Every rewrite must
match, so an upstream change that breaks one fails here instead of shipping a
stale hint.
"""
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, 'src', 'ezyplatform_cli', 'skills')
DEFAULT_SOURCE = os.path.join(os.path.dirname(ROOT), 'cppai', 'agents-plugins', 'ezyplatform')

# Usage lines in script docstrings (also shown by --help): script + subcommand -> ezy command.
USAGE = [
    ('python3 ezy_init.py create', 'ezy init'),
    ('python3 ezy_init.py token-help', 'ezy token'),
    ('python3 ezy_init.py check', 'ezy check'),
    ('python3 ezy_client.py get', 'ezy get'),
    ('python3 ezy_client.py whoami', 'ezy whoami'),
    ('python3 ezy_sync.py', 'ezy sync'),
    ('python3 ezy_publish.py', 'ezy publish'),
    ('python3 ezy_media.py', 'ezy media'),
    ('python3 ezy_messages.py', 'ezy i18n'),
    ('python3 ezy_verify.py', 'ezy verify'),
    ('python3 ezy_mail.py', 'ezy mail'),
]
# Hints printed at run time: (file, old, new, expected count).
HINTS = [
    ('ezy-publish/scripts/ezy_publish.py', 'python3 {os.path.relpath(__file__, root)} restore', 'ezy publish restore', 2),
    ('ezy-init/scripts/ezy_init.py', 'python3 {os.path.abspath(__file__)} check', 'ezy check', 1),
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
    return text


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
