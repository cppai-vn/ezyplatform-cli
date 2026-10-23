"""Diagnostic classifications, read budgets and reproducible bundled adaptations."""
import contextlib
import importlib.util
import io
import json
import re
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ezyplatform_cli.cli import SKILLS as INSTALLED_SKILLS

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'src/ezyplatform_cli/skills'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def capture(function, *args):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = function(*args)
    return result, output.getvalue()


class BundledStatusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for name in ('new', 'sync', 'media', 'mail', 'verify', 'publish'):
            setattr(cls, name, load(f'bundled_{name}', Path(INSTALLED_SKILLS) / f'ezy-{name}/scripts/ezy_{name}.py'))
        cls.client = cls.sync.ezy_client

    def test_check_missing_or_invalid_configuration_is_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            args = SimpleNamespace(target=folder)
            code, output = capture(self.new.cmd_check, args)
            self.assertEqual(code, 1)
            self.assertTrue(output.startswith('✗ environment.json missing'))
            Path(folder, 'environment.json').write_text('{')
            code, output = capture(self.new.cmd_check, args)
            self.assertEqual(code, 1)
            self.assertTrue(output.startswith('✗ environment.json is not valid JSON'))

    def test_check_success_keeps_token_private(self):
        with tempfile.TemporaryDirectory() as folder:
            env = {'default': True, 'name': 'test', 'admin_url': 'https://admin.example.test',
                   'admin_access_token': 'private-test-token'}
            Path(folder, 'environment.json').write_text(json.dumps([env]))
            Path(folder, 'environment.json').chmod(0o600)
            Path(folder, '.gitignore').write_text('environment.json\n')
            with mock.patch.object(self.client, 'request_json', side_effect=[[{'name': 'admin'}], {}]), \
                    mock.patch.object(self.client, 'request_text', return_value='https://example.test'):
                code, output = capture(self.new.cmd_check, SimpleNamespace(target=folder))
        self.assertEqual(code, 0)
        self.assertIn('✓ connected to', output)
        self.assertIn('✓ roles: admin', output)
        self.assertIn('use the installed ezy-guide skill', output)
        self.assertNotIn('private-test-token', output)
        self.assertNotIn('\033[', output)

    def test_setup_next_steps_point_to_installed_agent_skills(self):
        _, output = capture(self.new.print_token_help, 'https://admin.example.test', '/tmp/site')
        self.assertIn('Validate: ezy check /tmp/site', output)
        self.assertIn('use the installed ezy-guide skill for content work', output)

    def test_bundled_assets_do_not_advertise_removed_cli_routes(self):
        removed = re.compile(r'\bezy\s+(?:sync|status|pull|pull-all|publish|media|i18n|mail|verify|get)\b')
        for path in Path(INSTALLED_SKILLS).rglob('*'):
            if path.suffix in ('.py', '.md'):
                with self.subTest(path=str(path.relative_to(INSTALLED_SKILLS))):
                    self.assertIsNone(removed.search(path.read_text(encoding='utf-8')))

    def test_content_script_usage_and_rollback_hints_remain_available(self):
        for skill, script in [('sync', 'ezy_sync.py'), ('publish', 'ezy_publish.py'),
                              ('media', 'ezy_media.py'), ('i18n', 'ezy_messages.py'),
                              ('mail', 'ezy_mail.py'), ('verify', 'ezy_verify.py')]:
            path = Path(INSTALLED_SKILLS) / f'ezy-{skill}/scripts/{script}'
            self.assertIn(f'python3 {script}', path.read_text())
        publish = (Path(INSTALLED_SKILLS) / 'ezy-publish/scripts/ezy_publish.py').read_text()
        self.assertEqual(publish.count('{restore_command(backup, root)}'), 3)
        client = (Path(INSTALLED_SKILLS) / 'ezy-shared/ezy_client.py').read_text()
        self.assertIn('python3 ezy_client.py get <api-path>', client)

    def test_partial_publish_failure_prints_executable_restore_command(self):
        jobs = [{'target': f'page:page-{index}', 'lang': None, 'warn': None,
                 'live': {'id': index, 'slug': f'page-{index}', 'status': 'PUBLISHED',
                          'postType': 'PAGE', 'contentType': 'HTML'},
                 'changes': {'content': 'updated'}} for index in range(3)]
        with tempfile.TemporaryDirectory(prefix='site project ') as folder, \
                mock.patch.object(self.publish, '__file__', str(Path(folder, 'plugin files/ezy_publish.py'))), \
                mock.patch.object(self.publish, 'build_jobs', return_value=jobs), \
                mock.patch.object(self.publish, 'verify', return_value=[]) as verify, \
                mock.patch.object(self.client, 'put_post', side_effect=[None, self.client.EzyError(500, 'unavailable')]) as put:
            code, output = capture(self.publish.cmd_plan_or_apply,
                                   SimpleNamespace(targets=['page:home'], lang=None, cmd='apply', yes=True), folder, {})
            command = output.split('restore with: ', 1)[1].splitlines()[0]
            args = shlex.split(command)
            self.assertEqual(args[:3], ['python3', 'plugin files/ezy_publish.py', 'restore'])
            self.assertEqual(args[-1], '--yes')
            self.assertEqual(len(list(Path(folder, args[3]).glob('*.json'))), 3)
        self.assertEqual(code, 2)
        self.assertEqual(put.call_count, 2)
        verify.assert_called_once_with(jobs[0], {})

    def test_restore_command_quotes_script_and_backup_paths(self):
        with tempfile.TemporaryDirectory(prefix='site project ') as folder, \
                mock.patch.object(self.publish, '__file__', str(Path(folder, 'plugin files/ezy_publish.py'))):
            command = self.publish.restore_command(str(Path(folder, 'backup files')), folder)
        self.assertEqual(shlex.split(command), ['python3', 'plugin files/ezy_publish.py', 'restore', 'backup files', '--yes'])

    def test_sync_classifies_matches_drift_errors_and_drafts(self):
        for state, marker, code in [('match', '✓', 0), ('DIFF (local 2 / server 3 chars)', '✗', 1),
                                    ('ERROR 403', '✗', 1), ('MISSING on server (local status PUBLISHED)', '✗', 1),
                                    ('local only (DRAFT, not on server yet)', '?', 0)]:
            with self.subTest(state=state), mock.patch.object(self.sync.ezy_local, 'languages', return_value=[]), \
                    mock.patch.object(self.sync, 'compare', return_value=[('page:home', 'default', 'content', state)]):
                result, output = capture(self.sync.cmd_status, SimpleNamespace(targets=['page:home']), '/tmp', {})
            self.assertEqual(result, code)
            self.assertTrue(output.startswith(marker + ' page:home'), output)
            self.assertTrue(output.rstrip().splitlines()[-1].startswith(marker + ' '), output)

    def test_media_missing_and_empty_keep_success_exit_code(self):
        with mock.patch.object(self.media, 'exists', side_effect=[True, False]), \
                mock.patch.object(self.media, 'is_public', return_value=False):
            code, output = capture(self.media.cmd_status, SimpleNamespace(names=['private.css', 'missing.css']), '/tmp', {})
        self.assertEqual(code, 0)
        self.assertIn('✓ private.css', output)
        self.assertIn('✗ missing.css', output)
        self.assertIn('✗ 1 file(s)', output)
        with tempfile.TemporaryDirectory() as folder:
            code, output = capture(self.media.cmd_status, SimpleNamespace(names=[]), folder, {})
        self.assertEqual(code, 0)
        self.assertEqual(output, '\n? no local media files to check\n')

    def test_mail_pending_errors_and_password_masking(self):
        html = '<form id="mailSettingsForm"><input name="mailPassword" type="password" value="secret-test-password"></form>'
        for state, marker in [('SENT', '✓'), ('SEND_ERROR', '✗'), ('QUEUED', '?')]:
            with self.subTest(state=state), \
                    mock.patch.object(self.mail, 'delivery_services', return_value=[('SMTP', 'SMTP', True)]), \
                    mock.patch.object(self.client, 'request_text', return_value=html), \
                    mock.patch.object(self.mail, 'contact_settings', return_value={}), \
                    mock.patch.object(self.client, 'request_json', side_effect=[
                        {'items': [{'status': state, 'createdAt': 0}]}, {'total': 0}]):
                code, output = capture(self.mail.cmd_status, SimpleNamespace(), '/tmp', {})
            self.assertEqual(code, 0)
            self.assertIn(f'{marker} Last 1 mail(s)', output)
            self.assertIn('✓ mailPassword: set', output)
            self.assertNotIn('secret-test-password', output)
            if state == 'SEND_ERROR':
                self.assertIn('✗ last SEND_ERROR:', output)
            elif state == 'QUEUED':
                self.assertIn('? nothing was delivered:', output)

    def test_media_upload_result_matches_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            media = Path(folder, 'site.css')
            media.write_text('body {}')
            for verified in (True, False):
                with self.subTest(verified=verified), \
                        mock.patch.object(self.media, 'exists', side_effect=[False, verified]), \
                        mock.patch.object(self.client, 'upload_file') as upload:
                    code, output = capture(self.media.cmd_upload, SimpleNamespace(files=[str(media)], yes=True), folder, {})
                self.assertEqual(code, 0)
                self.assertIn(('✓' if verified else '✗') + ' add site.css', output)
                upload.assert_called_once()

    def test_media_visibility_result_matches_verification(self):
        for verified in (True, False):
            with self.subTest(verified=verified), \
                    mock.patch.object(self.media, 'exists', return_value=True), \
                    mock.patch.object(self.media, 'is_public', side_effect=[False, verified]), \
                    mock.patch.object(self.client, '_send') as send:
                code, output = capture(self.media.cmd_visibility, SimpleNamespace(name='site.css', cmd='public', yes=True), '/tmp', {})
            self.assertEqual(code, 0)
            self.assertIn('✓ changed' if verified else '✗ state did not change', output)
            send.assert_called_once_with('PUT', '/api/v1/media/site.css/public', env={})

    def test_mail_stored_request_count_distinguishes_unknown_and_zero(self):
        for total, marker in [(None, '?'), (0, '✓'), (2, '✓')]:
            with self.subTest(total=total), \
                    mock.patch.object(self.mail, 'delivery_services', return_value=[]), \
                    mock.patch.object(self.mail, 'contact_settings', return_value={}), \
                    mock.patch.object(self.client, 'request_json', side_effect=[{}, {'total': total}]):
                code, output = capture(self.mail.cmd_status, SimpleNamespace(), '/tmp', {})
            self.assertEqual(code, 0)
            self.assertIn(f'{marker} stored requests: {total}', output)

    def test_contact_settings_result_matches_reload(self):
        current = {'enableContactUsResponseMail': False}
        args = SimpleNamespace(response_mail='on', supporter_emails=None, yes=True)
        for verified in (True, False):
            with self.subTest(verified=verified), tempfile.TemporaryDirectory() as folder, \
                    mock.patch.object(self.mail, 'contact_settings', side_effect=[current, {'enableContactUsResponseMail': verified}]), \
                    mock.patch.object(self.client, 'request_json') as request:
                code, output = capture(self.mail.cmd_contact_settings, args, folder, {})
            self.assertEqual(code, 0 if verified else 2)
            self.assertIn('✓ saved and verified' if verified else '✗ differs after reload:', output)
            request.assert_called_once_with('PUT', '/ezysupport/api/v1/settings',
                                            {'enableContactUsResponseMail': True, 'supporterEmails': [], 'recruitmentEmails': []}, env={})

    def test_verify_classifies_results_and_uses_ten_second_budget(self):
        for status, html, expected in [(200, b'hello', 0), (404, b'hello', 1), (200, b'<p th:text="x">', 1)]:
            response = mock.MagicMock(status=status)
            response.read.return_value = html
            with mock.patch.object(self.client, 'load_env', return_value={}), \
                    mock.patch.object(self.client, 'request_text', return_value='https://example.test'), \
                    mock.patch.object(self.verify.urllib.request, 'urlopen') as urlopen:
                urlopen.return_value.__enter__.return_value = response
                code, output = capture(self.verify.cmd_live, SimpleNamespace(path='/', lang=None, expect=['hello']), '/tmp')
            self.assertEqual(code, expected)
            self.assertTrue(output.startswith(('✓' if status == 200 else '✗') + ' https://'))
            self.assertIn(('✓' if b'hello' in html else '✗') + " contains 'hello'", output)
            self.assertEqual(urlopen.call_args.kwargs['timeout'], 10)

    def test_reads_have_short_budget_and_writes_keep_long_budget(self):
        env = {'admin_url': 'https://admin.example.test', 'admin_access_token': 'test-token'}
        for method, timeout in [('GET', 10), ('POST', 60), ('PUT', 60), ('DELETE', 60)]:
            with mock.patch.object(self.client.urllib.request, 'urlopen') as urlopen:
                self.client._send(method, '/api/test', env=env)
            self.assertEqual(urlopen.call_args.kwargs['timeout'], timeout)

    def test_raw_get_and_whoami_remain_unprefixed_json(self):
        with mock.patch.object(self.client, 'request_json', return_value={'token': 'secret', 'value': 42}):
            code, output = capture(self.client.main, ['get', '/api/test'])
        self.assertEqual((code, output), (0, json.dumps({'token': '[redacted]', 'value': 42}, indent=1) + '\n'))
        env = {'name': 'test', 'admin_url': 'https://admin.example.test'}
        with mock.patch.object(self.client, 'load_env', return_value=env), \
                mock.patch.object(self.client, 'request_json', return_value=[{'name': 'admin'}]):
            code, output = capture(self.client.main, ['whoami'])
        self.assertEqual(code, 0)
        self.assertEqual(output, json.dumps(dict(environment='test', admin_url=env['admin_url'], roles=['admin']), indent=1) + '\n')


class VendorStatusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with mock.patch.object(sys, 'path', [str(ROOT / 'scripts')] + sys.path):
            cls.vendor = load('test_vendor_skills', ROOT / 'scripts/vendor_skills.py')

    def test_vendor_copies_renderer_and_adapts_upstream_read_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            source, dest = Path(folder, 'plugin'), Path(folder, 'bundled')
            shared = source / 'skills/ezy-shared'
            shared.mkdir(parents=True)
            (source / '.claude-plugin').mkdir()
            (source / '.claude-plugin/plugin.json').write_text('{"version": "test"}')
            (shared / 'ezy_client.py').write_text(
                'def _send(method):\n    try:\n'
                '        with urllib.request.urlopen(req, timeout=60) as resp:\n            pass\n'
                '    except Exception:\n        raise\n')
            with mock.patch.object(self.vendor, 'DEST', str(dest)), \
                    mock.patch.object(sys, 'argv', ['vendor_skills.py', str(source)]), \
                    mock.patch.object(self.vendor.subprocess, 'run', side_effect=OSError('fixture')):
                capture(self.vendor.main)
            self.assertIn("timeout=10 if method == 'GET' else 60", (dest / 'ezy-shared/ezy_client.py').read_text())
            compile((dest / 'ezy-shared/ezy_client.py').read_text(), 'vendored-client', 'exec')
            self.assertEqual((dest / 'ezy-shared/ezy_output.py').read_bytes(), (ROOT / 'src/ezyplatform_cli/status_output.py').read_bytes())

    def test_changed_upstream_source_fails_loudly(self):
        with self.assertRaisesRegex(SystemExit, 'update REWRITES'):
            self.vendor.rewrite(SKILLS / 'ezy-shared/ezy_client.py', 'with urllib.request.urlopen(req, timeout=30) as resp:')

    def test_vendor_preserves_standalone_content_command_hints(self):
        source = 'python3 ezy_messages.py push web --yes\n'
        self.assertEqual(self.vendor.rewrite(SKILLS / 'ezy-i18n/scripts/ezy_messages.py', source), source)

    def test_local_matching_upstream_reproduces_bundled_scripts(self):
        source = ROOT.parent / 'cppai/agents-plugins/ezyplatform'
        manifest = source / '.claude-plugin/plugin.json'
        if not manifest.exists():
            self.skipTest('matching upstream checkout is not available')
        if json.loads(manifest.read_text())['version'] != json.loads((SKILLS / 'VENDORED.json').read_text())['version']:
            self.skipTest('upstream checkout has a different plugin version')
        for original in (source / 'skills').rglob('*.py'):
            path = original.relative_to(source / 'skills')
            with self.subTest(path=path):
                self.assertEqual(self.vendor.rewrite(SKILLS / path, original.read_text()),
                                 (SKILLS / path).read_text())
        self.assertEqual((SKILLS / 'ezy-shared/ezy_output.py').read_bytes(), (ROOT / 'src/ezyplatform_cli/status_output.py').read_bytes())
