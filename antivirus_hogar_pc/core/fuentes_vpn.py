"""Fuentes VPN verificadas y lista unificada (v1.0.14).

Hasta la 1.0.13 la app solo conocía VPN Gate. La investigación
del 2026-11-25 (INVESTIGACION-AUTH-VPNGATE.md e
INVESTIGACION-FUENTES-VPN-EXTRA.md) cerró dos cosas:

1. El AUTH_FAILED de muchos nodos de VPN Gate NO es un problema
   de credenciales («vpn»/«vpn» es la única pública oficial):
   son nodos llenos o en mantenimiento que siguen anunciados.
   El manejo correcto es failover + priorizar pocas sesiones.
2. La única fuente adicional viable hoy es **VPNBook**: 10
   servidores fijos (US/CA/UK/DE/FR), usuario «vpnbook» y una
   contraseña PUBLICADA en su propia web que rota cada 1–2
   semanas — se lee de su página en cada refresco, NUNCA se
   quema en el binario — y configs descargables de su endpoint
   oficial `https://www.vpnbook.com/api/openvpn?hostname=…&
   protocol=…` (resuelto y verificado en el desarrollo de la
   1.0.14: GET simple, HTTP 200, .ovpn completo con su CA).

Y la revisión de factibilidad (FACTIBILIDAD-ESCANEO-FUENTES.md)
fijó el límite: el registro de fuentes es CERRADO y verificado
por humanos. Crece solo con versiones de la app o con un
archivo de fuentes verificado por huella en el canal de
actualizaciones. Nada de descubrir fuentes en la web abierta:
una config .ovpn de origen no verificado enruta TODO el
tráfico del usuario por un desconocido.

Este módulo es lógica pura (sin Qt ni Windows): raspado de
VPNBook, fusión con deduplicación, validación estructural,
caché en disco de la última lista buena, veredictos de la
sonda real con su caducidad, orden de candidatos y plan de
sondas con presupuesto. La orquestación con red y motor vive
en modules/net/servicios_red.py.
"""
import base64
import json
import os
import re
import time

from .vpngate import (
    ServidorVPN,
    config_estructuralmente_valida,
    extraer_remoto,
)

FUENTE_VPNGATE = "vpngate"
FUENTE_VPNBOOK = "vpnbook"

# Credenciales POR FUENTE. Las de VPN Gate son fijas y públicas.
# Las de VPNBook: usuario fijo «vpnbook» y contraseña VIGENTE
# leída de su página en cada refresco (rota cada 1–2 semanas);
# aquí solo vive el usuario, jamás la contraseña.
USUARIO_VPNGATE = "vpn"
CLAVE_VPNGATE = "vpn"
USUARIO_VPNBOOK = "vpnbook"

VPNBOOK_PAGINA = "https://www.vpnbook.com/freevpn/openvpn"
VPNBOOK_API_CONFIG = "https://www.vpnbook.com/api/openvpn"
# El protocolo de la config que la app pide por servidor de
# VPNBook: TCP 443 (el que mejor atraviesa redes, y el que
# permite la etapa de alcanzabilidad TCP de la sonda).
VPNBOOK_PROTOCOLO = "tcp443"

# Caducidad de los veredictos de la sonda (segundos): un
# «funciona» de hace una hora no garantiza nada (la lista rota
# por horas y los nodos se llenan y se vacían).
CADUCIDAD_VEREDICTO = {
    "verificado": 30 * 60,
    "auth_failed": 15 * 60,
    "inaccesible": 10 * 60,
}

# Familias de fallo del clasificador (winapi.vpn_win) que son
# del SERVIDOR o de su camino — las únicas ante las que el
# failover tiene sentido. Las demás (rutas, tarjeta, opciones,
# detenido, servicio, dco) son de ESTE equipo o de la propia
# app: saltar a otro servidor no las arregla.
FAMILIAS_SERVIDOR = ("credenciales", "saturado", "red", "tls",
                     "sin_respuesta")

# Veredicto que deja cada familia de fallo del servidor.
VEREDICTO_POR_FAMILIA = {
    "credenciales": "auth_failed",
    "saturado": "inaccesible",
    "red": "inaccesible",
    "tls": "inaccesible",
    "sin_respuesta": "inaccesible",
}


# --- VPNBook: raspado de su página oficial -------------------------------------

