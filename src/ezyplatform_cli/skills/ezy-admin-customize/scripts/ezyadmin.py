#!/usr/bin/env python3
import argparse
import base64
import datetime
import hashlib
import http.server
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

VERSION = '1.0.0'
USER_AGENT = 'ezyplatform-admin-customize/' + VERSION + ' (Python)'
CLIENT_NAME = 'AI admin customization'
MARKET_URL = os.environ.get('EZY_MARKET_URL', 'https://ezyplatform.com')
DEFAULT_ADMIN_URLS = ['http://localhost:9090', 'http://127.0.0.1:9090']
STATE_DIR = os.path.join(os.path.expanduser('~'), '.ezyplatform')
STATE_FILE = os.path.join(STATE_DIR, 'admin-customize.json')
MIN_EZYSUPPORT_VERSION = '0.6.2'
MIN_EZYLOGIN_VERSION = '0.4.1'
CODES_API = '/ezysupport/api/v1/settings/admin-additional-codes'
CLI_TOKEN_API = '/ezylogin/api/v1/cli/me/token'
HEAD_FILE = 'head.html'
FOOT_FILE = 'foot.html'
EXIT_NEED = 3


class HttpResult:
    def __init__(self, status, body, headers=None):
        self.status = status
        self.body = body
        self.headers = headers or {}

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


def call(method, url, body=None, token=None, timeout=60, content_type='application/json'):
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('User-Agent', USER_AGENT)
    req.add_header('Accept', 'application/json, text/html;q=0.9, */*;q=0.8')
    if data is not None:
        req.add_header('Content-Type', content_type)
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    try:
        with OPENER.open(req, timeout=timeout) as resp:
            return HttpResult(resp.status, resp.read(), dict(resp.headers))
    except urllib.error.HTTPError as e:
        return HttpResult(e.code, e.read() or b'', dict(e.headers or {}))
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


def normalize_url(url):
    url = url.strip().rstrip('/')
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'http://' + url
    return url


def resolve_admin_url(args, probe=True):
    if getattr(args, 'admin_url', None):
        return normalize_url(args.admin_url)
    if os.environ.get('EZY_ADMIN_URL'):
        return normalize_url(os.environ['EZY_ADMIN_URL'])
    state = load_state()
    if state.get('default_admin_url'):
        return state['default_admin_url']
    if probe:
        for url in DEFAULT_ADMIN_URLS:
            if call('GET', url + '/', timeout=5).status:
                return url
        local_home = find_local_home(args)
        if local_home:
            return 'http://localhost:%s' % local_admin_port(local_home)
    need('admin_url', 'admin URL unknown: ask the user for the address of their EzyPlatform admin '
         '(for example https://admin.example.com or http://localhost:9090) and pass --admin-url')


def get_token(admin_url):
    entry = load_state().get('tokens', {}).get(admin_url)
    if not entry:
        return None
    if entry.get('expiredAt') and entry['expiredAt'] / 1000 < time.time():
        return None
    return entry.get('accessToken')


def require_token(admin_url):
    token = get_token(admin_url)
    if not token:
        need('login', 'no valid admin token for %s: run the login command' % admin_url)
    res = call('GET', admin_url + '/api/v1/admins/me', token=token)
    if res.status == 401:
        need('login', 'the saved admin token was rejected (expired or signed out): run the login command again')
    if res.status == 0:
        need('admin_down', 'admin %s does not answer: start EzyPlatform or check the address' % admin_url)
    return token


def version_tuple(version):
    parts = []
    for p in (version or '').split('.'):
        digits = ''.join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def probe_ezylogin(admin_url):
    res = call('POST', admin_url + CLI_TOKEN_API, body={})
    data = res.json() if res.status else None
    if res.status == 0:
        return 'admin_down'
    if res.status == 404:
        return 'missing'
    if res.status == 403 and isinstance(data, dict) and data.get('cliLogin') == 'notAllowed':
        return 'disabled'
    if res.status == 400:
        return 'enabled'
    if res.status == 401:
        return 'outdated'
    return 'unknown_%s' % res.status


