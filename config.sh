#!/usr/bin/env bash

#######################################################################################################################################
# macOS 10.15+ (Catalina) Install script
# originally sourced from https://github.com/mathiasbynens/dotfiles/commit/ea68bda80a455e149d29156071d4c8472f6b93cb last-sync 21-1-24
# bot code inspired from https://github.com/atomantic/dotfiles/commit/5ed89376558b23f9ba0a4c361586ab888f6e29a2 last-sync 21-1-24
#######################################################################################################################################

# include library helpers for colorized echo and require_brew
source ./lib_sh/echos.sh
source ./lib_sh/requirers.sh

bot "Hi! I'm going to install tooling and tweak your system settings."

#######################################################################################################################################
bot "Configuring brew taps, casks & apps + mas apps + zsh config."
#######################################################################################################################################

# TODO: exit if no brew
# ```sh
# brew bundle dump -f
# cat Brewfile| pbcopy
# ```

# running "Turn off brew analytics."
# brew analytics off
# ok

# running "brew doctor & update."
# brew doctor
# brew update
# ok

# running "Install brew bundle."
# brew bundle
# ok

# running "Cleanup homebrew."
# brew cleanup --force > /dev/null 2>&1
# rm -f -r /Library/Caches/Homebrew/* > /dev/null 2>&1
# ok

#######################################################################################################################################
bot "Configuring mackup."
#######################################################################################################################################

## Mackup uses
## TODO: move to end? or elsehwere, maybe ask user? how do submodules work with this
# // TODO: // alias .macup.cfg to home dir
# TODO: mackup restore


###############################################################################
# Login Window                                                                #
###############################################################################

running "Reveal system info (IP address, hostname, OS version, etc.) when clicking the clock in the login screen"
sudo defaults write /Library/Preferences/com.apple.loginwindow AdminHostInfo HostName
ok

running "Show language menu in the top right corner of the boot screen"
sudo defaults write /Library/Preferences/com.apple.loginwindow showInputMenu -bool true
ok

# running "Disable guest login"
# sudo defaults write /Library/Preferences/com.apple.loginwindow GuestEnabled -bool false
# ok

# running "Add a message to the login screen"
# sudo defaults write /Library/Preferences/com.apple.loginwindow LoginwindowText "Beware\! You are logging into Vijay's laptop\!"
# ok

# running "Change login screen background"
# sudo defaults write /Library/Preferences/com.apple.loginwindow DesktopPicture "/Library/Desktop Pictures/Aqua Blue.jpg"
# ok

# running "Show Shutdown Button on Login Window"
# defaults write com.apple.loginwindow ShutDownDisabled -bool false
# ok

# running "Remove Restart Button From Login Window"
# defaults write com.apple.loginwindow RestartDisabled -bool true
# ok

running "Disable Login for Hidden User '>Console'"
defaults write com.apple.loginwindow DisableConsoleAccess -bool true
ok

#######################################################################################################################################
# General UI/UX                                                               #
#######################################################################################################################################

# Set computer name (as done via System Preferences → Sharing)
#sudo scutil --set ComputerName "TODO:0x6D746873"
#sudo scutil --set HostName "TODO:0x6D746873"
#sudo scutil --set LocalHostName "TODO:0x6D746873"
#sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.smb.server NetBIOSName -string "TODO:0x6D746873"

running "Disable the sound effects on boot."
sudo nvram SystemAudioVolume=" "
ok

running "Disable transparency in the menu bar and elsewhere on Yosemite."
defaults write com.apple.universalaccess reduceTransparency -bool true
ok

running "Set highlight color to green."
defaults write NSGlobalDomain AppleHighlightColor -string "0.764700 0.976500 0.568600"
ok

running "Set sidebar icon size to medium."
defaults write NSGlobalDomain NSTableViewDefaultSizeMode -int 2
ok

# Possible values: `WhenScrolling`, `Automatic` and `Always`
running "Always show scrollbars."
defaults write NSGlobalDomain AppleShowScrollBars -string "Always"
ok

running "Disable the over-the-top focus ring animation."
defaults write NSGlobalDomain NSUseAnimatedFocusRing -bool false
ok

running "Adjust toolbar title rollover delay."
defaults write NSGlobalDomain NSToolbarTitleViewRolloverDelay -float 0
ok

# running "Disable smooth scrolling (Uncomment if you’re on an older Mac that messes up the animation)."
# defaults write NSGlobalDomain NSScrollAnimationEnabled -bool false
# ok

running "Increase window resize speed for Cocoa applications."
defaults write NSGlobalDomain NSWindowResizeTime -float 0.001
ok

running "Expand save panel by default."
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode -bool true
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode2 -bool true
ok

running "Expand print panel by default."
defaults write NSGlobalDomain PMPrintingExpandedStateForPrint -bool true
defaults write NSGlobalDomain PMPrintingExpandedStateForPrint2 -bool true
ok

running "Save to disk (not to iCloud) by default."
defaults write NSGlobalDomain NSDocumentSaveNewDocumentsToCloud -bool false
ok

running "Automatically quit printer app once the print jobs complete."
defaults write com.apple.print.PrintingPrefs "Quit When Finished" -bool true
ok

running "Disable the “Are you sure you want to open this application?” dialog."
defaults write com.apple.LaunchServices LSQuarantine -bool false
ok

running "Remove duplicates in the “Open With” menu (also see `lscleanup` alias)."
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -kill -r -domain local -domain system -domain user
ok

running "Display ASCII control characters using caret notation in standard text views."
# Try e.g. `cd /tmp; unidecode "\x{0000}" > cc.txt; open -e cc.txt`
defaults write NSGlobalDomain NSTextShowsControlCharacters -bool true
ok

running "Disable Resume system-wide (saving window state)."
defaults write com.apple.systempreferences NSQuitAlwaysKeepsWindows -bool false
defaults write -g NSQuitAlwaysKeepsWindows -bool false
ok


# This works, although the checkbox will still appear to be checked.
running "Disable the 'reopen windows when logging back in' option"
defaults write com.apple.loginwindow TALLogoutSavesState -bool false
defaults write com.apple.loginwindow LoginwindowLaunchesRelaunchApps -bool false
ok


running "Disable Windows which were open prior to logging from reopening after logging in"
defaults write com.apple.finder RestoreWindowState -bool false
ok

running "Disable automatic termination of inactive apps."
defaults write NSGlobalDomain NSDisableAutomaticTermination -bool true
ok

# running "Disable the crash reporter."
# defaults write com.apple.CrashReporter DialogType -string "none"
# ok

running "Set Help Viewer windows to non-floating mode."
defaults write com.apple.helpviewer DevMode -bool true
ok

# running "Fix for the ancient UTF-8 bug in QuickLook (https://mths.be/bbo)."
# Commented out, as this is known to cause problems in various Adobe apps :(
# See https://github.com/mathiasbynens/dotfiles/issues/237
#echo "0x08000100:0" > ~/.CFUserTextEncoding
# ok

# running "Disable Notification Center and remove the menu bar icon."
# launchctl unload -w /System/Library/LaunchAgents/com.apple.notificationcenterui.plist 2> /dev/null
# ok

running "Disable automatic capitalization as it’s annoying when typing code."
defaults write NSGlobalDomain NSAutomaticCapitalizationEnabled -bool false
ok

running "Disable smart dashes as they’re annoying when typing code."
defaults write NSGlobalDomain NSAutomaticDashSubstitutionEnabled -bool false
ok

running "Disable automatic period substitution as it’s annoying when typing code."
defaults write NSGlobalDomain NSAutomaticPeriodSubstitutionEnabled -bool false
ok

