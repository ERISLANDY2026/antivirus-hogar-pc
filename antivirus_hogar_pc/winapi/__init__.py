"""Capa de acceso a Windows: PowerShell, WMI/CIM, COM y utilidades del sistema.

Todo lo que toca Windows pasa por aquí, con el comando exacto documentado.
Fuera de Windows, las funciones lanzan WindowsNoDisponible y la interfaz lo
enseña con honestidad en vez de romperse.
"""
import sys


class WindowsNoDisponible(RuntimeError):
    """La función llamada solo existe en Windows."""


def es_windows() -> bool:
    return sys.platform.startswith("win")
