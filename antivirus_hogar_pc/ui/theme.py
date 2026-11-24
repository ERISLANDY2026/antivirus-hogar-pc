"""Tema visual: «oscuro sereno, neón contenido» (línea de la investigación).

Fondo #0B0F17 · tarjetas #141B29 con BORDE definido #24304A y radio 14–16 ·
acento único cian #22D3EE · semáforos #34D399 / #FBBF24 / #F87171 ·
Segoe UI Variable. El usuario pidió expresamente cuadros CON bordes.
"""

FONDO = "#0B0F17"
TARJETA = "#141B29"
BORDE = "#24304A"
TEXTO = "#E8EEF7"
TEXTO_SUAVE = "#93A4BC"
CIAN = "#22D3EE"
VERDE = "#34D399"
AMBAR = "#FBBF24"
ROJO = "#F87171"
VERDE_BOTON = "#34A853"  # el botón verde de actualizar, como en Android

QSS = f"""
* {{ font-family: "Segoe UI Variable", "Segoe UI"; color: {TEXTO}; }}
QMainWindow, QWidget#raiz {{ background: {FONDO}; }}
QWidget {{ background: transparent; }}
QFrame#tarjeta, QGroupBox#tarjeta {{
    background: {TARJETA};
    border: 1px solid {BORDE};
    border-radius: 15px;
}}
QGroupBox#tarjeta {{ margin-top: 14px; padding-top: 8px; }}
QGroupBox#tarjeta::title {{ subcontrol-origin: margin; left: 14px; padding: 0 6px;
    color: {TEXTO}; font-weight: 600; }}
QLabel#titulo {{ font-size: 22px; font-weight: 600; }}
QLabel#subtitulo {{ color: {TEXTO_SUAVE}; font-size: 13px; }}
QLabel#frase {{ font-size: 14px; }}
QLabel#detalle {{ color: {TEXTO_SUAVE}; font-size: 12px; }}
QPushButton {{
    background: #1B2740; border: 1px solid {BORDE}; border-radius: 10px;
    padding: 8px 14px; font-size: 13px;
}}
QPushButton:hover {{ border-color: {CIAN}; }}
QPushButton:pressed {{ background: #223354; }}
QPushButton#primario {{ background: {CIAN}; color: #06222B; font-weight: 700; border: none; }}
QPushButton#primario:hover {{ background: #4BDDF5; }}
QPushButton#verde {{ background: {VERDE_BOTON}; color: white; font-weight: 700; border: none; }}
QPushButton#verde:hover {{ background: #3FBB61; }}
QPushButton#peligro {{ background: #3A1D24; border: 1px solid #6E2A35; color: #F2A0A8; }}
QPushButton:disabled {{ opacity: 0.45; }}
QPushButton#menu {{
    text-align: left; background: transparent; border: 1px solid transparent;
    border-radius: 10px; padding: 10px 12px; font-size: 14px;
}}
QPushButton#menu:hover {{ background: #16203A; }}
QPushButton#menu[activo="true"] {{ background: #16203A; border-color: {CIAN}; color: {CIAN}; }}
QProgressBar {{
    background: #101827; border: 1px solid {BORDE}; border-radius: 8px;
    height: 16px; text-align: center; font-size: 11px;
}}
QProgressBar::chunk {{ background: {CIAN}; border-radius: 7px; }}
QTableWidget {{
    background: {TARJETA}; border: 1px solid {BORDE}; border-radius: 12px;
    gridline-color: {BORDE}; font-size: 13px;
}}
QHeaderView::section {{ background: #101827; border: none; padding: 7px; font-weight: 600; }}
QListWidget {{ background: {TARJETA}; border: 1px solid {BORDE}; border-radius: 12px; }}
QLineEdit, QComboBox, QSpinBox {{
    background: #101827; border: 1px solid {BORDE}; border-radius: 9px; padding: 7px 10px;
}}
QCheckBox {{ font-size: 13px; spacing: 8px; }}
QScrollArea {{ border: none; }}
QToolTip {{ background: #1B2740; border: 1px solid {BORDE}; padding: 5px; }}
"""


def color_semaforo(nivel: str) -> str:
    return {"bien": VERDE, "regular": AMBAR, "mal": ROJO}.get(nivel, TEXTO_SUAVE)
