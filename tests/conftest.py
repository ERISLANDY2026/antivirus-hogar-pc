"""Configuración de la suite (Carril E): headless, sin Qt, sin Windows.

Solo se importa lógica pura: contracts, core.* y modules.<paquete>.registro.
Las páginas (Qt) NO se importan nunca en los tests.
"""
import os
import sys

RAIZ_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ_PROYECTO not in sys.path:
    sys.path.insert(0, RAIZ_PROYECTO)
