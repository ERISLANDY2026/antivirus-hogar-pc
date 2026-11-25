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
from antivirus_hogar_pc.core import fuentes_vpn as fuentes
from antivirus_hogar_pc.core.i18n import t
from antivirus_hogar_pc.core import updater
from antivirus_hogar_pc.core.v102 import valorar_velocidad
from antivirus_hogar_pc.core.velocidad import (
    medir_velocidad,
    medir_velocidad_en_vivo,
)
from antivirus_hogar_pc.core.vpngate import (
    ServidorVPN,
    config_estructuralmente_valida,
    descargar_lista_con_respaldo,
    descargar_lista_servidores,
    extraer_remoto,
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


# --- VPN: lista unificada de fuentes verificadas (v1.0.14) ----------------------
# Estado en memoria de la lista unificada: la última lista buena
# conocida, los veredictos de la sonda/intentos y la contraseña
# VIGENTE de VPNBook (leída de su página en cada refresco; jamás
# escrita en el código). Se carga perezosamente desde la caché
# en disco y se persiste en ella.
_ULTIMA_LISTA: list[ServidorVPN] = []
_VEREDICTOS: dict = {}
_CLAVE_VPNBOOK: str = ""
_ESTADO_FUENTES_CARGADO = False


def _cargar_estado_fuentes() -> None:
    """Carga (una vez) la caché en disco al estado en memoria."""
    global _CLAVE_VPNBOOK, _ESTADO_FUENTES_CARGADO
    if _ESTADO_FUENTES_CARGADO:
        return
    _ESTADO_FUENTES_CARGADO = True
    try:
        cache = fuentes.cargar_cache(config.ruta_cache_fuentes_vpn())
    except Exception:
        cache = None
    if cache:
        _VEREDICTOS.update(cache.get("veredictos") or {})
        if cache.get("clave_vpnbook"):
            _CLAVE_VPNBOOK = str(cache["clave_vpnbook"])
        if not _ULTIMA_LISTA and cache.get("servidores"):
            _ULTIMA_LISTA.extend(cache["servidores"])


def _persistir_veredictos() -> None:
    try:
        fuentes.actualizar_veredictos_cache(
            config.ruta_cache_fuentes_vpn(), _VEREDICTOS)
    except Exception:
        pass  # los veredictos nunca rompen la operación que anotan


def _anotar_veredicto(servidor: ServidorVPN, veredicto: str) -> None:
    """Todo intento real y toda sonda dejan su veredicto en el
    MISMO registro (con su hora): es la cola que el failover y
    el orden de la lista leen después."""
    fuentes.registrar_veredicto(_VEREDICTOS, servidor, veredicto)
    _persistir_veredictos()


def _descargar_texto_simple(url: str, timeout: int = 20) -> str:
    import urllib.request

    req = urllib.request.Request(
        url, headers={"User-Agent": "AntivirusHogarPC"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _servidores_vpnbook_en_vivo() -> tuple[list[ServidorVPN], str]:
    """VPNBook en vivo: (servidores, contraseña vigente).

    Lee su página oficial (hostnames + credenciales publicadas)
    y descarga la config de cada servidor de su endpoint
    oficial. Si la config de un servidor falla, entra su config
    de la SEMILLA verificada (las configs apenas cambian; lo
    que rota es la contraseña). Lanza si la página no responde:
    el llamante degrada a la semilla entera.
    """
    html = _descargar_texto_simple(fuentes.VPNBOOK_PAGINA, timeout=25)
    credenciales = fuentes.extraer_credenciales_vpnbook(html)
    hostnames = fuentes.extraer_hostnames_vpnbook(html)
    if not hostnames:
        raise RuntimeError("la página de VPNBook no trajo servidores")
    semilla = {s.hostname: s for s in fuentes.leer_semilla_vpnbook(
        config.carpeta_activos())}
    servidores: list[ServidorVPN] = []
    for hostname in hostnames:
        servidor = None
        try:
            ovpn = _descargar_texto_simple(
                fuentes.url_config_vpnbook(hostname), timeout=20)
            if config_estructuralmente_valida(ovpn):
                servidor = fuentes.servidor_vpnbook(hostname, ovpn)
        except Exception:
            servidor = None
        if servidor is None:
            servidor = semilla.get(hostname)
        if servidor is not None:
            servidores.append(servidor)
    clave = credenciales[1] if credenciales else ""
    return servidores, clave


def descargar_servidores_completos() -> ResultadoModulo:
    """La lista UNIFICADA de las fuentes verificadas (v1.0.14).

    VPN Gate por su cadena de rutas con reintento de siempre
    (config.VPNGATE_APIS, ahora con el espejo de GitHub como
    cuarta ruta) + VPNBook en vivo (página + endpoint oficial).
    Se fusionan deduplicadas y validadas estructuralmente
    (etapa 0: ninguna config sin destino real entra). Si VPN
    Gate cae entero, su parte entra por la SEMILLA con el aviso
    de respaldo de siempre; si VPNBook cae, entra su semilla.
    La lista fusionada buena se guarda como CACHÉ en disco:
    un refresco fallido jamás la toca y la lista nunca queda
    vacía.

    datos = {"servidores": [...], "es_semilla": bool,
             "fecha_semilla": str, "causa": str,
             "veredictos": {...}}. La página guarda la lista y
    aplica país/orden en local sin re-descargar.
    """
    global _CLAVE_VPNBOOK
    _cargar_estado_fuentes()
    # --- VPN Gate (cadena de siempre; costura de las pruebas) ---
    es_semilla = False
    causa_gate = ""
    fecha_semilla = ""
    url_fuente = ""
    try:
        gate, url_fuente = descargar_lista_con_respaldo(config.VPNGATE_APIS)
    except Exception as exc:
        causa_gate = str(exc)
        gate, fecha_semilla = leer_semilla_vpngate(config.carpeta_activos())
        es_semilla = True
    # --- VPNBook en vivo (mejor esfuerzo) ---
    vpnbook: list[ServidorVPN] = []
    vpnbook_en_vivo = False
    try:
        vpnbook, clave_nueva = _servidores_vpnbook_en_vivo()
        vpnbook_en_vivo = bool(vpnbook)
        if clave_nueva:
            _CLAVE_VPNBOOK = clave_nueva
    except Exception:
        vpnbook = []
    if not vpnbook:
        vpnbook = fuentes.leer_semilla_vpnbook(config.carpeta_activos())
    # --- Fusión + etapa 0 ---
    fusion, _descartadas = fuentes.filtrar_validas(
        fuentes.fusionar_listas([gate, vpnbook]))
    if not fusion:
        return ResultadoModulo(
            ok=False,
            mensaje=("No se pudo descargar la lista de servidores. "
                     f"Causa: {causa_gate or 'sin respuesta de las fuentes'} "
                     "Pulsa «Reintentar descarga» para intentarlo otra vez."),
            detalle_tecnico=causa_gate,
        )
    _ULTIMA_LISTA.clear()
    _ULTIMA_LISTA.extend(fusion)
    # La caché solo la escribe un refresco con ALGO en vivo: si
    # todo cayó a semilla, la caché anterior (más fresca) queda.
    if not es_semilla or vpnbook_en_vivo:
        try:
            fuentes.guardar_cache(
                config.ruta_cache_fuentes_vpn(), fusion,
                _VEREDICTOS, _CLAVE_VPNBOOK)
        except Exception:
            pass
    datos = {"servidores": fusion, "es_semilla": es_semilla,
             "fecha_semilla": fecha_semilla, "causa": causa_gate,
             "fuente": url_fuente, "veredictos": dict(_VEREDICTOS),
             "vpnbook": len(vpnbook)}
    if es_semilla:
        return ResultadoModulo(
            ok=True,
            mensaje=(f"Lista de respaldo del {fecha_semilla or 'la versión'} "
                     f"({len(gate)} servidores): no se pudo conectar "
                     f"con VPN Gate ({causa_gate}). Los servidores son "
                     "reales pero pueden haber cambiado; pulsa "
                     "«Reintentar descarga» para la lista en vivo."
                     + (f" Se añaden {len(vpnbook)} servidores de "
                        "VPNBook." if vpnbook else "")),
            datos=datos,
            detalle_tecnico=causa_gate,
        )
    return ResultadoModulo(
        ok=True,
        mensaje=(f"{len(fusion)} servidores · "
                 f"{len(paises_disponibles(fusion))} países · "
                 "Fuente: VPN Gate en vivo"
                 + (f" y VPNBook ({len(vpnbook)} servidores)."
                    if vpnbook else ".")),
        datos=datos,
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


def servidores_cache_o_semilla() -> ResultadoModulo:
    """v1.0.14: el poblado inicial de la página ANTES de la red.

    Primero la CACHÉ buena en disco (la última lista fusionada
    real, con sus veredictos); sin caché, las SEMILLAS fusionadas
    (VPN Gate + VPNBook). La lista jamás nace vacía y los sellos
    de verificación se pintan desde el primer segundo.
    """
    _cargar_estado_fuentes()
    cache = None
    try:
        cache = fuentes.cargar_cache(config.ruta_cache_fuentes_vpn())
    except Exception:
        cache = None
    if cache and cache.get("servidores"):
        servidores = cache["servidores"]
        _ULTIMA_LISTA.clear()
        _ULTIMA_LISTA.extend(servidores)
        return ResultadoModulo(
            ok=True,
            mensaje=(f"Lista guardada de la última búsqueda: "
                     f"{len(servidores)} servidores. "
                     "Buscando la lista en vivo…"),
            datos={"servidores": servidores, "es_semilla": False,
                   "es_cache": True, "fecha_semilla": "", "causa": "",
                   "veredictos": cache.get("veredictos") or {}},
        )
    semilla_gate, fecha = leer_semilla_vpngate(config.carpeta_activos())
    fusion, _desc = fuentes.filtrar_validas(fuentes.fusionar_listas(
        [semilla_gate,
         fuentes.leer_semilla_vpnbook(config.carpeta_activos())]))
    if not fusion:
        return ResultadoModulo(
            ok=False,
            mensaje=("La lista de respaldo de VPN Gate no está "
                     "disponible en esta instalación."),
            datos={"servidores": [], "es_semilla": True,
                   "fecha_semilla": fecha, "causa": ""},
        )
    _ULTIMA_LISTA.clear()
    _ULTIMA_LISTA.extend(fusion)
    return ResultadoModulo(
        ok=True,
        mensaje=(f"Lista de respaldo del {fecha or 'la versión'}: "
                 f"{len(fusion)} servidores (VPN Gate y VPNBook)."),
        datos={"servidores": fusion, "es_semilla": True,
               "fecha_semilla": fecha, "causa": "",
               "veredictos": dict(_VEREDICTOS)},
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


# Tope de intentos de una conexión con failover (el elegido +
# saltos): cada intento puede tardar decenas de segundos; cuatro
# es el equilibrio entre insistir y no dejar al usuario esperando.
_MAX_INTENTOS_FAILOVER = 4


def _intentar_openvpn(servidor: ServidorVPN) -> dict:
    """UN intento con el motor OpenVPN y las credenciales de la
    FUENTE del servidor. Devuelve el dict crudo del motor."""
    usuario, clave = fuentes.credenciales_de(servidor, _CLAVE_VPNBOOK)
    res = seguro(vpn_win.conectar_openvpn,
                 servidor.generar_ovpn(), servidor.hostname,
                 usuario=usuario, clave=clave)
    if res.ok and isinstance(res.datos, dict):
        return res.datos
    return {"ok": False,
            "mensaje": res.mensaje or "No se pudo conectar con OpenVPN.",
            "detalle": "", "datos": {"familia": "local"}}


def conectar_vpn(servidor: ServidorVPN,
                 candidatos: list[ServidorVPN] | None = None) -> ResultadoModulo:
    """Conecta con el servidor elegido, con FAILOVER (v1.0.14).

    v1.0.10 (cambio de motor): si OpenVPN está en el equipo (el
    INCORPORADO que instala la propia app, o uno que el usuario ya
    tuviera), la app levanta el túnel ELLA con el perfil .ovpn del
    servidor, en segundo plano y sin abrir ninguna ventana de
    OpenVPN; el resultado trae datos["conectado"]=True cuando el
    túnel quedó confirmado, para que el botón se ponga verde.

    v1.0.14 (investigación A): si el servidor elegido RECHAZA la
    conexión desde su lado (autenticación, saturación, TLS, sin
    respuesta…), la app lo marca con su veredicto y salta SOLA
    al siguiente candidato —verificados primero, luego pocas
    sesiones y más tiempo en línea— hasta conectar o agotar los
    intentos. Los fallos LOCALES (tarjeta, permisos, otro
    OpenVPN) no saltan: no los arregla otro servidor. El mensaje
    final, si ninguno acepta, lo dice tal cual: los servidores
    probados están llenos o fuera de servicio; jamás se culpa a
    la credencial, que es la correcta de cada fuente. Todo
    intento deja su veredicto en el registro compartido con la
    sonda.

    Respaldo (sin OpenVPN): se genera el .ovpn y se entrega al
    cliente VPN instalado; si no hay ninguno, el perfil queda
    guardado y se explica qué instalar.
    """
    _cargar_estado_fuentes()
    res_ov = seguro(vpn_win.openvpn_instalado)
    if res_ov.ok and res_ov.datos:
        base = list(candidatos) if candidatos else list(_ULTIMA_LISTA)
        cola = [servidor] + [
            s for s in fuentes.ordenar_candidatos(
                [s for s in base if s.hostname != servidor.hostname],
                _VEREDICTOS)]
        intentos: list[dict] = []
        ultimo: tuple[ServidorVPN, dict] | None = None
        for candidato in cola[:_MAX_INTENTOS_FAILOVER]:
            datos_ov = _intentar_openvpn(candidato)
            if datos_ov.get("ok"):
                _anotar_veredicto(candidato, "verificado")
                _guardar_estado_vpn(candidato, via="openvpn")
                _registrar_intento_vpn(
                    f"VPN: conectado a {candidato.hostname} "
                    f"({candidato.pais}) con OpenVPN.")
                # v1.0.12: si la puerta previa dejó un aviso (p. ej.
                # cierre de sesión pendiente o reserva elevada), el
                # usuario lo lee junto al «Conectado».
                aviso = str(datos_ov.get("detalle") or "").strip()
                nota_salto = ""
                if candidato.hostname != servidor.hostname:
                    nota_salto = t(
                        " El servidor {host} no aceptó la conexión "
                        "(lleno o fuera de servicio); la app probó "
                        "con el siguiente y conectó con este.",
                        host=servidor.hostname)
                return ResultadoModulo(
                    ok=True,
                    mensaje=(t("Conectado a {host} ({pais}) con "
                               "OpenVPN: el túnel está arriba y "
                               "trabaja en segundo plano, sin que "
                               "tengas que abrir ningún otro programa.",
                               host=candidato.hostname,
                               pais=candidato.pais)
                             + nota_salto
                             + (t(" Aviso: {aviso}", aviso=aviso)
                                if aviso else "")),
                    datos={"via": "openvpn", "conectado": True,
                           "hostname": candidato.hostname,
                           "intentos": intentos,
                           "veredictos": dict(_VEREDICTOS)},
                )
            mensaje_fallo = (datos_ov.get("mensaje") or
                             t("No se pudo conectar con OpenVPN."))
            detalle_fallo = datos_ov.get("detalle") or ""
            datos_motor = datos_ov.get("datos") or {}
            familia = str(datos_motor.get("familia") or "")
            ultimas = str(datos_motor.get("ultimas_lineas") or "")
            _registrar_intento_vpn(
                f"VPN: no se pudo conectar a {candidato.hostname} "
                f"({candidato.pais}): {mensaje_fallo}"
                + (f" Detalle técnico: {detalle_fallo}"
                   if detalle_fallo else "")
                + (f" Últimas líneas del registro de OpenVPN:\n{ultimas}"
                   if ultimas and ultimas not in detalle_fallo else ""))
            veredicto = fuentes.VEREDICTO_POR_FAMILIA.get(familia)
            if veredicto:
                _anotar_veredicto(candidato, veredicto)
            intentos.append({"hostname": candidato.hostname,
                             "familia": familia})
            ultimo = (candidato, datos_ov)
            if familia not in fuentes.FAMILIAS_SERVIDOR:
                break  # fallo local: otro servidor no lo arregla
        # --- desenlace: nadie conectó ---
        if ultimo is None:
            return ResultadoModulo(
                ok=False, mensaje=t(t("No se pudo conectar con OpenVPN.")),
                datos={"intentos": intentos,
                       "veredictos": dict(_VEREDICTOS)})
        _cand, datos_ov = ultimo
        mensaje_fallo = (datos_ov.get("mensaje") or
                         t("No se pudo conectar con OpenVPN."))
        detalle_fallo = datos_ov.get("detalle") or ""
        if (len(intentos) > 1 and all(
                i["familia"] in fuentes.FAMILIAS_SERVIDOR
                for i in intentos)):
            return ResultadoModulo(
                ok=False,
                mensaje=t("Ningún servidor aceptó la conexión: se "
                          "probaron {n} servidores y todos están "
                          "llenos o fuera de servicio en este "
                          "momento. No es tu conexión ni tu "
                          "credencial: es el estado de los servidores "
                          "gratuitos. Espera unos minutos o elige "
                          "otro país y vuelve a intentarlo.",
                          n=len(intentos)),
                detalle_tecnico=detalle_fallo,
                datos={"intentos": intentos,
                       "veredictos": dict(_VEREDICTOS)},
            )
        return ResultadoModulo(
            ok=False,
            mensaje=mensaje_fallo,
            detalle_tecnico=detalle_fallo,
            datos={"intentos": intentos,
                   "veredictos": dict(_VEREDICTOS)},
        )
    res_clientes = seguro(vpn_win.clientes_vpn_instalados)
    clientes = res_clientes.datos if res_clientes.ok else []
    nombre = f"vpngate-{servidor.pais_corto or 'xx'}-{servidor.hostname}.ovpn".replace("/", "_")
    res_guardar = seguro(
        vpn_win.guardar_ovpn, servidor.generar_ovpn(), vpn_win.carpeta_perfiles_vpn(), nombre)
    if not res_guardar.ok:
        return ResultadoModulo(
            ok=False, mensaje=t("No se pudo guardar el perfil de conexión."),
            detalle_tecnico=res_guardar.mensaje)
    ruta = res_guardar.datos
    if not clientes:
        return ResultadoModulo(
            ok=False,
            mensaje=t("El perfil quedó guardado, pero no se encontró "
                      "ningún cliente VPN instalado. Instala OpenVPN "
                      "(el de la comunidad, el que trae esta app) u "
                      "OpenVPN Connect, y luego abre el perfil desde "
                      "la carpeta de perfiles:\n{ruta}", ruta=ruta),
            datos={"ruta_ovpn": ruta},
        )
    cliente = clientes[0]
    res_abrir = seguro(vpn_win.abrir_perfil_vpn, ruta, cliente["ruta"])
    if res_abrir.ok and res_abrir.datos:
        _guardar_estado_vpn(servidor)
        return ResultadoModulo(
            ok=True,
            mensaje=t("Perfil entregado a {nombre}. Termina la "
                      "conexión en esa aplicación; esta app no crea "
                      "el túnel.", nombre=cliente['nombre']),
            datos={"ruta_ovpn": ruta, "cliente": cliente["nombre"]},
        )
    return ResultadoModulo(
        ok=False,
        mensaje=t("No se pudo abrir el perfil con {nombre}. "
                  "Ábrelo a mano desde:\n{ruta}",
                  nombre=cliente['nombre'], ruta=ruta),
        datos={"ruta_ovpn": ruta},
        detalle_tecnico=res_abrir.mensaje,
    )


def ip_publica() -> ResultadoModulo:
    ip = vpn_win.ip_publica_actual()
    if ip:
        return ResultadoModulo(ok=True, datos=ip)
    return ResultadoModulo(ok=False, mensaje="No se pudo consultar tu IP pública.")


# --- Refresco de fuentes y autoanálisis en segundo plano (v1.0.14) --------------
def _alcanzable_tcp(host: str, puerto: int, timeout: float = 3.0) -> bool:
    """Etapa 1 del autoanálisis: el puerto TCP responde. Solo
    filtra muertos evidentes; JAMÁS verifica un servidor (eso lo
    hace la sonda real)."""
    import socket

    try:
        with socket.create_connection((host, int(puerto)),
                                      timeout=timeout):
            return True
    except Exception:
        return False


def _ocupado_vpn() -> bool:
    """¿Hay un túnel puesto o un intento (del usuario o de la
    sonda) en curso? La sonda se difiere: una sola TAP."""
    try:
        estado = vpn_win.estado_openvpn()
        if estado.get("conectado") or estado.get("conectando"):
            return True
    except Exception:
        pass
    try:
        return bool(vpn_win.hay_tunel_openvpn())
    except Exception:
        return False


def _sondear_plan(plan: list[ServidorVPN],
                  presupuesto_s: float = 180.0) -> int:
    """Ejecuta las sondas del plan, UNA a una, con presupuesto.

    Etapa 1 (solo perfiles TCP): alcanzabilidad de 3 s. Etapa 2:
    la sonda REAL — OpenVPN hasta la aceptación del servidor
    (PUSH_REPLY / CONNECTED,SUCCESS) con las credenciales de su
    fuente y perfil route-nopull; tope ~20 s por nodo. Cada
    veredicto queda persistido en la caché. Si aparece un túnel
    o un intento del usuario, la ronda se detiene.
    """
    hechas = 0
    inicio = time.monotonic()
    for servidor in plan:
        if time.monotonic() - inicio > presupuesto_s:
            break
        if _ocupado_vpn():
            break
        remoto = None
        try:
            remoto = extraer_remoto(servidor.generar_ovpn())
        except Exception:
            remoto = None
        if remoto and remoto["proto"] == "tcp":
            if not _alcanzable_tcp(remoto["host"], remoto["puerto"]):
                _anotar_veredicto(servidor, "inaccesible")
                hechas += 1
                continue
        usuario, clave = fuentes.credenciales_de(servidor, _CLAVE_VPNBOOK)
        res = seguro(vpn_win.conectar_openvpn,
                     servidor.generar_ovpn(), servidor.hostname,
                     espera=20, usuario=usuario, clave=clave, sonda=True)
        datos_ov = res.datos if res.ok and isinstance(res.datos, dict) else {}
        if datos_ov.get("ok"):
            _anotar_veredicto(servidor, "verificado")
        else:
            familia = str((datos_ov.get("datos") or {}).get("familia")
                          or "")
            veredicto = fuentes.VEREDICTO_POR_FAMILIA.get(familia)
            if veredicto:
                _anotar_veredicto(servidor, veredicto)
        hechas += 1
    return hechas


def refresco_y_sondas_en_fondo(registrar=None) -> dict:
    """El gancho de arranque de la v1.0.14: refresco + sondas.

    Lo llama la ventana principal en un hilo de fondo al abrir la
    app (el autoarranque en bandeja al iniciar Windows es el
    mismo camino), gemelo del chequeo de OpenVPN: si toca por
    cadencia (~30 min), refresca la lista unificada (la caché
    solo se toca si el refresco es sano) y después corre el
    autoanálisis con su presupuesto sobre los candidatos del
    plan. Todo protegido: un fallo aquí jamás rompe el arranque
    ni deja la lista vacía. Devuelve {"refresco": bool,
    "sondas": n} para las pruebas.
    """
    def _anotar(texto: str) -> None:
        if registrar is not None:
            try:
                registrar("red", texto)
            except Exception:
                pass

    salida = {"refresco": False, "sondas": 0}
    try:
        _cargar_estado_fuentes()
        ruta_estado = config.ruta_estado_fuentes_vpn()
        estado = fuentes.leer_estado_refresco(ruta_estado)
        if fuentes.toca_refrescar(time.time(), estado):
            res = descargar_servidores_completos()
            estado["ultimo_refresco"] = time.time()
            fuentes.guardar_estado_refresco(ruta_estado, estado)
            salida["refresco"] = True
            _anotar(f"Fuentes VPN: refresco al arrancar — {res.mensaje}")
        lista = list(_ULTIMA_LISTA)
        if lista:
            plan = fuentes.plan_sondas(lista, _VEREDICTOS)
            if plan:
                salida["sondas"] = _sondear_plan(plan)
                if salida["sondas"]:
                    _anotar(
                        f"Autoanálisis VPN: {salida['sondas']} "
                        "sonda(s) real(es); los servidores "
                        "verificados mandan en la lista.")
    except Exception as exc:
        _anotar(f"Fuentes VPN: el refresco de fondo falló ({exc}); "
                "se conserva la lista anterior.")
    return salida


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
             "servidor": str, "pais": str}. «conectada» es REAL
    (v1.0.11): SOLO si la interfaz de gestión del motor OpenVPN
    confirma el túnel (CONNECTED,SUCCESS). La 1.0.10 también la
    daba por buena si había «un proceso openvpn» — y contaba la
    GUI y el servicio residente: de ahí el falso «CONECTADA a un
    servidor» de la foto del usuario sin haber conectado nunca.
    El servidor/país salen del último estado guardado.
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
    # v1.0.11: «conectada» SOLO con la confirmación real del motor
    # (CONNECTED,SUCCESS por su interfaz de gestión). Nada de
    # procesos: ni la GUI ni el servicio residente son un túnel.
    res_estado_ov = seguro(vpn_win.estado_openvpn)
    estado_ov = (res_estado_ov.datos
                 if res_estado_ov.ok and isinstance(res_estado_ov.datos, dict)
                 else {})
    conectada_ov = bool(estado_ov.get("conectado"))
    conectada = conectada_ov
    if conectada:
        via = " con OpenVPN" if conectada_ov else ""
        mensaje = t("VPN CONECTADA a {host} ({pais}){via}.",
                    host=guardado.get('hostname') or t('un servidor'),
                    pais=guardado.get('pais') or t('país sin anotar'),
                    via=t(" con OpenVPN") if conectada_ov else "")
    else:
        mensaje = t("VPN desconectada: no hay ningún túnel en marcha. Pulsa «Conectar» en un servidor de la lista: con OpenVPN (incluido) la app levanta el túnel ella misma; sin él, le entrega el perfil a tu cliente VPN.")
    return ResultadoModulo(ok=True, mensaje=mensaje, datos={
        "clientes": nombres, "ip": ip, "conectada": conectada,
        "servidor": guardado.get("hostname", ""), "pais": guardado.get("pais", ""),
        "openvpn": bool(estado_ov.get("instalado")),
        "conectada_openvpn": conectada_ov,
    })


def cancelar_intento_vpn() -> None:
    """Baja un intento de conexión OpenVPN AÚN en curso (v1.0.12).

    Lo llama la página de Red al destruirse (y el motor al salir
    la app): un intento «conectando» jamás se queda vivo sin
    dueño sujetando la tarjeta, como pasó en la 1.0.11. Un túnel
    confirmado no se toca: bajarlo es la orden de desconectar.
    """
    try:
        vpn_win.cerrar_intento_en_curso()
    except Exception:
        pass


def desconectar_vpn() -> ResultadoModulo:
    """Apaga la VPN desde la app.

    La conexión del motor OpenVPN (v1.0.10) se baja por su interfaz
    de gestión (signal SIGTERM). Las conexiones de otros clientes
    OpenVPN (Connect/GUI) no ofrecen un comando de desconexión para
    terceros: terminar su proceso openvpn cierra la conexión al
    momento (winapi.vpn_win.terminar_procesos_openvpn)."""
    # v1.0.10: primero el motor OpenVPN, si su túnel es el que está arriba.
    res_estado_ov = seguro(vpn_win.estado_openvpn)
    estado_ov = (res_estado_ov.datos
                 if res_estado_ov.ok and isinstance(res_estado_ov.datos, dict)
                 else {})
    if estado_ov.get("conectado"):
        res_desc = seguro(vpn_win.desconectar_openvpn)
        datos_desc = (res_desc.datos if res_desc.ok
                      and isinstance(res_desc.datos, dict) else {})
        if datos_desc.get("ok"):
            _borrar_estado_vpn()
            # v1.0.10: si había una actualización de OpenVPN
            # DIFERIDA por el túnel activo, este es su momento: se
            # aplica en segundo plano al cerrarlo.
            def _aplicar_diferida():
                try:
                    from ...core.actividad import RegistroActividad
                    from ...winapi import openvpn_update

                    registro = RegistroActividad(config.ruta_actividad())
                    openvpn_update.aplicar_pendiente(registro.registrar)
                except Exception:
                    pass

            import threading

            threading.Thread(target=_aplicar_diferida,
                             daemon=True).start()
            return ResultadoModulo(
                ok=True,
                mensaje=t("VPN desconectada: OpenVPN bajó el túnel. Tu IP pública volverá a ser la de tu proveedor en unos segundos."))
    res = seguro(vpn_win.terminar_procesos_openvpn)
    cerrados = int(res.datos) if res.ok and res.datos else 0
    habia_estado = bool(_leer_estado_vpn())
    _borrar_estado_vpn()
    if cerrados:
        return ResultadoModulo(
            ok=True,
            mensaje=t("VPN desconectada: se cerró el proceso de OpenVPN ({n} conexión(es)). Tu IP pública volverá a ser la de tu proveedor en unos segundos.", n=cerrados))
    if habia_estado:
        return ResultadoModulo(
            ok=True,
            mensaje=t("No se encontró ningún proceso OpenVPN en marcha (la conexión ya estaba cerrada o la lleva otro cliente VPN, que se desconecta en su propia ventana). El estado guardado quedó limpio: VPN desconectada."))
    return ResultadoModulo(
        ok=False,
        mensaje=("No hay ninguna conexión VPN activa que esta app pueda "
                 "cerrar. Si conectaste con otro cliente VPN (OpenVPN "
                 "GUI o Connect), desconecta desde su ventana."))


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
