
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