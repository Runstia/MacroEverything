"""
macro_app/i18n.py
Systeme de localisation.
- Charge les traductions depuis locales/<code>.json
- Detecte la langue Windows au premier demarrage (GetUserDefaultUILanguage)
- Fournit t(key, **kw) pour obtenir une chaine traduite avec substitution
- node_label(type_key) / cat_label(cat) pour les labels de noeuds traduits
"""

import json
import os
import ctypes

_LOCALES_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "locales")
)
_LANGS_FILE = os.path.join(_LOCALES_DIR, "langs.json")

_translations: dict = {}
_lang: str = "en"

# ── LCID primaire Windows -> code ISO 639-1 ───────────────────────────────
_LCID_PRIMARY_MAP: dict = {
    0x04: "zh",   # Chinese
    0x07: "de",   # German
    0x09: "en",   # English
    0x0A: "es",   # Spanish
    0x0C: "fr",   # French
    0x10: "it",   # Italian
    0x11: "ja",   # Japanese
    0x12: "ko",   # Korean
    0x13: "nl",   # Dutch
    0x14: "pl",   # Polish
    0x16: "pt",   # Portuguese
    0x19: "ru",   # Russian
    0x1D: "sv",   # Swedish
}


def _load_langs() -> dict:
    """Charge langs.json -> {code: {name, file}}."""
    try:
        with open(_LANGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {"en": {"name": "English", "file": "en.json"}}


def _load_file(lang_file: str) -> dict:
    """Charge un fichier JSON de traductions."""
    path = os.path.join(_LOCALES_DIR, lang_file)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def detect_windows_language() -> str:
    """Retourne le code langue detecte depuis Windows (ex: 'fr', 'en')."""
    try:
        lcid    = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        primary = lcid & 0x3FF   # bits 0..9 = primary language id
        return _LCID_PRIMARY_MAP.get(primary, "en")
    except Exception:
        return "en"


def init(lang_code: str | None = None) -> None:
    """
    Initialise le systeme i18n.
    - lang_code=None  : detection automatique via Windows
    - Si la langue n'existe pas dans langs.json, repli sur l'anglais.
    L'anglais est toujours charge en premier comme base de fallback.
    """
    global _translations, _lang
    langs = _load_langs()

    if lang_code is None:
        lang_code = detect_windows_language()

    if lang_code not in langs:
        lang_code = "en"

    _lang = lang_code

    # Base de fallback : anglais
    en_data: dict = {}
    if "en" in langs:
        en_data = _load_file(langs["en"]["file"])

    # Fusionner avec la langue cible (ecrase les cles en commun)
    if lang_code == "en":
        _translations = en_data
    else:
        lang_data     = _load_file(langs[lang_code]["file"])
        _translations = {**en_data, **lang_data}


def t(key: str, **kw) -> str:
    """Retourne la traduction de la cle, avec substitution optionnelle."""
    val = _translations.get(key, key)
    if kw:
        try:
            val = val.format(**kw)
        except (KeyError, IndexError, ValueError):
            pass
    return val


def current_lang() -> str:
    """Retourne le code de la langue courante."""
    return _lang


def get_available() -> dict:
    """Retourne {code: {name, file}} des langues disponibles."""
    return _load_langs()


def node_label(type_key: str) -> str:
    """Retourne le label traduit d'un type de noeud (fallback sur constants)."""
    key = f"node.{type_key}.label"
    if key in _translations:
        return _translations[key]
    from .constants import NODE_TYPES
    return NODE_TYPES.get(type_key, {}).get("label", type_key)


def cat_label(cat: str) -> str:
    """Retourne le label traduit d'une categorie de noeud."""
    return _translations.get(f"cat.{cat}", cat)
