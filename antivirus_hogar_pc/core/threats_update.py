"""Actualización de la base de amenazas desde abuse.ch.

Fuentes gratuitas y legales para uso doméstico (fair use de abuse.ch):
- MalwareBazaar: hashes de malware confirmado. Desde 2025 su API exige una
  Auth-Key GRATUITA (se crea en el portal de abuse.ch); sin clave se intenta
  el export público de hashes recientes.
- URLhaus: dominios/hosts de distribución de malware (para el bloqueador).
- OpenPhish: feed comunitario de phishing.

Este módulo parsea los formatos (lógica pura, probada) y descarga cuando el
usuario lo pide. Nada se descarga en segundo plano sin avisar.
"""
import csv
import io
import urllib.request

EXPORT_SHA256_RECIENTES = "https://bazaar.abuse.ch/export/txt/sha256/recent/"
EXPORT_MD5_RECIENTES = "https://bazaar.abuse.ch/export/txt/md5/recent/"
MALWAREBAZAAR_API = "https://mb-api.abuse.ch/api/v1/"


def _peticion(url: str, datos: bytes | None = None, auth_key: str = "",
              timeout: int = 60) -> str:
    cabeceras = {"User-Agent": "AntivirusHogarPC"}
    if auth_key:
        cabeceras["Auth-Key"] = auth_key
    req = urllib.request.Request(url, data=datos, headers=cabeceras)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parsear_export_hashes(texto: str,
                          etiqueta: str = "Malware conocido (abuse.ch)") -> list[tuple[str, str]]:
    """Lista de huellas en texto: una por línea (# = comentario).
    Devuelve [(huella, etiqueta)] con la etiqueta de la fuente."""
    salida: list[tuple[str, str]] = []
    for linea in texto.splitlines():
        huella = linea.strip().lower()
        if not huella or huella.startswith("#"):
            continue
        if len(huella) in (32, 64) and all(c in "0123456789abcdef" for c in huella):
            salida.append((huella, etiqueta))
    return salida


def parsear_csv_malwarebazaar(texto: str) -> list[tuple[str, str]]:
    """CSV completo de MalwareBazaar: usa sha256_hash y la firma/familia."""
    lineas = [ln for ln in texto.splitlines() if not ln.startswith("#")]
    if not lineas:
        return []
    lector = csv.DictReader(io.StringIO("\n".join(lineas)))
    salida: list[tuple[str, str]] = []
    for fila in lector:
        huella = (fila.get("sha256_hash") or "").strip().lower()
        if len(huella) != 64:
            continue
        etiqueta = (fila.get("signature") or "").strip()
        if not etiqueta or etiqueta.lower() == "n/a":
            etiqueta = "Malware conocido (MalwareBazaar)"
        else:
            etiqueta = f"{etiqueta} (MalwareBazaar)"
        salida.append((huella, etiqueta))
    return salida


def escribir_archivo_firmas(ruta: str, entradas: list[tuple[str, str]]) -> int:
    """Escribe el archivo de firmas extra en el formato de BaseFirmas."""
    unicas: dict[str, str] = {}
    for huella, etiqueta in entradas:
        unicas[huella] = etiqueta
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("# Firmas descargadas de abuse.ch (MalwareBazaar)\n")
        for huella in sorted(unicas):
            f.write(f"{huella}  {unicas[huella]}\n")
    return len(unicas)


def descargar_firmas_recientes(auth_key: str = "") -> list[tuple[str, str]]:
    """Hashes recientes (SHA-256 y MD5) de MalwareBazaar vía export público."""
    entradas: list[tuple[str, str]] = []
    for url in (EXPORT_SHA256_RECIENTES, EXPORT_MD5_RECIENTES):
        try:
            entradas += parsear_export_hashes(_peticion(url, auth_key=auth_key))
        except Exception:
            continue
    return entradas


# =============================================================================
# Cadena MULTI-FUENTE (v1.0.2, bug 6): varios respaldos, no solo abuse.ch.
#
# Verificado desde el entorno de construcción el 2026-11-24:
# - Los exports públicos de abuse.ch (bazaar/urlhaus) devuelven 410 Gone:
#   abuse.ch los retiró y TODO pasa por su API con Auth-Key gratuita.
#   Sin clave, esta fuente se intenta y reporta esa causa, sin bloquear
#   al resto de la cadena.
# - El hostfile de URLhaus también murió (410): lo sustituye el proyecto
#   malware-filter (curben), que republica los datos de URLhaus como
#   lista de dominios, gratis y sin clave.
# - ET Open y Spamhaus DROP responden, pero son listas de IP/CIDR: no
#   sirven a un bloqueador por dominios ni como huellas; quedan fuera y
#   su hueco lo cubre la lista oficial de dominios de CERT.PL (200).
# - DigitalSide no respondió desde el entorno de construcción: fuera.
#
# Cada fuente se intenta SIEMPRE (se fusiona, no se para en la primera),
# con su propio timeout, y su resultado se cuenta por separado. La
# actualización se logra si AL MENOS UNA fuente aporta.
# =============================================================================
import urllib.error
from dataclasses import dataclass, field
from urllib.parse import urlparse

