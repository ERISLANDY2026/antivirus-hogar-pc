"""Programador de tareas de Windows: escaneo semanal silencioso.

La tarea lanza la app con --escaneo-programado. La app escanea, guarda el
informe y solo muestra notificación si hay hallazgos (igual que en Android).
"""
import os
import sys

from .powershell import ejecutar_comando

NOMBRE_TAREA = "Antivirus Hogar - Escaneo semanal"


def comando_crear_tarea(ruta_ejecutable: str, dia: str = "MON", hora: str = "10:00") -> list[str]:
    """Comando schtasks exacto para crear la tarea semanal."""
    return [
        "schtasks", "/Create", "/F",
        "/TN", NOMBRE_TAREA,
        "/TR", f'"{ruta_ejecutable}" --escaneo-programado',
        "/SC", "WEEKLY", "/D", dia, "/ST", hora,
        "/RL", "LIMITED",
    ]


def ruta_ejecutable_app() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def crear_tarea_semanal(dia: str = "MON", hora: str = "10:00") -> bool:
    codigo, _s, _e = ejecutar_comando(
        comando_crear_tarea(ruta_ejecutable_app(), dia, hora), timeout=120
    )
    return codigo == 0


def eliminar_tarea_semanal() -> bool:
    codigo, _s, _e = ejecutar_comando(
        ["schtasks", "/Delete", "/F", "/TN", NOMBRE_TAREA], timeout=120
    )
    return codigo == 0


def existe_tarea_semanal() -> bool:
    codigo, _s, _e = ejecutar_comando(
        ["schtasks", "/Query", "/TN", NOMBRE_TAREA], timeout=60
    )
    return codigo == 0


def notificar_windows(titulo: str, mensaje: str) -> bool:
    """Notificación toast de Windows (best-effort) vía PowerShell."""
    from .powershell import ejecutar_powershell

    titulo_esc = titulo.replace("'", "''")
    mensaje_esc = mensaje.replace("'", "''")
    script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        "ContentType = WindowsRuntime] | Out-Null; "
        "$plantilla = [Windows.UI.Notifications.ToastNotificationManager]::"
        "GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        "$textos = $plantilla.GetElementsByTagName('text'); "
        f"$textos.Item(0).AppendChild($plantilla.CreateTextNode('{titulo_esc}')) | Out-Null; "
        f"$textos.Item(1).AppendChild($plantilla.CreateTextNode('{mensaje_esc}')) | Out-Null; "
        "$toast = [Windows.UI.Notifications.ToastNotification]::new($plantilla); "
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
        "'Antivirus Hogar PC').Show($toast)"
    )
    try:
        ejecutar_powershell(script, timeout=60)
        return True
    except Exception:
        return False
