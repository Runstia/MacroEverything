"""
macro_app/ui/app.py
Fenetre principale de l'application MacroEverything.
"""

import json
import os
import copy
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from ..constants import COLORS, FONTS, APP_VERSION
from ..utils import _play_cue
from ..models import new_macro, _remap_ids
from ..engine import MacroEngine
from ..hotkeys import HotkeyManager, HotkeySettingsDialog
from ..settings import load_settings, save_settings
from ..macros_folder import get_macros_dir, import_to_macros_dir
from .. import i18n
from ..i18n import t
from .tree_canvas import MacroTreeCanvas
from .dialogs import NodeEditorDialog, AddNodeDialog, LanguageDialog
from .panels import PropertiesPanel


def _bind_hover(btn, normal, hover):
    def _enter(e):
        if str(btn["state"]) != "disabled":
            btn.configure(bg=hover)
    btn.bind("<Enter>", _enter)
    btn.bind("<Leave>", lambda e: btn.configure(bg=normal))


class MacroEverythingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MacroEverything")
        self.geometry("1300x840")
        self.minsize(900, 600)
        self.configure(bg=COLORS["bg"])

        self._groups: list        = []
        self._current_group: dict = None
        self.current_macro: dict  = None
        self._lb_index: list      = []
        self._list_items: list    = []

        self._engine        = None
        self._engine_thread = None
        self._undo_stack    = []
        self._redo_stack    = []
        self._img_clipboard = None
        self._debug_overlay = False

        self._init_i18n()
        self._build_ui()
        self._apply_style()

        self.hotkey_manager = HotkeyManager(self)
        self._load_settings()
        self._load_all_files()
        self._update_title()
        self._refresh_hotkey_labels()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── INIT ────────────────────────────────────────────────
    def _init_i18n(self):
        data = load_settings()
        i18n.init(data.get("language", None))

    def _open_language_settings(self):
        LanguageDialog(self)

    def _on_close(self):
        dirty_groups = [g for g in self._groups if g["dirty"]]
        if dirty_groups:
            answer = messagebox.askyesnocancel(
                t("file.unsaved_title"), t("file.unsaved_msg"))
            if answer is None:
                return
            if answer:
                self._save_all_groups()
        self.hotkey_manager.stop()
        if self._engine:
            self._engine.stop()
        self.destroy()

    def _apply_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TScrollbar",
                        background=COLORS["bg3"],
                        troughcolor=COLORS["bg2"],
                        bordercolor=COLORS["bg2"],
                        arrowcolor=COLORS["text_dim"])

    # ── UI CONSTRUCTION ──────────────────────────────────────
    def _build_ui(self):
        self._build_topbar()
        self._build_bottombar()          # packer avant le frame principal
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True)
        self._build_macro_list(main)
        tk.Frame(main, bg=COLORS["border"], width=1).pack(side="left", fill="y")
        self._build_canvas_area(main)
        tk.Frame(main, bg=COLORS["border"], width=1).pack(side="left", fill="y")
        self.props_panel = PropertiesPanel(main, self)
        self.props_panel.pack(side="left", fill="both")
        self.bind_all("<Control-z>", lambda e: self._undo())
        self.bind_all("<Control-y>", lambda e: self._redo())

    def _build_topbar(self):
        bar = tk.Frame(self, bg=COLORS["bg3"], height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(bar, text="MacroEverything",
                 bg=COLORS["bg3"], fg=COLORS["accent"],
                 font=FONTS["title"]).pack(side="left", padx=(16, 4))

        # ── Groupe fichier (encadré) ──────────────────────────
        file_frame = tk.Frame(bar, bg=COLORS["bg2"],
                              highlightthickness=1,
                              highlightbackground=COLORS["surface"])
        file_frame.pack(side="left", padx=(6, 0), pady=9)

        for label, cmd in [
            (t("menu.new"),      self._new_group),
            (t("menu.open"),     self._open_file),
            (t("menu.save"),     self._save_current_group),
            (t("menu.save_all"), self._save_all_groups),
        ]:
            btn = tk.Button(file_frame, text=label,
                            bg=COLORS["bg2"], fg=COLORS["text"],
                            font=FONTS["normal"], relief="flat", cursor="hand2",
                            padx=11, pady=4, command=cmd)
            btn.pack(side="left")
            _bind_hover(btn, COLORS["bg2"], COLORS["bg3"])

        tk.Frame(bar, bg=COLORS["bg3"]).pack(side="left", fill="x", expand=True)

        # ── Version ──────────────────────────────────────────
        tk.Label(bar, text=f"v{APP_VERSION}",
                 bg=COLORS["bg3"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(side="right", padx=(0, 14))

        # ── Groupe paramètres (encadré) ───────────────────────
        cfg_frame = tk.Frame(bar, bg=COLORS["bg2"],
                             highlightthickness=1,
                             highlightbackground=COLORS["surface"])
        cfg_frame.pack(side="right", padx=(0, 6), pady=9)

        for label, cmd in [
            (t("menu.language"), self._open_language_settings),
            (t("menu.settings"), self._open_settings),
            (t("menu.hotkeys"),  self._open_hotkey_settings),
        ]:
            btn = tk.Button(cfg_frame, text=label,
                            bg=COLORS["bg2"], fg=COLORS["text_dim"],
                            font=FONTS["small"], relief="flat", cursor="hand2",
                            padx=9, pady=4, command=cmd)
            btn.pack(side="right")
            _bind_hover(btn, COLORS["bg2"], COLORS["bg3"])

    def _build_macro_list(self, parent):
        frame = tk.Frame(parent, bg=COLORS["bg2"], width=222)
        frame.pack(side="left", fill="y")
        frame.pack_propagate(False)

        hdr = tk.Frame(frame, bg=COLORS["bg3"], height=42)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=t("sidebar.my_macros"),
                 bg=COLORS["bg3"], fg=COLORS["text"],
                 font=FONTS["heading"]).pack(side="left", padx=12)
        add_btn = tk.Button(hdr, text="+",
                            bg=COLORS["accent"], fg=COLORS["bg"],
                            font=FONTS["heading"], relief="flat", cursor="hand2",
                            width=2, command=self._new_macro_in_current_group)
        add_btn.pack(side="right", padx=8)
        _bind_hover(add_btn, COLORS["accent"], "#74c7ec")

        tk.Frame(frame, bg=COLORS["border"], height=1).pack(fill="x")

        sc_wrap = tk.Frame(frame, bg=COLORS["bg2"])
        sc_wrap.pack(fill="both", expand=True)

        self._list_canvas = tk.Canvas(sc_wrap, bg=COLORS["bg2"],
                                      highlightthickness=0, bd=0)
        sc_sb = ttk.Scrollbar(sc_wrap, orient="vertical",
                               command=self._list_canvas.yview)
        self._list_canvas.configure(yscrollcommand=sc_sb.set)
        sc_sb.pack(side="right", fill="y")
        self._list_canvas.pack(side="left", fill="both", expand=True)

        self._list_inner = tk.Frame(self._list_canvas, bg=COLORS["bg2"])
        self._list_win_id = self._list_canvas.create_window(
            (0, 0), window=self._list_inner, anchor="nw")

        self._list_inner.bind(
            "<Configure>",
            lambda e: self._list_canvas.configure(
                scrollregion=self._list_canvas.bbox("all")))
        self._list_canvas.bind(
            "<Configure>",
            lambda e: self._list_canvas.itemconfig(
                self._list_win_id, width=e.width))
        self._list_canvas.bind(
            "<MouseWheel>",
            lambda e: self._list_canvas.yview_scroll(
                -1 * (e.delta // 120), "units"))

    def _build_canvas_area(self, parent):
        frame = tk.Frame(parent, bg=COLORS["bg2"])
        frame.pack(side="left", fill="both", expand=True)

        toolbar = tk.Frame(frame, bg=COLORS["bg3"], height=42)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        add_btn = tk.Button(toolbar, text=t("toolbar.add_node"),
                            bg=COLORS["accent"], fg=COLORS["bg"],
                            font=FONTS["normal"], relief="flat", cursor="hand2",
                            padx=12, pady=6, command=self.add_node_dialog)
        add_btn.pack(side="left", padx=8, pady=4)
        _bind_hover(add_btn, COLORS["accent"], "#74c7ec")

        self._undo_btn = tk.Button(toolbar, text=t("toolbar.undo"),
                                   bg=COLORS["bg3"], fg=COLORS["text_dim"],
                                   font=FONTS["small"], relief="flat",
                                   cursor="hand2", padx=8, pady=6,
                                   state="disabled", command=self._undo)
        self._undo_btn.pack(side="left", padx=(4, 0), pady=4)
        _bind_hover(self._undo_btn, COLORS["bg3"], COLORS["surface"])

        self._redo_btn = tk.Button(toolbar, text=t("toolbar.redo"),
                                   bg=COLORS["bg3"], fg=COLORS["text_dim"],
                                   font=FONTS["small"], relief="flat",
                                   cursor="hand2", padx=8, pady=6,
                                   state="disabled", command=self._redo)
        self._redo_btn.pack(side="left", padx=(2, 0), pady=4)
        _bind_hover(self._redo_btn, COLORS["bg3"], COLORS["surface"])

        self._macro_name_var = tk.StringVar()
        ne = tk.Entry(toolbar, textvariable=self._macro_name_var,
                      bg=COLORS["bg3"], fg=COLORS["text"],
                      font=FONTS["heading"], relief="flat",
                      insertbackground=COLORS["text"], width=24)
        ne.pack(side="left", padx=16, pady=6)
        ne.bind("<FocusOut>", self._on_name_change)
        ne.bind("<Return>",   self._on_name_change)

        self._loop_var = tk.BooleanVar()
        tk.Checkbutton(toolbar, text=t("toolbar.infinite_loop"),
                       variable=self._loop_var,
                       bg=COLORS["bg3"], fg=COLORS["text"],
                       selectcolor=COLORS["bg3"],
                       activebackground=COLORS["bg3"],
                       font=FONTS["normal"],
                       command=self._on_loop_change).pack(side="left", padx=4)

        tk.Frame(toolbar, bg=COLORS["border"], width=1,
                 height=24).pack(side="left", padx=(12, 0))
        tk.Label(toolbar, text=t("toolbar.resolution"),
                 bg=COLORS["bg3"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(side="left", padx=(8, 2), pady=6)
        self._res_w_var = tk.StringVar()
        res_w_e = tk.Entry(toolbar, textvariable=self._res_w_var,
                           bg=COLORS["bg3"], fg=COLORS["text"],
                           font=FONTS["small"], relief="flat",
                           insertbackground=COLORS["text"], width=5)
        res_w_e.pack(side="left", pady=6)
        res_w_e.bind("<FocusOut>", self._on_res_change)
        res_w_e.bind("<Return>",   self._on_res_change)
        tk.Label(toolbar, text="×",
                 bg=COLORS["bg3"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(side="left", padx=2)
        self._res_h_var = tk.StringVar()
        res_h_e = tk.Entry(toolbar, textvariable=self._res_h_var,
                           bg=COLORS["bg3"], fg=COLORS["text"],
                           font=FONTS["small"], relief="flat",
                           insertbackground=COLORS["text"], width=5)
        res_h_e.pack(side="left", pady=6)
        res_h_e.bind("<FocusOut>", self._on_res_change)
        res_h_e.bind("<Return>",   self._on_res_change)

        tk.Frame(frame, bg=COLORS["border"], height=1).pack(fill="x")

        canvas_frame = tk.Frame(frame, bg=COLORS["bg2"])
        canvas_frame.pack(fill="both", expand=True)

        vbar = ttk.Scrollbar(canvas_frame, orient="vertical")
        hbar = ttk.Scrollbar(canvas_frame, orient="horizontal")
        vbar.pack(side="right", fill="y")
        hbar.pack(side="bottom", fill="x")

        self.tree_canvas = MacroTreeCanvas(
            canvas_frame, self,
            yscrollcommand=vbar.set,
            xscrollcommand=hbar.set)
        self.tree_canvas.pack(fill="both", expand=True)
        vbar.configure(command=self.tree_canvas.yview)
        hbar.configure(command=self.tree_canvas.xview)
        self.tree_canvas.bind(
            "<MouseWheel>",
            lambda e: self.tree_canvas.yview_scroll(
                -1 * (e.delta // 120), "units"))

    def _build_bottombar(self):
        bar = tk.Frame(self, bg=COLORS["bg3"], height=56)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self._run_btn = tk.Button(
            bar, text=t("btn.run"),
            bg=COLORS["green"], fg=COLORS["bg"],
            font=("Segoe UI", 12, "bold"), relief="flat",
            cursor="hand2", padx=20, pady=8,
            activebackground="#c3f0bc", activeforeground=COLORS["bg"],
            command=self._run_macro)
        self._run_btn.pack(side="left", padx=12, pady=8)
        _bind_hover(self._run_btn, COLORS["green"], "#c3f0bc")

        self._pause_btn = tk.Button(
            bar, text=t("btn.pause"),
            bg=COLORS["bg3"], fg=COLORS["text_dim"],
            font=FONTS["normal"], relief="flat",
            cursor="hand2", padx=12, pady=8,
            activebackground=COLORS["surface"], activeforeground=COLORS["text"],
            state="disabled", command=self._pause_macro)
        self._pause_btn.pack(side="left", padx=4, pady=8)

        self._stop_btn = tk.Button(
            bar, text=t("btn.stop"),
            bg=COLORS["bg3"], fg=COLORS["text_dim"],
            font=FONTS["normal"], relief="flat",
            cursor="hand2", padx=12, pady=8,
            activebackground=COLORS["surface"], activeforeground=COLORS["text"],
            state="disabled", command=self._stop_macro)
        self._stop_btn.pack(side="left", padx=4, pady=8)

        tk.Frame(bar, bg=COLORS["bg3"]).pack(side="left", fill="x", expand=True)

        self._status_var = tk.StringVar(value=t("status.ready"))
        self._status_label = tk.Label(bar, textvariable=self._status_var,
                                      bg=COLORS["bg3"], fg=COLORS["text_dim"],
                                      font=FONTS["small"])
        self._status_label.pack(side="right", padx=16)

    # ── SETTINGS / HOTKEYS / LANG ────────────────────────────
    def _open_hotkey_settings(self):
        HotkeySettingsDialog(self, self.hotkey_manager,
                             on_apply=self._on_hotkeys_applied)

    def _open_settings(self):
        SettingsDialog(self)

    def _on_hotkeys_applied(self):
        self._refresh_hotkey_labels()
        self._save_settings()

    def _load_settings(self):
        data = load_settings()
        if "hotkeys" in data:
            self.hotkey_manager.hotkeys.update(data["hotkeys"])
        self._debug_overlay = bool(data.get("debug_overlay", False))

    def _save_settings(self):
        data = load_settings()
        data["hotkeys"]       = dict(self.hotkey_manager.hotkeys)
        data["debug_overlay"] = self._debug_overlay
        save_settings(data)

    def _refresh_hotkey_labels(self):
        hk = self.hotkey_manager.hotkeys
        r = hk.get("run",   "F9")  or "F9"
        s = hk.get("stop",  "F10") or "F10"
        p = hk.get("pause", "F11") or "F11"
        self._run_btn.configure(text=f"{t('btn.run')}  [{r}]")
        self._pause_btn.configure(text=f"{t('btn.pause')}  [{p}]")
        self._stop_btn.configure(text=f"{t('btn.stop')}  [{s}]")
        if not self._engine:
            self._status_var.set(t("status.ready_full", r=r, s=s, p=p))

    # ── CHARGEMENT INITIAL ───────────────────────────────────
    def _load_all_files(self):
        macros_dir = get_macros_dir()
        try:
            files = sorted(
                os.path.join(macros_dir, f)
                for f in os.listdir(macros_dir)
                if f.lower().endswith((".macros", ".json"))
            )
        except Exception:
            files = []

        for path in files:
            self._load_file_as_group(path, silent=True)

        if not self._groups:
            self._new_group(silent=True)

        if self._groups:
            self._current_group = self._groups[0]
            if self._current_group["macros"]:
                self._select_macro(self._current_group["macros"][0],
                                   self._current_group)

        self._refresh_macro_list()

    def _load_file_as_group(self, path, silent=False):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            macros = data.get("macros", [])
            if not macros:
                return
            group = {"path": path, "macros": macros, "dirty": False}
            self._groups.append(group)
            if "hotkeys" in data and hasattr(self, "hotkey_manager"):
                self.hotkey_manager.hotkeys.update(data["hotkeys"])
        except Exception as e:
            if not silent:
                messagebox.showerror(t("warn.error_open_title"),
                                     t("warn.error_open_msg", e=e))

    # ── SIDEBAR LIST ─────────────────────────────────────────
    def _refresh_macro_list(self):
        for w in self._list_inner.winfo_children():
            w.destroy()
        self._list_items = []
        self._lb_index   = []

        for group in self._groups:
            fname = (os.path.basename(group["path"])
                     if group["path"] else t("sidebar.unsaved_group"))
            dirty_mark = "  ●" if group["dirty"] else ""

            ghdr = tk.Frame(self._list_inner, bg=COLORS["bg"],
                            padx=10, pady=6, cursor="hand2")
            ghdr.pack(fill="x")
            lbl_ghdr = tk.Label(ghdr, text=f"{fname}{dirty_mark}",
                                bg=COLORS["bg"], fg=COLORS["accent"],
                                font=("Segoe UI", 8, "bold"), anchor="w")
            lbl_ghdr.pack(side="left", fill="x", expand=True)
            self._lb_index.append(None)

            def _make_ghdr_hover(w, lbl):
                def _enter(e):
                    w.configure(bg=COLORS["bg3"])
                    lbl.configure(bg=COLORS["bg3"])
                def _leave(e):
                    w.configure(bg=COLORS["bg"])
                    lbl.configure(bg=COLORS["bg"])
                return _enter, _leave

            _ent, _lev = _make_ghdr_hover(ghdr, lbl_ghdr)
            ghdr.bind("<Enter>",    _ent)
            ghdr.bind("<Leave>",    _lev)
            lbl_ghdr.bind("<Enter>", _ent)
            lbl_ghdr.bind("<Leave>", _lev)
            ghdr.bind("<Button-3>",
                      lambda e, g=group: self._group_context_menu(e, g))
            lbl_ghdr.bind("<Button-3>",
                          lambda e, g=group: self._group_context_menu(e, g))

            for macro in group["macros"]:
                item = self._make_list_item(group, macro)
                self._lb_index.append((group, macro))
                self._list_items.append(item)

        self._list_canvas.update_idletasks()
        self._list_canvas.configure(
            scrollregion=self._list_canvas.bbox("all"))

    def _make_list_item(self, group, macro):
        BG_N  = COLORS["bg2"]
        BG_H  = COLORS["bg3"]
        BG_S  = "#252540"
        ACC_S = COLORS["accent"]

        selected = (self.current_macro is macro)
        bg_now   = BG_S if selected else BG_N
        ac_now   = ACC_S if selected else BG_N

        row = tk.Frame(self._list_inner, bg=bg_now, cursor="hand2")
        row.pack(fill="x")

        accent = tk.Frame(row, bg=ac_now, width=3)
        accent.pack(side="left", fill="y")

        lbl = tk.Label(row, text=macro["name"],
                       bg=bg_now, fg=COLORS["text"],
                       font=FONTS["normal"], anchor="w", padx=10, pady=7)
        lbl.pack(side="left", fill="x", expand=True)

        def on_enter(e, r=row, a=accent, lb=lbl, m=macro):
            if self.current_macro is not m:
                r.configure(bg=BG_H); a.configure(bg=BG_H); lb.configure(bg=BG_H)

        def on_leave(e, r=row, a=accent, lb=lbl, m=macro):
            if self.current_macro is not m:
                r.configure(bg=BG_N); a.configure(bg=BG_N); lb.configure(bg=BG_N)

        def on_click(e, g=group, m=macro):
            self._select_macro(m, g)

        def on_dbl(e, g=group, m=macro):
            self._rename_macro_item(m, g)

        def on_rclick(e, g=group, m=macro):
            self._macro_item_context(e, m, g)

        def on_wheel(e):
            self._list_canvas.yview_scroll(-1 * (e.delta // 120), "units")

        for w in (row, lbl):
            w.bind("<Enter>",           on_enter)
            w.bind("<Leave>",           on_leave)
            w.bind("<Button-1>",        on_click)
            w.bind("<Double-Button-1>", on_dbl)
            w.bind("<Button-3>",        on_rclick)
            w.bind("<MouseWheel>",      on_wheel)
        accent.bind("<MouseWheel>", on_wheel)

        return (row, accent, lbl, group, macro)

    def _update_list_selection(self):
        BG_N  = COLORS["bg2"]
        BG_S  = "#252540"
        ACC_S = COLORS["accent"]
        for row, accent, lbl, group, macro in self._list_items:
            sel    = (self.current_macro is macro)
            bg_now = BG_S if sel else BG_N
            ac_now = ACC_S if sel else BG_N
            try:
                row.configure(bg=bg_now)
                accent.configure(bg=ac_now)
                lbl.configure(bg=bg_now)
            except tk.TclError:
                pass

    def _rename_macro_item(self, macro, group):
        name = simpledialog.askstring(
            t("macro.rename_title"), t("macro.rename_prompt"),
            initialvalue=macro["name"], parent=self)
        if name:
            macro["name"] = name
            self._refresh_macro_list()
            self._macro_name_var.set(name)
            self._mark_group_dirty(group)

    def _macro_item_context(self, event, macro, group):
        menu = tk.Menu(self, tearoff=0,
                       bg=COLORS["bg3"], fg=COLORS["text"],
                       activebackground=COLORS["accent"],
                       activeforeground=COLORS["bg"])
        menu.add_command(label=t("macro.rename"),
                         command=lambda: self._rename_macro_item(macro, group))
        menu.add_command(label=t("macro.duplicate"),
                         command=lambda: self._duplicate_macro(macro, group))
        menu.add_separator()
        menu.add_command(label=t("macro.delete"),
                         command=lambda: self._delete_macro(macro, group))
        menu.post(event.x_root, event.y_root)

    def _group_context_menu(self, event, group):
        menu = tk.Menu(self, tearoff=0,
                       bg=COLORS["bg3"], fg=COLORS["text"],
                       activebackground=COLORS["accent"],
                       activeforeground=COLORS["bg"])
        menu.add_command(label=t("group.rename"),
                         command=lambda: self._rename_group(group))
        menu.add_separator()
        menu.add_command(label=t("group.delete"),
                         command=lambda: self._delete_group(group))
        menu.post(event.x_root, event.y_root)

    def _select_macro(self, macro, group):
        self.current_macro  = macro
        self._current_group = group
        self._macro_name_var.set(macro["name"])
        self._loop_var.set(macro.get("loop", False))
        rw = macro.get("res_w", 0)
        rh = macro.get("res_h", 0)
        self._res_w_var.set(str(rw) if rw else "")
        self._res_h_var.set(str(rh) if rh else "")
        self.tree_canvas.refresh()
        self.props_panel._build_empty()
        self._update_list_selection()

    # ── GROUPS ───────────────────────────────────────────────
    def _new_group(self, silent=False):
        m = new_macro()
        try:
            import ctypes as _c
            m["res_w"] = _c.windll.user32.GetSystemMetrics(78)
            m["res_h"] = _c.windll.user32.GetSystemMetrics(79)
        except Exception:
            m["res_w"] = self.winfo_screenwidth()
            m["res_h"] = self.winfo_screenheight()
        group = {"path": None, "macros": [m], "dirty": True}
        self._groups.append(group)
        if not silent:
            self._select_macro(m, group)
            self._refresh_macro_list()
            self._update_title()

    def _save_current_group(self):
        if not self._current_group:
            return
        self._write_group(self._current_group)

    def _save_all_groups(self):
        for group in self._groups:
            if group["dirty"]:
                self._write_group(group)

    def _write_group(self, group):
        path = group.get("path")
        if not path:
            path = filedialog.asksaveasfilename(
                initialdir=get_macros_dir(),
                defaultextension=".macros",
                filetypes=[("MacroEverything", "*.macros"), ("JSON", "*.json")],
                title=t("file.save_title"))
            if not path:
                return
            group["path"] = path
        try:
            data = {
                "macros":  group["macros"],
                "hotkeys": self.hotkey_manager.hotkeys
                           if hasattr(self, "hotkey_manager") else {},
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            group["dirty"] = False
            self._refresh_macro_list()
            self._update_title()
            self._status_var.set(t("status.saved", name=os.path.basename(path)))
        except Exception as e:
            messagebox.showerror(t("warn.error_save_title"),
                                 t("warn.error_save_msg", e=e))

    def _open_file(self):
        path = filedialog.askopenfilename(
            initialdir=get_macros_dir(),
            filetypes=[("MacroEverything", "*.macros"), ("JSON", "*.json")],
            title=t("file.open_title"))
        if not path:
            return
        path = os.path.normpath(os.path.abspath(path))
        for g in self._groups:
            if g["path"] and os.path.normpath(os.path.abspath(g["path"])) == path:
                if g["macros"]:
                    self._select_macro(g["macros"][0], g)
                    self._refresh_macro_list()
                return
        path = import_to_macros_dir(path)
        prev_len = len(self._groups)
        self._load_file_as_group(path)
        if len(self._groups) > prev_len:
            new_group = self._groups[-1]
            if new_group["macros"]:
                self._select_macro(new_group["macros"][0], new_group)
            self._refresh_macro_list()
            self._update_title()

    def _mark_group_dirty(self, group=None):
        g = group or self._current_group
        if g and not g["dirty"]:
            g["dirty"] = True
            self._refresh_macro_list()
            self._update_title()

    def _update_title(self):
        base = "MacroEverything"
        if self._current_group and self._current_group.get("path"):
            base += f"  —  {os.path.basename(self._current_group['path'])}"
        if any(g["dirty"] for g in self._groups):
            base += "  ●"
        self.title(base)

    # ── MACROS ───────────────────────────────────────────────
    def _new_macro_in_current_group(self):
        if not self._current_group:
            self._new_group()
            return
        m = new_macro()
        try:
            import ctypes as _c
            m["res_w"] = _c.windll.user32.GetSystemMetrics(78)
            m["res_h"] = _c.windll.user32.GetSystemMetrics(79)
        except Exception:
            m["res_w"] = self.winfo_screenwidth()
            m["res_h"] = self.winfo_screenheight()
        self._current_group["macros"].append(m)
        self._select_macro(m, self._current_group)
        self._refresh_macro_list()
        self._mark_group_dirty()

    @property
    def macros(self):
        result = []
        for g in self._groups:
            result.extend(g["macros"])
        return result

    def _on_name_change(self, event=None):
        if self.current_macro:
            self.current_macro["name"] = self._macro_name_var.get()
            self._refresh_macro_list()
            self._mark_group_dirty()

    def _on_loop_change(self):
        if self.current_macro:
            self.current_macro["loop"] = self._loop_var.get()
            self._mark_group_dirty()

    def _on_res_change(self, event=None):
        if not self.current_macro:
            return
        try:
            w = int(self._res_w_var.get())
            if w > 0:
                self.current_macro["res_w"] = w
        except (ValueError, TypeError):
            pass
        try:
            h = int(self._res_h_var.get())
            if h > 0:
                self.current_macro["res_h"] = h
        except (ValueError, TypeError):
            pass
        self._mark_group_dirty()

    def _rename_group(self, group):
        old_path = group.get("path")
        old_name = os.path.splitext(os.path.basename(old_path))[0] if old_path else ""
        name = simpledialog.askstring(
            t("group.rename_title"), t("group.rename_prompt"),
            initialvalue=old_name, parent=self)
        if not name or name == old_name:
            return
        name = name.strip()
        if not name:
            return
        new_path = os.path.join(get_macros_dir(), name + ".macros")
        if old_path and os.path.isfile(old_path):
            try:
                os.rename(old_path, new_path)
            except Exception as e:
                messagebox.showerror(t("warn.error_save_title"),
                                     t("warn.error_save_msg", e=e))
                return
        group["path"] = new_path
        self._refresh_macro_list()
        self._update_title()

    def _delete_group(self, group):
        fname = (os.path.basename(group["path"])
                 if group["path"] else t("sidebar.unsaved_group"))
        if not messagebox.askyesno(t("group.delete_title"),
                                   t("group.delete_confirm", name=fname)):
            return
        if group.get("path") and os.path.isfile(group["path"]):
            try:
                os.remove(group["path"])
            except Exception:
                pass
        self._groups.remove(group)
        if not self._groups:
            self._new_group(silent=True)
        if self._current_group is group:
            self._current_group = self._groups[-1]
            last_macro = self._current_group["macros"][-1]
            self._select_macro(last_macro, self._current_group)
        self._refresh_macro_list()
        self._update_title()

    def _duplicate_macro(self, macro, group):
        dup = copy.deepcopy(macro)
        dup["name"] += t("macro.copy_suffix")
        _remap_ids(dup["nodes"])
        idx = group["macros"].index(macro)
        group["macros"].insert(idx + 1, dup)
        self._select_macro(dup, group)
        self._refresh_macro_list()
        self._mark_group_dirty(group)

    def _delete_macro(self, macro, group):
        if not messagebox.askyesno(t("macro.delete_title"),
                                   t("macro.delete_confirm", name=macro["name"])):
            return
        group["macros"].remove(macro)
        if not group["macros"]:
            self._groups.remove(group)
            if not self._groups:
                self._new_group(silent=True)
            self._current_group = self._groups[-1]
            self.current_macro  = self._current_group["macros"][-1]
        elif self.current_macro is macro:
            self.current_macro = group["macros"][-1]
            self._select_macro(self.current_macro, group)
        self._refresh_macro_list()
        self.tree_canvas.refresh()
        self._mark_group_dirty(group)

    # ── UNDO / REDO ──────────────────────────────────────────
    def _push_history(self):
        if not self._current_group:
            return
        cur_idx = (self._current_group["macros"].index(self.current_macro)
                   if self.current_macro in self._current_group["macros"] else 0)
        state = {
            "group":   self._current_group,
            "macros":  copy.deepcopy(self._current_group["macros"]),
            "cur_idx": cur_idx,
        }
        self._undo_stack.append(state)
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._update_undo_redo_btns()
        self._mark_group_dirty()

    def _undo(self):
        if not self._undo_stack:
            return
        if self._current_group:
            cur_idx = (self._current_group["macros"].index(self.current_macro)
                       if self.current_macro in self._current_group["macros"] else 0)
            self._redo_stack.append({
                "group":   self._current_group,
                "macros":  copy.deepcopy(self._current_group["macros"]),
                "cur_idx": cur_idx,
            })
        self._restore_state(self._undo_stack.pop())

    def _redo(self):
        if not self._redo_stack:
            return
        if self._current_group:
            cur_idx = (self._current_group["macros"].index(self.current_macro)
                       if self.current_macro in self._current_group["macros"] else 0)
            self._undo_stack.append({
                "group":   self._current_group,
                "macros":  copy.deepcopy(self._current_group["macros"]),
                "cur_idx": cur_idx,
            })
        self._restore_state(self._redo_stack.pop())

    def _restore_state(self, state):
        group = state["group"]
        group["macros"] = state["macros"]
        cur_idx = min(state["cur_idx"], len(group["macros"]) - 1)
        macro   = group["macros"][cur_idx] if group["macros"] else None
        if macro:
            self._select_macro(macro, group)
        self._refresh_macro_list()
        self._update_undo_redo_btns()

    def _update_undo_redo_btns(self):
        self._undo_btn.configure(
            state="normal" if self._undo_stack else "disabled",
            fg=COLORS["text"] if self._undo_stack else COLORS["text_dim"])
        self._redo_btn.configure(
            state="normal" if self._redo_stack else "disabled",
            fg=COLORS["text"] if self._redo_stack else COLORS["text_dim"])

    # ── NODES ────────────────────────────────────────────────
    def _find_parent_list(self, node_id, nodes=None):
        if nodes is None:
            nodes = self.current_macro["nodes"] if self.current_macro else []
        for i, n in enumerate(nodes):
            if n["id"] == node_id:
                return nodes, i
            for branch in n.get("children", []):
                result = self._find_parent_list(node_id, branch)
                if result[0] is not None:
                    return result
        return None, -1

    def select_node(self, node):
        self.props_panel.show_node(node)

    def edit_node(self, node):
        dlg = NodeEditorDialog(self, node, self)
        self.wait_window(dlg)
        try:
            self.props_panel.show_node(node)
        except Exception:
            pass

    def edit_comment(self, node):
        c = simpledialog.askstring(
            t("node.comment_title"), t("node.comment_prompt"),
            initialvalue=node.get("comment", ""), parent=self)
        if c is not None:
            self._push_history()
            node["comment"] = c
            self.tree_canvas.refresh()

    def add_node_dialog(self, parent_list=None):
        if parent_list is None:
            parent_list = self.current_macro["nodes"] if self.current_macro else []
        AddNodeDialog(self, self, parent_list)

    def add_node_after(self, node):
        lst, _ = self._find_parent_list(node["id"])
        if lst is None:
            return
        AddNodeDialog(self, self, lst, insert_after=node["id"])

    def delete_node(self, node):
        if not messagebox.askyesno(t("node.delete_title"), t("node.delete_confirm"),
                                   parent=self):
            return
        self._push_history()
        lst, idx = self._find_parent_list(node["id"])
        if lst is not None and idx >= 0:
            lst.pop(idx)
        self.tree_canvas.refresh()
        self.props_panel._build_empty()

    def move_node(self, node, direction):
        lst, idx = self._find_parent_list(node["id"])
        if lst is None:
            return
        new_idx = idx + direction
        if 0 <= new_idx < len(lst):
            self._push_history()
            lst[idx], lst[new_idx] = lst[new_idx], lst[idx]
            self.tree_canvas.refresh()

    def duplicate_node(self, node):
        lst, idx = self._find_parent_list(node["id"])
        if lst is None:
            return
        self._push_history()
        cloned = copy.deepcopy(node)
        _remap_ids([cloned])
        lst.insert(idx + 1, cloned)
        self.tree_canvas.refresh()
        self._mark_group_dirty()

    def copy_node_image(self, node):
        b64 = node["params"].get("template_b64", "")
        self._img_clipboard = b64 if b64 else None

    def paste_node_image(self, node):
        if not self._img_clipboard:
            return
        self._push_history()
        node["params"]["template_b64"] = self._img_clipboard
        self.tree_canvas.refresh()
        self._mark_group_dirty()
        try:
            self.props_panel.show_node(node)
        except Exception:
            pass

    # ── EXECUTION ────────────────────────────────────────────
    def _run_macro(self):
        if not self.current_macro:
            return
        if self._engine is not None:
            messagebox.showwarning(
                t("warn.already_running_title"),
                t("warn.already_running_msg",
                  stop_key=self.hotkey_manager.hotkeys.get("stop", "F10") or "F10"))
            return
        self._run_btn.configure(state="disabled")
        self._pause_btn.configure(state="normal",
                                   bg=COLORS["yellow"], fg=COLORS["bg"],
                                   activebackground="#fcefc8",
                                   activeforeground=COLORS["bg"])
        self._stop_btn.configure(state="normal",
                                  bg=COLORS["red"], fg=COLORS["bg"],
                                  activebackground="#fbc8d4",
                                  activeforeground=COLORS["bg"])
        self._status_var.set(t("status.running"))
        self._status_label.configure(fg=COLORS["green"])
        _play_cue("run")
        self._engine = MacroEngine(
            self.current_macro,
            macros_list=self.macros,
            on_step =self._on_step,
            on_done =self._on_done,
            on_error=self._on_error,
            debug_overlay=self._debug_overlay,
        )
        self._engine_thread = threading.Thread(
            target=self._engine.run, daemon=True)
        self._engine_thread.start()

    def _pause_macro(self):
        if not self._engine:
            return
        hk = self.hotkey_manager.hotkeys
        p = hk.get("pause", "F11") or "F11"
        if self._engine._pause:
            self._engine.resume()
            self._pause_btn.configure(text=f"{t('btn.pause')}  [{p}]")
            self._status_var.set(t("status.running"))
            self._status_label.configure(fg=COLORS["green"])
            _play_cue("run")
        else:
            self._engine.pause()
            self._pause_btn.configure(text=f"{t('btn.resume')}  [{p}]")
            self._status_var.set(t("status.paused"))
            self._status_label.configure(fg=COLORS["yellow"])
            _play_cue("pause")

    def _stop_macro(self):
        if self._engine:
            self._engine.stop()
        self._engine        = None
        self._engine_thread = None
        _play_cue("stop")
        self._reset_run_ui()

    def _on_step(self, node_id):
        self.after(0, lambda: self.tree_canvas.highlight_node(node_id))

    def _on_done(self):
        self.after(0, self._reset_run_ui)

    def _on_error(self, msg):
        self.after(0, lambda: messagebox.showerror(t("warn.error_title"), msg))
        self.after(0, self._reset_run_ui)

    def _reset_run_ui(self):
        self._engine        = None
        self._engine_thread = None
        hk = self.hotkey_manager.hotkeys
        r = hk.get("run",   "F9")  or "F9"
        s = hk.get("stop",  "F10") or "F10"
        p = hk.get("pause", "F11") or "F11"
        self._run_btn.configure(state="normal")
        self._pause_btn.configure(state="disabled",
                                   text=f"{t('btn.pause')}  [{p}]",
                                   bg=COLORS["bg3"], fg=COLORS["text_dim"],
                                   activebackground=COLORS["surface"],
                                   activeforeground=COLORS["text"])
        self._stop_btn.configure(state="disabled",
                                  bg=COLORS["bg3"], fg=COLORS["text_dim"],
                                  activebackground=COLORS["surface"],
                                  activeforeground=COLORS["text"])
        self._status_var.set(t("status.ready_full", r=r, s=s, p=p))
        self._status_label.configure(fg=COLORS["text_dim"])


# ────────────────────────────────────────────────────────────
#  DIALOGUE PARAMETRES
# ────────────────────────────────────────────────────────────
class SettingsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title(t("settings.title"))
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.grab_set()
        self.transient(app)
        self._build()
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        px = self.master.winfo_rootx() + self.master.winfo_width() // 2
        py = self.master.winfo_rooty() + self.master.winfo_height() // 2
        self.geometry(f"+{max(0, px - w // 2)}+{max(0, py - h // 2)}")

    def _build(self):
        pad = tk.Frame(self, bg=COLORS["bg"], padx=24, pady=20)
        pad.pack(fill="both", expand=True)

        tk.Label(pad, text=t("settings.title"),
                 bg=COLORS["bg"], fg=COLORS["accent"],
                 font=FONTS["heading"]).pack(anchor="w", pady=(0, 16))

        tk.Label(pad, text=t("settings.section_debug"),
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 6))

        self._dbg_var = tk.IntVar(value=1 if self.app._debug_overlay else 0)
        tk.Checkbutton(pad,
                       text=t("settings.debug_overlay"),
                       variable=self._dbg_var,
                       bg=COLORS["bg"], fg=COLORS["text"],
                       selectcolor=COLORS["bg"],
                       activebackground=COLORS["bg"],
                       font=FONTS["normal"]).pack(anchor="w")
        tk.Label(pad, text=t("settings.debug_overlay_hint"),
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"], wraplength=300, justify="left").pack(
                 anchor="w", pady=(2, 12))

        tk.Frame(pad, bg=COLORS["bg3"], height=1).pack(fill="x", pady=(8, 12))
        row = tk.Frame(pad, bg=COLORS["bg"])
        row.pack(anchor="e")

        cancel_btn = tk.Button(row, text=t("btn.cancel"),
                               bg=COLORS["surface"], fg=COLORS["text"],
                               font=FONTS["normal"], relief="flat", cursor="hand2",
                               padx=12, pady=6, command=self.destroy)
        cancel_btn.pack(side="left", padx=(0, 8))
        _bind_hover(cancel_btn, COLORS["surface"], COLORS["bg3"])

        ok_btn = tk.Button(row, text=t("btn.ok"),
                           bg=COLORS["accent"], fg=COLORS["bg"],
                           font=FONTS["normal"], relief="flat", cursor="hand2",
                           padx=12, pady=6, command=self._apply)
        ok_btn.pack(side="left")
        _bind_hover(ok_btn, COLORS["accent"], "#74c7ec")

    def _apply(self):
        self.app._debug_overlay = bool(self._dbg_var.get())
        self.app._save_settings()
        self.destroy()
