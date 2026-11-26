"""Páginas reales del Carril D: Actualizaciones y Red y VPN.

Todo el trabajo lento (red, winget, Windows Update) corre en un hilo
(_Trabajo) y llega a la UI como contracts.ResultadoModulo: la página solo
pinta el mensaje y los datos, nunca recibe excepciones.
"""
import math
import threading
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from antivirus_hogar_pc import config
from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
from antivirus_hogar_pc.core import fuentes_vpn
from antivirus_hogar_pc.core.i18n import t
from antivirus_hogar_pc.core.v102 import valorar_velocidad
from antivirus_hogar_pc.core.vpngate import ordenar_servidores, paises_disponibles
from antivirus_hogar_pc.core.wifi_parse import frecuencia_mhz, valorar_wifi
from antivirus_hogar_pc.ui import theme
from antivirus_hogar_pc.ui.icons import pixmap_icono
from antivirus_hogar_pc.ui.paginas_base import boton_principal, etiqueta, fila_estado, pagina_base, tarjeta
from antivirus_hogar_pc.ui.widgets_v102 import BarraProgreso, BotonPulso

from . import servicios_red as srv

_TREINTA_DIAS = 30 * 24 * 3600


class _Trabajo(QThread):
    """Ejecuta una operación de servicios_red fuera del hilo de la UI."""

    terminado = Signal(object)  # ResultadoModulo

    def __init__(self, funcion, parent=None):
        super().__init__(parent)
        self._funcion = funcion

    def run(self):  # noqa: N802 - nombre de Qt
        try:
            resultado = self._funcion()
        except Exception as exc:  # último seguro: la UI nunca recibe excepciones
            resultado = ResultadoModulo(ok=False, mensaje=f"No se pudo completar: {exc}")
        self.terminado.emit(resultado)


def _olvidar(pagina: QWidget, trabajo) -> None:
    try:
        if trabajo in pagina._trabajos:
            pagina._trabajos.remove(trabajo)
    except RuntimeError:
        pass  # la página ya se destruyó: nada que olvidar


def _soltar_trabajos(pagina: QWidget) -> None:
    """Al destruirse la página, los hilos en curso se DESPADREAN
    (v1.0.6): un QThread destruido mientras corre ABORTA el proceso
    (visto en la suite: la descarga real de VPN Gate de una ventana
    ya cerrada tumbaba el intérprete al recoger la página). Sin
    padre, el hilo termina su trabajo y se autoborra con la señal
    finished→deleteLater que _lanzar/_lanzar_vivo ya conectan; las
    señales hacia la página muerta se desconectan solas."""
    for trabajo in list(getattr(pagina, "_trabajos", []) or []):
        try:
            trabajo.setParent(None)
        except RuntimeError:
            pass


def _lanzar(pagina: QWidget, funcion, al_terminar) -> _Trabajo:
    trabajo = _Trabajo(funcion, pagina)
    trabajo.terminado.connect(al_terminar)
    trabajo.terminado.connect(lambda _r: _olvidar(pagina, trabajo))
    trabajo.finished.connect(trabajo.deleteLater)
    pagina._trabajos.append(trabajo)
    trabajo.start()
    return trabajo


class _TrabajoVivo(QThread):
    """Trabajo con señal de PROGRESO en vivo (v1.0.5): la función
    recibe un emisor progreso(*valores) seguro entre hilos y el
    resultado final llega como ResultadoModulo, igual que _Trabajo.
    Lo usa la medición de velocidad: los Mbps se pintan MIENTRAS se
    mide, no solo al final."""

    terminado = Signal(object)  # ResultadoModulo
    progreso = Signal(object)   # tupla de valores de progreso

    def __init__(self, funcion, parent=None):
        super().__init__(parent)
        self._funcion = funcion

    def run(self):  # noqa: N802 - nombre de Qt
        try:
            resultado = self._funcion(
                lambda *valores: self.progreso.emit(tuple(valores)))
        except Exception as exc:  # la UI nunca recibe excepciones
            resultado = ResultadoModulo(
                ok=False, mensaje=f"No se pudo completar: {exc}")
        self.terminado.emit(resultado)


def _lanzar_vivo(pagina: QWidget, funcion, al_progreso,
                 al_terminar) -> _TrabajoVivo:
    trabajo = _TrabajoVivo(funcion, pagina)
    trabajo.progreso.connect(lambda valores: al_progreso(*valores))
    trabajo.terminado.connect(al_terminar)
    trabajo.terminado.connect(lambda _r: _olvidar(pagina, trabajo))
    trabajo.finished.connect(trabajo.deleteLater)
    pagina._trabajos.append(trabajo)
    trabajo.start()
    return trabajo


