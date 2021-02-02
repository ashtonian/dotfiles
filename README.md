# dotfiles

macOS & windows dotfiles & post install scripts - better defaults, productive os, awesome tools.

## macOS Setup

This will initialize a freshly installed Mac OS (catalina) instance with all of my applications, cli tools, and adjust some basic operating system settings.

### Instructions

// TODOO:

## App Settings Highlights n Notes

### Global Shortcuts

* 1password
* Alfred
* Cheetsheet
* Email/Cal/Contacts
* move screens spaces
* Notion
* Record
* Screenshot
* Timer (horo)
* Todoist
* yoink

### iTerm2 Settings Highlights

#### Keymap

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

#### Text

* Cursor -> :radio_button: Box, :ballot_box_with_check: Blinking Cursor
* Text Rendering -> :ballot_box_with_check: Draw bold text in bold font, :ballot_box_with_check: Italic text, Use thin strokes for anti-aliased text: Always, :ballot_box_with_check: Use built-in Powerline glyphs, :ballot_box_with_check: Enable subpixel anti-aliasing
* Unicde -> :ballot_box_with_check: Use unicde version 9+ widths
* Font -> FiraCode Nerd Font, Regular, 15, :ballot_box_with_check: Use ligatures

### Brave Extensions

* [1password extension (Desktop version)](https://chrome.google.com/webstore/detail/1password-extension-deskt/aomjjhallfgjeglblehebfpbcfeobpgk)
* [Adblock for youtube](https://chrome.google.com/webstore/detail/adblock-for-youtube/cmedhionkhpnakcndndgjdbohmhepckk/related)
* [bypass paywalls (source only)](https://github.com/iamadamdev/bypass-paywalls-chrome)
* [clearURLS](https://chrome.google.com/webstore/detail/clearurls/lckanjgmijmafbedllaakclkaicjfmnk?hl=en)
* [dark reader](https://chrome.google.com/webstore/detail/dark-reader/eimadpbcbfnmbkopoojfekhnkhdbieeh/related?hl=en)
* [decentraleyes](https://chrome.google.com/webstore/detail/decentraleyes/ldpochfccmkkmhdbclfhpagapcfdljkj?hl=en)
* [dont fuck with paste](https://chrome.google.com/webstore/detail/dont-fuck-with-paste/nkgllhigpcljnhoakjkgaieabnkmgdkb?hl=en-US) - [source](https://github.com/jswanner/DontFuckWithPaste)
* [extension manager (aka switcher)](https://chrome.google.com/webstore/detail/extensions-manager-aka-sw/lpleipinonnoibneeejgjnoeekmbopbc?hl=en-US) - [fork](https://gitlab.com/jcrben-not-mine/extensions-manager-aka-switcher)
* [hacker news ux](https://chrome.google.com/webstore/detail/hacker-news-ux/chngbdmhgakoomomnnhfapkpbalpmhid?hl=en) - [source](https://github.com/volos/HackerNewsUX)
* [https everywhere](https://chrome.google.com/webstore/detail/https-everywhere/gcbommkclmclpchllfjekcdonpmejbdp/related?hl=en) - [source](https://github.com/efforg/https-everywhere)
* [json viewer](https://chrome.google.com/webstore/detail/json-viewer/gbmdgpbipfallnflgajpaliibnhdgobh?hl=en-US) - [source](https://github.com/tulios/json-viewer)
* [just read](https://chrome.google.com/webstore/detail/just-read/dgmanlpmmkibanfdgjocnabmcaclkmod/related?hl=en) - [source](https://github.com/ZachSaucier/Just-Read)
* [nordvpn](https://chrome.google.com/webstore/detail/nordvpn-%E2%80%94-1-vpn-chrome-ex/fjoaledfpmneenckfbpdfhkmimnjocfa?hl=en)
* [notion web clipper](https://chrome.google.com/webstore/detail/notion-web-clipper/knheggckgoiihginacbkhaalnibhilkk?hl=en) - [source](https://github.com/webclipper/web-clipper)
* [octotree](https://chrome.google.com/webstore/detail/octotree-github-code-tree/bkhaagjahfmjljalopjnoealnfndnagc) - [source](https://github.com/ovity/octotree)
* [old reddit redirect](https://chrome.google.com/webstore/detail/old-reddit-redirect/dneaehbmnbhcippjikoajpoabadpodje?hl=en) - [source](https://github.com/tom-james-watson/old-reddit-redirect)
* [open-in-iina](https://chrome.google.com/webstore/detail/open-in-iina/pdnojahnhpgmdhjdhgphgdcecehkbhfo)
* [privacy badger](https://chrome.google.com/webstore/detail/privacy-badger/pkehgijcmpdhfbdbbnkijodmdjhbjlgp?hl=en-US) - [source](https://github.com/EFForg/privacybadger/)
* [Reddit Enhancement Suite](https://chrome.google.com/webstore/detail/reddit-enhancement-suite/kbmfpngjjgdllneeigpgjifpgocmfgmb?hl=en-US) - [source](https://github.com/honestbleeps/Reddit-Enhancement-Suite)
* [regexp download organizer](https://chrome.google.com/webstore/detail/regexp-download-organizer/oamembonjndgangicfphlckkdmagpjlg?hl=en) - [source](https://github.com/unintended/download-organizer-chrome-extension)
* [rescuetime](https://chrome.google.com/webstore/detail/rescuetime-for-chrome-and/bdakmnplckeopfghnlpocafcepegjeap?hl=en-US)
* [save to pocket](https://chrome.google.com/webstore/detail/save-to-pocket/niloccemoadcdkdjlinkgdfekeahmflj?hl=en-US) - [source](https://github.cobm/Pocket/extension-save-to-pocket)
* [simple-allow-copy](https://chrome.google.com/webstore/detail/simple-allow-copy/aefehdhdciieocakfobpaaolhipkcpgc) - [source](https://github.com/FallenMax/chrome-extension-allow-copy)
* [Smile Always](https://chrome.google.com/webstore/detail/smile-always/jgpmhnmjbhgkhpbgelalfpplebgfjmbf?hl=en)
* [sourcegraph](https://chrome.google.com/webstore/detail/sourcegraph/dgjhfomjieaadpoljlnidmbgkdffpack?hl=en) - [source](https://github.com/sourcegraph/sourcegraph/tree/main/client/browser)
* [switch for pihole](https://chrome.google.com/webstore/detail/switch-for-pihole/ngoafjpapneaopfkpboebcahajopcifi?hl=en-US) - [source](https://github.com/badsgahhl/pihole-browser-extension)
* [terms of service didn't read](https://chrome.google.com/webstore/detail/terms-of-service-didn%E2%80%99t-r/hjdoplcnndgiblooccencgcggcoihigg?hl=en) - [source](https://chrome.google.com/webstore/detail/terms-of-service-didn%E2%80%99t-r/hjdoplcnndgiblooccencgcggcoihigg/related?hl=en)
* [todoist for chrome](https://chrome.google.com/webstore/detail/todoist-for-chrome/jldhpllghnbhlbpcmnajkpdmadaolakh?hl=en)
* [ublock origin](https://chrome.google.com/webstore/detail/ublock-origin/cjpalhdlnbpafiamejdnhcphjbkeiagm?hl=en) - [source](https://github.com/gorhill/uBlock)
* [ublock origin](https://chrome.google.com/webstore/detail/ublock-origin/cjpalhdlnbpafiamejdnhcphjbkeiagm?hl=en) - [source](https://github.com/gorhill/uBlock#ublock-origin)
* [view image](https://chrome.google.com/webstore/detail/view-image/jpcmhcelnjdmblfmjabdeclccemkghjk?hl=en) - [source](https://github.com/bijij/ViewImage)
* [vuejs dev tools](https://chrome.google.com/webstore/detail/vuejs-devtools/nhdogjmejiglipccpnnnanhbledajbpd/related?hl=en-US) - [source](https://github.com/vuejs/vue-devtools)
* [wakatime](https://github.com/wakatime/chrome-wakatime) - [source](https://github.com/wakatime/chrome-wakatime)
* [ynab toolkit](https://chrome.google.com/webstore/detail/toolkit-for-ynab/lmhdkkhepllpnondndgpgclfjnlofgjl?hl=en) - [source](https://github.com/toolkit-for-ynab/toolkit-for-ynab/blob/master/docs/feature-list.md)
* [zenhub for github](https://chrome.google.com/webstore/detail/zenhub-for-github/ogcgkffhplmphkaahpmffcafajaocjbd?hl=en-US)

### Safari

* [adguard for safari](https://apps.apple.com/us/app/adguard-for-safari/id1440147259?mt=12)
* [1password extension ()]()

### Kiwi (Android)

* [bypass paywalls (source only)](https://github.com/iamadamdev/bypass-paywalls-chrome)
* [clearURLS](https://chrome.google.com/webstore/detail/clearurls/lckanjgmijmafbedllaakclkaicjfmnk?hl=en)
* [dark reader](https://chrome.google.com/webstore/detail/dark-reader/eimadpbcbfnmbkopoojfekhnkhdbieeh/related?hl=en)
* [decentraleyes](https://chrome.google.com/webstore/detail/decentraleyes/ldpochfccmkkmhdbclfhpagapcfdljkj?hl=en)
* [https everywhere](https://chrome.google.com/webstore/detail/https-everywhere/gcbommkclmclpchllfjekcdonpmejbdp/related?hl=en) - [source]( https://github.com/efforg/https-everywhere)
* [old reddit redirect](https://chrome.google.com/webstore/detail/old-reddit-redirect/dneaehbmnbhcippjikoajpoabadpodje?hl=en) - [source](https://github.com/tom-james-watson/old-reddit-redirect)
* [privacy badger](https://chrome.google.com/webstore/detail/privacy-badger/pkehgijcmpdhfbdbbnkijodmdjhbjlgp?hl=en-US) - [source](https://github.com/EFForg/privacybadger/)
* [Reddit Enhancement Suite](https://chrome.google.com/webstore/detail/reddit-enhancement-suite/kbmfpngjjgdllneeigpgjifpgocmfgmb?hl=en-US) - [source](https://github.com/honestbleeps/Reddit-Enhancement-Suite)
* [ublock origin](https://chrome.google.com/webstore/detail/ublock-origin/cjpalhdlnbpafiamejdnhcphjbkeiagm?hl=en) - [source](https://github.com/gorhill/uBlock)

## Inspiration and Resources

* [awesome alfred workflows](https://github.com/alfred-workflows/awesome-alfred-workflows), [workflows](https://github.com/zenorocha/alfred-workflows)
* [awesome macos command line](https://github.com/herrbischoff/awesome-macos-command-line)
* [awesome-bash-alias](https://github.com/vikaskyadav/awesome-bash-alias)
* [awesome-dotfiles](https://github.com/webpro/awesome-dotfiles)
* [defaults](https://github.com/aerobounce/defaults.sh) - convert user defaults (plist) into shell script with ease!
* [dotfiles.github.com](https://github.com/dotfiles/dotfiles.github.com)
* [iCHAIT/awesome-macOS](https://github.com/iCHAIT/awesome-macOS)
* [jaywcjlove/awesome-mac](https://github.com/jaywcjlove/awesome-mac#readme)
* [Mathias Bytnens dotfiles](https://github.com/mathiasbynens/dotfiles)
* [quick look plugins](https://github.com/sindresorhus/quick-look-plugins)
* [serhii-londar/open-source-mac-os-apps](https://github.com/serhii-londar/open-source-mac-os-apps#readme)
* [shell startup file order](https://shreevatsa.wordpress.com/2008/03/30/zshbash-startup-files-loading-order-bashrc-zshrc-etc/)
* [vraravam brewfile](https://gist.github.com/vraravam/5e28ca1720c9dddacdc0e6db61e093fe)
* [vraravam os x defaults gist](https://gist.github.com/vraravam/8c9eae91a3750bed86b81e3a4711f842)

## Evaluation & Watch List

* [appcleaner](https://freemacsoft.net/appcleaner/)
* [asdf](https://asdf-vm.com/#/) - multi-cli version manager
* [bashhub](https://github.com/rcaloras/bashhub-client) - bashhub eery terminal command accross all systems and provides powerful querying across all
* [boilr](https://github.com/tmrts/boilr) - bootstrapper
* [brew-file](https://github.com/rcmdnk/homebrew-file/blob/master/docs/index.rst)
* [espanso](https://github.com/federico-terzi/espanso) - text expander
* [ferdi](https://getferdi.com/) - unified notifications - no signal
* [findergo](https://github.com/onmyway133/FinderGo) - add open to term to finder
* [how2](https://github.com/santinic/how2) - a sh snippet search util with natural language
* [krisp.ai](https://krisp.ai/pricing/) - Mute background noise, $$ tho
* [ls++](https://github.com/trapd00r/ls--),[lsp](https://raw.githubusercontent.com/dborzov/lsp/screenshots/symlinks.png) - wise to alias?
* [macOS GateKeeper Helper](https://github.com/wynioux/macOS-GateKeeper-Helper)
* [micktagger](https://micktagger.app/) - easy to add song to multiple sptofiy playlists
* [moom](https://manytricks.com/moom/),[divvy](https://mizage.com/divvy/),[rectangle](https://rectangleapp.com/) or [Amethyst](https://github.com/ianyh/Amethyst), [Magnet](https://apps.apple.com/ca/app/magnet/id441258766?mt=12), [bettersnaptool](https://folivora.ai/bettersnaptool),[cinch](https://apps.apple.com/fr/app/cinch/id412529613?mt=12) - tiling solution potentially with solution to move screens/spaces across monitor.
* [musicbrainz](https://picard.musicbrainz.org/) - music file tagger
* [neovim](https://neovim.io/)
* [pre-commit hooks](https://pre-commit.com/hooks.html)
* [prettyping](https://denilson.sa.nom.br/prettyping/) - wrap around ping, wise to alias
* [Privacy Single Use physical or Digital cards](https://privacy.com/card-issuing)
* [raycast](https://raycast.com/) - cool alfred like but for web apps, only a few apps.
* [selfcontrol](https://selfcontrolapp.com/), [focus](https://heyfocus.com/) - currently use rescuetimes version, like this not sure if this is better
* [slack keep presence](https://www.rubydoc.info/gems/slack-keep-presence/0.1.14)
* [soulver](https://www.acqualia.com/soulver/) - numi alternative
* [sshrc](https://github.com/cdown/sshrc) - Bring your .bashrc, .vimrc, etc. with you when you ssh
* [VimMotion](https://github.com/dwarvesf/VimMotionApp)

Extensions:

* [Chrome extension Source Viewer](https://chrome.google.com/webstore/detail/chrome-extension-source-v/jifpbeccnghkjeaalbbjmodiffmgedin?hl=en-US)
* [ChromeWebStoreSorter](https://github.com/ugur1yildiz/ChromeWebStoreSorter/blob/main/sorter.js)
* [Cluster Window Tab Manager](https://chrome.google.com/webstore/detail/cluster-window-tab-manage/aadahadfdmiibmdhfmpbeeebejmjnkef?hl=en) - move tabs between windows
* [Fakespot Fake Amazon Reviews and eBay Sellers](https://chrome.google.com/webstore/detail/fakespot-fake-amazon-revi/nakplnnackehceedgkgkokbgbmfghain)
* [fruitjuice](http://fruitjuiceapp.com/) - $$
* [hidden](https://github.com/dwarvesf/hidden) - bartender alt opensource
* [Keepa](https://chrome.google.com/webstore/detail/keepa-amazon-price-tracke/neebplgakaahbhdphmkckjjcegoiijjo?hl=en)
* [Tab Wrangler](https://chrome.google.com/webstore/detail/tab-wrangler/egnjhciaieeiiohknchakcodbpgjnchh?hl=en)
* [Toby](https://chrome.google.com/webstore/detail/toby-for-chrome/hddnkoipeenegfoeaoibdmnaalmgkpip?hl=en) - nice tab 'session' manager.
* [vimium](https://chrome.google.com/webstore/detail/vimium/dbepggeogbaibhgnhhndojpepiihcmeb?hl=en-US) - [source](https://github.com/philc/vimium/blob/master/README.md)

## Manual Work

* Signin to Apple Account, Mail|Contacts|Calendar, RescueTime
* VSCode, Alfred, Brave Sync Setup
* Install [bypass-paywalls-chrome](https://github.com/iamadamdev/bypass-paywalls-chrome.git) - [possible solution](https://stackoverflow.com/questions/16800696/how-install-crx-chrome-extension-via-command-line)

## Automation dreams and TODO

* https://github.com/Lord-Kamina/SwiftDefaultApps/issues/29 -> adjusts default apps, web app, programming -> vscode, video vlc, flac vox,  ssh,telnet + others -> iterm.

* add dev apps to security, privacy "dev tools" category to avoid security policy.
* TODO: vscode settings sync
* TODO: iterm2 plist gen
* TODO: highlight flux, vscode,
* TODO: review dropbox mackup
* when big sur is ready use disable menu bar [autohide](https://www.howtogeek.com/700398/how-to-automatically-hide-or-show-the-menu-bar-on-a-mac/) and adjust settings
* Wake on keyboard not mouse
* Dual boot linux encrypted disk - always The Disk you inserted was not readable on startup
* figureout t2 chip issue preventing vpn'd mac from using keyboard if route is present. [related hnews](https://news.ycombinator.com/item?id=24838816)
* shellsync, search, backup, history persistence, search, sync
* desktop background + screen saver sync + setup per res
* soulution - cli journal ? jyputer
* solution - sshkey, knownhosts manager/sync - is it wise?
* solution - vscode snippets
* solution - script hide all apps, empty trash, open apps in screen per a profile ie work -> vscode screen 1, iterm screen 2 vs personal
* cron fetch (docker, git, gohome, alfred, npm, zsh, ohmyzsh, vim, + others
* horo, monosnap, ohmystar workflow
* git/projects dir auto fetchs
* TODO: sync and update git clone https://github.com/dracula/iterm.git
* A program tried to load new system extension(s) signed by “MATT INGALLS”.  If you want to enable these extensions, open Security & Privacy System Preferences.

Alfred Workflows:

Builtins: System commands ie Logout, Sleep ect.. | Clipboard manager

* [advanced-google-maps-alfred-workflow?](https://github.com/stuartcryan/advanced-google-maps-alfred-workflow)
* [alfred-bluetooth-workflow](https://github.com/tilmanginzel/alfred-bluetooth-workflow)
* [alfred-convert](https://github.com/deanishe/alfred-convert)
* [alfred-fkill](https://github.com/SamVerschueren/alfred-fkill)
* [alfred-pocket](https://github.com/fniephaus/alfred-pocket)
* [alfred-sshs](https://github.com/deanishe/alfred-sshs)
* [alfred-vpn](https://github.com/stve/alfred-vpn)
* [Alfred-WordSearch](https://github.com/isaacpz/Alfred-WordSearch)
* [alfred-workflow-todoist](https://github.com/moranje/alfred-workflow-todoist)
* [alfred-workflows/tree/master/StrongPassword](https://github.com/vitorgalvao/alfred-workflows/tree/master/StrongPassword)
* [dash](https://www.alfredapp.com/blog/productivity/dash-quicker-api-documentation-search/)
* [flush-dns-106-110](https://www.packal.org/workflow/flush-dns-106-110)
* [moment](https://www.packal.org/workflow/moment)
* [notion-search-alfred-workflow/](https://github.com/wrjlewis/notion-search-alfred-workflow/)
* [numi](https://www.packal.org/workflow/numi)
* [pocket-alfred](https://www.packal.org/workflow/pocket-alfred)



* [2gua.rainbow-brackets](https://marketplace.visualstudio.com/items?itemName=2gua.rainbow-brackets)
* [766b.go-outliner](https://marketplace.visualstudio.com/items?itemName=766b.go-outliner)
* [aaronpowell.vscode-profile-switcher](https://marketplace.visualstudio.com/items?itemName=aaronpowell.vscode-profile-switcher)
* [abusaidm.html-snippets](https://marketplace.visualstudio.com/items?itemName=abusaidm.html-snippets)
* [adpyke.codesnap](https://marketplace.visualstudio.com/items?itemName=adpyke.codesnap)
* [AlanWalk.markdown-toc](https://marketplace.visualstudio.com/items?itemName=AlanWalk.markdown-toc)
* [alefragnani.project-manager](https://marketplace.visualstudio.com/items?itemName=alefragnani.project-manager)
* [bajdzis.vscode-database](https://marketplace.visualstudio.com/items?itemName=bajdzis.vscode-database)
* [christian-kohler.npm-intellisense](https://marketplace.visualstudio.com/items?itemName=christian-kohler.npm-intellisense)
* [christian-kohler.path-intellisense](https://marketplace.visualstudio.com/items?itemName=christian-kohler.path-intellisense)
* [CoenraadS.bracket-pair-colorizer](https://marketplace.visualstudio.com/items?itemName=CoenraadS.bracket-pair-colorizer)
* [d-koppenhagen.file-tree-to-text-generator](https://marketplace.visualstudio.com/items?itemName=d-koppenhagen.file-tree-to-text-generator)
* [darkriszty.markdown-table-prettify](https://marketplace.visualstudio.com/items?itemName=darkriszty.markdown-table-prettify)
* [DavidAnson.vscode-markdownlint](https://marketplace.visualstudio.com/items?itemName=DavidAnson.vscode-markdownlint)
* [deerawan.vscode-dash](https://marketplace.visualstudio.com/items?itemName=deerawan.vscode-dash)
* [eamodio.gitlens](https://marketplace.visualstudio.com/items?itemName=eamodio.gitlens)
* [fabiospampinato.vscode-markdown-todo](https://marketplace.visualstudio.com/items?itemName=fabiospampinato.vscode-markdown-todo)
* [fabiospampinato.vscode-projects-plus-todo-plus](https://marketplace.visualstudio.com/items?itemName=fabiospampinato.vscode-projects-plus-todo-plus)
* [fabiospampinato.vscode-projects-plus](https://marketplace.visualstudio.com/items?itemName=fabiospampinato.vscode-projects-plus)
* [fabiospampinato.vscode-todo-plus](https://marketplace.visualstudio.com/items?itemName=fabiospampinato.vscode-todo-plus)
* [file-icons.file-icons](https://marketplace.visualstudio.com/items?itemName=file-icons.file-icons)
* [flesler.url-encode](https://marketplace.visualstudio.com/items?itemName=flesler.url-encode)
* [GitHub.vscode-pull-request-github](https://marketplace.visualstudio.com/items?itemName=GitHub.vscode-pull-request-github)
* [golang.Go](https://marketplace.visualstudio.com/items?itemName=golang.Go)
* [Gruntfuggly.todo-tree](https://marketplace.visualstudio.com/items?itemName=Gruntfuggly.todo-tree)
* [HashiCorp.terraform](https://marketplace.visualstudio.com/items?itemName=HashiCorp.terraform)
* [marclipovsky.string-manipulation](https://marketplace.visualstudio.com/items?itemName=marclipovsky.string-manipulation)
* [mikestead.dotenv](https://marketplace.visualstudio.com/items?itemName=mikestead.dotenv)
* [mitchdenny.ecdc](https://marketplace.visualstudio.com/items?itemName=mitchdenny.ecdc)
* [mohsen1.prettify-json](https://marketplace.visualstudio.com/items?itemName=mohsen1.prettify-json)
* [ms-kubernetes-tools.vscode-kubernetes-tools](https://marketplace.visualstudio.com/items?itemName=ms-kubernetes-tools.vscode-kubernetes-tools)
* [ms-toolsai.jupyter](https://marketplace.visualstudio.com/items?itemName=ms-toolsai.jupyter)
* [nmsmith89.incrementor](https://marketplace.visualstudio.com/items?itemName=nmsmith89.incrementor)
* [octref.vetur](https://marketplace.visualstudio.com/items?itemName=octref.vetur)
* [piotrpalarz.vscode-gitignore-generator](https://marketplace.visualstudio.com/items?itemName=piotrpalarz.vscode-gitignore-generator)
* [qcz.text-power-tools](https://marketplace.visualstudio.com/items?itemName=qcz.text-power-tools)
* [redhat.vscode-yaml](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml)
* [run-at-scale.terraform-doc-snippets](https://marketplace.visualstudio.com/items?itemName=run-at-scale.terraform-doc-snippets)
* [sdras.vue-vscode-snippets](https://marketplace.visualstudio.com/items?itemName=sdras.vue-vscode-snippets)
* [Shan.code-settings-sync](https://marketplace.visualstudio.com/items?itemName=Shan.code-settings-sync)
* [streetsidesoftware.code-spell-checker](https://marketplace.visualstudio.com/items?itemName=streetsidesoftware.code-spell-checker)
* [tamasfe.even-better-toml](https://marketplace.visualstudio.com/items?itemName=tamasfe.even-better-toml)
* [tht13.html-preview-vscode](https://marketplace.visualstudio.com/items?itemName=tht13.html-preview-vscode)
* [Tyriar.sort-lines](https://marketplace.visualstudio.com/items?itemName=Tyriar.sort-lines)
* [vscode-icons-team.vscode-icons](https://marketplace.visualstudio.com/items?itemName=vscode-icons-team.vscode-icons)
* [WakaTime.vscode-wakatime](https://marketplace.visualstudio.com/items?itemName=WakaTime.vscode-wakatime)
* [wayou.vscode-todo-highlight](https://marketplace.visualstudio.com/items?itemName=wayou.vscode-todo-highlight)
* [wmaurer.vscode-jumpy](https://marketplace.visualstudio.com/items?itemName=wmaurer.vscode-jumpy)
* [xabikos.JavaScriptSnippets](https://marketplace.visualstudio.com/items?itemName=xabikos.JavaScriptSnippets)
* [yzhang.markdown-all-in-one](https://marketplace.visualstudio.com/items?itemName=yzhang.markdown-all-in-one)
* [zxh404.vscode-proto3](https://marketplace.visualstudio.com/items?itemName=zxh404.vscode-proto3)
vscode: