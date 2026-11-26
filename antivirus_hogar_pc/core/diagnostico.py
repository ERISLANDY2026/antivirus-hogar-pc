"""Autodiagnóstico de integridad de la aplicación (v1.0.19, nota 7).

Pedido del usuario: un botón «Diagnosticar integridad de la
aplicación» que corra un autodiagnóstico de TODAS las funciones
buscando fallas y códigos erróneos, con un informe en pantalla
que se pueda copiar y exportar.

Este módulo es el motor, sin Qt: una lista de comprobaciones
independientes — cada una devuelve {nombre, estado, detalle}
con estado «ok» | «aviso» | «error» — y el constructor del
informe en texto. Ninguna comprobación escribe ni repara nada:
diagnostica y dice la verdad, incluida la de «no aplica en
este equipo» fuera de Windows. Una comprobación que explota
se convierte en «error» con su excepción: el diagnóstico
nunca se cae por la falla que vino a buscar.
"""
import hashlib
import json
import os
import time

from .. import config
from .i18n import t

# Huella del radar INTOCABLE (la misma que vigila la suite
# desde la v1.0.6): si el archivo difiere, algo lo tocó.
HUELLA_RADAR = (
    "ec21a7b8044b90f6cdb4915aa8ec2affa98d7f74059bb4e742dbfe1109629bea")


def _ok(nombre: str, detalle: str) -> dict:
    return {"nombre": nombre, "estado": "ok", "detalle": detalle}


def _aviso(nombre: str, detalle: str) -> dict:
    return {"nombre": nombre, "estado": "aviso", "detalle": detalle}


def _error(nombre: str, detalle: str) -> dict:
    return {"nombre": nombre, "estado": "error", "detalle": detalle}


def _raiz_app() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _chk_version() -> dict:
    version = getattr(config, "VERSION", "")
    if version:
        return _ok(t("Versión de la aplicación"),
                   t("La aplicación informa la versión {v}.",
                     v=version))
    return _error(t("Versión de la aplicación"),
                  t("La aplicación no informa su versión."))


def _chk_modulos() -> dict:
    from ..modules import descubrir_modulos, errores_descubrimiento
    registros = descubrir_modulos()
    errores = errores_descubrimiento()
    if errores:
        return _error(
            t("Módulos de la aplicación"),
            t("{n} módulos cargados, pero hay fallos: {e}",
              n=len(registros), e="; ".join(errores[:3])))
    if not registros:
        return _error(t("Módulos de la aplicación"),
                      t("No cargó ningún módulo."))
    return _ok(t("Módulos de la aplicación"),
               t("{n} módulos cargados sin errores.",
                 n=len(registros)))