running "Disable smart quotes as they’re annoying when typing code."
defaults write NSGlobalDomain NSAutomaticQuoteSubstitutionEnabled -bool false
ok

# running "Set a custom wallpaper image. `DefaultDesktop.jpg` is already a symlink, and all wallpapers are in `/Library/Desktop Pictures/`. The default is `Wave.jpg`."
# rm -rf ~/Library/Application Support/Dock/desktoppicture.db
# sudo rm -rf /System/Library/CoreServices/DefaultDesktop.jpg
# sudo ln -s /path/to/your/image /System/Library/CoreServices/DefaultDesktop.jpg
# ok

# running "always boot in verbose mode (not MacOS GUI mode)."
# sudo nvram boot-args="-v"
# ok

running "allow 'locate' command."
sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.locate.plist > /dev/null 2>&1
ok

# running "Menu bar: disable transparency."
# defaults write NSGlobalDomain AppleEnableMenuBarTransparency -bool false
# ok

running "Enable 64-bit Kernel"
defaults write /Library/Preferences/SystemConfiguration/com.apple.Boot.plist "Kernel Flags" -string ""
ok 

# running "Set the some english acronyms/short forms for ease of typing"# defaults write -g NSUserDictionaryReplacementItems -array \
#     '{ on = 1; replace = cyl; with = "Cya later!"; }' \
#     '{ on = 1; replace = ttyl; with = "Talk to you later!"; }' \
#     '{ on = 1; replace = omw; with = "On my way!"; }' \
#     '{ on = 1; replace = omg; with = "Oh my God!"; }'
# ok

running "When switching applications, switch to respective space"
defaults write -g AppleSpacesSwitchOnActivate -bool true
ok

#######################################################################################################################################
bot "Configuring Trackpad, mouse, keyboard, Bluetooth accessories, and input."
#######################################################################################################################################

running "Trackpad: enable tap to click for this user and for the login screen."
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Clicking -bool true
defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
defaults write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
ok

# running "Trackpad: map bottom right corner to right-click."
# # defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadCornerSecondaryClick -int 2
# defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadRightClick -bool true
# # defaults -currentHost write NSGlobalDomain com.apple.trackpad.trackpadCornerClickBehavior -int 1
# defaults -currentHost write NSGlobalDomain com.apple.trackpad.enableSecondaryClick -bool true
# ok

# running "Disable 'natural' (Lion-style) scrolling."
# defaults write NSGlobalDomain com.apple.swipescrolldirection -bool false
# ok

# running "Increase sound quality for Bluetooth headphones/headsets."
# defaults write com.apple.BluetoothAudioAgent "Apple Bitpool Min (editable)" -int 40
# ok

running "Enable full keyboard access for all controls (e.g. enable Tab in modal dialogs)."
defaults write NSGlobalDomain AppleKeyboardUIMode -int 3
ok

running "Use scroll gesture with the Ctrl (^) modifier key to zoom."
defaults write com.apple.universalaccess closeViewScrollWheelToggle -bool true
defaults write com.apple.universalaccess HIDScrollZoomModifierMask -int 262144
ok

running "Follow the keyboard focus while zoomed in."
defaults write com.apple.universalaccess closeViewZoomFollowsFocus -bool true
ok

running "Disable press-and-hold for keys in favor of key repeat."
defaults write NSGlobalDomain ApplePressAndHoldEnabled -bool false
ok

running "Set a blazingly fast keyboard repeat rate."
defaults write NSGlobalDomain KeyRepeat -int 6
defaults write NSGlobalDomain InitialKeyRepeat -int 15
ok

running "Set language and text formats (english/US)."
defaults write NSGlobalDomain AppleLanguages -array "en"
defaults write NSGlobalDomain AppleLocale -string "en_US@currency=USD"
defaults write NSGlobalDomain AppleMeasurementUnits -string "Centimeters"
defaults write NSGlobalDomain AppleMetricUnits -bool true
ok

# running "Disable auto-correct."
# defaults write NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false
# ok

// TODO:
defaults write -g CheckSpellingWhileTyping -bool true

### get current zone
# sudo systemsetup -gettimezone

### get list of potential zones
# sudo systemsetup -listtimezones.

running "Set Time format to 24h + month + day of week."
defaults write com.apple.menuextra.clock DateFormat -string "EEE d MMM HH:mm:ss"
ok

running "Set timezone."
sudo systemsetup -settimezone America/Chicago
ok

running "Refresh ui."
killall SystemUIServer
ok

running  "Enable trackpad tap-and-a-half drag."
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Dragging -int 1
defaults write com.apple.AppleMultitouchTrackpad Dragging -int 1
ok

running "Enable trackpad Tap to drag."
defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 2
defaults write NSGlobalDomain com.apple.mouse.tapBehavior -int 2
# ok

# TODO: disable Moving with 3 fingers in any window "chrome" moves the window.
running  "Enable trackpad 3-finger drag."
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadThreeFingerDrag -bool true
defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerDrag -bool true
ok

running "Enable Drag lock."
defaults write com.apple.AppleMultitouchTrackpad DragLock -bool true
ok

running "Enable trackpad right click."
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadRightClick -bool true
defaults -currentHost write NSGlobalDomain com.apple.trackpad.enableSecondaryClick -bool true
defaults write com.apple.AppleMultitouchTrackpad TrackpadRightClick -bool true
ok

running "Enable swipe between pages."
defaults write NSGlobalDomain AppleEnableSwipeNavigateWithScrolls -bool true
ok

# running "Enable trackpad mission control swipe up 3 finger."
# defaults -currentHost write NSGlobalDomain com.apple.trackpad.threeFingerVertSwipeGesture -int 2
# defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerVertSwipeGesture -int 2
# defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadThreeFingerVertSwipeGesture -int 2
# ok

running "Enable trackpad mission control swipe up 4 finger."
defaults -currentHost write NSGlobalDomain com.apple.trackpad.fourFingerVertSwipeGesture -int 2
defaults write com.apple.AppleMultitouchTrackpad TrackpadFourFingerVertSwipeGesture -int 2
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadFourFingerVertSwipeGesture -int 2
ok

# running "Enable trackpad swipe between apps 3 finger."
# defaults -currentHost write NSGlobalDomain com.apple.trackpad.threeFingerHorizSwipeGesture -int 2
# defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerHorizSwipeGesture -int 2
# defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadThreeFingerHorizSwipeGesture -int 2
# ok

running "Enable trackpad swipe between apps 4 finger."
defaults -currentHost write NSGlobalDomain com.apple.trackpad.fourFingerHorizSwipeGesture -int 2
defaults write com.apple.AppleMultitouchTrackpad TrackpadFourFingerHorizSwipeGesture -int 2
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadFourFingerHorizSwipeGesture -int 2
ok
# MacBook Trackpad (built-in)
# TODO: when to use com.apple.trackpad vs com.apple.driver.applebluetoothmultitouch.trackpad
# TODO: defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerTapGesture -int 0

# TODO: update apple mouse settings for laptop
# com.apple.AppleMultitouchMouse.plist
# com.apple.driver.AppleBluetoothMultitouch.mouse.plist
# com.apple.driver.AppleHIDMouse.plist

running "Set better bluetooth audio settings."
defaults write com.apple.BluetoothAudioAgent "Apple Bitpool Max (editable)" 80
defaults write com.apple.BluetoothAudioAgent "Apple Bitpool Min (editable)" 80
defaults write com.apple.BluetoothAudioAgent "Apple Initial Bitpool (editable)" 80
defaults write com.apple.BluetoothAudioAgent "Apple Initial Bitpool Min (editable)" 80
defaults write com.apple.BluetoothAudioAgent "Negotiated Bitpool" 80
defaults write com.apple.BluetoothAudioAgent "Negotiated Bitpool Max" 80
defaults write com.apple.BluetoothAudioAgent "Negotiated Bitpool Min" 80
ok

