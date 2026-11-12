# zlogin.zsh - login zsh, after ~/.zshenv, ~/.zprofile and ~/.zshrc, through the
# local ~/.zlogin stub (feature shell.zsh).

# Codex's `zsh -lc <command>` hands off to bash here, so lines installers
# appended to ~/.zshenv and ~/.zprofile have run first (see zshenv.zsh).
if (( $+functions[_dotfiles_agent_bash] )); then
    _dotfiles_agent_bash "$@"
    unfunction _dotfiles_agent_bash
fi
