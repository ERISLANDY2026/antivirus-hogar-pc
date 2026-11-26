"""Fachada de servicios para la interfaz.

Envuelve core + winapi y traduce cualquier fallo (incluido «esto solo
funciona en Windows») a un resultado con mensaje en español, para que la
interfaz nunca se rompa: enseña el estado real o «no disponible».
"""
import json
import os
import time
from dataclasses import dataclass, field

from .. import config
from ..core.actividad import RegistroActividad
from ..core.quarantine import Cuarentena
from ..core.scancache import CacheEscaneo
from ..core.signatures import BaseFirmas
from ..winapi import WindowsNoDisponible, es_windows


@dataclass
class Resultado:
    ok: bool
    datos: object = None
    mensaje: str = ""


def seguro(funcion, *args, **kwargs) -> Resultado:
    """Ejecuta una llamada a Windows/core capturando el fallo con mensaje."""
    try:
        return Resultado(True, funcion(*args, **kwargs))
    except WindowsNoDisponible:
        return Resultado(False, None, "Disponible solo en Windows.")
    except Exception as exc:  # se enseña el motivo real, sin romper la app
        return Resultado(False, None, f"No se pudo completar: {exc}")


@dataclass
class Ajustes:
    url_actualizacion: str = config.UPDATE_VERSION_URL
    auth_key_abusech: str = ""
    letra_grande: bool = False
    fondo_animado: bool = True   # radar animado del Panel (v1.0.2)
    escaneo_semanal: bool = False
    ultimo_chequeo_actualizacion: float = 0.0
    # Arranque con Windows + rutina automática (v1.0.5, orden del
    # usuario): activados por defecto; interruptores en Ajustes.
    arranque_windows: bool = True
    rutina_automatica: bool = True
    # Idioma de la interfaz (v1.0.14, agregado del usuario):
    # «es» (por defecto, el de siempre) o «en». Lo fija el
    # selector del panel lateral y persiste entre arranques;
    # las instalaciones anteriores no lo traen y quedan en «es».
    idioma: str = "es"
    # Reconexión automática de la VPN (v1.0.16, frente 2):
    # si un túnel establecido se cae solo, el vigilante
    # reconecta sin que el usuario toque nada. Activado por
    # defecto; la desconexión MANUAL nunca se reconecta.
    vpn_reconectar_auto: bool = True
    # Escala de la interfaz (v1.0.16, frente 7): «normal» o
    # «grande» (letra y barra lateral ×1.22). Convive con el
    # letra_grande de siempre (×1.125 si escala es «normal»).
    escala_interfaz: str = "normal"
    # Programaciones (v1.0.5): lista de dicts de core.programaciones.
    programaciones: list = field(default_factory=list)

    _ruta: str = field(default="", repr=False)

    @classmethod
    def cargar(cls) -> "Ajustes":
        ruta = os.path.join(config.carpeta_datos(), "ajustes.json")
        ajustes = cls(_ruta=ruta)
        if os.path.isfile(ruta):
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                for clave, valor in datos.items():
                    if hasattr(ajustes, clave) and not clave.startswith("_"):
                        setattr(ajustes, clave, valor)
            except (OSError, ValueError):
                pass
        # Migración del canal (v1.0.5): la v1.0.1 guardó en ajustes.json
        # una url_actualizacion con un id MARCADOR («…Pendiente», un
        # archivo que nunca existió) y cada versión instalada encima la
        # heredaba, porque la app usa el ajuste guardado y no el valor
        # del código: el botón de actualizar daba «no encontrado» para
        # siempre (INFORME-CANAL.md, addenda forense). Si la URL
        # guardada no es la del código — o trae el marcador — se
        # restaura la buena y se guarda, para que el canal se repare
        # solo al abrir la app.
        guardada = ajustes.url_actualizacion or ""
        if guardada != config.UPDATE_VERSION_URL or "Pendiente" in guardada:
            ajustes.url_actualizacion = config.UPDATE_VERSION_URL
            try:
                ajustes.guardar()
            except OSError:
                pass  # la URL efectiva ya es la buena en esta sesión
        return ajustes

    def guardar(self) -> None:
        datos = {k: v for k, v in vars(self).items() if not k.startswith("_")}
        with open(self._ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)


class ServiciosApp:
    """Estado compartido de la aplicación (una instancia por ventana)."""

    def __init__(self) -> None:
        self.ajustes = Ajustes.cargar()
        self.base_firmas = BaseFirmas()
        self.base_firmas.cargar_semilla(config.carpeta_activos())
        extra = os.path.join(config.carpeta_datos(), "firmas_extra.txt")
        self.base_firmas.cargar_archivo(extra)
        self.cache = CacheEscaneo(config.ruta_bd_cache())
        self.actividad = RegistroActividad(config.ruta_actividad())
        self.cuarentena = Cuarentena(config.ruta_cuarentena())
        self.en_windows = es_windows()
        self._foto_programas: dict | None = None
        self._ultimo_escaneo: dict = {}

    # -- actividad ---------------------------------------------------------------
    def registrar_actividad(self, tipo, detalle) -> None:
        try:
            self.actividad.registrar(tipo, detalle)
        except Exception:
            pass  # el registro nunca debe romper la operación que anota

    # -- escaneo ---------------------------------------------------------------
    def registrar_escaneo(self, resultado) -> None:
        self._ultimo_escaneo = {
            "fecha": time.time(),
            "revisados": resultado.archivos_revisados,
            "hallazgos": len(resultado.hallazgos),
        }
        self.registrar_actividad(
            "escaneo",
            f"Escaneo: {resultado.archivos_revisados} archivos revisados, "
            f"{len(resultado.hallazgos)} hallazgo(s).")
        # Gancho opcional (v1.0.7): la bandeja avisa por globito si
        # un escaneo termina CON hallazgos (decidir sigue siendo del
        # usuario: la app nunca actúa sola ante una amenaza).
        gancho = getattr(self, "al_registrar_escaneo", None)
        if callable(gancho):
            try:
                gancho(dict(self._ultimo_escaneo))
            except Exception:
                pass

    def hallazgos_recientes(self) -> int:
        return int(self._ultimo_escaneo.get("hallazgos", 0))

    # -- rutas habituales -------------------------------------------------------
    @staticmethod
    def carpetas_riesgo() -> list[str]:
        hogar = os.path.expanduser("~")
        candidatas = [
            os.path.join(hogar, "Downloads"),
            os.path.join(hogar, "Descargas"),
            os.path.join(hogar, "Desktop"),
            os.path.join(hogar, "Escritorio"),
            os.path.join(hogar, "Documents"),
            os.path.join(hogar, "Documentos"),
            os.environ.get("TEMP", ""),
        ]
        return [c for c in candidatas if c and os.path.isdir(c)]

    @staticmethod
    def carpeta_descargas() -> str:
        hogar = os.path.expanduser("~")
        for nombre in ("Downloads", "Descargas"):
            ruta = os.path.join(hogar, nombre)
            if os.path.isdir(ruta):
                return ruta
        return ""
