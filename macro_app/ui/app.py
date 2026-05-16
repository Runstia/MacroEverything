"""
macro_app/ui/app.py
Fenetre principale de l'application MacroEverything.

Classes :
  MacroEverythingApp — fenetre tk.Tk racine, orchestre tous les composants
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

        self.macros         = []
        self.current_macro  = None
        self._engine        = None
        self._engine_thread = None
        self._file_path     = None
        self._undo_stack    = []
        self._redo_stack    = []
        self._dirty         = False

        self._init_i18n()
        self._build_ui()
        self._new_macro()
        self._apply_style()

        self.hotkey_manager = HotkeyManager(self)
        self._load_settings()
        self._load_last_file()
        self._dirty = False
        self._update_title()
        self._refresh_macro_list()
        self._refresh_hotkey_labels()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_i18n(self):
        """Charge la langue (depuis settings ou detection Windows) avant la construction UI."""
        data = load_settings()
        lang = data.get("language", None)  # None = detection automatique
        i18n.init(lang)

    def _open_language_settings(self):
        LanguageDialog(self)

    def _on_close(self):
        if self._dirty:
            answer = messagebox.askyesnocancel(
                t("file.unsaved_title"), t("file.unsaved_msg"))
            if answer is None:
                return
            if answer:
                self._save_file()
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

    # ── Construction de l'UI ──────────────────
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
            (t("menu.new"),     self._new_macro),
            (t("menu.open"),    self._open_file),
            (t("menu.save"),    self._save_file),
            (t("menu.save_as"), self._save_file_as),
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

        tk.Button(bar, text=t("menu.hotkeys"),
                  bg=COLORS["bg3"], fg=COLORS["text_dim"],
                  font=FONTS["small"], relief="flat", cursor="hand2",
                  padx=10, pady=8,
                  command=self._open_hotkey_settings).pack(side="right", padx=4)

        tk.Label(bar, text="v1.0",
                 bg=COLORS["bg3"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(side="right", padx=12)

    def _open_hotkey_settings(self):
        HotkeySettingsDialog(self, self.hotkey_manager,
                             on_apply=self._on_hotkeys_applied)

    def _on_hotkeys_applied(self):
        self._refresh_hotkey_labels()
        self._save_settings()

    def _load_settings(self):
        data = load_settings()
        if "hotkeys" in data:
            self.hotkey_manager.hotkeys.update(data["hotkeys"])

    def _save_settings(self):
        data = load_settings()
        data["hotkeys"] = dict(self.hotkey_manager.hotkeys)
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

    def _build_macro_list(self, parent):
        frame = tk.Frame(parent, bg=COLORS["bg2"], width=200)
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
                  width=2, command=self._new_macro).pack(side="right")

        self._macro_listbox = tk.Listbox(
            frame, bg=COLORS["bg2"], fg=COLORS["text"],
            font=FONTS["normal"], relief="flat",
            selectbackground=COLORS["accent"],
            selectforeground=COLORS["bg"],
            activestyle="none", bd=0, highlightthickness=0)
        self._macro_listbox.pack(fill="both", expand=True, padx=4, pady=4)
        self._macro_listbox.bind("<<ListboxSelect>>", self._on_macro_select)
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

        # ── Résolution de référence ────────────
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
        tk.Label(toolbar, text="\u00d7",
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

        self._status_var = tk.StringVar(
            value="Pret  -  F9 Executer  |  F10 Stop  |  F11 Pause")
        tk.Label(bar, textvariable=self._status_var,
                 bg=COLORS["bg3"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(side="right", padx=16)

        self._progress = ttk.Progressbar(bar, mode="indeterminate", length=100)
        self._progress.pack(side="right", padx=8, pady=16)

    # ── Gestion des macros ────────────────────
    def _refresh_macro_list(self):
        self._macro_listbox.delete(0, "end")
        in_macros_folder = bool(
            self._file_path and
            os.path.normpath(os.path.dirname(os.path.abspath(self._file_path)))
            == os.path.normpath(get_macros_dir()))
        for m in self.macros:
            if self._dirty:
                suffix = "  \u25cf"       # ● unsaved
            elif in_macros_folder:
                suffix = "  \U0001f4c1"   # 📁 saved in macros folder
            else:
                suffix = ""
            self._macro_listbox.insert("end", f"  {m['name']}{suffix}")
        if self.current_macro in self.macros:
            idx = self.macros.index(self.current_macro)
            self._macro_listbox.selection_set(idx)

    def _on_macro_select(self, event=None):
        sel = self._macro_listbox.curselection()
        if sel:
            self.current_macro = self.macros[sel[0]]
            self._macro_name_var.set(self.current_macro["name"])
            self._loop_var.set(self.current_macro.get("loop", False))
            rw = self.current_macro.get("res_w", 0)
            rh = self.current_macro.get("res_h", 0)
            self._res_w_var.set(str(rw) if rw else "")
            self._res_h_var.set(str(rh) if rh else "")
            self.tree_canvas.refresh()
            self.props_panel._build_empty()

    def _on_name_change(self, event=None):
        if self.current_macro:
            self.current_macro["name"] = self._macro_name_var.get()
            self._refresh_macro_list()
            self._mark_dirty()

    def _on_loop_change(self):
        if self.current_macro:
            self.current_macro["loop"] = self._loop_var.get()
            self._mark_dirty()

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
        self._mark_dirty()

    # ── Etat sauvegarde ──────────────────────
    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self._refresh_macro_list()
            self._update_title()

    def _mark_clean(self):
        self._dirty = False
        self._refresh_macro_list()
        self._update_title()

    def _update_title(self):
        base = "MacroEverything"
        if self._file_path:
            base += f"  \u2014  {os.path.basename(self._file_path)}"
        if self._dirty:
            base += "  \u25cf"
        self.title(base)

    def _load_last_file(self):
        """Charge le dernier fichier ouvert (depuis settings) ou le plus recent du dossier macros."""
        data = load_settings()
        last = data.get("last_file", "")
        if last and os.path.isfile(last):
            self._load_file(last, silent=True)
            return
        # Fallback : fichier le plus recent du dossier macros
        macros_dir = get_macros_dir()
        try:
            files = [
                os.path.join(macros_dir, f)
                for f in os.listdir(macros_dir)
                if f.lower().endswith((".macros", ".json"))
            ]
            if files:
                self._load_file(max(files, key=os.path.getmtime), silent=True)
        except Exception:
            pass

    def _load_file(self, path, silent=False):
        """Charge un fichier .macros dans l'application."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded = data.get("macros", [])
            if not loaded:
                return
            self.macros        = loaded
            self.current_macro = self.macros[0]
            self._file_path    = path
            if "hotkeys" in data and hasattr(self, "hotkey_manager"):
                self.hotkey_manager.hotkeys.update(data["hotkeys"])
            self._refresh_macro_list()
            self._macro_name_var.set(self.current_macro["name"])
            self._loop_var.set(self.current_macro.get("loop", False))
            rw = self.current_macro.get("res_w", 0)
            rh = self.current_macro.get("res_h", 0)
            self._res_w_var.set(str(rw) if rw else "")
            self._res_h_var.set(str(rh) if rh else "")
            self.tree_canvas.refresh()
            self._mark_clean()
        except Exception as e:
            if not silent:
                messagebox.showerror(t("warn.error_open_title"),
                                     t("warn.error_open_msg", e=e))

    def _new_macro(self):
        m = new_macro()
        m["res_w"] = self.winfo_screenwidth()
        m["res_h"] = self.winfo_screenheight()
        self.macros.append(m)
        self.current_macro = m
        self._refresh_macro_list()
        self._macro_name_var.set(m["name"])
        self._loop_var.set(False)
        self._res_w_var.set(str(m["res_w"]))
        self._res_h_var.set(str(m["res_h"]))
        self.tree_canvas.refresh()
        self._mark_dirty()

    def _rename_macro(self, event=None):
        sel = self._macro_listbox.curselection()
        if not sel:
            return
        m = self.macros[sel[0]]
        name = simpledialog.askstring(t("macro.rename_title"), t("macro.rename_prompt"),
                                      initialvalue=m["name"], parent=self)
        if name:
            m["name"] = name
            self._refresh_macro_list()
            self._macro_name_var.set(name)
            self._mark_dirty()

    def _macro_context_menu(self, event):
        sel = self._macro_listbox.curselection()
        if not sel:
            return
        m = self.macros[sel[0]]
        menu = tk.Menu(self, tearoff=0,
                       bg=COLORS["bg3"], fg=COLORS["text"],
                       activebackground=COLORS["accent"],
                       activeforeground=COLORS["bg"])
        menu.add_command(label=t("macro.rename"),    command=self._rename_macro)
        menu.add_command(label=t("macro.duplicate"), command=lambda: self._duplicate_macro(m))
        menu.add_separator()
        menu.add_command(label=t("macro.delete"),    command=lambda: self._delete_macro(m))
        menu.post(event.x_root, event.y_root)

    def _duplicate_macro(self, macro):
        dup = copy.deepcopy(macro)
        dup["name"] += t("macro.copy_suffix")
        _remap_ids(dup["nodes"])
        self.macros.append(dup)
        self.current_macro = dup
        self._refresh_macro_list()
        self.tree_canvas.refresh()
        self._mark_dirty()

    def _delete_macro(self, macro):
        if not messagebox.askyesno(t("macro.delete_title"), t("macro.delete_confirm", name=macro['name'])):
            return
        self.macros.remove(macro)
        self.current_macro = self.macros[-1] if self.macros else None
        if not self.current_macro:
            self._new_macro()
            return
        self._refresh_macro_list()
        self.tree_canvas.refresh()
        self._mark_dirty()

    # ── Historique Undo / Redo ────────────────
    def _push_history(self):
        try:
            idx = self.macros.index(self.current_macro)
        except ValueError:
            idx = 0
        self._undo_stack.append((copy.deepcopy(self.macros), idx))
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._update_undo_redo_btns()
        self._mark_dirty()

    def _undo(self):
        if not self._undo_stack:
            return
        try:
            idx = self.macros.index(self.current_macro)
        except ValueError:
            idx = 0
        self._redo_stack.append((copy.deepcopy(self.macros), idx))
        snapshot, midx = self._undo_stack.pop()
        self.macros = snapshot
        self.current_macro = self.macros[min(midx, len(self.macros) - 1)]
        self._refresh_macro_list()
        self._macro_name_var.set(self.current_macro["name"])
        self._loop_var.set(self.current_macro.get("loop", False))
        rw = self.current_macro.get("res_w", 0)
        rh = self.current_macro.get("res_h", 0)
        self._res_w_var.set(str(rw) if rw else "")
        self._res_h_var.set(str(rh) if rh else "")
        self.tree_canvas.refresh()
        self.props_panel._build_empty()
        self._update_undo_redo_btns()

    def _redo(self):
        if not self._redo_stack:
            return
        try:
            idx = self.macros.index(self.current_macro)
        except ValueError:
            idx = 0
        self._undo_stack.append((copy.deepcopy(self.macros), idx))
        snapshot, midx = self._redo_stack.pop()
        self.macros = snapshot
        self.current_macro = self.macros[min(midx, len(self.macros) - 1)]
        self._refresh_macro_list()
        self._macro_name_var.set(self.current_macro["name"])
        self._loop_var.set(self.current_macro.get("loop", False))
        rw = self.current_macro.get("res_w", 0)
        rh = self.current_macro.get("res_h", 0)
        self._res_w_var.set(str(rw) if rw else "")
        self._res_h_var.set(str(rh) if rh else "")
        self.tree_canvas.refresh()
        self.props_panel._build_empty()
        self._update_undo_redo_btns()

    def _update_undo_redo_btns(self):
        self._undo_btn.configure(
            state="normal" if self._undo_stack else "disabled",
            fg=COLORS["text"] if self._undo_stack else COLORS["text_dim"])
        self._redo_btn.configure(
            state="normal" if self._redo_stack else "disabled",
            fg=COLORS["text"] if self._redo_stack else COLORS["text_dim"])

    # ── Gestion des noeuds ────────────────────
    def _find_parent_list(self, node_id, nodes=None):
        """Retourne (list, index) du noeud dans son conteneur parent."""
        if nodes is None:
            nodes = self.current_macro["nodes"]
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
        if not messagebox.askyesno(t("node.delete_title"), t("node.delete_confirm"), parent=self):
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

    # ── Execution ─────────────────────────────
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
        self._status_var.set("Execution en cours...")
        self._progress.start(10)
        _play_cue("run")

        self._engine = MacroEngine(
            self.current_macro,
            macros_list=self.macros,
            on_step =self._on_step,
            on_done =self._on_done,
            on_error=self._on_error,
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
        self._pause_btn.configure(state="disabled", text=f"{t('btn.pause')}  [{p}]")
        self._stop_btn.configure(state="disabled")
        self._status_var.set(t("status.ready_full", r=r, s=s, p=p))
        self._progress.stop()

    # ── Fichiers ──────────────────────────────
    def _save_file(self):
        if self._file_path:
            self._write_file(self._file_path)
        else:
            self._save_file_as()

    def _save_file_as(self):
        path = filedialog.asksaveasfilename(
            initialdir=get_macros_dir(),
            defaultextension=".macros",
            filetypes=[("MacroEverything", "*.macros"), ("JSON", "*.json")],
            title=t("file.save_title"))
        if path:
            self._file_path = path
            self._write_file(path)

    def _write_file(self, path):
        try:
            data = {
                "macros":  self.macros,
                "hotkeys": self.hotkey_manager.hotkeys
                           if hasattr(self, "hotkey_manager") else {},
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._file_path = path
            settings = load_settings()
            settings["last_file"] = path
            save_settings(settings)
            self._mark_clean()
            self._status_var.set(t("status.saved", name=os.path.basename(path)))
        except Exception as e:
            messagebox.showerror(t("warn.error_save_title"), t("warn.error_save_msg", e=e))

    def _open_file(self):
        path = filedialog.askopenfilename(
            initialdir=get_macros_dir(),
            filetypes=[("MacroEverything", "*.macros"), ("JSON", "*.json")],
            title=t("file.open_title"))
        if not path:
            return
        if self._dirty:
            answer = messagebox.askyesnocancel(
                t("file.unsaved_title"), t("file.unsaved_msg"))
            if answer is None:
                return
            if answer:
                self._save_file()
        path = import_to_macros_dir(path)
        self._load_file(path)