running "Reseting audio service."
sudo killall coreaudiod
ok

#######################################################################################################################################
bot "Configuring Battery & Power."
#######################################################################################################################################

## Set Energy Saver Settings
# -a,ac,b,u = all, ac/adapter, battery, ups
# displaysleep, disksleep, sleep
# womp, ring, powernap, proximitywake, autorestart, lidwake, acwake = 0/1

running "Enable lid wakeup."
sudo pmset -a lidwake 1
ok

running "Restart automatically on power loss."
sudo pmset -a autorestart 1
ok

running "Restart automatically if the computer freezes."
sudo systemsetup -setrestartfreeze on
ok

running "Sleep the display after 5 minutes."
sudo pmset -a displaysleep 5
ok

running "Sleep the display after 5 minutes on battery."
sudo pmset -b displaysleep 5
ok

# running "Disable machine sleep while charging."
# sudo pmset -c sleep 0
# ok

running "Set machine sleep to 15 minutes."
sudo pmset -a sleep 15
ok

running "Set machine sleep to 5 minutes on battery."
sudo pmset -b sleep 5
ok

# running "Set standby delay to 24 hours (default is 1 hour)."
# sudo pmset -a standbydelay 86400
# ok

# running "Never go into computer sleep mode."
# sudo systemsetup -setcomputersleep Off > /dev/null
# ok

# Hibernation mode
# 0: Disable hibernation (speeds up entering sleep mode)
# 3: Copy RAM to disk so the system state can still be restored in case of a
#    power failure.
running "Disable hibernation."
sudo pmset -a hibernatemode 0
ok

# running "Remove the sleep image file to save disk space"
# sudo rm /private/var/vm/sleepimage
# ok

# running "Create a zero-byte file instead and make sure it can’t be rewritten"
# sudo touch /private/var/vm/sleepimage
# sudo chflags uchg /private/var/vm/sleepimage
# ok

running "Sleep the disk after 30 minutes."
sudo pmset -a disksleep 15
ok


#######################################################################################################################################
bot "Configuring the Screen."
#######################################################################################################################################

# running "Require password immediately after sleep or screen saver begins."
# defaults write com.apple.screensaver askForPassword -int 1
# defaults write com.apple.screensaver askForPasswordDelay -int 0
# ok

running "Save screenshots to the desktop."
# defaults write com.apple.screencapture location -string "${HOME}/Desktop"
ok

running "Save screenshots in PNG format (other options: BMP, GIF, JPG, PDF, TIFF)."
defaults write com.apple.screencapture type -string "png"
ok

running "Disable shadow in screenshots."
defaults write com.apple.screencapture disable-shadow -bool true
ok

# running "Enable subpixel font rendering on non-Apple LCDs."
# Reference: https://github.com/kevinSuttle/macOS-Defaults/issues/17#issuecomment-266633501
# defaults write NSGlobalDomain AppleFontSmoothing -int 2
# ok

running "Enable HiDPI display modes (requires restart)."
# sudo defaults write /Library/Preferences/com.apple.windowserver DisplayResolutionEnabled -bool true
ok

#######################################################################################################################################
bot "Configuring Finder."
#######################################################################################################################################

running "Finder: allow quitting via ⌘ + Q; doing so will also hide desktop icons."
defaults write com.apple.finder QuitMenuItem -bool true
ok

running "Finder: disable window animations and Get Info animations."
defaults write com.apple.finder DisableAllAnimations -bool true
ok

# For other paths, use `PfLo` and `file:///full/path/here/`
running "Set Desktop as the default location for new Finder windows."
defaults write com.apple.finder NewWindowTarget -string "PfDe"
defaults write com.apple.finder NewWindowTargetPath -string "file://${HOME}/Desktop/"
ok

running "Show icons for hard drives, servers, and removable media on the desktop"
defaults write com.apple.finder ShowExternalHardDrivesOnDesktop -bool true
defaults write com.apple.finder ShowHardDrivesOnDesktop -bool true
defaults write com.apple.finder ShowMountedServersOnDesktop -bool true
defaults write com.apple.finder ShowRemovableMediaOnDesktop -bool true
ok

running "Finder: show hidden files by default."
defaults write com.apple.finder AppleShowAllFiles -bool true
ok

running "Finder: show all filename extensions."
defaults write NSGlobalDomain AppleShowAllExtensions -bool true
ok

running "Finder: show status bar."
defaults write com.apple.finder ShowStatusBar -bool true
ok

running "Finder: show path bar."
defaults write com.apple.finder ShowPathbar -bool true
ok

running "Display full POSIX path as Finder window title."
defaults write com.apple.finder _FXShowPosixPathInTitle -bool true
ok

running "Keep folders on top when sorting by name."
defaults write com.apple.finder _FXSortFoldersFirst -bool true
ok

running "When performing a search, search the current folder by default."
defaults write com.apple.finder FXDefaultSearchScope -string "SCcf"
ok

running "Disable the warning when changing a file extension."
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false
ok

running "Enable spring loading for directories."
defaults write NSGlobalDomain com.apple.springing.enabled -bool true
ok

running "Remove the spring loading delay for directories."
defaults write NSGlobalDomain com.apple.springing.delay -float 0
ok

running "Avoid creating .DS_Store files on network or USB volumes."
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true
defaults write com.apple.desktopservices DSDontWriteUSBStores -bool true
ok

running "Disable disk image verification."
defaults write com.apple.frameworks.diskimages skip-verify -bool true
defaults write com.apple.frameworks.diskimages skip-verify-locked -bool true
defaults write com.apple.frameworks.diskimages skip-verify-remote -bool true
ok

running "Automatically open a new Finder window when a volume is mounted."
defaults write com.apple.frameworks.diskimages auto-open-ro-root -bool true
defaults write com.apple.frameworks.diskimages auto-open-rw-root -bool true
defaults write com.apple.finder OpenWindowForNewRemovableDisk -bool true
ok

running "Show item info near icons on the desktop and in other icon views."
/usr/libexec/PlistBuddy -c "Set :DesktopViewSettings:IconViewSettings:showItemInfo true" ~/Library/Preferences/com.apple.finder.plist
/usr/libexec/PlistBuddy -c "Set :FK_StandardViewSettings:IconViewSettings:showItemInfo true" ~/Library/Preferences/com.apple.finder.plist
/usr/libexec/PlistBuddy -c "Set :StandardViewSettings:IconViewSettings:showItemInfo true" ~/Library/Preferences/com.apple.finder.plist
ok

# running "Show item info to the right of the icons on the desktop."
# /usr/libexec/PlistBuddy -c "Set DesktopViewSettings:IconViewSettings:labelOnBottom false" ~/Library/Preferences/com.apple.finder.plist
# ok

running "Enable snap-to-grid for icons on the desktop and in other icon views."
/usr/libexec/PlistBuddy -c "Set :DesktopViewSettings:IconViewSettings:arrangeBy grid" ~/Library/Preferences/com.apple.finder.plist
/usr/libexec/PlistBuddy -c "Set :FK_StandardViewSettings:IconViewSettings:arrangeBy grid" ~/Library/Preferences/com.apple.finder.plist
/usr/libexec/PlistBuddy -c "Set :StandardViewSettings:IconViewSettings:arrangeBy grid" ~/Library/Preferences/com.apple.finder.plist
ok

