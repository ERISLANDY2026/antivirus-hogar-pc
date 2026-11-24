"""Lanzador de Antivirus Hogar PC (punto de entrada de PyInstaller)."""
import sys

from antivirus_hogar_pc.ui.main import main

if __name__ == "__main__":
    sys.exit(main(sys.argv))
