"""Arranque automático con Windows (v1.0.5).

Mecanismo estándar y reversible: el valor «AntivirusHogarPC» de la
clave Run del usuario (HKCU\\Software\\Microsoft\\Windows\\
CurrentVersion\\Run) apunta al ejecutable con --inicio-automatico.
Sin administrador, sin servicios: se escribe y se retira con
PowerShell oculto, como todo lo de la app. El interruptor vive en
Ajustes («Arrancar con Windows»); al desactivarlo el valor se borra.
"""
import os
import sys

from . import WindowsNoDisponible, es_windows
from .powershell import ejecutar_powershell

CLAVE_RUN = r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
NOMBRE_VALOR = "AntivirusHogarPC"


def ruta_ejecutable_app() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def comando_arranque(ruta_ejecutable: str) -> str:
    """El comando que Windows ejecuta al iniciar sesión."""
    return f'"{ruta_ejecutable}" --inicio-automatico'


def script_fijar_arranque(activo: bool, ruta_ejecutable: str) -> str:
    """El script de PowerShell (visible en tests; nunca en la UI)."""
    if activo:
        comando = comando_arranque(ruta_ejecutable).replace("'", "''")
        return (f"Set-ItemProperty -Path '{CLAVE_RUN}' "
                f"-Name '{NOMBRE_VALOR}' -Value '{comando}'")
    return (f"Remove-ItemProperty -Path '{CLAVE_RUN}' "
            f"-Name '{NOMBRE_VALOR}' -ErrorAction SilentlyContinue")


def fijar_arranque_windows(activo: bool,
                           ruta_ejecutable: str | None = None) -> bool:
    """Escribe (True) o retira (False) la entrada de arranque."""
    if not es_windows():
        raise WindowsNoDisponible("El arranque con Windows solo existe en Windows.")
    ruta = ruta_ejecutable or ruta_ejecutable_app()
    ejecutar_powershell(script_fijar_arranque(bool(activo), ruta), timeout=60)
    return True


def arranque_windows_activo() -> bool:
    """True si la entrada de arranque existe en el registro."""
    if not es_windows():
        raise WindowsNoDisponible("El arranque con Windows solo existe en Windows.")
    salida = ejecutar_powershell(
        f"if (Get-ItemProperty -Path '{CLAVE_RUN}' -Name '{NOMBRE_VALOR}' "
        "-ErrorAction SilentlyContinue) { 'SI' } else { 'NO' }",
        timeout=60)
    return "SI" in (salida or "")