def market_project(name):
    res = call('GET', MARKET_URL + '/api/v1/released-projects/' + urllib.parse.quote(name), timeout=30)
    if res.status != 200:
        return None
    return res.json()


def project_status(admin_url, token, name):
    res = call('GET', admin_url + '/api/v1/projects/' + urllib.parse.quote(name), token=token)
    if res.status == 403:
        return {'error': 'forbidden'}
    if res.status == 404:
        return {'installed': False}
    if res.status != 200:
        return {'error': 'http_%s' % res.status}
    version = (res.json() or {}).get('version')
    types_res = call('GET', admin_url + '/api/v1/projects/%s/module-types' % urllib.parse.quote(name), token=token)
    all_types = types_res.json() if types_res.status == 200 else []
    active_res = call('GET', admin_url + '/api/v1/projects/%s/module-types?active=true' % urllib.parse.quote(name), token=token)
    active_types = active_res.json() if active_res.status == 200 else []
    return {
        'installed': True,
        'version': version,
        'module_types': all_types or [],
        'active_types': active_types or [],
    }


def find_local_home(args):
    candidates = []
    if getattr(args, 'home', None):
        candidates.append(args.home)
    if os.environ.get('EZYPLATFORM_HOME'):
        candidates.append(os.environ['EZYPLATFORM_HOME'])
    home = os.path.expanduser('~')
    candidates += [
        os.path.join(home, 'ezyplatform', 'ezyplatform'),
        os.path.join(home, 'ezyplatform-dev-site', 'ezyplatform'),
        'C:\\ezyplatform\\ezyplatform',
    ]
    for c in candidates:
        if c and os.path.isfile(os.path.join(c, 'cli.sh' if os.name != 'nt' else 'cli.bat')):
            return os.path.abspath(c)
    return None


def local_admin_port(home):
    try:
        with open(os.path.join(home, 'admin', 'settings', 'config.properties'), encoding='utf-8') as f:
            for line in f:
                key, _, value = line.partition('=')
                if key.strip() == 'server.port' and value.strip().isdigit():
                    return value.strip()
    except OSError:
        pass
    return '9090'


def is_local_url(url):
    host = urllib.parse.urlparse(url).hostname or ''
    return host in ('localhost', '127.0.0.1', '::1')


def cmd_check(args):
    admin_url = resolve_admin_url(args)
    out('admin_url', admin_url)
    res = call('GET', admin_url + '/', timeout=10)
    out('admin_http', res.status)
    if res.status == 0:
        local_home = find_local_home(args) if is_local_url(admin_url) else None
        out('local_home', local_home or 'none')
        need('admin_down', 'admin does not answer: if EzyPlatform is on this computer start it '
             '(local-restart, or the ezyplatform-install skill), otherwise ask the user to check the address')
    login_state = probe_ezylogin(admin_url)
    out('ezylogin_cli_login', login_state)
    local_home = find_local_home(args) if is_local_url(admin_url) else None
    out('local_home', local_home or 'none')
    token = get_token(admin_url)
    token_ok = False
    if token:
        me = call('GET', admin_url + '/api/v1/admins/me', token=token)
        token_ok = me.status == 200
        if token_ok:
            data = me.json() or {}
            out('admin_username', data.get('username') or data.get('displayName') or '?')
    out('token', 'valid' if token_ok else ('rejected' if token else 'none'))
    if token_ok:
        for name, minimum in (('ezysupport', MIN_EZYSUPPORT_VERSION), ('ezylogin', MIN_EZYLOGIN_VERSION)):
            st = project_status(admin_url, token, name)
            if st.get('error'):
                out(name, 'unknown (%s)' % st['error'])
                continue
            if not st['installed']:
                out(name, 'not_installed')
                continue
            out(name + '_version', st['version'])
            out(name + '_active_types', ','.join(st['active_types']) or 'none')
        api = call('GET', admin_url + CODES_API, token=token)
        out('ezysupport_codes_api', {200: 'available', 404: 'missing', 403: 'forbidden'}.get(api.status, 'http_%s' % api.status))
    market = market_project('ezysupport')
    if market:
        out('ezysupport_latest', (market.get('latestVersion') or {}).get('name'))
    if login_state == 'missing':
        need('ezylogin_missing', 'EzyLogin is not installed or not active on this admin: install and activate it '
             '(local-install ezylogin when local_home is set, otherwise guide the user), restart, then check again')
    if login_state == 'outdated':
        need('ezylogin_outdated', 'EzyLogin is older than %s and has no CLI login: update it, restart, then check again' % MIN_EZYLOGIN_VERSION)
    if login_state == 'disabled' and not token_ok:
        need('admin_cli_login_disabled', 'open %s/ezylogin/settings/regular, tick "Allow admins to sign in from the command line (CLI)" '
             'and save (only an admin with EzyLogin settings permission can do it)' % admin_url)
    if not token_ok:
        need('login', 'run the login command: the browser opens and the user approves the request')
    print('READY')


