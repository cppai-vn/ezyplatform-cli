#!/usr/bin/env python3
"""Compare and pull EzyArticle pages / page fragments between the server and local files.

Usage:
    python3 ezy_sync.py status [target ...]            # every local target when none given
    python3 ezy_sync.py pull <target> [--lang LANG] [--write]
    python3 ezy_sync.py pull-all [--langs en,vi] [--only page_name ...] [--skip-placeholders] [--write]
    python3 ezy_sync.py discover-pages [--write]

Targets: page:<slug> | fragment:<page_name>/<fragment_name>
`pull`/`pull-all` are dry runs unless --write is given. They write content/head/foot
regions; meta.json (or meta.<lang>.json) is created when missing, in the
extension's format, but an existing one is never rewritten so local-only fields
survive. `pull-all` covers every fragment the server lists, every page the
server lists (GET /ezyarticle/api/v1/posts, trashed pages excluded) and local
pages; `discover-pages` finds page slugs linked from local HTML and pulls the
ones not yet managed locally (useful when only some pages should be pulled).
A page that exists only locally (not created on the server yet) is reported,
never treated as an error, so it does not stop a bulk pull.
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'ezy-shared'))
import ezy_client  # noqa: E402
from ezy_output import print_status  # noqa: E402
import ezy_local  # noqa: E402

COMPARED = ('content', 'additionalHead', 'additionalFoot', 'title', 'summary')
# The server keeps one summary for all languages, so a localized summary never matches.
LANG_SHARED = {'summary'}
PAGE_TYPES = {'PAGE', 'STANDALONE_PAGE', 'TEMPLATED_PAGE'}


def fetch(target, lang, env):
    """Server object for a target, or None when the server has no such page/fragment (HTTP 404)."""
    kind, _, name = target.partition(':')
    try:
        if kind == 'page':
            return ezy_client.get_page(name, lang, env)
        page_name, fragment_name = name.split('/')
        return ezy_client.get_fragment(page_name, fragment_name, lang, env)
    except ezy_client.EzyError as err:
        if err.status == 404:
            return None
        raise


def missing_state(folder):
    """How to report a target the server does not have: a local draft is expected, anything else is drift."""
    status = ezy_local.read_meta(folder).get('status')
    if status in (None, 'DRAFT'):
        return f"local only ({status or 'no status'}, not on server yet)"
    return f'MISSING on server (local status {status})'


def is_placeholder(target, server):
    """Theme fragments the server seeds with their own name as content and nothing else."""
    if not target.startswith('fragment:') or server.get('additionalHead') or server.get('additionalFoot'):
        return False
    return (server.get('content') or '').strip() == target.rsplit('/', 1)[1]


def compare(target, lang, root, env):
    folder = ezy_local.target_dir(root, target)
    local = ezy_local.local_fields(folder, lang)
    try:
        server = fetch(target, lang, env)
    except ezy_client.EzyError as err:
        return [(target, lang or 'default', 'server', f'ERROR {err.status}')]
    if not server:
        return [(target, lang or 'default', 'server', missing_state(folder))]
    rows = []
    for field in COMPARED:
        if field not in local:
            continue
        server_value = server.get(field) or ''
        if lang and field in LANG_SHARED:
            continue
        state = 'match' if local[field] == server_value else f'DIFF (local {len(local[field])} / server {len(server_value)} chars)'
        rows.append((target, lang or 'default', field, state))
    return rows


def cmd_status(args, root, env):
    targets = args.targets or ezy_local.list_targets(root)
    dirty = 0
    local_only = 0
    for target in targets:
        folder = ezy_local.target_dir(root, target)
        for lang in [None] + ezy_local.languages(folder):
            for row in compare(target, lang, root, env):
                if row[3] != 'match' and not row[3].startswith('local only'):
                    dirty += 1
                draft = row[3].startswith('local only')
                local_only += draft
                print_status(f'{row[0]:34} {row[1]:8} {row[2]:15} {row[3]}',
                             None if draft else row[3] == 'match')
    print()
    if dirty:
        print_status(f'{dirty} difference(s)', False)
    elif local_only:
        print_status(f'no differences; {local_only} local-only draft(s) not on server yet')
    else:
        print_status('local and server are in sync', True)
    return 1 if dirty else 0


def build_meta(target, server, lang):
    """meta.json in the extension's sync format; localized meta only carries the title."""
    if lang:
        return {'title': server.get('title') or ''}
    image = server.get('featuredImage') or {}
    meta = {'title': server.get('title') or '', 'summary': server.get('summary') or '',
            'featuredImageName': image.get('name')}
    if target.startswith('page:'):
        published = server.get('publishedAt')
        meta.update({'slug': target.partition(':')[2], 'pageType': server.get('postType')})
        meta.update({'contentType': server.get('contentType'), 'status': server.get('status'),
                     'priority': server.get('priority'),
                     'publishedAt': datetime.datetime.fromtimestamp(published / 1000).strftime('%Y-%m-%d %H:%M:%S') if published else None,
                     'password': server.get('password') or None,
                     'terms': [t.get('slug') if isinstance(t, dict) else t for t in server.get('terms') or []],
                     'metadata': server.get('metadata') or {}})
    else:
        meta.update({'contentType': server.get('contentType'), 'status': server.get('status')})
    return {k: v for k, v in meta.items() if v is not None}


