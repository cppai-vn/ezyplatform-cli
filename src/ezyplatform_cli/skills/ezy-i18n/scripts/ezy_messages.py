#!/usr/bin/env python3
"""Compare and push EzySupport i18n messages (web or admin) for one language.

Usage:
    ezy i18n diff <web|admin> [--lang LANG]
    ezy i18n push <web|admin> [--lang LANG] [--keys k1,k2] [--yes]

Local files: <target>/messages/messages.properties (default) and
messages_<lang>.properties. `push` sends ONLY keys that are new or changed
(or the --keys subset), never the whole map, so translations owned by other
plugins or edited in the admin UI are not overwritten. Dry run unless --yes.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'ezy-shared'))
import ezy_client  # noqa: E402


def parse_properties(text):
    """Minimal Java .properties reader: key=value or key:value, # and ! comments, trimmed."""
    result = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in '#!':
            continue
        sep = min((i for i in (line.find('='), line.find(':')) if i > 0), default=-1)
        if sep < 0:
            continue
        result[line[:sep].strip()] = line[sep + 1:].strip()
    return result


def local_messages(root, target, lang):
    name = f'messages_{lang}.properties' if lang else 'messages.properties'
    path = os.path.join(root, target, 'messages', name)
    if not os.path.isfile(path):
        raise SystemExit(f'missing {os.path.relpath(path, root)}')
    return parse_properties(open(path, encoding='utf-8').read())


def server_messages(target, lang, env):
    q = f'?i18n_lang={lang}' if lang else ''
    return ezy_client.request_json('GET', f'/ezysupport/api/v1/{target}/messages{q}', env=env) or {}


def changed(local, server):
    return {k: v for k, v in local.items() if server.get(k) != v}


def cmd_diff(args, root, env):
    local = local_messages(root, args.target, args.lang)
    server = server_messages(args.target, args.lang, env)
    delta = changed(local, server)
    for key, value in delta.items():
        print(f"  {'+' if key not in server else '~'} {key}={value}" + (f'   (server: {server[key]})' if key in server else ''))
    only_server = sorted(set(server) - set(local))
    print(f'\n{len(delta)} key(s) to push; {len(only_server)} server-only key(s) left untouched')
    return 1 if delta else 0


def cmd_push(args, root, env):
    local = local_messages(root, args.target, args.lang)
    server = server_messages(args.target, args.lang, env)
    delta = changed(local, server)
    if args.keys:
        wanted = [k.strip() for k in args.keys.split(',') if k.strip()]
        missing = [k for k in wanted if k not in local]
        if missing:
            raise SystemExit(f'keys not in the local file: {missing}')
        delta = {k: local[k] for k in wanted}
    if not delta:
        print('nothing to push')
        return 0
    for key, value in delta.items():
        print(f'  {key}={value}')
    if not args.yes:
        print('\ndry run: re-run with --yes after the human approves')
        return 0
    ezy_client.request_json('PUT', f'/ezysupport/api/v1/{args.target}/messages',
                            {'languageCode': args.lang, 'messageValueByKey': delta}, env)
    after = server_messages(args.target, args.lang, env)
    bad = [k for k, v in delta.items() if after.get(k) != v]
    print('  ✓ pushed and verified' if not bad else f'  x pushed but differs after reload: {bad}')
    return 0 if not bad else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    for name in ('diff', 'push'):
        p = sub.add_parser(name)
        p.add_argument('target', choices=['web', 'admin'])
        p.add_argument('--lang', help='omit for the default messages.properties')
        if name == 'push':
            p.add_argument('--keys')
            p.add_argument('--yes', action='store_true')
    args = parser.parse_args()
    root = ezy_client.find_project_root()
    env = ezy_client.load_env(root)
    return cmd_diff(args, root, env) if args.cmd == 'diff' else cmd_push(args, root, env)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except ezy_client.EzyError as err:
        print(f'error: {err}', file=sys.stderr)
        sys.exit(2)
