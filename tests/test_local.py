"""ezy new --mode local|both: compose files, environment.json, Docker checks and the first start.

No real Docker: state(), the docker commands and the HTTP probes are mocked.
"""
import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
from unittest import mock

from test_cli import run

from ezyplatform_cli import docker_setup, local_stack


def read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


class LocalProjectTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = os.path.join(tmp.name, 'site')
        used = mock.patch.object(local_stack, 'compose_project_used', return_value=[])
        self.used = used.start()
        self.addCleanup(used.stop)

    def envs(self):
        return json.loads(read(os.path.join(self.dir, 'environment.json')))

    def test_local_writes_compose_env_and_local_environment(self):
        code, out = run('new', self.dir, '--mode', 'local', '--no-start')
        self.assertEqual(code, 0, out)
        compose = read(os.path.join(self.dir, 'docker-compose.yml'))
        self.assertIn('?permitMysqlScheme', compose)
        self.assertIn('mysql_native_password', compose)
        self.assertIn('"-h", "127.0.0.1"', compose)
        env = local_stack.read_env(self.dir)
        self.assertGreater(len(env['MYSQL_PASSWORD']), 16)
        self.assertNotEqual(env['MYSQL_PASSWORD'], env['MYSQL_ROOT_PASSWORD'])
        if os.name != 'nt':
            self.assertEqual(stat.S_IMODE(os.stat(os.path.join(self.dir, '.env')).st_mode), 0o600)
        self.assertIn('.env', read(os.path.join(self.dir, '.gitignore')).split())
        envs = self.envs()
        self.assertEqual([e['name'] for e in envs], ['local'])
        self.assertEqual(envs[0]['admin_url'], f"http://127.0.0.1:{env['EZY_ADMIN_PORT']}")
        self.assertTrue(envs[0]['default'])
        self.assertIn('docker compose up -d', out)

    def test_both_keeps_live_entries_and_makes_local_default(self):
        code, out = run('new', self.dir, '--mode', 'both', '--admin-url', 'https://admin.example.test', '--no-start')
        self.assertEqual(code, 0, out)
        envs = {e['name']: e for e in self.envs()}
        self.assertTrue(envs['local']['default'])
        self.assertFalse(envs['production']['default'])
        self.assertEqual(envs['production']['admin_url'], 'https://admin.example.test')

    def test_rerun_keeps_ports_and_passwords(self):
        run('new', self.dir, '--mode', 'local', '--no-start')
        first = local_stack.read_env(self.dir)
        run('new', self.dir, '--mode', 'local', '--no-start')
        self.assertEqual(local_stack.read_env(self.dir), first)

    def test_every_new_project_gets_its_own_docker_project(self):
        other = os.path.join(os.path.dirname(self.dir), 'other', 'site')  # same folder name elsewhere
        run('new', self.dir, '--mode', 'local', '--no-start')
        run('new', other, '--mode', 'local', '--no-start')
        first = local_stack.read_env(self.dir)['COMPOSE_PROJECT_NAME']
        second = local_stack.read_env(other)['COMPOSE_PROJECT_NAME']
        self.assertTrue(first.startswith('ezy-site-') and second.startswith('ezy-site-'))
        self.assertNotEqual(first, second)

    def test_a_name_docker_already_uses_is_never_reused(self):
        # e.g. leftover volumes: their MySQL keeps old passwords, a new .env would get "Access denied"
        taken = []
        self.used.side_effect = lambda name: ['old-volume'] if not taken and not taken.append(name) else []
        run('new', self.dir, '--mode', 'local', '--no-start')
        self.assertNotEqual(local_stack.read_env(self.dir)['COMPOSE_PROJECT_NAME'], taken[0])

    def test_live_mode_writes_no_docker_files(self):
        code, out = run('new', self.dir, '--mode', 'live', '--admin-url', 'https://admin.example.test')
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'docker-compose.yml')))
        self.assertEqual(self.envs()[0]['name'], 'production')

    def test_missing_docker_is_not_installed_without_consent(self):
        with mock.patch.object(docker_setup, 'state', return_value='missing'), \
                mock.patch.object(docker_setup, '_run_steps') as steps, \
                mock.patch.object(docker_setup, 'install_commands', return_value=[['brew', 'install', '--cask', 'orbstack']]), \
                mock.patch('sys.stdin.isatty', return_value=False):
            code, out = run('new', self.dir, '--mode', 'local')
        self.assertEqual(code, 1, out)
        steps.assert_not_called()
        self.assertIn('--yes', out)
        self.assertTrue(os.path.exists(os.path.join(self.dir, 'docker-compose.yml')))

    def test_yes_installs_docker_then_starts_the_stack(self):
        states = iter(['missing', 'ready'])
        with mock.patch.object(docker_setup, 'state', side_effect=lambda: next(states)), \
                mock.patch.object(docker_setup, '_run_steps', return_value=True) as steps, \
                mock.patch.object(docker_setup, 'install_commands', return_value=[['brew', 'install', '--cask', 'orbstack']]), \
                mock.patch.object(local_stack, 'start', return_value=True) as start:
            code, out = run('new', self.dir, '--mode', 'local', '--yes')
        self.assertEqual(code, 0, out)
        steps.assert_called_once()
        start.assert_called_once()
        self.assertIn('/setup-admin', out)


class StartTest(unittest.TestCase):
    def test_first_boot_restarts_once_when_the_website_answers_404(self):
        calls = []
        clock = [0.0]
        admin = iter([0, 302])

        def status(url):
            if url.endswith('/login'):
                return next(admin, 302)
            # the website answers 404 until the app is restarted, as on a real first boot
            return 200 if ['docker', 'compose', 'restart', 'ezyplatform'] in calls else 404

        def sleep(seconds):
            clock[0] += seconds
        with mock.patch.object(local_stack.subprocess, 'call', side_effect=lambda argv, **kw: calls.append(argv) or 0), \
                mock.patch.object(local_stack, 'http_status', side_effect=status), \
                mock.patch.object(local_stack.time, 'sleep', side_effect=sleep), \
                mock.patch.object(local_stack.time, 'time', side_effect=lambda: clock[0]):
            env = {'EZY_ADMIN_PORT': '9090', 'EZY_WEB_PORT': '8080'}
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(local_stack.start('.', env))
        self.assertEqual(calls[0], ['docker', 'compose', 'up', '-d'])
        self.assertIn(['docker', 'compose', 'restart', 'ezyplatform'], calls)

    def test_install_commands_per_os(self):
        with mock.patch.object(docker_setup.shutil, 'which', return_value='/x'):
            self.assertEqual(docker_setup.install_commands('mac'), [['brew', 'install', '--cask', 'orbstack']])
            self.assertIn('get.docker.com', docker_setup.install_commands('linux')[0][2])
            self.assertEqual(docker_setup.install_commands('windows')[0][-1], 'Docker.DockerDesktop')
        with mock.patch.object(docker_setup.shutil, 'which', return_value=None):
            self.assertIsNone(docker_setup.install_commands('mac'))


if __name__ == '__main__':
    unittest.main()
