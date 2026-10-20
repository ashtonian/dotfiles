# /etc/zprofile's path_helper moves the system directories in front of everything
# in login shells; restore the shared order (Homebrew and toolchains ahead of
# /usr/bin).
[[ -r "$HOME/.config/shell/env.sh" ]] && emulate sh -c '. "$HOME/.config/shell/env.sh"'


# Added by OrbStack: command-line tools and integration
# This won't be added again if you remove it.
source ~/.orbstack/shell/init.zsh 2>/dev/null || :
