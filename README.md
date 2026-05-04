# Ubee512 Launcher

A simple launcher for Ubee512, tested on both Windows and Linux.

## What it does

- Remembers emulator, library, and data paths
- Scans for ROMs, disk images, and tape files
- Launches Ubee512 with selected disks and settings
- Shows the exact command before launch
- Supports printer output workflow
- Includes basic CP/M tools integration

## Important note

This launcher can run external tools and modify CP/M disk images. Back up disk images before writing files to them.

ROMs, disk images, emulator binaries, and third-party tools may have their own licences. Only include or share files you have permission to distribute.

## Folders

- `source/` contains the Python source code.
- `builds/windows/` contains the tested Windows build.
- `builds/linux/` contains the tested Linux build.

## Windows

Notes

The Windows version uses Windows-specific path handling and opens files/folders using Windows system calls.

The CP/M tools should be stored together, for example:

E:\ubee512\tools\cpmtools-2.10\

The diskdefs file must be in the same folder as cpmls.exe and cpmcp.exe. The launcher runs these tools from their own folder so that diskdefs can be found correctly.
Open the `builds/windows/` folder and run the launcher executable.

## Linux

Open the `builds/linux/` folder and run the launcher file.

You may need to make it executable first:

```bash
chmod +x ./Ubee512-Launcher

```

## License

This project is released under the MIT License.
