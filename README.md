# Anthony's Ubee512 Launcher

Anthony's Ubee512 Launcher is a simple desktop launcher for the uBee512 emulator.

The project currently includes separate launcher versions for:

- Linux
- macOS
- Windows

The launcher is designed to make it easier to select uBee512 paths, scan for ROMs, disks, and tape files, preview the launch command, and start the emulator without having to manually type long command-line instructions each time.

## Current Status

### Linux

**Current Linux version:** `1_5`

The Linux launcher has been updated and rebuilt for version `1_5`.

This version includes:

- improved launch behaviour
- scanning for ROMs, disk images, and tape files
- clearer diagnostics for missing folders and files
- updated tape-loading guidance
- support for mounting floppy disk images to drives A, B, C, and D
- printer output support for BASIC `LPRINT` and `LLIST`
- CP/M tools integration for inspecting and copying files to and from disk images
- an updated Linux executable and ZIP package

### macOS

A macOS launcher build is included in the project.

The macOS version uses macOS-specific path handling and macOS system calls for opening files and folders.

### Windows

A Windows launcher build is included in the project.

The Windows version uses Windows-specific path handling and Windows system calls for opening files and folders.

## Project Structure

```text
Ubee512-Launcher/
├── Builds/
│   ├── Linux/
│   ├── Mac/
│   └── Windows/
├── Source/
│   ├── AnthonysUbee512Launcher.py
│   ├── AnthonysUbee512MacLauncher.py
│   ├── AnthonysUbee512WindowsLauncher.py
│   └── versions/
├── LICENSE
└── README.md
```

## Builds

The packaged builds are stored in the `Builds/` folder.

```text
Builds/Linux/
Builds/Mac/
Builds/Windows/
```

### Linux Build

The current Linux downloadable package is:

```text
Builds/Linux/AnthonysUBee512Launcher-Linux.zip
```

The Linux executable is stored inside:

```text
Builds/Linux/AnthonysUBee512Launcher/
```

### macOS Build

The macOS build is stored in:

```text
Builds/Mac/
```

### Windows Build

The Windows build is stored in:

```text
Builds/Windows/
```

## Running the Linux Version

Download or open:

```text
Builds/Linux/AnthonysUBee512Launcher-Linux.zip
```

Extract the ZIP file.

Then open a terminal inside the extracted launcher folder and run:

```bash
./AnthonysUBee512Launcher
```

You may need to make the file executable first:

```bash
chmod +x ./AnthonysUBee512Launcher
```

## Running the macOS Version

Open the `Builds/Mac/` folder and use the macOS launcher package.

Depending on your macOS security settings, you may need to allow the app to run through System Settings after first launch.

The macOS version is intended for the macOS uBee512 package and uses macOS-specific default paths where appropriate.

## Running the Windows Version

Open the `Builds/Windows/` folder and run the Windows launcher executable.

The Windows version is intended for a Windows uBee512 setup and uses Windows-specific path handling.

## Source Files

The main Linux source file is:

```text
Source/AnthonysUbee512Launcher.py
```

The macOS source file is:

```text
Source/AnthonysUbee512MacLauncher.py
```

The Windows source file is:

```text
Source/AnthonysUbee512WindowsLauncher.py
```

Versioned source snapshots are stored in:

```text
Source/versions/
```

For example:

```text
Source/versions/AnthonysUbee512Launcher_1_5.py
```

## Linux Build Notes

The Linux build is created from the Linux source file using PyInstaller.

Recommended build process:

```bash
cd ~/Documents/Git/Ubee512-Launcher
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name AnthonysUBee512Launcher Source/AnthonysUbee512Launcher.py
```

After building, the generated executable appears in:

```text
dist/AnthonysUBee512Launcher
```

The tested executable should then be copied into:

```text
Builds/Linux/AnthonysUBee512Launcher/
```

The Linux ZIP package should be recreated after replacing the executable.

## CP/M Tools Notes

The launcher includes basic CP/M tools integration for inspecting disk images and copying files to and from disk images.

The launcher expects tools such as:

```text
cpmls
cpmcp
diskdefs
```

The `diskdefs` file should be stored in the same folder as the CP/M tools.

On Windows, for example, the CP/M tools may be stored together in a folder such as:

```text
E:\ubee512\tools\cpmtools-2.10\
```

On Linux or macOS, the tools may be installed system-wide or stored with the uBee512 tools, depending on the user's setup.

## ROMs, Disks, and Tapes

The launcher can scan for:

### ROM files

```text
.rom
.bin
```

### Disk image files

```text
.dsk
.dsk.gz
.img
.hd0
.hd1
.hd2
.hdd
.ds40_
.ds80_
.ds82_
.ds84_
.ss80_
```

### Tape files

```text
.mwb
.tap
.wav
```

The launcher scans recursively from the selected search root.

## Tape Loading Note

The launcher can attach tape files to the uBee512 launch command.

The exact command needed inside the emulator depends on the model and the tape format.

Common examples include:

```text
LOAD ""
```

or:

```text
CLOAD
```

After issuing the load command inside the emulator, use the uBee512 tape rewind/start shortcut or console tape control as required by the emulator.

## Printer Output

The launcher includes printer output support for uBee512.

Useful BASIC commands include:

```text
OUTL#1
LPRINT "TEST"
LLIST
OUTL#0
```

`OUTL#1` sends output to the printer device.

`OUTL#0` returns output to the screen.

Printed data may not appear in the host printer output file until uBee512 closes the printer file or exits.

## Development Workflow

The source code should be treated as the main version of the launcher.

Recommended workflow:

```bash
git checkout main
git pull origin main
git status
```

After making changes:

```bash
git add Source/AnthonysUbee512Launcher.py
git commit -m "Describe the source change"
git push origin main
```

For Linux releases, the usual order is:

1. Update and test the Linux source file.
2. Copy the source file to `Source/versions/`.
3. Commit and push the source.
4. Build the Linux executable.
5. Test the built executable.
6. Replace the Linux build in `Builds/Linux/`.
7. Recreate the Linux ZIP package.
8. Commit and push the build and ZIP.
9. Update the README if needed.
10. Tag the release if appropriate.

## License

This project is released under the MIT License.
