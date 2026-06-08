"""
macro_app/ui/app.py
Fenetre principale de l'application MacroEverything.

Classes :
  MacroEverythingApp — fenetre tk.Tk racine, orchestre tous les composants
  SettingsDialog     — dialogue parametres (debug overlay, etc.)

Modele de donnees (multi-groupes) :
  self._groups = [{"path": str|None, "macros": [...], "dirty": bool}, ...]
  self.current_macro  = la macro actuellement affichee dans l'editeur
  self._current_group = le groupe auquel current_macro appartient
"""

import json
import os
import copy
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from ..constants import COLORS, FONTS
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


class MacroEverythingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MacroEverything")
        self.geometry("1300x840")
        self.minsize(900, 600)
        self.configure(bg=COLORS["bg"])

        # ── Multi-groupes ──────────────────────
        # Chaque groupe = un fichier .macros
        self._groups: list        = []
        self._current_group: dict = None
        self.current_macro: dict  = None
        # _lb_index[i] = (groupe, macro) ou None si separateur
        self._lb_index: list      = []

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

    # ─────────────────────────────────────────
    #  INIT
    # ─────────────────────────────────────────
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
        style.configure("TCombobox",
                        fieldbackground=COLORS["bg3"],
                        background=COLORS["bg3"],
                        foreground=COLORS["text"],
                        selectbackground=COLORS["accent"])

    # ─────────────────────────────────────────
    #  CONSTRUCTION UI
    # ─────────────────────────────────────────
    def _build_ui(self):
        self._build_topbar()
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True)
        self._build_macro_list(main)
        tk.Frame(main, bg=COLORS["border"], width=1).pack(side="left", fill="y")
        self._build_canvas_area(main)
        tk.Frame(main, bg=COLORS["border"], width=1).pack(side="left", fill="y")
        self.props_panel = PropertiesPanel(main, self)
        self.props_panel.pack(side="left", fill="y")
        self._build_bottombar()
        self.bind_all("<Control-z>", lambda e: self._undo())
        self.bind_all("<Control-y>", lambda e: self._redo())

    def _build_topbar(self):
        bar = tk.Frame(self, bg=COLORS["bg3"], height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(bar, text="MacroEverything",
                 bg=COLORS["bg3"], fg=COLORS["accent"],
                 font=FONTS["title"]).pack(side="left", padx=16)

        for label, cmd in [
            (t("menu.new"),      self._new_group),
            (t("menu.open"),     self._open_file),
            (t("menu.save"),     self._save_current_group),
            (t("menu.save_all"), self._save_all_groups),
        ]:
            tk.Button(bar, text=label,
                      bg=COLORS["bg3"], fg=COLORS["text"],
                      font=FONTS["normal"], relief="flat", cursor="hand2",
                      padx=12, pady=8, activebackground=COLORS["surface"],
                      command=cmd).pack(side="left", padx=2)

        tk.Frame(bar, bg=COLORS["bg3"]).pack(side="left", fill="x", expand=True)

        tk.Button(bar, text=t("menu.language"),
                  bg=COLORS["bg3"], fg=COLORS["text_dim"],
                  font=FONTS["small"], relief="flat", cursor="hand2",
                  padx=10, pady=8,
                  command=self._open_language_settings).pack(side="right", padx=4)

        tk.Button(bar, text=t("menu.settings"),
                  bg=COLORS["bg3"], fg=COLORS["text_dim"],
                  font=FONTS["small"], relief="flat", cursor="hand2",
                  padx=10, pady=8,
                  command=self._open_settings).pack(side="right", padx=4)

        tk.Button(bar, text=t("menu.hotkeys"),
                  bg=COLORS["bg3"], fg=COLORS["text_dim"],
                  font=FONTS["small"], relief="flat", cursor="hand2",
                  padx=10, pady=8,
                  command=self._open_hotkey_settings).pack(side="right", padx=4)

        tk.Label(bar, text="v1.0",
                 bg=COLORS["bg3"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(side="right", padx=12)

    def _build_macro_list(self, parent):
        frame = tk.Frame(parent, bg=COLORS["bg2"], width=210)
        frame.pack(side="left", fill="y")
        frame.pack_propagate(False)

        hdr = tk.Frame(frame, bg=COLORS["bg3"], padx=10, pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text=t("sidebar.my_macros"),
                 bg=COLORS["bg3"], fg=COLORS["text"],
                 font=FONTS["heading"]).pack(side="left")
        tk.Button(hdr, text="+",
                  bg=COLORS["accent"], fg=COLORS["bg"],
                  font=FONTS["heading"], relief="flat", cursor="hand2",
                  width=2, command=self._new_macro_in_current_group).pack(side="right")

        self._macro_listbox = tk.Listbox(
            frame, bg=COLORS["bg2"], fg=COLORS["text"],
            font=FONTS["normal"], relief="flat",
            selectbackground=COLORS["accent"],
            selectforeground=COLORS["bg"],
            activestyle="none", bd=0, highlightthickness=0)
        self._macro_listbox.pack(fill="both", expand=True, padx=4, pady=4)
        self._macro_listbox.bind("<<ListboxSelect>>", self._on_listbox_select)
        self._macro_listbox.bind("<Double-Button-1>", self._rename_macro)
        self._macro_listbox.bind("<Button-3>",        self._macro_context_menu)

    def _build_canvas_area(self, parent):
        frame = tk.Frame(parent, bg=COLORS["bg2"])
        frame.pack(side="left", fill="both", expand=True)

        toolbar = tk.Frame(frame, bg=COLORS["bg3"], height=42)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        tk.Button(toolbar, text=t("toolbar.add_node"),
                  bg=COLORS["accent"], fg=COLORS["bg"],
                  font=FONTS["normal"], relief="flat", cursor="hand2",
                  padx=12, pady=6,
                  command=self.add_node_dialog).pack(side="left", padx=8, pady=4)

        self._undo_btn = tk.Button(toolbar, text=t("toolbar.undo"),
                                    bg=COLORS["bg3"], fg=COLORS["text_dim"],
                                    font=FONTS["small"], relief="flat",
                                    cursor="hand2", padx=8, pady=6,
                                    state="disabled", command=self._undo)
        self._undo_btn.pack(side="left", padx=(4, 0), pady=4)
        self._redo_btn = tk.Button(toolbar, text=t("toolbar.redo"),
                                    bg=COLORS["bg3"], fg=COLORS["text_dim"],
                                    font=FONTS["small"], relief="flat",
                                    cursor="hand2", padx=8, pady=6,
                                    state="disabled", command=self._redo)
        self._redo_btn.pack(side="left", padx=(2, 0), pady=4)

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
            lambda e: self.tree_canvas.yview_scroll(-1 * (e.delta // 120), "units"))

    def _build_bottombar(self):
        bar = tk.Frame(self, bg=COLORS["bg3"], height=56)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self._run_btn = tk.Button(
            bar, text=t("btn.run"),
            bg=COLORS["green"], fg=COLORS["bg"],
            font=("Segoe UI", 12, "bold"), relief="flat",
            cursor="hand2", padx=20, pady=8,
            command=self._run_macro)
        self._run_btn.pack(side="left", padx=12, pady=8)

        self._pause_btn = tk.Button(
            bar, text=t("btn.pause"),
            bg=COLORS["yellow"], fg=COLORS["bg"],
            font=FONTS["normal"], relief="flat",
            cursor="hand2", padx=12, pady=8,
            state="disabled", command=self._pause_macro)
        self._pause_btn.pack(side="left", padx=4, pady=8)

        self._stop_btn = tk.Button(
            bar, text=t("btn.stop"),
            bg=COLORS["red"], fg=COLORS["bg"],
            font=FONTS["normal"], relief="flat",
            cursor="hand2", padx=12, pady=8,
            state="disabled", command=self._stop_macro)
        self._stop_btn.pack(side="left", padx=4, pady=8)

        tk.Frame(bar, bg=COLORS["bg3"]).pack(side="left", fill="x", expand=True)

        self._status_var = tk.StringVar(value="Pret")
        tk.Label(bar, textvariable=self._status_var,
                 bg=COLORS["bg3"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(side="right", padx=16)

        self._progress = ttk.Progressbar(bar, mode="indeterminate", length=100)
        self._progress.pack(side="right", padx=8, pady=16)

    # ─────────────────────────────────────────
    #  PARAMETRES / HOTKEYS / LANGUE
    # ─────────────────────────────────────────
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

    # ─────────────────────────────────────────
    #  CHARGEMENT INITIAL
    # ─────────────────────────────────────────
    def _load_all_files(self):
        """Charge tous les .macros du dossier macros/ au demarrage."""
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
        """Charge un fichier .macros et l'ajoute comme nouveau groupe."""
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

    # ─────────────────────────────────────────
    #  LISTBOX : construction et navigation
    # ─────────────────────────────────────────
    def _refresh_macro_list(self):
        """Reconstruit la listbox avec separateurs entre les groupes."""
        lb = self._macro_listbox
        lb.delete(0, "end")
        self._lb_index = []

        for group in self._groups:
            fname = (os.path.basename(group["path"])
                     if group["path"] else t("sidebar.unsaved_group"))
            dirty_mark = " ●" if group["dirty"] else ""
            sep_label  = f"── {fname}{dirty_mark}"
            lb.insert("end", sep_label)
            lb.itemconfig("end",
                          fg=COLORS["accent"],
                          selectbackground=COLORS["bg2"],
                          selectforeground=COLORS["accent"])
            self._lb_index.append(None)

            for macro in group["macros"]:
                lb.insert("end", f"   {macro['name']}")
                self._lb_index.append((group, macro))

        # Rétablir la sélection
        if self.current_macro:
            for i, e in enumerate(self._lb_index):
                if e and e[1] is self.current_macro:
                    lb.selection_set(i)
                    lb.see(i)
                    break

    def _on_listbox_select(self, event=None):
        sel = self._macro_listbox.curselection()
        if not sel:
            return
        entry = self._lb_index[sel[0]]
        if entry is None:
            # Clic sur un separateur → refuser, remettre la selection courante
            self._macro_listbox.selection_clear(0, "end")
            if self.current_macro:
                for i, e in enumerate(self._lb_index):
                    if e and e[1] is self.current_macro:
                        self._macro_listbox.selection_set(i)
                        break
            return
        group, macro = entry
        self._select_macro(macro, group)

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

    # ─────────────────────────────────────────
    #  GESTION DES GROUPES (fichiers)
    # ─────────────────────────────────────────
    def _new_group(self, silent=False):
        """Cree un nouveau groupe (fichier) avec une macro vide."""
        m = new_macro()
        m["res_w"] = self.winfo_screenwidth()
        m["res_h"] = self.winfo_screenheight()
        group = {"path": None, "macros": [m], "dirty": True}
        self._groups.append(group)
        if not silent:
            self._select_macro(m, group)
            self._refresh_macro_list()
            self._update_title()

    def _save_current_group(self):
        """Sauvegarde uniquement le groupe de la macro selectionnee."""
        if not self._current_group:
            return
        self._write_group(self._current_group)

    def _save_all_groups(self):
        """Sauvegarde tous les groupes modifies."""
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
            base += f"  \u2014  {os.path.basename(self._current_group['path'])}"
        if any(g["dirty"] for g in self._groups):
            base += "  \u25cf"
        self.title(base)

    # ─────────────────────────────────────────
    #  GESTION DES MACROS (dans un groupe)
    # ─────────────────────────────────────────
    def _new_macro_in_current_group(self):
        """Ajoute une macro au groupe actuellement selectionne."""
        if not self._current_group:
            self._new_group()
            return
        m = new_macro()
        m["res_w"] = self.winfo_screenwidth()
        m["res_h"] = self.winfo_screenheight()
        self._current_group["macros"].append(m)
        self._select_macro(m, self._current_group)
        self._refresh_macro_list()
        self._mark_group_dirty()

    @property
    def macros(self):
        """Toutes les macros de tous les groupes, a plat (pour le moteur)."""
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

    def _rename_macro(self, event=None):
        sel = self._macro_listbox.curselection()
        if not sel:
            return
        entry = self._lb_index[sel[0]]
        if not entry:
            return
        group, macro = entry
        name = simpledialog.askstring(t("macro.rename_title"), t("macro.rename_prompt"),
                                      initialvalue=macro["name"], parent=self)
        if name:
            macro["name"] = name
            self._refresh_macro_list()
            self._macro_name_var.set(name)
            self._mark_group_dirty(group)

    def _macro_context_menu(self, event):
        sel = self._macro_listbox.curselection()
        # Forcer la sélection sur la ligne cliquée (le clic droit ne sélectionne pas)
        idx = self._macro_listbox.nearest(event.y)
        if idx < 0:
            return
        self._macro_listbox.selection_clear(0, "end")
        self._macro_listbox.selection_set(idx)
        entry = self._lb_index[idx]

        menu = tk.Menu(self, tearoff=0,
                       bg=COLORS["bg3"], fg=COLORS["text"],
                       activebackground=COLORS["accent"],
                       activeforeground=COLORS["bg"])

        if entry is None:
            # ── Clic sur un séparateur = menu groupe ──
            group = self._group_at_lb_index(idx)
            if group is None:
                return
            menu.add_command(label=t("group.rename"),
                             command=lambda: self._rename_group(group))
            menu.add_separator()
            menu.add_command(label=t("group.delete"),
                             command=lambda: self._delete_group(group))
        else:
            # ── Clic sur une macro = menu macro ──
            group, macro = entry
            menu.add_command(label=t("macro.rename"),
                             command=self._rename_macro)
            menu.add_command(label=t("macro.duplicate"),
                             command=lambda: self._duplicate_macro(macro, group))
            menu.add_separator()
            menu.add_command(label=t("macro.delete"),
                             command=lambda: self._delete_macro(macro, group))

        menu.post(event.x_root, event.y_root)

    def _group_at_lb_index(self, lb_idx: int):
        """Retourne le groupe associe au separateur a lb_idx."""
        # Le separateur est suivi des macros du groupe
        # Cherchons en avant la premiere macro dont le groupe est identifie
        for i in range(lb_idx + 1, len(self._lb_index)):
            e = self._lb_index[i]
            if e is None:
                break   # prochain separateur
            return e[0]
        # Aucune macro en dessous — chercher en arrière
        for i in range(lb_idx - 1, -1, -1):
            e = self._lb_index[i]
            if e is not None:
                return e[0]
        return None

    def _rename_group(self, group):
        """Renomme un groupe : nouveau nom de fichier dans le dossier macros/."""
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
        """Supprime un groupe (et son fichier apres confirmation)."""
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

    # ─────────────────────────────────────────
    #  HISTORIQUE UNDO / REDO
    # ─────────────────────────────────────────
    def _push_history(self):
        if not self._current_group:
            return
        state = {
            "group":  self._current_group,
            "macros": copy.deepcopy(self._current_group["macros"]),
            "cur_id": self.current_macro["id"] if self.current_macro else None,
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
            self._redo_stack.append({
                "group":  self._current_group,
                "macros": copy.deepcopy(self._current_group["macros"]),
                "cur_id": self.current_macro["id"] if self.current_macro else None,
            })
        self._restore_state(self._undo_stack.pop())

    def _redo(self):
        if not self._redo_stack:
            return
        if self._current_group:
            self._undo_stack.append({
                "group":  self._current_group,
                "macros": copy.deepcopy(self._current_group["macros"]),
                "cur_id": self.current_macro["id"] if self.current_macro else None,
            })
        self._restore_state(self._redo_stack.pop())

    def _restore_state(self, state):
        group = state["group"]
        group["macros"] = state["macros"]
        cur_id = state["cur_id"]
        macro  = next((m for m in group["macros"] if m["id"] == cur_id),
                      group["macros"][0] if group["macros"] else None)
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

    # ─────────────────────────────────────────
    #  GESTION DES NOEUDS
    # ─────────────────────────────────────────
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

    # ─────────────────────────────────────────
    #  EXECUTION
    # ─────────────────────────────────────────
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
        self._pause_btn.configure(state="normal")
        self._stop_btn.configure(state="normal")
        self._status_var.set(t("status.running"))
        self._progress.start(10)
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
            _play_cue("run")
        else:
            self._engine.pause()
            self._pause_btn.configure(text=f"{t('btn.resume')}  [{p}]")
            self._status_var.set(t("status.paused"))
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
                                   text=f"{t('btn.pause')}  [{p}]")
        self._stop_btn.configure(state="disabled")
        self._status_var.set(t("status.ready_full", r=r, s=s, p=p))
        self._progress.stop()


# ─────────────────────────────────────────────
#  DIALOGUE PARAMETRES
# ─────────────────────────────────────────────
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
        self.geometry(
            f"+{(self.winfo_screenwidth()  - w) // 2}"
            f"+{(self.winfo_screenheight() - h) // 2}")

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
                       selectcolor=COLORS["accent"],
                       activebackground=COLORS["bg"],
                       font=FONTS["normal"]).pack(anchor="w")
        tk.Label(pad, text=t("settings.debug_overlay_hint"),
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"], wraplength=300, justify="left").pack(
                 anchor="w", pady=(2, 12))

        tk.Frame(pad, bg=COLORS["bg3"], height=1).pack(fill="x", pady=(8, 12))
        row = tk.Frame(pad, bg=COLORS["bg"])
        row.pack(anchor="e")
        tk.Button(row, text=t("btn.cancel"),
                  bg=COLORS["surface"], fg=COLORS["text"],
                  font=FONTS["normal"], relief="flat", cursor="hand2",
                  padx=12, pady=6,
                  command=self.destroy).pack(side="left", padx=(0, 8))
        tk.Button(row, text=t("btn.ok"),
                  bg=COLORS["accent"], fg=COLORS["bg"],
                  font=FONTS["normal"], relief="flat", cursor="hand2",
                  padx=12, pady=6,
                  command=self._apply).pack(side="left")

    def _apply(self):
        self.app._debug_overlay = bool(self._dbg_var.get())
        self.app._save_settings()
        self.destroy()
