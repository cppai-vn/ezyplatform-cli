#!/usr/bin/env python3
"""Manage EzyPlatform media (the /api/v1/media library) from the command line.

Usage:
    python3 ezy_media.py status [name ...]           # local api/v1/media files vs server
    python3 ezy_media.py upload <file> [...] [--yes] # add, or replace when the name exists
    python3 ezy_media.py public|unpublic <name> --yes
    python3 ezy_media.py url <name>                  # web URL with a cache-busting ?v=

Upload and visibility changes are dry runs unless --yes is given.
Names must match ^[a-zA-Z0-9_-]+(.[a-zA-Z0-9_-]+)*$ (no spaces, no accents).
"""
import argparse
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'ezy-shared'))
import ezy_client  # noqa: E402
from ezy_output import print_status  # noqa: E402

NAME_RE = re.compile(r'^[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)*$')
SKIPPED_CONTENT = (b'{"token":"invalid"}',)


def media_dir(root):
    return os.path.join(root, 'api', 'v1', 'media')


def exists(name, env):
    data = ezy_client.request_json('GET', f'/api/v1/media/{urllib.request.quote(name)}/contains', env=env)
    return bool(data and data.get('contains'))


def is_public(name, env):
    data = ezy_client.request_json('GET', f'/api/v1/media/{urllib.request.quote(name)}/public', env=env)
    return bool(data and data.get('publicMedia'))


def cmd_status(args, root, env):
    folder = media_dir(root)
    names = args.names or (sorted(os.listdir(folder)) if os.path.isdir(folder) else [])
    missing = 0
    for name in names:
        on_server = exists(name, env)
        missing += not on_server
        visibility = ('public' if is_public(name, env) else 'private') if on_server else '-'
        print_status(f"{name:48} {'on server' if on_server else 'MISSING on server':18} {visibility}", on_server)
    print()
    if names:
        print_status(f'{missing} file(s) not on the server' if missing else 'all listed files exist on the server', not missing)
    else:
        print_status('no local media files to check')
    return 0


def cmd_upload(args, root, env):
    plan = []
    for path in args.files:
        name = os.path.basename(path)
        if not NAME_RE.match(name):
            raise SystemExit(f'invalid media name {name!r}: use only English letters, digits, ".", "-", "_"')
        data = open(path, 'rb').read()
        if not data.strip() or data.strip() in SKIPPED_CONTENT:
            raise SystemExit(f'{name} is empty or a placeholder; the platform refuses to sync it')
        plan.append((name, data, 'replace' if exists(name, env) else 'add'))
    for name, data, action in plan:
        print(f'  {action:7} {name} ({len(data)} bytes)')
    if not args.yes:
        print('\ndry run: re-run with --yes after the human approves')
        return 0
    for name, data, action in plan:
        path = '/api/v1/media/add?notPublic=false' if action == 'add' else f'/api/v1/media/{urllib.request.quote(name)}/replace-by-name'
        ezy_client.upload_file(path, name, data, env)
        verified = exists(name, env)
        print_status(f'{action} {name}' + (' (exists now)' if verified else ' — NOT found after upload'), verified)
    print('\nreference it as /api/v1/media/<name>?v=<timestamp>, or ezy:mhref / ezy:msrc for CSS and JS')
    return 0


def cmd_visibility(args, root, env):
    if not exists(args.name, env):
        raise SystemExit(f'{args.name} is not on the server')
    current = is_public(args.name, env)
    wanted = args.cmd == 'public'
    print(f"{args.name}: currently {'public' if current else 'private'} -> {'public' if wanted else 'private'}")
    if current == wanted:
        print('nothing to change')
        return 0
    if not args.yes:
        print('dry run: re-run with --yes after the human approves')
        return 0
    ezy_client._send('PUT', f'/api/v1/media/{urllib.request.quote(args.name)}/{args.cmd}', env=env)
    verified = is_public(args.name, env) == wanted
    print_status('changed' if verified else 'state did not change', verified)
    return 0


def cmd_url(args, root, env):
    web = ezy_client.request_text('/api/v1/settings/web-url', env).strip().rstrip('/')
    local = os.path.join(media_dir(root), args.name)
    version = int(os.path.getmtime(local)) if os.path.isfile(local) else None
    print(f'{web}/api/v1/media/{args.name}' + (f'?v={version}' if version else ''))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('status')
    s.add_argument('names', nargs='*')
    u = sub.add_parser('upload')
    u.add_argument('files', nargs='+')
    u.add_argument('--yes', action='store_true')
    for name in ('public', 'unpublic'):
        v = sub.add_parser(name)
        v.add_argument('name')
        v.add_argument('--yes', action='store_true')
    w = sub.add_parser('url')
    w.add_argument('name')
    args = parser.parse_args()
    root = ezy_client.find_project_root()
    env = ezy_client.load_env(root)
    handler = {'status': cmd_status, 'upload': cmd_upload, 'url': cmd_url}.get(args.cmd, cmd_visibility)
    return handler(args, root, env)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except ezy_client.EzyError as err:
        print_status(f'error: {err}', False, file=sys.stderr)
        sys.exit(2)
