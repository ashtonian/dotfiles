#!/usr/bin/env zsh

function gitnr() {
    if (( $# != 1 )); then
        print -u2 'Usage: gitnr DIRECTORY'
        return 1
    fi
    mkdir -- "$1" && builtin cd -- "$1" || return
    git init || return
    local setting
    for setting in user.name user.email user.signingkey gpg.program commit.gpgsign; do
        git config --get "$setting" >/dev/null || true
    done
    touch README && git add -- README || return
    git commit -S -m 'First commit' && git verify-commit HEAD
}

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
	if command du -b /dev/null > /dev/null 2>&1; then
		local arg=-sbh;
	else
		local arg=-sh;
	fi
	if [[ -n "$@" ]]; then
		command du $arg -- "$@";
	else
		command du $arg .[^.]* ./*;
	fi;
}

# Start an HTTP server from a directory, optionally specifying the port
function server() {
	local port="${1:-8000}";
	sleep 1 && open "http://localhost:${port}/" &
	python3 -m http.server "$port";
}

# Run `dig` and display the most useful info
function digs() {
	dig +nocmd "$1" any +multiline +noall +answer;
}

# `tre` is a shorthand for `tree` with hidden files and color enabled, ignoring
# the `.git` directory, listing directories first. The output gets piped into
# `less` with options to preserve color and line numbers, unless the output is
# small enough for one screen.
function tre() {
	tree -aC -I '.git|node_modules|bower_components' --dirsfirst "$@" | less -FRNX;
}

# Find process using a port (macOS compatible)
# Note: Use 'whodat' function for a more user-friendly alternative
function whoisport() {
	local port="${1:?Usage: whoisport <port>}"
	lsof -i ":${port}" -sTCP:LISTEN
}

# NOTE: removed a custom realpath() that shadowed the system binary with a
# broken, symlink-unaware implementation. Use the real `realpath` (macOS 12+
# ships one; `brew install coreutils` provides `grealpath`).

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


# Example fix_ssh_permissions function (optional).
# Remove or adjust if you don’t need permissions adjustments.
fix_ssh_permissions() {
  local ssh_dir="$1"
  if [[ ! -d "$ssh_dir" ]]; then
    echo "Directory '$ssh_dir' does not exist or is not accessible."
    return 1
  fi
  chmod 700 "$ssh_dir"
  find "$ssh_dir" -type f \( -name "id_*" -o -name "*.key" \) -exec chmod 600 {} \; 2>/dev/null
  find "$ssh_dir" -type f -name "*.pub" -exec chmod 644 {} \; 2>/dev/null
}

bootstrap_ssh_key() {
  # Ensure at least a key name is passed
  # if [[ $# -lt 1 ]]; then
  #   echo "Usage: bootstrap_ssh_key <key_name> [<key_directory> <key_type> <key_bits> <passphrase>]"
  #   return 1
  # fi

  local key_name="${1:-id}"               # <- FIX: remove the extra '$' that was causing errors
  local key_directory="${2:-$HOME/.ssh}"
  local key_type="${3:-Ed25519}"
  local key_bits="${4:-4096}"
  local passphrase="${5:-}"

  key_name="${key_name}_${key_type}"

  local private_key_file="${key_directory}/${key_name}"
  local public_key_file="${private_key_file}.pub"

  # Create the directory if it doesn't exist
  mkdir -p "${key_directory}"

  # (Optional) Fix directory permissions if desired
  fix_ssh_permissions "${key_directory}"

  # Generate key if it doesn't already exist
  if [[ ! -f "${private_key_file}" ]]; then
    # Ed25519 doesn't allow a custom bit length, so skip -b for Ed25519
    if [[ "$key_type" =~ ^[Ee][Dd]25519$ ]]; then
      ssh-keygen -t "${key_type}" \
                 -N "${passphrase}" \
                 -f "${private_key_file}" || {
        echo "Error generating SSH key."
        return 1
      }
    else
      ssh-keygen -t "${key_type}" \
                 -b "${key_bits}" \
                 -N "${passphrase}" \
                 -f "${private_key_file}" || {
        echo "Error generating SSH key."
        return 1
      }
    fi

    # (Optional) Start ssh-agent only if none is running
    if [[ -z "$SSH_AUTH_SOCK" ]]; then
      eval "$(ssh-agent -s)"
    fi

    # (Optional) Fix permissions on newly created key files
    fix_ssh_permissions "${key_directory}"

    # Add the new key to the agent
    ssh-add "${private_key_file}"

  else
    echo "SSH key '${key_name}' already exists in '${key_directory}'."
  fi

  # Display the public key if it exists (using 'bat' with extra flags)
  if [[ -f "${public_key_file}" ]]; then
    bat --style=changes,snip --paging=never "${public_key_file}"
  else
    echo "Warning: No public key file found at '${public_key_file}'."
  fi
}

function vscode_extensions_list() {
    if (( $# == 0 )); then
        vscode_list_md -o vscode_extensions_list.md
    else
        vscode_list_md "$@"
    fi
}

function vscode_list_md() (
    local output_file='' extensions extension publisher name details display description
    while (( $# )); do
        case "$1" in
            -o|--output)
                if (( $# < 2 )) || [[ -z "$2" || "$2" == -* ]]; then
                    print -u2 'An output filename is required.'
                    return 1
                fi
                output_file="$2"; shift 2 ;;
            -h|--help) print 'Usage: vscode_list_md [-o FILE]'; return 0 ;;
            *) print -u2 "Unknown argument: $1"; return 1 ;;
        esac
    done
    extensions=$(code --list-extensions) || return
    [[ -z "$output_file" ]] || exec > "$output_file"
    print '## VSCode Extensions List'
    print
    for extension in ${(f)extensions}; do
        [[ -n "$extension" ]] || continue
        publisher="${extension%%.*}"; name="${extension#*.}"
        display="$extension"; description=''
        if details=$(curl -fsS --max-time 10 "https://marketplace.visualstudio.com/_apis/public/gallery/publishers/$publisher/extensions/$name/latest" -H 'Accept: application/json' 2>/dev/null); then
            display=$(print -r -- "$details" | jq -r --arg fallback "$extension" '.displayName // $fallback' 2>/dev/null) || display="$extension"
            description=$(print -r -- "$details" | jq -r '.shortDescription // ""' 2>/dev/null) || description=''
        fi
        printf -- '- [%s](https://marketplace.visualstudio.com/items?itemName=%s)%s\n' "$display" "$extension" "${description:+: $description}"
    done
)

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


function chrome_list_ext_md() (
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
          output_stream=false
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
        local manifest_content="$(command cat "$manifest_path")"
        local name=$(jq -r '.name' <<< "$manifest_content")
        if [[ "$name" == "null" || "${name:0:2}" == "__" ]]; then
          name=$(jq -r '.short_name' <<< "$manifest_content")
        fi
        if [[ "$name" == "null" || "${name:0:2}" == "__" ]]; then
          name="$extension_id"
        fi
        local homepage_url=$(jq -r '.homepage_url' <<< "$manifest_content")
        local description=$(jq -r '.description' <<< "$manifest_content")

        if [[ "$description" == "null" || "${description:0:2}" == "__" ]]; then
          description=""
        fi

        if [[ "$homepage_url" != "null" && "${homepage_url:0:2}" != "__" ]]; then
          description="([Homepage](${homepage_url})) ${description} "
        fi

        local extension_info="[${name}](https://chrome.google.com/webstore/detail/${extension_id}): ${description}"
        echo "- $extension_info"
      fi
    fi
  done
)


function brew_list_md() (
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
          output_stream=false
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
)

function mas_list_md() (
  output_stream=true
  output_file="mas.md"

  while (( $# > 0 )); do
    case "$1" in
      -o)
        if [[ -n "$2" && $2 != -* ]]; then
          output_file="$2"
          output_stream=false
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
)

function flush_dns(){
  sudo dscacheutil -flushcache
  sudo killall -HUP mDNSResponder
}

function tf_destroy_apply(){
  bot "bro you tryna rebuild [y|n]?"
  read -r "?" response
  if [[ $response =~ (yes|y|Y) ]];then
    action "you'da boss."
    terraform destroy -var-file=.tfvars -auto-approve
    terraform apply -var-file=.tfvars -auto-approve
  else
    ok
  fi
}

function rename_aws_profile() {
    if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
        print 'Usage: rename_aws_profile OLD_PROFILE NEW_PROFILE'
        return 0
    fi
    if (( $# != 2 )); then
        print -u2 'Usage: rename_aws_profile OLD_PROFILE NEW_PROFILE'
        return 1
    fi
    python3 "${DOTFILES:-$HOME/.dotfiles}/bin/aws-profile" rename "$1" "$2"
}

# AWS profile completion for rename_aws_profile. Deferred: the credentials file
# is read at completion time (compctl -K calls the function), NOT on every shell
# startup, and a missing file is harmless.
_aws_profile_names() {
    reply=(${(f)"$(awk -F'[][]' '/^\[/{print $2}' "${AWS_SHARED_CREDENTIALS_FILE:-$HOME/.aws/credentials}" 2>/dev/null)"})
}
compctl -K _aws_profile_names rename_aws_profile

function tfmt(){
  local lpath="${1:-.}" # Use the first argument as the lpath, default to "." if not provided
  find "$lpath" -name "*.tf" -print0 | xargs -0 terraform fmt
}

# duplicated from ./funcs.sh not sure h
function action() {
    echo -e "\n${COL_YELLOW}[action]:$COL_RESET\n ⇒ $1..."
}
function ok() {
    echo -e "${COL_GREEN}[ok]$COL_RESET "$1
}
function bot() {
    echo -e "\n$COL_GREEN\[._.]/$COL_RESET - "$1
}

# uploads to github gpg keys, generate keys with gpg --full-generate-key
function upload_gpg_to_github() {
    # Check for GPG and GitHub CLI
    if ! command -v gpg &> /dev/null; then
        echo "GPG is not installed. Please install GPG."
        return 1
    fi

    if ! command -v gh &> /dev/null; then
        echo "GitHub CLI is not installed. Please install GitHub CLI and login."
        return 1
    fi

    # List existing GPG keys
    echo "Checking for existing GPG keys..."
    gpg --list-secret-keys --keyid-format LONG

    # Prompt for email used in the GPG key
    echo -n "Enter the email associated with the GPG key: "
    read email

    # Get the GPG key ID for the given email
    key_id=$(gpg --list-secret-keys --keyid-format LONG | grep -B 2 $email | head -n 1 | awk '{print $2}' | cut -d '/' -f 2)

    if [[ -z "$key_id" ]]; then
        echo "No GPG key found for $email. Please generate a key first. run: gpg --full-generate-key"
        return 1
    fi

    echo "Using GPG key ID: $key_id"

    # Export the GPG key
    echo "Exporting GPG key..."
    gpg --armor --export $email > gpg_key.pub

    # Upload the GPG key to GitHub
    echo "Uploading GPG key to GitHub..."
    if gh api user/gpg_keys -F armored_public_key=@"gpg_key.pub"; then
        echo "GPG key successfully uploaded to GitHub."
    else
        echo "Failed to upload GPG key to GitHub."
        return 1
    fi

    # Configure Git to use the GPG key
    git config --global user.signingkey $key_id
    git config --global commit.gpgsign true
    echo "Git configured to use GPG key: $key_id for signing."

    # Cleanup
    rm -f gpg_key.pub
    echo "Temporary GPG key file removed."
}

function upload_github_ssh_key() {
  local ssh_folder="$HOME/.ssh"   # default SSH folder
  local key_name=""               # optional title for the key
  local key_type=""               # "access" or "codesigning"
  local interactive=true          # if false, run non-interactive
  local chosen_key_file=""

  # Helper function to display usage/help
  function _show_help() {
    cat <<EOF
Usage: upload_github_ssh_key [options]

Scans a folder for SSH keys (public or private). If a private key is selected,
this script generates a public key from it and uploads to GitHub via gh CLI.

Options:
  -h, --help         Show this help message
  -d, --dir <dir>    Directory to scan for SSH keys (default: \$HOME/.ssh)
  -t, --type <type>  Key type: 'access' or 'codesigning'
                     (maps to 'authentication' or 'signing' in gh CLI)
  -n, --name <name>  Title for the uploaded key
  -y, --yes          Non-interactive mode: no user prompts
EOF
  }

  # Parse command-line arguments
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        _show_help
        return 0
        ;;
      -d|--dir)
        if [[ -n "$2" ]]; then
          ssh_folder="$2"
          shift 2
        else
          echo "Error: --dir requires a folder path."
          return 1
        fi
        ;;
      -t|--type)
        if [[ -n "$2" ]]; then
          if [[ "$2" == "access" || "$2" == "codesigning" ]]; then
            key_type="$2"
          else
            echo "Error: --type must be 'access' or 'codesigning'."
            return 1
          fi
          shift 2
        else
          echo "Error: --type requires 'access' or 'codesigning'."
          return 1
        fi
        ;;
      -n|--name)
        if [[ -n "$2" ]]; then
          key_name="$2"
          shift 2
        else
          echo "Error: --name requires a string."
          return 1
        fi
        ;;
      -y|--yes)
        interactive=false
        shift
        ;;
      *)
        echo "Unknown argument: $1"
        _show_help
        return 1
        ;;
    esac
  done

  # Validate the specified SSH directory
  if [[ ! -d "$ssh_folder" ]]; then
    echo "Error: SSH folder '$ssh_folder' does not exist."
    return 1
  fi

  # Gather potential key files (public .pub or private key headers)
  # This will collect all files in the directory, ignoring subfolders
  # We do '.*' and '*' to catch hidden or standard-named keys.
  # Adjust as you see fit (maybe only '*' if you don't want hidden).
  local all_files=(${ssh_folder}/*(N) ${ssh_folder}/.*(N))
  local possible_keys=()

  for f in "${all_files[@]}"; do
    # Skip directories
    [[ -d "$f" ]] && continue
    # We’ll do a quick check:
    # 1) If filename ends in .pub, definitely a public key.
    # 2) Otherwise, read the first few lines for a private key marker
    #    (e.g. RSA, OPENSSH, ED25519, ECDSA, EC).
    if [[ "$f" == *.pub ]]; then
      possible_keys+=("$f")
    else
      # Check for typical private key headers
      if grep -qE '^-----BEGIN (RSA |OPENSSH |EC |ED25519 |ECDSA )?PRIVATE KEY-----' "$f" 2>/dev/null; then
        possible_keys+=("$f")
      fi
    fi
  done

  if [[ ${#possible_keys[@]} -eq 0 ]]; then
    echo "No private or public SSH keys found in '$ssh_folder'."
    return 1
  fi

  # Interactive mode - list available keys for user selection
  if $interactive; then
    echo "Found the following SSH keys in '$ssh_folder':"
    local i=1
    for pk in "${possible_keys[@]}"; do
      echo "  $i) $(basename "$pk")"
      ((i++))
    done

    local selection
    while true; do
      read -r "?Enter the number of the key to upload: " selection
      if [[ "$selection" =~ ^[0-9]+$ ]] && (( selection >= 1 && selection <= ${#possible_keys[@]} )); then
        chosen_key_file="${possible_keys[$selection]}"
        break
      else
        echo "Invalid selection. Please enter a number from 1 to ${#possible_keys[@]}."
      fi
    done

    # Prompt for key title if none given
    if [[ -z "$key_name" ]]; then
      read -r "?Enter a title for this key (e.g., 'Work Laptop Key'): " key_name
      [[ -z "$key_name" ]] && key_name="Untitled Key"
    fi

    # Prompt for key type if none given
    if [[ -z "$key_type" ]]; then
      local type_input
      while true; do
        read -r "?Is this an access key or a code signing key? (access/codesigning): " type_input
        if [[ "$type_input" == "access" || "$type_input" == "codesigning" ]]; then
          key_type="$type_input"
          break
        else
          echo "Invalid input. Enter 'access' or 'codesigning'."
        fi
      done
    fi
  else
    # Non-interactive mode
    chosen_key_file="${possible_keys[1]}"
    [[ -z "$key_name" ]] && key_name="Untitled Key"
    [[ -z "$key_type" ]] && key_type="access"
  fi

  # Final safety checks
  if [[ -z "$chosen_key_file" ]]; then
    echo "Error: no key file selected."
    return 1
  fi

  # Decide if it's private or public by extension or content
  local is_private=false
  if [[ "$chosen_key_file" != *.pub ]]; then
    if grep -qE '^-----BEGIN (RSA |OPENSSH |EC |ED25519 |ECDSA )?PRIVATE KEY-----' "$chosen_key_file" 2>/dev/null; then
      is_private=true
    fi
  fi

  # If private key, generate a temporary public key
  local tmp_pub_key=""
  if $is_private; then
    echo "Selected key is a PRIVATE key. Generating public key with ssh-keygen..."
    tmp_pub_key="$(mktemp /tmp/github_pubkey.XXXXXX)"
    if ! ssh-keygen -y -f "$chosen_key_file" > "$tmp_pub_key" 2>/dev/null; then
      echo "Error: Failed to generate a public key from '$chosen_key_file'."
      rm -f "$tmp_pub_key"
      return 1
    fi
    echo "Public key generated at $tmp_pub_key (temporary)."
  else
    # Otherwise, it's already a public key
    tmp_pub_key="$chosen_key_file"
  fi

  local exit_code=0
  gh auth refresh --scopes "admin:public_key,admin:ssh_signing_key" || exit_code=$?
  if (( exit_code )); then
    $is_private && command rm -f -- "$tmp_pub_key"
    return "$exit_code"
  fi
  # Map user type "access" -> gh --type "authentication"
  #                "codesigning" -> gh --type "signing"
  local gh_type="authentication"
  if [[ "$key_type" == "codesigning" ]]; then
    gh_type="signing"
  fi

  # Use gh CLI to upload
  echo "Uploading key '$chosen_key_file' as '$key_name' ($gh_type) to GitHub..."
  gh ssh-key add "$tmp_pub_key" --title "$key_name" --type "$gh_type"
  exit_code=$?
  if $is_private; then
    command rm -f -- "$tmp_pub_key"
  fi

  if [[ $exit_code -eq 0 ]]; then
    echo "SSH key successfully uploaded to GitHub."
  else
    echo "Failed to upload SSH key. (gh exit code: $exit_code)"
  fi

  return $exit_code
}



function install_brewfiles() (
    setopt localoptions nullglob nocaseglob
    local -a brewfiles=(Brewfile-*(.)) selection parts
    local input part first last index file
    if [[ "${1:-}" == --help ]]; then
        print 'Usage: install_brewfiles [all|none|1,2|1-3]'
        return 0
    fi
    if (( ! ${#brewfiles} )); then
        print 'No Brewfiles found.'
        return 0
    fi
    if (( $# )); then
        input="$*"
    else
        for (( index=1; index <= ${#brewfiles}; index++ )); do
            printf '%d. %s\n' "$index" "${brewfiles[$index]}"
        done
        read -r 'input?Select Brewfiles (1,2; 1-3; all; none): ' || return 1
    fi
    case "$input" in
        all) selection=("${brewfiles[@]}") ;;
        none) return 0 ;;
        *)
            parts=(${=input//,/ })
            for part in "${parts[@]}"; do
                if [[ "$part" == <-> ]]; then
                    first=$((10#$part)); last=$first
                elif [[ "$part" == <->-<-> ]]; then
                    first=$((10#${part%-*})); last=$((10#${part#*-}))
                else
                    print -u2 "Invalid selection: $part"; return 1
                fi
                if (( first < 1 || last < first || last > ${#brewfiles} )); then
                    print -u2 "Selection is out of range: $part"; return 1
                fi
                for (( index=first; index <= last; index++ )); do
                    selection+=("${brewfiles[$index]}")
                done
            done ;;
    esac
    (( ${#selection} )) || return 1
    typeset -U selection
    local combined
    combined=$(mktemp "${TMPDIR:-/tmp}/dotfiles-brewfile.XXXXXX") || return
    trap 'command rm -f -- "$combined"' EXIT
    for file in "${selection[@]}"; do
        command cat -- "$file" >> "$combined" || return
        print >> "$combined"
    done
    brew bundle install --no-upgrade --file="$combined"
)

function whodat() {
    if [[ $1 == "help" ]]; then
        echo "Usage: whodat <port>"
        echo "Displays the application name and PID using the specified port."
        return 0
    fi

    if [[ -z $1 ]]; then
        echo "Error: No port number provided."
        echo "Use 'whodat help' for usage information."
        return 1
    fi

    local port=$1
    local info=$(lsof -i :$port -sTCP:LISTEN -Fpcn)

    if [[ -z $info ]]; then
        echo "No process found listening on port $port."
        return 1
    else
        echo "Application and PID using port $port:"
        echo "$info" | grep -E "p[0-9]+" -o | cut -c 2- | xargs -I {} ps -p {} -o comm=
        echo "$info" | grep -E "p[0-9]+" -o | cut -c 2-
    fi
}

function getem() {
    if [[ $1 == "help" ]]; then
        echo "Usage: getem <port>"
        echo "Kills the process that is using the specified port."
        return 0
    fi

    if [[ -z $1 ]]; then
        echo "Error: No port number provided."
        echo "Use 'getem help' for usage information."
        return 1
    fi

    local port=$1
    local pid=$(lsof -ti :$port -sTCP:LISTEN)

    if [[ -z $pid ]]; then
        echo "No process found listening on port $port."
        return 1
    else
        echo "Killing PID $pid that is using port $port."
        kill $pid
        if [[ $? -eq 0 ]]; then
            echo "Process $pid successfully terminated."
        else
            echo "Failed to kill process $pid."
            return 1
        fi
    fi
}

function assume_role() {
    if [[ "${1:-}" == --help ]]; then
        print 'Usage: assume_role ROLE_ARN SESSION_NAME PROFILE_NAME [REGION]'
        return 0
    fi
    if (( $# < 3 || $# > 4 )); then
        print -u2 'Usage: assume_role ROLE_ARN SESSION_NAME PROFILE_NAME [REGION]'
        return 1
    fi
    local output
    if ! output=$(aws sts assume-role --role-arn "$1" --role-session-name "$2" --output json); then
        print -u2 'Error assuming role; credentials were not changed.'
        return 1
    fi
    print -r -- "$output" | python3 "${DOTFILES:-$HOME/.dotfiles}/bin/aws-profile" assume "$3" "${4:-us-east-1}"
}

function run_on_servers() {
  # Usage/help text
  local usage="Usage: run_on_servers [--ignore-fingerprint|-i] <command_or_script> <server1> [server2 ...]"

  # Initialize ignore_fingerprint to false by default
  local ignore_fingerprint=false

  # Parse the optional flag first
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --ignore-fingerprint|-i)
        ignore_fingerprint=true
        shift
        ;;
      *)
        # First non-flag argument encountered; break out of the loop
        break
        ;;
    esac
  done

  # Now we need at least two arguments: a command/script + at least one server
  if (( $# < 2 )); then
    echo "$usage"
    return 1
  fi

  # The first (non-flag) argument is either a script file or a command.
  local script_or_cmd=$1
  shift

  # The remaining arguments are the target servers
  local servers=("$@")

  # Build an array of SSH/SCP options
  local ssh_opts=()
  if [[ "$ignore_fingerprint" == true ]]; then
    ssh_opts=( -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" )
  fi

  # If it's a file, we copy and run the file on each server
  if [[ -f "$script_or_cmd" ]]; then
    local script_name
    script_name="$(basename "$script_or_cmd")"
    for server in "${servers[@]}"; do
      echo "===== [${server}] Transferring and running script: ${script_or_cmd} ====="
      scp "${ssh_opts[@]}" "$script_or_cmd" "${server}:/tmp/${script_name}"
      ssh "${ssh_opts[@]}" "$server" "chmod +x /tmp/${script_name} && /tmp/${script_name}"
    done
  else
    # Otherwise, treat the first argument as a command and run directly over SSH
    for server in "${servers[@]}"; do
      echo "===== [${server}] Running command: ${script_or_cmd} ====="
      ssh "${ssh_opts[@]}" "$server" "$script_or_cmd"
    done
  fi
}


# # Usage: run_on_hosts.sh <host_file> <local_script> [<script_args>...]
# #   - host_file: A file containing one hostname/IP per line
# #   - local_script: Path to the script you want to run on each host
# #   - script_args (optional): Any additional arguments for the script

# # Check for at least 2 arguments
# if [ $# -lt 2 ]; then
#   echo "Usage: $0 <host_file> <local_script> [<script_args>...]"
#   exit 1
# fi

# HOST_FILE="$1"
# LOCAL_SCRIPT="$2"
# shift 2  # Shift remaining arguments to pass them to the remote script

# # Loop through each host in the file
# while read -r HOST; do
#   # Skip empty lines or commented lines
#   [[ -z "$HOST" || "$HOST" == \#* ]] && continue

#   echo "----- Running script on $HOST -----"

#   # Execute the local script on the remote server
#   # "-- < $LOCAL_SCRIPT" pipes the local script into bash on the remote side
#   # "$@" passes any extra arguments to the remote script
#   ssh -o StrictHostKeyChecking=no "$HOST" "bash -s" -- < "$LOCAL_SCRIPT" "$@"

#   echo "----- Done with $HOST -----"
#   echo
# done < "$HOST_FILE"
