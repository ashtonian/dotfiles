import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('desktop', str(ROOT / 'bin/configure-desktop'))
desktop = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(desktop)


class Desktop(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.apps = root / 'Applications'
        self.settings = root / 'System/Applications/System Settings.app'
        self.settings.mkdir(parents=True)
        self.apps.mkdir()
        self.enterContext(patch.multiple(desktop, HOME=root, APPS=self.apps, SYSTEM_APPS=self.settings.parent))
        self.enterContext(patch.object(desktop.shutil, 'which', return_value='dockutil'))
        self.run = self.enterContext(patch.object(desktop.subprocess, 'run', autospec=True))
        self.run.return_value = subprocess.CompletedProcess([], 0, stdout=b'saved dock')

    def test_only_installed_tiles_and_one_user_restart(self):
        desktop.dock()
        calls = [list(c.args[0]) for c in self.run.call_args_list]
        edits = [c for c in calls if c[0] == 'dockutil']
        self.assertTrue(all('--allhomes' not in c and '--no-restart' in c for c in edits))
        self.assertEqual(edits[0][1:3], ['--remove', 'all'])
        self.assertEqual([c[2] for c in edits[1:]], [self.settings, desktop.HOME, self.apps])
        restarts = [c for c in calls if c[0] == 'killall']
        self.assertEqual(restarts, [calls[-1]])
        self.assertEqual(restarts[0][1], '-u')

    def test_failed_dock_edit_restores_original_preferences(self):
        self.run.side_effect = [self.run.return_value, self.run.return_value,
                                subprocess.CalledProcessError(1, 'dockutil'), self.run.return_value]
        with self.assertRaises(subprocess.CalledProcessError):
            desktop.dock()
        self.run.assert_called_with(('defaults', 'import', 'com.apple.dock', '-'),
                                    check=True, input=b'saved dock')

    def test_only_associate_installed_apps(self):
        (self.apps / 'IINA.app').mkdir()
        desktop.associations()
        args = [c.args[0] for c in self.run.call_args_list]
        self.assertIn(('duti', '-s', 'com.colliderli.iina', '.mkv', 'all'), args)
        self.assertTrue(all(c[2] == 'com.colliderli.iina' for c in args))

        (self.apps / 'Visual Studio Code.app').mkdir()
        desktop.associations()
        self.run.assert_any_call(('duti', '-s', 'com.microsoft.VSCode', '.json', 'all'), check=True)

    def test_rejected_file_type_does_not_skip_remaining_types(self):
        (self.apps / 'IINA.app').mkdir()
        def reject_mkv(args, **kwargs):
            if '.mkv' in args:
                raise subprocess.CalledProcessError(1, args)
        self.run.side_effect = reject_mkv
        with self.assertRaisesRegex(RuntimeError, r'\.mkv'):
            desktop.associations()
        self.run.assert_any_call(('duti', '-s', 'com.colliderli.iina', '.mp4', 'all'), check=True)


class GitShortcuts(unittest.TestCase):
    def test_https_fetch_and_ssh_push(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, HOME=tmp, XDG_CONFIG_HOME=tmp, GIT_CONFIG_NOSYSTEM='1',
                       GIT_CONFIG_GLOBAL=str(ROOT / 'features/git/home/.config/git/config'))
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=tmp, env=env, text=True).strip()
            git('init', '-q')
            for alias, host in [('github', 'github.com'), ('gist', 'gist.github.com')]:
                git('remote', 'add', alias, alias + ':example/repo')
                self.assertEqual(git('remote', 'get-url', alias), f'https://{host}/example/repo')
                self.assertEqual(git('remote', 'get-url', '--push', alias), f'git@{host}:example/repo')
