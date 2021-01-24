# $HOME

This is my cross platform home folder - which contains post install scripts and related dotfiles for MacOS Catalina(OS X) and Windows 10. As well as my homelab setup, and network appliance install scripts, configs and docker files.



// TODO: 
// alias .macup.cfg to home 
// install brew 
// macup restore 
// os init 2 (settings based on apps)
// cron jobs 
// git sync 
// brewfile sync n save. 
// rename dotfiles


```sh
# initializes xcode & git 
sudo xcode-select --install
mkdir ~/Projects
git clone https://github.com/Ashtonian/-HOME.git
./~/Projects/-Home/catalina/init1.sh
```






## Manual Annoyances 

* Init.sh uses comments to deliniate between laptop / desktop setups
* 1password global shortcut cmd + \ conflicts with vscode split pane 

## Inspiration and related 
https://gist.github.com/brandonb927/3195465 
https://github.com/mathiasbynens/dotfiles
https://github.com/webpro/awesome-dotfiles
https://github.com/dotfiles/dotfiles.github.com 
https://github.com/atomantic/dotfiles/blob/master/install.sh






// TODO: ToC

## Mac OS Setup

This will initialize a freshly installed Mac OS (catalina) instance with all of applications, cli tools, and adjust some basic operating system settings.

### Instructions:

* Update macos and sign into apple, google accounts.
* run `macos.sh`
* setup mackup backing cloud (dropbox)
* run `mackup restore`

At this point most of the applications, cli tools, and background services should be installed and configured. Some may require additional first time setup.

Notes:
* package manager preference brew/cask -> mas - don't use app store gui, use `mas`when possible
* `defaults` - read settings with something like `defaults read com.apple.AppleMultitouchTrackpad`

### Things you still have to do manually
// TODO: find bash solution to script these out.
* apps
* add dev apps to security, privacy "dev tools" category to avoid security policiy. 
 * run monolingual to save space on language packs and architectures
 * setup vscode sync
 * sign into 1Password, Chrome, Firefox, Spotify, rescueTime, DropBox, OneDrive, Google Drive, Steam, Battle.NET, Pulse, Todoist, Notion, Office Ap, GitKraken, Pocket, Dash, Discord, Signal
* finder sidebar
  * rm tags section
  * add 'OS X' aka local mac install drive to finder sidebar
  * adjust favorites
    * (home folder)
    * Projects
    * Recents
    * Downloads
    * Desktop
    * Documents
    * Applications
    * Utilities
    * cloud accounts...
* enable "hard drives display on desktop" option
* sync spotify playlists
* setup default browser `system preferences -> general`
* https://github.com/iamadamdev/bypass-paywalls-chrome.git git clone - chrome://extensions - load 
* Startup Aps
 * Horo timer
 * Rescue Time
 * BTT
 * Lightshot
 * Dash
 * Google Cloud
 * Dropbox
 * One Drive
 * NordVPN
 * Flux
 * Pulse SMS
 * RescueTime
 * Docker
 * 1440
 * Notion
 * CheatSheet
 * 1Password7
 * Pocket
 * Todist
 * Cal / COntacts

Highlight TODO:

* chrome/ff extensions
* vscode extensions
* vim extensions
* zsh extensions
* applications/shell scripts overview

### Regen Create Brewfile

```sh
brew bundle dump -f
cat Brewfile| pbcopy
```

### macos.sh

