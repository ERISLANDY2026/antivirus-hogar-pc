"""Ventana principal: barra lateral construida DESDE EL REGISTRO de módulos.

Añadir un módulo nunca exige tocar este archivo: basta con que su paquete
declare su registro (modules/<paquete>/registro.py) y figure en
PAQUETES_MODULOS de modules/__init__.py. Las páginas se crean
perezosamente al navegar por primera vez.
"""
from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QStackedWidget, QVBoxLayout,
                               QWidget)

from ..contracts import ContextoModulo
from ..core import i18n
from ..core.i18n import t
from ..modules import crear_pagina, descubrir_modulos, errores_descubrimiento
from . import theme
from .ajustes_page import crear_pagina_ajustes
from .iconos_nav import LADO, AnimadorIconoNav, icono_nav
from .services import ServiciosApp
from .programar_page import crear_pagina_programar
from .version_page import crear_pagina_version

ANCHO_BARRA = 254  # v1.0.5: caben iconos de 36 px y «Programador de tareas»

# Icono de registro de cada módulo → icono 3D de navegación (v1.0.5).
_ICONO_NAV_POR_REGISTRO = {
    "inicio": "inicio", "lupa": "escanear", "escudo": "proteccion",
    "chip": "drivers", "limpieza": "limpieza", "disco": "discos",
    "actualizar": "actualizar", "red": "red", "informe": "informes",
}


