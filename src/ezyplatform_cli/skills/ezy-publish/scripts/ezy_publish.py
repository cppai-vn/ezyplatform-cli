#!/usr/bin/env python3
"""Publish local EzyArticle pages / fragments to the live site, with backup, verify and restore.

Usage:
    ezy publish plan  <target> [...] [--lang LANG]      # dry run, no writes
    ezy publish apply <target> [...] [--lang LANG] --yes
    ezy publish restore <backup-dir> --yes
    ezy publish remove <target> [...] [--force] [--yes]   # move to Trash

Targets: page:<slug> | fragment:<page_name>/<fragment_name> | post:<slug> (remove only)

Without --lang every language is published: the default plus each language that
has localized files locally. Fragments always go before pages, so a page never
references markup or CSS that is not live yet.

Only existing server posts are updated (PUT /ezyarticle/api/v1/posts/{id}); the
live post supplies slug, type, status and menu link, local files supply
content/head/foot/title. Creating new posts is out of scope: publish those once
with the VS Code extension, then manage them here.

`remove` moves posts to the admin Trash (DELETE /ezyarticle/api/v1/posts?ids=;
status becomes TRASH, the post still reads by id and slug). It backs up every
site language first and refuses a fragment that local HTML still includes via
ezy:replace unless --force. `restore` of such a backup sets the saved status
back (PUT /ezyarticle/api/v1/posts/status), then rewrites the content.
"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'ezy-shared'))
import ezy_client  # noqa: E402
import ezy_local  # noqa: E402

SENT = ('content', 'additionalHead', 'additionalFoot', 'title')


def fetch_live(target, lang, env):
    kind, _, name = target.partition(':')
    if kind == 'page':
        post = ezy_client.get_page(name, None, env)
    else:
        page_name, fragment_name = name.split('/')
        post = ezy_client.get_fragment(page_name, fragment_name, None, env)
    if not post or not post.get('id'):
        raise SystemExit(f'{target} does not exist on the server; publish it once with the VS Code extension first')
    return ezy_client.get_post(post['id'], lang, env) if lang else post


def ordered(targets):
    return [t for t in targets if t.startswith('fragment:')] + [t for t in targets if t.startswith('page:')]


def build_jobs(targets, only_lang, root, env):
    jobs = []
    for target in ordered(targets):
        folder = ezy_local.target_dir(root, target)
        if not os.path.isdir(folder):
            raise SystemExit(f'local folder missing for {target}: {folder}')
        langs = [only_lang] if only_lang else [None] + ezy_local.languages(folder)
        meta = ezy_local.read_meta(folder)
        for lang in langs:
            live = fetch_live(target, lang, env)
            local = ezy_local.local_fields(folder, lang)
            changes = {k: local[k] for k in SENT if k in local and local[k] != (live.get(k) or '')}
            if not lang and 'summary' in local and local['summary'] != (live.get('summary') or ''):
                changes['summary'] = local['summary']
            warn = None
            if meta.get('status') and meta['status'] != live.get('status'):
                warn = f"meta.json status {meta['status']} != live {live.get('status')} (live status is kept)"
            jobs.append({'target': target, 'lang': lang, 'live': live, 'changes': changes, 'warn': warn})
    return jobs


def describe(job):
    lang = job['lang'] or 'default'
    if not job['changes']:
        return f"  = {job['target']} [{lang}] up to date"
    fields = ', '.join(f"{k} ({len(v)} chars)" for k, v in job['changes'].items())
    return f"  ~ {job['target']} [{lang}] post {job['live']['id']}: {fields}"


def verify(job, env):
    after = ezy_client.get_post(job['live']['id'], job['lang'], env)
    bad = [k for k, v in job['changes'].items() if (after.get(k) or '') != v and k != 'summary']
    return bad


def cmd_plan_or_apply(args, root, env):
    jobs = build_jobs(args.targets, args.lang, root, env)
    print('Publish plan:')
    for job in jobs:
        print(describe(job))
        if job['warn']:
            print(f"    ! {job['warn']}")
    pending = [j for j in jobs if j['changes']]
    if not pending:
        print('\nnothing to publish')
        return 0
    if args.cmd == 'plan' or not args.yes:
        print(f'\n{len(pending)} update(s) pending. Dry run only: re-run "apply ... --yes" after the human approves.')
        return 0
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = os.path.join(root, '.artifacts', 'backups', stamp)
    os.makedirs(backup, exist_ok=True)
    for job in pending:
        name = f"{job['target'].replace(':', '-').replace('/', '-')}{'-' + job['lang'] if job['lang'] else ''}.json"
        with open(os.path.join(backup, name), 'w', encoding='utf-8') as fh:
            json.dump({'target': job['target'], 'lang': job['lang'], 'post': job['live']}, fh, ensure_ascii=False, indent=1)
    print(f'\nbackup: {os.path.relpath(backup, root)}')
    for job in pending:
        body = ezy_client.update_payload(job['live'], **job['changes'])
        if job['lang']:
            body['language'] = job['lang']
        try:
            ezy_client.put_post(job['live']['id'], body, env)
        except ezy_client.EzyError as err:
            print(f"  x {job['target']} [{job['lang'] or 'default'}] failed: {err}\n  stopped; earlier steps stay live, restore with: restore {os.path.relpath(backup, root)} --yes")
            return 2
        bad = verify(job, env)
        print(f"  ✓ {job['target']} [{job['lang'] or 'default'}] published" + (f' but differs after reload: {bad}' if bad else ' and verified'))
    print(f'\nrollback: ezy publish restore {os.path.relpath(backup, root)} --yes')
    return 0


def resolve(target, env):
    """Live post for a removal target; posts and pages share the by-slug endpoint."""
    kind, _, name = target.partition(':')
    if kind not in ('page', 'post', 'fragment') or not name:
        raise SystemExit(f"bad target '{target}': use page:<slug>, post:<slug> or fragment:<page>/<name>")
    try:
        if kind == 'fragment':
            page_name, fragment_name = name.split('/')
            post = ezy_client.get_fragment(page_name, fragment_name, None, env)
        else:
            post = ezy_client.get_page(name, None, env)
    except ezy_client.EzyError as err:
        if err.status != 404:
            raise
        post = None
    if not post or not post.get('id'):
        raise SystemExit(f'{target} does not exist on the server')
    return post


def fragment_users(root, target):
    """Local page/fragment files that include this fragment with ezy:replace (~{page/name :: region})."""
    name = target.partition(':')[2]
    pattern = re.compile(r'~\{\s*' + re.escape(name) + r'\s*::')
    users = []
    for folder in ('pages', 'page-fragments', 'posts'):
        for dirpath, _, files in os.walk(os.path.join(root, folder)):
            if os.path.relpath(dirpath, root).replace(os.sep, '/').endswith(name):
                continue
            for f in files:
                if f.endswith('.html') and pattern.search(open(os.path.join(dirpath, f), encoding='utf-8').read()):
                    users.append(os.path.relpath(os.path.join(dirpath, f), root))
    return users


def cmd_remove(args, root, env):
    posts = [(t, resolve(t, env)) for t in args.targets]
    print('Remove plan (move to Trash):')
    blocked = False
    for target, post in posts:
        print(f"  - {target} post {post['id']} {post.get('postType')} {post.get('status')}: {post.get('title')!r}")
        if post.get('status') == 'TRASH':
            print('    ! already in Trash')
        if target.startswith('fragment:'):
            users = fragment_users(root, target)
            if users:
                blocked = True
                print(f"    ! still included by {', '.join(users[:5])}{' ...' if len(users) > 5 else ''}")
    if blocked and not args.force:
        print('\nrefused: remove the ezy:replace includes first, or re-run with --force')
        return 1
    if not args.yes:
        print(f'\n{len(posts)} post(s) would move to Trash. Dry run only: re-run with --yes after the human approves.')
        return 0
    langs = ezy_client.site_languages(env)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = os.path.join(root, '.artifacts', 'backups', stamp + '-remove')
    os.makedirs(backup, exist_ok=True)
    for target, post in posts:
        for lang in [None] + langs[1:]:
            live = ezy_client.get_post(post['id'], lang, env)
            name = f"{target.replace(':', '-').replace('/', '-')}{'-' + lang if lang else ''}.json"
            with open(os.path.join(backup, name), 'w', encoding='utf-8') as fh:
                json.dump({'target': target, 'lang': lang, 'removed': True, 'post': live}, fh, ensure_ascii=False, indent=1)
    print(f'\nbackup: {os.path.relpath(backup, root)}')
    ezy_client.trash_posts([p['id'] for _, p in posts], env)
    failed = [t for t, p in posts if ezy_client.get_post(p['id'], None, env).get('status') != 'TRASH']
    listed = {p['id'] for p in ezy_client.list_posts(env=env)}
    for target, post in posts:
        ok = target not in failed and post['id'] not in listed
        print(f"  {'✓' if ok else 'x'} {target} {'in Trash and gone from the post list' if ok else 'NOT removed'}")
    print(f'\nundo: ezy publish restore {os.path.relpath(backup, root)} --yes')
    print('note: the public URL of a removed page shows the theme "not found" page, often with HTTP 200, not 404')
    return 2 if failed else 0


def cmd_restore(args, root, env):
    files = sorted(f for f in os.listdir(args.backup_dir) if f.endswith('.json'))
    if not files:
        raise SystemExit('no backup files found')
    entries = [json.load(open(os.path.join(args.backup_dir, f), encoding='utf-8')) for f in files]
    print('Restore plan:')
    for e in entries:
        print(f"  < {e['target']} [{e['lang'] or 'default'}] post {e['post']['id']}")
    if not args.yes:
        print('\ndry run: re-run with --yes after the human approves')
        return 0
    removed = {}
    for e in entries:
        if e.get('removed'):
            removed.setdefault(e['post']['status'], set()).add(e['post']['id'])
    for status, ids in removed.items():
        ezy_client.set_posts_status(sorted(ids), status, env)
        print(f"  ✓ took {len(ids)} post(s) out of Trash (status {status})")
    for e in entries:
        body = ezy_client.update_payload(e['post'], content=e['post'].get('content') or '',
                                         additionalHead=e['post'].get('additionalHead') or '',
                                         additionalFoot=e['post'].get('additionalFoot') or '')
        if e['lang']:
            body['language'] = e['lang']
        ezy_client.put_post(e['post']['id'], body, env)
        print(f"  ✓ restored {e['target']} [{e['lang'] or 'default'}]")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    for name in ('plan', 'apply'):
        p = sub.add_parser(name)
        p.add_argument('targets', nargs='+')
        p.add_argument('--lang')
        p.add_argument('--yes', action='store_true')
    r = sub.add_parser('restore')
    r.add_argument('backup_dir')
    r.add_argument('--yes', action='store_true')
    rm = sub.add_parser('remove')
    rm.add_argument('targets', nargs='+')
    rm.add_argument('--force', action='store_true', help='remove fragments that local HTML still includes')
    rm.add_argument('--yes', action='store_true')
    args = parser.parse_args()
    root = ezy_client.find_project_root()
    env = ezy_client.load_env(root)
    handler = {'restore': cmd_restore, 'remove': cmd_remove}.get(args.cmd, cmd_plan_or_apply)
    return handler(args, root, env)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except ezy_client.EzyError as err:
        print(f'error: {err}', file=sys.stderr)
        sys.exit(2)
