# Windows Post Install Script
This is a bootstrap script for windows.

## Choco
```
choco feature enable -n allowGlobalConfirmation
```

###### Standard Development: 
```
choco install poshgit
choco install git.install
choco install hg
choco install posh-hg
choco install sourcetree
# choco install visualstudio2015community
# choco install resharper
# choco install ncrunch-vs2015
choco install beyondcompare
choco install fiddler
```

###### Extended Development: 
```
choco install babun
choco install conemu
choco install wireshark
choco install nodejs.install
choco install nugetpackageexplorer
choco install procexp
choco install curl
```

###### Standard Util:
```
choco install google-chrome-x64
choco install f.lux
choco install windirstat
choco install javaruntime
choco install 7zip.install
choco install vlc
choco install paint.net
choco install googledrive
choco install atom
choco install filezilla
choco install winscp.install
```

###### Extended Util:
```
choco install dropbox
choco install cpu-z
choco install deluge
choco install putty
choco install virtualclonedrive
choco install imgburn
choco install malwarebytes
choco install avastfreeantivirus
choco install chocolateygui
choco install virtualbox
choco install adobereader
choco install ccleaner
choco install flashplayerplugin
choco install flashplayeractivex
```

###### Entertainment/Other:
```
choco install evernote
choco install spotify
choco install steam
choco install handbrake.install
```

## OneGet (Choco repo is currently broken) 
###### OnGet Resources: 
- https://github.com/PowerShell/PackageManagementProviderResource
- https://github.com/OneGet/oneget/wiki/cmdlets
- https://technet.microsoft.com/en-us/library/dn890703.aspx
- https://chocolatey.org/

###### Starter Code: 
```
Get-PackageProvider –Name Chocolatey -ForceBootstrap
Set-PackageSource -Name chocolatey -Trusted 

Install-Package f.lux
Install-Package google-chrome-x64
```
