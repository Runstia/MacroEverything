"""
macro_app/constants.py
Toutes les constantes visuelles et de configuration :
couleurs, polices, types de noeuds, icones, VK_MAP.
"""

APP_VERSION = "1.3.0"

# ─────────────────────────────────────────────
#  PALETTE DE COULEURS (theme Catppuccin Mocha)
# ─────────────────────────────────────────────
COLORS = {
    "bg":           "#1e1e2e",
    "bg2":          "#181825",
    "bg3":          "#313244",
    "surface":      "#45475a",
    "text":         "#cdd6f4",
    "text_dim":     "#6c7086",
    "accent":       "#89b4fa",
    "accent2":      "#cba6f7",
    "green":        "#a6e3a1",
    "red":          "#f38ba8",
    "yellow":       "#f9e2af",
    "orange":       "#fab387",
    "teal":         "#94e2d5",
    "border":       "#45475a",
    "shadow":       "#11111b",
    # Couleurs de fond des noeuds par categorie
    "node_mouse":   "#1a3050",
    "node_kbd":     "#1e2d4e",
    "node_sys":     "#2a1f50",
    "node_cond":    "#3a1e5f",
    "node_screen":  "#1e5f3a",
    "node_wait":    "#4a3010",
    "node_loop":    "#3a3a10",
    "node_stop":    "#5f1e1e",
    "node_var":     "#1a3d4f",
    "node_return":  "#5f1e4f",
    # Alias pour compat
    "node_action":  "#1a3050",
}

# ─────────────────────────────────────────────
#  POLICES
# ─────────────────────────────────────────────
FONTS = {
    "title":   ("Segoe UI", 15, "bold"),
    "heading": ("Segoe UI", 11, "bold"),
    "normal":  ("Segoe UI", 10),
    "small":   ("Segoe UI", 9),
    "tiny":    ("Segoe UI", 8),
    "mono":    ("Consolas", 10),
}

# ─────────────────────────────────────────────
#  TYPES DE NOEUDS
#  Chaque entree : label (fallback anglais), couleur, categorie
#  Les labels traduits sont dans locales/{lang}.json (node.{key}.label)
# ─────────────────────────────────────────────
NODE_TYPES = {
    # ── Souris ────────────────────────────────
    "action_click":        {"label": "Mouse click",        "color": COLORS["node_mouse"],  "cat": "Mouse"},
    "action_move":         {"label": "Move mouse",         "color": COLORS["node_mouse"],  "cat": "Mouse"},
    "action_scroll":       {"label": "Mouse scroll",       "color": COLORS["node_mouse"],  "cat": "Mouse"},
    "action_click_image":  {"label": "Click on image",     "color": COLORS["node_screen"], "cat": "Mouse"},
    # ── Clavier ───────────────────────────────
    "action_key":          {"label": "Keyboard key",       "color": COLORS["node_kbd"],    "cat": "Keyboard"},
    "action_type":         {"label": "Type text",          "color": COLORS["node_kbd"],    "cat": "Keyboard"},
    # ── Systeme ───────────────────────────────
    "action_wait":         {"label": "Wait",               "color": COLORS["node_wait"],   "cat": "System"},
    "action_run":          {"label": "Run program",        "color": COLORS["node_sys"],    "cat": "System"},
    "action_focus":        {"label": "Focus window",       "color": COLORS["node_sys"],    "cat": "System"},
    "action_window_layout":{"label": "Window layout",      "color": COLORS["node_sys"],    "cat": "System"},
    "record_replay":       {"label": "Record & Replay",    "color": COLORS["node_sys"],    "cat": "System"},
    # ── Conditions ────────────────────────────
    "condition_screen":    {"label": "If screen contains", "color": COLORS["node_screen"], "cat": "Condition"},
    "condition_pixel":     {"label": "If pixel = color",   "color": COLORS["node_screen"], "cat": "Condition"},
    "condition_var":       {"label": "If variable",        "color": COLORS["node_cond"],   "cat": "Condition"},
    "condition_group":     {"label": "If AND / OR",        "color": COLORS["node_cond"],   "cat": "Condition"},
    "condition_switch":    {"label": "Switch variable",    "color": COLORS["node_cond"],   "cat": "Condition"},
    # ── Boucles ───────────────────────────────
    "loop_count":          {"label": "Repeat N times",     "color": COLORS["node_loop"],   "cat": "Loop"},
    "loop_while":          {"label": "While screen",       "color": COLORS["node_loop"],   "cat": "Loop"},
    "loop_while_var":      {"label": "While variable",     "color": COLORS["node_loop"],   "cat": "Loop"},
    # ── Variables ─────────────────────────────
    "var_set":             {"label": "Set variable",       "color": COLORS["node_var"],    "cat": "Variable"},
    "var_add":             {"label": "Modify variable",    "color": COLORS["node_var"],    "cat": "Variable"},
    # ── Flux de controle ──────────────────────
    "label":               {"label": "Label",              "color": COLORS["surface"],     "cat": "Flow"},
    "goto":                {"label": "Go to label",        "color": COLORS["surface"],     "cat": "Flow"},
    "call_macro":          {"label": "Call macro",         "color": COLORS["node_sys"],    "cat": "Flow"},
    "stop":                {"label": "Stop macro",         "color": COLORS["node_stop"],   "cat": "Flow"},
    "stop_return":         {"label": "Return value",       "color": COLORS["node_return"], "cat": "Flow"},
}

# Ordre d'affichage des categories dans AddNodeDialog
NODE_CAT_ORDER = ["Mouse", "Keyboard", "System", "Condition", "Loop", "Variable", "Flow"]

# ─────────────────────────────────────────────
#  ICONES UNICODE PAR TYPE DE NOEUD
# ─────────────────────────────────────────────
NODE_ICONS = {
    "action_click":        "\U0001f5b1",
    "action_key":          "⌨",
    "action_type":         "\U0001f4dd",
    "action_move":         "→",
    "action_scroll":       "⇳",
    "action_wait":         "⏱",
    "action_run":          "▶",
    "action_focus":        "\U0001f3af",
    "action_click_image":  "\U0001f50d",
    "action_window_layout":"❖",
    "condition_screen":    "\U0001f4f8",
    "condition_pixel":     "\U0001f3a8",
    "loop_count":          "\U0001f501",
    "loop_while":          "\U0001f504",
    "stop":                "⏹",
    "label":               "\U0001f3f7",
    "goto":                "↩",
    "var_set":             "\U0001f4be",
    "var_add":             "⊕",
    "condition_var":       "\U0001f522",
    "loop_while_var":      "∞",
    "condition_group":     "⋇",
    "condition_switch":    "⊟",
    "call_macro":          "↳",
    "stop_return":         "↵",
    "record_replay":       "⏺",
}

# ─────────────────────────────────────────────
#  CODES TOUCHES VIRTUELLES WINDOWS (hotkeys)
# ─────────────────────────────────────────────
VK_MAP = {
    "F1": 0x70, "F2": 0x71, "F3": 0x72,  "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76,  "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
}