running "Increase grid spacing for icons on the desktop and in other icon views."
/usr/libexec/PlistBuddy -c "Set :DesktopViewSettings:IconViewSettings:gridSpacing 100" ~/Library/Preferences/com.apple.finder.plist
/usr/libexec/PlistBuddy -c "Set :FK_StandardViewSettings:IconViewSettings:gridSpacing 100" ~/Library/Preferences/com.apple.finder.plist
/usr/libexec/PlistBuddy -c "Set :StandardViewSettings:IconViewSettings:gridSpacing 100" ~/Library/Preferences/com.apple.finder.plist
ok

# running "Increase the size of icons on the desktop and in other icon views."
# /usr/libexec/PlistBuddy -c "Set :DesktopViewSettings:IconViewSettings:iconSize 80" ~/Library/Preferences/com.apple.finder.plist
# /usr/libexec/PlistBuddy -c "Set :FK_StandardViewSettings:IconViewSettings:iconSize 80" ~/Library/Preferences/com.apple.finder.plist
# /usr/libexec/PlistBuddy -c "Set :StandardViewSettings:IconViewSettings:iconSize 80" ~/Library/Preferences/com.apple.finder.plist
# ok

# Four-letter codes for the other view modes: Flwv ▸ Cover Flow View Nlsv ▸ List View clmv ▸ Column View icnv ▸ Icon View
running "Use list view in all Finder windows by default."
defaults write com.apple.finder FXPreferredViewStyle -string "Nlsv"
defaults write com.apple.finder SearchRecentsSavedViewStyle -string "Nlsv"
ok

running "Disable the warning before emptying the Trash."
defaults write com.apple.finder WarnOnEmptyTrash -bool false
ok

running "Enable AirDrop over Ethernet and on unsupported Macs running Lio.n."
defaults write com.apple.NetworkBrowser BrowseAllInterfaces -bool true
ok

running "Show the ~/Library folder."
chflags nohidden ~/Library && xattr -d com.apple.FinderInfo ~/Library
ok

running "Show the /Volumes folder."
sudo chflags nohidden /Volumes
ok

running "Remove Dropbox’s green checkmark icons in Finder."
file=/Applications/Dropbox.app/Contents/Resources/emblem-dropbox-uptodate.icns
[ -e "${file}" ] && mv -f "${file}" "${file}.bak"
ok

running "Expand the following File Info panes:."
# “General”, “Open with”, and “Sharing & Permissions”
defaults write com.apple.finder FXInfoPanesExpanded -dict \
	General -bool true \
	OpenWith -bool true \
	Privileges -bool true
ok

running "Show preview pane" Y
defaults write com.apple.finder ShowPreviewPane -bool true
ok


running "Allowing text selection in Quick Look/Preview in Finder by default"
defaults write com.apple.finder QLEnableTextSelection -bool true
ok

# TODO: ds_store
#######################################################################################################################################
bot "Configuring Dock, Dashboard, and hot corners, Menu bar"
#######################################################################################################################################

running "Enable highlight hover effect for the grid view of a stack (Dock)."
defaults write com.apple.dock mouse-over-hilite-stack -bool true
ok

running "Set the icon size of Dock items to 60 pixels."
defaults write com.apple.dock tilesize -int 60
ok

running "Change minimize/maximize window effect."
defaults write com.apple.dock mineffect -string "scale"
ok

running "Minimize windows into their application’s icon."
defaults write com.apple.dock minimize-to-application -bool true
ok

running "Enable spring loading for all Dock items."
defaults write com.apple.dock enable-spring-load-actions-on-all-items -bool true
ok

running "Show indicator lights for open applications in the Dock."
defaults write com.apple.dock show-process-indicators -bool true
ok

# running "Wipe all (default) app icons from the Dock."
# This is only really useful when setting up a new Mac, or if you don’t use
# the Dock to launch apps.
# defaults write com.apple.dock persistent-apps -array
# ok

# running "Show only open applications in the Dock."
# defaults write com.apple.dock static-only -bool true.
# ok

running "Don’t animate opening applications from the Dock."
defaults write com.apple.dock launchanim -bool false
ok

running "Speed up Mission Control animations."
defaults write com.apple.dock expose-animation-duration -float 0.1
ok

# (i.e. use the old Exposé behavior instead)
running "Don’t group windows by application in Mission Control."
defaults write com.apple.dock expose-group-by-app -bool false
ok

running "Disable Dashboard."
defaults write com.apple.dashboard mcx-disabled -bool true
ok

running "Don’t show Dashboard as a Space."
defaults write com.apple.dock dashboard-in-overlay -bool true
ok

running "Don’t automatically rearrange Spaces based on most recent use."
defaults write com.apple.dock mru-spaces -bool false
ok

running "Remove the auto-hiding Dock delay."
defaults write com.apple.dock autohide-delay -float 0
ok

running "Remove the animation when hiding/showing the Dock."
defaults write com.apple.dock autohide-time-modifier -float 0
ok

running "Automatically hide and show the Dock."
defaults write com.apple.dock autohide -bool true
ok

running "Make Dock icons of hidden applications translucent."
defaults write com.apple.dock showhidden -bool true
ok

running "Don’t show recent applications in Dock."
defaults write com.apple.dock show-recents -bool false
ok

running "Disable multi-display swoosh animations"
defaults write com.apple.dock workspaces-swoosh-animation-off -bool false
ok


# running "Disable the Launchpad gesture (pinch with thumb and three fingers)."
# defaults write com.apple.dock showLaunchpadGestureEnabled -int 0
# ok

# running "Reset Launchpad, but keep the desktop wallpaper intact"
# find "${HOME}/Library/Application Support/Dock" -name "*-*.db" -maxdepth 1 -delete
# ok

# running "Add iOS & Watch Simulator to Launchpad"
# sudo ln -sf "/Applications/Xcode.app/Contents/Developer/Applications/Simulator.app" "/Applications/Simulator.app"
# sudo ln -sf "/Applications/Xcode.app/Contents/Developer/Applications/Simulator (Watch).app" "/Applications/Simulator (Watch).app"
# ok

# running "Add a spacer to the left side of the Dock (where the applications are)."
# defaults write com.apple.dock persistent-apps -array-add '{tile-data={}; tile-type="spacer-tile";}'
# ok

# running "Add a spacer to the right side of the Dock (where the Trash is)."
# defaults write com.apple.dock persistent-others -array-add '{tile-data={}; tile-type="spacer-tile";}'
# ok

running "Add a 'Recent Applications' stack to the Dock"
defaults write com.apple.dock persistent-others -array-add '{ "tile-data" = { "list-type" = 1; }; "tile-type" = "recents-tile"; }'
ok

# Hot corners
# Possible values:
#  0: no-op
#  2: Mission Control
#  3: Show application windows
#  4: Desktop
#  5: Start screen saver
#  6: Disable screen saver
#  7: Dashboard
# 10: Put display to sleep
# 11: Launchpad
# 12: Notification Center
# 13: Lock Screen
# Top left screen corner → Mission Control
# running "Configure top corners."
# defaults write com.apple.dock wvous-tl-corner -int 2
# defaults write com.apple.dock wvous-tl-modifier -int 0
# # Top right screen corner → Desktop
# defaults write com.apple.dock wvous-tr-corner -int 4
# defaults write com.apple.dock wvous-tr-modifier -int 0
# # Bottom left screen corner → Start screen saver
# defaults write com.apple.dock wvous-bl-corner -int 5
# defaults write com.apple.dock wvous-bl-modifier -int 0
# ok

## Dockutil dependency installed in with brewfile
running "Make dock empty."
dockutil --remove all --allhomes
ok

# add apps
running "Add apps to dock."
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
ok

# // TODO: folder for chat apps

running "add folders to dock"
dockutil --add '~/' --view grid --sort name
dockutil --add '/Applications' --view grid --display folder --allhomes --sort name
dockutil --add '/Applications/Utilities' --view grid --display folder --allhomes --sort name
dockutil --add '~/Downloads' --view grid --display folder --allhomes --sort dateadded
ok

