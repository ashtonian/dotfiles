#!/usr/bin/env bash

# include library helpers for colorized echo and require_brew
source ./lib_sh/echos.sh
source ./lib_sh/requirers.sh

bot "Hi! I'm going to install tooling and tweak your system settings. Here I go...";ok

#######################################################################################################################################
bot "installing brew taps, casks & apps + mas apps + oh-my-zsh"
#######################################################################################################################################
running "install oh my zsh"
# install oh my zsh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)";ok
