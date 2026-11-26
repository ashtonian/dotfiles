import json
import os
import plistlib
import re
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / 'features'
ZSH_DIR = FEATURES / 'shell.zsh/home/.config/zsh'


def install_shell(home, stubs):
    """The shell.env and shell.zsh features as `dotfiles apply` installs them:
    a link per tracked file, and the named entry-point stubs with the lines
    their manifests declare."""
    for feature in ('shell.env', 'shell.zsh'):
        root = FEATURES / feature / 'home'
        for source in root.rglob('*'):
            if source.is_file():
                target = home / source.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(source)
        manifest = tomllib.loads((FEATURES / feature / 'feature.toml').read_text())
        for stub in manifest['provides'].get('stub', []):
            if stub['path'] in stubs:
                (home / stub['path']).write_text(stub['line'] + '\n')


def cached_eval_helper():
    """_dotfiles_cached_eval exactly as 00-init.zsh defines it, without zinit."""
    source = (ZSH_DIR / '00-init.zsh').read_text()
    helper = source[source.index('_dotfiles_cached_eval() {'):]
    return helper[:helper.index('\n}\n') + 3]


# launchctl for tests: print, bootstrap, bootout, kickstart and list against
# $DOTFILES_TEST_LAUNCHD, with launchctl's exit statuses; every call is recorded.
LAUNCHCTL_STUB = r'''dir=${DOTFILES_TEST_LAUNCHD:?}
printf '%s\n' "$*" >> "$dir/.audit"
case $1 in
print) job=$dir/${2##*/}; [ -f "$job" ] || { echo "Could not find service" >&2; exit 113; }
       state="not running"; [ ! -e "$job.running" ] || state=running
       printf '%s = {\n\tstate = %s\n}\n' "$2" "$state" ;;
bootstrap) job=$dir/$(basename "$3" .plist)
       [ ! -f "$job" ] || { echo "Bootstrap failed: 5: Input/output error" >&2; exit 5; }; cp "$3" "$job" ;;
bootout) job=$dir/${2##*/}; [ -f "$job" ] || { echo "Boot-out failed: 3: No such process" >&2; exit 3; }; rm "$job" ;;
kickstart) [ -f "$dir/${3##*/}" ] || exit 113 ;;
list) [ -f "$dir/$2" ] || exit 113; [ ! -e "$dir/$2.running" ] || echo '{ "PID" = 42; }' ;;
esac'''


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dotfiles-test-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.bin = self.path / 'bin'
        self.bin.mkdir()
        self.env = os.environ.copy()
        self.env.update(DOTFILES=str(ROOT), DOTFILES_DIR=str(self.path),
                        SYNC_DIR=str(self.path / 'sync'),
                        AWS_SHARED_CREDENTIALS_FILE=str(self.path / 'credentials'),
                        AWS_CONFIG_FILE=str(self.path / 'config'),
                        PATH=str(self.bin) + os.pathsep + self.env['PATH'],
                        XDG_CACHE_HOME=str(self.path / 'cache'),
                        XDG_CONFIG_HOME=str(self.path / 'config'),
                        TMPDIR=str(self.path),
                        PYTHONDONTWRITEBYTECODE='1')
        # No test reaches the real sudo; one that needs root to be available stubs it again.
        self.cli('sudo', 'exit 1')
        # Nor the real launchd: a GUI domain kept as one file per loaded label,
        # holding the plist it was bootstrapped from. The engine and the scripts
        # both run this one.
        self.launchd = self.path / 'launchd'
        self.launchd.mkdir()
        self.cli('launchctl', LAUNCHCTL_STUB)
        self.env.update(DOTFILES_LAUNCHCTL=str(self.bin / 'launchctl'), DOTFILES_TEST_LAUNCHD=str(self.launchd))
        self.env.pop('XPC_SERVICE_NAME', None)

    def launchctl_calls(self):
        audit = self.launchd / '.audit'
        return audit.read_text().splitlines() if audit.exists() else []

    def loaded(self, label, running=False):
        """launchd has LABEL loaded, as a run of dotfiles apply left it."""
        (self.launchd / label).write_text('plist')
        if running:
            (self.launchd / f'{label}.running').touch()

    def stub_engine(self, loads=(), unloads=()):
        """DOTFILES_BIN that records its arguments and, as apply would, loads
        LOADS and unloads UNLOADS in the stub launchd."""
        audit = self.path / 'engine-audit'
        code = f'printf "%s\\n" "$*" >> {audit}\n'
        code += ''.join(f'printf plist > "$DOTFILES_TEST_LAUNCHD/{label}"\n' for label in loads)
        code += ''.join(f'rm -f "$DOTFILES_TEST_LAUNCHD/{label}"\n' for label in unloads)
        self.cli('dotfiles', code)
        self.env['DOTFILES_BIN'] = str(self.bin / 'dotfiles')
        return lambda: audit.read_text().splitlines() if audit.exists() else []

    def cli(self, name, code):
        file = self.bin / name
        file.write_text('#!/bin/sh\n' + code + '\n')
        file.chmod(0o755)

    def zsh(self, code, *args, input=None):
        return subprocess.run(['/bin/zsh', '-fc', 'source "$1"; shift; ' + code,
                               'test', str(ROOT / 'lib_sh/funcs.sh'), *args],
                              cwd=self.path, env=self.env, input=input,
                              capture_output=True, text=True, timeout=20)

    def bash(self, code, *args, source='sync.sh', timeout=20):
        return subprocess.run(['/bin/bash', '-c', 'source "$1"; shift; ' + code,
                               'test', str(ROOT / source), *args],
                              cwd=self.path, env=self.env, capture_output=True,
                              text=True, timeout=timeout)


class Credentials(Fixture):
    def setUp(self):
        super().setUp()
        self.credentials = Path(self.env['AWS_SHARED_CREDENTIALS_FILE'])
        self.config = Path(self.env['AWS_CONFIG_FILE'])
        self.credentials.write_text('[other]\naws_access_key_id = EXAMPLE_OLD\n')
        self.credentials.chmod(0o600)
        self.env['DOTFILES_TEST_AWS'] = json.dumps({'Credentials': {
            'AccessKeyId': 'EXAMPLE_ACCESS', 'SecretAccessKey': 'EXAMPLE_SECRET',
            'SessionToken': 'EXAMPLE_TOKEN', 'Expiration': 'EXAMPLE_EXPIRATION'}})
        self.cli('aws', 'printf "%s\\n" "$DOTFILES_TEST_AWS"\nexit "${DOTFILES_TEST_AWS_EXIT:-0}"')

    def test_assume_preserves_other_profiles_and_private_mode(self):
        p = self.zsh('assume_role example-role example-session "review.prod"')
        self.assertEqual(p.returncode, 0, p.stderr)
        data = self.credentials.read_text()
        self.assertIn('[other]', data)
        self.assertIn('[review.prod]', data)
        self.assertEqual(stat.S_IMODE(self.credentials.stat().st_mode), 0o600)
        for value in ('EXAMPLE_ACCESS', 'EXAMPLE_SECRET', 'EXAMPLE_TOKEN'):
            self.assertNotIn(value, p.stdout + p.stderr)
        self.assertEqual([p.name for p in self.path.glob('.credentials.*') if p.name != '.credentials.lock'], [])

    def test_invalid_response_and_failed_aws_leave_file_unchanged(self):
        original = self.credentials.read_bytes()
        for response in ('{}', 'not json', '{"Credentials":null}',
                         '{"Credentials":{"AccessKeyId":"null"}}'):
            with self.subTest(response=response):
                self.env['DOTFILES_TEST_AWS'] = response
                p = self.zsh('assume_role role session review')
                self.assertNotEqual(p.returncode, 0)
                self.assertEqual(self.credentials.read_bytes(), original)
        self.env['DOTFILES_TEST_AWS_EXIT'] = '7'
        p = self.zsh('assume_role role session review')
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(self.credentials.read_bytes(), original)

    def test_concurrent_updates_keep_both_profiles(self):
        children = []
        for name in ('first', 'second'):
            children.append(subprocess.Popen(['/bin/zsh', '-fc',
                'source "$1"; assume_role role session "$2"', 'test',
                str(ROOT / 'lib_sh/funcs.sh'), name], cwd=self.path, env=self.env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        for child in children:
            _, error = child.communicate(timeout=20)
            self.assertEqual(child.returncode, 0, error)
        self.assertIn('[first]', self.credentials.read_text())
        self.assertIn('[second]', self.credentials.read_text())

    def test_symlink_is_preserved(self):
        real = self.path / 'real-credentials'
        self.credentials.rename(real)
        self.credentials.symlink_to(real)
        p = self.zsh('assume_role role session review')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(self.credentials.is_symlink())
        self.assertIn('[review]', real.read_text())
        self.assertEqual(stat.S_IMODE(real.stat().st_mode), 0o600)

    def test_rename_headers_and_default_profile(self):
        self.credentials.write_text('[old]\naws_access_key_id = EXAMPLE\n[other]\nx = keep\n')
        self.config.write_text('[profile old]\nregion = us-east-1\n')
        p = self.zsh('rename_aws_profile old default')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('[default]', self.credentials.read_text())
        self.assertIn('[default]', self.config.read_text())
        self.assertIn('[other]', self.credentials.read_text())
        p = self.zsh('rename_aws_profile default "new.prod"')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('[new.prod]', self.credentials.read_text())
        self.assertIn('[profile new.prod]', self.config.read_text())
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)

    def test_rename_rejects_collisions_before_writing(self):
        self.config.write_text('[profile target]\nregion = us-east-1\n')
        before = (self.credentials.read_bytes(), self.config.read_bytes())
        p = self.zsh('rename_aws_profile other target')
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual((self.credentials.read_bytes(), self.config.read_bytes()), before)

    def test_rename_profile_present_in_only_one_file(self):
        p = self.zsh('rename_aws_profile other renamed')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('[renamed]', self.credentials.read_text())
        self.assertFalse(self.config.exists())

    def test_existing_section_without_final_newline_is_replaced(self):
        self.credentials.write_text('[review]')
        p = self.zsh('assume_role role session review')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.credentials.read_text().count('[review]'), 1)