class VentanaPrincipal(QMainWindow):
    def __init__(self, servicios: ServiciosApp | None = None) -> None:
        super().__init__()
        self.servicios = servicios or ServiciosApp()
        # Idioma guardado en los ajustes (v1.0.14): se fija ANTES
        # de construir nada para que toda la carcasa nazca en el
        # idioma elegido.
        i18n.fijar_idioma(getattr(self.servicios.ajustes, "idioma", "es"))
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
        # Cristal oscuro con borde luminoso (tema v1.0.5).
        barra.setStyleSheet(
            "background: rgba(9, 14, 26, 208); "
            "border-right: 1px solid rgba(125, 211, 252, 90);")
        lay_barra = QVBoxLayout(barra)
        lay_barra.setContentsMargins(12, 16, 12, 12)
        lay_barra.setSpacing(6)
        self._lbl_titulo = QLabel("🛡  " + t("Antivirus Hogar"))
        self._lbl_titulo.setStyleSheet("font-size: 16px; font-weight: 700;")
        lay_barra.addWidget(self._lbl_titulo)
        self._lbl_subtitulo = QLabel(t("Compañero de Defender"))
        self._lbl_subtitulo.setObjectName("detalle")
        lay_barra.addWidget(self._lbl_subtitulo)
        lay_barra.addSpacing(10)

        # Iconos 3D animados: uno por pestaña, en colores, más
        # grandes (36 px). v1.0.6: la puerta GLOBAL de animación se
        # fija desde el interruptor de Ajustes (gobierna iconos,
        # bordes de tarjetas y fondo) y cada icono lleva un DESFASE
        # propio para que no se muevan todos a la vez.
        from .animacion import fijar_animaciones_activas

        self._animadores_nav: dict[str, AnimadorIconoNav] = {}
        _animado = bool(getattr(self.servicios.ajustes, "fondo_animado", True))
        fijar_animaciones_activas(_animado)
        for _i, registro in enumerate(
                sorted(self._registros.values(), key=lambda r: r.orden)):
            boton = QPushButton(t(registro.titulo))
            boton.setObjectName("menu")
            nombre_nav = _ICONO_NAV_POR_REGISTRO.get(registro.icono, "inicio")
            boton.setIcon(icono_nav(nombre_nav))
            boton.setIconSize(QSize(LADO, LADO))
            boton.clicked.connect(lambda _=False, rid=registro.id: self.ir_a(rid))
            lay_barra.addWidget(boton)
            self._botones[registro.id] = boton
            self._animadores_nav[registro.id] = AnimadorIconoNav(
                boton, nombre_nav, animado=_animado,
                girar=(registro.id == "actualizaciones"), parent=self,
                desfase=_i * 0.55)

        # Aviso VISIBLE si algún módulo no cargó (v1.0.1): antes el fallo
        # era silencioso y la ventana abría vacía sin explicación.
        errores = errores_descubrimiento()
        if errores or not self._registros:
            aviso = QLabel(t(
                "⚠ Algunos módulos no cargaron. Detalle en "
                "errores-modulos.log (carpeta de datos de la app).")
            )
            aviso.setWordWrap(True)
            aviso.setStyleSheet("color: #F87171; font-size: 12px;")
            lay_barra.addWidget(aviso)

        # «Versión de la app» (v1.0.5): entrada fija bajo Informes (el
        # último módulo), con su icono 3D animado como los demás.
        boton_version = QPushButton(t("Versión de la app"))
        boton_version.setObjectName("menu")
        boton_version.setIcon(icono_nav("version"))
        boton_version.setIconSize(QSize(LADO, LADO))
        boton_version.clicked.connect(lambda: self.ir_a("version"))
        lay_barra.addWidget(boton_version)
        self._botones["version"] = boton_version
        self._animadores_nav["version"] = AnimadorIconoNav(
            boton_version, "version", animado=_animado, parent=self,
            desfase=5.5)

        # «Programador de tareas» (v1.0.5): bajo «Versión de la app»,
        # con el icono de calendario 3D animado.
        boton_programar = QPushButton(t("Programador de tareas"))
        boton_programar.setObjectName("menu")
        boton_programar.setIcon(icono_nav("calendario"))
        boton_programar.setIconSize(QSize(LADO, LADO))
        boton_programar.clicked.connect(lambda: self.ir_a("programar"))
        lay_barra.addWidget(boton_programar)
        self._botones["programar"] = boton_programar
        self._animadores_nav["programar"] = AnimadorIconoNav(
            boton_programar, "calendario", animado=_animado, parent=self,
            desfase=6.05)

        lay_barra.addStretch(1)
        # Selector de IDIOMA (v1.0.14, agregado del usuario):
        # visible en el panel izquierdo, sobre «Ajustes». Cambia
        # TODA la interfaz al momento (la carcasa se retraduce y
        # la página visible se recrea en el idioma nuevo; el
        # túnel VPN no se toca) y la elección queda guardada en
        # los ajustes para los próximos arranques.
        self._lbl_idioma = QLabel(t("Idioma"))
        self._lbl_idioma.setObjectName("detalle")
        lay_barra.addWidget(self._lbl_idioma)
        self._combo_idioma = QComboBox()
        self._combo_idioma.addItem("Español", "es")
        self._combo_idioma.addItem("English", "en")
        indice_idioma = self._combo_idioma.findData(
            i18n.idioma_actual())
        self._combo_idioma.setCurrentIndex(
            indice_idioma if indice_idioma >= 0 else 0)
        self._combo_idioma.currentIndexChanged.connect(
            lambda _i: self._cambiar_idioma(
                self._combo_idioma.currentData()))
        lay_barra.addWidget(self._combo_idioma)
        boton_ajustes = QPushButton(t("Ajustes"))
        boton_ajustes.setObjectName("menu")
        boton_ajustes.setIcon(icono_nav("ajustes"))
        boton_ajustes.setIconSize(QSize(LADO, LADO))
        boton_ajustes.clicked.connect(lambda: self.ir_a("ajustes"))
        lay_barra.addWidget(boton_ajustes)
        self._botones["ajustes"] = boton_ajustes
        self._animadores_nav["ajustes"] = AnimadorIconoNav(
            boton_ajustes, "ajustes", animado=_animado, parent=self,
            desfase=6.6)

        # --- Área de páginas -------------------------------------------------
        self.pila = QStackedWidget()
        layout_raiz.addWidget(barra)
        layout_raiz.addWidget(self.pila, 1)
        self.setCentralWidget(raiz)

        # Bandeja del sistema (v1.0.7): main la crea y la fija aquí;
        # mientras exista, cerrar la ventana la OCULTA a la bandeja
        # en vez de cerrar la app (salir es «Salir» del menú).
        self._bandeja = None
        self._saliendo = False
        self._aviso_bandeja_dado = False
        # v1.0.14: página visible (para recrearla al cambiar el
        # idioma) y gancho opcional que main usa para retraducir
        # la bandeja del sistema al cambiar el idioma.
        self._id_actual = ""
        self.al_cambiar_idioma = None

        primero = sorted(self._registros.values(), key=lambda r: r.orden)
        if primero:
            self.ir_a(primero[0].id)
        else:
            # Sin módulos no se deja el área en blanco: se explica el fallo.
            vacio = QLabel(t(
                "No se cargó ningún módulo de la aplicación.\n"
                "Revisa errores-modulos.log en la carpeta de datos de la app.")
            )
            vacio.setWordWrap(True)
            self.pila.addWidget(vacio)
            self.pila.setCurrentWidget(vacio)

    # -- navegación -----------------------------------------------------------
    def _obtener_pagina(self, id_modulo: str) -> QWidget:
        if id_modulo not in self._paginas:
            if id_modulo == "ajustes":
                pagina = crear_pagina_ajustes(self.ctx)
            elif id_modulo == "version":
                pagina = crear_pagina_version(self.ctx)
            elif id_modulo == "programar":
                pagina = crear_pagina_programar(self.ctx)
            else:
                pagina = crear_pagina(self._registros[id_modulo], self.ctx)
            self._paginas[id_modulo] = pagina
            self.pila.addWidget(pagina)
        return self._paginas[id_modulo]

    def refrescar_rutina(self) -> None:
        """Refresca el resumen de la rutina automática en Inicio (si la
        página ya existe): lo llama main al terminar la rutina."""
        pagina = self._paginas.get("panel")
        gancho = getattr(pagina, "refrescar_rutina", None) if pagina else None
        if callable(gancho):
            gancho()

    # -- bandeja del sistema (v1.0.7) ------------------------------------------
    def fijar_bandeja(self, bandeja) -> None:
        self._bandeja = bandeja

    def salir(self) -> None:
        """Salida de verdad (la opción «Salir» del menú de la bandeja)."""
        self._saliendo = True
        self.close()

    def closeEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        if self._bandeja is not None and not self._saliendo:
            evento.ignore()
            self.hide()
            if not self._aviso_bandeja_dado:
                self._aviso_bandeja_dado = True
                self._bandeja.avisar(
                    "Antivirus Hogar PC",
                    t("La app sigue trabajando en la bandeja, junto al "
                      "reloj. Doble clic en su icono para abrirla; "
                      "«Salir» en su menú la cierra de verdad."))
            return
        super().closeEvent(evento)

    # -- idioma (v1.0.14) ---------------------------------------------------------
    def _cambiar_idioma(self, codigo: str) -> None:
        """El selector del panel: guarda la elección, retraduce
        la carcasa y RECREA las páginas en el idioma nuevo, sin
        reiniciar la app y sin tocar el motor (un túnel VPN
        activo sigue arriba: vive fuera de la UI)."""
        codigo = codigo if codigo in i18n.IDIOMAS else "es"
        if codigo == i18n.idioma_actual():
            return
        try:
            self.servicios.ajustes.idioma = codigo
            self.servicios.ajustes.guardar()
        except Exception:
            pass  # el cambio vale para la sesión aunque no se guarde
        i18n.fijar_idioma(codigo)
        self._retraducir_carcasa()
        destino = self._id_actual
        for pagina in list(self._paginas.values()):
            self.pila.removeWidget(pagina)
            pagina.deleteLater()
        self._paginas.clear()
        if destino:
            self.ir_a(destino)
        if callable(self.al_cambiar_idioma):
            self.al_cambiar_idioma()

    def _retraducir_carcasa(self) -> None:
        self._lbl_titulo.setText("🛡  " + t("Antivirus Hogar"))
        self._lbl_subtitulo.setText(t("Compañero de Defender"))
        self._lbl_idioma.setText(t("Idioma"))
        for rid, boton in self._botones.items():
            if rid in self._registros:
                boton.setText(t(self._registros[rid].titulo))
        self._botones["version"].setText(t("Versión de la app"))
        self._botones["programar"].setText(t("Programador de tareas"))
        self._botones["ajustes"].setText(t("Ajustes"))

    # -- pausa de animaciones con la ventana oculta (v1.0.14) ----------------------
    def hideEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        from .animacion import fijar_pausa

        fijar_pausa(True)
        super().hideEvent(evento)

    def showEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        from .animacion import fijar_pausa

        fijar_pausa(False)
        super().showEvent(evento)

    def changeEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        if evento.type() == QEvent.Type.WindowStateChange:
            from .animacion import fijar_pausa

            fijar_pausa(self.isMinimized())
        super().changeEvent(evento)

    def ir_a(self, id_modulo: str) -> None:
        if id_modulo not in ("ajustes", "version", "programar") \
                and id_modulo not in self._registros:
            return
        self._id_actual = id_modulo
        pagina = self._obtener_pagina(id_modulo)
        if id_modulo == "panel":
            self.refrescar_rutina()
        self.pila.setCurrentWidget(pagina)
        for rid, boton in self._botones.items():
            boton.setProperty("activo", "true" if rid == id_modulo else "false")
            boton.style().unpolish(boton)
            boton.style().polish(boton)
            animador = self._animadores_nav.get(rid)
            if animador is not None:
                animador.fijar_activo(rid == id_modulo)
        self.pila.setFocus(Qt.FocusReason.OtherFocusReason)
