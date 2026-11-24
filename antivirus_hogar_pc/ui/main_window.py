"""Ventana principal: barra lateral construida DESDE EL REGISTRO de módulos.

Añadir un módulo nunca exige tocar este archivo: basta con que su paquete
declare su registro (modules/<paquete>/registro.py). Las páginas se crean
perezosamente al navegar por primera vez.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from ..contracts import ContextoModulo
from ..modules import crear_pagina, descubrir_modulos
from . import theme
from .ajustes_page import crear_pagina_ajustes
from .icons import pixmap_icono
from .services import ServiciosApp

ANCHO_BARRA = 216


class VentanaPrincipal(QMainWindow):
    def __init__(self, servicios: ServiciosApp | None = None) -> None:
        super().__init__()
        self.servicios = servicios or ServiciosApp()
        self.setWindowTitle("Antivirus Hogar PC")
        self.resize(1120, 700)
        self.setMinimumSize(960, 620)

        self.ctx = ContextoModulo(servicios=self.servicios, al_navegar=self.ir_a)
        self._paginas: dict[str, QWidget] = {}
        self._botones: dict[str, QPushButton] = {}
        self._registros = {r.id: r for r in descubrir_modulos()}

        raiz = QWidget()
        raiz.setObjectName("raiz")
        layout_raiz = QHBoxLayout(raiz)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        # --- Barra lateral -------------------------------------------------
        barra = QWidget()
        barra.setFixedWidth(ANCHO_BARRA)
        barra.setStyleSheet(f"background: #0E1420; border-right: 1px solid {theme.BORDE};")
        lay_barra = QVBoxLayout(barra)
        lay_barra.setContentsMargins(12, 16, 12, 12)
        lay_barra.setSpacing(6)
        titulo = QLabel("🛡  Antivirus Hogar")
        titulo.setStyleSheet("font-size: 16px; font-weight: 700;")
        lay_barra.addWidget(titulo)
        subtitulo = QLabel("Compañero de Defender")
        subtitulo.setObjectName("detalle")
        lay_barra.addWidget(subtitulo)
        lay_barra.addSpacing(10)

        for registro in sorted(self._registros.values(), key=lambda r: r.orden):
            boton = QPushButton(registro.titulo)
            boton.setObjectName("menu")
            boton.setIcon(pixmap_icono(registro.icono, theme.TEXTO_SUAVE, 20))
            boton.clicked.connect(lambda _=False, rid=registro.id: self.ir_a(rid))
            lay_barra.addWidget(boton)
            self._botones[registro.id] = boton

        lay_barra.addStretch(1)
        boton_ajustes = QPushButton("Ajustes")
        boton_ajustes.setObjectName("menu")
        boton_ajustes.setIcon(pixmap_icono("engranaje", theme.TEXTO_SUAVE, 20))
        boton_ajustes.clicked.connect(lambda: self.ir_a("ajustes"))
        lay_barra.addWidget(boton_ajustes)
        self._botones["ajustes"] = boton_ajustes

        # --- Área de páginas -------------------------------------------------
        self.pila = QStackedWidget()
        layout_raiz.addWidget(barra)
        layout_raiz.addWidget(self.pila, 1)
        self.setCentralWidget(raiz)

        primero = sorted(self._registros.values(), key=lambda r: r.orden)
        if primero:
            self.ir_a(primero[0].id)

    # -- navegación -----------------------------------------------------------
    def _obtener_pagina(self, id_modulo: str) -> QWidget:
        if id_modulo not in self._paginas:
            if id_modulo == "ajustes":
                pagina = crear_pagina_ajustes(self.ctx)
            else:
                pagina = crear_pagina(self._registros[id_modulo], self.ctx)
            self._paginas[id_modulo] = pagina
            self.pila.addWidget(pagina)
        return self._paginas[id_modulo]

    def ir_a(self, id_modulo: str) -> None:
        if id_modulo != "ajustes" and id_modulo not in self._registros:
            return
        pagina = self._obtener_pagina(id_modulo)
        self.pila.setCurrentWidget(pagina)
        for rid, boton in self._botones.items():
            boton.setProperty("activo", "true" if rid == id_modulo else "false")
            boton.style().unpolish(boton)
            boton.style().polish(boton)
        self.pila.setFocus(Qt.FocusReason.OtherFocusReason)