_PAISES_VPNBOOK = {
    "us": ("United States", "US"),
    "ca": ("Canada", "CA"),
    "uk": ("United Kingdom", "UK"),
    "de": ("Germany", "DE"),
    "fr": ("France", "FR"),
    "pl": ("Poland", "PL"),
}

_RE_CREDENCIALES = re.compile(
    r"Username:\s*([A-Za-z0-9_.\-]+?)\.?\s+Password:\s*([^\s<]+)")
_RE_HOSTNAME = re.compile(r"\b([a-z]{2}\d+\.vpnbook\.com)\b")


def extraer_credenciales_vpnbook(html: str) -> tuple[str, str] | None:
    """(usuario, contraseña) publicados en la página de VPNBook.

    Ancla principal: el bloque de preguntas frecuentes (JSON-LD)
    que trae literalmente «Username: vpnbook. Password: XXXXXX.
    … last changed on …». Devuelve None si no se encuentra: el
    llamante conserva la última contraseña conocida y marca la
    fuente «credencial por confirmar» — la fuente NO desaparece
    de la lista por un raspado fallido.
    """
    m = _RE_CREDENCIALES.search(html or "")
    if not m:
        return None
    # La página escribe «vpnbook.» y «CLAVE.» con el punto de la
    # frase: no forma parte de la credencial.
    return m.group(1).rstrip("."), m.group(2).rstrip(".,;:")


def extraer_hostnames_vpnbook(html: str) -> list[str]:
    """Los hostnames de servidor publicados en la página (sin
    duplicados, en el orden en que aparecen)."""
    vistos: list[str] = []
    for m in _RE_HOSTNAME.finditer(html or ""):
        host = m.group(1)
        if host not in vistos:
            vistos.append(host)
    return vistos


def pais_de_hostname_vpnbook(hostname: str) -> tuple[str, str]:
    """(país, código) por el prefijo del hostname (us16 → US)."""
    prefijo = re.match(r"([a-z]{2})\d+\.vpnbook\.com",
                       hostname or "")
    if prefijo:
        return _PAISES_VPNBOOK.get(prefijo.group(1), ("", ""))
    return "", ""


def servidor_vpnbook(hostname: str, contenido_ovpn: str) -> ServidorVPN:
    """Un ServidorVPN de la fuente VPNBook desde su config.

    La config viaja en el mismo campo Base64 que usa VPN Gate:
    `generar_ovpn()` funciona igual para las dos fuentes.
    Velocidad/ping/sesiones no los publica VPNBook: quedan a 0
    (la sonda y el uso real son los que ordenan estos nodos).
    """
    pais, pais_corto = pais_de_hostname_vpnbook(hostname)
    return ServidorVPN(
        hostname=hostname,
        ip="",
        puntuacion=0,
        ping_ms=9999,
        velocidad_bps=0,
        pais=pais,
        pais_corto=pais_corto,
        sesiones=0,
        uptime=0,
        total_usuarios=0,
        operador="VPNBook",
        mensaje="",
        ovpn_base64=base64.b64encode(
            (contenido_ovpn or "").encode("utf-8")).decode("ascii"),
        fuente=FUENTE_VPNBOOK,
    )


def url_config_vpnbook(hostname: str,
                       protocolo: str = VPNBOOK_PROTOCOLO) -> str:
    """El endpoint oficial de descarga de la config de un servidor.

    Resuelto en el desarrollo de la 1.0.14 inspeccionando el
    selector de la propia web: es un GET simple
    (/api/openvpn?hostname=…&protocol=tcp443|tcp80|udp53|
    udp25000) que devuelve el .ovpn completo.
    """
    return (f"{VPNBOOK_API_CONFIG}?hostname={hostname}"
            f"&protocol={protocolo}")


