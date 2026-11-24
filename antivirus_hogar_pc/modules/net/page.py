"""Páginas reales del Carril D: Actualizaciones y Red y VPN.

Todo el trabajo lento (red, winget, Windows Update) corre en un hilo
(_Trabajo) y llega a la UI como contracts.ResultadoModulo: la página solo
pinta el mensaje y los datos, nunca recibe excepciones.
"""
import time

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
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
from antivirus_hogar_pc.core.v102 import valorar_velocidad
from antivirus_hogar_pc.core.vpngate import ordenar_servidores, paises_disponibles
from antivirus_hogar_pc.core.wifi_parse import valorar_wifi
from antivirus_hogar_pc.ui import theme
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


def _lanzar(pagina: QWidget, funcion, al_terminar) -> _Trabajo:
    trabajo = _Trabajo(funcion, pagina)
    trabajo.terminado.connect(al_terminar)
    trabajo.terminado.connect(lambda _r: pagina._trabajos.remove(trabajo)
                              if trabajo in pagina._trabajos else None)
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
        self.setWindowTitle("Qué trae esta actualización")
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
        boton_no = QPushButton("Ahora no")
        boton_no.clicked.connect(self.reject)
        boton_si = QPushButton("Actualizar ahora")
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
        self._programas: list = []
        self._ocupado = False
        self._todo_restantes: list = []
        self._todo_total = 0
        self._todo_completados = 0

        pagina, layout = pagina_base(
            "Actualizaciones",
            "Los programas de tu PC, Windows y la propia aplicación, al día.")
        self._scroll = pagina

        # --- La propia app -----------------------------------------------------
        tarjeta_app, lay = tarjeta("Antivirus Hogar PC")
        self._tarjeta_app = tarjeta_app
        self._lbl_app = etiqueta(f"Estás en la versión {config.VERSION}.")
        lay.addWidget(self._lbl_app)
        self._btn_app = BotonPulso("Buscar actualizaciones de la app")
        self._btn_app.setObjectName("verde")
        self._btn_app.activar_pulso(True)
        self._btn_app.clicked.connect(lambda: self._buscar_app(silencioso=False))
        lay.addWidget(self._btn_app)
        layout.addWidget(tarjeta_app)

        # --- Programas (winget) --------------------------------------------------
        tarjeta_winget, lay_w = tarjeta("Programas desactualizados (winget)")
        self._tarjeta_winget = tarjeta_winget
        self._barra_winget = BarraProgreso()
        lay_w.addWidget(self._barra_winget)
        self._lbl_winget = etiqueta("Pulsa buscar para ver qué programas tienen "
                                    "una versión más nueva.")
        lay_w.addWidget(self._lbl_winget)
        self._tabla_winget = QTableWidget(0, 5)
        self._tabla_winget.setHorizontalHeaderLabels(
            ["Programa", "Versión", "Disponible", "Origen", "Acción"])
        lay_w.addWidget(self._tabla_winget)
        fila_w = QHBoxLayout()
        self._btn_winget = boton_principal("Buscar programas desactualizados", "primario")
        self._btn_winget.clicked.connect(self._buscar_winget)
        self._btn_todo = QPushButton("Actualizar todo")
        self._btn_todo.clicked.connect(self._actualizar_todo)
        fila_w.addWidget(self._btn_winget)
        fila_w.addWidget(self._btn_todo)
        fila_w.addStretch(1)
        lay_w.addLayout(fila_w)
        layout.addWidget(tarjeta_winget)

        # --- Windows Update ---------------------------------------------------------
        tarjeta_wu, lay_u = tarjeta("Actualizaciones de Windows pendientes")
        self._tarjeta_wu = tarjeta_wu
        self._barra_wu = BarraProgreso()
        lay_u.addWidget(self._barra_wu)
        self._lbl_wu = etiqueta("Pulsa buscar para consultar Windows Update.")
        lay_u.addWidget(self._lbl_wu)
        self._lista_wu = QListWidget()
        lay_u.addWidget(self._lista_wu)
        fila_u = QHBoxLayout()
        self._btn_wu = boton_principal("Buscar actualizaciones de Windows", "primario")
        self._btn_wu.clicked.connect(self._buscar_wu)
        self._btn_abrir_wu = QPushButton("Abrir Windows Update")
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
        destino.setText(resultado.mensaje or ("Hecho." if resultado.ok else "No se pudo."))

    def _fijar_ocupado(self, ocupado: bool) -> None:
        self._ocupado = ocupado
        for boton in (self._btn_app, self._btn_winget, self._btn_todo, self._btn_wu):
            boton.setEnabled(not ocupado)

    # -- la propia app ---------------------------------------------------------------
    def _buscar_app(self, silencioso: bool) -> None:
        servicios = getattr(self._ctx, "servicios", None)
        ajustes = getattr(servicios, "ajustes", None)
        if ajustes is None:
            self._lbl_app.setText("El servicio de ajustes no está disponible.")
            return
        self._lbl_app.setText("Comprobando el canal de actualizaciones…")
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
            self._lbl_app.setText("Descargando la actualización…")
            _lanzar(self, lambda: srv.instalar_actualizacion_app(info),
                    lambda r: self._lbl_app.setText(r.mensaje))

    # -- winget ---------------------------------------------------------------------
    def _buscar_winget(self) -> None:
        self._tarjeta_winget.fijar_activa(True)
        self._barra_winget.fijar_texto("Buscando con winget…")
        self._lbl_winget.setText("Buscando con winget… puede tardar un poco.")
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
            boton = QPushButton("Actualizar")
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
            self, "Actualizar todo",
            "Se actualizarán TODOS los programas de la lista con winget, "
            "uno a uno. Algunos pueden pedir confirmación o reiniciar su "
            "instalador. ¿Seguimos?")
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        if not self._programas:
            self._lbl_winget.setText(
                "Primero pulsa «Buscar programas desactualizados» para tener la lista.")
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
            "Consultando Windows Update… (Windows no informa porcentaje)")
        self._lbl_wu.setText("Consultando Windows Update… la primera vez tarda.")
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


