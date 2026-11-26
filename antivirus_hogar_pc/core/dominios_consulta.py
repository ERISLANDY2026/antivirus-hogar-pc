"""Consulta de dominios/IP con la FUENTE identificada (v1.0.21).

La base de bloqueo (hosts) sigue siendo la de siempre. Esta es una
base de CONSULTA aparte, con fuentes redistribuibles y atribución
por dominio:

- Phishing.Database (MIT): snapshot ACTIVE incluido en la app y
  refrescado por core.threats_update.actualizar_bases_consulta().
- Feodo Tracker (CC0): IPs C2 (+ hostname cuando la fuente lo da).
- La propia base de bloqueo ya fusionada (StevenBlack/hosts y
  demás fuentes históricas) también se puede consultar.

Nada de esta base de consulta se escribe en el archivo hosts: el
bloqueo sigue gobernado por core.hosts_blocker con su copia de
seguridad y su restauración de siempre. abuse.ch (URLhaus y cía.)
NO se redistribuye de nuevo: sus términos del 4-nov-2025 exigen
Auth-Key y limitan el uso gratuito a fines sin ánimo de lucro.
"""
import os
import re
from urllib.parse import urlparse

from .. import config

_PATRON_IP = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def normalizar_dominio(valor: str) -> str:
    """Normaliza un dominio, una IP o una URL a su host en minúsculas.

    Acepta líneas de lista (con comentario o en formato hosts) y
    consultas sueltas (dominio, IP o URL completa). Devuelve "" si
    no hay un host aprovechable.
    """
    d = (valor or "").strip().lower()
    if not d or d.startswith("#") or d.startswith(";"):
        return ""
    if "://" in d or "/" in d or ":" in d:
        host = urlparse(d if "://" in d else f"http://{d}").hostname
        d = host or ""
    partes = d.split()
    if len(partes) == 2 and partes[0] in ("0.0.0.0", "127.0.0.1"):
        d = partes[1]
    elif len(partes) > 1:
        return ""
    d = d.strip().strip(".")
    if d.startswith("*."):
        d = d[2:]
    if _PATRON_IP.match(d):
        return d
    if "." not in d or " " in d:
        return ""
    return d

FUENTE_PHISHING_DB = "Phishing.Database (MIT)"
FUENTE_FEODO = "Feodo Tracker (CC0)"
FUENTE_BASE_BLOQUEO = "Base de bloqueo de la app"

_cache: dict[str, frozenset] = {}


def _leer_lista(ruta: str) -> frozenset:
    if ruta in _cache:
        return _cache[ruta]
    valores: set[str] = set()
    try:
        with open(ruta, "r", encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                d = normalizar_dominio(linea)
                if d:
                    valores.add(d)
    except OSError:
        pass
    congelado = frozenset(valores)
    _cache[ruta] = congelado
    return congelado


def _rutas(nombre: str) -> list[str]:
    """La copia refrescada en datos manda sobre la incluida."""
    return [os.path.join(config.carpeta_datos(), nombre),
            os.path.join(config.carpeta_activos(), nombre)]


def _conjunto(nombre: str) -> frozenset:
    for ruta in _rutas(nombre):
        if os.path.isfile(ruta):
            return _leer_lista(ruta)
    return frozenset()


def conjunto_phishing_db() -> frozenset:
    return _conjunto("dominios_phishing_db.txt")


def conjunto_feodo() -> frozenset:
    return _conjunto("dominios_feodo.txt")


def conjunto_base_bloqueo() -> frozenset:
    """Dominios de las bases de bloqueo (fusionada + semilla)."""
    from .seguridad import rutas_base_dominios

    valores: set[str] = set()
    for base in ("fusionada", "semilla"):
        for ruta in rutas_base_dominios(base):
            valores |= _leer_lista(ruta)
    return frozenset(valores)


def _variantes(dominio: str) -> list[str]:
    """El dominio y sus padres: sub.ejemplo.com → ejemplo.com."""
    d = normalizar_dominio(dominio)
    if not d:
        return []
    partes = d.split(".")
    return [".".join(partes[i:]) for i in range(len(partes) - 1)]


def fuente_de(dominio_o_url: str) -> str | None:
    """¿En qué fuente figura este dominio/IP? None si en ninguna.

    Acepta un dominio, una IP o una URL completa. La respuesta
    identifica la fuente para que la interfaz la enseñe: la
    atribución es parte del dato, no un adorno.
    """
    variantes = _variantes(dominio_o_url)
    if not variantes:
        return None
    feodo = conjunto_feodo()
    for v in variantes:
        if v in feodo:
            return FUENTE_FEODO
    phishing = conjunto_phishing_db()
    for v in variantes:
        if v in phishing:
            return FUENTE_PHISHING_DB
    base = conjunto_base_bloqueo()
    for v in variantes:
        if v in base:
            return FUENTE_BASE_BLOQUEO
    return None


def conteos() -> dict[str, int]:
    """Tamaño de cada base de consulta, para la interfaz."""
    return {
        FUENTE_PHISHING_DB: len(conjunto_phishing_db()),
        FUENTE_FEODO: len(conjunto_feodo()),
        FUENTE_BASE_BLOQUEO: len(conjunto_base_bloqueo()),
    }


def extraer_feodo(registros: list) -> tuple[list[str], list[str]]:
    """(IPs, hostnames) desde el JSON de Feodo Tracker.

    Función pura: la usa threats_update al refrescar y la puede
    probar la suite sin red.
    """
    ips: set[str] = set()
    hosts: set[str] = set()
    for r in registros or []:
        if not isinstance(r, dict):
            continue
        ip = str(r.get("ip_address", "") or "").strip()
        if ip:
            ips.add(ip)
        host = normalizar_dominio(str(r.get("hostname", "") or ""))
        if host:
            hosts.add(host)
    return sorted(ips), sorted(hosts)


def invalidar_cache() -> None:
    _cache.clear()
