"""
macro_app/ui/dialogs.py
Dialogues de l'application :
  NodeEditorDialog    — edition des parametres d'un noeud
  PickerWindow        — selection de coordonnees en surimpression ecran
  RegionCaptureWindow — selection d'une zone de capture ecran
  AddNodeDialog       — choix du type de noeud a ajouter
  LanguageDialog      — selection de la langue de l'interface
"""

import io
import base64
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from ..constants import COLORS, FONTS, NODE_TYPES, NODE_ICONS
from ..utils import PIL_AVAILABLE, Image, ImageTk, ImageGrab
from ..models import new_node, _collect_labels, _collect_var_names
from ..i18n import t as _t, node_label, cat_label


# ─────────────────────────────────────────────
#  DIALOGUE D'EDITION DE NOEUDS
# ─────────────────────────────────────────────
class NodeEditorDialog(tk.Toplevel):
    def __init__(self, parent, node, app):
        super().__init__(parent)
        self.node   = node
        self.app    = app
        self.result = None
        ntype = NODE_TYPES.get(node["type"], {})
        self.title(f"{_t('node.edit_prefix')}  -  {node_label(node['type'])}")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)
        self._build_ui()
        self._center()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(
            f"+{(self.winfo_screenwidth() - w) // 2}"
            f"+{(self.winfo_screenheight() - h) // 2}")

    def _build_ui(self):
        t = self.node["type"]
        p = self.node["params"]
        frame = tk.Frame(self, bg=COLORS["bg"], padx=20, pady=16)
        frame.pack(fill="both", expand=True)
        ntype = NODE_TYPES.get(t, {})
        icon  = NODE_ICONS.get(t, "")
        tk.Label(frame,
                 text=f"{icon}  {node_label(t)}",
                 bg=COLORS["bg"], fg=COLORS["accent"],
                 font=FONTS["heading"]).pack(anchor="w", pady=(0, 12))
        self.vars = {}

        if t == "action_click":
            self._field(frame, "x",     _t("field.pos_x"),        p.get("x", 0))
            self._field(frame, "y",     _t("field.pos_y"),        p.get("y", 0))
            self._choice(frame, "button", _t("field.button"),
                         p.get("button", "left"), ["left", "right", "middle"])
            self._field(frame, "count", _t("field.click_count"),  p.get("count", 1))
            self._pick_coords_btn(frame)

        elif t == "action_move":
            self._field(frame, "x", _t("field.pos_x"), p.get("x", 0))
            self._field(frame, "y", _t("field.pos_y"), p.get("y", 0))
            self._pick_coords_btn(frame)

        elif t == "action_scroll":
            self._field(frame, "x",     _t("field.pos_x"),          p.get("x", 0))
            self._field(frame, "y",     _t("field.pos_y"),          p.get("y", 0))
            self._field(frame, "delta", _t("field.scroll_delta"),   p.get("delta", 3))
            self._pick_coords_btn(frame)

        elif t == "action_key":
            tk.Label(frame, text=_t("field.key_combo"),
                     bg=COLORS["bg"], fg=COLORS["text_dim"],
                     font=FONTS["small"]).pack(anchor="w")
            tk.Label(frame, text=_t("field.key_combo_hint"),
                     bg=COLORS["bg"], fg=COLORS["text_dim"],
                     font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=(0, 4))
            v = tk.StringVar(value=p.get("keys", ""))
            self.vars["keys"] = v
            tk.Entry(frame, textvariable=v,
                     bg=COLORS["bg3"], fg=COLORS["text"],
                     font=FONTS["mono"], insertbackground=COLORS["text"],
                     relief="flat", width=30).pack(fill="x", pady=(0, 8))
            qf = tk.Frame(frame, bg=COLORS["bg"])
            qf.pack(fill="x", pady=(0, 8))
            tk.Label(qf, text=_t("field.quick"), bg=COLORS["bg"],
                     fg=COLORS["text_dim"], font=FONTS["small"]).pack(side="left")
            for s in ["enter", "esc", "tab", "ctrl+c", "ctrl+v", "ctrl+z", "alt+F4", "F5"]:
                tk.Button(qf, text=s,
                          bg=COLORS["bg3"], fg=COLORS["text"],
                          font=FONTS["small"], relief="flat", cursor="hand2",
                          padx=5, pady=2,
                          command=lambda s=s: v.set(s)).pack(side="left", padx=2)

        elif t == "action_type":
            tk.Label(frame, text=_t("field.text_to_type"),
                     bg=COLORS["bg"], fg=COLORS["text_dim"],
                     font=FONTS["small"]).pack(anchor="w")
            self._txt_widget = tk.Text(
                frame, bg=COLORS["bg3"], fg=COLORS["text"],
                font=FONTS["normal"], insertbackground=COLORS["text"],
                relief="flat", width=40, height=4, wrap="word")
            self._txt_widget.insert("1.0", p.get("text", ""))
            self._txt_widget.pack(fill="x", pady=(0, 8))

        elif t == "action_wait":
            self._field(frame, "ms", _t("field.duration_ms"), p.get("ms", 1000))
            qf = tk.Frame(frame, bg=COLORS["bg"])
            qf.pack(fill="x", pady=(0, 8))
            tk.Label(qf, text=_t("field.quick"), bg=COLORS["bg"],
                     fg=COLORS["text_dim"], font=FONTS["small"]).pack(side="left")
            for lbl, val in [("0.5s", 500), ("1s", 1000), ("2s", 2000), ("5s", 5000)]:
                tk.Button(qf, text=lbl,
                          bg=COLORS["bg3"], fg=COLORS["text"],
                          font=FONTS["small"], relief="flat", cursor="hand2",
                          padx=5, pady=2,
                          command=lambda v=val: self.vars["ms"].set(str(v))
                          ).pack(side="left", padx=2)

        elif t == "action_run":
            tk.Label(frame, text=_t("field.run_cmd"),
                     bg=COLORS["bg"], fg=COLORS["text_dim"],
                     font=FONTS["small"]).pack(anchor="w")
            row = tk.Frame(frame, bg=COLORS["bg"])
            row.pack(fill="x", pady=(0, 8))
            v = tk.StringVar(value=p.get("command", ""))
            self.vars["command"] = v
            tk.Entry(row, textvariable=v,
                     bg=COLORS["bg3"], fg=COLORS["text"],
                     font=FONTS["normal"], insertbackground=COLORS["text"],
                     relief="flat", width=30).pack(side="left", fill="x", expand=True)
            tk.Button(row, text="...",
                      bg=COLORS["bg3"], fg=COLORS["text"],
                      relief="flat", cursor="hand2",
                      command=lambda: v.set(filedialog.askopenfilename())
                      ).pack(side="left", padx=4)

        elif t in ("condition_screen", "loop_while"):
            self._build_screen_capture_ui(frame, p)

        elif t == "condition_pixel":
            self._field(frame, "x",         _t("field.pixel_x"),   p.get("x", 0))
            self._field(frame, "y",         _t("field.pixel_y"),   p.get("y", 0))
            self._field(frame, "r",         _t("field.color_r"),   p.get("r", 0))
            self._field(frame, "g",         _t("field.color_g"),   p.get("g", 0))
            self._field(frame, "b",         _t("field.color_b"),   p.get("b", 0))
            self._field(frame, "tolerance", _t("field.tolerance"), p.get("tolerance", 10))
            self._pick_pixel_btn(frame)

        elif t == "loop_count":
            self._field(frame, "count", _t("field.repeat_count"), p.get("count", 1))

        elif t == "label":
            self._field(frame, "name", _t("field.label_name"), p.get("name", ""))

        elif t == "goto":
            labels = _collect_labels(self.app.current_macro)
            tk.Label(frame, text=_t("field.goto_target"),
                     bg=COLORS["bg"], fg=COLORS["text_dim"],
                     font=FONTS["small"]).pack(anchor="w")
            v = tk.StringVar(value=p.get("target", ""))
            self.vars["target"] = v
            if labels:
                cb = ttk.Combobox(frame, textvariable=v, values=labels,
                                  font=FONTS["normal"], width=28, state="readonly")
                cb.pack(fill="x", pady=(0, 8))
                tk.Button(frame, text=_t("btn.refresh"),
                          bg=COLORS["bg3"], fg=COLORS["text_dim"],
                          font=FONTS["small"], relief="flat", cursor="hand2",
                          padx=6, pady=3,
                          command=lambda: cb.configure(
                              values=_collect_labels(self.app.current_macro))
                          ).pack(anchor="w", pady=(0, 4))
            else:
                tk.Entry(frame, textvariable=v,
                         bg=COLORS["bg3"], fg=COLORS["text"],
                         font=FONTS["normal"], insertbackground=COLORS["text"],
                         relief="flat", width=30).pack(fill="x", pady=(0, 4))
                tk.Label(frame,
                         text=_t("field.no_labels"),
                         bg=COLORS["bg"], fg=COLORS["yellow"],
                         font=FONTS["small"], justify="left").pack(anchor="w", pady=(0, 8))

        elif t == "action_focus":
            tk.Label(frame,
                     text=_t("field.focus_hint"),
                     bg=COLORS["bg"], fg=COLORS["text_dim"],
                     font=FONTS["small"], justify="left").pack(anchor="w", pady=(0, 4))
            self._field(frame, "title", _t("field.window_title"), p.get("title", ""))
            v_partial = tk.BooleanVar(value=bool(p.get("partial", True)))
            self.vars["partial"] = v_partial
            tk.Checkbutton(frame, text=_t("field.partial_match"),
                           variable=v_partial,
                           bg=COLORS["bg"], fg=COLORS["text"],
                           selectcolor=COLORS["bg3"],
                           activebackground=COLORS["bg"],
                           font=FONTS["normal"]).pack(anchor="w", pady=(0, 8))

        elif t == "var_set":
            var_names = _collect_var_names(self.app.current_macro["nodes"])
            self._combo_field(frame, "name",  _t("field.var_name"),  p.get("name",  ""), var_names)
            self._field(frame, "value", _t("field.var_value"), p.get("value", 0))

        elif t == "var_add":
            var_names = _collect_var_names(self.app.current_macro["nodes"])
            self._combo_field(frame, "name",  _t("field.var_name"),  p.get("name",  ""), var_names)
            self._field(frame, "delta", _t("field.var_delta"), p.get("delta", 1))

        elif t == "condition_var":
            var_names = _collect_var_names(self.app.current_macro["nodes"])
            self._combo_field(frame, "name", _t("field.variable"),    p.get("name", ""), var_names)
            self._choice(frame, "op", _t("field.op_compare"),
                         p.get("op", "=="), ["==", "!=", ">", "<", ">=", "<="])
            self._field(frame, "ref", _t("field.compare_value"),   p.get("ref", 0))

        elif t == "loop_while_var":
            var_names = _collect_var_names(self.app.current_macro["nodes"])
            self._combo_field(frame, "name", _t("field.condition_var"), p.get("name", ""), var_names)
            self._choice(frame, "op", _t("field.operator"),
                         p.get("op", "=="), ["==", "!=", ">", "<", ">=", "<="])
            self._field(frame, "ref",      _t("field.ref_value"),  p.get("ref", 0))
            self._field(frame, "max_iter", _t("field.max_iter"),   p.get("max_iter", 10000))

        elif t == "call_macro":
            tk.Label(frame,
                     text=_t("node.call_macro_desc"),
                     bg=COLORS["bg"], fg=COLORS["text_dim"],
                     font=FONTS["small"], justify="left").pack(anchor="w", pady=(0, 8))
            names = [m["name"] for m in self.app.macros
                     if m is not self.app.current_macro]
            self._combo_field(frame, "macro_name", _t("field.macro_name"),
                              p.get("macro_name", ""), names)

        elif t == "stop_return":
            tk.Label(frame,
                     text=_t("node.stop_return_desc"),
                     bg=COLORS["bg"], fg=COLORS["text_dim"],
                     font=FONTS["small"], justify="left").pack(anchor="w", pady=(0, 8))
            self._choice(frame, "value", _t("field.return_value"),
                         str(p.get("value", "False")), ["True", "False"])

        elif t == "record_replay":
            self._build_record_replay_ui(frame, p)

        elif t == "condition_group":
            self._cg_logic_var  = tk.StringVar(value=p.get("logic", "AND"))
            self._cg_conditions = list(p.get("conditions", []))
            lf = tk.Frame(frame, bg=COLORS["bg"])
            lf.pack(fill="x", pady=(0, 10))
            tk.Label(lf, text=_t("field.logic"),
                     bg=COLORS["bg"], fg=COLORS["text_dim"],
                     font=FONTS["normal"]).pack(side="left", padx=(0, 8))
            for logic in ["AND", "OR"]:
                tk.Radiobutton(lf, text=logic, variable=self._cg_logic_var,
                               value=logic,
                               bg=COLORS["bg"], fg=COLORS["text"],
                               selectcolor=COLORS["bg3"],
                               activebackground=COLORS["bg"],
                               font=("Segoe UI", 11, "bold")).pack(side="left", padx=10)
            tk.Label(frame, text=_t("field.conditions"),
                     bg=COLORS["bg"], fg=COLORS["text_dim"],
                     font=FONTS["small"]).pack(anchor="w")
            self._cg_list_frame = tk.Frame(frame, bg=COLORS["bg3"])
            self._cg_list_frame.pack(fill="x", pady=(2, 8))
            self._refresh_cg_list()
            tk.Button(frame, text=_t("btn.add_condition"),
                      bg=COLORS["accent"], fg=COLORS["bg"],
                      font=FONTS["normal"], relief="flat", cursor="hand2",
                      padx=10, pady=5,
                      command=self._add_cg_condition).pack(anchor="w", pady=(0, 8))

        # ── Boutons OK / Annuler ──
        bf = tk.Frame(frame, bg=COLORS["bg"])
        bf.pack(fill="x", pady=(16, 0))
        tk.Button(bf, text=_t("btn.confirm"),
                  bg=COLORS["green"], fg=COLORS["bg"],
                  font=FONTS["heading"], relief="flat", cursor="hand2",
                  padx=16, pady=8,
                  command=self._ok).pack(side="right", padx=(8, 0))
        tk.Button(bf, text=_t("btn.cancel"),
                  bg=COLORS["surface"], fg=COLORS["text"],
                  font=FONTS["normal"], relief="flat", cursor="hand2",
                  padx=16, pady=8,
                  command=self.destroy).pack(side="right")

    # ── Helpers de construction ───────────────
    def _build_record_replay_ui(self, frame, p):
        """Interface de configuration du noeud Enregistrer/Rejouer."""
        FKEYS = ["F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12"]

        # Actions déjà enregistrées (liste locale mutable)
        self._rec_actions  = list(p.get("actions", []))
        self._rec_stop_flag = [False]   # [0] = True pour stopper le thread
        self._rec_thread    = None

        self._combo_field(frame, "hotkey",
                          _t("rr.hotkey"),
                          p.get("hotkey", "F6"), FKEYS)

        # ── Ce qui est enregistré ──
        tk.Label(frame, text=_t("rr.what_record"),
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(anchor="w", pady=(6, 2))

        # Dict vivant lu par le thread d'enregistrement (GIL-safe)
        self._rr_filter = {
            "record_clicks":     bool(p.get("record_clicks",     True)),
            "record_wheel":      bool(p.get("record_wheel",      True)),
            "record_mouse_move": bool(p.get("record_mouse_move", False)),
            "record_keyboard":   bool(p.get("record_keyboard",   True)),
            "mouse_mode":        p.get("mouse_mode", "absolute"),
        }

        checks_frame = tk.Frame(frame, bg=COLORS["bg"])
        checks_frame.pack(fill="x", pady=(0, 6))
        for col, (key, lbl_key, default) in enumerate([
            ("record_clicks",     "rr.clicks",     True),
            ("record_wheel",      "rr.wheel",       True),
            ("record_mouse_move", "rr.mouse_move",  False),
            ("record_keyboard",   "rr.keyboard",    True),
        ]):
            v = tk.IntVar(value=1 if p.get(key, default) else 0)
            self.vars[key] = v
            def _sync(_, __, ___, k=key, var=v):
                self._rr_filter[k] = bool(var.get())
            v.trace_add("write", _sync)
            tk.Checkbutton(checks_frame, text=_t(lbl_key),
                           variable=v,
                           bg=COLORS["bg"], fg=COLORS["text"],
                           selectcolor=COLORS["bg3"],
                           activebackground=COLORS["bg"],
                           font=FONTS["normal"]).grid(
                row=col // 2, column=col % 2, sticky="w", padx=(0, 16), pady=2)

        # ── Mode coordonnées souris ──
        tk.Label(frame, text=_t("rr.mouse_mode"),
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(anchor="w", pady=(8, 2))
        mode_v = tk.StringVar(value=p.get("mouse_mode", "absolute"))
        self.vars["mouse_mode"] = mode_v
        def _sync_mode(_, __, ___):
            self._rr_filter["mouse_mode"] = mode_v.get()
        mode_v.trace_add("write", _sync_mode)
        self._mode_radios = []
        for mode, lbl_key in [("absolute", "rr.absolute"), ("relative", "rr.relative")]:
            rb = tk.Radiobutton(frame, text=_t(lbl_key),
                                variable=mode_v, value=mode,
                                bg=COLORS["bg"], fg=COLORS["text"],
                                selectcolor=COLORS["bg3"],
                                activebackground=COLORS["bg"],
                                font=FONTS["normal"],
                                wraplength=320, justify="left")
            rb.pack(anchor="w", pady=2)
            self._mode_radios.append(rb)
        # Verrouiller si des actions sont déjà enregistrées
        if self._rec_actions:
            for rb in self._mode_radios:
                rb.config(state="disabled")

        # ── Bouton enregistrement ──
        tk.Frame(frame, bg=COLORS["bg3"], height=1).pack(fill="x", pady=(10, 8))

        n0      = len(self._rec_actions)
        btn_lbl = _t("rr.btn_re_record") if n0 > 0 else _t("rr.btn_record")
        self._btn_rr = tk.Button(frame, text=btn_lbl,
                                  bg=COLORS["red"], fg=COLORS["bg"],
                                  font=FONTS["heading"], relief="flat", cursor="hand2",
                                  padx=14, pady=8,
                                  command=self._start_rr_recording)
        self._btn_rr.pack(anchor="w", pady=(0, 4))

        self._lbl_rr_status = tk.Label(frame, text="",
                                        bg=COLORS["bg"], fg=COLORS["yellow"],
                                        font=FONTS["small"], justify="left", wraplength=340)
        self._lbl_rr_status.pack(anchor="w")

        info = _t("rr.actions_count", n=n0) if n0 > 0 else _t("rr.no_actions")
        self._lbl_rr_count = tk.Label(frame, text=info,
                                       bg=COLORS["bg"],
                                       fg=COLORS["green"] if n0 > 0 else COLORS["text_dim"],
                                       font=FONTS["small"])
        self._lbl_rr_count.pack(anchor="w", pady=(4, 0))

        tk.Label(frame, text=_t("rr.hint"),
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"], justify="left", wraplength=340).pack(
                 anchor="w", pady=(6, 0))

        # Fermeture propre si enregistrement en cours
        self.protocol("WM_DELETE_WINDOW", self._on_rr_dialog_close)

    def _start_rr_recording(self):
        """Lance l'enregistrement dans un thread dédié."""
        self._rec_stop_flag[0] = False
        self._btn_rr.config(state="disabled")
        # Déverrouiller le mode souris pour la nouvelle session
        for rb in getattr(self, "_mode_radios", []):
            rb.config(state="normal")
        trigger = self.vars["hotkey"].get()
        self._lbl_rr_status.config(
            text=_t("rr.armed_status", trigger=trigger),
            fg=COLORS["yellow"])
        self._rec_thread = threading.Thread(
            target=self._run_rr_recording_thread,
            args=(trigger,),
            daemon=True)
        self._rec_thread.start()

    def _run_rr_recording_thread(self, hotkey):
        """Thread : phase 1 = attendre touche, phase 2 = hooks throttl\u00e9s."""
        import ctypes
        import ctypes.wintypes
        import time
        try:
            user32 = ctypes.windll.user32
            user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                              ctypes.c_size_t, ctypes.c_size_t]
            user32.CallNextHookEx.restype  = ctypes.c_size_t
        except Exception:
            self.after(0, self._on_rr_recording_done, [])
            return

        VK_TRIGGER = {
            "F1": 0x70, "F2": 0x71, "F3": 0x72,  "F4": 0x73,
            "F5": 0x74, "F6": 0x75, "F7": 0x76,  "F8": 0x77,
            "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
        }.get(hotkey.upper(), 0x75)

        # ── Phase 1 : attendre l'appui sur la touche trigger ───────────
        was_down = False
        while not self._rec_stop_flag[0]:
            is_down = bool(user32.GetAsyncKeyState(VK_TRIGGER) & 0x8000)
            if is_down and not was_down:
                break
            was_down = is_down
            time.sleep(0.02)

        if self._rec_stop_flag[0]:
            try:
                self.after(0, self._on_rr_recording_done, [])
            except Exception:
                pass
            return

        while user32.GetAsyncKeyState(VK_TRIGGER) & 0x8000:  # attendre rel\u00e2chement
            time.sleep(0.01)

        try:
            self.after(0, self._on_rr_started, hotkey)
        except Exception:
            pass

        # ── Lire les filtres au démarrage effectif (après la touche trigger) ──
        _f          = getattr(self, "_rr_filter", {})
        do_clicks   = _f.get("record_clicks",     True)
        do_wheel    = _f.get("record_wheel",      True)
        do_move     = _f.get("record_mouse_move", False)
        do_keyboard = _f.get("record_keyboard",   True)
        mouse_mode  = _f.get("mouse_mode",        "absolute")

        # ── Phase 2 : enregistrement via hooks LL ─────────────────────
        actions = []
        state   = {"last_t": time.perf_counter(), "stop": False,
                   "last_move_t": 0.0}

        if mouse_mode == "relative":
            pt = ctypes.wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            state["orig_x"] = pt.x
            state["orig_y"] = pt.y

        WH_KEYBOARD_LL = 13;  WH_MOUSE_LL    = 14
        WM_LBUTTONDOWN = 0x0201; WM_LBUTTONUP   = 0x0202
        WM_RBUTTONDOWN = 0x0204; WM_RBUTTONUP   = 0x0205
        WM_MBUTTONDOWN = 0x0207; WM_MBUTTONUP   = 0x0208
        WM_MOUSEMOVE   = 0x0200; WM_MOUSEWHEEL  = 0x020A
        WM_KEYDOWN     = 0x0100; WM_SYSKEYDOWN  = 0x0104
        WM_KEYUP       = 0x0101; WM_SYSKEYUP    = 0x0105
        MOVE_INTERVAL  = 0.020   # 50 fps max pour les d\u00e9placements souris

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("pt",          ctypes.wintypes.POINT),
                        ("mouseData",   ctypes.c_ulong),
                        ("flags",       ctypes.c_ulong),
                        ("time",        ctypes.c_ulong),
                        ("dwExtraInfo", ctypes.c_ulong)]

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("vkCode",      ctypes.c_ulong),
                        ("scanCode",    ctypes.c_ulong),
                        ("flags",       ctypes.c_ulong),
                        ("time",        ctypes.c_ulong),
                        ("dwExtraInfo", ctypes.c_ulong)]

        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_size_t, ctypes.c_int,
                                       ctypes.c_size_t, ctypes.c_size_t)

        def _dt():
            now = time.perf_counter()
            dt  = max(0.0, now - state["last_t"])
            state["last_t"] = now
            return dt

        def mouse_cb(nCode, wParam, lParam):
            if nCode >= 0 and not state["stop"]:
                # Chemin rapide pour les mouvements : throttle AVANT ctypes.cast
                if wParam == WM_MOUSEMOVE:
                    if do_move:
                        now_m = time.perf_counter()
                        if now_m - state["last_move_t"] >= MOVE_INTERVAL:
                            ms = ctypes.cast(
                                lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                            x, y = ms.pt.x, ms.pt.y
                            rx = x - state.get("orig_x", x) if mouse_mode == "relative" else x
                            ry = y - state.get("orig_y", y) if mouse_mode == "relative" else y
                            state["last_move_t"] = now_m
                            actions.append({"t": "move", "x": rx, "y": ry, "dt": _dt()})
                else:
                    ms = ctypes.cast(
                        lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    x, y = ms.pt.x, ms.pt.y
                    if mouse_mode == "relative":
                        rx = x - state.get("orig_x", x)
                        ry = y - state.get("orig_y", y)
                    else:
                        rx, ry = x, y
                    dt = _dt()
                    if wParam in (WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN) and do_clicks:
                        btn = ("left"   if wParam == WM_LBUTTONDOWN
                               else "right" if wParam == WM_RBUTTONDOWN else "middle")
                        actions.append({"t": "click_dn", "x": rx, "y": ry, "btn": btn, "dt": dt})
                    elif wParam in (WM_LBUTTONUP, WM_RBUTTONUP, WM_MBUTTONUP) and do_clicks:
                        btn = ("left"   if wParam == WM_LBUTTONUP
                               else "right" if wParam == WM_RBUTTONUP else "middle")
                        actions.append({"t": "click_up", "x": rx, "y": ry, "btn": btn, "dt": dt})
                    elif wParam == WM_MOUSEWHEEL and do_wheel:
                        delta = ctypes.c_short(ms.mouseData >> 16).value // 120
                        actions.append({"t": "scroll", "x": rx, "y": ry, "delta": delta, "dt": dt})
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        def kb_cb(nCode, wParam, lParam):
            if nCode >= 0 and not state["stop"]:
                kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = kb.vkCode
                if vk == VK_TRIGGER and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    state["stop"] = True
                    return 1   # avaler la touche d'arrêt
                if do_keyboard and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    actions.append({"t": "key_dn", "vk": vk, "dt": _dt()})
                elif do_keyboard and wParam in (WM_KEYUP, WM_SYSKEYUP):
                    actions.append({"t": "key_up", "vk": vk, "dt": _dt()})
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        mouse_proc = HOOKPROC(mouse_cb)
        kb_proc    = HOOKPROC(kb_cb)
        h_mouse = user32.SetWindowsHookExW(WH_MOUSE_LL,    mouse_proc, None, 0)
        h_kb    = user32.SetWindowsHookExW(WH_KEYBOARD_LL, kb_proc,    None, 0)

        msg = ctypes.wintypes.MSG()
        while not state["stop"] and not self._rec_stop_flag[0]:
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.001)

        user32.UnhookWindowsHookEx(h_mouse)
        user32.UnhookWindowsHookEx(h_kb)
        try:
            self.after(0, self._on_rr_recording_done, actions)
        except Exception:
            pass  # dialog peut avoir été détruite

    def _on_rr_started(self, hotkey):
        """Appel\u00e9 dans le thread Tkinter quand la touche d\u00e9marre l'enregistrement."""
        self._lbl_rr_status.config(
            text=_t("rr.recording_status", trigger=hotkey),
            fg=COLORS["red"])

    def _on_rr_recording_done(self, actions):
        """Appelé dans le thread Tkinter une fois l'enregistrement terminé."""
        self._rec_actions = actions
        # Verrouiller le mode : les coordonnées enregistrées doivent rester cohérentes
        if actions:
            for rb in getattr(self, "_mode_radios", []):
                rb.config(state="disabled")
        n = len(actions)
        self._lbl_rr_status.config(text="")
        self._lbl_rr_count.config(
            text=_t("rr.actions_count", n=n) if n > 0 else _t("rr.no_actions"),
            fg=COLORS["green"] if n > 0 else COLORS["text_dim"])
        self._btn_rr.config(
            state="normal",
            text=_t("rr.btn_re_record") if n > 0 else _t("rr.btn_record"))

    def _on_rr_dialog_close(self):
        """Arrête l'enregistrement éventuel puis ferme la dialog."""
        if hasattr(self, "_rec_stop_flag"):
            self._rec_stop_flag[0] = True
        self.destroy()

    def _field(self, parent, key, label, default=""):
        tk.Label(parent, text=label,
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(anchor="w")
        v = tk.StringVar(value=str(default))
        self.vars[key] = v
        tk.Entry(parent, textvariable=v,
                 bg=COLORS["bg3"], fg=COLORS["text"],
                 font=FONTS["normal"], insertbackground=COLORS["text"],
                 relief="flat", width=30).pack(fill="x", pady=(0, 8))

    def _combo_field(self, parent, key, label, default="", options=None):
        """Champ editable avec liste deroulante de suggestions."""
        tk.Label(parent, text=label,
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(anchor="w")
        v = tk.StringVar(value=str(default))
        self.vars[key] = v
        cb = ttk.Combobox(parent, textvariable=v,
                          values=options or [],
                          font=FONTS["normal"], width=28)
        cb.pack(fill="x", pady=(0, 8))

    def _choice(self, parent, key, label, default, options):
        tk.Label(parent, text=label,
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(anchor="w")
        v = tk.StringVar(value=default)
        self.vars[key] = v
        row = tk.Frame(parent, bg=COLORS["bg"])
        row.pack(fill="x", pady=(0, 8))
        for opt in options:
            tk.Radiobutton(row, text=opt, variable=v, value=opt,
                           bg=COLORS["bg"], fg=COLORS["text"],
                           selectcolor=COLORS["bg3"],
                           activebackground=COLORS["bg"],
                           font=FONTS["normal"]).pack(side="left", padx=8)

    def _pick_coords_btn(self, parent):
        def pick():
            self.withdraw()
            PickerWindow(self, self._set_xy)
        tk.Button(parent,
                  text=_t("btn.pick_position"),
                  bg=COLORS["accent"], fg=COLORS["bg"],
                  font=FONTS["normal"], relief="flat", cursor="hand2",
                  padx=12, pady=6, command=pick).pack(pady=(0, 8))

    def _pick_pixel_btn(self, parent):
        def pick():
            self.withdraw()
            PickerWindow(self, self._set_pixel)
        tk.Button(parent,
                  text=_t("btn.pick_pixel"),
                  bg=COLORS["teal"], fg=COLORS["bg"],
                  font=FONTS["normal"], relief="flat", cursor="hand2",
                  padx=12, pady=6, command=pick).pack(pady=(0, 8))

    def _set_xy(self, x, y):
        self.deiconify()
        if "x" in self.vars: self.vars["x"].set(str(x))
        if "y" in self.vars: self.vars["y"].set(str(y))

    def _set_pixel(self, x, y):
        self.deiconify()
        if "x" in self.vars: self.vars["x"].set(str(x))
        if "y" in self.vars: self.vars["y"].set(str(y))
        if PIL_AVAILABLE and ImageGrab:
            try:
                px = ImageGrab.grab(bbox=(x, y, x + 1, y + 1)).getpixel((0, 0))
                if "r" in self.vars: self.vars["r"].set(str(px[0]))
                if "g" in self.vars: self.vars["g"].set(str(px[1]))
                if "b" in self.vars: self.vars["b"].set(str(px[2]))
            except Exception:
                pass

    def _build_screen_capture_ui(self, frame, p):
        self._template_b64 = p.get("template_b64", "")
        self._region       = p.get("region", None)
        if p.get("threshold") is None:
            p["threshold"] = 0.85

        pf = tk.Frame(frame, bg=COLORS["bg3"], width=220, height=90)
        pf.pack(fill="x", pady=(0, 8))
        pf.pack_propagate(False)
        self._preview_lbl = tk.Label(pf, bg=COLORS["bg3"],
                                     fg=COLORS["text_dim"],
                                     text=_t("capture.none"),
                                     font=FONTS["small"])
        self._preview_lbl.place(relx=0.5, rely=0.5, anchor="center")
        if self._template_b64 and PIL_AVAILABLE:
            self._show_preview()

        row = tk.Frame(frame, bg=COLORS["bg"])
        row.pack(fill="x", pady=(0, 8))
        tk.Button(row, text=_t("capture.btn_capture"),
                  bg=COLORS["accent2"], fg=COLORS["bg"],
                  font=FONTS["normal"], relief="flat", cursor="hand2",
                  padx=12, pady=6,
                  command=self._capture).pack(side="left", padx=(0, 8))
        tk.Button(row, text=_t("capture.btn_clear"),
                  bg=COLORS["surface"], fg=COLORS["text"],
                  font=FONTS["small"], relief="flat", cursor="hand2",
                  padx=8, pady=6,
                  command=self._clear).pack(side="left")

        self._field(frame, "threshold",
                    _t("capture.threshold"),
                    p.get("threshold", 0.85))
        if self.node["type"] == "loop_while":
            self._field(frame, "max_iter",
                        _t("field.max_iter_loop"),
                        p.get("max_iter", 100))

    def _show_preview(self):
        if not PIL_AVAILABLE or not Image or not ImageTk:
            return
        try:
            img = Image.open(io.BytesIO(base64.b64decode(self._template_b64)))
            img.thumbnail((220, 90))
            photo = ImageTk.PhotoImage(img)
            self._preview_lbl.configure(image=photo, text="")
            self._preview_lbl._photo = photo
        except Exception:
            pass

    def _capture(self):
        self.withdraw()
        RegionCaptureWindow(self, self._on_captured)

    def _on_captured(self, img):
        self.deiconify()
        if img is None:
            return
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        self._template_b64 = base64.b64encode(buf.getvalue()).decode()
        self._show_preview()

    def _clear(self):
        self._template_b64 = ""
        self._preview_lbl.configure(image="", text=_t("capture.none"))

    # ── Helpers condition_group ───────────────
    def _refresh_cg_list(self):
        for w in self._cg_list_frame.winfo_children():
            w.destroy()
        if not self._cg_conditions:
            tk.Label(self._cg_list_frame,
                     text=_t("cg.empty"),
                     bg=COLORS["bg3"], fg=COLORS["text_dim"],
                     font=FONTS["small"]).pack(anchor="w", padx=8, pady=6)
            return
        for i, cond in enumerate(self._cg_conditions):
            row = tk.Frame(self._cg_list_frame, bg=COLORS["bg3"])
            row.pack(fill="x", padx=4, pady=2)
            tk.Label(row, text=self._sub_cond_desc(cond),
                     bg=COLORS["bg3"], fg=COLORS["text"],
                     font=FONTS["small"], anchor="w"
                     ).pack(side="left", fill="x", expand=True, padx=4)
            tk.Button(row, text="\u270e",
                      bg=COLORS["bg3"], fg=COLORS["accent"],
                      font=FONTS["small"], relief="flat", cursor="hand2",
                      padx=4,
                      command=lambda i=i: self._edit_cg_condition(i)
                      ).pack(side="right")
            tk.Button(row, text="\u2715",
                      bg=COLORS["bg3"], fg=COLORS["red"],
                      font=FONTS["small"], relief="flat", cursor="hand2",
                      padx=4,
                      command=lambda i=i: self._remove_cg_condition(i)
                      ).pack(side="right", padx=2)

    @staticmethod
    def _sub_cond_desc(cond: dict) -> str:
        ct = cond.get("type", "")
        if ct == "var":
            return (f"[Variable]  {cond.get('name','?')} "
                    f"{cond.get('op','==')} {cond.get('ref', 0)}")
        if ct == "pixel":
            return (f"[Pixel]  ({cond.get('x','?')},{cond.get('y','?')})  "
                    f"rgb({cond.get('r','?')},{cond.get('g','?')},{cond.get('b','?')})")
        return str(cond)

    def _add_cg_condition(self):
        var_names = _collect_var_names(self.app.current_macro["nodes"])
        dlg = _SubCondDialog(self, var_names=var_names)
        self.wait_window(dlg)
        if dlg.result:
            self._cg_conditions.append(dlg.result)
            self._refresh_cg_list()

    def _edit_cg_condition(self, idx):
        var_names = _collect_var_names(self.app.current_macro["nodes"])
        dlg = _SubCondDialog(self, existing=self._cg_conditions[idx], var_names=var_names)
        self.wait_window(dlg)
        if dlg.result:
            self._cg_conditions[idx] = dlg.result
            self._refresh_cg_list()

    def _remove_cg_condition(self, idx):
        self._cg_conditions.pop(idx)
        self._refresh_cg_list()

    def _ok(self):
        t = self.node["type"]

        # Traitement special condition_group (structure non standard)
        if t == "condition_group":
            p = {
                "logic":      self._cg_logic_var.get(),
                "conditions": list(self._cg_conditions),
            }
            self.app._push_history()
            self.node["params"] = p
            self.result = p
            self.destroy()
            self.app.tree_canvas.refresh()
            return

        # Traitement special record_replay : booleans + preservation des actions
        if t == "record_replay":
            # Arrêter l'enregistrement en cours si besoin
            if hasattr(self, "_rec_stop_flag"):
                self._rec_stop_flag[0] = True
            p = {
                "hotkey":            self.vars["hotkey"].get(),
                "record_clicks":     bool(self.vars["record_clicks"].get()),
                "record_wheel":      bool(self.vars["record_wheel"].get()),
                "record_mouse_move": bool(self.vars["record_mouse_move"].get()),
                "record_keyboard":   bool(self.vars["record_keyboard"].get()),
                "mouse_mode":        self.vars["mouse_mode"].get(),
                "actions":           getattr(self, "_rec_actions",
                                             self.node["params"].get("actions", [])),
            }
            self.app._push_history()
            self.node["params"] = p
            self.result = p
            self.destroy()
            self.app.tree_canvas.refresh()
            return

        p = {}
        if t == "action_type":
            p["text"] = self._txt_widget.get("1.0", "end-1c")
        else:
            for key, var in self.vars.items():
                p[key] = var.get()

        # delta est entier (scroll) sauf pour var_add ou il est un flottant
        int_fields = ("x", "y", "r", "g", "b", "count", "tolerance", "ms", "max_iter")
        if t not in ("var_add",):
            int_fields = int_fields + ("delta",)
        for ik in int_fields:
            if ik in p:
                try:
                    p[ik] = int(float(p[ik]))
                except (ValueError, TypeError):
                    p[ik] = 0
        float_fields = ["threshold"]
        if t in ("var_set", "var_add", "condition_var", "loop_while_var"):
            float_fields += ["value", "ref", "delta"]
        for fk in float_fields:
            if fk in p:
                try:
                    p[fk] = float(p[fk])
                except (ValueError, TypeError):
                    p[fk] = 0.0
        # stop_return : conserver la valeur comme chaine "True"/"False"
        if t == "stop_return" and "value" in p:
            p["value"] = str(p["value"])  # ne pas convertir en nombre

        if t in ("condition_screen", "loop_while"):
            p["template_b64"] = self._template_b64
            p["region"]       = self._region

        self.app._push_history()
        self.node["params"] = p
        self.result = p
        self.destroy()
        self.app.tree_canvas.refresh()


# ─────────────────────────────────────────────
#  OVERLAY COORDONNEES
# ─────────────────────────────────────────────
class PickerWindow(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.attributes("-fullscreen", True)
        self.attributes("-alpha", 0.25)
        self.attributes("-topmost", True)
        self.configure(bg="black", cursor="crosshair")
        self.bind("<Button-1>", self._pick)
        self.bind("<Escape>",   lambda e: self._cancel())
        tk.Label(self,
                 text=_t("picker.instruction"),
                 bg="#000000", fg="#ffffff",
                 font=("Segoe UI", 14, "bold")).place(relx=0.5, rely=0.05, anchor="center")
        self._pos_lbl = tk.Label(self, bg="#000000", fg="#89b4fa",
                                  font=("Consolas", 12))
        self._pos_lbl.place(relx=0.5, rely=0.10, anchor="center")
        self.bind("<Motion>",
                  lambda e: self._pos_lbl.configure(text=f"X: {e.x}   Y: {e.y}"))

    def _pick(self, event):
        x, y = event.x, event.y
        self.destroy()
        self.callback(x, y)

    def _cancel(self):
        self.destroy()
        try:
            self.master.deiconify()
        except Exception:
            pass


# ─────────────────────────────────────────────
#  CAPTURE DE REGION
# ─────────────────────────────────────────────
class RegionCaptureWindow(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback    = callback
        self._start      = None
        self._rect       = None
        self._screenshot = ImageGrab.grab() if (PIL_AVAILABLE and ImageGrab) else None

        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.configure(cursor="crosshair")

        self._canvas = tk.Canvas(self, highlightthickness=0, cursor="crosshair")
        self._canvas.pack(fill="both", expand=True)

        if self._screenshot and ImageTk:
            self._bg_photo = ImageTk.PhotoImage(self._screenshot)
            self._canvas.create_image(0, 0, anchor="nw", image=self._bg_photo)
            self._canvas.create_rectangle(
                0, 0, self._screenshot.width, self._screenshot.height,
                fill="black", stipple="gray50", outline="")

        self._canvas.bind("<ButtonPress-1>",   self._on_press)
        self._canvas.bind("<B1-Motion>",        self._on_drag)
        self._canvas.bind("<ButtonRelease-1>",  self._on_release)
        self.bind("<Escape>", lambda e: self._cancel())

        tk.Label(self._canvas,
                 text=_t("capture.region_instruction"),
                 bg="#1e1e2e", fg="#cdd6f4",
                 font=("Segoe UI", 12, "bold"),
                 padx=12, pady=6).place(relx=0.5, rely=0.02, anchor="n")

    def _on_press(self, event):
        self._start = (event.x, event.y)
        if self._rect:
            self._canvas.delete(self._rect)

    def _on_drag(self, event):
        if not self._start:
            return
        if self._rect:
            self._canvas.delete(self._rect)
        x0, y0 = self._start
        self._rect = self._canvas.create_rectangle(
            x0, y0, event.x, event.y,
            outline="#89b4fa", width=2, dash=(4, 2))
        w, h = abs(event.x - x0), abs(event.y - y0)
        self._canvas.delete("sizelbl")
        self._canvas.create_text(
            min(x0, event.x) + w // 2, min(y0, event.y) - 10,
            text=f"{w} x {h}", fill="#f9e2af",
            font=("Consolas", 10, "bold"), tags="sizelbl")

    def _on_release(self, event):
        if not self._start:
            return
        x0, y0 = self._start
        self.destroy()
        if self._screenshot:
            x = min(x0, event.x); y = min(y0, event.y)
            w = abs(event.x - x0); h = abs(event.y - y0)
            if w > 4 and h > 4:
                self.callback(self._screenshot.crop((x, y, x + w, y + h)))
                return
        self.callback(None)

    def _cancel(self):
        self.destroy()
        self.callback(None)
        try:
            self.master.deiconify()
        except Exception:
            pass


# ─────────────────────────────────────────────
#  DIALOGUE D'AJOUT DE NOEUD
# ─────────────────────────────────────────────
class AddNodeDialog(tk.Toplevel):
    def __init__(self, parent, app, target_list, insert_after=None):
        super().__init__(parent)
        self.app          = app
        self.target_list  = target_list
        self.insert_after = insert_after
        self.title(_t("node.add_title"))
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)
        self._build()
        self._center()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(
            f"+{(self.winfo_screenwidth() - w) // 2}"
            f"+{(self.winfo_screenheight() - h) // 2}")

    def _build(self):
        frame = tk.Frame(self, bg=COLORS["bg"], padx=20, pady=16)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=_t("node.add_choose"),
                 bg=COLORS["bg"], fg=COLORS["accent"],
                 font=FONTS["heading"]).pack(anchor="w", pady=(0, 12))

        cats = {}
        for key, info in NODE_TYPES.items():
            cats.setdefault(info["cat"], []).append((key, info))

        for cat, items in cats.items():
            tk.Label(frame, text=cat_label(cat).upper(),
                     bg=COLORS["bg"], fg=COLORS["text_dim"],
                     font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(8, 2))
            row = tk.Frame(frame, bg=COLORS["bg"])
            row.pack(fill="x", pady=2)
            for key, info in items:
                icon = NODE_ICONS.get(key, "")
                lbl  = f"{icon}  {node_label(key)}" if icon else node_label(key)
                tk.Button(row, text=lbl,
                          bg=info["color"], fg=COLORS["text"],
                          font=FONTS["normal"], relief="flat", cursor="hand2",
                          padx=10, pady=8, wraplength=130, justify="left",
                          command=lambda k=key: self._add(k)
                          ).pack(side="left", padx=4, pady=2)

        tk.Button(frame, text=_t("btn.cancel"),
                  bg=COLORS["surface"], fg=COLORS["text"],
                  font=FONTS["normal"], relief="flat", cursor="hand2",
                  padx=16, pady=8,
                  command=self.destroy).pack(pady=(12, 0))

    def _add(self, node_type):
        node = new_node(node_type)
        self.app._push_history()
        if self.insert_after is not None:
            idx = next((i for i, n in enumerate(self.target_list)
                        if n["id"] == self.insert_after), -1)
            if idx >= 0:
                self.target_list.insert(idx + 1, node)
            else:
                self.target_list.append(node)
        else:
            self.target_list.append(node)
        self.destroy()
        self.app.tree_canvas.refresh()
        self.app.edit_node(node)


# ─────────────────────────────────────────────
#  DIALOGUE DE SOUS-CONDITION  (pour condition_group)
# ─────────────────────────────────────────────
class _SubCondDialog(tk.Toplevel):
    """Dialogue pour creer/editer une sous-condition (Variable ou Pixel)."""

    def __init__(self, parent, existing: dict = None, var_names: list = None):
        super().__init__(parent)
        self.result     = None
        self._data      = dict(existing) if existing else {}
        self._svars     = {}
        self._var_names = var_names or []
        self.title(_t("subcond.title"))
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)
        self._build()
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(
            f"+{(self.winfo_screenwidth() - w) // 2}"
            f"+{(self.winfo_screenheight() - h) // 2}")

    def _build(self):
        f = tk.Frame(self, bg=COLORS["bg"], padx=20, pady=16)
        f.pack(fill="both", expand=True)

        tk.Label(f, text=_t("subcond.type"),
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(anchor="w")
        self._type_var = tk.StringVar(value=self._data.get("type", "var"))
        tf = tk.Frame(f, bg=COLORS["bg"])
        tf.pack(fill="x", pady=(0, 10))
        for ctype, clabel in [("var", "Variable"), ("pixel", "Pixel")]:
            tk.Radiobutton(tf, text=clabel, variable=self._type_var, value=ctype,
                           bg=COLORS["bg"], fg=COLORS["text"],
                           selectcolor=COLORS["bg3"],
                           activebackground=COLORS["bg"],
                           font=FONTS["normal"],
                           command=self._refresh_fields).pack(side="left", padx=8)

        self._fields_f = tk.Frame(f, bg=COLORS["bg"])
        self._fields_f.pack(fill="x")
        self._refresh_fields()

        bf = tk.Frame(f, bg=COLORS["bg"])
        bf.pack(fill="x", pady=(14, 0))
        tk.Button(bf, text=_t("btn.confirm"),
                  bg=COLORS["green"], fg=COLORS["bg"],
                  font=FONTS["heading"], relief="flat", cursor="hand2",
                  padx=12, pady=6, command=self._ok).pack(side="right", padx=(8, 0))
        tk.Button(bf, text=_t("btn.cancel"),
                  bg=COLORS["surface"], fg=COLORS["text"],
                  font=FONTS["normal"], relief="flat", cursor="hand2",
                  padx=12, pady=6, command=self.destroy).pack(side="right")

    def _refresh_fields(self):
        for w in self._fields_f.winfo_children():
            w.destroy()
        self._svars = {}
        ctype = self._type_var.get()
        d = self._data
        if ctype == "var":
            self._add_combo("name",  _t("field.var_name"), d.get("name", ""), self._var_names)
            self._add_radio("op",    _t("field.operator"), d.get("op", "=="),
                            ["==", "!=", ">", "<", ">=", "<="])
            self._add_entry("ref",   _t("field.value"),    d.get("ref", 0))
        elif ctype == "pixel":
            self._add_entry("x",         "X",                     d.get("x", 0))
            self._add_entry("y",         "Y",                     d.get("y", 0))
            self._add_entry("r",         _t("field.red"),          d.get("r", 0))
            self._add_entry("g",         _t("field.green"),        d.get("g", 0))
            self._add_entry("b",         _t("field.blue"),         d.get("b", 0))
            self._add_entry("tolerance", _t("field.tolerance"),    d.get("tolerance", 10))

    def _add_entry(self, key, label, default):
        tk.Label(self._fields_f, text=label,
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(anchor="w")
        v = tk.StringVar(value=str(default))
        self._svars[key] = v
        tk.Entry(self._fields_f, textvariable=v,
                 bg=COLORS["bg3"], fg=COLORS["text"],
                 font=FONTS["normal"], insertbackground=COLORS["text"],
                 relief="flat", width=24).pack(fill="x", pady=(0, 6))

    def _add_combo(self, key, label, default, options):
        tk.Label(self._fields_f, text=label,
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(anchor="w")
        v = tk.StringVar(value=str(default))
        self._svars[key] = v
        ttk.Combobox(self._fields_f, textvariable=v,
                     values=options, font=FONTS["normal"],
                     width=24).pack(fill="x", pady=(0, 6))

    def _add_radio(self, key, label, default, options):
        tk.Label(self._fields_f, text=label,
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"]).pack(anchor="w")
        v = tk.StringVar(value=default)
        self._svars[key] = v
        row = tk.Frame(self._fields_f, bg=COLORS["bg"])
        row.pack(fill="x", pady=(0, 6))
        for opt in options:
            tk.Radiobutton(row, text=opt, variable=v, value=opt,
                           bg=COLORS["bg"], fg=COLORS["text"],
                           selectcolor=COLORS["bg3"],
                           activebackground=COLORS["bg"],
                           font=FONTS["normal"]).pack(side="left", padx=4)

    def _ok(self):
        ctype  = self._type_var.get()
        result = {"type": ctype}
        for key, var in self._svars.items():
            result[key] = var.get()
        if ctype == "pixel":
            for k in ("x", "y", "r", "g", "b", "tolerance"):
                try:    result[k] = int(float(result.get(k, 0)))
                except: result[k] = 0
        elif ctype == "var":
            try:    result["ref"] = float(result.get("ref", 0))
            except: result["ref"] = 0.0
        self.result = result
        self.destroy()


# ─────────────────────────────────────────────
#  DIALOGUE DE SELECTION DE LANGUE
# ─────────────────────────────────────────────
class LanguageDialog(tk.Toplevel):
    """Permet a l'utilisateur de choisir la langue de l'interface."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title(_t("lang.title"))
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)
        self._build()
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(
            f"+{(self.winfo_screenwidth() - w) // 2}"
            f"+{(self.winfo_screenheight() - h) // 2}")

    def _build(self):
        from .. import i18n
        from ..settings import load_settings, save_settings as _save

        frame = tk.Frame(self, bg=COLORS["bg"], padx=24, pady=18)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=_t("lang.label"),
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["normal"]).pack(anchor="w", pady=(0, 10))

        langs = i18n.get_available()
        current = i18n.current_lang()
        self._lang_var = tk.StringVar(value=current)

        for code, info in langs.items():
            tk.Radiobutton(
                frame, text=info["name"],
                variable=self._lang_var, value=code,
                bg=COLORS["bg"], fg=COLORS["text"],
                selectcolor=COLORS["bg3"],
                activebackground=COLORS["bg"],
                font=FONTS["normal"],
            ).pack(anchor="w", pady=3)

        tk.Label(frame, text=_t("lang.apply_note"),
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=FONTS["small"], justify="left",
                 wraplength=280).pack(anchor="w", pady=(14, 8))

        bf = tk.Frame(frame, bg=COLORS["bg"])
        bf.pack(fill="x", pady=(4, 0))

        def _apply():
            data = load_settings()
            data["language"] = self._lang_var.get()
            _save(data)
            self.destroy()

        tk.Button(bf, text=_t("btn.apply"),
                  bg=COLORS["accent"], fg=COLORS["bg"],
                  font=FONTS["normal"], relief="flat", cursor="hand2",
                  padx=16, pady=6,
                  command=_apply).pack(side="left", padx=(0, 8))
        tk.Button(bf, text=_t("btn.cancel"),
                  bg=COLORS["surface"], fg=COLORS["text"],
                  font=FONTS["normal"], relief="flat", cursor="hand2",
                  padx=16, pady=6,
                  command=self.destroy).pack(side="left")
