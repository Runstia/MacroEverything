"""
macro_app/ui/panels.py
Panneau lateral de proprietes du noeud selectionne.

Classes :
  PropertiesPanel — panneau tkinter.Frame avec affichage dynamique
"""

import tkinter as tk

from ..constants import COLORS, FONTS, NODE_TYPES, NODE_ICONS
from ..i18n import t, node_label


class PropertiesPanel(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg2"], width=265)
        self.app = app
        self.pack_propagate(False)
        self._build_empty()

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _build_empty(self):
        self._clear()
        tk.Label(self, text=t("props.title"),
                 bg=COLORS["bg2"], fg=COLORS["text_dim"],
                 font=FONTS["heading"]).pack(pady=16)
        tk.Label(self,
                 text=t("props.no_selection"),
                 bg=COLORS["bg2"], fg=COLORS["text_dim"],
                 font=FONTS["small"], justify="center").pack(pady=8)

    def show_node(self, node):
        self._clear()
        p    = node["params"]
        t    = node["type"]
        info = NODE_TYPES.get(t, {})
        icon = NODE_ICONS.get(t, "")

        hdr = tk.Frame(self, bg=info.get("color", COLORS["bg3"]), padx=12, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr,
                 text=f"{icon}  {node_label(t)}",
                 bg=info.get("color", COLORS["bg3"]),
                 fg=COLORS["text"], font=FONTS["heading"]).pack(anchor="w")
        tk.Label(hdr, text=f"ID: {node['id']}",
                 bg=info.get("color", COLORS["bg3"]),
                 fg=COLORS["text_dim"], font=("Consolas", 8)).pack(anchor="w")

        body = tk.Frame(self, bg=COLORS["bg2"], padx=12)
        body.pack(fill="both", expand=True, pady=8)

        for k, v in p.items():
            f = tk.Frame(body, bg=COLORS["bg2"])
            f.pack(fill="x", pady=2)
            tk.Label(f, text=k + ":", bg=COLORS["bg2"],
                     fg=COLORS["text_dim"], font=FONTS["small"],
                     width=12, anchor="w").pack(side="left")
            disp = (t("panel.yes") if k == "template_b64" and v else
                    (t("panel.no") if k == "template_b64" else
                     (str(v)[:24] + "..." if len(str(v)) > 24 else str(v))))
            tk.Label(f, text=disp, bg=COLORS["bg2"], fg=COLORS["text"],
                     font=FONTS["mono"], anchor="w",
                     wraplength=130, justify="left").pack(side="left", fill="x")

        if node.get("comment"):
            tk.Label(body, text=t("panel.comment"),
                     bg=COLORS["bg2"], fg=COLORS["text_dim"],
                     font=FONTS["small"]).pack(anchor="w", pady=(8, 2))
            tk.Label(body, text=node["comment"],
                     bg=COLORS["bg3"], fg=COLORS["yellow"],
                     font=FONTS["small"], wraplength=220,
                     padx=8, pady=6, justify="left").pack(fill="x")

        bf = tk.Frame(self, bg=COLORS["bg2"], padx=12, pady=8)
        bf.pack(fill="x", side="bottom")
        tk.Button(bf, text=t("panel.btn_edit"),
                  bg=COLORS["accent"], fg=COLORS["bg"],
                  font=FONTS["normal"], relief="flat", cursor="hand2",
                  command=lambda: self.app.edit_node(node)).pack(fill="x", pady=2)
        tk.Button(bf, text=t("panel.btn_delete"),
                  bg=COLORS["red"], fg=COLORS["bg"],
                  font=FONTS["normal"], relief="flat", cursor="hand2",
                  command=lambda: self.app.delete_node(node)).pack(fill="x", pady=2)