### have a look at potential menu bar options
# ls /System/Library/CoreServices/Menu\ Extras/

### edit plist manually with Xcode
# open -a Xcode ~/Library/Preferences/com.apple.systemuiserver.plist

# warning if system doesn't have one of these like AirPort or Bluetooth it will break
# ## DESKTOP TODO: make configurable switch

# running "Set system items for laptop menu bar."
# defaults write com.apple.systemuiserver menuExtras -array \
# "/System/Library/CoreServices/Menu Extras/AirPort.menu" \
# "/System/Library/CoreServices/Menu Extras/Bluetooth.menu" \
# "/System/Library/CoreServices/Menu Extras/Clock.menu" \
# "/System/Library/CoreServices/Menu Extras/Displays.menu" \
# "/System/Library/CoreServices/Menu Extras/Volume.menu" \
# ok

running "Set system items for desktop menu bar."
defaults write com.apple.systemuiserver menuExtras -array \
"/System/Library/CoreServices/Menu Extras/Bluetooth.menu" \
"/System/Library/CoreServices/Menu Extras/Clock.menu" \
"/System/Library/CoreServices/Menu Extras/Volume.menu" \
ok

running "refresh ui."
killall SystemUIServer
ok

#######################################################################################################################################
bot "Configuring Safari & WebKit"                                                             #
#######################################################################################################################################

running "Privacy: don’t send search queries to Apple."
defaults write com.apple.Safari UniversalSearchEnabled -bool false
defaults write com.apple.Safari SuppressSearchSuggestions -bool true
ok

running "Press Tab to highlight each item on a web page."
defaults write com.apple.Safari WebKitTabToLinksPreferenceKey -bool true
defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2TabsToLinks -bool true
ok

running "Show the full URL in the address bar (note: this still hides the scheme)."
defaults write com.apple.Safari ShowFullURLInSmartSearchField -bool true
ok

running "Set Safari’s home page to `about:blank` for faster loading."
defaults write com.apple.Safari HomePage -string "about:blank"
ok

running "Prevent Safari from opening ‘safe’ files automatically after downloading."
defaults write com.apple.Safari AutoOpenSafeDownloads -bool false
ok

running "Allow hitting the Backspace key to go to the previous page in history."
defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2BackspaceKeyNavigationEnabled -bool true
ok

running "Hide Safari’s bookmarks bar by default."
defaults write com.apple.Safari ShowFavoritesBar -bool false
ok

running "Hide Safari’s sidebar in Top Sites."
defaults write com.apple.Safari ShowSidebarInTopSites -bool false
ok

running "Disable Safari’s thumbnail cache for History and Top Sites."
defaults write com.apple.Safari DebugSnapshotsUpdatePolicy -int 2
ok

running "Enable Safari’s debug menu."
defaults write com.apple.Safari IncludeInternalDebugMenu -bool true
ok

running "Make Safari’s search banners default to Contains instead of Starts With."
defaults write com.apple.Safari FindOnPageMatchesWordStartsOnly -bool false
ok

running "Remove useless icons from Safari’s bookmarks bar."
defaults write com.apple.Safari ProxiesInBookmarksBar "()"
ok

running "Enable the Develop menu and the Web Inspector in Safari."
defaults write com.apple.Safari IncludeDevelopMenu -bool true
defaults write com.apple.Safari WebKitDeveloperExtrasEnabledPreferenceKey -bool true
defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2DeveloperExtrasEnabled -bool true
ok

running "Add a context menu item for showing the Web Inspector in web views."
defaults write NSGlobalDomain WebKitDeveloperExtras -bool true
ok

running "Enable continuous spellchecking."
defaults write com.apple.SafariWebContinuousSpellCheckingEnabled -bool true
ok

running "Automatically grammar check web forms"
defaults write com.apple.safari WebGrammarCheckingEnabled -bool true
ok


# running "Disable auto-correct."
# defaults write com.apple.Safari WebAutomaticSpellingCorrectionEnabled -bool false
# ok

running "Disable AutoFill."
defaults write com.apple.Safari AutoFillFromAddressBook -bool false
defaults write com.apple.Safari AutoFillPasswords -bool false
defaults write com.apple.Safari AutoFillCreditCardData -bool false
defaults write com.apple.Safari AutoFillMiscellaneousForms -bool false
ok

running "Warn about fraudulent websites."
defaults write com.apple.Safari WarnAboutFraudulentWebsites -bool true
ok

running "Disable plug-ins."
defaults write com.apple.Safari WebKitPluginsEnabled -bool false
defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2PluginsEnabled -bool false
ok

running "Disable Java."
defaults write com.apple.Safari WebKitJavaEnabled -bool false
defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2JavaEnabled -bool false
defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2JavaEnabledForLocalFiles -bool false
ok

running "Block pop-up windows."
defaults write com.apple.Safari WebKitJavaScriptCanOpenWindowsAutomatically -bool false
defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2JavaScriptCanOpenWindowsAutomatically -bool false
ok

# running "Disable auto-playing video."
# defaults write com.apple.Safari WebKitMediaPlaybackAllowsInline -bool false
# defaults write com.apple.SafariTechnologyPreview WebKitMediaPlaybackAllowsInline -bool false
# defaults write com.apple.Safari com.apple.Safari.ContentPageGroupIdentifier.WebKit2AllowsInlineMediaPlayback -bool false
# defaults write com.apple.SafariTechnologyPreview com.apple.Safari.ContentPageGroupIdentifier.WebKit2AllowsInlineMediaPlayback -bool false
# ok

running "Enable Do Not Track."
defaults write com.apple.Safari SendDoNotTrackHTTPHeader -bool true
ok

running "Update extensions automaticall."
defaults write com.apple.Safari InstallExtensionUpdatesAutomatically -bool true
ok

# Requires Safari 5.0.1 or later. Feature that is intended to increase the speed at which pages load. DNS (Domain Name System) prefetching kicks in when you load a webpage that contains links to other pages. As soon as the initial page is loaded, Safari 5.0.1 (or later) begins resolving the listed links’ domain names to their IP addresses. Prefetching can occasionally result in 'slow performance, partially-loaded pages, or webpage ‘cannot be found’ messages.”
running "Increase page load speed in Safari"
defaults write com.apple.safari WebKitDNSPrefetchingEnabled -bool true
ok

running "Disable Data Detectors"
defaults write com.apple.Safari WebKitUsesEncodingDetector -bool false
ok

running "Enable developer menu in Safari"
defaults write com.apple.Safari IncludeDebugMenu -bool true
ok


#######################################################################################################################################
bot "Configuring Mail."
#######################################################################################################################################

running "Disable send and reply animations in Mail.app."
defaults write com.apple.mail DisableReplyAnimations -bool true
defaults write com.apple.mail DisableSendAnimations -bool true
ok

running "Copy email addresses as 'foo@example.com' instead of 'Foo Bar <foo@example.com>' in Mail.app."
defaults write com.apple.mail AddressesIncludeNameOnPasteboard -bool false
ok

running "Add the keyboard shortcut ⌘ + Enter to send an email in Mail.app."
defaults write com.apple.mail NSUserKeyEquivalents -dict-add "Send" -string "@\\U21a9"
ok

running "Display emails in threaded mode, sorted by date (oldest at the top)."
defaults write com.apple.mail DraftsViewerAttributes -dict-add "DisplayInThreadedMode" -string "yes"
defaults write com.apple.mail DraftsViewerAttributes -dict-add "SortedDescending" -string "yes"
defaults write com.apple.mail DraftsViewerAttributes -dict-add "SortOrder" -string "received-date"
ok

