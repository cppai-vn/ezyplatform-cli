#!/usr/bin/env python3
"""Shared EzyPlatform admin API client for the ezy-* skills.

- Reads the admin URL and access token from the project's environment.json
  (the entry with "default": true, or the one named by $EZY_ENV).
- Never prints the token; responses are redacted before display.
- Sends an explicit User-Agent because Cloudflare blocks the default
  Python-urllib signature with error 1010.

CLI (read-only helper):
    ezy get <api-path>        # redacted JSON to stdout
    ezy whoami                # roles of the token owner
"""
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

USER_AGENT = 'ezy-skills/1.0'
SENSITIVE_KEYS = ('token', 'password', 'secret', 'apikey', 'api_key', 'hash')


def find_project_root(start=None):
    """Walk up from `start` (default: cwd) to the folder holding environment.json."""
    path = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.isfile(os.path.join(path, 'environment.json')):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            raise SystemExit('environment.json not found; run inside an EzyArticle project')
        path = parent


def load_env(root=None):
    root = root or find_project_root()
    envs = json.load(open(os.path.join(root, 'environment.json'), encoding='utf-8'))
    wanted = os.environ.get('EZY_ENV')
    for env in envs:
        if (wanted and env.get('name') == wanted) or (not wanted and env.get('default')):
            if not env.get('admin_url') or not env.get('admin_access_token'):
                raise SystemExit(f"environment '{env.get('name')}' is missing admin_url or admin_access_token")
            return env
    raise SystemExit(f"no environment {'named ' + wanted if wanted else 'marked default'} in environment.json")


