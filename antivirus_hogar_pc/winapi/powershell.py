"""Ejecución de PowerShell y lectura de su salida JSON."""
import base64
import json
import subprocess
import sys

from . import WindowsNoDisponible, es_windows


def _flags() -> int:
    if sys.platform.startswith("win"):
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def ejecutar_powershell(script: str, timeout: int = 180) -> str:
    """Ejecuta un script de PowerShell y devuelve stdout (texto)."""
    if not es_windows():
        raise WindowsNoDisponible("PowerShell solo está disponible en Windows.")
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-Command", script],
        capture_output=True, text=True, timeout=timeout,
        creationflags=_flags(),
    )
    if proc.returncode != 0 and proc.stderr.strip():
        raise RuntimeError(f"PowerShell: {proc.stderr.strip()[:400]}")
    return proc.stdout


def ejecutar_powershell_json(script: str, timeout: int = 180):
    """Ejecuta el script (que debe terminar en ConvertTo-Json) y parsea."""
    salida = ejecutar_powershell(script, timeout=timeout).strip()
    if not salida:
        return None
    datos = json.loads(salida)
    return datos


def como_lista(datos) -> list:
    """ConvertTo-Json devuelve un objeto suelto si hay un solo resultado."""
    if datos is None:
        return []
    if isinstance(datos, list):
        return datos
    return [datos]


def ejecutar_elevado(script: str, timeout: int = 300) -> bool:
    """Ejecuta PowerShell ELEVADO (pide UAC al usuario) y espera a que acabe.

    Se usa solo para acciones que exigen administrador y siempre tras la
    confirmación del usuario en la interfaz (p. ej. activar CFA, escribir el
    hosts, crear un punto de restauración). Devuelve True si se lanzó.
    """
    if not es_windows():
        raise WindowsNoDisponible("La elevación UAC solo existe en Windows.")
    codificado = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    lanzador = (
        "$p = Start-Process powershell.exe -Verb RunAs -Wait -PassThru "
        f"-ArgumentList '-NoProfile','-NonInteractive','-EncodedCommand','{codificado}'; "
        "exit $p.ExitCode"
    )
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", lanzador],
        capture_output=True, text=True, timeout=timeout, creationflags=_flags(),
    )
    return proc.returncode == 0


def ejecutar_comando(args: list[str], timeout: int = 180) -> tuple[int, str, str]:
    """Ejecuta un programa de Windows (netsh, schtasks, winget, MpCmdRun…)."""
    if not es_windows():
        raise WindowsNoDisponible(f"{args[0]} solo está disponible en Windows.")
    proc = subprocess.run(
        args, capture_output=True, text=True, timeout=timeout, creationflags=_flags(),
    )
    return proc.returncode, proc.stdout, proc.stderr
