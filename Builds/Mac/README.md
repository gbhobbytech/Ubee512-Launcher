### macOS security note

The macOS build is not currently Apple-notarised, so macOS may block it the first time it is opened.

If the app is blocked, try:

1. Right-click the app and choose **Open**
2. Confirm that you want to open it

If needed, remove the quarantine flag from Terminal:

```bash
xattr -dr com.apple.quarantine "/path/to/Anthonys Ubee512 Launcher.app"
```
The launcher expects the uBee512 emulator and support files to be set up separately.


For your own testing, the command would be:

```bash
xattr -dr com.apple.quarantine "Anthonys Ubee512 Launcher.app"
```
When downloading from GitHub, use **Download raw file** for the ZIP.
Do not right-click and save the GitHub preview page.
