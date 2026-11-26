"""Anti-ransomware propio en modo usuario (v1.0.21).

Dos capas honestas, sin prometer lo que un programa sin kernel no
puede prometer (NO es intercepción garantizada: es detección y
contención temprana, como el concepto CryptoDrop):

1. Archivos SEÑUELO en las carpetas protegidas: documentos con un
   contenido-marca que nadie debe tocar. Si un señuelo cambia o
   desaparece, algo está tocando la carpeta: aviso inmediato.
2. Vigilancia de RÁFAGAS: fotos periódicas de las carpetas
   protegidas; si en una ventana corta cambian muchos archivos Y
   su contenido nuevo tiene entropía de cifrado, es la firma
   clásica de un ransomware en marcha: aviso claro.

Al dispararse, la app AVISA (ese es su modo de nacimiento: «solo
avisar»). La contención —suspender el proceso sospechoso— solo
ocurre si el usuario la ordena en el propio aviso, nunca sola.
El vigilante no eleva privilegios ni toca Defender: convive con
CFA, no lo sustituye.
"""
import hashlib
import json
import os
import time
from dataclasses import dataclass, field

from .. import config
from .hashing import entropia_shannon

MARCA_SENUELO = "ANTIVIRUS-HOGAR-PC SEÑUELO"
NOMBRES_SENUELO = (
    "00-copia-de-seguridad.txt",
    "00-respaldo-documentos.docx",
    "00-notas-importantes.txt",
)
UMBRAL_RAFAGA = 8            # archivos tocados en la ventana
UMBRAL_ENTROPIA = 7.2        # entropía media de lo tocado
VENTANA_SEGUNDOS = 120       # ventana de la ráfaga


@dataclass
class AlertaRansomware:
    motivo: str  # senuelo|rafaga
    detalle: str = ""
    archivos: list[str] = field(default_factory=list)
    procesos: list[dict] = field(default_factory=list)


# --- Señuelos ---------------------------------------------------------------

def _ruta_registro() -> str:
    return os.path.join(config.carpeta_datos(), "senuelos.json")


