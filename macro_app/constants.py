"""
macro_app/constants.py
Toutes les constantes visuelles et de configuration :
couleurs, polices, types de noeuds, icones, VK_MAP.
"""

# ─────────────────────────────────────────────
#  PALETTE DE COULEURS (theme Catppuccin Mocha)
# ─────────────────────────────────────────────
COLORS = {
    "bg":           "#1e1e2e",
    "bg2":          "#181825",
    "bg3":          "#313244",
    "surface":      "#45475a",
    "text":         "#cdd6f4",
    "text_dim":     "#585b70",
    "accent":       "#89b4fa",
    "accent2":      "#cba6f7",
    "green":        "#a6e3a1",
    "red":          "#f38ba8",
    "yellow":       "#f9e2af",
    "orange":       "#fab387",
    "teal":         "#94e2d5",
    "border":       "#313244",
    # Couleurs de fond des noeuds
    "node_action":  "#1e3a5f",
    "node_cond":    "#3a1e5f",
    "node_screen":  "#1e5f3a",
    "node_wait":    "#5f3a1e",
    "node_loop":    "#5f5f1e",
    "node_stop":    "#5f1e1e",
    "node_var":     "#1a3d4f",
    "node_return":   "#5f1e4f",
}

# ─────────────────────────────────────────────
#  POLICES
# ─────────────────────────────────────────────
FONTS = {
    "title":   ("Segoe UI", 16, "bold"),
    "heading": ("Segoe UI", 12, "bold"),
    "normal":  ("Segoe UI", 10),
    "small":   ("Segoe UI", 9),
    "mono":    ("Consolas", 10),
}

# ─────────────────────────────────────────────
#  TYPES DE NOEUDS
#  Chaque entree : label affiché, couleur de fond, categorie
# ─────────────────────────────────────────────
NODE_TYPES = {
    "action_click":     {"label": "Clic souris",        "color": COLORS["node_action"],  "cat": "Action"},
    "action_key":       {"label": "Touche clavier",     "color": COLORS["node_action"],  "cat": "Action"},
    "action_type":      {"label": "Saisir du texte",    "color": COLORS["node_action"],  "cat": "Action"},
    "action_move":      {"label": "Deplacer souris",    "color": COLORS["node_action"],  "cat": "Action"},
    "action_scroll":    {"label": "Scroll souris",      "color": COLORS["node_action"],  "cat": "Action"},
    "action_wait":      {"label": "Attendre",           "color": COLORS["node_wait"],    "cat": "Action"},
    "action_run":       {"label": "Lancer programme",   "color": COLORS["node_action"],  "cat": "Action"},
    "action_focus":     {"label": "Focus fenetre",      "color": COLORS["node_action"],  "cat": "Action"},
    "condition_screen": {"label": "Si ecran contient",  "color": COLORS["node_screen"],  "cat": "Condition"},
    "condition_pixel":  {"label": "Si pixel = couleur", "color": COLORS["node_screen"],  "cat": "Condition"},
    "loop_count":       {"label": "Repeter N fois",     "color": COLORS["node_loop"],    "cat": "Boucle"},
    "loop_while":       {"label": "Tant que",           "color": COLORS["node_loop"],    "cat": "Boucle"},
    "stop":             {"label": "Arreter la macro",   "color": COLORS["node_stop"],    "cat": "Controle"},
    "label":            {"label": "Etiquette",          "color": COLORS["surface"],      "cat": "Controle"},
    "goto":             {"label": "Aller a etiquette",  "color": COLORS["surface"],      "cat": "Controle"},
    "var_set":          {"label": "Definir variable",   "color": COLORS["node_var"],     "cat": "Variable"},
    "var_add":          {"label": "Modifier variable",  "color": COLORS["node_var"],     "cat": "Variable"},
    "condition_var":    {"label": "Si variable",        "color": COLORS["node_cond"],    "cat": "Condition"},
    "loop_while_var":   {"label": "Tant que variable",  "color": COLORS["node_loop"],    "cat": "Boucle"},
    "condition_group":  {"label": "Si AND / OR",        "color": COLORS["node_cond"],    "cat": "Condition"},
    "call_macro":       {"label": "Appeler une macro",  "color": COLORS["node_action"],  "cat": "Controle"},
    "stop_return":       {"label": "Retourner valeur",   "color": COLORS["node_return"],  "cat": "Controle"},
    "record_replay":     {"label": "Enregistrer/Rejouer","color": COLORS["node_action"],  "cat": "Action"},
}

# ─────────────────────────────────────────────
#  ICONES UNICODE PAR TYPE DE NOEUD
# ─────────────────────────────────────────────
NODE_ICONS = {
    "action_click":     "\U0001f5b1",
    "action_key":       "\u2328",
    "action_type":      "\U0001f4dd",
    "action_move":      "\u2192",
    "action_scroll":    "\u21f3",
    "action_wait":      "\u23f1",
    "action_run":       "\u25b6",
    "action_focus":     "\U0001f3af",
    "condition_screen": "\U0001f4f8",
    "condition_pixel":  "\U0001f3a8",
    "loop_count":       "\U0001f501",
    "loop_while":       "\U0001f504",
    "stop":             "\u23f9",
    "label":            "\U0001f3f7",
    "goto":             "\u21a9",
    "var_set":          "\U0001f4be",
    "var_add":          "\u2295",
    "condition_var":    "\U0001f522",
    "loop_while_var":   "\u221e",
    "condition_group":  "\u22c7",
    "call_macro":       "\u21b3",
    "stop_return":       "\u21b5",
    "record_replay":     "\u23fa",
}

# ─────────────────────────────────────────────
#  CODES TOUCHES VIRTUELLES WINDOWS (hotkeys)
# ─────────────────────────────────────────────
VK_MAP = {
    "F1": 0x70, "F2": 0x71, "F3": 0x72,  "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76,  "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
}
