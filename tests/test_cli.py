"""End-to-end checks of the `ezy` command against a local stub admin server."""
import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from unittest import mock
from http.server import BaseHTTPRequestHandler, HTTPServer

from ezyplatform_cli import cli
from ezyplatform_cli.cli import main

ROUTES = {
    '/api/v1/admins/me/roles': [{'name': 'content_admin'}],
    '/api/v1/settings/web-url': 'https://www.example.test',
    '/ezyarticle/api/v1/pages/fragments?keyword=': {'common': ['header', 'footer']},
}


class StubAdmin(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Authorization') != 'Bearer test-token' or self.path not in ROUTES:
            self.send_response(401 if self.path in ROUTES else 404)
            self.end_headers()
            return
        value = ROUTES[self.path]
        body = (value if isinstance(value, str) else json.dumps(value)).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def run(*argv, cwd=None):
    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    os.chdir(cwd or old)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
    finally:
        os.chdir(old)
    return code, out.getvalue() + err.getvalue()


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_help_and_version(self):
        self.assertEqual(run('--help')[0], 0)
        code, out = run('--version')
        self.assertEqual(code, 0)
        self.assertIn('ezyplatform skills', out)
        self.assertEqual(run('nope')[0], 2)

    def test_subcommand_help_uses_ezy_names(self):
        for cmd in ('new', 'init', 'plugins', 'skills', 'check', 'token', 'whoami'):
            code, out = run(cmd, '--help')
            self.assertEqual(code, 0, cmd)
            self.assertIn('usage: ezy ', out)
            self.assertNotIn('python3 ezy_', out)

    def test_site_operations_handoff_to_plugins_without_executing(self):
        removed = ('get', 'content', 'sync', 'status', 'pull', 'pull-all', 'publish', 'media', 'i18n', 'mail', 'verify')
        with mock.patch.object(cli, 'run_script', side_effect=AssertionError('site script must not run')) as execute:
            for command in removed:
                for option in ('--help', '--yes'):
                    with self.subTest(command=command, option=option):
                        code, out = run(command, option, cwd=self.dir)
                        self.assertEqual(code, 2)
                        self.assertIn('handled by the ezyplatform plugin', out)
                        self.assertIn('coding agent', out)
                        self.assertIn('ezy init', out)
            execute.assert_not_called()
        self.assertEqual(os.listdir(self.dir), [])
        code, help_text = run('--help')
        for command in removed:
            self.assertNotRegex(help_text, rf'(?m)^  {command}(?: |$)')
        self.assertNotIn('Publish (', help_text)

    def test_init_with_a_folder_points_to_new(self):
        code, out = run('init', self.dir, '--admin-url', 'https://admin.example.test')
        self.assertEqual(code, 2)
        self.assertIn('ezy new', out)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'environment.json')))

    def test_new_then_check_placeholder_fails(self):
        code, out = run('new', self.dir, '--admin-url', 'https://admin.example.test')
        self.assertEqual(code, 0, out)
        for name in ('environment.json', 'AGENTS.md', 'README.md', '.gitignore', 'pages/example-page/meta.json'):
            self.assertTrue(os.path.exists(os.path.join(self.dir, name)), name)
        self.assertIn('ezy check', out)
        code, out = run('check', self.dir)
        self.assertEqual(code, 1)
        self.assertIn('admin_access_token is still the placeholder', out)

    def test_unreachable_server_is_a_short_error(self):
        run('new', self.dir, '--admin-url', 'http://127.0.0.1:9')
        code, out = run('whoami', cwd=self.dir)
        self.assertEqual(code, 2)
        self.assertIn('cannot reach the admin server', out)
        self.assertNotIn('Traceback', out)

    def test_copy_skills(self):
        code, out = run('new', self.dir, '--copy-skills', '--no-example')
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, '.claude/skills/ezy-guide/SKILL.md')))
        self.assertTrue(os.path.isfile(os.path.join(self.dir, '.claude/skills/ezy-shared/ezy_client.py')))
        for skill, script in [('ezy-publish', 'ezy_publish.py'), ('ezy-sync', 'ezy_sync.py')]:
            self.assertTrue(os.path.isfile(os.path.join(self.dir, '.claude/skills', skill, 'scripts', script)))

    def test_check_and_whoami_against_server(self):
        server = HTTPServer(('127.0.0.1', 0), StubAdmin)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = f'http://127.0.0.1:{server.server_port}'
        run('new', self.dir, '--admin-url', url)
        env_path = os.path.join(self.dir, 'environment.json')
        with open(env_path) as fh:
            envs = json.load(fh)
        envs[0]['admin_access_token'] = 'test-token'
        with open(env_path, 'w') as fh:
            json.dump(envs, fh)
        code, out = run('check', self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn('roles: content_admin', out)
        self.assertIn('fragment groups on server: 1 (2 fragments)', out)
        self.assertNotIn('test-token', out)
        code, out = run('whoami', cwd=self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn('content_admin', out)


class UpdateTest(unittest.TestCase):
    def setUp(self):
        from ezyplatform_cli import self_update
        self.mod = self_update
        patcher = mock.patch.object(self_update, 'find_uv', return_value='/bin/uv')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_already_latest(self):
        with mock.patch.object(self.mod, 'latest_version', return_value=self.mod.__version__), \
                mock.patch.object(self.mod, 'refresh', return_value=0) as refresh, \
                mock.patch.object(self.mod.subprocess, 'call') as call:
            code, out = run('update')
        self.assertEqual(code, 0)
        self.assertIn('is the latest version', out)
        call.assert_not_called()
        refresh.assert_called_once()

    @unittest.skipIf(os.name == 'nt', 'Windows installs in a new console window')
    def test_installs_newer_release_wheel(self):
        with mock.patch.object(self.mod, 'latest_version', return_value='99.0.0'), \
                mock.patch.object(self.mod.subprocess, 'call', return_value=0) as call:
            code, out = run('update')
        self.assertEqual(code, 0, out)
        cmd = call.call_args_list[0][0][0]
        self.assertEqual(cmd[:4], ['/bin/uv', 'tool', 'install', '--force'])
        self.assertTrue(cmd[-1].endswith('/v99.0.0/ezyplatform_cli-99.0.0-py3-none-any.whl'))
        # then the new ezy refreshes plugins and skill copies
        self.assertEqual(call.call_args_list[1][0][0][-2:], ['update', '--refresh'])

    def test_uninstall_needs_confirmation(self):
        with mock.patch.object(self.mod.sys.stdin, 'isatty', return_value=False), \
                mock.patch.object(self.mod.subprocess, 'call') as call:
            code, out = run('uninstall')
        self.assertEqual(code, 1)
        self.assertIn('--yes', out)
        call.assert_not_called()

    @unittest.skipIf(os.name == 'nt', 'Windows uninstalls in a new console window')
    def test_uninstall_uses_the_installing_tool(self):
        for how, expected in (('uv', ['/bin/uv', 'tool', 'uninstall', 'ezyplatform-cli']),
                              ('pipx', ['pipx', 'uninstall', 'ezyplatform-cli'])):
            with mock.patch.object(self.mod, 'installer', return_value=how), \
                    mock.patch.object(self.mod.subprocess, 'call', return_value=0) as call:
                code, out = run('uninstall', '--yes')
            self.assertEqual(code, 0, out)
            self.assertEqual(call.call_args[0][0], expected)

    def test_offline_is_a_short_error(self):
        with mock.patch.object(self.mod, 'latest_version', side_effect=OSError('offline')):
            code, out = run('update')
        self.assertEqual(code, 2)
        self.assertIn('cannot check for updates', out)


if __name__ == '__main__':
    unittest.main()