def leer_semilla_vpnbook(carpeta_activos: str) -> list[ServidorVPN]:
    """Las 10 configs de VPNBook incluidas en la app (respaldo).

    Descargadas del endpoint oficial al construir la versión
    (assets/vpnbook_seed.json), como la semilla de VPN Gate: si
    el endpoint no responde en un refresco, los servidores de
    VPNBook siguen en la lista con estas configs verificadas y
    solo la contraseña se refresca en vivo (es lo que rota).
    La contraseña NO viaja en la semilla: nunca se quema.
    """
    ruta = os.path.join(carpeta_activos, "vpnbook_seed.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        return []
    servidores = []
    for entrada in datos.get("servidores") or []:
        host = str(entrada.get("hostname") or "")
        ovpn = str(entrada.get("ovpn") or "")
        if host and ovpn and config_estructuralmente_valida(ovpn):
            servidores.append(servidor_vpnbook(host, ovpn))
    return servidores


# --- Credenciales por fuente -----------------------------------------------------

def credenciales_de(servidor: ServidorVPN,
                    clave_vpnbook: str = "") -> tuple[str, str]:
    """Las credenciales de conexión SEGÚN LA FUENTE del servidor.

    VPN Gate → («vpn», «vpn»). VPNBook → («vpnbook», la
    contraseña vigente que el refresco leyó de su página; si aún
    no se conoce ninguna, "" — el intento dará AUTH_FAILED, el
    veredicto quedará anotado y el failover saltará: el sistema
    se degrada, no se rompe).
    """
    if getattr(servidor, "fuente", FUENTE_VPNGATE) == FUENTE_VPNBOOK:
        return USUARIO_VPNBOOK, clave_vpnbook or ""
    return USUARIO_VPNGATE, CLAVE_VPNGATE


# --- Fusión, deduplicación y validación -------------------------------------------

def clave_deduplicacion(servidor: ServidorVPN) -> tuple:
    """La identidad de un nodo entre fuentes: su destino real
    (host, puerto, proto) según su config; sin config legible,
    (hostname, ip)."""
    try:
        remoto = extraer_remoto(servidor.generar_ovpn())
    except Exception:
        remoto = None
    if remoto:
        return (remoto["host"].lower(), remoto["puerto"],
                remoto["proto"])
    return ((servidor.hostname or "").lower(),
            (servidor.ip or "").lower(), 0, "")


def fusionar_listas(listas) -> list[ServidorVPN]:
    """Fusiona las listas de las fuentes en UNA, deduplicada.

    El orden de `listas` es el orden de preferencia: ante el
    mismo destino real en dos fuentes, gana la primera (la de
    credencial verificada más fresca, según el llamante).
    """
    salida: list[ServidorVPN] = []
    vistos: set = set()
    for lista in listas or []:
        for servidor in lista or []:
            clave = clave_deduplicacion(servidor)
            if clave in vistos:
                continue
            vistos.add(clave)
            salida.append(servidor)
    return salida


def filtrar_validas(servidores) -> tuple[list[ServidorVPN], int]:
    """Etapa 0 del autoanálisis: solo entran configs con destino
    real (client + remote con puerto y protocolo). Devuelve
    (válidas, descartadas)."""
    validas = []
    descartadas = 0
    for servidor in servidores or []:
        try:
            ok = config_estructuralmente_valida(servidor.generar_ovpn())
        except Exception:
            ok = False
        if ok:
            validas.append(servidor)
        else:
            descartadas += 1
    return validas, descartadas


# --- Veredictos de la sonda --------------------------------------------------------

def clave_servidor(servidor: ServidorVPN) -> str:
    """La clave de un servidor en el registro de veredictos."""
    return f"{getattr(servidor, 'fuente', FUENTE_VPNGATE)}:{servidor.hostname}"


def registrar_veredicto(veredictos: dict, servidor: ServidorVPN,
                        veredicto: str, ahora: float | None = None) -> dict:
    """Anota el veredicto de un servidor con su hora. Devuelve el
    registro actualizado (se muta el dict recibido)."""
    veredictos[clave_servidor(servidor)] = {
        "veredicto": veredicto,
        "cuando": time.time() if ahora is None else ahora,
    }
    return veredictos


def veredicto_de(veredictos: dict, servidor: ServidorVPN,
                 ahora: float | None = None) -> tuple[str, float]:
    """(estado, cuando) de un servidor: el veredicto VIGENTE.

    Estados: «verificado», «auth_failed», «inaccesible» (los
    tres solo si no han caducado) o «sin_verificar». Un
    veredicto caducado se reporta como («caducado:<tipo>» no —
    se reporta «sin_verificar» con la hora del último veredicto,
    para que la UI pueda decir «verificado a las 09:12, ya
    caducado» si quiere; el ORDEN lo decide rango_veredicto).
    """
    ahora = time.time() if ahora is None else ahora
    entrada = (veredictos or {}).get(clave_servidor(servidor))
    if not isinstance(entrada, dict):
        return "sin_verificar", 0.0
    tipo = str(entrada.get("veredicto") or "")
    cuando = float(entrada.get("cuando") or 0.0)
    caducidad = CADUCIDAD_VEREDICTO.get(tipo)
    if caducidad is None:
        return "sin_verificar", cuando
    if ahora - cuando <= caducidad:
        return tipo, cuando
    return "sin_verificar", cuando


def rango_veredicto(veredictos: dict, servidor: ServidorVPN,
                    ahora: float | None = None) -> int:
    """El rango de un servidor para ordenar candidatos:
    0 = verificado vigente · 1 = sin verificar ·
    2 = veredicto caducado (fue bueno o malo, ya no manda) ·
    3 = rechazado vigente (lleno/sin acceso: el último)."""
    ahora = time.time() if ahora is None else ahora
    entrada = (veredictos or {}).get(clave_servidor(servidor))
    if not isinstance(entrada, dict):
        return 1
    tipo = str(entrada.get("veredicto") or "")
    cuando = float(entrada.get("cuando") or 0.0)
    caducidad = CADUCIDAD_VEREDICTO.get(tipo)
    if caducidad is None:
        return 1
    if ahora - cuando > caducidad:
        return 2
    if tipo == "verificado":
        return 0
    return 3


def ordenar_candidatos(servidores, veredictos: dict | None = None,
                       ahora: float | None = None) -> list[ServidorVPN]:
    """El orden de intento de la v1.0.14 (investigación A):
    verificados primero; entre el resto, POCAS SESIONES y buen
    uptime mandan — la velocidad bruta deja de mandar, porque
    los nodos «más rápidos» de la lista son los saturados que
    rechazan con AUTH_FAILED."""
    ahora = time.time() if ahora is None else ahora
    veredictos = veredictos or {}
    return sorted(
        servidores or [],
        key=lambda s: (rango_veredicto(veredictos, s, ahora),
                       s.sesiones, -s.uptime, -s.velocidad_bps))


# --- Plan de sondas (etapa 2, con presupuesto) --------------------------------------

def plan_sondas(servidores, veredictos: dict | None = None,
                ahora: float | None = None,
                max_por_pais: int = 3,
                max_vpnbook: int = 3,
                presupuesto_s: float = 180.0,
                coste_est_s: float = 20.0) -> list[ServidorVPN]:
    """A quién se le hace la sonda REAL en este refresco.

    Reglas (FACTIBILIDAD, Parte C): solo candidatos — por país,
    los mejores según el orden anti-saturación (pocas sesiones +
    uptime) —; se salta a quien ya tiene veredicto VIGENTE (la
    sonda no se repite); los 10 de VPNBook se reparten a lo
    largo del día (máx. `max_vpnbook` por refresco, primero los
    de veredicto más antiguo); y el total cabe en el
    presupuesto de tiempo (~3 min por refresco, ~20 s por nodo
    en el peor caso). Las sondas son SECUENCIALES (una sola
    tarjeta TAP): este plan es una cola, no un barrido.
    """
    ahora = time.time() if ahora is None else ahora
    veredictos = veredictos or {}
    tope_total = max(0, int(presupuesto_s // max(1.0, coste_est_s)))
    por_pais: dict[str, list[ServidorVPN]] = {}
    de_vpnbook: list[ServidorVPN] = []
    for servidor in servidores or []:
        estado, _cuando = veredicto_de(veredictos, servidor, ahora)
        if estado != "sin_verificar":
            continue  # veredicto vigente: no se re-sonda
        if getattr(servidor, "fuente", "") == FUENTE_VPNBOOK:
            de_vpnbook.append(servidor)
        else:
            por_pais.setdefault(servidor.pais or "", []).append(servidor)
    plan: list[ServidorVPN] = []
    for pais in sorted(por_pais):
        candidatos = sorted(
            por_pais[pais],
            key=lambda s: (s.sesiones, -s.uptime, -s.velocidad_bps))
        plan.extend(candidatos[:max_por_pais])
    # VPNBook: primero los de veredicto más antiguo (rotación a
    # lo largo del día hasta cubrir los 10).
    de_vpnbook.sort(
        key=lambda s: (veredictos.get(clave_servidor(s), {})
                       .get("cuando", 0.0)))
    plan.extend(de_vpnbook[:max_vpnbook])
    return plan[:tope_total]


# --- Caché en disco de la última lista buena -----------------------------------------

def _servidor_a_dict(servidor: ServidorVPN) -> dict:
    return {
        "hostname": servidor.hostname, "ip": servidor.ip,
        "puntuacion": servidor.puntuacion, "ping_ms": servidor.ping_ms,
        "velocidad_bps": servidor.velocidad_bps, "pais": servidor.pais,
        "pais_corto": servidor.pais_corto, "sesiones": servidor.sesiones,
        "uptime": servidor.uptime,
        "total_usuarios": servidor.total_usuarios,
        "operador": servidor.operador, "mensaje": servidor.mensaje,
        "ovpn_base64": servidor.ovpn_base64,
        "fuente": getattr(servidor, "fuente", FUENTE_VPNGATE),
    }


def _dict_a_servidor(datos: dict) -> ServidorVPN | None:
    try:
        return ServidorVPN(
            hostname=str(datos.get("hostname") or ""),
            ip=str(datos.get("ip") or ""),
            puntuacion=int(datos.get("puntuacion") or 0),
            ping_ms=int(datos.get("ping_ms") or 9999),
            velocidad_bps=int(datos.get("velocidad_bps") or 0),
            pais=str(datos.get("pais") or ""),
            pais_corto=str(datos.get("pais_corto") or ""),
            sesiones=int(datos.get("sesiones") or 0),
            uptime=int(datos.get("uptime") or 0),
            total_usuarios=int(datos.get("total_usuarios") or 0),
            operador=str(datos.get("operador") or ""),
            mensaje=str(datos.get("mensaje") or ""),
            ovpn_base64=str(datos.get("ovpn_base64") or ""),
            fuente=str(datos.get("fuente") or FUENTE_VPNGATE),
        )
    except (TypeError, ValueError):
        return None


def guardar_cache(ruta: str, servidores, veredictos: dict,
                  clave_vpnbook: str = "",
                  ahora: float | None = None) -> bool:
    """Guarda la lista FUSIONADA buena (con veredictos y la
    contraseña vigente de VPNBook) en disco. Solo la escribe un
    refresco SANO: un refresco fallido jamás la toca (lo
    garantiza el llamante no llamando). Escritura atómica
    (temporal + reemplazo) para no dejar una caché a medias."""
    datos = {
        "cuando": time.time() if ahora is None else ahora,
        "servidores": [_servidor_a_dict(s) for s in servidores or []],
        "veredictos": veredictos or {},
        "vpnbook": {"usuario": USUARIO_VPNBOOK,
                    "clave": clave_vpnbook or ""},
    }
    try:
        temporal = ruta + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False)
        os.replace(temporal, ruta)
        return True
    except OSError:
        return False


def cargar_cache(ruta: str) -> dict | None:
    """La última lista buena guardada, o None si no hay/está mal.

    {"servidores": [ServidorVPN], "veredictos": {...},
     "clave_vpnbook": str, "cuando": float}."""
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(datos, dict):
        return None
    servidores = []
    for entrada in datos.get("servidores") or []:
        if isinstance(entrada, dict):
            servidor = _dict_a_servidor(entrada)
            if servidor is not None:
                servidores.append(servidor)
    if not servidores:
        return None
    vpnbook = datos.get("vpnbook") or {}
    return {
        "servidores": servidores,
        "veredictos": datos.get("veredictos") or {},
        "clave_vpnbook": str(vpnbook.get("clave") or ""),
        "cuando": float(datos.get("cuando") or 0.0),
    }


def actualizar_veredictos_cache(ruta: str, veredictos: dict) -> bool:
    """Reescribe SOLO los veredictos de la caché existente (los
    intentos reales del usuario y las sondas los actualizan sin
    rehacer la lista). Si no hay caché, no crea ninguna."""
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        if not isinstance(datos, dict):
            return False
    except (OSError, ValueError):
        return False
    datos["veredictos"] = veredictos or {}
    try:
        temporal = ruta + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False)
        os.replace(temporal, ruta)
        return True
    except OSError:
        return False


# --- Cadencia del refresco -----------------------------------------------------------

def toca_refrescar(ahora: float, estado: dict,
                   minutos: float = 30.0) -> bool:
    """¿Toca refrescar las fuentes? (el primer arranque, sí;
    después, cada ~30 min: la lista de VPN Gate rota por horas
    y refrescar en cada arranque seguido desperdiciaría red)."""
    ultimo = (estado or {}).get("ultimo_refresco")
    if not isinstance(ultimo, (int, float)):
        return True
    return (ahora - float(ultimo)) >= minutos * 60


def leer_estado_refresco(ruta: str) -> dict:
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def guardar_estado_refresco(ruta: str, estado: dict) -> None:
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False)
    except OSError:
        pass
