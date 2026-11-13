import json
import os
from pathlib import Path
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

    def cli(self, name, code):
        file = self.bin / name
        file.write_text('#!/bin/sh\n' + code + '\n')
        file.chmod(0o755)

    def zsh(self, code, *args, input=None):
        return subprocess.run(['/bin/zsh', '-fc', 'source "$1"; shift; ' + code,
                               'test', str(ROOT / 'lib_sh/funcs.sh'), *args],
                              cwd=self.path, env=self.env, input=input,
                              capture_output=True, text=True, timeout=20)

    def bash(self, code, *args, source='sync.sh'):
        return subprocess.run(['/bin/bash', '-c', 'source "$1"; shift; ' + code,
                               'test', str(ROOT / source), *args],
                              cwd=self.path, env=self.env, capture_output=True,
                              text=True, timeout=20)


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
        self.assertIn('upgrade', audit.read_text())
        self.env['DOTFILES_TEST_BREW_EXIT'] = '7'
        p = subprocess.run(args, env=self.env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 7)
        self.assertEqual(p.stdout, '')
        self.assertIn('Command failed', p.stderr)

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
        for name in ('dracula-iterm', 'colorls', 'alfred-dracula'):
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


class Sync(Fixture):
    def setUp(self):
        super().setUp()
        (self.path / 'logs').mkdir()

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
        self.repo = self.path / 'repo'
        subprocess.run(['git', 'init', '-q', '-b', 'master', str(self.repo)], check=True, env=self.env)
        for name, value in {'user.name': 'Fixture', 'user.email': 'fixture@example.com',
                            'user.signingkey': str(key), 'gpg.format': 'ssh', 'gpg.program': '/usr/bin/true',
                            'gpg.ssh.allowedSignersFile': str(signers), 'commit.gpgsign': 'true'}.items():
            self.git('config', name, value)
        (self.repo / 'sub').mkdir()
        for name in ('tracked', 'sub/app.local'):
            (self.repo / name).write_text('one\n')
        self.git('add', 'tracked', 'sub/app.local')
        self.git('commit', '-q', '-m', 'initial')

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
        self.env.update(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / '.config'),
                        XDG_STATE_HOME=str(self.home / '.local/state'))

    def dotfiles(self, *args):
        return subprocess.run([str(self.engine), *args, '--home', str(self.home), '--repo', str(ROOT)],
                              env=self.env, capture_output=True, text=True, timeout=60)

    def converge(self, profiles):
        p = self.dotfiles('init', '--profiles', profiles)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        again = self.dotfiles('apply')
        self.assertEqual((again.returncode, again.stdout), (0, ''), 'a second apply changes nothing')
        doctor = self.dotfiles('doctor')
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        return (self.home / '.config/dotfiles/generated/Brewfile').read_text()

    def test_doctor_reports_an_xdg_config_home_it_does_not_install_into(self):
        self.converge('base')
        self.env['XDG_CONFIG_HOME'] = str(self.path / 'elsewhere')
        p = self.dotfiles('doctor')
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn('problem     XDG_CONFIG_HOME', p.stdout)

    def test_apply_refuses_without_a_machine_manifest(self):
        p = self.dotfiles('apply')
        self.assertEqual(p.returncode, 2)
        self.assertIn('dotfiles init --profiles', p.stderr)
        self.assertEqual(list(self.home.iterdir()), [], 'nothing is installed or removed')

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

    def test_a_desktop_machine_gets_a_working_shell_git_and_ssh(self):
        brewfile = self.converge('base,dev,desktop,server')
        self.assertIn('cask "', brewfile)
        self.assertIn('vscode "', brewfile)
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

    def test_a_host_profile_sets_its_values(self):
        self.converge('base,dev,desktop,studio')
        env = (self.home / '.config/dotfiles/generated/env.sh').read_text()
        self.assertIn("PLAYWRIGHT_BROWSERS_PATH='/Volumes/E2TB/cache/ms-playwright'", env)
        self.assertIn("AGENT_MONITOR_DATA_DIR='/Volumes/E2TB/agent-monitor'", env)

    def test_the_work_machine_gets_dev_apps_and_nothing_personal(self):
        brewfile = self.converge('base,dev,work')
        self.assertIn('cask "iterm2"', brewfile)
        self.assertIn('cask "slack"', brewfile, 'applications for any desk reach the work machine')
        for general in ('mas "Okta Verify"', 'mas "Xcode"'):
            self.assertIn(general, brewfile)
        for personal in ('cask "spotify"', 'cask "steam"', 'mas "Day One"', 'wakatime', 'rescuetime'):
            self.assertNotIn(personal, brewfile)
        for home_cluster in ('.config/opencode/opencode.jsonc', '.config/otel-agent/config.yaml'):
            self.assertFalse((self.home / home_cluster).exists(), home_cluster)
        self.assertFalse((self.home / '.config/neofetch').exists())
        self.assertFalse((self.home / '.mackup.cfg').exists())
        self.assertTrue((self.home / '.claude/CLAUDE.md').is_symlink(), 'dev features are on')