class Helpers(Fixture):
    def test_public_ssh_key_survives_upload_and_auth_failures(self):
        key = self.path / 'fixture.pub'
        key.write_text('ssh-ed25519 EXAMPLE fixture\n')
        for failure in ('', 'auth', 'upload'):
            self.env['DOTFILES_TEST_GH_FAILURE'] = failure
            self.cli('gh', 'case "$1" in auth) [ "$DOTFILES_TEST_GH_FAILURE" != auth ];; ssh-key) [ "$DOTFILES_TEST_GH_FAILURE" != upload ];; esac')
            p = self.zsh('upload_github_ssh_key -y --dir "$1"', str(self.path))
            self.assertEqual(p.returncode == 0, not failure, p.stderr)
            self.assertTrue(key.exists())

    def test_exporters_restore_stdout(self):
        self.cli('code', 'printf "publisher.extension\\n"')
        self.cli('curl', 'printf \'{"displayName":"Fixture","shortDescription":"Example"}\\n\'')
        self.cli('brew', 'exit 0')
        self.cli('mas', 'printf "123 Example App\\n"')
        self.cli('ls', 'printf "__dotfiles_missing_fixture__\\n"')
        for name in ('vscode_list_md', 'brew_list_md', 'mas_list_md', 'chrome_list_ext_md'):
            with self.subTest(name=name):
                p = self.zsh(name + ' -o "export.md"; print STDOUT_RESTORED')
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertIn('STDOUT_RESTORED', p.stdout)
                self.assertNotIn('STDOUT_RESTORED', (self.path / 'export.md').read_text())
        p = self.zsh('vscode_extensions_list')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('publisher.extension', (self.path / 'vscode_extensions_list.md').read_text())

    def test_terraform_rebuild_needs_a_whole_yes(self):
        audit = self.path / 'tf-audit'
        self.env['DOTFILES_TEST_AUDIT'] = str(audit)
        self.cli('terraform', 'printf "%s\\n" "$1" >> "$DOTFILES_TEST_AUDIT"')
        for answer, calls in (('not yet', []), ('no', []), ('yes', ['destroy', 'apply']), ('Y', ['destroy', 'apply'])):
            with self.subTest(answer=answer):
                audit.unlink(missing_ok=True)
                p = self.zsh('tf_destroy_apply', input=answer + '\n')
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(audit.read_text().split() if audit.exists() else [], calls)

    def test_brewfile_selection_and_invalid_inputs(self):
        (self.path / 'Brewfile-one').write_text('brew "one"\n')
        (self.path / 'Brewfile-two').write_text('brew "two"\n')
        audit = self.path / 'brew-audit'
        self.env['DOTFILES_TEST_AUDIT'] = str(audit)
        self.cli('brew', 'for arg do case "$arg" in --file=*) cat "${arg#--file=}" > "$DOTFILES_TEST_AUDIT";; esac; done')
        p = self.zsh('install_brewfiles', input='1-2,2\n')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(audit.read_text().count('brew "one"'), 1)
        self.assertEqual(audit.read_text().count('brew "two"'), 1)
        for selection in ('0', '3', '2-1', '1-x', 'all; touch injected'):
            audit.unlink(missing_ok=True)
            p = self.zsh('install_brewfiles "$1"', selection)
            self.assertNotEqual(p.returncode, 0)
            self.assertFalse(audit.exists())
        self.assertFalse((self.path / 'injected').exists())

    def test_gitnr_stops_when_directory_already_exists(self):
        existing = self.path / 'existing'
        existing.mkdir()
        audit = self.path / 'git-audit'
        self.env['DOTFILES_TEST_AUDIT'] = str(audit)
        self.cli('git', 'printf "%s\\n" "$*" >> "$DOTFILES_TEST_AUDIT"')
        p = self.zsh('gitnr "$1"', str(existing))
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(audit.exists())
        self.assertFalse((self.path / 'README').exists())

    def test_output_helpers_accept_missing_argument_under_nounset(self):
        p = self.bash('set -u; ok; print_success "done"', source='lib_sh/echos.sh')
        self.assertEqual(p.returncode, 0, p.stderr)
        p = subprocess.run(['/bin/zsh', '-fc', 'set -u; source "$1"; ok',
                            'test', str(ROOT / 'lib_sh/echos.sh')], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_quiet_update_executes_commands_and_reports_errors(self):
        audit = self.path / 'brew-audit'
        self.env['DOTFILES_TEST_AUDIT'] = str(audit)
        self.cli('brew', 'printf "%s\\n" "$*" >> "$DOTFILES_TEST_AUDIT"\nprintf "command output\\n"\nexit "${DOTFILES_TEST_BREW_EXIT:-0}"')
        args = ['/bin/bash', str(ROOT / 'bin/dotfiles-update.sh'), '--quiet', '--brew']
        p = subprocess.run(args, env=self.env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, '')
        self.assertIn('upgrade --formula', audit.read_text())
        self.assertIn('upgrade --cask', audit.read_text())
        self.env['DOTFILES_TEST_BREW_EXIT'] = '7'
        p = subprocess.run(args, env=self.env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stdout, '')
        self.assertIn('brew update failed', p.stderr)
        self.assertIn('brew cleanup failed', p.stderr, 'every step runs after a failed one')

    def update_brew_unattended(self, script):
        """`dotfiles-update.sh --quiet --brew` with no terminal, brew answering from script."""
        audit = self.path / 'brew-audit'
        self.env['DOTFILES_TEST_AUDIT'] = str(audit)
        self.cli('brew', 'printf "%s NO_SUDO=%s\\n" "$*" "${HOMEBREW_NO_SUDO:-}" >> "$DOTFILES_TEST_AUDIT"\n' + script)
        p = subprocess.run(['/bin/bash', str(ROOT / 'bin/dotfiles-update.sh'), '--quiet', '--brew'],
                           env=self.env, capture_output=True, text=True, timeout=60, start_new_session=True)
        log = (self.path / 'logs/update.log').read_text()
        return p, audit.read_text().splitlines(), log

    def test_unattended_update_retries_each_item_alone_and_leaves_root_upgrades_for_a_terminal(self):
        p, calls, log = self.update_brew_unattended(r"""case "$*" in
  "upgrade --formula") echo "Error: Your Xcode (26.1.1) is too outdated." >&2; exit 1 ;;
  "outdated --formula --json=v2") echo '{"formulae":[{"name":"ripgrep","pinned":false},{"name":"tap/x/opencode","pinned":false},{"name":"held","pinned":true}],"casks":[]}' ;;
  "upgrade --formula tap/x/opencode") echo "Error: Your Xcode (26.1.1) is too outdated." >&2; exit 1 ;;
  "upgrade --cask") exit 1 ;;
  "outdated --cask --json=v2") echo '{"formulae":[],"casks":[{"name":"wireshark-app"},{"name":"parallels"},{"name":"slack"}]}' ;;
  "upgrade --cask wireshark-app") echo "Error: wireshark-app: The pkg artifact requires sudo, but HOMEBREW_NO_SUDO is set." >&2; exit 1 ;;
  "upgrade --cask parallels") echo "touch: /Applications/Parallels Desktop.app/.homebrew-write-test: Permission denied" >&2; exit 1 ;;
  doctor) echo "Warning: Your Xcode is too outdated." >&2; exit 1 ;;
esac
exit 0""")
        self.assertEqual(p.returncode, 1, p.stderr)
        upgrades = [c for c in calls if c.startswith('upgrade')]
        self.assertEqual(upgrades, ['upgrade --formula NO_SUDO=1', 'upgrade --formula ripgrep NO_SUDO=1',
                                    'upgrade --formula tap/x/opencode NO_SUDO=1', 'upgrade --cask NO_SUDO=1',
                                    'upgrade --cask wireshark-app NO_SUDO=1', 'upgrade --cask parallels NO_SUDO=1',
                                    'upgrade --cask slack NO_SUDO=1'], 'a pinned formula is never retried')
        self.assertIn('cleanup --prune=7 NO_SUDO=1', calls, 'cleanup runs after failed upgrades')
        self.assertIn('ERROR: brew upgrade --formula failed for tap/x/opencode;', log)
        self.assertIn('WARN: Left wireshark-app parallels for a terminal', log)
        self.assertIn('run: brew upgrade --cask wireshark-app parallels', log)
        self.assertNotIn('brew upgrade --cask failed', log, 'needing root is not a failure')
        self.assertIn('WARN: brew doctor reported problems', log)

    def test_unattended_update_with_only_root_upgrades_left_succeeds(self):
        p, calls, log = self.update_brew_unattended(r"""case "$*" in
  "upgrade --cask") exit 1 ;;
  "outdated --cask --json=v2") echo '{"casks":[{"name":"nordvpn"}]}' ;;
  "upgrade --cask nordvpn") echo "Error: nordvpn: The pkg artifact requires sudo, but HOMEBREW_NO_SUDO is set." >&2; exit 1 ;;
esac
exit 0""")
        self.assertEqual(p.returncode, 0, p.stderr + log)
        self.assertIn('WARN: Left nordvpn for a terminal', log)
        self.assertIn('Homebrew update complete', log)

    def test_update_with_passwordless_sudo_lets_homebrew_use_it(self):
        self.cli('sudo', 'exit 0')
        p, calls, log = self.update_brew_unattended('exit 0')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('upgrade --cask NO_SUDO=', calls)
        self.assertNotIn('NO_SUDO=1', '\n'.join(calls))

    def test_every_update_stage_runs_when_an_earlier_one_fails(self):
        home = self.path / 'home'
        (home / '.local/share/zinit/zinit.git').mkdir(parents=True)
        (self.path / '.git').mkdir()
        audit = self.path / 'audit'
        sync = self.path / 'sync.sh'
        sync.write_text('#!/bin/sh\nprintf "sync.sh %s\\n" "$*" >> "$DOTFILES_TEST_AUDIT"\n')
        sync.chmod(0o755)
        self.cli('brew', 'printf "brew %s\\n" "$*" >> "$DOTFILES_TEST_AUDIT"\nexit 1')
        for tool in ('git', 'zsh'):
            self.cli(tool, f'printf "{tool} %s\\n" "$*" >> "$DOTFILES_TEST_AUDIT"')
        self.env.update(HOME=str(home), DOTFILES_TEST_AUDIT=str(audit), XDG_DATA_HOME=str(home / '.local/share'))
        self.env.pop('DOTFILES_MISE_CANARY', None)  # not the canary: the Go stage has nothing to do
        p = subprocess.run(['/bin/bash', str(ROOT / 'bin/dotfiles-update.sh'), '--quiet', '--all'],
                           env=self.env, capture_output=True, text=True, timeout=60, start_new_session=True)
        self.assertEqual(p.returncode, 1, p.stderr)
        steps = audit.read_text()
        self.assertIn('zsh -ic zinit update --all --quiet', steps)
        self.assertIn('sync.sh sync', steps)
        self.assertIn('failed stages: brew\n', p.stderr)

    def test_atuin_keeps_history_keys_after_fzf_loads(self):
        fzf = shutil.which('fzf')
        if not fzf:
            self.skipTest('fzf required')
        self.cli('atuin', "printf \"bindkey -M emacs '^R' atuin-search\\nbindkey -M emacs '^[[A' atuin-up-search\\n\"")
        code = cached_eval_helper() + 'source "$1"; eval "$("$2" --zsh)"; bindkey -M emacs "^R"; bindkey -M emacs "^[[A"'
        p = subprocess.run(['/bin/zsh', '-fc', code, 'test',
                            str(ZSH_DIR / '40-keybindings.zsh'), fzf],
                           env=self.env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('atuin-search', p.stdout)
        self.assertIn('atuin-up-search', p.stdout)

    def test_ssh_local_overrides_win(self):
        local = self.path / 'ssh.local'
        local.write_text('Host dotfiles-fixture\n ControlMaster no\n ControlPath none\n IdentitiesOnly no\n UseKeychain no\n')
        config = (FEATURES / 'ssh/home/.ssh/dotfiles.conf').read_text().replace('Include ~/.orbstack/ssh/config', '')
        config = config.replace('Include config.local', 'Include ' + str(local))
        file = self.path / 'ssh.config'
        file.write_text(config)
        p = subprocess.run(['/usr/bin/ssh', '-G', '-F', str(file), 'dotfiles-fixture'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('controlmaster false', p.stdout.replace('controlmaster no', 'controlmaster false'))
        self.assertIn('identitiesonly no', p.stdout)
        self.assertNotIn('controlpath /', p.stdout)

    def test_bootstrap_creates_no_commit_identity_or_backup_repository(self):
        for name in ('colorls',):
            (self.path / 'sync' / name).mkdir(parents=True)
        self.cli('git', 'printf "%s\\n" "$*" >> "$DOTFILES_TEST_AUDIT"')
        audit = self.path / 'git-audit'
        self.env['DOTFILES_TEST_AUDIT'] = str(audit)
        p = self.bash('SYNC_DIR="$1"; setup_sync_dir', str(self.path / 'sync'), source='install.sh')
        self.assertEqual(p.returncode, 0, p.stderr)
        calls = audit.read_text() if audit.exists() else ''
        for forbidden in ('init', 'commit', 'user.email'):
            self.assertNotIn(forbidden, calls)
        self.assertFalse((self.path / 'sync' / 'mackup').exists())


@unittest.skipUnless(Path('/usr/bin/lockf').exists(), 'macOS lockf required')
class SyncLock(Fixture):
    """The sync lock sync.sh and dotfiles-update.sh share (lib_sh/sync-lock.sh)."""

    def setUp(self):
        super().setUp()
        (self.path / 'logs').mkdir()
        self.audit = self.path / 'audit'
        self.env['DOTFILES_TEST_AUDIT'] = str(self.audit)

    def hold_lock(self):
        """A sync in progress: a process holding the lock until it is killed."""
        p = subprocess.Popen(['/bin/bash', '-c', 'source "$1"; acquire_lock; echo READY; read -r _',
                              'test', str(ROOT / 'sync.sh')], env=self.env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.poll() is None and (p.kill(), p.communicate(timeout=5)))
        self.assertEqual(p.stdout.readline().strip(), 'READY')
        return p

    def update(self, *args, **env):
        return subprocess.run(['/bin/bash', str(ROOT / 'bin/dotfiles-update.sh'), '--quiet', *args],
                              env=dict(self.env, **env), capture_output=True, text=True,
                              timeout=60, start_new_session=True)

    def calls(self):
        return self.audit.read_text().splitlines() if self.audit.exists() else []

    def test_update_waits_for_a_sync_in_progress_then_gives_up_without_updating(self):
        self.cli('brew', 'printf "brew %s\\n" "$*" >> "$DOTFILES_TEST_AUDIT"')
        holder = self.hold_lock()
        p = self.update('--brew', UPDATE_LOCK_WAIT='1')
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn('still held', p.stderr)
        self.assertIn('waiting up to 1s', (self.path / 'logs/update.log').read_text())
        self.assertEqual(self.calls(), [], 'no stage runs without the lock')
        holder.kill()
        holder.communicate(timeout=5)
        p = self.update('--brew')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('brew upgrade --formula', self.calls())

    def test_a_malformed_wait_is_refused(self):
        p = self.update('--brew', UPDATE_LOCK_WAIT='5m')
        self.assertEqual(p.returncode, 1)
        self.assertIn('whole number of seconds', p.stderr)

    def test_no_sync_runs_while_the_update_upgrades_packages(self):
        # Mid-upgrade, brew starts a sync, as the 4-hourly job would.
        self.cli('brew', f'case "$*" in "upgrade --formula") /bin/bash {ROOT / "sync.sh"} check >> "$DOTFILES_TEST_AUDIT" 2>&1 ;; esac')
        p = self.update('--brew')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('Another sync or update is already running', self.audit.read_text())

    def test_the_updates_own_sync_runs_inside_its_lock(self):
        (self.path / '.git').mkdir()
        sync = self.path / 'sync.sh'
        sync.write_text(f'#!/bin/sh\nexec /bin/bash {ROOT / "sync.sh"} check\n')
        sync.chmod(0o755)
        p = self.update('--sync')
        self.assertEqual(p.returncode, 0, p.stderr)
        log = (self.path / 'logs/sync.log').read_text()
        self.assertIn('Sync lock is available', log)
        self.assertNotIn('Another sync', log)

    def test_a_daemon_an_update_stage_starts_does_not_keep_the_lock(self):
        pidfile = self.path / 'daemon.pid'
        # Like a Homebrew service restarted by an upgrade: started by a stage, outliving the run.
        self.cli('brew', f'case "$*" in update) sleep 300 </dev/null >/dev/null 2>&1 & echo $! > {pidfile} ;; esac')
        self.addCleanup(lambda: pidfile.exists() and subprocess.run(['kill', pidfile.read_text().strip()]))
        p = self.update('--brew')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(pidfile.exists(), 'the stage started its daemon')
        q = subprocess.run(['/bin/bash', str(ROOT / 'sync.sh'), 'check'], env=self.env,
                           capture_output=True, text=True, timeout=30)
        self.assertIn('lock is available', q.stdout, 'the daemon must not hold the sync lock')

    def test_an_unrelated_descriptor_9_is_not_taken_for_the_lock(self):
        self.hold_lock()
        p = self.bash('exec 9>/dev/null; sync_lock_take "$1" 0; echo "status $?"',
                      str(self.path / 'logs'), source='lib_sh/sync-lock.sh')
        self.assertIn('status 75', p.stdout, p.stderr)


class Sync(Fixture):
    def setUp(self):
        super().setUp()
        (self.path / 'logs').mkdir()
        # Never the developer's home: its machine.toml and overlays would
        # decide what these runs publish.
        (self.path / 'empty-home').mkdir()
        self.env['HOME'] = str(self.path / 'empty-home')

    @unittest.skipUnless(Path('/usr/bin/lockf').exists(), 'macOS lockf required')
    def test_kernel_lock_blocks_concurrency_and_recovers_after_crash(self):
        p = subprocess.Popen(['/bin/bash', '-c', 'source "$1"; acquire_lock; echo READY; read -r _',
                              'test', str(ROOT / 'sync.sh')], env=self.env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        self.assertEqual(p.stdout.readline().strip(), 'READY')
        args = ['/bin/bash', str(ROOT / 'sync.sh'), 'check']
        q = subprocess.run(args, env=self.env, capture_output=True, text=True)
        self.assertIn('Another sync', q.stdout)
        p.kill()
        p.communicate(timeout=5)
        q = subprocess.run(args, env=self.env, capture_output=True, text=True)
        self.assertEqual(q.returncode, 0, q.stderr)
        self.assertIn('lock is available', q.stdout)

    def test_a_daemon_a_step_starts_does_not_keep_the_lock(self):
        home = self.path / 'home'
        (home / '.config/dotfiles/generated').mkdir(parents=True)
        (home / '.config/dotfiles/generated/Brewfile').write_text('brew "git"\n')
        pidfile = self.path / 'daemon.pid'
        # Like `op daemon` or gpg-agent: started by a step, outliving the run.
        self.cli('brew', f'sleep 300 </dev/null >/dev/null 2>&1 &\necho $! > {pidfile}\nexit 0')
        self.addCleanup(lambda: pidfile.exists() and subprocess.run(['kill', pidfile.read_text().strip()]))
        env = dict(self.env, HOME=str(home))
        p = subprocess.run(['/bin/bash', str(ROOT / 'sync.sh'), 'brewfile'], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(pidfile.exists(), 'the step started its daemon')
        q = subprocess.run(['/bin/bash', str(ROOT / 'sync.sh'), 'check'], env=env, capture_output=True, text=True, timeout=30)
        self.assertIn('lock is available', q.stdout, 'the daemon must not hold the sync lock')

    def test_real_git_operation_states_are_not_staged_or_committed(self):
        subprocess.run(['git', 'clone', '--shared', '--quiet', str(ROOT), str(self.path / 'repo')], check=True)
        repo = self.path / 'repo'
        original_index = (repo / '.git/index').read_bytes()
        for state in ('MERGE_HEAD', 'rebase-merge', 'CHERRY_PICK_HEAD', 'BISECT_LOG'):
            with self.subTest(state=state):
                marker = repo / '.git' / state
                marker.write_text('fixture')
                p = self.bash('sync_git_repo "$1"', str(repo))
                self.assertNotEqual(p.returncode, 0)
                self.assertIn('Git operation in progress', p.stdout)
                self.assertEqual((repo / '.git/index').read_bytes(), original_index)
                marker.unlink()

    def test_sync_only_installs_missing_packages_without_upgrade(self):
        audit = self.path / 'brew-audit'
        self.env['DOTFILES_TEST_AUDIT'] = str(audit)
        home = self.path / 'home'
        generated = home / '.config/dotfiles/generated'
        generated.mkdir(parents=True)
        (generated / 'Brewfile').write_text('brew "example"\n')
        self.env['HOME'] = str(home)
        self.cli('brew', 'printf "%s AUTO_UPDATE=%s\\n" "$*" "$HOMEBREW_NO_AUTO_UPDATE" >> "$DOTFILES_TEST_AUDIT"\ncase "$*" in *check*) exit 1;; esac')
        p = self.bash('sync_brewfile')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('install --no-upgrade', audit.read_text())
        self.assertIn('AUTO_UPDATE=1', audit.read_text())

    def brewfile_with_root_entries(self):
        home = self.path / 'home'
        generated = home / '.config/dotfiles/generated'
        generated.mkdir(parents=True)
        (generated / 'Brewfile').write_text('cask "karabiner-elements" # tool.karabiner\ncask "slack" # brew.apps\n'
                                            'cask "alfred" # brew.apps\n'
                                            'mas "Keynote", id: 361285480 # brew.mas\n'
                                            'mas "Parallels Desktop", id: 1085114709 # brew.mas\n')
        audit = self.path / 'brew-audit'
        self.env.update(HOME=str(home), DOTFILES_TEST_AUDIT=str(audit))
        info = json.dumps({'formulae': [], 'casks': [
            {'token': 'karabiner-elements', 'full_token': 'karabiner-elements',
             'artifacts': [{'uninstall': [{'script': {'sudo': True}}]}, {'pkg': ['Karabiner-Elements.pkg']}]},
            {'token': 'slack', 'full_token': 'slack',
             'artifacts': [{'uninstall': [{'delete': ['/x'], 'sudo': True}]}, {'app': ['Slack.app']}]}]})
        self.cli('brew', f'''case "$*" in
  "bundle check"*) exit 1 ;;
  "bundle list --cask"*) printf 'karabiner-elements\\nslack\\nalfred\\n' ;;
  "list --cask -1") echo alfred ;;
  "info --json=v2 --cask karabiner-elements slack") echo '{info}' ;;
  "bundle install"*) printf 'install CASK_SKIP=%s MAS_SKIP=%s NO_SUDO=%s\\n' "$HOMEBREW_BUNDLE_CASK_SKIP" "$HOMEBREW_BUNDLE_MAS_SKIP" "${{HOMEBREW_NO_SUDO:-}}" >> "$DOTFILES_TEST_AUDIT" ;;
  *) echo "unexpected brew $*" >&2; exit 2 ;;
esac''')
        self.cli('mas', 'printf "361285480  Keynote  (16.0)\\n"')
        return audit

    def test_unattended_sync_leaves_root_installs_for_a_terminal(self):
        audit = self.brewfile_with_root_entries()
        p = subprocess.run(['/bin/bash', '-c', 'source "$1"; sync_brewfile', 'test', str(ROOT / 'sync.sh')],
                           cwd=self.path, env=self.env, capture_output=True, text=True, timeout=30,
                           start_new_session=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(audit.read_text(), 'install CASK_SKIP=karabiner-elements MAS_SKIP=1085114709 NO_SUDO=1\n',
                         'a cask that needs root only to uninstall still installs; an installed app is not skipped')
        self.assertIn('WARN: Left cask karabiner-elements, mas Parallels Desktop (1085114709) for a terminal', p.stdout)
        self.assertIn('run: brew bundle install --file=', p.stdout)

    def test_sync_with_passwordless_sudo_installs_everything(self):
        audit = self.brewfile_with_root_entries()
        self.cli('sudo', 'exit 0')
        p = subprocess.run(['/bin/bash', '-c', 'source "$1"; sync_brewfile', 'test', str(ROOT / 'sync.sh')],
                           cwd=self.path, env=self.env, capture_output=True, text=True, timeout=30,
                           start_new_session=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(audit.read_text(), 'install CASK_SKIP= MAS_SKIP= NO_SUDO=\n')
        self.assertNotIn('WARN', p.stdout)

    def test_sync_installs_mise_tools_only_when_some_are_missing(self):
        audit = self.path / 'mise-audit'
        home = self.path / 'home'
        home.mkdir()
        self.env.update(HOME=str(home), DOTFILES_TEST_AUDIT=str(audit))
        self.cli('mise', 'printf "%s\\n" "$*" >> "$DOTFILES_TEST_AUDIT"\n'
                 'case "$*" in *"ls --missing"*) printf "%s" "${MISE_MISSING:-}" ;; esac')
        p = self.bash('sync_mise_tools')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn('install', audit.read_text())
        self.env['MISE_MISSING'] = 'go  1.27.5 (missing)'
        p = self.bash('sync_mise_tools')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('-C %s install --yes' % home, audit.read_text())

    def claude_code_fixture(self, name, enabled=True, installed=False, installer=None):
        """A home for sync_claude_code: an engine reporting agents.claude as
        ENABLED, a curl that serves INSTALLER (by default one that installs a
        stand-in claude), and the stand-in already there when INSTALLED."""
        home = self.path / name
        home.mkdir()
        if installed:
            (home / '.local/bin').mkdir(parents=True)
            (home / '.local/bin/claude').write_text('#!/bin/sh\n')
            (home / '.local/bin/claude').chmod(0o755)
        audit = self.path / f'{name}-curl'
        status = {'features': [{'id': 'agents.claude', 'enabled': enabled, 'source': 'profile:dev'},
                               {'id': 'agents.codex', 'enabled': True, 'source': 'profile:dev'}]}
        self.cli('dotfiles', f"printf '%s\\n' '{json.dumps(status)}'")
        self.cli('curl', 'out=; url=\n'
                 'while [ $# -gt 0 ]; do case "$1" in -o) out=$2; shift ;; -*) ;; *) url=$1 ;; esac; shift; done\n'
                 'printf "%s\\n" "$url" >> "$DOTFILES_TEST_AUDIT"\n'
                 'printf "%s\\n" "$DOTFILES_TEST_INSTALLER" > "$out"')
        installer = installer or ('mkdir -p "$HOME/.local/bin" && printf "#!/bin/sh\\n" > "$HOME/.local/bin/claude"'
                                  ' && chmod +x "$HOME/.local/bin/claude"')
        self.env.update(HOME=str(home), DOTFILES_BIN=str(self.bin / 'dotfiles'), DOTFILES_TEST_AUDIT=str(audit),
                        DOTFILES_TEST_INSTALLER=installer)
        return home, lambda: audit.read_text().splitlines() if audit.exists() else []

    def test_claude_code_is_installed_natively_only_where_wanted_and_missing(self):
        url = 'https://claude.ai/install.sh'
        cases = [
            ('missing', dict(), 0, [url], True),
            ('installed', dict(installed=True), 0, [], True),
            ('not-wanted', dict(enabled=False), 0, [], False),
            ('installer-fails', dict(installer='exit 3'), 1, [url], False),
        ]
        for name, kwargs, code, fetched, claude_after in cases:
            with self.subTest(name):
                home, curl_calls = self.claude_code_fixture(name, **kwargs)
                p = self.bash('sync_claude_code')
                self.assertEqual(p.returncode, code, p.stdout + p.stderr)
                self.assertEqual(curl_calls(), fetched)
                self.assertEqual((home / '.local/bin/claude').exists(), claude_after)
                if code:
                    self.assertIn('the Claude Code installer failed (exit 3)', p.stdout)
        self.assertEqual(list(self.path.glob('claude-install.*')), [], 'the downloaded installer is removed')

    def test_a_stalled_claude_code_installer_is_stopped_at_its_deadline(self):
        child = self.path / 'child.pid'
        self.claude_code_fixture('stalled', installer=f'sleep 300 & echo $! > {child}; wait')
        self.env['CLAUDE_CODE_INSTALL_TIMEOUT'] = '2'
        p = self.bash('sync_claude_code')
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn('did not finish within 2s and was stopped', p.stdout)
        pid = int(child.read_text())
        self.addCleanup(lambda: subprocess.run(['kill', str(pid)], capture_output=True))
        time.sleep(0.5)
        self.assertNotEqual(subprocess.run(['kill', '-0', str(pid)], capture_output=True).returncode, 0,
                            'what the installer started is stopped with it')

    def test_sync_converges_the_telemetry_collector_and_reports_failure(self):
        audit = self.path / 'otel-audit'
        self.env['DOTFILES_TEST_AUDIT'] = str(audit)
        # DOTFILES_DIR is the fixture, so its bin/ is the checkout's bin/.
        self.cli('otel-agent', 'printf "%s\\n" "$*" >> "$DOTFILES_TEST_AUDIT"\nexit "${OTEL_EXIT:-0}"')
        p = self.bash('sync_otel_agent')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(audit.read_text(), 'converge\n')
        self.env['OTEL_EXIT'] = '78'
        p = self.bash('sync_otel_agent')
        self.assertEqual(p.returncode, 1)
        self.assertIn('telemetry collector did not converge', p.stdout)

    def test_sync_never_runs_mackup(self):
        audit = self.path / 'mackup-audit'
        home = self.path / 'home'
        home.mkdir()
        self.env.update(HOME=str(home), DOTFILES_TEST_AUDIT=str(audit))
        self.cli('mackup', 'printf "%s\\n" "$*" >> "$DOTFILES_TEST_AUDIT"')
        self.cli('curl', 'exit 0')
        self.cli('brew', 'exit 0')
        for command in ('sync', 'all'):
            subprocess.run(['/bin/bash', str(ROOT / 'sync.sh'), command], cwd=self.path, env=self.env,
                           capture_output=True, text=True, timeout=60)
        self.assertFalse(audit.exists())
        p = subprocess.run(['/bin/bash', str(ROOT / 'sync.sh'), 'mackup'], cwd=self.path, env=self.env,
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 1)
        self.assertIn('Usage', p.stdout)
        self.assertNotIn('mackup', p.stdout)

    def mock_sync(self, failure=''):
        self.env['DOTFILES_TEST_FAILURE'] = failure
        self.env['DOTFILES_TEST_AUDIT'] = str(self.path / 'git-audit')
        return self.bash(MOCK_GIT + '\nsync_git_repo "$DOTFILES_DIR"')

    def test_signing_failure_stops_publication(self):
        p = self.mock_sync('commit')
        self.assertNotEqual(p.returncode, 0)
        audit = (self.path / 'git-audit').read_text()
        self.assertIn('git commit -S ', audit)
        self.assertNotIn('git push ', audit)

    def test_secret_scan_failure_stops_commit_and_push(self):
        p = self.mock_sync('scan')
        self.assertNotEqual(p.returncode, 0)
        audit = (self.path / 'git-audit').read_text()
        self.assertNotIn('git commit ', audit)
        self.assertNotIn('git push ', audit)

    def test_merge_failure_aborts_and_never_pushes(self):
        p = self.mock_sync('merge')
        self.assertNotEqual(p.returncode, 0)
        audit = (self.path / 'git-audit').read_text()
        self.assertIn('git merge --abort', audit)
        self.assertNotIn('git push ', audit)

    def test_local_verification_failure_stops_publication(self):
        p = self.mock_sync('verify')
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn('git push ', (self.path / 'git-audit').read_text())

    def test_trailing_slash_does_not_bypass_secret_scan(self):
        self.env['DOTFILES_DIR'] = str(self.path) + '/'
        p = self.mock_sync('scan')
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn('git push ', (self.path / 'git-audit').read_text())

    def test_signed_publication_checks_github_verification(self):
        p = self.mock_sync()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        audit = (self.path / 'git-audit').read_text()
        self.assertIn('git add -u -- . ', audit)
        self.assertNotIn('git add -A', audit)
        self.assertIn('git commit -S ', audit)
        self.assertIn('git verify-commit ', audit)
        self.assertIn('git merge --no-edit --gpg-sign', audit)
        self.assertIn('git push origin HEAD:refs/heads/master', audit)
        self.assertIn('gh api repos/example/dotfiles/commits/', audit)

    def test_github_bad_email_is_reported_as_failure(self):
        p = self.mock_sync('github')
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('bad_email', p.stdout)
        self.assertIn('user.email', p.stdout)


def age(path, minutes=120):
    then = time.time() - minutes * 60
    os.utime(path, (then, then))


class SignedRepo(Fixture):
    """A real repository that signs with a throwaway SSH key."""

    def setUp(self):
        super().setUp()
        (self.path / 'logs').mkdir()
        home = self.path / 'home'
        home.mkdir()
        self.env.update(HOME=str(home), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        self.env.pop('SYNC_QUIET_MINUTES', None)
        key = self.path / 'signing'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'fixture', '-f', str(key)],
                       check=True, env=self.env)
        signers = self.path / 'allowed_signers'
        signers.write_text('fixture@example.com ' + (self.path / 'signing.pub').read_text())
        self.signing = {'user.name': 'Fixture', 'user.email': 'fixture@example.com',
                        'user.signingkey': str(key), 'gpg.format': 'ssh', 'gpg.program': '/usr/bin/true',
                        'gpg.ssh.allowedSignersFile': str(signers), 'commit.gpgsign': 'true'}
        self.repo = self.path / 'repo'
        subprocess.run(['git', 'init', '-q', '-b', 'master', str(self.repo)], check=True, env=self.env)
        self.configure_signing(self.repo)
        (self.repo / 'sub').mkdir()
        for name in ('tracked', 'sub/app.local'):
            (self.repo / name).write_text('one\n')
        self.git('add', 'tracked', 'sub/app.local')
        self.git('commit', '-q', '-m', 'initial')

    def configure_signing(self, repo):
        for name, value in self.signing.items():
            subprocess.run(['git', '-C', str(repo), 'config', name, value], check=True, env=self.env)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], env=self.env, check=True,
                              capture_output=True, text=True).stdout

    def edit(self, name, minutes_ago=120):
        (self.repo / name).write_text('two\n')
        if minutes_ago:
            age(self.repo / name, minutes_ago)



class SyncGit(SignedRepo):
    """sync_git_repo publishing tracked edits."""

    def sync(self):
        return self.bash('sync_git_repo "$1"', str(self.repo))

    def test_publishes_tracked_edits_and_never_new_files(self):
        self.edit('tracked')
        self.edit('sub/app.local')
        (self.repo / 'new-file').write_text('dropped here by a tool\n')
        p = self.sync()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(self.git('log', '-1', '--format=%s').startswith('auto: sync'))
        self.assertEqual(self.git('show', '--name-only', '--format=', 'HEAD').split(), ['tracked'])
        self.assertIn('?? new-file', self.git('status', '--porcelain'))
        self.assertIn('1 untracked file', p.stdout)

    def test_recent_edit_is_left_for_a_later_run(self):
        self.edit('tracked', minutes_ago=0)
        p = self.sync()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('changed in the last 30 minutes', p.stdout)
        self.assertEqual(self.git('log', '-1', '--format=%s'), 'initial\n')

    def test_index_lock_is_left_for_a_later_run(self):
        self.edit('tracked')
        (self.repo / '.git/index.lock').write_text('')
        p = self.sync()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('index lock', p.stdout)
        self.assertEqual(self.git('log', '-1', '--format=%s'), 'initial\n')


class SyncOverlays(SignedRepo):
    """sync_overlays: the overlays the engine names are synced before apply."""

    def setUp(self):
        super().setUp()
        origin = self.path / 'overlay.git'
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'master', str(origin)], check=True, env=self.env)
        self.git('remote', 'add', 'origin', str(origin))
        self.git('push', '-q', '-u', 'origin', 'master')
        self.origin = origin
        machine = Path(self.env['HOME']) / '.config/dotfiles/machine.toml'
        machine.parent.mkdir(parents=True)
        machine.write_text('overlays = ["repo", "missing"]\nprofiles = ["base"]\n')
        self.missing = self.path / 'missing'
        engine_calls = self.stub_engine()
        self.cli('dotfiles', f'printf "%s\\n" "$*" >> {self.path / "engine-audit"}\n'
                             f'[ "$1" = overlays ] && printf "%s\\n%s\\n" {self.repo} {self.missing}\nexit 0')
        self.engine_calls = engine_calls

    def test_listed_overlays_publish_and_a_missing_one_is_reported(self):
        self.edit('tracked')
        p = self.bash('sync_overlays')
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertEqual(self.engine_calls(), [f'overlays --machine {self.env["HOME"]}/.config/dotfiles/machine.toml'])
        pushed = subprocess.run(['git', '--git-dir', str(self.origin), 'log', '-1', '--format=%s'],
                                env=self.env, capture_output=True, text=True, check=True).stdout
        self.assertTrue(pushed.startswith('auto: sync'), "the overlay's tracked edit is published to its own remote")
        self.assertIn(f'lists overlay missing, which is not cloned at {self.missing}', p.stdout)

    def test_a_machine_without_a_manifest_has_no_overlays(self):
        (Path(self.env['HOME']) / '.config/dotfiles/machine.toml').unlink()
        p = self.bash('sync_overlays')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.engine_calls(), [])


class SyncWithoutIdentity(SignedRepo):
    """sync_git_repo on a repository that cannot sign: it receives, and publishes nothing."""

    def setUp(self):
        super().setUp()
        origin = self.path / 'origin.git'
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'master', str(origin)], check=True, env=self.env)
        self.git('remote', 'add', 'origin', str(origin))
        self.git('push', '-q', '-u', 'origin', 'master')
        self.other = self.path / 'other'
        subprocess.run(['git', 'clone', '-q', str(origin), str(self.other)], check=True, env=self.env)

    def upstream_commit(self, name):
        """Another machine publishes NAME, a new file."""
        (self.other / name).write_text('upstream\n')
        for args in (['add', name],
                     ['-c', 'user.name=Other', '-c', 'user.email=other@example.com', '-c', 'commit.gpgsign=false',
                      'commit', '-q', '-m', 'upstream ' + name],
                     ['push', '-q', 'origin', 'master']):
            subprocess.run(['git', '-C', str(self.other), *args], check=True, env=self.env)
        return subprocess.run(['git', '-C', str(self.other), 'rev-parse', 'HEAD'], env=self.env, check=True,
                              capture_output=True, text=True).stdout

    def sync(self):
        return self.bash('sync_git_repo "$1"', str(self.repo))

    def test_fast_forwards_to_what_brings_the_identity(self):
        upstream = self.upstream_commit('identity')
        self.git('config', '--unset', 'user.email')
        p = self.sync()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('receiving only', p.stdout)
        self.assertEqual(self.git('rev-parse', 'HEAD'), upstream)

    def test_local_edits_wait_for_the_identity_and_fail_the_run(self):
        upstream = self.upstream_commit('identity')
        self.edit('tracked')
        self.git('config', '--unset', 'user.signingkey')
        p = self.sync()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn('committing them needs a signing identity', p.stdout)
        self.assertEqual(self.git('rev-parse', 'HEAD'), upstream, 'what does not touch the edit still arrives')
        self.assertEqual(self.git('status', '--porcelain', '--untracked-files=no'), ' M tracked\n')

    def test_a_diverged_branch_is_left_as_it_is(self):
        self.upstream_commit('identity')
        (self.repo / 'local').write_text('local\n')
        self.git('add', 'local')
        self.git('commit', '-q', '-m', 'local')
        before = self.git('rev-parse', 'HEAD')
        self.git('config', '--unset', 'user.email')
        p = self.sync()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn('cannot fast-forward', p.stdout)
        self.assertEqual(self.git('rev-parse', 'HEAD'), before)
        self.assertEqual(self.git('status', '--porcelain'), '')


class PrivateNames(SignedRepo):
    """The public checkout names nothing an overlay's denylist.txt keeps private."""

    def setUp(self):
        super().setUp()
        overlay = self.path / 'overlays/personal'
        overlay.mkdir(parents=True)
        (overlay / 'denylist.txt').write_text('# private repositories\nsecret-repo\n\nclient-org  # a client\n')
        machine = Path(self.env['HOME']) / '.config/dotfiles/machine.toml'
        machine.parent.mkdir(parents=True)
        machine.write_text('overlays = ["personal"]\nprofiles = ["base"]\n')
        self.cli('dotfiles', f'[ "$1" = overlays ] && echo {overlay} && echo {self.path / "overlays/unlisted"}\nexit 0')
        self.env['DOTFILES_BIN'] = str(self.bin / 'dotfiles')

    def check(self):
        return subprocess.run([str(ROOT / 'bin/check-private-names'), str(self.repo)], env=self.env,
                              capture_output=True, text=True, timeout=20)

    def test_a_tracked_line_with_a_listed_name_fails(self):
        self.assertEqual(self.check().returncode, 0, 'a clean tree passes')
        (self.repo / 'tracked').write_text('see Client-Org/infra\nsecret-repository is fine\n')
        p = self.check()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn('tracked:1:see Client-Org/infra', p.stdout)
        self.assertNotIn('secret-repository', p.stdout, 'names match whole words only')

    def test_sync_publishes_nothing_that_names_one(self):
        self.env['DOTFILES_DIR'] = str(self.repo)
        (self.repo / 'logs').mkdir()
        if not shutil.which('gitleaks'):
            self.skipTest('gitleaks required by the publish scan')
        self.edit('tracked')
        (self.repo / 'tracked').write_text('moved to secret-repo\n')
        age(self.repo / 'tracked', 120)
        p = self.bash('sync_dotfiles')
        self.assertNotEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('name what an overlay keeps private', p.stdout)
        self.assertEqual(self.git('log', '-1', '--format=%s'), 'initial\n')


MISE_PIN = 'features/tool.mise/home/.config/mise/conf.d/dotfiles.toml'


class GoPin(SignedRepo):
    """dotfiles-update.sh --go moving the Go pin to its minor's newest patch."""

    def setUp(self):
        super().setUp()
        self.pin = self.repo / MISE_PIN
        self.pin.parent.mkdir(parents=True)
        self.pin.write_text((ROOT / MISE_PIN).read_text().replace(self.current_pin(ROOT / MISE_PIN), '1.27.4'))
        self.git('add', MISE_PIN)
        self.git('commit', '-q', '-m', 'pin')
        origin = self.path / 'origin.git'
        subprocess.run(['git', 'clone', '-q', '--bare', str(self.repo), str(origin)], check=True, env=self.env)
        self.git('remote', 'add', 'origin', str(origin))
        self.git('fetch', '-q', 'origin')
        self.git('branch', '-q', '--set-upstream-to=origin/master')
        self.audit = self.path / 'mise-audit'
        self.env.update(DOTFILES_DIR=str(self.repo), DOTFILES_TEST_AUDIT=str(self.audit),
                        DOTFILES_MISE_CANARY='canary-host', MISE_LATEST='1.27.5', MISE_GO_VERSION='1.27.5')
        self.cli('scutil', 'printf "%s\\n" "${FIXTURE_HOST:-canary-host}"')
        # latest prints MISE_LATEST; install records its arguments; exec runs
        # `go version` as the Go release MISE_GO_VERSION.
        self.cli('mise', '\n'.join([
            'printf "%s\\n" "$*" >> "$DOTFILES_TEST_AUDIT"',
            'case "$1" in',
            '  latest) printf "%s\\n" "$MISE_LATEST" ;;',
            '  install) exit "${MISE_INSTALL_EXIT:-0}" ;;',
            '  exec) printf "go version go%s darwin/arm64\\n" "$MISE_GO_VERSION" ;;',
            'esac']))

    @staticmethod
    def current_pin(path):
        return re.search(r'^go = "([0-9.]+)"$', path.read_text(), re.M).group(1)

    def update(self):
        return subprocess.run(['/bin/bash', str(ROOT / 'bin/dotfiles-update.sh'), '--quiet', '--go'],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def test_moves_to_the_newest_patch_and_commits_it_signed(self):
        p = self.update()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.current_pin(self.pin), '1.27.5')
        self.assertEqual(self.git('log', '-1', '--format=%s'), 'mise: pin Go 1.27.5\n')
        self.assertEqual(self.git('show', '--name-only', '--format=', 'HEAD').split(), [MISE_PIN])
        self.git('verify-commit', 'HEAD')
        calls = self.audit.read_text()
        self.assertIn('latest go@1.27', calls)
        self.assertIn('install --yes go@1.27.5', calls)

    def test_changes_nothing_off_the_canary_or_when_already_newest(self):
        for env in ({'FIXTURE_HOST': 'other-host'}, {'DOTFILES_MISE_CANARY': ''}, {'MISE_LATEST': '1.27.4'}):
            with self.subTest(env=env):
                saved = {k: self.env.get(k) for k in env}
                self.env.update(env)
                p = self.update()
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(self.current_pin(self.pin), '1.27.4')
                self.assertEqual(self.git('log', '-1', '--format=%s'), 'pin\n')
                for k, v in saved.items():
                    if v is None:
                        self.env.pop(k, None)
                    else:
                        self.env[k] = v
        self.assertNotIn('install', self.audit.read_text())

    def test_reads_the_canary_from_the_generated_settings(self):
        del self.env['DOTFILES_MISE_CANARY']
        generated = Path(self.env['HOME']) / '.config/dotfiles/generated'
        generated.mkdir(parents=True)
        (generated / 'env.sh').write_text(
            "[ -n \"${DOTFILES_MISE_CANARY:-}\" ] || DOTFILES_MISE_CANARY='canary-host'; export DOTFILES_MISE_CANARY\n")
        p = self.update()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.current_pin(self.pin), '1.27.5')

    def test_leaves_an_edited_pin_file_alone(self):
        self.pin.write_text(self.pin.read_text() + '# a local note\n')
        p = self.update()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('uncommitted edits', (self.repo / 'logs/update.log').read_text())
        self.assertEqual(self.current_pin(self.pin), '1.27.4')
        self.assertEqual(self.git('log', '-1', '--format=%s'), 'pin\n')

    def test_a_release_that_does_not_install_or_run_keeps_the_pin(self):
        for env in ({'MISE_INSTALL_EXIT': '3'}, {'MISE_GO_VERSION': '1.27.4'}):
            with self.subTest(env=env):
                self.env.update(env)
                p = self.update()
                self.assertNotEqual(p.returncode, 0)
                self.assertEqual(self.current_pin(self.pin), '1.27.4')
                self.assertEqual(self.git('log', '-1', '--format=%s'), 'pin\n')
                self.env.pop('MISE_INSTALL_EXIT', None)
                self.env['MISE_GO_VERSION'] = '1.27.5'

    def test_a_commit_that_fails_restores_the_pin(self):
        self.git('config', 'user.signingkey', str(self.path / 'no-such-key'))
        p = self.update()
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(self.current_pin(self.pin), '1.27.4')
        self.assertEqual(self.git('status', '--porcelain', '--', MISE_PIN), '')
        self.assertEqual(self.git('log', '-1', '--format=%s'), 'pin\n')


# A stand-in for an upstream checkout's engine: `check` and `apply` record
# their arguments, and `check` exits with CHECK_EXIT.
FAKE_ENGINE = """package main

import (
	"os"
	"strings"
)

const checkExit = CHECK_EXIT

func main() {
	args := []byte(strings.Join(os.Args[1:], "\\n"))
	switch os.Args[1] {
	case "check":
		os.WriteFile(os.Getenv("DOTFILES_TEST_CHECKED"), args, 0o644)
		os.Exit(checkExit)
	case "apply":
		os.WriteFile(os.Getenv("DOTFILES_TEST_APPLIED"), args, 0o644)
	}
}
"""


