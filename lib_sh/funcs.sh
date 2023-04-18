#!/usr/bin/env zsh

function gitnr() { mkdir $1; cd $1; git init; touch README; git add README; git commit -mFirst-commit;}

# Do a Matrix movie effect of falling characters
function matrix1() {
    echo -e "\e[1;40m" ; clear ; while :; do echo $LINES $COLUMNS $(( $RANDOM % $COLUMNS)) $(( $RANDOM % 72 )) ;sleep 0.05; done|gawk '{ letters="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*()"; c=$4; letter=substr(letters,c,1);a[$3]=0;for (x in a) {o=a[x];a[x]=a[x]+1; printf "\033[%s;%sH\033[2;32m%s",o,x,letter; printf "\033[%s;%sH\033[1;37m%s\033[0;0H",a[x],x,letter;if (a[x] >= $1) { a[x]=0; } }}'
}

function matrix2() {
    echo -e "\e[1;40m" ; clear ; characters=$( jot -c 94 33 | tr -d '\n' ) ; while :; do echo $LINES $COLUMNS $(( $RANDOM % $COLUMNS)) $(( $RANDOM % 72 )) $characters ;sleep 0.05; done|gawk '{ letters=$5; c=$4; letter=substr(letters,c,1);a[$3]=0;for (x in a) {o=a[x];a[x]=a[x]+1; printf "\033[%s;%sH\033[2;32m%s",o,x,letter; printf "\033[%s;%sH\033[1;37m%s\033[0;0H",a[x],x,letter;if (a[x] >= $1) { a[x]=0; } }}'
}

# Create a new directory and enter it
function mkd() {
	mkdir -p "$@" && cd "$_";
}

