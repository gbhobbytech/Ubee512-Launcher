#!/usr/bin/env python3
"""
Ubee512 Launcher for Windows

A Windows desktop launcher for Ubee512 that:
- remembers emulator, library, and data paths
- scans recursively for ROMs, disks, and tape files
- launches Ubee512 with a sensible default ROM
- previews the exact command before launch
- provides a printer-output workflow
- provides basic CP/M tools integration
"""

from __future__ import annotations

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

APP_NAME = "Anthony's Ubee512 Launcher - Windows"

# This edition is intentionally Windows-specific.
IS_WINDOWS = True

CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Ubee512 Launcher"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_UBEE_EXECUTABLE = Path("C:/ubee512/ubee512.exe")
DEFAULT_LIBRARY_PATH = Path("C:/ubee512")
DEFAULT_SEARCH_ROOT = Path.home() / "Documents" / "Ubee512"
DEFAULT_ROM1_PATH = DEFAULT_SEARCH_ROOT / "roms" / "rom1.bin"
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
    ".mwb",
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
    "Plain launch",
    "Floppy A (-a)",
    "Floppy B (-b)",
    "CF/IDE boot (--ide-a0)",
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

CPM_FORMAT_PRESETS = [
    "",
    "ds40",
    "ss80",
    "ds80",
    "ds82",
    "ds84",
]


def default_cpmtools_path(name: str) -> str:
    """Return a sensible Windows default for optional cpmtools utilities."""
    exe_name = name if name.lower().endswith(".exe") else f"{name}.exe"
    candidates = [
        Path("C:/ubee512/tools/cpmtools-2.10") / exe_name,
        Path.home() / "ubee512" / "tools" / "cpmtools-2.10" / exe_name,
    ]
    for bundled in candidates:
        if bundled.exists():
            return str(bundled)
    return exe_name


DEFAULT_CONFIG = {
    "ubee_executable": str(DEFAULT_UBEE_EXECUTABLE),
    "library_path": str(DEFAULT_LIBRARY_PATH),
    "search_root": str(DEFAULT_SEARCH_ROOT),
    "model_preset": "pcf",
    "rom256k": "none",
    "extra_args": "",
    "last_boot_mode": "Plain launch",
    "last_rom": str(DEFAULT_ROM1_PATH),
    "last_disk": "",
    "printer_output_file": str(DEFAULT_PRINTER_FILE),
    "printer_mode": "Off",
    "cpmls_executable": default_cpmtools_path("cpmls"),
    "cpmcp_executable": default_cpmtools_path("cpmcp"),
    "cpm_format": "",
    "cpm_user": "0",
    "cpm_filename": "*.*",
    "cpm_target_name": "",
    "host_export_dir": str(DEFAULT_HOST_EXPORT_DIR),
    "include_hidden": False,
    "mounted_drive_a": "",
    "mounted_drive_b": "",
    "mounted_drive_c": "",
    "mounted_drive_d": "",
    "advanced_mode": False,
}


@dataclass
class ScanResults:
    roms: list[Path]
    disks: list[Path]
    tapes: list[Path]