@unittest.skipUnless(shutil.which('go'), 'Go required to build the upstream engine')
class SyncFeaturesLayout(SignedRepo):
    """The run that first pulls the features layout: gated on a machine manifest and on the
    upstream engine building and planning it, then applied in the same run."""

    def setUp(self):
        super().setUp()
        self.origin = self.path / 'origin.git'
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'master', str(self.origin)], check=True, env=self.env)
        self.git('remote', 'add', 'origin', str(self.origin))
        self.git('push', '-q', '-u', 'origin', 'master')
        (self.repo / 'logs').mkdir()
        self.machine = Path(self.env['HOME']) / '.config/dotfiles/machine.toml'
        self.applied = self.path / 'applied'
        self.checked = self.path / 'checked'
        self.engine = self.path / 'engine/dotfiles'
        gocache = subprocess.run(['go', 'env', 'GOCACHE'], capture_output=True, text=True, check=True).stdout.strip()
        self.env.pop('XDG_CONFIG_HOME', None)
        self.env.update(DOTFILES_DIR=str(self.repo),
                        DOTFILES_BIN=str(self.engine), DOTFILES_TEST_APPLIED=str(self.applied),
                        DOTFILES_TEST_CHECKED=str(self.checked), GOCACHE=gocache)

    def publish_upstream(self, check_exit=0, engine=FAKE_ENGINE):
        """Upstream gains the features layout and its engine; this machine has not pulled it yet."""
        files = {'features/shell.env/feature.toml': 'id = "shell.env"\n', 'profiles/base.toml': '',
                 'profiles/dev.toml': '', 'go.mod': 'module example.invalid/engine\n\ngo 1.21\n',
                 'cmd/dotfiles/main.go': engine.replace('CHECK_EXIT', str(check_exit))}
        for name, text in files.items():
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text(text)
        self.git('add', *files)
        self.git('commit', '-q', '-m', 'features layout')
        self.git('push', '-q', 'origin', 'master')
        self.git('reset', '-q', '--hard', 'HEAD~1')
        self.upstream = self.git('rev-parse', 'origin/master').strip()

    def write_machine(self):
        self.machine.parent.mkdir(parents=True)
        self.machine.write_text('profiles = ["base"]\n')

    def run_sync(self):
        return self.bash('sync_dotfiles; s=$?; apply_features || s=1; exit $s')

    def assert_not_merged(self, p):
        self.assertNotEqual(p.returncode, 0)
        self.assertNotEqual(self.git('rev-parse', 'HEAD').strip(), self.upstream)
        self.assertFalse(self.applied.exists())

    def test_without_a_machine_manifest_nothing_is_merged_or_applied(self):
        self.publish_upstream()
        p = self.run_sync()
        self.assert_not_merged(p)
        self.assertIn('has no ' + str(self.machine), p.stdout)
        self.assertIn('available: base dev', p.stdout)
        self.assertFalse(self.checked.exists())

    def test_with_a_machine_manifest_the_same_run_merges_and_applies(self):
        self.publish_upstream()
        self.write_machine()
        p = self.run_sync()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD').strip(), self.upstream)
        checked = self.checked.read_text().split('\n')
        self.assertEqual((checked[0], checked[1], checked[3], checked[4]), ('check', '--repo', '--machine', str(self.machine)))
        self.assertFalse(Path(checked[2]).exists(), 'the upstream tree is removed after the check')
        self.assertEqual(self.applied.read_text().split(), ['apply', '--repo', str(self.repo.resolve())])
        self.assertIn('Building ' + str(self.engine), p.stdout, 'the merged engine is built for the apply')

    def test_an_upstream_engine_that_cannot_plan_this_machine_is_not_merged(self):
        self.publish_upstream(check_exit=2)
        self.write_machine()
        p = self.run_sync()
        self.assert_not_merged(p)
        self.assertIn('cannot plan', p.stdout)

    def test_an_upstream_engine_that_does_not_build_is_not_merged(self):
        self.publish_upstream(engine=FAKE_ENGINE.replace('func main() {', 'func main() { undefined()'))
        self.write_machine()
        p = self.run_sync()
        self.assert_not_merged(p)
        self.assertIn('does not build', p.stdout)
        self.assertFalse(self.checked.exists())


# A stand-in engine for a sync's checkouts: `overlays` names the first LISTED
# paths in DOTFILES_TEST_OVERLAYS, and `check` fails as the real engine does
# while the first of them does not define the feature machine.toml enables.
CHECKOUTS_ENGINE = """package main

import (
	"os"
	"strings"
)

const overlays = LISTED

func main() {
	listed := strings.Fields(os.Getenv("DOTFILES_TEST_OVERLAYS"))[:overlays]
	switch os.Args[1] {
	case "overlays":
		os.Stdout.WriteString(strings.Join(listed, "\\n") + "\\n")
	case "check":
		if _, err := os.Stat(listed[0] + "/features/personal.tool/feature.toml"); err != nil {
			os.Stderr.WriteString("dotfiles: feature resolution failed: machine enables unknown feature \\"personal.tool\\"\\n")
			os.Exit(2)
		}
	}
}
"""


@unittest.skipUnless(shutil.which('go'), 'Go required to build the engines')
class SyncCheckouts(SignedRepo):
    """sync_checkouts: the dotfiles merge is checked against the overlays apply will read, and
    an overlay only the merged engine names is synced in the same run."""

    def setUp(self):
        super().setUp()
        self.engine = self.path / 'engine/dotfiles'
        self.overlays = [self.path / 'overlays/personal', self.path / 'overlays/client']
        gocache = subprocess.run(['go', 'env', 'GOCACHE'], capture_output=True, text=True, check=True).stdout.strip()
        self.env.pop('XDG_CONFIG_HOME', None)
        self.env.update(DOTFILES_DIR=str(self.repo), DOTFILES_BIN=str(self.engine), GOCACHE=gocache,
                        DOTFILES_TEST_OVERLAYS=' '.join(map(str, self.overlays)))
        machine = Path(self.env['HOME']) / '.config/dotfiles/machine.toml'
        machine.parent.mkdir(parents=True)
        machine.write_text('overlays = ["personal", "client"]\nprofiles = ["base"]\n\n'
                           '[features]\nenable = ["personal.tool"]\n')
        (self.repo / 'logs').mkdir()
        self.commit(self.repo, self.engine_files(1), 'engine')
        self.with_origin(self.repo)
        self.dotfiles_upstream = self.incoming(self.repo, self.engine_files(2), 'the engine names a second overlay')
        for overlay in self.overlays:
            self.run_git(self.path, 'init', '-q', '-b', 'master', str(overlay))
            self.configure_signing(overlay)
            self.commit(overlay, {'README.md': overlay.name + '\n'}, 'initial')
            self.with_origin(overlay)
        self.overlay_upstream = [
            self.incoming(self.overlays[0], {'features/personal.tool/feature.toml': 'id = "personal.tool"\n'},
                          'personal.tool'),
            self.incoming(self.overlays[1], {'README.md': 'client, updated\n'}, 'update'),
        ]

    @staticmethod
    def engine_files(overlays):
        return {'features/shell.env/feature.toml': 'id = "shell.env"\n', 'profiles/base.toml': '',
                'go.mod': 'module example.invalid/engine\n\ngo 1.21\n',
                'cmd/dotfiles/main.go': CHECKOUTS_ENGINE.replace('LISTED', str(overlays))}

    def run_git(self, repo, *args):
        return subprocess.run(['git', '-C', str(repo), *args], env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, repo, files, message):
        for name, text in files.items():
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text(text)
        self.run_git(repo, 'add', *files)
        self.run_git(repo, 'commit', '-q', '-m', message)

    def with_origin(self, repo):
        origin = self.path / f'{repo.name}.git'
        self.run_git(self.path, 'init', '-q', '--bare', '-b', 'master', str(origin))
        self.run_git(repo, 'remote', 'add', 'origin', str(origin))
        self.run_git(repo, 'push', '-q', '-u', 'origin', 'master')

    def incoming(self, repo, files, message):
        """Another machine publishes MESSAGE to REPO's origin, which REPO has fetched but not merged."""
        self.commit(repo, files, message)
        self.run_git(repo, 'push', '-q', 'origin', 'master')
        self.run_git(repo, 'reset', '-q', '--hard', 'HEAD~1')
        return self.run_git(repo, 'rev-parse', 'origin/master')

    def sync(self):
        return self.bash('sync_checkouts', timeout=120)

    def test_a_feature_only_an_incoming_overlay_commit_defines_does_not_hold_the_merge_back(self):
        p = self.sync()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.run_git(self.overlays[0], 'rev-parse', 'HEAD'), self.overlay_upstream[0])
        self.assertEqual(self.run_git(self.repo, 'rev-parse', 'HEAD'), self.dotfiles_upstream)
        self.assertNotIn('cannot plan', p.stdout)

    def test_an_overlay_only_the_merged_engine_names_is_synced_in_the_same_run(self):
        p = self.sync()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.run_git(self.overlays[1], 'rev-parse', 'HEAD'), self.overlay_upstream[1])
        self.assertEqual(p.stdout.count('INFO: Syncing personal'), 1, 'each overlay is synced once per run')


