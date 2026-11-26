"""Puntuación de descargas (v1.0.21): veredicto con fundamento.

Para un archivo (típicamente una descarga) combina señales
INDEPENDIENTES y dice por qué:

- CIRCL hashlookup (sin clave): si la huella figura en su base de
  software conocido, el archivo es «conocido» — OJO: conocido NO es
  «seguro»; un hash conocido puede ser también un programa malo ya
  catalogado, y esta señal jamás se presenta como garantía.
- Firma Authenticode: válida / ausente / inválida (winapi, Windows).
- Marca de origen (Zone.Identifier / MOTW): si Windows marcó el
  archivo como venido de Internet.
- Entropía de Shannon: señal SECUNDARIA (un instalador empaquetado
  o cifrado la tiene alta sin ser malo); solo cuenta en archivos
  ejecutables, donde un binario «de la nada» muy comprimido suma.

100 % Python y SIN SUBIR EL ARCHIVO A NINGÚN SERVICIO: a CIRCL
solo viaja la huella SHA-256, nunca el contenido.
"""
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .hashing import huellas_archivo
from .hashing import entropia_shannon

URL_CIRCL = "https://hashlookup.circl.lu/lookup/sha256/"

EXTENSIONES_EJECUTABLES = {
    ".exe", ".msi", ".dll", ".sys", ".scr", ".com", ".bat", ".cmd",
    ".ps1", ".vbs", ".js", ".jse", ".wsf", ".hta", ".cpl", ".ocx",
}


@dataclass
class Senales:
    sha256: str = ""
    md5: str = ""
    tamano: int = 0
    circl: str = "sin_respuesta"  # conocido|no_conocido|sin_respuesta
    circl_nombre: str = ""
    firma: str = "no_disponible"  # valida|ausente|invalida|no_disponible
    firmante: str = ""
    motw: bool | None = None  # None = no comprobable en este sistema
    motw_origen: str = ""
    entropia: float = 0.0
    es_ejecutable: bool = False


@dataclass
class Puntuacion:
    nivel: str  # conocido|normal|precaucion|riesgo
    puntos: int
    motivos: list[str] = field(default_factory=list)  # códigos
    senales: Senales = field(default_factory=Senales)


def consultar_circl(sha256: str, timeout: int = 10) -> tuple[str, str]:
    """(estado, nombre). Solo viaja la huella, nunca el archivo.

    estado: «conocido» (200), «no_conocido» (404: la base no lo
    tiene, que NO significa que sea malo) o «sin_respuesta».
    """
    sha = (sha256 or "").strip().lower()
    if len(sha) != 64:
        return "sin_respuesta", ""
    peticion = urllib.request.Request(
        URL_CIRCL + sha,
        headers={"User-Agent": "AntivirusHogarPC/1.0 "
                               "(hashlookup; solo hash)"})
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as resp:
            datos = json.loads(resp.read().decode("utf-8", "replace"))
        nombre = ""
        if isinstance(datos, dict):
            nombre = str(datos.get("FileName", "") or "")
        return "conocido", nombre
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return "no_conocido", ""
        return "sin_respuesta", ""
    except Exception:
        return "sin_respuesta", ""


def leer_motw(ruta: str) -> tuple[bool | None, str]:
    """Marca de origen (Zone.Identifier) de un archivo, en Windows.

    Devuelve (True, origen) si el archivo trae la marca de Internet,
    (False, "") si se pudo comprobar que no la trae, y (None, "") si
    no se puede comprobar (fuera de Windows o error de lectura).
    """
    if os.name != "nt":
        return None, ""
    try:
        with open(ruta + ":Zone.Identifier", "r",
                  encoding="utf-8", errors="replace") as fh:
            contenido = fh.read()
    except FileNotFoundError:
        return False, ""
    except OSError:
        return None, ""
    origen = ""
    for linea in contenido.splitlines():
        if "=" in linea:
            clave, valor = linea.split("=", 1)
            if clave.strip().lower() in ("hosturl", "referrerurl"):
                origen = valor.strip()
                break
    return True, origen


def _firma_de(ruta: str) -> tuple[str, str]:
    """(estado, firmante) reutilizando el verificador de OpenVPN."""
    if os.name != "nt":
        return "no_disponible", ""
    try:
        from ..winapi.openvpn_update import firma_authenticode

        res = firma_authenticode(ruta)
    except Exception:
        return "no_disponible", ""
    firmante = str(res.get("firmante", "") or "")
    if res.get("valida"):
        return "valida", firmante
    if firmante:
        return "invalida", firmante
    return "ausente", ""


def puntuar(senales: Senales) -> Puntuacion:
    """Reglas de puntuación, puras y auditables.

    Positivo = más sospechoso. La entropía solo suma en
    ejecutables. «Conocido» (CIRCL) baja la puntuación pero el
    nivel jamás se llama «seguro»: conocido ≠ seguro.
    """
    puntos = 0
    motivos: list[str] = []
    if senales.circl == "conocido":
        puntos -= 30
        motivos.append("circl_conocido")
    elif senales.circl == "no_conocido":
        motivos.append("circl_no_conocido")
    else:
        motivos.append("circl_sin_respuesta")
    if senales.firma == "valida":
        puntos -= 25
        motivos.append("firma_valida")
    elif senales.firma == "invalida":
        puntos += 45
        motivos.append("firma_invalida")
    elif senales.firma == "ausente" and senales.es_ejecutable:
        puntos += 10
        motivos.append("firma_ausente")
    if senales.motw is True:
        puntos += 15
        motivos.append("motw_internet")
    if senales.es_ejecutable:
        if senales.entropia >= 7.5:
            puntos += 20
            motivos.append("entropia_muy_alta")
        elif senales.entropia >= 7.2:
            puntos += 10
            motivos.append("entropia_alta")
    if puntos >= 50:
        nivel = "riesgo"
    elif puntos >= 25:
        nivel = "precaucion"
    elif senales.circl == "conocido" and puntos < 25:
        nivel = "conocido"
    else:
        nivel = "normal"
    return Puntuacion(nivel=nivel, puntos=puntos, motivos=motivos,
                      senales=senales)


def evaluar(ruta: str, consultar_red: bool = True) -> Puntuacion:
    """Evalúa un archivo combinando todas las señales locales y,
    si se pide, la consulta por huella a CIRCL (sin subir nada)."""
    sha256, md5 = huellas_archivo(ruta)
    senales = Senales(
        sha256=sha256, md5=md5, tamano=os.path.getsize(ruta),
        es_ejecutable=os.path.splitext(ruta)[1].lower()
        in EXTENSIONES_EJECUTABLES)
    senales.firma, senales.firmante = _firma_de(ruta)
    senales.motw, senales.motw_origen = leer_motw(ruta)
    try:
        with open(ruta, "rb") as fh:
            senales.entropia = entropia_shannon(fh.read(4 * 1024 * 1024))
    except OSError:
        senales.entropia = 0.0
    if consultar_red:
        senales.circl, senales.circl_nombre = consultar_circl(sha256)
    return puntuar(senales)
