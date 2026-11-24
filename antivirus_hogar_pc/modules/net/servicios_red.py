"""Operaciones reales del Carril D (red y actualizaciones).

Cada función devuelve contracts.ResultadoModulo: los errores viajan en el
sobre, nunca como excepciones a la UI. Las llamadas a Windows pasan por
winapi y por ui.services.seguro, que traduce «solo Windows» y cualquier
fallo a un mensaje en español llano.
"""
import os
import time

from antivirus_hogar_pc import config
from antivirus_hogar_pc.contracts import ActualizacionWindows, ResultadoModulo
from antivirus_hogar_pc.core import updater
from antivirus_hogar_pc.core.vpngate import (
    ServidorVPN,
    descargar_lista_servidores,
    ordenar_servidores,
    paises_disponibles,
)
from antivirus_hogar_pc.core.wifi_parse import (
    parsear_netsh_wlan,
    parsear_perfiles_guardados,
    valorar_wifi,
)
from antivirus_hogar_pc.ui.services import seguro
from antivirus_hogar_pc.winapi import es_windows, system_info, tuneup_win, vpn_win
from antivirus_hogar_pc.winapi.powershell import ejecutar_comando


def _sobre(res) -> ResultadoModulo:
    """Convierte el Resultado de ui.services.seguro en ResultadoModulo."""
    if res.ok:
        return ResultadoModulo(ok=True, datos=res.datos)
    return ResultadoModulo(ok=False, mensaje=res.mensaje or "No se pudo completar la operación.")


# --- VPN Gate -------------------------------------------------------------------
def descargar_servidores_completos() -> ResultadoModulo:
    """Descarga la lista pública de VPN Gate SIN filtrar ni ordenar.

    datos = lista completa de ServidorVPN. La página la guarda y aplica el
    país/orden en local (core.vpngate.ordenar_servidores) sin re-descargar.
    """
    res = seguro(descargar_lista_servidores, config.VPNGATE_API)
    if not res.ok:
        return ResultadoModulo(
            ok=False,
            mensaje="No se pudo descargar la lista de servidores de VPN Gate. "
                    "Revisa tu conexión a internet e inténtalo de nuevo.",
            detalle_tecnico=res.mensaje,
        )
    servidores: list[ServidorVPN] = res.datos or []
    return ResultadoModulo(
        ok=True,
        mensaje=f"{len(servidores)} servidores disponibles.",
        datos=servidores,
    )


def servidores_vpn(criterio: str = "velocidad", pais: str = "") -> ResultadoModulo:
    """Descarga la lista, la filtra por país y la ordena (atajo de una llamada)."""
    completo = descargar_servidores_completos()
    if not completo.ok:
        return completo
    servidores: list[ServidorVPN] = completo.datos or []
    if pais:
        servidores = [s for s in servidores if s.pais == pais]
    servidores = ordenar_servidores(servidores, criterio)
    return ResultadoModulo(
        ok=True,
        mensaje=f"{len(servidores)} servidores disponibles.",
        datos=servidores,
    )


def lista_paises() -> ResultadoModulo:
    """Países presentes en la lista actual de VPN Gate (para el desplegable)."""
    res = seguro(descargar_lista_servidores, config.VPNGATE_API)
    if not res.ok:
        return ResultadoModulo(ok=False, mensaje=res.mensaje)
    return ResultadoModulo(ok=True, datos=paises_disponibles(res.datos or []))


def conectar_vpn(servidor: ServidorVPN) -> ResultadoModulo:
    """Genera el .ovpn del servidor y lo entrega al cliente VPN instalado.

    La app NO crea el túnel: delega en SoftEther VPN Client (recomendado
    por VPN Gate) u OpenVPN Connect/GUI. Si no hay cliente, el perfil queda
    guardado y se explica qué instalar.
    """
    res_clientes = seguro(vpn_win.clientes_vpn_instalados)
    clientes = res_clientes.datos if res_clientes.ok else []
    nombre = f"vpngate-{servidor.pais_corto or 'xx'}-{servidor.hostname}.ovpn".replace("/", "_")
    res_guardar = seguro(
        vpn_win.guardar_ovpn, servidor.generar_ovpn(), vpn_win.carpeta_perfiles_vpn(), nombre)
    if not res_guardar.ok:
        return ResultadoModulo(
            ok=False, mensaje="No se pudo guardar el perfil de conexión.",
            detalle_tecnico=res_guardar.mensaje)
    ruta = res_guardar.datos
    if not clientes:
        return ResultadoModulo(
            ok=False,
            mensaje=("El perfil quedó guardado, pero no se encontró ningún cliente VPN "
                     "instalado. Instala SoftEther VPN Client (el recomendado por "
                     "VPN Gate) u OpenVPN Connect, y luego abre el perfil desde "
                     f"la carpeta de perfiles:\n{ruta}"),
            datos={"ruta_ovpn": ruta},
        )
    cliente = clientes[0]
    res_abrir = seguro(vpn_win.abrir_perfil_vpn, ruta, cliente["ruta"])
    if res_abrir.ok and res_abrir.datos:
        return ResultadoModulo(
            ok=True,
            mensaje=(f"Perfil entregado a {cliente['nombre']}. Termina la conexión "
                     "en esa aplicación; esta app no crea el túnel."),
            datos={"ruta_ovpn": ruta, "cliente": cliente["nombre"]},
        )
    return ResultadoModulo(
        ok=False,
        mensaje=(f"No se pudo abrir el perfil con {cliente['nombre']}. "
                 f"Ábrelo a mano desde:\n{ruta}"),
        datos={"ruta_ovpn": ruta},
        detalle_tecnico=res_abrir.mensaje,
    )


