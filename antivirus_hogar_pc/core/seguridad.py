"""Servicio de seguridad del Carril B: bloqueador hosts, protección al
instalar (modo usuario) e informe de privacidad/persistencia.

Orquesta core (hosts_blocker, watch_logic, scanner) + winapi y devuelve
siempre el sobre congelado `ResultadoModulo`: ningún error llega a la UI
como excepción. Nada actúa solo: cada función hace exactamente la
operación que el usuario pidió con su botón.
"""
import json
import os
import time
from dataclasses import asdict

from .. import config
from ..contracts import HostsEstado, ResultadoModulo
from ..winapi import es_windows
from ..winapi import system_info, tuneup_win
from . import hosts_blocker
from .scanner import EXTENSIONES_EJECUTABLES, Hallazgo, analizar_archivo
from .signatures import BaseFirmas
from .watch_logic import ProgramaInstalado, diff_programas, ejecutables_nuevos

# ---------------------------------------------------------------------------
# Estado local del bloqueador (qué base se activó, si está en pausa)
# ---------------------------------------------------------------------------

def _ruta_estado_local() -> str:
    return os.path.join(config.carpeta_datos(), "estado_bloqueador.json")


def _leer_estado_local() -> dict:
    ruta = _ruta_estado_local()
    if os.path.isfile(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                datos = json.load(f)
            if isinstance(datos, dict):
                return datos
        except (OSError, ValueError):
            pass
    return {"base": "semilla", "pausado": False}


def _guardar_estado_local(estado: dict) -> None:
    with open(_ruta_estado_local(), "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=1)


def _ultimo_respaldo_hosts() -> str:
    carpeta = config.ruta_respaldos()
    candidatos = [
        os.path.join(carpeta, n) for n in os.listdir(carpeta)
        if n.startswith("hosts_") and n.endswith(".bak")
    ] if os.path.isdir(carpeta) else []
    if not candidatos:
        return ""
    return max(candidatos, key=os.path.getmtime)


# ---------------------------------------------------------------------------
# Bloqueador hosts
# ---------------------------------------------------------------------------

def rutas_base_dominios(base: str) -> list[str]:
    activos = config.carpeta_activos()
    if base == "fusionada":
        return [os.path.join(activos, "dominios_fusionados.txt")]
    return [
        os.path.join(activos, "malware_seed.txt"),
        os.path.join(activos, "adblock_seed.txt"),
    ]


def estado_hosts() -> HostsEstado:
    """Estado real del bloqueador leyendo el hosts de Windows."""
    if not es_windows():
        raise RuntimeError("Disponible solo en Windows.")
    texto = tuneup_win.leer_hosts()
    local = _leer_estado_local()
    return HostsEstado(
        activo=hosts_blocker.bloque_activo(texto),
        dominios_bloqueados=hosts_blocker.contar_bloqueados(texto),
        base_usada=local.get("base", "semilla"),
        ruta_respaldo=_ultimo_respaldo_hosts(),
        dns_reforzado=False,
    )


def activar_hosts(base: str = "semilla") -> ResultadoModulo:
    """Escribe el bloque de la app en el hosts (con respaldo y elevación)."""
    if base not in ("semilla", "fusionada"):
        base = "semilla"
    try:
        dominios = hosts_blocker.cargar_dominios(rutas_base_dominios(base))
        if not dominios:
            return ResultadoModulo(False, "No se encontró la base de dominios.")
        texto = tuneup_win.leer_hosts()
        nuevo = hosts_blocker.aplicar_bloque(texto, dominios)
        if not tuneup_win.escribir_hosts_elevado(nuevo, config.ruta_respaldos()):
            return ResultadoModulo(
                False, "Windows no confirmó la escritura del archivo hosts. "
                       "Acepta el aviso de administrador e inténtalo de nuevo.")
        _guardar_estado_local({"base": base, "pausado": False})
        estado = estado_hosts()
        nombre_base = "fusionada" if base == "fusionada" else "semilla"
        return ResultadoModulo(
            True,
            f"Bloqueo activado: {estado.dominios_bloqueados} dominios bloqueados "
            f"con la base {nombre_base}.",
            datos=estado)
    except Exception as exc:
        return ResultadoModulo(False, f"No se pudo activar el bloqueo: {exc}",
                               detalle_tecnico=repr(exc))


def quitar_hosts() -> ResultadoModulo:
    """Quita SOLO el bloque de la app; el resto del hosts queda intacto."""
    try:
        texto = tuneup_win.leer_hosts()
        if not hosts_blocker.bloque_activo(texto):
            return ResultadoModulo(True, "El bloqueo ya estaba desactivado.",
                                   datos=estado_hosts())
        nuevo = hosts_blocker.quitar_bloque(texto)
        if not tuneup_win.escribir_hosts_elevado(nuevo, config.ruta_respaldos()):
            return ResultadoModulo(False, "Windows no confirmó la escritura del archivo hosts.")
        _guardar_estado_local({"base": _leer_estado_local().get("base", "semilla"),
                               "pausado": False})
        return ResultadoModulo(True, "Bloqueo quitado. El archivo hosts quedó como estaba.",
                               datos=estado_hosts())
    except Exception as exc:
        return ResultadoModulo(False, f"No se pudo quitar el bloqueo: {exc}",
                               detalle_tecnico=repr(exc))


def pausar_hosts() -> ResultadoModulo:
    """Pausa = quitar el bloque recordando la base para poder reanudar."""
    local = _leer_estado_local()
    resultado = quitar_hosts()
    if resultado.ok:
        _guardar_estado_local({"base": local.get("base", "semilla"), "pausado": True})
        resultado.mensaje = ("Bloqueo en pausa. Pulsa «Reanudar el bloqueo» "
                             "cuando quieras volver a activarlo.")
        if resultado.datos is not None:
            resultado.datos = estado_hosts()
    return resultado


def reanudar_hosts() -> ResultadoModulo:
    local = _leer_estado_local()
    return activar_hosts(local.get("base", "semilla"))


def esta_pausado() -> bool:
    return bool(_leer_estado_local().get("pausado", False))


def restaurar_respaldo_hosts() -> ResultadoModulo:
    """Vuelve a poner la última copia del hosts guardada antes de un cambio."""
    respaldo = _ultimo_respaldo_hosts()
    if not respaldo:
        return ResultadoModulo(False, "Todavía no hay ninguna copia del archivo hosts.")
    try:
        with open(respaldo, "r", encoding="utf-8", errors="replace") as f:
            texto = f.read()
        if not tuneup_win.escribir_hosts_elevado(texto, config.ruta_respaldos()):
            return ResultadoModulo(False, "Windows no confirmó la escritura del archivo hosts.")
        _guardar_estado_local({"base": "semilla", "pausado": False})
        return ResultadoModulo(
            True, f"Copia restaurada: {os.path.basename(respaldo)}.",
            datos=estado_hosts())
    except Exception as exc:
        return ResultadoModulo(False, f"No se pudo restaurar la copia: {exc}",
                               detalle_tecnico=repr(exc))


# ---------------------------------------------------------------------------
# Protección al instalar (modo usuario, honesta)
# ---------------------------------------------------------------------------

def _ruta_foto_programas() -> str:
    return os.path.join(config.carpeta_datos(), "foto_programas.json")


def _ruta_ejecutables_conocidos() -> str:
    return os.path.join(config.carpeta_datos(), "ejecutables_conocidos.json")


def _cargar_foto() -> dict[str, ProgramaInstalado] | None:
    ruta = _ruta_foto_programas()
    if not os.path.isfile(ruta):
        return None
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return {k: ProgramaInstalado(**v) for k, v in datos.items()}
    except (OSError, ValueError, TypeError):
        return None


def _guardar_foto(programas: dict[str, ProgramaInstalado]) -> None:
    with open(_ruta_foto_programas(), "w", encoding="utf-8") as f:
        json.dump({k: asdict(v) for k, v in programas.items()}, f,
                  ensure_ascii=False, indent=1)


def _cargar_conocidos() -> set[str] | None:
    ruta = _ruta_ejecutables_conocidos()
    if not os.path.isfile(ruta):
        return None
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return None


def _guardar_conocidos(conocidos: set[str]) -> None:
    with open(_ruta_ejecutables_conocidos(), "w", encoding="utf-8") as f:
        json.dump(sorted(conocidos), f, ensure_ascii=False, indent=1)


def _revisar_carpeta_programa(carpeta: str, base: BaseFirmas,
                              tope: int = 200) -> list[Hallazgo]:
    """Contrasta los ejecutables de primer nivel de la carpeta de un
    programa recién instalado contra la base de huellas."""
    hallazgos: list[Hallazgo] = []
    if not carpeta or not os.path.isdir(carpeta):
        return hallazgos
    revisados = 0
    for nombre in sorted(os.listdir(carpeta)):
        if revisados >= tope:
            break
        ruta = os.path.join(carpeta, nombre)
        if not os.path.isfile(ruta):
            continue
        if os.path.splitext(nombre)[1].lower() not in EXTENSIONES_EJECUTABLES:
            continue
        revisados += 1
        try:
            hallazgo = analizar_archivo(ruta, base)
        except OSError:
            continue
        if hallazgo:
            hallazgos.append(hallazgo)
    return hallazgos


def revisar_instalaciones(base: BaseFirmas,
                          carpetas_vigiladas: list[str]) -> ResultadoModulo:
    """Revisión bajo demanda: foto de programas instalados (diff) +
    ejecutables nuevos en las carpetas vigiladas, todo contrastado con la
    base. La foto se actualiza al terminar: la próxima revisión solo
    mostrará lo nuevo desde esta.

    datos: {primera_vez, programas_nuevos, programas_eliminados,
            ejecutables_nuevos, hallazgos}
    """
    datos = {
        "primera_vez": False,
        "programas_nuevos": [],
        "programas_eliminados": [],
        "ejecutables_nuevos": [],
        "hallazgos": [],
    }
    try:
        # --- ejecutables nuevos en Descargas / Escritorio / Temp ----------
        conocidos = _cargar_conocidos()
        primera_vez = conocidos is None
        conocidos = conocidos or set()
        actuales: set[str] = set(conocidos)
        nuevos_ejecutables: list[str] = []
        for carpeta in carpetas_vigiladas:
            for ruta in ejecutables_nuevos(carpeta, conocidos, EXTENSIONES_EJECUTABLES):
                nuevos_ejecutables.append(ruta)
                actuales.add(ruta)
            if os.path.isdir(carpeta):
                for nombre in os.listdir(carpeta):
                    ruta = os.path.join(carpeta, nombre)
                    if (os.path.isfile(ruta)
                            and os.path.splitext(nombre)[1].lower() in EXTENSIONES_EJECUTABLES):
                        actuales.add(ruta)
        _guardar_conocidos(actuales)
        if not primera_vez:
            datos["ejecutables_nuevos"] = sorted(nuevos_ejecutables)

        # --- programas instalados (solo Windows: claves Uninstall) ---------
        if es_windows():
            foto_anterior = _cargar_foto()
            foto_actual = system_info.programas_instalados()
            if foto_anterior is None:
                primera_vez = True
            else:
                nuevos, eliminados, _actualizados = diff_programas(foto_anterior, foto_actual)
                datos["programas_nuevos"] = nuevos
                datos["programas_eliminados"] = eliminados
            _guardar_foto(foto_actual)

        datos["primera_vez"] = primera_vez

        # --- contraste con la base de huellas -------------------------------
        hallazgos: list[Hallazgo] = []
        for ruta in datos["ejecutables_nuevos"]:
            try:
                hallazgo = analizar_archivo(ruta, base)
            except OSError:
                continue
            if hallazgo:
                hallazgos.append(hallazgo)
        for programa in datos["programas_nuevos"]:
            hallazgos += _revisar_carpeta_programa(programa.carpeta, base)
        datos["hallazgos"] = hallazgos

        if primera_vez and not hallazgos:
            mensaje = ("Primera revisión: se guardó la foto de referencia. "
                       "A partir de ahora se avisará de lo nuevo que aparezca.")
        elif hallazgos:
            mensaje = (f"Atención: {len(hallazgos)} archivo(s) coinciden con la base "
                       "de malware conocido. Decide tú qué hacer con cada uno.")
        elif datos["programas_nuevos"] or datos["ejecutables_nuevos"]:
            mensaje = ("Hay novedades (programas o archivos nuevos) y ninguno "
                       "coincide con la base de malware conocido.")
        else:
            mensaje = "Sin novedades desde la última revisión y nada sospechoso."
        return ResultadoModulo(True, mensaje, datos=datos)
    except Exception as exc:
        return ResultadoModulo(False, f"No se pudo completar la revisión: {exc}",
                               detalle_tecnico=repr(exc))


# ---------------------------------------------------------------------------
# Informe de privacidad / persistencia
# ---------------------------------------------------------------------------

def generar_informe() -> ResultadoModulo:
    """datos: {programas, arranque, tareas, servicios} tal como los da winapi."""
    if not es_windows():
        return ResultadoModulo(
            False, "El informe lee el registro y los servicios de Windows: "
                   "disponible solo en Windows.")
    try:
        datos = {
            "programas": system_info.programas_instalados(),
            "arranque": system_info.elementos_arranque(),
            "tareas": system_info.tareas_programadas(),
            "servicios": system_info.servicios_terceros(),
        }
        n_sospechosas = sum(1 for t in datos["tareas"] if t.get("sospechosa"))
        mensaje = (
            f"Informe listo: {len(datos['programas'])} programas instalados, "
            f"{len(datos['arranque'])} elementos de arranque, "
            f"{len(datos['tareas'])} tareas programadas"
            + (f" ({n_sospechosas} marcadas para revisar)" if n_sospechosas else "")
            + f" y {len(datos['servicios'])} servicios de terceros."
        )
        return ResultadoModulo(True, mensaje, datos=datos)
    except Exception as exc:
        return ResultadoModulo(False, f"No se pudo generar el informe: {exc}",
                               detalle_tecnico=repr(exc))


def texto_informe(datos: dict) -> str:
    """El informe en texto llano, listo para enseñar y para guardar."""
    from .hashing import tamano_legible

    lineas = [
        "ANTIVIRUS HOGAR PC — INFORME DE PRIVACIDAD Y PERSISTENCIA",
        f"Generado: {time.strftime('%d/%m/%Y %H:%M')}",
        "",
        "Esto es información para que TÚ decidas: la app no borra ni desactiva",
        "nada por su cuenta. Lo marcado como «revisar» es una heurística simple,",
        "no un veredicto.",
        "",
    ]
    programas: dict[str, ProgramaInstalado] = datos.get("programas", {})
    lineas.append(f"== PROGRAMAS INSTALADOS ({len(programas)}) ==")
    for p in sorted(programas.values(), key=lambda x: x.nombre.lower()):
        extra = []
        if p.editor:
            extra.append(p.editor)
        if p.version:
            extra.append(f"v{p.version}")
        if p.tamano_kb:
            extra.append(tamano_legible(p.tamano_kb * 1024))
        if p.fecha_instalacion:
            extra.append(f"instalado: {p.fecha_instalacion}")
        lineas.append(f"- {p.nombre}" + (f" ({', '.join(extra)})" if extra else ""))
    lineas.append("")

    arranque = datos.get("arranque", [])
    lineas.append(f"== ARRANQUE CON WINDOWS ({len(arranque)}) ==")
    lineas.append("Claves Run/RunOnce, carpeta de inicio y registro:")
    for e in arranque:
        lineas.append(f"- {e.get('nombre', '')}: {e.get('comando', '')} "
                      f"[{e.get('ubicacion', '')}]")
    lineas.append("")

    tareas = datos.get("tareas", [])
    sospechosas = [t for t in tareas if t.get("sospechosa")]
    lineas.append(f"== TAREAS PROGRAMADAS ({len(tareas)}, {len(sospechosas)} para revisar) ==")
    for t in sospechosas:
        lineas.append(f"- REVISAR: {t.get('nombre', '')} — {t.get('motivo_sospecha', '')}")
        lineas.append(f"  Acción: {t.get('accion', '')}")
    for t in tareas:
        if not t.get("sospechosa"):
            lineas.append(f"- {t.get('nombre', '')} [{t.get('ruta', '')}]")
    lineas.append("")

    servicios = datos.get("servicios", [])
    lineas.append(f"== SERVICIOS DE TERCEROS EN AUTOMÁTICO ({len(servicios)}) ==")
    for s in servicios:
        lineas.append(f"- {s.get('nombre', '')} ({s.get('estado', '')}): {s.get('ruta', '')}")
    lineas.append("")
    return "\n".join(lineas)


def guardar_informe(texto: str, ruta: str = "") -> str:
    """Guarda el informe; por defecto en la carpeta de informes de la app."""
    if not ruta:
        marca = time.strftime("%Y%m%d-%H%M%S")
        ruta = os.path.join(config.ruta_informes(), f"informe-privacidad-{marca}.txt")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    return ruta
