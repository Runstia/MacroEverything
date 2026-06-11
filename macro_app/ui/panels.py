"""
macro_app/ui/panels.py
Panneau lateral de proprietes du noeud selectionne.
"""

import tkinter as tk
from tkinter import ttk

from ..constants import COLORS, FONTS, NODE_TYPES, NODE_ICONS
from ..i18n import t as _t, node_label
from ..utils import PIL_AVAILABLE, Image, ImageTk


def _bind_hover(btn, normal, hover):
    def _enter(e):
        if str(btn["state"]) != "disabled":
            btn.configure(bg=hover)
    btn.bind("<Enter>", _enter)
    btn.bind("<Leave>", lambda e: btn.configure(bg=normal))


# ─────────────────────────────────────────────
#  OVERLAYS ÉCRAN
# ─────────────────────────────────────────────
class _CoordOverlay(tk.Toplevel):
    """Viseur flottant centré sur la position réelle de l'action."""
    _TRANS = "#010101"

    def __init__(self, root, real_x: int, real_y: int, color: str, label: str = ""):
        super().__init__(root)
        SIZE = 120
        GAP  = 10
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=self._TRANS)
        self.attributes("-transparentcolor", self._TRANS)
        self.geometry(f"{SIZE}x{SIZE}+{real_x - SIZE // 2}+{real_y - SIZE // 2}")
        cvs = tk.Canvas(self, bg=self._TRANS, width=SIZE, height=SIZE,
                        highlightthickness=0, bd=0)
        cvs.pack(fill="both", expand=True)
        cx = cy = SIZE // 2
        for x0, y0, x1, y1 in [(0, cy, cx-GAP, cy), (cx+GAP, cy, SIZE, cy),
                                 (cx, 0, cx, cy-GAP), (cx, cy+GAP, cx, SIZE)]:
            cvs.create_line(x0, y0, x1, y1, fill=color, width=2)
        r = 3
        cvs.create_oval(cx-r, cy-r, cx+r, cy+r, fill=color, outline=self._TRANS)
        if label:
            cvs.create_text(cx, SIZE - 4, text=label,
                            anchor="s", fill=color, font=("Consolas", 8))
        self.bind("<Button-1>", lambda e: self.destroy())
        self.bind("<Escape>",   lambda e: self.destroy())


class _RegionOverlay(tk.Toplevel):
    """Rectangle flottant délimitant la zone de recherche d'image."""
    _TRANS = "#010101"

    def __init__(self, root, x1: int, y1: int, x2: int, y2: int, color: str):
        super().__init__(root)
        w = max(10, x2 - x1)
        h = max(10, y2 - y1)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=self._TRANS)
        self.attributes("-transparentcolor", self._TRANS)
        self.geometry(f"{w}x{h}+{x1}+{y1}")
        cvs = tk.Canvas(self, bg=self._TRANS, width=w, height=h,
                        highlightthickness=0, bd=0)
        cvs.pack(fill="both", expand=True)
        cvs.create_rectangle(1, 1, w-2, h-2,
                              outline=color, width=2, fill=self._TRANS)
        cvs.create_text(5, 5, text=f"{w}×{h}  ({x1},{y1})",
                        anchor="nw", fill=color, font=("Consolas", 8, "bold"))
        self.bind("<Button-1>", lambda e: self.destroy())
        self.bind("<Escape>",   lambda e: self.destroy())


