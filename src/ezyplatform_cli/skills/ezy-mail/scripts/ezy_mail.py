#!/usr/bin/env python3
"""EzyMail delivery health, mail templates and the EzySupport Contact Us form flow.

Usage:
    python3 ezy_mail.py status                                   # read-only health report
    python3 ezy_mail.py templates                                # local mail-templates/ vs server
    python3 ezy_mail.py pull <template_name> [--write]
    python3 ezy_mail.py push <template_name> [--yes]
    python3 ezy_mail.py contact-settings [--response-mail on|off] [--supporter-emails a@x,b@y] [--yes]
    python3 ezy_mail.py test-contact --email <inbox you own> [--yes]

Every write is a dry run unless --yes is given. Delivery-service credentials
(SMTP password, API keys) are never read, printed or written: the human enters
them in Admin -> EzyMail -> Settings.
"""
import argparse
import collections
import datetime
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'ezy-shared'))
import ezy_client  # noqa: E402
from ezy_output import print_status  # noqa: E402

TEMPLATE_FILES = {'title.html': 'titleTemplate', 'content.html': 'contentTemplate'}
CONTACT_FIELDS = ('contactUsYourName', 'contactUsYourEmail', 'contactUsSubject', 'contactUsMessage')
# Settings saved as lists by the admin page; the PUT replaces the whole form, so every field is resent.
LIST_FIELDS = ('supporterEmails', 'recruitmentEmails')


def stamp(ms):
    return datetime.datetime.fromtimestamp(ms / 1000).strftime('%Y-%m-%d %H:%M') if ms else '-'


def form_values(page_html, form_id=None):
    """Field values of an admin form (inputs, textareas, selects); password values are reduced to set/unset."""
    body = page_html
    if form_id:
        start = page_html.find(f'id="{form_id}"')
        if start < 0:
            raise SystemExit(f'form {form_id} not found; the admin page layout changed')
        body = page_html[start:page_html.find('</form>', start)]
    values = {}
    for m in re.finditer(r'<input\b([^>]*)>', body):
        attrs = m.group(1)
        name = re.search(r'name="([^"]+)"', attrs)
        if not name:
            continue
        kind = (re.search(r'type="([^"]+)"', attrs) or [None, 'text'])[1]
        value = re.search(r'value="([^"]*)"', attrs)
        value = html.unescape(value.group(1)) if value else ''
        if kind == 'checkbox':
            values[name.group(1)] = 'checked' in attrs
        elif kind == 'password':
            values[name.group(1)] = '<set>' if value else ''
        else:
            values[name.group(1)] = value
    for m in re.finditer(r'<textarea\b([^>]*)>(.*?)</textarea>', body, re.S):
        name = re.search(r'name="([^"]+)"', m.group(1))
        if name:
            values[name.group(1)] = html.unescape(m.group(2).strip())
    for m in re.finditer(r'<select\b([^>]*)>(.*?)</select>', body, re.S):
        name = re.search(r'name="([^"]+)"', m.group(1))
        chosen = re.search(r'<option[^>]*value="([^"]*)"[^>]*selected', m.group(2))
        if name:
            values[name.group(1)] = chosen.group(1) if chosen else None
    return values


def delivery_services(env):
    """[(code, name, is_default)] from Admin -> EzyMail -> Settings."""
    page = ezy_client.request_text('/ezymail/settings', env)
    codes = list(dict.fromkeys(re.findall(r'/ezymail/settings/mail-delivery-services/([A-Z0-9_]+)', page)))
    text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', re.sub(r'<script.*?</script>', '', page, flags=re.S)))
    rows = re.findall(r'\b\d+ ([A-Za-z0-9 ]+?) (Yes|Set As)\b', text[text.find('Default Actions'):])
    return [(code, name, flag == 'Yes') for code, (name, flag) in zip(codes, rows)]


def contact_settings(env):
    return form_values(ezy_client.request_text('/ezysupport/settings', env), 'updateSettingsForm')


