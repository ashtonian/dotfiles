# WindowsBootStrapper
This is a bootstrap script for windows using OneGet/PackageManagement in win 10+ or windows management framework.

Resources: 
https://github.com/PowerShell/PackageManagementProviderResource
https://github.com/OneGet/oneget/wiki/cmdlets
https://technet.microsoft.com/en-us/library/dn890703.aspx
https://chocolatey.org/


Get-PackageProvider –Name Chocolatey -ForceBootstrap -Trusted
Set-PackageSource -Name chocolatey -Trusted 

Install-Package f.lux
Install-Package google-chrome-x64
