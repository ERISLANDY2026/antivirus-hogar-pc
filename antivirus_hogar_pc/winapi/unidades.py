"""Unidades del sistema (v1.0.21): extraíbles y drivers presentes.

- unidades_extraibles(): memorias USB conectadas, para OFRECER su
  escaneo con Defender (nunca automático sin aviso la primera vez).
- archivos_sys_instalados(): los .sys presentes en System32\\drivers,
  que es donde viven los drivers cargados: la materia prima del
  chequeo BYOVD por huella (core.byovd).
"""
import glob
import os


def unidades_extraibles() -> list[dict]:
    """[{raiz, etiqueta}] de las unidades extraíbles conectadas.

    En Windows se pregunta a GetDriveTypeW (2 = extraíble); fuera
    de Windows se devuelve la lista vacía.
    """
    salida: list[dict] = []
    if os.name != "nt":
        return salida
    import ctypes
    import string

    get_tipo = ctypes.windll.kernel32.GetDriveTypeW
    for letra in string.ascii_uppercase:
        raiz = f"{letra}:\\"
        try:
            if get_tipo(raiz) == 2:  # DRIVE_REMOVABLE
                salida.append({"raiz": raiz, "etiqueta": letra + ":"})
        except Exception:
            continue
    # Etiqueta legible si psutil la conoce (punto de montaje).
    try:
        import psutil

        for part in psutil.disk_partitions(all=False):
            for unidad in salida:
                if part.mountpoint.upper().startswith(
                        unidad["raiz"][0].upper()):
                    unidad["etiqueta"] = (
                        f"{unidad['raiz']} ({part.device})")
    except Exception:
        pass
    return salida


def archivos_sys_instalados() -> list[str]:
    """Rutas de los .sys en System32\\drivers (drivers cargados)."""
    if os.name != "nt":
        return []
    raiz = os.environ.get("SystemRoot", r"C:\Windows")
    carpeta = os.path.join(raiz, "System32", "drivers")
    return sorted(glob.glob(os.path.join(carpeta, "*.sys")))
