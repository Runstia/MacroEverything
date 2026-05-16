"""
macro_app/utils.py
Detection de la plateforme, disponibilite de Pillow,
et utilitaires systeme (sons de retour audio).
"""

import time
import threading

# ─────────────────────────────────────────────
#  DETECTION WINDOWS + CTYPES
# ─────────────────────────────────────────────
try:
    import ctypes
    import ctypes.wintypes
    import winsound as _winsound
    WINDOWS = True
except ImportError:
    ctypes    = None
    _winsound = None
    WINDOWS   = False

# ─────────────────────────────────────────────
#  DETECTION PILLOW
# ─────────────────────────────────────────────
try:
    from PIL import Image, ImageTk, ImageGrab, ImageChops
    PIL_AVAILABLE = True
except ImportError:
    Image = ImageTk = ImageGrab = ImageChops = None
    PIL_AVAILABLE = False


# ─────────────────────────────────────────────
#  SONS DE RETOUR AUDIO
# ─────────────────────────────────────────────
def _play_cue(cue_type: str) -> None:
    """Joue un son de retour dans un thread daemon.

    cue_type : 'run' | 'stop' | 'pause'
    """
    if _winsound is None:
        return

    def _do():
        try:
            if cue_type == "run":
                _winsound.Beep(880, 100)
            elif cue_type == "stop":
                _winsound.Beep(440, 180)
            elif cue_type == "pause":
                _winsound.Beep(660, 80)
                time.sleep(0.06)
                _winsound.Beep(660, 80)
        except Exception:
            pass

    threading.Thread(target=_do, daemon=True).start()
