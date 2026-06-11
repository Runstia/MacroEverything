"""
macro_app/ui/tree_canvas.py
Widget arbre visuel des noeuds d'une macro.
"""

import io
import base64
import tkinter as tk

from ..constants import COLORS, FONTS, NODE_TYPES, NODE_ICONS
from ..utils import PIL_AVAILABLE, Image, ImageTk
from ..models import _node_contains
from ..i18n import t as _t, node_label


# ─────────────────────────────────────────────
#  TOOLTIP IMAGE SURVOL
# ─────────────────────────────────────────────
class _ImgTooltip:
    def __init__(self, root):
        self._win = tk.Toplevel(root)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.configure(bg=COLORS["bg3"])
        self._win.withdraw()
        tk.Label(self._win, text=_t("canvas.image_ref"),
                 bg=COLORS["bg3"], fg=COLORS["text_dim"],
                 font=FONTS["small"], padx=8, pady=3).pack()
        self._img_lbl = tk.Label(self._win, bg=COLORS["bg3"],
                                  relief="flat", padx=4, pady=4)
        self._img_lbl.pack()
        self._cur_id = None

    def show(self, node_id, b64_data, rx, ry):
        if not PIL_AVAILABLE:
            return
        if self._cur_id == node_id:
            self._win.geometry(f"+{rx + 16}+{ry + 16}")
            return
        try:
            img = Image.open(io.BytesIO(base64.b64decode(b64_data)))
            img.thumbnail((240, 180))
            photo = ImageTk.PhotoImage(img)
            self._img_lbl.configure(image=photo)
            self._img_lbl._photo = photo
            self._cur_id = node_id
            self._win.deiconify()
            self._win.geometry(f"+{rx + 16}+{ry + 16}")
        except Exception:
            pass

    def hide(self):
        self._win.withdraw()
        self._cur_id = None


