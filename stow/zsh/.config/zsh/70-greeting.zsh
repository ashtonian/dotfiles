# 70-greeting.zsh - Fun terminal greeting on shell startup

#=============================================================================
# COWSAY + FORTUNE + LOLCAT
#=============================================================================
SHOW_COWSAY=true

if [[ "${SHOW_COWSAY}" == "true" ]] && command -v cowsay &>/dev/null && command -v fortune &>/dev/null && command -v lolcat &>/dev/null; then
  animals=(
    blowfish dragon-and-cow hellokitty milk smallturkey bong dragon kiss
    moofasa turtle bud-frogs elephant-in-snake kitty moose stegosaurus tux
    bunnyelephant koala mutilated stimpy udder cheese eyes kosh ren supermilker
    vader-koala luke-koala satanic surgery vader daemon ghostbusters sheep
    telebears www beavis.zen default head-in meow skeleton three-eyes
  )
  animal=${animals[$RANDOM % $#animals + 1]}
  fortune -s computers | cowsay -f $animal | lolcat
fi
