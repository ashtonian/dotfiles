
* Install macos. 
* verify trim, mem size, apfs. 
* update macos and sign into apple + google accounts. 
* cleanup dock
* adjust energy settings
* adjust topbar
* homewbrew
* brew install
* mackup restore

```zsh
# prereq
sudo xcode-select --install

# install homebrew 
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"

# install brewfile dependencies including zsh
brew bundle

# install oh my zsh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

# set zsh as default shell for user 
chsh -s /bin/zsh

# for py
pip install ipython
```
