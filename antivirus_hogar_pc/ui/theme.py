"""Tema visual v1.0.2: oscuro sereno con COLOR, cromados y RGB.

El usuario dijo que la v1.0.1 era «aburrida»: botones casi sin colores,
animaciones breves, sin RGB ni cromados y barras sin porcentaje. Esta
versión mantiene la paleta base y TODOS los objectName existentes
(tarjeta, titulo, subtitulo, detalle, primario, verde, peligro, menu…)
pero da vida a los controles:

- Botones por defecto: gradiente cromado metálico gris-azulado.
- #primario: gradiente cian vivo · #verde: gradiente verde ·
  #peligro: gradiente rojo oscuro; hover con borde brillante y
  pressed más oscuro en todos.
- QProgressBar: 20 px de alto, texto centrado en negrita (el % se ve
  grande) y chunk con gradiente. Es el RESPALDO visual: las barras
  animadas RGB de verdad las pinta ui/widgets_v102.py por paintEvent.

Fondo #0B0F17 · tarjetas #141B29 con BORDE definido #24304A y radio
14–16 · acento cian #22D3EE · semáforos #34D399 / #FBBF24 / #F87171 ·
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
    /* Cromado metálico gris-azulado: luz arriba, sombra abajo. */
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3D4E6E, stop:0.45 #26334E, stop:0.55 #1B2740, stop:1 #141E33);
    border: 1px solid #4A5F88; border-radius: 10px;
    padding: 8px 14px; font-size: 13px;
}}
QPushButton:hover {{ border: 1px solid {CIAN};
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4A5F88, stop:0.45 #2E3E5E, stop:0.55 #223354, stop:1 #182642);
}}
QPushButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #141E33, stop:0.5 #101827, stop:1 #0D1424);
    border-color: #33456A;
}}
QPushButton#primario {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #7DEFFC, stop:0.5 {CIAN}, stop:1 #0E9BB8);
    color: #06222B; font-weight: 700; border: 1px solid #7DEFFC;
}}
QPushButton#primario:hover {{ border: 1px solid #D9FAFF;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #A5F3FC, stop:0.5 #4BDDF5, stop:1 #14B8D4);
}}
QPushButton#primario:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0E9BB8, stop:0.5 #0B7E99, stop:1 #095E73);
    border-color: #0E9BB8; color: #E6FBFF;
}}
QPushButton#verde {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #5CC46F, stop:0.5 {VERDE_BOTON}, stop:1 #237A38);
    color: white; font-weight: 700; border: 1px solid #5CC46F;
}}
QPushButton#verde:hover {{ border: 1px solid #A7E8B5;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #74D184, stop:0.5 #3FBB61, stop:1 #2A8A42);
}}
QPushButton#verde:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #237A38, stop:0.5 #1C6330, stop:1 #144A24);
    border-color: #237A38;
}}
QPushButton#peligro {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #6E2432, stop:0.5 #4A1B26, stop:1 #3A1D24);
    border: 1px solid #8A3040; color: #F6C3C9;
}}
QPushButton#peligro:hover {{ border: 1px solid {ROJO};
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #822C3D, stop:0.5 #571F2B, stop:1 #421E28);
}}
QPushButton#peligro:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2A1219, stop:0.5 #21101A, stop:1 #180B12);
    border-color: #5A2230; color: #F2A0A8;
}}
QPushButton:disabled {{ opacity: 0.45; }}
QPushButton#menu {{
    text-align: left; background: transparent; border: 1px solid transparent;
    border-radius: 10px; padding: 10px 12px; font-size: 14px;
}}
QPushButton#menu:hover {{ background: #16203A; }}
QPushButton#menu[activo="true"] {{ background: #16203A; border-color: {CIAN}; color: {CIAN}; }}
QProgressBar {{
    background: #101827; border: 1px solid {BORDE}; border-radius: 10px;
    height: 20px; text-align: center; font-size: 12px; font-weight: 700;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0E9BB8, stop:0.5 {CIAN}, stop:1 {VERDE});
    border-radius: 9px;
}}
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
