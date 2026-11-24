"""Tune-up: temporales, papelera, arranque reversible, respaldo del registro,
archivo hosts y winget.

Reglas: primero INFORME de cuánto ocupa; el borrado lo confirma el usuario;
el arranque se desactiva de forma REVERSIBLE (nunca se borra a la primera);
SIN limpiador de registro (descartado: sin beneficio y con riesgo).
"""
import json
import os
import shutil
import time

from ..core.winget_parse import ProgramaDesactualizado, parsear_winget_upgrade
from . import es_windows
from .powershell import ejecutar_comando, ejecutar_elevado, ejecutar_powershell, ejecutar_powershell_json

CARPETAS_TEMPORALES = [
    ("Temporales del usuario", lambda: os.environ.get("TEMP", "")),
    ("Temporales de Windows", lambda: r"C:\Windows\Temp"),
    ("Miniaturas e iconos", lambda: os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Explorer")),
    ("Informes de errores", lambda: os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "WER")),
]


def _tamano_carpeta(ruta: str, solo_patron: str = "") -> int:
    total = 0
    if not ruta or not os.path.isdir(ruta):
        return 0
    for dirpath, _dirs, archivos in os.walk(ruta):
        for nombre in archivos:
            if solo_patron and solo_patron not in nombre.lower():
                continue
            try:
                total += os.path.getsize(os.path.join(dirpath, nombre))
            except OSError:
                continue
    return total


def analizar_temporales() -> list[dict]:
    resultado = []
    for nombre, obtener in CARPETAS_TEMPORALES:
        ruta = obtener()
        patron = "thumbcache" if "Miniaturas" in nombre else ""
        resultado.append({"nombre": nombre, "ruta": ruta,
                          "tamano": _tamano_carpeta(ruta, patron)})
    return resultado


def limpiar_temporales() -> dict:
    """Borra el contenido de las carpetas temporales (lo bloqueado se salta)."""
    borrados = 0
    errores = 0
    for _nombre, obtener in CARPETAS_TEMPORALES:
        ruta = obtener()
        if not ruta or not os.path.isdir(ruta):
            continue
        for dirpath, _dirs, archivos in os.walk(ruta):
            for nombre in archivos:
                try:
                    os.remove(os.path.join(dirpath, nombre))
                    borrados += 1
                except OSError:
                    errores += 1
    return {"borrados": borrados, "errores": errores}


def tamano_papelera() -> int:
    script = (
        "$total = 0; Get-ChildItem 'C:\\$Recycle.Bin' -Recurse -Force "
        "-ErrorAction SilentlyContinue | ForEach-Object { $total += $_.Length }; "
        "$total | ConvertTo-Json"
    )
    try:
        datos = ejecutar_powershell_json(script, timeout=300)
        return int(datos) if isinstance(datos, (int, float)) else 0
    except Exception:
        return 0


