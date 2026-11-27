"""Sonda rápida de servidores OpenVPN (v1.0.22, notas del usuario).

El problema que resuelve (pedido expreso del usuario el
2026-11-27): la verificación de la lista de VPN gratuita tardaba
minutos porque probaba cada servidor con una CONEXIÓN real —
lanzando openvpn.exe (o su servicio) servidor a servidor — y el
usuario no tiene 5–10 minutos para mirar esa ventana. Y que el
estatus rápido sea FUNCIONAL, no maquillaje: un ping ICMP solo
prueba que la máquina existe, no que su servicio VPN viva.

La sonda de este módulo habla el protocolo de verdad: envía el
paquete inicial REAL de un cliente OpenVPN (P_CONTROL_HARD_RESET
_CLIENT_V2, primer byte 0x38) al remote del perfil — por UDP, o
por TCP con su prefijo de longitud de 2 bytes si el perfil es
TCP — y el servidor SOLO contesta (con su propio hard-reset,
primer byte 0x40) si su servicio OpenVPN está vivo y aceptando.
Sin respuesta en el plazo = no responde. Nada de esto lanza
openvpn.exe, nada pide administrador (cero pop-ups de UAC) y
nada abre un túnel: la prueba del túnel completo con
credenciales sigue ocurriendo una sola vez, cuando el usuario
pulsa «Conectar».

Límite honesto: un servidor con tls-auth/tls-crypt en su perfil
descarta en silencio paquetes sin la firma HMAC de su llave, así
que puede no contestar a esta sonda aunque esté vivo. Los
perfiles de las fuentes de la app (VPN Gate y VPNBook) no usan
esa llave en sus configs públicas; si un día una fuente la
añade, ese servidor se juzgará por la vía de siempre (el intento
real de conexión del usuario y su veredicto).

Sin Qt y sin Windows: sockets de la librería estándar, usable y
probable en cualquier plataforma.
"""
import os
import socket
import struct
from concurrent.futures import ThreadPoolExecutor, as_completed

# Opcodes del protocolo OpenVPN (el opcode va en los 5 bits
# altos del primer byte; los 3 bajos son el key-id, 0 aquí).
OPCODE_CLIENTE_HARD_RESET = 0x38  # P_CONTROL_HARD_RESET_CLIENT_V2 (7 << 3)
OPCODE_SERVIDOR_HARD_RESET = 0x40  # P_CONTROL_HARD_RESET_SERVER_V2 (8 << 3)

TIMEOUT_DEFECTO_S = 3.0
CONCURRENCIA_DEFECTO = 256


def construir_paquete_cliente(sesion: bytes | None = None) -> bytes:
    """El paquete inicial real de un cliente OpenVPN (v2).

    Formato del P_CONTROL_HARD_RESET_CLIENT_V2: opcode (1 B),
    id de sesión local (8 B), nº de acks que lleva (1 B = 0),
    id de sesión remota (8 B = 0, aún no se conoce) y packet-id
    fiable (4 B = 0). Es el mismo primer vuelo que openvpn.exe
    manda al conectar: el servidor lo reconoce como el inicio
    de un apretón de manos y contesta con el suyo.
    """
    if sesion is None:
        sesion = os.urandom(8)
    if len(sesion) != 8:
        raise ValueError("el id de sesión OpenVPN son 8 bytes")
    return (
        bytes([OPCODE_CLIENTE_HARD_RESET])
        + sesion
        + b"\x00"          # n_acks = 0
        + b"\x00" * 8      # sesión remota: aún ninguna
        + struct.pack(">I", 0)  # packet-id fiable 0
    )


def es_respuesta_servidor(datos: bytes | None) -> bool:
    """True si `datos` es el hard-reset de un servidor OpenVPN.

    Se acepta cualquier key-id (los 3 bits bajos) y se exige el
    opcode exacto de hard-reset de servidor: otra cosa (un eco,
    un servicio distinto en ese puerto, basura) NO marca a
    nadie como «Online» — la sonda no maquilla.
    """
    if not datos:
        return False
    return (datos[0] & 0xF8) == OPCODE_SERVIDOR_HARD_RESET