# Huellas SIN clave (v1.0.3): el proyecto malicious-hash (GitHub, licencia
# MIT, actualización horaria) agrega varias fuentes públicas de hashes de
# malware confirmado y las publica como texto plano, una huella por línea.
# Verificado en vivo el 2026-11-24 desde el entorno de construcción:
# full-hash-sha256-aa.txt = 130.905 SHA-256 válidas; full-hash-md5-aa.txt
# = 4.049 MD5 válidas. Con esto las huellas ya NO dependen de la Auth-Key
# de abuse.ch (que queda como fuente opcional para quien la tenga).
URL_MALICIOUS_HASH_SHA256 = ("https://raw.githubusercontent.com/romainmarcoux/"
                             "malicious-hash/main/full-hash-sha256-aa.txt")
URL_MALICIOUS_HASH_MD5 = ("https://raw.githubusercontent.com/romainmarcoux/"
                          "malicious-hash/main/full-hash-md5-aa.txt")
ETIQUETA_MALICIOUS_HASH = "Malware conocido (malicious-hash)"

URL_URLHAUS_FILTER = "https://malware-filter.gitlab.io/malware-filter/urlhaus-filter-domains.txt"
URL_PHISHING_DATABASE = ("https://raw.githubusercontent.com/Phishing-Database/"
                         "Phishing.Database/master/phishing-domains-ACTIVE.txt")
URL_OPENPHISH = "https://openphish.com/feed.txt"
URL_CERT_PL = "https://hole.cert.pl/domains/v2/domains.txt"


@dataclass
class ResultadoFuente:
    nombre: str
    cantidad: int = 0          # huellas + dominios aportados (tras fusionar, brutos)
    error: str = ""            # causa real si falló
    opcional: bool = False     # fuente opcional no consultada (p. ej. sin clave):
                               # no cuenta como «falló» en el resumen


@dataclass
class ResultadoMultifuente:
    por_fuente: list[ResultadoFuente] = field(default_factory=list)
    hashes: list[tuple[str, str]] = field(default_factory=list)   # (huella, etiqueta)
    dominios: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return any(f.cantidad > 0 for f in self.por_fuente)

    def resumen(self) -> str:
        partes = []
        for f in self.por_fuente:
            if f.opcional:
                partes.append(f"{f.nombre}: opcional (sin clave; no se consultó)")
            elif f.error:
                partes.append(f"{f.nombre}: falló ({f.error})")
            else:
                partes.append(f"{f.nombre}: {f.cantidad} firmas")
        return " · ".join(partes)


