"""Auto-actualización propia (mismo esquema que Android).

Se descarga un version.json del canal de Drive con:
  {"version": "1.1.0", "notas": "Qué trae…", "url": "https://…/instalador.exe",
   "sha256": "…huella del instalador…"}

La app compara versiones, enseña el diálogo «Qué trae esta actualización» y,
solo si el usuario pulsa el botón verde, descarga el instalador, VERIFICA su
SHA-256 y lo abre. En Windows sin firma, SmartScreen avisará: es lo esperado
y se explica en el propio diálogo.
"""
import http.client
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .drivers_logic import comparar_versiones
from .hashing import sha256_archivo


class ErrorActualizacion(Exception):
    """Fallo al comprobar el canal, CLASIFICADO para un mensaje honesto.

    tipo:
    - "sin_conexion": no se llegó al servidor (red caída, DNS, tiempo fuera).
    - "no_encontrado": el servidor respondió 404: el archivo de versión no
      está publicado (esto fue el bug de la v1.0.1: el id era un marcador).
    - "respuesta_invalida": respondió, pero el contenido no es un
      version-pc.json válido.
    """

    def __init__(self, tipo: str, detalle: str = ""):
        super().__init__(detalle or tipo)
        self.tipo = tipo
        self.detalle = detalle


@dataclass
class InfoActualizacion:
    version: str
    notas: str
    url: str
    sha256: str = ""


def parsear_version_json(texto: str) -> InfoActualizacion:
    datos = json.loads(texto)
    return InfoActualizacion(
        version=str(datos.get("version", "")).strip(),
        notas=str(datos.get("notas", "")).strip(),
        url=str(datos.get("url", "")).strip(),
        sha256=str(datos.get("sha256", "")).strip().lower(),
    )


def hay_actualizacion(version_actual: str, info: InfoActualizacion) -> bool:
    return bool(info.version) and comparar_versiones(info.version, version_actual) > 0


