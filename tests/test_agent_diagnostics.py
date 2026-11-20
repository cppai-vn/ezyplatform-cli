"""Fast local-state detection, parallel bounded probes, and full agent scanning."""
import contextlib
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from ezyplatform_cli import agents, doctor, self_update, skills_install
from test_cli import run


class LocalRegistryFastPathTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = os.path.join(tmp.name, 'home')
        os.makedirs(self.home)
        env = mock.patch.dict(os.environ, {'HOME': self.home, 'CLAUDE_CONFIG_DIR': '', 'CODEX_HOME': ''})
        env.start()
        self.addCleanup(env.stop)

    def write(self, rel, content):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(content)
        return path

    def test_claude_local_installed_disabled_and_missing_path(self):
        install_dir = os.path.join(self.home, '.claude', 'plugins', 'cache', 'cppai', 'ezyplatform', '0.5.0')
        os.makedirs(install_dir)
        self.write('.claude/plugins/installed_plugins.json', json.dumps({
            'version': 2,
            'plugins': {'ezyplatform@cppai': [{'scope': 'user', 'installPath': install_dir, 'version': '0.5.0'}]},
        }))
        self.assertEqual(agents.local_plugin_status('claude'), (True, '0.5.0', 'plugin'))

        self.write('.claude/settings.json', json.dumps({'enabledPlugins': {'ezyplatform@cppai': False}}))
        self.assertEqual(agents.local_plugin_status('claude'), (False, '0.5.0', 'disabled'))

        self.write('.claude/settings.json', json.dumps({'enabledPlugins': {'ezyplatform@cppai': True}}))
        self.write('.claude/plugins/installed_plugins.json', json.dumps({'version': 2, 'plugins': {}}))
        self.assertEqual(agents.local_plugin_status('claude'), (False, None, 'local'))

    def test_codex_local_enabled_disabled_and_cli_uses_marketplace_filter(self):
        self.assertIn('--marketplace', agents.AGENTS['codex']['list'])
        self.assertIn(agents.MARKETPLACE, agents.AGENTS['codex']['list'])

        self.write('.codex/config.toml', '[plugins."ezyplatform@cppai"]\nenabled = true\n')
        # Without cache directory, local check defers to CLI (None) rather than guessing.
        self.assertEqual(agents.local_plugin_status('codex'), (None, None, None))

        self.write('.codex/plugins/cache/cppai/ezyplatform/0.5.0/README.md', 'ok')
        self.assertEqual(agents.local_plugin_status('codex'), (True, '0.5.0', 'plugin'))

        self.write('.codex/config.toml', '[plugins."ezyplatform@cppai"]\nenabled = false\n')
        self.assertEqual(agents.local_plugin_status('codex'), (False, '0.5.0', 'local'))

        self.write('.codex/config.toml', '[plugins."other@openai"]\nenabled = true\n')
        self.assertEqual(agents.local_plugin_status('codex'), (False, '0.5.0', 'local'))

    def test_omp_local_installed_and_not_installed(self):
        install_dir = os.path.join(self.home, '.omp', 'plugins', 'cache', 'cppai___ezyplatform___0.5.0')
        os.makedirs(install_dir)
        self.write('.omp/plugins/installed_plugins.json', json.dumps({
            'version': 2,
            'plugins': {'ezyplatform@cppai': [{'installPath': install_dir, 'version': '0.5.0'}]},
        }))
        self.assertEqual(agents.local_plugin_status('omp'), (True, '0.5.0', 'plugin'))

        self.write('.omp/plugins/installed_plugins.json', json.dumps({'version': 2, 'plugins': {}}))
        self.assertEqual(agents.local_plugin_status('omp'), (False, None, 'local'))

    def test_cursor_local_plugin_skills_and_not_installed(self):
        os.makedirs(os.path.join(self.home, '.cursor'))
        self.assertEqual(agents.local_plugin_status('cursor'), (False, None, 'local'))

        self.write('.cursor/skills/ezy-guide/SKILL.md', '# guide')
        self.assertEqual(agents.local_plugin_status('cursor'), (True, None, 'skills'))

        self.write('.cursor/plugins/cache/cppai/ezyplatform/abc123/README.md', 'plugin')
        self.assertEqual(agents.local_plugin_status('cursor'), (True, None, 'plugin'))