running "Disable inline attachments (just show the icons)."
defaults write com.apple.mail DisableInlineAttachmentViewing -bool true
ok

# running "Disable automatic spell checking."
# defaults write com.apple.mail SpellCheckingBehavior -string "NoSpellCheckingEnabled"
# ok

running "Set a minimum font size of 15px (affects reading and sending email)"
defaults write com.apple.mail MinimumHTMLFontSize 15
ok

#######################################################################################################################################
bot "Configuring Spotlight."
#######################################################################################################################################

# running "Hide Spotlight tray-icon (and subsequent helper)."
# sudo chmod 600 /System/Library/CoreServices/Search.bundle/Contents/MacOS/Search
# ok

# Use `sudo mdutil -i off "/Volumes/foo"` to stop indexing any volume.
# running "Disable Spotlight indexing for any volume that gets mounted and has not yet been indexed."
# sudo defaults write /.Spotlight-V100/VolumeConfiguration Exclusions -array "/Volumes"
# ok

running "Change indexing order and disable some file types from being indexed."
# Yosemite-specific search results (remove them if you are using macOS 10.9 or older):
# 	MENU_DEFINITION
# 	MENU_CONVERSION
# 	MENU_EXPRESSION
# 	MENU_SPOTLIGHT_SUGGESTIONS (send search queries to Apple)
# 	MENU_WEBSEARCH             (send search queries to Apple)
# 	MENU_OTHER
defaults write com.apple.spotlight orderedItems -array \
    '{"enabled" = 1;"name" = "APPLICATIONS";}' \
    '{"enabled" = 1;"name" = "SYSTEM_PREFS";}' \
    '{"enabled" = 1;"name" = "DIRECTORIES";}' \
    '{"enabled" = 1;"name" = "PDF";}' \
    '{"enabled" = 1;"name" = "FONTS";}' \
    '{"enabled" = 1;"name" = "DOCUMENTS";}' \
    '{"enabled" = 0;"name" = "MESSAGES";}' \
    '{"enabled" = 0;"name" = "CONTACT";}' \
    '{"enabled" = 0;"name" = "EVENT_TODO";}' \
    '{"enabled" = 1;"name" = "IMAGES";}' \
    '{"enabled" = 0;"name" = "BOOKMARKS";}' \
    '{"enabled" = 1;"name" = "MUSIC";}' \
    '{"enabled" = 1;"name" = "MOVIES";}' \
    '{"enabled" = 0;"name" = "PRESENTATIONS";}' \
    '{"enabled" = 1;"name" = "SPREADSHEETS";}' \
    '{"enabled" = 1;"name" = "SOURCE";}' \
    '{"enabled" = 0;"name" = "MENU_DEFINITION";}' \
    '{"enabled" = 0;"name" = "MENU_OTHER";}' \
    '{"enabled" = 0;"name" = "MENU_CONVERSION";}' \
    '{"enabled" = 0;"name" = "MENU_EXPRESSION";}' \
    '{"enabled" = 0;"name" = "MENU_WEBSEARCH";}' \
    '{"enabled" = 1;"name" = "MENU_SPOTLIGHT_SUGGESTIONS";}'
    ok

running "Load new settings before rebuilding the index."
killall mds > /dev/null 2>&1
ok

running "Make sure indexing is enabled for the main volume."
sudo mdutil -i on / > /dev/null
ok

running "Rebuild the index from scratch."
sudo mdutil -E / > /dev/null
ok

#######################################################################################################################################
bot "Time Machine."
#######################################################################################################################################

running "Prevent Time Machine from prompting to use new hard drives as backup volume."
defaults write com.apple.TimeMachine DoNotOfferNewDisksForBackup -bool true
ok

# running "Disable local Time Machine backups."
# hash tmutil &> /dev/null && sudo tmutil disablelocal
# ok

#######################################################################################################################################
bot "Configuring Activity Monitor."
#######################################################################################################################################

running "Show the main window when launching Activity Monitor."
defaults write com.apple.ActivityMonitor OpenMainWindow -bool true
ok

running "Visualize CPU usage in the Activity Monitor Dock icon."
defaults write com.apple.ActivityMonitor IconType -int 5
ok

# Show processes in Activity Monitor
# 100: All Processes
# 101: All Processes, Hierarchally
# 102: My Processes
# 103: System Processes
# 104: Other User Processes
# 105: Active Processes
# 106: Inactive Processes
# 106: Inactive Processes
# 107: Windowed Processes
running "Show all processes in Activity Monitor."
defaults write com.apple.ActivityMonitor ShowCategory -int 100
ok

running "Sort Activity Monitor results by CPU usage."
defaults write com.apple.ActivityMonitor SortColumn -string "CPUUsage"
defaults write com.apple.ActivityMonitor SortDirection -int 0
ok

running "Set columns for each tab."
defaults write com.apple.ActivityMonitor "UserColumnsPerTab v5.0" -dict \
    '0' '( Command, CPUUsage, CPUTime, Threads, PID, UID, Ports )' \
    '1' '( Command, ResidentSize, Threads, Ports, PID, UID,  )' \
    '2' '( Command, PowerScore, 12HRPower, AppSleep, UID, powerAssertion )' \
    '3' '( Command, bytesWritten, bytesRead, Architecture, PID, UID, CPUUsage )' \
    '4' '( Command, txBytes, rxBytes, PID, UID, txPackets, rxPackets, CPUUsage )'
    ok

running "Sort columns in each tab."
defaults write com.apple.ActivityMonitor UserColumnSortPerTab -dict \
    '0' '{ direction = 0; sort = CPUUsage; }' \
    '1' '{ direction = 0; sort = ResidentSize; }' \
    '2' '{ direction = 0; sort = 12HRPower; }' \
    '3' '{ direction = 0; sort = bytesWritten; }' \
    '4' '{ direction = 0; sort = txBytes; }'
    ok

running "Update refresh frequency (in seconds)."
# 1: Very often (1 sec)
# 2: Often (2 sec)
# 5: Normally (5 sec)
defaults write com.apple.ActivityMonitor UpdatePeriod -int 2
ok

running "Show Data in the Disk graph (instead of IO)."
defaults write com.apple.ActivityMonitor DiskGraphType -int 1
ok

running "Show Data in the Network graph (instead of packets)."
defaults write com.apple.ActivityMonitor NetworkGraphType -int 1
ok

running "Change Dock Icon."
# 0: Application Icon
# 2: Network Usage
# 3: Disk Activity
# 5: CPU Usage
# 6: CPU History
defaults write com.apple.ActivityMonitor IconType -int 3
ok

#######################################################################################################################################
bot "Configuring Address Book, Dashboard, iCal, TextEdit, Preview and Disk Utility."
#######################################################################################################################################

running "Enable the debug menu in Address Book"
defaults write com.apple.addressbook ABShowDebugMenu -bool true
ok

running "Enable Dashboard dev mode (allows keeping widgets on the desktop)"
defaults write com.apple.dashboard devmode -bool true
ok

running "Enable the debug menu in iCal (pre-10.8)"
defaults write com.apple.iCal IncludeDebugMenu -bool true
ok

running "Use plain text mode for new TextEdit documents"
defaults write com.apple.TextEdit RichText -int 0
ok

running "Open and save files as UTF-8 in TextEdit"
defaults write com.apple.TextEdit PlainTextEncoding -int 4
defaults write com.apple.TextEdit PlainTextEncodingForWrite -int 4
ok

running "Enable the debug menu in Disk Utility"
defaults write com.apple.DiskUtility DUDebugMenuEnabled -bool true
defaults write com.apple.DiskUtility advanced-image-options -bool true
ok

