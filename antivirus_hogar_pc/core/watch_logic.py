"""Protección al instalar (modo usuario, honesta) e informe de persistencia.

Sin kernel no hay interceptación en tiempo real; lo que sí funciona:
- Foto de programas instalados y DIFF contra la foto anterior → «programa
  nuevo», que se revisa contra la base de huellas.
- Ejecutables nuevos en Descargas/Escritorio desde la última revisión.
- Heurística simple y explicable para tareas programadas sospechosas.
"""
import os
from dataclasses import dataclass


@dataclass
class ProgramaInstalado:
    nombre: str
    editor: str = ""
    version: str = ""
    fecha_instalacion: str = ""
    tamano_kb: int = 0
    cadena_desinstalacion: str = ""
    carpeta: str = ""


def diff_programas(
    antes: dict[str, ProgramaInstalado], despues: dict[str, ProgramaInstalado]
) -> tuple[list[ProgramaInstalado], list[ProgramaInstalado], list[ProgramaInstalado]]:
    """(nuevos, eliminados, actualizados) comparando por nombre."""
    nuevos = [p for k, p in despues.items() if k not in antes]
    eliminados = [p for k, p in antes.items() if k not in despues]
    actualizados = [
        despues[k] for k in despues
        if k in antes and despues[k].version != antes[k].version
    ]
    return nuevos, eliminados, actualizados


def ejecutables_nuevos(
    carpeta: str, conocidos: set[str], extensiones: set[str]
) -> list[str]:
    """Rutas de ejecutables presentes en la carpeta que no estaban en la foto."""
    encontrados: list[str] = []
    if not carpeta or not os.path.isdir(carpeta):
        return encontrados
    for nombre in os.listdir(carpeta):
        ruta = os.path.join(carpeta, nombre)
        if not os.path.isfile(ruta):
            continue
        if os.path.splitext(nombre)[1].lower() not in extensiones:
            continue
        if ruta not in conocidos:
            encontrados.append(ruta)
    return sorted(encontrados)


_MARCAS_SOSPECHA_TAREA = (
    "\\temp\\", "\\tmp\\", "appdata", "powershell", "wscript", "cscript",
    "mshta", "rundll32", ".bat", ".vbs", ".js",
)


def es_tarea_sospechosa(accion: str, autor: str = "") -> tuple[bool, str]:
    """Heurística explicable: tarea que lanza scripts o cosas desde carpetas
    temporales. No es un veredicto: es un «revísalo»."""
    texto = (accion or "").lower()
    for marca in _MARCAS_SOSPECHA_TAREA:
        if marca in texto:
            return True, f"La acción menciona «{marca.strip(chr(92))}»."
    if autor and autor.lower() in ("", "desconocido", "unknown"):
        return True, "La tarea no declara autor."
    return False, ""