def _sondear_udp(host: str, puerto: int, paquete: bytes,
                 timeout: float) -> bool:
    """Un vuelo UDP: se manda el hard-reset y se espera el del
    servidor. Cualquier respuesta que no sea la suya (otro
    servicio en el mismo puerto) no cuenta."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        s.sendto(paquete, (host, puerto))
        while True:
            datos, _origen = s.recvfrom(2048)
            if es_respuesta_servidor(datos):
                return True
            # Ruido ajeno en el puerto: se sigue esperando a la
            # respuesta de verdad hasta que venza el plazo.


def _sondear_tcp(host: str, puerto: int, paquete: bytes,
                 timeout: float) -> bool:
    """El mismo apretón por TCP: en modo TCP, OpenVPN antepone
    a cada paquete su longitud (2 bytes, big-endian)."""
    with socket.create_connection((host, puerto), timeout=timeout) as s:
        s.settimeout(timeout)
        s.sendall(struct.pack(">H", len(paquete)) + paquete)
        cabecera = s.recv(2)
        if len(cabecera) < 2:
            return False
        (longitud,) = struct.unpack(">H", cabecera)
        if longitud <= 0 or longitud > 4096:
            return False
        datos = b""
        while len(datos) < longitud:
            trozo = s.recv(longitud - len(datos))
            if not trozo:
                return False
            datos += trozo
        return es_respuesta_servidor(datos)


def sondear(host: str, puerto: int, proto: str = "udp",
            timeout: float = TIMEOUT_DEFECTO_S) -> bool:
    """¿Responde el servicio OpenVPN de (host, puerto)?

    True SOLO si llega su hard-reset de servidor dentro del
    plazo. Cualquier fallo (DNS, red, plazo, puerto cerrado)
    es False: la sonda nunca lanza hacia su llamante.
    """
    if not host or not puerto:
        return False
    paquete = construir_paquete_cliente()
    try:
        if str(proto or "udp").lower().startswith("tcp"):
            return _sondear_tcp(host, int(puerto), paquete, timeout)
        return _sondear_udp(host, int(puerto), paquete, timeout)
    except Exception:
        return False


def sondear_muchos(destinos, al_resultado=None,
                   timeout: float = TIMEOUT_DEFECTO_S,
                   concurrencia: int = CONCURRENCIA_DEFECTO,
                   cancelar=None) -> dict:
    """Sonda EN PARALELO de muchos destinos a la vez.

    `destinos`: iterable de claves hashables a (host, puerto,
    proto) — p. ej. {clave: (host, puerto, proto)}. Devuelve
    {clave: bool}. Con cientos de sondas concurrentes y un
    plazo corto, una lista entera se verifica en segundos, no
    en los minutos de la conexión real de antes.

    `al_resultado(clave, respondio)` se invoca en cuanto cae
    CADA resultado (la UI pinta la fila en vivo); sus errores
    nunca detienen el barrido. `cancelar` (un threading.Event o
    un callable que devuelva bool) detiene la entrega de
    resultados nuevos: lo ya contestado queda, el resto no se
    reporta (y sus sondas en vuelo se abandonan al cerrar).
    """
    destinos = dict(destinos or {})
    resultados: dict = {}
    if not destinos:
        return resultados

    def _cancelado() -> bool:
        if cancelar is None:
            return False
        try:
            if hasattr(cancelar, "is_set"):
                return bool(cancelar.is_set())
            return bool(cancelar())
        except Exception:
            return False

    def _trabajo(clave, destino):
        host, puerto, proto = destino
        return clave, sondear(host, puerto, proto, timeout)

    trabajadores = max(1, min(int(concurrencia), len(destinos)))
    with ThreadPoolExecutor(max_workers=trabajadores) as pool:
        futuros = [pool.submit(_trabajo, clave, destino)
                   for clave, destino in destinos.items()]
        # as_completed: cada resultado se entrega EN CUANTO cae
        # (la fila se pinta en vivo), no en el orden de la lista.
        for futuro in as_completed(futuros):
            if _cancelado():
                break
            try:
                clave, respondio = futuro.result()
            except Exception:
                continue
            resultados[clave] = respondio
            if al_resultado is not None:
                try:
                    al_resultado(clave, respondio)
                except Exception:
                    pass  # un oyente roto no detiene el barrido
    return resultados
