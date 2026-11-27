"""Ventana principal: barra lateral construida DESDE EL REGISTRO de módulos.

Añadir un módulo nunca exige tocar este archivo: basta con que su paquete
declare su registro (modules/<paquete>/registro.py) y figure en
PAQUETES_MODULOS de modules/__init__.py. Las páginas se crean
perezosamente al navegar por primera vez.
"""
import os

from PySide6.QtCore import QEvent, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QPushButton,
                               QScrollArea, QStackedWidget, QVBoxLayout,
                               QWidget)

from ..contracts import ContextoModulo
from ..core import i18n
from ..core.i18n import t
from ..modules import crear_pagina, descubrir_modulos, errores_descubrimiento
from . import theme
from .ajustes_page import crear_pagina_ajustes
from .diagnostico_page import crear_pagina_diagnostico
from .historial_page import crear_pagina_historial
from .iconos_nav import LADO, AnimadorIconoNav, icono_nav
from .services import ServiciosApp
from .programar_page import crear_pagina_programar
from .version_page import crear_pagina_version

ANCHO_BARRA = 254  # v1.0.5: caben iconos de 36 px y «Programador de tareas»


class _TrabajadorVigia(QThread):
    """Una pasada del vigilante anti-ransomware (v1.0.21) fuera del
    hilo de la interfaz: señuelos + foto de carpetas + ráfagas."""

    listo = Signal(object)

    def __init__(self, funcion, parent=None):
        super().__init__(parent)
        self._funcion = funcion

    def run(self) -> None:
        try:
            resultado = self._funcion()
        except Exception:
            resultado = None
        self.listo.emit(resultado)

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
        self.setWindowTitle("WAR — Home Guardian")
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
        # v1.0.16 (frente 7): el ancho crece con la escala de la
        # interfaz para que las etiquetas grandes no se corten.
        from .escala import factor_de

        barra.setFixedWidth(
            int(ANCHO_BARRA * factor_de(self.servicios.ajustes)))
        # Cristal oscuro con borde luminoso (tema v1.0.5).
        barra.setStyleSheet(
            "background: rgba(9, 14, 26, 208); "
            "border-right: 1px solid rgba(125, 211, 252, 90);")
        lay_barra = QVBoxLayout(barra)
        lay_barra.setContentsMargins(12, 16, 12, 12)
        lay_barra.setSpacing(6)
        # v1.0.18 (nota 6): el encabezado lleva el ICONO DE LA
        # APLICACIÓN (el escudo con el espartano dorado, el mismo
        # del ejecutable) a tamaño legible, en vez del escudito
        # de texto que había junto al nombre.
        import os

        from PySide6.QtGui import QPixmap

        from .. import config as _config

        fila_titulo = QHBoxLayout()
        fila_titulo.setSpacing(9)
        self._lbl_icono_app = QLabel()
        pix_icono = QPixmap(os.path.join(
            _config.carpeta_activos(), "icono_app.png"))
        if not pix_icono.isNull():
            self._lbl_icono_app.setPixmap(pix_icono.scaled(
                38, 38, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        fila_titulo.addWidget(self._lbl_icono_app)
        # v1.0.22: el nombre nuevo, SOLO en inglés — «WAR — Home
        # Guardian» — pintado por ui.marca_war con el diseño
        # aprobado por el usuario: «WAR» en degradado cian
        # eléctrico con borde dorado fino y arcos de energía,
        # «Home Guardian» debajo en plateado, encendido tipo
        # radar al abrir y resplandor que respira. La marca NO
        # se traduce: es el nombre, en su único idioma.
        from .marca_war import MarcaWAR

        self._marca_war = MarcaWAR()
        fila_titulo.addWidget(self._marca_war)
        fila_titulo.addStretch(1)
        lay_barra.addLayout(fila_titulo)
        lay_barra.addSpacing(4)

        # Selector de IDIOMA (v1.0.14; v1.0.18, nota 6: sube a la
        # parte alta del panel, justo debajo del encabezado y
        # encima de «Inicio»). Cambia TODA la interfaz al momento
        # (la carcasa se retraduce y la página visible se recrea
        # en el idioma nuevo; el túnel VPN no se toca) y la
        # elección queda guardada en los ajustes.
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
        lay_barra.addSpacing(10)

        # v1.0.19 (nota 1): la columna de navegación va en un
        # área con DESPLAZAMIENTO vertical. Causa raíz del
        # recorte que vio el usuario: la columna completa (13
        # módulos + entradas fijas + encabezado) suma más alto
        # que la ventana, y el layout comprimía los botones por
        # debajo de su tamaño natural — texto e icono cortados.
        # Con el área de desplazamiento ningún botón se comprime
        # jamás: cada uno conserva su tamaño completo y, si la
        # ventana es baja, la columna se desplaza. El encabezado
        # (título e idioma) y el pie (Ajustes, Historial) quedan
        # fijos fuera del área.
        area_nav = QScrollArea()
        area_nav.setWidgetResizable(True)
        area_nav.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area_nav.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        area_nav.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget {"
            " background: transparent; }")
        contenedor_nav = QWidget()
        lay_nav = QVBoxLayout(contenedor_nav)
        lay_nav.setContentsMargins(0, 0, 0, 0)
        lay_nav.setSpacing(6)
        area_nav.setWidget(contenedor_nav)
        self._area_nav = area_nav

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
            lay_nav.addWidget(boton)
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
            lay_nav.addWidget(aviso)

        # «Versión de la app» (v1.0.5): entrada fija bajo Informes (el
        # último módulo), con su icono 3D animado como los demás.
        boton_version = QPushButton(t("Versión de la app"))
        boton_version.setObjectName("menu")
        boton_version.setIcon(icono_nav("version"))
        boton_version.setIconSize(QSize(LADO, LADO))
        boton_version.clicked.connect(lambda: self.ir_a("version"))
        lay_nav.addWidget(boton_version)
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
        lay_nav.addWidget(boton_programar)
        self._botones["programar"] = boton_programar
        self._animadores_nav["programar"] = AnimadorIconoNav(
            boton_programar, "calendario", animado=_animado, parent=self,
            desfase=6.05)

        # «Diagnosticar integridad de la aplicación» (v1.0.19,
        # nota 7): entrada fija tras el Programador. Su etiqueta
        # es la más larga del panel: va en DOS líneas para que
        # se lea entera sin recortes (nota 1) en cualquier
        # escala.
        boton_diagnostico = QPushButton(
            t("Diagnosticar integridad\nde la aplicación"))
        boton_diagnostico.setObjectName("menu")
        boton_diagnostico.setIcon(icono_nav("informes"))
        boton_diagnostico.setIconSize(QSize(LADO, LADO))
        boton_diagnostico.clicked.connect(
            lambda: self.ir_a("diagnostico"))
        lay_nav.addWidget(boton_diagnostico)
        self._botones["diagnostico"] = boton_diagnostico
        self._animadores_nav["diagnostico"] = AnimadorIconoNav(
            boton_diagnostico, "informes", animado=_animado,
            parent=self, desfase=6.32)

        lay_nav.addStretch(1)
        lay_barra.addWidget(area_nav, 1)
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

        # «Historial de la aplicación» (v1.0.18, nota 5): el
        # ÚLTIMO ítem del panel — el historial completo de
        # versiones sale de la página «Versión de la app» y vive
        # aquí, en su propia pantalla.
        boton_historial = QPushButton(t("Historial de la aplicación"))
        boton_historial.setObjectName("menu")
        boton_historial.setIcon(icono_nav("informes"))
        boton_historial.setIconSize(QSize(LADO, LADO))
        boton_historial.clicked.connect(lambda: self.ir_a("historial"))
        lay_barra.addWidget(boton_historial)
        self._botones["historial"] = boton_historial
        self._animadores_nav["historial"] = AnimadorIconoNav(
            boton_historial, "informes", animado=_animado, parent=self,
            desfase=7.15)

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

        # Vigilante anti-ransomware propio (v1.0.21): señuelos en
        # las carpetas protegidas + vigilancia de ráfagas. Nace en
        # modo «solo avisar» (Ajustes): detecta y avisa; suspender
        # un proceso solo ocurre si el usuario lo ordena en el
        # aviso. Sin elevación y sin tocar Defender.
        self._vigia: dict = {"fotos": {}, "trabajador": None,
                             "alerta_viva": False}
        self._temporizador_ransomware = QTimer(self)
        self._temporizador_ransomware.setInterval(30000)
        self._temporizador_ransomware.timeout.connect(
            self._chequeo_ransomware)
        self._temporizador_ransomware.start()

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
            elif id_modulo == "historial":
                pagina = crear_pagina_historial(self.ctx)
            elif id_modulo == "programar":
                pagina = crear_pagina_programar(self.ctx)
            elif id_modulo == "diagnostico":
                pagina = crear_pagina_diagnostico(self.ctx)
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

    # -- vigilante anti-ransomware (v1.0.21) ----------------------------------
    def _carpetas_vigiladas(self) -> list[str]:
        """Las carpetas protegidas por CFA si se pueden leer; si
        no, las carpetas personales típicas del usuario."""
        try:
            from ..winapi import defender

            carpetas = defender.carpetas_protegidas_cfa()
            if carpetas:
                return list(carpetas)
        except Exception:
            pass
        candidatas = [
            os.path.expanduser(os.path.join("~", "Documents")),
            os.path.expanduser(os.path.join("~", "Desktop")),
            self.servicios.carpeta_descargas(),
        ]
        return [c for c in candidatas if c and os.path.isdir(c)]

    def _chequeo_ransomware(self) -> None:
        if getattr(self.servicios.ajustes, "antiransomware_modo",
                   "avisar") != "avisar":
            return
        trabajador = self._vigia.get("trabajador")
        if trabajador is not None and trabajador.isRunning():
            return
        fotos_previas = dict(self._vigia["fotos"])
        carpetas = self._carpetas_vigiladas()
        if not carpetas:
            return

        def trabajo():
            from ..core import antiransomware as ar

            tocados = ar.verificar_senuelos()
            ar.crear_senuelos(carpetas)
            fotos: dict = {}
            for carpeta in carpetas:
                fotos.update(ar.foto_carpeta(carpeta))
            alerta = None
            if fotos_previas:
                alerta = ar.analizar_cambios(fotos_previas, fotos)
            if alerta is not None:
                alerta.procesos = ar.procesos_recientes()
            return {"fotos": fotos, "senuelos_tocados": tocados,
                    "alerta": alerta}

        trabajador = _TrabajadorVigia(trabajo, parent=self)
        trabajador.listo.connect(self._al_chequeo_ransomware)
        trabajador.finished.connect(trabajador.deleteLater)
        self._vigia["trabajador"] = trabajador
        trabajador.start()

    def _al_chequeo_ransomware(self, resultado) -> None:
        if not isinstance(resultado, dict):
            return
        self._vigia["fotos"] = resultado.get("fotos", {})
        if self._vigia["alerta_viva"]:
            return
        tocados = resultado.get("senuelos_tocados") or []
        alerta = resultado.get("alerta")
        if tocados:
            self._aviso_ransomware(
                t("Un archivo señuelo cambió o desapareció: algo "
                  "está tocando una carpeta protegida."),
                alerta.procesos if alerta else [])
        elif alerta is not None:
            self._aviso_ransomware(
                t("Posible cifrado masivo en marcha: {detalle}",
                  detalle=alerta.detalle), alerta.procesos)

    def _aviso_ransomware(self, texto: str, procesos: list) -> None:
        self._vigia["alerta_viva"] = True
        try:
            self.servicios.registrar_actividad("antiransomware", texto)
        except Exception:
            pass
        if self._bandeja is not None:
            try:
                self._bandeja.avisar(t("Antivirus Hogar PC"), texto)
            except Exception:
                pass
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Icon.Warning)
        caja.setWindowTitle(t("Posible ransomware"))
        caja.setText(texto + "\n\n" + t(
            "Esto es una detección en modo usuario: puede ser un "
            "programa legítimo comprimiendo muchos archivos, pero "
            "si no reconoces la actividad, actúa ahora: desconecta "
            "la red y revisa qué programa lo está haciendo."))
        boton_procesos = None
        if procesos:
            boton_procesos = caja.addButton(
                t("Ver procesos recientes"),
                QMessageBox.ButtonRole.ActionRole)
        caja.addButton(t("Entendido"), QMessageBox.ButtonRole.AcceptRole)
        caja.exec()
        if boton_procesos is not None and caja.clickedButton() is boton_procesos:
            self._dialogo_procesos_sospechosos(procesos)
        self._vigia["alerta_viva"] = False

    def _dialogo_procesos_sospechosos(self, procesos: list) -> None:
        dialogo = QDialog(self)
        dialogo.setWindowTitle(t("Procesos recientes"))
        lay = QVBoxLayout(dialogo)
        lay.addWidget(QLabel(t(
            "Procesos que arrancaron en los últimos minutos. "
            "Suspender uno lo congela sin cerrarlo (reversible "
            "desde el Administrador de tareas); hazlo solo si no "
            "lo reconoces.")))
        for proc in procesos[:12]:
            fila = QHBoxLayout()
            fila.addWidget(QLabel(
                f"{proc.get('nombre', '?')} (PID {proc.get('pid', '?')})"
                f" — {proc.get('exe', '')}"), 1)
            boton = QPushButton(t("Suspender"))

            def suspender(_=False, pid=proc.get("pid"), b=boton):
                from ..core import antiransomware as ar

                if pid and ar.suspender_proceso(int(pid)):
                    b.setText(t("Suspendido"))
                    b.setEnabled(False)

            boton.clicked.connect(suspender)
            fila.addWidget(boton)
            lay.addLayout(fila)
        cerrar = QPushButton(t("Cerrar"))
        cerrar.clicked.connect(dialogo.accept)
        lay.addWidget(cerrar)
        dialogo.exec()

    def closeEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        if self._bandeja is not None and not self._saliendo:
            evento.ignore()
            self.hide()
            if not self._aviso_bandeja_dado:
                self._aviso_bandeja_dado = True
                self._bandeja.avisar(
                    "WAR — Home Guardian",
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
        # v1.0.22: la marca «WAR — Home Guardian» no se
        # retraduce (nombre solo en inglés, decisión del
        # usuario); el resto de la carcasa, sí.
        self._lbl_idioma.setText(t("Idioma"))
        for rid, boton in self._botones.items():
            if rid in self._registros:
                boton.setText(t(self._registros[rid].titulo))
        self._botones["version"].setText(t("Versión de la app"))
        self._botones["programar"].setText(t("Programador de tareas"))
        self._botones["ajustes"].setText(t("Ajustes"))
        self._botones["historial"].setText(
            t("Historial de la aplicación"))
        # v1.0.22: la etiqueta del diagnóstico también se
        # retraduce (su botón nació fuera del registro de
        # módulos y la retraducción no lo alcanzaba).
        if "diagnostico" in self._botones:
            self._botones["diagnostico"].setText(
                t("Diagnosticar integridad\nde la aplicación"))

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
        # v1.0.22: «diagnostico» entra en los ids fijos — sin
        # esto, el botón «Diagnosticar integridad de la
        # aplicación» moría aquí en silencio desde la 1.0.19:
        # ni era id fijo ni módulo registrado, y el clic se
        # descartaba sin abrir su página (que sí existía).
        if id_modulo not in ("ajustes", "version", "programar",
                             "historial", "diagnostico") \
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
