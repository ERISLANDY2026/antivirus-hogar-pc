"""Lógica pura de salud de discos (Carril C).

Convierte los datos crudos de las dos fuentes a contracts.SmartInfo:
- pySMART/smartctl (fuente principal cuando está disponible), y
- Get-PhysicalDisk + Get-StorageReliabilityCounter (winapi.disks, respaldo).

Regla de honestidad del proyecto: si una fuente no devuelve datos (disco
tras puente USB, RAID, controlador sin SMART) el resultado es
``sin_datos=True`` = «no se puede leer», NUNCA «sano».
"""
import re

from antivirus_hogar_pc.contracts import SmartInfo

_LIMITE_DESGASTE_REGULAR = 90  # % de vida consumida a partir del cual se avisa


def _normalizar(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (texto or "").lower()).strip()


def _coincide_modelo(a: str, b: str) -> bool:
    """True si dos nombres de disco parecen el mismo (tokens en común)."""
    ta = {t for t in _normalizar(a).split() if len(t) >= 3}
    tb = {t for t in _normalizar(b).split() if len(t) >= 3}
    return bool(ta and tb and ta & tb)


# --- Fuente 1: pySMART / smartctl ---------------------------------------------
def smart_desde_pysmart(datos: dict) -> SmartInfo:
    """datos (lo recoge el adaptador de servicios_sistema con getattr
    defensivo): modelo, tipo, evaluacion («PASS»/«FAIL»/«»), temperatura_c,
    horas_encendido, desgaste_pct (% de vida CONSUMIDA), errores."""
    modelo = str(datos.get("modelo") or "Disco")
    evaluacion = str(datos.get("evaluacion") or "").upper()
    temperatura = datos.get("temperatura_c")
    horas = datos.get("horas_encendido")
    desgaste = datos.get("desgaste_pct")
    errores = datos.get("errores")

    hay_datos = bool(evaluacion) or temperatura is not None or horas is not None \
        or desgaste is not None or errores is not None
    if not hay_datos:
        return SmartInfo(
            disco=modelo, tipo=str(datos.get("tipo") or ""),
            salud="desconocido", sin_datos=True,
            detalle="smartctl no devolvió datos SMART de este disco "
                    "(habitual tras un puente USB o en RAID): no se puede leer "
                    "su salud. No significa que esté sano ni dañado.")

    if evaluacion == "FAIL":
        salud = "mal"
    elif evaluacion == "PASS":
        salud = "bien"
        if (errores or 0) > 0 or (desgaste is not None and desgaste >= _LIMITE_DESGASTE_REGULAR):
            salud = "regular"
    else:  # hay contadores pero smartctl no dio veredicto global
        salud = "regular" if (errores or 0) > 0 else "desconocido"

    detalle = "Datos SMART leídos con smartctl (pySMART)."
    if salud == "mal":
        detalle = ("smartctl marca este disco como FALLIDO: haz copia de "
                   "seguridad cuanto antes y plantéate sustituirlo.")
    elif salud == "regular":
        detalle = ("smartctl lo da por bueno, pero hay señales de desgaste o "
                   "errores: conviene vigilarlo y tener copia de seguridad.")
    return SmartInfo(
        disco=modelo, tipo=str(datos.get("tipo") or ""), salud=salud,
        temperatura_c=temperatura, horas_encendido=horas,
        desgaste_pct=desgaste, errores=errores, detalle=detalle)


# --- Fuente 2: Get-PhysicalDisk (respaldo de Windows) ---------------------------
_TIPOS_FISICOS = {"SSD": "SSD", "HDD": "HDD", "NVME": "NVMe"}


def smart_desde_physicaldisk(d: dict) -> SmartInfo:
    """d: un dict de winapi.disks.discos_fisicos()."""
    nombre = str(d.get("nombre") or "Disco")
    tipo = _TIPOS_FISICOS.get(str(d.get("tipo") or "").upper(), "")
    if d.get("sin_datos"):
        return SmartInfo(
            disco=nombre, tipo=tipo, salud="desconocido", sin_datos=True,
            detalle="Windows no devolvió el estado de este disco (puede estar "
                    "tras un puente USB o en RAID): no se puede leer su salud. "
                    "No significa que esté sano ni dañado.")
    salud_win = str(d.get("salud") or "")
    salud = {"Healthy": "bien", "Warning": "regular",
             "Unhealthy": "mal"}.get(salud_win, "desconocido")
    detalle = "Estado leído con Get-PhysicalDisk de Windows."
    if salud == "mal":
        detalle = ("Windows marca este disco como NO saludable: haz copia de "
                   "seguridad cuanto antes y plantéate sustituirlo.")
    elif salud == "regular":
        detalle = ("Windows marca este disco con AVISO: conviene vigilarlo y "
                   "tener copia de seguridad.")
    return SmartInfo(
        disco=nombre, tipo=tipo, salud=salud,
        temperatura_c=d.get("temperatura"), horas_encendido=d.get("horas"),
        desgaste_pct=d.get("desgaste_pct"), errores=d.get("errores_lectura"),
        detalle=detalle)


# --- Fusión de fuentes ----------------------------------------------------------
def fusionar_smart(de_pysmart: list[SmartInfo],
                   de_windows: list[SmartInfo]) -> list[SmartInfo]:
    """Combina ambas fuentes por disco: manda la que tenga datos; si las dos
    tienen, manda pySMART/smartctl (más detalle) y se anota el respaldo."""
    resultado: list[SmartInfo] = []
    usados: set[int] = set()
    for info_win in de_windows:
        elegido = info_win
        for i, info_py in enumerate(de_pysmart):
            if i in usados or not _coincide_modelo(info_py.disco, info_win.disco):
                continue
            usados.add(i)
            if not info_py.sin_datos:
                elegido = info_py
                if not info_win.sin_datos and info_win.salud != info_py.salud:
                    elegido.detalle += (f" Windows (Get-PhysicalDisk) lo ve "
                                        f"como «{info_win.salud}».")
            break
        resultado.append(elegido)
    for i, info_py in enumerate(de_pysmart):
        if i not in usados:
            resultado.append(info_py)
    return resultado


# --- Qué operación de Optimize-Volume toca a cada volumen -----------------------
def tipo_para_volumen(discos_fisicos: list[dict], tamano_volumen: int) -> str:
    """«SSD», «HDD» o «» (no se puede determinar → no se toca el volumen).

    discos_fisicos: dicts de winapi.disks.discos_fisicos(). Reglas: si todos
    los discos con tipo conocido comparten tipo, ese; si hay mezcla, solo se
    decide cuando un único disco puede contener el volumen por tamaño."""
    conocidos = [d for d in discos_fisicos
                 if str(d.get("tipo") or "").upper() in ("SSD", "HDD")]
    if not conocidos:
        return ""
    tipos = {str(d["tipo"]).upper() for d in conocidos}
    if len(tipos) == 1:
        return conocidos[0]["tipo"].upper()
    candidatos = [d for d in conocidos
                  if int(d.get("tamano") or 0) >= tamano_volumen > 0]
    if len(candidatos) == 1:
        return str(candidatos[0]["tipo"]).upper()
    return ""