@unittest.skipUnless(shutil.which('go'), 'Go required to build the engine')
class RealFeatures(Fixture):
    """The repository's own features and profiles, applied by the real engine to a fresh home."""

    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='dotfiles-engine-')
        cls.engine = Path(cls.build.name) / 'dotfiles'
        subprocess.run(['go', 'build', '-trimpath', '-o', str(cls.engine), './cmd/dotfiles'],
                       cwd=ROOT, check=True, env=dict(os.environ, GOTOOLCHAIN='local'), timeout=300)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        self.home.mkdir()
        if sys.platform == 'darwin':
            # Every macOS account has one; macos.spotlight's check would
            # otherwise see the LaunchAgent step create it after the hooks ran.
            (self.home / 'Library/Logs').mkdir(parents=True)
        self.env.update(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / '.config'),
                        XDG_STATE_HOME=str(self.home / '.local/state'))
        # Never the Muxy installed on this computer: install_muxy() points
        # here at a stand-in.
        self.env['DOTFILES_MUXY_APP'] = str(self.path / 'no-muxy.app')
        self.muxy_settings = self.path / 'muxy-settings.json'
        # Nor this computer's Spotlight exclusion list, which macos.spotlight's
        # hooks read and change.
        self.env['SPOTLIGHT_EXCLUSIONS_STORE'] = str(self.path / 'spotlight-exclusions.json')
        # Never this computer's root-owned agent configs either: a system
        # root of the test's own, set up as `apply --sudo` leaves a Mac.
        self.system = self.path / 'system'
        self.env['DOTFILES_SYSTEM_ROOT'] = str(self.system)
        p = subprocess.run(['/bin/bash', str(ROOT / 'bin/dotfiles-agents'), 'install'], env=self.env,
                           capture_output=True, text=True, timeout=60)
        if p.returncode == 69:
            self.skipTest('bash 4 or later required by dotfiles-agents')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def install_muxy(self):
        """A stand-in for Muxy under the fresh home's ~/Applications, where the
        engine looks first: its `muxy config` keeps settings in a JSON file."""
        settings = self.muxy_settings
        settings.write_text(json.dumps({'appearance.dark_theme': 'Muxy', 'appearance.layout': 'project_focused'}))
        cli = self.home / 'Applications/Muxy.app/Contents/MacOS/muxy'
        cli.parent.mkdir(parents=True)
        cli.write_text(f'''#!{sys.executable}
import json, pathlib, sys, tomllib
state = pathlib.Path({str(settings)!r})
values = json.loads(state.read_text())
args = [a for a in sys.argv[1:] if a not in ('--json', '--')]
if args[:2] == ['config', 'list']:
    print(json.dumps(values))
elif args[:2] == ['config', 'set'] and len(args) == 4:
    values[args[2]] = tomllib.loads('v = ' + args[3])['v']
    state.write_text(json.dumps(values))
    print(json.dumps({{'key': args[2], 'applied': False}}))
elif args[:2] == ['config', 'unset'] and len(args) == 3:
    values.pop(args[2], None)
    state.write_text(json.dumps(values))
else:
    sys.exit('muxy: unknown command')
''')
        cli.chmod(0o755)
        self.env['DOTFILES_MUXY_APP'] = str(self.home / 'Applications/Muxy.app')

    def dotfiles(self, *args):
        return subprocess.run([str(self.engine), *args, '--home', str(self.home), '--repo', str(ROOT)],
                              env=self.env, capture_output=True, text=True, timeout=60)

    def converge(self, profiles):
        self.install_muxy()
        p = self.dotfiles('init', '--profiles', profiles)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        again = self.dotfiles('apply')
        self.assertEqual((again.returncode, again.stdout), (0, ''), 'a second apply changes nothing')
        doctor = self.dotfiles('doctor')
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        return (self.home / '.config/dotfiles/generated/Brewfile').read_text()

    def test_root_configs_wait_for_apply_sudo_and_the_shell_says_so(self):
        shutil.rmtree(self.system)  # a Mac before its first `apply --sudo`
        self.install_muxy()
        self.assertEqual(self.dotfiles('init', '--profiles', 'base,dev').returncode, 0)
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        claude = self.system / 'Library/Application Support/ClaudeCode/managed-settings.d/50-dotfiles.json'
        if sys.platform != 'darwin':
            claude = self.system / 'etc/claude-code/managed-settings.d/50-dotfiles.json'
        codex = self.system / 'etc/codex/config.toml'
        self.assertIn(f'problem     agents.claude.bash: missing: {claude} is missing; run `dotfiles apply --sudo`', p.stdout)
        self.assertIn(f'problem     agents.codex.bash: missing: {codex} is missing; run `dotfiles apply --sudo`', p.stdout)
        attention = self.home / '.local/state/dotfiles/attention'
        self.assertEqual(attention.read_text().count('run `dotfiles apply --sudo`'), 2)
        notice = subprocess.run(['/bin/zsh', '-fc', f'source {ROOT}/features/dotfiles.sync/zshrc.zsh'],
                                env=self.env, capture_output=True, text=True, timeout=20)
        self.assertIn('dotfiles: 2 problem(s) need you; the first: agents.claude.bash: missing', notice.stderr)

        # The test's system root is writable, so dotfiles-agents needs no sudo.
        p = self.dotfiles('apply', '--sudo')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('hook        agents.codex.bash -> missing', p.stdout)
        self.assertTrue(claude.is_file() and codex.is_file())
        self.assertFalse(attention.exists(), 'apply removes the notice once nothing needs the owner')
        self.assertEqual(self.dotfiles('doctor').returncode, 0)

        machine = self.home / '.config/dotfiles/machine.toml'
        machine.write_text(machine.read_text() + '\n[features]\ndisable = ["agents.codex.bash"]\n')
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn('problem     agents.codex.bash: turned off, and its teardown needs administrator rights; run `dotfiles apply --sudo`', p.stdout)
        self.assertTrue(codex.exists())
        p = self.dotfiles('apply', '--sudo')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('teardown    agents.codex.bash -> hooks.teardown', p.stdout)
        self.assertFalse(codex.exists())
        self.assertTrue(claude.exists())

    def test_doctor_reports_an_xdg_config_home_it_does_not_install_into(self):
        self.converge('base')
        self.env['XDG_CONFIG_HOME'] = str(self.path / 'elsewhere')
        p = self.dotfiles('doctor')
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn('problem     XDG_CONFIG_HOME', p.stdout)

    def test_apply_refuses_without_a_machine_manifest(self):
        before = sorted(self.home.rglob('*'))
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 2)
        self.assertIn('dotfiles init --profiles', p.stderr)
        self.assertEqual(sorted(self.home.rglob('*')), before, 'nothing is installed or removed')

    def test_check_plans_this_machine_without_touching_home(self):
        p = self.dotfiles('init', '--profiles', 'base,dev,desktop,server')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        before = sorted(self.home.rglob('*'))
        p = self.dotfiles('check')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(sorted(self.home.rglob('*')), before, 'check reads and writes nothing under home')
        machine = self.home / '.config/dotfiles/machine.toml'
        machine.write_text(machine.read_text() + '[features]\nenable = ["no.such-feature"]\n')
        p = self.dotfiles('check')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn('no.such-feature', p.stderr)

    def test_a_machine_overrides_a_shared_muxy_setting_and_says_where_it_comes_from(self):
        self.install_muxy()
        p = self.dotfiles('init', '--profiles', 'base,desktop')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        machine = self.home / '.config/dotfiles/machine.toml'
        manifest = machine.read_text()
        machine.write_text(manifest + '\n[prefs]\n"muxy:terminal.font_size" = 13.0 # the small screen\n')

        check = self.dotfiles('check')
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn('app setting: muxy:terminal.font_size = 13.0, from machine (tool.muxy shares 14.0)\n', check.stdout)
        self.assertIn('app setting: muxy:appearance.dark_theme = "Dracula", from tool.muxy\n', check.stdout)
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(json.loads(self.muxy_settings.read_text())['terminal.font_size'], 13.0)
        doctor = self.dotfiles('doctor')
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        self.assertIn('app-setting muxy:terminal.font_size = 13.0, from machine (tool.muxy shares 14.0)\n', doctor.stdout)
        status = self.dotfiles('status')
        self.assertRegex(status.stdout, r'muxy:terminal\.font_size +13\.0 +machine \(tool\.muxy shares 14\.0\)')
        rows = {r['id']: r for r in json.loads(self.dotfiles('status', '--json').stdout)['prefs']}
        self.assertEqual(rows['muxy:terminal.font_size'], {'id': 'muxy:terminal.font_size', 'value': 13.0,
                                                           'set_by': 'machine', 'feature': 'tool.muxy', 'shared': 14.0})
        self.assertEqual(rows['muxy:appearance.dark_theme']['set_by'], 'tool.muxy')

        machine.write_text(manifest + '\n[prefs]\n"muxy:terminal.font_size" = 12.0\n')
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('update-pref muxy:terminal.font_size', p.stdout)
        self.assertEqual(json.loads(self.muxy_settings.read_text())['terminal.font_size'], 12.0)

        machine.write_text(manifest)
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(json.loads(self.muxy_settings.read_text())['terminal.font_size'], 14.0, 'back to the shared value')

        machine.write_text(manifest + '\n[prefs]\n"muxy:terminal.font_siz" = 13.0\n')
        p = self.dotfiles('check')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn('[prefs] "muxy:terminal.font_siz": no feature owns this setting', p.stderr)
        status = self.dotfiles('status')
        self.assertEqual(status.returncode, 2, 'status reports the plan error')
        self.assertIn('tool.muxy', status.stdout, 'after showing what it can')
        self.assertIn('no feature owns this setting', status.stderr)

        # An override for a feature turned off here changes nothing and fails nothing.
        machine.write_text(manifest + '\n[features]\ndisable = ["tool.muxy"]\n\n[prefs]\n"muxy:terminal.font_size" = 13.0\n')
        check = self.dotfiles('check')
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn(f'note: muxy:terminal.font_size: {machine} [prefs] sets it, but tool.muxy, which owns it, is off here, so it is ignored\n',
                      check.stdout)

        machine.write_text(manifest + '\n[features]\ndisable = ["tool.muxy"]\n')
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(json.loads(self.muxy_settings.read_text()), {'appearance.dark_theme': 'Muxy', 'appearance.layout': 'project_focused'},
                         'teardown puts back what Muxy had before dotfiles')

    def forget(self, *ids):
        # Flags go before the settings named.
        return subprocess.run([str(self.engine), 'forget', '--home', str(self.home), '--repo', str(ROOT), *ids],
                              env=self.env, capture_output=True, text=True, timeout=60)

    def test_an_uninstalled_muxy_keeps_its_earlier_values_until_forgotten(self):
        self.install_muxy()
        p = self.dotfiles('init', '--profiles', 'base,desktop')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.dotfiles('apply').returncode, 0)
        p = self.forget('muxy:appearance.dark_theme')
        self.assertEqual(p.returncode, 64, 'tool.muxy still owns it')

        shutil.rmtree(self.home / 'Applications/Muxy.app')  # uninstalled
        machine = self.home / '.config/dotfiles/machine.toml'
        machine.write_text(machine.read_text() + '\n[features]\ndisable = ["tool.muxy"]\n')
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, 'an app that is not there is no failure: ' + p.stdout + p.stderr)
        doctor = self.dotfiles('doctor')
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        self.assertIn('waiting     muxy:appearance.dark_theme: app not available', doctor.stdout)
        self.assertIn('its value from before dotfiles, "Muxy", waits to be put back', doctor.stdout)

        p = self.forget('muxy:appearance.dark_theme')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(p.stdout, 'forget-pref muxy:appearance.dark_theme -> before dotfiles set it, it was "Muxy"\n')
        doctor = self.dotfiles('doctor')
        self.assertNotIn('muxy:appearance.dark_theme', doctor.stdout)
        self.assertIn('waiting     muxy:terminal.font_size', doctor.stdout, 'the others still wait')

    def test_a_desktop_machine_gets_a_working_shell_git_and_ssh(self):
        brewfile = self.converge('base,dev,desktop,server')
        self.assertIn('cask "', brewfile)
        self.assertIn('vscode "', brewfile)
        self.assertIn('cask "muxy" # tool.muxy', brewfile)
        shared = tomllib.loads((FEATURES / 'tool.muxy/muxy.toml').read_text())
        self.assertEqual(json.loads(self.muxy_settings.read_text()), shared | {'appearance.layout': 'project_focused'},
                         'the shared Muxy settings are set, and the rest of Muxy is left alone')
        if sys.platform == 'darwin':
            karabiner = self.home / '.config/karabiner/karabiner.json'
            self.assertTrue(karabiner.is_file() and not karabiner.is_symlink(),
                            'Karabiner replaces karabiner.json when it saves, so the file is a copy')
        for stub in ('.zshenv', '.zprofile', '.zshrc', '.zlogin', '.bashrc', '.bash_profile', '.gitconfig', '.ssh/config'):
            self.assertFalse((self.home / stub).is_symlink(), stub + ' is a local stub')
        self.assertTrue((self.home / '.config/zsh/00-init.zsh').is_symlink())
        self.assertFalse((self.home / '.config/zsh').is_symlink(), 'no directory is linked')
        env = {'HOME': str(self.home), 'PATH': '/usr/bin:/bin', 'XDG_CONFIG_HOME': str(self.home / '.config')}
        p = subprocess.run(['/bin/zsh', '-lc', 'print -rn -- $PATH'], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(p.stdout.startswith(str(self.home / '.local/bin') + ':'), p.stdout)
        (self.home / '.gitconfig.local').write_text('[user]\n\temail = machine@example.invalid\n')
        p = subprocess.run(['git', 'config', '--get', 'user.email'], cwd=self.home, env=env,
                           capture_output=True, text=True)
        self.assertEqual(p.stdout.strip(), 'machine@example.invalid', 'the machine-local file wins')
        with open(self.home / '.ssh/config', 'a') as f:
            f.write('Host appended.invalid\n    ControlMaster no\n')
        def ssh_option(host, option):
            p = subprocess.run(['/usr/bin/ssh', '-G', '-F', str(self.home / '.ssh/config'), host],
                               env=env, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            return dict(line.split(' ', 1) for line in p.stdout.splitlines())[option]
        self.assertEqual(ssh_option('example.invalid', 'controlmaster'), 'auto', 'the shared defaults apply')
        self.assertEqual(ssh_option('appended.invalid', 'controlmaster'), 'false',
                         'a host an installer appends to ~/.ssh/config wins over the defaults')

    def test_a_dev_machine_gets_the_agent_launchers_subagents_and_guard(self):
        self.converge('base,dev')
        for rel in ('.claude/agents/scout.md', '.claude/agents/reader.md', '.codex/agents/scout.toml',
                    '.codex/agents/reader.toml', '.config/agent-delegation/policy.md', '.claude/statusline-p10k.sh',
                    '.claude/skills/repo-guard/.claude-plugin/plugin.json', '.claude/skills/repo-guard/hooks/hooks.json',
                    '.claude/mcp/github-headers.sh', '.local/bin/repo-guard', '.local/bin/claude-subagent-economics'):
            self.assertTrue((self.home / rel).is_symlink(), rel)
        self.assertFalse((self.home / '.claude/skills/repo-guard').is_symlink(), 'linked file by file')
        self.assertFalse((self.home / '.config/repo-guard').exists(), 'the protected lists come from overlays')
        launchers = 'claudemore claudemax' + (' gptmore gptmax' if sys.platform == 'darwin' else '')
        p = subprocess.run(['/bin/zsh', '-fc', f'source {self.home}/.config/dotfiles/generated/zshrc.zsh; whence -w {launchers}'],
                           env={'HOME': str(self.home), 'PATH': '/usr/bin:/bin'}, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(p.stdout.count(': function'), len(launchers.split()), p.stdout)

    def test_a_host_profile_sets_its_values(self):
        self.converge('base,dev,desktop,studio')
        env = (self.home / '.config/dotfiles/generated/env.sh').read_text()
        self.assertIn("PLAYWRIGHT_BROWSERS_PATH='/Volumes/E2TB/cache/ms-playwright'", env)
        self.assertIn("GO_EXTRA_BUILD_CACHES='/Volumes/E2TB2/cache/go/build'", env)

    def agent(self, label):
        return self.home / 'Library/LaunchAgents' / f'{label}.plist'

    def test_every_mac_runs_the_sync_and_update_jobs(self):
        self.converge('base')
        for label in ('com.dotfiles.sync', 'com.dotfiles.update', 'com.ashtonian.disk-hygiene'):
            installed = self.agent(label).read_text()
            self.assertIn(f'<string>{self.home}/.dotfiles/', installed, '$HOME is this home')
            self.assertNotIn('$HOME', installed)
            self.assertEqual((self.launchd / label).read_text(), installed, label + ' is loaded from it')
        self.assertTrue((self.home / 'Library/Logs/disk-hygiene').is_dir(), 'launchd does not create log directories')
        self.assertFalse(self.agent('com.ashtonian.codex-remote-control').exists(), 'agents.codex is a dev feature')

    def test_an_agent_waits_for_its_setup_and_goes_with_it(self):
        self.converge('base,dev,desktop')
        enrolled = self.home / '.local/share/otel-agent'
        doctor = self.dotfiles('doctor')
        self.assertIn(f'waiting     com.ashtonian.otel-agent: installs once {enrolled}/endpoint exists', doctor.stdout)
        self.assertFalse(self.agent('com.ashtonian.otel-agent').exists())

        enrolled.mkdir(parents=True)
        for name in ('endpoint', 'token', 'host'):
            (enrolled / name).write_text('x\n')
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('load        ' + str(self.agent('com.ashtonian.otel-agent')), p.stdout)
        self.assertTrue((self.launchd / 'com.ashtonian.otel-agent').exists())

        (enrolled / 'host').unlink()
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse(self.agent('com.ashtonian.otel-agent').exists())
        self.assertFalse((self.launchd / 'com.ashtonian.otel-agent').exists(), 'unloaded too')

    @unittest.skipUnless(sys.platform == 'darwin', 'tool.muxy is a macOS feature')
    def test_a_desktop_mac_gets_muxy_from_the_app_and_its_server_list_job(self):
        brewfile = self.converge('base,dev,desktop')  # with the stand-in Muxy
        self.assertIn('brew "python" # tool.muxy', brewfile, 'muxy-reconcile needs tomllib')
        for name in ('muxy', 'muxy-reconcile'):
            link = self.home / '.local/bin' / name
            self.assertEqual(link.resolve(), FEATURES / 'tool.muxy/home/.local/bin' / name)
        label = 'com.ashtonian.muxy-reconcile'
        ready = Path('/Applications/Muxy.app').exists() and Path('/opt/homebrew/bin/python3').exists()
        if ready:
            installed = self.agent(label).read_text()
            self.assertIn(f'<string>{self.home}/.local/bin/muxy-reconcile</string>', installed)
            self.assertIn(f'<string>{self.home}/.config/muxy/servers.d</string>', installed)
            self.assertTrue((self.launchd / label).exists(), 'loaded')
            self.assertTrue((self.home / 'Library/Logs/muxy-reconcile').is_dir())
        else:
            self.assertFalse(self.agent(label).exists(), 'it waits for the app and python3')
            self.assertIn(f'waiting     {label}: installs once', self.dotfiles('doctor').stdout)

        env_sh = self.home / '.config/dotfiles/generated/env.sh'
        self.assertIn("MUXY_RECONCILE_MODE='report'; export MUXY_RECONCILE_MODE # muxy.reconcile", env_sh.read_text(),
                      'every Mac only reports until its machine.toml says apply')
        machine = self.home / '.config/dotfiles/machine.toml'
        manifest = machine.read_text()
        self.assertNotIn('[settings]', manifest)
        machine.write_text(manifest + '\n[settings]\n"muxy.reconcile" = "aply"\n')
        check = self.dotfiles('check')
        self.assertEqual(check.returncode, 2, check.stdout + check.stderr)
        self.assertIn('setting "muxy.reconcile": want one of report, apply, got "aply"', check.stderr)
        machine.write_text(manifest + '\n[settings]\n"muxy.reconcile" = "apply"\n')
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("MUXY_RECONCILE_MODE='apply'", env_sh.read_text())

    @unittest.skipUnless(sys.platform == 'darwin', 'tool.muxy is a macOS feature')
    def test_a_muxy_installed_by_muxy_is_left_alone_while_its_server_copy_is_there(self):
        # What Muxy's "Install muxy-server" leaves: its own copy, which a
        # running muxy-server executes from, and a link into it.
        copy = self.home / '.local/bin/.muxy'
        own = copy / 'pair-2.1.0.abcdef/muxy'
        own.parent.mkdir(parents=True)
        own.write_text('#!/bin/sh\n')
        (copy / 'current').symlink_to('pair-2.1.0.abcdef')
        link = self.home / '.local/bin/muxy'
        link.symlink_to('.muxy/current/muxy')
        held = f'waiting     {link}: left alone while {copy} exists\n'
        self.install_muxy()

        p = self.dotfiles('init', '--profiles', 'base,dev,desktop')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(os.readlink(link), '.muxy/current/muxy', 'left as it was')
        self.assertEqual(own.read_text(), '#!/bin/sh\n')
        self.assertTrue((self.home / '.local/bin/muxy-reconcile').is_symlink(), 'the rest of the feature applies')
        doctor = self.dotfiles('doctor')
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        self.assertIn(held, doctor.stdout)

        # Even with the link gone, its place stays empty while the copy is there.
        link.unlink()
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse(link.exists() or link.is_symlink())

        # After a planned server restart the copy is moved aside, and apply links the wrapper.
        copy.rename(self.path / 'muxy-server-copy')
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(link.resolve(), FEATURES / 'tool.muxy/home/.local/bin/muxy')

    def test_apply_takes_over_the_retired_installers_agents(self):
        stale = '<?xml version="1.0"?>\n<plist version="1.0"><dict><key>Label</key><string>{}</string></dict></plist>\n'
        self.agent('x').parent.mkdir(parents=True)
        for label in ('com.dotfiles.sync', 'com.ashtonian.codex-remote-control'):
            self.agent(label).write_text(stale.format(label))
            self.loaded(label)
        p = self.dotfiles('init', '--profiles', 'base')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('<key>StartInterval</key>', self.agent('com.dotfiles.sync').read_text())
        self.assertIn('<key>StartInterval</key>', (self.launchd / 'com.dotfiles.sync').read_text(), 'reloaded')
        self.assertFalse(self.agent('com.ashtonian.codex-remote-control').exists(), 'its feature is off here')
        self.assertFalse((self.launchd / 'com.ashtonian.codex-remote-control').exists())

    def test_the_work_machine_gets_dev_apps_and_nothing_personal(self):
        brewfile = self.converge('base,dev,work')
        self.assertIn('cask "orbstack"', brewfile)
        self.assertIn('cask "slack"', brewfile, 'applications for any desk reach the work machine')
        for general in ('mas "Okta Verify"', 'mas "Monosnap"'):
            self.assertIn(general, brewfile)
        for personal in ('cask "spotify"', 'cask "steam"', 'mas "Day One"', 'wakatime', 'rescuetime'):
            self.assertNotIn(personal, brewfile)
        for home_cluster in ('.config/opencode/opencode.jsonc', '.config/otel-agent/config.yaml'):
            self.assertFalse((self.home / home_cluster).exists(), home_cluster)
        self.assertFalse((self.home / '.mackup.cfg').exists())
        self.assertTrue((self.home / '.claude/CLAUDE.md').is_symlink(), 'dev features are on')
        self.assertEqual(json.loads(self.muxy_settings.read_text())['appearance.dark_theme'], 'Muxy',
                         'Muxy is a desktop feature')

    def test_claude_code_keeps_its_own_settings_and_takes_the_theme(self):
        settings = self.home / '.claude/settings.json'
        settings.parent.mkdir()
        settings.write_text('{\n  "hooks": {\n    "Stop": []\n  },\n  "theme": "dark-ansi"\n}\n')
        self.converge('base,dev')
        shared = tomllib.loads((FEATURES / 'agents.claude/claude.toml').read_text())
        self.assertEqual(json.loads(settings.read_text()), {'hooks': {'Stop': []}, 'theme': 'custom:dracula'} | shared,
                         "the shared keys are set and the machine's own hooks stay")
        self.assertTrue(settings.read_text().startswith('{\n  "hooks": {\n    "Stop": []\n  },\n  "theme": "custom:dracula",\n'),
                        'keys already there keep their order and formatting')
        theme = self.home / '.claude/themes/dracula.json'
        self.assertFalse(theme.is_symlink(), 'Claude Code rewrites its themes, so the theme is a managed copy')
        self.assertEqual(json.loads(theme.read_text())['name'], 'Dracula')

        machine = self.home / '.config/dotfiles/machine.toml'
        machine.write_text(machine.read_text() + '[features]\ndisable = ["agents.claude.theme"]\n')
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('restore-pref claude:theme -> "dark-ansi"', p.stdout)
        self.assertEqual(json.loads(settings.read_text())['theme'], 'dark-ansi', 'disabling it puts back what was there')
        self.assertFalse(theme.exists())


class Install(Fixture):
    """install.sh piped into bash, as `curl ... | bash -s -- ...` runs it, with no terminal for prompts."""

    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        dotfiles = self.home / '.dotfiles'
        (dotfiles / '.git').mkdir(parents=True)
        for theme in ('colorls',):
            (self.home / '.sync' / theme).mkdir(parents=True)
        (dotfiles / 'profiles').mkdir()
        (dotfiles / 'profiles/base.toml').write_text('# Every machine.\n')
        self.audit = self.path / 'audit'
        sync = dotfiles / 'sync.sh'
        sync.write_text('#!/bin/sh\nprintf "sync.sh %s\\n" "$*" >> "$DOTFILES_TEST_AUDIT"\n')
        sync.chmod(0o755)
        for tool in ('sudo', 'xcode-select', 'brew', 'git', 'go', 'dotfiles'):
            self.cli(tool, f'printf "{tool} %s\\n" "$*" >> "$DOTFILES_TEST_AUDIT"')
        self.machine = self.home / '.config/dotfiles/machine.toml'
        self.env.update(HOME=str(self.home), DOTFILES_TEST_AUDIT=str(self.audit),
                        DOTFILES_BIN=str(self.bin / 'dotfiles'))
        self.env.pop('XDG_CONFIG_HOME', None)
        self.env.pop('DOTFILES_PROFILES', None)

    def install(self, *args):
        return subprocess.run(['/bin/bash', '-s', '--', *args], input=(ROOT / 'install.sh').read_text(),
                              cwd=self.path, env=self.env, capture_output=True, text=True, timeout=60,
                              start_new_session=True)

    def test_installs_through_the_engine(self):
        p = self.install('--profiles', 'base,dev')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('Installation complete', p.stdout)
        steps = [line for line in self.audit.read_text().splitlines()
                 if line.startswith(('sync.sh', 'dotfiles'))]
        # The LaunchAgents load last: the sync job runs at load, and would take
        # the sync lock from the package steps.
        self.assertEqual(steps, ['sync.sh build',
                                 f'dotfiles init --repo {self.home}/.dotfiles --profiles base,dev',
                                 f'dotfiles apply --repo {self.home}/.dotfiles --launch-agents=false',
                                 'sync.sh brewfile', 'sync.sh mise', 'sync.sh github-mcp', 'sync.sh apply'])
        self.assertNotIn('stow', self.audit.read_text())

    def test_keeps_an_existing_machine_manifest(self):
        self.machine.parent.mkdir(parents=True)
        self.machine.write_text('profiles = ["base"]\n')
        p = self.install()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn('dotfiles init', self.audit.read_text())
        self.assertIn('sync.sh apply', self.audit.read_text())

    def test_without_profiles_or_a_terminal_it_stops_before_installing(self):
        p = self.install()
        self.assertEqual(p.returncode, 64, p.stdout + p.stderr)
        self.assertIn('--profiles', p.stdout)
        self.assertNotIn('sync.sh', self.audit.read_text() if self.audit.exists() else '')


@unittest.skipUnless(sys.platform == 'darwin', 'APFS clones and codesign are macOS-only')
class StableExec(Fixture):
    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        self.home.mkdir()
        self.prefix = self.path / 'homebrew'
        (self.prefix / 'bin').mkdir(parents=True)
        self.env.update(HOME=str(self.home), HOMEBREW_PREFIX=str(self.prefix))
        self.cli('codesign', 'exit "${DOTFILES_TEST_CODESIGN:-0}"')
        self.libexec = self.home / '.local/libexec'

    def executable(self, path):
        path.parent.mkdir(parents=True)
        path.write_text('#!/bin/sh\necho "ran $*"\n')
        path.chmod(0o755)

    def release(self):
        self.executable(self.prefix / 'Cellar/fixture/1.0/bin/fixture')
        (self.prefix / 'bin/fixture').symlink_to('../Cellar/fixture/1.0/bin/fixture')

    def run_stable(self, *args):
        return subprocess.run(['/bin/zsh', '-f', str(ROOT / 'bin/stable-exec'), *args], cwd=self.path,
                              env=self.env, capture_output=True, text=True, timeout=20)

    def test_missing_tool_is_unavailable_and_copies_nothing(self):
        p = self.run_stable('fixture')
        self.assertEqual(p.returncode, 69, p.stderr)
        self.assertFalse(self.libexec.exists())

    def test_link_outside_a_release_is_refused(self):
        self.executable(self.prefix / 'opt/fixture/bin/fixture')
        (self.prefix / 'bin/fixture').symlink_to(self.prefix / 'opt/fixture/bin/fixture')
        p = self.run_stable('fixture')
        self.assertEqual(p.returncode, 69, p.stderr)
        self.assertFalse(self.libexec.exists())

    def test_release_runs_from_the_stable_copy(self):
        self.release()
        p = self.run_stable('fixture', 'a', 'b')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), 'ran a b')
        self.assertTrue((self.libexec / 'fixture-stable/bin/fixture').exists())

    def test_failed_signature_check_leaves_no_partial_copy(self):
        self.release()
        self.env['DOTFILES_TEST_CODESIGN'] = '1'
        p = self.run_stable('fixture')
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse((self.libexec / 'fixture-stable').exists())
        self.assertEqual([c.name for c in self.libexec.iterdir() if '.new.' in c.name], [])


class OpencodeHomelab(Fixture):
    @unittest.skipUnless(shutil.which('bun'), 'Bun required for OpenCode plugins')
    def test_credentials_stay_with_the_enrolled_gateway(self):
        settings = self.path / '.local/share/opencode/homelab'
        settings.mkdir(parents=True)
        (settings / 'base-url').write_text('http://fixture.local/v1\n')
        plugin = FEATURES / 'agents.opencode/home/.config/opencode/plugins/homelab.ts'
        script = """
import { Homelab } from 'PLUGIN'
import { strict as assert } from 'node:assert'
import { writeFile } from 'node:fs/promises'
const hook = await Homelab()
async function provider(options) {
  const config = {provider: {homelab: {options, models: {local: {}}}}}
  await hook.config(config)
  return config.provider.homelab
}
assert.equal(await provider({}), undefined)
await writeFile(process.env.HOME + '/.local/share/opencode/homelab/litellm.key', 'fixture-key\\n')
const enrolled = await provider({headerTimeout: 42})
assert.deepEqual(enrolled.options, {headerTimeout: 42, baseURL: 'http://fixture.local/v1', apiKey: 'fixture-key'})
assert.ok(enrolled.models.local)
assert.equal(await provider({baseURL: 'https://other.invalid'}), undefined)
const custom = {baseURL: 'https://other.invalid', apiKey: 'other-key'}
assert.deepEqual((await provider(custom)).options, custom)
""".replace('PLUGIN', plugin.as_posix())
        subprocess.run(['bun', '-e', script], cwd=self.path, env=dict(self.env, HOME=str(self.path)),
                       check=True, timeout=15)


class OpencodeServer(Fixture):
    def run_server(self, **overrides):
        home = self.path / 'home'
        password = home / '.local/share/opencode/homelab/server-password'
        password.parent.mkdir(parents=True, exist_ok=True)
        password.write_text('fixture')
        bin_dir = self.path / 'server-bin'
        bin_dir.mkdir(exist_ok=True)
        shutil.copy(ROOT / 'bin/opencode-server', bin_dir)
        (bin_dir / 'stable-exec').write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
        (bin_dir / 'stable-exec').chmod(0o755)
        env = dict(self.env, HOME=str(home))
        env.pop('OPENCODE_HOSTNAME', None)
        env.update(overrides)
        p = subprocess.run(['/bin/zsh', '-f', str(bin_dir / 'opencode-server')], cwd=self.path, env=env,
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        args = p.stdout.split()
        return args[args.index('--hostname') + 1]

    def test_listens_on_loopback_unless_told_otherwise(self):
        self.assertEqual(self.run_server(), '127.0.0.1')
        self.assertEqual(self.run_server(OPENCODE_HOSTNAME='192.0.2.10'), '192.0.2.10')


MOCK_GIT = r'''
git() {
    printf 'git %s\n' "$*" >> "$DOTFILES_TEST_AUDIT"
    case "$1" in
      rev-parse)
        case "${2:-}" in
          --git-dir) echo .git ;;
          --git-path) printf '%s/.git/%s\n' "$DOTFILES_DIR" "$3" ;;
          --abbrev-ref) echo origin/master ;;
          HEAD) if [[ -f "$DOTFILES_DIR/committed" ]]; then echo fixture-new; else echo fixture-old; fi ;;
          *) echo fixture-old ;;
        esac ;;
      symbolic-ref) echo master ;;
      ls-files) return 0 ;;
      cat-file) return 1 ;;  # upstream has the fixture's own layout, without features/
      config)
        case "$3" in
          user.name) echo Fixture ;;
          user.email) echo fixture@example.com ;;
          user.signingkey) echo EXAMPLE_KEY ;;
          gpg.program) echo /usr/bin/true ;;
          commit.gpgsign) echo true ;;
        esac ;;
      remote) echo https://github.com/example/dotfiles.git ;;
      status) [[ -f "$DOTFILES_DIR/committed" ]] || echo ' M fixture' ;;
      diff) return 1 ;;
      commit) [[ "$DOTFILES_TEST_FAILURE" != commit ]] || return 8; touch "$DOTFILES_DIR/committed" ;;
      verify-commit) [[ "$DOTFILES_TEST_FAILURE" != verify ]] ;;
      merge) [[ "${2:-}" == --abort || "$DOTFILES_TEST_FAILURE" != merge ]] ;;
      rev-list) echo fixture-new ;;
      *) return 0 ;;
    esac
}
gitleaks() {
    printf 'gitleaks %s\n' "$*" >> "$DOTFILES_TEST_AUDIT"
    [[ "$DOTFILES_TEST_FAILURE" != scan ]]
}
gh() {
    printf 'gh %s\n' "$*" >> "$DOTFILES_TEST_AUDIT"
    if [[ "$DOTFILES_TEST_FAILURE" == github ]]; then echo bad_email; else echo verified; fi
}
sleep() { :; }
'''


# Where OpenCode installed the plugin's dependencies: its config directory on a
# machine that runs it, or DOTFILES_TEST_OPENCODE_DEPS (a directory holding
# node_modules/@opencode-ai/plugin).
OPENCODE_DEPS = Path(os.environ.get('DOTFILES_TEST_OPENCODE_DEPS', Path.home() / '.config/opencode'))


class Delegate(Fixture):
    def worker_args(self, access):
        if not shutil.which('bun'):
            self.skipTest('Bun required')
        if not (OPENCODE_DEPS / 'node_modules/@opencode-ai/plugin').is_dir():
            self.skipTest('OpenCode plugin dependencies required')
        # The plugin as apply installs it: linked into a config directory that
        # holds OpenCode's node_modules.
        config = self.path / 'opencode'
        (config / 'plugins').mkdir(parents=True)
        (config / 'node_modules').symlink_to(OPENCODE_DEPS / 'node_modules')
        (config / 'plugins/delegate.ts').symlink_to(FEATURES / 'agents.opencode/home/.config/opencode/plugins/delegate.ts')
        self.env['DELEGATE_STATE_DIR'] = str(self.path / 'jobs-state')
        self.env['DELEGATE_POLL_MS'] = '60000'
        worker = self.bin / 'fake-claude'
        worker.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
pathlib.Path(os.environ['DELEGATE_JOB_DIR'], 'argv.json').write_text(json.dumps(sys.argv[1:]))
print(json.dumps({'type':'result','session_id':'fixture-session','result':'fixture complete','is_error':False}))
''')
        worker.chmod(0o755)
        self.env['DELEGATE_CLAUDE_BIN'] = str(worker)
        # Read jobs must never ask for write approval; write jobs are approved.
        ask = 'async()=>{throw Error("unexpected write approval")}' if access == 'read' else 'async()=>({})'
        harness = self.path / 'delegate.ts'
        harness.write_text('''
const {DelegatePlugin} = await import(process.env.DELEGATE_PLUGIN);
const {existsSync, readFileSync} = await import('node:fs');
const {join} = await import('node:path');
const hooks = await DelegatePlugin({client:{app:{log:async()=>({})},session:{promptAsync:async()=>({})}}});
const context = {sessionID:'fixture-owner',agent:'coordinator',directory:process.cwd(),ask:ASK};
const result = await hooks.tool.delegate_start.execute({worker:'claude',title:'fixture',task:'Fixture task',access:'ACCESS',cwd:process.cwd()},context);
const job = result.metadata.job;
const dir = join(process.env.DELEGATE_STATE_DIR,'jobs',job);
for (let i=0;i<100 && !existsSync(join(dir,'exit'));i++) await Bun.sleep(20);
if (!existsSync(join(dir,'exit'))) throw Error('worker did not exit');
process.stdout.write(readFileSync(join(dir,'argv.json'),'utf8'));
'''.replace('ASK', ask).replace('ACCESS', access))
        self.env['DELEGATE_PLUGIN'] = str(config / 'plugins/delegate.ts')
        p = subprocess.run(['bun', str(harness)], cwd=self.path, env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return json.loads(p.stdout)

    def test_read_worker_exposes_only_read_tools(self):
        args = self.worker_args('read')
        self.assertIn('--restricted', args)
        self.assertEqual(args[args.index('--tools') + 1], 'Read,Glob,Grep')
        self.assertIn('--strict-mcp-config', args)
        self.assertEqual(json.loads(args[args.index('--mcp-config') + 1]), {'mcpServers': {}})
        self.assertNotIn('--dangerously-skip-permissions', args)

    def test_write_worker_runs_like_claudemore_with_subagents(self):
        args = self.worker_args('write')
        self.assertIn('--dangerously-skip-permissions', args)
        self.assertEqual(args[args.index('--permission-mode') + 1], 'bypassPermissions')
        self.assertNotIn('--disallowedTools', args)
        self.assertNotIn('--restricted', args)

class SharedEnvironment(Fixture):
    BREW_BIN = '/opt/homebrew/bin'

    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        for d in ('bin', '.local/bin'):
            (self.home / d).mkdir(parents=True)
        install_shell(self.home, {'.zshenv', '.zprofile', '.bashrc', '.bash_profile'})

    def path_of(self, *argv):
        env = {'HOME': str(self.home), 'PATH': '/usr/bin:/bin', 'TMPDIR': str(self.path)}
        p = subprocess.run([*argv], cwd=self.path, env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip().split(':')

    def assert_order(self, path):
        self.assertEqual(path[:2], [str(self.home / 'bin'), str(self.home / '.local/bin')])
        self.assertIn('/usr/bin', path)
        self.assertEqual(len(path), len(set(path)), 'duplicate PATH entries')
        if Path(self.BREW_BIN).is_dir():
            self.assertLess(path.index(self.BREW_BIN), path.index('/usr/bin'))

    def test_builds_path_from_an_empty_environment(self):
        self.assert_order(self.path_of('/bin/sh', '-c', '. "$HOME/.config/shell/env.sh"; printf %s "$PATH"'))

    def test_is_idempotent(self):
        once = self.path_of('/bin/sh', '-c', '. "$HOME/.config/shell/env.sh"; printf %s "$PATH"')
        twice = self.path_of('/bin/sh', '-c', '. "$HOME/.config/shell/env.sh"; . "$HOME/.config/shell/env.sh"; printf %s "$PATH"')
        self.assertEqual(once, twice)

    def test_login_zsh_keeps_the_order_after_path_helper(self):
        self.assert_order(self.path_of('/bin/zsh', '-l', '-c', 'print -rn -- $PATH'))

    def test_native_zsh_with_nomatch_can_source_it(self):
        # Claude Code prepends CLAUDE_ENV_FILE to commands in sessions still on zsh.
        self.assert_order(self.path_of('/bin/zsh', '-f', '-c',
                                       'setopt NOMATCH; source "$HOME/.config/shell/env.sh" && print -rn -- $PATH'))

    def test_bashrc_reads_the_shared_environment(self):
        self.assert_order(self.path_of('/bin/bash', '-c', '. "$HOME/.bashrc"; printf %s "$PATH"'))

    def test_nested_shell_keeps_a_directory_a_command_put_first(self):
        venv = self.path / 'venv/bin'
        venv.mkdir(parents=True)
        path = self.path_of('/bin/sh', '-c', '. "$HOME/.config/shell/env.sh"; PATH="$1:$PATH"; '
                            '/bin/zsh -c \'print -rn -- $PATH\'', 'sh', str(venv))
        self.assertEqual(path[0], str(venv))

    def venv_first(self, shell_command, *argv):
        """PATH as composed, then a virtualenv activated in front, then shell_command."""
        venv = self.path / 'venv/bin'
        venv.mkdir(parents=True, exist_ok=True)
        return venv, self.path_of('/bin/sh', '-c', '. "$HOME/.config/shell/env.sh"; PATH="$1:$PATH"; shift; '
                                  + shell_command, 'sh', str(venv), *argv)

    def test_login_shells_keep_a_virtualenv_first_after_path_helper(self):
        shells = [['/bin/zsh', '-lc', 'print -rn -- $PATH']]
        # Debian's /etc/profile replaces PATH in login bash before any file of
        # ours runs; macOS's path_helper keeps what the shell inherited.
        if sys.platform == 'darwin':
            shells.append(['/bin/bash', '-lc', 'printf %s "$PATH"'])
        for shell in shells:
            venv, path = self.venv_first('exec "$@"', *shell)
            self.assertEqual(path[0], str(venv), shell[0])
            self.assertEqual(path[1:3], [str(self.home / 'bin'), str(self.home / '.local/bin')], shell[0])

    def test_shells_nested_in_a_recomposed_one_keep_a_virtualenv_first(self):
        # A login zsh composes PATH again after path_helper; a shell it starts
        # sources env.sh once more.
        nested = self.path / 'nested.zsh'
        nested.write_text('/bin/sh -c \'. "$HOME/.config/shell/env.sh"; exec /bin/zsh -c "print -rn -- \\$PATH"\'\n')
        venv, path = self.venv_first('exec /bin/zsh -l "$1"', str(nested))
        self.assertEqual(path[0], str(venv))

    def test_a_virtualenv_stays_first_when_mise_drops_its_shims(self):
        shims = self.home / '.local/share/mise/shims'
        installs = self.home / '.local/share/mise/installs/node/24/bin'
        for d in (shims, installs):
            d.mkdir(parents=True)
        # mise's prompt hook takes its shims out of PATH and puts the tool
        # directories in front, then a nested shell starts.
        venv, path = self.venv_first('PATH=$(printf %s "$PATH" | tr : "\\n" | grep -vx "$1" | paste -sd: -); '
                                     'PATH="$2:$PATH"; exec /bin/zsh -c \'print -rn -- $PATH\'', str(shims), str(installs))
        self.assertEqual(path[0], str(venv))
        self.assertIn(str(shims), path, 'the nested shell gets the shims back')
        self.assertNotIn(str(installs), path[:3])

    def test_editor_is_chosen_on_the_composed_path(self):
        self.cli('nvim', 'exit 0')
        (self.home / '.local/bin/nvim').symlink_to(self.bin / 'nvim')
        env = {'HOME': str(self.home), 'PATH': '/usr/bin:/bin', 'TMPDIR': str(self.path)}
        p = subprocess.run(['/bin/sh', '-c', '. "$HOME/.config/shell/env.sh"; printf %s "$EDITOR"'],
                           env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.stdout, 'nvim')

    def test_sourcing_under_errexit_survives_a_missing_generated_file(self):
        env = {'HOME': str(self.home), 'PATH': '/usr/bin:/bin', 'TMPDIR': str(self.path)}
        for sh in ('/bin/sh', '/bin/dash', '/bin/bash'):
            if Path(sh).exists():
                p = subprocess.run([sh, '-ec', '. "$HOME/.config/shell/env.sh"; echo survived'],
                                   env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(p.stdout.strip(), 'survived', sh)

    def test_bash_drops_the_agent_shell_marker(self):
        env = {'HOME': str(self.home), 'PATH': '/usr/bin:/bin', 'TMPDIR': str(self.path), 'AGENT_SHELL': 'codex'}
        p = subprocess.run(['/bin/bash', '-c', '. "$HOME/.bashrc"; printf %s "${AGENT_SHELL-unset}"'],
                           env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.stdout, 'unset', 'a zsh this bash starts must not hand off to bash')

    def test_mise_shims_sit_below_the_users_own_bins(self):
        shims = self.home / '.local/share/mise/shims'
        shims.mkdir(parents=True)
        path = self.path_of('/bin/sh', '-c', '. "$HOME/.config/shell/env.sh"; printf %s "$PATH"')
        self.assertLess(path.index(str(self.home / '.local/bin')), path.index(str(shims)))
        self.assertLess(path.index(str(shims)), path.index('/usr/bin'))

    def test_a_reset_path_is_composed_again(self):
        self.assert_order(self.path_of('/bin/sh', '-c', '. "$HOME/.config/shell/env.sh"; PATH=/usr/bin:/bin; '
                                       '. "$HOME/.config/shell/env.sh"; printf %s "$PATH"'))


def current_bash():
    """A bash 4 or later the .zshenv hand-off would pick, or None."""
    for candidate in ('/opt/homebrew/bin/bash', '/usr/local/bin/bash', '/usr/bin/bash'):
        if Path(candidate).exists() and subprocess.run(
                [candidate, '-c', '(( BASH_VERSINFO[0] >= 4 ))']).returncode == 0:
            return candidate
    return None


class AgentShell(Fixture):
    """Codex runs `zsh -lc <command>` with AGENT_SHELL set by its system config."""

    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        self.home.mkdir()
        install_shell(self.home, {'.zshenv', '.zprofile', '.zlogin'})

    def run_codex_shell(self, command, *args, marker=True, login=True):
        env = {'HOME': str(self.home), 'PATH': '/usr/bin:/bin', 'TMPDIR': str(self.path)}
        if marker:
            env['AGENT_SHELL'] = 'codex'
        return subprocess.run(['/bin/zsh', '-lc' if login else '-c', command, *args], cwd=self.path, env=env,
                              capture_output=True, text=True, timeout=20)

    @unittest.skipUnless(current_bash(), 'bash 4 or later required')
    def test_lines_installers_append_to_the_stubs_run_before_the_hand_off(self):
        for stub, var in (('.zshenv', 'FROM_ZSHENV'), ('.zprofile', 'FROM_ZPROFILE')):
            with open(self.home / stub, 'a') as f:
                f.write(f'export {var}=yes\n')
        p = self.run_codex_shell('echo "${BASH_VERSINFO[0]} ${FROM_ZSHENV:-missing} ${FROM_ZPROFILE:-missing}"')
        self.assertEqual(p.returncode, 0, p.stderr)
        major, *seen = p.stdout.split()
        self.assertGreaterEqual(int(major), 4)
        self.assertEqual(seen, ['yes', 'yes'])

    @unittest.skipUnless(current_bash(), 'bash 4 or later required')
    def test_a_plain_marked_zsh_c_hands_off_too(self):
        p = self.run_codex_shell('echo ${BASH_VERSINFO[0]}', login=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertGreaterEqual(int(p.stdout.strip()), 4)

    @unittest.skipUnless(current_bash(), 'bash 4 or later required')
    def test_marked_shell_runs_the_command_in_bash(self):
        p = self.run_codex_shell('echo "$0 $*"; echo ${BASH_VERSINFO[0]}; echo ====; echo /nonexistent-*-glob;'
                                 ' s="a b"; set -- $s; echo $#;'
                                 ' echo "child:$(zsh -fc \'print -r -- ${AGENT_SHELL:-unset}\')"',
                                 'name', 'x', 'y')
        self.assertEqual(p.returncode, 0, p.stderr)
        lines = p.stdout.splitlines()
        self.assertEqual(lines[0], 'name x y')
        self.assertGreaterEqual(int(lines[1]), 4)
        self.assertEqual(lines[2:], ['====', '/nonexistent-*-glob', '2', 'child:unset'])

    def test_unmarked_shell_keeps_zsh_semantics(self):
        p = self.run_codex_shell('print -r -- /nonexistent-*-glob', marker=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('no matches found', p.stderr)


class RealSessionGate(Fixture):
    """Launchers and command-replacing aliases exist only in real terminal sessions."""

    def aliases(self, real):
        code = (f'ZSH_REAL_SESSION={real}; source {ROOT}/lib_sh/claude.sh; '
                f'source {ZSH_DIR}/50-aliases.zsh; '
                'for a in c cc ccont cr co rm; do alias $a >/dev/null && print $a; done; true')
        p = subprocess.run(['/bin/zsh', '-f', '-c', code], cwd=self.path, env=self.env,
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.split()

    def test_tool_shells_get_no_launchers_or_replacements(self):
        self.assertEqual(self.aliases(0), [])

    def test_real_sessions_get_launchers_but_never_cc(self):
        self.assertEqual(self.aliases(1), ['c', 'ccont', 'cr', 'co', 'rm'])

    def test_flag_incompatible_replacements_never_take_the_real_name(self):
        for name in ('eza', 'ncdu', 'gping', 'htop'):
            self.cli(name, 'exit 0')
        code = (f'ZSH_REAL_SESSION=1; source {ZSH_DIR}/50-aliases.zsh; '
                'for a in ls du ping top; do alias $a >/dev/null && print $a; done; print -r -- "ll=$aliases[ll]"')
        p = subprocess.run(['/bin/zsh', '-f', '-c', code], cwd=self.path, env=self.env,
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.split('\n')[0], "ll=eza -l --icons --git")


class CachedEval(Fixture):
    """_dotfiles_cached_eval runs a tool's init once per release and arguments."""

    def setUp(self):
        super().setUp()
        self.cache = Path(self.env['XDG_CACHE_HOME'])
        self.runs = self.path / 'runs'
        self.env['DOTFILES_TEST_RUNS'] = str(self.runs)
        self.cli('fixture-tool', 'echo run >> "$DOTFILES_TEST_RUNS"\n'
                 '[ "$1" = fail ] && exit 3\necho "fixture_loaded=$1"')

    def load(self, *args):
        p = subprocess.run(['/bin/zsh', '-f', '-c', cached_eval_helper() + '_dotfiles_cached_eval fixture "$@"; '
                            'print -r -- "rc=$? loaded=${fixture_loaded:-none}"', 'zsh', 'fixture-tool', *args],
                           cwd=self.path, env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.stderr, '')
        return p.stdout.strip()

    def tool_runs(self):
        return len(self.runs.read_text().split()) if self.runs.exists() else 0

    def test_reuses_the_output_until_the_arguments_change(self):
        for _ in range(3):
            self.assertEqual(self.load('v1'), 'rc=0 loaded=v1')
        self.assertEqual(self.tool_runs(), 1)
        self.assertEqual(self.load('v2'), 'rc=0 loaded=v2')
        self.assertEqual(self.tool_runs(), 2)

    def test_a_named_variable_is_part_of_the_cache_key(self):
        def load(value):
            p = subprocess.run(['/bin/zsh', '-f', '-c', cached_eval_helper() + 'FIXTURE_OPT=$1; '
                                '_dotfiles_cached_eval fixture -e FIXTURE_OPT fixture-tool v1; print -r -- $?', 'zsh', value],
                               cwd=self.path, env=self.env, capture_output=True, text=True, timeout=20)
            self.assertEqual((p.stdout.strip(), p.stderr), ('0', ''))
        load('a')
        load('a')
        self.assertEqual(self.tool_runs(), 1)
        load('b')
        self.assertEqual(self.tool_runs(), 2)

    def test_each_real_session_activates_mise_with_its_own_path(self):
        # mise's activation script carries literal values from the shell that ran it.
        self.cli('mise', '[ "$1" = activate ] && printf "MISE_SAW_PATH=%s\\n" "\'$PATH\'"')
        def activated_with(path):
            env = dict(self.env, PATH=path, DOTFILES=str(self.path / 'no-dotfiles'))
            p = subprocess.run(['/bin/zsh', '-f', '-c', cached_eval_helper() + 'ZSH_REAL_SESSION=1; '
                                f'source {ZSH_DIR / "60-functions.zsh"}; print -r -- $MISE_SAW_PATH'],
                               cwd=self.path, env=env, capture_output=True, text=True, timeout=20)
            return p.stdout.strip().splitlines()[-1]
        first, second = f'{self.bin}:/usr/bin:/bin', f'{self.path}:{self.bin}:/usr/bin:/bin'
        self.assertEqual(activated_with(first), first)
        self.assertEqual(activated_with(second), second)

    def test_a_failing_init_leaves_no_cache(self):
        self.assertEqual(self.load('fail'), 'rc=1 loaded=none')
        self.assertEqual(list((self.cache / 'zsh').iterdir()), [])

    def test_a_missing_tool_is_skipped(self):
        (self.bin / 'fixture-tool').unlink()
        self.assertEqual(self.load('v1'), 'rc=0 loaded=none')


class DotfilesAgents(Fixture):
    def setUp(self):
        super().setUp()
        if not current_bash():
            self.skipTest('bash 4 or later required')
        self.root = self.path / 'root'
        self.env['DOTFILES_SYSTEM_ROOT'] = str(self.root)
        if sys.platform == 'darwin':
            self.claude = self.root / 'Library/Application Support/ClaudeCode/managed-settings.d/50-dotfiles.json'
        else:
            self.claude = self.root / 'etc/claude-code/managed-settings.d/50-dotfiles.json'
        self.codex = self.root / 'etc/codex/config.toml'

    def agents(self, command):
        return subprocess.run(['/bin/bash', str(ROOT / 'bin/dotfiles-agents'), command], cwd=self.path,
                              env=self.env, capture_output=True, text=True, timeout=20)

    def test_install_writes_both_configs_and_check_confirms_them(self):
        self.assertEqual(self.agents('check').returncode, 1)
        p = self.agents('install')
        self.assertEqual(p.returncode, 0, p.stderr)
        claude = json.loads(self.claude.read_text())
        self.assertIs(claude['attribution'], False, 'no Co-Authored-By trailer, PR line or session link')
        shell = claude['env']['CLAUDE_CODE_SHELL']
        self.assertEqual(subprocess.run([shell, '-c', '(( BASH_VERSINFO[0] >= 4 ))']).returncode, 0)
        codex = tomllib.loads(self.codex.read_text())
        self.assertIs(codex['features']['shell_snapshot'], False)
        self.assertEqual(codex['shell_environment_policy']['set'], {'AGENT_SHELL': 'codex'})
        [group] = codex['hooks']['PreToolUse']
        self.assertEqual(group['matcher'], 'Bash', 'the shell tool, as Codex names it for hooks')
        [hook] = group['hooks']
        self.assertEqual((hook['type'], hook['timeout']), ('command', 10))
        self.assertIn('$HOME/.local/bin/repo-guard', hook['command'])
        self.assertEqual(stat.S_IMODE(self.codex.stat().st_mode), 0o644)
        [claude_start] = claude['hooks']['SessionStart']
        self.assertNotIn('matcher', claude_start, 'every source: startup, resume, clear, compact')
        [codex_start] = codex['hooks']['SessionStart']
        self.assertNotIn('matcher', codex_start)
        [claude_hook], [codex_hook] = claude_start['hooks'], codex_start['hooks']
        self.assertEqual((claude_hook['type'], claude_hook['timeout']), ('command', 10))
        self.assertEqual((codex_hook['type'], codex_hook['timeout']), ('command', 10))
        self.assertEqual(claude_hook['command'], codex_hook['command'], 'one policy hook for both')
        self.assertGreater(codex_hook['additionalContextLimit'], len(self.POLICY.read_bytes()))
        self.assertEqual(self.agents('check').returncode, 0)

    POLICY = FEATURES / 'agents.delegation/home/.config/agent-delegation/policy.md'

    def test_the_session_hook_prints_the_policy_and_passes_without_it(self):
        self.agents('install')
        [hook] = json.loads(self.claude.read_text())['hooks']['SessionStart'][0]['hooks']
        home = self.path / 'home'
        policy = home / '.config/agent-delegation/policy.md'
        policy.parent.mkdir(parents=True)
        policy.symlink_to(self.POLICY)
        for shell in ('/bin/sh', '/bin/bash', '/bin/zsh'):
            with self.subTest(shell=shell):
                p = subprocess.run([shell, '-c', hook['command']], input='{"hook_event_name":"SessionStart"}',
                                   env={'HOME': str(home), 'PATH': '/usr/bin:/bin'}, capture_output=True,
                                   text=True, timeout=10)
                self.assertEqual((p.returncode, p.stdout, p.stderr), (0, self.POLICY.read_text(), ''))
        policy.unlink()
        p = subprocess.run(['/bin/sh', '-c', hook['command']], env={'HOME': str(home), 'PATH': '/usr/bin:/bin'},
                           capture_output=True, text=True, timeout=10)
        self.assertEqual((p.returncode, p.stdout), (0, ''), 'a home without the feature adds nothing')

    def test_check_reports_an_edited_config(self):
        self.agents('install')
        with self.codex.open('a') as f:
            f.write('model = "edited"\n')
        p = self.agents('check')
        self.assertEqual(p.returncode, 1)
        self.assertIn('changed', p.stdout)

    def test_a_config_it_did_not_write_is_left_alone(self):
        self.codex.parent.mkdir(parents=True)
        self.codex.write_text('model = "mine"\n')
        for command in ('install', 'uninstall'):
            with self.subTest(command=command):
                p = self.agents(command)
                self.assertEqual(p.returncode, 73)
                self.assertEqual(self.codex.read_text(), 'model = "mine"\n')

    def test_uninstall_removes_what_install_wrote(self):
        self.agents('install')
        p = self.agents('uninstall')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(self.claude.exists())
        self.assertFalse(self.codex.exists())


class ClaudeLaunchers(Fixture):
    """claudemore and claudemax from the agents.claude fragment, with a stub claude."""

    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        self.home.mkdir()
        self.work = self.path / 'work/repo'
        self.work.mkdir(parents=True)
        self.out = self.path / 'out'
        self.out.mkdir()
        self.cli('claude', f'printf "%s\\n" "$@" > {self.out}/argv\nenv > {self.out}/env')
        self.env.update(HOME=str(self.home))
        for name in ('CLAUDE_CONNECTORS', 'ENABLE_CLAUDEAI_MCP_SERVERS'):
            self.env.pop(name, None)

    def launch(self, launcher, *args, **env):
        p = subprocess.run(['/bin/zsh', '-fc', f'source {FEATURES / "agents.claude/zshrc.zsh"}; "$@"', 'test',
                            launcher, *args], cwd=self.work, env=dict(self.env, **env),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        argv = (self.out / 'argv').read_text().splitlines()
        environment = dict(line.split('=', 1) for line in (self.out / 'env').read_text().splitlines() if '=' in line)
        return p, argv, environment

    def test_sessions_get_no_connectors(self):
        p, argv, env = self.launch('claudemore', '--resume', 'x')
        self.assertEqual(argv[argv.index('--model') + 1], 'opus[1m]')
        self.assertNotIn('--append-system-prompt-file', argv, 'the managed SessionStart hook carries the policy')
        self.assertEqual(argv[-2:], ['--resume', 'x'], 'arguments pass through last')
        self.assertRegex(argv[argv.index('--name') + 1], r'^repo@.+-1$')
        self.assertEqual(env.get('ENABLE_CLAUDEAI_MCP_SERVERS'), 'false')
        _, argv, _ = self.launch('claudemax')
        self.assertEqual(argv[argv.index('--model') + 1], 'fable[1m]')

    def test_connectors_are_opt_in_per_launch(self):
        _, _, env = self.launch('claudemore', CLAUDE_CONNECTORS='1')
        self.assertNotIn('ENABLE_CLAUDEAI_MCP_SERVERS', env)


class CodexLaunchers(Fixture):
    """gptmore and gptmax from the agents.codex fragment, with a stub codex."""

    def setUp(self):
        super().setUp()
        self.work = self.path / 'work'
        self.work.mkdir()
        self.cli('codex', f'printf "%s\\n" "$@" > {self.path}/argv')
        self.env.pop('CODEX_CONNECTORS', None)
        self.env.pop('CODEX_HOME', None)
        self.env['HOME'] = str(self.path)

    def launch(self, launcher, *args, **env):
        p = subprocess.run(['/bin/zsh', '-fc', f'source {FEATURES / "agents.codex/zshrc.zsh"}; "$@"', 'test',
                            launcher, *args], cwd=self.work, env=dict(self.env, **env),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return (self.path / 'argv').read_text().splitlines()

    def test_sessions_attach_to_the_local_server_without_connectors(self):
        argv = self.launch('gptmore', 'resume', '--last')
        self.assertEqual(argv[:4], ['--remote', f'unix://{self.path}/.codex/dotfiles-app-server.sock',
                                    '-C', str(self.work.resolve())])
        self.assertEqual(argv[argv.index('--model') + 1], 'gpt-6.1-sol')
        self.assertIn('model_reasoning_effort=xhigh', argv)
        self.assertEqual(argv[argv.index('--disable') + 1], 'apps', 'no ChatGPT connectors')
        self.assertEqual(argv[-3:], ['--yolo', 'resume', '--last'])
        argv = self.launch('gptmax')
        self.assertEqual(argv[argv.index('--model') + 1], 'gpt-6-astra')
        self.assertIn('model_reasoning_effort=max', argv)

    def test_connectors_are_opt_in_per_launch(self):
        self.assertNotIn('--disable', self.launch('gptmore', CODEX_CONNECTORS='1'))

    def test_the_launcher_uses_the_server_endpoint_for_a_custom_codex_home(self):
        home = self.path / 'custom codex'
        argv = self.launch('gptmore', CODEX_HOME=str(home))
        self.assertEqual(argv[:2], ['--remote', f'unix://{home}/dotfiles-app-server.sock'])


class CodexAppServer(Fixture):
    """bin/codex-app-server, run beside a stub stable-exec that records its arguments."""

    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        self.home.mkdir()
        self.env.pop('CODEX_HOME', None)
        shutil.copy(ROOT / 'bin/codex-app-server', self.bin)
        self.cli('stable-exec', f'for a in "$@"; do printf "%s\\0" "$a"; done > {self.path}/argv')

    def serve(self):
        p = subprocess.run([str(self.bin / 'codex-app-server')], env=dict(self.env, HOME=str(self.home)),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p, (self.path / 'argv').read_text().split('\0')[:-1]

    def test_the_server_runs_on_its_own_socket(self):
        policy = self.home / '.config/agent-delegation/policy.md'
        policy.parent.mkdir(parents=True)
        policy.write_text('# policy\n')
        _, argv = self.serve()
        self.assertEqual(argv, ['codex', 'app-server', '--remote-control', '--listen',
                                f'unix://{self.home}/.codex/dotfiles-app-server.sock'],
                         'the managed SessionStart hook carries the policy, not -c')

    def test_printing_the_endpoint_does_not_start_the_server(self):
        for home in (self.home / '.codex', self.path / 'custom codex'):
            with self.subTest(home=home):
                env = dict(self.env, HOME=str(self.home), CODEX_HOME=str(home))
                p = subprocess.run([str(self.bin / 'codex-app-server'), '--print-endpoint'], env=env,
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual((p.returncode, p.stdout, p.stderr),
                                 (0, f'unix://{home}/dotfiles-app-server.sock\n', ''))
                self.assertFalse((self.path / 'argv').exists())
                self.env['CODEX_HOME'] = str(home)
                _, argv = self.serve()
                self.assertEqual(argv[argv.index('--listen') + 1], p.stdout.strip())
                (self.path / 'argv').unlink()


class Delegation(unittest.TestCase):
    """The scout and reader subagents are one definition in two encodings."""

    HOME = FEATURES / 'agents.delegation/home'

    def test_codex_roles_match_the_claude_subagents(self):
        for name in ('scout', 'reader'):
            with self.subTest(name):
                _, front, body = (self.HOME / f'.claude/agents/{name}.md').read_text().split('---\n', 2)
                claude = dict(line.split(': ', 1) for line in front.strip().splitlines())
                role = tomllib.loads((self.HOME / f'.codex/agents/{name}.toml').read_text())
                self.assertEqual((claude['name'], role['name']), (name, name))
                # Codex states a role's model in its description itself.
                self.assertEqual(role['description'], re.sub(r' Runs on \w+\.$', '', json.loads(claude['description'])))
                self.assertEqual(role['developer_instructions'].strip(), body.strip())
                self.assertEqual(role['features'], {'apps': False, 'plugins': False})
                self.assertTrue(role['model'] and role['model_reasoning_effort'])


class RepoGuard(Fixture):
    """repo-guard: its own cases under current bash and macOS's bash 3.2, and the
    command each harness registers for it reaching the same script."""

    FEATURE = FEATURES / 'agents.repo-guard'

    def setUp(self):
        super().setUp()
        if not shutil.which('jq'):
            self.skipTest('jq required by the hook')

    def test_guard_cases_pass(self):
        for shell in dict.fromkeys(filter(None, [current_bash(), '/bin/bash' if Path('/bin/bash').exists() else None])):
            with self.subTest(bash=shell):
                p = subprocess.run([shell, str(self.FEATURE / 'guard_test.sh')], env=dict(os.environ, GUARD_BASH=shell),
                                   capture_output=True, text=True, timeout=240)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                self.assertIn('fail=0', p.stdout)

    def registrations(self):
        """The hook command of the Claude Code plugin and of the Codex system config."""
        claude = json.loads((self.FEATURE / 'home/.claude/skills/repo-guard/hooks/hooks.json').read_text())
        [claude_group] = claude['hooks']['PreToolUse']
        [claude_hook] = claude_group['hooks']
        self.assertEqual((claude_group['matcher'], claude_hook['onFailure']), ('Bash', 'block'))
        root = self.path / 'root'
        p = subprocess.run(['/bin/bash', str(ROOT / 'bin/dotfiles-agents'), 'install'], cwd=self.path,
                           env=dict(self.env, DOTFILES_SYSTEM_ROOT=str(root)), capture_output=True, text=True, timeout=20)
        if p.returncode == 69:
            self.skipTest('bash 4 or later required by dotfiles-agents')
        self.assertEqual(p.returncode, 0, p.stderr)
        [codex_group] = tomllib.loads((root / 'etc/codex/config.toml').read_text())['hooks']['PreToolUse']
        return {'claude': claude_hook['command'], 'codex': codex_group['hooks'][0]['command']}

    def run_hook(self, command, home, cwd, shell='/bin/sh'):
        payload = {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'cwd': str(cwd),
                   'tool_input': {'command': 'git push origin main'}}
        env = {'HOME': str(home), 'PATH': os.path.dirname(shutil.which('jq')) + ':/usr/bin:/bin'}
        return subprocess.run([shell, '-c', command], input=json.dumps(payload), env=env, cwd=cwd,
                              capture_output=True, text=True, timeout=30)

    def test_both_harnesses_run_the_one_guard(self):
        home = self.path / 'home'
        (home / '.local/bin').mkdir(parents=True)
        (home / '.local/bin/repo-guard').symlink_to(self.FEATURE / 'bin/repo-guard')
        (home / '.config/repo-guard/protected.d').mkdir(parents=True)
        (home / '.config/repo-guard/protected.d/a.txt').write_text('example-owner/protected-repo\n')
        clone = self.path / 'clone'
        subprocess.run(['git', 'init', '-q', str(clone)], check=True)
        subprocess.run(['git', '-C', str(clone), 'remote', 'add', 'origin', 'git@github.com:example-owner/protected-repo.git'],
                       check=True)
        for harness, command in self.registrations().items():
            # Codex runs a hook through the session's shell; Claude Code through its own.
            for shell in ('/bin/sh', '/bin/zsh') if harness == 'codex' else ('/bin/sh',):
                with self.subTest(harness=harness, shell=shell):
                    p = self.run_hook(command, home, clone, shell)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertEqual(json.loads(p.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_codex_passes_without_the_feature_and_blocks_when_the_guard_breaks(self):
        command = self.registrations()['codex']
        clone = self.path / 'clone'
        clone.mkdir()
        p = self.run_hook(command, self.path / 'no-feature', clone)
        self.assertEqual((p.returncode, p.stdout), (0, ''), p.stderr)
        for name, guard in (('crashes', '#!/bin/sh\nexit 1\n'), ('is a dangling link', None)):
            with self.subTest(name):
                home = self.path / name.replace(' ', '-')
                (home / '.local/bin').mkdir(parents=True)
                link = home / '.local/bin/repo-guard'
                if guard is None:
                    link.symlink_to(self.path / 'missing')
                else:
                    link.write_text(guard)
                p = self.run_hook(command, home, clone)
                self.assertEqual(p.returncode, 2, 'Codex blocks only on exit 2')
                self.assertIn('repo-guard: exited', p.stderr)


class SubagentEconomics(Fixture):
    SCRIPT = FEATURES / 'agents.claude/bin/claude-subagent-economics'

    def run_script(self, projects):
        return subprocess.run([sys.executable, '-I', str(self.SCRIPT), '--projects', str(projects), '--days', '7'],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def test_prices_a_subagent_run_against_its_parent(self):
        session = self.path / 'projects/project/session'
        (session / 'subagents').mkdir(parents=True)
        usage = {'input_tokens': 1000, 'cache_creation_input_tokens': 2000, 'cache_read_input_tokens': 3000,
                 'output_tokens': 400}
        (session / 'subagents/agent-1.meta.json').write_text(json.dumps({'agentType': 'scout', 'toolUseId': 'toolu_1'}))
        (session / 'subagents/agent-1.jsonl').write_text(
            json.dumps({'type': 'assistant', 'message': {'id': 'm1', 'usage': usage,
                                                         'content': [{'type': 'text', 'text': 'x' * 40}]}}) + '\n')
        parent = [{'type': 'user', 'toolUseId': 'toolu_1'}] + [
            {'type': 'assistant', 'message': {'id': f'p{i}'}} for i in range(3)]
        (self.path / 'projects/project/session.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in parent))
        p = self.run_script(self.path / 'projects')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('runs: 1  by type: scout=1', p.stdout)
        self.assertRegex(p.stdout, r'parent requests until the next compaction +p25= +3\.00')

    def test_no_runs_is_exit_1(self):
        (self.path / 'projects').mkdir()
        p = self.run_script(self.path / 'projects')
        self.assertEqual(p.returncode, 1)
        self.assertIn('no subagent runs', p.stderr)


class GpgAgentSupervisor(Fixture):
    """bin/gpg-agent-supervisor against a fake agent: the PID that answers on
    gpg's socket is the content of a file, and gpgconf's --launch starts the
    next PID from 501 unless DOTFILES_TEST_AGENT_FAILS is set."""

    SCRIPT = 'bin/gpg-agent-supervisor'

    def setUp(self):
        super().setUp()
        self.agent = self.path / 'agent.pid'
        self.calls = self.path / 'calls'
        self.env.update(FAKE_AGENT=str(self.agent), FAKE_NEXT=str(self.path / 'next.pid'),
                        CALLS=str(self.calls))
        self.cli('gpg-connect-agent', '''
case " $* " in *" --no-autostart "*) ;; *) echo "autostart $*" >>"$CALLS" ;; esac
if [ -s "$FAKE_AGENT" ]; then echo "D $(cat "$FAKE_AGENT")"; echo OK
else echo 'gpg-connect-agent: no gpg-agent running in this session' >&2; fi''')
        self.cli('gpgconf', '''
