#!/usr/bin/env python3
import argparse
import base64
import datetime
import hashlib
import http.server
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
import zipfile

VERSION = '1.0.0'
USER_AGENT = 'ezyplatform-publish-skill/' + VERSION + ' (Python)'
CLIENT_NAME = 'AI skill publisher'
DEFAULT_MARKET_URL = 'https://ezyplatform.com'
STATE_DIR = os.path.join(os.path.expanduser('~'), '.ezyplatform')
STATE_FILE = os.path.join(STATE_DIR, 'publish-skill.json')
CLI_TOKEN_API = '/ezylogin/api/v1/cli/token'
SKILL_API = '/api/v1/account/ai-skill-library'
EXIT_NEED = 3

MAX_FILE_COUNT = 100
MAX_PATH_LENGTH = 255
MAX_CONTENT_LENGTH = 30000
MAX_TITLE_LENGTH = 300
MAX_CATEGORY_LENGTH = 256
DEFAULT_MAX_ZIP_MB = 2
DEFAULT_MAX_EXTRACTED_MB = 5

SKIPPED_DIRS = {
    '.git', '.svn', '.hg', '.idea', '.vscode', 'node_modules',
    '__pycache__', '__MACOSX', 'target', 'build', 'dist', '.gradle', '.venv', 'venv',
}
SKIPPED_FILE_RES = [re.compile(p) for p in (
    r'^\.DS_Store$', r'^\._', r'^Thumbs\.db$', r'\.pyc$', r'\.class$', r'~$', r'\.swp$',
)]
SENSITIVE_FILE_RES = [re.compile(p, re.I) for p in (
    r'^\.env($|\.)', r'\.pem$', r'\.key$', r'\.p12$', r'\.pfx$', r'\.jks$', r'\.keystore$',
    r'^id_(rsa|dsa|ecdsa|ed25519)', r'^environment\.json$', r'^setup\.properties$',
    r'\.(sqlite|sqlite3|db)$', r'^credentials', r'\.log$', r'^\.npmrc$', r'^\.pypirc$',
    r'^\.netrc$', r'\.jws$', r'\.kdbx$', r'\.ovpn$', r'^\.htpasswd$', r'^publish-skill\.json$',
)]
PLACEHOLDER_RE = re.compile(r'[<>{}$*]|x{3,}|\.\.\.|example|placeholder|your[_-]|changeme|^\?+$', re.I)
CONTENT_RES = [
    ('private key', re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
    ('aws access key', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ('github token', re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b')),
    ('api key (sk-)', re.compile(r'\bsk-[A-Za-z0-9_-]{20,}')),
    ('slack token', re.compile(r'\bxox[abprs]-[A-Za-z0-9-]{10,}')),
    ('google api key', re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b')),
    ('jwt', re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}')),
    ('bcrypt hash', re.compile(r'\$2[abxy]\$\d\d\$[./A-Za-z0-9]{53}')),
    ('bearer token', re.compile(r'\bBearer\s+[A-Za-z0-9._~+/=-]{20,}')),
    ('credentials in url', re.compile(r'://[^\s/:@<>{}]+:[^\s/@<>{}]+@')),
    ('home path', re.compile(r'(/Users/|/home/)(?!<|\$|USER|user\b|username\b|me\b|you\b)[A-Za-z0-9._-]+|[A-Za-z]:\\Users\\(?!<|%)[A-Za-z0-9._-]+')),
    ('email', re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')),
]
ASSIGNMENT_RE = re.compile(
    r'''(?i)\b([\w.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key)[\w.-]*)\s*[:=]\s*["']?([^\s"',;)]{6,})'''
)
SAFE_EMAIL_RE = re.compile(r'@(example\.(com|org|net)|localhost)$|^(noreply|no-reply|user|admin|you|name)@', re.I)


class HttpResult:
    def __init__(self, status, body):
        self.status = status
        self.body = body

    def text(self):
        return self.body.decode('utf-8', errors='replace')

    def json(self):
        try:
            return json.loads(self.text() or 'null')
        except ValueError:
            return None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def call(method, url, body=None, token=None, timeout=120, content_type='application/json'):
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('User-Agent', USER_AGENT)
    req.add_header('Accept', 'application/json')
    if data is not None:
        req.add_header('Content-Type', content_type)
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    try:
        with OPENER.open(req, timeout=timeout) as resp:
            return HttpResult(resp.status, resp.read())
    except urllib.error.HTTPError as e:
        return HttpResult(e.code, e.read() or b'')
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError):
        return HttpResult(0, b'')


def out(key, value):
    print('%s=%s' % (key, value))


def need(code, message):
    print('NEED %s: %s' % (code, message))
    sys.exit(EXIT_NEED)


def die(message):
    print('ERROR: ' + message, file=sys.stderr)
    sys.exit(1)


def load_state():
    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE_FILE + '.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)
    try:
        os.chmod(STATE_FILE, 0o600)
    except OSError:
        pass


def market_url(args):
    url = getattr(args, 'market_url', None) or os.environ.get('EZY_MARKET_URL') or DEFAULT_MARKET_URL
    url = url.strip().rstrip('/')
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'https://' + url
    return url


def saved_token(market):
    entry = load_state().get('tokens', {}).get(market)
    if not entry or not entry.get('accessToken'):
        return None
    expired_at = entry.get('expiredAt')
    if expired_at and expired_at <= int(time.time() * 1000) + 60000:
        return None
    return entry['accessToken']


def token_state(market, token):
    if not token:
        return 'missing'
    res = call('GET', market + SKILL_API + '?limit=1', token=token, timeout=30)
    if res.status == 200:
        return 'valid'
    if res.status in (401, 403):
        return 'expired'
    if res.status == 0:
        return 'unreachable'
    return 'error_%s' % res.status


def require_token(market):
    token = saved_token(market)
    state = token_state(market, token)
    if state == 'valid':
        return token
    if state == 'unreachable':
        die('%s does not answer, check the internet connection' % market)
    if state.startswith('error_'):
        die('%s answered HTTP %s when checking the sign-in' % (market, state[6:]))
    need('login', 'not signed in to %s (token %s): run login' % (market, state))


def api(market, token, method, path, body=None, content_type='application/json', ok=(200, 201, 204)):
    res = call(method, market + path, body=body, token=token, content_type=content_type)
    if res.status in ok:
        return res
    if res.status == 401:
        need('login', 'the sign-in expired or was signed out: run login')
    if res.status == 0:
        die('%s does not answer' % market)
    data = res.json()
    explain_error(res.status, data, res.text())


ERROR_HINTS = {
    ('user', 'notSkillSeller'): ('seller', 'the account is not a skill seller yet: ask the user, then run register-seller'),
    ('seller', 'removed'): ('seller_removed', 'the marketplace disabled selling for this account: the user must contact https://ezyplatform.com/contact-us'),
    ('sellerRegistration', 'disabled'): ('seller_registration_closed', 'seller registration is closed on the marketplace: the user must contact https://ezyplatform.com/contact-us'),
    ('title', 'duplicated'): ('title_duplicated', 'a skill with this title already exists on the marketplace: if it is the user\'s own skill (see list) use update, otherwise choose another title'),
    ('skill', 'notFound'): ('skill_not_found', 'no skill with this id belongs to the signed-in account: run list'),
    ('project', 'noReleasedVersion'): ('project_not_released', 'the project has no released version yet, a skill can only be linked to a released project'),
    ('project', 'notFound'): ('project_not_found', 'no project with this id: run projects'),
}


def explain_error(status, data, text):
    if isinstance(data, dict):
        for key, value in data.items():
            hint = ERROR_HINTS.get((key, value))
            if hint:
                need(hint[0], hint[1])
        if status == 400 and data.get('file'):
            die('the server refused the package: file=%s (skillPackageTooLarge = zip over 2 MB or over 5 MB extracted, '
                'tooMany = over 100 files, skillPackageInvalidPath = bad file name, skillPackageMainFileOverLength = SKILL.md over 30000 characters, '
                'skillPackageMainFileEmpty = empty SKILL.md, invalid = not a zip or not UTF-8)' % data['file'])
    die('HTTP %s %s' % (status, text[:500]))


def items_of(page):
    if isinstance(page, dict):
        return page.get('items') or []
    if isinstance(page, list):
        return page
    return []


def cmd_check(args):
    market = market_url(args)
    out('MARKET', market)
    home = call('GET', market + '/', timeout=30)
    if home.status == 0:
        need('offline', '%s does not answer: check the internet connection' % market)
    token = saved_token(market)
    state = token_state(market, token)
    out('TOKEN', state)
    out('TOKEN_FILE', STATE_FILE)
    if state != 'valid':
        need('login', 'run login so the user approves this tool on %s' % market)
    print('READY')


def cmd_login(args):
    market = market_url(args)
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).decode('ascii').rstrip('=')
    expected_state = secrets.token_urlsafe(24)
    result = {}
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != '/callback':
                self.send_response(404)
                self.end_headers()
                return
            q = urllib.parse.parse_qs(parsed.query)
            ok = q.get('state', [''])[0] == expected_state and q.get('code')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            message = ('Signed in. You can close this tab and go back to your AI assistant.' if ok
                       else 'Sign in failed. Go back to your AI assistant and try again.')
            self.wfile.write(('<!doctype html><meta charset="utf-8"><title>EzyPlatform</title>'
                              '<body style="font-family:sans-serif;padding:40px">%s</body>' % message).encode('utf-8'))
            if ok:
                result['code'] = q['code'][0]
            else:
                result['error'] = 'state'
            done.set()

    server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    redirect_uri = 'http://127.0.0.1:%d/callback' % server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    authorize_url = market + '/ezylogin/cli/authorize?' + urllib.parse.urlencode({
        'client_name': CLIENT_NAME,
        'redirect_uri': redirect_uri,
        'state': expected_state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    })
    print('OPEN_URL=' + authorize_url, flush=True)
    if not args.no_browser:
        try:
            opened = webbrowser.open(authorize_url)
        except Exception:
            opened = False
        print('BROWSER_OPENED=%s' % ('yes' if opened else 'no'), flush=True)
    print('WAITING: the user signs in to %s if needed and clicks Approve (up to %d seconds)' % (market, args.timeout), flush=True)
    finished = done.wait(args.timeout)
    server.shutdown()
    if not finished:
        die('no approval within %d seconds; run login again' % args.timeout)
    if result.get('error'):
        die('the callback did not match this login (state mismatch); run login again')
    res = call('POST', market + CLI_TOKEN_API, body={
        'code': result['code'],
        'codeVerifier': verifier,
        'redirectUri': redirect_uri,
    })
    if res.status == 403:
        need('cli_login_disabled', '%s does not allow signing in from tools right now: the user must contact the marketplace' % market)
    if res.status != 200:
        die('token exchange failed: HTTP %s %s' % (res.status, res.text()[:300]))
    data = res.json() or {}
    if not data.get('accessToken'):
        die('token exchange returned no token')
    st = load_state()
    st.setdefault('tokens', {})[market] = {
        'accessToken': data['accessToken'],
        'expiredAt': data.get('accessTokenExpiredAt'),
        'savedAt': int(time.time() * 1000),
    }
    save_state(st)
    out('RESULT_LOGIN', 'ok')
    out('RESULT_TOKEN_FILE', STATE_FILE)
    expired = data.get('accessTokenExpiredAt')
    if expired:
        out('RESULT_EXPIRES_AT', datetime.datetime.fromtimestamp(expired / 1000).isoformat(timespec='minutes'))


def cmd_logout(args):
    market = market_url(args)
    st = load_state()
    entry = st.get('tokens', {}).pop(market, None)
    save_state(st)
    out('RESULT_LOGOUT', 'removed' if entry else 'none')
    if entry:
        print('note: the session still exists on the marketplace until it expires; '
              'the user can sign it out in the list of signed-in devices of their account')


def is_skipped(rel_path):
    parts = rel_path.split('/')
    if any(p in SKIPPED_DIRS for p in parts[:-1]):
        return True
    return any(r.search(parts[-1]) for r in SKIPPED_FILE_RES)


def collect_files(skill_dir):
    files = []
    for root, dirs, names in os.walk(skill_dir):
        dirs[:] = sorted(d for d in dirs if d not in SKIPPED_DIRS)
        for name in sorted(names):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, skill_dir).replace(os.sep, '/')
            if os.path.islink(full):
                files.append((rel, full, 'symlink'))
            elif not is_skipped(rel):
                files.append((rel, full, None))
    return files


def personal_markers():
    markers = set()
    try:
        email = subprocess.run(['git', 'config', 'user.email'], capture_output=True, text=True).stdout.strip()
        if email:
            markers.add(email)
    except OSError:
        pass
    home = os.path.expanduser('~')
    if home not in ('/', ''):
        markers.add(home)
    return markers


def mask(value):
    value = value.strip()
    if len(value) <= 8:
        return value[:2] + '***'
    return value[:4] + '***' + value[-2:]


def read_frontmatter(text):
    text = text.replace('\r\n', '\n')
    if not text.startswith('---\n'):
        return {}
    end = text.find('\n---', 4)
    if end < 0:
        return {}
    result = {}
    for line in text[4:end].split('\n'):
        m = re.match(r'^([A-Za-z_][\w-]*)\s*:\s*(.*)$', line)
        if m:
            result[m.group(1)] = m.group(2).strip().strip('"\'')
    return result


def read_text(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


def skill_files_of(files):
    return [rel for rel, _, kind in files if not kind and rel.split('/')[-1] == 'SKILL.md' and rel.count('/') <= 1]


def scan(skill_dir):
    skill_dir = os.path.abspath(skill_dir)
    if not os.path.isdir(skill_dir):
        die('not a folder: %s' % skill_dir)
    findings = []
    files = collect_files(skill_dir)
    markers = personal_markers()
    skill_paths = skill_files_of(files)
    if not skill_paths:
        findings.append(('SKILL.md', 0, 'structure', 'no SKILL.md at the folder root (or in its direct sub-folders for a bundle)'))
    for rel in skill_paths:
        content = read_text(os.path.join(skill_dir, rel))
        front = read_frontmatter(content)
        if not front.get('name') or not front.get('description'):
            findings.append((rel, 1, 'structure', 'frontmatter needs name and description'))
        if rel == 'SKILL.md' and len(content) > MAX_CONTENT_LENGTH:
            findings.append((rel, 0, 'structure', 'SKILL.md has %d characters, the marketplace max is %d: move details into references/ files' % (len(content), MAX_CONTENT_LENGTH)))
    root_name = len(os.path.basename(skill_dir)) + 1
    for rel, full, kind in files:
        name = rel.split('/')[-1]
        if kind == 'symlink':
            findings.append((rel, 0, 'symlink', 'symbolic link, replace it with the real file or remove it'))
            continue
        if len(rel) + root_name > MAX_PATH_LENGTH or any(ch in rel for ch in '\\:'):
            findings.append((rel, 0, 'structure', 'path too long or contains \\ or :'))
        if any(r.search(name) for r in SENSITIVE_FILE_RES):
            findings.append((rel, 0, 'sensitive file', 'this kind of file usually holds secrets or private data'))
            continue
        with open(full, 'rb') as f:
            raw = f.read()
        if b'\0' in raw[:8192]:
            findings.append((rel, 0, 'binary', 'binary file, check it by hand (%d bytes)' % len(raw)))
            continue
        text = raw.decode('utf-8', errors='replace')
        for no, line in enumerate(text.splitlines(), 1):
            for marker in markers:
                if marker and marker in line:
                    findings.append((rel, no, 'personal data', 'contains ' + mask(marker)))
            for label, regex in CONTENT_RES:
                for m in regex.finditer(line):
                    value = m.group(0)
                    if label == 'email' and SAFE_EMAIL_RE.search(value):
                        continue
                    if label == 'credentials in url' and PLACEHOLDER_RE.search(value):
                        continue
                    findings.append((rel, no, label, mask(value)))
            for m in ASSIGNMENT_RE.finditer(line):
                value = m.group(2)
                if PLACEHOLDER_RE.search(value) or value.startswith('/') or re.match(r'^[A-Za-z_][\w.]*\(', value) \
                        or re.match(r'^(true|false|null|none|required|invalid|\?)$', value, re.I):
                    continue
                if re.match(r'^[A-Za-z_][A-Za-z0-9_.]*$', value) and not re.search(r'\d', value):
                    continue
                findings.append((rel, no, 'secret assignment', m.group(1) + '=' + mask(value)))
    if len(files) > MAX_FILE_COUNT:
        findings.append(('.', 0, 'structure', '%d files, the marketplace max is %d' % (len(files), MAX_FILE_COUNT)))
    return files, findings


def print_scan(skill_dir, files, findings):
    print('skill folder:', os.path.abspath(skill_dir))
    print('files to package (%d):' % len(files))
    for rel, full, kind in files:
        print('  %s%s' % (rel, ' (symlink)' if kind else ' (%d bytes)' % os.path.getsize(full)))
    if findings:
        print('findings (%d):' % len(findings))
        for rel, no, label, detail in findings:
            print('  %s%s [%s] %s' % (rel, ':%d' % no if no else '', label, detail))
    else:
        print('findings: none')


def cmd_scan(args):
    files, findings = scan(args.dir)
    print_scan(args.dir, files, findings)
    sys.exit(1 if findings else 0)


def cmd_pack(args):
    skill_dir = os.path.abspath(args.dir)
    files, findings = scan(skill_dir)
    print_scan(skill_dir, files, findings)
    if findings and not args.force:
        die('refused: fix the findings, or pass --force only after checking that each one is a false positive')
    root_skill = os.path.join(skill_dir, 'SKILL.md')
    front = read_frontmatter(read_text(root_skill)) if os.path.isfile(root_skill) else {}
    root = re.sub(r'[^A-Za-z0-9._-]+', '-', front.get('name') or os.path.basename(skill_dir)).strip('-') or 'skill'
    target = os.path.abspath(args.out or os.path.join(os.getcwd(), root + '.zip'))
    if target.startswith(skill_dir + os.sep):
        die('refused: write the zip outside the skill folder')
    total = 0
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel, full, kind in files:
            if kind:
                continue
            with open(full, 'rb') as f:
                data = f.read()
            total += len(data)
            info = zipfile.ZipInfo(root + '/' + rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    size = os.path.getsize(target)
    out('RESULT_ZIP', target)
    out('RESULT_ZIP_BYTES', size)
    out('RESULT_EXTRACTED_BYTES', total)
    if size > DEFAULT_MAX_ZIP_MB * 1024 * 1024 or total > DEFAULT_MAX_EXTRACTED_MB * 1024 * 1024:
        print('warning: bigger than the marketplace limits (%d MB zip, %d MB extracted), remove big files' % (DEFAULT_MAX_ZIP_MB, DEFAULT_MAX_EXTRACTED_MB))


def zip_skill_content(zip_path):
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = [n for n in z.namelist() if not n.endswith('/')]
            for n in names:
                parts = n.split('/')
                if parts[-1] == 'SKILL.md' and len(parts) <= 2:
                    return z.read(n).decode('utf-8', errors='replace')
    except (OSError, zipfile.BadZipFile):
        die('not a zip file: %s' % zip_path)
    return None


def multipart(data, zip_path):
    boundary = '----EzySkill' + uuid.uuid4().hex
    body = ('--%s\r\nContent-Disposition: form-data; name="data"; filename="blob"\r\n'
            'Content-Type: application/json\r\n\r\n' % boundary).encode() + json.dumps(data).encode('utf-8') + b'\r\n'
    body += ('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\n'
             'Content-Type: application/zip\r\n\r\n' % (boundary, os.path.basename(zip_path))).encode()
    with open(zip_path, 'rb') as f:
        body += f.read()
    body += b'\r\n' + ('--%s--\r\n' % boundary).encode()
    return body, 'multipart/form-data; boundary=' + boundary


def check_meta(title, category):
    if title is not None and (not title.strip() or len(title) > MAX_TITLE_LENGTH):
        die('title is required and must be at most %d characters' % MAX_TITLE_LENGTH)
    if category and len(category.strip()) > MAX_CATEGORY_LENGTH:
        die('category must be at most %d characters' % MAX_CATEGORY_LENGTH)


def price_text(value):
    if value is None:
        return None
    text = str(value).replace(',', '').strip()
    try:
        if float(text) < 0:
            raise ValueError
    except ValueError:
        die('invalid price: %s' % value)
    return text


def default_currency(market):
    res = call('GET', market + '/api/v1/currencies/default', timeout=30)
    return res.json() if res.status == 200 else None


def print_skill(market, s):
    out('ID', s.get('id'))
    out('TITLE', s.get('title'))
    out('STATUS', s.get('status'))
    out('CATEGORY', s.get('categoryName') or '')
    out('DESCRIPTION', (s.get('description') or '').replace('\n', ' '))
    prices = s.get('prices') or []
    out('PRICE', ', '.join(p.get('formattedPriceIncludeIsoCode') or str(p.get('price')) for p in prices) or 'free')
    pkg = s.get('skillPackage') or {}
    if pkg:
        out('PACKAGE', '%s files, %s scripts, %s skills, %s bytes' % (pkg.get('fileCount'), pkg.get('scriptFileCount'), pkg.get('skillCount'), pkg.get('totalSize')))
    revision = s.get('revision')
    if revision:
        out('PENDING_UPDATE', '%s (waiting for review, cancel with cancel-update)' % revision.get('status'))
    if s.get('status') == 'PUBLISHED' and s.get('slug'):
        out('PUBLIC_URL', '%s/ezyai/skill-library/%s' % (market, s['slug']))
    out('MANAGE_URL', market + '/account/ai-skill-library')


def get_skill(market, token, skill_id):
    return api(market, token, 'GET', '%s/%d' % (SKILL_API, skill_id)).json() or {}


def cmd_categories(args):
    market = market_url(args)
    query = {'limit': 100}
    if args.keyword:
        query['keyword'] = args.keyword
    res = call('GET', market + '/api/v1/skill-library/categories?' + urllib.parse.urlencode(query), timeout=30)
    if res.status != 200:
        die('cannot read categories: HTTP %s' % res.status)
    for c in items_of(res.json()):
        print('%s\t%s' % (c.get('originalName') or c.get('name'), c.get('name')))


def cmd_currency(args):
    market = market_url(args)
    currency = default_currency(market)
    if not currency:
        die('cannot read the default currency')
    for key in ('id', 'isoCode', 'name', 'symbol'):
        if key in currency:
            out(key.upper(), currency[key])


def cmd_list(args):
    market = market_url(args)
    token = require_token(market)
    query = {'limit': 50}
    if args.keyword:
        query['keyword'] = args.keyword
    if args.status:
        query['status'] = args.status
    page = api(market, token, 'GET', SKILL_API + '?' + urllib.parse.urlencode(query)).json()
    rows = items_of(page)
    if not rows:
        print('no skills')
    for s in rows:
        pending = ' +pending-update' if s.get('revision') else ''
        print('%s\t%s%s\t%s\t%s' % (s.get('id'), s.get('status'), pending, s.get('categoryName') or '-', s.get('title')))


def cmd_show(args):
    market = market_url(args)
    token = require_token(market)
    print_skill(market, get_skill(market, token, args.id))


def cmd_projects(args):
    market = market_url(args)
    token = require_token(market)
    query = {'limit': 50}
    if args.keyword:
        query['keyword'] = args.keyword
    page = api(market, token, 'GET', '/api/v1/account/projects?' + urllib.parse.urlencode(query)).json()
    rows = items_of(page)
    if not rows:
        print('no projects')
    for p in rows:
        version = (p.get('latestVersion') or {}).get('name') or 'not released'
        print('%s\t%s\t%s\t%s' % (p.get('id'), p.get('name'), version, p.get('displayName') or ''))


def cmd_register_seller(args):
    market = market_url(args)
    token = require_token(market)
    res = call('POST', market + '/api/v1/account/seller-registration', token=token)
    data = res.json()
    if res.status in (200, 204):
        out('RESULT_SELLER', 'registered')
        return
    if res.status == 400 and isinstance(data, dict) and data.get('seller') == 'registered':
        out('RESULT_SELLER', 'already')
        return
    if res.status == 401:
        need('login', 'run login')
    explain_error(res.status, data, res.text())


def build_data(args, current=None):
    current = current or {}
    data = {
        'title': args.title if args.title is not None else current.get('title'),
        'description': args.description if args.description is not None else current.get('description'),
        'categoryName': args.category if args.category is not None else current.get('categoryName'),
        'currencyId': 0,
    }
    if getattr(args, 'free', False):
        price, original = None, None
    else:
        price = price_text(args.price)
        original = price_text(args.original_price)
        if price is None and original is None and current:
            currency = default_currency(market_url(args)) or {}
            for p in current.get('prices') or []:
                if not currency or p.get('currencyId') == currency.get('id'):
                    price, original = p.get('price'), p.get('originalPrice')
                    break
    if original is not None and price is None:
        die('--original-price needs --price')
    if price is not None and original is not None and float(original) < float(price):
        die('--original-price must be greater than or equal to --price')
    if price is not None:
        data['price'] = str(price)
    if original is not None:
        data['originalPrice'] = str(original)
    return data


def cmd_add(args):
    market = market_url(args)
    token = require_token(market)
    check_meta(args.title, args.category)
    data = build_data(args)
    if args.project_id:
        data['forEntityType'] = 'project'
        data['forEntityId'] = args.project_id
    if args.zip:
        if zip_skill_content(args.zip) is None:
            print('warning: the zip has no SKILL.md at its root folder, the marketplace shows README.md or a file list instead')
        body, content_type = multipart(data, args.zip)
        res = api(market, token, 'POST', SKILL_API + '/add-package', body=body, content_type=content_type)
    else:
        if not args.content_file:
            die('pass --zip (recommended) or --content-file')
        data['content'] = read_text(args.content_file)
        res = api(market, token, 'POST', SKILL_API + '/add', body=data)
    created = res.json() or {}
    skill_id = created.get('createdId') or created.get('id')
    out('RESULT_ADD', 'ok')
    if skill_id:
        print_skill(market, get_skill(market, token, int(skill_id)))


def cmd_update(args):
    market = market_url(args)
    token = require_token(market)
    check_meta(args.title, args.category)
    current = get_skill(market, token, args.id)
    data = build_data(args, current)
    if args.zip:
        if zip_skill_content(args.zip) is None:
            print('warning: the zip has no SKILL.md at its root folder')
        body, content_type = multipart(data, args.zip)
        res = api(market, token, 'POST', '%s/%d/package' % (SKILL_API, args.id), body=body, content_type=content_type)
    else:
        if args.content_file:
            data['content'] = read_text(args.content_file)
        else:
            revision = current.get('revision') or {}
            data['content'] = revision.get('content') or current.get('content')
        res = api(market, token, 'PUT', '%s/%d' % (SKILL_API, args.id), body=data)
    review = (res.json() or {}).get('reviewRequired')
    out('RESULT_UPDATE', 'ok')
    out('REVIEW_REQUIRED', 'yes' if review else 'no')
    print_skill(market, get_skill(market, token, args.id))


def cmd_cancel_update(args):
    market = market_url(args)
    token = require_token(market)
    api(market, token, 'DELETE', '%s/%d/revision' % (SKILL_API, args.id))
    out('RESULT_CANCEL_UPDATE', 'ok')


def cmd_trash(args):
    market = market_url(args)
    token = require_token(market)
    api(market, token, 'DELETE', '%s/%d' % (SKILL_API, args.id))
    out('RESULT_TRASH', 'ok')


def cmd_open(args):
    market = market_url(args)
    url = market + (args.path if args.path.startswith('/') else '/' + args.path)
    try:
        opened = webbrowser.open(url)
    except Exception:
        opened = False
    out('OPEN_URL', url)
    out('BROWSER_OPENED', 'yes' if opened else 'no')


def main():
    parser = argparse.ArgumentParser(description='Publish AI skills to the EzyPlatform marketplace')
    parser.add_argument('--market-url', help='marketplace address (default %s, or EZY_MARKET_URL)' % DEFAULT_MARKET_URL)
    sub = parser.add_subparsers(dest='command')

    def add(name, func, help_text):
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(func=func)
        return p

    add('check', cmd_check, 'marketplace reachable and signed in')
    p = add('login', cmd_login, 'sign in with EzyLogin CLI login (browser approval)')
    p.add_argument('--no-browser', action='store_true')
    p.add_argument('--timeout', type=int, default=600)
    add('logout', cmd_logout, 'forget the saved token')
    p = add('scan', cmd_scan, 'list files and find secrets / personal data')
    p.add_argument('dir')
    p = add('pack', cmd_pack, 'scan and build a clean zip')
    p.add_argument('dir')
    p.add_argument('--out')
    p.add_argument('--force', action='store_true')
    p = add('categories', cmd_categories, 'existing skill categories')
    p.add_argument('--keyword')
    add('currency', cmd_currency, 'default currency of prices')
    p = add('list', cmd_list, 'skills of the signed-in account')
    p.add_argument('--keyword')
    p.add_argument('--status')
    p = add('show', cmd_show, 'one skill of the signed-in account')
    p.add_argument('id', type=int)
    p = add('projects', cmd_projects, 'plugins/themes of the signed-in account')
    p.add_argument('--keyword')
    add('register-seller', cmd_register_seller, 'register the account as a skill seller')
    for name, func, help_text in (
        ('add', cmd_add, 'add a new skill (sent to review)'),
        ('update', cmd_update, 'update a skill, keeps what is not passed'),
    ):
        p = add(name, func, help_text)
        if name == 'update':
            p.add_argument('id', type=int)
        p.add_argument('--zip')
        p.add_argument('--content-file')
        p.add_argument('--title', required=(name == 'add'))
        p.add_argument('--description')
        p.add_argument('--category')
        p.add_argument('--price')
        p.add_argument('--original-price')
        if name == 'add':
            p.add_argument('--project-id', type=int)
        else:
            p.add_argument('--free', action='store_true')
    p = add('cancel-update', cmd_cancel_update, 'cancel the pending update of a published skill')
    p.add_argument('id', type=int)
    p = add('trash', cmd_trash, 'move a skill to trash')
    p.add_argument('id', type=int)
    p = add('open', cmd_open, 'open a marketplace page in the browser')
    p.add_argument('--path', default='/account/ai-skill-library')
    args = parser.parse_args()
    if not getattr(args, 'func', None):
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == '__main__':
    main()
