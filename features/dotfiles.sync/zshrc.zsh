# The problems the last `dotfiles apply` left for the owner (feature
# dotfiles.sync): an unattended sync only logs them, so a new terminal says
# so. apply rewrites the file every run and removes it once there are none.
() {
  local file=${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles/attention
  [[ -s $file ]] || return 0
  local -a problems=("${(@f)$(<$file)}")
  print -u2 -- "dotfiles: ${#problems} problem(s) need you; the first: ${problems[1]}"
  print -u2 -- "dotfiles: see all with: dotfiles doctor"
}
