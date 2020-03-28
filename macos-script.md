
TODO: 
* Install macos. 
* verify trim, mem size, apfs. 
* update macos and sign into apple + google accounts. 
* cleanup dock using dockutil - setting fixed apps, trashcan, dividers, Applications, Utilities, Home Folder, Downloads, set folder types
* cleanup finder - rm tags, add all drives including os x to locations, add clouds in one place, on left add favorites, apps, utilities, desktop, docs, home, videos, downloads, projects, ect..  
* adjust energy settings
* mackup restore

Notes: 
* package manager preference brew/cask -> mas - don't use app store gui, use `mas`

TODO: 
* downloads org
* downloads sync 
* shell history persistence, search, sync
* remote access, share keyboard/mouse 
* record screens and audio
* backup
* setup startup apps
* 

```zsh
# prereq
sudo xcode-select --install

# install homebrew 
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"

# install brewfile brew, cask, and mas packages, including zsh
brew bundle

# install oh my zsh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

# set zsh as default shell for user 
chsh -s /bin/zsh

# have a look at potential menu bar options 
# ls /System/Library/CoreServices/Menu\ Extras/ 

# edit plist manually with Xcode 
# open -a Xcode ~/Library/Preferences/com.apple.systemuiserver.plist

# read settings with something like defaults read com.apple.AppleMultitouchTrackpad

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

# set timezone 
sudo systemsetup -settimezone "America/Chicago"

# get current zone 
# sudo systemsetup -gettimezone

# get list of potential zones 
# sudo systemsetup -listtimezones.

# connect trackpad physcially and setup
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

# for py
pip install ipython
```