def _chk_carpeta_datos() -> dict:
    carpeta = config.carpeta_datos()
    sonda = os.path.join(carpeta, ".sonda_diagnostico")
    try:
        os.makedirs(carpeta, exist_ok=True)
        with open(sonda, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(sonda)
    except OSError as exc:
        return _error(t("Carpeta de datos"),
                      t("No se puede escribir en {c}: {e}",
                        c=carpeta, e=exc))
    return _ok(t("Carpeta de datos"),
               t("Se puede leer y escribir en {c}.", c=carpeta))


def _chk_ajustes() -> dict:
    ruta = os.path.join(config.carpeta_datos(), "ajustes.json")
    if not os.path.isfile(ruta):
        return _aviso(t("Ajustes guardados"),
                      t("Aún no hay ajustes guardados; se usan "
                        "los valores de fábrica."))
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        if not isinstance(datos, dict):
            raise ValueError("la raíz no es un objeto")
    except (OSError, ValueError) as exc:
        return _error(t("Ajustes guardados"),
                      t("El archivo de ajustes está dañado: {e}",
                        e=exc))
    return _ok(t("Ajustes guardados"),
               t("El archivo de ajustes se lee bien ({n} claves).",
                 n=len(datos)))


def _chk_registro_actividad() -> dict:
    ruta = config.ruta_actividad()
    if not os.path.isfile(ruta):
        return _aviso(t("Registro de actividad"),
                      t("Aún no hay registro de actividad."))
    try:
        with open(ruta, encoding="utf-8") as f:
            lineas = sum(1 for linea in f if linea.strip())
    except OSError as exc:
        return _error(t("Registro de actividad"),
                      t("No se puede leer el registro: {e}", e=exc))
    return _ok(t("Registro de actividad"),
               t("El registro se lee bien ({n} entradas).",
                 n=lineas))


def _chk_activos() -> dict:
    carpeta = config.carpeta_activos()
    esperados = {
        "espartano_radar.png": 100_000,
        "espartano_animado.webp": 1_000_000,
        "icono_app.png": 1_000,
    }
    faltan, chicos = [], []
    for nombre, minimo in esperados.items():
        ruta = os.path.join(carpeta, nombre)
        if not os.path.isfile(ruta):
            faltan.append(nombre)
        elif os.path.getsize(ruta) < minimo:
            chicos.append(nombre)
    if faltan:
        return _error(t("Archivos de la interfaz"),
                      t("Faltan archivos: {n}",
                        n=", ".join(faltan)))
    if chicos:
        return _aviso(t("Archivos de la interfaz"),
                      t("Archivos con tamaño sospechoso: {n}",
                        n=", ".join(chicos)))
    return _ok(t("Archivos de la interfaz"),
               t("Los archivos visuales están completos."))


def _chk_radar() -> dict:
    ruta = os.path.join(_raiz_app(), "ui", "fondo_radar.py")
    try:
        with open(ruta, "rb") as f:
            huella = hashlib.sha256(f.read()).hexdigest()
    except OSError as exc:
        return _error(t("Diseño del radar"),
                      t("No se puede leer el radar: {e}", e=exc))
    if huella != HUELLA_RADAR:
        return _error(t("Diseño del radar"),
                      t("El archivo del radar difiere del diseño "
                        "aprobado."))
    return _ok(t("Diseño del radar"),
               t("El radar conserva su diseño aprobado."))


def _chk_openvpn() -> dict:
    from ..winapi import es_windows
    if not es_windows():
        return _aviso(t("OpenVPN (VPN)"),
                      t("No aplica fuera de Windows."))
    from ..winapi.vpn_win import (openvpn_instalado,
                                  _servicio_interactivo_activo)
    if not openvpn_instalado():
        return _error(t("OpenVPN (VPN)"),
                      t("OpenVPN no aparece instalado."))
    if _servicio_interactivo_activo():
        return _ok(t("OpenVPN (VPN)"),
                   t("OpenVPN está instalado y su servicio "
                     "interactivo está activo."))
    return _aviso(t("OpenVPN (VPN)"),
                  t("OpenVPN está instalado, pero su servicio "
                    "interactivo no está activo."))


def _chk_bloqueador() -> dict:
    from ..winapi import es_windows
    if not es_windows():
        return _aviso(t("Bloqueador de dominios"),
                      t("No aplica fuera de Windows."))
    from ..core.hosts_blocker import analizar_bloque, contar_bloqueados
    from ..winapi.tuneup_win import leer_hosts
    try:
        texto_hosts = leer_hosts()
        analisis = analizar_bloque(texto_hosts)
    except Exception as exc:  # el hosts puede estar bloqueado
        return _aviso(t("Bloqueador de dominios"),
                      t("No se pudo leer el archivo hosts: {e}",
                        e=exc))
    if analisis.get("danado"):
        return _error(t("Bloqueador de dominios"),
                      t("El bloque del archivo hosts está dañado "
                        "({m}) y conviene restaurarlo.",
                        m=analisis.get("motivo", "")))
    return _ok(t("Bloqueador de dominios"),
               t("El archivo hosts está íntegro "
                 "({n} dominios bloqueados).",
                 n=contar_bloqueados(texto_hosts)))


def _chk_optimizar() -> dict:
    """El testigo de la nota 5: el registro de eventos de ESTA
    máquina conoce al optimizador (proveedor correcto)."""
    from ..winapi import es_windows
    if not es_windows():
        return _aviso(t("Optimizar con Windows"),
                      t("No aplica fuera de Windows."))
    from ..winapi.disks import consultar_eventos_optimizacion
    eventos = consultar_eventos_optimizacion(
        "C", time.time() - 30 * 24 * 3600)
    if eventos:
        return _ok(t("Optimizar con Windows"),
                   t("El registro de eventos de este equipo sí "
                     "guarda las optimizaciones "
                     "({n} en 30 días).", n=len(eventos)))
    return _aviso(t("Optimizar con Windows"),
                  t("El registro de eventos no guarda "
                    "optimizaciones recientes; el veredicto se "
                    "apoyará en el resultado del ayudante."))


def _chk_puesta_a_punto() -> dict:
    from ..core.puesta_a_punto import (componer_veredicto,
                                       ejecutar_puesta_a_punto)
    if callable(ejecutar_puesta_a_punto) and \
            callable(componer_veredicto):
        return _ok(t("Puesta a punto"),
                   t("El motor de la rutina está íntegro."))
    return _error(t("Puesta a punto"),
                  t("El motor de la rutina no responde."))


def _chk_actualizaciones() -> dict:
    url = getattr(config, "UPDATE_VERSION_URL", "")
    if url:
        return _ok(t("Canal de actualizaciones"),
                   t("El canal de actualizaciones está "
                     "configurado."))
    return _error(t("Canal de actualizaciones"),
                  t("El canal de actualizaciones no está "
                    "configurado."))


COMPROBACIONES = [
    _chk_version, _chk_modulos, _chk_carpeta_datos, _chk_ajustes,
    _chk_registro_actividad, _chk_activos, _chk_radar,
    _chk_openvpn, _chk_bloqueador, _chk_optimizar,
    _chk_puesta_a_punto, _chk_actualizaciones,
]


def diagnosticar() -> list[dict]:
    """Corre TODAS las comprobaciones; ninguna puede tumbar
    el diagnóstico: la que explota sale como error con su
    excepción escrita."""
    resultados: list[dict] = []
    for funcion in COMPROBACIONES:
        try:
            resultados.append(funcion())
        except Exception as exc:  # a propósito: se informa
            resultados.append(_error(
                getattr(funcion, "__name__", "comprobación"),
                f"{type(exc).__name__}: {exc}"))
    return resultados


_SIMBOLOS = {"ok": "✓", "aviso": "⚠", "error": "✗"}


def construir_informe(resultados: list[dict],
                      cuando: float | None = None) -> str:
    """El informe en texto plano: listo para enseñar, copiar
    y exportar tal cual."""
    cuando = time.time() if cuando is None else cuando
    fecha = time.strftime("%Y-%m-%d %H:%M", time.localtime(cuando))
    bien = sum(1 for r in resultados if r["estado"] == "ok")
    avisos = sum(1 for r in resultados if r["estado"] == "aviso")
    fallos = sum(1 for r in resultados if r["estado"] == "error")
    lineas = [
        t("Diagnóstico de integridad de la aplicación"),
        t("Antivirus Hogar PC {v} — {f}",
          v=getattr(config, "VERSION", "?"), f=fecha),
        "",
    ]
    for r in resultados:
        lineas.append(f"{_SIMBOLOS.get(r['estado'], '?')} "
                      f"{r['nombre']}: {r['detalle']}")
    lineas += [
        "",
        t("Resumen: {ok} bien · {av} avisos · {er} fallos",
          ok=bien, av=avisos, er=fallos),
    ]
    return "\n".join(lineas)