def ip_publica() -> ResultadoModulo:
    ip = vpn_win.ip_publica_actual()
    if ip:
        return ResultadoModulo(ok=True, datos=ip)
    return ResultadoModulo(ok=False, mensaje="No se pudo consultar tu IP pública.")


# --- Wi-Fi -----------------------------------------------------------------------
def informe_wifi() -> ResultadoModulo:
    """Red actual (netsh wlan show interfaces) + redes guardadas (show profiles).

    datos = {"info": InfoWifi, "nivel": str, "frase": str,
             "perfiles_guardados": list[str], "perfil_red": str}
    """
    res = seguro(system_info.info_wifi)
    if not res.ok:
        return _sobre(res)
    info = parsear_netsh_wlan(res.datos or "")
    nivel, frase = valorar_wifi(info)
    perfiles: list[str] = []
    res_perfiles = seguro(ejecutar_comando, ["netsh", "wlan", "show", "profiles"])
    if res_perfiles.ok:
        _rc, salida, _err = res_perfiles.datos
        perfiles = parsear_perfiles_guardados(salida or "")
    res_categoria = seguro(system_info.perfil_red)
    categoria = res_categoria.datos if res_categoria.ok else ""
    return ResultadoModulo(
        ok=True,
        mensaje=frase,
        datos={
            "info": info,
            "nivel": nivel,
            "frase": frase,
            "perfiles_guardados": perfiles,
            "perfil_red": categoria,
        },
    )


# --- Actualizaciones de Windows ----------------------------------------------------
def actualizaciones_windows() -> ResultadoModulo:
    """Pendientes vía COM Microsoft.Update.Session (winapi.system_info).

    datos = lista de contracts.ActualizacionWindows. Límite honesto: la
    función de winapi no separa las de tipo Driver (Type='Driver'), así que
    `es_driver` queda False; el título de cada una sí se muestra tal cual.
    """
    res = seguro(system_info.actualizaciones_pendientes_windows)
    if not res.ok:
        return _sobre(res)
    lista = [
        ActualizacionWindows(
            titulo=d.get("titulo", ""),
            descargada=bool(d.get("descargada")),
            requiere_reinicio=bool(d.get("reinicio")),
            es_driver=False,
        )
        for d in (res.datos or [])
    ]
    return ResultadoModulo(
        ok=True,
        mensaje=(f"Hay {len(lista)} actualizaciones de Windows pendientes."
                 if lista else "Windows está al día."),
        datos=lista,
    )


def abrir_windows_update() -> ResultadoModulo:
    if not es_windows():
        return ResultadoModulo(ok=False, mensaje="Disponible solo en Windows.")
    try:
        os.startfile("ms-settings:windowsupdate")  # noqa: S606 - ajuste del sistema
        return ResultadoModulo(ok=True, mensaje="Se abrió Windows Update.")
    except OSError as exc:
        return ResultadoModulo(ok=False, mensaje=f"No se pudo abrir Windows Update: {exc}")


# --- Programas (winget) --------------------------------------------------------------
def programas_desactualizados() -> ResultadoModulo:
    """Salida de `winget upgrade` parseada a ProgramaDesactualizado."""
    res = seguro(tuneup_win.programas_desactualizados_winget)
    if not res.ok:
        return _sobre(res)
    lista = res.datos or []
    return ResultadoModulo(
        ok=True,
        mensaje=(f"Hay {len(lista)} programas con actualización disponible."
                 if lista else "Todos los programas están al día."),
        datos=lista,
    )


