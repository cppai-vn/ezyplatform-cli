"""ezy init / plugins / skills / doctor / update --refresh against fake agent CLIs.

Each fake agent is a small shell script on PATH that records its arguments and
keeps "marketplace added" / "plugin installed" as files, so the real agents on
the machine are never touched. HOME points at a temporary folder.
"""
import json
import os
import stat
import tempfile
import unittest
from unittest import mock

from test_cli import run

FAKE_AGENT = r'''#!/bin/sh
name=$(basename "$0")
echo "$name $*" >> "$FAKE_DIR/log"
case "$*" in
  *"marketplace list"*) [ -f "$FAKE_DIR/$name.mp" ] && echo cppai; exit 0 ;;
  *"marketplace add"*) touch "$FAKE_DIR/$name.mp"; exit 0 ;;
  *"plugin list"*) if [ -f "$FAKE_DIR/$name.installed" ]; then echo '[{"id": "ezyplatform@cppai"}]'; else echo '[]'; fi; exit 0 ;;
  *"plugin install"*|*"plugin add"*) touch "$FAKE_DIR/$name.installed"; exit 0 ;;
esac
exit 0
'''


def read_json(path):
    with open(path) as fh:
        return json.load(fh)


@unittest.skipIf(os.name == 'nt', 'fake agents are shell scripts')
class SetupTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = os.path.join(tmp.name, 'home')
        self.bin = os.path.join(tmp.name, 'bin')
        os.makedirs(self.home)
        os.makedirs(self.bin)
        env = mock.patch.dict(os.environ, {'HOME': self.home, 'XDG_CONFIG_HOME': os.path.join(self.home, '.config'),
                                           'PATH': self.bin + os.pathsep + '/usr/bin:/bin', 'FAKE_DIR': self.bin})
        env.start()
        self.addCleanup(env.stop)
        from ezyplatform_cli import self_update
        latest = mock.patch.object(self_update, 'latest_version', return_value=self_update.__version__)
        latest.start()
        self.addCleanup(latest.stop)

    def agent(self, *names):
        for name in names:
            path = os.path.join(self.bin, name)
            with open(path, 'w') as fh:
                fh.write(FAKE_AGENT)
            os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def log(self):
        path = os.path.join(self.bin, 'log')
        if not os.path.exists(path):
            return ''
        with open(path) as fh:
            return fh.read()

    def skills_dir(self, *parts):
        return os.path.join(self.home, *parts)

    def test_plugins_install_adds_marketplace_once(self):
        self.agent('claude', 'codex')
        code, out = run('plugins', 'install', '--target', 'claude,codex')
        self.assertEqual(code, 0, out)
        log = self.log()
        self.assertIn('claude plugin marketplace add cppai-vn/agents-plugins', log)
        self.assertIn('claude plugin install ezyplatform@cppai', log)
        self.assertIn('codex plugin add ezyplatform@cppai', log)
        code, out = run('plugins', 'install', '--target', 'claude')
        self.assertIn('already installed', out)
        self.assertEqual(self.log().count('claude plugin install'), 1)

    def test_init_installs_plugin_and_skill_copy_then_doctor_is_clean(self):
        self.agent('claude', 'opencode')
        code, out = run('init', '--yes')
        self.assertEqual(code, 0, out)
        self.assertIn('claude plugin install ezyplatform@cppai', self.log())
        copy = self.skills_dir('.config', 'opencode', 'skills')
        self.assertTrue(os.path.isfile(os.path.join(copy, 'ezy-guide', 'SKILL.md')))
        self.assertIn('All good.', out)
        code, out = run('skills', 'verify')
        self.assertEqual(code, 0, out)
        self.assertIn('ok', out)

    def test_skill_copy_where_a_plugin_loads_is_refused_and_doctor_flags_force(self):
        self.agent('claude')
        run('plugins', 'install', '--target', 'claude')
        claude_skills = self.skills_dir('.claude', 'skills')
        code, out = run('skills', 'install', '--dir', claude_skills)
        self.assertEqual(code, 1)
        self.assertIn('would appear twice', out)
        self.assertTrue(out.startswith('✗ '), out)
        self.assertFalse(os.path.exists(os.path.join(claude_skills, 'ezy-guide')))
        run('skills', 'install', '--dir', claude_skills, '--force')
        code, out = run('doctor')
        self.assertEqual(code, 1)
        self.assertIn('skills loaded twice', out)
        code, out = run('skills', 'remove', '--dir', claude_skills)
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith('✓ '), out)
        self.assertFalse(os.path.exists(os.path.join(claude_skills, 'ezy-guide')))

    def test_users_own_ezy_skill_survives_remove_and_refresh(self):
        dest = self.skills_dir('my-agent', 'skills')
        own = os.path.join(dest, 'ezy-mycompany')
        os.makedirs(own)
        with open(os.path.join(own, 'SKILL.md'), 'w') as fh:
            fh.write('mine')
        run('skills', 'install', '--dir', dest)
        run('update', '--refresh')
        self.assertTrue(os.path.isfile(os.path.join(own, 'SKILL.md')))
        run('skills', 'remove', '--dir', dest)
        self.assertTrue(os.path.isfile(os.path.join(own, 'SKILL.md')))
        self.assertFalse(os.path.exists(os.path.join(dest, 'ezy-guide')))

    def test_codex_available_plugin_is_not_installed(self):
        from ezyplatform_cli import agents
        listing = '{"installed": [{"pluginId": "pdf@openai"}], "available": [{"pluginId": "ezyplatform@cppai"}]}'
        with mock.patch.object(agents, 'detected', return_value=True), \
                mock.patch.object(agents, 'run', return_value=(0, listing)):
            self.assertFalse(agents.plugin_installed('codex'))
        with mock.patch.object(agents, 'detected', return_value=True), \
                mock.patch.object(agents, 'run', return_value=(0, '[{"name": "ezyplatform", "marketplace": "other"}]')):
            self.assertFalse(agents.plugin_installed('omp'))

    def test_windows_batch_line_quotes_every_argument(self):
        from ezyplatform_cli import self_update
        line = self_update.cmd_line(['C:\\Users\\John Doe\\uv.exe', '--python', '>=3.9', 'https://x/a%b.whl'])
        self.assertEqual(line, '"C:\\Users\\John Doe\\uv.exe" "--python" ">=3.9" "https://x/a%%b.whl"')

    def test_verify_reports_modified_copy(self):
        dest = self.skills_dir('my-agent', 'skills')
        run('skills', 'install', '--dir', dest)
        with open(os.path.join(dest, 'ezy-guide', 'SKILL.md'), 'a') as fh:
            fh.write('\nlocal edit\n')
        code, out = run('skills', 'verify', '--dir', dest)
        self.assertEqual(code, 1)
        self.assertIn('modified (1 files)', out)

    def test_refresh_updates_plugins_and_outdated_copies(self):
        self.agent('claude')
        run('plugins', 'install', '--target', 'claude')
        dest = self.skills_dir('my-agent', 'skills')
        run('skills', 'install', '--dir', dest)
        manifest = os.path.join(dest, 'ezy-shared', '.ezy-install.json')
        data = read_json(manifest)
        data['version'] = '0.0.1'
        with open(manifest, 'w') as fh:
            json.dump(data, fh)
        code, out = run('update', '--refresh')
        self.assertEqual(code, 0, out)
        self.assertIn('claude plugin update ezyplatform@cppai', self.log())
        self.assertIn('claude plugin marketplace update cppai', self.log())
        from ezyplatform_cli import skills_install
        self.assertEqual(read_json(manifest)['version'], skills_install.bundled_info()['version'])


if __name__ == '__main__':
    unittest.main()
