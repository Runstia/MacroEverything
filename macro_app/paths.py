"""
macro_app/paths.py
Resolution des chemins selon le mode d'execution.

- Mode dev (script Python) : chemins relatifs au projet
- Mode frozen (.exe PyInstaller onefile) :
    * Donnees utilisateur -> %%LOCALAPPDATA%%/RunFaster/MacroEverything  (persistant)
    * Ressources embarquees -> sys._MEIPASS  (temp, lecture seule)
"""

import os
import sys


def get_user_data_dir() -> str:
    """Dossier persistant pour les donnees utilisateur (macros, parametres).

    .exe -> %%LOCALAPPDATA%%/RunFaster/MacroEverything
    dev  -> racine du projet
    """
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        path = os.path.join(base, "RunFaster", "MacroEverything")
        os.makedirs(path, exist_ok=True)
        return path
    # Mode developpement -- dossier parent de macro_app/
    return os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def get_bundled_dir(name: str) -> str:
    """Chemin vers un dossier de ressources embarquees (ex: 'locales').

    .exe -> sys._MEIPASS/<name>   (extraction PyInstaller, lecture seule)
    dev  -> racine du projet/<name>
    """
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, name)
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", name))
