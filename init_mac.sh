### Intended for Catalina to be ran in this repo with bundle file.  

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


## TODO: MERGE 

# OS X tweaks
##############################################################################
# BT Audio Quality                                                           #
##############################################################################

defaults write com.apple.BluetoothAudioAgent "Apple Bitpool Max (editable)" 80 
defaults write com.apple.BluetoothAudioAgent "Apple Bitpool Min (editable)" 80 
defaults write com.apple.BluetoothAudioAgent "Apple Initial Bitpool (editable)" 80 
defaults write com.apple.BluetoothAudioAgent "Apple Initial Bitpool Min (editable)" 80 
defaults write com.apple.BluetoothAudioAgent "Negotiated Bitpool" 80 
defaults write com.apple.BluetoothAudioAgent "Negotiated Bitpool Max" 80 
defaults write com.apple.BluetoothAudioAgent "Negotiated Bitpool Min" 80
sudo killall coreaudiod

##############################################################################
# Clock                                                                   #
##############################################################################
# Set Time format to 24h + month + day of week 
defaults write com.apple.menuextra.clock DateFormat -string 'EEE MMM d  H:mm:ss'

# Set timezone
sudo systemsetup -settimezone America/Chicago

# Disable sleep
sudo systemsetup  -setcomputersleep never

##############################################################################
# Security                                                                   #
##############################################################################
# Based on:
# https://github.com/drduh/macOS-Security-and-Privacy-Guide
# https://benchmarks.cisecurity.org/tools2/osx/CIS_Apple_OSX_10.12_Benchmark_v1.0.0.pdf

# Enable firewall. Possible values:
#   0 = off
#   1 = on for specific sevices
#   2 = on for essential services
sudo defaults write /Library/Preferences/com.apple.alf globalstate -int 1

# Enable firewall stealth mode (no response to ICMP / ping requests)
# Source: https://support.apple.com/kb/PH18642
#sudo defaults write /Library/Preferences/com.apple.alf stealthenabled -int 1
sudo defaults write /Library/Preferences/com.apple.alf stealthenabled -int 1

# Disable remote apple events
sudo systemsetup -setremoteappleevents off

# Disable remote login
sudo systemsetup -setremotelogin off

# Disable wake-on modem
sudo systemsetup -setwakeonmodem off

# Disable wake-on LAN
sudo systemsetup -setwakeonnetworkaccess off

# Disable the “Are you sure you want to open this application?” dialog
defaults write com.apple.LaunchServices LSQuarantine -bool false

###############################################################################
# SSD-specific tweaks                                                         #
###############################################################################

# "Disable local Time Machine snapshots"
sudo tmutil disablelocal

# "Remove the sleep image file to save disk space"
sudo rm -rf /Private/var/vm/sleepimage
# "Create a zero-byte file instead"
sudo touch /Private/var/vm/sleepimage
# "…and make sure it can’t be rewritten"
sudo chflags uchg /Private/var/vm/sleepimage

# running "Show icons for hard drives, servers, and removable media on the desktop"
defaults write com.apple.finder ShowExternalHardDrivesOnDesktop -bool true
defaults write com.apple.finder ShowHardDrivesOnDesktop -bool true
defaults write com.apple.finder ShowMountedServersOnDesktop -bool true
defaults write com.apple.finder ShowRemovableMediaOnDesktop -bool true

# running "Wipe all (default) app icons from the Dock"
# # This is only really useful when setting up a new Mac, or if you don’t use
# # the Dock to launch apps.
defaults write com.apple.dock persistent-apps -array ""

# running "allow 'locate' command"
sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.locate.plist > /dev/null 2>&1

# running "Set standby delay to 24 hours (default is 1 hour)"
sudo pmset -a standbydelay 86400

# running "Disable the sound effects on boot"
sudo nvram SystemAudioVolume=" "

defaults write com.apple.systemuiserver menuExtras -array \
  "/System/Library/CoreServices/Menu Extras/Bluetooth.menu" \
  "/System/Library/CoreServices/Menu Extras/Battery.menu" \
  "/System/Library/CoreServices/Menu Extras/Clock.menu"
ok

# running "Set highlight color to green"
defaults write NSGlobalDomain AppleHighlightColor -string "0.764700 0.976500 0.568600"

# running "Set sidebar icon size to medium"
defaults write NSGlobalDomain NSTableViewDefaultSizeMode -int 2

# running "Always show scrollbars"
defaults write NSGlobalDomain AppleShowScrollBars -string "Always"
# Possible values: `WhenScrolling`, `Automatic` and `Always`


# running "Expand save panel by default"
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode -bool true
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode2 -bool true

# running "Expand print panel by default"
defaults write NSGlobalDomain PMPrintingExpandedStateForPrint -bool true
defaults write NSGlobalDomain PMPrintingExpandedStateForPrint2 -bool true