class DiagnosticProbeTest(unittest.TestCase):
    def setUp(self):
        for patch in (
            mock.patch.object(agents, 'detected', side_effect=lambda n: n in ('claude', 'codex')),
            mock.patch.object(agents, 'STATUS_TIMEOUT', 1),
            mock.patch.object(self_update, 'latest_version', return_value=self_update.__version__),
            mock.patch.object(skills_install, 'copies', return_value=[]),
            mock.patch.object(skills_install, 'target_status_rows', return_value=[]),
            mock.patch.object(doctor, 'project_root', return_value=None),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.agent('claude', 'print(\'[ {"id": "ezyplatform@cppai"} ]\')')
        self.agent('codex', 'print(\'[ {"id": "ezyplatform@cppai"} ]\')')

    def agent(self, name, source):
        config = dict(agents.AGENTS[name], list=[sys.executable, '-c', source])
        patch = mock.patch.dict(agents.AGENTS, {name: config})
        patch.start()
        self.addCleanup(patch.stop)

    def test_stalled_agent_is_unknown_and_other_agents_still_checked(self):
        self.agent('claude', 'import time; time.sleep(2); print("[]")')
        for command in [('plugins', 'status', '--target', 'claude,codex'), ('doctor',)]:
            with self.subTest(command=command):
                code, out = run(*command)
                self.assertIn('plugin list could not be read', out)
                self.assertIn('Codex                ezyplatform@cppai installed', out)
                self.assertNotIn('plugin not installed', out)
                self.assertIn(code, (0, 1))
                if command == ('doctor',):
                    self.assertIn('Skill copies', out)
                    self.assertEqual(code, 1)
                    self.assertIn('could not check plugins for claude', out)
                    self.assertNotIn('All good.', out)

    def test_parallel_cli_probes_overlap(self):
        self.agent('claude', 'import time; time.sleep(0.4); print(\'[{"id":"ezyplatform@cppai"}]\')')
        self.agent('codex', 'import time; time.sleep(0.4); print(\'[{"id":"ezyplatform@cppai"}]\')')
        t0 = time.monotonic()
        rows = agents.status_rows(['claude', 'codex'])
        elapsed = time.monotonic() - t0
        self.assertEqual([r[3] for r in rows], [True, True])
        self.assertLess(elapsed, 0.75, f'expected parallel execution, took {elapsed:.2f}s')

    def test_probe_warnings_do_not_break_successful_json(self):
        self.agent('claude', 'import sys; print("warning", file=sys.stderr); print(\'[{"id":"ezyplatform@cppai"}]\')')
        self.assertTrue(agents.plugin_installed('claude'))

    def test_guard_probes_use_check_budget_and_mutations_keep_their_budget(self):
        with mock.patch.object(agents, 'run', return_value=(0, '[]')) as runner:
            agents.plugin_installed('claude')
            self.assertEqual(runner.call_args.kwargs['timeout'], agents.STATUS_TIMEOUT)
            self.assertTrue(runner.call_args.kwargs.get('non_interactive'))
        with mock.patch.object(agents, 'run', return_value=(0, '')) as runner, \
                contextlib.redirect_stdout(io.StringIO()):
            agents.update('codex')
            self.assertNotIn('timeout', runner.call_args.kwargs)
            self.assertNotIn('non_interactive', runner.call_args.kwargs)

    @unittest.skipIf(os.name == 'nt', 'POSIX process-group cleanup for the pre-fix reproducer')
    def test_plugin_query_does_not_wait_for_callers_open_stdin(self):
        query = 'import sys; sys.stdin.read(); print(\'[{"id":"ezyplatform@cppai"}]\')'
        source = f'''
import sys
from ezyplatform_cli import agents
agents.AGENTS['claude']['list'] = [sys.executable, '-c', {query!r}]
assert agents.plugin_installed('claude') is True
'''
        proc = subprocess.Popen([sys.executable, '-c', source], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        try:
            proc.wait(timeout=3)
            out, err = proc.communicate()
            self.assertEqual(proc.returncode, 0, err.decode())
        except subprocess.TimeoutExpired:
            self.fail('plugin query waited for the caller to close stdin')
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.communicate()

    def test_timeout_stops_probe_descendants(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = os.path.join(folder, 'child-finished')
            child = (f'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); '
                     f'time.sleep(1.4); open({marker!r}, "w").close()')
            self.agent('claude', f'import subprocess, sys, time; subprocess.Popen([sys.executable, "-c", {child!r}]); time.sleep(2); print("[]")')
            rows = agents.status_rows(['claude'])
            time.sleep(1.5)
            self.assertIsNone(rows[0][3])
            self.assertFalse(os.path.exists(marker), 'timed-out probe left a child running')


class SkillAgentsScanTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = os.path.join(tmp.name, 'home')
        self.bin = os.path.join(tmp.name, 'bin')
        os.makedirs(self.home)
        os.makedirs(self.bin)
        env = mock.patch.dict(os.environ, {
            'HOME': self.home,
            'XDG_CONFIG_HOME': os.path.join(self.home, '.config'),
            'PATH': self.bin + os.pathsep + '/usr/bin:/bin',
        })
        env.start()
        self.addCleanup(env.stop)

    def make_bin(self, name):
        path = os.path.join(self.bin, name)
        with open(path, 'w') as fh:
            fh.write('#!/bin/sh\nexit 0\n')
        os.chmod(path, 0o755)

    def test_antigravity_and_gemini_share_one_deduplicated_skill_dir(self):
        self.make_bin('agy')
        self.make_bin('gemini')
        dests = skills_install.default_dests()
        self.assertEqual(dests, [skills_install.expand('~/.gemini/skills')])

        code, out = run('skills', 'install')
        self.assertEqual(code, 0, out)
        rows = {r[0]: r for r in skills_install.target_status_rows()}
        self.assertTrue(rows['antigravity'][2])
        self.assertEqual(rows['antigravity'][4], 'ok')
        self.assertTrue(rows['gemini'][2])
        self.assertEqual(rows['gemini'][4], 'ok')


if __name__ == '__main__':
    unittest.main()
