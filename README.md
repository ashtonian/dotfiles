# dotfiles

macOS & [windows](./win10/readme.md) dotfiles & post install scripts - better defaults, productive os, awesome tools.

This will initialize a freshly installed Mac OS (catalina) instance with all of my applications, cli tools, and adjust some basic operating system settings.


## Instructions

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/ashtonian/dotfiles/master/install.sh)"
```

## Basic Tool Overview

* mas
* Brew / bundle
* mackup
* git sync

### System Tools

* dockutil
* displayplacer
* [defaults](https://github.com/aerobounce/defaults.sh) - convert user defaults (plist) into shell script with ease!
* sidebarutil

## App Settings Highlights n Notes

See [software](./Software.md) page for macOS packages, vsCode extensions, web extensions.

### Global Shortcuts

* 1password- <kbd>⌘</kbd><kbd>⇧</kbd><kbd>P</kbd>
* Alfred- <kbd>⌘</kbd><kbd>space</kbd> prompt, <kbd>⌘</kbd><kbd>⌥</kbd><kbd>C</kbd> view clip history
* Cheetsheet hold- <kbd>⌘</kbd>
* Notion
* MonoSnap - <kbd>⌘</kbd><kbd>⌥</kbd><kbd>5</kbd> capture area, <kbd>⌘</kbd><kbd>⌥</kbd><kbd>6</kbd> capture fullscreen, <kbd>⌘</kbd><kbd>⌥</kbd><kbd>4</kbd> record video, toggle record fullscreen <kbd>⌘</kbd><kbd>⌃</kbd><kbd>⇧</kbd><kbd>F</kbd>, <kbd>⌃</kbd><kbd>⇧</kbd><kbd>space</kbd> start/pause,  <kbd>⌘</kbd><kbd>⌥</kbd><kbd>Q</kbd> Stop
* Timer (horo) - <kbd>⌃</kbd><kbd>⌥</kbd><kbd>T</kbd>
* Todoist - <kbd>⌃</kbd><kbd>⌘</kbd><kbd>T</kbd> show/hide,  <kbd>⌃</kbd><kbd>⌘</kbd><kbd>A</kbd> Quick task
* yoink - <kbd>⌃</kbd><kbd>⌥</kbd><kbd>Y</kbd>
* numi - <kbd>⌃</kbd><kbd>⌥</kbd><kbd>N</kbd>

### Manual Work

* VSCode, Alfred, Brave Sync Setup
* Signin to Apple Account, Mail|Contacts|Calendar, RescueTime (app,web plugin), Todoist (web plugin, app), Notion (web plugin, desktop), Spotify, Slack, Discord, Signal, Steam
* Override Spotlight with Alfred
* Install [bypass-paywalls-chrome](https://github.com/iamadamdev/bypass-paywalls-chrome.git) - [possible solution](https://stackoverflow.com/questions/16800696/how-install-crx-chrome-extension-via-command-line)
* Open all apps to deal with initial sys preferences and startup settings

## Automation Dreams

* https://github.com/Lord-Kamina/SwiftDefaultApps/issues/29 -> adjusts default apps, web app, programming -> vscode, video vlc, flac vox,  ssh,telnet + others -> iterm.
* add dev apps to security, privacy "dev tools" category to avoid security policy.
* TODO: automate open here https://gist.github.com/pdanford/158d74e2026f393e953ed43ff8168ec1
* better [.gitconfig](https://github.com/mathiasbynens/dotfiles/blob/main/.gitconfig) or [.gitconfig](https://github.com/atomantic/dotfiles/blob/master/homedir/.gitconfig)
* figureout t2 chip issue preventing vpn'd mac from using keyboard if route is not present. [related hnews](https://news.ycombinator.com/item?id=24838816)
* shellsync, search, backup, history persistence, search, sync
* desktop background + screen saver sync + setup per res

## Inspiration and Resources

* [awesome alfred workflows](https://github.com/alfred-workflows/awesome-alfred-workflows), [more workflows](https://github.com/zenorocha/alfred-workflows)
* [awesome macos command line](https://github.com/herrbischoff/awesome-macos-command-line)
* [awesome-bash-alias](https://github.com/vikaskyadav/awesome-bash-alias)
* [awesome-dotfiles](https://github.com/webpro/awesome-dotfiles)
* [dotfiles.github.com](https://github.com/dotfiles/dotfiles.github.com)
* [iCHAIT/awesome-macOS](https://github.com/iCHAIT/awesome-macOS)
* [jaywcjlove/awesome-mac](https://github.com/jaywcjlove/awesome-mac#readme)
* [Mathias Bytnens dotfiles](https://github.com/mathiasbynens/dotfiles)
* [quick look plugins](https://github.com/sindresorhus/quick-look-plugins)
* [serhii-londar/open-source-mac-os-apps](https://github.com/serhii-londar/open-source-mac-os-apps#readme)
* [shell startup file order](https://shreevatsa.wordpress.com/2008/03/30/zshbash-startup-files-loading-order-bashrc-zshrc-etc/)
* [vraravam os x defaults gist](https://gist.github.com/vraravam/8c9eae91a3750bed86b81e3a4711f842)
