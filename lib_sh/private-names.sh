# shellcheck shell=bash
# private_names_found CHECKOUT ENGINE: print each tracked line in CHECKOUT that
# names something an overlay keeps private, and succeed when there is one.
# Each overlay ENGINE lists (`dotfiles overlays`) may hold denylist.txt: one
# name per line, matched as a whole word and ignoring case; blank lines and
# lines starting with # are skipped. The lists stay in the overlays, so the
# check runs only where they are cloned, never in public CI.
private_names_found() {
    local checkout="$1" engine="$2" dirs dir names
    dirs=$("$engine" overlays) || return 2
    names=$(
        while IFS= read -r dir; do
            [[ -n "$dir" && -f "$dir/denylist.txt" ]] || continue
            sed -e 's/[[:space:]]*#.*$//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$dir/denylist.txt"
        done <<< "$dirs" | sed '/^$/d' | sort -u
    )
    [[ -n "$names" ]] || return 1
    git -C "$checkout" grep -n -I -i -w -F -f <(printf '%s\n' "$names") -- .
}
