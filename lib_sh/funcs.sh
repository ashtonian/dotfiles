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


function chrome_list_ext_md() {
  local usage="Usage: chrome_list_ext_md [-o output_file] [--ids-only] [--browser browser_name]

Description: This function exports a list of installed Chrome, Brave, or Vivaldi extensions, with the option to output just the extension IDs.

Options:
  -o          Output the results to a file instead of the terminal
  --ids-only  List only the extension IDs, without additional information
  --browser   Specify the browser to use (chrome, brave, vivaldi). Default is chrome.
  --help      Show this help message
"

  local output_stream=true
  local output_file="chrome.md"
  local ids_only=false
  local browser="brave"

  while [[ "$#" -gt 0 ]]; do
    case $1 in
      -o)
        if [[ -n "$2" && $2 != -* ]]; then
          output_file="$2"
          shift 2
        else
          shift
        fi
        ;;
      --ids-only)
        ids_only=true
        shift
        ;;
      --browser)
        browser="$2"
        shift 2
        ;;
      --help)
        echo "$usage"
        return
        ;;
      *)
        echo "$usage"
        return
        ;;
    esac
  done

  typeset -A linux_dirs mac_dirs windows_dirs
  linux_dirs=(
    chrome "$HOME/.config/google-chrome/Default/Extensions"
    brave "$HOME/.config/BraveSoftware/Brave-Browser/Default/Extensions"
    vivaldi "$HOME/.config/vivaldi/Default/Extensions"
  )
  mac_dirs=(
    chrome "$HOME/Library/Application Support/Google/Chrome/Default/Extensions"
    brave "$HOME/Library/Application Support/BraveSoftware/Brave-Browser/Default/Extensions"
    vivaldi "$HOME/Library/Application Support/Vivaldi/Default/Extensions"
  )
  windows_dirs=(
    chrome "$LOCALAPPDATA/Google/Chrome/User Data/Default/Extensions"
    brave "$LOCALAPPDATA/BraveSoftware/Brave-Browser/User Data/Default/Extensions"
    vivaldi "$LOCALAPPDATA/Vivaldi/User Data/Default/Extensions"
  )
  local extensions_path
  case "$(uname)" in
    Linux*)
      extensions_path="${linux_dirs[$browser]}"
      ;;
    Darwin*)
      extensions_path="${mac_dirs[$browser]}"
      ;;
    CYGWIN*|MINGW*|MSYS*)
      extensions_path="${windows_dirs[$browser]}"
      ;;
    *)
      echo "Unsupported platform"
      return
      ;;
  esac

  if [[ -z "$extensions_path" ]]; then
    echo "Unsupported browser"
    return
  fi

  if ! $output_stream; then
    exec 3>&1
    exec 1> "$output_file"
  fi

  echo ""
  echo "## ${(C)browser} Extensions\n"
  echo ""

  for extension_id in ${(f)"$(command ls -1 "$extensions_path")"}; do
    local manifest_path="${extensions_path}/${extension_id}/$(command ls -v "${extensions_path}/${extension_id}" | tail -n 1)/manifest.json"

    if [[ -f "$manifest_path" ]]; then
      if $ids_only; then
        echo "$extension_id"
      else
        local manifest_content="$(cat "$manifest_path")"
        local name=$(jq -r '.name' <<< "$manifest_content")
        if [[ "$name" == "null" || "${name:0:2}" == "__" ]]; then
          name=$(jq -r '.short_name' <<< "$manifest_content")
        fi
        if [[ "$name" == "null" || "${name:0:2}" == "__" ]]; then
          name="N/A"
        fi
        local homepage_url=$(jq -r '.homepage_url' <<< "$manifest_content")
        local description=$(jq -r '.description' <<< "$manifest_content")

        if [[ "$description" == "null" || "${description:0:2}" == "__" ]]; then
          description="N/A"
        fi

        if [[ "$homepage_url" != "null" && "${homepage_url:0:2}" != "__" ]]; then
          description="([Homepage](${homepage_url})) ${description} "
        fi

        local extension_info="[${name}](https://chrome.google.com/webstore/detail/${extension_id}): ${description}"
        echo "- $extension_info"
      fi
    fi
  done


}


