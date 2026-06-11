"""
macro_app/macros_folder.py
Gestion du dossier centralise des fichiers de macros.
Toutes les macros sont stockees dans macros/ (cree automatiquement).
"""

import os
import shutil

from .paths import get_user_data_dir


def get_macros_dir() -> str:
    """Retourne (et cree si absent) le dossier macros/ dans les données utilisateur."""
    folder = os.path.join(get_user_data_dir(), "macros")
    os.makedirs(folder, exist_ok=True)
    return folder


def import_to_macros_dir(path: str) -> str:
    """Copie le fichier dans macros/ s'il n'y est pas deja.
    Retourne le chemin du fichier dans macros/ (original ou copie)."""
    macros_dir = get_macros_dir()
    abs_src = os.path.normpath(os.path.abspath(path))
    abs_dir = os.path.normpath(macros_dir)
    if os.path.dirname(abs_src) == abs_dir:
        return path                             # deja dans macros/
    dest = os.path.join(macros_dir, os.path.basename(path))
    shutil.copy2(path, dest)
    return dest


def list_macro_files() -> list:
    """Liste les noms de fichiers .macros/.json dans le dossier macros/."""
    macros_dir = get_macros_dir()
    return sorted(
        f for f in os.listdir(macros_dir)
        if f.lower().endswith((".macros", ".json"))
    )
