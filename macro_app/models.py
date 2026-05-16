"""
macro_app/models.py
Modele de donnees : creation de noeuds et de macros,
et fonctions utilitaires sur l'arbre de noeuds.
"""

import uuid
import copy


# ─────────────────────────────────────────────
#  CREATION DE NOEUDS / MACROS
# ─────────────────────────────────────────────
def new_node(node_type: str, params: dict = None) -> dict:
    """Cree un noeud avec les valeurs par defaut selon son type."""
    node = {
        "id":       str(uuid.uuid4())[:8],
        "type":     node_type,
        "params":   params or {},
        "children": [],
        "comment":  "",
    }
    # Les noeuds a deux branches (Si VRAI / Si FAUX)
    if node_type in ("condition_screen", "condition_pixel", "loop_while",
                     "condition_var", "condition_group", "call_macro"):
        node["children"] = [[], []]
    # Noeuds a une seule branche (corps de boucle)
    elif node_type in ("loop_count", "loop_while_var"):
        node["children"] = [[]]
    return node


def new_macro() -> dict:
    """Cree une macro vide avec valeurs par defaut."""
    return {
        "name":  "Nouvelle macro",
        "loop":  False,
        "nodes": [],
        "res_w": 0,
        "res_h": 0,
    }


# ─────────────────────────────────────────────
#  UTILITAIRES SUR L'ARBRE DE NOEUDS
# ─────────────────────────────────────────────
def _remap_ids(nodes: list) -> None:
    """Regenere des IDs uniques pour tous les noeuds (apres un deepcopy)."""
    for n in nodes:
        n["id"] = str(uuid.uuid4())[:8]
        for branch in n.get("children", []):
            _remap_ids(branch)


def _collect_labels(macro: dict) -> list:
    """Retourne la liste des noms d'etiquettes definies dans la macro."""
    labels = []

    def _scan(nodes):
        for n in nodes:
            if n["type"] == "label":
                name = n["params"].get("name", "").strip()
                if name and name not in labels:
                    labels.append(name)
            for branch in n.get("children", []):
                _scan(branch)

    if macro:
        _scan(macro.get("nodes", []))
    return labels


def _collect_var_names(nodes: list) -> list:
    """Retourne la liste des noms de variables definis dans l'arbre de noeuds."""
    names = []

    def _scan(ns):
        for n in ns:
            if n["type"] in ("var_set", "var_add"):
                name = n["params"].get("name", "").strip()
                if name and name not in names:
                    names.append(name)
            for branch in n.get("children", []):
                _scan(branch)

    _scan(nodes)
    return names


def _node_contains(parent: dict, target_id: str) -> bool:
    """Retourne True si target_id est un descendant (direct ou indirect) de parent."""
    for branch in parent.get("children", []):
        for n in branch:
            if n["id"] == target_id:
                return True
            if _node_contains(n, target_id):
                return True
    return False
