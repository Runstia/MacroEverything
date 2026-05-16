"""
macro_app/settings.py
Lecture et ecriture des parametres persistants dans settings.json.
Toutes les preferences applicatives (hotkeys, options futures) transitent ici.
"""

import json
import os

_SETTINGS_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "settings.json")
)


def load_settings() -> dict:
    """Charge settings.json. Retourne un dict vide si absent ou invalide."""
    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(data: dict) -> None:
    """Ecrit le dict dans settings.json (cree ou ecrase le fichier)."""
    try:
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