def cmd_login(args):
    admin_url = resolve_admin_url(args)
    state = probe_ezylogin(admin_url)
    if state == 'admin_down':
        need('admin_down', 'admin %s does not answer' % admin_url)
    if state == 'missing':
        need('ezylogin_missing', 'EzyLogin is not installed or not active on %s' % admin_url)
    if state == 'outdated':
        need('ezylogin_outdated', 'EzyLogin is older than %s: update it first' % MIN_EZYLOGIN_VERSION)
    if state == 'disabled':
        need('admin_cli_login_disabled', 'open %s/ezylogin/settings/regular, tick "Allow admins to sign in from the command line (CLI)" and save' % admin_url)
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
                       else 'Sign in failed (state mismatch). Go back to your AI assistant and try again.')
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
    authorize_url = admin_url + '/ezylogin/cli/authorize?' + urllib.parse.urlencode({
        'client_name': CLIENT_NAME,
        'redirect_uri': redirect_uri,
        'state': expected_state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    })
    print('OPEN_URL=' + authorize_url, flush=True)
    if not args.no_browser:
        opened = False
        try:
            opened = webbrowser.open(authorize_url)
        except Exception:
            opened = False
        print('BROWSER_OPENED=%s' % ('yes' if opened else 'no'), flush=True)
    print('WAITING: the user signs in to the admin if needed and clicks Approve (up to %d seconds)' % args.timeout, flush=True)
    finished = done.wait(args.timeout)
    server.shutdown()
    if not finished:
        die('no approval within %d seconds; run login again' % args.timeout)
    if result.get('error'):
        die('the callback did not match this login (state mismatch); run login again')
    res = call('POST', admin_url + CLI_TOKEN_API, body={
        'code': result['code'],
        'codeVerifier': verifier,
        'redirectUri': redirect_uri,
    })
    if res.status != 200:
        die('token exchange failed: HTTP %s %s' % (res.status, res.text()[:300]))
    data = res.json() or {}
    if not data.get('accessToken'):
        die('token exchange returned no token')
    st = load_state()
    st.setdefault('tokens', {})[admin_url] = {
        'accessToken': data['accessToken'],
        'expiredAt': data.get('accessTokenExpiredAt'),
        'savedAt': int(time.time() * 1000),
    }
    st['default_admin_url'] = admin_url
    save_state(st)
    expired = data.get('accessTokenExpiredAt')
    out('RESULT_LOGIN', 'ok')
    out('RESULT_TOKEN_FILE', STATE_FILE)
    if expired:
        out('RESULT_EXPIRES_AT', datetime.datetime.fromtimestamp(expired / 1000).isoformat(timespec='minutes'))


def cmd_logout(args):
    admin_url = resolve_admin_url(args, probe=False)
    st = load_state()
    entry = st.get('tokens', {}).pop(admin_url, None)
    save_state(st)
    out('RESULT_LOGOUT', 'removed' if entry else 'none')


