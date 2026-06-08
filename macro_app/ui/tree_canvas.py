"""
macro_app/ui/tree_canvas.py
Widget arbre visuel des noeuds d'une macro.

Classes :
  _ImgTooltip      — fenetre flottante de prévisualisation d'image
  MacroTreeCanvas  — canvas tkinter avec rendu, drag&drop, menus contextuels
"""

import io
import copy
import base64
import tkinter as tk

from ..constants import COLORS, FONTS, NODE_TYPES, NODE_ICONS
from ..utils import PIL_AVAILABLE, Image, ImageTk
from ..models import _node_contains, _remap_ids
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
                 font=FONTS["small"], padx=6, pady=2).pack()
        self._img_lbl = tk.Label(self._win, bg=COLORS["bg3"],
                                  relief="flat", padx=2, pady=2)
        self._img_lbl.pack()
        self._cur_id = None

    def show(self, node_id, b64_data, rx, ry):
        if not PIL_AVAILABLE:
            return
        if self._cur_id == node_id:
            self._win.geometry(f"+{rx + 14}+{ry + 14}")
            return
        try:
            img = Image.open(io.BytesIO(base64.b64decode(b64_data)))
            img.thumbnail((220, 160))
            photo = ImageTk.PhotoImage(img)
            self._img_lbl.configure(image=photo)
            self._img_lbl._photo = photo
            self._cur_id = node_id
            self._win.deiconify()
            self._win.geometry(f"+{rx + 14}+{ry + 14}")
        except Exception:
            pass

    def hide(self):
        self._win.withdraw()
        self._cur_id = None