# running "Save to disk (not to iCloud) by default"
defaults write NSGlobalDomain NSDocumentSaveNewDocumentsToCloud -bool false

# running "Automatically quit printer app once the print jobs complete"
defaults write com.apple.print.PrintingPrefs "Quit When Finished" -bool true

# running "Disable the “Are you sure you want to open this application?” dialog"
defaults write com.apple.LaunchServices LSQuarantine -bool false

# running "Remove duplicates in the “Open With” menu (also see 'lscleanup' alias)"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -kill -r -domain local -domain system -domain user

# running "Display ASCII control characters using caret notation in standard text views"
# Try e.g. `cd /tmp; unidecode "\x{0000}" > cc.txt; open -e cc.txt`
defaults write NSGlobalDomain NSTextShowsControlCharacters -bool true

#running "Disable automatic termination of inactive apps"
defaults write NSGlobalDomain NSDisableAutomaticTermination -bool true

# running "Disable the crash reporter"
defaults write com.apple.CrashReporter DialogType -string "none"

# running "Reveal IP, hostname, OS, etc. when clicking clock in login window"
sudo defaults write /Library/Preferences/com.apple.loginwindow AdminHostInfo HostName

# running "Disable smart quotes as they’re annoying when typing code"
defaults write NSGlobalDomain NSAutomaticQuoteSubstitutionEnabled -bool false

# running "Disable smart dashes as they’re annoying when typing code"
defaults write NSGlobalDomain NSAutomaticDashSubstitutionEnabled -bool false


###############################################################################
# bot "Trackpad, mouse, keyboard, Bluetooth accessories, and input"
###############################################################################
# Enable 4 finger drag
defaults write NSGlobalDomain AppleEnableSwipeNavigateWithScrolls -bool true
defaults -currentHost write NSGlobalDomain com.apple.trackpad.fourFingerHorizSwipeGesture -int 1
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadFourFingerHorizSwipeGesture -int 1

#Fix Scroll
defaults write NSGlobalDomain com.apple.swipescrolldirection -bool false 

# 3 Finger drag for trackpad, not sure if its working 
defaults -currentHost write NSGlobalDomain com.apple.trackpad.threeFingerSwipeGesture -int 1

# Tap Clicking For Trackpad 
defaults write com.apple.AppleMultitouchTrackpad Clicking -bool true
sudo defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Clicking -bool true

# Enable "tap-and-a-half" to drag.
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Dragging -int 1
defaults write com.apple.AppleMultitouchTrackpad Dragging -int 1

# Enable 3-finger drag. (Moving with 3 fingers in any window "chrome" moves the window.)
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadThreeFingerDrag -bool true
defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerDrag -bool true

# Tap Clicking For Magic Mouse 
sudo defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
sudo defaults write NSGlobalDomain com.apple.mouse.tapBehavior -int 1

# Tap And drag clicking notice 2 v 1, overwrite
defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 2
defaults write NSGlobalDomain com.apple.mouse.tapBehavior -int 2

# running "Trackpad: enable tap to click for this user and for the login screen"
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Clicking -bool true
defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
defaults write NSGlobalDomain com.apple.mouse.tapBehavior -int 1

# running "Disable 'natural' (Lion-style) scrolling"
defaults write NSGlobalDomain com.apple.swipescrolldirection -bool false

# running "Increase sound quality for Bluetooth headphones/headsets"
defaults write com.apple.BluetoothAudioAgent "Apple Bitpool Min (editable)" -int 40

# running "Enable full keyboard access for all controls (e.g. enable Tab in modal dialogs)"
defaults write NSGlobalDomain AppleKeyboardUIMode -int 3

# running "Use scroll gesture with the Ctrl (^) modifier key to zoom"
defaults write com.apple.universalaccess closeViewScrollWheelToggle -bool true
defaults write com.apple.universalaccess HIDScrollZoomModifierMask -int 262144

#running "Follow the keyboard focus while zoomed in"
defaults write com.apple.universalaccess closeViewZoomFollowsFocus -bool true

# running "Set language and text formats (english/US)"
defaults write NSGlobalDomain AppleLanguages -array "en"
defaults write NSGlobalDomain AppleLocale -string "en_US@currency=USD"
defaults write NSGlobalDomain AppleMeasurementUnits -string "Centimeters"
defaults write NSGlobalDomain AppleMetricUnits -bool true

# running "Disable auto-correct"
# defaults write NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false

###############################################################################
# bot "Configuring the Screen"
###############################################################################

# running "Require password immediately after sleep or screen saver begins"
defaults write com.apple.screensaver askForPassword -int 1
defaults write com.apple.screensaver askForPasswordDelay -int 0

# Srunning "Save screenshots to the desktop"
defaults write com.apple.screencapture location -string "${HOME}/Desktop"

