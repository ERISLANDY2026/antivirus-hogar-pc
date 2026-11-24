"""Iconos 3D ANIMADOS del panel izquierdo (v1.0.5).

Lo que pidió el usuario: para CADA pestaña, un icono propio y
correspondiente a su función, MÁS GRANDE que el glyph anterior
(36 px lógicos en el panel), EN COLORES MODERNOS con efecto 3D y
ANIMADO con sentido:

- Paleta vibrante actual: gradientes cian/violeta/verde neón y
  compañía, dos paradas por icono, combinados con el tema de cristal.
- Efecto 3D: sombra suave desplazada, relleno en gradiente diagonal
  y GLOSS (brillo de cristal en la mitad superior).
- Animación sutil: al pasar el ratón el icono crece un poco y gana
  brillo; la pestaña SELECCIONADA pulsa despacio; el de
  «Actualizaciones» además GIRA mientras es la activa (comprobando).
- Se respeta el interruptor «Fondo animado» de Ajustes: con la
  animación apagada los iconos quedan estáticos (sin temporizador).

Los iconos se dibujan por código con QPainter (siluetas rellenas en
una caja de 48, supersampling ×2): ningún archivo externo, ningún
glyph de texto plano. ui/icons.py (iconos de FILAS de estado) no se
toca: esto es solo la navegación.
"""
import math

from PySide6.QtCore import QEvent, QObject, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QPushButton

LADO = 36        # tamaño lógico del icono en el panel (px)
_CAJA = 48.0     # caja de dibujo de cada silueta
_SS = 2          # supersampling al rasterizar

# nombre → (color claro, color oscuro) del gradiente 3D
PALETA_NAV: dict[str, tuple[str, str]] = {
    "inicio": ("#67E8F9", "#2563EB"),        # casa: cian → azul
    "escanear": ("#F0ABFC", "#A21CAF"),      # lupa: rosa → fucsia
    "proteccion": ("#4ADE80", "#059669"),    # escudo: verde neón
    "drivers": ("#FDBA74", "#EA580C"),       # chip: naranja
    "limpieza": ("#FDA4AF", "#E11D48"),      # escoba: rosa → rojo
    "discos": ("#93C5FD", "#1D4ED8"),        # disco: azul
    "actualizar": ("#BEF264", "#16A34A"),    # flechas: lima → verde
    "red": ("#C4B5FD", "#7C3AED"),           # globo: violeta
    "informes": ("#5EEAD4", "#0D9488"),      # gráfica: turquesa
    "ajustes": ("#A5B4FC", "#4F46E5"),       # engranaje: índigo
    "version": ("#FDE68A", "#D97706"),       # placa «i»: dorado
    "calendario": ("#7DD3FC", "#6D28D9"),    # calendario: cielo → violeta
}


# --- Siluetas (caja 48×48, rellenos) -------------------------------------------

def _casa(p: QPainter) -> None:
    ruta = QPainterPath()
    ruta.moveTo(24, 5)
    ruta.lineTo(43, 21)
    ruta.lineTo(38.5, 21)
    ruta.lineTo(38.5, 41)
    ruta.lineTo(29, 41)
    ruta.lineTo(29, 31.5)
    ruta.lineTo(19, 31.5)
    ruta.lineTo(19, 41)
    ruta.lineTo(9.5, 41)
    ruta.lineTo(9.5, 21)
    ruta.lineTo(5, 21)
    ruta.closeSubpath()
    p.drawPath(ruta)


