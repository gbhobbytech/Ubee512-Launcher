#!/usr/bin/env python3
"""
Ubee512 Launcher

A Linux desktop launcher for Ubee512 that:
- remembers emulator, library, and data paths
- scans recursively for ROMs, disks, and tape files
- launches Ubee512 with a sensible default ROM
- previews the exact command before launch
- provides a printer-output workflow
- provides basic CP/M tools integration
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

VERSION = "1_5i"
APP_NAME = f"Anthony's Ubee512 Launcher {VERSION}"
CONFIG_DIR = Path.home() / ".config" / "ubee512-launcher"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_WINDOW_GEOMETRY = "1180x740"

DEFAULT_UBEE_EXECUTABLE = Path("/usr/local/bin/ubee512")
DEFAULT_SEARCH_ROOT = Path.home() / ".ubee512"
DEFAULT_PRINTER_FILE = DEFAULT_SEARCH_ROOT / "printer" / "printout.txt"
DEFAULT_HOST_EXPORT_DIR = Path.home() / "Documents" / "Ubee512 Exports"

ROM_EXTENSIONS = {
    ".rom",
    ".bin",
}

DISK_EXTENSIONS = {
    ".dsk",
    ".dsk.gz",
    ".img",
    ".hd0",
    ".hd1",
    ".hd2",
    ".hdd",
    ".ds40_",
    ".ds80_",
    ".ds82_",
    ".ds84_",
    ".ss80_",
}

TAPE_EXTENSIONS = {
    ".tap",
    ".wav",
}

FLOPPY_EXTENSIONS = {
    ".dsk",
    ".dsk.gz",
    ".ds40_",
    ".ds80_",
    ".ds82_",
    ".ds84_",
    ".ss80_",
}

IDE_EXTENSIONS = {
    ".img",
    ".hd0",
    ".hd1",
    ".hd2",
    ".hdd",
}

BOOT_MODES = [
    "Auto / plain launch",
    "Model select",
    "IDE/CF boot",
    "Custom arguments only",
]

MODEL_PRESETS = [
    "pcf",
    "scf",
    "p1024k",
    "1024k",
    "p512k",
    "512k",
    "p256k",
    "256k",
    "p128k",
    "128k",
    "p64k",
    "64k",
    "56k",
    "256tc",
    "tterm",
    "ppc85",
    "pc85b",
    "pc85",
    "pc",
    "ic",
    "2mhz",
    "2mhzdd",
    "dd",
]

# These models are ROM/tape-style machines and should not receive stale
# floppy image arguments from the launcher. The user can still override with
# Extra args if they deliberately need an unusual uBee512 command.
ROM_TAPE_ONLY_MODELS = {
    "tterm",
    "ppc85",
    "pc85b",
    "pc85",
    "pc",
    "ic",
    "2mhz",
}

MODEL_DISK_ALIAS_HINTS = {
    "p512k": "p512k.dsk",
    "512k": "512k.dsk",
    "p128k": "p128k.dsk",
    "128k": "128k.dsk",
    "p64k": "p64k.dsk",
    "64k": "64k.dsk",
    "56k": "56k.dsk",
    "2mhzdd": "2mhzdd.dsk",
    "dd": "dd.dsk",
}

CF_MODEL_ALIAS_HINTS = {
    "pcf": ("cfboot", "cfboot.hd1"),
    "scf": ("cfboot", "cfboot.hd1"),
}

# These prefixes are used only for diagnostics. They do not change how
# uBee512 loads ROMs. uBee512 remains responsible for normal ROM loading
# through roms.alias and MD5 matching.
MODEL_ROM_ALIAS_PREFIXES = {
    "ic": ("IC_",),
    "pc": ("PC_",),
    "pc85": ("PC85_",),
    "pc85b": ("PC85B_",),
    "ppc85": ("PC85_", "PC85B_"),
    "tterm": ("TTERM_", "256TC_", "TELETERM_"),
    "256tc": ("256TC_",),
    "2mhz": ("2MHZ_",),
    "2mhzdd": ("2MHZ_",),
    "p512k": ("P512K_", "PREMIUM_512K_"),
    "512k": ("512K_",),
    "p256k": ("P256K_", "PREMIUM_256K_"),
    "256k": ("256K_",),
    "p128k": ("P128K_", "PREMIUM_128K_"),
    "128k": ("128K_",),
    "p64k": ("P64K_", "PREMIUM_64K_"),
    "64k": ("64K_",),
    "56k": ("56K_",),
    "pcf": ("PCF_", "BN56CF", "SCF_"),
    "scf": ("SCF_", "BN56CF", "PCF_"),
}

TAPE_MODES = [
    "Auto",
    "WAV",
    "TAP",
]

CPM_FORMAT_PRESETS = [
    "",
    "ds40",
    "ss80",
    "ds80",
    "ds82",
    "ds84",
]


def default_cpmtools_path(name: str) -> str:
    bundled = Path.home() / "ubee512" / "tools" / "cpmtools-2.10" / name
    return str(bundled) if bundled.exists() else name


DEFAULT_CONFIG = {
    "ubee_executable": str(DEFAULT_UBEE_EXECUTABLE),
    "library_path": "",
    "search_root": str(DEFAULT_SEARCH_ROOT),
    "model_preset": "pcf",
    "rom256k": "none",
    "extra_args": "",
    "last_boot_mode": "Auto / plain launch",
    "last_rom": "",
    "last_disk": "",
    "tape_mode": "Auto",
    "mounted_tape": "",
    "printer_output_file": str(DEFAULT_PRINTER_FILE),
    "printer_mode": "Off",
    "cpmls_executable": default_cpmtools_path("cpmls"),
    "cpmcp_executable": default_cpmtools_path("cpmcp"),
    "cpm_format": "",
    "cpm_user": "0",
    "cpm_filename": "*.*",
    "cpm_target_name": "",
    "host_export_dir": str(DEFAULT_HOST_EXPORT_DIR),
    "mounted_drive_a": "",
    "mounted_drive_b": "",
    "mounted_drive_c": "",
    "mounted_drive_d": "",
    "advanced_mode": False,
    "window_geometry": DEFAULT_WINDOW_GEOMETRY,
}


@dataclass
class ScanResults:
    roms: list[Path]
    disks: list[Path]
    tapes: list[Path]


def has_extension(path: Path, extensions: set[str]) -> bool:
    lower_name = path.name.lower()
    return any(lower_name.endswith(ext) for ext in extensions)


class ToolTip:
    """Small hover tooltip for brief contextual help."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip_window: tk.Toplevel | None = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event=None) -> None:
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + 18
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            padding=(8, 5),
            relief=tk.SOLID,
            borderwidth=1,
        )
        label.pack()

    def hide(self, _event=None) -> None:
        if self.tip_window is not None:
            self.tip_window.destroy()
            self.tip_window = None