def vaciar_papelera() -> bool:
    try:
        ejecutar_powershell("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
        return True
    except Exception:
        return False


# --- Arranque reversible ------------------------------------------------------
def _ruta_estado_arranque(carpeta_respaldos: str) -> str:
    return os.path.join(carpeta_respaldos, "arranque_desactivado.json")


def _leer_estado_arranque(carpeta_respaldos: str) -> list[dict]:
    ruta = _ruta_estado_arranque(carpeta_respaldos)
    if os.path.isfile(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return []
    return []


def desactivar_arranque_inicio(nombre_acceso: str, carpeta_respaldos: str) -> bool:
    """Mueve un acceso directo de la carpeta de inicio a la de respaldos."""
    carpeta_inicio = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )
    origen = os.path.join(carpeta_inicio, nombre_acceso)
    if not os.path.isfile(origen):
        return False
    destino = os.path.join(carpeta_respaldos, f"arranque_{int(time.time())}_{nombre_acceso}")
    shutil.move(origen, destino)
    estado = _leer_estado_arranque(carpeta_respaldos)
    estado.append({"tipo": "acceso_inicio", "nombre": nombre_acceso,
                    "respaldo": destino, "fecha": time.time()})
    with open(_ruta_estado_arranque(carpeta_respaldos), "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=1)
    return True


def restaurar_arranque(carpeta_respaldos: str) -> int:
    """Devuelve todo lo desactivado por la app. Devuelve cuántos volvieron."""
    estado = _leer_estado_arranque(carpeta_respaldos)
    carpeta_inicio = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )
    restaurados = 0
    restantes = []
    for item in estado:
        if item.get("tipo") == "acceso_inicio" and os.path.isfile(item["respaldo"]):
            destino = os.path.join(carpeta_inicio, item["nombre"])
            if not os.path.exists(destino):
                shutil.move(item["respaldo"], destino)
                restaurados += 1
                continue
        restantes.append(item)
    with open(_ruta_estado_arranque(carpeta_respaldos), "w", encoding="utf-8") as f:
        json.dump(restantes, f, ensure_ascii=False, indent=1)
    return restaurados


# --- Respaldo del registro (la alternativa segura al «limpiador») ------------
def respaldo_registro(carpeta_respaldos: str) -> list[str]:
    """Exporta HKCU\\Software y HKLM\\SOFTWARE a archivos .reg con fecha."""
    marca = time.strftime("%Y%m%d-%H%M%S")
    creados = []
    for clave, nombre in (("HKCU\\Software", "registro_usuario"),
                          ("HKLM\\SOFTWARE", "registro_sistema")):
        destino = os.path.join(carpeta_respaldos, f"{nombre}_{marca}.reg")
        codigo, _s, _e = ejecutar_comando(["reg", "export", clave, destino, "/y"], timeout=600)
        if codigo == 0 and os.path.isfile(destino):
            creados.append(destino)
    return creados


# --- Archivo hosts --------------------------------------------------------------
RUTA_HOSTS = r"C:\Windows\System32\drivers\etc\hosts"


def leer_hosts() -> str:
    with open(RUTA_HOSTS, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def escribir_hosts_elevado(nuevo_texto: str, carpeta_respaldos: str) -> bool:
    """Respalda el hosts actual y escribe el nuevo con elevación (UAC)."""
    marca = time.strftime("%Y%m%d-%H%M%S")
    respaldo = os.path.join(carpeta_respaldos, f"hosts_{marca}.bak")
    try:
        shutil.copyfile(RUTA_HOSTS, respaldo)
    except OSError:
        pass
    temporal = os.path.join(carpeta_respaldos, "hosts_nuevo.txt")
    with open(temporal, "w", encoding="utf-8", newline="\n") as f:
        f.write(nuevo_texto)
    temp_esc = temporal.replace("'", "''")
    return ejecutar_elevado(
        f"Copy-Item -Force '{temp_esc}' '{RUTA_HOSTS}'; ipconfig /flushdns | Out-Null",
        timeout=120,
    )


# --- winget ---------------------------------------------------------------------
def programas_desactualizados_winget() -> list[ProgramaDesactualizado]:
    _codigo, salida, _error = ejecutar_comando(
        ["winget", "upgrade", "--include-unknown", "--accept-source-agreements"],
        timeout=600,
    )
    return parsear_winget_upgrade(salida)


def actualizar_programa_winget(id_paquete: str) -> tuple[int, str]:
    codigo, salida, error = ejecutar_comando(
        ["winget", "upgrade", "--id", id_paquete, "--exact",
         "--accept-source-agreements", "--accept-package-agreements"],
        timeout=1800,
    )
    return codigo, (salida or error or "").strip()


def actualizar_todo_winget() -> tuple[int, str]:
    codigo, salida, error = ejecutar_comando(
        ["winget", "upgrade", "--all", "--include-unknown",
         "--accept-source-agreements", "--accept-package-agreements"],
        timeout=3600,
    )
    return codigo, (salida or error or "").strip()


def abrir_configuracion_dns() -> None:
    """Abre el panel de red de Windows para el modo DNS reforzado (guiado)."""
    if es_windows():
        os.startfile("ms-settings:network-status")  # noqa: S606 - ajuste del sistema