def actualizar_programa(id_paquete: str, nombre: str = "") -> ResultadoModulo:
    res = seguro(tuneup_win.actualizar_programa_winget, id_paquete)
    if not res.ok:
        return _sobre(res)
    codigo, salida = res.datos
    etiqueta = nombre or id_paquete
    if codigo == 0:
        return ResultadoModulo(ok=True, mensaje=f"«{etiqueta}» se actualizó correctamente.")
    return ResultadoModulo(
        ok=False,
        mensaje=f"No se pudo actualizar «{etiqueta}». Puede que pida confirmación o "
                "que el programa esté abierto; ciérralo e inténtalo de nuevo.",
        detalle_tecnico=salida[-800:] if salida else "",
    )


def actualizar_todo() -> ResultadoModulo:
    """`winget upgrade --all`. La CONFIRMACIÓN la pide la página antes de llamar."""
    res = seguro(tuneup_win.actualizar_todo_winget)
    if not res.ok:
        return _sobre(res)
    codigo, salida = res.datos
    if codigo == 0:
        return ResultadoModulo(ok=True, mensaje="Todos los programas se actualizaron.")
    return ResultadoModulo(
        ok=False,
        mensaje="La actualización general terminó con avisos: algún programa no "
                "se pudo actualizar. Vuelve a buscar para ver cuáles quedan.",
        detalle_tecnico=salida[-800:] if salida else "",
    )


# --- Auto-actualización de la propia app ------------------------------------------------
def comprobar_actualizacion_app(ajustes) -> ResultadoModulo:
    """Chequeo contra el version.json del canal de Drive (core.updater).

    datos = InfoActualizacion si hay versión nueva; None si está al día.
    Registra la fecha del chequeo en los ajustes (chequeo mensual como en
    Android: la página lo lanza sola si el último fue hace más de 30 días).
    """
    url = (getattr(ajustes, "url_actualizacion", "") or "").strip()
    ajustes.ultimo_chequeo_actualizacion = time.time()
    try:
        ajustes.guardar()
    except Exception:
        pass
    if not url:
        return ResultadoModulo(
            ok=False,
            mensaje="El canal de actualizaciones aún no está configurado en Ajustes.")
    res = seguro(updater.comprobar_actualizacion, url, config.VERSION)
    if not res.ok:
        return ResultadoModulo(
            ok=False,
            mensaje="No se pudo comprobar si hay una actualización. "
                    "Revisa tu conexión a internet.",
            detalle_tecnico=res.mensaje,
        )
    info = res.datos
    if info is None:
        return ResultadoModulo(
            ok=True, mensaje=f"Estás en la última versión ({config.VERSION}).", datos=None)
    return ResultadoModulo(
        ok=True,
        mensaje=f"Hay una versión nueva: {info.version}.",
        datos=info,
    )


def instalar_actualizacion_app(info) -> ResultadoModulo:
    """Descarga el instalador, VERIFICA su SHA-256 y lo abre.

    Sin huella en el version.json no se instala nada: es la garantía de que
    el archivo es el publicado en el canal. En Windows, SmartScreen avisará
    porque el instalador no lleva firma comercial: es lo esperado.
    """
    if not info.sha256:
        return ResultadoModulo(
            ok=False,
            mensaje="La actualización no trae huella de seguridad (SHA-256) en el "
                    "canal, así que no se instala por precaución.")
    carpeta = os.path.join(config.carpeta_datos(), "actualizaciones")
    destino = os.path.join(carpeta, updater.nombre_instalador(info.url))
    res = seguro(updater.descargar_archivo, info.url, destino)
    if not res.ok:
        return ResultadoModulo(
            ok=False, mensaje="No se pudo descargar la actualización.",
            detalle_tecnico=res.mensaje)
    if not updater.verificar_sha256(destino, info.sha256):
        try:
            os.remove(destino)
        except OSError:
            pass
        return ResultadoModulo(
            ok=False,
            mensaje="El archivo descargado no coincide con la huella de seguridad "
                    "del canal. Se ha borrado y NO se ha instalado nada.")
    if not es_windows():
        return ResultadoModulo(
            ok=False, mensaje="El instalador solo se abre en Windows.",
            datos={"ruta": destino})
    try:
        os.startfile(destino)  # noqa: S606 - instalador verificado por SHA-256
    except OSError as exc:
        return ResultadoModulo(
            ok=False, mensaje=f"Descargado y verificado, pero no se pudo abrir: {exc}",
            datos={"ruta": destino})
    return ResultadoModulo(
        ok=True,
        mensaje="Instalador descargado y verificado. Se ha abierto: sigue sus "
                "pasos y esta versión se cerrará al instalar la nueva.",
        datos={"ruta": destino},
    )