class UbeeLauncherApp:
    @staticmethod
    def printer_mode_to_index(mode: str) -> int:
        mapping = {
            "Off": 0,
            "Raw text (--print)": 1,
            "ASCII decimal (--printa)": 2,
        }
        return mapping.get(mode, 0)

    @staticmethod
    def printer_mode_label(index: int) -> str:
        labels = {
            0: "Off",
            1: "Raw text (--print)",
            2: "ASCII decimal (--printa)",
        }
        return labels.get(int(index), "Off")

    def on_printer_mode_slider(self, value: str) -> None:
        snapped = round(float(value))
        self.printer_mode_var.set(snapped)
        self.update_printer_mode_ui()
        self.refresh_command_preview()

    def update_printer_mode_ui(self) -> None:
        if hasattr(self, "printer_mode_value_label"):
            self.printer_mode_value_label.configure(
                text=self.printer_mode_label(self.printer_mode_var.get())
            )
        self.refresh_command_preview()

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_NAME)

        self.config = self.load_config()
        self.scan_results = ScanResults([], [], [])

        self.root.geometry(self.config.get("window_geometry", DEFAULT_WINDOW_GEOMETRY))
        self.root.minsize(980, 620)
        try:
            self.root.option_add("*tearOff", False)
        except Exception:
            pass

        self.ubee_var = tk.StringVar(value=self.config.get("ubee_executable", DEFAULT_CONFIG["ubee_executable"]))
        self.search_root_var = tk.StringVar(value=self.config.get("search_root", DEFAULT_CONFIG["search_root"]))
        self.library_path_var = tk.StringVar(value=self.config.get("library_path", DEFAULT_CONFIG["library_path"]))
        self.model_var = tk.StringVar(value=self.config.get("model_preset", DEFAULT_CONFIG["model_preset"]))
        self.rom256k_var = tk.StringVar(value=self.config.get("rom256k", DEFAULT_CONFIG["rom256k"]))
        self.boot_mode_var = tk.StringVar(value=self.config.get("last_boot_mode", DEFAULT_CONFIG["last_boot_mode"]))
        self.tape_mode_var = tk.StringVar(value=self.config.get("tape_mode", DEFAULT_CONFIG["tape_mode"]))
        self.mounted_tape_var = tk.StringVar(value=self.config.get("mounted_tape", DEFAULT_CONFIG["mounted_tape"]))
        self.extra_args_var = tk.StringVar(value=self.config.get("extra_args", DEFAULT_CONFIG["extra_args"]))
        self.status_var = tk.StringVar(value="Set your paths, scan, then launch.")
        self.setup_info_var = tk.StringVar(value="Quick setup\n\nClick Auto setup to detect uBee512 and scan ~/.ubee512.\n\nROM override, CP/M tools, printer capture, model selection and other specialist options are available in Advanced mode.")
        self.command_preview_var = tk.StringVar(value="")
        self.diagnostics_summary_var = tk.StringVar(value="Diagnostics have not been run yet.")
        self.default_rom1_var = tk.StringVar(value=self.config.get("last_rom", DEFAULT_CONFIG["last_rom"]))
        self.advanced_mode_var = tk.BooleanVar(value=self.config.get("advanced_mode", DEFAULT_CONFIG["advanced_mode"]))

        self.printer_output_var = tk.StringVar(
            value=self.config.get("printer_output_file", DEFAULT_CONFIG["printer_output_file"])
        )
        self.printer_mode_var = tk.IntVar(
            value=self.printer_mode_to_index(
                self.config.get("printer_mode", DEFAULT_CONFIG["printer_mode"])
            )
        )
        self.cpmls_var = tk.StringVar(value=self.config.get("cpmls_executable", DEFAULT_CONFIG["cpmls_executable"]))
        self.cpmcp_var = tk.StringVar(value=self.config.get("cpmcp_executable", DEFAULT_CONFIG["cpmcp_executable"]))
        self.cpm_format_var = tk.StringVar(value=self.config.get("cpm_format", DEFAULT_CONFIG["cpm_format"]))
        self.cpm_user_var = tk.StringVar(value=self.config.get("cpm_user", DEFAULT_CONFIG["cpm_user"]))
        self.cpm_filename_var = tk.StringVar(value=self.config.get("cpm_filename", DEFAULT_CONFIG["cpm_filename"]))
        self.cpm_target_name_var = tk.StringVar(value=self.config.get("cpm_target_name", DEFAULT_CONFIG["cpm_target_name"]))
        self.host_export_dir_var = tk.StringVar(
            value=self.config.get("host_export_dir", DEFAULT_CONFIG["host_export_dir"])
        )
        self.host_import_files_var = tk.StringVar(value="")
        self.current_cpm_disk_var = tk.StringVar(value="None selected")
        self.mounted_drive_vars = {
            "A": tk.StringVar(value=self.config.get("mounted_drive_a", DEFAULT_CONFIG["mounted_drive_a"])),
            "B": tk.StringVar(value=self.config.get("mounted_drive_b", DEFAULT_CONFIG["mounted_drive_b"])),
            "C": tk.StringVar(value=self.config.get("mounted_drive_c", DEFAULT_CONFIG["mounted_drive_c"])),
            "D": tk.StringVar(value=self.config.get("mounted_drive_d", DEFAULT_CONFIG["mounted_drive_d"])),
        }

        self.mounted_drive_display_vars = {
            drive: tk.StringVar() for drive in ("A", "B", "C", "D")
        }

        self.configure_styles()
        self._build_ui()
        self.update_mode_ui()
        self._bind_events()
        self.refresh_command_preview()
        self.refresh_printer_preview()
        self.update_current_cpm_selection()
        self.root.after(150, self.scan_saved_root_on_startup)

    def normalize_boot_mode(self, value: str) -> str:
        """Keep launch mode values inside the supported v1_5i list."""
        return value if value in BOOT_MODES else "Auto / plain launch"

    def load_config(self) -> dict:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                config = {**DEFAULT_CONFIG, **json.loads(CONFIG_FILE.read_text(encoding="utf-8"))}
                config["last_boot_mode"] = self.normalize_boot_mode(config.get("last_boot_mode", "Auto / plain launch"))
                old_tape_mode = config.get("tape_mode", "Auto")
                tape_mode_mapping = {
                    "Off": "Auto",
                    "WAV input (--tapei)": "Auto",
                    "TAP input (--tapfilei)": "Auto",
                }
                config["tape_mode"] = tape_mode_mapping.get(old_tape_mode, old_tape_mode)
                if config["tape_mode"] not in TAPE_MODES:
                    config["tape_mode"] = "Auto"
                return config
            except Exception:
                return DEFAULT_CONFIG.copy()
        return DEFAULT_CONFIG.copy()

    def save_config(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        selected_disk = self.get_selected_disk_path()
        payload = {
            "ubee_executable": self.ubee_var.get().strip(),
            "library_path": self.library_path_var.get().strip(),
            "search_root": self.search_root_var.get().strip(),
            "model_preset": self.model_var.get().strip(),
            "rom256k": self.rom256k_var.get().strip(),
            "extra_args": self.extra_args_var.get().strip(),
            "last_boot_mode": self.boot_mode_var.get().strip(),
            "last_rom": self.default_rom1_var.get().strip(),
            "last_disk": str(selected_disk) if selected_disk else "",
            "tape_mode": self.tape_mode_var.get().strip(),
            "mounted_tape": self.mounted_tape_var.get().strip(),
            "printer_output_file": self.printer_output_var.get().strip(),
            "printer_mode": self.printer_mode_label(self.printer_mode_var.get()),
            "cpmls_executable": self.cpmls_var.get().strip(),
            "cpmcp_executable": self.cpmcp_var.get().strip(),
            "cpm_format": self.cpm_format_var.get().strip(),
            "cpm_user": self.cpm_user_var.get().strip(),
            "cpm_filename": self.cpm_filename_var.get().strip(),
            "cpm_target_name": self.cpm_target_name_var.get().strip(),
            "host_export_dir": self.host_export_dir_var.get().strip(),
            "mounted_drive_a": self.mounted_drive_vars["A"].get().strip(),
            "mounted_drive_b": self.mounted_drive_vars["B"].get().strip(),
            "mounted_drive_c": self.mounted_drive_vars["C"].get().strip(),
            "mounted_drive_d": self.mounted_drive_vars["D"].get().strip(),
            "advanced_mode": self.advanced_mode_var.get(),
            "window_geometry": self.root.winfo_geometry(),
        }
        CONFIG_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _build_ui(self) -> None:
        """Build a compact wide layout that resizes cleanly on desktop displays."""
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=0)

        self.root.minsize(980, 620)

        top = ttk.LabelFrame(self.root, text="Paths and launch settings", padding=(10, 8))
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        for col in (1, 4):
            top.columnconfigure(col, weight=1)

        ttk.Label(top, text="Ubee executable").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(top, textvariable=self.ubee_var).grid(row=0, column=1, columnspan=4, sticky="ew", pady=2)
        ttk.Button(top, text="Find", command=self.choose_ubee_executable, width=10).grid(row=0, column=5, padx=(6, 0), pady=2)

        ttk.Label(top, text="Search root").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(top, textvariable=self.search_root_var).grid(row=1, column=1, columnspan=4, sticky="ew", pady=2)
        ttk.Button(top, text="Browse", command=self.choose_search_root, width=10).grid(row=1, column=5, padx=(6, 0), pady=2)

        # Keep the library path override internally for unusual or broken Linux
        # installs, but do not show it as part of the normal setup UI.
        # Most uBee512 installations should launch without LD_LIBRARY_PATH help.
        self.library_path_label = ttk.Label(top, text="Library path override")
        self.library_path_entry = ttk.Entry(top, textvariable=self.library_path_var)
        self.library_path_button = ttk.Button(top, text="Browse", command=self.choose_library_path, width=10)

        controls = ttk.Frame(top)
        controls.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(6, 0))
        controls.columnconfigure(12, weight=1)

        self.boot_mode_label = ttk.Label(controls, text="Launch mode")
        self.boot_mode_label.grid(row=0, column=0, sticky="w")
        self.boot_mode_entry = ttk.Combobox(
            controls,
            textvariable=self.boot_mode_var,
            values=BOOT_MODES,
            state="readonly",
            width=22,
        )
        self.boot_mode_entry.grid(row=0, column=1, sticky="w", padx=(6, 14))

        self.model_label = ttk.Label(controls, text="Microbee model")
        self.model_label.grid(row=0, column=2, sticky="w")
        self.model_entry = ttk.Combobox(
            controls,
            textvariable=self.model_var,
            values=MODEL_PRESETS,
            state="readonly",
            width=10,
        )
        self.model_entry.grid(row=0, column=3, sticky="w", padx=(6, 14))

        self.rom256k_label = ttk.Label(controls, text="rom256k")
        self.rom256k_label.grid(row=0, column=4, sticky="w")
        # rom256k is a specialist Compact Flash ROM option. Keep it available
        # through Extra args rather than as a normal launcher control.
        self.rom256k_entry = ttk.Entry(controls, textvariable=self.rom256k_var, width=10)
        self.rom256k_entry.grid(row=0, column=5, sticky="w", padx=(6, 14))
        self.rom256k_label.grid_remove()
        self.rom256k_entry.grid_remove()

        self.interface_mode_label = ttk.Label(controls, text="Interface mode")
        self.interface_mode_label.grid(row=0, column=6, sticky="w", padx=(0, 6))

        self.interface_mode_frame = ttk.Frame(controls)
        self.interface_mode_frame.grid(row=0, column=7, sticky="w", padx=(0, 10))

        self.simple_mode_radio = ttk.Radiobutton(
            self.interface_mode_frame,
            text="Simple",
            variable=self.advanced_mode_var,
            value=False,
            command=self.update_mode_ui,
        )
        self.simple_mode_radio.pack(side=tk.LEFT)

        self.advanced_mode_radio = ttk.Radiobutton(
            self.interface_mode_frame,
            text="Advanced",
            variable=self.advanced_mode_var,
            value=True,
            command=self.update_mode_ui,
        )
        self.advanced_mode_radio.pack(side=tk.LEFT, padx=(8, 0))

        self.auto_setup_button = ttk.Button(controls, text="Auto setup", command=self.auto_setup, width=12, style="Auto.TButton")
        self.auto_setup_button.grid(row=0, column=8, sticky="w", padx=(0, 8))
        ttk.Button(controls, text="Scan files", command=self.scan_files, width=12).grid(row=0, column=9, sticky="w")
        ttk.Label(controls, textvariable=self.status_var).grid(row=0, column=10, columnspan=2, sticky="e", padx=(12, 0))

        self.middle = ttk.Frame(self.root)
        self.middle.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        self.middle.columnconfigure(0, weight=1)
        self.middle.columnconfigure(1, weight=0)
        self.middle.rowconfigure(0, weight=1)

        files_area = ttk.LabelFrame(self.middle, text="Media library", padding=8)
        self.files_area = files_area
        files_area.grid(row=0, column=0, sticky="nsew")

        right = ttk.Frame(self.middle, padding=0)
        self.advanced_panel = right
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        files_area.columnconfigure(0, weight=1)
        files_area.columnconfigure(1, weight=0)
        files_area.columnconfigure(2, weight=1)
        files_area.columnconfigure(3, weight=0)
        files_area.rowconfigure(1, weight=1)
        files_area.rowconfigure(3, weight=1)

        self.disk_label = ttk.Label(files_area, text="Disk images", font=("TkDefaultFont", 10, "bold"))
        self.disk_label.grid(row=0, column=0, sticky="w")
        self.disk_list = tk.Listbox(files_area, exportselection=False, height=18)
        self.disk_list.grid(row=1, column=0, rowspan=3, sticky="nsew", pady=(4, 0), padx=(0, 4))
        self.disk_scroll = ttk.Scrollbar(files_area, orient="vertical", command=self.disk_list.yview)
        self.disk_scroll.grid(row=1, column=1, rowspan=3, sticky="ns", pady=(4, 0), padx=(0, 8))
        self.disk_list.configure(yscrollcommand=self.disk_scroll.set)

        self.tape_label = ttk.Label(files_area, text="Tape files", font=("TkDefaultFont", 10, "bold"))
        self.tape_label.grid(row=0, column=2, sticky="w")
        self.tape_list = tk.Listbox(files_area, exportselection=False, height=8)
        self.tape_list.grid(row=1, column=2, sticky="nsew", pady=(4, 8), padx=(0, 4))
        self.tape_scroll = ttk.Scrollbar(files_area, orient="vertical", command=self.tape_list.yview)
        self.tape_scroll.grid(row=1, column=3, sticky="ns", pady=(4, 8))
        self.tape_list.configure(yscrollcommand=self.tape_scroll.set)

        self.rom_label = ttk.Label(files_area, text="ROMs", font=("TkDefaultFont", 10, "bold"))
        self.rom_label.grid(row=2, column=2, sticky="w")
        self.rom_list = tk.Listbox(files_area, exportselection=False, height=8)
        self.rom_list.grid(row=3, column=2, sticky="nsew", pady=(4, 0), padx=(0, 4))
        self.rom_scroll = ttk.Scrollbar(files_area, orient="vertical", command=self.rom_list.yview)
        self.rom_scroll.grid(row=3, column=3, sticky="ns", pady=(4, 0))
        self.rom_list.configure(yscrollcommand=self.rom_scroll.set)

        # Keep the media library grid static in both Simple and Advanced mode.
        # Disk stays full-height on the left, with Tape above ROMs on the right.
        # Earlier dynamic re-gridding of Tape/ROM widgets caused overlap after toggling modes.

        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.workflow = ttk.Notebook(right)
        self.workflow.grid(row=0, column=0, sticky="nsew")

        self.printer_tab = ttk.Frame(self.workflow, padding=8)
        self.cpm_tab = ttk.Frame(self.workflow, padding=0)
        self.diagnostics_tab = ttk.Frame(self.workflow, padding=8)
        self.workflow.add(self.printer_tab, text="Printer / LPRINT")
        self.workflow.add(self.cpm_tab, text="CP/M tools")
        self.workflow.add(self.diagnostics_tab, text="Diagnostics / Maintenance")

        self._build_printer_tab(self.printer_tab)
        self._build_scrollable_cpm_tab(self.cpm_tab)
        self._build_diagnostics_tab(self.diagnostics_tab)

        bottom = ttk.Frame(self.root, padding=(10, 4, 10, 8))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=3)
        bottom.columnconfigure(1, weight=4)

        mounted_panel = ttk.LabelFrame(bottom, text="Mounted media", padding=(8, 6))
        mounted_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        mounted_panel.columnconfigure(1, weight=1)
        mounted_panel.columnconfigure(4, weight=1)

        floppy_heading = ttk.Frame(mounted_panel)
        floppy_heading.grid(row=0, column=0, columnspan=7, sticky="w", pady=(0, 4))
        ttk.Label(floppy_heading, text="Floppy drives", font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT)
        disk_support_note = ttk.Label(floppy_heading, text=" [?]", font=("TkDefaultFont", 8), foreground="gray")
        disk_support_note.pack(side=tk.LEFT)
        ToolTip(
            disk_support_note,
            "Disk mounting depends on the selected Microbee model and uBee512 support.\n"
            "Some models may not support disk boot.",
        )

        for idx, drive in enumerate(("A", "B", "C", "D")):
            row = 1 + idx // 2
            col_offset = 0 if idx % 2 == 0 else 3
            ttk.Label(mounted_panel, text=f"{drive}:").grid(row=row, column=col_offset, sticky="w", padx=(0, 4), pady=3)
            ttk.Entry(mounted_panel, textvariable=self.mounted_drive_display_vars[drive], state="readonly", width=16).grid(
                row=row, column=col_offset + 1, sticky="ew", pady=3
            )
            drive_buttons = ttk.Frame(mounted_panel)
            drive_buttons.grid(row=row, column=col_offset + 2, sticky="w", padx=(4, 10), pady=3)
            ttk.Button(
                drive_buttons,
                text="Mount",
                command=lambda d=drive: self.mount_selected_to_drive(d),
                width=7,
            ).pack(side=tk.LEFT)
            ttk.Button(
                drive_buttons,
                text="Clear",
                command=lambda d=drive: self.clear_mounted_drive(d),
                width=6,
            ).pack(side=tk.LEFT, padx=(4, 0))

        ttk.Button(
            mounted_panel,
            text="Clear all",
            command=self.clear_all_mounted_drives,
            width=10,
        ).grid(row=1, column=6, rowspan=2, sticky="ns", padx=(4, 0), pady=3)

        self.tape_section_label = ttk.Frame(mounted_panel)
        self.tape_section_label.grid(row=3, column=0, columnspan=7, sticky="w", pady=(10, 4))
        ttk.Label(self.tape_section_label, text="Tape input", font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT)
        tape_help_note = ttk.Label(self.tape_section_label, text=" [?]", font=("TkDefaultFont", 8), foreground="gray")
        tape_help_note.pack(side=tk.LEFT)
        ToolTip(
            tape_help_note,
            "Select a tape file from the Tape files list, then press Use tape.\n\n"
            "Auto mode chooses WAV or TAP based on the file extension.\n\n"
            "After launching uBee512, use LOAD \"\" or CLOAD at the BASIC prompt, "
            "then press Alt+T / EMUKEY+T to rewind/start the tape.\n\n"
            "When loading finishes, type RUN if the program does not auto-start.",
        )

        self.tape_mode_label = ttk.Label(mounted_panel, text="Mode")
        self.tape_mode_label.grid(row=4, column=0, sticky="w", padx=(0, 4), pady=3)
        self.tape_mode_entry = ttk.Combobox(
            mounted_panel,
            textvariable=self.tape_mode_var,
            values=TAPE_MODES,
            state="readonly",
            width=20,
        )
        self.tape_mode_entry.grid(row=4, column=1, columnspan=2, sticky="w", pady=3)
        self.use_selected_tape_button = ttk.Button(mounted_panel, text="Use tape", command=self.use_selected_tape_input)
        self.use_selected_tape_button.grid(row=4, column=3, columnspan=2, sticky="w", padx=(8, 0), pady=3)
        self.clear_tape_button = ttk.Button(mounted_panel, text="Clear tape", command=self.clear_tape_input)
        self.clear_tape_button.grid(row=4, column=5, columnspan=2, sticky="e", pady=3)

        self.tape_file_label = ttk.Label(mounted_panel, text="File")
        self.tape_file_label.grid(row=5, column=0, sticky="w", padx=(0, 4), pady=3)
        self.tape_file_entry = ttk.Entry(mounted_panel, textvariable=self.mounted_tape_var)
        self.tape_file_entry.grid(row=5, column=1, columnspan=6, sticky="ew", pady=3)
        ttk.Label(
            mounted_panel,
            text="Select tape  >  Use tape  >  Launch",
            justify=tk.LEFT,
        ).grid(row=6, column=0, columnspan=7, sticky="w", pady=(2, 0))

        launch_panel = ttk.LabelFrame(bottom, text="Launch command", padding=(8, 6))
        launch_panel.grid(row=0, column=1, sticky="nsew")
        launch_panel.columnconfigure(1, weight=1)

        self.args_frame = launch_panel

        self.extra_args_label = ttk.Label(launch_panel, text="Extra args")
        self.extra_args_label.grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        self.extra_args_entry = ttk.Entry(launch_panel, textvariable=self.extra_args_var)
        self.extra_args_entry.grid(row=0, column=1, columnspan=3, sticky="ew", pady=2)

        self.rom1_label = ttk.Frame(launch_panel)
        self.rom1_label.grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Label(self.rom1_label, text="ROM override").pack(side=tk.LEFT)
        rom_help_note = ttk.Label(self.rom1_label, text=" [?]", font=("TkDefaultFont", 8), foreground="gray")
        rom_help_note.pack(side=tk.LEFT)
        ToolTip(
            rom_help_note,
            "Optional advanced override for uBee512 --rom1.\n\n"
            "Most users should leave this blank and let uBee512 load ROMs through roms.alias.",
        )
        self.rom1_entry = ttk.Entry(launch_panel, textvariable=self.default_rom1_var)
        self.rom1_entry.grid(row=1, column=1, columnspan=3, sticky="ew", pady=2)

        ttk.Label(launch_panel, text="Command").grid(row=2, column=0, sticky="nw", padx=(0, 6), pady=2)
        self.command_preview_text = tk.Text(
            launch_panel,
            height=4,
            wrap=tk.WORD,
            relief=tk.SUNKEN,
            borderwidth=1,
            highlightthickness=0,
            background="white",
            foreground="black",
            selectbackground="#2f6fed",
            selectforeground="white",
        )
        self.command_preview_text.grid(row=2, column=1, columnspan=3, sticky="ew", pady=2)
        self.command_preview_text.configure(state="disabled")

        ttk.Button(launch_panel, text="Copy command", command=self.copy_command).grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Button(launch_panel, text="Keyboard Help", command=self.show_keyboard_help).grid(row=3, column=1, sticky="w", pady=(6, 0), padx=(8, 0))
        ttk.Button(launch_panel, text="Launch Ubee512", command=self.launch_ubee).grid(row=3, column=3, sticky="e", pady=(6, 0))


    def update_mode_ui(self) -> None:
        advanced = self.advanced_mode_var.get()

        # Simple mode stays deliberately plain. Advanced mode exposes boot/model
        # overrides, ROM override, printer capture, CP/M tools, diagnostics, and custom args.
        advanced_widgets = [
            self.boot_mode_label,
            self.boot_mode_entry,
            self.model_label,
            self.model_entry,
            self.extra_args_label,
            self.extra_args_entry,
            self.rom1_label,
            self.rom1_entry,
        ]
        for widget in advanced_widgets:
            if advanced:
                widget.grid()
            else:
                widget.grid_remove()

        # Auto setup is a Simple-mode convenience. In Advanced mode it is available
        # from Diagnostics / Maintenance so the top row stays uncluttered.
        if advanced:
            self.auto_setup_button.grid_remove()
            self.advanced_panel.grid()
            self.middle.columnconfigure(1, weight=2)
            if hasattr(self, "diagnostics_text"):
                self.refresh_diagnostics()
        else:
            self.auto_setup_button.grid()
            self.advanced_panel.grid_remove()
            self.middle.columnconfigure(1, weight=0)

        self.rom256k_label.grid_remove()
        self.rom256k_entry.grid_remove()

        # Do not re-grid media widgets here. Disk / Tape / ROM remain a fixed
        # three-column layout in both modes to avoid Tkinter layout corruption.
        self.update_model_selector_state()
        self.refresh_command_preview()

    def _bind_events(self) -> None:
        for var in [
            self.ubee_var,
            self.search_root_var,
            self.library_path_var,
            self.rom256k_var,
            self.boot_mode_var,
            self.tape_mode_var,
            self.mounted_tape_var,
            self.extra_args_var,
            self.default_rom1_var,
            self.printer_output_var,
            self.cpmls_var,
            self.cpmcp_var,
            self.cpm_format_var,
            self.cpm_user_var,
            self.cpm_filename_var,
            self.cpm_target_name_var,
            self.host_export_dir_var,
            self.mounted_drive_vars["A"],
            self.mounted_drive_vars["B"],
            self.mounted_drive_vars["C"],
            self.mounted_drive_vars["D"],
        ]:
            var.trace_add("write", lambda *_: self.refresh_command_preview())

        self.model_var.trace_add("write", self.on_model_changed)
        self.boot_mode_var.trace_add("write", lambda *_: self.update_model_selector_state())
        self.printer_mode_var.trace_add("write", lambda *_: self.update_printer_mode_ui())
        self.rom_list.bind("<<ListboxSelect>>", self.on_rom_selection_changed)
        self.disk_list.bind("<<ListboxSelect>>", self.on_disk_selection_changed)
        self.tape_list.bind("<<ListboxSelect>>", self.on_tape_selection_changed)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)


    def update_model_selector_state(self) -> None:
        boot_mode = self.normalize_boot_mode(self.boot_mode_var.get().strip())
        if hasattr(self, "model_entry"):
            state = "readonly" if self.advanced_mode_var.get() and boot_mode == "Model select" else "disabled"
            self.model_entry.configure(state=state)

    def on_model_changed(self, *_args) -> None:
        self.update_model_selector_state()
        self.refresh_command_preview()

    def configure_styles(self) -> None:
        try:
            style = ttk.Style()
            style.configure("Auto.TButton", background="#c8f7c5", font=("TkDefaultFont", 9, "bold"))
            style.map("Auto.TButton", background=[("active", "#b7efb3")])
        except Exception:
            pass

    def update_setup_info(self) -> None:
        ubee = self.ubee_var.get().strip()
        root = Path(self.search_root_var.get().strip()).expanduser() if self.search_root_var.get().strip() else DEFAULT_SEARCH_ROOT
        rom_dir = root / "roms"
        disk_dir = root / "disks"
        tape_dir = root / "tapes"
        rom_count = len(self.scan_results.roms) if self.scan_results.roms else len([p for p in rom_dir.glob("*") if p.is_file()]) if rom_dir.exists() else 0
        disk_count = len(self.scan_results.disks) if self.scan_results.disks else len([p for p in disk_dir.rglob("*") if p.is_file()]) if disk_dir.exists() else 0
        tape_count = len(self.scan_results.tapes) if self.scan_results.tapes else len([p for p in tape_dir.rglob("*") if p.is_file()]) if tape_dir.exists() else 0
        ubee_status = "found" if (ubee and (Path(ubee).expanduser().exists() or shutil.which(ubee))) else "not set"
        data_status = "found" if root.exists() else "not found"
        self.setup_info_var.set(
            "Quick setup\n\n"
            f"uBee512: {ubee_status}\n"
            f"Data folder: {data_status}\n"
            f"ROMs: {rom_count} found\n"
            f"Disks: {disk_count} found\n"
            f"Tapes: {tape_count} found\n\n"
            "ROM override, CP/M tools, printer capture, model selection and other specialist options are available in Advanced mode."
        )

    def scan_saved_root_on_startup(self) -> None:
        root_text = self.search_root_var.get().strip()
        if not root_text:
            return
        root = Path(root_text).expanduser()
        if root.exists() and root.is_dir():
            try:
                self.scan_files(show_errors=False)
                self.status_var.set("Scanned saved search root.")
            except Exception:
                # Startup scanning should never prevent the launcher from opening.
                self.status_var.set("Saved search root could not be scanned.")

    def auto_setup(self) -> None:
        found = shutil.which("ubee512")
        if found:
            self.ubee_var.set(found)
        elif DEFAULT_UBEE_EXECUTABLE.exists():
            self.ubee_var.set(str(DEFAULT_UBEE_EXECUTABLE))

        self.search_root_var.set(str(DEFAULT_SEARCH_ROOT))
        self.printer_output_var.set(str(DEFAULT_PRINTER_FILE))

        if not DEFAULT_SEARCH_ROOT.exists():
            messagebox.showwarning(
                APP_NAME,
                "The uBee512 data folder was not found.\n\nRun ubee512 once from the terminal to create ~/.ubee512, then run Auto setup again.",
            )
            self.status_var.set("Auto setup needs ~/.ubee512. Run ubee512 once first.")
            self.update_setup_info()
            return

        self.scan_files()
        self.update_setup_info()
        self.refresh_command_preview()
        self.status_var.set("Auto setup complete.")

    def clear_config(self) -> None:
        proceed = messagebox.askyesno(
            APP_NAME,
            "Clear the launcher configuration?\n\nThis resets saved launcher paths, mounted drives, window size and UI settings. It does not delete your uBee512 ROMs, disks or files.",
        )
        if not proceed:
            return

        try:
            if CONFIG_FILE.exists():
                CONFIG_FILE.unlink()
        except Exception:
            pass

        self.ubee_var.set(DEFAULT_CONFIG["ubee_executable"])
        self.library_path_var.set(DEFAULT_CONFIG["library_path"])
        self.search_root_var.set(DEFAULT_CONFIG["search_root"])
        self.model_var.set(DEFAULT_CONFIG["model_preset"])
        self.rom256k_var.set(DEFAULT_CONFIG["rom256k"])
        self.extra_args_var.set(DEFAULT_CONFIG["extra_args"])
        self.boot_mode_var.set(DEFAULT_CONFIG["last_boot_mode"])
        self.default_rom1_var.set(DEFAULT_CONFIG["last_rom"])
        self.tape_mode_var.set(DEFAULT_CONFIG["tape_mode"])
        self.mounted_tape_var.set(DEFAULT_CONFIG["mounted_tape"])
        self.printer_output_var.set(DEFAULT_CONFIG["printer_output_file"])
        self.printer_mode_var.set(self.printer_mode_to_index(DEFAULT_CONFIG["printer_mode"]))
        self.advanced_mode_var.set(DEFAULT_CONFIG["advanced_mode"])
        for drive in ("A", "B", "C", "D"):
            self.mounted_drive_vars[drive].set("")
        self.disk_list.delete(0, tk.END)
        self.tape_list.delete(0, tk.END)
        self.rom_list.delete(0, tk.END)
        self.scan_results = ScanResults([], [], [])
        self.root.geometry(DEFAULT_WINDOW_GEOMETRY)
        self.update_mounted_drive_displays()
        self.update_mode_ui()
        self.update_setup_info()
        if hasattr(self, "diagnostics_text"):
            self.refresh_diagnostics()
        self.save_config()
        self.status_var.set("Launcher config cleared.")

    def choose_ubee_executable(self) -> None:
        path = filedialog.askopenfilename(title="Select ubee512 executable")
        if path:
            self.ubee_var.set(path)

    def choose_search_root(self) -> None:
        path = filedialog.askdirectory(title="Select Ubee data folder")
        if path:
            self.search_root_var.set(path)

    def choose_library_path(self) -> None:
        path = filedialog.askdirectory(title="Select library folder containing libdsk/libSDL/etc")
        if path:
            self.library_path_var.set(path)

    def choose_printer_output_file(self) -> None:
        current = self.printer_output_var.get().strip()
        initialdir = str(Path(current).expanduser().parent) if current else str(Path.home())
        initialfile = Path(current).name if current else "printout.txt"
        path = filedialog.asksaveasfilename(
            title="Select printer output text file",
            initialdir=initialdir,
            initialfile=initialfile,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.printer_output_var.set(path)
            self.refresh_printer_preview()

    def choose_host_export_dir(self) -> None:
        path = filedialog.askdirectory(title="Select host export folder")
        if path:
            self.host_export_dir_var.set(path)

    def choose_host_import_files(self) -> None:
        paths = filedialog.askopenfilenames(title="Select host file(s) to copy to the disk image")
        if paths:
            self.host_import_files_var.set("; ".join(paths))

    def read_disks_alias(self, root: Path | None = None) -> dict[str, str]:
        """Read simple alias -> target entries from disks.alias.

        This intentionally ignores MD5 targets. uBee512 can use MD5 matching
        itself; the launcher only reports filename-based boot guidance.
        """
        root = root or self.get_search_root_path()
        alias_path = root / "disks.alias"
        aliases: dict[str, str] = {}
        if not alias_path.is_file():
            return aliases

        try:
            lines = alias_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return aliases

        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            parts = line.split()
            if not parts:
                continue
            alias = parts[0].strip()
            target = parts[1].strip() if len(parts) > 1 else alias
            if target.lower().startswith("md5="):
                continue
            aliases[alias.lower()] = target
        return aliases

    def read_roms_alias(self, root: Path | None = None) -> dict[str, str]:
        """Read ROM aliases from roms.alias for diagnostics only.

        The target may be a filename, an md5= value, or blank. Blank entries
        are reported as informational because some aliases are optional or
        user-supplied. This does not attempt to replace uBee512's own ROM loader.
        """
        root = root or self.get_search_root_path()
        alias_path = root / "roms.alias"
        aliases: dict[str, str] = {}
        if not alias_path.is_file():
            return aliases

        try:
            lines = alias_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return aliases

        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            parts = line.split()
            if not parts:
                continue
            alias = parts[0].strip()
            target = parts[1].strip() if len(parts) > 1 else ""
            if alias:
                aliases[alias.upper()] = target
        return aliases

    def read_rom_md5_index(self, root: Path | None = None) -> set[str]:
        """Read known MD5 hashes from roms.md5.user and roms.md5.auto."""
        root = root or self.get_search_root_path()
        hashes: set[str] = set()
        for md5_path in (root / "roms.md5.user", root / "roms.md5.auto"):
            if not md5_path.is_file():
                continue
            try:
                lines = md5_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for raw_line in lines:
                for part in raw_line.replace("=", " ").split():
                    token = part.strip().lower()
                    if len(token) == 32 and all(ch in "0123456789abcdef" for ch in token):
                        hashes.add(token)
        return hashes

    def scanned_rom_md5s(self) -> dict[str, list[Path]]:
        """Calculate MD5 hashes for scanned ROM files.

        This is intentionally limited to files already found by the launcher scan,
        so it remains a diagnostic helper rather than a separate ROM manager.
        """
        hashes: dict[str, list[Path]] = {}
        for rom in self.scan_results.roms:
            try:
                digest = hashlib.md5(rom.read_bytes()).hexdigest().lower()
            except Exception:
                continue
            hashes.setdefault(digest, []).append(rom)
        return hashes

    def rom_alias_prefixes_for_model(self, model: str) -> tuple[str, ...]:
        return MODEL_ROM_ALIAS_PREFIXES.get(model.strip().lower(), ())

    def selected_model_rom_aliases(self, root: Path | None = None) -> dict[str, str]:
        root = root or self.get_search_root_path()
        model = self.model_var.get().strip().lower()
        prefixes = tuple(prefix.upper() for prefix in self.rom_alias_prefixes_for_model(model))
        if not prefixes:
            return {}
        aliases = self.read_roms_alias(root)
        return {
            alias: target
            for alias, target in aliases.items()
            if any(alias.startswith(prefix) for prefix in prefixes)
        }

    def rom_alias_target_status(
        self,
        alias: str,
        target: str,
        root: Path,
        indexed_md5s: set[str],
        scanned_md5s: dict[str, list[Path]],
    ) -> tuple[str, bool | None, str]:
        """Return diagnostic status for a ROM alias target.

        status is one of: found, missing, info. found_bool is True/False for
        FOUND/MISSING lines and None for INFO lines.
        """
        target = target.strip()
        if not target:
            return (
                "info",
                None,
                "listed without a filename or MD5 target; may be optional or user-supplied",
            )

        if target.lower().startswith("md5="):
            wanted = target.split("=", 1)[1].strip().lower()
            in_index = wanted in indexed_md5s
            scanned_paths = scanned_md5s.get(wanted, [])
            if scanned_paths:
                sample = scanned_paths[0]
                return (
                    "found",
                    True,
                    f"MD5 target matched by scanned ROM file: {sample}",
                )
            if in_index:
                return (
                    "found",
                    True,
                    "MD5 target is present in roms.md5.user or roms.md5.auto",
                )
            return (
                "missing",
                False,
                f"MD5 target not found in scanned ROMs or ROM MD5 index: {wanted}",
            )

        candidate_paths = [root / "roms" / target, root / "roms" / alias]
        for path in candidate_paths:
            if path.is_file():
                return ("found", True, str(path))
        return (
            "missing",
            False,
            f"filename target not found under ROMs folder: {target}",
        )

    def get_search_root_path(self) -> Path:
        root_text = self.search_root_var.get().strip()
        return Path(root_text).expanduser() if root_text else DEFAULT_SEARCH_ROOT

    def expected_disk_aliases_for_model(self, model: str) -> list[str]:
        model = model.strip().lower()
        if model in MODEL_DISK_ALIAS_HINTS:
            return [MODEL_DISK_ALIAS_HINTS[model]]
        if model in CF_MODEL_ALIAS_HINTS:
            return list(CF_MODEL_ALIAS_HINTS[model])
        return []

    def boot_alias_diagnostic(self, root: Path | None = None) -> dict[str, object]:
        root = root or self.get_search_root_path()
        model = self.model_var.get().strip().lower()
        aliases = self.read_disks_alias(root)
        expected_aliases = self.expected_disk_aliases_for_model(model)
        disks_dir = root / "disks"
        fallback = disks_dir / "boot.dsk"

        resolved: list[tuple[str, str, bool]] = []
        for alias in expected_aliases:
            target = aliases.get(alias.lower(), alias)
            target_path = disks_dir / target
            resolved.append((alias, target, target_path.is_file()))

        return {
            "model": model,
            "rom_tape_only": model in ROM_TAPE_ONLY_MODELS,
            "cf_guidance": model in CF_MODEL_ALIAS_HINTS,
            "aliases": aliases,
            "expected_aliases": expected_aliases,
            "resolved": resolved,
            "fallback_boot_dsk": fallback,
            "fallback_exists": fallback.is_file(),
            "disks_alias_path": root / "disks.alias",
            "disks_alias_exists": (root / "disks.alias").is_file(),
        }

    def selected_model_boot_warning(self) -> str:
        """v1_5i uses a note only; it does not restrict model/disk combinations."""
        return ""

    def _build_diagnostics_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        button_row = ttk.Frame(parent)
        button_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(button_row, text="Refresh diagnostics", command=self.refresh_diagnostics).pack(side=tk.LEFT)
        ttk.Button(button_row, text="Copy all", command=self.copy_all_diagnostics).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(button_row, text="Auto setup", command=self.auto_setup).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(button_row, text="Maintenance:").pack(side=tk.LEFT, padx=(16, 0))
        ttk.Button(button_row, text="Clear launcher config", command=self.clear_config).pack(side=tk.LEFT, padx=(6, 0))

        self.diagnostics_text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, height=18)
        self.diagnostics_text.grid(row=1, column=0, sticky="nsew")
        self.diagnostics_text.configure(state="disabled")
        self.refresh_diagnostics()

    def diagnostics_line(self, label: str, found: bool, detail: str = "") -> str:
        mark = "FOUND" if found else "MISSING"
        suffix = f" - {detail}" if detail else ""
        return f"{mark}: {label}{suffix}"

    def info_line(self, label: str, detail: str = "") -> str:
        suffix = f" - {detail}" if detail else ""
        return f"INFO: {label}{suffix}"

    def refresh_diagnostics(self) -> None:
        root = self.get_search_root_path()
        ubee_text = self.ubee_var.get().strip()
        ubee_path = Path(ubee_text).expanduser() if ubee_text else None
        ubee_found = bool(ubee_text and ((ubee_path and ubee_path.exists()) or shutil.which(ubee_text)))
        boot_info = self.boot_alias_diagnostic(root)

        lines: list[str] = []
        lines.append(f"Anthony's Ubee512 Launcher {VERSION} diagnostics")
        lines.append("")
        lines.append(self.diagnostics_line("uBee512 executable", ubee_found, ubee_text or "not set"))
        lines.append(self.diagnostics_line("uBee512 data folder", root.exists() and root.is_dir(), str(root)))
        lines.append(self.diagnostics_line("ROMs folder", (root / "roms").is_dir(), str(root / "roms")))
        lines.append(self.diagnostics_line("Disks folder", (root / "disks").is_dir(), str(root / "disks")))
        lines.append(self.diagnostics_line("Tapes folder", (root / "tapes").is_dir(), str(root / "tapes")))
        lines.append(self.diagnostics_line("Printer folder", (root / "printer").is_dir(), str(root / "printer")))
        lines.append(self.diagnostics_line("ubee512rc", (root / "ubee512rc").is_file(), str(root / "ubee512rc")))
        lines.append(self.diagnostics_line("roms.alias", (root / "roms.alias").is_file(), str(root / "roms.alias")))
        lines.append(self.diagnostics_line("disks.alias", bool(boot_info["disks_alias_exists"]), str(boot_info["disks_alias_path"])))
        lines.append(self.diagnostics_line("ROM MD5 index", (root / "roms.md5.user").is_file() or (root / "roms.md5.auto").is_file(), "roms.md5.user or roms.md5.auto"))
        lines.append(self.diagnostics_line("LibDsk config link", (Path.home() / ".libdskrc").exists(), str(Path.home() / ".libdskrc")))
        library_path = self.library_path_var.get().strip()
        if library_path:
            lines.append(self.info_line("Library path override", f"{library_path} (added to LD_LIBRARY_PATH when launching)"))
        else:
            lines.append(self.info_line("Library path override", "not set; most uBee512 installations should leave this blank"))
        lines.append("")
        lines.append("Selected model disk guidance")
        model = str(boot_info["model"]) or "not set"
        lines.append(self.info_line("Selected model", model))
        if boot_info["rom_tape_only"]:
            lines.append(self.info_line("Expected disk alias", "No disk boot expected for this model"))
            lines.append(self.info_line("Mounted disk arguments", "allowed when explicitly mounted; actual support depends on uBee512/model"))
        elif boot_info["cf_guidance"]:
            expected = ", ".join(str(alias) for alias in boot_info["expected_aliases"])
            lines.append(self.info_line("Expected disk alias guidance", expected))
            lines.append(self.info_line("CF/IDE note", "uBee512 may rely on its own alias/default handling. The launcher will not force a disk."))
        elif boot_info["expected_aliases"]:
            lines.append(self.info_line("Expected disk alias", ", ".join(str(alias) for alias in boot_info["expected_aliases"])))
        else:
            lines.append(self.info_line("Expected disk alias", "No launcher hint for this model"))

        resolved = boot_info["resolved"]
        if isinstance(resolved, list) and resolved:
            for alias, target, exists in resolved:
                lines.append(self.info_line("Alias target from disks.alias", f"{alias} -> {target}"))
                lines.append(self.diagnostics_line(f"Expected disk target ({target})", exists, str(root / "disks" / target)))
        elif not boot_info["rom_tape_only"]:
            lines.append(self.info_line("Alias target from disks.alias", "not applicable"))
        fallback = boot_info["fallback_boot_dsk"]
        lines.append(self.diagnostics_line("Fallback boot.dsk", bool(boot_info["fallback_exists"]), str(fallback)))
        warning = self.selected_model_boot_warning()
        if warning:
            lines.append("")
            lines.append("Boot warning:")
            lines.append(warning)

        lines.append("")
        lines.append("Selected model ROM guidance")
        lines.append(self.info_line("Selected model", model))
        lines.append(self.info_line("ROM loading method", "uBee512 normally uses roms.alias and MD5 matching"))
        rom_aliases = self.selected_model_rom_aliases(root)
        prefixes = self.rom_alias_prefixes_for_model(model)
        if prefixes:
            lines.append(self.info_line("ROM alias prefixes checked", ", ".join(prefixes)))
        else:
            lines.append(self.info_line("ROM alias prefixes checked", "No launcher hint for this model"))

        indexed_md5s = self.read_rom_md5_index(root)
        scanned_md5s = self.scanned_rom_md5s()
        lines.append(self.diagnostics_line("ROM MD5 hashes in index", bool(indexed_md5s), f"{len(indexed_md5s)} hash(es) found"))
        lines.append(self.diagnostics_line("Scanned ROM MD5 matches", bool(scanned_md5s), f"{len(scanned_md5s)} unique ROM hash(es) from scanned files"))
        rom_override = self.default_rom1_var.get().strip()
        if rom_override:
            override_path = Path(rom_override).expanduser()
            lines.append(self.diagnostics_line("ROM override (--rom1)", override_path.is_file(), str(override_path)))
            lines.append(self.info_line("ROM override note", "--rom1 is a manual override, not the normal uBee512 ROM loading path"))
        else:
            lines.append(self.info_line("ROM override (--rom1)", "not set"))

        if rom_aliases:
            lines.append(self.info_line("Model ROM aliases found", str(len(rom_aliases))))
            for alias in sorted(rom_aliases):
                target = rom_aliases[alias]
                status, found, detail = self.rom_alias_target_status(alias, target, root, indexed_md5s, scanned_md5s)
                if status == "info":
                    lines.append(self.info_line(alias, detail))
                else:
                    lines.append(self.diagnostics_line(alias, bool(found), detail))
        elif prefixes:
            lines.append(self.info_line("Model ROM aliases found", "none matching the selected model prefix"))

        if model in ROM_TAPE_ONLY_MODELS:
            lines.append(self.info_line("ROM/tape-only note", "If launch fails with 'no ROM image file(s)', the needed ROM may be absent or not recognised by the MD5 index"))

        lines.append("")
        lines.append(f"Scanned ROMs: {len(self.scan_results.roms)}")
        lines.append(f"Scanned disks: {len(self.scan_results.disks)}")
        lines.append(f"Scanned tapes: {len(self.scan_results.tapes)}")
        lines.append("")

        if ubee_found:
            try:
                exe = ubee_text if shutil.which(ubee_text) else str(ubee_path)
                result = subprocess.run([exe, "--help"], capture_output=True, text=True, check=False, timeout=3)
                output_lines = (result.stdout or result.stderr).splitlines()
                first_line = output_lines[0] if output_lines else "no output"
                lines.append(self.diagnostics_line("uBee512 responds", bool(output_lines), first_line))
            except Exception as exc:
                lines.append(self.diagnostics_line("uBee512 responds", False, str(exc)))

            try:
                exe = ubee_text if shutil.which(ubee_text) else str(ubee_path)
                result = subprocess.run([exe, "--lmodel"], capture_output=True, text=True, check=False, timeout=3)
                models = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                lines.append(self.diagnostics_line("Model list", bool(models), f"{len(models)} model(s) found"))
            except Exception as exc:
                lines.append(self.diagnostics_line("Model list", False, str(exc)))

            if ubee_path and ubee_path.exists():
                try:
                    result = subprocess.run(["ldd", str(ubee_path)], capture_output=True, text=True, check=False, timeout=3)
                    missing = [line.strip() for line in result.stdout.splitlines() if "not found" in line]
                    if missing:
                        lines.append(self.diagnostics_line("Shared libraries", False, "; ".join(missing[:5])))
                    else:
                        lines.append(self.diagnostics_line("Shared libraries", True, "no missing libraries reported by ldd"))
                except Exception:
                    pass

        lines.append("")
        lines.append("Current command preview:")
        lines.append(self.command_preview_var.get().strip() or "No command preview yet.")

        text = "\n".join(lines)
        if hasattr(self, "diagnostics_text"):
            self.set_text_widget(self.diagnostics_text, text)
        self.diagnostics_summary_var.set(text)

    def copy_all_diagnostics(self) -> None:
        text = self.diagnostics_summary_var.get().strip()
        if not text or text == "Diagnostics have not been run yet.":
            self.refresh_diagnostics()
            text = self.diagnostics_summary_var.get().strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("Diagnostics copied to clipboard.")

    def _build_printer_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(3, weight=1)

        ttk.Label(parent, text="Printer mode").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        printer_mode_row = ttk.Frame(parent)
        printer_mode_row.grid(row=0, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Scale(
            printer_mode_row,
            from_=0,
            to=2,
            length=60,
            variable=self.printer_mode_var,
            command=self.on_printer_mode_slider,
        ).pack(side=tk.LEFT)
        self.printer_mode_value_label = ttk.Label(
            printer_mode_row,
            text=self.printer_mode_label(self.printer_mode_var.get()),
        )
        self.printer_mode_value_label.pack(side=tk.LEFT, padx=(10, 0))
        printer_help_note = ttk.Label(printer_mode_row, text=" [?]", font=("TkDefaultFont", 8), foreground="gray")
        printer_help_note.pack(side=tk.LEFT)
        ToolTip(
            printer_help_note,
            "Use OUTL#1 for the printer device and OUTL#0 for screen output.\n\n"
            "Then use LPRINT \"TEXT\" for a quick test or LLIST for a BASIC program listing.\n\n"
            "Raw mode uses --print. ASCII mode uses --printa.\n\n"
            "Printed data may not appear in the host file until uBee512 closes the printer file or exits.",
        )

        ttk.Label(parent, text="Printer output file").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(parent, textvariable=self.printer_output_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="Browse", command=self.choose_printer_output_file).grid(row=1, column=2, padx=(8, 0), pady=4)

        printer_buttons = ttk.Frame(parent)
        printer_buttons.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 8))
        ttk.Button(printer_buttons, text="Refresh", command=self.refresh_printer_preview).pack(side=tk.LEFT)
        ttk.Button(printer_buttons, text="Open file", command=self.open_printer_file).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(printer_buttons, text="Open folder", command=self.open_printer_folder).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(printer_buttons, text="Clear file", command=self.clear_printer_output).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(printer_buttons, text="Save copy as...", command=self.export_printer_output).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(printer_buttons, text="Copy all", command=self.copy_all_printer_output).pack(side=tk.LEFT, padx=(8, 0))

        self.printer_preview = scrolledtext.ScrolledText(parent, wrap=tk.WORD, height=18)
        self.printer_preview.grid(row=3, column=0, columnspan=3, sticky="nsew")
        self.printer_preview.configure(state="disabled")


    def _build_scrollable_cpm_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="nsew")

        content = ttk.Frame(canvas, padding=8)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def _sync_scrollregion(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _resize_content(event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        content.bind("<Configure>", _sync_scrollregion)
        canvas.bind("<Configure>", _resize_content)

        self._build_cpm_tab(content)

    def _build_cpm_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(5, weight=1)

        cpm_help_row = ttk.Frame(parent)
        cpm_help_row.grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Label(cpm_help_row, text="CP/M tools help", font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT)
        cpm_help_note = ttk.Label(cpm_help_row, text=" [?]", font=("TkDefaultFont", 8), foreground="gray")
        cpm_help_note.pack(side=tk.LEFT)
        ToolTip(
            cpm_help_note,
            "Use these tools to inspect a CP/M disk image or move files between the host and disk image.\n\n"
            "Pick the disk image in the main Disk images list first, then choose the action below.\n\n"
            "You may need cpmls and cpmcp installed and the correct disk format selected.",
        )

        common = ttk.LabelFrame(parent, text="CP/M disk and tool settings", padding=8)
        common.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        common.columnconfigure(1, weight=1)
        common.columnconfigure(3, weight=1)

        ttk.Label(common, text="Current disk image").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(common, textvariable=self.current_cpm_disk_var, state="readonly").grid(row=0, column=1, columnspan=3, sticky="ew", pady=4)

        ttk.Label(common, text="Disk format").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(common, textvariable=self.cpm_format_var, values=CPM_FORMAT_PRESETS, state="readonly").grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(common, text="CP/M user").grid(row=1, column=2, sticky="w", padx=(16, 8), pady=4)
        ttk.Entry(common, textvariable=self.cpm_user_var, width=8).grid(row=1, column=3, sticky="w", pady=4)

        ttk.Label(common, text="cpmls executable").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(common, textvariable=self.cpmls_var).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Label(common, text="cpmcp executable").grid(row=2, column=2, sticky="w", padx=(16, 8), pady=4)
        ttk.Entry(common, textvariable=self.cpmcp_var).grid(row=2, column=3, sticky="ew", pady=4)

        inspect_frame = ttk.LabelFrame(parent, text="Inspect disk image", padding=8)
        inspect_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(
            inspect_frame,
            text="Show the directory for the selected disk image using the current format.",
            justify=tk.LEFT,
        ).pack(anchor="w")
        inspect_buttons = ttk.Frame(inspect_frame)
        inspect_buttons.pack(anchor="w", pady=(6, 0))
        ttk.Button(inspect_buttons, text="Inspect disk image", command=self.run_cpmls).pack(side=tk.LEFT)
        ttk.Button(inspect_buttons, text="Show example commands", command=self.show_cpm_examples).pack(side=tk.LEFT, padx=(8, 0))

        from_frame = ttk.LabelFrame(parent, text="Copy from disk image", padding=8)
        from_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        from_frame.columnconfigure(1, weight=1)
        ttk.Label(from_frame, text="Files on disk").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(from_frame, textvariable=self.cpm_filename_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(from_frame, text="Host folder").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(from_frame, textvariable=self.host_export_dir_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(from_frame, text="Browse", command=self.choose_host_export_dir).grid(row=1, column=2, padx=(8, 0), pady=4)
        from_buttons = ttk.Frame(from_frame)
        from_buttons.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Button(from_buttons, text="Copy from disk image", command=self.run_cpmcp_export).pack(side=tk.LEFT)
        ttk.Button(from_buttons, text="Open folder", command=self.open_export_folder).pack(side=tk.LEFT, padx=(8, 0))

        to_frame = ttk.LabelFrame(parent, text="Copy to disk image", padding=8)
        to_frame.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        to_frame.columnconfigure(1, weight=1)
        ttk.Label(to_frame, text="Host file(s)").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(to_frame, textvariable=self.host_import_files_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(to_frame, text="Browse", command=self.choose_host_import_files).grid(row=0, column=2, padx=(8, 0), pady=4)
        ttk.Label(to_frame, text="Target name (optional)").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(to_frame, textvariable=self.cpm_target_name_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(
            to_frame,
            text="Leave target name empty to keep the original host filename.\nIf multiple host files are selected, the optional target name is ignored.",
            justify=tk.LEFT,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        ttk.Button(to_frame, text="Copy to disk image", command=self.run_cpmcp_import).grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))

        self.cpm_output = scrolledtext.ScrolledText(parent, wrap=tk.WORD, height=14)
        self.cpm_output.grid(row=5, column=0, sticky="nsew")
        self.cpm_output.configure(state="disabled")

    def find_files(self, root_path: Path) -> ScanResults:
        roms: list[Path] = []
        disks: list[Path] = []
        tapes: list[Path] = []

        for dirpath, _dirnames, filenames in os.walk(root_path):
            for name in filenames:
                p = Path(dirpath) / name

                if has_extension(p, ROM_EXTENSIONS):
                    roms.append(p)
                elif has_extension(p, DISK_EXTENSIONS):
                    disks.append(p)
                elif p.suffix.lower() in TAPE_EXTENSIONS:
                    tapes.append(p)

        roms.sort(key=lambda p: str(p).lower())
        disks.sort(key=lambda p: str(p).lower())
        tapes.sort(key=lambda p: str(p).lower())
        return ScanResults(roms=roms, disks=disks, tapes=tapes)

    def scan_files(self, show_errors: bool = True) -> None:
        root = Path(self.search_root_var.get().strip()).expanduser()
        if not root.exists() or not root.is_dir():
            if show_errors:
                messagebox.showerror(APP_NAME, "Please choose a valid search root folder.")
            return

        self.status_var.set("Scanning...")
        self.root.update_idletasks()

        self.scan_results = self.find_files(root)
        self.populate_listboxes()
        self.restore_previous_selection()
        self.refresh_command_preview()

        self.status_var.set(
            f"Found {len(self.scan_results.roms)} ROM(s), {len(self.scan_results.disks)} disk image(s), and {len(self.scan_results.tapes)} tape file(s)."
        )
        self.update_setup_info()
        if hasattr(self, "diagnostics_text"):
            self.refresh_diagnostics()

    def populate_listboxes(self) -> None:
        self.rom_list.delete(0, tk.END)
        self.disk_list.delete(0, tk.END)
        self.tape_list.delete(0, tk.END)

        for path in self.scan_results.roms:
            self.rom_list.insert(tk.END, self.display_mounted_path(path))

        for path in self.scan_results.disks:
            self.disk_list.insert(tk.END, self.display_mounted_path(path))

        for path in self.scan_results.tapes:
            self.tape_list.insert(tk.END, self.display_mounted_path(path))

        self.update_setup_info()

    def display_path(self, path: Path) -> str:
        try:
            base = Path(self.search_root_var.get().strip()).expanduser()
            return str(path.relative_to(base))
        except Exception:
            return str(path)

    def display_mounted_path(self, path: Path) -> str:
        return path.name

    def infer_cpm_format_for_disk(self, path: Path | None) -> str:
        if path is None:
            return ""
        lower_name = path.name.lower()
        for fmt in ("ds40", "ss80", "ds80", "ds82", "ds84"):
            if fmt in lower_name:
                return fmt
        return ""

    def infer_cpm_image_type_for_disk(self, path: Path | None) -> str:
        if path is None:
            return ""
        lower_name = path.name.lower()
        if lower_name.endswith('.dsk') or lower_name.endswith('.dsk.gz'):
            return 'dsk'
        return ''

    def update_current_cpm_selection(self) -> None:
        disk = self.get_selected_disk_path()
        if disk is None:
            self.current_cpm_disk_var.set("None selected")
            return
        self.current_cpm_disk_var.set(disk.name)
        inferred = self.infer_cpm_format_for_disk(disk)
        if inferred:
            self.cpm_format_var.set(inferred)

    def on_disk_selection_changed(self, _event=None) -> None:
        self.refresh_command_preview()
        self.update_current_cpm_selection()

    def on_rom_selection_changed(self, _event=None) -> None:
        rom = self.get_selected_rom_path()
        if rom is not None:
            if self.advanced_mode_var.get():
                self.default_rom1_var.set(str(rom))
                self.status_var.set(f"Selected ROM override: {rom.name}")
            else:
                self.status_var.set(f"Selected ROM: {rom.name}. Enable Advanced mode to use it as a ROM override.")
        self.refresh_command_preview()

    def on_tape_selection_changed(self, _event=None) -> None:
        tape = self.get_selected_tape_path()
        if tape is not None:
            self.status_var.set(f"Selected tape: {tape.name}. Press 'Use tape' to mount it as input.")

    def infer_tape_kind_for_path(self, path: Path | None) -> str:
        if path is None:
            return ""
        suffix = path.suffix.lower()
        if suffix == ".wav":
            return "WAV"
        if suffix == ".tap":
            return "TAP"
        return ""

    def selected_tape_kind(self, tape: Path) -> str:
        mode = self.tape_mode_var.get().strip()
        if mode in {"WAV", "TAP"}:
            return mode
        return self.infer_tape_kind_for_path(tape)

    def use_selected_tape_input(self) -> None:
        tape = self.get_selected_tape_path()
        if tape is None:
            messagebox.showerror(APP_NAME, "Select a WAV or TAP tape file first.")
            return
        if not self.infer_tape_kind_for_path(tape):
            messagebox.showerror(APP_NAME, "Tape input supports WAV and TAP files only.")
            return
        self.mounted_tape_var.set(str(tape))
        if self.tape_mode_var.get().strip() not in TAPE_MODES:
            self.tape_mode_var.set("Auto")
        self.status_var.set(f"Mounted tape input: {tape.name}")
        self.refresh_command_preview()

    def clear_tape_input(self) -> None:
        self.tape_mode_var.set("Auto")
        self.mounted_tape_var.set("")
        self.status_var.set("Cleared tape input.")
        self.refresh_command_preview()

    def update_mounted_drive_displays(self) -> None:
        for drive in ("A", "B", "C", "D"):
            value = self.mounted_drive_vars[drive].get().strip()
            self.mounted_drive_display_vars[drive].set(Path(value).name if value else "")

    def restore_previous_selection(self) -> None:
        last_disk = self.config.get("last_disk", "")

        if last_disk:
            for i, p in enumerate(self.scan_results.disks):
                if str(p) == last_disk:
                    self.disk_list.selection_clear(0, tk.END)
                    self.disk_list.selection_set(i)
                    self.disk_list.see(i)
                    break
        self.update_current_cpm_selection()

    def get_selected_rom_path(self) -> Path | None:
        sel = self.rom_list.curselection()
        if not sel:
            return None
        return self.scan_results.roms[sel[0]]

    def get_selected_disk_path(self) -> Path | None:
        sel = self.disk_list.curselection()
        if not sel:
            return None
        return self.scan_results.disks[sel[0]]

    def get_selected_tape_path(self) -> Path | None:
        sel = self.tape_list.curselection()
        if not sel:
            return None
        return self.scan_results.tapes[sel[0]]

    def get_mounted_floppy_paths(self) -> dict[str, Path]:
        mounted: dict[str, Path] = {}
        for drive in ("A", "B", "C", "D"):
            value = self.mounted_drive_vars[drive].get().strip()
            if value:
                mounted[drive] = Path(value)
        return mounted

    def mount_selected_to_drive(self, drive: str) -> None:
        disk = self.get_selected_disk_path()
        if disk is None:
            messagebox.showerror(APP_NAME, "Select a disk image first.")
            return
        if not self.is_floppy_image(disk):
            messagebox.showerror(APP_NAME, f"Drive {drive}: needs a floppy disk image such as .dsk, .ds80_, or .ss80_.")
            return
        self.mounted_drive_vars[drive].set(str(disk))
        self.update_mounted_drive_displays()
        self.status_var.set(f"Mounted {disk.name} in drive {drive}.")
        self.refresh_command_preview()

    def clear_mounted_drive(self, drive: str) -> None:
        self.mounted_drive_vars[drive].set("")
        self.update_mounted_drive_displays()
        self.status_var.set(f"Cleared mounted disk in drive {drive}.")
        self.refresh_command_preview()

    def clear_mounted_drives_silent(self) -> None:
        for drive in ("A", "B", "C", "D"):
            self.mounted_drive_vars[drive].set("")
        self.update_mounted_drive_displays()

    def clear_all_mounted_drives(self) -> None:
        self.clear_mounted_drives_silent()
        self.status_var.set("Cleared all mounted drives.")
        self.refresh_command_preview()

    def is_floppy_image(self, path: Path | None) -> bool:
        if path is None:
            return False
        return has_extension(path, FLOPPY_EXTENSIONS)

    def is_ide_image(self, path: Path | None) -> bool:
        if path is None:
            return False
        return has_extension(path, IDE_EXTENSIONS)

    def build_command(self) -> list[str]:
        ubee = self.ubee_var.get().strip()
        if not ubee:
            return []

        cmd: list[str] = [ubee]
        boot_mode = self.normalize_boot_mode(self.boot_mode_var.get().strip())
        if boot_mode != self.boot_mode_var.get().strip():
            self.boot_mode_var.set(boot_mode)

        extra = self.extra_args_var.get().strip()

        # Custom arguments only is a true manual command mode.
        # It does not add printer, tape, ROM, model, IDE, or mounted floppy arguments.
        if self.advanced_mode_var.get() and boot_mode == "Custom arguments only":
            if extra:
                try:
                    cmd.extend(shlex.split(extra))
                except ValueError:
                    cmd.extend(extra.split())
            return cmd

        printer_mode = self.printer_mode_label(self.printer_mode_var.get())
        printer_output = self.printer_output_var.get().strip()
        if self.advanced_mode_var.get() and printer_mode != "Off":
            cmd.append("--parallel-port=printer")
            if printer_output:
                if printer_mode == "ASCII decimal (--printa)":
                    cmd.append(f"--printa={printer_output}")
                else:
                    cmd.append(f"--print={printer_output}")

        model = self.model_var.get().strip()

        # The model only affects the command when Launch mode is explicitly Model select.
        if self.advanced_mode_var.get() and boot_mode == "Model select" and model:
            cmd.append(f"--model={model}")

        mounted_floppies = self.get_mounted_floppy_paths()
        disk_flags_allowed = boot_mode in {"Auto / plain launch", "Model select"}

        # Selecting a disk in the media list is only a selection. Disk flags are
        # added only when the user explicitly mounts a disk to A/B/C/D.
        if mounted_floppies and disk_flags_allowed:
            for drive, flag in (("A", "-a"), ("B", "-b"), ("C", "-c"), ("D", "-d")):
                path = mounted_floppies.get(drive)
                if path is not None:
                    cmd.extend([flag, str(path)])

        if self.advanced_mode_var.get() and boot_mode == "IDE/CF boot":
            disk = self.get_selected_disk_path()
            rom256k = self.rom256k_var.get().strip()
            if rom256k and rom256k.lower() != "none":
                cmd.append(f"--rom256k={rom256k}")
            if disk and self.is_ide_image(disk):
                cmd.append(f"--ide-a0={disk}")

        tape_text = self.mounted_tape_var.get().strip()
        if boot_mode != "Custom arguments only" and tape_text:
            tape = Path(tape_text).expanduser()
            tape_kind = self.selected_tape_kind(tape)
            if tape_kind == "WAV":
                cmd.append(f"--tapei={tape}")
            elif tape_kind == "TAP":
                cmd.append(f"--tapfilei={tape}")

        rom_text = self.default_rom1_var.get().strip()
        if self.advanced_mode_var.get() and rom_text:
            rom = Path(rom_text).expanduser()
            if rom.is_file():
                cmd.append(f"--rom1={rom}")

        # Extra args remain available in the guided modes, except that Custom
        # arguments only returns earlier as a clean manual command.
        if self.advanced_mode_var.get() and extra:
            try:
                cmd.extend(shlex.split(extra))
            except ValueError:
                cmd.extend(extra.split())

        return cmd

    def refresh_command_preview(self) -> None:
        cmd = self.build_command()
        command_text = self.shell_join(cmd) if cmd else ""
        self.command_preview_var.set(command_text)
        if hasattr(self, "command_preview_text"):
            self.command_preview_text.configure(state="normal")
            self.command_preview_text.delete("1.0", tk.END)
            self.command_preview_text.insert("1.0", command_text)
            self.command_preview_text.configure(state="disabled")

    def copy_command(self) -> None:
        cmd = self.command_preview_var.get().strip()
        if not cmd:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(cmd)
        self.status_var.set("Command copied to clipboard.")

    def show_keyboard_help(self) -> None:
        help_text = (
            "Microbee / uBee512 key mapping\n"
            "===============================\n\n"
            "Microbee key differences\n"
            "------------------------\n"
            "256TC / Teleterm models\n"
            "  SELECT    = Page Up\n\n"
            "Standard / Premium models\n"
            "  LINEFEED  = Page Up\n"
            "  RESET     = Page Down\n"
            "  SHIFT 0   = Shift + Insert\n\n"
            "All models\n"
            "  BREAK     = Pause / Break\n"
            "  Function keys = Ctrl + number\n\n"
            "Emulator control\n"
            "----------------\n"
            "  End                 = Exit emulator\n"
            "  Page Down           = Reset emulator\n"
            "  Esc + Page Down     = Bypass confirmation on reset\n\n"
            "EMUKEY\n"
            "------\n"
            "EMUKEY is Home or Alt.\n"
            "On 256TC / Teleterm, Alt is only usable if --lpen is enabled.\n\n"
            "Useful EMUKEY shortcuts\n"
            "-----------------------\n"
            "  EMUKEY + Enter       = Full screen\n"
            "  EMUKEY + T           = Tape rewind\n"
            "  EMUKEY + S           = Sound mute\n"
            "  EMUKEY + P           = Pause emulator\n"
            "  EMUKEY + Up/Down     = Volume up / down\n"
            "  EMUKEY + W           = Mouse wheel mode\n"
            "  EMUKEY + M           = Microbee mouse toggle\n"
            "  EMUKEY + C           = Console mode\n"
            "  EMUKEY + F           = OpenGL filter toggle\n"
            "  EMUKEY + Page Down   = Power cycle\n\n"
            "Printer reminder\n"
            "----------------\n"
            "  OUTL#1   = printer device\n"
            "  OUTL#0   = screen output\n"
            '  LPRINT "TEST"\n'
            "  LLIST\n"
        )

        window = tk.Toplevel(self.root)
        window.title("Keyboard Help")
        window.geometry("760x520")
        window.minsize(980, 680)
        window.transient(self.root)

        frame = ttk.Frame(window, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert("1.0", help_text)
        text.configure(state="disabled")

        button_row = ttk.Frame(frame)
        button_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_row, text="Close", command=window.destroy).pack(side=tk.RIGHT)

    def launch_ubee(self) -> None:
        cmd = self.build_command()
        if not cmd:
            messagebox.showerror(APP_NAME, "No command to run.")
            return

        printer_mode = self.printer_mode_label(self.printer_mode_var.get())
        if self.advanced_mode_var.get() and printer_mode != "Off":
            reminder = (
                "You have decided to boot with print to file enabled.\n\n"
                "Remember to set the output device correctly in BASIC:\n\n"
                "OUTL#1   sends printer output to the parallel printer device\n"
                "OUTL#0   sends output to the screen\n\n"
                "Useful commands:\n"
                'LPRINT "TEST"\n'
                "LLIST\n\n"
                "Printed data may not appear in the host file until uBee512 closes the printer file or exits.\n\n"
                "Press OK to continue launching."
            )
            proceed = messagebox.askokcancel(APP_NAME, reminder)
            if not proceed:
                self.status_var.set("Launch cancelled.")
                return

        tape_text = self.mounted_tape_var.get().strip()
        if self.normalize_boot_mode(self.boot_mode_var.get().strip()) != "Custom arguments only" and tape_text:
            reminder = (
                "You have mounted a tape file as emulator input.\n\n"
                "WAV files use --tapei. TAP files use --tapfilei.\n"
                "Only one tape input is mounted by the launcher at a time.\n\n"
                "At the BASIC READY prompt, try:\n"
                '  LOAD ""\n'
                "then press Alt+T / EMUKEY+T to rewind and start the tape.\n\n"
                "Some BASIC versions may use CLOAD instead. If LOAD gives a syntax error, try CLOAD.\n"
                "When loading finishes, type RUN if the program does not auto-start.\n\n"
                "Press OK to continue launching."
            )
            proceed = messagebox.askokcancel(APP_NAME, reminder)
            if not proceed:
                self.status_var.set("Launch cancelled.")
                return

        boot_mode = self.normalize_boot_mode(self.boot_mode_var.get().strip())
        disk = self.get_selected_disk_path()
        if self.advanced_mode_var.get() and boot_mode == "IDE/CF boot" and disk and not self.is_ide_image(disk):
            messagebox.showerror(APP_NAME, "IDE/CF boot needs a hard disk image such as .hd0, .hd1, .hd2, .hdd, or .img.")
            return

        # No validation is needed for the selected media-list disk in other modes because
        # selection alone no longer adds boot media. mount_selected_to_drive()
        # already validates mounted floppy images before they reach the command.
        boot_warning = self.selected_model_boot_warning()
        if boot_warning:
            proceed = messagebox.askokcancel(APP_NAME, boot_warning + "\n\nPress OK to continue launching anyway.")
            if not proceed:
                self.status_var.set("Launch cancelled.")
                return

        executable = cmd[0]
        if os.path.sep not in executable and shutil.which(executable) is None:
            messagebox.showerror(
                APP_NAME,
                f"Could not find '{executable}' in PATH. Set the full path to your ubee512 executable.",
            )
            return

        env = os.environ.copy()
        env["HOME"] = str(Path.home())
        library_path = self.library_path_var.get().strip()
        if self.advanced_mode_var.get() and library_path:
            existing = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = f"{library_path}:{existing}" if existing else library_path

        try:
            subprocess.Popen(cmd, start_new_session=True, env=env, cwd=str(Path.home()))
            self.save_config()
            self.status_var.set("Ubee512 process started.")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Failed to launch Ubee512:\n\n{exc}")

    def shell_join(self, cmd: list[str]) -> str:
        return shlex.join(cmd)

    def set_text_widget(self, widget: scrolledtext.ScrolledText, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def append_cpm_output(self, text: str) -> None:
        self.cpm_output.configure(state="normal")
        self.cpm_output.delete("1.0", tk.END)
        self.cpm_output.insert("1.0", text)
        self.cpm_output.configure(state="disabled")

    def refresh_printer_preview(self) -> None:
        printer_text = self.printer_output_var.get().strip()
        if not printer_text:
            self.set_text_widget(self.printer_preview, "Printer output file not set.")
            return

        path = Path(printer_text).expanduser()
        if not path.exists():
            self.set_text_widget(self.printer_preview, "Printer output file not found yet.")
            return
        if not path.is_file():
            self.set_text_widget(self.printer_preview, f"Printer output path is not a file:\n\n{path}")
            return
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            text = f"Could not read printer output file:\n\n{exc}"
        self.set_text_widget(self.printer_preview, text)

    def open_path_in_file_manager(self, path: Path) -> None:
        target = path.expanduser()
        try:
            subprocess.Popen(["xdg-open", str(target)])
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not open path:\n\n{exc}")

    def open_printer_file(self) -> None:
        self.open_path_in_file_manager(Path(self.printer_output_var.get().strip()))

    def open_printer_folder(self) -> None:
        self.open_path_in_file_manager(Path(self.printer_output_var.get().strip()).expanduser().parent)

    def clear_printer_output(self) -> None:
        path = Path(self.printer_output_var.get().strip()).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        self.refresh_printer_preview()
        self.status_var.set("Printer output cleared.")

    def export_printer_output(self) -> None:
        source = Path(self.printer_output_var.get().strip()).expanduser()
        if not source.exists():
            messagebox.showerror(APP_NAME, "Printer output file does not exist yet.")
            return
        dest = filedialog.asksaveasfilename(title="Save printer output as", initialfile=source.name)
        if not dest:
            return
        shutil.copy2(source, dest)
        self.status_var.set("Printer output exported.")

    def copy_all_printer_output(self) -> None:
        text = self.printer_preview.get("1.0", tk.END).rstrip()
        if not text:
            self.status_var.set("Printer output is empty.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("Printer output copied to clipboard.")

    def build_cpm_base_command(self, executable: str, disk: Path) -> list[str]:
        cmd = [executable]
        cpm_format = self.cpm_format_var.get().strip() or self.infer_cpm_format_for_disk(disk)
        if cpm_format:
            cmd.extend(["-f", cpm_format])
        image_type = self.infer_cpm_image_type_for_disk(disk)
        if image_type:
            cmd.extend(["-T", image_type])
        cmd.append(str(disk))
        return cmd

    def run_cpmls(self) -> None:
        disk = self.get_selected_disk_path()
        executable = self.cpmls_var.get().strip()
        if disk is None:
            messagebox.showerror(APP_NAME, "Select a disk image first.")
            return
        if not executable:
            messagebox.showerror(APP_NAME, "Set the cpmls executable first.")
            return

        cmd = self.build_cpm_base_command(executable, disk)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                cwd=str(Path(executable).expanduser().resolve().parent),
            )
            output = self.shell_join(cmd) + "\n\n"
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            if result.returncode != 0:
                output += f"\nReturn code: {result.returncode}\n"
            self.append_cpm_output(output)
            self.status_var.set("Inspected disk image.")
        except Exception as exc:
            self.append_cpm_output(f"Failed to inspect disk image:\n\n{exc}")

    def run_cpmcp_export(self) -> None:
        disk = self.get_selected_disk_path()
        executable = self.cpmcp_var.get().strip()
        filename = self.cpm_filename_var.get().strip() or "*.*"
        user = self.cpm_user_var.get().strip() or "0"
        export_dir = Path(self.host_export_dir_var.get().strip()).expanduser()
        if disk is None:
            messagebox.showerror(APP_NAME, "Select a disk image first.")
            return
        if not executable:
            messagebox.showerror(APP_NAME, "Set the cpmcp executable first.")
            return

        export_dir.mkdir(parents=True, exist_ok=True)
        cmd = self.build_cpm_base_command(executable, disk)
        cmd.extend([f"{user}:{filename}", str(export_dir)])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            output = self.shell_join(cmd) + "\n\n"
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            if result.returncode == 0:
                output += f"\nCopied from disk image to: {export_dir}\n"
                self.status_var.set(f"Copied from disk image to {export_dir}")
            else:
                output += f"\nReturn code: {result.returncode}\n"
            self.append_cpm_output(output)
        except Exception as exc:
            self.append_cpm_output(f"Failed to copy from disk image:\n\n{exc}")

    def prompt_for_disk_backup(self, disk: Path, user: str, import_files: list[Path]) -> bool:
        summary = "\n".join(f"- {path.name}" for path in import_files)
        message = (
            "You are about to copy files to this disk image:\n\n"
            f"{disk.name}\n\n"
            f"CP/M user: {user}\n"
            f"Files:\n{summary}\n\n"
            "Writing to a disk image can change or overwrite data.\n"
            "Would you like to create a backup copy first?"
        )
        choice = messagebox.askyesnocancel(APP_NAME, message, icon=messagebox.WARNING)
        if choice is None:
            self.status_var.set("Copy to disk image cancelled.")
            return False
        if choice:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = disk.with_name(f"{disk.stem}_backup_{timestamp}{disk.suffix}")
            try:
                shutil.copy2(disk, backup_path)
                self.status_var.set(f"Backup created: {backup_path.name}")
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Could not create disk backup:\n\n{exc}")
                self.status_var.set("Copy to disk image cancelled.")
                return False
        return True

    def run_cpmcp_import(self) -> None:
        disk = self.get_selected_disk_path()
        executable = self.cpmcp_var.get().strip()
        import_files_text = self.host_import_files_var.get().strip()
        user = self.cpm_user_var.get().strip() or "0"
        target_name = self.cpm_target_name_var.get().strip()
        if disk is None:
            messagebox.showerror(APP_NAME, "Select a disk image first.")
            return
        if not executable:
            messagebox.showerror(APP_NAME, "Set the cpmcp executable first.")
            return
        if not import_files_text:
            messagebox.showerror(APP_NAME, "Select one or more host files first.")
            return

        import_files = [Path(part.strip()).expanduser() for part in import_files_text.split(";") if part.strip()]
        missing = [str(path) for path in import_files if not path.exists()]
        if missing:
            messagebox.showerror(APP_NAME, "These host files were not found:\n\n" + "\n".join(missing))
            return

        if not self.prompt_for_disk_backup(disk, user, import_files):
            return

        cmd = self.build_cpm_base_command(executable, disk)
        cmd.extend(str(path) for path in import_files)
        if len(import_files) == 1 and target_name:
            destination = f"{user}:{target_name}"
        else:
            destination = f"{user}:"
        cmd.append(destination)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            output = self.shell_join(cmd) + "\n\n"
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            if result.returncode == 0:
                output += f"\nCopied {len(import_files)} host file(s) to disk image.\n"
                self.status_var.set(f"Copied {len(import_files)} host file(s) to disk image")
            else:
                output += f"\nReturn code: {result.returncode}\n"
            self.append_cpm_output(output)
        except Exception as exc:
            self.append_cpm_output(f"Failed to copy to disk image:\n\n{exc}")

    def open_export_folder(self) -> None:
        self.open_path_in_file_manager(Path(self.host_export_dir_var.get().strip()))

    def show_cpm_examples(self) -> None:
        disk = self.get_selected_disk_path()
        disk_text = str(disk) if disk else "/path/to/disk.dsk"
        cpm_format = self.cpm_format_var.get().strip() or self.infer_cpm_format_for_disk(disk) or "your-format"
        filename = self.cpm_filename_var.get().strip() or "*.*"
        user = self.cpm_user_var.get().strip() or "0"
        export_dir = Path(self.host_export_dir_var.get().strip()).expanduser()
        target_name = self.cpm_target_name_var.get().strip() or "FILE.BAS"

        example_text = (
            "Example CP/M tools commands for the selected disk image:\n\n"
            f"Inspect disk image:\ncpmls -f {cpm_format} {disk_text}\n\n"
            f"Copy from disk image:\ncpmcp -f {cpm_format} {disk_text} {user}:{filename} {export_dir}\n\n"
            f"Copy to disk image:\ncpmcp -f {cpm_format} {disk_text} /path/to/host/file {user}:{target_name}\n"
        )
        self.append_cpm_output(example_text)

    def on_close(self) -> None:
        self.save_config()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    UbeeLauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