echo "gpgconf $*" >>"$CALLS"
case "$*" in
  '--kill gpg-agent') rm -f "$FAKE_AGENT" ;;
  '--launch gpg-agent')
    [ -s "$FAKE_AGENT" ] && exit 0
    [ -n "${DOTFILES_TEST_AGENT_FAILS:-}" ] && exit 0
    next=$(( $(cat "$FAKE_NEXT" 2>/dev/null || echo 500) + 1 ))
    echo "$next" >"$FAKE_NEXT"; echo "$next" >"$FAKE_AGENT" ;;
esac''')

    def running(self, pid):
        self.agent.write_text(f'{pid}\n')

    def answering(self):
        return self.agent.read_text().strip() if self.agent.exists() else None

    def recorded(self):
        return self.calls.read_text().splitlines() if self.calls.exists() else []

    def test_start_replaces_the_running_agent(self):
        self.running(100)
        p = self.bash('start_agent', source=self.SCRIPT)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), '501')
        self.assertEqual(self.answering(), '501')

    def test_check_keeps_the_agent_it_started(self):
        self.running(501)
        p = self.bash('check_agent 501', source=self.SCRIPT)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), '501')
        self.assertEqual(self.recorded(), [])

    def test_check_replaces_an_agent_started_elsewhere(self):
        self.running(777)
        p = self.bash('check_agent 501', source=self.SCRIPT)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), '501')
        self.assertEqual(self.answering(), '501')
        self.assertIn('gpg-agent 777 was started outside this login', p.stderr)

    def test_check_restarts_a_stopped_agent(self):
        p = self.bash('check_agent 400', source=self.SCRIPT)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), '501')
        self.assertEqual(self.answering(), '501')
        self.assertIn('gpg-agent 400 is gone', p.stderr)

    def test_an_agent_that_never_answers_fails_the_start(self):
        self.env['DOTFILES_TEST_AGENT_FAILS'] = '1'
        p = self.bash('start_agent', source=self.SCRIPT)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(p.stdout.strip(), '')
        self.assertIn('gpg-agent did not start', p.stderr)

    def test_never_autostarts_an_agent_from_its_own_queries(self):
        self.running(777)
        self.bash('check_agent "$(start_agent)"', source=self.SCRIPT)
        self.assertEqual([c for c in self.recorded() if c.startswith('autostart')], [])

    def test_refuses_an_invalid_interval_before_touching_the_agent(self):
        self.running(777)
        for value in ('0', '1.5', 'ten'):
            with self.subTest(value=value):
                self.env['GPG_AGENT_SUPERVISOR_SECONDS'] = value
                p = subprocess.run(['/bin/bash', str(ROOT / self.SCRIPT)], cwd=self.path, env=self.env,
                                   capture_output=True, text=True, timeout=20)
                self.assertEqual(p.returncode, 64)
                self.assertIn('GPG_AGENT_SUPERVISOR_SECONDS', p.stderr)
                self.assertEqual(self.answering(), '777')


class OtelAgent(Fixture):
    SCRIPT = ROOT / 'bin/otel-agent'
    CONFIG = FEATURES / 'agents.otel-agent/home/.config/otel-agent/config.yaml'
    VERSION = re.search(r'OTELCOL_VERSION=(\S+)', (ROOT / 'bin/otel-agent').read_text())[1]
    PLATFORM = 'darwin_arm64' if os.uname().machine == 'arm64' else 'darwin_amd64'
    TOKEN = 'a' * 48

    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        self.home.mkdir()
        self.enrolled = self.home / '.local/share/otel-agent'
        self.state = self.home / '.local/state/otel-agent'
        self.libexec = self.home / '.local/libexec/otelcol'
        self.config = self.home / '.config/otel-agent/config.yaml'
        self.curl_audit = self.path / 'curl-audit'
        self.env.update(HOME=str(self.home), OTEL_TEST_CURL=str(self.curl_audit))
        for name in ('OTEL_AGENT_HOME', 'OTEL_AGENT_STATE', 'OTEL_AGENT_LIBEXEC', 'OTEL_AGENT_CONFIG',
                     'OTEL_AGENT_HOST', 'OTEL_AGENT_KUBE_CONTEXT', 'XDG_STATE_HOME'):
            self.env.pop(name, None)
        # dotfiles apply loads the collector's LaunchAgent once this Mac is enrolled.
        self.engine_calls = self.stub_engine(loads=['com.ashtonian.otel-agent'])
        self.target = f'gui/{os.getuid()}/com.ashtonian.otel-agent'
        # Downloads fail unless a test serves an archive; every URL is recorded.
        self.cli('curl', 'printf "%s\\n" "$*" >> "$OTEL_TEST_CURL"\n'
                 'out=; while [ $# -gt 0 ]; do [ "$1" = -o ] && out=$2; shift; done\n'
                 '[ -n "${OTEL_TEST_ARCHIVE:-}" ] && [ -n "$out" ] && cp "$OTEL_TEST_ARCHIVE" "$out" && exit 0\n'
                 'exit 7')

    def run_agent(self, *args, input=None):
        return subprocess.run(['/bin/zsh', '-f', str(self.SCRIPT), *args],
                              cwd=self.path, env=self.env, input=input,
                              capture_output=True, text=True, timeout=30)

    def calls(self, suffix=''):
        if suffix == '.curl':
            return self.curl_audit.read_text().splitlines() if self.curl_audit.exists() else []
        return self.launchctl_calls()

    def install_collector(self, directory=None):
        """A stand-in collector that prints what serve handed it."""
        collector = self.libexec / (directory or f'{self.VERSION}_{self.PLATFORM}') / 'otelcol-contrib'
        collector.parent.mkdir(parents=True)
        collector.write_text('#!/bin/sh\nprintf "%s\\n" "args=$*" "gateway=$OTEL_AGENT_GATEWAY" '
                             '"token=$OTEL_AGENT_TOKEN" "host=$OTEL_AGENT_HOST" "queue=$OTEL_AGENT_QUEUE"\n')
        collector.chmod(0o755)
        return collector

    def enroll(self, host='studio'):
        self.enrolled.mkdir(parents=True)
        (self.enrolled / 'endpoint').write_text('https://gateway.example\n')
        (self.enrolled / 'token').write_text(self.TOKEN + '\n')
        if host:
            (self.enrolled / 'host').write_text(host + '\n')
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text('receivers: {}\n')

    def test_serve_runs_pinned_collector_with_enrolled_gateway_host_and_queue(self):
        self.install_collector()
        self.enroll('mbp')
        p = self.run_agent('serve')
        self.assertEqual(p.returncode, 0, p.stderr)
        lines = dict(line.split('=', 1) for line in p.stdout.splitlines())
        self.assertEqual(lines['args'], f'--config={self.config}')
        self.assertEqual(lines['gateway'], 'https://gateway.example')
        self.assertEqual(lines['token'], self.TOKEN)
        self.assertEqual(lines['host'], 'mbp')
        self.assertEqual(lines['queue'], str(self.state / 'queue'))
        self.assertEqual(stat.S_IMODE((self.state / 'queue').stat().st_mode), 0o700)
        self.assertTrue((self.state / 'serving').read_text().strip())

    def test_host_environment_overrides_the_enrolled_name(self):
        self.install_collector()
        self.enroll('mbp')
        self.env['OTEL_AGENT_HOST'] = 'mini'
        p = self.run_agent('serve')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('host=mini', p.stdout)

    def test_serve_refuses_until_the_mac_is_enrolled_with_a_host(self):
        self.install_collector()
        p = self.run_agent('serve')
        self.assertEqual(p.returncode, 78)
        self.assertIn('otel-agent enroll', p.stderr)
        # Enrolled before host names existed: the token is the old shared one.
        self.enroll(host=None)
        p = self.run_agent('serve')
        self.assertEqual(p.returncode, 78)
        self.assertIn('no host name configured', p.stderr)
        self.env['OTEL_AGENT_HOST'] = 'Example-Mac-mini'
        p = self.run_agent('serve')
        self.assertEqual(p.returncode, 78)
        self.assertIn('not a short lowercase name', p.stderr)

    def test_serve_installs_a_release_the_pin_moved_to_and_verifies_it(self):
        # A pull moved the pin; the old release is still installed.
        old = self.install_collector('0.163.1')
        self.enroll()
        archive = self.path / 'otelcol.tar.gz'
        archive.write_bytes(b'not the pinned archive')
        self.env['OTEL_TEST_ARCHIVE'] = str(archive)
        p = self.run_agent('serve')
        self.assertEqual(p.returncode, 65)
        self.assertIn('checksum mismatch', p.stderr)
        [download] = self.calls('.curl')
        self.assertTrue(download.endswith(
            f'/releases/download/v{self.VERSION}/otelcol-contrib_{self.VERSION}_{self.PLATFORM}.tar.gz'), download)
        self.assertTrue(old.exists(), 'nothing is removed until the new release is in place')
        self.assertFalse((self.libexec / f'{self.VERSION}_{self.PLATFORM}').exists())

    def test_a_failed_download_is_reported(self):
        self.enroll()
        p = self.run_agent('serve')
        self.assertEqual(p.returncode, 69)
        self.assertIn('downloading https://github.com/', p.stderr)

    def test_an_architecture_without_a_pinned_release_is_refused(self):
        self.cli('uname', 'echo ppc')
        p = self.run_agent('install')
        self.assertEqual(p.returncode, 69)
        self.assertIn('no otelcol-contrib release is pinned for ppc', p.stderr)
        self.assertEqual(self.calls('.curl'), [])

    def test_install_keeps_only_the_pinned_release(self):
        self.install_collector()
        self.install_collector('0.163.1')
        other = 'darwin_amd64' if self.PLATFORM == 'darwin_arm64' else 'darwin_arm64'
        self.install_collector(f'{self.VERSION}_{other}')
        p = self.run_agent('install')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(sorted(d.name for d in self.libexec.iterdir()), [f'{self.VERSION}_{self.PLATFORM}'])
        self.assertIn('otel-agent enroll HOST', p.stdout)
        self.assertEqual(self.engine_calls(), [], 'the LaunchAgent waits for enrollment')
        self.assertNotIn('kickstart', ' '.join(self.calls()))

    def test_configure_stores_gateway_host_and_token_privately_and_starts_the_agent(self):
        self.install_collector()
        self.config.parent.mkdir(parents=True)
        self.config.write_text('')
        p = self.run_agent('configure', 'https://gateway.example/', 'mini', input=self.TOKEN + '\n')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((self.enrolled / 'endpoint').read_text(), 'https://gateway.example\n')
        self.assertEqual((self.enrolled / 'token').read_text(), self.TOKEN + '\n')
        self.assertEqual((self.enrolled / 'host').read_text(), 'mini\n')
        self.assertEqual(stat.S_IMODE(self.enrolled.stat().st_mode), 0o700)
        for name in ('endpoint', 'token', 'host'):
            self.assertEqual(stat.S_IMODE((self.enrolled / name).stat().st_mode), 0o600)
        self.assertNotIn(self.TOKEN, p.stdout + p.stderr)
        self.assertEqual(self.engine_calls(), [f'apply --repo {ROOT}'], 'apply installs and loads the agent')
        self.assertTrue((self.launchd / 'com.ashtonian.otel-agent').exists())

    def test_configure_restarts_a_loaded_collector_on_the_new_token(self):
        self.install_collector()
        self.enroll()
        self.loaded('com.ashtonian.otel-agent')
        p = self.run_agent('configure', 'https://gateway.example', 'mini', input=self.TOKEN + '\n')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(f'kickstart -k {self.target}', self.calls())
        self.assertEqual(self.engine_calls(), [])

    def test_configure_reports_a_collector_its_feature_does_not_install(self):
        self.install_collector()
        self.config.parent.mkdir(parents=True)
        self.config.write_text('')
        self.engine_calls = self.stub_engine()
        p = self.run_agent('configure', 'https://gateway.example', 'mini', input=self.TOKEN + '\n')
        self.assertEqual(p.returncode, 78, p.stderr)
        self.assertIn('enable the agents.otel-agent feature', p.stderr)

    def test_the_launchagent_waits_for_enrollment_and_restarts_while_enrolled(self):
        feature = tomllib.loads((FEATURES / 'agents.otel-agent/feature.toml').read_text())
        [agent] = feature['provides']['launch_agent']
        self.assertEqual(agent['when_exists'][-1], '~/.local/share/otel-agent/host',
                         'configure writes the host file last')
        template = (FEATURES / 'agents.otel-agent' / agent['plist']).read_text()
        self.assertIn('<key>$HOME/.local/share/otel-agent/host</key>', template)

    def test_configure_rejects_plain_http_short_tokens_and_hostnames(self):
        self.install_collector()
        for args, token, status in ((('http://gateway.example', 'mini'), self.TOKEN, 64),
                                    (('https://gateway.example', 'mini'), 'short', 65),
                                    (('https://gateway.example', 'Example-Mac-mini'), self.TOKEN, 64),
                                    (('https://gateway.example',), self.TOKEN, 64)):
            with self.subTest(args=args):
                p = self.run_agent('configure', *args, input=token + '\n')
                self.assertEqual(p.returncode, status, p.stderr)
        self.assertFalse(self.enrolled.exists())

    def test_enroll_reads_this_hosts_token_and_gateway_from_the_cluster(self):
        self.install_collector()
        self.config.parent.mkdir(parents=True)
        self.config.write_text('')
        audit = self.path / 'kubectl-audit'
        self.env['OTEL_TEST_KUBECTL'] = str(audit)
        self.cli('kubectl', 'printf "%s\\n" "$*" >> "$OTEL_TEST_KUBECTL"\ncase "$*" in\n'
                 '  *render-domains*) printf home.example | base64 ;;\n'
                 f'  *otel-gateway-token-mbp*) printf {self.TOKEN} | base64 ;;\n'
                 '  *) exit 1 ;;\nesac')
        p = self.run_agent('enroll', 'mbp', '--context', 'admin@cluster')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((self.enrolled / 'endpoint').read_text(), 'https://otel.home.example\n')
        self.assertEqual((self.enrolled / 'token').read_text(), self.TOKEN + '\n')
        self.assertEqual((self.enrolled / 'host').read_text(), 'mbp\n')
        self.assertNotIn(self.TOKEN, p.stdout + p.stderr)
        calls = audit.read_text().splitlines()
        self.assertTrue(all(call.startswith('--context=admin@cluster ') for call in calls), calls)
        self.assertTrue(any('-n monitoring get secret otel-gateway-token-mbp' in call for call in calls), calls)

    def test_enroll_without_a_secret_for_the_host_stores_nothing(self):
        self.cli('kubectl', 'case "$*" in *render-domains*) printf home.example | base64 ;; '
                 '*) echo "secrets not found" >&2; exit 1 ;; esac')
        p = self.run_agent('enroll', 'laptop')
        self.assertEqual(p.returncode, 69)
        self.assertIn('otel-gateway-token-laptop', p.stderr)
        self.assertFalse(self.enrolled.exists())

    def test_enroll_without_kubectl_explains_piping_the_token_in(self):
        self.env['PATH'] = f'{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin'
        p = self.run_agent('enroll', 'mini')
        self.assertEqual(p.returncode, 69)
        self.assertIn('otel-gateway-token-mini', p.stderr)
        self.assertIn('| ssh <this mac> ~/.dotfiles/bin/otel-agent configure https://otel.', p.stderr)

    def test_converge_skips_a_mac_that_never_enrolled(self):
        p = self.run_agent('converge')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout + p.stderr, '')
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.calls('.curl'), [])

    def test_converge_restarts_the_collector_only_when_what_it_runs_from_changed(self):
        self.install_collector()
        self.enroll()
        self.assertEqual(self.run_agent('serve').returncode, 0)
        self.loaded('com.ashtonian.otel-agent', running=True)
        p = self.run_agent('converge')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual([call for call in self.calls() if not call.startswith('print ')], [])
        # A pull changes the config the running collector started from.
        self.config.write_text('receivers: {otlp: {}}\n')
        p = self.run_agent('converge')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(f'kickstart -k {self.target}', self.calls())
        self.assertIn('restarted the collector', p.stdout)

    def test_converge_reports_a_collector_apply_did_not_load(self):
        self.install_collector()
        self.enroll()
        p = self.run_agent('converge')
        self.assertEqual(p.returncode, 78)
        self.assertIn('dotfiles apply loads it while the agents.otel-agent feature is on', p.stderr)

    def test_converge_reports_a_mac_enrolled_without_a_host(self):
        self.install_collector()
        self.enroll(host=None)
        p = self.run_agent('converge')
        self.assertEqual(p.returncode, 78)
        self.assertIn('otel-agent enroll HOST', p.stderr)
        self.assertEqual(self.calls(), [])

    def test_status_shows_host_queue_and_counters(self):
        self.install_collector()
        self.enroll('mbp')
        (self.state / 'queue').mkdir(parents=True)
        (self.state / 'queue/exporter_otlp_http_logs_logs').write_bytes(b'\0' * (3 << 20))
        self.loaded('com.ashtonian.otel-agent', running=True)
        metrics = self.path / 'metrics.txt'
        metrics.write_text(
            'otelcol_exporter_queue_size{data_type="logs",exporter="otlp_http/logs"} 1.572864e+06\n'
            'otelcol_exporter_queue_capacity{data_type="logs",exporter="otlp_http/logs"} 8.05306368e+08\n'
            'otelcol_exporter_queue_capacity{data_type="metrics",exporter="otlp_http/metrics"} 2.147483648e+09\n'
            'otelcol_exporter_queue_size{data_type="metrics",exporter="otlp_http/metrics"} 0\n'
            'otelcol_exporter_sent_log_records{exporter="otlp_http/logs"} 12\n')
        self.cli('curl', f'case "$*" in *8889*) cat {metrics} ;; esac')
        p = self.run_agent('status')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('service:   running', p.stdout)
        self.assertIn('host:      mbp', p.stdout)
        self.assertIn(f'queue:     3 MiB on disk in {self.state}/queue', p.stdout)
        self.assertIn('health:    ok', p.stdout)
        self.assertRegex(p.stdout, r'queue logs +1\.5 of 768 MiB')
        self.assertRegex(p.stdout, r'queue metrics +0\.0 of 2048 MiB')
        self.assertRegex(p.stdout, r'otelcol_exporter_sent_log_records +12')

    def test_unknown_command_is_a_usage_error(self):
        self.assertEqual(self.run_agent('bogus').returncode, 64)

    def test_collector_config_deletes_identity_and_content_keys(self):
        text = self.CONFIG.read_text()
        # Every delete pattern, with `*alias` resolved to its `&anchor` value.
        anchors = dict(re.findall(r"&(\w+) '([^']+)'", text))
        patterns = [re.compile(literal or anchors[ref])
                    for ref, literal in re.findall(r"pattern: (?:[&*](\w+) ?)?(?:'([^']+)')?", text)]
        deleted = lambda key: any(p.search(key) for p in patterns)
        for key in ('user.email', 'user.id', 'user.account_id', 'user.account_uuid',
                    'organization.id', 'prompt', 'prompt_text', 'response', 'tool_input',
                    'tool_parameters', 'arguments', 'output', 'error', 'error.message',
                    'auth.error', 'body', 'diff'):
            self.assertTrue(deleted(key), key)
        for key in ('tool_name', 'tool_result_size_bytes', 'duration_ms', 'event.name',
                    'session.id', 'mcp_server', 'model', 'service.name', 'error_type'):
            self.assertFalse(deleted(key), key)

    def test_collector_config_queue_files_have_room_above_every_queue(self):
        # A queue file holds about 1.3 times its queue's bytes. The queue limit
        # must bind before the file's, or a full file also refuses the writes
        # that acknowledge delivered batches.
        text = self.CONFIG.read_text()
        queues = [int(size) for size in re.findall(r'^\s+queue_size: (\d+)', text, re.M)]
        self.assertEqual(len(queues), 2, 'one queue per signal')
        self.assertEqual(len(re.findall(r'^\s+storage: file_storage/queue$', text, re.M)), 2)
        self.assertEqual(len(re.findall(r'^\s+sizer: bytes$', text, re.M)), 2)
        max_size = int(re.search(r'^\s+max_size: (\d+)', text, re.M)[1])
        self.assertGreaterEqual(max_size, 1.4 * max(queues))
        self.assertRegex(text, r'(?m)^\s+on_rebound: true$')


class AgentMcp(Fixture):
    SCRIPT = FEATURES / 'agents.agent-mcp/home/.local/bin/agent-mcp'

    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        self.mcp = self.path / 'mcp'
        self.config = self.path / 'agent-mcp'
        self.env.update(HOME=str(self.home), AGENT_MCP_HOME=str(self.mcp), AGENT_MCP_CONFIG=str(self.config))

    def run_mcp(self, *args):
        return subprocess.run(['/bin/sh', str(self.SCRIPT), *args], cwd=self.path, env=self.env,
                              capture_output=True, text=True, timeout=20)

    def fake(self, path, name='server'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'#!/bin/sh\necho "{name} $*"\n')
        path.chmod(0o755)

    def test_unknown_server_or_harness_is_a_usage_error(self):
        self.assertEqual(self.run_mcp('bogus').returncode, 64)
        p = self.run_mcp('serena', 'gemini')
        self.assertEqual(p.returncode, 64)
        self.assertIn("unknown harness 'gemini'", p.stderr)

    def test_missing_install_names_the_server(self):
        p = self.run_mcp('pprof')
        self.assertEqual(p.returncode, 69)
        self.assertIn('pprof:', p.stderr)
        self.assertIn('not installed', p.stderr)

    def test_serena_uses_the_claude_context_file_for_claude(self):
        self.fake(self.bin / 'serena', 'serena')
        (self.config).mkdir()
        (self.config / 'serena-claude-code.yml').write_text('')
        p = self.run_mcp('serena', 'claude')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(f'--context {self.config}/serena-claude-code.yml', p.stdout)
        for flag in ('--project-from-cwd', '--add-mode no-memories', '--enable-web-dashboard false',
                     '--open-web-dashboard false'):
            self.assertIn(flag, p.stdout)

    def test_serena_uses_upstream_context_for_codex(self):
        self.fake(self.bin / 'serena', 'serena')
        p = self.run_mcp('serena', 'codex')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('--context codex ', p.stdout)

    def test_serena_for_claude_without_context_file_is_a_config_error(self):
        self.fake(self.bin / 'serena', 'serena')
        p = self.run_mcp('serena')
        self.assertEqual(p.returncode, 78)
        self.assertIn('enable the agents.agent-mcp feature', p.stderr)

    def test_codebase_memory_restricts_codex_to_the_analysis_profile(self):
        self.fake(self.home / '.local/libexec/codebase-memory-mcp/0.12.1/codebase-memory-mcp', 'cbm')
        self.assertEqual(self.run_mcp('codebase-memory', 'codex').stdout.strip(), 'cbm --tool-profile=analysis')
        self.assertEqual(self.run_mcp('codebase-memory', 'claude').stdout.strip(), 'cbm')

    def test_grafana_enables_fewer_tool_categories_for_codex(self):
        self.fake(self.mcp / 'grafana.sh', 'grafana')
        claude = self.run_mcp('grafana').stdout
        codex = self.run_mcp('grafana', 'codex').stdout
        self.assertIn('pyroscope', claude)
        self.assertNotIn('pyroscope', codex)
        self.assertIn('-enabled-tools search,datasource,prometheus,loki,dashboard', codex)

    def test_github_uses_the_active_account_and_only_offers_reads(self):
        self.env["HOMEBREW_PREFIX"] = str(self.path)
        self.cli("gh", 'test "$*" = "auth token --hostname github.com" && echo fixture-token')
        self.cli("mise", 'test "$*" = "-C $HOME which github-mcp-server" && command -v github-mcp-server')
        self.cli("github-mcp-server", 'test "$GITHUB_PERSONAL_ACCESS_TOKEN" = fixture-token && echo "$@"')
        result = self.run_mcp("github")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "stdio --gh-host https://github.com --read-only --toolsets default,actions")
        self.cli("gh", "exit 1")
        result = self.run_mcp("github")
        self.assertEqual(result.returncode, 77)
        self.assertEqual(result.stdout, "")

    def test_kubernetes_stays_read_only(self):
        self.fake(self.mcp / 'bin/kubernetes-mcp-server', 'k8s')
        out = self.run_mcp('kubernetes').stdout
        for flag in ('--read-only', '--disable-destructive', '--disable-multi-cluster'):
            self.assertIn(flag, out)


@unittest.skipUnless(sys.platform == 'darwin', 'go-cache-trim uses BSD stat and find')
class GoCacheTrim(Fixture):
    """bin/go-cache-trim against fake caches whose entries carry the mtime of
    their last use; a fake go reports the first cache as GOCACHE."""

    README = ('This directory holds cached build artifacts from the Go build system.\n'
              'Run "go clean -cache" if the directory is getting too large.\n')
    KIB = 64

    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        self.home.mkdir()
        self.cache = self.make_cache('cache')
        self.cli('go', 'echo "$FAKE_GOCACHE"')
        self.env.update(HOME=str(self.home), FAKE_GOCACHE=str(self.cache), GO_CACHE_TRIM_HOURS='24')
        for name in ('GO_EXTRA_BUILD_CACHES', 'GO_CACHE_TRIM_MAX_GIB'):
            self.env.pop(name, None)

    def make_cache(self, name):
        cache = self.path / name
        (cache / 'fuzz').mkdir(parents=True)
        (cache / 'README').write_text(self.README)
        return cache

    def entry(self, cache, name, hours_since_use):
        """Writes an entry in hex directory 'ab' and returns its allocated bytes."""
        path = cache / 'ab' / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b'\1' * self.KIB * 1024)
        used = time.time() - hours_since_use * 3600
        os.utime(path, (used, used))
        return path.stat().st_blocks * 512

    def cap(self, allocated_bytes):
        self.env['GO_CACHE_TRIM_MAX_GIB'] = f'{allocated_bytes / 2**30:.12f}'

    def entries(self, cache):
        return sorted(p.name for p in (cache / 'ab').iterdir())

    def run_trim(self, *args):
        return subprocess.run(['/bin/bash', str(ROOT / 'bin/go-cache-trim'), *args],
                              cwd=self.path, env=self.env, capture_output=True, text=True, timeout=20)

    def test_drops_unused_entries_then_least_recently_used_down_to_the_cap(self):
        size = self.entry(self.cache, 'unused', 30)
        for name, hours in (('lru-oldest', 10), ('lru-next', 5), ('recent', 1), ('new', 0)):
            self.entry(self.cache, name, hours)
        (self.cache / 'fuzz' / 'corpus').write_text('x')
        self.cap(2 * size + 4096)
        p = self.run_trim()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.entries(self.cache), ['new', 'recent'])
        self.assertTrue((self.cache / 'fuzz' / 'corpus').exists())
        self.assertTrue((self.cache / 'README').exists())
        self.assertIn('deleted 3 entries', p.stdout)
        self.assertIn('listed 1 unused for 24 h and 2 least recently used', p.stdout)

    def test_keeps_entries_used_in_the_last_two_hours_over_the_cap(self):
        size = self.entry(self.cache, 'older', 3)
        self.entry(self.cache, 'recent', 1)
        self.cap(size // 2)
        p = self.run_trim()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.entries(self.cache), ['recent'])
        self.assertIn('still over the cap, with entries used in the last 2 h', p.stdout)

    def test_dry_run_deletes_nothing(self):
        size = self.entry(self.cache, 'unused', 30)
        self.entry(self.cache, 'lru', 5)
        self.cap(size + 4096)
        p = self.run_trim('--dry-run')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.entries(self.cache), ['lru', 'unused'])
        self.assertIn('would delete 1 entries', p.stdout)

    def test_trims_extra_caches_and_refuses_a_directory_that_is_not_a_cache(self):
        extra = self.make_cache('extra')
        self.entry(extra, 'unused', 30)
        stranger = self.path / 'stranger'
        (stranger / 'ab').mkdir(parents=True)
        (stranger / 'ab' / 'keep').write_text('x')
        never_used = self.path / 'never-used'
        never_used.mkdir()
        self.env['GO_EXTRA_BUILD_CACHES'] = f'{stranger}:{extra}/:{self.cache}:{never_used}'
        p = self.run_trim()
        self.assertEqual(p.returncode, 1)
        self.assertIn(f'{stranger} is not a Go build cache', p.stderr)
        self.assertTrue((stranger / 'ab' / 'keep').exists())
        self.assertFalse((extra / 'ab' / 'unused').exists())
        self.assertIn(f'cache {never_used} empty', p.stdout)
        self.assertEqual(p.stdout.count(f'from {self.cache}:'), 1)

    def test_rejects_a_cap_that_is_not_a_positive_number_of_gib(self):
        for value in ('0', '-5', '400G', ''):
            self.env['GO_CACHE_TRIM_MAX_GIB'] = value
            with self.subTest(value=value):
                p = self.run_trim()
                if value == '':
                    self.assertEqual(p.returncode, 0, p.stderr)
                else:
                    self.assertEqual(p.returncode, 2)
                    self.assertIn('want a number of GiB above 0', p.stderr)


class DisableAerials(Fixture):
    """bin/disable-aerials against a store laid out as macOS 27 writes it before
    anyone picks a wallpaper: every entry linked to the default aerial."""

    SCRIPT = ROOT / 'bin/disable-aerials'

    def setUp(self):
        super().setUp()
        self.env['XDG_STATE_HOME'] = str(self.path / 'state')
        self.store = self.path / 'Store/Index.plist'
        self.picture = self.path / 'Still.png'
        self.picture.write_bytes(b'png')
        self.saver = self.path / 'Message.saver'
        (self.saver / 'Contents').mkdir(parents=True)
        (self.saver / 'Contents/Info.plist').write_bytes(plistlib.dumps({}))

    @staticmethod
    def linked():
        return {'Linked': {'Content': {'Choices': [{'Configuration': b'', 'Files': [], 'Provider': 'default'}],
                                       'EncodedOptionValues': '$null', 'Shuffle': '$null'}},
                'Type': 'linked'}

    def write_store(self, store):
        self.store.parent.mkdir(parents=True, exist_ok=True)
        self.store.write_bytes(plistlib.dumps(store, fmt=plistlib.FMT_BINARY))

    def run_script(self, *args, saver=None):
        return subprocess.run([str(self.SCRIPT), '--store', str(self.store), '--picture', str(self.picture),
                               '--saver', str(saver or self.saver), *args],
                              env=self.env, capture_output=True, text=True, timeout=20)

    def choice(self, entry, slot):
        choice = entry[slot]['Content']['Choices'][0]
        return choice['Provider'], plistlib.loads(choice['Configuration'])

    def backups(self):
        directory = self.path / 'state/dotfiles/wallpaper'
        return sorted(directory.iterdir()) if directory.exists() else []

    def assert_still(self, entry):
        self.assertEqual(entry['Type'], 'individual')
        self.assertNotIn('Linked', entry)
        self.assertEqual(self.choice(entry, 'Desktop'),
                         ('com.apple.wallpaper.choice.image',
                          {'type': 'imageFile', 'url': {'relative': self.picture.resolve().as_uri()}}))
        self.assertEqual(self.choice(entry, 'Idle'),
                         ('com.apple.wallpaper.choice.screen-saver',
                          {'module': {'relative': self.saver.resolve().as_uri() + '/'}}))

    def test_every_linked_entry_gets_the_still_picture_and_saver(self):
        self.write_store({'AllSpacesAndDisplays': self.linked(), 'SystemDefault': self.linked(),
                          'Displays': {'37D8832A-2D66-02CA-B9F7-8F30A301B230': self.linked()}, 'Spaces': {}})
        before = self.store.read_bytes()
        p = self.run_script()
        self.assertEqual(p.returncode, 0, p.stderr)
        store = plistlib.loads(self.store.read_bytes())
        for entry in (store['AllSpacesAndDisplays'], store['SystemDefault'],
                      store['Displays']['37D8832A-2D66-02CA-B9F7-8F30A301B230']):
            self.assert_still(entry)
        self.assertEqual(store['Spaces'], {})
        [backup] = self.backups()
        self.assertEqual(backup.read_bytes(), before)

    def test_a_second_run_changes_nothing(self):
        self.write_store({'AllSpacesAndDisplays': self.linked(), 'SystemDefault': self.linked()})
        self.assertEqual(self.run_script().returncode, 0)
        after_first = self.store.read_bytes()
        p = self.run_script()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('has no aerial', p.stdout)
        self.assertEqual(self.store.read_bytes(), after_first)
        self.assertEqual(len(self.backups()), 1)

    @staticmethod
    def slot(provider, configuration):
        return {'Content': {'Choices': [{'Configuration': plistlib.dumps(configuration, fmt=plistlib.FMT_BINARY),
                                         'Files': [], 'Provider': provider}],
                            'EncodedOptionValues': '$null', 'Shuffle': '$null'}}

    def chosen_picture(self):
        return self.slot('com.apple.wallpaper.choice.image',
                         {'type': 'imageFolder', 'url': {'relative': 'file:///Users/someone/Wallpapers/'}})

    def chosen_saver(self):
        return self.slot('com.apple.wallpaper.choice.screen-saver',
                         {'module': {'relative': 'file:///System/Library/Screen%20Savers/Hello.saver/'}})

    def test_chosen_pictures_and_savers_are_left_alone(self):
        # As a Mac whose owner picked a picture folder per display: nothing is an aerial.
        self.write_store({'AllSpacesAndDisplays': {'Type': 'individual', 'Idle': self.chosen_saver()},
                          'SystemDefault': {'Type': 'individual', 'Desktop': self.chosen_picture(),
                                            'Idle': self.chosen_saver()},
                          'Displays': {'32F6F12E': {'Type': 'individual', 'Desktop': self.chosen_picture(),
                                                    'Idle': self.chosen_saver()}},
                          'Spaces': {}})
        before = self.store.read_bytes()
        p = self.run_script()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('has no aerial', p.stdout)
        self.assertEqual(self.store.read_bytes(), before)
        self.assertEqual(self.backups(), [])

    def test_only_the_aerial_slot_of_an_entry_is_replaced(self):
        self.write_store({'AllSpacesAndDisplays': {'Type': 'individual', 'Desktop': self.chosen_picture(),
                                                   'Idle': self.slot('com.apple.wallpaper.choice.aerials', {})},
                          'SystemDefault': {'Type': 'linked',
                                            'Linked': self.slot('com.apple.wallpaper.choice.dynamic', {})}})
        p = self.run_script()
        self.assertEqual(p.returncode, 0, p.stderr)
        store = plistlib.loads(self.store.read_bytes())
        entry = store['AllSpacesAndDisplays']
        self.assertEqual(self.choice(entry, 'Desktop'),
                         ('com.apple.wallpaper.choice.image',
                          {'type': 'imageFolder', 'url': {'relative': 'file:///Users/someone/Wallpapers/'}}))
        self.assertEqual(self.choice(entry, 'Idle'),
                         ('com.apple.wallpaper.choice.screen-saver',
                          {'module': {'relative': self.saver.resolve().as_uri() + '/'}}))
        self.assertEqual(store['SystemDefault']['Type'], 'linked')
        self.assertEqual(store['SystemDefault']['Linked']['Content']['Choices'][0]['Provider'],
                         'com.apple.wallpaper.choice.dynamic')
        self.assertIn('/AllSpacesAndDisplays', p.stdout)
        self.assertNotIn('/SystemDefault', p.stdout)

    def test_dry_run_writes_nothing(self):
        self.write_store({'AllSpacesAndDisplays': self.linked()})
        before = self.store.read_bytes()
        p = self.run_script('--dry-run')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('/AllSpacesAndDisplays', p.stdout)
        self.assertEqual(self.store.read_bytes(), before)
        self.assertEqual(self.backups(), [])

    def test_a_missing_store_is_created_with_stills(self):
        p = self.run_script()
        self.assertEqual(p.returncode, 0, p.stderr)
        store = plistlib.loads(self.store.read_bytes())
        self.assert_still(store['AllSpacesAndDisplays'])
        self.assert_still(store['SystemDefault'])

    def test_an_unknown_entry_layout_is_refused_untouched(self):
        self.write_store({'AllSpacesAndDisplays': self.linked(), 'SystemDefault': {'Type': 'per-app', 'Desktop': {}}})
        before = self.store.read_bytes()
        p = self.run_script()
        self.assertEqual(p.returncode, 1)
        self.assertIn("/SystemDefault: unknown entry type 'per-app'", p.stderr)
        self.assertEqual(self.store.read_bytes(), before)
        self.assertEqual(self.backups(), [])

    def test_a_saver_that_is_not_a_bundle_is_refused(self):
        self.write_store({'AllSpacesAndDisplays': self.linked()})
        p = self.run_script(saver=self.picture)
        self.assertEqual(p.returncode, 2)
        self.assertIn('not a screen saver bundle', p.stderr)


class SpotlightExclusions(Fixture):
    """Config parsing and planning; the calls into mds are exercised by `spotlight-exclusions check`."""
    FEATURE = FEATURES / 'macos.spotlight'

    @classmethod
    def setUpClass(cls):
        import importlib.machinery
        import importlib.util
        script = cls.FEATURE / 'home/.local/bin/spotlight-exclusions'
        loader = importlib.machinery.SourceFileLoader('spotlight_exclusions', str(script))
        cls.tool = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(cls.tool)

    def config(self, text):
        path = self.path / 'exclusions'
        path.write_text(text)
        return path

    def test_config_expands_home_normalizes_and_drops_comments_and_duplicates(self):
        from unittest import mock
        home = self.path / 'home'
        text = '# comment\n\n~/Library/pnpm\n  /usr/local/  \n~/Library/../Library/pnpm\n'
        with mock.patch.dict(os.environ, HOME=str(home)):
            folders = self.tool.read_config(self.config(text))
        self.assertEqual(folders, [str(home / 'Library/pnpm'), '/usr/local'])

    def test_relative_path_is_rejected_with_its_line(self):
        with self.assertRaisesRegex(self.tool.ConfigError, r'exclusions:2: .*not an absolute'):
            self.tool.read_config(self.config('/usr/local\nLibrary/pnpm\n'))

    def test_shipped_config_parses(self):
        folders = self.tool.read_config(self.FEATURE / 'home/.config/spotlight/exclusions')
        self.assertIn('/usr/local', folders)
        self.assertTrue(all(os.path.isabs(f) for f in folders))

    def test_plan_matches_folders_by_identity_not_spelling(self):
        kept, new = self.path / 'kept', self.path / 'new'
        kept.mkdir()
        new.mkdir()
        alias = self.path / 'alias'
        alias.symlink_to(kept)
        absent = str(self.path / 'absent')
        result = self.tool.plan([str(kept), str(new), absent], current=[str(alias), str(self.path / 'gone')])
        self.assertEqual(result.excluded, [str(kept)])
        self.assertEqual(result.add, [str(new)])
        self.assertEqual(result.absent, [absent])

    def configured(self, shared, local=None):
        from unittest import mock
        self.config(shared)
        if local is not None:
            (self.path / 'exclusions.local').write_text(local)
        with mock.patch.dict(os.environ, SPOTLIGHT_EXCLUSIONS_FILE=str(self.path / 'exclusions')):
            return self.tool.configured_folders()

    def test_local_list_follows_the_shared_list_without_duplicates(self):
        folders = self.configured('/usr/local\n/opt/shared\n', local='/opt/checkout\n/usr/local\n')
        self.assertEqual(folders, ['/usr/local', '/opt/shared', '/opt/checkout'])

    def test_missing_local_list_leaves_the_shared_list(self):
        self.assertEqual(self.configured('/usr/local\n'), ['/usr/local'])

    def test_the_feature_check_reports_what_apply_would_exclude(self):
        kept, new = self.path / 'kept', self.path / 'new'
        kept.mkdir()
        new.mkdir()
        self.config(f'{kept}\n{new}\n{self.path / "absent"}\n')
        store = self.path / 'store.json'
        store.write_text(json.dumps([str(kept)]))
        tool = self.FEATURE / 'home/.local/bin/spotlight-exclusions'
        env = dict(self.env, SPOTLIGHT_EXCLUSIONS_FILE=str(self.path / 'exclusions'),
                   SPOTLIGHT_EXCLUSIONS_STORE=str(store))

        def check():
            p = subprocess.run([sys.executable, str(tool), 'check', '--json'], env=env,
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(p.returncode, 0, p.stderr)
            return json.loads(p.stdout)

        if sys.platform != 'darwin':
            self.skipTest('Spotlight exists only on macOS')
        self.assertEqual(check(), {'state': 'drift', 'detail': f'Spotlight indexes {new}'})
        p = subprocess.run([sys.executable, str(tool), 'apply'], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(store.read_text()), [str(kept), str(new)])
        self.assertEqual(check(), {'state': 'ok', 'detail': ''})
        env['SPOTLIGHT_EXCLUSIONS_FILE'] = str(self.path / 'missing')
        self.assertEqual(check()['state'], 'error', 'a check that cannot read its list says so, and exits 0')

    def fake_mdfind(self, results, status=0):
        """An mdfind on PATH that logs its scope and prints RESULTS (one path per line)."""
        log = self.path / 'mdfind.log'
        listing = self.path / 'mdfind.out'
        listing.write_text(''.join(f'{r}\n' for r in results))
        script = self.bin / 'mdfind'
        script.write_text(f'#!/bin/sh\necho "$2" >> "{log}"\ncat "{listing}"\nexit {status}\n')
        script.chmod(0o755)
        return log

    def test_counts_come_from_one_query_on_the_parent(self):
        from unittest import mock
        work, code = self.path / 'work', self.path / 'code'
        work.mkdir()
        code.mkdir()
        # mdfind prints canonical paths: /private/var, not the /var symlink.
        real = Path(os.path.realpath(self.path))
        log = self.fake_mdfind([real / 'work/a', real / 'work/b/c', real / 'code/d', real / 'workshop/e', real / 'f'])
        with mock.patch.dict(os.environ, PATH=f'{self.bin}{os.pathsep}{os.environ["PATH"]}'):
            counts = self.tool.indexed_items([str(work), str(code)], timeout=10)
        self.assertEqual(counts, {str(work): '2', str(code): '1'})
        self.assertEqual(log.read_text().split(), [os.path.realpath(self.path)])

    def test_failed_count_reads_unknown(self):
        from unittest import mock
        work = self.path / 'work'
        work.mkdir()
        self.fake_mdfind([work / 'a'], status=1)
        with mock.patch.dict(os.environ, PATH=f'{self.bin}{os.pathsep}{os.environ["PATH"]}'):
            self.assertEqual(self.tool.indexed_items([str(work)], timeout=10), {str(work): '?'})

    def test_local_list_errors_name_the_local_file(self):
        (self.path / 'file').write_text('')
        with self.assertRaisesRegex(self.tool.ConfigError, r'exclusions\.local: .*file is not a folder'):
            self.configured('/usr/local\n', local=f'{self.path / "file"}\n')



class DiskHygiene(Fixture):
    """bin/disk-hygiene deletes what nobody has used for its window and caps agent logs."""

    OLD = time.time() - 30 * 86400
    SESSION = '0e351e5b-ab30-4b92-ba41-ef1112fdc582'
    OTHER = '7afe0905-7498-4687-ad48-608587873eb8'

    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        self.tmp = self.path / 'tmp'
        self.volumes = self.path / 'Volumes'
        self.agents = self.home / 'Library/LaunchAgents'
        self.apply_state = self.path / 'state/dotfiles/applied.json'
        for d in (self.home / '.cache', self.tmp, self.volumes, self.agents):
            d.mkdir(parents=True)
        self.env.update(HOME=str(self.home), DISK_HYGIENE_TMP=str(self.tmp),
                        DISK_HYGIENE_VOLUMES=str(self.volumes), XDG_STATE_HOME=str(self.path / 'state'),
                        CODEX_HOME=str(self.home / '.codex'))
        self.env.pop('DISK_HYGIENE_KEEP', None)
        self.env.pop('DISK_HYGIENE_TRANSCRIPT_DAYS', None)
        self.env.pop('DISK_HYGIENE_KEYED', None)
        self.env.pop('DISK_HYGIENE_CACHE_DRIVE', None)
        self.env.pop('DISK_HYGIENE_RELOCATE', None)

    def tree(self, root, files=('data',), age=None):
        """A directory holding FILES; with AGE, every entry was last used that long ago."""
        root.mkdir(parents=True, exist_ok=True)
        for name in files:
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text('x')
        if age is not None:
            for entry in sorted(root.rglob('*'), key=lambda e: -len(e.parts)) + [root]:
                os.utime(entry, (age, age), follow_symlinks=False)
        return root

    def run_hygiene(self, *args):
        return subprocess.run([str(ROOT / 'bin/disk-hygiene'), *args], env=self.env,
                              capture_output=True, text=True, timeout=60)

    def scratch(self, tmp, project, session):
        return tmp / f'claude-{os.getuid()}' / project / session

    def test_deletes_only_scratch_of_sessions_unused_for_the_window(self):
        stale = self.tree(self.scratch(self.tmp, '-Users-me', self.SESSION), ('tasks/a.output',), self.OLD)
        # A live session's markers are directories with nothing inside.
        live = self.scratch(self.tmp, '-Users-me', self.OTHER)
        for d in ('started', 'scratchpad'):
            (live / d).mkdir(parents=True)
        not_a_session = self.tree(self.scratch(self.tmp, '-Users-me', 'notes'), age=self.OLD)
        not_a_project = self.tree(self.scratch(self.tmp, 'bundled-skills', '2.1.325'), age=self.OLD)
        on_drive = self.tree(self.scratch(self.volumes / 'D/tmp', '-Volumes-D-w', self.SESSION), age=self.OLD)
        p = self.run_hygiene()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse(stale.exists())
        self.assertFalse(on_drive.exists())
        self.assertFalse(on_drive.parent.exists(), 'an emptied project directory stays behind')
        for kept in (live, not_a_session, not_a_project):
            self.assertTrue(kept.exists(), kept)

    def rollout(self, rel, session, written, read=None):
        """A Codex transcript under CODEX_HOME/REL, last written at WRITTEN and read at READ."""
        f = self.home / '.codex' / rel / f'rollout-2026-01-02T03-04-05-{session}.jsonl'
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text('{}\n')
        os.utime(f, (read or written, written))
        return f

    def stub_codex(self, failing=''):
        """A codex whose `delete --force ID` removes ID's transcript, except FAILING's."""
        audit = self.path / 'codex-audit'
        self.cli('codex', f'printf "%s\\n" "$*" >> {audit}\n'
                          '[ "$1" = delete ] && [ "$2" = --force ] || exit 2\n'
                          f'[ "$3" = "{failing}" ] && exit 1\n'
                          'find "$CODEX_HOME" -name "rollout-*-$3.jsonl" -delete')
        return lambda: sorted(audit.read_text().splitlines()) if audit.exists() else []

    def test_codex_sessions_unwritten_for_the_window_are_deleted_through_codex(self):
        stale_ids = ('11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222',
                     '33333333-3333-4333-8333-333333333333')
        long_ago = time.time() - 120 * 86400
        stale = self.rollout('sessions/2026/01/02', stale_ids[0], long_ago)
        only_read = self.rollout('sessions/2026/01/03', stale_ids[1], long_ago, read=time.time())
        archived = self.rollout('archived_sessions', stale_ids[2], long_ago)
        fresh = self.rollout('sessions/2026/11/25', self.SESSION, time.time(), read=long_ago)
        within_window = self.rollout('sessions/2026/09/26', self.OTHER, time.time() - 60 * 86400)
        notes = self.home / '.codex/sessions/notes.txt'
        notes.write_text('x')
        os.utime(notes, (long_ago, long_ago))
        calls = self.stub_codex()

        p = self.run_hygiene('--dry-run')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(calls(), [], 'a dry run deletes nothing')
        self.assertEqual(p.stdout.count('would delete Codex session'), 3, p.stdout)

        p = self.run_hygiene()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(calls(), sorted(f'delete --force {i}' for i in stale_ids))
        for gone in (stale, only_read, archived):
            self.assertFalse(gone.exists(), gone)
        self.assertFalse(stale.parent.exists(), 'the emptied date directory goes')
        for stays in (fresh, within_window, notes, self.home / '.codex/sessions'):
            self.assertTrue(stays.exists(), stays)

    def test_a_codex_session_codex_cannot_delete_fails_the_run(self):
        stuck = self.rollout('sessions/2026/01/02', self.OTHER, time.time() - 120 * 86400)
        self.stub_codex(failing=self.OTHER)
        p = self.run_hygiene()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn(f'could not delete Codex session {self.OTHER}', p.stdout)
        self.assertTrue(stuck.exists())

    def test_caches_go_whole_or_a_key_at_a_time(self):
        cache = self.home / '.cache'
        unused = self.tree(cache / 'oldtool', ('a', 'deep/b'), self.OLD)
        in_use = self.tree(cache / 'livetool', ('old',), self.OLD)
        (in_use / 'fresh').write_text('x')
        old_key = self.tree(cache / 'repo-a/pr1-sync', age=self.OLD)
        new_key = self.tree(cache / 'repo-a/pr2-sync')
        generated = self.home / '.config/dotfiles/generated'
        generated.mkdir(parents=True)
        (generated / 'env.sh').write_text("export DISK_HYGIENE_KEYED='repo-a'\n")
        kept = self.tree(cache / 'models', age=self.OLD)
        target = self.tree(self.path / 'elsewhere', age=self.OLD)
        (cache / 'linked').symlink_to(target)
        on_drive = self.tree(self.volumes / 'D/cache/xdg/oldtool', age=self.OLD)
        self.env['DISK_HYGIENE_KEEP'] = 'models'
        p = self.run_hygiene()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        for gone in (unused, old_key, on_drive):
            self.assertFalse(gone.exists(), gone)
        for stays in (in_use / 'old', new_key, kept, target / 'data', cache / 'linked'):
            self.assertTrue(stays.exists(), stays)

    def test_read_only_trees_are_removed(self):
        tool = self.tree(self.home / '.cache/tool', ('mod/example.com@v1/go.mod',), self.OLD)
        module = tool / 'mod/example.com@v1'
        (module / 'go.mod').chmod(0o444)
        module.chmod(0o555)
        p = self.run_hygiene()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse((self.home / '.cache/tool').exists())

    def test_an_entry_it_cannot_read_all_of_counts_as_used(self):
        tool = self.tree(self.home / '.cache/tool', ('private/data', 'other'), self.OLD)
        (tool / 'private').chmod(0)
        self.addCleanup((tool / 'private').chmod, 0o755)
        p = self.run_hygiene()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue((tool / 'other').exists())

    def test_file_caches_lose_only_their_unused_files(self):
        index = self.home / 'Library/Caches/goimports'
        self.tree(index, ('old.idx',), self.OLD)
        (index / 'new.idx').write_text('x')
        p = self.run_hygiene()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(sorted(f.name for f in index.iterdir()), ['new.idx'])

    def cache_drive(self, relocate):
        """A mounted drive D named as the cache drive, relocating RELOCATE."""
        drive = self.volumes / 'D'
        drive.mkdir()
        self.env.update(DISK_HYGIENE_CACHE_DRIVE=str(drive), DISK_HYGIENE_RELOCATE=relocate)
        return drive

    def test_caches_move_to_the_cache_drive_and_their_internal_copies_go(self):
        drive = self.cache_drive('Library/Caches/gopls .cache/uv Library/Caches/staticcheck '
                                 'Library/Caches/absent .npm/_cacache=npm')
        caches = self.home / 'Library/Caches'
        gopls = self.tree(caches / 'gopls', ('index/a',))
        uv = self.tree(self.home / '.cache/uv', ('wheels/b',))
        elsewhere = self.tree(self.path / 'elsewhere')
        (caches / 'staticcheck').symlink_to(elsewhere)
        p = self.run_hygiene()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        for src, name in ((gopls, 'gopls'), (uv, 'uv')):
            with self.subTest(name):
                self.assertTrue(src.is_symlink(), src)
                self.assertEqual(os.readlink(src), str(drive / 'cache/xdg' / name))
                self.assertEqual(list((drive / 'cache/xdg' / name).iterdir()), [], 'a moved cache starts over')
                self.assertIn(f'moved cache {src} to {drive}/cache/xdg/{name}', p.stdout)
        self.assertEqual(os.readlink(caches / 'staticcheck'), str(elsewhere), 'a link it did not make stays')
        self.assertFalse(os.path.lexists(caches / 'absent'), 'a cache its tool never made is not linked')
        self.assertFalse((self.home / '.npm').exists())
        self.assertEqual(list(self.home.rglob('*.disk-hygiene-*')), [], 'the internal copy is deleted')

    def test_a_relocated_cache_pruned_whole_on_the_drive_gets_its_directory_back(self):
        drive = self.cache_drive('Library/Caches/gopls')
        target = self.tree(drive / 'cache/xdg/gopls', ('old',), self.OLD)
        (self.home / 'Library/Caches').mkdir(parents=True)
        (self.home / 'Library/Caches/gopls').symlink_to(target)
        p = self.run_hygiene()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(target.is_dir(), 'a tool would find its link dangling')
        self.assertFalse((target / 'old').exists())
        self.assertIn(f'recreated {target}', p.stdout)

    def test_a_relocated_file_cache_still_loses_only_its_unused_files(self):
        drive = self.cache_drive('Library/Caches/goimports')
        target = self.tree(drive / 'cache/xdg/goimports', ('old.idx',), self.OLD)
        (target / 'new.idx').write_text('x')
        (self.home / 'Library/Caches').mkdir(parents=True)
        (self.home / 'Library/Caches/goimports').symlink_to(target)
        p = self.run_hygiene()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(sorted(f.name for f in target.iterdir()), ['new.idx'])

    def test_a_cache_a_running_process_has_open_waits(self):
        self.cache_drive('Library/Caches/index')
        index = self.tree(self.home / 'Library/Caches/index', ('db.sqlite',))
        holder = subprocess.Popen([sys.executable, '-c', 'import sys, time; f = open(sys.argv[1]); print("open", flush=True); time.sleep(60)',
                                   str(index / 'db.sqlite')], stdout=subprocess.PIPE, text=True)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), 'open')
        p = self.run_hygiene()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse(index.is_symlink())
        self.assertTrue((index / 'db.sqlite').exists())
        self.assertIn(f'cache {index} is open in a running process', p.stdout)

    def test_caches_stay_while_the_cache_drive_is_not_mounted(self):
        self.env.update(DISK_HYGIENE_CACHE_DRIVE=str(self.volumes / 'Gone'), DISK_HYGIENE_RELOCATE='Library/Caches/gopls')
        gopls = self.tree(self.home / 'Library/Caches/gopls')
        p = self.run_hygiene()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse(gopls.is_symlink())
        self.assertTrue((gopls / 'data').exists())
        self.assertIn('is not mounted', p.stdout)

    def test_dry_run_moves_no_cache(self):
        drive = self.cache_drive('Library/Caches/gopls')
        gopls = self.tree(self.home / 'Library/Caches/gopls')
        p = self.run_hygiene('--dry-run')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse(gopls.is_symlink())
        self.assertFalse((drive / 'cache').exists())
        self.assertIn(f'would move cache {gopls} to {drive}/cache/xdg/gopls', p.stdout)

    def test_rejects_relocate_entries_outside_home(self):
        drive = self.cache_drive('/etc/x Library/../../up Library/Caches/ok=a/b')
        p = self.run_hygiene()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        for entry in ('/etc/x', 'Library/../../up', 'Library/Caches/ok=a/b'):
            self.assertIn(f'DISK_HYGIENE_RELOCATE entry {entry}: want', p.stdout)
        self.assertFalse((drive / 'cache').exists())

    def agent(self, label, log, applied):
        """An installed LaunchAgent logging to LOG; APPLIED records it as dotfiles apply's."""
        plist = (f'<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0"><dict>'
                 f'<key>Label</key><string>{label}</string>'
                 f'<key>StandardOutPath</key><string>{log}</string>'
                 f'<key>StandardErrorPath</key><string>{log}</string></dict></plist>\n')
        installed = self.agents / f'{label}.plist'
        installed.write_text(plist)
        if applied:
            state = json.loads(self.apply_state.read_text()) if self.apply_state.exists() else {'version': 1}
            state.setdefault('agents', {})[label] = {'path': str(installed), 'sha256': '', 'loaded': ''}
            self.apply_state.parent.mkdir(parents=True, exist_ok=True)
            self.apply_state.write_text(json.dumps(state))

    def test_caps_the_logs_of_the_agents_apply_installed_in_place_from_a_line_boundary(self):
        ours, theirs = self.path / 'ours.log', self.path / 'theirs.log'
        lines = ''.join(f'line {n:04d}\n' for n in range(400))
        for log in (ours, theirs):
            log.write_text(lines)
        self.agent('com.example.ours', ours, applied=True)
        self.agent('com.example.theirs', theirs, applied=False)
        inode = ours.stat().st_ino
        self.env['DISK_HYGIENE_LOG_MAX_BYTES'] = '1000'
        p = self.run_hygiene()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        capped = ours.read_text()
        self.assertEqual(ours.stat().st_ino, inode, 'launchd would go on writing to a moved file')
        self.assertLessEqual(len(capped), 500)
        self.assertTrue(capped.startswith('line ') and capped.endswith('line 0399\n'), capped[:20])
        self.assertEqual(theirs.read_text(), lines)

    def test_dry_run_changes_nothing(self):
        stale = self.tree(self.scratch(self.tmp, '-Users-me', self.SESSION), age=self.OLD)
        unused = self.tree(self.home / '.cache/oldtool', age=self.OLD)
        p = self.run_hygiene('--dry-run')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(stale.exists() and unused.exists())
        self.assertIn(f'would remove cache {unused}', p.stdout)

    def test_rejects_windows_that_are_not_whole_days(self):
        for value in ('0', '-1', '1.5', 'week'):
            with self.subTest(value=value):
                self.env['DISK_HYGIENE_CACHE_DAYS'] = value
                p = self.run_hygiene('--dry-run')
                self.assertEqual(p.returncode, 2)
                self.assertIn('DISK_HYGIENE_CACHE_DAYS', p.stderr)


class RotateLog(Fixture):
    """rotate_log moves an outgrown log aside and keeps the newest archives."""

    def test_rotates_past_the_limit_and_keeps_the_newest_archives(self):
        log = self.path / 'sync.log'
        for epoch in (1700000000, 1700000100, 1700000200):
            (self.path / f'sync.log.{epoch}.old').write_text('old')
        log.write_text('x' * 20)
        p = self.bash('rotate_log "$1" 10 2', str(log), source='lib_sh/rotate-log.sh')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(log.exists())
        archives = sorted(f.name for f in self.path.glob('sync.log.*.old'))
        self.assertEqual(len(archives), 2)
        self.assertEqual(archives[0], 'sync.log.1700000200.old')

    def test_leaves_a_log_within_the_limit(self):
        log = self.path / 'sync.log'
        log.write_text('x' * 5)
        p = self.bash('rotate_log "$1" 10 2', str(log), source='lib_sh/rotate-log.sh')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(log.read_text(), 'x' * 5)


class SessionDrive(Fixture):
    """A session working on a drive keeps its scratch and its commands' caches there."""

    def drive_env(self, cwd, volumes):
        source = (FEATURES / 'agents.claude/zshrc.zsh').read_text()
        helper = source[source.index('_claude_drive_env() {'):]
        helper = helper[:helper.index('\n}\n') + 3]
        p = subprocess.run(['/bin/zsh', '-fc', helper + '_claude_drive_env "$1"; print -rl -- $reply',
                            'test', str(volumes)], cwd=cwd, env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.split()

    def test_a_linked_directory_on_a_drive_uses_that_drive(self):
        volumes = self.path.resolve() / 'Volumes'
        work = volumes / 'D/workgroups/repo'
        work.mkdir(parents=True)
        (self.path / 'workgroups').symlink_to(volumes / 'D/workgroups')
        env = self.drive_env(self.path / 'workgroups/repo', volumes)
        self.assertEqual(env, [f'CLAUDE_CODE_TMPDIR={volumes}/D/tmp',
                               f'DOTFILES_CACHE_HOME={volumes}/D/cache/xdg'])
        self.assertTrue((volumes / 'D/tmp').is_dir() and (volumes / 'D/cache/xdg').is_dir())

    def test_a_directory_off_the_drives_changes_nothing(self):
        (self.path / 'Volumes').mkdir()
        self.assertEqual(self.drive_env(self.path, self.path.resolve() / 'Volumes'), [])

    def test_shells_cache_on_the_drive_but_gitstead_keeps_its_cache(self):
        home = self.path / 'home'
        home.mkdir()
        install_shell(home, set())
        drive_cache = self.path / 'cache-xdg'
        drive_cache.mkdir()
        code = '. "$HOME/.config/shell/env.sh"; . "$HOME/.config/shell/env.sh"; printf "%s\\n" "$XDG_CACHE_HOME" "$GITSTEAD_CACHE"'
        for cache_home, expected in ((str(drive_cache), [str(drive_cache), f'{home}/.cache/gitstead']),
                                     (str(self.path / 'missing'), ['', ''])):
            with self.subTest(cache_home=cache_home):
                env = {'HOME': str(home), 'PATH': '/usr/bin:/bin', 'DOTFILES_CACHE_HOME': cache_home}
                p = subprocess.run(['/bin/sh', '-c', code], env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stdout.split('\n')[:2], expected)


class PasskeysOff(Fixture):
    FEATURE = FEATURES / 'browser.passkeys-off'
    EXTENSION = FEATURE / 'home/.local/share/browser-extensions/passkeys-off'
    TOOL = FEATURE / 'home/.local/bin/passkeys-off'

    def setUp(self):
        super().setUp()
        self.firefox = self.path / 'Firefox'
        self.chromium = self.path / 'Brave-Browser'
        self.env.update(PASSKEYS_OFF_FIREFOX=str(self.firefox), PASSKEYS_OFF_CHROMIUM=str(self.chromium),
                        PASSKEYS_OFF_EXTENSION=str(self.EXTENSION))

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(self.TOOL), *args], env=self.env,
                              capture_output=True, text=True, timeout=20)

    def firefox_profiles(self):
        """One relative and one absolute profile, as profiles.ini lists them."""
        relative = self.firefox / 'Profiles/abc.default-release'
        absolute = self.path / 'elsewhere/xyz.work'
        relative.mkdir(parents=True)
        absolute.mkdir(parents=True)
        (self.firefox / 'profiles.ini').write_text(
            '[General]\nStartWithLastProfile=1\n\n'
            '[Profile0]\nName=default-release\nIsRelative=1\nPath=Profiles/abc.default-release\n\n'
            f'[Profile1]\nName=work\nIsRelative=0\nPath={absolute}\n\n[Install4F96D1932A9F858E]\nDefault=x\n')
        return relative, absolute

    def chromium_profile(self, name, extensions):
        profile = self.chromium / name
        profile.mkdir(parents=True)
        (profile / 'Secure Preferences').write_text(json.dumps({'extensions': {'settings': extensions}}))

    @unittest.skipUnless(shutil.which('node'), 'node required to run the extension script')
    def test_extension_refuses_passkeys_and_keeps_explicit_sign_in(self):
        manifest = json.loads((self.EXTENSION / 'manifest.json').read_text())
        script = manifest['content_scripts'][0]
        self.assertEqual((script['world'], script['run_at'], script['all_frames']), ('MAIN', 'document_start', True))
        harness = self.path / 'harness.mjs'
        harness.write_text("""
const {readFileSync} = await import('node:fs');
const calls = [];
globalThis.CredentialsContainer = class {
  create(options) { calls.push('create'); return Promise.resolve('native create'); }
  get(options) { calls.push('get'); return Promise.resolve('native get'); }
};
globalThis.PublicKeyCredential = class {};
PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable = async () => true;
PublicKeyCredential.isConditionalMediationAvailable = async () => true;
PublicKeyCredential.getClientCapabilities = async () => ({conditionalGet: true, hybridTransport: true});
(0, eval)(readFileSync(process.env.SCRIPT, 'utf8'));
const credentials = new CredentialsContainer();
const settle = (p) => p.then((v) => `resolved: ${v}`, (e) => e.name);
const page = new AbortController();
const conditional = settle(credentials.get({publicKey: {}, mediation: 'conditional', signal: page.signal}));
const pending = await Promise.race([conditional, new Promise((r) => setTimeout(() => r('pending'), 50))]);
page.abort(new DOMException('page cancelled', 'AbortError'));
process.stdout.write(JSON.stringify({
  uvpaa: await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable(),
  conditionalAvailable: await PublicKeyCredential.isConditionalMediationAvailable(),
  capabilities: await PublicKeyCredential.getClientCapabilities(),
  createPasskey: await settle(credentials.create({publicKey: {}})),
  createPassword: await settle(credentials.create({password: {}})),
  conditionalBeforeAbort: pending,
  conditionalAfterAbort: await conditional,
  explicitSignIn: await settle(credentials.get({publicKey: {}})),
  nativeCalls: calls,
}));
""")
        env = dict(self.env, SCRIPT=str(self.EXTENSION / script['js'][0]))
        p = subprocess.run(['node', str(harness)], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout), {
            'uvpaa': False,
            'conditionalAvailable': False,
            'capabilities': {'conditionalGet': False, 'hybridTransport': False},
            'createPasskey': 'NotAllowedError',
            'createPassword': 'resolved: native create',
            'conditionalBeforeAbort': 'pending',
            'conditionalAfterAbort': 'AbortError',
            'explicitSignIn': 'resolved: native get',
            'nativeCalls': ['create', 'get'],
        })

    def test_apply_writes_the_block_once_and_keeps_other_prefs(self):
        relative, absolute = self.firefox_profiles()
        (relative / 'user.js').write_text(
            'user_pref("browser.startup.page", 3);\n'
            '// BEGIN passkeys-off (old wording)\nuser_pref("security.webauthn.enable_macos_passkeys", true);\n'
            '// END passkeys-off\nuser_pref("general.smoothScroll", false);')
        dry = self.run_tool('apply', '--dry-run')
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn('would write', dry.stdout)
        self.assertFalse((absolute / 'user.js').exists())

        self.assertEqual(self.run_tool('check').returncode, 1)
        first = self.run_tool('apply')
        self.assertEqual(first.returncode, 0, first.stderr)
        expected_block = ('// BEGIN passkeys-off (written by ~/.local/bin/passkeys-off; edits between these lines are replaced)\n'
                          'user_pref("security.webauthn.enable_macos_passkeys", false);\n'
                          'user_pref("security.webauthn.enable_conditional_mediation", false);\n'
                          '// END passkeys-off\n')
        self.assertEqual((relative / 'user.js').read_text(),
                         'user_pref("browser.startup.page", 3);\nuser_pref("general.smoothScroll", false);\n' + expected_block)
        self.assertEqual((absolute / 'user.js').read_text(), expected_block)

        second = self.run_tool('apply')
        self.assertEqual(second.stdout.count(': ok'), 2, second.stdout)
        check = self.run_tool('check')
        self.assertEqual(check.returncode, 0, check.stdout)
        self.assertIn('Passwords app', check.stdout)

    def test_check_reports_each_chromium_profile(self):
        unpacked = {'location': 4, 'path': str(self.EXTENSION)}
        self.chromium_profile('Default', {'a' * 32: unpacked, 'aeblfdkhhhdcdjpifhhbdiojplfjncoa': {'location': 1}})
        self.chromium_profile('Profile 1', {'b' * 32: dict(unpacked, disable_reasons=[1])})
        self.chromium_profile('Profile 2', {'c' * 32: {'location': 4, 'path': str(self.path / 'other')}})
        self.chromium_profile('System Profile', {})
        p = self.run_tool('check')
        self.assertEqual(p.returncode, 1)
        lines = p.stdout.splitlines()
        self.assertIn('Brave-Browser Default: ok', lines)
        self.assertIn('Brave-Browser Profile 1: Passkeys Off is disabled (turn it on in the extensions page)', lines)
        self.assertTrue(any(l.startswith('Brave-Browser Profile 2: Passkeys Off not loaded') for l in lines), p.stdout)
        self.assertFalse(any('System Profile' in l for l in lines))
        self.assertTrue(any(l.strip().startswith('1Password, in each browser') for l in lines), p.stdout)



MUXY_APP = Path('/Applications/Muxy.app')
needs_muxy = unittest.skipUnless((MUXY_APP / 'Contents/MacOS/muxy').exists(),
                                 'Muxy.app required: its own parser checks what muxy-reconcile writes')

# Muxy's settings.toml as the app saves it: tables in key order, servers among
# them. The prompt holds a line that looks like a [[servers]] table.
MUXY_SETTINGS = '''commands = []

