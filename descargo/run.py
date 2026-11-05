"""Lanzador de DescarGO (también usado por PyInstaller)."""

import sys

from descargo.app import main

if __name__ == "__main__":
    sys.exit(main())
