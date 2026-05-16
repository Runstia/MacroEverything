"""
macro_app/hotkeys.py
Gestionnaire de hotkeys globaux (Windows) et dialogue de configuration.

Classes :
  HotkeyManager         — thread daemon qui surveille les touches F-keys
  HotkeySettingsDialog  — interface de configuration des raccourcis
"""

import time
import threading
import tkinter as tk
from tkinter import ttk

try:
    import ctypes
except ImportError:
    ctypes = None

from .constants import COLORS, FONTS, VK_MAP
from .utils import WINDOWS
from .i18n import t as _t


class HotkeyManager:
    DEFAULT = {"run": "F9", "stop": "F10", "pause": "F11"}

    def __init__(self, app):
        self.app      = app
        self.hotkeys  = dict(self.DEFAULT)
        self._running = True
        self._prev    = {}
        if WINDOWS and ctypes:
            self._thread = threading.Thread(target=self._poll, daemon=True)
            self._thread.start()

    def _poll(self):
        while self._running:
            for action, key in list(self.hotkeys.items()):
                vk = VK_MAP.get(key)
                if not vk:
                    continue
                state   = ctypes.windll.user32.GetAsyncKeyState(vk)
                is_down = bool(state & 0x8000)
                was     = self._prev.get(key, False)
                if is_down and not was:
                    self._trigger(action)
                self._prev[key] = is_down
            time.sleep(0.05)

    def _trigger(self, action):
        if action == "run":
            self.app.after(0, self.app._run_macro)
        elif action == "stop":
            self.app.after(0, self.app._stop_macro)
        elif action == "pause":
            self.app.after(0, self.app._pause_macro)

    def stop(self):
        self._running = False


class HotkeySettingsDialog(tk.Toplevel):
    def __init__(self, parent, hotkey_manager, on_apply=None):
        super().__init__(parent)
        self.hm = hotkey_manager
        self._on_apply_cb = on_apply
        self.title(_t("hotkeys.title"))
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)
        self._build()
        self._center()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{(self.winfo_screenwidth()-w)//2}+{(self.winfo_screenheight()-h)//2}")

    def _build(self):
        f = tk.Frame(self, bg=COLORS["bg"], padx=24, pady=20)
        f.pack(fill="both", expand=True)

        tk.Label(f, text=_t("hotkeys.header"),
                 bg=COLORS["bg"], fg=COLORS["accent"],
                 font=FONTS["heading"]).pack(anchor="w", pady=(0, 6))

        tk.Label(f,
                 text=_t("hotkeys.desc"),
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"], justify="left").pack(anchor="w", pady=(0, 14))

        self.vars = {}
        options = list(VK_MAP.keys()) + [_t("hotkeys.none")]
        labels  = {
            "run":   _t("hotkeys.run"),
            "stop":  _t("hotkeys.stop"),
            "pause": _t("hotkeys.pause"),
        }

        for action, alabel in labels.items():
            row = tk.Frame(f, bg=COLORS["bg"])
            row.pack(fill="x", pady=4)
            tk.Label(row, text=alabel, bg=COLORS["bg"], fg=COLORS["text"],
                     font=FONTS["normal"], width=22, anchor="w").pack(side="left")
            v = tk.StringVar(value=self.hm.hotkeys.get(action, _t("hotkeys.none")))
            self.vars[action] = v
            ttk.Combobox(row, textvariable=v, values=options,
                         state="readonly", width=10,
                         font=FONTS["normal"]).pack(side="left", padx=8)

        bf = tk.Frame(f, bg=COLORS["bg"])
        bf.pack(fill="x", pady=(18, 0))
        tk.Button(bf, text=_t("btn.apply"),
                  bg=COLORS["green"], fg=COLORS["bg"],
                  font=FONTS["heading"], relief="flat", cursor="hand2",
                  padx=16, pady=8, command=self._apply).pack(side="right", padx=(8, 0))
        tk.Button(bf, text=_t("btn.cancel"),
                  bg=COLORS["surface"], fg=COLORS["text"],
                  font=FONTS["normal"], relief="flat", cursor="hand2",
                  padx=16, pady=8, command=self.destroy).pack(side="right")

    def _apply(self):
        for action, var in self.vars.items():
            val = var.get()
            self.hm.hotkeys[action] = val if val != _t("hotkeys.none") else ""
        self.destroy()
        if self._on_apply_cb:
            self._on_apply_cb()