class Install(Fixture):
    """install.sh piped into bash, as `curl ... | bash -s -- ...` runs it, with no terminal for prompts."""

    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        dotfiles = self.home / '.dotfiles'
        (dotfiles / '.git').mkdir(parents=True)
        for theme in ('dracula-iterm', 'colorls', 'alfred-dracula'):
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
        self.assertEqual(steps, ['sync.sh build',
                                 f'dotfiles init --repo {self.home}/.dotfiles --profiles base,dev',
                                 'sync.sh apply', 'sync.sh brewfile'])
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
        shell = json.loads(self.claude.read_text())['env']['CLAUDE_CODE_SHELL']
        self.assertEqual(subprocess.run([shell, '-c', '(( BASH_VERSINFO[0] >= 4 ))']).returncode, 0)
        codex = self.codex.read_text()
        self.assertIn('shell_snapshot = false', codex)
        self.assertIn('AGENT_SHELL = "codex"', codex)
        self.assertEqual(stat.S_IMODE(self.codex.stat().st_mode), 0o644)
        self.assertEqual(self.agents('check').returncode, 0)

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


class AgentMonitorFixture(Fixture):
    NODE_VERSION = '24.22.0'

    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        self.home.mkdir()
        self.monitor = self.home / '.local/share/agent-monitor'
        self.env.update(HOME=str(self.home), MISE_DATA_DIR=str(self.path / 'mise'))
        self.env.pop('AGENT_MONITOR_HOME', None)
        self.env.pop('AGENT_MONITOR_PORT', None)
        self.env.pop('CODEX_HOME', None)

    def node_path(self):
        return self.path / f'mise/installs/node/{self.NODE_VERSION}/bin/node'

    def install_node(self, script=None):
        node = self.node_path()
        node.parent.mkdir(parents=True)
        if script is None:
            real = shutil.which('node')
            if not real:
                self.skipTest('Node.js required')
            node.symlink_to(real)
        else:
            node.write_text(script)
            node.chmod(0o755)

    def run_monitor(self, *args):
        return subprocess.run(['/bin/zsh', '-f', str(ROOT / 'bin/agent-monitor'), *args],
                              cwd=self.path, env=self.env, capture_output=True, text=True, timeout=20)