function brew_list_md() {
  local output_stream=true
  local output_file="brew.md"
  local show_dependencies=false
  local inline_dependencies=false
  local include_casks=false

  while (( $# > 0 )); do
    case "$1" in
      -d|--dependencies)
        show_dependencies=true
        shift
        ;;
      -i|--inline-dependencies)
        inline_dependencies=true
        shift
        ;;
      -c|--casks)
        include_casks=true
        shift
        ;;
      -o)
        if [[ -n "$2" && $2 != -* ]]; then
          output_file="$2"
          shift 2
        else
          shift
        fi
        ;;
      -h|--help)
        echo "Usage: brew_list_md [-d|--dependencies] [-i|--inline-dependencies] [-c|--casks] [-o output_file]"
        echo "Generate a markdown list of software installed via Homebrew."
        echo "Use the -c or --casks flag to lists Homebrew casks in a seperate section."
        echo "Use the -d or --dependencies flag to list Homebrew dependencies in a separate section."
        echo "Use the -i or --inline-dependencies flag to list and link dependencies for each Homebrew formula or cask."
        echo "By default, the output is sent to the standard output stream. Use the -o flag to output to a file (default: brew.md ), optionally specify the filename."
        return 0
        ;;
      *)
        echo "Unknown argument: $1"
        echo "Use -h or --help for usage information."
        return 1
        ;;
    esac
  done

  if ! $output_stream; then
    exec 3>&1
    exec 1> "$output_file"
  fi

  if $include_casks; then
    echo ""
    echo "## Homebrew Casks"
    echo ""

    cask_list=$(brew list --cask)

    for cask in ${(f)cask_list}; do
      info=$(brew info --cask --json=v2 $cask)
      name=$(jq -r '.casks[0].name[0]' <<< "$info")
      homepage=$(jq -r '.casks[0].homepage' <<< "$info")
      desc=$(jq -r '.casks[0].desc' <<< "$info")
      tap=$(jq -r '.casks[0].tap' <<< "$info")
      tap_url="https://github.com/$tap"

      if [[ $tap == "homebrew/cask" ]]; then
        echo "- [$name]($homepage): $desc"
      else
        echo "- [$name]($homepage) ([Tap: $tap]($tap_url)): $desc"
      fi

      if $inline_dependencies; then
        dependencies=$(jq -r '.casks[0].depends_on.formula[]' <<<"$info")
        if [[ -n $dependencies ]]; then
          echo "  - Dependencies:"
          for dep in ${(f)dependencies}; do
            dep_info=$(brew info --json=v2 $dep)
            dep_homepage=$(jq -r '.formulae[0].homepage' <<<"$dep_info")
            dep_url="https://formulae.brew.sh/formula/$dep"
            echo "    - [$dep]($dep_homepage) - [$dep]($dep_url)"
          done
        fi
      fi
    done
  fi

  echo ""
  echo "## Homebrew Formulaes"
  echo ""

  formulae=$(brew leaves)

  for formula in ${(f)formulae}; do
    formula_info=$(brew info --json=v2 $formula)
    name=$(jq -r '.formulae[0].name' <<< $formula_info)
    homepage=$(jq -r '.formulae[0].homepage' <<< $formula_info)
    desc=$(jq -r '.formulae[0].desc' <<< $formula_info)
    brew_url="https://formulae.brew.sh/formula/$formula"

    echo "- [$name]($homepage): $desc"

    if $inline_dependencies; then
      dependencies=$(brew deps $formula)
      if [[ -n $dependencies ]]; then
        echo "  - Dependencies:"
        for dep in ${(f)dependencies}; do
          formula_dep_info=$(brew info --json=v2 $dep)
          dep_homepage=$(jq -r '.formulae[0].homepage' <<< "$formula_dep_info")
          dep_url="https://formulae.brew.sh/formula/$dep"
          echo "    - [$dep]($dep_homepage) - [$dep]($dep_url)"
        done
      fi
    fi
  done

  if $show_dependencies; then
    echo ""
    echo "## Homebrew Dependencies"
    echo ""

    installed_formulae=$(brew list --formula -1)
    for formula in ${(f)installed_formulae}; do
      if [[ $(brew uses --installed $formula) ]]; then
        dep_form_info=$(brew info --json=v2 $formula)
        name=$(jq -r '.formulae[0].name' <<< $dep_form_info)
        homepage=$(jq -r '.formulae[0].homepage' <<< $dep_form_info)
        desc=$(jq -r '.formulae[0].desc' <<< $dep_form_info)
        brew_url="https://formulae.brew.sh/formula/$formula"

        echo "- [$name]($homepage) - [$formula]($brew_url): $desc"
      fi
    done
  fi
}

function mas_list_md() {
  output_stream=true
  output_file="mas.md"

  while (( $# > 0 )); do
    case "$1" in
      -o)
        if [[ -n "$2" && $2 != -* ]]; then
          output_file="$2"
          shift 2
        else
          shift
        fi
        ;;
      -h|--help)
        echo "Usage: mas_list_md [-o output_file]"
        echo "Generate a markdown list of software installed via MAS (Mac App Store)."
        echo "By default, the output is sent to the standard output stream. Use the -o flag followed by the output optional (default:mas.md) file name to save the output to a file instead."
        return 0
        ;;
      *)
        echo "Unknown argument: $1"
        echo "Use -h or --help for usage information."
        return 1
        ;;
    esac
  done

  if ! $output_stream; then
    exec 3>&1
    exec 1> "$output_file"
  fi

  echo ""
  echo "## Mac App Store Apps"
  echo ""

  app_list=$(mas list)
  for line in ${(f)app_list}; do
    app_id=$(echo $line | awk '{print $1}')
    app_name=$(echo $line | cut -f 2- -d ' ')
    app_store_url="https://apps.apple.com/app/id$app_id"

    echo "- $app_name - [$app_id]($app_store_url)"
  done
}