def cmd_plugin_status(args):
    admin_url = resolve_admin_url(args)
    token = require_token(admin_url)
    name = args.name
    st = project_status(admin_url, token, name)
    market = market_project(name)
    latest = (market or {}).get('latestVersion', {}) or {}
    out('name', name)
    if st.get('error') == 'forbidden':
        need('plugin_permission', 'this admin account cannot manage plugins: sign in with a super admin '
             '(or an admin with plugin management permission) or ask the user to do it in Modules')
    if st.get('error'):
        die('cannot read %s: %s' % (name, st['error']))
    out('installed', 'yes' if st['installed'] else 'no')
    if st['installed']:
        out('version', st['version'])
        out('module_types', ','.join(st['module_types']))
        out('active_types', ','.join(st['active_types']) or 'none')
    out('latest_version', latest.get('name') or 'unknown')
    out('market_module_types', ','.join((market or {}).get('includeModuleTypes') or []))
    price = (market or {}).get('price') or 0
    out('price', 'free' if not price else price)
    if not st['installed']:
        print('ACTION=install')
    elif latest.get('name') and version_tuple(st['version']) < version_tuple(latest['name']):
        print('ACTION=upgrade')
    elif set((market or {}).get('includeModuleTypes') or st['module_types']) - set(st['active_types']):
        print('ACTION=activate')
    else:
        print('ACTION=none')


def wait_admin(admin_url, seconds):
    start = time.time()
    time.sleep(5)
    while time.time() - start < seconds:
        res = call('GET', admin_url + '/', timeout=5)
        if res.status and res.status < 500:
            return True
        time.sleep(3)
    return False


def cmd_plugin_install(args):
    admin_url = resolve_admin_url(args)
    token = require_token(admin_url)
    name = args.name
    market = market_project(name)
    if not market:
        die('%s is not on the market %s' % (name, MARKET_URL))
    if (market.get('price') or 0) and not args.paid_ok:
        need('paid_plugin', '%s costs %s: ask the user first; buying happens on %s and the market account must be '
             'connected in the admin (Modules > Market), then run again with --paid-ok' % (name, market.get('price'), MARKET_URL))
    version = args.version or (market.get('latestVersion') or {}).get('name')
    if not version:
        die('cannot find the latest version of %s' % name)
    before = project_status(admin_url, token, name)
    if before.get('error') == 'forbidden':
        need('plugin_permission', 'this admin account cannot manage plugins: use a super admin account or guide the user (Modules > Market)')
    if before.get('installed') and before.get('version') == version and not args.force:
        out('RESULT_INSTALL', 'already_%s' % version)
    else:
        print('INSTALLING %s %s from %s (this can take a minute)' % (name, version, MARKET_URL), flush=True)
        res = call('POST', admin_url + '/api/v1/projects/%s/%s/install?marketUrl=%s' % (
            urllib.parse.quote(name), urllib.parse.quote(version), urllib.parse.quote(MARKET_URL)),
            body=b'', token=token, timeout=600)
        if res.status == 403:
            need('plugin_permission', 'this admin account cannot install plugins: use a super admin account or guide the user (Modules > Market)')
        if res.status not in (200, 204):
            die('install failed: HTTP %s %s' % (res.status, res.text()[:300]))
        status_res = call('GET', admin_url + '/api/v1/projects/version-status', token=token)
        installed = [it for it in (status_res.json() or []) if it.get('projectName') == name]
        out('RESULT_INSTALL', ','.join('%s:%s' % (it.get('version'), it.get('status')) for it in installed) or 'unknown')
        if not any(it.get('version') == version for it in installed):
            die('the admin did not install %s %s; read the admin log (logs/admin-server.log) or install it from Modules > Market' % (name, version))
    module_types = market.get('includeModuleTypes') or before.get('module_types') or []
    body = {'moduleTypes': module_types, 'restart': not args.no_restart}
    print('ACTIVATING %s (%s), restart=%s' % (name, ','.join(module_types), str(not args.no_restart).lower()), flush=True)
    res = call('POST', admin_url + '/api/v1/projects/%s/activate' % urllib.parse.quote(name), body=body, token=token, timeout=120)
    if res.status not in (0, 200, 204):
        die('activate failed: HTTP %s %s' % (res.status, res.text()[:300]))
    if args.no_restart:
        out('RESULT_RESTART_NEEDED', 'true')
        return
    print('WAITING for the admin to restart (1-3 minutes)', flush=True)
    if not wait_admin(admin_url, args.timeout):
        die('the admin did not come back within %d seconds; read logs/admin-server.log' % args.timeout)
    after = project_status(admin_url, require_token(admin_url), name)
    out('RESULT_VERSION', after.get('version'))
    out('RESULT_ACTIVE_TYPES', ','.join(after.get('active_types') or []) or 'none')


