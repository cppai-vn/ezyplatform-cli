#!/usr/bin/env python3
"""Preview locally and check the live site for EzyArticle pages.

Usage:
    ezy verify preview <slug> [--lang LANG]
        Inline every <ezy:block ezy:replace="~{page/fragment :: region}"/> with the
        local fragment file and write .artifacts/preview/<slug>[.<lang>].html.
        Thymeleaf (th:*, ezyfunctions, #messages) is NOT executed: dynamic parts
        such as server menus stay empty, so judge layout and styling only.
    ezy verify live [path] [--lang LANG] [--expect TEXT ...]
        Fetch the public page and report HTTP status, size, unrendered template
        markers and whether each expected text is present.
"""
import argparse
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'ezy-shared'))
import ezy_client  # noqa: E402
import ezy_local  # noqa: E402

INCLUDE = re.compile(r'<ezy:block\s+ezy:replace="~\{([\w-]+)/([\w-]+)\s*::\s*(content|head|foot)\}"\s*/>')
UNRENDERED = re.compile(r'<ezy:block|\sth:[a-z]+=|\sezy:(?:replace|utext|mhref|msrc)=')


def cmd_preview(args, root):
    folder = ezy_local.target_dir(root, f'page:{args.slug}')
    page = ezy_local.read_region(folder, 'content', args.lang)
    if page is None:
        raise SystemExit(f'pages/{args.slug}/content.html not found')
    missing = []

    def inline(match):
        frag_dir = os.path.join(root, 'page-fragments', match.group(1), match.group(2))
        text = ezy_local.read_region(frag_dir, match.group(3), args.lang)
        if text is None:
            missing.append(match.group(0))
            return ''
        return text

    html = INCLUDE.sub(inline, page)
    out_dir = os.path.join(root, '.artifacts', 'preview')
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{args.slug}{'.' + args.lang if args.lang else ''}.html")
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(html)
    print(f'wrote {os.path.relpath(out, root)} ({len(html)} chars)')
    if missing:
        print('missing fragments (removed from preview):\n  ' + '\n  '.join(missing))
    leftovers = len(re.findall(r'\sth:[a-z]+=', html))
    if leftovers:
        print(f'note: {leftovers} Thymeleaf attribute(s) are not executed in a local preview')
    print(f'serve it: python3 -m http.server 8765 --bind 127.0.0.1 --directory {os.path.relpath(out_dir, root)}')
    return 1 if missing else 0


def cmd_live(args, root):
    env = ezy_client.load_env(root)
    web = ezy_client.request_text('/api/v1/settings/web-url', env).strip().rstrip('/')
    path = args.path if args.path.startswith('/') else '/' + args.path
    url = web + path + (('&' if '?' in path else '?') + f'lang={args.lang}' if args.lang else '')
    req = urllib.request.Request(url, headers={'User-Agent': ezy_client.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status, html = resp.status, resp.read().decode(errors='replace')
    except urllib.error.HTTPError as err:
        status, html = err.code, err.read().decode(errors='replace')
    print(f'{url} -> HTTP {status}, {len(html)} chars')
    markers = UNRENDERED.findall(html)
    print(f'unrendered template markers: {len(markers)}' + (f' e.g. {markers[:3]}' if markers else ''))
    failed = 0
    for text in args.expect or []:
        ok = text in html
        failed += not ok
        print(f"  {'✓' if ok else 'x'} contains {text!r}")
    return 0 if status == 200 and not markers and not failed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('preview')
    p.add_argument('slug')
    p.add_argument('--lang')
    lv = sub.add_parser('live')
    lv.add_argument('path', nargs='?', default='/')
    lv.add_argument('--lang')
    lv.add_argument('--expect', nargs='*')
    args = parser.parse_args()
    root = ezy_client.find_project_root()
    return cmd_preview(args, root) if args.cmd == 'preview' else cmd_live(args, root)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except ezy_client.EzyError as err:
        print(f'error: {err}', file=sys.stderr)
        sys.exit(2)