# =====================================================================================
# Actualizaciones
# =====================================================================================
class _DialogoActualizacion(QDialog):
    """«Qué trae esta actualización» — como en la app de Android."""

    def __init__(self, info, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Qué trae esta actualización"))
        layout = QVBoxLayout(self)
        titulo = QLabel(f"Versión {info.version} disponible")
        titulo.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(titulo)
        layout.addWidget(etiqueta(f"Ahora tienes la {config.VERSION}."))
        notas = QLabel(info.notas or "Mejoras y correcciones.")
        notas.setWordWrap(True)
        layout.addWidget(notas)
        aviso = etiqueta(
            "Al actualizar se descarga el instalador, se comprueba su huella "
            "de seguridad (SHA-256) y se abre. Windows mostrará el aviso de "
            "SmartScreen porque el instalador no lleva firma comercial: es "
            "lo esperado, pulsa «Más información» → «Ejecutar de todas formas».",
            suave=True)
        layout.addWidget(aviso)
        fila = QHBoxLayout()
        boton_no = QPushButton(t("Ahora no"))
        boton_no.clicked.connect(self.reject)
        boton_si = QPushButton(t("Actualizar ahora"))
        boton_si.setObjectName("verde")
        boton_si.clicked.connect(self.accept)
        fila.addWidget(boton_no)
        fila.addStretch(1)
        fila.addWidget(boton_si)
        layout.addLayout(fila)


class _PaginaActualizaciones(QWidget):
    def __init__(self, ctx: ContextoModulo):
        super().__init__()
        self._ctx = ctx
        self._trabajos: list[_Trabajo] = []
        self.destroyed.connect(lambda _=None: _soltar_trabajos(self))
        self._programas: list = []
        self._ocupado = False
        self._todo_restantes: list = []
        self._todo_total = 0
        self._todo_completados = 0

        pagina, layout = pagina_base(
            t("Actualizaciones"),
            t("Los programas de tu PC, Windows y la propia aplicación, al día."))
        self._scroll = pagina

        # --- La propia app -----------------------------------------------------
        tarjeta_app, lay = tarjeta("Antivirus Hogar PC")
        self._tarjeta_app = tarjeta_app
        self._lbl_app = etiqueta(f"Estás en la versión {config.VERSION}.")
        lay.addWidget(self._lbl_app)
        self._btn_app = BotonPulso(t("Buscar actualizaciones de la app"))
        self._btn_app.setObjectName("verde")
        self._btn_app.activar_pulso(True)
        self._btn_app.clicked.connect(lambda: self._buscar_app(silencioso=False))
        lay.addWidget(self._btn_app)
        layout.addWidget(tarjeta_app)

        # --- Programas (winget) --------------------------------------------------
        tarjeta_winget, lay_w = tarjeta(t("Programas desactualizados (winget)"))
        self._tarjeta_winget = tarjeta_winget
        self._barra_winget = BarraProgreso()
        lay_w.addWidget(self._barra_winget)
        self._lbl_winget = etiqueta(t("Pulsa buscar para ver qué programas tienen una versión más nueva."))
        lay_w.addWidget(self._lbl_winget)
        self._tabla_winget = QTableWidget(0, 5)
        self._tabla_winget.setHorizontalHeaderLabels(
            [t("Programa"), t("Versión"), t("Disponible"), t("Origen"), t("Acción")])
        lay_w.addWidget(self._tabla_winget)
        fila_w = QHBoxLayout()
        self._btn_winget = boton_principal(t("Buscar programas desactualizados"), "primario")
        self._btn_winget.clicked.connect(self._buscar_winget)
        self._btn_todo = QPushButton(t("Actualizar todo"))
        self._btn_todo.clicked.connect(self._actualizar_todo)
        fila_w.addWidget(self._btn_winget)
        fila_w.addWidget(self._btn_todo)
        fila_w.addStretch(1)
        lay_w.addLayout(fila_w)
        layout.addWidget(tarjeta_winget)

        # --- Windows Update ---------------------------------------------------------
        tarjeta_wu, lay_u = tarjeta(t("Actualizaciones de Windows pendientes"))
        self._tarjeta_wu = tarjeta_wu
        self._barra_wu = BarraProgreso()
        lay_u.addWidget(self._barra_wu)
        self._lbl_wu = etiqueta(t("Pulsa buscar para consultar Windows Update."))
        lay_u.addWidget(self._lbl_wu)
        self._lista_wu = QListWidget()
        lay_u.addWidget(self._lista_wu)
        fila_u = QHBoxLayout()
        self._btn_wu = boton_principal(t("Buscar actualizaciones de Windows"), "primario")
        self._btn_wu.clicked.connect(self._buscar_wu)
        self._btn_abrir_wu = QPushButton(t("Abrir Windows Update"))
        self._btn_abrir_wu.clicked.connect(
            lambda: self._mostrar_simple(srv.abrir_windows_update(), self._lbl_wu))
        fila_u.addWidget(self._btn_wu)
        fila_u.addWidget(self._btn_abrir_wu)
        fila_u.addStretch(1)
        lay_u.addLayout(fila_u)
        layout.addWidget(tarjeta_wu)
        layout.addStretch(1)

        # Chequeo mensual automático (como en Android): si el último fue hace
        # más de 30 días, se comprueba al abrir la página y solo salta el
        # diálogo si de verdad hay una versión nueva.
        servicios = getattr(ctx, "servicios", None)
        ajustes = getattr(servicios, "ajustes", None)
        if ajustes is not None and \
                time.time() - float(getattr(ajustes, "ultimo_chequeo_actualizacion", 0)) > _TREINTA_DIAS:
            QTimer.singleShot(600, lambda: self._buscar_app(silencioso=True))

    # -- utilidades ---------------------------------------------------------------
    def widget(self) -> QWidget:
        return self._scroll

    def _mostrar_simple(self, resultado: ResultadoModulo, destino: QLabel) -> None:
        destino.setText(resultado.mensaje or (t("Hecho.") if resultado.ok else t("No se pudo.")))

    def _fijar_ocupado(self, ocupado: bool) -> None:
        self._ocupado = ocupado
        for boton in (self._btn_app, self._btn_winget, self._btn_todo, self._btn_wu):
            boton.setEnabled(not ocupado)

    # -- la propia app ---------------------------------------------------------------
    def _buscar_app(self, silencioso: bool) -> None:
        servicios = getattr(self._ctx, "servicios", None)
        ajustes = getattr(servicios, "ajustes", None)
        if ajustes is None:
            self._lbl_app.setText(t("El servicio de ajustes no está disponible."))
            return
        self._lbl_app.setText(t("Comprobando el canal de actualizaciones…"))
        _lanzar(self, lambda: srv.comprobar_actualizacion_app(ajustes),
                lambda r: self._app_comprobada(r, silencioso))

    def _app_comprobada(self, resultado: ResultadoModulo, silencioso: bool) -> None:
        if not resultado.ok:
            self._lbl_app.setText(resultado.mensaje)
            return
        info = resultado.datos
        if info is None:
            self._lbl_app.setText(resultado.mensaje)
            return
        self._lbl_app.setText(resultado.mensaje)
        dialogo = _DialogoActualizacion(info, self)
        if dialogo.exec():
            self._lbl_app.setText(t("Descargando la actualización…"))
            _lanzar(self, lambda: srv.instalar_actualizacion_app(info),
                    lambda r: self._lbl_app.setText(r.mensaje))

    # -- winget ---------------------------------------------------------------------
    def _buscar_winget(self) -> None:
        self._tarjeta_winget.fijar_activa(True)
        self._barra_winget.fijar_texto(t("Buscando con winget…"))
        self._lbl_winget.setText(t("Buscando con winget… puede tardar un poco."))
        self._fijar_ocupado(True)
        _lanzar(self, srv.programas_desactualizados, self._winget_buscado)

    def _winget_buscado(self, resultado: ResultadoModulo) -> None:
        self._tarjeta_winget.fijar_activa(False)
        self._fijar_ocupado(False)
        self._lbl_winget.setText(resultado.mensaje)
        self._programas = resultado.datos or []
        tabla = self._tabla_winget
        tabla.setRowCount(len(self._programas))
        for i, p in enumerate(self._programas):
            tabla.setItem(i, 0, QTableWidgetItem(p.nombre))
            tabla.setItem(i, 1, QTableWidgetItem(p.version_actual))
            tabla.setItem(i, 2, QTableWidgetItem(p.version_disponible))
            tabla.setItem(i, 3, QTableWidgetItem(p.origen))
            boton = QPushButton(t("Actualizar"))
            boton.clicked.connect(lambda _=False, prog=p: self._actualizar_uno(prog))
            tabla.setCellWidget(i, 4, boton)
        tabla.resizeColumnsToContents()

    def _actualizar_uno(self, programa) -> None:
        self._barra_winget.fijar_etapas(1, 1, f"Actualizando {programa.nombre}")
        self._lbl_winget.setText(f"Actualizando «{programa.nombre}»…")
        self._fijar_ocupado(True)

        def al_terminar(r: ResultadoModulo) -> None:
            self._barra_winget.terminar()
            self._lbl_winget.setText(r.mensaje)
            self._buscar_winget()

        _lanzar(self, lambda: srv.actualizar_programa(programa.id_paquete, programa.nombre),
                al_terminar)

    def _actualizar_todo(self) -> None:
        respuesta = QMessageBox.question(
            self, t("Actualizar todo"),
            t("Se actualizarán TODOS los programas de la lista con winget, uno a uno. Algunos pueden pedir confirmación o reiniciar su instalador. ¿Seguimos?"))
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        if not self._programas:
            self._lbl_winget.setText(
                t("Primero pulsa «Buscar programas desactualizados» para tener la lista."))
            return
        self._todo_restantes = list(self._programas)
        self._todo_total = len(self._todo_restantes)
        self._todo_completados = 0
        self._barra_winget.fijar(0, self._todo_total, "programas")
        self._lbl_winget.setText(
            f"Actualizando {self._todo_total} programas, uno a uno…")
        self._fijar_ocupado(True)
        self._actualizar_siguiente()

    def _actualizar_siguiente(self) -> None:
        if not self._todo_restantes:
            self._barra_winget.terminar()
            self._lbl_winget.setText(
                f"Actualización en cadena terminada: {self._todo_completados} "
                f"de {self._todo_total} programas procesados.")
            self._buscar_winget()
            return
        programa = self._todo_restantes.pop(0)
        self._lbl_winget.setText(
            f"Actualizando «{programa.nombre}» "
            f"({self._todo_completados + 1} de {self._todo_total})…")

        def al_terminar(r: ResultadoModulo, prog=programa) -> None:
            self._todo_completados += 1
            self._barra_winget.fijar(
                self._todo_completados, self._todo_total, "programas")
            if r.mensaje:
                self._lbl_winget.setText(r.mensaje)
            self._actualizar_siguiente()

        _lanzar(self, lambda prog=programa: srv.actualizar_programa(
            prog.id_paquete, prog.nombre), al_terminar)

    # -- Windows Update ----------------------------------------------------------------
    def _buscar_wu(self) -> None:
        self._tarjeta_wu.fijar_activa(True)
        self._barra_wu.fijar_texto(
            t("Consultando Windows Update… (Windows no informa porcentaje)"))
        self._lbl_wu.setText(t("Consultando Windows Update… la primera vez tarda."))
        self._fijar_ocupado(True)
        _lanzar(self, srv.actualizaciones_windows, self._wu_buscado)

    def _wu_buscado(self, resultado: ResultadoModulo) -> None:
        self._tarjeta_wu.fijar_activa(False)
        self._fijar_ocupado(False)
        self._lbl_wu.setText(resultado.mensaje)
        self._lista_wu.clear()
        for act in resultado.datos or []:
            texto = act.titulo
            extras = []
            if act.descargada:
                extras.append("descargada")
            if act.requiere_reinicio:
                extras.append("requiere reinicio")
            if extras:
                texto += "  (" + ", ".join(extras) + ")"
            self._lista_wu.addItem(texto)


def _conservar(pagina: QWidget) -> QWidget:
    """Devuelve el widget visible de la página ANCLANDO el objeto
    página a él.

    Causa raíz (v1.0.6, notas del usuario en su PC real): la ventana
    principal guarda SOLO el widget devuelto por la factoría. Las
    páginas de este módulo son objetos QObject sin padre y sin otra
    referencia: al terminar la factoría, Python los destruía y con
    ellos morían TODAS sus conexiones (botones que no hacían nada,
    ni siquiera el «cargando») y sus temporizadores de autocarga
    (Wi-Fi «todavía sin leer», desplegable de VPN vacío para
    siempre). El atributo mantiene el objeto vivo mientras viva el
    widget que la ventana sí conserva.
    """
    widget = pagina.widget()
    widget._pagina_controladora = pagina  # noqa: SLF001 - ancla de vida
    return widget


def crear_pagina_actualizaciones(ctx: ContextoModulo):
    return _conservar(_PaginaActualizaciones(ctx))


# =====================================================================================
# Red y VPN
# =====================================================================================
class GloboEsquina(QWidget):
    """Esfera de la Tierra girando en la esquina de la tabla de VPN Gate.

    Pedido del usuario (2026-11-25, con foto): la celda de esquina de
    la tabla de servidores (arriba a la izquierda, sobre la columna
    de números) se veía como un cuadro blanco vacío. Este widget se
    coloca ENCIMA de esa esquina y dibuja el planeta por código
    (QPainter, sin imágenes): océano con degradado radial y luz
    arriba a la izquierda, continentes simplificados en verde y
    borde cian del tema vidrio, sobre el mismo fondo oscuro de la
    cabecera de la tabla.

    Gira a UNA VUELTA POR SEGUNDO (fijado por el usuario tras ver las
    muestras de 6 s y de 3 s por vuelta), colgando del RELOJ
    compartido de 50 ms de la app y de la puerta global de
    animaciones (interruptor `fondo_animado` de Ajustes): apagadas
    las animaciones, el globo se queda quieto. Los clics lo atraviesan
    (la esquina sigue siendo el botón de la tabla).
    """

    # Siluetas MUY simplificadas (longitud, latitud): a ~44x28 px
    # solo tienen que sugerir los continentes.
    _CONTINENTES = (
        # América del Norte
        ((-165, 68), (-140, 70), (-125, 71), (-110, 68), (-95, 79),
         (-85, 69), (-76, 62), (-65, 60), (-55, 52), (-64, 44),
         (-70, 42), (-74, 39), (-76, 35), (-80, 32), (-81, 26),
         (-84, 30), (-90, 29), (-97, 26), (-97, 22), (-94, 18),
         (-90, 21), (-86, 13), (-79, 9), (-85, 11), (-92, 15),
         (-104, 19), (-110, 24), (-114, 29), (-118, 33), (-122, 37),
         (-124, 46), (-130, 54), (-147, 60), (-162, 58)),
        # América del Sur
        ((-77, 7), (-71, 12), (-64, 10), (-55, 6), (-50, 0),
         (-44, -3), (-35, -8), (-39, -13), (-40, -20), (-46, -24),
         (-52, -32), (-57, -38), (-62, -41), (-65, -45), (-68, -54),
         (-71, -54), (-73, -50), (-74, -44), (-73, -37), (-72, -30),
         (-70, -18), (-75, -15), (-79, -7), (-80, -4), (-78, 0),
         (-80, 3)),
        # África
        ((-6, 35), (3, 37), (10, 37), (20, 32), (30, 31), (33, 27),
         (37, 22), (43, 12), (48, 11), (51, 12), (44, 5), (41, -2),
         (40, -11), (37, -18), (35, -23), (32, -29), (26, -34),
         (19, -35), (17, -32), (14, -23), (13, -18), (12, -15),
         (9, -1), (9, 4), (-8, 5), (-13, 8), (-17, 15), (-17, 21),
         (-16, 27), (-9, 31)),
        # Eurasia
        ((-10, 36), (-9, 43), (-2, 44), (-5, 48), (-1, 50), (5, 53),
         (8, 57), (5, 60), (11, 59), (18, 56), (24, 56), (28, 60),
         (30, 62), (40, 64), (55, 68), (80, 73), (110, 74),
         (140, 72), (170, 66), (178, 65), (162, 60), (157, 52),
         (142, 50), (140, 45), (135, 35), (126, 38), (122, 38),
         (121, 31), (115, 23), (109, 19), (109, 13), (103, 7),
         (98, 10), (93, 17), (88, 22), (80, 15), (77, 8), (72, 19),
         (66, 25), (57, 26), (52, 29), (48, 29), (44, 29), (43, 33),
         (36, 36), (30, 36), (27, 37), (23, 36), (19, 40), (15, 38),
         (12, 44), (7, 44), (3, 43), (0, 39), (-2, 37)),
        # Australia
        ((113, -22), (114, -28), (115, -34), (124, -33), (132, -32),
         (135, -35), (140, -38), (145, -38), (150, -37), (153, -31),
         (151, -24), (146, -19), (142, -11), (140, -18), (136, -15),
         (132, -11), (126, -14), (118, -20)),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._angulo = 20.0  # posición estática bonita si no hay animación
        self._suscrito = False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                          True)

    def showEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        super().showEvent(evento)
        self._sincronizar_suscripcion()

    def hideEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        self._desuscribir()
        super().hideEvent(evento)

    def _sincronizar_suscripcion(self) -> None:
        from antivirus_hogar_pc.ui.animacion import RELOJ, animaciones_activas

        if animaciones_activas() and not self._suscrito:
            RELOJ.tic.connect(self._al_tic)
            RELOJ.suscribir()
            self._suscrito = True

    def _desuscribir(self) -> None:
        if self._suscrito:
            from antivirus_hogar_pc.ui.animacion import RELOJ

            RELOJ.tic.disconnect(self._al_tic)
            RELOJ.desuscribir()
            self._suscrito = False

    def _al_tic(self, t: float) -> None:
        # Una vuelta por segundo: el reloj emite el tiempo acumulado.
        self._angulo = (t * 360.0) % 360.0
        self.update()

    def paintEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Fondo: el vidrio oscuro de la cabecera de la tabla (nada blanco).
        pintor.fillRect(self.rect(), QColor(16, 24, 39))
        ancho, alto = self.width(), self.height()
        if ancho < 8 or alto < 8:
            return
        radio = min(ancho, alto) / 2.0 - 1.5
        cx, cy = ancho / 2.0, alto / 2.0
        circulo = QRectF(cx - radio, cy - radio, radio * 2, radio * 2)
        # Océano: degradado radial con la luz arriba a la izquierda.
        oceano = QRadialGradient(cx - radio * 0.4, cy - radio * 0.4,
                                 radio * 1.7)
        oceano.setColorAt(0.0, QColor(125, 211, 252))
        oceano.setColorAt(0.55, QColor(37, 99, 235))
        oceano.setColorAt(1.0, QColor(23, 37, 84))
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(oceano)
        pintor.drawEllipse(circulo)
        # Continentes: proyección ortográfica con el giro actual; al
        # acercarse al borde del disco se comprimen (rotación real).
        pintor.save()
        recorte = QPainterPath()
        recorte.addEllipse(circulo)
        pintor.setClipPath(recorte)
        tierra = QColor(52, 211, 153, 235)
        pintor.setBrush(tierra)
        for continente in self._CONTINENTES:
            puntos = QPolygonF()
            for lon, lat in continente:
                delta = math.radians(lon - self._angulo)
                coseno = math.cos(delta)
                if coseno <= 0.02:
                    continue  # cara oculta del planeta
                x = cx + radio * math.cos(math.radians(lat)) \
                    * math.sin(delta)
                y = cy - radio * math.sin(math.radians(lat))
                puntos.append(QPointF(x, y))
            if puntos.size() >= 3:
                pintor.drawPolygon(puntos)
        pintor.restore()
        # Brillo especular suave y borde cian eléctrico del tema.
        brillo = QRadialGradient(cx - radio * 0.45, cy - radio * 0.45,
                                 radio * 0.9)
        brillo.setColorAt(0.0, QColor(255, 255, 255, 70))
        brillo.setColorAt(1.0, QColor(255, 255, 255, 0))
        pintor.setBrush(brillo)
        pintor.drawEllipse(circulo)
        pintor.setBrush(Qt.BrushStyle.NoBrush)
        pintor.setPen(QColor(34, 211, 238, 200))
        pintor.drawEllipse(circulo)


class _PaginaRed(QWidget):
    # v1.0.18: el barrido de verificación del arranque avisa por
    # los oyentes de servicios_red desde un hilo de fondo; esta
    # señal lo trae al hilo de la UI para pintar los sellos en
    # vivo en la tabla.
    _senal_verificacion_fondo = Signal(int, int, int, int, str, str)

    def __init__(self, ctx: ContextoModulo):
        super().__init__()
        self._ctx = ctx
        self._oyente_fondo = (
            lambda *v: self._senal_verificacion_fondo.emit(*v))
        self._senal_verificacion_fondo.connect(
            self._progreso_verificacion_fondo)
        self.destroyed.connect(
            lambda _=None: srv.desregistrar_oyente_verificacion(
                self._oyente_fondo))
        self._trabajos: list[_Trabajo] = []
        self.destroyed.connect(lambda _=None: _soltar_trabajos(self))
        # v1.0.12: al cerrarse la página/app con un intento de
        # conexión AÚN en curso, el intento se baja: jamás queda
        # un openvpn huérfano sujetando la tarjeta.
        self.destroyed.connect(
            lambda _=None: srv.cancelar_intento_vpn())
        self._servidores: list = []       # lista completa descargada
        self._visibles: list = []         # lista filtrada/ordenada en pantalla
        self._servidor_conectado: str = ""  # hostname con el túnel arriba (v1.0.7)
        self._vpn_conectando: bool = False  # un solo intento a la vez (v1.0.12)
        # v1.0.14: veredictos del autoanálisis y de los intentos
        # (clave «fuente:hostname» → {"estado", "cuando"}): el
        # sello de verificación de cada fila y el orden
        # «Recomendado» se pintan con esto.
        self._veredictos: dict = {}

        pagina, layout = pagina_base(
            t("Red y VPN"),
            t("Tu Wi-Fi de un vistazo y la VPN gratuita de VPN Gate."))
        self._scroll = pagina

        # --- Wi-Fi ----------------------------------------------------------------
        tarjeta_wifi, lay = tarjeta(t("Wi-Fi"))
        self._tarjeta_wifi = tarjeta_wifi
        self._fila_wifi = lay
        self._contenedor_wifi = QWidget()
        self._lay_wifi = QVBoxLayout(self._contenedor_wifi)
        self._lay_wifi.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._contenedor_wifi)
        # Resumen INTERACTIVO de la red (v1.0.5): el NOMBRE de la red
        # conectada se ve de un vistazo y, al tocar el resumen, se
        # despliega el panel con TODOS los detalles que Windows da.
        self._btn_red_wifi = QPushButton(t("Wi-Fi: todavía sin leer"))
        self._btn_red_wifi.setObjectName("menu")
        self._btn_red_wifi.setIcon(pixmap_icono("wifi", theme.CIAN, 24))
        self._btn_red_wifi.setCheckable(True)
        self._btn_red_wifi.setStyleSheet(
            "font-size: 15px; font-weight: 700; text-align: left;")
        self._btn_red_wifi.toggled.connect(self._alternar_detalles_wifi)
        lay.addWidget(self._btn_red_wifi)
        self._panel_wifi = QWidget()
        rejilla_wifi = QGridLayout(self._panel_wifi)
        rejilla_wifi.setContentsMargins(10, 4, 6, 4)
        rejilla_wifi.setHorizontalSpacing(14)
        rejilla_wifi.setVerticalSpacing(3)
        self._wifi_valores: dict[str, QLabel] = {}
        for fila_det, (clave_det, titulo_det) in enumerate((
                ("ssid", t("Red (SSID)")), ("senal", t("Intensidad de señal")),
                ("banda", t("Banda")), ("canal", t("Canal")),
                ("frecuencia", t("Frecuencia")),
                ("enlace", t("Velocidad de enlace")),
                ("seguridad", t("Seguridad")), ("radio", t("Tipo de radio")),
                ("ip", t("IP local")), ("puerta", t("Puerta de enlace")),
                ("dns", "DNS"), ("perfil", t("Perfil de red")))):
            rejilla_wifi.addWidget(etiqueta(titulo_det, suave=True),
                                   fila_det, 0)
            valor_det = etiqueta("—")
            valor_det.setStyleSheet("font-weight: 600;")
            rejilla_wifi.addWidget(valor_det, fila_det, 1)
            self._wifi_valores[clave_det] = valor_det
        self._panel_wifi.setVisible(False)
        lay.addWidget(self._panel_wifi)
        self._lbl_wifi_detalle = etiqueta("")
        lay.addWidget(self._lbl_wifi_detalle)
        self._lbl_perfiles = etiqueta("", suave=True)
        lay.addWidget(self._lbl_perfiles)
        self._btn_wifi = boton_principal(t("Actualizar datos de Wi-Fi"), "primario")
        self._btn_wifi.clicked.connect(self._cargar_wifi)
        lay.addWidget(self._btn_wifi)
        self._barra_wifi = BarraProgreso()
        self._barra_wifi.setVisible(False)
        lay.addWidget(self._barra_wifi)
        self._lbl_wifi_sello = etiqueta("", suave=True)
        lay.addWidget(self._lbl_wifi_sello)
        layout.addWidget(tarjeta_wifi)

        # --- Velocidad de internet y estado VPN -------------------------------------
        tarjeta_vel, lay_vel = tarjeta(t("Velocidad de internet y estado VPN"))
        self._tarjeta_vel = tarjeta_vel
        self._lbl_velocidad = etiqueta(t("Todavía no se ha medido la velocidad."))
        lay_vel.addWidget(self._lbl_velocidad)
        # Valores EN VIVO (v1.0.5): ping, descarga y subida en colores
        # RGB y letra mediana (16 px), actualizándose DURANTE la
        # medición — primero la descarga y después la subida.
        fila_vals = QHBoxLayout()
        self._val_ping = self._bloque_valor(fila_vals, t("PING"), theme.CIAN)
        self._val_bajada = self._bloque_valor(fila_vals, t("DESCARGA"), theme.VERDE)
        self._val_subida = self._bloque_valor(fila_vals, t("SUBIDA"), "#A78BFA")
        lay_vel.addLayout(fila_vals)
        self._lbl_valoracion = etiqueta("", suave=True)
        lay_vel.addWidget(self._lbl_valoracion)
        self._btn_velocidad = boton_principal(t("Medir velocidad"), "primario")
        self._btn_velocidad.clicked.connect(self._medir_velocidad)
        lay_vel.addWidget(self._btn_velocidad)
        self._lbl_estado_vpn = etiqueta(t("Estado VPN sin consultar."), suave=True)
        lay_vel.addWidget(self._lbl_estado_vpn)
        self._btn_estado_vpn = QPushButton(t("Ver estado VPN"))
        self._btn_estado_vpn.clicked.connect(self._ver_estado_vpn)
        lay_vel.addWidget(self._btn_estado_vpn)
        layout.addWidget(tarjeta_vel)

        # --- VPN Gate ----------------------------------------------------------------
        tarjeta_vpn, lay_v = tarjeta(
            t("VPN gratuita (VPN Gate y VPNBook, servidores de voluntarios)"))
        self._tarjeta_vpn = tarjeta_vpn
        aviso = etiqueta(
            t("AVISO: estos servidores los ofrecen VOLUNTARIOS y el operador puede registrar la conexión. Úsalos para navegar con otra ubicación, nunca para banca, compras ni datos sensibles."))
        aviso.setStyleSheet(f"color: {theme.AMBAR};")
        lay_v.addWidget(aviso)

        # Interruptor general de la VPN (v1.0.2): estado + apagado desde la app
        fila_switch = QHBoxLayout()
        self._lbl_switch_vpn = etiqueta(t("VPN: consultando el estado…"))
        fila_switch.addWidget(self._lbl_switch_vpn, 1)
        self._btn_desconectar = QPushButton(t("Desconectar VPN"))
        self._btn_desconectar.setObjectName("peligro")
        self._btn_desconectar.setEnabled(False)
        self._btn_desconectar.clicked.connect(self._desconectar_vpn)
        fila_switch.addWidget(self._btn_desconectar)
        lay_v.addLayout(fila_switch)

        fila_ctrl = QHBoxLayout()
        fila_ctrl.addWidget(QLabel(t("País:")))
        self._combo_pais = QComboBox()
        self._combo_pais.addItem(t("Todos los países"), "")
        self._combo_pais.currentIndexChanged.connect(self._repintar_servidores)
        fila_ctrl.addWidget(self._combo_pais)
        fila_ctrl.addWidget(QLabel(t("Ordenar por:")))
        self._combo_orden = QComboBox()
        # v1.0.14: el orden por defecto es «Recomendado»
        # (verificados primero; luego pocas sesiones y más
        # tiempo en línea): la velocidad bruta deja de mandar,
        # porque los nodos más rápidos de la lista pública son
        # justo los que suelen estar llenos.
        self._combo_orden.addItem(t("Recomendado"), "recomendado")
        self._combo_orden.addItem(t("Velocidad"), "velocidad")
        self._combo_orden.addItem(t("Ping (respuesta)"), "ping")
        self._combo_orden.addItem(t("Sesiones actuales"), "sesiones")
        self._combo_orden.addItem(t("Puntuación"), "puntuacion")
        self._combo_orden.currentIndexChanged.connect(self._repintar_servidores)
        fila_ctrl.addWidget(self._combo_orden)
        self._btn_servidores = boton_principal(t("Actualizar lista de servidores"), "primario")
        self._btn_servidores.clicked.connect(self._cargar_servidores)
        fila_ctrl.addWidget(self._btn_servidores)
        # v1.0.15 (idea del usuario en llamada): «Verificar
        # servidores» — barrido completo con la sonda real; cada
        # fila recibe su ✓/✗ en cuanto cae su resultado, con
        # barra, conteo y porcentaje subiendo. Pulsarlo otra vez
        # lo detiene.
        self._btn_verificar = QPushButton(t("Verificar servidores"))
        self._btn_verificar.clicked.connect(self._verificar_servidores)
        fila_ctrl.addWidget(self._btn_verificar)
        self._verificando = False
        self._cancelar_verificacion = threading.Event()
        fila_ctrl.addStretch(1)
        lay_v.addLayout(fila_ctrl)

        self._lbl_vpn = etiqueta(t("Pulsa «Actualizar lista de servidores» para descargar la lista pública de VPN Gate."))
        lay_v.addWidget(self._lbl_vpn)
        # v1.0.11: el DETALLE TÉCNICO del intento VPN, visible bajo
        # el mensaje: la causa real del registro de OpenVPN. En la
        # 1.0.10 el detalle se calculaba pero no se pintaba en todo
        # el flujo VPN, y un error fatal del perfil se veía como
        # «servidor apagado o saturado» sin forma de saber más.
        self._lbl_vpn_detalle = etiqueta("", suave=True)
        lay_v.addWidget(self._lbl_vpn_detalle)
        # Barrita TEMPORAL de la actualización (v1.0.5): visible solo
        # mientras se busca la lista; desaparece al terminar.
        self._barra_vpn = BarraProgreso()
        self._barra_vpn.setVisible(False)
        lay_v.addWidget(self._barra_vpn)
        self._lbl_verificacion = etiqueta("", suave=True)
        self._lbl_verificacion.setVisible(False)
        lay_v.addWidget(self._lbl_verificacion)
        # v1.0.19 (nota 6): barrita DEDICADA a la verificación
        # de servidores — la de arriba se comparte con la
        # actualización de la lista y se pisaban. Ésta enseña el
        # avance del chequeo (manual o del arranque), el servidor
        # en curso como señal de vida y, con el vigilante de
        # abajo, avisa si el chequeo se traba (sin avance en
        # UMBRAL_TRABADA_S segundos).
        self._barra_verificacion = BarraProgreso()
        self._barra_verificacion.setVisible(False)
        lay_v.addWidget(self._barra_verificacion)
        self._verificacion_activa = False
        self._ultimo_avance_verificacion = 0.0
        self._hechos_verificacion = 0
        self._total_verificacion = 0
        self._vigia_verificacion = QTimer(self)
        self._vigia_verificacion.setInterval(2000)
        self._vigia_verificacion.timeout.connect(
            self._vigilar_verificacion)
        self._vigia_verificacion.start()
        # v1.0.14: 8 columnas — la lista UNIFICADA enseña la
        # FUENTE de cada servidor y su sello de VERIFICACIÓN con
        # la hora del autoanálisis: [País, Servidor, Fuente,
        # Velocidad, Ping, Sesiones, Verificación, Acción].
        self._tabla_vpn = QTableWidget(0, 8)
        self._tabla_vpn.setHorizontalHeaderLabels(
            [t("País"), t("Servidor"), t("Fuente"), t("Velocidad"), t("Ping"),
             t("Sesiones"), t("Verificación"), t("Acción")])
        # v1.0.10: altura de fila suficiente para el botón «Conectar»
        # completo. El tema da al botón ≈37 px (texto 13 px + padding
        # 8 px arriba/abajo + bordes) y el contenedor de la celda
        # añade 2 px por lado: con la altura por defecto de Qt
        # (~30 px) el botón se veía CORTADO por abajo (reportado por
        # el usuario en la 1.0.9). 42 px lo deja entero, y
        # _repintar_servidores remata con resizeRowsToContents().
        self._tabla_vpn.verticalHeader().setDefaultSectionSize(42)
        lay_v.addWidget(self._tabla_vpn)
        # Globo terráqueo girando sobre la celda de esquina de la
        # tabla (v1.0.8, pedido del usuario): tapa el cuadro blanco
        # de la esquina sin tocar columnas ni datos.
        self._globo_vpn = GloboEsquina(self._tabla_vpn)
        self._situar_globo_vpn()
        self._tabla_vpn.horizontalHeader().sectionResized.connect(
            lambda *_: self._situar_globo_vpn())
        self._tabla_vpn.verticalHeader().sectionResized.connect(
            lambda *_: self._situar_globo_vpn())
        lay_v.addWidget(etiqueta(
            "Con OpenVPN (incluido con la app) la conexión se hace desde "
            "aquí: pulsa «Conectar» en un servidor y el túnel sube en "
            "segundo plano; el botón de esa fila se pone verde y dice "
            "«Conectado», y a su lado aparece el botón rojo «Desconectar» "
            "para bajar el túnel desde la misma fila. "
            "Sin OpenVPN, la app genera el perfil .ovpn y se lo entrega "
            "a tu cliente VPN."))
        fila_ip = QHBoxLayout()
        self._lbl_ip = etiqueta(t("Tu IP pública: sin consultar."))
        self._btn_ip = QPushButton(t("Consultar mi IP pública"))
        self._btn_ip.clicked.connect(self._consultar_ip)
        fila_ip.addWidget(self._lbl_ip)
        fila_ip.addWidget(self._btn_ip)
        fila_ip.addStretch(1)
        lay_v.addLayout(fila_ip)
        layout.addWidget(tarjeta_vpn)
        layout.addStretch(1)

        QTimer.singleShot(300, self._cargar_wifi)
        # Carga AUTOMÁTICA de la lista de VPN Gate al abrir la sección
        # (v1.0.2: antes solo se descargaba a mano y un fallo dejaba el
        # desplegable de países vacío en silencio).
        QTimer.singleShot(500, self._cargar_servidores)
        QTimer.singleShot(800, self._ver_estado_vpn)

    def widget(self) -> QWidget:
        return self._scroll

    def _situar_globo_vpn(self) -> None:
        """Coloca el globo sobre la esquina de la tabla de VPN Gate:
        ancho = el de la cabecera vertical (la columna de números) y
        alto = el de la cabecera horizontal."""
        tabla = self._tabla_vpn
        ancho = tabla.verticalHeader().width()
        alto = tabla.horizontalHeader().height()
        self._globo_vpn.setGeometry(0, 0, max(0, ancho), max(0, alto))
        self._globo_vpn.raise_()

    # -- Wi-Fi ----------------------------------------------------------------------
    def _cargar_wifi(self) -> None:
        # Feedback INMEDIATO (bug 4): antes el botón no hacía nada visible.
        self._tarjeta_wifi.fijar_activa(True)
        self._btn_wifi.setEnabled(False)
        self._btn_wifi.setText(t("Leyendo…"))
        self._barra_wifi.setVisible(True)
        self._barra_wifi.fijar_texto(t("Leyendo la red Wi-Fi…"))
        self._btn_red_wifi.setText(t("Wi-Fi: leyendo…"))
        self._lbl_wifi_detalle.setText(t("Leyendo la red Wi-Fi…"))
        _lanzar(self, srv.informe_wifi, self._wifi_cargado)

    def _alternar_detalles_wifi(self, abierto: bool) -> None:
        self._panel_wifi.setVisible(bool(abierto))

    def _fijar_detalle_wifi(self, clave: str, texto: str) -> None:
        lbl = self._wifi_valores.get(clave)
        if lbl is not None:
            lbl.setText(texto if texto else "—")

    def _wifi_cargado(self, resultado: ResultadoModulo) -> None:
        import time as _time

        self._tarjeta_wifi.fijar_activa(False)
        self._btn_wifi.setEnabled(True)
        self._btn_wifi.setText(t("Actualizar datos de Wi-Fi"))
        self._barra_wifi.terminar()
        # Vaciar la fila anterior
        while self._lay_wifi.count():
            item = self._lay_wifi.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not resultado.ok:
            causa = resultado.mensaje
            if resultado.detalle_tecnico:
                causa += f" ({resultado.detalle_tecnico})"
            self._lay_wifi.addWidget(fila_estado(
                "wifi", "estatico", t("Wi-Fi no disponible"), causa, theme.ROJO))
            self._btn_red_wifi.setText(t("Wi-Fi no disponible"))
            self._lbl_wifi_detalle.setText("")
            self._lbl_perfiles.setText("")
            self._lbl_wifi_sello.setText(
                f"No se pudo actualizar ({_time.strftime('%H:%M:%S')}).")
            return
        self._lbl_wifi_sello.setText(
            f"Actualizado a las {_time.strftime('%H:%M:%S')}")
        datos = resultado.datos or {}
        info = datos.get("info")
        nivel = datos.get("nivel", "sin_datos")
        frase = datos.get("frase", "")
        red = datos.get("red_local") or {}
        # Panel de detalles (v1.0.5): se rellena con TODO lo que
        # Windows expone — netsh (SSID, señal, banda, canal, enlace,
        # seguridad, radio) + la conexión local (IP, puerta, DNS).
        if info is not None:
            self._fijar_detalle_wifi("ssid", info.ssid)
            self._fijar_detalle_wifi(
                "senal", f"{info.senal_pct} %"
                if info.senal_pct is not None else "")
            self._fijar_detalle_wifi("banda", info.banda)
            self._fijar_detalle_wifi("canal", info.canal)
            frec = frecuencia_mhz(info.banda, info.canal)
            self._fijar_detalle_wifi(
                "frecuencia", f"{frec} MHz" if frec else "")
            if info.velocidad_rx_mbps is not None or \
                    info.velocidad_tx_mbps is not None:
                rx = (f"{info.velocidad_rx_mbps:g}"
                      if info.velocidad_rx_mbps is not None else "—")
                tx = (f"{info.velocidad_tx_mbps:g}"
                      if info.velocidad_tx_mbps is not None else "—")
                self._fijar_detalle_wifi("enlace", f"↓ {rx} Mbps · ↑ {tx} Mbps")
            else:
                self._fijar_detalle_wifi("enlace", "")
            seguridad = info.autenticacion or ""
            if info.cifrado:
                seguridad = (f"{seguridad} ({info.cifrado})"
                             if seguridad else info.cifrado)
            self._fijar_detalle_wifi("seguridad", seguridad)
            self._fijar_detalle_wifi("radio", info.tipo_radio)
        self._fijar_detalle_wifi("ip", str(red.get("ip") or ""))
        self._fijar_detalle_wifi("puerta", str(red.get("puerta_enlace") or ""))
        self._fijar_detalle_wifi("dns", ", ".join(red.get("dns") or []))
        self._fijar_detalle_wifi("perfil", str(datos.get("perfil_red") or ""))
        color = {"bien": theme.VERDE, "regular": theme.AMBAR,
                 "mal": theme.ROJO}.get(nivel, theme.CIAN)
        if info and info.conectada:
            # El NOMBRE de la red, visible sin adivinar (v1.0.5).
            senal_txt = (f" · Señal {info.senal_pct} %"
                         if info.senal_pct is not None else "")
            self._btn_red_wifi.setText(
                f"Red Wi-Fi: {info.ssid}{senal_txt} — toca para los detalles")
            self._lbl_wifi_detalle.setStyleSheet(f"color: {color};")
            self._lbl_wifi_detalle.setText(frase)
        else:
            self._btn_red_wifi.setText(
                t("Sin red Wi-Fi conectada — toca para los detalles"))
            self._lbl_wifi_detalle.setStyleSheet("")
            if red.get("ip"):
                # Por cable no es «sección vacía»: se dice claro y los
                # datos de ESA conexión van en el panel de detalles.
                self._lbl_wifi_detalle.setText(
                    "Esta PC no está por Wi-Fi: la conexión va por cable "
                    f"u otra vía ({red.get('interfaz') or 'Ethernet'}, "
                    f"IP {red['ip']}). Sus datos están en el detalle.")
            else:
                self._lbl_wifi_detalle.setText(
                    frase or t("No hay ninguna red Wi-Fi conectada ahora mismo."))
        perfiles = datos.get("perfiles_guardados") or []
        self._lbl_perfiles.setText(
            "Redes guardadas en este PC: " + (", ".join(perfiles) if perfiles else "ninguna"))

    # -- VPN Gate ---------------------------------------------------------------------
    # --- Verificar servidores (v1.0.15) ---------------------------------
    def _verificar_servidores(self) -> None:
        if self._verificando:
            self._cancelar_verificacion.set()
            self._lbl_verificacion.setText(
                t("Deteniendo la verificación…"))
            return
        if not self._servidores:
            self._lbl_vpn.setText(
                t("Primero actualiza la lista de servidores."))
            return
        self._verificando = True
        self._cancelar_verificacion = threading.Event()
        self._btn_verificar.setText(t("Detener verificación"))
        self._barra_verificacion.setVisible(True)
        self._barra_verificacion.fijar(0, len(self._servidores))
        self._verificacion_activa = True
        self._ultimo_avance_verificacion = time.monotonic()
        self._hechos_verificacion = 0
        self._total_verificacion = len(self._servidores)
        self._lbl_verificacion.setVisible(True)
        self._lbl_verificacion.setText(t(
            "Verificando servidores: {pct} % — comprobados {h} de "
            "{t} · ✓ {ok} · ✗ {mal}",
            pct=0, h=0, t=len(self._servidores), ok=0, mal=0))
        cancelar = self._cancelar_verificacion

        def trabajo(progreso):
            return srv.verificar_todos_los_servidores(
                al_progreso=lambda *v: progreso(*v), cancelar=cancelar)

        _lanzar_vivo(self, trabajo, self._progreso_verificacion,
                     self._fin_verificacion)

    def _progreso_verificacion(self, hechos, total, verificados,
                               fallidos, hostname, fase) -> None:
        pct = int(hechos * 100 / total) if total else 100
        # v1.0.19 (nota 6): la barrita dedicada + la señal de
        # vida: cada aviso del barrido refresca el «último
        # avance» del vigilante y el texto enseña el servidor
        # EN CURSO — el usuario ve que el chequeo está activo
        # y cuánto falta, no una barra muda.
        self._barra_verificacion.setVisible(True)
        self._barra_verificacion.fijar(hechos, total)
        self._verificacion_activa = True
        self._ultimo_avance_verificacion = time.monotonic()
        self._hechos_verificacion = hechos
        self._total_verificacion = total
        if total and hechos >= total:
            self._verificacion_activa = False
        if fase == "pausa":
            self._lbl_verificacion.setText(t(
                "Verificación en pausa (hay una conexión VPN en "
                "curso): {pct} % — comprobados {h} de {t} · "
                "✓ {ok} · ✗ {mal}",
                pct=pct, h=hechos, t=total, ok=verificados,
                mal=fallidos))
        elif hostname:
            self._lbl_verificacion.setText(t(
                "Verificando servidores: {pct} % — comprobados "
                "{h} de {t} · ✓ {ok} · ✗ {mal} · ahora: {host}",
                pct=pct, h=hechos, t=total, ok=verificados,
                mal=fallidos, host=hostname))
        else:
            self._lbl_verificacion.setText(t(
                "Verificando servidores: {pct} % — comprobados "
                "{h} de {t} · ✓ {ok} · ✗ {mal}",
                pct=pct, h=hechos, t=total, ok=verificados,
                mal=fallidos))
        # El sello de la fila cae en cuanto llega su veredicto:
        # se relee el registro compartido y se repinta la tabla
        # (el orden «Recomendado» ya pone los verificados
        # primero, como en el autoanálisis).
        barra = self._tabla_vpn.verticalScrollBar()
        posicion = barra.value() if barra is not None else 0
        self._veredictos = srv.veredictos_actuales()
        self._repintar_servidores()
        if barra is not None:
            barra.setValue(posicion)

    def _fin_verificacion(self, resultado) -> None:
        self._verificando = False
        self._verificacion_activa = False
        self._btn_verificar.setText(t("Verificar servidores"))
        datos = resultado.datos or {}
        if datos.get("veredictos"):
            self._veredictos = datos["veredictos"]
            self._repintar_servidores()
        total = int(datos.get("total") or 0)
        hechos = int(datos.get("comprobados") or 0)
        if total:
            self._barra_verificacion.fijar(hechos, total)
        self._lbl_vpn.setText(resultado.mensaje)
        self._lbl_verificacion.setText(resultado.mensaje)

    def _vigilar_verificacion(self) -> None:
        """v1.0.19 (nota 6): si el barrido activo deja de
        avanzar más de UMBRAL_TRABADA_S, la etiqueta lo dice —
        «parece trabada» con los segundos de silencio y el
        conteo alcanzado — en vez de dejar al usuario mirando
        una barra quieta sin saber si sigue o se colgó."""
        ahora = time.monotonic()
        if not srv.verificacion_trabada(
                self._verificacion_activa,
                self._ultimo_avance_verificacion, ahora,
                self._hechos_verificacion,
                self._total_verificacion):
            return
        silencio = int(ahora - self._ultimo_avance_verificacion)
        self._lbl_verificacion.setVisible(True)
        self._lbl_verificacion.setText(t(
            "La verificación parece trabada: sin avance desde "
            "hace {s} s — comprobados {h} de {t}. Si sigue así, "
            "deténla y vuelve a intentarlo.",
            s=silencio, h=self._hechos_verificacion,
            t=self._total_verificacion))

    # --- Verificación del arranque en vivo (v1.0.18, nota 4) -----
    def showEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        super().showEvent(evento)
        srv.registrar_oyente_verificacion(self._oyente_fondo)

    def hideEvent(self, evento) -> None:  # noqa: N802 (nombre de Qt)
        srv.desregistrar_oyente_verificacion(self._oyente_fondo)
        super().hideEvent(evento)

    def _progreso_verificacion_fondo(self, hechos, total, verificados,
                                     fallidos, hostname, fase) -> None:
        """El barrido del arranque llega en vivo: los sellos de
        la tabla se llenan servidor a servidor sin que el
        usuario pulse nada. Si el barrido MANUAL está en curso,
        su propio canal manda y este aviso se ignora."""
        if self._verificando or not self._servidores:
            return
        self._barra_verificacion.setVisible(True)
        self._lbl_verificacion.setVisible(True)
        self._progreso_verificacion(hechos, total, verificados,
                                     fallidos, hostname, fase)

    def _cargar_servidores(self) -> None:
        self._tarjeta_vpn.fijar_activa(True)
        # Barrita temporal: aparece mientras se actualiza (v1.0.5).
        self._barra_vpn.setVisible(True)
        self._barra_vpn.fijar_texto(t("Actualizando la lista de servidores…"))
        self._btn_servidores.setEnabled(False)
        # SEMILLA PRIMERO (v1.0.5, corrección de raíz): si aún no hay
        # lista, el desplegable y la tabla se pueblan AL INSTANTE con
        # la lista de respaldo local — nunca quedan vacíos esperando a
        # la red; la lista en vivo reemplaza cuando llega.
        # v1.0.14: el poblado previo es la CACHÉ buena en disco (la
        # última lista fusionada real, con sus sellos) y solo sin
        # caché se cae a las semillas fusionadas.
        if not self._servidores:
            previa = srv.servidores_cache_o_semilla()
            if previa.ok:
                self._aplicar_lista(previa)
                datos_previa = (previa.datos
                                if isinstance(previa.datos, dict) else {})
                if datos_previa.get("es_cache"):
                    self._lbl_vpn.setStyleSheet("")
                    self._lbl_vpn.setText(previa.mensaje or "")
                else:
                    self._lbl_vpn.setStyleSheet(
                        f"color: {theme.AMBAR}; font-weight: 600;")
                    self._lbl_vpn.setText(
                        "⚠ " + (previa.mensaje or "") +
                        " Buscando la lista en vivo…")
            else:
                self._lbl_vpn.setStyleSheet("")
                self._lbl_vpn.setText(t("Descargando la lista de VPN Gate…"))
        else:
            self._lbl_vpn.setStyleSheet("")
            self._lbl_vpn.setText(t("Actualizando la lista de servidores…"))
        _lanzar(self, srv.descargar_servidores_completos,
                self._servidores_cargados)

    def _servidores_cargados(self, resultado: ResultadoModulo) -> None:
        self._tarjeta_vpn.fijar_activa(False)
        self._btn_servidores.setEnabled(True)
        # La barrita temporal DESAPARECE al terminar (v1.0.5).
        self._barra_vpn.terminar()
        self._barra_vpn.setVisible(False)
        if not resultado.ok:
            if self._servidores:
                # Ya había lista (la semilla puebla desde el primer
                # segundo): se CONSERVA y se avisa de que la puesta al
                # día falló — nunca vacío en silencio.
                self._lbl_vpn.setStyleSheet(
                    f"color: {theme.AMBAR}; font-weight: 600;")
                self._lbl_vpn.setText(
                    "⚠ No se pudo actualizar la lista en vivo; sigues "
                    "con la lista de respaldo. " + resultado.mensaje)
                self._btn_servidores.setText(t("Reintentar descarga"))
                return
            # Error VISIBLE con la causa y reintento
            self._lbl_vpn.setStyleSheet(f"color: {theme.ROJO};")
            self._lbl_vpn.setText(resultado.mensaje)
            self._btn_servidores.setText(t("Reintentar descarga"))
            return
        self._aplicar_lista(resultado)

    def _aplicar_lista(self, resultado: ResultadoModulo) -> None:
        """Puebla desplegable y tabla con una lista ya obtenida (en
        vivo o la semilla) y deja el aviso que corresponda."""
        if isinstance(resultado.datos, dict):
            datos = resultado.datos
            self._servidores = list(datos.get("servidores") or [])
        else:  # compatibilidad: la lista pelada de la v1.0.2
            datos = {}
            self._servidores = list(resultado.datos or [])
        # v1.0.14: los veredictos viajan con la lista (caché,
        # refresco e intentos los actualizan en el servicio).
        if isinstance(datos.get("veredictos"), dict):
            self._veredictos = dict(datos["veredictos"])
        self._es_semilla_activa = bool(datos.get("es_semilla"))
        self._fecha_semilla = str(datos.get("fecha_semilla") or "")
        if datos.get("es_semilla"):
            # Lista SEMILLA (v1.0.3): la tabla y el desplegable se
            # pueblan igual, pero el aviso de respaldo queda VISIBLE
            # (ámbar) con la fecha y la causa, y el botón invita a
            # reintentar la descarga en vivo.
            self._lbl_vpn.setStyleSheet(f"color: {theme.AMBAR}; font-weight: 600;")
            self._lbl_vpn.setText("⚠ " + resultado.mensaje)
            self._btn_servidores.setText(t("Reintentar descarga"))
            self._poblar_combo_paises()
            self._repintar_servidores()
            return
        self._lbl_vpn.setStyleSheet("")
        self._btn_servidores.setText(t("Actualizar lista de servidores"))
        self._poblar_combo_paises()
        self._repintar_servidores()
        # Aviso final obligatorio (v1.0.5): cuántos servidores/países
        # se cargaron y de QUÉ fuente vinieron.
        if resultado.mensaje:
            self._lbl_vpn.setText(resultado.mensaje)

    def _poblar_combo_paises(self) -> None:
        pais_actual = self._combo_pais.currentData()
        self._combo_pais.blockSignals(True)
        self._combo_pais.clear()
        self._combo_pais.addItem(t("Todos los países"), "")
        for pais in paises_disponibles(self._servidores):
            self._combo_pais.addItem(pais, pais)
        indice = self._combo_pais.findData(pais_actual or "")
        self._combo_pais.setCurrentIndex(indice if indice >= 0 else 0)
        self._combo_pais.blockSignals(False)

    @staticmethod
    def _texto_fuente(servidor) -> str:
        """La marca de fuente de la fila (v1.0.14)."""
        return {"vpngate": "VPN Gate",
                "vpnbook": "VPNBook"}.get(
                    getattr(servidor, "fuente", "vpngate") or "vpngate",
                    "VPN Gate")

    def _texto_verificacion(self, servidor) -> str:
        """El sello de verificación de la fila, con su hora.

        Solo los veredictos VIGENTES se enseñan como tales
        («✓ Verificado 14:32», «Lleno/sin acceso 14:32», «No
        responde 14:32»); un veredicto caducado vuelve a «Sin
        verificar» con la hora del último intento, y sin sonda
        ni intento previos, «Sin verificar» a secas.
        """
        estado, cuando = fuentes_vpn.veredicto_de(
            self._veredictos, servidor)
        if estado == "verificado":
            return t("✓ Verificado ") + time.strftime(
                "%H:%M", time.localtime(cuando))
        if estado == "auth_failed":
            return t("Lleno/sin acceso ") + time.strftime(
                "%H:%M", time.localtime(cuando))
        if estado == "inaccesible":
            return t("No responde ") + time.strftime(
                "%H:%M", time.localtime(cuando))
        if cuando:
            return t("Sin verificar · ") + time.strftime(
                "%H:%M", time.localtime(cuando))
        return t("Sin verificar")

    def _repintar_servidores(self) -> None:
        if not self._servidores:
            return
        pais = self._combo_pais.currentData() or ""
        criterio = self._combo_orden.currentData() or "recomendado"
        visibles = [s for s in self._servidores if not pais or s.pais == pais]
        if criterio == "recomendado":
            # v1.0.14: verificados primero; luego pocas sesiones
            # y más tiempo en línea (core.fuentes_vpn).
            self._visibles = fuentes_vpn.ordenar_candidatos(
                visibles, self._veredictos)
        else:
            ordenados = ordenar_servidores(visibles, criterio)
            # Dentro de cada grupo de veredicto manda el criterio
            # elegido; entre grupos, el veredicto (orden estable).
            ahora = time.time()
            ordenados.sort(
                key=lambda s: fuentes_vpn.rango_veredicto(
                    self._veredictos, s, ahora))
            self._visibles = ordenados
        texto = f"{len(self._visibles)} servidores en la lista."
        if getattr(self, "_es_semilla_activa", False):
            # El aviso de respaldo NO se pierde al repintar/filtrar.
            texto = ("⚠ Lista de respaldo del "
                     f"{getattr(self, '_fecha_semilla', '')} "
                     "(sin conexión con VPN Gate). " + texto)
            self._lbl_vpn.setStyleSheet(
                f"color: {theme.AMBAR}; font-weight: 600;")
        self._lbl_vpn.setText(texto)
        tabla = self._tabla_vpn
        tabla.setRowCount(len(self._visibles))
        for i, s in enumerate(self._visibles):
            tabla.setItem(i, 0, QTableWidgetItem(s.pais))
            tabla.setItem(i, 1, QTableWidgetItem(s.hostname))
            # v1.0.14: la FUENTE de la fila y su sello de
            # verificación con la hora.
            tabla.setItem(i, 2, QTableWidgetItem(self._texto_fuente(s)))
            tabla.setItem(i, 3, QTableWidgetItem(
                f"{s.velocidad_mbps:.0f} Mbps"
                if s.velocidad_mbps else "—"))
            tabla.setItem(i, 4, QTableWidgetItem(
                f"{s.ping_ms} ms" if s.ping_ms < 9000 else "—"))
            tabla.setItem(i, 5, QTableWidgetItem(str(s.sesiones)))
            tabla.setItem(i, 6, QTableWidgetItem(
                self._texto_verificacion(s)))
            # Celda de acción (v1.0.9, cambio pedido por el usuario):
            # un contenedor por fila. Sin conexión: solo «Conectar».
            # Con el túnel arriba en ESE servidor: su botón se pone
            # VERDE y dice «Conectado» y A SU DERECHA, en la misma
            # fila, aparece el botón ROJO «Desconectar».
            celda = QWidget()
            fila_botones = QHBoxLayout(celda)
            fila_botones.setContentsMargins(2, 2, 2, 2)
            fila_botones.setSpacing(6)
            boton = QPushButton(t("Conectar"))
            if s.hostname == self._servidor_conectado:
                boton.setText(t("Conectado"))
                boton.setObjectName("verde")
                boton.setEnabled(False)
                boton.setStyleSheet(
                    f"background-color: {theme.VERDE_BOTON}; color: white; "
                    "font-weight: 700; border-radius: 8px; padding: 6px 12px;")
                fila_botones.addWidget(boton)
                boton_desc = QPushButton(t("Desconectar"))
                boton_desc.setObjectName("peligro")
                boton_desc.setStyleSheet(
                    f"background-color: {theme.ROJO_BOTON}; color: white; "
                    "font-weight: 700; border-radius: 8px; padding: 6px 12px;")
                boton_desc.clicked.connect(
                    lambda _=False: self._desconectar_vpn())
                fila_botones.addWidget(boton_desc)
            else:
                boton.clicked.connect(
                    lambda _=False, serv=s: self._conectar(serv))
                fila_botones.addWidget(boton)
            tabla.setCellWidget(i, 7, celda)
        tabla.resizeColumnsToContents()
        # v1.0.10: red de seguridad de la altura de fila — tras
        # poblar, cada fila se ajusta a su contenido (el botón
        # «Conectar» completo, sin corte inferior) y ninguna baja
        # de 42 px aunque el ajuste al contenido dé menos.
        tabla.resizeRowsToContents()
        for i in range(tabla.rowCount()):
            if tabla.rowHeight(i) < 42:
                tabla.setRowHeight(i, 42)
        if self._servidor_conectado:
            # v1.0.9: con dos botones en la fila conectada, la columna
            # de acción no debe quedarse estrecha y apretarlos.
            tabla.setColumnWidth(7, max(tabla.columnWidth(7), 250))

    def _conectar(self, servidor) -> None:
        # v1.0.12: UN solo intento a la vez — un segundo clic
        # mientras uno conecta no lanza otro openvpn encima del
        # primero (la 1.0.11 los dejaba pelearse por la tarjeta y
        # el primero quedaba huérfano).
        if self._vpn_conectando:
            self._lbl_vpn.setText(
                t("Ya hay una conexión en curso: espera a que termine antes de conectar con otro servidor."))
            return
        self._vpn_conectando = True
        self._lbl_vpn.setStyleSheet("")
        self._lbl_vpn.setText(f"Conectando con {servidor.hostname}…")
        self._lbl_vpn_detalle.setText("")

        def _al_conectar(r: ResultadoModulo) -> None:
            self._vpn_conectando = False
            # v1.0.14: el intento (y el failover) actualizan los
            # veredictos: los sellos se repintan con lo aprendido.
            if isinstance((r.datos or {}).get("veredictos"), dict):
                self._veredictos = dict(r.datos["veredictos"])
            if r.ok and (r.datos or {}).get("conectado"):
                # v1.0.7: túnel confirmado por el motor → el botón de
                # ESE servidor se pone verde y dice «Conectado».
                # v1.0.14: con failover, el servidor conectado puede
                # ser OTRO (el que aceptó): manda el del resultado.
                self._servidor_conectado = (
                    (r.datos or {}).get("hostname") or servidor.hostname)
                self._repintar_servidores()
                self._lbl_vpn.setStyleSheet(
                    f"color: {theme.VERDE}; font-weight: 700;")
                self._lbl_vpn.setText(t("Conectado: ") + t(r.mensaje))
                self._lbl_vpn_detalle.setText("")
            else:
                # v1.0.14: los sellos se repintan con los
                # veredictos del intento ANTES de fijar el mensaje
                # (el repintado reescribe la etiqueta de estado).
                if (r.datos or {}).get("veredictos"):
                    self._repintar_servidores()
                self._lbl_vpn.setStyleSheet("")
                self._lbl_vpn.setText(r.mensaje)
                # v1.0.11: la causa REAL, visible bajo el mensaje
                # (antes el detalle técnico no se pintaba nunca en
                # el flujo VPN y el fallo quedaba indiagnosticable).
                self._lbl_vpn_detalle.setText(
                    f"Detalle técnico: {r.detalle_tecnico}"
                    if r.detalle_tecnico else "")
            # v1.0.11: el interruptor se refresca TAMBIÉN tras un
            # fallo (en la 1.0.10 solo se refrescaba si r.ok y el
            # rótulo falso de «CONECTADA» se quedaba puesto).
            self._ver_estado_vpn()

        # v1.0.14: la lista completa viaja como candidatos del
        # failover (el servicio salta solo al siguiente si el
        # servidor elegido rechaza la conexión).
        _lanzar(self, lambda: srv.conectar_vpn(
            servidor, list(self._servidores)), _al_conectar)

    def _desconectar_vpn(self) -> None:
        self._btn_desconectar.setEnabled(False)
        self._lbl_switch_vpn.setText(t("VPN: desconectando…"))
        _lanzar(self, srv.desconectar_vpn, self._vpn_desconectada)

    def _vpn_desconectada(self, resultado: ResultadoModulo) -> None:
        self._lbl_switch_vpn.setText(
            t("VPN: Desconectada") if resultado.ok else f"VPN: {resultado.mensaje}")
        self._btn_desconectar.setEnabled(False)
        self._lbl_estado_vpn.setText(resultado.mensaje)
        if resultado.ok and self._servidor_conectado:
            # v1.0.7: ningún botón queda en verde tras desconectar.
            self._servidor_conectado = ""
            self._repintar_servidores()
        self._consultar_ip()  # la IP pública se refresca tras desconectar

    def _consultar_ip(self) -> None:
        self._lbl_ip.setText(t("Consultando tu IP pública…"))
        _lanzar(self, srv.ip_publica,
                lambda r: self._lbl_ip.setText(
                    f"Tu IP pública: {r.datos}" if r.ok else r.mensaje))

    # -- Velocidad y estado VPN -------------------------------------------------------
    @staticmethod
    def _bloque_valor(fila: QHBoxLayout, titulo: str, color: str) -> QLabel:
        """Un medidor de la fila de velocidad: rótulo suave + valor en
        color RGB, letra mediana (16 px) y negrita."""
        bloque = QVBoxLayout()
        bloque.addWidget(etiqueta(titulo, suave=True))
        valor = QLabel("—")
        valor.setStyleSheet(
            f"color: {color}; font-size: 16px; font-weight: 700;")
        bloque.addWidget(valor)
        fila.addLayout(bloque)
        fila.addStretch(1)
        return valor

    def _medir_velocidad(self) -> None:
        self._tarjeta_vel.fijar_activa(True)
        self._lbl_velocidad.setText(
            t("Midiendo en segundo plano… primero la DESCARGA y después la SUBIDA (valores en vivo)."))
        self._lbl_valoracion.setText("")
        self._val_ping.setText("…")
        self._val_bajada.setText("…")
        self._val_subida.setText("—")
        self._btn_velocidad.setEnabled(False)
        _lanzar_vivo(self,
                     lambda emisor: srv.prueba_velocidad_viva(
                         lambda fase, mbps: emisor(fase, mbps)),
                     self._progreso_velocidad, self._velocidad_medida)

    def _progreso_velocidad(self, fase: str, mbps: float) -> None:
        # Llega DURANTE la medición (señal desde el hilo): el valor de
        # la fase en curso se actualiza en pantalla, no solo al final.
        if fase == "bajada":
            self._val_bajada.setText(f"{mbps:.1f} Mbps")
            self._lbl_velocidad.setText(
                f"Descargando… {mbps:.1f} Mbps en este momento.")
        elif fase == "subida":
            self._val_subida.setText(f"{mbps:.1f} Mbps")
            self._lbl_velocidad.setText(
                f"Subiendo… {mbps:.1f} Mbps en este momento.")

    def _velocidad_medida(self, resultado: ResultadoModulo) -> None:
        self._tarjeta_vel.fijar_activa(False)
        self._btn_velocidad.setEnabled(True)
        if not resultado.ok:
            self._lbl_velocidad.setText(resultado.mensaje)
            self._lbl_valoracion.setText("")
            self._val_ping.setText("—")
            self._val_bajada.setText("—")
            self._val_subida.setText("—")
            return
        datos = resultado.datos or {}
        ping = datos.get("ping_ms")
        bajada = float(datos.get("bajada_mbps") or 0.0)
        subida = float(datos.get("subida_mbps") or 0.0)
        self._val_ping.setText(f"{ping} ms" if ping is not None else "—")
        self._val_bajada.setText(f"{bajada:.1f} Mbps")
        self._val_subida.setText(f"{subida:.1f} Mbps")
        self._lbl_velocidad.setText(
            f"Medición terminada — Ping: {ping if ping is not None else '—'} ms"
            f" · Bajada: {bajada:.1f} Mbps · Subida: {subida:.1f} Mbps")
        self._lbl_valoracion.setText(valorar_velocidad(bajada))

    def _ver_estado_vpn(self) -> None:
        self._lbl_estado_vpn.setText(t("Consultando el estado VPN…"))
        self._btn_estado_vpn.setEnabled(False)
        _lanzar(self, srv.estado_vpn, self._estado_vpn_visto)

    def _estado_vpn_visto(self, resultado: ResultadoModulo) -> None:
        self._btn_estado_vpn.setEnabled(True)
        if not resultado.ok:
            self._lbl_estado_vpn.setText(resultado.mensaje)
            return
        datos = resultado.datos or {}
        clientes = datos.get("clientes") or []
        ip = datos.get("ip") or ""
        # Interruptor general: estado real (proceso openvpn) + servidor anotado
        if datos.get("conectada"):
            servidor = datos.get("servidor") or "un servidor"
            pais = datos.get("pais") or ""
            self._lbl_switch_vpn.setText(
                t("VPN: CONECTADA a {servidor}", servidor=servidor) + (f" ({pais})" if pais else ""))
            self._btn_desconectar.setEnabled(True)
            # v1.0.7: el botón del servidor conectado se ve en verde.
            if datos.get("servidor") != self._servidor_conectado:
                self._servidor_conectado = datos.get("servidor") or ""
                self._repintar_servidores()
        else:
            self._lbl_switch_vpn.setText(t("VPN: Desconectada"))
            self._btn_desconectar.setEnabled(False)
            if self._servidor_conectado:
                self._servidor_conectado = ""
                self._repintar_servidores()
        lineas = [
            t("Clientes VPN instalados: ") + (", ".join(clientes) if clientes else t("ninguno")),
            t("IP pública actual: ") + (ip if ip else t("sin consultar / no disponible")),
            ("Con OpenVPN (incluido con la app) el túnel lo levanta y "
             "lo baja la propia app desde aquí; con otro cliente, la app "
             "le entrega el perfil y «Desconectar VPN» cierra su proceso "
             "de OpenVPN."),
        ]
        self._lbl_estado_vpn.setText("\n".join(lineas))


def crear_pagina_red(ctx: ContextoModulo):
    return _conservar(_PaginaRed(ctx))


# Compatibilidad: valorar_wifi se usa en el esqueleto anterior; se mantiene
# importado para que otros carriles lo reutilicen desde aquí si lo necesitan.
_ = valorar_wifi