```zsh

## Initial Setup
# prereq - initializes xcode
sudo xcode-select --install

# install homebrew - package manager used for shell apps and `cask` for os x applications and services
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"

# install brewfile brew, cask, and mas packages, including zsh
brew bundle

# install oh my zsh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

# set zsh as default shell for user
chsh -s /bin/zsh


## Timezone
# set timezone
sudo systemsetup -settimezone "America/Chicago"

# get current zone
# sudo systemsetup -gettimezone

# get list of potential zones
# sudo systemsetup -listtimezones.


## Menu aka Mac Bar
# have a look at potential menu bar options
# ls /System/Library/CoreServices/Menu\ Extras/

# edit plist manually with Xcode
# open -a Xcode ~/Library/Preferences/com.apple.systemuiserver.plist


# fix menu bar - warning if system doesn't have one of these like AirPort or Bluetooth it will break
defaults write com.apple.systemuiserver menuExtras -array \
"/System/Library/CoreServices/Menu Extras/AirPort.menu" \
"/System/Library/CoreServices/Menu Extras/Bluetooth.menu" \
"/System/Library/CoreServices/Menu Extras/Clock.menu" \
"/System/Library/CoreServices/Menu Extras/Displays.menu" \
"/System/Library/CoreServices/Menu Extras/Volume.menu" \

# refresh ui
killall SystemUIServer

# change clock format
defaults write com.apple.menuextra.clock IsAnalog -bool false
defaults write com.apple.menuextra.clock DateFormat -string "EEE d MMM HH:mm:ss"

# refresh ui
killall SystemUIServer


## Security
# enable stealth mode to disable ping response ect..
sudo defaults write /Library/Preferences/com.apple.alf stealthenabled -int 1

# enable basic firewall
sudo defaults write /Library/Preferences/com.apple.alf globalstate -int 1


## Set Energy Saver Settings
# -a,ac,b,u = all, ac/adapter, battery, ups

# sets display sleep time, disksleap, sleep, enabling wake on ethernet and wake on modem ring on ac
sudo pmset -ac displaysleep 15 disksleep 30 sleep 45 womp 1 ring 1

# sets display sleep time, disksleap, sleep, enabling wake on ethernet and wake on modem ring on battery
sudo pmset -b displaysleep 2 disksleep 3 sleep 4 womp 0 ring 0

# sets the system to shutdown after x minutes, the ups is reporting <=y% battery or <=z minutes remaining
sudo pmset -u haltafter 2 haltlevel 25 haltremain 60

## Trackpad
# tap to click, double tap/click for right click
# 3 finger drag enabled
# 3 finger spread/ collapse for desktop and applications page
# 4 finger swipe between apps
defaults write com.apple.AppleMultitouchTrackpad ActualStrength -int 0
defaults write com.apple.AppleMultitouchTrackpad Clicking -int 1
defaults write com.apple.AppleMultitouchTrackpad FirstClickThreshold -int 0
defaults write com.apple.AppleMultitouchTrackpad SecondClickThreshold -int 0
defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerDrag -int 1
defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerHorizSwipeGesture -int 0
defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerTapGesture -int 0
defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerVertSwipeGesture -int 0

## Dock
# Remove all to initially reset dock
dockutil --remove all --allhomes

# add apps
dockutil --add '/System/Applications/System Preferences.app' --allhomes
dockutil --add '/Applications/iTerm.app' --allhomes
dockutil --add '/Applications/Visual Studio Code.app' --allhomes
dockutil --add '/Applications/Google Chrome.app' --allhomes
dockutil --add '/Applications/Firefox.app' --allhomes
dockutil --add '/Applications/Notion.app' --allhomes
dockutil --add '/Applications/Todoist.app' --allhomes
dockutil --add '/System/Applications/Calendar.app' --allhomes
dockutil --add '/System/Applications/Contacts.app' --allhomes
dockutil --add '/Applications/Pocket.app' --allhomes
dockutil --add '/Applications/Signal.app' --allhomes
dockutil --add '/Applications/Pulse SMS.app' --allhomes
dockutil --add '/Applications/Spotify.app' --allhomes

# add folders
dockutil --add '~/' --view grid --sort name
dockutil --add '/Applications' --view grid --display folder --allhomes --sort name
dockutil --add '/Applications/Utilities' --view grid --display folder --allhomes --sort name
dockutil --add '~/Downloads' --view grid --display folder --allhomes --sort dateadded


## configure git basics
git config --global diff.tool bc3
git config --global merge.tool bc3
git config --global mergetool.bc3.trustExitCode true

git config --global core.autocrlf input

git config --global user.name "ashtonian"
git config --global user.email "github@ashtonkinslow.com"

git config --global core.excludesfile ~/.gitignore
echo .DS_Store >> ~/.gitignore

## Setup Py Env
# for py
pip install ipython
```

#### Automation dreams and TODO