def read_codes(admin_url, token):
    res = call('GET', admin_url + CODES_API, token=token)
    if res.status == 404:
        need('ezysupport_outdated', 'EzySupport on this admin has no admin-additional-codes API (needs >= %s): '
             'run plugin-status ezysupport and plugin-install ezysupport' % MIN_EZYSUPPORT_VERSION)
    if res.status == 403:
        need('settings_permission', 'this admin account cannot change EzySupport settings: use a super admin account')
    if res.status != 200:
        die('cannot read the admin codes: HTTP %s %s' % (res.status, res.text()[:300]))
    data = res.json() or {}
    return data.get('additionalHead') or '', data.get('additionalFoot') or ''


def write_codes(admin_url, token, head, foot):
    res = call('PUT', admin_url + CODES_API, body={'additionalHead': head, 'additionalFoot': foot}, token=token)
    if res.status == 404:
        need('ezysupport_outdated', 'EzySupport needs >= %s: run plugin-install ezysupport' % MIN_EZYSUPPORT_VERSION)
    if res.status == 403:
        need('settings_permission', 'this admin account cannot change EzySupport settings: use a super admin account')
    if res.status not in (200, 204):
        die('save failed: HTTP %s %s' % (res.status, res.text()[:300]))
    saved_head, saved_foot = read_codes(admin_url, token)
    if saved_head != head.strip() or saved_foot != foot.strip():
        die('the saved codes differ from what was sent')


def read_file(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def write_file(path, content):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)


def backup(admin_url, token, folder):
    head, foot = read_codes(admin_url, token)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    target = os.path.join(folder, '.backups', stamp)
    write_file(os.path.join(target, HEAD_FILE), head)
    write_file(os.path.join(target, FOOT_FILE), foot)
    return target


def cmd_pull(args):
    admin_url = resolve_admin_url(args)
    token = require_token(admin_url)
    head, foot = read_codes(admin_url, token)
    for name, content in ((HEAD_FILE, head), (FOOT_FILE, foot)):
        path = os.path.join(args.dir, name)
        if os.path.exists(path) and not args.force and read_file(path).strip() != content.strip():
            die('%s exists and differs from the server; use --force to overwrite it' % path)
        write_file(path, content + ('\n' if content and not content.endswith('\n') else ''))
    out('RESULT_DIR', os.path.abspath(args.dir))
    out('RESULT_HEAD_CHARS', len(head))
    out('RESULT_FOOT_CHARS', len(foot))


def cmd_push(args):
    admin_url = resolve_admin_url(args)
    token = require_token(admin_url)
    head_path = os.path.join(args.dir, HEAD_FILE)
    foot_path = os.path.join(args.dir, FOOT_FILE)
    for path in (head_path, foot_path):
        if not os.path.isfile(path):
            die('%s is missing: create it (an empty file clears that part)' % path)
    head, foot = read_file(head_path), read_file(foot_path)
    saved = backup(admin_url, token, args.dir)
    write_codes(admin_url, token, head, foot)
    out('RESULT_SAVED', 'ok')
    out('RESULT_BACKUP', saved)
    out('RESULT_HEAD_CHARS', len(head.strip()))
    out('RESULT_FOOT_CHARS', len(foot.strip()))


def cmd_restore(args):
    admin_url = resolve_admin_url(args)
    token = require_token(admin_url)
    source = args.backup
    if not source:
        root = os.path.join(args.dir, '.backups')
        items = sorted(os.listdir(root)) if os.path.isdir(root) else []
        if not items:
            die('no backup in %s' % root)
        source = os.path.join(root, items[-1])
    head = read_file(os.path.join(source, HEAD_FILE))
    foot = read_file(os.path.join(source, FOOT_FILE))
    saved = backup(admin_url, token, args.dir)
    write_codes(admin_url, token, head, foot)
    out('RESULT_RESTORED_FROM', os.path.abspath(source))
    out('RESULT_BACKUP', saved)


