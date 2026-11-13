# ~/.bash_profile - login bash (bash -l, ssh, a terminal set to bash) reads
# this file instead of ~/.bashrc, so hand off to the same configuration.
[ -r "$HOME/.bashrc" ] && . "$HOME/.bashrc"
