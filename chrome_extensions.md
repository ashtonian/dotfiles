# Chrome Extensions

No browser inventory is checked in here. To export the Default profile from an
interactive shell, choose the browser explicitly:

```sh
chrome_list_ext_md --browser chrome -o /tmp/chrome-extensions.md
```

Supported browser values are `chrome`, `brave`, and `vivaldi`. Other profiles
are not included. Review the output before publishing; an installed-extension
list can reveal work tools or personal services. This export is a snapshot and
does not install or synchronize extensions.