def _causa(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (401, 403):
            return "exige la Auth-Key gratuita de abuse.ch (se guarda en Ajustes)"
        if exc.code == 410:
            return "la fuente retiró ese archivo (HTTP 410)"
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return "sin conexión con esa fuente"
    return str(exc)[:120] or exc.__class__.__name__


def parsear_dominios_texto(texto: str) -> list[str]:
    """Dominios de una lista en texto: uno por línea o en formato hosts
    («0.0.0.0 dominio»), con # como comentario. Descarta IPs sueltas."""
    dominios: set[str] = set()
    for linea in texto.splitlines():
        d = linea.strip().lower()
        if not d or d.startswith("#") or d.startswith(";"):
            continue
        partes = d.split()
        if len(partes) == 2 and partes[0] in ("0.0.0.0", "127.0.0.1"):
            d = partes[1]
        elif len(partes) > 1:
            continue
        if "." in d and "/" not in d and ":" not in d and not d[0].isdigit():
            dominios.add(d.strip("."))
    return sorted(dominios)


def parsear_dominios_de_urls(texto: str) -> list[str]:
    """Dominios desde un feed de URLs completas (OpenPhish)."""
    dominios: set[str] = set()
    for linea in texto.splitlines():
        url = linea.strip()
        if not url or url.startswith("#"):
            continue
        host = urlparse(url if "://" in url else f"http://{url}").hostname
        if host and "." in host:
            dominios.add(host.lower())
    return sorted(dominios)


def _fuente_abusech(descargador, auth_key: str) -> ResultadoFuente:
    """MalwareBazaar (huellas) vía API con Auth-Key. OPCIONAL (v1.0.3):
    sin clave NO se consulta y NO cuenta como fallo — las huellas llegan
    de malicious-hash, que no pide clave. Con clave, se consulta y suma."""
    nombre = "abuse.ch (MalwareBazaar)"
    if not auth_key:
        return ResultadoFuente(nombre, 0, "", opcional=True), []
    try:
        datos = b"query=get_recent&selector=100"
        texto = descargador(MALWAREBAZAAR_API, datos, auth_key, 45)
        entradas = parsear_csv_malwarebazaar(texto)
        return ResultadoFuente(nombre, len(entradas)), entradas
    except Exception as exc:
        return ResultadoFuente(nombre, 0, _causa(exc)), []


def actualizar_firmas_multifuente(auth_key: str = "", descargador=None) -> ResultadoMultifuente:
    """Intenta TODAS las fuentes y fusiona. `descargador(url, datos,
    auth_key, timeout) -> texto` es inyectable para la suite."""
    bajar = descargador or _peticion
    resultado = ResultadoMultifuente()
    hashes: dict[str, str] = {}
    dominios: set[str] = set()

    # 1) abuse.ch con Auth-Key (huellas, OPCIONAL: sin clave no es fallo)
    fuente, entradas = _fuente_abusech(bajar, auth_key)
    resultado.por_fuente.append(fuente)
    for huella, etiqueta in entradas:
        hashes[huella] = etiqueta

    # 2) malicious-hash (huellas SIN clave): SHA-256 y MD5 por separado,
    # para que el resumen enseñe cuánto trajo cada archivo.
    for nombre, url in (
        ("malicious-hash (SHA-256)", URL_MALICIOUS_HASH_SHA256),
        ("malicious-hash (MD5)", URL_MALICIOUS_HASH_MD5),
    ):
        try:
            texto = bajar(url, None, "", 60)
            encontrados = parsear_export_hashes(texto, ETIQUETA_MALICIOUS_HASH)
            resultado.por_fuente.append(ResultadoFuente(nombre, len(encontrados)))
            for huella, etiqueta in encontrados:
                hashes[huella] = etiqueta
        except Exception as exc:
            resultado.por_fuente.append(ResultadoFuente(nombre, 0, _causa(exc)))

    # 3-6) fuentes de dominios sin clave
    for nombre, url, parser in (
        ("URLhaus (vía malware-filter)", URL_URLHAUS_FILTER, parsear_dominios_texto),
        ("Phishing.Database", URL_PHISHING_DATABASE, parsear_dominios_texto),
        ("OpenPhish", URL_OPENPHISH, parsear_dominios_de_urls),
        ("CERT.PL", URL_CERT_PL, parsear_dominios_texto),
    ):
        try:
            texto = bajar(url, None, "", 45)
            encontrados = parser(texto)
            resultado.por_fuente.append(ResultadoFuente(nombre, len(encontrados)))
            dominios.update(encontrados)
        except Exception as exc:
            resultado.por_fuente.append(ResultadoFuente(nombre, 0, _causa(exc)))

    resultado.hashes = sorted(hashes.items())
    resultado.dominios = sorted(dominios)
    return resultado


def escribir_archivo_dominios(ruta: str, dominios: list[str]) -> int:
    """Dominios descargados, uno por línea (formato de hosts_blocker)."""
    unicos = sorted(set(dominios))
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("# Dominios descargados de fuentes públicas (v1.0.2)\n")
        for d in unicos:
            f.write(d + "\n")
    return len(unicos)


# --- Bases de CONSULTA con atribución (v1.0.21) -------------------------------
# Phishing.Database (MIT) y Feodo Tracker (CC0) alimentan la base
# de consulta de core.dominios_consulta: NO entran en la fusión del
# hosts (Feodo son IPs C2, inútiles en un hosts; Phishing.Database
# ya aporta a la fusión por su propia fuente de texto). Aquí se
# guardan APARTE, con su fuente, para poder decir de dónde sale
# cada dominio/IP al consultar.
import json as _json
import os as _os

from .. import config as _config

URL_FEODO_JSON = "https://feodotracker.abuse.ch/downloads/ipblocklist.json"


def actualizar_bases_consulta() -> dict:
    """Refresca dominios_phishing_db.txt y dominios_feodo.txt en la
    carpeta de datos. Devuelve conteos por base (0 si falló)."""
    from . import dominios_consulta

    salida = {"phishing_db": 0, "feodo": 0}
    carpeta = _config.carpeta_datos()
    try:
        _os.makedirs(carpeta, exist_ok=True)
    except OSError:
        return salida
    # Phishing.Database ACTIVE (MIT): la misma descarga que ya usa
    # la cadena de fusión, guardada además como base de consulta.
    try:
        texto = _peticion(URL_PHISHING_DATABASE, timeout=120)
    except Exception:
        texto = ""
    if texto:
        dominios = parsear_dominios_texto(texto)
        if dominios:
            ruta = _os.path.join(carpeta, "dominios_phishing_db.txt")
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write("# Phishing.Database — phishing-domains-ACTIVE.txt\n")
                fh.write("# Licencia: MIT. Base de CONSULTA (no va al hosts).\n")
                for d in dominios:
                    fh.write(d + "\n")
            salida["phishing_db"] = len(dominios)
    # Feodo Tracker (CC0): IPs C2 + hostnames si los hay.
    try:
        crudo = _peticion(URL_FEODO_JSON, timeout=60)
        registros = _json.loads(crudo)
    except Exception:
        registros = None
    if isinstance(registros, list):
        ips, hosts = dominios_consulta.extraer_feodo(registros)
        ruta = _os.path.join(carpeta, "dominios_feodo.txt")
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write("# Feodo Tracker — ipblocklist (IPs C2)\n")
            fh.write("# Licencia: CC0. Base de CONSULTA (no va al hosts).\n")
            for valor in ips + hosts:
                fh.write(valor + "\n")
        salida["feodo"] = len(ips) + len(hosts)
    dominios_consulta.invalidar_cache()
    return salida