class PropertiesPanel(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg2"], width=270)
        self.app = app
        self.pack_propagate(False)
        self._overlay_win = None

        # ── Sous-header persistant (42px, aligné sidebar + canvas) ──
        self._hdr_bar = tk.Frame(self, bg=COLORS["bg3"], height=42)
        self._hdr_bar.pack(fill="x")
        self._hdr_bar.pack_propagate(False)
        tk.Label(self._hdr_bar, text=_t("props.title"),
                 bg=COLORS["bg3"], fg=COLORS["text"],
                 font=FONTS["heading"]).pack(side="left", padx=12)
        tk.Frame(self, bg=COLORS["border"], height=1).pack(fill="x")

        # ── Zone de contenu (reconstruite à chaque sélection) ───────
        self._body = tk.Frame(self, bg=COLORS["bg2"])
        self._body.pack(fill="both", expand=True)

        self._build_empty()

    def _destroy_overlay(self):
        if self._overlay_win:
            try:
                self._overlay_win.destroy()
            except Exception:
                pass
            self._overlay_win = None

    def _clear(self):
        self._destroy_overlay()
        for w in self._body.winfo_children():
            w.destroy()

    def _build_empty(self):
        self._clear()
        wrap = tk.Frame(self._body, bg=COLORS["bg2"])
        wrap.place(relx=0.5, rely=0.42, anchor="center")
        tk.Label(wrap, text=_t("props.no_selection"),
                 bg=COLORS["bg2"], fg=COLORS["text_dim"],
                 font=FONTS["small"], justify="center").pack()

    def show_node(self, node):
        self._clear()
        p     = node["params"]
        ntype = node["type"]
        info  = NODE_TYPES.get(ntype, {})
        icon  = NODE_ICONS.get(ntype, "")
        col   = info.get("color", COLORS["bg3"])

        # ── Boutons action (packed en side=bottom en premier) ────
        bf = tk.Frame(self._body, bg=COLORS["bg2"], padx=12, pady=10)
        bf.pack(fill="x", side="bottom")
        tk.Frame(bf, bg=COLORS["border"], height=1).pack(fill="x", pady=(0, 8))
        edit_btn = tk.Button(bf, text=_t("panel.btn_edit"),
                             bg=COLORS["accent"], fg=COLORS["bg"],
                             font=FONTS["normal"], relief="flat", cursor="hand2",
                             pady=7,
                             command=lambda: self.app.edit_node(node))
        edit_btn.pack(fill="x", pady=(0, 4))
        _bind_hover(edit_btn, COLORS["accent"], "#74c7ec")
        del_btn = tk.Button(bf, text=_t("panel.btn_delete"),
                            bg=COLORS["bg3"], fg=COLORS["red"],
                            font=FONTS["normal"], relief="flat", cursor="hand2",
                            pady=7,
                            command=lambda: self.app.delete_node(node))
        del_btn.pack(fill="x")
        _bind_hover(del_btn, COLORS["bg3"], COLORS["surface"])

        # ── Header coloré du nœud ────────────────────────
        hdr = tk.Frame(self._body, bg=col, padx=14, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"{icon}  {node_label(ntype)}",
                 bg=col, fg=COLORS["text"],
                 font=FONTS["heading"]).pack(anchor="w")
        tk.Label(hdr, text=ntype,
                 bg=col, fg=COLORS["text_dim"],
                 font=FONTS["tiny"]).pack(anchor="w", pady=(3, 0))

        tk.Frame(self._body, bg=COLORS["border"], height=1).pack(fill="x")

        # ── Scrollable params body ───────────────────────
        outer = tk.Frame(self._body, bg=COLORS["bg2"])
        outer.pack(fill="both", expand=True)

        sc = tk.Canvas(outer, bg=COLORS["bg2"],
                       highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=sc.yview)
        sc.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        sc.pack(side="left", fill="both", expand=True)

        body = tk.Frame(sc, bg=COLORS["bg2"], padx=14)
        win_id = sc.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda e: sc.configure(scrollregion=sc.bbox("all")))
        sc.bind("<Configure>",
                lambda e: sc.itemconfig(win_id, width=e.width))
        sc.bind("<MouseWheel>",
                lambda e: sc.yview_scroll(-1 * (e.delta // 120), "units"))

        tk.Frame(body, bg=COLORS["bg2"], height=10).pack()

        # ── Prévisualisations ────────────────────────────
        _COORD_NODES = ("action_click", "action_move", "action_scroll", "condition_pixel")
        _IMAGE_NODES = ("condition_screen", "loop_while", "action_click_image")

        skip_keys: set = set()

        if ntype in _COORD_NODES:
            self._build_coord_preview(body, p, ntype)
            self._add_overlay_btn(body, lambda: self._create_coord_overlay(p, ntype))
        elif ntype in _IMAGE_NODES:
            self._build_image_preview(body, p)
            skip_keys = {"template_b64", "region"}

        # ── Paramètres ───────────────────────────────────
        for k, v in p.items():
            if k in skip_keys:
                continue

            row = tk.Frame(body, bg=COLORS["bg2"])
            row.pack(fill="x", pady=(0, 8))

            if k == "template_b64":
                has_img = bool(v)
                tk.Label(row, text="capture",
                         bg=COLORS["bg2"], fg=COLORS["text_dim"],
                         font=FONTS["tiny"]).pack(anchor="w")
                tk.Label(row,
                         text="✔  captured" if has_img else "✘  not set",
                         bg=COLORS["node_screen"] if has_img else COLORS["bg3"],
                         fg=COLORS["green"] if has_img else COLORS["text_dim"],
                         font=FONTS["small"], padx=8, pady=3).pack(anchor="w")
                continue

            tk.Label(row, text=k,
                     bg=COLORS["bg2"], fg=COLORS["text_dim"],
                     font=FONTS["tiny"]).pack(anchor="w")

            if isinstance(v, bool):
                val_txt = "✔  Yes" if v else "—  No"
                val_fg  = COLORS["green"] if v else COLORS["text_dim"]
            else:
                s       = str(v)
                val_txt = (s[:40] + "…") if len(s) > 40 else s
                val_fg  = COLORS["text"]

            tk.Label(row, text=val_txt,
                     bg=COLORS["bg2"], fg=val_fg,
                     font=FONTS["normal"], anchor="w",
                     wraplength=210, justify="left").pack(anchor="w", fill="x")

        # ── Zone de recherche (nœuds image) ─────────────
        if ntype in _IMAGE_NODES:
            region = p.get("region")
            row = tk.Frame(body, bg=COLORS["bg2"])
            row.pack(fill="x", pady=(0, 4))
            tk.Label(row, text=_t("region.label"),
                     bg=COLORS["bg2"], fg=COLORS["text_dim"],
                     font=FONTS["tiny"]).pack(anchor="w")
            if region:
                x1, y1, x2, y2 = (int(region[0]), int(region[1]),
                                   int(region[2]), int(region[3]))
                w, h = x2 - x1, y2 - y1
                txt = f"{x1},{y1}  →  {w}×{h} px"
                fg  = COLORS["teal"]
            else:
                txt = _t("region.none")
                fg  = COLORS["text_dim"]
            tk.Label(row, text=txt, bg=COLORS["bg2"], fg=fg,
                     font=FONTS["small"]).pack(anchor="w")
            if region:
                self._add_overlay_btn(
                    body, lambda r=region: self._create_region_overlay(r))

        if node.get("comment"):
            tk.Frame(body, bg=COLORS["border"], height=1).pack(fill="x", pady=(0, 8))
            tk.Label(body, text=_t("panel.comment"),
                     bg=COLORS["bg2"], fg=COLORS["text_dim"],
                     font=FONTS["tiny"]).pack(anchor="w")
            tk.Label(body, text=node["comment"],
                     bg=COLORS["bg3"], fg=COLORS["yellow"],
                     font=FONTS["small"], wraplength=220,
                     padx=10, pady=6, justify="left").pack(fill="x", pady=(2, 0))

        tk.Frame(body, bg=COLORS["bg2"], height=10).pack()

    # ── Helpers de prévisualisation ──────────────────
    def _build_coord_preview(self, body, params, ntype):
        """Canvas minimap — crosshair à la position (x, y) dans la résolution de référence."""
        x = int(params.get("x", 0))
        y = int(params.get("y", 0))
        macro = self.app.current_macro
        ref_w = int(macro.get("res_w", 0)) or 1920
        ref_h = int(macro.get("res_h", 0)) or 1080

        CW, CH = 232, 130
        cvs = tk.Canvas(body, bg=COLORS["bg"], width=CW, height=CH,
                        highlightthickness=1, highlightbackground=COLORS["border"],
                        bd=0)
        cvs.pack(fill="x", pady=(0, 12))

        # Grille en tiers
        for i in [1, 2]:
            gx = CW * i // 3
            gy = CH * i // 3
            cvs.create_line(gx, 0, gx, CH, fill=COLORS["bg3"], width=1)
            cvs.create_line(0, gy, CW, gy, fill=COLORS["bg3"], width=1)

        cx = max(4, min(CW - 4, int(x * CW / ref_w)))
        cy = max(4, min(CH - 4, int(y * CH / ref_h)))

        if ntype == "action_scroll":
            dot_col = COLORS["teal"]
        elif ntype == "condition_pixel":
            dot_col = COLORS["accent2"]
        else:
            dot_col = COLORS["accent"]

        cvs.create_line(cx, 0,  cx, CH,  fill=dot_col, width=1, dash=(4, 4))
        cvs.create_line(0,  cy, CW, cy,  fill=dot_col, width=1, dash=(4, 4))
        r = 5
        cvs.create_oval(cx - r, cy - r, cx + r, cy + r,
                        fill=dot_col, outline=COLORS["text"], width=1)
        cvs.create_text(CW - 4, CH - 4, text=f"({x}, {y})",
                        anchor="se", fill=COLORS["text_dim"], font=FONTS["tiny"])
        cvs.create_text(4, CH - 4, text=f"{ref_w}×{ref_h}",
                        anchor="sw", fill=COLORS["text_dim"], font=FONTS["tiny"])

        if ntype == "action_scroll":
            delta = int(params.get("delta", 3))
            arrow = "▲" if delta >= 0 else "▼"
            cvs.create_text(cx + 8, cy - 8,
                            text=f"{arrow}{abs(delta)}",
                            anchor="sw", fill=COLORS["teal"], font=FONTS["small"])

        if ntype == "condition_pixel":
            rv = max(0, min(255, int(params.get("r", 0))))
            gv = max(0, min(255, int(params.get("g", 0))))
            bv = max(0, min(255, int(params.get("b", 0))))
            hex_col = f"#{rv:02x}{gv:02x}{bv:02x}"
            cvs.create_rectangle(4, CH - 22, 38, CH - 4,
                                  fill=hex_col, outline=COLORS["border"], width=1)
            cvs.create_text(42, CH - 4, anchor="sw",
                            text=f"rgb({rv},{gv},{bv})",
                            fill=COLORS["text_dim"], font=FONTS["tiny"])

    def _build_image_preview(self, body, params):
        """Thumbnail PIL de template_b64, avec chip de secours si PIL absent."""
        template_b64 = params.get("template_b64", "")
        if template_b64 and PIL_AVAILABLE and Image and ImageTk:
            try:
                import io, base64 as _b64
                img = Image.open(io.BytesIO(_b64.b64decode(template_b64)))
                orig_w, orig_h = img.size
                img.thumbnail((232, 100))
                photo = ImageTk.PhotoImage(img)
                frm = tk.Frame(body, bg=COLORS["bg3"])
                frm.pack(fill="x", pady=(0, 2))
                lbl = tk.Label(frm, image=photo, bg=COLORS["bg3"])
                lbl._photo = photo
                lbl.pack()
                tk.Label(body, text=f"{orig_w}×{orig_h} px",
                         bg=COLORS["bg2"], fg=COLORS["text_dim"],
                         font=FONTS["tiny"]).pack(anchor="w", pady=(0, 8))
                return
            except Exception:
                pass
        # Chip de secours
        row = tk.Frame(body, bg=COLORS["bg2"])
        row.pack(fill="x", pady=(0, 8))
        tk.Label(row, text="capture",
                 bg=COLORS["bg2"], fg=COLORS["text_dim"],
                 font=FONTS["tiny"]).pack(anchor="w")
        has = bool(template_b64)
        tk.Label(row,
                 text="✔  captured" if has else "✘  not set",
                 bg=COLORS["node_screen"] if has else COLORS["bg3"],
                 fg=COLORS["green"] if has else COLORS["text_dim"],
                 font=FONTS["small"], padx=8, pady=3).pack(anchor="w")

    # ── Helpers overlay écran ─────────────────────────
    @staticmethod
    def _compute_scale(macro) -> tuple:
        """Retourne (sx, sy) : facteurs macro-résolution → résolution actuelle."""
        try:
            import ctypes
            rec_w = int(macro.get("res_w", 0))
            rec_h = int(macro.get("res_h", 0))
            if rec_w > 0 and rec_h > 0:
                cur_w = ctypes.windll.user32.GetSystemMetrics(78)
                cur_h = ctypes.windll.user32.GetSystemMetrics(79)
                if cur_w > 0 and cur_h > 0:
                    return cur_w / rec_w, cur_h / rec_h
        except Exception:
            pass
        return 1.0, 1.0

    def _create_coord_overlay(self, params, ntype):
        sx, sy = self._compute_scale(self.app.current_macro)
        x = int(params.get("x", 0))
        y = int(params.get("y", 0))
        real_x = round(x * sx)
        real_y = round(y * sy)
        color = (COLORS["teal"]    if ntype == "action_scroll"   else
                 COLORS["accent2"] if ntype == "condition_pixel" else
                 COLORS["accent"])
        scale_note = f"  ×{sx:.2g}" if sx != 1.0 else ""
        label = f"({real_x}, {real_y}){scale_note}"
        try:
            return _CoordOverlay(self.winfo_toplevel(), real_x, real_y, color, label)
        except Exception:
            return None

    def _create_region_overlay(self, region):
        if not region:
            return None
        sx, sy = self._compute_scale(self.app.current_macro)
        x1 = round(int(region[0]) * sx)
        y1 = round(int(region[1]) * sy)
        x2 = round(int(region[2]) * sx)
        y2 = round(int(region[3]) * sy)
        try:
            return _RegionOverlay(self.winfo_toplevel(),
                                  x1, y1, x2, y2, COLORS["teal"])
        except Exception:
            return None

    def _add_overlay_btn(self, body, create_fn):
        """Bouton toggle pour afficher/masquer l'overlay écran."""
        btn_ref = [None]

        def _toggle():
            if self._overlay_win and self._overlay_win.winfo_exists():
                self._destroy_overlay()
                btn_ref[0].configure(text=_t("panel.overlay_show"),
                                     fg=COLORS["text_dim"])
            else:
                self._destroy_overlay()
                ov = create_fn()
                self._overlay_win = ov
                if ov:
                    btn_ref[0].configure(text=_t("panel.overlay_hide"),
                                         fg=COLORS["accent"])

        btn = tk.Button(body, text=_t("panel.overlay_show"),
                        bg=COLORS["bg3"], fg=COLORS["text_dim"],
                        font=FONTS["tiny"], relief="flat", cursor="hand2",
                        padx=6, pady=2, command=_toggle)
        btn.pack(anchor="w", pady=(0, 10))
        btn_ref[0] = btn