def redact(value):
    if isinstance(value, dict):
        return {k: ('[redacted]' if any(s in k.lower() for s in SENSITIVE_KEYS) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


class EzyError(Exception):
    def __init__(self, status, body):
        super().__init__(f'HTTP {status}: {body[:300]}')
        self.status = status
        self.body = body


def _send(method, path, data=None, content_type=None, env=None, accept='application/json'):
    env = env or load_env()
    url = env['admin_url'].rstrip('/') + path
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', 'Bearer ' + env['admin_access_token'])
    req.add_header('Accept', accept)
    req.add_header('User-Agent', USER_AGENT)
    if content_type:
        req.add_header('Content-Type', content_type)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        raise EzyError(err.code, err.read().decode(errors='replace')) from None


def request_json(method, path, body=None, env=None):
    data = json.dumps(body).encode() if body is not None else None
    _, raw = _send(method, path, data, 'application/json' if data is not None else None, env)
    text = raw.decode(errors='replace').strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise EzyError(200, 'non-JSON response: ' + text[:200]) from None


def request_text(path, env=None):
    _, raw = _send('GET', path, env=env, accept='*/*')
    return raw.decode(errors='replace')


def request_bytes(path, env=None):
    _, raw = _send('GET', path, env=env, accept='*/*')
    return raw


def upload_file(path, file_name, file_bytes, env=None):
    """POST multipart/form-data with the single field `file`, as the extension does."""
    boundary = '----EzySkills' + uuid.uuid4().hex
    head = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
            'Content-Type: application/octet-stream\r\n\r\n').encode()
    body = head + file_bytes + f'\r\n--{boundary}--\r\n'.encode()
    status, raw = _send('POST', path, body, f'multipart/form-data; boundary={boundary}', env)
    return status, raw.decode(errors='replace')


# ---- Content helpers shared by sync / publish ----

def get_page(slug, lang=None, env=None):
    q = f'?i18n_lang={lang}' if lang else ''
    return request_json('GET', f'/ezyarticle/api/v1/post-by-slug/{urllib.request.quote(slug)}{q}', env=env)


def get_fragment(page_name, fragment_name, lang=None, env=None):
    """The fragment-by-name endpoint ignores i18n_lang, so localized reads go through /posts/{id}."""
    base = request_json('GET', f'/ezyarticle/api/v1/pages/{urllib.request.quote(page_name)}/fragments/{urllib.request.quote(fragment_name)}', env=env)
    if not lang or not base or not base.get('id'):
        return base
    return request_json('GET', f"/ezyarticle/api/v1/posts/{base['id']}?i18n_lang={lang}", env=env)


def get_post(post_id, lang=None, env=None):
    q = f'?i18n_lang={lang}' if lang else ''
    return request_json('GET', f'/ezyarticle/api/v1/posts/{post_id}{q}', env=env)


def put_post(post_id, body, env=None):
    return request_json('PUT', f'/ezyarticle/api/v1/posts/{post_id}', body, env=env)


def list_posts(post_types=None, env=None, page_size=100):
    """Every non-trashed post (pages, posts, fragments) from GET /ezyarticle/api/v1/posts.

    Items are summaries (id, slug, title, status, postType, timestamps) without content.
    Trashed posts are not listed. `post_types` filters on postType, e.g. {'PAGE', 'STANDALONE_PAGE'}.
    """
    items, token = [], None
    while True:
        query = f'?limit={page_size}' + (f'&nextPageToken={urllib.request.quote(token)}' if token else '')
        page = request_json('GET', f'/ezyarticle/api/v1/posts{query}', env=env) or {}
        items += page.get('items') or []
        token = (page.get('pageToken') or {}).get('next')
        if not token or not (page.get('continuation') or {}).get('hasNext'):
            break
    return [p for p in items if not post_types or p.get('postType') in post_types]


def trash_posts(ids, env=None):
    """DELETE /ezyarticle/api/v1/posts?ids=: moves posts to the admin Trash (status TRASH), not a hard delete."""
    return request_json('DELETE', '/ezyarticle/api/v1/posts?ids=' + ','.join(str(i) for i in ids), env=env)


def set_posts_status(ids, status, env=None):
    """PUT /ezyarticle/api/v1/posts/status?ids=: bulk status change, as the admin list does (restores from Trash)."""
    return request_json('PUT', '/ezyarticle/api/v1/posts/status?ids=' + ','.join(str(i) for i in ids), {'status': status}, env=env)


def site_languages(env=None):
    """Active website language codes from the `web_languages` setting, default language first; [] when unset."""
    settings = {s.get('name'): s.get('value') for s in (request_json('GET', '/api/v1/settings', env=env) or {}).get('items') or []}
    try:
        langs = [l for l in json.loads(settings.get('web_languages') or '[]') if l.get('active')]
    except (TypeError, ValueError):
        return []
    default = settings.get('web_default_language')
    codes = [l['code'] for l in sorted(langs, key=lambda l: l.get('displayOrder') or 0)]
    return sorted(codes, key=lambda c: c != default)


def update_payload(live_post, **changes):
    """PUT body rebuilt from the live post so slug, type, status and menu link survive.

    This server rejects metadata/terms/priority/publishedAt/parentId/commentStatus
    in the PUT body with 400 {"fields":"invalid"}; omitting them keeps stored values.
    """
    body = {
        'title': live_post.get('title') or '',
        'content': live_post.get('content') or '',
        'summary': live_post.get('summary') or '',
        'contentType': live_post['contentType'],
        'status': live_post['status'],
        'postType': live_post['postType'],
        'slug': live_post['slug'],
        'additionalHead': live_post.get('additionalHead') or '',
        'additionalFoot': live_post.get('additionalFoot') or '',
    }
    if live_post.get('menu'):
        body['menuId'] = live_post['menu']['id']
    body.update({k: v for k, v in changes.items() if v is not None})
    return body


def main(argv):
    if len(argv) >= 2 and argv[0] == 'get':
        print(json.dumps(redact(request_json('GET', argv[1])), ensure_ascii=False, indent=1))
    elif argv[:1] == ['whoami']:
        env = load_env()
        roles = request_json('GET', '/api/v1/admins/me/roles', env=env)
        print(json.dumps({'environment': env.get('name'), 'admin_url': env['admin_url'],
                          'roles': [r.get('name') for r in roles or []]}, indent=1))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except EzyError as err:
        print(f'error: {err}', file=sys.stderr)
        sys.exit(2)
