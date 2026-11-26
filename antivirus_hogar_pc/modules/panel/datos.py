"""Datos REALES del Panel (Carril A): winapi + psutil → contracts.InformeSalud.

Sin Qt: la página (page.py) llama a esto desde un hilo para no bloquear la
interfaz (la búsqueda COM de actualizaciones puede tardar).

Honestidad fuera de Windows (Linux/CI): las llamadas a winapi lanzan
WindowsNoDisponible; aquí se capturan y los campos quedan en None, así que
core.health los EXCLUYE de la puntuación y la página enseña «no disponible
en este equipo de pruebas». Nunca se inventa una cifra.
"""
import os
import time

try:
    import psutil
except ImportError:  # la app lo declara en requirements.txt; en CI puede faltar
    psutil = None

from antivirus_hogar_pc.contracts import DatosPanel, InformeSalud, ResultadoModulo
from antivirus_hogar_pc.core.health import EstadoSalud, calcular_salud
from antivirus_hogar_pc.winapi import defender as win_defender
from antivirus_hogar_pc.winapi import disks as win_disks
from antivirus_hogar_pc.winapi import es_windows
from antivirus_hogar_pc.winapi import system_info as win_sistema


def _intentar(funcion, errores: list[str], nombre: str):
    """Ejecuta una lectura de Windows; si falla, devuelve None y lo anota."""
    try:
        return funcion()
    except Exception as exc:  # WindowsNoDisponible incluido: degradación honesta
        errores.append(f"{nombre}: {exc}")
        return None


def animaciones_windows_permitidas() -> bool:
    """¿Windows pide reducir animaciones? (SPI_GETANIMATION vía ctypes.)

    Si la lectura no es posible (no Windows, sin ctypes, error), se
    devuelve True: el interruptor de Ajustes manda entonces."""
    if not es_windows():
        return True
    try:
        import ctypes

        class _ANIMATIONINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("iMinAnimate", ctypes.c_int)]

        info = _ANIMATIONINFO()
        info.cbSize = ctypes.sizeof(_ANIMATIONINFO)
        ok = ctypes.windll.user32.SystemParametersInfoW(
            0x0048, info.cbSize, ctypes.byref(info), 0)  # SPI_GETANIMATION
        if ok:
            return info.iMinAnimate != 0
    except Exception:
        pass
    return True


def _raiz_sistema() -> str:
    if os.name == "nt":
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"


def leer_datos_panel() -> DatosPanel:
    """CPU/RAM/disco en vivo con psutil (multiplataforma, lectura rápida)."""
    datos = DatosPanel()
    if psutil is None:
        return datos
    try:
        datos.cpu_pct = float(psutil.cpu_percent(interval=None))
    except Exception:
        pass
    try:
        memoria = psutil.virtual_memory()
        datos.ram_pct = float(memoria.percent)
        datos.ram_usada_gb = round(memoria.used / 1024 ** 3, 1)
        datos.ram_total_gb = round(memoria.total / 1024 ** 3, 1)
    except Exception:
        pass
    try:
        disco = psutil.disk_usage(_raiz_sistema())
        datos.disco_sistema_pct = float(disco.percent)
        datos.disco_libre_gb = round(disco.free / 1024 ** 3, 1)
        datos.disco_total_gb = round(disco.total / 1024 ** 3, 1)
    except Exception:
        pass
    try:
        datos.tiempo_encendido_h = round((time.time() - psutil.boot_time()) / 3600, 1)
    except Exception:
        pass
    return datos


def _disco_sano(discos: list[dict]) -> bool | None:
    """Salud del primer disco con datos SMART; None si ninguno se puede leer."""
    for disco in discos:
        if not disco.get("sin_datos"):
            return bool(disco.get("sano"))
    return None


