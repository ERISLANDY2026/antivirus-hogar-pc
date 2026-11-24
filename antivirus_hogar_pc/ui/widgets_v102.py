"""Widgets visuales de la v1.0.2: color, RGB animado y porcentajes.

El usuario pidió que la interfaz dejara de ser «aburrida»: barras con
el porcentaje SIEMPRE visible, efectos RGB y botones con vida. Aquí
viven las piezas que el QSS solo no puede hacer (animación real):

- BarraProgreso: QProgressBar pintada a mano (paintEvent) con un
  gradiente RGB que se desplaza con un QTimer (~60 ms). El texto sale
  de core.v102: % REAL cuando se puede contar; texto de etapa cuando
  la operación no da % real (p. ej. Windows Update) — nunca un %
  inventado.
- BotonPulso: botón con brillo cian al pasar el mouse y pulso
  opcional para la acción principal de cada pantalla.
- Medidor: fila compacta «título + barra + detalle» (CPU, RAM, disco).
- TarjetaAnimada: la tarjeta de siempre (objectName «tarjeta», fondo
  TARJETA, radio 15) que, cuando está activa, dibuja su borde con un
  gradiente RGB animado.

La animación solo corre mientras el widget está visible y en un modo
con sentido (determinado/etapas); al ocultarse, el temporizador para.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from ..core.v102 import porcentaje, texto_etapa, texto_porcentaje
from . import theme

# Matices base del arcoíris del chunk/borde (en vueltas HSV, 0–1):
# cian → verde → violeta → rosa → ámbar y vuelta a empezar.
_MATICES = (0.52, 0.38, 0.75, 0.93, 0.10)


def _colores_rgb(desplazamiento: float, ancho: float) -> QLinearGradient:
    """Gradiente horizontal con los matices rotados por `desplazamiento`.

    El gradiente cubre el ANCHO COMPLETO de la barra (no solo el chunk)
    para que el color fluya continuo a medida que el chunk crece.
    """
    grad = QLinearGradient(0.0, 0.0, max(1.0, ancho), 0.0)
    n = len(_MATICES)
    for i in range(n + 1):
        matiz = (_MATICES[i % n] + desplazamiento) % 1.0
        grad.setColorAt(i / n, QColor.fromHsvF(matiz, 0.72, 0.96))
    return grad


class BarraProgreso(QProgressBar):
    """Barra determinada con gradiente RGB animado y texto honesto.

    Modos:
    - determinado: % real con fijar(parte, total, unidad).
    - etapas: pasos sin % (fijar_etapas) para operaciones donde el
      sistema no expone un porcentaje real.
    - indeterminado visual: fijar_texto(texto) enseña la etapa en curso.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        # El texto lo pintamos nosotros en paintEvent (centrado, negrita).
        self.setTextVisible(False)
        self.setMinimumHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._modo = "determinado"  # determinado | etapas | indeterminado
        self._texto = ""
        self._desplazamiento = 0.0
        self._temporizador = QTimer(self)
        self._temporizador.setInterval(60)
        self._temporizador.timeout.connect(self._avanzar_rgb)

    # -- API pública ------------------------------------------------------
    def fijar(self, parte: float, total: float, unidad: str = "") -> None:
        """Progreso real contado: «37 % · 12 de 32 archivos».

        Si no hay total válido no se inventa nada: se delega a
        fijar_texto("…") y la barra queda en modo indeterminado visual.
        """
        pct = porcentaje(parte, total)
        if pct is None:
            self.fijar_texto("…")
            return
        self._modo = "determinado"
        self.setValue(pct)
        self._texto = texto_porcentaje(parte, total, unidad)
        self._actualizar_animacion()
        self.update()

    def fijar_etapas(self, paso: int, total: int, etapa: str) -> None:
        """Progreso por pasos SIN porcentaje: «Paso 2 de 3 · Instalando…».

        Para operaciones donde Windows no da un % real (Windows Update):
        la barra se llena por pasos completados, pero el texto jamás
        muestra un porcentaje.
        """
        self._modo = "etapas"
        pct = porcentaje(paso, total)
        self.setValue(pct if pct is not None else 0)
        self._texto = texto_etapa(paso, total, etapa)
        self._actualizar_animacion()
        self.update()

    def fijar_texto(self, texto: str) -> None:
        """Modo indeterminado visual: solo el texto de la etapa en curso."""
        self._modo = "indeterminado"
        self.setValue(0)
        self._texto = texto
        self._actualizar_animacion()
        self.update()

    def terminar(self, texto: str = "100 %") -> None:
        """Cierra la operación: barra llena, texto final, animación parada."""
        self._modo = "determinado"
        self.setValue(self.maximum())
        self._texto = texto
        self._temporizador.stop()
        self.update()

    # -- Uso interno (Medidor, en este mismo módulo) -----------------------
    def _poner_porcentaje(self, pct: float) -> None:
        """Fija la barra con un % ya calculado (medidores CPU/RAM/disco)."""
        valor = max(0, min(100, int(round(pct))))
        self._modo = "determinado"
        self.setValue(valor)
        self._texto = f"{valor} %"
        self._actualizar_animacion()
        self.update()

    # -- Animación ----------------------------------------------------------
    def _avanzar_rgb(self) -> None:
        self._desplazamiento = (self._desplazamiento + 0.015) % 1.0
        self.update()

    def _actualizar_animacion(self) -> None:
        """El RGB solo corre visible, en modo determinado/etapas y
        con la puerta global de animaciones encendida (v1.0.6)."""
        from .animacion import animaciones_activas

        if self.isVisible() and animaciones_activas() \
                and self._modo in ("determinado", "etapas"):
            if not self._temporizador.isActive():
                self._temporizador.start()
        else:
            self._temporizador.stop()

    def showEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        super().showEvent(evento)
        self._actualizar_animacion()

    def hideEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        self._temporizador.stop()
        super().hideEvent(evento)

    # -- Pintura --------------------------------------------------------------
    def paintEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        recto = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radio = recto.height() / 2.0

        # Fondo oscuro con borde (mismo papel que el QSS de respaldo).
        camino = QPainterPath()
        camino.addRoundedRect(recto, radio, radio)
        pintor.fillPath(camino, QColor("#101827"))
        pintor.setPen(QPen(QColor(theme.BORDE), 1))
        pintor.drawPath(camino)

        # Chunk con el gradiente RGB animado, recortado a la pastilla.
        if self._modo == "indeterminado":
            fraccion = 0.0
        else:
            rango = self.maximum() - self.minimum()
            fraccion = (self.value() - self.minimum()) / rango if rango > 0 else 0.0
        if fraccion > 0:
            pintor.save()
            pintor.setClipPath(camino)
            ancho_chunk = recto.width() * max(0.0, min(1.0, fraccion))
            chunk = QRectF(recto.left(), recto.top(), ancho_chunk, recto.height())
            pintor.fillRect(chunk, _colores_rgb(self._desplazamiento, recto.width()))
            pintor.restore()

        # Texto centrado en negrita, con sombra para que se lea sobre
        # el chunk brillante y sobre el fondo oscuro a la vez.
        if self._texto:
            fuente = self.font()
            fuente.setBold(True)
            fuente.setPointSize(11)
            pintor.setFont(fuente)
            pintor.setPen(QColor(0, 0, 0, 170))
            pintor.drawText(recto.translated(0, 1), Qt.AlignmentFlag.AlignCenter, self._texto)
            pintor.setPen(QColor(theme.TEXTO))
            pintor.drawText(recto, Qt.AlignmentFlag.AlignCenter, self._texto)
        pintor.end()


