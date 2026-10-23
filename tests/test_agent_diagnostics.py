"""Diagnostic waits against real, controlled child processes; no installed agents."""
import contextlib
import io
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


class DiagnosticTest(unittest.TestCase):
    def setUp(self):
        for patch in (
            mock.patch.object(agents, 'detected', side_effect=lambda n: n in ('claude', 'codex')),
            mock.patch.object(agents, 'STATUS_TIMEOUT', 1),
            mock.patch.object(self_update, 'latest_version', return_value=self_update.__version__),
            mock.patch.object(skills_install, 'copies', return_value=[]),
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

    def test_only_completed_results_are_printed_and_flushed_before_next_probe(self):
        class Output(io.StringIO):
            flushed = ''

            def flush(self):
                self.flushed = self.getvalue()

        output = Output()
        original = agents.plugin_installed

        def inspect(name, **kwargs):
            self.assertNotIn('Checking ', output.getvalue())
            if name == 'codex':
                self.assertIn('Claude Code          ezyplatform@cppai installed', output.flushed)
            return original(name, **kwargs)

        with contextlib.redirect_stdout(output), mock.patch.object(agents, 'plugin_installed', side_effect=inspect):
            agents.main(['status', '--target', 'claude,codex'])
        self.assertNotIn('Checking ', output.getvalue())
        self.assertEqual(len(output.getvalue().splitlines()), 2)

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

    def test_doctor_release_failure_does_not_block_other_diagnostics(self):
        with mock.patch.object(self_update, 'latest_version', side_effect=OSError('offline')) as latest:
            code, out = run('doctor')
        self.assertIn('could not check for updates', out)
        self.assertNotIn('Checking ', out)
        self.assertIn('Skill copies', out)
        self.assertEqual(latest.call_args.kwargs.get('timeout'), 10)

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
            # wait(), unlike communicate(), keeps our input pipe open.
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


class ReleaseTimeoutTest(unittest.TestCase):
    def test_release_fallback_uses_requested_timeout(self):
        with mock.patch.object(self_update.urllib.request, 'urlopen', side_effect=OSError('offline')) as request:
            with self.assertRaises(OSError):
                self_update.latest_version(timeout=10)
        self.assertEqual(len(request.call_args_list), 2)
        self.assertTrue(all(call.kwargs['timeout'] == 10 for call in request.call_args_list))

    def test_release_checks_default_to_ten_seconds(self):
        with mock.patch.object(self_update.urllib.request, 'urlopen', side_effect=OSError('offline')) as request:
            with self.assertRaises(OSError):
                self_update.latest_version()
        self.assertTrue(all(call.kwargs['timeout'] == 10 for call in request.call_args_list))

    def test_plugin_and_marketplace_checks_default_to_ten_seconds(self):
        with mock.patch.object(agents, 'detected', return_value=True), \
                mock.patch.object(agents, 'run', return_value=(0, '[]')) as runner, \
                contextlib.redirect_stdout(io.StringIO()):
            agents.install('claude', dry_run=True)
        self.assertEqual([call.args[0] for call in runner.call_args_list],
                         [agents.AGENTS['claude']['list'], agents.AGENTS['claude']['marketplaces']])
        self.assertTrue(all(call.kwargs['timeout'] == 10 for call in runner.call_args_list))


if __name__ == '__main__':
    unittest.main()