def descargar_texto(url: str, timeout: int = 30) -> str:
    """Descarga texto clasificando el fallo (ErrorActualizacion)."""
    req = urllib.request.Request(url, headers={"User-Agent": "AntivirusHogarPC"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ErrorActualizacion(
                "no_encontrado", f"HTTP 404 en {url}") from exc
        raise ErrorActualizacion(
            "respuesta_invalida", f"HTTP {exc.code} en {url}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ErrorActualizacion("sin_conexion", str(exc)) from exc


def descargar_archivo(url: str, destino: str, timeout: int = 600,
                      reintentos: int = 3, pausa: float = 0.4) -> str:
    """Descarga un archivo con REINTENTOS y REANUDACIÓN (v1.0.5).

    La descarga del instalador desde la red del usuario se cortó dos
    veces el 2026-11-24 («No se pudo descargar la actualización»): un
    solo intento no basta en una conexión inestable. Ahora:

    - Hasta ``reintentos`` intentos en total ante cortes de red,
      tiempos fuera y errores 5xx/429 del servidor.
    - Si un intento se corta a mitad, el siguiente pide ``Range`` desde
      los bytes ya escritos en ``destino``; si el servidor responde 206
      se añade al parcial, y si responde 200 (no acepta rangos) se
      empieza de cero. Un 416 invalida el parcial y se borra.
    - Los demás 4xx (404 y compañía) no se reintentan: no se arreglan
      esperando. Si todos los intentos fallan se relanza la ÚLTIMA
      excepción, como antes: quien llama registra el detalle técnico.
    - La verificación SHA-256 la sigue haciendo quien llama, sobre el
      archivo ya completo.
    """
    # v1.0.7 (lección de la entrega 1.0.6 en la PC real): si la carpeta
    # de destino no existe, la descarga moría al instante al intentar
    # escribir («No se pudo descargar la actualización») y el usuario
    # tuvo que crearla a mano. El descargador la crea SIEMPRE.
    carpeta_destino = os.path.dirname(os.path.abspath(destino))
    os.makedirs(carpeta_destino, exist_ok=True)
    intentos = max(1, int(reintentos))
    ultimo_error: BaseException | None = None
    for intento in range(intentos):
        ya = os.path.getsize(destino) if os.path.isfile(destino) else 0
        cabeceras = {"User-Agent": "AntivirusHogarPC"}
        if ya > 0:
            cabeceras["Range"] = f"bytes={ya}-"
        req = urllib.request.Request(url, headers=cabeceras)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                # 206 = el servidor aceptó seguir desde el parcial;
                # 200 = ignoró el Range: se reescribe desde cero.
                anadir = ya > 0 and getattr(resp, "status", 200) == 206
                esperado_txt = resp.headers.get("Content-Length")
                esperado = (int(esperado_txt) if esperado_txt
                            and esperado_txt.isdigit() else None)
                escritos = 0
                with open(destino, "ab" if anadir else "wb") as f:
                    while True:
                        bloque = resp.read(1024 * 256)
                        if not bloque:
                            break
                        f.write(bloque)
                        escritos += len(bloque)
                if esperado is not None and escritos < esperado:
                    # Corte LIMPIO (EOF anticipado): read() no siempre
                    # lanza; sin esta comprobación el parcial pasaría
                    # por descarga completa. Se trata como corte más:
                    # el siguiente intento reanuda con Range.
                    raise http.client.IncompleteRead(
                        f"descarga cortada: {escritos} de {esperado} bytes",
                        esperado)
            return destino
        except urllib.error.HTTPError as exc:
            ultimo_error = exc
            if exc.code == 416 and ya > 0:
                # El rango ya no vale (parcial corrupto o era el archivo
                # entero): se borra y el siguiente intento baja de cero.
                try:
                    os.remove(destino)
                except OSError:
                    pass
            elif 400 <= exc.code < 500 and exc.code != 429:
                raise  # error del cliente: reintentar no lo arregla
        except (urllib.error.URLError, TimeoutError, OSError,
                http.client.HTTPException) as exc:
            ultimo_error = exc
        if intento + 1 < intentos and pausa:
            time.sleep(pausa * (intento + 1))
    assert ultimo_error is not None  # intentos >= 1: siempre hubo un fallo
    raise ultimo_error


def verificar_sha256(ruta: str, esperado: str) -> bool:
    if not esperado:
        return False
    return sha256_archivo(ruta).lower() == esperado.lower()


# --- Descarga de la actualización con identidad propia (v1.0.18) --------------
class ErrorHuellaActualizacion(Exception):
    """La descarga completó pero su huella no coincide ni tras
    re-descargar limpia dentro del mismo intento (nota 2)."""


def _ruta_parcial(carpeta: str, version: str) -> str:
    """El parcial de UNA actualización concreta: su nombre lleva
    la versión, así un parcial de otra versión jamás se mezcla."""
    segura = "".join(c if (c.isalnum() or c in ".-_") else "_"
                     for c in (version or "sin-version"))
    return os.path.join(carpeta, f"actualizacion-{segura}.part")


def _ruta_identidad(ruta_parcial: str) -> str:
    return ruta_parcial + ".identidad.json"


def _leer_identidad(ruta_parcial: str) -> dict:
    try:
        with open(_ruta_identidad(ruta_parcial), "r",
                  encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _guardar_identidad(ruta_parcial: str, url: str, sha256: str,
                       version: str) -> None:
    with open(_ruta_identidad(ruta_parcial), "w",
              encoding="utf-8") as f:
        json.dump({"url": url, "sha256": sha256.lower(),
                   "version": version}, f)


def _borrar_parcial(ruta_parcial: str) -> None:
    for ruta in (ruta_parcial, _ruta_identidad(ruta_parcial)):
        try:
            os.remove(ruta)
        except OSError:
            pass


def descargar_actualizacion(url: str, sha256: str, version: str,
                            carpeta: str,
                            nombre_final: str | None = None,
                            reintentos: int = 3) -> str:
    """Descarga el instalador de la actualización EN UN SOLO CLIC
    (v1.0.18, nota 2 del usuario: «la mayoría de las veces falla
    por huella y hay que pulsar otra vez»).

    La causa era el parcial compartido: un corte del hotspot se
    reanudaba o mezclaba con restos de otra descarga y la huella
    final no cuadraba. Ahora la descarga lleva IDENTIDAD PROPIA:

    - El parcial se llama por versión y guarda su identidad
      (URL + huella esperada) en un archivo hermano. Solo se
      reanuda si la identidad coincide EXACTA con lo pedido; un
      parcial ajeno o sin identidad se descarta y se baja limpio.
    - Si la huella del parcial completo no coincide, se descarta
      y se RE-DESCARGA LIMPIA dentro de la misma llamada (el
      usuario no pulsa nada más). Solo si la segunda descarga
      completa también trae otra huella se levanta
      ErrorHuellaActualizacion: eso ya es un canal corrupto, no
      un corte de red.
    - Los fallos de red de la descarga (tras sus reintentos con
      reanudación) se propagan tal cual: un clic termina en
      instalación verificada o en un error real de red.

    Devuelve la ruta final (el parcial verificado, renombrado).
    """
    if not sha256:
        raise ErrorHuellaActualizacion(
            "La actualización no trae huella esperada.")
    os.makedirs(carpeta, exist_ok=True)
    nombre = nombre_final or nombre_instalador(url)
    destino = os.path.join(carpeta, nombre)
    parcial = _ruta_parcial(carpeta, version)
    identidad = _leer_identidad(parcial)
    if not (os.path.isfile(parcial)
            and identidad.get("url") == url
            and str(identidad.get("sha256") or "").lower()
            == sha256.lower()
            and identidad.get("version") == version):
        # Parcial ajeno, de otra versión o sin identidad: jamás
        # se reanuda sobre él; la descarga empieza limpia.
        _borrar_parcial(parcial)
    for intento in range(2):
        if not os.path.isfile(parcial):
            _guardar_identidad(parcial, url, sha256, version)
        descargar_archivo(url, parcial, reintentos=reintentos)
        if verificar_sha256(parcial, sha256):
            os.replace(parcial, destino)
            try:
                os.remove(_ruta_identidad(parcial))
            except OSError:
                pass
            return destino
        # Huella mala con la descarga «completa»: parcial fuera
        # y re-descarga limpia DENTRO del mismo clic.
        _borrar_parcial(parcial)
        if intento == 1:
            raise ErrorHuellaActualizacion(
                "La huella no coincide ni tras re-descargar el "
                "instalador completo dos veces.")
    raise ErrorHuellaActualizacion("Descarga no completada.")


def comprobar_actualizacion(url_version: str, version_actual: str) -> InfoActualizacion | None:
    """Devuelve la info si hay una versión más nueva; None si no la hay.

    Lanza ErrorActualizacion clasificado si el canal falla: quien llama
    (la página, vía servicios) enseña el mensaje que corresponde a la
    causa REAL, no un genérico «revisa tu conexión»."""
    if not url_version:
        raise ErrorActualizacion("no_encontrado", "Canal sin configurar.")
    texto = descargar_texto(url_version)
    try:
        info = parsear_version_json(texto)
    except (ValueError, TypeError) as exc:
        raise ErrorActualizacion(
            "respuesta_invalida", f"El canal no devolvió un JSON válido: {exc}") from exc
    if not info.version:
        raise ErrorActualizacion(
            "respuesta_invalida", "El archivo de versión no trae campo «version».")
    return info if hay_actualizacion(version_actual, info) else None


def nombre_instalador(url: str) -> str:
    nombre = os.path.basename(url.split("?")[0]) or "AntivirusHogarPC-Setup.exe"
    if not nombre.lower().endswith(".exe"):
        nombre += ".exe"
    return nombre
