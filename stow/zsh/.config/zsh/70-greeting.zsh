# 70-greeting.zsh - Fun terminal greeting on shell startup

#=============================================================================
# COWSAY + FORTUNE + LOLCAT
#=============================================================================
SHOW_COWSAY=true

if [[ "${SHOW_COWSAY}" == "true" ]] && command -v cowsay &>/dev/null && command -v fortune &>/dev/null && command -v lolcat &>/dev/null; then
  # Built from `cowsay -l` on this system
  animals=($(cowsay -l | tail -n +2))
  animal=${animals[$RANDOM % $#animals + 1]}
  fortune -s computers | cowsay -f $animal | lolcat
fi
