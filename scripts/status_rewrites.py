"""Fail-fast CLI adaptations of the upstream skills' diagnostic output."""

NEW = 'ezy-new/scripts/ezy_new.py'
SYNC = 'ezy-sync/scripts/ezy_sync.py'
MEDIA = 'ezy-media/scripts/ezy_media.py'
MAIL = 'ezy-mail/scripts/ezy_mail.py'
VERIFY = 'ezy-verify/scripts/ezy_verify.py'
CLIENT = 'ezy-shared/ezy_client.py'

# Each source fragment is checked exactly, like the command hints in the vendor.
# A plugin upgrade must explicitly reconcile any changed diagnostic behavior.
REWRITES = [
    (NEW, "sys.path.insert(0, os.path.join(SKILLS_ROOT, 'ezy-shared'))",
     "sys.path.insert(0, os.path.join(SKILLS_ROOT, 'ezy-shared'))\nfrom ezy_output import print_status  # noqa: E402", 1),
    *[(path, 'import ezy_client  # noqa: E402',
       'import ezy_client  # noqa: E402\nfrom ezy_output import print_status  # noqa: E402', 1)
      for path in (SYNC, MEDIA, MAIL, VERIFY)],
    (CLIENT, 'with urllib.request.urlopen(req, timeout=60) as resp:',
     "# Read-only checks have a short budget; writes and uploads retain theirs.\n"
     "        with urllib.request.urlopen(req, timeout=10 if method == 'GET' else 60) as resp:", 1),
    (VERIFY, 'with urllib.request.urlopen(req, timeout=60) as resp:',
     'with urllib.request.urlopen(req, timeout=10) as resp:', 1),
    (NEW, 'print(f\'x environment.json missing in {root}; run "create" first\')',
     'print_status(f\'environment.json missing in {root}; run "ezy new" first\', False)', 1),
    (NEW, "print(f'x environment.json is not valid JSON: {err}')",
     "print_status(f'environment.json is not valid JSON: {err}', False)", 1),
    (NEW, "print('! environment.json is readable by other users; consider: chmod 600 environment.json')",
     "print_status('environment.json is readable by other users; consider: chmod 600 environment.json')", 1),
    (NEW, "print('x not ready:\\n  - ' + '\\n  - '.join(problems) + '\\n')",
     "print_status('not ready:', False)\n        for problem in problems:\n            print_status(problem, False)\n        print()", 1),
    (NEW, "print(f'x connection failed: HTTP {err.status} — {hint.get(err.status, err.body[:200])}')",
     "print_status(f'connection failed: HTTP {err.status} — {hint.get(err.status, err.body[:200])}', False)", 1),
    (NEW, "print(f'x cannot reach {url}: {err}')",
     "print_status(f'cannot reach {url}: {err}', False)", 1),
    (NEW, 'print(f"✓ connected to {url} as environment \'{env.get(\'name\')}\'")',
     'print_status(f"connected to {url} as environment \'{env.get(\'name\')}\'", True)', 1),
    (NEW, 'print(f"  roles: {\', \'.join(roles) or \'none\'}" + (\'  (full admin rights — keep this token private)\' if \'super_admin\' in roles else \'\'))',
     'print_status(f"roles: {\', \'.join(roles) or \'none\'}" + (\'  (full admin rights — keep this token private)\' if \'super_admin\' in roles else \'\'), True)', 1),
    (NEW, "print(f'  public site: {web}')", "print_status(f'public site: {web}', True)", 1),
    (NEW, "print(f'  fragment groups on server: {len(fragments)} ({sum(len(v) for v in fragments.values())} fragments)')",
     "print_status(f'fragment groups on server: {len(fragments)} ({sum(len(v) for v in fragments.values())} fragments)', True)", 1),
    (NEW, 'print(f"  local pages: {\', \'.join(local_pages) or \'none\'}")',
     'print_status(f"local pages: {\', \'.join(local_pages) or \'none\'}")', 1),
    (SYNC, '    dirty = 0\n', '    dirty = 0\n    local_only = 0\n', 1),
    (SYNC, "                print(f'{row[0]:34} {row[1]:8} {row[2]:15} {row[3]}')",
     "                draft = row[3].startswith('local only')\n"
     "                local_only += draft\n"
     "                print_status(f'{row[0]:34} {row[1]:8} {row[2]:15} {row[3]}',\n"
     "                             None if draft else row[3] == 'match')", 1),
    (SYNC, "    print(f'\\n{dirty} difference(s)' if dirty else '\\nlocal and server are in sync')",
     "    print()\n"
     "    if dirty:\n"
     "        print_status(f'{dirty} difference(s)', False)\n"
     "    elif local_only:\n"
     "        print_status(f'no differences; {local_only} local-only draft(s) not on server yet')\n"
     "    else:\n"
     "        print_status('local and server are in sync', True)", 1),
    (MEDIA, 'print(f"{name:48} {\'on server\' if on_server else \'MISSING on server\':18} {visibility}")',
     'print_status(f"{name:48} {\'on server\' if on_server else \'MISSING on server\':18} {visibility}", on_server)', 1),
    (MEDIA, "    print(f'\\n{missing} file(s) not on the server' if missing else '\\nall listed files exist on the server')",
     "    print()\n"
     "    if names:\n"
     "        print_status(f'{missing} file(s) not on the server' if missing else 'all listed files exist on the server', not missing)\n"
     "    else:\n"
     "        print_status('no local media files to check')", 1),
    (MEDIA, "        print(f'  ✓ {action} {name}' + (' (exists now)' if exists(name, env) else ' — NOT found after upload'))",
     "        verified = exists(name, env)\n"
     "        print_status(f'{action} {name}' + (' (exists now)' if verified else ' — NOT found after upload'), verified)", 1),
    (MEDIA, "    print('  ✓ changed' if is_public(args.name, env) == wanted else '  x state did not change')",
     "    verified = is_public(args.name, env) == wanted\n"
     "    print_status('changed' if verified else 'state did not change', verified)", 1),
    (MAIL, "print('  ! no default delivery service found')",
     "print_status('no default delivery service found', False)", 1),
    (MAIL, "print(f'  default: {default[1]} ({default[0]})')",
     "print_status(f'default: {default[1]} ({default[0]})', True)", 1),
    (MAIL, 'print(f\'  {key}: {fields[key] or "(empty)"}\')',
     'print_status(f\'{key}: {fields[key] or "(empty)"}\', bool(fields[key]))', 1),
    (MAIL, 'print(f"  {key}: {\'set\' if fields[key] else \'(empty)\'}")',
     'print_status(f"{key}: {\'set\' if fields[key] else \'(empty)\'}", True if fields[key] else None)', 1),
    (MAIL, 'print(f"  ! empty fields: {\', \'.join(empty)}; every mail fails until they are filled in the admin")',
     'print_status(f"empty fields: {\', \'.join(empty)}; every mail fails until they are filled in the admin", False)', 1),
    (MAIL, '    print(f"\\nLast {len(mails)} mail(s): {dict(counts) or \'none\'}")',
     '    print()\n'
     '    health = False if counts.get(\'SEND_ERROR\') else True if mails and set(counts) == {\'SENT\'} else None\n'
     '    print_status(f"Last {len(mails)} mail(s): {dict(counts) or \'none\'}", health)', 1),
    (MAIL, 'print(f"  last SENT: {stamp(last_sent[\'createdAt\']) if last_sent else \'never (in this window)\'}")',
     'print_status(f"last SENT: {stamp(last_sent[\'createdAt\']) if last_sent else \'never (in this window)\'}", True if last_sent else None)', 1),
    (MAIL, 'print(f"  last SEND_ERROR: {stamp(last_error[\'createdAt\'])} {last_error.get(\'title\', \'\')[:60]!r}")',
     'print_status(f"last SEND_ERROR: {stamp(last_error[\'createdAt\'])} {last_error.get(\'title\', \'\')[:60]!r}", False)', 1),
    (MAIL, "print('  ! nothing was delivered: fix the delivery service before building features that send mail')",
     "print_status('nothing was delivered: fix the delivery service before building features that send mail', False if last_error else None)", 1),
    (MAIL, 'print(f"  {key}: {cs.get(key) if cs.get(key) not in (\'\', None) else \'(empty)\'}")',
     'print_status(f"{key}: {cs.get(key) if cs.get(key) not in (\'\', None) else \'(empty)\'}")', 1),
    (MAIL, "print('  ! no supporter emails: nobody is notified of new contact requests')",
     "print_status('no supporter emails: nobody is notified of new contact requests', False)", 1),
    (MAIL, "print(f'  stored requests: {total}')",
     "print_status(f'stored requests: {total}', True if total is not None else None)", 1),
    (MAIL, "print(f'  EzySupport not available: {err}')",
     "print_status(f'EzySupport not available: {err}', False)", 1),
    (MAIL, "print('saved and verified (no other setting changed)' if not drift else f'! differs after reload: {drift}')",
     "print_status('saved and verified (no other setting changed)' if not drift else f'differs after reload: {drift}', not drift)", 1),
    (VERIFY, "print(f'{url} -> HTTP {status}, {len(html)} chars')",
     "print_status(f'{url} -> HTTP {status}, {len(html)} chars', status == 200)", 1),
    (VERIFY, "print(f'unrendered template markers: {len(markers)}' + (f' e.g. {markers[:3]}' if markers else ''))",
     "print_status(f'unrendered template markers: {len(markers)}' + (f' e.g. {markers[:3]}' if markers else ''), not markers)", 1),
    (VERIFY, 'print(f"  {\'✓\' if ok else \'x\'} contains {text!r}")',
     'print_status(f"contains {text!r}", ok)', 1),
    *[(path, "print(f'error: {err}', file=sys.stderr)",
       "print_status(f'error: {err}', False, file=sys.stderr)", 1)
      for path in (SYNC, MEDIA, MAIL, VERIFY)],
]


def rewrite_status(path, text):
    """Apply only known source shapes; reject drift before a vendor can ship it."""
    for file, old, new, count in REWRITES:
        if path != file:
            continue
        found = text.count(old)
        if found != count:
            raise SystemExit(f'{path}: expected {count} x {old!r}, found {found}; update REWRITES')
        text = text.replace(old, new)
    return text
