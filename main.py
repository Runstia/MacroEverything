"""
main.py — Point d'entree de MacroEverything.
Lance la verification de Pillow, puis ouvre l'application.
"""

import sys
import subprocess
import ctypes
import tkinter as tk
from tkinter import messagebox

from macro_app.utils import PIL_AVAILABLE
from macro_app.ui.app import MacroEverythingApp


def _set_dpi_aware():
    """Active la conscience DPI par moniteur v2 (Windows 10+), sinon repli basique."""
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
    except AttributeError:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main():
    _set_dpi_aware()

    if not PIL_AVAILABLE:
        root = tk.Tk()
        root.withdraw()
        install = messagebox.askyesno(
            "Dependance manquante",
            "Pillow n'est pas installe (requis pour les captures d'ecran).\n\n"
            "Installer maintenant ? (pip install pillow)")
        root.destroy()
        if install:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
            messagebox.showinfo("Installe",
                                "Pillow installe. Relancez l'application.")
        return

    MacroEverythingApp().mainloop()


if __name__ == "__main__":
    main()