running "Auto-play videos when opened with QuickTime Player"
defaults write com.apple.QuickTimePlayerX MGPlayMovieOnOpen -bool true
ok

running "Shows all partitions for a disk in the main list"
defaults write com.apple.DiskUtility DUShowEveryPartition -bool true
ok

running "Debug All Message Level"
defaults write com.apple.DiskUtility DUDebugMessageLevel -int 4
ok

running "Show Details In First Aid"
defaults write com.apple.DiskUtility DUShowDetailsInFirstAid -bool true
ok


running "Quit Always Keeps Windows"
defaults write com.apple.Preview NSQuitAlwaysKeepsWindows -bool true
ok

#######################################################################################################################################
bot "Configuring Mac App Store."
#######################################################################################################################################

running "Enable the WebKit Developer Tools in the Mac App Store."
defaults write com.apple.appstore WebKitDeveloperExtras -bool true
ok

running "Enable Debug Menu in the Mac App Store."
defaults write com.apple.appstore ShowDebugMenu -bool true
ok

running "Enable the automatic update check."
defaults write com.apple.SoftwareUpdate AutomaticCheckEnabled -bool true
ok

running "Check for software updates daily, not just once per week."
defaults write com.apple.SoftwareUpdate ScheduleFrequency -int 1
ok

running "Download newly available updates in background."
defaults write com.apple.SoftwareUpdate AutomaticDownload -int 1
ok

running "Show app-centric sidebar"
defaults write com.apple.finder FK_AppCentricShowSidebar -bool true
ok

# running "Install System data files & security updates."
# defaults write com.apple.SoftwareUpdate CriticalUpdateInstall -int 1
# ok

# running "Automatically download apps purchased on other Macs."
# defaults write com.apple.SoftwareUpdate ConfigDataInstall -int 1
# ok

# running "Turn on app auto-update."
# defaults write com.apple.commerce AutoUpdate -bool true
# ok

# running "Allow the App Store to reboot machine on macOS updates."
# defaults write com.apple.commerce AutoUpdateRestartRequired -bool true
# ok

#######################################################################################################################################
bot "Configuring Photos."                                                                      #
#######################################################################################################################################

running "Prevent Photos from opening automatically when devices are plugged in."
defaults -currentHost write com.apple.ImageCapture disableHotPlug -bool true
ok

#######################################################################################################################################
bot "Configuring Messages."
#######################################################################################################################################

# running "Disable automatic emoji substitution (i.e. use plain text smileys)."
# defaults write com.apple.messageshelper.MessageController SOInputLineSettings -dict-add "automaticEmojiSubstitutionEnablediMessage" -bool false
# ok

running "Disable smart quotes as it’s annoying for messages that contain code."
defaults write com.apple.messageshelper.MessageController SOInputLineSettings -dict-add "automaticQuoteSubstitutionEnabled" -bool false
ok

# running "Disable continuous spell checking."
# defaults write com.apple.messageshelper.MessageController SOInputLineSettings -dict-add "continuousSpellCheckingEnabled" -bool false
# ok

#######################################################################################################################################
bot "Configuring Google Chrome & Google Chrome Canary"                                        #
#######################################################################################################################################

running "Disable the all too sensitive backswipe on trackpads."
defaults write com.google.Chrome AppleEnableSwipeNavigateWithScrolls -bool false
defaults write com.google.Chrome.canary AppleEnableSwipeNavigateWithScrolls -bool false
ok

running "Disable the all too sensitive backswipe on Magic Mouse."
defaults write com.google.Chrome AppleEnableMouseSwipeNavigateWithScrolls -bool false
defaults write com.google.Chrome.canary AppleEnableMouseSwipeNavigateWithScrolls -bool false
ok

running "Use the system-native print preview dialog."
defaults write com.google.Chrome DisablePrintPreview -bool true
defaults write com.google.Chrome.canary DisablePrintPreview -bool true
ok

running "Expand the print dialog by default."
defaults write com.google.Chrome PMPrintingExpandedStateForPrint2 -bool true
defaults write com.google.Chrome.canary PMPrintingExpandedStateForPrint2 -bool true
ok

#######################################################################################################################################
bot "Configuring Security."
#######################################################################################################################################
# Based on:
# https://github.com/drduh/macOS-Security-and-Privacy-Guide
# https://benchmarks.cisecurity.org/tools2/osx/CIS_Apple_OSX_10.12_Benchmark_v1.0.0.pdf

# Enable firewall. Possible values:
#   0 = off
#   1 = on for specific sevices
#   2 = on for essential services
running "Enable firewall."
sudo defaults write /Library/Preferences/com.apple.alf globalstate -int 1
ok

# Source: https://support.apple.com/kb/PH18642

running "Enable firewall stealth mode (no response to ICMP / ping requests)."
sudo defaults write /Library/Preferences/com.apple.alf stealthenabled -int 1
ok

# running "Enable firewall logging."
# sudo defaults write /Library/Preferences/com.apple.alf loggingenabled -int 1
# ok

running "Do not automatically allow signed software to receive incoming connections."
#sudo defaults write /Library/Preferences/com.apple.alf allowsignedenabled -bool false
ok

# running "Log firewall events for 90 days."
# sudo perl -p -i -e 's/rotate=seq compress file_max=5M all_max=50M/rotate=utc compress file_max=5M ttl=90/g' "/etc/asl.conf"
# sudo perl -p -i -e 's/appfirewall.log file_max=5M all_max=50M/appfirewall.log rotate=utc compress file_max=5M ttl=90/g' "/etc/asl.conf"
# ok

# (uncomment if above is not commented out)
# running "Reload the firewall."
# launchctl unload /System/Library/LaunchAgents/com.apple.alf.useragent.plist
# sudo launchctl unload /System/Library/LaunchDaemons/com.apple.alf.agent.plist
# sudo launchctl load /System/Library/LaunchDaemons/com.apple.alf.agent.plist
# launchctl load /System/Library/LaunchAgents/com.apple.alf.useragent.plist
# ok

# running "Disable IR remote control."
# sudo defaults write /Library/Preferences/com.apple.driver.AppleIRController DeviceEnabled -bool false
# ok

# running "Turn Bluetooth off completely."
# sudo defaults write /Library/Preferences/com.apple.Bluetooth ControllerPowerState -int 0
# sudo launchctl unload /System/Library/LaunchDaemons/com.apple.blued.plist
# sudo launchctl load /System/Library/LaunchDaemons/com.apple.blued.plist
# ok

# running "Disable wifi captive portal."
#sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.captive.control Active -bool false
# ok

running "Disable remote apple events."
sudo systemsetup -setremoteappleevents off
ok

running "Disable remote login."
sudo systemsetup -setremotelogin off
ok

# running "Disable wake-on modem."
# sudo systemsetup -setwakeonmodem off
# ok

# running "Disable wake-on LAN."
# sudo systemsetup -setwakeonnetworkaccess off
# ok

# running "Disable file-sharing via AFP or SMB."
# sudo launchctl unload -w /System/Library/LaunchDaemons/com.apple.AppleFileServer.plist
# sudo launchctl unload -w /System/Library/LaunchDaemons/com.apple.smbd.plist
# ok

running "Display login window as name and password."
#sudo defaults write /Library/Preferences/com.apple.loginwindow SHOWFULLNAME -bool true
ok

running "Do not show password hints."
#sudo defaults write /Library/Preferences/com.apple.loginwindow RetriesUntilHint -int 0
ok

# running "Automatically lock the login keychain for inactivity after 6 hours."
# security set-keychain-settings -t 21600 -l ~/Library/Keychains/login.keychain
# ok

# Source: https://web.archive.org/web/20160114141929/http://training.apple.com/pdf/WP_FileVault2.pdf.
# running "Destroy FileVault key when going into standby mode, forcing a re-auth.."
# sudo pmset destroyfvkeyonstandby 1
# ok

