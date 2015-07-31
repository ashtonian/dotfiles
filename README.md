# Windows Bootstrapper
This is a bootstrap script for windows 

## Choco

##### Development
```
choco install poshgit
choco install git.install
choco install hg
choco install posh-hg
choco install sourcetree
choco install wireshark
choco install fiddler
choco install nodejs.install
choco install beyondcompare
choco install nugetpackageexplorer
choco install python
choco install procexp
choco install conemu
choco install curl
# choco install visualstudio2013ultimate
# choco install resharper
# choco install ncrunch-vs2015
# choco install pycharm
# choco install webstorm
```

##### Standard Util
```
choco install filezilla
choco install winscp.install
choco install ccleaner
choco install windirstat
choco install flashplayerplugin
choco install flashplayeractivex
choco install javaruntime
choco install adobereader
choco install 7zip.install
choco install vlc
choco install paint.net
choco install google-chrome-x64
choco install notepadplusplus.install
choco install sublimetext3
choco install f.lux
choco install dropbox
choco install googledrive
```

##### Extended Util
```
choco install putty
choco install malwarebytes
choco install avastfreeantivirus
choco install cpu-z
choco install chocolateygui
choco install virtualbox
choco install deluge
choco install virtualclonedrive
choco install imgburn
```

##### Entertainment/Other
```
choco install evernote
choco install spotify
choco install steam
choco install handbrake.install
```

## OneGet (Choco repo is currently broken) 
##### OnGet Resources: 
- https://github.com/PowerShell/PackageManagementProviderResource
- https://github.com/OneGet/oneget/wiki/cmdlets
- https://technet.microsoft.com/en-us/library/dn890703.aspx
- https://chocolatey.org/

##### Starter Code: 
```
Get-PackageProvider –Name Chocolatey -ForceBootstrap
Set-PackageSource -Name chocolatey -Trusted 

Install-Package f.lux
Install-Package google-chrome-x64
```
