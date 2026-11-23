# shellcheck shell=bash
# Log rotation for scripts that append to their own log file (sync.sh,
# bin/dotfiles-update.sh). A log a running process holds open, such as a
# LaunchAgent's StandardOutPath, cannot be moved aside; bin/disk-hygiene caps
# those in place.

# rotate_log FILE [MAX_BYTES] [KEEP]: once FILE is larger than MAX_BYTES
# (1 MiB), move it to FILE.<epoch>.old, and keep only the newest KEEP (3) of
# those archives.
rotate_log() {
    local file=$1 max=${2:-1048576} keep=${3:-3} archive index
    local archives=()
    if [[ -f $file ]] && (( $(wc -c <"$file") > max )); then
        mv -- "$file" "$file.$(date +%s).old"
    fi
    for archive in "$file".*.old; do
        [[ -f $archive ]] && archives+=("$archive")
    done
    # Epoch timestamps in the names sort from oldest to newest.
    for (( index = 0; index < ${#archives[@]} - keep; index++ )); do
        rm -f -- "${archives[$index]}"
    done
    return 0
}
