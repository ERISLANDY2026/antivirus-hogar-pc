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


def parsear_export_hashes(texto: str) -> list[tuple[str, str]]:
    """Export TXT de abuse.ch: una huella por línea (# = comentario).
    Devuelve [(huella, etiqueta)] con etiqueta genérica de la fuente."""
    salida: list[tuple[str, str]] = []
    for linea in texto.splitlines():
        huella = linea.strip().lower()
        if not huella or huella.startswith("#"):
            continue
        if len(huella) in (32, 64) and all(c in "0123456789abcdef" for c in huella):
            salida.append((huella, "Malware conocido (abuse.ch)"))
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
            if f.error:
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
    """MalwareBazaar (huellas) vía API con Auth-Key; sin clave se intenta
    igual y la causa queda registrada (la API la exige desde 2025)."""
    nombre = "abuse.ch (MalwareBazaar)"
    if not auth_key:
        return ResultadoFuente(
            nombre, 0,
            "requiere la Auth-Key gratuita de abuse.ch (se guarda en Ajustes)"), []
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

    # 1) abuse.ch con Auth-Key (huellas)
    fuente, entradas = _fuente_abusech(bajar, auth_key)
    resultado.por_fuente.append(fuente)
    for huella, etiqueta in entradas:
        hashes[huella] = etiqueta

    # 2-5) fuentes de dominios sin clave
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