class BotonPulso(QPushButton):
    """Botón con brillo cian al pasar el mouse y pulso opcional.

    El pulso (activar_pulso(True)) hace palpitar el brillo de la sombra:
    es para LA acción principal de la pantalla (escanear, actualizar…),
    para que el ojo vaya solo a ella.
    """

    def __init__(self, texto: str = "", parent: QWidget | None = None) -> None:
        super().__init__(texto, parent)
        self._sombra = QGraphicsDropShadowEffect(self)
        self._sombra.setColor(QColor(theme.CIAN))
        self._sombra.setOffset(0, 0)
        self._sombra.setBlurRadius(0)
        self.setGraphicsEffect(self._sombra)
        self._pulso_activo = False
        self._sobre = False  # el mouse está encima
        self._fase = 0.0
        self._temporizador = QTimer(self)
        self._temporizador.setInterval(50)
        self._temporizador.timeout.connect(self._palpitar)

    def activar_pulso(self, activo: bool) -> None:
        """Enciende/apaga el palpitar del brillo (acción principal)."""
        from .animacion import animaciones_activas

        self._pulso_activo = bool(activo) and animaciones_activas()
        if self._pulso_activo and self.isVisible():
            self._temporizador.start()
        else:
            self._temporizador.stop()
            self._aplicar_brillo_base()

    def enterEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        self._sobre = True
        if not self._pulso_activo:
            self._sombra.setBlurRadius(18)
            color = QColor(theme.CIAN)
            color.setAlpha(190)
            self._sombra.setColor(color)
        super().enterEvent(evento)

    def leaveEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        self._sobre = False
        if not self._pulso_activo:
            self._sombra.setBlurRadius(0)
        super().leaveEvent(evento)

    def showEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        super().showEvent(evento)
        if self._pulso_activo:
            self._temporizador.start()

    def hideEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        self._temporizador.stop()
        super().hideEvent(evento)

    def _palpitar(self) -> None:
        self._fase += 0.18
        onda = (math.sin(self._fase) + 1.0) / 2.0  # 0..1 suave
        self._sombra.setBlurRadius(12 + 16 * onda)
        color = QColor(theme.CIAN)
        color.setAlpha(int(120 + 120 * onda))
        self._sombra.setColor(color)

    def _aplicar_brillo_base(self) -> None:
        if self._sobre:
            self._sombra.setBlurRadius(18)
            color = QColor(theme.CIAN)
            color.setAlpha(190)
            self._sombra.setColor(color)
        else:
            self._sombra.setBlurRadius(0)


