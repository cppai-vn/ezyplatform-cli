"""Status presentation must stay readable in terminals, pipes and legacy consoles."""
import contextlib
import io
import os
import unittest
from unittest import mock

from ezyplatform_cli import agents, doctor, self_update, skills_install
from ezyplatform_cli.status_output import print_status
from test_cli import run


class Terminal(io.StringIO):
    def isatty(self):
        return True


class StatusOutputTest(unittest.TestCase):
    def test_terminal_colors_only_the_result_marker(self):
        output = Terminal()
        with mock.patch.dict(os.environ, {'TERM': 'xterm', 'NO_COLOR': ''}), \
                mock.patch('ezyplatform_cli.status_output.os.name', 'posix'):
            print_status('ready', True, file=output)
            print_status('failed', False, file=output)
            print_status('check manually', file=output)
        self.assertEqual(output.getvalue(), '\033[32m✓\033[0m ready\n\033[31m✗\033[0m failed\n? check manually\n')

    def test_redirected_output_and_color_opt_out_keep_plain_markers(self):
        for output, env in [(io.StringIO(), {}), (Terminal(), {'NO_COLOR': '1'}),
                            (Terminal(), {'TERM': 'dumb'})]:
            with self.subTest(env=env), mock.patch.dict(os.environ, env):
                print_status('ready', True, file=output)
                print_status('failed', False, file=output)
                self.assertEqual(output.getvalue(), '✓ ready\n✗ failed\n')

    def test_ascii_stream_uses_legible_fallback(self):
        raw = io.BytesIO()
        output = io.TextIOWrapper(raw, encoding='ascii')
        print_status('ready', True, file=output)
        print_status('failed', False, file=output)
        self.assertEqual(raw.getvalue(), b'[OK] ready\n[X] failed\n')

    def test_stderr_uses_its_own_color_capability(self):
        output, errors = Terminal(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            print_status('failed', False, file=errors)
        self.assertEqual(errors.getvalue(), '✗ failed\n')
        self.assertEqual(output.getvalue(), '')

    def test_plugin_states_distinguish_installed_missing_unknown_and_manual(self):
        rows = [('claude', 'installed', True, True), ('codex', 'missing plugin', True, False),
                ('omp', 'failed query', True, None), ('copilot', 'missing agent', False, None),
                ('cursor', 'manual', True, None)]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            agents.print_status(rows=rows)
        lines = output.getvalue().splitlines()
        self.assertEqual([line[0] for line in lines], ['✓', '✗', '✗', '✗', '?'])
        self.assertIn('plugin list could not be read', lines[2])

    def test_skill_status_marks_valid_and_modified_copies(self):
        with mock.patch.object(skills_install, 'copies', return_value=[('/valid', 'ok'), ('/edited', 'modified (1 files)')]):
            code, output = run('skills', 'status')
        self.assertEqual(code, 1)
        self.assertEqual([line[0] for line in output.splitlines()], ['✓', '✗'])

    def test_doctor_summary_and_failed_release_have_result_markers(self):
        with mock.patch.object(agents, 'status_rows', return_value=[('claude', 'Claude Code', True, True)]), \
                mock.patch.object(skills_install, 'copies', return_value=[]), \
                mock.patch.dict(skills_install.TARGETS, {}, clear=True), \
                mock.patch.dict(skills_install.READS, {}, clear=True), \
                mock.patch.object(doctor, 'project_root', return_value=None), \
                mock.patch.object(self_update, 'latest_version', side_effect=OSError('offline')):
            code, output = run('doctor')
        self.assertEqual(code, 0)  # Optional update lookup keeps the existing exit contract.
        self.assertIn(f'✗ version   {self_update.__version__}  (could not check for updates)', output)
        self.assertIn('✓ All good.', output)
        self.assertNotIn('\033[', output)


if __name__ == '__main__':
    unittest.main()