[ai.commit]
include_unstaged = true
push = true

[ai.prompts]
commit = """
Summarize the change.
[[servers]]
id = "not a server"
"""

[appearance]
dark_theme = "Dracula"
hidden_worktrees = [
    "0123456789abcdef0123456789abcdef",
]
tips_visible = true

[appearance.sidebar_servers_expanded]

[clipboard]
copy_on_select = false

[quick_terminal]
enabled = true

[quick_terminal.shortcut]
type = "unassigned"

{servers}[window]
close_behavior = "close_session"
default_size = [
    1200.0,
    800.0,
]

[worktrees.projects]
'''


class MuxyReconcile(Fixture):
    """muxy-reconcile against a real Muxy profile directory and Muxy's own parser;
    ssh -G and this Mac's addresses are stand-ins."""
    FEATURE = FEATURES / 'tool.muxy'
    TOOL = FEATURE / 'home/.local/bin/muxy-reconcile'
    WRAPPER = FEATURE / 'home/.local/bin/muxy'
    # Each destination's HostName, as `ssh -G` would print it. The desk has two
    # interfaces: its alias names one, its .local name answers with the other.
    HOSTS = {'desk': '192.0.2.94', 'desk.local': '192.0.2.230', 'laptop': '192.0.2.91',
             'tower': '192.0.2.93', 'tower.local': '192.0.2.93', 'devbox': '198.51.100.7',
             'gone': 'nowhere.invalid'}
    # Each machine's sshd host key answers on these addresses.
    MACHINES = {'desk': ('192.0.2.94', '192.0.2.230'), 'laptop': ('192.0.2.91',),
                'tower': ('192.0.2.93',), 'devbox': ('198.51.100.7',)}
    # The tests run as the Laptop.
    SELF = '192.0.2.91 127.0.0.1'

    @classmethod
    def setUpClass(cls):
        cls.keys = tempfile.TemporaryDirectory(prefix='muxy-host-keys-')
        lines = []
        for machine, addresses in cls.MACHINES.items():
            key = Path(cls.keys.name) / machine
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', machine, '-f', str(key)], check=True)
            kind, blob = (key.with_suffix('.pub')).read_text().split()[:2]
            lines.append(f'{",".join(addresses)} {kind} {blob}\n')
        cls.known_hosts = Path(cls.keys.name) / 'known_hosts'
        cls.known_hosts.write_text(''.join(lines))
        # Hashed, as HashKnownHosts writes them.
        subprocess.run(['ssh-keygen', '-q', '-H', '-f', str(cls.known_hosts)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.keys.cleanup()

    def setUp(self):
        super().setUp()
        self.user = subprocess.run(['id', '-un'], capture_output=True, text=True, check=True).stdout.strip()
        self.profile = self.path / 'muxy'
        self.profile.mkdir()
        self.settings = self.profile / 'settings.toml'
        self.lists = self.path / 'config/muxy/servers.d'
        self.lists.mkdir(parents=True)
        self.state = self.path / 'state/muxy-reconcile/managed.json'
        self.log = self.path / 'logs/muxy-reconcile.log'
        (self.path / 'hosts').write_text(''.join(f'{k} {v}\n' for k, v in self.HOSTS.items()))
        self.cli('ssh', r'''[ "$1" = -G ] || exit 2; shift; [ "$1" = -- ] && shift