* downloads sync, org
* shell history persistence, search, sync
* setup startup apps
* figure out backup solution - encrypt, chunk, sync, consider time machine sync
* remote access, keyboard/mouse share
* find software to record screen(s) and audio
* desktop background + screen saver sync + setup per res
* .ssh backup/sync - security
* setup startup env for languages
  * node - nvm, npm, web
  * golang
  * docker, terraform
  * .net core
  * python
* Figure out maintenance scripts
  * update/clean sys files
  * update/clean search (spotlight + related)
  * fetch updates for cli (docker, git, gohome, npm, zsh, ohmyzsh, vim, + others)
* antivirus install + other hardening
* git/projects backup/auto sync
* more granular file changes for < x amount of changes ie solution for inbetween commits automagically
* antivirus + other
* code snippets solution
* regex tool solution
* multi screen/tiling improvement

## Windows Post Install Script

This is a bootstrap script for windows.

### Choco Install, Git And Debloat

```powershell
Set-ExecutionPolicy AllSigned
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))
choco feature enable -n allowGlobalConfirmation

# install git
choco install git

# make project dir
cd C:\
mkdir Projects
cd C:\Projects

## setup debloaters
# run initial debloater
git clone https://github.com/W4RH4WK/Debloat-Windows-10.git
cd ./Debloat-Windows-10/
Set-ExecutionPolicy Unrestricted -Scope CurrentUser
ls -Recurse *.ps*1 | Unblock-File
cd ./scripts
./block-telemetry.ps1
./disable-services.ps1
./fix-privacy-settings.ps1
./optimize-user-interface.ps1
./optimize-windows-update.ps1
./remove-default-apps.ps1
cd ../

# run smaller additional windows debloater
git clone https://github.com/Sycnex/Windows10Debloater.git
cd ./Windows10Debloater/
./Windows10SysPrepDebloater.ps1 -Debloat -Privacy
cd ../

## Disable UAC
Set-ItemProperty -Path REGISTRY::HKEY_LOCAL_MACHINE\Software\Microsoft\Windows\CurrentVersion\Policies\System -Name ConsentPromptBehaviorAdmin -Value 0

```


#### Standard Util

```powershell
choco install chocolatey-core.extension
choco install google-chrome-x64
choco install 1password
choco install f.lux
choco install windirstat
choco install javaruntime
choco install 7zip.install
choco install vlc
choco install paint.net
choco install atom
choco install sublimetext2
choco install winscp.install
choco install todoist
choco install notion
```

#### Display Driver

```powershell
choco install nvidia-display-driver
# Or
choco install
```


#### Standard Development

```powershell
choco install vscode
choco install docker
choco install docker-compose
choco install poshgit
choco install gitkraken
choco install git.install
choco install conemu
# choco install visualstudio2019community
# choco install resharper
# choco install ncrunch-vs2019
choco install beyondcompare
choco install babun
choco install cygwin
choco install wireshark
choco install fiddler
choco install nvm
choco install nugetpackageexplorer
choco install procexp
choco install curl
choco install awscli
choco install vim
choco install golang
choco install terraform
choco install python
choco install pip
choco install firacode
choco install font-awesome-font
choco install rescuetime
```
#### Cloud

```powershell
choco install googledrive
choco install icloud
choco install dropbox
```

#### Extended Util

```powershell
choco install nordvpn
choco install cpu-z
choco install deluge
choco install putty
choco install virtualclonedrive
choco install imgburn
choco install malwarebytes
choco install avastfreeantivirus
choco install chocolateygui
choco install office-tool

choco install adobereader
choco install rufus
choco install ccleaner
choco install flashplayerplugin
choco install flashplayeractivex

choco install kubernetes-helm
choco install vmwareworkstation

choco install goland
choco install jetbrainstoolbox
choco install resharper
choco install jetbrains-rider
```

#### Entertainment/Other

```powershell

choco install signal
choco install discord

choco install spotify
choco install toastify
choco install handbrake.install
choco install dolphin
choco install steam
choco install origin
choco install uplay
choco install battle.net
choco install goggalaxy
```

#### TODO

* settings sync between all apps
* shell sync, search, backup
* enable windows features for dev
* enable any networking protocols
* secuirty settings to lock down box
  * silent mode
  * fw on
  * no sharing script
  *
