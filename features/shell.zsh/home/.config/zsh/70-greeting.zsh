# Optional terminal greeting; enable with SHOW_COWSAY=true in ~/.zshrc.local.
dotfiles_greeting() {
    [[ "${SHOW_COWSAY:-false}" == true && "${ZSH_REAL_SESSION:-0}" == 1 && -t 1 ]] || return 0
    command -v cowsay &>/dev/null && command -v fortune &>/dev/null && command -v lolcat &>/dev/null || return 0
    local -a animals
    local animal
    animals=($(cowsay -l | tail -n +2))
    (( ${#animals} )) || return 0
    animal=${animals[$RANDOM % ${#animals} + 1]}
    fortune -s computers | cowsay -f "$animal" | lolcat
}
