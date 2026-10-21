"""Local EzyArticle project layout helpers shared by the ezy-* scripts.

Targets are written as `page:<slug>` or `fragment:<page_name>/<fragment_name>`.
Localized files follow the extension convention: content.<lang>.html,
head.<lang>.html, foot.<lang>.html, meta.<lang>.json, each falling back to the
non-localized file when missing.
"""
import json
import os
import re

REGIONS = {'content': 'content', 'head': 'additionalHead', 'foot': 'additionalFoot'}
# Site-relative links that can point at a page: /<slug> or /pages/<slug>, no file extension.
PAGE_LINK = re.compile(r'href=["\']/(?:pages/)?([a-z0-9][a-z0-9_-]*)/?(?=["\'?#])', re.I)
LANG_FILE = re.compile(r'^(content|head|foot|meta)\.([a-z]{2}(?:-[A-Za-z]{2})?)\.(html|json)$')


def target_dir(root, target):
    kind, _, name = target.partition(':')
    if kind == 'page' and name:
        return os.path.join(root, 'pages', name)
    if kind == 'fragment' and name.count('/') == 1:
        return os.path.join(root, 'page-fragments', *name.split('/'))
    raise SystemExit(f"bad target '{target}': use page:<slug> or fragment:<page>/<name>")


def list_targets(root):
    found = []
    pages = os.path.join(root, 'pages')
    if os.path.isdir(pages):
        found += [f'page:{d}' for d in sorted(os.listdir(pages)) if os.path.isdir(os.path.join(pages, d))]
    frags = os.path.join(root, 'page-fragments')
    if os.path.isdir(frags):
        for page in sorted(os.listdir(frags)):
            pdir = os.path.join(frags, page)
            if os.path.isdir(pdir):
                found += [f'fragment:{page}/{f}' for f in sorted(os.listdir(pdir)) if os.path.isdir(os.path.join(pdir, f))]
    return found


def languages(folder):
    """Languages that have at least one localized file in the folder (default excluded)."""
    langs = set()
    for name in os.listdir(folder) if os.path.isdir(folder) else []:
        m = LANG_FILE.match(name)
        if m:
            langs.add(m.group(2))
    return sorted(langs)


def _read(path):
    return open(path, encoding='utf-8').read() if os.path.isfile(path) else None


def read_region(folder, region, lang=None):
    """Localized file first, then the default file; None when neither exists."""
    if lang:
        text = _read(os.path.join(folder, f'{region}.{lang}.html'))
        if text is not None:
            return text
    return _read(os.path.join(folder, f'{region}.html'))


def read_meta(folder, lang=None):
    meta = json.loads(_read(os.path.join(folder, 'meta.json')) or '{}')
    if lang:
        meta.update(json.loads(_read(os.path.join(folder, f'meta.{lang}.json')) or '{}'))
    return meta


def local_fields(folder, lang=None):
    """Fields comparable with / sendable to the server for one language."""
    fields = {}
    for region, key in REGIONS.items():
        text = read_region(folder, region, lang)
        if text is not None:
            fields[key] = text
    meta = read_meta(folder, lang)
    if 'title' in meta:
        fields['title'] = meta['title']
    if 'summary' in meta:
        fields['summary'] = meta['summary']
    return fields


def write_region(folder, region, text, lang=None):
    os.makedirs(folder, exist_ok=True)
    name = f'{region}.{lang}.html' if lang else f'{region}.html'
    with open(os.path.join(folder, name), 'w', encoding='utf-8') as fh:
        fh.write(text)
    return name


def linked_page_slugs(root):
    """{slug: [files linking to it]} for site-relative links in local page and fragment HTML."""
    found = {}
    for base in ('pages', 'page-fragments'):
        for folder, _, files in os.walk(os.path.join(root, base)):
            for name in sorted(f for f in files if f.endswith('.html')):
                path = os.path.join(folder, name)
                for slug in PAGE_LINK.findall(_read(path)):
                    found.setdefault(slug, []).append(os.path.relpath(path, root))
    return found
