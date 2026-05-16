"""
main.py — Point d'entree de MacroEverything.
Lance la verification de Pillow, puis ouvre l'application.
"""

import sys
import subprocess
import tkinter as tk
from tkinter import messagebox

from macro_app.utils import PIL_AVAILABLE
from macro_app.ui.app import MacroEverythingApp


def main():
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