def pull_target(target, lang, write, root, env, quiet=False, skip_placeholders=False):
    """Pull one target/language. Returns the number of files written (or that would be)."""
    folder = ezy_local.target_dir(root, target)
    server = fetch(target, lang, env)
    if not server:
        print(f'  - {target}: {missing_state(folder)}, nothing to pull')
        return 0
    if skip_placeholders and not os.path.isdir(folder) and is_placeholder(target, server):
        return 0
    changes = []
    for region, key in ezy_local.REGIONS.items():
        value = server.get(key) or ''
        exists = ezy_local.read_region(folder, region, lang) is not None
        current = ezy_local.read_region(folder, region, lang) or ''
        if value == current or (not value and not exists):
            continue
        changes.append((f'{region}.{lang}.html' if lang else f'{region}.html', value))
    meta_name = f'meta.{lang}.json' if lang else 'meta.json'
    meta_path = os.path.join(folder, meta_name)
    default_title = ezy_local.read_meta(folder).get('title')
    untranslated = lang and server.get('title') == default_title
    if not os.path.isfile(meta_path) and not untranslated:
        changes.append((meta_name, json.dumps(build_meta(target, server, lang), ensure_ascii=False, indent=2) + '\n'))
    elif os.path.isfile(meta_path):
        meta = ezy_local.read_meta(folder, lang)
        if server.get('title') and meta.get('title') != server.get('title'):
            print(f"  note: {target} [{lang or 'default'}] title differs (server: {server.get('title')!r}); edit {meta_name} by hand if intended")
    if not changes and not quiet:
        print(f"  = {target} [{lang or 'default'}] already matches the server")
    for name, value in changes:
        rel = os.path.relpath(os.path.join(folder, name), root)
        if write:
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, name), 'w', encoding='utf-8') as fh:
                fh.write(value)
            print(f'  wrote {rel} ({len(value)} chars)')
        else:
            print(f'  would write {rel} ({len(value)} chars)')
    return len(changes)


def cmd_pull(args, root, env):
    count = pull_target(args.target, args.lang, args.write, root, env)
    if count and not args.write:
        print('\ndry run: re-run with --write to write local files')
    return 0


def cmd_pull_all(args, root, env):
    """Every fragment and page listed by the server plus every local page, default + requested languages."""
    groups = ezy_client.request_json('GET', '/ezyarticle/api/v1/pages/fragments?keyword=', env=env) or {}
    targets = [f'fragment:{page}/{name}' for page in sorted(groups) for name in sorted(groups[page])]
    if args.only:
        targets = [t for t in targets if t.split(':', 1)[1].split('/')[0] in args.only]
    pages = {f"page:{p['slug']}" for p in ezy_client.list_posts(PAGE_TYPES, env) if p.get('slug')}
    if args.only:
        pages = set()
    pages |= {t for t in ezy_local.list_targets(root) if t.startswith('page:')}
    targets += sorted(pages)
    langs = [None] + [l.strip() for l in (args.langs or '').split(',') if l.strip()]
    print(f'{len(targets)} target(s) x {len(langs)} language(s)')
    total = 0
    for target in targets:
        for lang in langs:
            total += pull_target(target, lang, args.write, root, env, quiet=True,
                                 skip_placeholders=args.skip_placeholders)
    if not total:
        print('everything already matches the server')
    elif not args.write:
        print(f'\n{total} file(s) would be written. Dry run: re-run with --write after checking git status.')
    else:
        print(f'\n{total} file(s) written')
    return 0


def cmd_discover_pages(args, root, env):
    """Page slugs linked from local HTML (href="/<slug>" or "/pages/<slug>") that are not local yet."""
    links = ezy_local.linked_page_slugs(root)
    local = {t.partition(':')[2] for t in ezy_local.list_targets(root) if t.startswith('page:')}
    new = sorted(slug for slug in links if slug not in local)
    print(f'{len(links)} linked slug(s), {len(links) - len(new)} already local')
    total = 0
    for slug in new:
        if fetch(f'page:{slug}', None, env) is None:
            print(f'  . /{slug} is not a page (route or missing), linked from {links[slug][0]}')
            continue
        print(f'  + page:{slug} (linked from {links[slug][0]})')
        total += pull_target(f'page:{slug}', None, args.write, root, env, quiet=True)
    if total and not args.write:
        print('\ndry run: re-run with --write to pull the new pages')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    st = sub.add_parser('status')
    st.add_argument('targets', nargs='*')
    pl = sub.add_parser('pull')
    pl.add_argument('target')
    pl.add_argument('--lang')
    pl.add_argument('--write', action='store_true')
    pa = sub.add_parser('pull-all')
    pa.add_argument('--langs', help='comma-separated extra languages, e.g. en,vi')
    pa.add_argument('--only', nargs='*', help='limit fragments to these page_name groups, e.g. cppai common (server pages are then skipped; local pages are still pulled)')
    pa.add_argument('--skip-placeholders', action='store_true',
                    help='do not create folders for fragments whose content is only their own name')
    pa.add_argument('--write', action='store_true')
    dp = sub.add_parser('discover-pages')
    dp.add_argument('--write', action='store_true')
    args = parser.parse_args()
    root = ezy_client.find_project_root()
    env = ezy_client.load_env(root)
    return {'status': cmd_status, 'pull': cmd_pull, 'pull-all': cmd_pull_all,
            'discover-pages': cmd_discover_pages}[args.cmd](args, root, env)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except ezy_client.EzyError as err:
        print_status(f'error: {err}', False, file=sys.stderr)
        sys.exit(2)