def cmd_reset(args):
    admin_url = resolve_admin_url(args)
    token = require_token(admin_url)
    saved = backup(admin_url, token, args.dir)
    write_codes(admin_url, token, '', '')
    out('RESULT_RESET', 'ok')
    out('RESULT_BACKUP', saved)


def marker_lines(code):
    lines = [line.strip() for line in code.splitlines() if line.strip()]
    return lines[:1] + lines[-1:] if lines else []


def cmd_verify(args):
    admin_url = resolve_admin_url(args)
    token = require_token(admin_url)
    head, foot = read_codes(admin_url, token)
    paths = args.path or ['/']
    failed = False
    for path in paths:
        res = call('GET', admin_url + path, token=token)
        html = res.text() if res.status == 200 else ''
        location = res.headers.get('Location') or res.headers.get('location') or ''
        if res.status in (301, 302, 303, 307, 308):
            out('page ' + path, 'redirect %s %s' % (res.status, location))
            failed = True
            continue
        missing = [m for m in marker_lines(head) + marker_lines(foot) if m not in html]
        state = 'ok' if res.status == 200 and not missing else 'http_%s missing=%d' % (res.status, len(missing))
        out('page ' + path, state)
        failed = failed or state != 'ok'
    out('head_chars', len(head))
    out('foot_chars', len(foot))
    if failed:
        sys.exit(1)


def cmd_open(args):
    admin_url = resolve_admin_url(args)
    url = admin_url + (args.path or '/')
    out('OPEN_URL', url)
    try:
        opened = webbrowser.open(url)
    except Exception:
        opened = False
    out('BROWSER_OPENED', 'yes' if opened else 'no')


def run_cli(home, command):
    if os.name == 'nt':
        cmd = ['cmd', '/c', 'cli.bat', command]
    else:
        cmd = ['sh', 'cli.sh', command]
    env = dict(os.environ)
    java_home = env.get('JAVA_HOME')
    if not java_home or not os.path.exists(os.path.join(java_home, 'bin')):
        jdk_root = os.path.join(os.path.dirname(home), 'jdk')
        if os.path.isdir(jdk_root):
            for root, dirs, files in os.walk(jdk_root):
                if os.path.basename(root) == 'bin' and ('java' in files or 'java.exe' in files):
                    java_home = os.path.dirname(root)
                    break
    if java_home:
        env['JAVA_HOME'] = java_home
        env['PATH'] = os.path.join(java_home, 'bin') + os.pathsep + env.get('PATH', '')
    if not shutil.which('java', path=env.get('PATH')):
        need('java', 'java 8 is not on PATH for %s: set JAVA_HOME (the ezyplatform-install skill ships a JDK in <install dir>/jdk)' % home)
    print('RUN cli %s' % command, flush=True)
    proc = subprocess.run(cmd, cwd=home, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
    text = proc.stdout.decode('utf-8', errors='replace')
    return proc.returncode, text


def installed_types(home, name):
    types = {
        'admin-plugin': os.path.join(home, 'admin', 'plugins', name),
        'web-plugin': os.path.join(home, 'web', 'plugins', name),
        'theme': os.path.join(home, 'web', 'themes', name),
    }
    return [t for t, p in types.items() if os.path.isfile(os.path.join(p, 'module.properties'))]


def cmd_local_install(args):
    home = find_local_home(args)
    if not home:
        need('local_home', 'no local EzyPlatform folder found: pass --home <folder with cli.sh>, or guide the user to install from Modules > Market')
    name = args.name
    out('home', home)
    if args.update and installed_types(home, name):
        code, text = run_cli(home, 'update-modules %s' % name)
        print(text[-1500:])
        code, text = run_cli(home, 'run-update')
        print(text[-1500:])
    elif not installed_types(home, name):
        code, text = run_cli(home, 'install %s' % name)
        print(text[-1500:])
    types = installed_types(home, name)
    if not types:
        die('%s is not installed in %s' % (name, home))
    for t in types:
        if t == 'theme':
            continue
        code, text = run_cli(home, 'activate %s %s' % (t, name))
        print(text[-600:])
    out('RESULT_INSTALLED_TYPES', ','.join(types))
    out('RESULT_RESTART_NEEDED', 'true')


def cmd_local_restart(args):
    home = find_local_home(args)
    if not home:
        need('local_home', 'no local EzyPlatform folder found: pass --home <folder with cli.sh>')
    ctl = os.path.join(os.path.dirname(home), 'ezyplatform-ctl.sh' if os.name != 'nt' else 'ezyplatform-ctl.ps1')
    if os.path.isfile(ctl):
        if os.name == 'nt':
            subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ctl, 'stop'])
            subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ctl, 'start'])
        else:
            subprocess.run(['bash', ctl, 'stop'])
            subprocess.run(['bash', ctl, 'start'])
    else:
        for target in args.targets:
            code, text = run_cli(home, 'restart %s' % target)
            print(text[-600:])
    admin_url = resolve_admin_url(args)
    if not wait_admin(admin_url, args.timeout):
        die('admin %s did not answer within %d seconds; read %s' % (admin_url, args.timeout, os.path.join(home, 'logs', 'admin-server.log')))
    out('RESULT_ADMIN_URL', admin_url)