# ─────────────────────────────────────────────
#  WIDGET ARBRE VISUEL
# ─────────────────────────────────────────────
class MacroTreeCanvas(tk.Canvas):
    NODE_W = 264
    NODE_H = 52
    H_GAP  = 16      # Espace entre noeuds successifs
    INDENT = 36      # Décalage horizontal des sous-branches
    RADIUS = 9       # Rayon des coins arrondis
    RAIL_COLOR = "#2a2a44"   # Couleur du rail séquentiel

    def __init__(self, master, app, **kw):
        super().__init__(master, bg=COLORS["bg2"], highlightthickness=0, **kw)
        self.app          = app
        self.nodes_pos    = {}
        self.branch_zones = []
        self._selected    = None

        self._drag_node   = None
        self._drag_origin = None
        self._drag_moved  = False

        self.bind("<ButtonPress-1>",   self._on_press)
        self.bind("<B1-Motion>",       self._on_drag_motion)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Double-Button-1>", self._on_double)
        self.bind("<Button-3>",        self._on_right_click)
        self.bind("<Configure>",       lambda e: self.refresh())
        self.bind("<Motion>",          self._on_hover)
        self.bind("<Leave>",           lambda e: self._hide_tooltip())
        self._tooltip = None

    # ── Helpers visuels ─────────────────────────
    def _rounded_rect(self, x, y, w, h, r=8, **kw):
        x2, y2 = x + w, y + h
        pts = [
            x + r, y,   x2 - r, y,
            x2, y,      x2, y + r,
            x2, y2 - r, x2, y2,
            x2 - r, y2, x + r, y2,
            x, y2,      x, y2 - r,
            x, y + r,   x, y,
        ]
        return self.create_polygon(pts, smooth=True, **kw)

    def _darken(self, hex_color, amount=72):
        try:
            r = max(0, int(hex_color[1:3], 16) - amount)
            g = max(0, int(hex_color[3:5], 16) - amount)
            b = max(0, int(hex_color[5:7], 16) - amount)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return COLORS["bg3"]

    def _lighten(self, hex_color, amount=50):
        try:
            r = min(255, int(hex_color[1:3], 16) + amount)
            g = min(255, int(hex_color[3:5], 16) + amount)
            b = min(255, int(hex_color[5:7], 16) + amount)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    # ── Rendu principal ─────────────────────────
    def refresh(self):
        self.delete("all")
        self.nodes_pos.clear()
        self.branch_zones.clear()
        macro = self.app.current_macro
        if not macro:
            self._draw_empty_hint()
            return
        ROOT_X, ROOT_Y = 32, 24
        y_end = self._draw_nodes(macro["nodes"], ROOT_X, ROOT_Y, depth=0)
        zone_bottom = max(y_end, ROOT_Y + self.NODE_H * 2)
        self.branch_zones.append(
            (ROOT_X - self.INDENT, ROOT_Y,
             ROOT_X + self.NODE_W, zone_bottom, macro["nodes"])
        )
        bbox = self.bbox("all")
        if bbox:
            self.configure(scrollregion=(
                bbox[0] - 24, bbox[1] - 24,
                bbox[2] + 48, bbox[3] + 48))

    def _draw_empty_hint(self):
        w = self.winfo_width() or 600
        h = self.winfo_height() or 400
        self.create_text(w // 2, h // 2 - 14,
                         text="No macro selected",
                         fill=COLORS["text_dim"],
                         font=FONTS["heading"],
                         anchor="center")

    def _draw_nodes(self, nodes, x, y, depth=0,
                    branch_label=None, branch_color=None):
        col = branch_color or COLORS["accent"]

        if branch_label is not None:
            y = self._draw_branch_header(x, y, branch_label, col)

        prev_y2 = None   # Bas du noeud précédent (pour le rail)

        for node in nodes:
            nx, ny = x, y

            # Rail de flux séquentiel (dessiné avant les noeuds pour rester derrière)
            if prev_y2 is not None:
                self._draw_rail(nx, prev_y2, ny)

            self._draw_single_node(node, nx, ny)
            self.nodes_pos[node["id"]] = (nx, ny, node)

            bottom  = ny + self.NODE_H
            y_after = bottom + self.H_GAP
            prev_y2 = bottom
            t       = node["type"]

            if t in ("condition_screen", "condition_pixel"):
                children = node.get("children", [[], []])
                while len(children) < 2:
                    children.append([])
                node["children"] = children
                sub_x = x + self.INDENT
                for bnodes, blbl, bcol in [
                    (children[0], _t("branch.true"),  COLORS["green"]),
                    (children[1], _t("branch.false"), COLORS["red"]),
                ]:
                    zone_y  = y_after
                    self._draw_branch_cable(nx, bottom, sub_x, y_after, bcol)
                    y_after = self._draw_nodes(bnodes, sub_x, y_after, depth+1,
                                               branch_label=blbl, branch_color=bcol)
                    y_after = self._draw_add_btn(sub_x, y_after, bnodes, bcol)
                    self.branch_zones.append(
                        (sub_x, zone_y, sub_x + self.NODE_W, y_after, bnodes))
                    y_after += self.H_GAP

            elif t in ("loop_while", "loop_count", "loop_while_var"):
                children = node.get("children", [[]])
                if not children:
                    children = [[]]
                node["children"] = children
                sub_x  = x + self.INDENT
                bcol   = COLORS["accent2"]
                zone_y = y_after
                self._draw_branch_cable(nx, bottom, sub_x, y_after, bcol)
                y_after = self._draw_nodes(children[0], sub_x, y_after, depth+1,
                                            branch_label=_t("branch.loop_body"),
                                            branch_color=bcol)
                y_after = self._draw_add_btn(sub_x, y_after, children[0], bcol)
                self.branch_zones.append(
                    (sub_x, zone_y, sub_x + self.NODE_W, y_after, children[0]))
                y_after += self.H_GAP

            elif t == "condition_switch":
                cases    = node["params"].get("cases", [])
                children = node.get("children", [])
                target_n = len(cases) + 1  # +1 pour default
                while len(children) < target_n:
                    children.append([])
                node["children"] = children
                sub_x = x + self.INDENT
                for i, bnodes in enumerate(children[:target_n]):
                    if i < len(cases):
                        blbl = f"= {cases[i]}"
                        bcol = self._case_color(i)
                    else:
                        blbl = _t("branch.default")
                        bcol = COLORS["text_dim"]
                    zone_y  = y_after
                    self._draw_branch_cable(nx, bottom, sub_x, y_after, bcol)
                    y_after = self._draw_nodes(bnodes, sub_x, y_after, depth+1,
                                               branch_label=blbl, branch_color=bcol)
                    y_after = self._draw_add_btn(sub_x, y_after, bnodes, bcol)
                    self.branch_zones.append(
                        (sub_x, zone_y, sub_x + self.NODE_W, y_after, bnodes))
                    y_after += self.H_GAP

            elif t in ("condition_var", "condition_group", "call_macro"):
                children = node.get("children", [[], []])
                while len(children) < 2:
                    children.append([])
                node["children"] = children
                sub_x = x + self.INDENT
                for bnodes, blbl, bcol in [
                    (children[0], _t("branch.true"),  COLORS["green"]),
                    (children[1], _t("branch.false"), COLORS["red"]),
                ]:
                    zone_y  = y_after
                    self._draw_branch_cable(nx, bottom, sub_x, y_after, bcol)
                    y_after = self._draw_nodes(bnodes, sub_x, y_after, depth+1,
                                               branch_label=blbl, branch_color=bcol)
                    y_after = self._draw_add_btn(sub_x, y_after, bnodes, bcol)
                    self.branch_zones.append(
                        (sub_x, zone_y, sub_x + self.NODE_W, y_after, bnodes))
                    y_after += self.H_GAP

            y = y_after

        return y

    # ── Connecteurs ─────────────────────────────
    def _case_color(self, idx):
        palette = [COLORS["accent"], COLORS["teal"], COLORS["orange"],
                   COLORS["accent2"], COLORS["yellow"], COLORS["green"]]
        return palette[idx % len(palette)]

    def _draw_rail(self, x, y_from, y_to):
        """Rail séquentiel vertical discret (dessiné derrière les noeuds)."""
        cx = x + 14
        self.create_line(cx, y_from, cx, y_to,
                         fill=self.RAIL_COLOR, width=1, dash=(2, 4),
                         tags="rail")

    def _draw_branch_header(self, x, y, label, col):
        """Chip de label de branche — fond sombre + texte couleur branche."""
        try:
            r = max(0, int(col[1:3], 16) - 80)
            g = max(0, int(col[3:5], 16) - 80)
            b = max(0, int(col[5:7], 16) - 80)
            bg = f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            bg = COLORS["bg3"]
        chip_h = 20
        chip_w = max(90, len(label) * 7 + 20)
        self.create_rectangle(x, y, x + chip_w, y + chip_h,
                               fill=bg, outline=col, width=1)
        self.create_text(x + 8, y + 10, text=label, anchor="w",
                         fill=col, font=FONTS["tiny"])
        return y + chip_h + 6

    def _draw_branch_cable(self, nx, y_from, sub_x, y_to, col):
        """Câble angulaire vif vers sous-branche (joinstyle MITER, pas de smooth)."""
        x_src  = nx + 14
        x_dst  = sub_x + 14
        bend_y = y_from + 10

        # Vertical court depuis bas du parent
        self.create_line(x_src, y_from, x_src, bend_y,
                         fill=col, width=1,
                         joinstyle=tk.MITER)
        # Horizontal jusqu'à la colonne de la sous-branche
        self.create_line(x_src, bend_y, x_dst, bend_y,
                         fill=col, width=1,
                         joinstyle=tk.MITER)
        # Vertical jusqu'au chip de branche, avec petite flèche
        self.create_line(x_dst, bend_y, x_dst, y_to - 4,
                         fill=col, width=1,
                         arrow=tk.LAST, arrowshape=(5, 7, 2),
                         joinstyle=tk.MITER)

    def _draw_add_btn(self, x, y, branch_list, col):
        """Bouton discret '+ Ajouter ici' au bas de chaque branche."""
        bw, bh = 158, 20
        tag    = f"addbtn_{id(branch_list)}"
        bg_col = COLORS["bg2"]
        r = self.create_rectangle(x, y, x + bw, y + bh,
                                   fill=bg_col, outline=col, width=1,
                                   tags=(tag,))
        self.create_text(x + bw // 2, y + bh // 2,
                         text=_t("canvas.add_to_branch"),
                         fill=COLORS["text_dim"], font=FONTS["tiny"],
                         tags=(tag,))
        self.tag_bind(tag, "<Button-1>",
                      lambda e, bl=branch_list: self.app.add_node_dialog(bl))
        self.tag_bind(tag, "<Enter>",
                      lambda e, _r=r: self.itemconfig(_r, fill=COLORS["bg3"]))
        self.tag_bind(tag, "<Leave>",
                      lambda e, _r=r: self.itemconfig(_r, fill=bg_col))
        return y + bh + 8

    # ── Rendu d'un noeud ────────────────────────
    def _draw_single_node(self, node, x, y):
        ntype    = NODE_TYPES.get(node["type"],
                                  {"label": node["type"], "color": COLORS["surface"]})
        cat_col  = ntype["color"]
        selected = (node["id"] == self._selected)
        is_drag  = (self._drag_node is not None
                    and self._drag_node["id"] == node["id"]
                    and self._drag_moved)

        fill_col   = self._darken(cat_col, 68) if not is_drag else COLORS["bg3"]
        border_col = COLORS["accent"] if selected else "#2c2c40"
        border_w   = 2 if selected else 1
        accent_col = self._lighten(cat_col, 45) if not selected else COLORS["accent"]
        text_col   = COLORS["text_dim"] if is_drag else COLORS["text"]
        icon       = NODE_ICONS.get(node["type"], "")
        tag        = f"node_{node['id']}"

        # Ombre fine (1px décalage)
        self._rounded_rect(x + 1, y + 2, self.NODE_W, self.NODE_H, r=self.RADIUS,
                           fill="#0d0d1a", outline="")

        # Corps du noeud
        self._rounded_rect(x, y, self.NODE_W, self.NODE_H, r=self.RADIUS,
                           fill=fill_col, outline=border_col, width=border_w,
                           tags=(tag,))

        # Accent gauche : ligne épaisse avec capstyle ROUND (fiable, pas de polygon)
        lx = x + 4
        self.create_line(lx, y + self.RADIUS + 2,
                         lx, y + self.NODE_H - self.RADIUS - 2,
                         fill=accent_col, width=4, capstyle=tk.ROUND,
                         tags=(tag,))

        # Icône
        text_x = x + 18
        if icon:
            self.create_text(text_x, y + 15, text=icon, anchor="w",
                             fill=accent_col, font=("Segoe UI", 11),
                             tags=(tag,))
            text_x += 22

        # Label du noeud
        self.create_text(text_x, y + 15, text=node_label(node["type"]),
                         anchor="w", fill=text_col, font=FONTS["normal"],
                         tags=(tag,))

        # Résumé des paramètres
        summary = self._param_summary(node)
        if summary:
            self.create_text(x + 18, y + 37, text=summary, anchor="w",
                             fill=COLORS["text_dim"], font=FONTS["tiny"],
                             tags=(tag,))

        # Commentaire flottant
        if node.get("comment"):
            cm = node["comment"][:28] + ("…" if len(node["comment"]) > 28 else "")
            self.create_text(x + self.NODE_W + 8, y + self.NODE_H // 2,
                             text=f"💬 {cm}", anchor="w",
                             fill=COLORS["yellow"], font=FONTS["tiny"])

    # ── Résumé des paramètres ───────────────────
    def _param_summary(self, node):
        p = node["params"]
        t = node["type"]
        if t == "action_click":
            cnt = p.get("count", 1)
            return (f"({p.get('x','?')}, {p.get('y','?')})  {p.get('button','left')}"
                    + (f"  ×{cnt}" if cnt > 1 else ""))
        if t in ("action_move", "action_scroll"):
            return f"({p.get('x','?')}, {p.get('y','?')})"
        if t == "action_key":
            return _t("summary.keys", keys=p.get("keys", ""))
        if t == "action_type":
            txt = str(p.get("text", ""))
            return _t("summary.text", text=txt[:28] + "…" if len(txt) > 28 else txt)
        if t == "action_wait":
            return _t("summary.duration", ms=p.get("ms", 1000))
        if t == "action_run":
            cmd = str(p.get("command", ""))
            return _t("summary.cmd", cmd=cmd[:28] + "…" if len(cmd) > 28 else cmd)
        if t == "action_focus":
            return _t("summary.window", title=p.get("title", ""))
        if t in ("condition_screen", "loop_while"):
            return _t("summary.capture_ok" if p.get("template_b64") else "summary.capture_nok")
        if t == "action_click_image":
            return _t("summary.click_image_ok" if p.get("template_b64") else "summary.click_image_nok")
        if t == "action_window_layout":
            from ..i18n import t as _ti
            return _t("summary.window_layout",
                      title=p.get("title", "?"),
                      preset=_ti(f"preset.{p.get('preset', 'center')}"))
        if t == "condition_pixel":
            return (f"({p.get('x','?')},{p.get('y','?')})"
                    f"  rgb({p.get('r','?')},{p.get('g','?')},{p.get('b','?')})")
        if t == "loop_count":
            return _t("summary.reps", n=p.get("count", 1))
        if t == "label":
            return _t("summary.label_name", name=p.get("name", ""))
        if t == "goto":
            return f"→ {p.get('target', '')}"
        if t == "var_set":
            return f"{p.get('name', '?')} = {p.get('value', 0)}"
        if t == "var_add":
            d = p.get("delta", 0)
            return f"{p.get('name', '?')} {'+' if float(d) >= 0 else ''}{d}"
        if t == "condition_var":
            return f"{p.get('name', '?')} {p.get('op', '==')} {p.get('ref', 0)}"
        if t == "loop_while_var":
            return _t("summary.while_var", name=p.get("name", "?"),
                      op=p.get("op", "=="), ref=p.get("ref", 0))
        if t == "condition_group":
            n = len(p.get("conditions", []))
            return _t("summary.condition_s" if n <= 1 else "summary.condition_pl",
                      logic=p.get("logic", "AND"), n=n)
        if t == "call_macro":
            return f"↳ {p.get('macro_name', '?')}"
        if t == "stop_return":
            return (_t("summary.return_true") if str(p.get("value", "False")) == "True"
                    else _t("summary.return_false"))
        if t == "record_replay":
            return _t("summary.record_replay", hotkey=p.get("hotkey", "F6"),
                      n=len(p.get("actions", [])), mode=p.get("mouse_mode", "absolute"))
        if t == "condition_switch":
            name = p.get("variable", "?")
            n    = len(p.get("cases", []))
            return _t("summary.switch", var=name, n=n)
        return ""

    # ── Recherche canvas ────────────────────────
    def _find_node_at(self, cx, cy):
        for nid, (x, y, node) in self.nodes_pos.items():
            if x <= cx <= x + self.NODE_W and y <= cy <= y + self.NODE_H:
                return node
        return None

    def _find_branch_zone_at(self, cx, cy):
        for (x1, y1, x2, y2, bl) in self.branch_zones:
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                return bl
        return None

    # ── Interactions souris ────────────────────
    def _on_press(self, event):
        cx, cy = self.canvasx(event.x), self.canvasy(event.y)
        node = self._find_node_at(cx, cy)
        self._drag_node   = node
        self._drag_origin = (cx, cy)
        self._drag_moved  = False
        self._selected    = node["id"] if node else None
        self.refresh()
        if node:
            self.app.select_node(node)

    def _on_drag_motion(self, event):
        if not self._drag_node:
            return
        cx, cy = self.canvasx(event.x), self.canvasy(event.y)
        ox, oy = self._drag_origin
        if abs(cx - ox) < 5 and abs(cy - oy) < 5:
            return

        self._drag_moved = True
        nw, nh = self.NODE_W, self.NODE_H
        gx, gy = cx - nw // 2, cy - nh // 2

        # Fantôme du noeud déplacé
        self.delete("drag_ghost")
        self._rounded_rect(gx, gy, nw, nh, r=self.RADIUS,
                           outline=COLORS["accent"], width=2, dash=(3, 2),
                           fill=COLORS["bg3"], tags="drag_ghost")
        self.create_text(gx + nw // 2, gy + nh // 2,
                         text=node_label(self._drag_node["type"]),
                         fill=COLORS["accent"], font=FONTS["normal"],
                         tags="drag_ghost")

        # Indicateur de zone de drop (ligne d'insertion horizontale)
        self.delete("drop_highlight")
        target = self._find_node_at(cx, cy)
        if target and target["id"] != self._drag_node["id"]:
            tx, ty, _ = self.nodes_pos[target["id"]]
            # Ligne d'insertion sous le noeud cible
            ins_y = ty + nh + self.H_GAP // 2
            self.create_line(tx + 6, ins_y, tx + nw - 6, ins_y,
                             fill=COLORS["accent"], width=2,
                             tags="drop_highlight")
            self.create_oval(tx + 2, ins_y - 3, tx + 10, ins_y + 3,
                             fill=COLORS["accent"], outline="",
                             tags="drop_highlight")
        elif not target:
            bzone = self._find_branch_zone_at(cx, cy)
            if bzone is not None:
                bz = next((z for z in self.branch_zones if z[4] is bzone), None)
                if bz:
                    self.create_rectangle(bz[0] - 2, bz[1] - 2,
                                          bz[2] + 2, bz[3] + 2,
                                          outline=COLORS["yellow"], width=1,
                                          dash=(4, 3), fill="",
                                          tags="drop_highlight")

        # Indicateur toujours derrière les noeuds
        self.tag_lower("drop_highlight")

    def _on_release(self, event):
        self.delete("drag_ghost")
        self.delete("drop_highlight")
        if self._drag_node and self._drag_moved:
            cx, cy = self.canvasx(event.x), self.canvasy(event.y)
            target = self._find_node_at(cx, cy)
            if target and target["id"] != self._drag_node["id"]:
                self._do_drop(self._drag_node, target)
            elif not target:
                branch = self._find_branch_zone_at(cx, cy)
                if branch is not None:
                    self._do_drop_to_branch(self._drag_node, branch)
        self._drag_node  = None
        self._drag_moved = False

    def _do_drop(self, drag_node, target_node):
        if _node_contains(drag_node, target_node["id"]):
            return
        app = self.app
        app._push_history()
        src_list, src_idx = app._find_parent_list(drag_node["id"])
        tgt_list, _       = app._find_parent_list(target_node["id"])
        if src_list is None or tgt_list is None:
            return
        src_list.pop(src_idx)
        try:
            new_idx = tgt_list.index(target_node)
        except ValueError:
            new_idx = len(tgt_list) - 1
        tgt_list.insert(new_idx + 1, drag_node)
        self.refresh()

    def _do_drop_to_branch(self, drag_node, target_list):
        def _owns(node, lst):
            for branch in node.get("children", []):
                if branch is lst:
                    return True
                for child in branch:
                    if _owns(child, lst):
                        return True
            return False
        if _owns(drag_node, target_list):
            return
        app = self.app
        app._push_history()
        src_list, src_idx = app._find_parent_list(drag_node["id"])
        if src_list is None or src_list is target_list:
            return
        src_list.pop(src_idx)
        target_list.append(drag_node)
        self.refresh()

    def _on_double(self, event):
        if self._drag_moved:
            return
        cx, cy = self.canvasx(event.x), self.canvasy(event.y)
        node = self._find_node_at(cx, cy)
        if node:
            self.app.edit_node(node)

    def _on_right_click(self, event):
        cx, cy = self.canvasx(event.x), self.canvasy(event.y)
        node = self._find_node_at(cx, cy)
        menu = tk.Menu(self, tearoff=0,
                       bg=COLORS["bg3"], fg=COLORS["text"],
                       activebackground=COLORS["accent"],
                       activeforeground=COLORS["bg"],
                       relief="flat", bd=0)
        if node:
            menu.add_command(label=f"  {_t('menu.edit')}",
                             command=lambda: self.app.edit_node(node))
            menu.add_command(label=f"  {_t('menu.comment')}",
                             command=lambda: self.app.edit_comment(node))
            menu.add_separator()
            menu.add_command(label=f"  {_t('menu.move_up')}",
                             command=lambda: self.app.move_node(node, -1))
            menu.add_command(label=f"  {_t('menu.move_down')}",
                             command=lambda: self.app.move_node(node, +1))
            menu.add_separator()
            menu.add_command(label=f"  {_t('menu.duplicate')}",
                             command=lambda: self.app.duplicate_node(node))
            menu.add_command(label=f"  {_t('menu.add_after')}",
                             command=lambda: self.app.add_node_after(node))
            menu.add_separator()
            has_img = node["type"] in ("condition_screen", "loop_while",
                                        "action_click_image")
            if has_img:
                menu.add_command(label=f"  {_t('menu.copy_image')}",
                                 command=lambda: self.app.copy_node_image(node))
                has_clip = bool(getattr(self.app, "_img_clipboard", None))
                menu.add_command(label=f"  {_t('menu.paste_image')}",
                                 state="normal" if has_clip else "disabled",
                                 command=lambda: self.app.paste_node_image(node))
                menu.add_separator()
            menu.add_command(label=f"  {_t('menu.delete')}",
                             command=lambda: self.app.delete_node(node))
        else:
            menu.add_command(label=f"  {_t('menu.add_node')}",
                             command=self.app.add_node_dialog)
        menu.post(event.x_root, event.y_root)

    def highlight_node(self, node_id):
        self._selected = node_id
        self.refresh()

    # ── Tooltip image au survol ──────────────────
    def _get_tooltip(self):
        if self._tooltip is None:
            try:
                self._tooltip = _ImgTooltip(self.winfo_toplevel())
            except Exception:
                pass
        return self._tooltip

    def _on_hover(self, event):
        if self._drag_moved:
            return
        cx, cy = self.canvasx(event.x), self.canvasy(event.y)
        node = self._find_node_at(cx, cy)
        img_types = ("condition_screen", "loop_while", "action_click_image")
        if node and node["type"] in img_types:
            b64 = node["params"].get("template_b64", "")
            if b64:
                tip = self._get_tooltip()
                if tip:
                    tip.show(node["id"], b64, event.x_root, event.y_root)
                return
        self._hide_tooltip()

    def _hide_tooltip(self):
        if self._tooltip:
            self._tooltip.hide()
