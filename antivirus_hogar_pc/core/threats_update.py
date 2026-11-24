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