# ─────────────────────────────────────────────
#  WIDGET ARBRE VISUEL
# ─────────────────────────────────────────────
class MacroTreeCanvas(tk.Canvas):
    NODE_W = 260
    NODE_H = 52
    H_GAP  = 36
    INDENT = 28

    def __init__(self, master, app, **kw):
        super().__init__(master, bg=COLORS["bg2"], highlightthickness=0, **kw)
        self.app         = app
        self.nodes_pos   = {}   # id -> (x, y, node)
        self.branch_zones = []  # (x1, y1, x2, y2, branch_list)
        self._selected   = None

        # Drag & drop
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
        self._tooltip = None   # cree apres que la fenetre est prete

    # ── Rendu ──────────────────────────────────
    def refresh(self):
        self.delete("all")
        self.nodes_pos.clear()
        self.branch_zones.clear()
        macro = self.app.current_macro
        if not macro:
            return
        ROOT_X, ROOT_Y = 30, 20
        y_end = self._draw_nodes(macro["nodes"], ROOT_X, ROOT_Y, depth=0)
        # Zone de dépôt pour la liste racine : permet de déposer en fin de liste
        # même si elle est vide (y_end = ROOT_Y dans ce cas → on garantit une hauteur)
        zone_bottom = max(y_end, ROOT_Y + self.NODE_H * 2)
        self.branch_zones.append(
            (ROOT_X - self.INDENT, ROOT_Y, ROOT_X + self.NODE_W, zone_bottom,
             macro["nodes"])
        )
        bbox = self.bbox("all")
        if bbox:
            self.configure(scrollregion=(
                bbox[0] - 20, bbox[1] - 20,
                bbox[2] + 40, bbox[3] + 40))

    def _draw_nodes(self, nodes, x, y, depth=0,
                    branch_label=None, branch_color=None):
        col = branch_color or COLORS["accent"]

        if branch_label is not None:
            bg_col = self._darken(col, 70)
            lw = max(100, len(branch_label) * 7 + 20)
            self.create_rectangle(x, y, x + lw, y + 20,
                                   fill=bg_col, outline="")
            self.create_text(x + 8, y + 10, text=branch_label, anchor="w",
                             fill=col, font=FONTS["small"])
            y += 26

        prev_bottom = None

        for node in nodes:
            nx, ny = x, y
            self._draw_single_node(node, nx, ny)
            self.nodes_pos[node["id"]] = (nx, ny, node)

            if prev_bottom is not None:
                self._draw_arrow(nx, prev_bottom, nx, ny)

            bottom      = ny + self.NODE_H
            prev_bottom = bottom
            y_after     = ny + self.NODE_H + self.H_GAP
            t = node["type"]

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
                    zone_y = y_after
                    self._draw_branch_cable(nx, bottom, sub_x, y_after + 10, bcol)
                    y_after = self._draw_nodes(
                        bnodes, sub_x, y_after,
                        depth + 1,
                        branch_label=blbl,
                        branch_color=bcol,
                    )
                    y_after = self._draw_add_btn(sub_x, y_after, bnodes, bcol)
                    self.branch_zones.append((sub_x, zone_y, sub_x + self.NODE_W, y_after, bnodes))
                    y_after += self.H_GAP // 2

            elif t == "loop_while":
                children = node.get("children", [[]])
                while len(children) < 1:
                    children.append([])
                node["children"] = children
                sub_x = x + self.INDENT
                bcol  = COLORS["accent2"]
                zone_y = y_after
                self._draw_branch_cable(nx, bottom, sub_x, y_after + 10, bcol)
                y_after = self._draw_nodes(
                    children[0], sub_x, y_after, depth + 1,
                    branch_label=_t("branch.loop_body"),
                    branch_color=bcol,
                )
                y_after = self._draw_add_btn(sub_x, y_after, children[0], bcol)
                self.branch_zones.append((sub_x, zone_y, sub_x + self.NODE_W, y_after, children[0]))
                y_after += self.H_GAP // 2

            elif t == "loop_count":
                children = node.get("children", [[]])
                if not children:
                    children = [[]]
                node["children"] = children
                sub_x = x + self.INDENT
                bcol  = COLORS["accent"]
                zone_y = y_after
                self._draw_branch_cable(nx, bottom, sub_x, y_after + 10, bcol)
                y_after = self._draw_nodes(
                    children[0], sub_x, y_after, depth + 1,
                    branch_label=_t("branch.loop_body"),
                    branch_color=bcol,
                )
                y_after = self._draw_add_btn(sub_x, y_after, children[0], bcol)
                self.branch_zones.append((sub_x, zone_y, sub_x + self.NODE_W, y_after, children[0]))
                y_after += self.H_GAP // 2

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
                    zone_y = y_after
                    self._draw_branch_cable(nx, bottom, sub_x, y_after + 10, bcol)
                    y_after = self._draw_nodes(
                        bnodes, sub_x, y_after,
                        depth + 1,
                        branch_label=blbl,
                        branch_color=bcol,
                    )
                    y_after = self._draw_add_btn(sub_x, y_after, bnodes, bcol)
                    self.branch_zones.append((sub_x, zone_y, sub_x + self.NODE_W, y_after, bnodes))
                    y_after += self.H_GAP // 2

            elif t == "loop_while_var":
                children = node.get("children", [[]])
                if not children:
                    children = [[]]
                node["children"] = children
                sub_x = x + self.INDENT
                bcol  = COLORS["accent2"]
                zone_y = y_after
                self._draw_branch_cable(nx, bottom, sub_x, y_after + 10, bcol)
                y_after = self._draw_nodes(
                    children[0], sub_x, y_after, depth + 1,
                    branch_label=_t("branch.loop_body"),
                    branch_color=bcol,
                )
                y_after = self._draw_add_btn(sub_x, y_after, children[0], bcol)
                self.branch_zones.append((sub_x, zone_y, sub_x + self.NODE_W, y_after, children[0]))
                y_after += self.H_GAP // 2

            y = y_after

        return y

    def _draw_add_btn(self, x, y, branch_list, col):
        """Bouton cliquable en bas de chaque branche."""
        bw, bh = 180, 22
        tag = f"addbtn_{id(branch_list)}"
        r = self.create_rectangle(x, y, x + bw, y + bh,
                                   fill=COLORS["bg3"],
                                   outline=col, dash=(2, 2),
                                   tags=(tag,))
        self.create_text(x + bw // 2, y + bh // 2,
                         text=_t("canvas.add_to_branch"),
                         fill=COLORS["text_dim"],
                         font=("Segoe UI", 8),
                         tags=(tag,))
        self.tag_bind(tag, "<Button-1>",
                      lambda e, bl=branch_list: self.app.add_node_dialog(bl))
        self.tag_bind(tag, "<Enter>",
                      lambda e, r=r: self.itemconfig(r, fill=COLORS["surface"]))
        self.tag_bind(tag, "<Leave>",
                      lambda e, r=r: self.itemconfig(r, fill=COLORS["bg3"]))
        return y + bh + 4

    def _draw_single_node(self, node, x, y):
        ntype    = NODE_TYPES.get(node["type"],
                                  {"label": node["type"], "color": COLORS["surface"]})
        color    = ntype["color"]
        selected = (node["id"] == self._selected)
        is_drag  = (self._drag_node is not None
                    and self._drag_node["id"] == node["id"]
                    and self._drag_moved)

        fill_col   = COLORS["bg3"] if is_drag else color
        border_col = COLORS["accent"] if selected else COLORS["border"]
        border_w   = 2 if selected else 1
        icon       = NODE_ICONS.get(node["type"], "")

        # Ombre
        self.create_rectangle(x + 3, y + 3,
                               x + self.NODE_W + 3, y + self.NODE_H + 3,
                               fill="#000000", outline="", stipple="gray25")
        # Corps
        self.create_rectangle(x, y, x + self.NODE_W, y + self.NODE_H,
                               fill=fill_col,
                               outline=border_col, width=border_w,
                               tags=(f"node_{node['id']}",))
        # Bande gauche
        self.create_rectangle(x, y, x + 5, y + self.NODE_H,
                               fill=COLORS["accent"] if selected
                               else self._lighten(color, 40),
                               outline="")
        # Icone + label
        label_text = f"{icon}  {node_label(node['type'])}" if icon else node_label(node['type'])
        self.create_text(x + 14, y + 15, text=label_text, anchor="w",
                         fill=COLORS["text"] if not is_drag else COLORS["text_dim"],
                         font=FONTS["normal"],
                         tags=(f"node_{node['id']}",))
        # Resume parametres
        summary = self._param_summary(node)
        if summary:
            self.create_text(x + 14, y + 34, text=summary, anchor="w",
                             fill=COLORS["text_dim"], font=FONTS["small"],
                             tags=(f"node_{node['id']}",))
        # ID discret
        self.create_text(x + self.NODE_W - 5, y + 6,
                         text=f"#{node['id']}",
                         anchor="ne", fill=COLORS["text_dim"],
                         font=("Consolas", 7))
        # Commentaire
        if node.get("comment"):
            self.create_text(x + self.NODE_W + 8, y + self.NODE_H // 2,
                             text=f"  {node['comment'][:30]}",
                             anchor="w", fill=COLORS["yellow"], font=FONTS["small"])

    def _lighten(self, hex_color, amount=40):
        try:
            r = min(255, int(hex_color[1:3], 16) + amount)
            g = min(255, int(hex_color[3:5], 16) + amount)
            b = min(255, int(hex_color[5:7], 16) + amount)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    def _darken(self, hex_color, amount=60):
        try:
            r = max(0, int(hex_color[1:3], 16) - amount)
            g = max(0, int(hex_color[3:5], 16) - amount)
            b = max(0, int(hex_color[5:7], 16) - amount)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return COLORS["bg3"]

    def _draw_arrow(self, x1, y1, x2, y2):
        # Départ : flanc bas-gauche du noeud courant
        # Arrivée : milieu du flanc gauche du noeud suivant
        # Route en L sur la marge gauche pour éviter les superpositions
        x_dep  = x1 + 14               # léger décalage depuis le bord gauche
        x_rail = x1 - 12               # couloir vertical à gauche des noeuds
        y_arr  = y2 + self.NODE_H // 2 # milieu vertical du noeud cible
        self.create_line(
            x_dep, y1,
            x_rail, y1,
            x_rail, y_arr,
            x2, y_arr,
            fill=COLORS["text_dim"], width=2,
            arrow=tk.LAST, arrowshape=(8, 10, 4),
            joinstyle=tk.ROUND,
        )

    def _draw_branch_cable(self, nx, y_from, sub_x, y_to, col):
        """Cable de branche : flanc bas-gauche du parent → flanc gauche de la cible.
        Utilise le même couloir gauche que _draw_arrow pour ne pas se superposer.
        """
        x_dep  = nx + 14
        x_rail = nx - 8
        self.create_line(
            x_dep, y_from,
            x_rail, y_from,
            x_rail, y_to,
            sub_x, y_to,
            fill=col, width=1, dash=(3, 3),
            arrow=tk.LAST, arrowshape=(6, 8, 3),
            joinstyle=tk.ROUND,
        )

    def _find_branch_zone_at(self, cx, cy):
        """Retourne la liste de la branche sous le curseur, ou None."""
        for (x1, y1, x2, y2, bl) in self.branch_zones:
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                return bl
        return None

    def _do_drop_to_branch(self, drag_node, target_list):
        """Deplace drag_node à la fin de target_list (branche vide ou zone libre)."""
        # Empêcher de déposer un noeud dans sa propre descendance
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

    def _param_summary(self, node):
        p = node["params"]
        t = node["type"]   # variable locale, PAS la fonction i18n
        if t == "action_click":
            return f"x={p.get('x','?')}  y={p.get('y','?')}  {p.get('button','left')}  x{p.get('count',1)}"
        elif t in ("action_move", "action_scroll"):
            return f"x={p.get('x','?')}  y={p.get('y','?')}"
        elif t == "action_key":
            return _t("summary.keys", keys=p.get("keys", ""))
        elif t == "action_type":
            txt = str(p.get("text", ""))
            short = txt[:28] + "..." if len(txt) > 28 else txt
            return _t("summary.text", text=short)
        elif t == "action_wait":
            return _t("summary.duration", ms=p.get("ms", 1000))
        elif t == "action_run":
            cmd = str(p.get("command", ""))
            short = cmd[:28] + "..." if len(cmd) > 28 else cmd
            return _t("summary.cmd", cmd=short)
        elif t == "action_focus":
            return _t("summary.window", title=p.get("title", ""))
        elif t in ("condition_screen", "loop_while"):
            return _t("summary.capture_ok" if p.get("template_b64") else "summary.capture_nok")
        elif t == "condition_pixel":
            return (f"Pixel ({p.get('x','?')},{p.get('y','?')}) "
                    f"rgb({p.get('r','?')},{p.get('g','?')},{p.get('b','?')})")
        elif t == "loop_count":
            return _t("summary.reps", n=p.get("count", 1))
        elif t == "label":
            return _t("summary.label_name", name=p.get("name", ""))
        elif t == "goto":
            return f"-> {p.get('target', '')}"
        elif t == "var_set":
            return f"{p.get('name', '?')} = {p.get('value', 0)}"
        elif t == "var_add":
            delta = p.get('delta', 0)
            sign = "+" if float(delta) >= 0 else ""
            return f"{p.get('name', '?')} {sign}{delta}"
        elif t == "condition_var":
            return f"{p.get('name', '?')} {p.get('op', '==')} {p.get('ref', 0)}"
        elif t == "loop_while_var":
            return _t("summary.while_var", name=p.get("name", "?"),
                      op=p.get("op", "=="), ref=p.get("ref", 0))
        elif t == "condition_group":
            n = len(p.get("conditions", []))
            logic = p.get("logic", "AND")
            key = "summary.condition_s" if n <= 1 else "summary.condition_pl"
            return _t(key, logic=logic, n=n)
        elif t == "call_macro":
            return f"\u21b3 {p.get('macro_name', '?')}"
        elif t == "stop_return":
            val = p.get("value", "False")
            return _t("summary.return_true") if str(val) == "True" else _t("summary.return_false")
        elif t == "record_replay":
            hotkey = p.get("hotkey", "F6")
            n      = len(p.get("actions", []))
            mode   = p.get("mouse_mode", "absolute")
            return _t("summary.record_replay", hotkey=hotkey, n=n, mode=mode)
        return ""

    def _find_node_at(self, cx, cy):
        for nid, (x, y, node) in self.nodes_pos.items():
            if x <= cx <= x + self.NODE_W and y <= cy <= y + self.NODE_H:
                return node
        return None

    # ── Interactions souris ──────────────────
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

        self.delete("drag_ghost")
        self.create_rectangle(gx, gy, gx + nw, gy + nh,
                               outline=COLORS["accent"], width=2,
                               fill=COLORS["bg3"], dash=(4, 3),
                               tags="drag_ghost")
        ntype = NODE_TYPES.get(self._drag_node["type"], {})
        self.create_text(gx + nw // 2, gy + nh // 2,
                         text=node_label(self._drag_node["type"]),
                         fill=COLORS["accent"], font=FONTS["normal"],
                         tags="drag_ghost")

        # Surligner cible potentielle
        self.delete("drop_highlight")
        target = self._find_node_at(cx, cy)
        if target and target["id"] != self._drag_node["id"]:
            tx, ty, _ = self.nodes_pos[target["id"]]
            self.create_rectangle(tx - 2, ty - 2,
                                   tx + self.NODE_W + 2, ty + self.NODE_H + 2,
                                   outline=COLORS["yellow"], width=2,
                                   tags="drop_highlight")
        elif not target:
            bzone = self._find_branch_zone_at(cx, cy)
            if bzone is not None:
                bz = next((z for z in self.branch_zones if z[4] is bzone), None)
                if bz:
                    self.create_rectangle(bz[0] - 2, bz[1] - 2,
                                           bz[2] + 2, bz[3] + 2,
                                           outline=COLORS["yellow"], width=2,
                                           dash=(4, 3), tags="drop_highlight")

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
        # Empecher de deposer un noeud parent sur l'un de ses descendants
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
            new_idx = len(tgt_list)
        tgt_list.insert(new_idx, drag_node)
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
                       activeforeground=COLORS["bg"])
        if node:
            menu.add_command(label=_t("menu.edit"),
                             command=lambda: self.app.edit_node(node))
            menu.add_command(label=_t("menu.comment"),
                             command=lambda: self.app.edit_comment(node))
            menu.add_separator()
            menu.add_command(label=_t("menu.move_up"),
                             command=lambda: self.app.move_node(node, -1))
            menu.add_command(label=_t("menu.move_down"),
                             command=lambda: self.app.move_node(node, +1))
            menu.add_separator()
            menu.add_command(label=_t("menu.duplicate"),
                             command=lambda: self.app.duplicate_node(node))
            menu.add_command(label=_t("menu.add_after"),
                             command=lambda: self.app.add_node_after(node))
            menu.add_separator()
            # Copier / Coller image (condition_screen et loop_while uniquement)
            has_img = node["type"] in ("condition_screen", "loop_while")
            if has_img:
                menu.add_command(label=_t("menu.copy_image"),
                                 command=lambda: self.app.copy_node_image(node))
                has_clip = bool(getattr(self.app, "_img_clipboard", None))
                paste_state = "normal" if has_clip else "disabled"
                menu.add_command(label=_t("menu.paste_image"),
                                 state=paste_state,
                                 command=lambda: self.app.paste_node_image(node))
                menu.add_separator()
            menu.add_command(label=_t("menu.delete"),
                             command=lambda: self.app.delete_node(node))
        else:
            menu.add_command(label=_t("menu.add_node"),
                             command=self.app.add_node_dialog)
        menu.post(event.x_root, event.y_root)

    def highlight_node(self, node_id):
        self._selected = node_id
        self.refresh()

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
        if node and node["type"] in ("condition_screen", "loop_while"):
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