def cmd_status(args, root, env):
    print('Mail delivery service')
    services = delivery_services(env)
    default = next((s for s in services if s[2]), None)
    if not default:
        print_status('no default delivery service found', False)
    else:
        fields = form_values(ezy_client.request_text(f'/ezymail/settings/mail-delivery-services/{default[0]}', env), 'mailSettingsForm')
        empty = [k for k, v in fields.items() if v == '' and not k.lower().endswith('password')]
        password = [k for k in fields if k.lower().endswith('password')]
        print_status(f'default: {default[1]} ({default[0]})', True)
        for key in ('defaultSenderName', 'defaultSender', 'mailHost', 'mailPort', 'mailUsername'):
            if key in fields:
                print_status(f'{key}: {fields[key] or "(empty)"}', bool(fields[key]))
        for key in password:
            print_status(f"{key}: {'set' if fields[key] else '(empty)'}", True if fields[key] else None)
        if empty:
            print_status(f"empty fields: {', '.join(empty)}; every mail fails until they are filled in the admin", False)
    mails = (ezy_client.request_json('GET', '/ezymail/api/v1/mails?limit=200', env=env) or {}).get('items') or []
    counts = collections.Counter(m.get('status') for m in mails)
    print()
    health = False if counts.get('SEND_ERROR') else True if mails and set(counts) == {'SENT'} else None
    print_status(f"Last {len(mails)} mail(s): {dict(counts) or 'none'}", health)
    last_sent = next((m for m in mails if m.get('status') == 'SENT'), None)
    last_error = next((m for m in mails if m.get('status') == 'SEND_ERROR'), None)
    print_status(f"last SENT: {stamp(last_sent['createdAt']) if last_sent else 'never (in this window)'}", True if last_sent else None)
    if last_error:
        print_status(f"last SEND_ERROR: {stamp(last_error['createdAt'])} {last_error.get('title', '')[:60]!r}", False)
    if mails and not last_sent:
        print_status('nothing was delivered: fix the delivery service before building features that send mail', False if last_error else None)
    print('\nEzySupport Contact Us')
    try:
        cs = contact_settings(env)
        for key in ('enableContactUs', 'enableContactUsResponseMail', 'supporterEmails', 'acceptedContactUsMetadataKeys'):
            print_status(f"{key}: {cs.get(key) if cs.get(key) not in ('', None) else '(empty)'}")
        if cs.get('enableContactUs') and not cs.get('supporterEmails'):
            print_status('no supporter emails: nobody is notified of new contact requests', False)
        total = (ezy_client.request_json('GET', '/ezysupport/api/v1/contact-us?limit=1', env=env) or {}).get('total')
        print_status(f'stored requests: {total}', True if total is not None else None)
    except (ezy_client.EzyError, SystemExit) as err:
        print_status(f'EzySupport not available: {err}', False)
    return 0


def template_dir(root, name):
    return os.path.join(root, 'mail-templates', name)


def server_template(name, env):
    try:
        return ezy_client.request_json('GET', f'/ezymail/api/v1/template-by-name/{urllib.request.quote(name)}', env=env)
    except ezy_client.EzyError as err:
        if err.status == 404:
            return None
        raise


def local_template(root, name):
    folder = template_dir(root, name)
    if not os.path.isdir(folder):
        raise SystemExit(f'local folder missing: {os.path.relpath(folder, root)}')
    data = {key: open(os.path.join(folder, f), encoding='utf-8').read() if os.path.isfile(os.path.join(folder, f)) else ''
            for f, key in TEMPLATE_FILES.items()}
    meta_path = os.path.join(folder, 'meta.json')
    meta = json.load(open(meta_path, encoding='utf-8')) if os.path.isfile(meta_path) else {}
    data.update(contentType=meta.get('contentType') or 'HTML', status=meta.get('status') or 'COMPLETED')
    return data


def template_diff(local, server):
    if not server:
        return ['(new on server)']
    return [k for k in ('titleTemplate', 'contentTemplate', 'contentType', 'status')
            if (local.get(k) or '') != (server.get(k) or '')]


