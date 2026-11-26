"""Iconos 3D dentro de las PÁGINAS (v1.0.16, frente 5).

En la 1.0.15 el acabado gráfico 3D llegó al panel izquierdo,
pero las filas de estado de las páginas (fila_estado: Defender,
firewall, actualizaciones, disco…) seguían con el dibujo SVG
por código de ui/icons.py. Desde esta versión esas filas usan
el MISMO acabado:

- Las identidades que ya existen como recurso de navegación
  se reutilizan (escudo→proteccion, lupa→escanear, …) y se
  componen con pixmap_nav (las transformaciones de siempre).
- Las que faltaban (llama del firewall, carpeta de la
  protección contra ransomware, alerta, wifi) se generaron con
  el mismo procedimiento (lámina sobre magenta → PNG con alfa)
  y viven en assets/iconos3d/paginas/ — subcarpeta para no
  tocar el invariante de los 12 de navegación.
- La animación cuelga del RELOJ compartido de ui.animacion,
  con los mismos modos que el SVG (pulso, giro, llama,
  parpadeo) y las mismas puertas: interruptor de Ajustes,
  pausa con la ventana oculta y ahorro por batería. Sin
  recurso o con un fallo al componer, la fila cae al
  IconoAnimado SVG de siempre: nunca una fila sin icono.
"""
import math
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

# Icono de fila (nombre de ui/icons.py) → recurso 3D existente.
MAPA_RECURSOS_NAV = {
    "escudo": "proteccion",
    "lupa": "escanear",
    "actualizar": "actualizar",
    "disco": "discos",
    "inicio": "inicio",
    "limpieza": "limpieza",
    "red": "red",
    "informe": "informes",
    "chip": "drivers",
    "engranaje": "ajustes",
}
# Iconos generados para las páginas (assets/iconos3d/paginas/).
PROPIOS_PAGINA = ("llama", "carpeta", "alerta", "wifi")

_cache_propios: dict[str, QPixmap | None] = {}


def _ruta_propio(nombre: str) -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "iconos3d", "paginas", f"{nombre}.png")


def _recurso_propio(nombre: str) -> QPixmap | None:
    if nombre not in _cache_propios:
        ruta = _ruta_propio(nombre)
        pm = QPixmap(ruta) if os.path.isfile(ruta) else None
        _cache_propios[nombre] = None if pm is None or pm.isNull() else pm
    return _cache_propios[nombre]


def recurso_para(nombre: str) -> tuple[str, str] | None:
    """(tipo, nombre) del recurso 3D de un icono de fila:
    ("nav", recurso) si reutiliza uno de navegación,
    ("pagina", nombre) si es de los generados para páginas,
    None si no hay recurso (la fila usa el SVG de respaldo)."""
    from .iconos_nav import _recurso_3d

    if nombre in MAPA_RECURSOS_NAV:
        recurso = MAPA_RECURSOS_NAV[nombre]
        if _recurso_3d(recurso) is not None:
            return ("nav", recurso)
    if nombre in PROPIOS_PAGINA and _recurso_propio(nombre) is not None:
        return ("pagina", nombre)
    return None


class IconoEstado3D(QLabel):
    """El icono 3D de una fila de estado, animado por el reloj
    compartido con el modo de la fila (pulso/giro/llama/
    parpadeo/estatico)."""

    def __init__(self, nombre: str, modo: str = "estatico",
                 tamano: int = 30, parent=None):
        super().__init__(parent)
        self._nombre = nombre
        self._modo = modo
        self._tamano = tamano
        self._suscrito = False
        self.setFixedSize(tamano, tamano)
        self._pintar(0.0)

    # -- composición ---------------------------------------------------------
    def _pintar(self, t: float) -> None:
        escala, brillo, rotacion = 1.0, 0.0, 0.0
        if self._modo == "pulso":
            escala = 1.0 + 0.07 * math.sin(t * 3.0)
        elif self._modo == "giro":
            rotacion = (t * 40.0) % 360.0
        elif self._modo == "llama":
            brillo = 0.35 + 0.35 * math.sin(t * 5.0)
        elif self._modo == "parpadeo":
            brillo = 0.7 if math.sin(t * 2.2) > 0 else 0.0
        try:
            hallado = recurso_para(self._nombre)
            if hallado is None:
                return
            tipo, nombre = hallado
            if tipo == "nav":
                from .iconos_nav import pixmap_nav

                pm = pixmap_nav(nombre, escala=escala,
                                brillo=max(0.0, brillo),
                                rotacion=rotacion)
            else:
                from .iconos_nav import _pixmap_desde_recurso

                pm = _pixmap_desde_recurso(
                    nombre, _recurso_propio(nombre), escala,
                    max(0.0, brillo), rotacion, 0.0, -1.0)
            lado = self._tamano * 2
            pm = pm.scaled(lado, lado, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            pm.setDevicePixelRatio(2)
            self.setPixmap(pm)
        except Exception:
            pass  # un icono jamás rompe la fila que lo enseña

    # -- suscripción al reloj compartido --------------------------------------
    def showEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        super().showEvent(evento)
        if self._modo != "estatico" and not self._suscrito:
            from .animacion import RELOJ

            RELOJ.tic.connect(self._al_tic)
            RELOJ.suscribir()
            self._suscrito = True

    def hideEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        super().hideEvent(evento)
        if self._suscrito:
            from .animacion import RELOJ

            try:
                RELOJ.tic.disconnect(self._al_tic)
            except (RuntimeError, TypeError):
                pass
            RELOJ.desuscribir()
            self._suscrito = False

    def _al_tic(self, t: float) -> None:
        self._pintar(t)