class AgentMonitor(AgentMonitorFixture):
    def test_serve_runs_pinned_node_on_loopback(self):
        self.install_node('#!/bin/sh\nprintf "%s\\n" "cwd=$PWD" "args=$*" "host=$DASHBOARD_HOST" '
                          '"port=$DASHBOARD_PORT" "data=$DASHBOARD_DATA_DIR" "env=$DASHBOARD_ENV_PATH" '
                          '"update=$DASHBOARD_UPDATE_CHECK"\n')
        (self.monitor / 'app/server').mkdir(parents=True)
        (self.monitor / 'app/server/index.js').write_text('')
        p = self.run_monitor('serve')
        self.assertEqual(p.returncode, 0, p.stderr)
        lines = dict(line.split('=', 1) for line in p.stdout.splitlines())
        self.assertEqual(Path(lines['cwd']).resolve(), (self.monitor / 'app').resolve())
        self.assertEqual(lines['args'], 'server/index.js')
        self.assertEqual(lines['host'], '127.0.0.1')
        self.assertEqual(lines['port'], '4820')
        self.assertEqual(lines['data'], str(self.monitor / 'data'))
        self.assertEqual(lines['env'], str(self.monitor / 'config/.env'))
        self.assertEqual(lines['update'], '0')

    def test_serve_without_install_is_a_config_error(self):
        p = self.run_monitor('serve')
        self.assertEqual(p.returncode, 78)
        self.assertIn('run agent-monitor install', p.stderr)

    def test_gate_listens_on_the_configured_address(self):
        self.install_node('#!/bin/sh\nprintf "%s\\n" "host=$GATE_LISTEN_HOST" "port=$GATE_PORT"\n')
        token = self.monitor / 'config/gate-token'
        token.parent.mkdir(parents=True)
        token.write_text('x' * 64)
        self.env.pop('AGENT_MONITOR_GATE_HOST', None)
        for override, host in ((None, '0.0.0.0'), ('192.0.2.10', '192.0.2.10')):
            with self.subTest(host=host):
                if override:
                    self.env['AGENT_MONITOR_GATE_HOST'] = override
                p = self.run_monitor('gate')
                self.assertEqual(p.returncode, 0, p.stderr)
                lines = dict(line.split('=', 1) for line in p.stdout.splitlines())
                self.assertEqual(lines, {'host': host, 'port': '4821'})

    def test_unknown_command_is_a_usage_error(self):
        p = self.run_monitor('bogus')
        self.assertEqual(p.returncode, 64)
        self.assertIn('usage:', p.stderr)

    def test_uninstall_hooks_removes_only_dashboard_entries(self):
        self.install_node()
        handler = self.monitor / 'app/scripts/hook-handler.js'
        other = {'hooks': [{'type': 'command', 'command': 'prettier --write'}]}
        ours = {'hooks': [{'type': 'command', 'command': f'node "{handler}" Stop'}]}
        claude = self.home / '.claude/settings.json'
        claude.parent.mkdir()
        claude.write_text(json.dumps({'model': 'opus', 'hooks': {'PostToolUse': [other, ours], 'Stop': [ours]}}))
        codex = self.home / '.codex/hooks.json'
        codex.parent.mkdir()
        codex_ours = {'hooks': [{'type': 'command',
                                 'command': f'node "{self.monitor}/app/scripts/codex-hook-handler.js" Stop'}]}
        codex.write_text(json.dumps({'hooks': {'Stop': [codex_ours]}}))
        p = self.run_monitor('uninstall-hooks')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(claude.read_text()), {'model': 'opus', 'hooks': {'PostToolUse': [other]}})
        self.assertEqual(json.loads(codex.read_text()), {'hooks': {}})

    def test_lan_enable_rejects_a_short_token(self):
        p = subprocess.run(['/bin/zsh', '-f', str(ROOT / 'bin/agent-monitor'), 'lan', 'enable'],
                           cwd=self.path, env=self.env, input='short\n', capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 65)
        self.assertFalse((self.monitor / 'config/gate-token').exists())