def cmd_templates(args, root, env):
    server = (ezy_client.request_json('GET', '/ezymail/api/v1/templates?limit=200', env=env) or {}).get('items') or []
    names = {t['name'] for t in server}
    local_root = os.path.join(root, 'mail-templates')
    local = sorted(d for d in os.listdir(local_root) if os.path.isdir(os.path.join(local_root, d))) if os.path.isdir(local_root) else []
    for name in local:
        diff = template_diff(local_template(root, name), server_template(name, env) if name in names else None)
        print(f"  {name:36} {'match' if not diff else 'DIFF: ' + ', '.join(diff)}")
    for t in sorted(server, key=lambda t: t['name']):
        if t['name'] not in local:
            print(f"  {t['name']:36} server only: {t.get('titleTemplate', '')[:50]!r}")
    return 0


def cmd_pull(args, root, env):
    server = server_template(args.name, env)
    if not server:
        raise SystemExit(f'mail template {args.name} not found on the server')
    folder = template_dir(root, args.name)
    meta_path = os.path.join(folder, 'meta.json')
    meta = json.load(open(meta_path, encoding='utf-8')) if os.path.isfile(meta_path) else {}
    meta.update(contentType=server.get('contentType') or 'HTML', status=server.get('status'))
    meta.setdefault('parameters', {})
    files = {f: server.get(key) or '' for f, key in TEMPLATE_FILES.items()}
    files['meta.json'] = json.dumps(meta, ensure_ascii=False, indent=2) + '\n'
    for name, value in files.items():
        rel = os.path.relpath(os.path.join(folder, name), root)
        if args.write:
            os.makedirs(folder, exist_ok=True)
            open(os.path.join(folder, name), 'w', encoding='utf-8').write(value)
            print(f'  wrote {rel}')
        else:
            print(f'  would write {rel} ({len(value)} chars)')
    if not args.write:
        print('\ndry run: re-run with --write')
    return 0


