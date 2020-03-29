
TODO: 
* Install macos. 
* verify trim, mem size, apfs. 
* update macos and sign into apple + google accounts. 
* cleanup dock using dockutil - setting fixed apps, trashcan, dividers, Applications, Utilities, Home Folder, Downloads, set folder types
* cleanup finder - rm tags, add all drives including os x to locations, add clouds in one place, on left add favorites, apps, utilities, desktop, docs, home, videos, downloads, projects, ect..  
* mackup restore

Notes: 
* package manager preference brew/cask -> mas - don't use app store gui, use `mas`
* # read settings with something like defaults read com.apple.AppleMultitouchTrackpad


TODO: 
* downloads org
* downloads sync
* shell history persistence, search, sync
* remote access, share keyboard/mouse
* record screens and audio
* backup
* setup startup apps
* set default browser
* desktop/screen saver sync/setup
* chrome/ff extensions
* vscode extensions
* vim extensions
* zsh extensions
* applications/shell scripts overview
* .ssh backup/sync
* time machine + backup solution
* setup golang,.net,frontend + backend .js, python
* document core accounts: 1password, chrome, apple, firefox, dropbox, github 
* maintenance schedules - updates, cache clear/clean, optimze spoltlight, fetch git sources, fetch docker sources
* git/projects backup/auto sync
* more granular file changes for < x amount of changes ie solution for inbetween commits automagically
* antivirus + other


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

## Setup Trackpad 
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

## Setup Py Env
# for py
pip install ipython
```
