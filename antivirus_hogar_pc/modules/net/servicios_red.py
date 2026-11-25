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
from antivirus_hogar_pc.core.v102 import valorar_velocidad
from antivirus_hogar_pc.core.velocidad import (
    medir_velocidad,
    medir_velocidad_en_vivo,
)
from antivirus_hogar_pc.core.vpngate import (
    ServidorVPN,
    descargar_lista_con_respaldo,
    descargar_lista_servidores,
    leer_semilla_vpngate,
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

    v1.0.3 (problema 5): cadena de rutas con reintento
    (core.vpngate.descargar_lista_con_respaldo sobre config.VPNGATE_APIS)
    y, si TODAS fallan, LISTA SEMILLA incluida en la app: la página
    puebla la tabla y el desplegable con la semilla y enseña el aviso
    de respaldo con su fecha y la causa — nunca la lista vacía en
    silencio.

    datos = {"servidores": [...], "es_semilla": bool,
             "fecha_semilla": str, "causa": str}. La página guarda la
    lista y aplica país/orden en local sin re-descargar.
    """
    try:
        servidores, url_fuente = descargar_lista_con_respaldo(config.VPNGATE_APIS)
    except Exception as exc:
        causa = str(exc)
        semilla, fecha = leer_semilla_vpngate(config.carpeta_activos())
        if semilla:
            return ResultadoModulo(
                ok=True,
                mensaje=(f"Lista de respaldo del {fecha or 'la versión'} "
                         f"({len(semilla)} servidores): no se pudo conectar "
                         f"con VPN Gate ({causa}). Los servidores son "
                         "reales pero pueden haber cambiado; pulsa "
                         "«Reintentar descarga» para la lista en vivo."),
                datos={"servidores": semilla, "es_semilla": True,
                       "fecha_semilla": fecha, "causa": causa},
                detalle_tecnico=causa,
            )
        return ResultadoModulo(
            ok=False,
            mensaje=("No se pudo descargar la lista de servidores de VPN Gate. "
                     f"Causa: {causa} "
                     "Pulsa «Reintentar descarga» para intentarlo otra vez."),
            detalle_tecnico=causa,
        )
    return ResultadoModulo(
        ok=True,
        mensaje=(f"{len(servidores)} servidores · "
                 f"{len(paises_disponibles(servidores))} países · "
                 "Fuente: VPN Gate en vivo."),
        datos={"servidores": servidores, "es_semilla": False,
               "fecha_semilla": "", "causa": "", "fuente": url_fuente},
    )


def servidores_semilla() -> ResultadoModulo:
    """La lista SEMILLA local, SIN tocar la red: instantánea.

    v1.0.5: la página la puebla PRIMERO, nada más abrir la sección o
    pulsar el botón, para que el desplegable de países NUNCA quede
    vacío esperando a la red; la descarga en vivo la reemplaza cuando
    llega. Si ni la semilla existiera (instalación dañada), ok=False.
    """
    semilla, fecha = leer_semilla_vpngate(config.carpeta_activos())
    if not semilla:
        return ResultadoModulo(
            ok=False,
            mensaje="La lista de respaldo no está disponible en esta "
                    "instalación.")
    return ResultadoModulo(
        ok=True,
        mensaje=(f"Lista de respaldo del {fecha or 'la versión'}: "
                 f"{len(semilla)} servidores · "
                 f"{len(paises_disponibles(semilla))} países."),
        datos={"servidores": semilla, "es_semilla": True,
               "fecha_semilla": fecha, "causa": ""},
    )


def _servidores_de(datos) -> list[ServidorVPN]:
    """Desempaqueta datos de descargar_servidores_completos (dict v1.0.3;
    se tolera la lista pelada de la v1.0.2 por compatibilidad)."""
    if isinstance(datos, dict):
        return list(datos.get("servidores") or [])
    return list(datos or [])


def servidores_vpn(criterio: str = "velocidad", pais: str = "") -> ResultadoModulo:
    """Descarga la lista, la filtra por país y la ordena (atajo de una llamada)."""
    completo = descargar_servidores_completos()
    if not completo.ok:
        return completo
    servidores = _servidores_de(completo.datos)
    if pais:
        servidores = [s for s in servidores if s.pais == pais]
    servidores = ordenar_servidores(servidores, criterio)
    return ResultadoModulo(
        ok=True,
        mensaje=completo.mensaje,
        datos=servidores,
    )


def lista_paises() -> ResultadoModulo:
    """Países presentes en la lista actual de VPN Gate (para el desplegable)."""
    completo = descargar_servidores_completos()
    if not completo.ok:
        return ResultadoModulo(ok=False, mensaje=completo.mensaje)
    return ResultadoModulo(
        ok=True, datos=paises_disponibles(_servidores_de(completo.datos)))


def _registrar_intento_vpn(detalle: str) -> None:
    """Anota el intento de conexión VPN en actividad.jsonl (v1.0.8).

    Hasta la 1.0.7 la línea real de error de vpncmd viajaba en el
    detalle del resultado y se PERDÍA: nadie la escribía en el
    registro. Desde la 1.0.8 cada intento (conectado o fallido) deja
    su mensaje y su detalle técnico en el registro de actividad.
    """
    try:
        from antivirus_hogar_pc.core.actividad import RegistroActividad

        RegistroActividad(config.ruta_actividad()).registrar(
            "red", detalle)
    except Exception:
        pass  # el registro nunca debe romper la conexión que anota


def conectar_vpn(servidor: ServidorVPN) -> ResultadoModulo:
    """Conecta con el servidor elegido de VPN Gate.

    v1.0.7 (pedido central del usuario): si SoftEther está en el
    equipo (el INCORPORADO que instala la propia app, o uno que el
    usuario ya tuviera), la app crea la conexión y la levanta ELLA
    por vpncmd, en segundo plano y sin abrir la ventana de
    SoftEther; el resultado trae datos["conectado"]=True cuando el
    túnel quedó confirmado, para que el botón se ponga verde.

    Respaldo (sin SoftEther): la vía de siempre — se genera el .ovpn
    y se entrega al cliente VPN instalado; si no hay ninguno, el
    perfil queda guardado y se explica qué instalar.
    """
    res_se = seguro(vpn_win.softether_instalado)
    if res_se.ok and res_se.datos:
        res = seguro(vpn_win.conectar_softether, servidor.hostname)
        datos_se = res.datos if res.ok and isinstance(res.datos, dict) else {}
        if datos_se.get("ok"):
            _guardar_estado_vpn(servidor, via="softether")
            _registrar_intento_vpn(
                f"VPN Gate: conectado a {servidor.hostname} "
                f"({servidor.pais}) con SoftEther.")
            return ResultadoModulo(
                ok=True,
                mensaje=(f"Conectado a {servidor.hostname} "
                         f"({servidor.pais}) con SoftEther: el túnel "
                         "está arriba y trabaja en segundo plano, sin "
                         "que tengas que abrir ningún otro programa."),
                datos={"via": "softether", "conectado": True,
                       "hostname": servidor.hostname},
            )
        mensaje_fallo = (datos_se.get("mensaje") or
                         "No se pudo conectar con SoftEther.")
        detalle_fallo = datos_se.get("detalle") or res.mensaje or ""
        _registrar_intento_vpn(
            f"VPN Gate: no se pudo conectar a {servidor.hostname} "
            f"({servidor.pais}): {mensaje_fallo}"
            + (f" Detalle técnico: {detalle_fallo}"
               if detalle_fallo else ""))
        return ResultadoModulo(
            ok=False,
            mensaje=mensaje_fallo,
            detalle_tecnico=detalle_fallo,
        )
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
        _guardar_estado_vpn(servidor)
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


# --- Velocidad de internet y estado VPN -------------------------------------------
def prueba_velocidad() -> ResultadoModulo:
    """Descarga real contra speed.cloudflare.com (core.velocidad).

    datos = {"ok", "ping_ms", "bajada_mbps", "bytes"} tal como lo devuelve
    medir_velocidad(); el mensaje lleva la valoración en español.
    """
    try:
        datos = medir_velocidad()
    except Exception as exc:  # medir ya captura red; último seguro para la UI
        return ResultadoModulo(
            ok=False, mensaje=f"No se pudo medir la velocidad: {exc}")
    if not datos.get("ok"):
        return ResultadoModulo(
            ok=False,
            mensaje="No se pudo medir la velocidad. Revisa tu conexión a internet.",
            datos=datos)
    bajada = float(datos.get("bajada_mbps") or 0.0)
    ping = datos.get("ping_ms")
    mensaje = (f"Ping: {ping} ms · Bajada: {bajada:.1f} Mbps. "
               f"{valorar_velocidad(bajada)}")
    return ResultadoModulo(ok=True, mensaje=mensaje, datos=datos)


def prueba_velocidad_viva(al_progreso=None) -> ResultadoModulo:
    """Medición EN VIVO (v1.0.5): bajada y subida reales contra
    Cloudflare, con al_progreso(fase, mbps) DURANTE la transferencia.

    datos = {"ping_ms", "bajada_mbps", "subida_mbps"}. Si falla, el
    mensaje es claro («revisa tu conexión») y la causa técnica va en
    detalle_tecnico (visible en el registro), nunca números inventados.
    """
    datos = medir_velocidad_en_vivo(al_progreso)
    if not datos.get("ok"):
        return ResultadoModulo(
            ok=False,
            mensaje=("No se pudo medir la velocidad. Revisa tu conexión "
                     "a internet y vuelve a intentarlo."),
            datos=datos,
            detalle_tecnico=str(datos.get("causa") or ""))
    bajada = float(datos.get("bajada_mbps") or 0.0)
    subida = float(datos.get("subida_mbps") or 0.0)
    ping = datos.get("ping_ms")
    mensaje = (f"Ping: {ping} ms · Bajada: {bajada:.1f} Mbps · "
               f"Subida: {subida:.1f} Mbps. {valorar_velocidad(bajada)}")
    return ResultadoModulo(ok=True, mensaje=mensaje, datos=datos)


# --- Estado de la conexión VPN (v1.0.2): sí/no + desconexión -------------------
def _ruta_estado_vpn() -> str:
    return os.path.join(config.carpeta_datos(), "vpn_estado.json")


def _guardar_estado_vpn(servidor, via: str = "") -> None:
    """Anota a qué servidor se conectó/entregó el perfil y cuándo."""
    import json as _json
    import time as _time

    try:
        with open(_ruta_estado_vpn(), "w", encoding="utf-8") as f:
            _json.dump({
                "hostname": getattr(servidor, "hostname", ""),
                "pais": getattr(servidor, "pais", ""),
                "desde": _time.time(),
                "via": via,
            }, f, ensure_ascii=False)
    except OSError:
        pass


def _leer_estado_vpn() -> dict:
    import json as _json

    try:
        with open(_ruta_estado_vpn(), "r", encoding="utf-8") as f:
            datos = _json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _borrar_estado_vpn() -> None:
    try:
        os.remove(_ruta_estado_vpn())
    except OSError:
        pass


def estado_vpn() -> ResultadoModulo:
    """Estado de la VPN: clientes, IP pública y si hay túnel vivo.

    datos = {"clientes": [nombres], "ip": str, "conectada": bool,
             "servidor": str, "pais": str}. «conectada» es REAL: hay un
    proceso openvpn en marcha (el túnel lo crea el cliente, no la app);
    el servidor/país salen del último perfil que la app entregó.
    """
    res_clientes = seguro(vpn_win.clientes_vpn_instalados)
    clientes_raw = res_clientes.datos if res_clientes.ok else []
    nombres = []
    for cliente in clientes_raw or []:
        if isinstance(cliente, dict):
            nombres.append(str(cliente.get("nombre", "") or "Cliente VPN"))
        else:
            nombres.append(str(cliente))
    res_ip = seguro(vpn_win.ip_publica_actual)
    ip = str(res_ip.datos) if res_ip.ok and res_ip.datos else ""
    guardado = _leer_estado_vpn()
    conectada = bool(seguro(vpn_win.hay_tunel_openvpn).datos)
    # v1.0.7: el túnel de SoftEther (incorporado) también es conexión
    # viva, y su estado lo confirma vpncmd, no un proceso openvpn.
    res_estado_se = seguro(vpn_win.estado_softether)
    estado_se = (res_estado_se.datos
                 if res_estado_se.ok and isinstance(res_estado_se.datos, dict)
                 else {})
    conectada_se = bool(estado_se.get("conectado"))
    conectada = conectada or conectada_se
    if conectada:
        via = " con SoftEther" if conectada_se else ""
        mensaje = (f"VPN CONECTADA a {guardado.get('hostname') or 'un servidor'}"
                   f" ({guardado.get('pais') or 'país sin anotar'}){via}.")
    else:
        mensaje = ("VPN desconectada: no hay ningún túnel en marcha. "
                   "Pulsa «Conectar» en un servidor de la lista: con "
                   "SoftEther (incluido) la app levanta el túnel ella "
                   "misma; sin él, le entrega el perfil a tu cliente VPN.")
    return ResultadoModulo(ok=True, mensaje=mensaje, datos={
        "clientes": nombres, "ip": ip, "conectada": conectada,
        "servidor": guardado.get("hostname", ""), "pais": guardado.get("pais", ""),
        "softether": bool(estado_se.get("instalado")),
        "conectada_softether": conectada_se,
    })


def desconectar_vpn() -> ResultadoModulo:
    """Apaga la VPN desde la app cerrando el proceso openvpn del túnel.

    OpenVPN Connect/GUI no ofrecen un comando de desconexión para
    terceros; terminar su proceso openvpn cierra la conexión al momento
    (winapi.vpn_win.terminar_procesos_openvpn). La conexión de
    SoftEther (v1.0.7) se baja por vpncmd (AccountDisconnect)."""
    # v1.0.7: primero SoftEther, si su túnel es el que está arriba.
    res_estado_se = seguro(vpn_win.estado_softether)
    estado_se = (res_estado_se.datos
                 if res_estado_se.ok and isinstance(res_estado_se.datos, dict)
                 else {})
    if estado_se.get("conectado"):
        res_desc = seguro(vpn_win.desconectar_softether)
        datos_desc = (res_desc.datos if res_desc.ok
                      and isinstance(res_desc.datos, dict) else {})
        if datos_desc.get("ok"):
            _borrar_estado_vpn()
            # v1.0.7, punto 7: si había una actualización de
            # SoftEther DIFERIDA por el túnel activo, este es su
            # momento: se aplica en segundo plano al cerrarlo.
            def _aplicar_diferida():
                try:
                    from ...core.actividad import RegistroActividad
                    from ...winapi import softether_update

                    registro = RegistroActividad(config.ruta_actividad())
                    softether_update.aplicar_pendiente(registro.registrar)
                except Exception:
                    pass

            import threading

            threading.Thread(target=_aplicar_diferida,
                             daemon=True).start()
            return ResultadoModulo(
                ok=True,
                mensaje=("VPN desconectada: SoftEther bajó el túnel. "
                         "Tu IP pública volverá a ser la de tu "
                         "proveedor en unos segundos."))
    res = seguro(vpn_win.terminar_procesos_openvpn)
    cerrados = int(res.datos) if res.ok and res.datos else 0
    habia_estado = bool(_leer_estado_vpn())
    _borrar_estado_vpn()
    if cerrados:
        return ResultadoModulo(
            ok=True,
            mensaje=(f"VPN desconectada: se cerró el proceso de OpenVPN "
                    f"({cerrados} conexión(es)). Tu IP pública volverá a ser "
                    "la de tu proveedor en unos segundos."))
    if habia_estado:
        return ResultadoModulo(
            ok=True,
            mensaje=("No se encontró ningún proceso OpenVPN en marcha (la "
                    "conexión ya estaba cerrada o la lleva SoftEther, que "
                    "se desconecta en su propia ventana). El estado guardado "
                    "quedó limpio: VPN desconectada."))
    return ResultadoModulo(
        ok=False,
        mensaje=("No hay ninguna conexión VPN activa que esta app pueda "
                 "cerrar. Si conectaste con SoftEther VPN Client, "
                 "desconecta desde su ventana."))


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
    # Datos de la conexión local (IP, puerta de enlace, DNS) para el
    # panel de detalles de la Wi-Fi (v1.0.5): se piden de la interfaz
    # Wi-Fi si la hay; si no, de la conexión activa (cable).
    res_red = seguro(system_info.info_red_local, info.nombre)
    red_local = res_red.datos if res_red.ok and isinstance(res_red.datos, dict) \
        else {}
    return ResultadoModulo(
        ok=True,
        mensaje=frase,
        datos={
            "info": info,
            "nivel": nivel,
            "frase": frase,
            "perfiles_guardados": perfiles,
            "perfil_red": categoria,
            "red_local": red_local,
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
    # Mensajes HONESTOS por causa (bug v1.0.1: todo caía en «revisa tu
    # conexión» aunque el fallo era que el archivo de versión no existía).
    try:
        info = updater.comprobar_actualizacion(url, config.VERSION)
    except updater.ErrorActualizacion as exc:
        mensajes = {
            "sin_conexion": (
                "No se pudo conectar con el canal de actualizaciones: parece "
                "que no hay conexión a internet. Revisa tu conexión e "
                "inténtalo de nuevo."),
            "no_encontrado": (
                "El canal de actualizaciones respondió «no encontrado»: el "
                "archivo de versión no está publicado. No es tu conexión: "
                "hay que volver a publicarlo en el canal (avísanos)."),
            "respuesta_invalida": (
                "El canal de actualizaciones respondió, pero su archivo de "
                "versión no es válido. No es tu conexión: hay que corregirlo "
                "en el canal (avísanos)."),
        }
        return ResultadoModulo(
            ok=False,
            mensaje=mensajes.get(exc.tipo, mensajes["sin_conexion"]),
            detalle_tecnico=exc.detalle,
        )
    except Exception as exc:  # último seguro, clasificado como conexión
        return ResultadoModulo(
            ok=False,
            mensaje="No se pudo conectar con el canal de actualizaciones: "
                    "parece que no hay conexión a internet. Revisa tu "
                    "conexión e inténtalo de nuevo.",
            detalle_tecnico=repr(exc),
        )
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
    # v1.0.7: la carpeta se crea aquí también (en la PC real faltaba y
    # el botón fallaba por eso); el descargador además la garantiza.
    os.makedirs(carpeta, exist_ok=True)
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
