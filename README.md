# dotfiles

macOS & windows dotfiles & post install scripts - better defaults, no os noise, awesome tools.

## macOS Setup

This will initialize a freshly installed Mac OS (catalina) instance with all of applications, cli tools, and adjust some basic operating system settings.

### Instructions:

* https://gist.github.com/vraravam/5e28ca1720c9dddacdc0e6db61e093fe
* https://gist.github.com/vraravam/8c9eae91a3750bed86b81e3a4711f842
* increase dock icon size
* decrease desktop grid
* verify finder list / open pannels
TODO:
* curl init.sh
* alias .macup.cfg to home
* install brew
* macup restore
* cron jobs
* mackup sync n save.
* rename dotfiles
* finder favorites
```sh
# initializes xcode & git
sudo xcode-select --install
mkdir ~/Projects
git clone https://github.com/Ashtonian/-HOME.git
./~/Projects/-Home/catalina/init1.sh
```

## iTerm2 Settings Highlights

### Keymap

* Preferences -> profile -> keymap -> load presets -> natural typing - gives use of things like <kbd>⌥</kbd> + <kbd>←</kbd>,<kbd>→</kbd>
* add <kbd>⌃</kbd><kbd>⌘</kbd><kbd>f</kbd> | Action: toggle full screen
* add <kbd>⌥</kbd><kbd>⇧</kbd><kbd>←</kbd> | Action: Move Start of Selection Back > Move by Word.
* add <kbd>⌥</kbd><kbd>⇧</kbd><kbd>→</kbd> | Action: Move End of Selection Forward > Move by Word.
* add <kbd>⌥</kbd><kbd>←</kbd> | Action: Move start of selection back > Move by character.
* add <kbd>⌥</kbd><kbd>→</kbd> | Action: Move end of selection forward > Move by character.
* add <kbd>⌘</kbd><kbd>z</kbd> | Action: Send Hex Codes > `0x1f`
* add <kbd>⇧</kbd><kbd>⌘</kbd><kbd>Z</kbd> Action: Send Hex Codes > `0x18 0x1f`
  * Typically not bound in bash, zsh or readline, so we can set it to a unused hexcode which we can then fix in zsh. [Stack overflow](http://stackoverflow.com/questions/6205157/iterm2-how-to-get-jump-to-beginning-end-of-line-in-bash-shell#answer-29403520):
  * ```sh
    # adds redo
    $ echo 'bindkey "^X^_" redo' >> ~/.zshrc

    # reload your .zshrc for changes to take effect
    $ source ~/.zshrc
    ```

### Manual Things

* enable cmd shft f ring central 
* auto install https://github.com/iamadamdev/bypass-paywalls-chrome.git git clone - chrome://extensions - load
* add dev apps to security, privacy "dev tools" category to avoid security policiy.
* fix "are you sure you want to open app" 
* run monolingual to save space on language packs and architectures
* setup vscode sync
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
* setup default browser `system preferences -> general`
* 1password global shortcut cmd + \ conflicts with vscode split pane
* Cal/Contacts/Mail Account
* apple Account signin
* darkreader site settings

## Inspiration and related

* [Mathias Bytnens dotfiles](https://github.com/mathiasbynens/dotfiles)
* [awesome-dotfiles](https://github.com/webpro/awesome-dotfiles)
* [dotfiles.github.com](https://github.com/dotfiles/dotfiles.github.com)
* [shell startup file order](https://shreevatsa.wordpress.com/2008/03/30/zshbash-startup-files-loading-order-bashrc-zshrc-etc/)
* [iCHAIT/awesome-macOS](https://github.com/iCHAIT/awesome-macOS)
* [jaywcjlove/awesome-mac](https://github.com/jaywcjlove/awesome-mac#readme)
* [serhii-londar/open-source-mac-os-apps](https://github.com/serhii-londar/open-source-mac-os-apps#readme)
* [awesome macos command line](https://github.com/herrbischoff/awesome-macos-command-line)

## Software I want to checkout or configure

* ln -s $HOME/.dotfiles/.mackup.cfg $HOME/.mackup.cfg
* https://github.com/webpro/awesome-dotfiles
* cask_args appdir: '/Applications'
* https://github.com/rcmdnk/homebrew-file/blob/master/docs/index.rst
* https://rogueamoeba.com/loopback/
* https://krisp.ai/
* brew install thefuck
* optional remove dockutil and others
* brew install git-extras
* brew install gh or hub?
* brew install direnv
* set beyondcompare as merge tool
* brew install diff-so-fancy
* brew install asciinema
* tmux
* powerline or zsh theme
* fsh
* FZF
* neofetch
* maybe [meeting notifier](https://github.com/leits/MeetingBar)
* clipboard manager maybe [flycut](https://github.com/TermiT/Flycut/blob/master/help.md)
* weather solution ie shell or bar [datweatherdo](https://github.com/inderdhir/DatWeatherDoe)
* cryptomator
* [VimMotion](https://github.com/dwarvesf/VimMotionApp)
* [macOS GateKeeper Helper](https://github.com/wynioux/macOS-GateKeeper-Helper)
* https://github.com/Mortennn/Dozer or https://github.com/dwarvesf/hidden or bartender
* tiling/grid solution? maybe [divvy](https://mizage.com/divvy/) or [Amethyst](https://github.com/ianyh/Amethyst)
* battery health informer maybe [fruitjuice](http://fruitjuiceapp.com/
)
* [displayplacer](https://github.com/jakehilborn/displayplacer) cli to adjust monitor placement
* (quick-look-plugins)[https://github.com/sindresorhus/quick-look-plugins]
* better [.gitconfig](https://github.com/mathiasbynens/dotfiles/blob/main/.gitconfig) or [.gitconfig](https://github.com/atomantic/dotfiles/blob/master/homedir/.gitconfig)
* source some cool [functions](https://github.com/mathiasbynens/dotfiles/blob/main/.functions) like local http
* [FinderSidebarEditor](https://github.com/robperc/FinderSidebarEditor)
* Alfred alternative or workflows [awesome-workflows](https://github.com/alfred-workflows/awesome-alfred-workflows),[workflows](https://github.com/zenorocha/alfred-workflows)
* brew install gs
brew install imagemagick --with-webp
brew install p7zip
brew install pv
brew install rename
brew install zopfli
brew "shellcheck"
cask "beardedspice"
cask "keepingyouawake"
```sh
#!/usr/bin/env bash

# Create a new git repo with one README commit and CD into it
function gitnr() { mkdir $1; cd $1; git init; touch README; git add README; git commit -mFirst-commit;}

# Do a Matrix movie effect of falling characters
function matrix1() {
echo -e "\e[1;40m" ; clear ; while :; do echo $LINES $COLUMNS $(( $RANDOM % $COLUMNS)) $(( $RANDOM % 72 )) ;sleep 0.05; done|gawk '{ letters="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*()"; c=$4; letter=substr(letters,c,1);a[$3]=0;for (x in a) {o=a[x];a[x]=a[x]+1; printf "\033[%s;%sH\033[2;32m%s",o,x,letter; printf "\033[%s;%sH\033[1;37m%s\033[0;0H",a[x],x,letter;if (a[x] >= $1) { a[x]=0; } }}'
}

function matrix2() {
echo -e "\e[1;40m" ; clear ; characters=$( jot -c 94 33 | tr -d '\n' ) ; while :; do echo $LINES $COLUMNS $(( $RANDOM % $COLUMNS)) $(( $RANDOM % 72 )) $characters ;sleep 0.05; done|gawk '{ letters=$5; c=$4; letter=substr(letters,c,1);a[$3]=0;for (x in a) {o=a[x];a[x]=a[x]+1; printf "\033[%s;%sH\033[2;32m%s",o,x,letter; printf "\033[%s;%sH\033[1;37m%s\033[0;0H",a[x],x,letter;if (a[x] >= $1) { a[x]=0; } }}'
}
```

## Automation dreams and TODO

* defaults write com.agilebits.onepassword7 "ShortcutRecorder BrowserActivation" -dict "keyChars" -string '\' "keyCharsIgnoringModifiers" -string '\' "keyCode" -int 42 "modifierFlags" -int 1048576 "modifiers" -int 256 "ShortcutRecorder GlobalLock", "ShortcutRecorder GlobalActivation", and "ShortcutRecorder BrowserActivation"
* Wake on keyboard not mouse
* Dual boot linux encrypted disk - always The Disk you inserted was not readable on startup
* Last login: Sun Jan 24 18:55:04 on ttys000
[oh-my-zsh] Insecure completion-dependent directories detected:
drwxrwxr-x  7 ashtonian  admin  224 Jan 23 16:11 /usr/local/share/zsh
drwxrwxr-x  4 ashtonian  admin  128 Jan 20 14:39 /usr/local/share/zsh/site-functions
* adjust default apps for mac extensions and default to vscode
* figureout t2 chip issue preventing vpn'd mac from using keyboard if route is present. [related hnews](https://news.ycombinator.com/item?id=24838816)
* init.sh uses comments to deliniate between laptop / desktop setups
* shell sync, search, backup
* shell history persistence, search, sync
* downloads sync, org
* setup startup apps script to open apps per a profile ie work -> vscode screen 1, iterm screen 2 vs personal
* find software to record screen(s) and audio
* desktop background + screen saver sync + setup per res
* .ssh backup/sync - security
* cron fetch (docker, git, gohome, npm, zsh, ohmyzsh, vim, + others)
* git/projects dir auto fetch
* code snippets solution
* regex tool solution
* multi screen/tiling improvement
* script hide all apps, empty trash
* opensource pocket, notion, todoist
* degoogle
  * destore android 
* kiwi mobile 
* default zoom rate
* amazon/shop price compare extension
* extension review
* alias for quickly initing repo with known gitignore and pushing to gh,bb,gitlab
* way to clone and archive n sync all star'd repos

Highlight:

* chrome
  ** replace toby?
  ** cluster?
* ff extensions
* vscode extensions
* vim extensions
* zsh extensions
* applications/shell scripts overview
* brew + brewfile, mackup, mas, dockutil, sidebar util

Watchlist: 

* [Keepa](https://chrome.google.com/webstore/detail/keepa-amazon-price-tracke/neebplgakaahbhdphmkckjjcegoiijjo?hl=en)
* [ChromeWebStoreSorter](https://github.com/ugur1yildiz/ChromeWebStoreSorter/blob/main/sorter.js)
* [Fakespot Fake Amazon Reviews and eBay Sellers](https://chrome.google.com/webstore/detail/fakespot-fake-amazon-revi/nakplnnackehceedgkgkokbgbmfghain)
* [Privacy Single Use physical or Digital cards](https://privacy.com/card-issuing)
* [Tab Wrangler](https://chrome.google.com/webstore/detail/tab-wrangler/egnjhciaieeiiohknchakcodbpgjnchh?hl=en)
* [Cluster Window Tab Manager](https://chrome.google.com/webstore/detail/cluster-window-tab-manage/aadahadfdmiibmdhfmpbeeebejmjnkef?hl=en) - move tabs between windows
* [Toby](https://chrome.google.com/webstore/detail/toby-for-chrome/hddnkoipeenegfoeaoibdmnaalmgkpip?hl=en) - nice tab 'session' manager. 
* [vimium](https://chrome.google.com/webstore/detail/vimium/dbepggeogbaibhgnhhndojpepiihcmeb?hl=en-US) - [source](https://github.com/philc/vimium/blob/master/README.md)
* [Chrome extension Source Viewer](https://chrome.google.com/webstore/detail/chrome-extension-source-v/jifpbeccnghkjeaalbbjmodiffmgedin?hl=en-US)

Brave Extensions: 

* [extension manager (aka switcher)](https://chrome.google.com/webstore/detail/extensions-manager-aka-sw/lpleipinonnoibneeejgjnoeekmbopbc?hl=en-US) - [fork](https://gitlab.com/jcrben-not-mine/extensions-manager-aka-switcher)
* [1password extension (Desktop version)](https://chrome.google.com/webstore/detail/1password-extension-deskt/aomjjhallfgjeglblehebfpbcfeobpgk)
* [bypass paywalls (source only)](https://github.com/iamadamdev/bypass-paywalls-chrome)
* [Adblock for youtube](https://chrome.google.com/webstore/detail/adblock-for-youtube/cmedhionkhpnakcndndgjdbohmhepckk/related)
* [simple-allow-copy](https://chrome.google.com/webstore/detail/simple-allow-copy/aefehdhdciieocakfobpaaolhipkcpgc) - [source](https://github.com/FallenMax/chrome-extension-allow-copy)
* [ublock origin](https://chrome.google.com/webstore/detail/ublock-origin/cjpalhdlnbpafiamejdnhcphjbkeiagm?hl=en) - [source](https://github.com/gorhill/uBlock#ublock-origin)
* [Smile Always](https://chrome.google.com/webstore/detail/smile-always/jgpmhnmjbhgkhpbgelalfpplebgfjmbf?hl=en)
* [clearURLS](https://chrome.google.com/webstore/detail/clearurls/lckanjgmijmafbedllaakclkaicjfmnk?hl=en)
* [dark reader](https://chrome.google.com/webstore/detail/dark-reader/eimadpbcbfnmbkopoojfekhnkhdbieeh/related?hl=en)
* [decentraleyes](https://chrome.google.com/webstore/detail/decentraleyes/ldpochfccmkkmhdbclfhpagapcfdljkj?hl=en)
* [privacy badger](https://chrome.google.com/webstore/detail/privacy-badger/pkehgijcmpdhfbdbbnkijodmdjhbjlgp?hl=en-US) - [source](https://github.com/EFForg/privacybadger/)
* [dont fuck with paste](https://chrome.google.com/webstore/detail/dont-fuck-with-paste/nkgllhigpcljnhoakjkgaieabnkmgdkb?hl=en-US) - [source](https://github.com/jswanner/DontFuckWithPaste)
* [https everywhere](https://chrome.google.com/webstore/detail/https-everywhere/gcbommkclmclpchllfjekcdonpmejbdp/related?hl=en) - [source]( https://github.com/efforg/https-everywhere)
* [json viewer](https://chrome.google.com/webstore/detail/json-viewer/gbmdgpbipfallnflgajpaliibnhdgobh?hl=en-US) - [source](https://github.com/tulios/json-viewer)
* [just read](https://chrome.google.com/webstore/detail/just-read/dgmanlpmmkibanfdgjocnabmcaclkmod/related?hl=en) - [source](https://github.com/ZachSaucier/Just-Read)
* [nordvpn](https://chrome.google.com/webstore/detail/nordvpn-%E2%80%94-1-vpn-chrome-ex/fjoaledfpmneenckfbpdfhkmimnjocfa?hl=en)
* [notion web clipper](https://chrome.google.com/webstore/detail/notion-web-clipper/knheggckgoiihginacbkhaalnibhilkk?hl=en) - [source](https://github.com/webclipper/web-clipper)
* [octotree](https://chrome.google.com/webstore/detail/octotree-github-code-tree/bkhaagjahfmjljalopjnoealnfndnagc) - [source](https://github.com/ovity/octotree)
* [Reddit Enhancement Suite](https://chrome.google.com/webstore/detail/reddit-enhancement-suite/kbmfpngjjgdllneeigpgjifpgocmfgmb?hl=en-US) - [source](https://github.com/honestbleeps/Reddit-Enhancement-Suite)
* [old reddit redirect](https://chrome.google.com/webstore/detail/old-reddit-redirect/dneaehbmnbhcippjikoajpoabadpodje?hl=en) - [source](https://github.com/tom-james-watson/old-reddit-redirect)
* [regexp download organizer](https://chrome.google.com/webstore/detail/regexp-download-organizer/oamembonjndgangicfphlckkdmagpjlg?hl=en) - [source](https://github.com/unintended/download-organizer-chrome-extension)
* [rescuetime](https://chrome.google.com/webstore/detail/rescuetime-for-chrome-and/bdakmnplckeopfghnlpocafcepegjeap?hl=en-US)
* [save to pocket](https://chrome.google.com/webstore/detail/save-to-pocket/niloccemoadcdkdjlinkgdfekeahmflj?hl=en-US) - [source](https://github.cobm/Pocket/extension-save-to-pocket)
* [sourcegraph](https://chrome.google.com/webstore/detail/sourcegraph/dgjhfomjieaadpoljlnidmbgkdffpack?hl=en) - [source](https://github.com/sourcegraph/sourcegraph/tree/main/client/browser)
* [switch for pihole](https://chrome.google.com/webstore/detail/switch-for-pihole/ngoafjpapneaopfkpboebcahajopcifi?hl=en-US) - [source](https://github.com/badsgahhl/pihole-browser-extension)
* [terms of service didn't read](https://chrome.google.com/webstore/detail/terms-of-service-didn%E2%80%99t-r/hjdoplcnndgiblooccencgcggcoihigg?hl=en) - [source](https://chrome.google.com/webstore/detail/terms-of-service-didn%E2%80%99t-r/hjdoplcnndgiblooccencgcggcoihigg/related?hl=en)
* [todoist for chrome](https://chrome.google.com/webstore/detail/todoist-for-chrome/jldhpllghnbhlbpcmnajkpdmadaolakh?hl=en)
* [ublock origin](https://chrome.google.com/webstore/detail/ublock-origin/cjpalhdlnbpafiamejdnhcphjbkeiagm?hl=en) - [source](https://github.com/gorhill/uBlock)
* [view image](https://chrome.google.com/webstore/detail/view-image/jpcmhcelnjdmblfmjabdeclccemkghjk?hl=en) - [source](https://github.com/bijij/ViewImage)
* [vuejs dev tools](https://chrome.google.com/webstore/detail/vuejs-devtools/nhdogjmejiglipccpnnnanhbledajbpd/related?hl=en-US) - [source](https://github.com/vuejs/vue-devtools)
* [wakatime](https://github.com/wakatime/chrome-wakatime) - [source](https://github.com/wakatime/chrome-wakatime)
* [zenhub for github](https://chrome.google.com/webstore/detail/zenhub-for-github/ogcgkffhplmphkaahpmffcafajaocjbd?hl=en-US)
* [ynab toolkit](https://chrome.google.com/webstore/detail/toolkit-for-ynab/lmhdkkhepllpnondndgpgclfjnlofgjl?hl=en) - [source](https://github.com/toolkit-for-ynab/toolkit-for-ynab/blob/master/docs/feature-list.md)
* [hacker news ux](https://chrome.google.com/webstore/detail/hacker-news-ux/chngbdmhgakoomomnnhfapkpbalpmhid?hl=en) - [source](https://github.com/volos/HackerNewsUX)

Safari: 

* [1password extension ()]()
* [adguard for safari](https://apps.apple.com/us/app/adguard-for-safari/id1440147259?mt=12)

Kiwi (Android):

* [ublock origin](https://chrome.google.com/webstore/detail/ublock-origin/cjpalhdlnbpafiamejdnhcphjbkeiagm?hl=en) - [source](https://github.com/gorhill/uBlock)
* [https everywhere](https://chrome.google.com/webstore/detail/https-everywhere/gcbommkclmclpchllfjekcdonpmejbdp/related?hl=en) - [source]( https://github.com/efforg/https-everywhere)
* [clearURLS](https://chrome.google.com/webstore/detail/clearurls/lckanjgmijmafbedllaakclkaicjfmnk?hl=en)
* [dark reader](https://chrome.google.com/webstore/detail/dark-reader/eimadpbcbfnmbkopoojfekhnkhdbieeh/related?hl=en)
* [decentraleyes](https://chrome.google.com/webstore/detail/decentraleyes/ldpochfccmkkmhdbclfhpagapcfdljkj?hl=en)
* [privacy badger](https://chrome.google.com/webstore/detail/privacy-badger/pkehgijcmpdhfbdbbnkijodmdjhbjlgp?hl=en-US) - [source](https://github.com/EFForg/privacybadger/)
* [bypass paywalls (source only)](https://github.com/iamadamdev/bypass-paywalls-chrome)
* [Reddit Enhancement Suite](https://chrome.google.com/webstore/detail/reddit-enhancement-suite/kbmfpngjjgdllneeigpgjifpgocmfgmb?hl=en-US) - [source](https://github.com/honestbleeps/Reddit-Enhancement-Suite)
* [old reddit redirect](https://chrome.google.com/webstore/detail/old-reddit-redirect/dneaehbmnbhcippjikoajpoabadpodje?hl=en) - [source](https://github.com/tom-james-watson/old-reddit-redirect)