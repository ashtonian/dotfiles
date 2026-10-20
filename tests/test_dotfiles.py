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
    def worker_args(self, access):
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
        # Read jobs must never ask for write approval; write jobs are approved.
        ask = 'async()=>{throw Error("unexpected write approval")}' if access == 'read' else 'async()=>({})'
        harness = self.path / 'delegate.ts'
        harness.write_text('''
const {DelegatePlugin} = await import(process.env.DOTFILES + '/stow/opencode/.config/opencode/plugins/delegate.ts');
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
        for d in ('bin', '.local/bin', '.config/shell'):
            (self.home / d).mkdir(parents=True)
        (self.home / '.config/shell/env.sh').symlink_to(ROOT / 'stow/shell/.config/shell/env.sh')
        for name in ('.zshenv', '.zprofile'):
            (self.home / name).symlink_to(ROOT / 'stow/zsh' / name)
        (self.home / '.bashrc').symlink_to(ROOT / 'stow/shell/.bashrc')

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


class AgentShell(Fixture):
    def run_zsh(self, code, marker):
        env = dict(self.env)
        env.pop('AGENT_SHELL', None)
        if marker:
            env['AGENT_SHELL'] = 'codex'
        return subprocess.run(['/bin/zsh', '-f', '-c', f'source {ROOT}/stow/zsh/.zshenv; {code}'],
                              cwd=self.path, env=env, capture_output=True, text=True, timeout=20)

    def test_marked_shell_runs_bash_style_commands(self):
        p = self.run_zsh('print -r -- ==== ; print -r -- /nonexistent-*-glob; s="a b"; set -- $s; print $#;'
                         ' print -r -- "child:$(zsh -fc \'print -r -- ${AGENT_SHELL:-unset}\')"', True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.split(), ['====', '/nonexistent-*-glob', '2', 'child:unset'])

    def test_unmarked_shell_keeps_zsh_semantics(self):
        p = self.run_zsh('print -r -- /nonexistent-*-glob', False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('no matches found', p.stderr)


class AgentMonitorFixture(Fixture):
    NODE_VERSION = '24.22.0'

    def setUp(self):
        super().setUp()
        self.home = self.path / 'home'
        self.home.mkdir()
        self.monitor = self.home / '.local/share/agent-monitor'
        self.env.update(HOME=str(self.home), FNM_DIR=str(self.path / 'fnm'))
        self.env.pop('AGENT_MONITOR_HOME', None)
        self.env.pop('AGENT_MONITOR_PORT', None)
        self.env.pop('CODEX_HOME', None)

    def node_path(self):
        return self.path / f'fnm/node-versions/v{self.NODE_VERSION}/installation/bin/node'

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
        text = (ROOT / 'stow/otel-agent/.config/otel-agent/config.yaml').read_text()
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
    SCRIPT = ROOT / 'stow/agent-mcp/.local/bin/agent-mcp'

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
        self.assertIn('stow the agent-mcp package', p.stderr)

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