# Determine size of a file or total size of a directory
function fs() {
	if du -b /dev/null > /dev/null 2>&1; then
		local arg=-sbh;
	else
		local arg=-sh;
	fi
	if [[ -n "$@" ]]; then
		du $arg -- "$@";
	else
		du $arg .[^.]* ./*;
	fi;
}

# Start an HTTP server from a directory, optionally specifying the port
# TODO: conv to go static
function server() {
	local port="${1:-8000}";
	sleep 1 && open "http://localhost:${port}/" &
	# Set the default Content-Type to `text/plain` instead of `application/octet-stream`
	# And serve everything as UTF-8 (although not technically correct, this doesn’t break anything for binary files)
	python -c $'import SimpleHTTPServer;\nmap = SimpleHTTPServer.SimpleHTTPRequestHandler.extensions_map;\nmap[""] = "text/plain";\nfor key, value in map.items():\n\tmap[key] = value + ";charset=UTF-8";\nSimpleHTTPServer.test();' "$port";
}

# Run `dig` and display the most useful info
function digga() {
	dig +nocmd "$1" any +multiline +noall +answer;
}

# `tre` is a shorthand for `tree` with hidden files and color enabled, ignoring
# the `.git` directory, listing directories first. The output gets piped into
# `less` with options to preserve color and line numbers, unless the output is
# small enough for one screen.
function tre() {
	tree -aC -I '.git|node_modules|bower_components' --dirsfirst "$@" | less -FRNX;
}

function whoisport (){
        port=$1
        pidInfo=$(fuser $port/tcp 2> /dev/null)
        pid=$(echo $pidInfo | cut -d':' -f2)
        ls -l /proc/$pid/exe
}

function realpath() {
    [[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"
}

function move_and_link() {
    if [ $# -ne 2 ]; then
        echo "Usage: move_and_link <source_path> <target_path>"
        return 1
    fi

    source_path="$1"
    target_path="$2"
    target_parent="$(dirname -- "$target_path")"

    # Check if source path is valid and writable, and if target parent directory is valid and writable
    if [ ! -e "$source_path" ] || [ ! -w "$source_path" ]; then
        echo "Error: Invalid or unwritable source path."
        return 1
    fi

	if [ ! -d "$target_parent" ] || [ ! -w "$target_parent" ]; then
        echo "Error: Invalid or unwritable target path."
        return 1
    fi

    # Check if target path exists
    if [ -e "$target_path" ]; then
        echo "Error: Target path $target_path already exists."
        return 1
    fi

    # Move the file or folder to the new location
    mv "$source_path" "$target_path"

    # Create a symbolic link at the original location
    ln -s "$target_path" "$source_path"

    echo "Moved $source_path to $target_path and created a symbolic link."
}


# Usage: bootstrap_ssh_key <key_name> [<key_directory> <key_type> <key_bits> <passphrase>]
bootstrap_ssh_key() {
  local key_name=$1
  local key_directory=${2:-~/.ssh}
  local key_type=${3:-rsa}
  local key_bits=${4:-4096}
  local passphrase=${5:-""}

  local private_key_file="${key_directory}/${key_name}"
  local public_key_file="${private_key_file}.pub"

  # Create the directory if it doesn't exist
  mkdir -p "${key_directory}"

  # Check if the private key file exists
  if [[ ! -f "${private_key_file}" ]]; then
    # Generate the SSH key
    ssh-keygen -t "${key_type}" -b "${key_bits}" -N "${passphrase}" -f "${private_key_file}"

    # Add the key to the SSH agent
    eval "$(ssh-agent -s)"
    ssh-add "${private_key_file}"

  else
    echo "SSH key '${key_name}' already exists in '${key_directory}'."
  fi
  cat --style=changes,snip --paging=never ${public_key_file}
}


function export_chrome_extensions() {
  local usage="Usage: export_chrome_extensions [output_file]"

  local output_file="chrome_extensions.md"

  if [[ "$#" -eq 1 ]]; then
    if [[ "$1" = "--help" ]]; then
      echo $usage
      return
    else
      output_file="$1"
    fi
  elif [[ "$#" -gt 1 ]]; then
    echo $usage
    return
  fi

  local extensions_path
  case "$(uname)" in
    Linux*)   extensions_path="$HOME/.config/google-chrome/Default/Extensions" ;;
    Darwin*)  extensions_path="$HOME/Library/Application Support/Google/Chrome/Default/Extensions" ;;
    CYGWIN*|MINGW*|MSYS*) extensions_path="$LOCALAPPDATA/Google/Chrome/User Data/Default/Extensions" ;;
    *)
      echo "Unsupported platform"
      return
      ;;
  esac

  echo "# Chrome Extensions\n" > "$output_file"

  for extension_id in ${(f)"$(ls -1 "$extensions_path")"}; do
    local manifest_path="${extensions_path}/${extension_id}/$(ls -v "${extensions_path}/${extension_id}" | tail -n 1)/manifest.json"

    if [[ -f "$manifest_path" ]]; then
      local extension_info=$(cat "$manifest_path" | jq -r '"\(.name) | https://chrome.google.com/webstore/detail/\(.id) | \(.description)"')
      echo "- $extension_info" >> "$output_file"
    fi
  done

  echo "Markdown list saved to $output_file"
}

#!/bin/zsh
function open_chrome_extensions() {
  local usage="Usage: open_chrome_extensions [extension_id1] [extension_id2] ..."

  local default_extension_ids=("default_extension_id1" "default_extension_id2")

  if [[ "$#" -eq 0 ]]; then
    echo "Using default extension IDs"
    set -- "${default_extension_ids[@]}"
  elif [[ "$1" = "--help" ]]; then
    echo $usage
    return
  fi

  for extension_id in "$@"
  do
    local link="https://chrome.google.com/webstore/detail/${extension_id}"
    xdg-open $link || open $link || start chrome $link
  done
}
function brew_mas_list() {
  output_file="software_list.md"
  directly_installed=false

  while (( $# > 0 )); do
    case "$1" in
      -d)
        directly_installed=true
        shift
        ;;
      -h|--help)
        echo "Usage: brew_mas_list [-d] [output_file]"
        echo "Generate a markdown list of software installed via Homebrew and MAS (Mac App Store)."
        echo "The output file is optional; by default, it is named 'software_list.md'."
        echo "Use the -d flag to list only directly installed Homebrew formulae."
        return 0
        ;;
      *)
        output_file="$1"
        shift
        ;;
    esac
  done

  echo "# Brew and MAS installed software list" > "$output_file"
  echo "" >> "$output_file"

  echo "## Homebrew" >> "$output_file"
  echo "" >> "$output_file"

  if $directly_installed; then
    formulae=$(brew leaves)
  else
    formulae=$(brew list --formula -1)
  fi

  for formula in ${(f)formulae}; do
    name=$(brew info --json=v2 $formula | jq -r '.formulae[0].name')
    homepage=$(brew info --json=v2 $formula | jq -r '.formulae[0].homepage')
    desc=$(brew info --json=v2 $formula | jq -r '.formulae[0].desc')
    brew_url="https://formulae.brew.sh/formula/$formula"

    echo "- [$name]($homepage) - [$formula]($brew_url): $desc" >> "$output_file"
  done

  echo "" >> "$output_file"
  echo "## Mac App Store" >> "$output_file"
  echo "" >> "$output_file"

  mas list | while read -r line; do
    app_id=$(echo $line | awk '{print $1}')
    app_name=$(echo $line | cut -f 2- -d ' ')
    app_store_url="https://apps.apple.com/app/id$app_id"

    echo "- $app_name - [$app_id]($app_store_url)" >> "$output_file"
  done
}