# running "Disable Bonjour multicast advertisements."
# sudo defaults write /Library/Preferences/com.apple.mDNSResponder.plist NoMulticastAdvertisements -bool true
# ok

running "Disable diagnostic reports."
sudo launchctl unload -w /System/Library/LaunchDaemons/com.apple.SubmitDiagInfo.plist
ok

# running "Log authentication events for 90 days."
# sudo perl -p -i -e 's/rotate=seq file_max=5M all_max=20M/rotate=utc file_max=5M ttl=90/g' "/etc/asl/com.apple.authd"
# ok

# running "Log installation events for a year."
# sudo perl -p -i -e 's/format=bsd/format=bsd mode=0640 rotate=utc compress file_max=5M ttl=365/g' "/etc/asl/com.apple.install"
# ok

# running "Increase the retention time for system.log and secure.log."
# sudo perl -p -i -e 's/\/var\/log\/wtmp.*$/\/var\/log\/wtmp   \t\t\t640\ \ 31\    *\t\@hh24\ \J/g' "/etc/newsyslog.conf"
# ok

# running "Keep a log of kernel events for 30 days."
# sudo perl -p -i -e 's|flags:lo,aa|flags:lo,aa,ad,fd,fm,-all,^-fa,^-fc,^-cl|g' /private/etc/security/audit_control
# sudo perl -p -i -e 's|filesz:2M|filesz:10M|g' /private/etc/security/audit_control
# sudo perl -p -i -e 's|expire-after:10M|expire-after: 30d |g' /private/etc/security/audit_control

running "Disable the Are you sure you want to open this application? dialog"
defaults write com.apple.LaunchServices LSQuarantine -bool false
ok

running "Empty Trash securely by default."
defaults write com.apple.finder EmptyTrashSecurely -bool true
ok

###############################################################################
# Monolingual                                                                 #
###############################################################################

running "Monolingual settings"
defaults write net.sourceforge.Monolingual SUAutomaticallyUpdate -bool true
defaults write net.sourceforge.Monolingual SUEnableAutomaticChecks -bool true
defaults write net.sourceforge.Monolingual SUSendProfileInfo -bool false
defaults write net.sourceforge.Monolingual Strip -bool true
ok


# ###############################################################################
# # iTerm 2                                                                     #
# ###############################################################################

# # TODO: Need to set the keyboard overrides for "back/forward 1 word" AND "Jobs to Ignore"
# running "iTerm2 settings"
#  defaults write com.googlecode.iterm2 AllowClipboardAccess -bool true
# oklecode.iterm2 AppleAntiAliasingThreshold -bool true
#  defaults write com.googlecode.iterm2 AppleScrollAnimationEnabled -bool false
#  defaults write com.googlecode.iterm2 AppleSmoothFixedFontsSizeThreshold -bool true
#  defaults write com.googlecode.iterm2 AppleWindowTabbingMode -string "manual"
#  defaults write com.googlecode.iterm2 AutoCommandHistory -bool false
#  defaults write com.googlecode.iterm2 CheckTestRelease -bool true
#  defaults write com.googlecode.iterm2 DimBackgroundWindows -bool true
#  defaults write com.googlecode.iterm2 HideTab -bool false
#  defaults write com.googlecode.iterm2 HotkeyMigratedFromSingleToMulti -bool true
#  defaults write com.googlecode.iterm2 IRMemory -int 4
#  defaults write com.googlecode.iterm2 NSFontPanelAttributes -string "1, 0"
#  defaults write com.googlecode.iterm2 NSNavLastRootDirectory -string "${HOME}/Desktop"
#  defaults write com.googlecode.iterm2 NSQuotedKeystrokeBinding -string ""
#  defaults write com.googlecode.iterm2 NSScrollAnimationEnabled -bool false
#  defaults write com.googlecode.iterm2 NSScrollViewShouldScrollUnderTitlebar -bool false
#  defaults write com.googlecode.iterm2 NoSyncCommandHistoryHasEverBeenUsed -bool true
#  defaults write com.googlecode.iterm2 NoSyncDoNotWarnBeforeMultilinePaste -bool true
#  defaults write com.googlecode.iterm2 NoSyncDoNotWarnBeforeMultilinePaste_selection -bool false
#  defaults write com.googlecode.iterm2 NoSyncDoNotWarnBeforePastingOneLineEndingInNewlineAtShellPrompt -bool true
#  defaults write com.googlecode.iterm2 NoSyncDoNotWarnBeforePastingOneLineEndingInNewlineAtShellPrompt_selection -bool true
#  defaults write com.googlecode.iterm2 NoSyncHaveRequestedFullDiskAccess -bool true
#  defaults write com.googlecode.iterm2 NoSyncHaveWarnedAboutPasteConfirmationChange -bool true
#  defaults write com.googlecode.iterm2 NoSyncPermissionToShowTip -bool true
#  defaults write com.googlecode.iterm2 NoSyncSuppressBroadcastInputWarning -bool true
#  defaults write com.googlecode.iterm2 NoSyncSuppressBroadcastInputWarning_selection -bool false
#  defaults write com.googlecode.iterm2 OnlyWhenMoreTabs -bool false
#  defaults write com.googlecode.iterm2 OpenArrangementAtStartup -bool false
#  defaults write com.googlecode.iterm2 OpenNoWindowsAtStartup -bool false
#  defaults write com.googlecode.iterm2 PromptOnQuit -bool false
#  defaults write com.googlecode.iterm2 SUAutomaticallyUpdate -bool true
#  defaults write com.googlecode.iterm2 SUEnableAutomaticChecks -bool true
#  defaults write com.googlecode.iterm2 SUFeedAlternateAppNameKey -string iTerm;
#  defaults write com.googlecode.iterm2 SUFeedURL -string "https://iterm2.com/appcasts/final.xml?shard=69"
#  defaults write com.googlecode.iterm2 SUHasLaunchedBefore -bool true
#  defaults write com.googlecode.iterm2 SUUpdateRelaunchingMarker -bool false
#  defaults write com.googlecode.iterm2 SavePasteHistory -bool false
#  defaults write com.googlecode.iterm2 ShowBookmarkName -bool false
#  defaults write com.googlecode.iterm2 SplitPaneDimmingAmount -string "0.4070612980769232"
#  defaults write com.googlecode.iterm2 StatusBarPosition -integer 1
#  defaults write com.googlecode.iterm2 SuppressRestartAnnouncement -bool true
#  defaults write com.googlecode.iterm2 TabStyleWithAutomaticOption -integer 4
#  defaults write com.googlecode.iterm2 TraditionalVisualBell -bool true
#  defaults write com.googlecode.iterm2 UseBorder -bool true
#  defaults write com.googlecode.iterm2 WordCharacters -string "/-+\\\\~-integer."
#  defaults write com.googlecode.iterm2 findMode_iTerm -bool false
#  defaults write com.googlecode.iterm2 kCPKSelectionViewPreferredModeKey -bool false
#  defaults write com.googlecode.iterm2 kCPKSelectionViewShowHSBTextFieldsKey -bool false




#######################################################################################################################################
bot  "Kill affected applications."                                                  #
#######################################################################################################################################

for app in "Activity Monitor" \
	"Address Book" \
	"Calendar" \
	"Contacts" \
	"Dock" \
	"Finder" \
	"Google Chrome" \
	"Mail" \
	"Photos" \
	"Safari" \
	"SystemUIServer" \
	"Terminal" \
	"iCal"; do
	killall "${app}" &> /dev/null
done

Bot "Done. Note that some of these changes require a logout/restart to take effect."