def has_extension(path: Path, extensions: set[str]) -> bool:
    lower_name = path.name.lower()
    return any(lower_name.endswith(ext) for ext in extensions)


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
        self.root.geometry("1160x760")
        self.root.minsize(1220, 1140)

        self.config = self.load_config()
        self.scan_results = ScanResults([], [], [])

        self.ubee_var = tk.StringVar(value=self.config.get("ubee_executable", DEFAULT_CONFIG["ubee_executable"]))
        self.search_root_var = tk.StringVar(value=self.config.get("search_root", DEFAULT_CONFIG["search_root"]))
        self.library_path_var = tk.StringVar(value=self.config.get("library_path", DEFAULT_CONFIG["library_path"]))
        self.model_var = tk.StringVar(value=self.config.get("model_preset", DEFAULT_CONFIG["model_preset"]))
        self.rom256k_var = tk.StringVar(value=self.config.get("rom256k", DEFAULT_CONFIG["rom256k"]))
        self.boot_mode_var = tk.StringVar(value=self.config.get("last_boot_mode", DEFAULT_CONFIG["last_boot_mode"]))
        self.extra_args_var = tk.StringVar(value=self.config.get("extra_args", DEFAULT_CONFIG["extra_args"]))
        self.status_var = tk.StringVar(value="Set your Windows paths, scan, then launch.")
        self.command_preview_var = tk.StringVar(value="")
        self.default_rom1_var = tk.StringVar(value=self.config.get("last_rom", DEFAULT_CONFIG["last_rom"]))
        self.include_hidden_var = tk.BooleanVar(value=self.config.get("include_hidden", DEFAULT_CONFIG["include_hidden"]))
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

        self._build_ui()
        self.update_mode_ui()
        self._bind_events()
        self.refresh_command_preview()
        self.refresh_printer_preview()
        self.update_current_cpm_selection()

    def load_config(self) -> dict:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                return {**DEFAULT_CONFIG, **json.loads(CONFIG_FILE.read_text(encoding="utf-8"))}
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
            "printer_output_file": self.printer_output_var.get().strip(),
            "printer_mode": self.printer_mode_label(self.printer_mode_var.get()),
            "cpmls_executable": self.cpmls_var.get().strip(),
            "cpmcp_executable": self.cpmcp_var.get().strip(),
            "cpm_format": self.cpm_format_var.get().strip(),
            "cpm_user": self.cpm_user_var.get().strip(),
            "cpm_filename": self.cpm_filename_var.get().strip(),
            "cpm_target_name": self.cpm_target_name_var.get().strip(),
            "host_export_dir": self.host_export_dir_var.get().strip(),
            "include_hidden": self.include_hidden_var.get(),
            "mounted_drive_a": self.mounted_drive_vars["A"].get().strip(),
            "mounted_drive_b": self.mounted_drive_vars["B"].get().strip(),
            "mounted_drive_c": self.mounted_drive_vars["C"].get().strip(),
            "mounted_drive_d": self.mounted_drive_vars["D"].get().strip(),
            "advanced_mode": self.advanced_mode_var.get(),
        }
        CONFIG_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _build_ui(self) -> None:
        """Build a compact wide layout that resizes cleanly on desktop displays."""
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=0)

        self.root.geometry("1380x820")
        self.root.minsize(1120, 680)

        top = ttk.LabelFrame(self.root, text="Paths and launch settings", padding=(10, 8))
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        for col in (1, 4):
            top.columnconfigure(col, weight=1)

        ttk.Label(top, text="Ubee executable").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(top, textvariable=self.ubee_var).grid(row=0, column=1, columnspan=4, sticky="ew", pady=2)
        ttk.Button(top, text="Find", command=self.choose_ubee_executable, width=10).grid(row=0, column=5, padx=(6, 0), pady=2)

        ttk.Label(top, text="Search root").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(top, textvariable=self.search_root_var).grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Button(top, text="Browse", command=self.choose_search_root, width=10).grid(row=1, column=2, padx=(6, 14), pady=2)

        ttk.Label(top, text="Library path").grid(row=1, column=3, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(top, textvariable=self.library_path_var).grid(row=1, column=4, sticky="ew", pady=2)
        ttk.Button(top, text="Browse", command=self.choose_library_path, width=10).grid(row=1, column=5, padx=(6, 0), pady=2)

        controls = ttk.Frame(top)
        controls.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(6, 0))
        controls.columnconfigure(9, weight=1)

        ttk.Label(controls, text="Boot mode").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            controls,
            textvariable=self.boot_mode_var,
            values=BOOT_MODES,
            state="readonly",
            width=22,
        ).grid(row=0, column=1, sticky="w", padx=(6, 14))

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
        self.rom256k_entry = ttk.Entry(controls, textvariable=self.rom256k_var, width=10)
        self.rom256k_entry.grid(row=0, column=5, sticky="w", padx=(6, 14))

        ttk.Checkbutton(controls, text="Include hidden", variable=self.include_hidden_var).grid(
            row=0, column=6, sticky="w", padx=(0, 10)
        )
        ttk.Checkbutton(
            controls,
            text="Advanced mode",
            variable=self.advanced_mode_var,
            command=self.update_mode_ui,
        ).grid(row=0, column=7, sticky="w", padx=(0, 10))
        ttk.Button(controls, text="Scan files", command=self.scan_files, width=12).grid(row=0, column=8, sticky="w")
        ttk.Label(controls, textvariable=self.status_var).grid(row=0, column=9, sticky="e", padx=(12, 0))

        middle = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        middle.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)

        files_area = ttk.LabelFrame(middle, text="Media library", padding=8)
        right = ttk.Frame(middle, padding=0)
        middle.add(files_area, weight=2)
        middle.add(right, weight=5)

        files_area.columnconfigure(0, weight=1)
        files_area.columnconfigure(1, weight=0)
        files_area.columnconfigure(2, weight=1)
        files_area.columnconfigure(3, weight=0)
        files_area.rowconfigure(1, weight=1)
        files_area.rowconfigure(3, weight=1)

        ttk.Label(files_area, text="Disk images", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.disk_list = tk.Listbox(files_area, exportselection=False, height=18)
        self.disk_list.grid(row=1, column=0, rowspan=3, sticky="nsew", pady=(4, 0), padx=(0, 4))
        disk_scroll = ttk.Scrollbar(files_area, orient="vertical", command=self.disk_list.yview)
        disk_scroll.grid(row=1, column=1, rowspan=3, sticky="ns", pady=(4, 0), padx=(0, 8))
        self.disk_list.configure(yscrollcommand=disk_scroll.set)

        ttk.Label(files_area, text="Tape files", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=2, sticky="w")
        self.tape_list = tk.Listbox(files_area, exportselection=False, height=8)
        self.tape_list.grid(row=1, column=2, sticky="nsew", pady=(4, 8), padx=(0, 4))
        tape_scroll = ttk.Scrollbar(files_area, orient="vertical", command=self.tape_list.yview)
        tape_scroll.grid(row=1, column=3, sticky="ns", pady=(4, 8))
        self.tape_list.configure(yscrollcommand=tape_scroll.set)

        ttk.Label(files_area, text="ROMs", font=("TkDefaultFont", 10, "bold")).grid(row=2, column=2, sticky="w")
        self.rom_list = tk.Listbox(files_area, exportselection=False, height=8)
        self.rom_list.grid(row=3, column=2, sticky="nsew", pady=(4, 0), padx=(0, 4))
        rom_scroll = ttk.Scrollbar(files_area, orient="vertical", command=self.rom_list.yview)
        rom_scroll.grid(row=3, column=3, sticky="ns", pady=(4, 0))
        self.rom_list.configure(yscrollcommand=rom_scroll.set)

        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.workflow = ttk.Notebook(right)
        self.workflow.grid(row=0, column=0, sticky="nsew")

        self.printer_tab = ttk.Frame(self.workflow, padding=8)
        self.cpm_tab = ttk.Frame(self.workflow, padding=0)
        self.workflow.add(self.printer_tab, text="Printer / LPRINT")
        self.workflow.add(self.cpm_tab, text="CP/M tools")

        self._build_printer_tab(self.printer_tab)
        self._build_scrollable_cpm_tab(self.cpm_tab)

        bottom = ttk.Frame(self.root, padding=(10, 4, 10, 8))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=3)
        bottom.columnconfigure(1, weight=4)

        mounted_panel = ttk.LabelFrame(bottom, text="Mounted floppy drives", padding=(8, 6))
        mounted_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        mounted_panel.columnconfigure(1, weight=1)
        mounted_panel.columnconfigure(4, weight=1)

        for idx, drive in enumerate(("A", "B", "C", "D")):
            row = idx // 2
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
        ).grid(row=0, column=6, rowspan=2, sticky="ns", padx=(4, 0), pady=3)

        launch_panel = ttk.LabelFrame(bottom, text="Launch command", padding=(8, 6))
        launch_panel.grid(row=0, column=1, sticky="nsew")
        launch_panel.columnconfigure(1, weight=1)

        self.args_frame = launch_panel

        self.extra_args_label = ttk.Label(launch_panel, text="Extra args")
        self.extra_args_label.grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        self.extra_args_entry = ttk.Entry(launch_panel, textvariable=self.extra_args_var)
        self.extra_args_entry.grid(row=0, column=1, columnspan=3, sticky="ew", pady=2)

        ttk.Label(launch_panel, text="ROM1 file").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(launch_panel, textvariable=self.default_rom1_var).grid(row=1, column=1, columnspan=3, sticky="ew", pady=2)

        ttk.Label(launch_panel, text="Command preview").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        preview = ttk.Entry(launch_panel, textvariable=self.command_preview_var, state="readonly")
        preview.grid(row=2, column=1, columnspan=3, sticky="ew", pady=2)

        ttk.Button(launch_panel, text="Copy command", command=self.copy_command).grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Button(launch_panel, text="Keyboard Help", command=self.show_keyboard_help).grid(row=3, column=1, sticky="w", pady=(6, 0), padx=(8, 0))
        ttk.Button(launch_panel, text="Launch Ubee512", command=self.launch_ubee).grid(row=3, column=3, sticky="e", pady=(6, 0))


    def update_mode_ui(self) -> None:
        advanced = self.advanced_mode_var.get()

        for widget in [self.model_label, self.model_entry, self.rom256k_label, self.rom256k_entry]:
            if advanced:
                widget.grid()
            else:
                widget.grid_remove()

        if advanced:
            self.extra_args_label.grid()
            self.extra_args_entry.grid()
        else:
            self.extra_args_label.grid_remove()
            self.extra_args_entry.grid_remove()

        tab_ids = self.workflow.tabs()
        cpm_visible = str(self.cpm_tab) in tab_ids
        if advanced and not cpm_visible:
            self.workflow.add(self.cpm_tab, text="CP/M tools")
        elif not advanced and cpm_visible:
            self.workflow.forget(self.cpm_tab)

    def _bind_events(self) -> None:
        for var in [
            self.ubee_var,
            self.search_root_var,
            self.library_path_var,
            self.model_var,
            self.rom256k_var,
            self.boot_mode_var,
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

        self.include_hidden_var.trace_add("write", lambda *_: self.refresh_command_preview())
        self.printer_mode_var.trace_add("write", lambda *_: self.update_printer_mode_ui())
        self.rom_list.bind("<<ListboxSelect>>", self.on_rom_selection_changed)
        self.disk_list.bind("<<ListboxSelect>>", self.on_disk_selection_changed)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

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

    def _build_printer_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(3, weight=1)

        ttk.Label(parent, text="Printer mode").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        printer_mode_row = ttk.Frame(parent)
        printer_mode_row.grid(row=0, column=1, columnspan=2, sticky="ew", pady=4)
        printer_mode_row.columnconfigure(1, weight=1)
        ttk.Label(printer_mode_row, text="Off").grid(row=0, column=0, sticky="w")
        ttk.Scale(
            printer_mode_row,
            from_=0,
            to=2,
            variable=self.printer_mode_var,
            command=self.on_printer_mode_slider,
        ).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Label(printer_mode_row, text="ASCII").grid(row=0, column=2, sticky="e")
        self.printer_mode_value_label = ttk.Label(
            printer_mode_row,
            text=self.printer_mode_label(self.printer_mode_var.get()),
        )
        self.printer_mode_value_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

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

        printer_help = (
            'Use OUTL#1 for the printer device and OUTL#0 for screen output.\n'
            'Then use LPRINT "TEXT" for a quick test or LLIST for a BASIC program listing.\n'
            "Raw mode uses --print. ASCII mode uses --printa.\n"
            "Printed data may not appear in the host file until uBee512 closes the printer file or exits."
        )
        ttk.Label(parent, text=printer_help, justify=tk.LEFT).grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))

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

        help_text = (
            "Use these tools when you want to inspect a CP/M disk image or move files between the host and the disk image.\n"
            "Pick the disk image in the main Disk images list first, then choose the action you want below."
        )
        ttk.Label(parent, text=help_text, justify=tk.LEFT).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        common = ttk.LabelFrame(parent, text="Common settings", padding=8)
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

        for dirpath, dirnames, filenames in os.walk(root_path):
            if not self.include_hidden_var.get():
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]

            for name in filenames:
                if not self.include_hidden_var.get() and name.startswith("."):
                    continue

                p = Path(dirpath) / name

                if has_extension(p, ROM_EXTENSIONS):
                    roms.append(p)
                elif has_extension(p, DISK_EXTENSIONS):
                    disks.append(p)
                elif has_extension(p, TAPE_EXTENSIONS):
                    tapes.append(p)

        roms.sort(key=lambda p: str(p).lower())
        disks.sort(key=lambda p: str(p).lower())
        tapes.sort(key=lambda p: str(p).lower())
        return ScanResults(roms=roms, disks=disks, tapes=tapes)

    def scan_files(self) -> None:
        root = Path(self.search_root_var.get().strip()).expanduser()
        if not root.exists() or not root.is_dir():
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
            self.default_rom1_var.set(str(rom))
            self.status_var.set(f"Selected ROM1: {rom.name}")
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

    def clear_all_mounted_drives(self) -> None:
        for drive in ("A", "B", "C", "D"):
            self.mounted_drive_vars[drive].set("")
        self.update_mounted_drive_displays()
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

        printer_mode = self.printer_mode_label(self.printer_mode_var.get())
        printer_output = self.printer_output_var.get().strip()
        if printer_mode != "Off":
            cmd.append("--parallel-port=printer")
            if printer_output:
                if printer_mode == "ASCII decimal (--printa)":
                    cmd.append(f"--printa={printer_output}")
                else:
                    cmd.append(f"--print={printer_output}")

        model = self.model_var.get().strip()
        if model:
            cmd.append(f"--model={model}")

        boot_mode = self.boot_mode_var.get().strip()
        disk = self.get_selected_disk_path()
        rom256k = self.rom256k_var.get().strip()
        mounted_floppies = self.get_mounted_floppy_paths()

        if mounted_floppies:
            for drive, flag in (("A", "-a"), ("B", "-b"), ("C", "-c"), ("D", "-d")):
                path = mounted_floppies.get(drive)
                if path is not None:
                    cmd.extend([flag, str(path)])
        elif boot_mode == "Floppy A (-a)":
            if disk and self.is_floppy_image(disk):
                cmd.extend(["-a", str(disk)])
        elif boot_mode == "Floppy B (-b)":
            if disk and self.is_floppy_image(disk):
                cmd.extend(["-b", str(disk)])
        elif boot_mode == "CF/IDE boot (--ide-a0)":
            if rom256k:
                cmd.append(f"--rom256k={rom256k}")
            if disk and self.is_ide_image(disk):
                cmd.append(f"--ide-a0={disk}")
        elif boot_mode == "Plain launch":
            if disk and self.is_floppy_image(disk):
                cmd.extend(["-a", str(disk)])
            elif disk and self.is_ide_image(disk):
                if rom256k:
                    cmd.append(f"--rom256k={rom256k}")
                cmd.append(f"--ide-a0={disk}")

        extra = self.extra_args_var.get().strip()
        if extra:
            try:
                cmd.extend(shlex.split(extra))
            except ValueError:
                cmd.extend(extra.split())

        return cmd

    def refresh_command_preview(self) -> None:
        cmd = self.build_command()
        if not cmd:
            self.command_preview_var.set("")
            return

        rom = Path(self.default_rom1_var.get().strip()).expanduser()
        cmd = [arg for arg in cmd if not arg.startswith("--rom1=")]
        if rom.exists():
            cmd.append(f"--rom1={rom}")

        self.command_preview_var.set(self.shell_join(cmd))

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
        if printer_mode != "Off":
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

        boot_mode = self.boot_mode_var.get().strip()
        disk = self.get_selected_disk_path()
        mounted_floppies = self.get_mounted_floppy_paths()

        if not mounted_floppies and boot_mode in {"Floppy A (-a)", "Floppy B (-b)"} and disk and not self.is_floppy_image(disk):
            messagebox.showerror(APP_NAME, "Floppy boot mode needs a floppy disk image such as .dsk, .ds80_, or .ss80_.")
            return

        if boot_mode == "CF/IDE boot (--ide-a0)" and disk and not self.is_ide_image(disk):
            messagebox.showerror(APP_NAME, "CF/IDE boot needs a hard disk image such as .hd0, .hd1, .hd2, .hdd, or .img.")
            return

        executable = cmd[0]
        executable_path = Path(executable).expanduser()
        if not executable_path.is_file() and shutil.which(executable) is None:
            messagebox.showerror(
                APP_NAME,
                f"Could not find '{executable}' in PATH. Set the full path to your ubee512 executable.",
            )
            return

        env = os.environ.copy()
        env["HOME"] = str(Path.home())
        library_path = self.library_path_var.get().strip()
        if library_path:
            existing = env.get("PATH", "")
            env["PATH"] = f"{library_path};{existing}" if existing else library_path

        rom = Path(self.default_rom1_var.get().strip()).expanduser()
        cmd = [arg for arg in cmd if not arg.startswith("--rom1=")]
        if rom.exists():
            cmd.append(f"--rom1={rom}")

        try:
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            subprocess.Popen(cmd, env=env, cwd=str(Path.home()), creationflags=creationflags)
            self.save_config()
            self.status_var.set("Ubee512 launched.")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Failed to launch Ubee512:\n\n{exc}")

    def shell_join(self, cmd: list[str]) -> str:
        """Format the command preview using Windows command-line quoting."""
        return subprocess.list2cmdline([str(part) for part in cmd])

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
        path = Path(self.printer_output_var.get().strip()).expanduser()
        if not path.exists():
            self.set_text_widget(self.printer_preview, "Printer output file not found yet.")
            return
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            text = f"Could not read printer output file:\n\n{exc}"
        self.set_text_widget(self.printer_preview, text)

    def open_path_in_file_manager(self, path: Path) -> None:
        target = path.expanduser()
        try:
            os.startfile(str(target))
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
    # Build this file on Windows with:
    # py -m PyInstaller --onefile --windowed --name AnthonysUbee512Launcher Source\AnthonysUbee512WindowsLauncher.py
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