def crear_pagina_actualizaciones(ctx: ContextoModulo):
    return _PaginaActualizaciones(ctx).widget()


# =====================================================================================
# Red y VPN
# =====================================================================================
class _PaginaRed(QWidget):
    def __init__(self, ctx: ContextoModulo):
        super().__init__()
        self._ctx = ctx
        self._trabajos: list[_Trabajo] = []
        self._servidores: list = []       # lista completa descargada
        self._visibles: list = []         # lista filtrada/ordenada en pantalla

        pagina, layout = pagina_base(
            "Red y VPN",
            "Tu Wi-Fi de un vistazo y la VPN gratuita de VPN Gate.")
        self._scroll = pagina

        # --- Wi-Fi ----------------------------------------------------------------
        tarjeta_wifi, lay = tarjeta("Wi-Fi")
        self._tarjeta_wifi = tarjeta_wifi
        self._fila_wifi = lay
        self._contenedor_wifi = QWidget()
        self._lay_wifi = QVBoxLayout(self._contenedor_wifi)
        self._lay_wifi.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._contenedor_wifi)
        self._lbl_wifi_detalle = etiqueta("")
        lay.addWidget(self._lbl_wifi_detalle)
        self._lbl_perfiles = etiqueta("", suave=True)
        lay.addWidget(self._lbl_perfiles)
        self._btn_wifi = boton_principal("Actualizar datos de Wi-Fi", "primario")
        self._btn_wifi.clicked.connect(self._cargar_wifi)
        lay.addWidget(self._btn_wifi)
        self._barra_wifi = BarraProgreso()
        self._barra_wifi.setVisible(False)
        lay.addWidget(self._barra_wifi)
        self._lbl_wifi_sello = etiqueta("", suave=True)
        lay.addWidget(self._lbl_wifi_sello)
        layout.addWidget(tarjeta_wifi)

        # --- Velocidad de internet y estado VPN -------------------------------------
        tarjeta_vel, lay_vel = tarjeta("Velocidad de internet y estado VPN")
        self._tarjeta_vel = tarjeta_vel
        self._lbl_velocidad = etiqueta("Todavía no se ha medido la velocidad.")
        lay_vel.addWidget(self._lbl_velocidad)
        self._lbl_valoracion = etiqueta("", suave=True)
        lay_vel.addWidget(self._lbl_valoracion)
        self._btn_velocidad = boton_principal("Medir velocidad", "primario")
        self._btn_velocidad.clicked.connect(self._medir_velocidad)
        lay_vel.addWidget(self._btn_velocidad)
        self._lbl_estado_vpn = etiqueta("Estado VPN sin consultar.", suave=True)
        lay_vel.addWidget(self._lbl_estado_vpn)
        self._btn_estado_vpn = QPushButton("Ver estado VPN")
        self._btn_estado_vpn.clicked.connect(self._ver_estado_vpn)
        lay_vel.addWidget(self._btn_estado_vpn)
        layout.addWidget(tarjeta_vel)

        # --- VPN Gate ----------------------------------------------------------------
        tarjeta_vpn, lay_v = tarjeta("VPN Gate (servidores de voluntarios)")
        self._tarjeta_vpn = tarjeta_vpn
        aviso = etiqueta(
            "AVISO: estos servidores los ofrecen VOLUNTARIOS y el operador puede "
            "registrar la conexión. Úsalos para navegar con otra ubicación, "
            "nunca para banca, compras ni datos sensibles.")
        aviso.setStyleSheet(f"color: {theme.AMBAR};")
        lay_v.addWidget(aviso)

        # Interruptor general de la VPN (v1.0.2): estado + apagado desde la app
        fila_switch = QHBoxLayout()
        self._lbl_switch_vpn = etiqueta("VPN: consultando el estado…")
        fila_switch.addWidget(self._lbl_switch_vpn, 1)
        self._btn_desconectar = QPushButton("Desconectar VPN")
        self._btn_desconectar.setObjectName("peligro")
        self._btn_desconectar.setEnabled(False)
        self._btn_desconectar.clicked.connect(self._desconectar_vpn)
        fila_switch.addWidget(self._btn_desconectar)
        lay_v.addLayout(fila_switch)

        fila_ctrl = QHBoxLayout()
        fila_ctrl.addWidget(QLabel("País:"))
        self._combo_pais = QComboBox()
        self._combo_pais.addItem("Todos los países", "")
        self._combo_pais.currentIndexChanged.connect(self._repintar_servidores)
        fila_ctrl.addWidget(self._combo_pais)
        fila_ctrl.addWidget(QLabel("Ordenar por:"))
        self._combo_orden = QComboBox()
        self._combo_orden.addItem("Velocidad", "velocidad")
        self._combo_orden.addItem("Ping (respuesta)", "ping")
        self._combo_orden.addItem("Sesiones actuales", "sesiones")
        self._combo_orden.addItem("Puntuación", "puntuacion")
        self._combo_orden.currentIndexChanged.connect(self._repintar_servidores)
        fila_ctrl.addWidget(self._combo_orden)
        self._btn_servidores = boton_principal("Actualizar lista de servidores", "primario")
        self._btn_servidores.clicked.connect(self._cargar_servidores)
        fila_ctrl.addWidget(self._btn_servidores)
        fila_ctrl.addStretch(1)
        lay_v.addLayout(fila_ctrl)

        self._lbl_vpn = etiqueta("Pulsa «Actualizar lista de servidores» para "
                                 "descargar la lista pública de VPN Gate.")
        lay_v.addWidget(self._lbl_vpn)
        self._tabla_vpn = QTableWidget(0, 6)
        self._tabla_vpn.setHorizontalHeaderLabels(
            ["País", "Servidor", "Velocidad", "Ping", "Sesiones", "Acción"])
        lay_v.addWidget(self._tabla_vpn)
        lay_v.addWidget(etiqueta(
            "La conexión la hace SoftEther VPN Client (recomendado por VPN Gate) "
            "u OpenVPN Connect: la app genera el perfil .ovpn y se lo entrega; "
            "no crea el túnel."))
        fila_ip = QHBoxLayout()
        self._lbl_ip = etiqueta("Tu IP pública: sin consultar.")
        self._btn_ip = QPushButton("Consultar mi IP pública")
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

    # -- Wi-Fi ----------------------------------------------------------------------
    def _cargar_wifi(self) -> None:
        # Feedback INMEDIATO (bug 4): antes el botón no hacía nada visible.
        self._tarjeta_wifi.fijar_activa(True)
        self._btn_wifi.setEnabled(False)
        self._btn_wifi.setText("Leyendo…")
        self._barra_wifi.setVisible(True)
        self._barra_wifi.fijar_texto("Leyendo la red Wi-Fi…")
        self._lbl_wifi_detalle.setText("Leyendo la red Wi-Fi…")
        _lanzar(self, srv.informe_wifi, self._wifi_cargado)

    def _wifi_cargado(self, resultado: ResultadoModulo) -> None:
        import time as _time

        self._tarjeta_wifi.fijar_activa(False)
        self._btn_wifi.setEnabled(True)
        self._btn_wifi.setText("Actualizar datos de Wi-Fi")
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
                "wifi", "estatico", "Wi-Fi no disponible", causa, theme.ROJO))
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
        color = {"bien": theme.VERDE, "regular": theme.AMBAR, "mal": theme.ROJO}.get(
            nivel, theme.CIAN)
        titulo = f"Red: {info.ssid}" if info and info.ssid else "Sin red Wi-Fi conectada"
        self._lay_wifi.addWidget(fila_estado("wifi", "estatico", titulo, frase, color))
        if info and info.conectada:
            senal = f"{info.senal_pct} %" if info.senal_pct is not None else "—"
            detalle = (f"Señal {senal} · Banda {info.banda or '—'} · Canal {info.canal or '—'} "
                       f"· Seguridad {info.autenticacion or '—'} ({info.cifrado or '—'}) "
                       f"· Radio {info.tipo_radio or '—'}")
            categoria = datos.get("perfil_red") or ""
            if categoria:
                detalle += f" · Perfil de red: {categoria}"
            self._lbl_wifi_detalle.setText(detalle)
        else:
            self._lbl_wifi_detalle.setText("")
        perfiles = datos.get("perfiles_guardados") or []
        self._lbl_perfiles.setText(
            "Redes guardadas en este PC: " + (", ".join(perfiles) if perfiles else "ninguna"))

    # -- VPN Gate ---------------------------------------------------------------------
    def _cargar_servidores(self) -> None:
        self._tarjeta_vpn.fijar_activa(True)
        self._lbl_vpn.setStyleSheet("")
        self._lbl_vpn.setText("Descargando la lista de VPN Gate…")
        self._btn_servidores.setEnabled(False)
        _lanzar(self, srv.descargar_servidores_completos, self._servidores_cargados)

    def _servidores_cargados(self, resultado: ResultadoModulo) -> None:
        self._tarjeta_vpn.fijar_activa(False)
        self._btn_servidores.setEnabled(True)
        if not resultado.ok:
            # Error VISIBLE con la causa y reintento (nada de vacío en silencio)
            self._lbl_vpn.setStyleSheet(f"color: {theme.ROJO};")
            self._lbl_vpn.setText(resultado.mensaje)
            self._btn_servidores.setText("Reintentar descarga")
            return
        if isinstance(resultado.datos, dict):
            datos = resultado.datos
            self._servidores = list(datos.get("servidores") or [])
        else:  # compatibilidad: la lista pelada de la v1.0.2
            datos = {}
            self._servidores = list(resultado.datos or [])
        self._es_semilla_activa = bool(datos.get("es_semilla"))
        self._fecha_semilla = str(datos.get("fecha_semilla") or "")
        if datos.get("es_semilla"):
            # Lista SEMILLA (v1.0.3): la tabla y el desplegable se
            # pueblan igual, pero el aviso de respaldo queda VISIBLE
            # (ámbar) con la fecha y la causa, y el botón invita a
            # reintentar la descarga en vivo.
            self._lbl_vpn.setStyleSheet(f"color: {theme.AMBAR}; font-weight: 600;")
            self._lbl_vpn.setText("⚠ " + resultado.mensaje)
            self._btn_servidores.setText("Reintentar descarga")
            self._poblar_combo_paises()
            self._repintar_servidores()
            return
        self._lbl_vpn.setStyleSheet("")
        self._btn_servidores.setText("Actualizar lista de servidores")
        self._poblar_combo_paises()
        self._repintar_servidores()

    def _poblar_combo_paises(self) -> None:
        pais_actual = self._combo_pais.currentData()
        self._combo_pais.blockSignals(True)
        self._combo_pais.clear()
        self._combo_pais.addItem("Todos los países", "")
        for pais in paises_disponibles(self._servidores):
            self._combo_pais.addItem(pais, pais)
        indice = self._combo_pais.findData(pais_actual or "")
        self._combo_pais.setCurrentIndex(indice if indice >= 0 else 0)
        self._combo_pais.blockSignals(False)

    def _repintar_servidores(self) -> None:
        if not self._servidores:
            return
        pais = self._combo_pais.currentData() or ""
        criterio = self._combo_orden.currentData() or "velocidad"
        visibles = [s for s in self._servidores if not pais or s.pais == pais]
        self._visibles = ordenar_servidores(visibles, criterio)
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
            tabla.setItem(i, 2, QTableWidgetItem(f"{s.velocidad_mbps:.0f} Mbps"))
            tabla.setItem(i, 3, QTableWidgetItem(f"{s.ping_ms} ms"))
            tabla.setItem(i, 4, QTableWidgetItem(str(s.sesiones)))
            boton = QPushButton("Conectar")
            boton.clicked.connect(lambda _=False, serv=s: self._conectar(serv))
            tabla.setCellWidget(i, 5, boton)
        tabla.resizeColumnsToContents()

    def _conectar(self, servidor) -> None:
        self._lbl_vpn.setText(f"Preparando el perfil de {servidor.hostname}…")

        def _al_conectar(r: ResultadoModulo) -> None:
            self._lbl_vpn.setText(r.mensaje)
            if r.ok:
                self._ver_estado_vpn()  # el interruptor refleja el servidor

        _lanzar(self, lambda: srv.conectar_vpn(servidor), _al_conectar)

    def _desconectar_vpn(self) -> None:
        self._btn_desconectar.setEnabled(False)
        self._lbl_switch_vpn.setText("VPN: desconectando…")
        _lanzar(self, srv.desconectar_vpn, self._vpn_desconectada)

    def _vpn_desconectada(self, resultado: ResultadoModulo) -> None:
        self._lbl_switch_vpn.setText(
            "VPN: Desconectada" if resultado.ok else f"VPN: {resultado.mensaje}")
        self._btn_desconectar.setEnabled(False)
        self._lbl_estado_vpn.setText(resultado.mensaje)
        self._consultar_ip()  # la IP pública se refresca tras desconectar

    def _consultar_ip(self) -> None:
        self._lbl_ip.setText("Consultando tu IP pública…")
        _lanzar(self, srv.ip_publica,
                lambda r: self._lbl_ip.setText(
                    f"Tu IP pública: {r.datos}" if r.ok else r.mensaje))

    # -- Velocidad y estado VPN -------------------------------------------------------
    def _medir_velocidad(self) -> None:
        self._tarjeta_vel.fijar_activa(True)
        self._lbl_velocidad.setText("Midiendo la velocidad… (descarga real de prueba)")
        self._lbl_valoracion.setText("")
        self._btn_velocidad.setEnabled(False)
        _lanzar(self, srv.prueba_velocidad, self._velocidad_medida)

    def _velocidad_medida(self, resultado: ResultadoModulo) -> None:
        self._tarjeta_vel.fijar_activa(False)
        self._btn_velocidad.setEnabled(True)
        if not resultado.ok:
            self._lbl_velocidad.setText(resultado.mensaje)
            self._lbl_valoracion.setText("")
            return
        datos = resultado.datos or {}
        ping = datos.get("ping_ms")
        bajada = float(datos.get("bajada_mbps") or 0.0)
        ping_txt = f"{ping} ms" if ping is not None else "—"
        self._lbl_velocidad.setText(f"Ping: {ping_txt} · Bajada: {bajada:.1f} Mbps")
        self._lbl_valoracion.setText(valorar_velocidad(bajada))

    def _ver_estado_vpn(self) -> None:
        self._lbl_estado_vpn.setText("Consultando el estado VPN…")
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
                f"VPN: CONECTADA a {servidor}" + (f" ({pais})" if pais else ""))
            self._btn_desconectar.setEnabled(True)
        else:
            self._lbl_switch_vpn.setText("VPN: Desconectada")
            self._btn_desconectar.setEnabled(False)
        lineas = [
            "Clientes VPN instalados: " + (", ".join(clientes) if clientes else "ninguno"),
            "IP pública actual: " + (ip if ip else "sin consultar / no disponible"),
            ("El túnel lo crea el cliente VPN con el perfil que la app le "
             "entrega; el interruptor «Desconectar VPN» sí lo apaga desde "
             "aquí cerrando el proceso de OpenVPN."),
        ]
        self._lbl_estado_vpn.setText("\n".join(lineas))


def crear_pagina_red(ctx: ContextoModulo):
    return _PaginaRed(ctx).widget()


# Compatibilidad: valorar_wifi se usa en el esqueleto anterior; se mantiene
# importado para que otros carriles lo reutilicen desde aquí si lo necesitan.
_ = valorar_wifi
