# $Home

This is my cross platform `home` folder - which contains post install scripts for MacOS (OS X) and Windows 10. As well as my home lab server and network appliance install scripts, configs and docker files. 

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
* setup default browser `system preferences -> general`

Highlight TODO:

* chrome/ff extensions
* vscode extensions
* vim extensions
* zsh extensions
* applications/shell scripts overview


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

### Choco
```
choco feature enable -n allowGlobalConfirmation
```

###### Standard Development: 
```
choco install poshgit
choco install git.install
choco install conemu
choco install hg
choco install posh-hg
choco install sourcetree
# choco install visualstudio2015community
# choco install resharper
# choco install ncrunch-vs2015
choco install beyondcompare
choco install fiddler
```

###### Extended Development: 
```
choco install babun
choco install conemu
choco install wireshark
choco install nodejs.install
choco install nugetpackageexplorer
choco install procexp
choco install curl
```

###### Standard Util:
```
choco install google-chrome-x64
choco install f.lux
choco install windirstat
choco install javaruntime
choco install 7zip.install
choco install vlc
choco install paint.net
choco install googledrive
choco install atom
choco install filezilla
choco install winscp.install
```

###### Extended Util:
```
choco install dropbox
choco install cpu-z
choco install deluge
choco install putty
choco install virtualclonedrive
choco install imgburn
choco install malwarebytes
choco install avastfreeantivirus
choco install chocolateygui
choco install virtualbox
choco install adobereader
choco install ccleaner
choco install flashplayerplugin
choco install flashplayeractivex
```

###### Entertainment/Other:
```
choco install evernote
choco install spotify
choco install steam
choco install handbrake.install
```

### OneGet (Choco repo is currently broken) 
###### OnGet Resources: 
- https://github.com/PowerShell/PackageManagementProviderResource
- https://github.com/OneGet/oneget/wiki/cmdlets
- https://technet.microsoft.com/en-us/library/dn890703.aspx
- https://chocolatey.org/

###### Starter Code: 
```
Get-PackageProvider –Name Chocolatey -ForceBootstrap
Set-PackageSource -Name chocolatey -Trusted 

Install-Package f.lux
Install-Package google-chrome-x64
```
