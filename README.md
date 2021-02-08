# dotfiles

macOS & [windows](./win10/readme.md) dotfiles & post install scripts - better defaults, productive os, awesome tools.

This will initialize a freshly installed Mac OS (catalina) instance with all of my applications, cli tools, and adjust some basic operating system settings.

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

* 1password
* Alfred
* Cheetsheet
* Email/Cal/Contacts
* move screens spaces
* Notion
* Record
* MonoSnap - screenshot/record
* Timer (horo)
* Todoist
* yoink
* numi  <kbd>⌘</kbd><kbd>⇧</kbd><kbd>N</kbd>
* Micktagger
* alttab?

## Instructions

// TODOO:
run init.sh
run install.sh
restart
mackup restore
Execute on manual work

### Manual Work

* Signin to Apple Account, Mail|Contacts|Calendar, RescueTime (app,web plugin), Waka(web plugin, cli, vscode), Todoist (web plugin, app), Notion (web plugin, desktop), Pulse SMS (app), Spotify, Slack, Discord, Signal, Steam, RPi Web Plugin, Pocket (App,Plugin)
* VSCode, Alfred, Brave Sync Setup
* Override Spotlight with Alfred
* Install [bypass-paywalls-chrome](https://github.com/iamadamdev/bypass-paywalls-chrome.git) - [possible solution](https://stackoverflow.com/questions/16800696/how-install-crx-chrome-extension-via-command-line)
* go get https://github.com/dborzov/lsp
* npm install -g how2
* Open all apps to deal with initial sys preferences and startup settings

## Automation dreams and TODO

* https://github.com/Lord-Kamina/SwiftDefaultApps/issues/29 -> adjusts default apps, web app, programming -> vscode, video vlc, flac vox,  ssh,telnet + others -> iterm.
* add dev apps to security, privacy "dev tools" category to avoid security policy.
* TODO: automate open here https://gist.github.com/pdanford/158d74e2026f393e953ed43ff8168ec1
* set beyondcompare as merge tool
* better [.gitconfig](https://github.com/mathiasbynens/dotfiles/blob/main/.gitconfig) or [.gitconfig](https://github.com/atomantic/dotfiles/blob/master/homedir/.gitconfig)
* Wake on keyboard not mouse
* Dual boot linux encrypted disk - always The Disk you inserted was not readable on startup
* figureout t2 chip issue preventing vpn'd mac from using keyboard if route is present. [related hnews](https://news.ycombinator.com/item?id=24838816)
* shellsync, search, backup, history persistence, search, sync
* desktop background + screen saver sync + setup per res
* soulution - cli journal ? jyputer
* solution - would snippets help? snippetslab
* solution - script hide all apps, empty trash, open apps in screen per a profile ie work -> vscode screen 1, iterm screen 2 vs personal
* cron fetch (docker, git, gohome, alfred, npm, zsh, ohmyzsh, vim, + others
* horo, monosnap, ohmystar workflow
* git/projects dir auto fetchs

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
* [vraravam brewfile](https://gist.github.com/vraravam/5e28ca1720c9dddacdc0e6db61e093fe)
* [vraravam os x defaults gist](https://gist.github.com/vraravam/8c9eae91a3750bed86b81e3a4711f842)