# running "Save screenshots in PNG format (other options: BMP, GIF, JPG, PDF, TIFF)"
defaults write com.apple.screencapture type -string "png"

###############################################################################
# bot "Finder Configs"
###############################################################################
# running "Disable window animations and Get Info animations"
defaults write com.apple.finder DisableAllAnimations -bool true

# running "Set Desktop as the default location for new Finder windows"
# For other paths, use 'PfLo' and 'file:///full/path/here/'
defaults write com.apple.finder NewWindowTarget -string "PfDe"
defaults write com.apple.finder NewWindowTargetPath -string "file://${HOME}/Desktop/"

# running "Show hidden files by default"
defaults write com.apple.finder AppleShowAllFiles -bool true

# running "Show all filename extensions"
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# running "Show status bar"
defaults write com.apple.finder ShowStatusBar -bool true

# running "Show path bar"
defaults write com.apple.finder ShowPathbar -bool true

# running "Allow text selection in Quick Look"
defaults write com.apple.finder QLEnableTextSelection -bool true

# running "Display full POSIX path as Finder window title"
defaults write com.apple.finder _FXShowPosixPathInTitle -bool true

# running "When performing a search, search the current folder by default"
defaults write com.apple.finder FXDefaultSearchScope -string "SCcf"

# running "Disable the warning when changing a file extension"
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false

# running "Enable spring loading for directories"
defaults write NSGlobalDomain com.apple.springing.enabled -bool true

# running "Remove the spring loading delay for directories"
defaults write NSGlobalDomain com.apple.springing.delay -float 0

# running "Avoid creating .DS_Store files on network volumes"
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true

# running "Automatically open a new Finder window when a volume is mounted"
defaults write com.apple.frameworks.diskimages auto-open-ro-root -bool true
defaults write com.apple.frameworks.diskimages auto-open-rw-root -bool true
defaults write com.apple.finder OpenWindowForNewRemovableDisk -bool true

# running "Use list view in all Finder windows by default"
# Four-letter codes for the other view modes: `icnv`, `clmv`, `Flwv`
defaults write com.apple.finder FXPreferredViewStyle -string "Nlsv"

# running "Disable the warning before emptying the Trash"
defaults write com.apple.finder WarnOnEmptyTrash -bool false

# running "Empty Trash securely by default"
defaults write com.apple.finder EmptyTrashSecurely -bool true

# running "Expand the following File Info panes: “General”, “Open with”, and “Sharing & Permissions”"
defaults write com.apple.finder FXInfoPanesExpanded -dict \
  General -bool true \
  OpenWith -bool true \
  Privileges -bool true

###############################################################################
# bot "Dock & Dashboard"
###############################################################################
# running "Speed up Mission Control animations"
defaults write com.apple.dock expose-animation-duration -float 0.1

# running "Don’t group windows by application in Mission Control"
# (i.e. use the old Exposé behavior instead)
defaults write com.apple.dock expose-group-by-app -bool false

# running "Disable Dashboard"
defaults write com.apple.dashboard mcx-disabled -bool true

# running "Don’t show Dashboard as a Space"
defaults write com.apple.dock dashboard-in-overlay -bool true

# running "Don’t automatically rearrange Spaces based on most recent use"
defaults write com.apple.dock mru-spaces -bool false

#running "Reset Launchpad, but keep the desktop wallpaper intact"
find "${HOME}/Library/Application Support/Dock" -name "*-*.db" -maxdepth 1 -delete

###############################################################################
# bot "Activity Monitor"
###############################################################################

# running "Show the main window when launching Activity Monitor"
defaults write com.apple.ActivityMonitor OpenMainWindow -bool true

# running "Visualize CPU usage in the Activity Monitor Dock icon"
defaults write com.apple.ActivityMonitor IconType -int 5

# running "Show all processes in Activity Monitor"
defaults write com.apple.ActivityMonitor ShowCategory -int 0

# running "Sort Activity Monitor results by CPU usage"
defaults write com.apple.ActivityMonitor SortColumn -string "CPUUsage"
defaults write com.apple.ActivityMonitor SortDirection -int 0

###############################################################################
# bot "Address Book, Dashboard, iCal, TextEdit, and Disk Utility, Iterm"
###############################################################################
# running "Use plain text mode for new TextEdit documents"
defaults write com.apple.TextEdit RichText -int 0
# running "Open and save files as UTF-8 in TextEdit"
defaults write com.apple.TextEdit PlainTextEncoding -int 4
defaults write com.apple.TextEdit PlainTextEncodingForWrite -int 4

# running "Enable the debug menu in Disk Utility"
defaults write com.apple.DiskUtility DUDebugMenuEnabled -bool true
defaults write com.apple.DiskUtility advanced-image-options -bool true
 