class AgentMonitorGate(AgentMonitorFixture):
    TOKEN = 'fixture-token-' + 'x' * 40

    def setUp(self):
        super().setUp()
        import http.server
        import socket
        import threading

        self.upstream_requests = []
        requests = self.upstream_requests

        class Upstream(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.headers.get('Upgrade'):
                    self.connection.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n'
                                            b'Connection: Upgrade\r\nX-Seen-Host: '
                                            + self.headers['Host'].encode() + b'\r\n\r\n')
                    self.connection.sendall(self.connection.recv(4))
                    self.close_connection = True
                    return
                self.reply()

            do_POST = do_GET

            def reply(self):
                length = int(self.headers.get('Content-Length') or 0)
                if length:
                    self.rfile.read(length)
                requests.append(self.path)
                body = json.dumps({k.lower(): v for k, v in self.headers.items()}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.upstream = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        threading.Thread(target=self.upstream.serve_forever, daemon=True).start()
        self.addCleanup(self.upstream.server_close)
        self.addCleanup(self.upstream.shutdown)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            self.gate_port = probe.getsockname()[1]
        self.install_node()
        config = self.monitor / 'config'
        config.mkdir(parents=True)
        (config / 'gate-token').write_text(self.TOKEN)
        self.env.update(AGENT_MONITOR_PORT=str(self.upstream.server_address[1]),
                        AGENT_MONITOR_GATE_PORT=str(self.gate_port))

    def start_gate(self):
        import socket
        import time
        gate = subprocess.Popen(['/bin/zsh', '-f', str(ROOT / 'bin/agent-monitor'), 'gate'],
                                cwd=self.path, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        def stop():
            gate.terminate()
            gate.communicate(timeout=10)  # also closes the pipe
        self.addCleanup(stop)
        for _ in range(100):
            try:
                socket.create_connection(('127.0.0.1', self.gate_port), timeout=0.2).close()
                return gate
            except OSError:
                time.sleep(0.05)
        self.fail('gate did not start')

    def request(self, path, method='GET', token=None):
        import http.client
        conn = http.client.HTTPConnection('127.0.0.1', self.gate_port, timeout=5)
        headers = {'Host': 'agents.example'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        conn.request(method, path, body=b'{}' if method == 'POST' else None, headers=headers)
        try:
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def test_requires_the_token_and_presents_requests_as_local(self):
        self.start_gate()
        self.assertEqual(self.request('/api/sessions')[0], 401)
        self.assertEqual(self.request('/api/sessions', token='wrong' * 10)[0], 401)
        status, body = self.request('/api/sessions', token=self.TOKEN)
        self.assertEqual(status, 200)
        seen = json.loads(body)
        self.assertEqual(seen['host'], f'127.0.0.1:{self.upstream.server_address[1]}')
        self.assertNotIn('authorization', seen)
        self.assertEqual(seen['x-forwarded-host'], 'agents.example')

    def test_refuses_hook_routes(self):
        self.start_gate()
        self.assertEqual(self.request('/api/hooks/event', method='POST', token=self.TOKEN)[0], 404)
        self.assertEqual(self.request('/api/hooks', method='POST', token=self.TOKEN)[0], 404)
        self.assertEqual(self.upstream_requests, [])

    def test_relays_websocket_upgrades(self):
        import socket
        self.start_gate()
        with socket.create_connection(('127.0.0.1', self.gate_port), timeout=5) as client:
            client.sendall(b'GET /ws HTTP/1.1\r\nHost: agents.example\r\nUpgrade: websocket\r\n'
                           b'Connection: Upgrade\r\nSec-WebSocket-Key: Zml4dHVyZQ==\r\n'
                           b'Sec-WebSocket-Version: 13\r\nAuthorization: Bearer ' + self.TOKEN.encode() + b'\r\n\r\n')
            head = b''
            while b'\r\n\r\n' not in head:
                head += client.recv(1024)
            self.assertTrue(head.startswith(b'HTTP/1.1 101'), head)
            self.assertIn(f'X-Seen-Host: 127.0.0.1:{self.upstream.server_address[1]}'.encode(), head)
            client.sendall(b'ping')
            self.assertEqual(client.recv(4), b'ping')

    def test_refuses_to_start_with_a_weak_token(self):
        (self.monitor / 'config/gate-token').write_text('short')
        p = subprocess.run(['/bin/zsh', '-f', str(ROOT / 'bin/agent-monitor'), 'gate'],
                           cwd=self.path, env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 78)
        self.assertIn('fewer than 32 characters', p.stderr)


class OtelAgent(Fixture):
    VERSION = '0.163.1'
    TOKEN = 'a' * 48

    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        self.home.mkdir()
        self.state = self.home / '.local/share/otel-agent'
        self.libexec = self.home / '.local/libexec/otelcol'
        self.config = self.home / '.config/otel-agent/config.yaml'
        self.env.update(HOME=str(self.home), OTEL_AGENT_HOST='test-host')
        for name in ('OTEL_AGENT_HOME', 'OTEL_AGENT_LIBEXEC', 'OTEL_AGENT_CONFIG'):
            self.env.pop(name, None)

    def run_agent(self, *args, input=None):
        return subprocess.run(['/bin/zsh', '-f', str(ROOT / 'bin/otel-agent'), *args],
                              cwd=self.path, env=self.env, input=input,
                              capture_output=True, text=True, timeout=20)

    def install_collector(self, version=VERSION):
        collector = self.libexec / version / 'otelcol'
        collector.parent.mkdir(parents=True)
        collector.write_text('#!/bin/sh\nprintf "%s\\n" "args=$*" "gateway=$OTEL_AGENT_GATEWAY" '
                             '"token=$OTEL_AGENT_TOKEN" "host=$OTEL_AGENT_HOST"\n')
        collector.chmod(0o755)
        return collector

    def configure(self):
        self.state.mkdir(parents=True)
        (self.state / 'endpoint').write_text('https://gateway.example\n')
        (self.state / 'token').write_text(self.TOKEN + '\n')

    def test_serve_runs_pinned_collector_with_gateway_from_state(self):
        self.install_collector()
        self.configure()
        self.config.parent.mkdir(parents=True)
        self.config.write_text('')
        p = self.run_agent('serve')
        self.assertEqual(p.returncode, 0, p.stderr)
        lines = dict(line.split('=', 1) for line in p.stdout.splitlines())
        self.assertEqual(lines['args'], f'--config={self.config}')
        self.assertEqual(lines['gateway'], 'https://gateway.example')
        self.assertEqual(lines['token'], self.TOKEN)
        self.assertEqual(lines['host'], 'test-host')

    def test_serve_without_gateway_is_a_config_error(self):
        self.install_collector()
        p = self.run_agent('serve')
        self.assertEqual(p.returncode, 78)
        self.assertIn('otel-agent configure', p.stderr)

    def test_configure_stores_gateway_privately(self):
        p = self.run_agent('configure', 'https://gateway.example/', input=self.TOKEN + '\n')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((self.state / 'endpoint').read_text(), 'https://gateway.example\n')
        self.assertEqual((self.state / 'token').read_text(), self.TOKEN + '\n')
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o700)
        for name in ('endpoint', 'token'):
            self.assertEqual(stat.S_IMODE((self.state / name).stat().st_mode), 0o600)
        self.assertIn('run otel-agent install', p.stdout)

    def test_configure_rejects_plain_http_and_short_tokens(self):
        p = self.run_agent('configure', 'http://gateway.example', input=self.TOKEN + '\n')
        self.assertEqual(p.returncode, 64)
        p = self.run_agent('configure', 'https://gateway.example', input='short\n')
        self.assertEqual(p.returncode, 65)
        self.assertFalse((self.state / 'token').exists())

    def test_install_keeps_only_the_pinned_version(self):
        self.install_collector()
        self.install_collector('0.150.0')
        p = self.run_agent('install')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(sorted(d.name for d in self.libexec.iterdir()), [self.VERSION])
        self.assertIn('otel-agent configure', p.stdout)

    def test_unknown_command_is_a_usage_error(self):
        self.assertEqual(self.run_agent('bogus').returncode, 64)

    def test_collector_config_deletes_identity_and_content_keys(self):
        import re
        text = (FEATURES / 'agents.otel-agent/home/.config/otel-agent/config.yaml').read_text()
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

    def test_kubernetes_stays_read_only(self):
        self.fake(self.mcp / 'bin/kubernetes-mcp-server', 'k8s')
        out = self.run_mcp('kubernetes').stdout
        for flag in ('--read-only', '--disable-destructive', '--disable-multi-cluster'):
            self.assertIn(flag, out)


if __name__ == '__main__':
    unittest.main()