def cmd_push(args, root, env):
    local = local_template(root, args.name)
    server = server_template(args.name, env)
    diff = template_diff(local, server)
    print(f"{args.name}: {'up to date' if not diff else ', '.join(diff)}")
    if not diff:
        return 0
    if not args.yes:
        print('dry run: re-run with --yes after the human approves')
        return 0
    if server:
        backup = os.path.join(root, '.artifacts', 'backups', datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-mail-template')
        os.makedirs(backup, exist_ok=True)
        json.dump(server, open(os.path.join(backup, f'{args.name}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'backup: {os.path.relpath(backup, root)}')
    ezy_client.request_json('POST', '/ezymail/api/v1/templates/add-or-update', dict(templateName=args.name, **local), env=env)
    left = template_diff(local, server_template(args.name, env))
    print('verified' if not left else f'differs after reload: {left}')
    return 0 if not left else 2


def cmd_contact_settings(args, root, env):
    current = contact_settings(env)
    wanted = dict(current)
    if args.response_mail:
        wanted['enableContactUsResponseMail'] = args.response_mail == 'on'
    if args.supporter_emails is not None:
        wanted['supporterEmails'] = ', '.join(e.strip() for e in args.supporter_emails.split(',') if e.strip())
    changes = {k: (current.get(k), wanted[k]) for k in wanted if wanted[k] != current.get(k)}
    for key in ('enableContactUs', 'enableContactUsResponseMail', 'supporterEmails'):
        print(f"  {key}: {current.get(key)!r}" + (f' -> {wanted[key]!r}' if key in changes else ''))
    if not changes:
        print('nothing to change')
        return 0
    if not args.yes:
        print('dry run: re-run with --yes after the human approves')
        return 0
    backup = os.path.join(root, '.artifacts', 'backups', datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-ezysupport-settings')
    os.makedirs(backup, exist_ok=True)
    json.dump(current, open(os.path.join(backup, 'settings.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    body = dict(wanted)
    for key in LIST_FIELDS:
        body[key] = [e.strip() for e in (body.get(key) or '').split(',') if e.strip()]
    ezy_client.request_json('PUT', '/ezysupport/api/v1/settings', body, env=env)
    after = contact_settings(env)
    drift = {k: (wanted.get(k), after.get(k)) for k in set(wanted) | set(after) if wanted.get(k) != after.get(k)}
    print(f'backup: {os.path.relpath(backup, root)}')
    print_status('saved and verified (no other setting changed)' if not drift else f'differs after reload: {drift}', not drift)
    return 0 if not drift else 2


def cmd_test_contact(args, root, env):
    web_url = ezy_client.request_text('/api/v1/settings/web-url', env).strip().rstrip('/')
    body = {'contactUsYourName': 'ezy-mail test', 'contactUsYourEmail': args.email,
            'contactUsSubject': 'ezy-mail test ' + datetime.datetime.now().strftime('%H:%M:%S'),
            'contactUsMessage': 'Automated Contact Us check; this request is deleted right after the check.'}
    print(f'POST {web_url}/api/v1/contact-us as {args.email!r}; this stores a request and sends real mail')
    if not args.yes:
        print('dry run: re-run with --yes after the human approves')
        return 0
    req = urllib.request.Request(web_url + '/api/v1/contact-us', data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', 'User-Agent': ezy_client.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status, text = resp.status, resp.read().decode(errors='replace')
    except urllib.error.HTTPError as err:
        status, text = err.code, err.read().decode(errors='replace')
    print(f'  public API answered {status} {text[:200]!r}')
    if status >= 300 or re.search(r'"(error|contactUs\w+)"\s*:', text):
        return 2
    time.sleep(args.wait)
    requests = (ezy_client.request_json('GET', '/ezysupport/api/v1/contact-us?limit=20', env=env) or {}).get('items') or []
    record = next((r for r in requests if r.get('title') == body['contactUsSubject']), None)
    print(f"  stored request: {'id ' + str(record['id']) if record else 'NOT FOUND'}")
    mails = (ezy_client.request_json('GET', '/ezymail/api/v1/mails?limit=20', env=env) or {}).get('items') or []
    since = (record or {}).get('createdAt', 0)
    for m in [m for m in mails if m.get('createdAt', 0) >= since and m.get('id') != (record or {}).get('id')]:
        print(f"  mail {m['id']} {m['status']:11} to {m.get('to')}: {m.get('title', '')[:60]!r}")
    if record:
        ezy_client.request_json('DELETE', f"/ezysupport/api/v1/contact-us/{record['id']}", env=env)
        print('  test request deleted (EzySupport keeps it with status DELETED)')
    return 0 if record else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    sub.add_parser('templates')
    pl = sub.add_parser('pull')
    pl.add_argument('name')
    pl.add_argument('--write', action='store_true')
    ps = sub.add_parser('push')
    ps.add_argument('name')
    ps.add_argument('--yes', action='store_true')
    cs = sub.add_parser('contact-settings')
    cs.add_argument('--response-mail', choices=('on', 'off'))
    cs.add_argument('--supporter-emails', help='comma-separated list; empty string clears it')
    cs.add_argument('--yes', action='store_true')
    tc = sub.add_parser('test-contact')
    tc.add_argument('--email', required=True, help='an inbox the site owner controls')
    tc.add_argument('--wait', type=int, default=15, help='seconds to wait for the mails to be processed')
    tc.add_argument('--yes', action='store_true')
    args = parser.parse_args()
    root = ezy_client.find_project_root()
    env = ezy_client.load_env(root)
    return {'status': cmd_status, 'templates': cmd_templates, 'pull': cmd_pull, 'push': cmd_push,
            'contact-settings': cmd_contact_settings, 'test-contact': cmd_test_contact}[args.cmd](args, root, env)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except ezy_client.EzyError as err:
        print_status(f'error: {err}', False, file=sys.stderr)
        sys.exit(2)