class Medidor(QWidget):
    """Fila compacta: título + BarraProgreso + detalle (CPU, RAM, disco)."""

    def __init__(self, titulo: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(10)
        self._lbl_titulo = QLabel(titulo)
        self._lbl_titulo.setMinimumWidth(110)
        self._lbl_titulo.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(self._lbl_titulo)
        self.barra = BarraProgreso()
        layout.addWidget(self.barra, 1)
        self._lbl_detalle = QLabel("")
        self._lbl_detalle.setObjectName("detalle")
        layout.addWidget(self._lbl_detalle)

    def fijar(self, pct: float | None, detalle: str = "") -> None:
        """pct None = dato no disponible: la barra muestra «—», sin inventar."""
        if pct is None:
            self.barra.fijar_texto("—")
        else:
            self.barra._poner_porcentaje(pct)
        self._lbl_detalle.setText(detalle)


class TarjetaAnimada(QFrame):
    """La tarjeta del tema (objectName «tarjeta»): VIDRIO + borde con
    movimiento (v1.0.6, nota 7 del usuario: acabado moderno en TODAS
    las secciones).

    - Efecto de vidrio siempre: sobre el fondo del QSS se pinta un
      brillo vertical suave (luz arriba, transparente abajo),
      recortado a la esquina redondeada.
    - Borde con vida: con las animaciones encendidas (puerta global
      de ui.animacion) y la tarjeta visible, un gradiente de color
      tenue RECORRE el borde despacio, colgando del RELOJ compartido
      (un solo temporizador para toda la app; al ocultarse la
      tarjeta se desuscribe y no gasta nada).
    - fijar_activa(True) mantiene el borde RGB fuerte de «tarjeta
      en curso» de la v1.0.2, con el mismo recorrido.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tarjeta")
        self._activa = False
        self._desplazamiento = 0.0
        self._suscrita = False
        self._ultimo_tic = -1

    def fijar_activa(self, activa: bool) -> None:
        """Activa/apaga el borde RGB fuerte de la tarjeta."""
        self._activa = bool(activa)
        self.update()

    def showEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        super().showEvent(evento)
        self._sincronizar_suscripcion()

    def hideEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        self._desuscribir()
        super().hideEvent(evento)

    def _sincronizar_suscripcion(self) -> None:
        from .animacion import RELOJ, animaciones_activas

        if animaciones_activas() and not self._suscrita:
            RELOJ.tic.connect(self._al_tic)
            RELOJ.suscribir()
            self._suscrita = True

    def _desuscribir(self) -> None:
        if self._suscrita:
            from .animacion import RELOJ

            RELOJ.tic.disconnect(self._al_tic)
            RELOJ.desuscribir()
            self._suscrita = False

    def _al_tic(self, t: float) -> None:
        # Cuantizado a 0,1 s: el borde se mueve sin repintar de más.
        paso = int(t * 10)
        if paso == self._ultimo_tic:
            return
        self._ultimo_tic = paso
        self._desplazamiento = (t * 0.045) % 1.0
        self.update()

    def paintEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        # Primero la tarjeta normal del QSS (fondo TARJETA + borde BORDE).
        super().paintEvent(evento)
        from .animacion import animaciones_activas

        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        recto = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        camino = QPainterPath()
        camino.addRoundedRect(QRectF(self.rect()), 15, 15)
        # Vidrio: luz suave en la mitad superior.
        pintor.save()
        pintor.setClipPath(camino)
        vidrio = QLinearGradient(0, 0, 0, self.height())
        vidrio.setColorAt(0.0, QColor(190, 225, 255, 26))
        vidrio.setColorAt(0.45, QColor(190, 225, 255, 7))
        vidrio.setColorAt(1.0, QColor(190, 225, 255, 0))
        pintor.fillRect(self.rect(), vidrio)
        pintor.restore()
        # Borde con movimiento (tenue en reposo, RGB fuerte si activa).
        if not (self._activa or animaciones_activas()):
            pintor.end()
            return
        grad = QLinearGradient(recto.topLeft(), recto.bottomRight())
        n = len(_MATICES)
        for i in range(n + 1):
            matiz = (_MATICES[i % n] + self._desplazamiento) % 1.0
            color = QColor.fromHsvF(matiz, 0.72, 0.96)
            if not self._activa:
                color.setAlpha(110)  # recorrido tenue en reposo
            grad.setColorAt(i / n, color)
        pintor.setPen(QPen(grad, 2 if self._activa else 1.5))
        pintor.setBrush(Qt.BrushStyle.NoBrush)
        pintor.drawRoundedRect(recto, 15, 15)
        pintor.end()
        pintor.end()
