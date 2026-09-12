# Anthony's Ubee512 Launcher for macOS

Current Mac version: **Anthony's Ubee512 Launcher v1_6**

## Download

Two macOS builds are available. Choose the version that matches your Mac.

### Apple Silicon Macs

For Macs using Apple Silicon processors such as M1, M2, M3 or M4:

```text
AnthonysUBee512Launcher-Mac-ARM-v1_6.zip
```

### Intel Macs

For Macs using an Intel processor:

```text
AnthonysUBee512Launcher-Mac-Intel-v1_6.zip
```

If you are unsure which processor your Mac has, choose **About This Mac** from the Apple menu and check the processor or chip information.

Older Mac builds have been moved into the `archive/` folder so the current downloads are easier to identify.

## What's New in v1_6

* Display/Performance landing tab
* selectable video and monitor modes
* safe preset Microbee aspect ratios
* default launcher-branded emulator title with a custom override
* clock-speed presets from 1 MHz to 150 MHz and Turbo mode
* scrollable Advanced tabs for smaller windows and varied display scaling
* restored macOS-specific keyboard help for MacBook and Apple keyboards

## System Notes

The launcher does **not** include uBee512 itself, ROMs, disk images or tape files.

You will need a working uBee512 installation and your uBee512 data folder set up separately.

A typical uBee512 data folder contains folders such as:

```text
~/.ubee512/roms
~/.ubee512/disks
~/.ubee512/tapes
```

### Apple Silicon Build

The ARM build is intended for Apple Silicon Macs.

### Intel Build

The Intel build is a native 64-bit `x86_64` application intended for Intel Macs.

The launcher and user interface have been tested on an Intel Mac running macOS High Sierra 10.13.6. The uBee512 emulator itself was not installed on that test machine, so launching the emulator from this Intel build has not yet been fully verified.

## First Launch on macOS

The macOS builds are not currently Apple-notarised, so macOS may block the app the first time it is opened.

If macOS blocks the app:

1. Open **System Settings** or **System Preferences**, depending on your macOS version.
2. Go to **Privacy & Security** or the equivalent security settings.
3. Look for the blocked application message.
4. Choose **Open Anyway** if available.

You may also be able to right-click the app and choose **Open** the first time.

## How to Use

1. Download and unzip the appropriate Mac build.
2. Move the app wherever you want to keep it.
3. Open the launcher.
4. Use **Auto setup** where possible.
5. Check that the launcher can find your uBee512 executable and uBee512 data folder.
6. Scan for ROMs, disks and tapes.
7. Launch uBee512.

## Important Limitations

The Mac builds are newer and less extensively tested than the Linux version.

The launcher should be treated as a helper for an existing uBee512 installation, not as a full uBee512 installer.

If the emulator cannot find required ROMs or boot disks, check your uBee512 installation and `~/.ubee512` setup first.

## Archived Builds

Older Mac builds are kept in the `archive/` folder for reference.

Most users should download one of the current v1_6 builds from this folder rather than an archived version.