def _lupa(p: QPainter, oscuro: QColor) -> None:
    p.drawEllipse(QRectF(10, 8, 24, 24))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(oscuro, 6.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(30, 30, 41, 41)
    p.setPen(Qt.PenStyle.NoPen)


def _escudo(p: QPainter, oscuro: QColor) -> None:
    ruta = QPainterPath()
    ruta.moveTo(24, 4)
    ruta.cubicTo(30, 8, 35.5, 9.5, 41, 9.5)
    ruta.lineTo(41, 21)
    ruta.cubicTo(41, 33, 34.5, 40.5, 24, 44.5)
    ruta.cubicTo(13.5, 40.5, 7, 33, 7, 21)
    ruta.lineTo(7, 9.5)
    ruta.cubicTo(12.5, 9.5, 18, 8, 24, 4)
    p.drawPath(ruta)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(255, 255, 255, 235), 3.6, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    ruta2 = QPainterPath()
    ruta2.moveTo(15.5, 24)
    ruta2.lineTo(21.5, 30.5)
    ruta2.lineTo(33, 17.5)
    p.drawPath(ruta2)
    p.setPen(Qt.PenStyle.NoPen)


def _chip(p: QPainter, oscuro: QColor) -> None:
    p.setPen(QPen(oscuro, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for t in (17, 24, 31):
        p.drawLine(t, 5, t, 12)
        p.drawLine(t, 36, t, 43)
        p.drawLine(5, t, 12, t)
        p.drawLine(36, t, 43, t)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(12, 12, 24, 24), 4, 4)
    p.setBrush(QColor(255, 255, 255, 90))
    p.drawRoundedRect(QRectF(19, 19, 10, 10), 2.5, 2.5)


def _escoba(p: QPainter, oscuro: QColor) -> None:
    p.setPen(QPen(oscuro, 4.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(33, 5, 21, 27)
    p.setPen(Qt.PenStyle.NoPen)
    ruta = QPainterPath()
    ruta.moveTo(13, 28)
    ruta.lineTo(27, 28)
    ruta.lineTo(31, 44)
    ruta.lineTo(9, 44)
    ruta.closeSubpath()
    p.drawPath(ruta)
    p.setPen(QPen(QColor(0, 0, 0, 70), 1.6))
    for x in (15, 20, 25):
        p.drawLine(x, 31, x - 1.5, 41.5)
    p.setPen(Qt.PenStyle.NoPen)


def _disco(p: QPainter, oscuro: QColor) -> None:
    p.drawEllipse(QRectF(7, 7, 34, 34))
    p.setBrush(QColor(255, 255, 255, 110))
    p.drawEllipse(QRectF(18.5, 18.5, 11, 11))
    p.setBrush(oscuro)
    p.drawEllipse(QRectF(21.8, 21.8, 4.4, 4.4))


def _actualizar(p: QPainter, oscuro: QColor) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(oscuro, 5.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawArc(QRectF(10, 10, 28, 28), -30 * 16, 285 * 16)
    p.setPen(Qt.PenStyle.NoPen)
    # Punta de flecha en el extremo superior del arco
    punta = QPainterPath()
    punta.moveTo(24, 2.5)
    punta.lineTo(31.5, 10.5)
    punta.lineTo(17.5, 12.5)
    punta.closeSubpath()
    p.drawPath(punta)


def _globo(p: QPainter, oscuro: QColor) -> None:
    p.drawEllipse(QRectF(8, 8, 32, 32))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(255, 255, 255, 150), 2.0))
    p.drawEllipse(QRectF(18, 8, 12, 32))
    p.drawLine(8.5, 24, 39.5, 24)
    p.drawArc(QRectF(8, 2, 32, 20), 0, -180 * 16)
    p.drawArc(QRectF(8, 26, 32, 20), 0, 180 * 16)
    p.setPen(Qt.PenStyle.NoPen)


def _informe(p: QPainter, oscuro: QColor) -> None:
    p.drawRoundedRect(QRectF(13, 5, 22, 38), 3.5, 3.5)
    p.setBrush(oscuro)
    for x, alto in ((18.5, 9), (24.5, 15), (30.5, 20)):
        p.drawRoundedRect(QRectF(x - 2.1, 38 - alto, 4.2, alto), 1.6, 1.6)


def _engranaje(p: QPainter, oscuro: QColor) -> None:
    p.save()
    p.translate(24, 24)
    for k in range(8):
        p.save()
        p.rotate(k * 45)
        p.drawRoundedRect(QRectF(-3.4, -20.5, 6.8, 9.5), 2.0, 2.0)
        p.restore()
    p.drawEllipse(QRectF(-13.5, -13.5, 27, 27))
    p.restore()
    p.setBrush(oscuro)
    p.drawEllipse(QRectF(19.2, 19.2, 9.6, 9.6))


def _placa_version(p: QPainter, oscuro: QColor) -> None:
    """Placa de información: círculo con la «i» en formas (punto y
    barra), sin texto."""
    p.drawEllipse(QRectF(7, 7, 34, 34))
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawEllipse(QRectF(21.4, 13.5, 5.2, 5.2))
    p.drawRoundedRect(QRectF(21.4, 22.5, 5.2, 12), 2.6, 2.6)


def _calendario(p: QPainter, oscuro: QColor) -> None:
    """Calendario: hoja con anillas arriba y rejilla de días."""
    p.drawRoundedRect(QRectF(8, 11, 32, 30), 4.5, 4.5)
    p.setBrush(QColor(255, 255, 255, 235))
    for x in (16.5, 29.5):
        p.drawRoundedRect(QRectF(x - 1.8, 5.5, 3.6, 10), 1.8, 1.8)
    p.setBrush(QColor(255, 255, 255, 150))
    p.drawRect(QRectF(8, 19.5, 32, 2.2))
    p.setBrush(oscuro)
    for fila_y in (27.5, 34.5):
        for col_x in (14.5, 22.0, 29.5):
            p.drawEllipse(QRectF(col_x - 1.7, fila_y - 1.7, 3.4, 3.4))


_DIBUJOS = {
    "inicio": lambda p, o: _casa(p),
    "escanear": _lupa,
    "proteccion": _escudo,
    "drivers": _chip,
    "limpieza": _escoba,
    "discos": lambda p, o: _disco(p, o),
    "actualizar": _actualizar,
    "red": _globo,
    "informes": _informe,
    "ajustes": _engranaje,
    "version": _placa_version,
    "calendario": _calendario,
}


def _silueta(nombre: str, p: QPainter, claro: QColor, oscuro: QColor) -> None:
    grad = QLinearGradient(0, 0, _CAJA, _CAJA)
    grad.setColorAt(0.0, claro)
    grad.setColorAt(1.0, oscuro)
    p.setBrush(QBrush(grad))
    p.setPen(Qt.PenStyle.NoPen)
    _DIBUJOS[nombre](p, oscuro)


def _mezcla(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(int(a.red() + (b.red() - a.red()) * t),
                  int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


def pixmap_nav(nombre: str, escala: float = 1.0, brillo: float = 0.0,
               rotacion: float = 0.0, dy: float = 0.0,
               barrido: float = -1.0) -> QPixmap:
    """El icono de una pestaña como QPixmap de LADO×LADO lógicos.

    escala: pulso/hover (1.0 = reposo). brillo: 0..1 de luz extra.
    rotacion: grados (la vuelta de «Actualizaciones» al comprobar).
    dy: flotación vertical en px lógicos (animación continua).
    barrido: 0..1 = posición de la banda de brillo que cruza el
    icono (animación continua); fuera de ese rango no se dibuja.

    3D reforzado (v1.0.6, nota del usuario: «no están en 3D»):
    EXTRUSIÓN oscura bajo el cuerpo (borde de profundidad abajo),
    sombra más profunda, gradiente de TRES paradas (luz arriba,
    color pleno en el centro, sombra abajo) y gloss de cristal más
    marcado en la mitad superior.
    """
    claro_hex, oscuro_hex = PALETA_NAV[nombre]
    claro, oscuro = QColor(claro_hex), QColor(oscuro_hex)
    pm = QPixmap(LADO * _SS, LADO * _SS)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    factor = (LADO * _SS) / _CAJA
    p.translate(LADO * _SS / 2, LADO * _SS / 2 + dy * _SS)
    p.scale(factor * escala, factor * escala)
    if rotacion:
        p.rotate(rotacion)
    p.translate(-_CAJA / 2, -_CAJA / 2)
    # Sombra suave y profunda del cuerpo 3D
    p.save()
    p.translate(0, 3.4)
    p.setBrush(QColor(0, 0, 0, 120))
    p.setPen(Qt.PenStyle.NoPen)
    _DIBUJOS[nombre](p, QColor(0, 0, 0, 120))
    p.restore()
    # EXTRUSIÓN: la silueta en el tono oscuro, desplazada hacia
    # abajo — el «canto» que da volumen al mirar el icono.
    p.save()
    p.translate(0, 2.2)
    p.setBrush(oscuro.darker(145))
    p.setPen(Qt.PenStyle.NoPen)
    _DIBUJOS[nombre](p, oscuro.darker(145))
    p.restore()
    # Cuerpo en gradiente de tres paradas
    grad = QLinearGradient(0, 0, _CAJA * 0.35, _CAJA)
    grad.setColorAt(0.0, _mezcla(claro, QColor(255, 255, 255), 0.22))
    grad.setColorAt(0.45, claro)
    grad.setColorAt(1.0, oscuro)
    p.setBrush(QBrush(grad))
    p.setPen(Qt.PenStyle.NoPen)
    _DIBUJOS[nombre](p, oscuro)
    # Gloss de cristal: luz fuerte en la mitad superior (SourceAtop:
    # solo sobre el cuerpo ya dibujado, nunca sobre el fondo).
    p.save()
    p.setCompositionMode(
        QPainter.CompositionMode.CompositionMode_SourceAtop)
    p.setClipRect(QRectF(0, 0, _CAJA, _CAJA * 0.52))
    gloss = QLinearGradient(0, 0, 0, _CAJA * 0.52)
    gloss.setColorAt(0.0, QColor(255, 255, 255, 140))
    gloss.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setBrush(gloss)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(2, -12, _CAJA - 4, 30))
    p.restore()
    if brillo > 0.01:  # luz extra de hover/selección
        p.save()
        p.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceAtop)
        p.setBrush(QColor(255, 255, 255, int(70 * min(brillo, 1.0))))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(0, 0, _CAJA, _CAJA))
        p.restore()
    if 0.0 <= barrido <= 1.0:
        # Banda de brillo que CRUZA el icono (SourceAtop: solo
        # pinta donde ya hay icono, no sobre el fondo transparente).
        p.save()
        p.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceAtop)
        p.translate(_CAJA / 2, _CAJA / 2)
        p.rotate(24)
        x = -_CAJA * 1.1 + barrido * _CAJA * 2.2
        banda = QLinearGradient(x - 7, 0, x + 7, 0)
        banda.setColorAt(0.0, QColor(255, 255, 255, 0))
        banda.setColorAt(0.5, QColor(255, 255, 255, 95))
        banda.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(banda)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(QRectF(x - 7, -_CAJA, 14, _CAJA * 2))
        p.restore()
    p.end()
    pm.setDevicePixelRatio(_SS)
    return pm


def icono_nav(nombre: str) -> QIcon:
    return QIcon(pixmap_nav(nombre))


class AnimadorIconoNav(QObject):
    """Anima el icono de UN botón de navegación (ver docstring del módulo).

    v1.0.6 (nota del usuario: «no tienen animación»): en la 1.0.5
    SOLO se movía la pestaña activa o la que tenía el ratón encima,
    y con una amplitud mínima (±5 %): el panel se veía congelado.
    Ahora, con la animación encendida, TODOS los iconos se mueven
    de continuo y de forma VISIBLE: flotan suave (suben y bajan
    ±1,6 px, desfasados entre sí) y una banda de brillo cruza cada
    icono cada pocos segundos; la activa además pulsa más grande
    y «Actualizaciones» gira mientras es la activa. Todo cuelga
    del RELOJ compartido (ui.animacion): un solo temporizador
    para la app, y la puerta global de Ajustes lo apaga todo.

    Con animado=False o la puerta global apagada no hay suscripción
    al reloj: el icono queda estático en reposo.
    """

    def __init__(self, boton: QPushButton, nombre: str,
                 animado: bool = True, girar: bool = False,
                 parent: QObject | None = None, desfase: float = 0.0):
        super().__init__(parent or boton)
        self._boton = boton
        self._nombre = nombre
        self._girar = bool(girar)
        self._animado = bool(animado)
        self._desfase = float(desfase)
        self._hover = False
        self._activo = False
        self._escala = 1.0
        self._brillo = 0.0
        self._rotacion = 0.0
        self._dy = 0.0
        self._barrido = -1.0
        self._suscrito = False
        self._ultima_clave: tuple | None = None
        boton.installEventFilter(self)
        self._sincronizar_suscripcion()
        self._pintar(forzar=True)

    # -- API ----------------------------------------------------------------------
    def fijar_activo(self, activo: bool) -> None:
        self._activo = bool(activo)
        if not self._activo:
            self._rotacion = 0.0
        self._pintar(forzar=True)

    def fijar_animado(self, animado: bool) -> None:
        self._animado = bool(animado)
        self._sincronizar_suscripcion()
        if not self._animado:
            self._escala, self._brillo, self._rotacion = 1.0, 0.0, 0.0
            self._dy, self._barrido = 0.0, -1.0
        self._pintar(forzar=True)

    def animando(self) -> bool:
        return self._suscrito

    # -- internos -------------------------------------------------------------------
    def eventFilter(self, objeto, evento):  # noqa: N802 - nombre de Qt
        if objeto is self._boton:
            if evento.type() == QEvent.Type.Enter:
                self._hover = True
            elif evento.type() == QEvent.Type.Leave:
                self._hover = False
        return super().eventFilter(objeto, evento)

    def _sincronizar_suscripcion(self) -> None:
        from .animacion import RELOJ, animaciones_activas

        quiere = self._animado and animaciones_activas()
        if quiere and not self._suscrito:
            RELOJ.tic.connect(self._tic)
            RELOJ.suscribir()
            self._suscrito = True
        elif not quiere and self._suscrito:
            RELOJ.tic.disconnect(self._tic)
            RELOJ.desuscribir()
            self._suscrito = False

    def _tic(self, t: float) -> None:
        # Flotación continua de TODOS los iconos (desfasada).
        self._dy = 1.6 * math.sin(t * 1.85 + self._desfase * 2.1)
        # Banda de brillo: cruza cada ~4,6 s, desfasada por icono.
        ciclo = (t + self._desfase * 1.37) % 4.6
        self._barrido = ciclo / 0.9 if ciclo < 0.9 else -1.0
        if self._activo:
            self._escala = 1.07 + 0.045 * math.sin(t * 3.6)
            self._brillo = 0.5 + 0.28 * math.sin(t * 3.6)
            if self._girar:
                self._rotacion = (self._rotacion + 7.0) % 360.0
        elif self._hover:
            self._escala, self._brillo = 1.13, 0.6
        else:
            self._escala, self._brillo = 1.0, 0.12
        self._pintar()

    def _pintar(self, forzar: bool = False) -> None:
        # Cuantizar: solo se repinta si el cuadro cambia de verdad
        # (rendimiento: 12 iconos × 20 fps sin trabajo inútil).
        clave = (round(self._escala, 3), round(self._brillo, 2),
                 round(self._rotacion), round(self._dy * 2),
                 round(self._barrido, 2) if self._barrido >= 0 else -1)
        if not forzar and clave == self._ultima_clave:
            return
        self._ultima_clave = clave
        self._boton.setIcon(QIcon(pixmap_nav(
            self._nombre, self._escala, self._brillo, self._rotacion,
            dy=self._dy, barrido=self._barrido)))