def main():
    parser = argparse.ArgumentParser(prog='ezy admin-customize', description='Customize the EzyPlatform admin look through EzySupport')
    parser.add_argument('--version', action='version', version=VERSION)
    sub = parser.add_subparsers(dest='command')

    def add(name, func, help_text):
        p = sub.add_parser(name, help=help_text)
        p.add_argument('--admin-url', help='admin address, for example http://localhost:9090')
        p.set_defaults(func=func)
        return p

    add('check', cmd_check, 'check the admin, EzyLogin CLI login, the saved token and EzySupport').add_argument('--home')
    p = add('login', cmd_login, 'sign in through EzyLogin CLI login (browser approval)')
    p.add_argument('--timeout', type=int, default=600)
    p.add_argument('--no-browser', action='store_true')
    add('logout', cmd_logout, 'forget the saved token of this admin')
    p = add('plugin-status', cmd_plugin_status, 'installed and latest version of a plugin')
    p.add_argument('name', nargs='?', default='ezysupport')
    p = add('plugin-install', cmd_plugin_install, 'install or upgrade a plugin from the market, activate and restart')
    p.add_argument('name', nargs='?', default='ezysupport')
    p.add_argument('--version')
    p.add_argument('--no-restart', action='store_true')
    p.add_argument('--force', action='store_true')
    p.add_argument('--paid-ok', action='store_true')
    p.add_argument('--timeout', type=int, default=420)
    for name, func, text in (
        ('pull', cmd_pull, 'download the current head/foot codes into --dir'),
        ('push', cmd_push, 'back up the current codes, then save head.html and foot.html of --dir'),
        ('restore', cmd_restore, 'save a backup again (latest by default)'),
        ('reset', cmd_reset, 'back up, then remove the custom codes (default admin look)'),
    ):
        p = add(name, func, text)
        p.add_argument('--dir', default='admin-customization')
        if name == 'pull':
            p.add_argument('--force', action='store_true')
        if name == 'restore':
            p.add_argument('--backup')
    p = add('verify', cmd_verify, 'check that admin pages contain the saved codes')
    p.add_argument('--path', action='append')
    p = add('open', cmd_open, 'open an admin page in the default browser')
    p.add_argument('--path')
    p = add('local-install', cmd_local_install, 'install/update and activate a plugin in a local EzyPlatform folder with cli.sh')
    p.add_argument('name')
    p.add_argument('--home')
    p.add_argument('--update', action='store_true')
    p = add('local-restart', cmd_local_restart, 'restart a local EzyPlatform and wait for the admin')
    p.add_argument('--home')
    p.add_argument('--targets', nargs='+', default=['admin', 'web'])
    p.add_argument('--timeout', type=int, default=420)
    args = parser.parse_args()
    if not getattr(args, 'func', None):
        parser.print_help()
        sys.exit(2)
    args.func(args)


if __name__ == '__main__':
    main()
