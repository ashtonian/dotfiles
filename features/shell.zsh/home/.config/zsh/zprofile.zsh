# /etc/zprofile's path_helper moves the system directories in front of everything
# in login shells; restore the shared order (Homebrew and toolchains ahead of
# /usr/bin).
[[ -r "$HOME/.config/shell/env.sh" ]] && emulate sh -c '. "$HOME/.config/shell/env.sh"'

# OrbStack's command-line tools, where OrbStack is installed.
[[ -r ~/.orbstack/shell/init.zsh ]] && source ~/.orbstack/shell/init.zsh