def _huella_contenido(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def contenido_senuelo(nombre: str) -> str:
    return (f"{MARCA_SENUELO}\nArchivo señuelo de Antivirus Hogar PC "
            f"({nombre}).\nNadie debe modificarlo: si cambia, la app "
            "avisa de actividad sospechosa en esta carpeta.\n")


def crear_senuelos(carpetas: list[str]) -> dict[str, list[str]]:
    """Crea los señuelos que falten y (re)escribe el registro.

    Devuelve {carpeta: [rutas]} con lo que quedó sembrado.
    Idempotente: un señuelo sano no se reescribe.
    """
    registro: dict[str, str] = {}
    sembrados: dict[str, list[str]] = {}
    for carpeta in carpetas:
        rutas: list[str] = []
        if not carpeta or not os.path.isdir(carpeta):
            continue
        for nombre in NOMBRES_SENUELO:
            ruta = os.path.join(carpeta, nombre)
            contenido = contenido_senuelo(nombre)
            try:
                if os.path.isfile(ruta):
                    with open(ruta, "r", encoding="utf-8",
                              errors="replace") as fh:
                        actual = fh.read()
                    if MARCA_SENUELO not in actual:
                        # Hay un archivo del usuario con ese nombre:
                        # no se pisa jamás.
                        continue
                else:
                    with open(ruta, "w", encoding="utf-8") as fh:
                        fh.write(contenido)
                registro[ruta] = _huella_contenido(contenido)
                rutas.append(ruta)
            except OSError:
                continue
        if rutas:
            sembrados[carpeta] = rutas
    try:
        os.makedirs(config.carpeta_datos(), exist_ok=True)
        with open(_ruta_registro(), "w", encoding="utf-8") as fh:
            json.dump(registro, fh, ensure_ascii=False, indent=1)
    except OSError:
        pass
    return sembrados


def verificar_senuelos() -> list[str]:
    """Rutas de señuelos borrados o alterados desde el registro."""
    try:
        with open(_ruta_registro(), "r", encoding="utf-8") as fh:
            registro = json.load(fh)
    except (OSError, ValueError):
        return []
    tocados: list[str] = []
    for ruta, huella in (registro or {}).items():
        try:
            with open(ruta, "r", encoding="utf-8",
                      errors="replace") as fh:
                actual = fh.read()
        except OSError:
            tocados.append(ruta)  # borrado o ilegible
            continue
        if _huella_contenido(actual) != huella:
            tocados.append(ruta)
    return tocados


# --- Ráfagas ------------------------------------------------------------------

def foto_carpeta(carpeta: str, limite: int = 20000) -> dict[str, tuple]:
    """{ruta: (mtime, tamaño)} de los archivos de una carpeta."""
    foto: dict[str, tuple] = {}
    if not carpeta or not os.path.isdir(carpeta):
        return foto
    for raiz, _dirs, archivos in os.walk(carpeta):
        for nombre in archivos:
            if len(foto) >= limite:
                return foto
            ruta = os.path.join(raiz, nombre)
            try:
                st = os.stat(ruta)
            except OSError:
                continue
            foto[ruta] = (st.st_mtime, st.st_size)
    return foto


def _entropia_de(ruta: str) -> float:
    try:
        with open(ruta, "rb") as fh:
            return entropia_shannon(fh.read(256 * 1024))
    except OSError:
        return 0.0


def analizar_cambios(antes: dict, despues: dict,
                     ahora: float | None = None) -> AlertaRansomware | None:
    """¿La diferencia entre dos fotos huele a cifrado masivo?

    Pura y probable: ráfaga = al menos UMBRAL_RAFAGA archivos
    modificados dentro de la ventana Y entropía media de lo
    modificado ≥ UMBRAL_ENTROPIA (contenido cifrado/comprimido).
    """
    ahora = time.time() if ahora is None else ahora
    tocados: list[str] = []
    for ruta, (mtime, tam) in despues.items():
        previo = antes.get(ruta)
        if previo is None:
            continue  # archivo nuevo: no cuenta como cifrado de uno viejo
        if previo != (mtime, tam) and ahora - mtime <= VENTANA_SEGUNDOS:
            tocados.append(ruta)
    if len(tocados) < UMBRAL_RAFAGA:
        return None
    entropias = [_entropia_de(r) for r in tocados[:40]]
    media = sum(entropias) / max(1, len(entropias))
    if media < UMBRAL_ENTROPIA:
        return None
    return AlertaRansomware(
        motivo="rafaga",
        detalle=(f"{len(tocados)} archivos modificados en menos de "
                 f"{VENTANA_SEGUNDOS} s con entropía media "
                 f"{media:.2f} (contenido posiblemente cifrado)."),
        archivos=tocados[:40])


def procesos_recientes(segundos: int = VENTANA_SEGUNDOS) -> list[dict]:
    """Procesos creados dentro de la ventana: candidatos a revisar.

    Solo lectura (psutil). Suspenderlos es decisión del usuario
    en el aviso, nunca automática.
    """
    try:
        import psutil
    except Exception:
        return []
    ahora = time.time()
    salida: list[dict] = []
    propio = os.getpid()
    for proc in psutil.process_iter(["pid", "name", "create_time", "exe"]):
        try:
            info = proc.info
            if info["pid"] == propio:
                continue
            if ahora - float(info["create_time"] or 0) <= segundos:
                salida.append({"pid": info["pid"],
                               "nombre": info["name"] or "",
                               "exe": info["exe"] or ""})
        except Exception:
            continue
    return salida


def suspender_proceso(pid: int) -> bool:
    """Suspensión en modo usuario (psutil). La llama SOLO la
    interfaz tras la confirmación expresa del usuario en el aviso."""
    try:
        import psutil

        psutil.Process(int(pid)).suspend()
        return True
    except Exception:
        return False
