#!/usr/bin/env python3
import argparse
import base64
import hashlib
import html
import http.server
import json
import os
import re
import secrets
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser

DEFAULT_BASE_URL = 'https://ezyplatform.com'
CRED_FILE = os.path.expanduser('~/.ezyplatform/credentials.json')
CLIENT_NAME = 'ezymarket'
USER_AGENT = 'ezymarket-cli/1.0'
LOGIN_TIMEOUT = 600
ICON_RATIO = (512, 512)
BANNER_RATIO = (1640, 720)


def die(message, code=1):
    print('ERROR: ' + message, file=sys.stderr)
    sys.exit(code)


def b64url(data):
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


def read_creds():
    try:
        with open(CRED_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def load_token(base):
    entry = read_creds().get(base)
    return entry.get('accessToken') if isinstance(entry, dict) else None


def save_token(base, token):
    creds = read_creds()
    creds[base] = {'accessToken': token, 'savedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    os.makedirs(os.path.dirname(CRED_FILE), exist_ok=True)
    fd = os.open(CRED_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(creds, f, indent=2)
    os.chmod(CRED_FILE, 0o600)


def remove_token(base):
    creds = read_creds()
    if base in creds:
        del creds[base]
        fd = os.open(CRED_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(creds, f, indent=2)
        return True
    return False


def raw_request(base, method, path, body=None, ctype=None, token=None):
    r = urllib.request.Request(base + path, data=body, method=method)
    r.add_header('User-Agent', USER_AGENT)
    if token:
        r.add_header('Authorization', 'Bearer ' + token)
    if ctype:
        r.add_header('Content-Type', ctype)
    try:
        with urllib.request.urlopen(r, timeout=900) as resp:
            return resp.status, resp.read().decode(errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors='replace')
    except urllib.error.URLError as e:
        die('cannot reach %s: %s' % (base, e.reason))


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    result = {}

    def log_message(self, *args):
        pass

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path != '/callback':
            self.send_response(404)
            self.end_headers()
            return
        q = urllib.parse.parse_qs(url.query)
        code = (q.get('code') or [None])[0]
        state = (q.get('state') or [None])[0]
        ok = code and state == self.server.expected_state
        self.send_response(200 if ok else 400)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        title = 'Logged in' if ok else 'Login failed'
        msg = 'You can close this tab and return to the terminal.' if ok else 'Invalid state or missing code. Run the login command again.'
        self.wfile.write(('<!doctype html><meta charset="utf-8"><title>%s</title>'
                          '<body style="font-family:sans-serif;text-align:center;padding:48px">'
                          '<h2>%s</h2><p>%s</p></body>' % (title, title, msg)).encode())
        if ok:
            self.server.code = code


def token_works(base, token):
    if not token:
        return False
    st, _ = raw_request(base, 'GET', '/api/v1/account/projects?limit=1', token=token)
    return st not in (401, 403)


def login(base, force=False):
    old = load_token(base)
    if not force and token_works(base, old):
        print('Already logged in to %s (token still valid).' % base)
        return old
    verifier = b64url(secrets.token_bytes(32))
    challenge = b64url(hashlib.sha256(verifier.encode()).digest())
    state = b64url(secrets.token_bytes(16))
    server = http.server.HTTPServer(('127.0.0.1', 0), CallbackHandler)
    server.expected_state = state
    server.code = None
    server.timeout = 1
    redirect_uri = 'http://127.0.0.1:%d/callback' % server.server_address[1]
    query = urllib.parse.urlencode({
        'client_name': CLIENT_NAME,
        'redirect_uri': redirect_uri,
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    })
    url = '%s/ezylogin/cli/authorize?%s' % (base, query)
    print('Opening the browser to approve the CLI login.')
    print('If it does not open, visit this URL yourself:\n' + url)
    print('On the approval page, check that the result address is %s, then click Approve.' % redirect_uri)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    deadline = time.time() + LOGIN_TIMEOUT
    while server.code is None and time.time() < deadline:
        server.handle_request()
    server.server_close()
    if server.code is None:
        die('login timed out after %d seconds' % LOGIN_TIMEOUT, 3)
    body = json.dumps({'code': server.code, 'codeVerifier': verifier, 'redirectUri': redirect_uri}).encode()
    st, txt = raw_request(base, 'POST', '/ezylogin/api/v1/cli/token', body, 'application/json')
    if st == 403 and 'cliLogin' in txt:
        die('CLI login is disabled on %s (cliLogin: notAllowed). Contact the marketplace support.' % base, 3)
    if st >= 400:
        die('token exchange failed: HTTP %d %s' % (st, txt[:300]), 3)
    data = json.loads(txt)
    save_token(base, data['accessToken'])
    expired = data.get('accessTokenExpiredAt')
    when = time.strftime('%Y-%m-%d %H:%M', time.localtime(expired / 1000)) if expired else 'unknown'
    print('Logged in. Token saved to %s (mode 600), expires at %s.' % (CRED_FILE, when))
    return data['accessToken']


class Api:
    def __init__(self, base):
        self.base = base
        self.token = load_token(base)

    def call(self, method, path, body=None, ctype=None, retried=False):
        if not self.token:
            self.token = login(self.base)
        st, txt = raw_request(self.base, method, path, body, ctype, self.token)
        if st == 401 and not retried:
            print('Token expired or revoked, logging in again...')
            self.token = login(self.base, force=True)
            return self.call(method, path, body, ctype, True)
        return st, txt

    def json(self, method, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        return self.call(method, path, body, 'application/json' if body is not None else None)


def explain(st, txt):
    hints = {
        'permission': 'your account has no permission on this project: the project owner must add you at /account/members with a role that includes project management',
        'projectType': 'the marketplace does not currently allow users to publish this project type',
        'releaseBundleOf': 'the project is still SETTING_UP: set both an icon and a banner with the update command first',
        'bundleSignature': 'the newest version has not been approved (signed) by the marketplace yet',
        'cliLogin': 'CLI login is disabled on this site',
    }
    for k, v in hints.items():
        if '"%s"' % k in txt:
            return 'HTTP %d %s\nHint: %s' % (st, txt[:800], v)
    return 'HTTP %d %s' % (st, txt[:800])


def must(result, what):
    st, txt = result
    if st >= 400:
        die('%s failed: %s' % (what, explain(st, txt)))
    return txt


def text_of(page):
    page = re.sub(r'(?is)<script.*?</script>|<style.*?</style>', ' ', page)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', page))).strip()


def project_simple(api, name):
    return json.loads(must(api.call('GET', '/api/v1/account/projects/%s/simple' % urllib.parse.quote(name)), 'get project'))


def image_size(path):
    with open(path, 'rb') as f:
        head = f.read(26)
        if head[:8] == b'\x89PNG\r\n\x1a\n':
            return struct.unpack('>II', head[16:24])
        if head[:2] == b'\xff\xd8':
            f.seek(2)
            while True:
                marker = f.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    return None
                if marker[1] in (0xC0, 0xC1, 0xC2):
                    f.read(3)
                    h, w = struct.unpack('>HH', f.read(4))
                    return w, h
                seg = struct.unpack('>H', f.read(2))[0]
                f.seek(seg - 2, 1)
    return None


def multipart(fields, files):
    boundary = '----ezymarket' + uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (boundary, k, v)).encode())
    for k, (fname, data, ctype) in files.items():
        parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\n'
                      'Content-Type: %s\r\n\r\n' % (boundary, k, fname, ctype)).encode() + data + b'\r\n')
    parts.append(('--%s--\r\n' % boundary).encode())
    return b''.join(parts), 'multipart/form-data; boundary=' + boundary


def read_notes(path):
    with open(path) as f:
        notes = f.read().strip()
    if not notes:
        die('notes file is empty')
    if re.search(r'(?i)<script', notes):
        die('notes must not contain <script>')
    return notes


def cmd_login(a):
    login(a.base_url, a.force)


def cmd_logout(a):
    print('Local token removed.' if remove_token(a.base_url) else 'No local token for %s.' % a.base_url)


def cmd_whoami(a):
    token = load_token(a.base_url)
    print('logged in' if token_works(a.base_url, token) else 'not logged in (run login)')


def cmd_projects(a):
    api = Api(a.base_url)
    q = urllib.parse.urlencode({'limit': a.limit, 'keyword': a.keyword or ''})
    data = json.loads(must(api.call('GET', '/api/v1/account/projects?' + q), 'list projects'))
    for p in data.get('items', []):
        print(json.dumps(p, ensure_ascii=False))


def cmd_categories(a):
    api = Api(a.base_url)
    page = must(api.call('GET', '/account/projects/create'), 'open create page')
    m = re.search(r'(?is)<select[^>]*id="categoryId"[^>]*>(.*?)</select>', page)
    if not m:
        die('cannot find the category list on /account/projects/create')
    for value, label in re.findall(r'(?is)<option[^>]*value="(\d+)"[^>]*>(.*?)</option>', m.group(1)):
        if value != '0':
            print('%s\t%s' % (value, text_of(label)))


def cmd_upload_media(a):
    if not os.path.isfile(a.file):
        die('file not found: ' + a.file)
    size = image_size(a.file)
    if a.kind and size:
        rw, rh = ICON_RATIO if a.kind == 'icon' else BANNER_RATIO
        if size[0] * rh != size[1] * rw:
            die('%s must have the ratio %dx%d, got %dx%d' % (a.kind, rw, rh, size[0], size[1]))
    ctype = 'image/png' if a.file.lower().endswith('.png') else 'image/jpeg' if re.search(r'(?i)\.jpe?g$', a.file) else 'application/octet-stream'
    with open(a.file, 'rb') as f:
        body, ct = multipart({}, {'file': (os.path.basename(a.file), f.read(), ctype)})
    api = Api(a.base_url)
    media = json.loads(must(api.call('POST', '/api/v1/media/add', body, ct), 'upload media'))
    print(json.dumps({'id': media.get('id'), 'name': media.get('name'), 'url': '%s/api/v1/media/%s' % (a.base_url, media.get('name')), 'size': size}, ensure_ascii=False))


def load_body(path):
    with open(path) as f:
        body = json.load(f)
    if 'descriptionFile' in body:
        with open(os.path.join(os.path.dirname(os.path.abspath(path)), body.pop('descriptionFile'))) as f:
            body['description'] = f.read().strip()
    return body


def check_body(body):
    errs = []
    name = body.get('projectName') or ''
    if not re.fullmatch(r'[a-zA-Z0-9\s]{2,60}', name):
        errs.append('projectName: 2..60 chars, letters, digits and spaces only')
    if not re.fullmatch(r'[a-z0-9_.]{12,120}', body.get('packageName') or ''):
        errs.append('packageName: 12..120 chars of a-z 0-9 _ . (e.g. com.example.myplugin)')
    sd = body.get('shortDescription') or ''
    if not 9 <= len(sd) <= 40:
        errs.append('shortDescription: 9..40 chars (got %d)' % len(sd))
    d = body.get('description') or ''
    if not 100 <= len(d) <= 6000:
        errs.append('description: 100..6000 chars (got %d)' % len(d))
    if re.search(r'(?i)<script', d):
        errs.append('description: <script> is not allowed')
    for t in body.get('tags') or []:
        if not re.fullmatch(r'[a-z0-9\-\s]{2,32}', t.lower()):
            errs.append('tags: "%s" must be 2..32 chars of a-z 0-9 - space' % t)
    if int(body.get('categoryId') or 0) <= 0:
        errs.append('categoryId: required (see the categories command)')
    yt = body.get('introYouTubeVideoId') or ''
    if yt and (not 8 <= len(yt) <= 60 or "'" in yt or '"' in yt):
        errs.append('introYouTubeVideoId: 8..60 chars, the video id only, not the URL')
    if errs:
        die('invalid project body:\n  ' + '\n  '.join(errs))


def cmd_create(a):
    body = load_body(a.json)
    check_body(body)
    if not body.get('iconImageId') or not body.get('bannerImageId'):
        print('WARNING: without iconImageId and bannerImageId the project stays SETTING_UP and versions cannot be uploaded.')
    api = Api(a.base_url)
    print(must(api.json('POST', '/api/v1/account/projects/create', body), 'create project'))


def cmd_get(a):
    api = Api(a.base_url)
    p = json.loads(must(api.call('GET', '/api/v1/account/projects/%s' % urllib.parse.quote(a.name)), 'get project'))
    body = {
        'projectName': p.get('displayName'),
        'packageName': p.get('packageName'),
        'iconImageId': (p.get('iconImage') or {}).get('id', 0),
        'bannerImageId': (p.get('bannerImage') or {}).get('id', 0),
        'introYouTubeVideoId': p.get('introYouTubeVideoId'),
        'categoryId': (p.get('category') or {}).get('id', 0),
        'tags': p.get('tagNames') or [],
        'price': p.get('price'),
        'originalPrice': p.get('originalPrice'),
        'shortDescription': p.get('shortDescription'),
        'description': p.get('description'),
    }
    print('# project id %s, url name %s' % (p.get('id'), p.get('name')), file=sys.stderr)
    out = json.dumps(body, indent=2, ensure_ascii=False)
    if a.out:
        with open(a.out, 'w') as f:
            f.write(out + '\n')
        print('saved editable body to ' + a.out, file=sys.stderr)
    else:
        print(out)


def cmd_update(a):
    body = load_body(a.json)
    check_body(body)
    api = Api(a.base_url)
    pid = project_simple(api, a.name)['id']
    must(api.json('PUT', '/api/v1/account/projects/%d' % pid, body), 'update project')
    print('updated project %s (id %d)' % (a.name, pid))


def cmd_status(a):
    api = Api(a.base_url)
    p = project_simple(api, a.name)
    print('project:', json.dumps(p, ensure_ascii=False))
    page = must(api.call('GET', '/account/projects/%s' % urllib.parse.quote(a.name)), 'open project page')
    newest = 'none'
    if re.search(r'data-bs-target="#cancel-version-modal"', page):
        newest = 'REVIEWING (waiting for the marketplace review)'
    elif re.search(r'data-bs-target="#release-version-modal"', page):
        newest = 'RELEASABLE (approved, run release to publish)'
    elif re.search(r"showReleaseProjectModal\('[^']+'\)", page):
        newest = 'SETTING_UP or REJECTED (upload the bundle again; open the project page to read the review notes)'
    elif re.search(r'showReleaseProjectModal\(\)', page):
        newest = 'RELEASED or no version yet (a new version can be uploaded)'
    print('newest version:', newest)
    print('page: %s/account/projects/%s' % (a.base_url, a.name))
    st, txt = raw_request(a.base_url, 'GET', '/api/v1/released-projects/%s' % urllib.parse.quote(a.name))
    print('public listing: HTTP %d' % st)


def cmd_upload_version(a):
    api = Api(a.base_url)
    p = project_simple(api, a.name)
    expected = '%s-%s.zip' % (p['name'], a.version)
    if os.path.basename(a.zip) != expected:
        die('the bundle file must be named %s (project url name + "-" + version)' % expected)
    if not re.fullmatch(r'\d+\.\d+\.\d+', a.version):
        die('version must look like 1.2.3')
    if p.get('status') == 'SETTING_UP':
        die('project is SETTING_UP: set icon and banner first (get -> edit -> update)')
    with open(a.zip, 'rb') as f:
        data = f.read()
    if data[:2] != b'PK':
        die('the bundle is not a zip file')
    print('uploading %s (%.1f MB)...' % (expected, len(data) / 1048576.0))
    body, ct = multipart(
        {'projectVersion': a.version, 'releaseNotes': read_notes(a.notes_file)},
        {'file': (expected, data, 'application/zip')}
    )
    txt = must(api.call('POST', '/api/v1/account/projects/%d/versions/newest/create-or-update' % p['id'], body, ct), 'upload version')
    try:
        v = json.loads(txt)
        print('uploaded: version id %s, name %s; now waiting for the marketplace review' % (v.get('id'), v.get('name')))
    except ValueError:
        print('uploaded:', txt[:300])


def cmd_upload_source(a):
    api = Api(a.base_url)
    p = project_simple(api, a.name)
    expected = '%s-%s-sources.zip' % (p['name'], a.version)
    if os.path.basename(a.zip) != expected:
        die('the source bundle file must be named ' + expected)
    with open(a.zip, 'rb') as f:
        data = f.read()
    body, ct = multipart({'notes': read_notes(a.notes_file)}, {'file': (expected, data, 'application/zip')})
    print(must(api.call('PUT', '/api/v1/account/projects/%d/versions/%s/source-code' % (p['id'], a.version), body, ct), 'upload source code'))


def cmd_add_gallery(a):
    api = Api(a.base_url)
    pid = project_simple(api, a.name)['id']
    must(api.json('PUT', '/api/v1/account/projects/%d/medias/%d' % (pid, a.media_id), {}), 'add gallery media')
    print('added media %d to the gallery of %s' % (a.media_id, a.name))


def newest_action(a, action, method='POST'):
    api = Api(a.base_url)
    pid = project_simple(api, a.name)['id']
    must(api.json(method, '/api/v1/account/projects/%d/versions/newest%s' % (pid, action), None if method == 'DELETE' else {}), action or 'delete')


def cmd_release(a):
    newest_action(a, '/release')
    print('released; public page: %s/market/items/%s' % (a.base_url, a.name))


def cmd_cancel(a):
    newest_action(a, '/cancel')
    print('newest version review cancelled')


def cmd_delete_newest(a):
    newest_action(a, '', 'DELETE')
    print('newest (unreleased) version deleted')


def main():
    p = argparse.ArgumentParser(description='Submit plugins and themes to the EzyPlatform marketplace')
    p.add_argument('--base-url', default=os.environ.get('EZYMARKET_BASE_URL', DEFAULT_BASE_URL))
    sp = p.add_subparsers(dest='cmd', required=True)

    s = sp.add_parser('login'); s.add_argument('--force', action='store_true'); s.set_defaults(f=cmd_login)
    sp.add_parser('logout').set_defaults(f=cmd_logout)
    sp.add_parser('whoami').set_defaults(f=cmd_whoami)
    s = sp.add_parser('projects'); s.add_argument('--keyword'); s.add_argument('--limit', type=int, default=20); s.set_defaults(f=cmd_projects)
    sp.add_parser('categories').set_defaults(f=cmd_categories)
    s = sp.add_parser('upload-media'); s.add_argument('file'); s.add_argument('--kind', choices=['icon', 'banner']); s.set_defaults(f=cmd_upload_media)
    s = sp.add_parser('create'); s.add_argument('--json', required=True); s.set_defaults(f=cmd_create)
    s = sp.add_parser('get'); s.add_argument('--name', required=True); s.add_argument('--out'); s.set_defaults(f=cmd_get)
    s = sp.add_parser('update'); s.add_argument('--name', required=True); s.add_argument('--json', required=True); s.set_defaults(f=cmd_update)
    s = sp.add_parser('status'); s.add_argument('--name', required=True); s.set_defaults(f=cmd_status)
    s = sp.add_parser('upload-version'); s.add_argument('--name', required=True); s.add_argument('--version', required=True)
    s.add_argument('--zip', required=True); s.add_argument('--notes-file', required=True); s.set_defaults(f=cmd_upload_version)
    s = sp.add_parser('upload-source'); s.add_argument('--name', required=True); s.add_argument('--version', required=True)
    s.add_argument('--zip', required=True); s.add_argument('--notes-file', required=True); s.set_defaults(f=cmd_upload_source)
    s = sp.add_parser('add-gallery'); s.add_argument('--name', required=True); s.add_argument('--media-id', type=int, required=True); s.set_defaults(f=cmd_add_gallery)
    for n, fn in (('release', cmd_release), ('cancel', cmd_cancel), ('delete-newest', cmd_delete_newest)):
        s = sp.add_parser(n); s.add_argument('--name', required=True); s.set_defaults(f=fn)

    a = p.parse_args()
    a.base_url = a.base_url.rstrip('/')
    a.f(a)


if __name__ == '__main__':
    main()