def recoger_informe(servicios=None) -> ResultadoModulo:
    """Lee el estado real del equipo y lo empaqueta como InformeSalud.

    `servicios` es ui.services.ServiciosApp (o None en pruebas): de ahí sale
    el último escaneo registrado por el módulo Escáner.
    """
    errores: list[str] = []

    defender = _intentar(win_defender.estado_defender, errores, "Defender") or {}
    perfiles = _intentar(win_defender.perfiles_firewall, errores, "Firewall")
    firewall_activo = (
        win_defender.firewall_todo_activo(perfiles) if perfiles else None
    )
    cfa = _intentar(win_defender.estado_cfa, errores, "Protección de carpetas") or {}
    version = _intentar(win_sistema.version_windows, errores, "Versión de Windows") or {}
    pendientes = _intentar(
        win_sistema.actualizaciones_pendientes_windows, errores, "Actualizaciones"
    )
    arranque = _intentar(win_sistema.elementos_arranque, errores, "Arranque")
    discos = _intentar(win_disks.discos_fisicos, errores, "Discos") or []

    # Tendencia de salud del disco (v1.0.16, frente 4): la
    # lectura de hoy alimenta el historial y la tendencia se
    # calcula contra ~30 días atrás (sin historial suficiente,
    # «sin_historial»: la página dirá «historial en
    # construcción», nunca una tendencia inventada).
    tendencia: dict = {}
    try:
        from antivirus_hogar_pc.core import historial_discos

        _hist = historial_discos.registrar_lecturas(
            discos, historial_discos.ruta_historial())
        tendencia = historial_discos.tendencia_principal(discos, _hist)
    except Exception:
        tendencia = {}

    ultimo_escaneo: dict = {}
    if servicios is not None:
        ultimo_escaneo = dict(getattr(servicios, "_ultimo_escaneo", None) or {})

    es_win10 = bool(version.get("es_windows_10"))
    es_win11 = bool(version.get("es_windows_11"))
    estado = EstadoSalud(
        defender_activo=(
            bool(defender.get("activo")) and bool(defender.get("tiempo_real"))
            if defender else None
        ),
        defender_firmas_al_dia=defender.get("firmas_al_dia") if defender else None,
        firewall_activo=firewall_activo,
        windows_al_dia=(len(pendientes) == 0) if pendientes is not None else None,
        windows_con_soporte=(True if es_win11 else False if es_win10 else None),
        cfa_activo=bool(cfa.get("activo")) if cfa else None,
        hallazgos_recientes=(
            int(ultimo_escaneo["hallazgos"]) if ultimo_escaneo else None
        ),
        disco_sano=_disco_sano(discos),
        entradas_arranque=len(arranque) if arranque is not None else None,
    )

    informe = InformeSalud(
        salud=calcular_salud(estado),
        defender=defender,
        firewall_activo=firewall_activo,
        actualizaciones_windows=len(pendientes) if pendientes is not None else None,
        windows_sin_soporte=es_win10,
        cfa=cfa,
        panel=leer_datos_panel(),
        ultimo_escaneo=ultimo_escaneo,
        tendencia_disco=tendencia,
    )

    if not es_windows():
        mensaje = ("Datos de Windows no disponibles en este equipo de pruebas: "
                   "solo se muestra el estado del sistema.")
    elif errores:
        mensaje = "Estado leído, pero alguna comprobación no se pudo completar."
    else:
        mensaje = "Estado del equipo actualizado."
    return ResultadoModulo(
        ok=True,
        mensaje=mensaje,
        datos=informe,
        detalle_tecnico="; ".join(errores),
    )


def recoger_pendientes(servicios, informe: InformeSalud | None = None):
    """Los pendientes de Inicio (v1.0.16, frente 3): junta los
    datos REALES disponibles y delega la decisión en
    core.pendientes. Cada fuente que falla o no existe aporta
    None («sin dato»): su pendiente no se enseña."""
    from antivirus_hogar_pc.core import estado_mantenimiento
    from antivirus_hogar_pc.core.pendientes import calcular_pendientes

    # Último escaneo: el de esta sesión o el último «escaneo»
    # del registro de actividad (la memoria persistente).
    ultimo_escaneo: float | None = None
    if servicios is not None:
        en_sesion = getattr(servicios, "_ultimo_escaneo", None) or {}
        if en_sesion.get("fecha"):
            ultimo_escaneo = float(en_sesion["fecha"])
        actividad = getattr(servicios, "actividad", None)
        if actividad is not None:
            try:
                for entrada in actividad.leer(300):
                    if entrada.tipo == "escaneo":
                        if ultimo_escaneo is None \
                                or entrada.cuando > ultimo_escaneo:
                            ultimo_escaneo = float(entrada.cuando)
                        break
            except Exception:
                pass

    # VPN: servidores de la lista vigente sin veredicto
    # «verificado» vigente (solo si hay lista cargada/caché).
    vpn: dict | None = None
    try:
        from antivirus_hogar_pc.core import fuentes_vpn as fuentes
        from antivirus_hogar_pc.modules.net import servicios_red

        lista_res = servicios_red.servidores_cache_o_semilla()
        lista = lista_res.datos if lista_res.ok else []
        if lista:
            veredictos = servicios_red.veredictos_actuales()
            verificados = sum(
                1 for s in lista
                if fuentes.veredicto_de(veredictos, s)[0] == "verificado")
            vpn = {"total": len(lista), "verificados": verificados}
    except Exception:
        vpn = None

    return calcular_pendientes(
        ultimo_escaneo=ultimo_escaneo,
        revision_drivers=estado_mantenimiento.leer_revision_drivers(),
        ultima_optimizacion=estado_mantenimiento.leer_ultima_optimizacion(),
        actualizaciones_windows=(
            informe.actualizaciones_windows if informe is not None
            else None),
        vpn=vpn,
        tendencia_disco=(
            informe.tendencia_disco if informe is not None else None),
    )