d=$1; user=$(id -un); host=${d#*@}; [ "$host" = "$d" ] || user=${d%%@*}
[ "$host" != "${FAKE_SSH_FAIL:-}" ] || { echo "ssh: $host: bad configuration" >&2; exit 255; }
mapped=$(awk -v h="$host" '$1 == h {print $2}' "$FAKE_SSH_HOSTS")
printf 'user %s\nhostname %s\nport 22\nuserknownhostsfile %s\nglobalknownhostsfile none\n' \
    "$user" "${mapped:-$host}" "$FAKE_KNOWN_HOSTS"
if [ -n "${FAKE_SSH_TOUCH:-}" ] && [ ! -e "$FAKE_SSH_TOUCH.done" ]; then
    printf '\n' >> "$FAKE_SSH_TOUCH"; : > "$FAKE_SSH_TOUCH.done"
fi''')
        self.env.update(MUXY_DIR=str(self.profile), XDG_CONFIG_HOME=str(self.path / 'config'),
                        XDG_STATE_HOME=str(self.path / 'state'), MUXY_RECONCILE_LOG=str(self.log),
                        MUXY_RECONCILE_SSH=str(self.bin / 'ssh'), FAKE_SSH_HOSTS=str(self.path / 'hosts'),
                        MUXY_RECONCILE_SELF_ADDRESSES=self.SELF, FAKE_KNOWN_HOSTS=str(self.known_hosts),
                        MUXY_RECONCILE_HOST_KEYS=str(Path(self.keys.name) / 'laptop.pub'),
                        # Never this Mac's own generated settings.
                        HOME=str(self.path / 'home'))
        for name in ('DOTFILES_MUXY_APP', 'MUXY_RECONCILE_MODE', 'MUXY_RECONCILE_EXCLUDE'):
            self.env.pop(name, None)
        self.generate(mode='apply')

    def generate(self, mode=None, exclude=''):
        """The settings as dotfiles apply generates them into env.sh; mode None
        is an env.sh from before muxy.reconcile existed."""
        generated = Path(self.env['HOME']) / '.config/dotfiles/generated'
        generated.mkdir(parents=True, exist_ok=True)
        settings = {'MUXY_RECONCILE_EXCLUDE': ('muxy.exclude_servers', exclude)}
        if mode is not None:
            settings['MUXY_RECONCILE_MODE'] = ('muxy.reconcile', mode)
        (generated / 'env.sh').write_text(''.join(
            f'[ -n "${{{var}:-}}" ] || {var}={shlex.quote(value)}; export {var} # {name}\n'
            for var, (name, value) in settings.items()))

    def write_settings(self, *servers):
        body = ''.join('[[servers]]\n' + ''.join(f'{k} = {json.dumps(v)}\n' for k, v in sorted(s.items())) + '\n'
                       for s in servers)
        self.settings.write_text(MUXY_SETTINGS.replace('{servers}', body))
        return self.settings.read_bytes()

    def declare(self, *servers, name='personal', group='Macs'):
        text = f'group = "{group}"\n' + ''.join(
            '\n[[server]]\n' + ''.join(f'{k} = {json.dumps(v)}\n' for k, v in s.items()) for s in servers)
        (self.lists / f'{name}.toml').write_text(text)

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(self.TOOL), *args], env=self.env,
                              capture_output=True, text=True, timeout=60)

    def servers(self):
        return tomllib.loads(self.settings.read_text()).get('servers', [])

    def without_servers(self, text):
        """The file with its [[servers]] tables taken out."""
        return re.sub(r'^\[\[servers\]\]\n(?:[a-z_]+ = .*\n)*\n?', '', text, flags=re.MULTILINE)

    def managed(self):
        profiles = json.loads(self.state.read_text())['profiles']
        return profiles[str(self.settings)]

    def declare_macs(self):
        self.declare({'name': 'Desk', 'ssh': 'desk'}, {'name': 'Laptop', 'ssh': 'laptop'},
                     {'name': 'tower', 'ssh': 'tower'})

    @needs_muxy
    def test_adopts_the_same_machine_by_host_key_skips_this_mac_and_adds_the_rest(self):
        desk_id = '5e1ec7ed5e1ec7ed5e1ec7ed5e1ec7ed'
        before = self.write_settings({'group': 'active', 'id': desk_id, 'name': 'desk',
                                      'password_login': True, 'ssh': f'{self.user}@desk.local'})
        self.declare_macs()
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('1 added, 1 adopted', p.stdout)
        desk, tower = self.servers()
        self.assertEqual(desk, {'group': 'Macs', 'id': desk_id, 'name': 'Desk', 'password_login': True, 'ssh': 'desk'},
                         'the entry keeps its id, and the keys a list does not set')
        self.assertEqual({k: tower[k] for k in ('group', 'name', 'ssh')}, {'group': 'Macs', 'name': 'tower', 'ssh': 'tower'})
        self.assertRegex(tower['id'], r'^[0-9a-f]{32}$')
        self.assertNotIn('laptop', [s.get('ssh') for s in self.servers()], 'this Mac is never listed')
        self.assertEqual(self.without_servers(self.settings.read_text()), self.without_servers(before.decode()),
                         'every byte outside [[servers]] is as it was')
        self.assertIn('[[servers]]\nid = "not a server"', self.settings.read_text(), 'the prompt is untouched')
        self.assertEqual(self.managed(), {desk_id: {'ssh': 'desk', 'adopted': True}, tower['id']: {'ssh': 'tower'}})

    @needs_muxy
    def test_adopts_by_address_when_no_host_key_is_known(self):
        tower_id = '70e470e470e470e470e470e470e470e4'
        self.write_settings({'id': tower_id, 'name': 'tower.local', 'ssh': f'{self.user}@tower.local'})
        self.env['FAKE_KNOWN_HOSTS'] = str(self.path / 'empty_known_hosts')
        self.declare_macs()
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('1 adopted', p.stdout)
        self.assertIn('2 no host key', p.stdout, 'Muxy cannot connect to either until a key is accepted')
        self.assertEqual(self.servers()[0], {'group': 'Macs', 'id': tower_id, 'name': 'tower', 'ssh': 'tower'})
        self.assertIn('`ssh desk` accepts one', self.log.read_text())

    @needs_muxy
    def test_this_mac_is_known_by_its_host_key_on_any_address(self):
        self.write_settings()
        self.env['MUXY_RECONCILE_SELF_ADDRESSES'] = '203.0.113.99'
        self.declare_macs()
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual([s['ssh'] for s in self.servers()], ['desk', 'tower'])

    @needs_muxy
    def test_new_entries_go_where_muxy_writes_them_with_fresh_ids(self):
        before = self.write_settings()
        self.declare({'name': 'Desk', 'ssh': 'desk'}, {'name': 'tower', 'ssh': 'tower'},
                     {'name': 'devbox', 'ssh': 'devbox', 'ssh_command': 'orb ssh devbox'})
        self.env['FAKE_KNOWN_HOSTS'] = str(self.path / 'empty_known_hosts')
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('3 added', p.stdout)
        self.assertIn('2 no host key', p.stdout, 'devbox logs in through its command, not known_hosts')
        text = self.settings.read_text()
        self.assertLess(text.index('[quick_terminal.shortcut]'), text.index('[[servers]]\ngroup'))
        self.assertLess(text.rindex('[[servers]]'), text.index('[window]'))
        ids = [s['id'] for s in self.servers()]
        self.assertEqual(len(set(ids)), 3)
        self.assertTrue(all(re.fullmatch(r'[0-9a-f]{32}', i) for i in ids), ids)
        self.assertEqual(self.servers()[2], {'group': 'Macs', 'id': ids[2], 'name': 'devbox',
                                             'ssh_command': 'orb ssh devbox'}, 'a command replaces the destination')
        self.assertEqual(self.without_servers(text), self.without_servers(before.decode()))

    @needs_muxy
    def test_keeps_entries_it_did_not_write_and_removes_its_own_when_undeclared(self):
        hand = {'id': 'c0ffee00c0ffee00c0ffee00c0ffee00', 'identity_file': '~/.ssh/devbox', 'name': 'devbox',
                'ssh': 'me@devbox'}
        self.write_settings(hand)
        hand_text = '[[servers]]\nid = "c0ffee00c0ffee00c0ffee00c0ffee00"\nidentity_file = "~/.ssh/devbox"\n'
        self.declare_macs()
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('1 not managed', p.stdout)
        self.assertEqual([s['name'] for s in self.servers()], ['devbox', 'Desk', 'tower'])

        self.declare({'name': 'Desk', 'ssh': 'desk'})
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('1 removed', p.stdout)
        self.assertEqual(self.servers()[0], hand)
        self.assertIn(hand_text, self.settings.read_text(), 'its table is byte for byte as it was')
        self.assertEqual([s['name'] for s in self.servers()], ['devbox', 'Desk'])

        (self.lists / 'personal.toml').unlink()
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.servers(), [hand], 'with no lists, only the hand-added entry stays')

    @needs_muxy
    def test_an_entry_that_turns_out_to_be_this_mac_is_removed_unless_added_by_hand(self):
        laptop_id = '0123456789abcdef0123456789abcdef'
        for record, left in (({'ssh': 'laptop'}, ['desk', 'tower']),
                             ({'ssh': 'laptop', 'adopted': True}, ['laptop', 'desk', 'tower'])):
            with self.subTest(record=record):
                self.write_settings({'id': laptop_id, 'name': 'Laptop', 'ssh': 'laptop'})
                self.state.parent.mkdir(parents=True, exist_ok=True)
                self.state.write_text(json.dumps({'version': 1, 'profiles': {str(self.settings): {laptop_id: record}}}))
                self.declare_macs()
                p = self.run_tool()
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                self.assertEqual([s['ssh'] for s in self.servers()], left)
                self.assertNotIn(laptop_id, self.managed())

    @needs_muxy
    def test_a_second_run_writes_nothing_and_never_calls_muxy(self):
        self.write_settings()
        self.declare_macs()
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        written, stat = self.settings.read_bytes(), self.settings.stat()
        self.env['DOTFILES_MUXY_APP'] = str(self.path / 'no-such.app')
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(p.stdout, 'muxy-reconcile: in step: 2 unchanged, 1 this Mac\n')
        self.assertEqual((self.settings.read_bytes(), self.settings.stat().st_mtime_ns), (written, stat.st_mtime_ns))

    @needs_muxy
    def test_a_value_muxy_refuses_leaves_the_file_as_it_was(self):
        before = self.write_settings()
        self.declare({'name': 'x' * 300, 'ssh': 'desk'})
        p = self.run_tool()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn('Muxy refuses the new servers', p.stderr)
        self.assertIn('enter a name of 1', p.stderr, "Muxy's own message")
        self.assertEqual(self.settings.read_bytes(), before)
        self.assertFalse(self.state.exists())
        self.assertEqual(sorted(p.name for p in self.profile.iterdir()), ['settings.toml'], 'no temporary files left')

    @needs_muxy
    def test_a_file_muxy_already_refuses_is_left_alone(self):
        before = self.write_settings({'id': '9eedd63357b54359b76e762c6bc2775c', 'name': 'here', 'ssh': 'devbox'})
        self.declare_macs()
        p = self.run_tool()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn('Muxy refuses the current', p.stderr)
        self.assertIn("this computer's server ID cannot be listed", p.stderr)
        self.assertEqual(self.settings.read_bytes(), before)

    @needs_muxy
    def test_a_save_during_the_run_wins(self):
        before = self.write_settings()
        self.declare_macs()
        self.env['FAKE_SSH_TOUCH'] = str(self.settings)
        p = self.run_tool()
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertIn('changed during this run', p.stderr)
        self.assertEqual(self.settings.read_bytes(), before + b'\n', 'the other save is kept, this run wrote nothing')
        self.assertFalse(self.state.exists())

    @needs_muxy
    def test_a_name_that_stops_resolving_keeps_its_entry(self):
        self.write_settings()
        self.declare({'name': 'gone', 'ssh': 'gone'})
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('1 unresolved', p.stdout)
        self.assertEqual(self.servers(), [], 'an unknown name might be this Mac, so it is not added')

        (self.path / 'hosts').write_text('gone 203.0.113.5\n')
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        added, = self.servers()
        (self.path / 'hosts').write_text('gone nowhere.invalid\n')
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.servers(), [added], 'its entry stays while the name does not resolve')

    def test_the_log_stays_under_its_bound(self):
        self.write_settings()
        self.env['MUXY_RECONCILE_LOG_MAX_BYTES'] = '1024'
        for _ in range(30):
            p = self.run_tool()
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        logs = sorted(p.name for p in self.log.parent.iterdir())
        self.assertEqual(logs, ['muxy-reconcile.log', 'muxy-reconcile.log.1'])
        self.assertLessEqual(sum((self.log.parent / n).stat().st_size for n in logs), 2 * 1024 + 512)

    def test_a_bad_list_stops_the_run_and_writes_nothing(self):
        before = self.write_settings()
        for text, message in (('[[server]]\nname = "a"\nssh = "-oProxyCommand=x"\n', 'must be one destination'),
                              ('[[server]]\nname = "a"\nssh = "a"\nport = 22\n', 'unknown keys: port'),
                              ('[[server]]\nname = "a"\n', 'ssh is required'),
                              ('group = 1\n', 'group must be a string')):
            with self.subTest(text=text):
                (self.lists / 'bad.toml').write_text(text)
                p = self.run_tool()
                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertIn(message, p.stderr)
                self.assertEqual(self.settings.read_bytes(), before)

    @needs_muxy
    def test_an_excluded_server_is_left_out_and_its_entry_removed(self):
        self.write_settings()
        self.declare_macs()
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual([s['ssh'] for s in self.servers()], ['desk', 'tower'])

        self.generate(mode='apply', exclude='personal/tower')
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('1 removed, 1 unchanged, 1 this Mac, 1 excluded', p.stdout)
        self.assertEqual([s['ssh'] for s in self.servers()], ['desk'])
        self.assertIn('excluded: tower (personal/tower): muxy.exclude_servers leaves it out on this Mac',
                      self.log.read_text())

        self.generate(mode='apply')
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual([s['ssh'] for s in self.servers()], ['desk', 'tower'], 'back once no longer excluded')

    @needs_muxy
    def test_a_server_excluded_and_declared_again_locally_keeps_its_entry(self):
        self.write_settings()
        self.declare_macs()
        self.assertEqual(self.run_tool().returncode, 0)
        tower_id = self.servers()[1]['id']

        # This Mac's own name and group for one server of a shared list.
        self.generate(mode='apply', exclude='personal/tower')
        self.declare({'name': 'Build tower', 'ssh': 'tower'}, name='local', group='Here')
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('1 updated', p.stdout)
        tower = next(s for s in self.servers() if s['ssh'] == 'tower')
        self.assertEqual(tower, {'group': 'Here', 'id': tower_id, 'name': 'Build tower', 'ssh': 'tower'},
                         'the same entry, so its tabs stay')

    def test_an_exclusion_that_matches_no_server_writes_nothing(self):
        for value, message in (('personal/towr', 'muxy.exclude_servers names personal/towr, which no list in'),
                               ('work/tower', 'muxy.exclude_servers names work/tower'),
                               ('tower', "'tower' is not <list>/<ssh>"),
                               ('personal/', "'personal/' is not <list>/<ssh>")):
            with self.subTest(value=value):
                before = self.write_settings()
                self.declare_macs()
                self.generate(mode='apply', exclude=value)
                p = self.run_tool()
                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertIn(message, p.stderr)
                self.assertEqual(self.settings.read_bytes(), before, 'a typo never adds what it meant to leave out')
                self.assertFalse(self.state.exists())

    def test_the_settings_are_what_dotfiles_apply_generated_unless_a_flag_says_otherwise(self):
        self.generate(mode='apply', exclude='personal/desk')
        # A shell that loaded an older env.sh passes its values on.
        self.env.update(MUXY_RECONCILE_EXCLUDE='', MUXY_RECONCILE_MODE='apply')
        self.write_settings()
        self.declare({'name': 'Desk', 'ssh': 'desk'}, {'name': 'Laptop', 'ssh': 'laptop'})
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(p.stdout, 'muxy-reconcile: in step: 1 this Mac, 1 excluded\n',
                         'the desk is left out, so nothing needs writing and Muxy never runs')

        p = self.run_tool('--exclude-servers', 'personal/dsk')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn('names personal/dsk', p.stderr)

        self.generate(mode='aply')
        p = self.run_tool()
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("muxy.reconcile (MUXY_RECONCILE_MODE) is 'aply'; want one of report, apply", p.stderr)

    @needs_muxy
    def test_report_logs_the_change_and_writes_nothing(self):
        before = self.write_settings({'id': '5e1ec7ed5e1ec7ed5e1ec7ed5e1ec7ed', 'name': 'desk', 'ssh': 'desk.local',
                                      'identity_file': '~/.ssh/desk'})
        mtime = self.settings.stat().st_mtime_ns
        self.declare_macs()
        env_sh = Path(self.env['HOME']) / '.config/dotfiles/generated/env.sh'
        # The setting; an env.sh from before it; no env.sh at all. The default is report.
        for generated in ('report', None, 'no env.sh'):
            with self.subTest(generated=generated):
                self.generate(mode=generated)
                if generated == 'no env.sh':
                    env_sh.unlink()
                p = self.run_tool()
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                self.assertTrue(p.stdout.endswith('muxy-reconcile: report: would change: 1 added, 1 adopted, '
                                                  '1 this Mac (Muxy accepts it); nothing written, as muxy.reconcile '
                                                  'is report\n'), p.stdout)
                self.assertIn('+name = "Desk"', p.stdout)
                self.assertIn('-ssh = "desk.local"', p.stdout)
                self.assertEqual((self.settings.read_bytes(), self.settings.stat().st_mtime_ns), (before, mtime))
                self.assertFalse(self.state.exists(), 'no state written either')
                log = self.log.read_text()
                self.assertIn('diff: +name = "tower"', log, 'the log holds the diff')
                self.assertNotIn('wrote ', log)

        p = self.run_tool('--mode', 'apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('changed: 1 added, 1 adopted', p.stdout)

    @needs_muxy
    def test_an_adopted_entry_keeps_its_own_keys_and_is_released_not_removed(self):
        hand = {'id': '33333333333333333333333333333333', 'identity_file': '~/.ssh/desk', 'name': 'My desk',
                'password_login': False, 'ssh': 'desk.local'}
        self.write_settings(hand)
        self.declare({'name': 'Desk', 'ssh': 'desk'}, {'name': 'tower', 'ssh': 'tower'})
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        desk = {'group': 'Macs', 'id': hand['id'], 'identity_file': '~/.ssh/desk', 'name': 'Desk',
                'password_login': False, 'ssh': 'desk'}
        self.assertEqual(self.servers()[0], desk, 'only the keys a list sets are overwritten')
        self.assertEqual(self.managed()[hand['id']], {'ssh': 'desk', 'adopted': True})

        released = (f'released: Desk ({hand["id"]}): no longer declared, but it was added by hand, '
                    'so it stays as it is and is no longer managed')
        self.generate(mode='apply', exclude='personal/desk')
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('1 released', p.stdout)
        self.assertEqual(self.servers()[0], desk, 'excluded: left as it is')
        self.assertNotIn(hand['id'], self.managed())
        self.assertIn(released, self.log.read_text())

        self.generate(mode='apply')
        self.assertIn('1 adopted', self.run_tool().stdout)
        self.declare({'name': 'tower', 'ssh': 'tower'})
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('1 released', p.stdout)
        self.assertEqual(self.servers()[0], desk, 'undeclared: left as it is')
        self.assertNotIn(hand['id'], self.managed())

    @needs_muxy
    def test_an_entry_muxy_paired_is_released_not_removed(self):
        self.write_settings()
        self.declare({'name': 'Desk', 'ssh': 'desk'}, {'name': 'tower', 'ssh': 'tower'})
        self.assertEqual(self.run_tool().returncode, 0)
        desk_id = self.servers()[0]['id']
        # Muxy pairs with the desk: a [servers.paired] table takes the place of its ssh.
        table = f'[[servers]]\ngroup = "Macs"\nid = "{desk_id}"\nname = "Desk"\n'
        text = self.settings.read_text()
        self.settings.write_text(text.replace(table + 'ssh = "desk"\n', table + (
            '\n[servers.paired]\nhosts = ["192.0.2.94"]\nport = 4433\n'
            f'fingerprint = "{"ab" * 32}"\ndevice = "{"01" * 16}"\n')))
        paired = self.settings.read_bytes()

        self.generate(mode='apply', exclude='personal/desk')
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('1 released', p.stdout)
        self.assertEqual(self.settings.read_bytes(), paired, 'left as it is')
        self.assertNotIn(desk_id, self.managed())
        self.assertIn(f'released: Desk ({desk_id}): no longer declared, but Muxy paired it', self.log.read_text())

    @needs_muxy
    def test_a_missing_list_directory_with_managed_entries_writes_nothing(self):
        self.write_settings()
        self.declare_macs()
        self.assertEqual(self.run_tool().returncode, 0)
        written = (self.settings.read_bytes(), self.state.read_bytes())

        shutil.rmtree(self.lists)
        p = self.run_tool()
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn(f'{self.lists} is missing, but {self.state} manages 2 entries', p.stderr)
        self.assertEqual((self.settings.read_bytes(), self.state.read_bytes()), written)

        # A list linked from a volume that is not mounted is as unreadable.
        self.lists.mkdir()
        (self.lists / 'personal.toml').symlink_to(self.path / 'unmounted/personal.toml')
        p = self.run_tool()
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn('personal.toml', p.stderr)
        self.assertEqual((self.settings.read_bytes(), self.state.read_bytes()), written)

    def test_a_state_file_it_did_not_write_stops_the_run(self):
        entry_id = '22222222222222222222222222222222'
        before = self.write_settings({'id': entry_id, 'name': 'x', 'ssh': 'desk'})
        self.declare({'name': 'Desk', 'ssh': 'desk'})
        self.state.parent.mkdir(parents=True)
        for records in ({entry_id: 'desk'}, {entry_id: {'ssh': 'desk', 'adopted': 'yes'}},
                        {entry_id: {'ssh': 'desk', 'port': 22}}, []):
            with self.subTest(records=records):
                self.state.write_text(json.dumps({'version': 1, 'profiles': {str(self.settings): records}}))
                p = self.run_tool()
                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertIn('not muxy-reconcile records; delete it to start over', p.stderr)
                self.assertNotIn('Traceback', p.stderr)
                self.assertEqual(self.settings.read_bytes(), before)

    @needs_muxy
    def test_an_empty_inline_list_of_servers_becomes_tables(self):
        # Muxy saves an empty list of servers as `servers = []` among the root keys.
        self.settings.write_text(MUXY_SETTINGS.replace('{servers}', '').replace(
            'commands = []\n', 'commands = []\nservers = []\n'))
        self.declare({'name': 'Desk', 'ssh': 'desk'})
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual([s['ssh'] for s in self.servers()], ['desk'])
        self.assertNotIn('servers = []', self.settings.read_text())

    def test_a_destination_declared_twice_is_refused(self):
        self.write_settings()
        self.declare({'name': 'Desk', 'ssh': 'desk'})
        self.declare({'name': 'Desk again', 'ssh': 'desk'}, name='work', group='Work')
        p = self.run_tool()
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("ssh 'desk' is declared in both personal.toml and work.toml", p.stderr)

    def test_ssh_failing_for_a_declared_server_is_an_error(self):
        before = self.write_settings()
        self.declare_macs()
        self.env['FAKE_SSH_FAIL'] = 'tower'
        p = self.run_tool()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn('ssh -G tower: ssh: tower: bad configuration', p.stderr)
        self.assertEqual(self.settings.read_bytes(), before)

    def test_without_muxy_a_needed_change_exits_unavailable(self):
        self.write_settings()
        self.declare_macs()
        self.env['DOTFILES_MUXY_APP'] = str(self.path / 'no-such.app')
        p = self.run_tool()
        self.assertEqual(p.returncode, 69, p.stdout + p.stderr)
        self.assertIn('install Muxy', p.stderr)

    def test_a_profile_muxy_has_not_created_is_left_for_later(self):
        self.declare_macs()
        p = self.run_tool()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('does not exist yet', p.stdout)
        self.assertFalse(self.settings.exists())

    @needs_muxy
    def test_the_wrapper_runs_the_apps_own_tool(self):
        p = subprocess.run([str(self.WRAPPER), '--version'], env=self.env, capture_output=True, text=True, timeout=20)
        bundled = subprocess.run([str(MUXY_APP / 'Contents/MacOS/muxy'), '--version'],
                                 capture_output=True, text=True, timeout=20)
        self.assertEqual((p.returncode, p.stdout), (0, bundled.stdout))

    def test_the_wrapper_prefers_a_per_user_app(self):
        home = self.path / 'home'
        tool = home / 'Applications/Muxy.app/Contents/MacOS/muxy'
        tool.parent.mkdir(parents=True)
        tool.write_text('#!/bin/sh\necho "per-user $*"\n')
        tool.chmod(0o755)
        env = dict(self.env, HOME=str(home))
        p = subprocess.run([str(self.WRAPPER), '--version'], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual((p.returncode, p.stdout), (0, 'per-user --version\n'))
        env['DOTFILES_MUXY_APP'] = str(self.path / 'no-such.app')
        p = subprocess.run([str(self.WRAPPER), '--version'], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 69, 'DOTFILES_MUXY_APP, when set, is the only app')

    def test_the_wrapper_names_a_missing_app(self):
        self.env['DOTFILES_MUXY_APP'] = str(self.path / 'no-such.app')
        p = subprocess.run([str(self.WRAPPER), '--version'], env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 69)
        self.assertIn('no-such.app/Contents/MacOS/muxy is missing', p.stderr)


class Karabiner(unittest.TestCase):
    """The managed karabiner.json (tool.karabiner, docs/KARABINER.md)."""
    CONFIG = FEATURES / 'tool.karabiner/home/.config/karabiner/karabiner.json'

    def setUp(self):
        self.profile, = json.loads(self.CONFIG.read_text())['profiles']

    def rule(self, description_start):
        rules = [r for r in self.profile['complex_modifications']['rules']
                 if r['description'].startswith(description_start)]
        self.assertEqual(len(rules), 1, description_start)
        return rules[0]

    def test_the_mouse_rule_names_only_mice_karabiner_modifies(self):
        # Karabiner ignores a pointing device unless `devices` enables it, so a rule naming any
        # other mouse would never see its buttons.
        modified = [d['identifiers'] for d in self.profile['devices'] if d.get('ignore') is False]
        manipulator, = self.rule('G502 X PLUS')['manipulators']
        self.assertEqual(manipulator['to'], [{'key_code': 'mission_control'}])
        condition, = manipulator['conditions']
        self.assertEqual(condition['type'], 'device_if')
        self.assertTrue(condition['identifiers'])
        for mouse in condition['identifiers']:
            self.assertIn(dict(mouse, is_pointing_device=True), modified)

    def test_non_apple_keyboards_keep_plain_function_keys(self):
        manipulators = self.rule('Non-Apple keyboards')['manipulators']
        self.assertEqual([m['from']['key_code'] for m in manipulators], [f'f{i}' for i in range(1, 13)])
        for m in manipulators:
            self.assertEqual(m['to'], [{'key_code': m['from']['key_code']}])
            self.assertEqual([c['type'] for c in m['conditions']], ['device_unless'])


if __name__ == '__main__':
    unittest.main()
