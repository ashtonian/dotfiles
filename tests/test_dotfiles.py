import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIVE = Path.home() / '.dotfiles'


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
        code = 'source "$1"; eval "$("$2" --zsh)"; bindkey -M emacs "^R"; bindkey -M emacs "^[[A"'
        p = subprocess.run(['/bin/zsh', '-fc', code, 'test',
                            str(ROOT / 'stow/zsh/.config/zsh/40-keybindings.zsh'), fzf],
                           env=self.env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('atuin-search', p.stdout)
        self.assertIn('atuin-up-search', p.stdout)

    def test_ssh_local_overrides_win(self):
        local = self.path / 'ssh.local'
        local.write_text('Host dotfiles-fixture\n ControlMaster no\n ControlPath none\n IdentitiesOnly no\n UseKeychain no\n')
        config = (ROOT / 'stow/ssh/.ssh/config').read_text().replace('Include ~/.orbstack/ssh/config', '')
        config = config.replace('Include config.local', 'Include ' + str(local))
        file = self.path / 'ssh.config'
        file.write_text(config)
        p = subprocess.run(['/usr/bin/ssh', '-G', '-F', str(file), 'dotfiles-fixture'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('controlmaster false', p.stdout.replace('controlmaster no', 'controlmaster false'))
        self.assertIn('identitiesonly no', p.stdout)
        self.assertNotIn('controlpath /', p.stdout)

    def test_bootstrap_uses_no_invented_identity_or_initial_commit(self):
        for name in ('dracula-iterm', 'colorls', 'alfred-dracula', 'mackup'):
            (self.path / 'sync' / name).mkdir(parents=True)
        self.cli('git', 'printf "%s\\n" "$*" >> "$DOTFILES_TEST_AUDIT"')
        audit = self.path / 'git-audit'
        self.env['DOTFILES_TEST_AUDIT'] = str(audit)
        p = self.bash('SYNC_DIR="$1"; setup_sync_dir', str(self.path / 'sync'), source='install.sh')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('init', audit.read_text())
        self.assertNotIn('commit', audit.read_text())
        self.assertNotIn('user.email', audit.read_text())


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

    def test_real_git_operation_states_are_not_staged_or_committed(self):
        subprocess.run(['git', 'clone', '--shared', '--quiet', str(LIVE), str(self.path / 'repo')], check=True)
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
        (self.path / 'Brewfile').write_text('brew "example"\n')
        self.cli('brew', 'printf "%s AUTO_UPDATE=%s\\n" "$*" "$HOMEBREW_NO_AUTO_UPDATE" >> "$DOTFILES_TEST_AUDIT"\ncase "$*" in *check*) exit 1;; esac')
        p = self.bash('sync_brewfile')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('install --no-upgrade', audit.read_text())
        self.assertIn('AUTO_UPDATE=1', audit.read_text())

    def test_mackup_uses_temporary_config_and_preserves_symlink(self):
        config = self.path / 'mackup-source.cfg'
        original = '[storage]\nengine = file_system\npath = .sync\ndirectory = shared\n'
        config.write_text(original)
        linked = self.path / 'mackup.cfg'
        linked.symlink_to(config)
        audit = self.path / 'mackup-audit'
        self.env.update(MACKUP_CONFIG_FILE=str(linked), DOTFILES_TEST_AUDIT=str(audit))
        file = self.bin / 'mackup'
        file.write_text('''#!/usr/bin/env python3
import configparser, json, os, pathlib, sys
config_file = sys.argv[1].split('=', 1)[1]
config = configparser.ConfigParser()
config.read(config_file)
pathlib.Path(os.environ['DOTFILES_TEST_AUDIT']).write_text(json.dumps({'file':config_file,'storage':dict(config['storage'])}))
''')
        file.chmod(0o755)
        p = self.bash('stable_host() { echo FixtureHost; }; run_mackup_backup')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        data = json.loads(audit.read_text())
        self.assertEqual(data['storage']['path'], self.env['SYNC_DIR'])
        self.assertEqual(data['storage']['directory'], 'mackup/FixtureHost')
        self.assertFalse(Path(data['file']).exists())
        self.assertTrue(linked.is_symlink())
        self.assertEqual(config.read_text(), original)

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


class Delegate(Fixture):
    def test_read_worker_exposes_only_read_tools(self):
        if not shutil.which('bun'):
            self.skipTest('Bun required')
        dependencies = ROOT / 'stow/opencode/.config/opencode/node_modules'
        if not dependencies.exists():
            self.skipTest('OpenCode plugin dependencies required')
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
        harness = self.path / 'delegate.ts'
        harness.write_text('''
const {DelegatePlugin} = await import(process.env.DOTFILES + '/stow/opencode/.config/opencode/plugins/delegate.ts');
const {existsSync, readFileSync} = await import('node:fs');
const {join} = await import('node:path');
const hooks = await DelegatePlugin({client:{app:{log:async()=>({})},session:{promptAsync:async()=>({})}}});
const context = {sessionID:'fixture-owner',agent:'coordinator',directory:process.cwd(),ask:async()=>{throw Error('unexpected write approval')}};
const result = await hooks.tool.delegate_start.execute({worker:'claude',title:'fixture',task:'Read fixture',access:'read',cwd:process.cwd()},context);
const job = result.metadata.job;
const dir = join(process.env.DELEGATE_STATE_DIR,'jobs',job);
for (let i=0;i<100 && !existsSync(join(dir,'exit'));i++) await Bun.sleep(20);
if (!existsSync(join(dir,'exit'))) throw Error('worker did not exit');
process.stdout.write(readFileSync(join(dir,'argv.json'),'utf8'));
''')
        p = subprocess.run(['bun', str(harness)], cwd=self.path, env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        args = json.loads(p.stdout)
        self.assertIn('--restricted', args)
        self.assertEqual(args[args.index('--tools') + 1], 'Read,Glob,Grep')
        self.assertIn('--strict-mcp-config', args)
        self.assertEqual(json.loads(args[args.index('--mcp-config') + 1]), {'mcpServers': {}})
        self.assertNotIn('--dangerously-skip-permissions', args)


if __name__ == '__main__':
    unittest.main()
