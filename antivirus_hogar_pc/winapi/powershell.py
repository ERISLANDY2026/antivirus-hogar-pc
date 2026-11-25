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
        capture_output=True, text=True, errors="replace", timeout=timeout,
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


def ejecutar_elevado_interactivo(script: str, timeout: int = 300) -> bool:
    """Ejecuta PowerShell ELEVADO e INTERACTIVO (SIN -NonInteractive).

    v1.0.9 lo trajo para la creación de la tarjeta virtual de
    SoftEther (retirada en la 1.0.10 con el cambio de motor VPN a
    OpenVPN); se conserva como utilidad genérica de elevación
    interactiva para pasos que necesiten que un aviso de Windows
    PUEDA aparecer y aceptarse. Devuelve True si el proceso
    elevado terminó con código 0.
    """
    if not es_windows():
        raise WindowsNoDisponible("La elevación UAC solo existe en Windows.")
    codificado = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    lanzador = (
        "$p = Start-Process powershell.exe -Verb RunAs -Wait -PassThru "
        f"-ArgumentList '-NoProfile','-EncodedCommand','{codificado}'; "
        "exit $p.ExitCode"
    )
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", lanzador],
        capture_output=True, text=True, timeout=timeout, creationflags=_flags(),
    )
    return proc.returncode == 0


def lanzar_elevado_oculto(script: str, timeout_lanzamiento: int = 120) -> int:
    """Lanza PowerShell ELEVADO con la ventana OCULTA y devuelve su PID.

    Diferencia con ejecutar_elevado: aquel espera a que el proceso
    acabe y su ventana de PowerShell SE VEÍA trabajando (así pasaba la
    optimización de volúmenes hasta la v1.0.4: Windows abría el Shell
    en primer plano). Aquí Start-Process lleva -WindowStyle Hidden:
    el proceso elevado corre EN SEGUNDO PLANO, sin ninguna ventana de
    consola. El aviso UAC es de Windows y sí aparece (es del sistema,
    no una ventana de Shell).

    No espera a que el proceso termine: devuelve su PID en cuanto
    arranca. Como un proceso elevado no puede devolver su salida por
    tubería al padre no elevado, el llamante vigila el resultado por
    los archivos que el propio script escriba (patrón de la
    optimización de volúmenes). Si el usuario cancela el aviso UAC o
    el lanzamiento falla, lanza RuntimeError con la causa.
    """
    if not es_windows():
        raise WindowsNoDisponible("La elevación UAC solo existe en Windows.")
    codificado = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    lanzador = (
        "try { $p = Start-Process powershell.exe -Verb RunAs "
        "-WindowStyle Hidden -PassThru "
        f"-ArgumentList '-NoProfile','-NonInteractive','-EncodedCommand','{codificado}'; "
        "Write-Output $p.Id } catch { exit 3 }"
    )
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", lanzador],
        capture_output=True, text=True, errors="replace",
        timeout=timeout_lanzamiento, creationflags=_flags(),
    )
    texto = (proc.stdout or "").strip()
    if proc.returncode != 0 or not texto.isdigit():
        raise RuntimeError(
            "No se pudo lanzar el proceso de administrador "
            "(¿se canceló el aviso de Windows?).")
    return int(texto)


def ejecutar_comando(args: list[str], timeout: int = 180) -> tuple[int, str, str]:
    """Ejecuta un programa de Windows (netsh, schtasks, winget, MpCmdRun…)."""
    if not es_windows():
        raise WindowsNoDisponible(f"{args[0]} solo está disponible en Windows.")
    proc = subprocess.run(
        args, capture_output=True, text=True, errors="replace",
        timeout=timeout, creationflags=_flags(),
    )
    return proc.returncode, proc.stdout, proc.stderr
