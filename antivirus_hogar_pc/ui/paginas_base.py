"""Piezas comunes para construir páginas (esqueleto Ola 0 y módulos reales).

El integrador es dueño de este archivo; los carriles lo USAN, no lo editan.
Toda página: título, subtítulo y tarjetas CON borde (QFrame#tarjeta).
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from . import theme
from .icons import IconoAnimado
from .widgets_v102 import BotonPulso, TarjetaAnimada


def boton_principal(texto: str, nombre_objeto: str = "") -> BotonPulso:
    """LA acción principal de una tarjeta/página (v1.0.3): BotonPulso
    con el pulso ENCENDIDO, conservando el objectName del tema
    («primario», «verde», «peligro») para el gradiente cromado del QSS.
    En la v1.0.2 BotonPulso existía pero no se usaba en ninguna página:
    fuera del Panel todo eran QPushButton pelados."""
    boton = BotonPulso(texto)
    if nombre_objeto:
        boton.setObjectName(nombre_objeto)
    boton.activar_pulso(True)
    return boton


def pagina_base(titulo: str, subtitulo: str = "", demo: bool = False) -> tuple[QWidget, QVBoxLayout]:
    """Crea una página con scroll y devuelve (widget, layout vertical)."""
    contenido = QWidget()
    layout = QVBoxLayout(contenido)
    layout.setSpacing(14)
    layout.setContentsMargins(22, 18, 22, 18)
    lbl_titulo = QLabel(titulo)
    lbl_titulo.setObjectName("titulo")
    layout.addWidget(lbl_titulo)
    if subtitulo:
        lbl_sub = QLabel(subtitulo)
        lbl_sub.setObjectName("subtitulo")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_sub)
    if demo:
        aviso = QLabel("Ola 0 · Datos de demostración: la pantalla ya tiene la forma final; "
                       "los datos reales llegan con el módulo de su carril.")
        aviso.setObjectName("detalle")
        aviso.setWordWrap(True)
        layout.addWidget(aviso)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(contenido)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    return scroll, layout


def tarjeta(titulo: str = "") -> tuple[QFrame, QVBoxLayout]:
    # v1.0.2: TarjetaAnimada (QFrame con objectName "tarjeta"); se ve como
    # la tarjeta del QSS y puede encender su borde RGB con fijar_activa().
    frame = TarjetaAnimada()
    frame.setObjectName("tarjeta")
    layout = QVBoxLayout(frame)
    layout.setSpacing(8)
    layout.setContentsMargins(16, 14, 16, 14)
    if titulo:
        lbl = QLabel(titulo)
        lbl.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(lbl)
    return frame, layout


def fila_estado(icono: str, modo: str, titulo: str, frase: str,
                color: str = theme.CIAN) -> QWidget:
    """Fila con icono (animado) al frente, título y frase — como pidió el usuario."""
    fila = QWidget()
    layout = QHBoxLayout(fila)
    layout.setContentsMargins(0, 2, 0, 2)
    layout.addWidget(IconoAnimado(icono, color, 30, modo))
    textos = QVBoxLayout()
    lbl_t = QLabel(titulo)
    lbl_t.setStyleSheet("font-size: 14px; font-weight: 600;")
    lbl_f = QLabel(frase)
    lbl_f.setObjectName("detalle")
    lbl_f.setWordWrap(True)
    textos.addWidget(lbl_t)
    textos.addWidget(lbl_f)
    layout.addLayout(textos, 1)
    return fila


def etiqueta(texto: str, suave: bool = False) -> QLabel:
    lbl = QLabel(texto)
    if suave:
        lbl.setObjectName("detalle")
    lbl.setWordWrap(True)
    return lbl


def alinear_arriba(layout: QVBoxLayout) -> None:
    layout.addStretch(1)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
