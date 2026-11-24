"""Páginas reales del Carril C: Drivers, Discos y Limpieza.

- Drivers: winapi.drivers_win + core.drivers_logic — cadena oficial del
  usuario (Windows Update/Catálogo → chip → marca de la PC), punto de
  restauración antes de instalar y solo drivers firmados. La tabla da el
  ancho flexible SOLO al dispositivo: la columna «Acción» tiene ancho
  fijo y queda siempre visible a la derecha.
- Discos: contracts.SmartInfo vía pySMART/smartctl con respaldo
  Get-PhysicalDisk; sin datos = «no se puede leer», nunca «sano».
  Optimización con Optimize-Volume (TRIM en SSD, defrag en HDD).
  Mapa de uso por carpetas del usuario, con % sobre el total medido.
- Limpieza: informe antes de borrar, borrado tras confirmación con
  progreso real por partidas, arranque reversible con su impacto, y
  respaldo (punto de restauración + copia del registro).
  SIN limpiador de registro.

Las barras son ui.widgets_v102.BarraProgreso: porcentaje SOLO donde se
puede contar de verdad (pasos del escaneo, partidas de la limpieza,
carpetas del mapa); donde Windows no informa % (la instalación de
Windows Update) se enseña la etapa, nunca un porcentaje inventado.

Todo el trabajo pesado corre en un hilo (QThread) tras la barra de
progreso: la ventana nunca se congela y los procesos quedan ocultos.
"""
from PySide6.QtCore import QObject, Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QLabel, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
from antivirus_hogar_pc.core import drivers_logic
from antivirus_hogar_pc.core.hashing import tamano_legible
from antivirus_hogar_pc.ui import theme
from antivirus_hogar_pc.ui.paginas_base import (boton_principal, etiqueta,
                                                fila_estado, pagina_base,
                                                tarjeta)
from antivirus_hogar_pc.ui.widgets_v102 import BarraProgreso

from . import servicios_sistema as svc

_TEXTOS_ESTADO = {
    "al_dia": ("Al día", theme.VERDE),
    "hay_uno_mas_nuevo": ("Hay uno más nuevo", theme.AMBAR),
    "sin_datos": ("Sin confirmar", theme.TEXTO_SUAVE),
}
_TEXTOS_SALUD = {"bien": "buena", "regular": "con aviso",
                 "mal": "mala", "desconocido": "sin leer"}
_IMPACTO = {
    "alto": ("Alto", theme.ROJO),
    "medio": ("Medio", theme.AMBAR),
    "bajo": ("Bajo", theme.VERDE),
}


def _registrar(ctx: ContextoModulo, tipo: str, detalle: str) -> None:
    """Registro de actividad vía ctx.servicios.registrar_actividad, si
    existe (en pruebas puede ser un fake sin ese método): nunca rompe."""
    try:
        registrar = getattr(getattr(ctx, "servicios", None),
                            "registrar_actividad", None)
        if callable(registrar):
            registrar(tipo, detalle)
    except Exception:
        pass  # el registro es un extra; jamás debe tumbar la página


class _Trabajador(QThread):
    """Ejecuta una función de servicios fuera del hilo de la ventana.

    Si se le pide progreso, la función recibe como primer argumento un
    emisor seguro entre hilos: progreso(*valores) viaja por señal Qt."""
    terminado = Signal(object)
    progreso = Signal(object)

    def __init__(self, funcion, *args, con_progreso: bool = False):
        super().__init__()
        self._funcion = funcion
        self._args = args
        self._con_progreso = con_progreso

    def run(self):  # noqa: N802 (API de Qt)
        try:
            if self._con_progreso:
                resultado = self._funcion(
                    lambda *valores: self.progreso.emit(tuple(valores)),
                    *self._args)
            else:
                resultado = self._funcion(*self._args)
        except Exception as exc:  # los servicios ya no lanzan; red de seguridad
            resultado = ResultadoModulo(ok=False,
                                        mensaje=f"No se pudo completar: {exc}")
        self.terminado.emit(resultado)


class _ReceptorProgreso(QObject):
    """Recibe el progreso en el hilo de la ventana (la señal llega en
    cola desde el hilo trabajador) y lo pasa a la barra."""

    def __init__(self, al_progreso):
        super().__init__()
        self._al_progreso = al_progreso

    @Slot(object)
    def recibir(self, valores):
        try:
            self._al_progreso(*valores)
        except Exception:
            pass


class _GestorTrabajos:
    """Mantiene vivos los hilos hasta que terminan y entrega el resultado."""

    def __init__(self):
        self._activos: list[_Trabajador] = []
        self._receptores: list[_ReceptorProgreso] = []

    def lanzar(self, funcion, al_terminar, *args, al_progreso=None) -> None:
        trabajador = _Trabajador(funcion, *args,
                                 con_progreso=al_progreso is not None)
        receptor = None
        if al_progreso is not None:
            receptor = _ReceptorProgreso(al_progreso)
            trabajador.progreso.connect(receptor.recibir)
            self._receptores.append(receptor)

        def _fin(resultado):
            if trabajador in self._activos:
                self._activos.remove(trabajador)
            if receptor is not None and receptor in self._receptores:
                self._receptores.remove(receptor)
            al_terminar(resultado)

        trabajador.terminado.connect(_fin)
        self._activos.append(trabajador)
        trabajador.start()

    @property
    def ocupado(self) -> bool:
        return bool(self._activos)


def _vaciar(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def _abrir(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))


def _confirmar(padre: QWidget, titulo: str, texto: str) -> bool:
    respuesta = QMessageBox.question(
        padre, titulo, texto,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No)
    return respuesta == QMessageBox.StandardButton.Yes


# === DRIVERS ======================================================================
def crear_pagina_drivers(ctx: ContextoModulo):
    pagina, layout = pagina_base(
        "Drivers",
        "Escanea los drivers de la PC y los contrasta con las fuentes "
        "oficiales, en este orden: Windows Update y el Catálogo de Microsoft; "
        "si no está ahí, el fabricante del chip (NVIDIA, AMD, Intel) y la "
        "marca de tu PC. Todo ocurre por detrás: solo verás la barra de "
        "progreso y el aviso al terminar.")
    gestor = _GestorTrabajos()
    estado_actual: dict = {"estados": [], "fabricante_pc": ""}

    tarjeta_escaner, lay_e = tarjeta("Drivers de esta PC")
    barra = BarraProgreso()
    barra.setVisible(False)
    lbl_estado = etiqueta("Todavía no se ha escaneado. Pulsa «Escanear drivers».",
                          suave=True)
    tabla = QTableWidget(0, 5)
    tabla.setHorizontalHeaderLabels(
        ["Dispositivo", "Versión instalada", "Fecha", "Estado", "Acción"])
    # Sin estirar la última sección: la «Acción» tiene ancho FIJO y siempre
    # visible; el ancho sobrante lo absorbe solo el nombre del dispositivo,
    # que se corta con elipsis y enseña el nombre completo en el tooltip.
    cabecera = tabla.horizontalHeader()
    cabecera.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    cabecera.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
    cabecera.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
    cabecera.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
    cabecera.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
    tabla.setColumnWidth(1, 150)   # Versión instalada, acotada
    tabla.setColumnWidth(2, 110)   # Fecha, acotada
    tabla.setColumnWidth(3, 130)   # Estado, acotada
    tabla.setColumnWidth(4, 250)   # Acción: Actualizar + Fuentes oficiales
    tabla.setTextElideMode(Qt.TextElideMode.ElideRight)
    btn_escanear = boton_principal("Escanear drivers", "primario")
    lbl_causa_wu = etiqueta("", suave=True)
    lbl_causa_wu.setVisible(False)
    lay_e.addWidget(btn_escanear)
    lay_e.addWidget(barra)
    lay_e.addWidget(lbl_estado)
    lay_e.addWidget(lbl_causa_wu)
    lay_e.addWidget(tabla)
    lay_e.addWidget(etiqueta(
        "Antes de instalar un driver se crea un punto de restauración "
        "automático, y solo se instalan drivers firmados (Windows Update "
        "solo sirve drivers firmados por Microsoft). Nada de bases de "
        "terceros."))
    layout.addWidget(tarjeta_escaner)

    tarjeta_fuentes, lay_f = tarjeta("Cadena oficial de fuentes")
    lay_f.addWidget(etiqueta(
        "1) Windows Update / Microsoft Update Catalog · 2) Fabricante del "
        "chip · 3) Página oficial de la marca de tu PC. Tras escanear, cada "
        "driver tendrá aquí y en su fila los enlaces que le tocan."))
    contenedor_enlaces = QVBoxLayout()
    lay_f.addLayout(contenedor_enlaces)
    layout.addWidget(tarjeta_fuentes)
    layout.addStretch(1)

    def _pintar_enlaces():
        _vaciar(contenedor_enlaces)
        fila = QHBoxLayout()
        btn_wu = QPushButton("Abrir Windows Update")
        btn_wu.clicked.connect(lambda: _abrir("ms-settings:windowsupdate"))
        fila.addWidget(btn_wu)
        btn_catalogo = QPushButton("Microsoft Update Catalog")
        btn_catalogo.clicked.connect(
            lambda: _abrir(drivers_logic.URL_CATALOGO_MICROSOFT))
        fila.addWidget(btn_catalogo)
        fila.addStretch(1)
        contenedor = QWidget()
        contenedor.setLayout(fila)
        contenedor_enlaces.addWidget(contenedor)

    def _al_terminar_actualizacion(resultado: ResultadoModulo):
        barra.terminar()
        btn_escanear.setEnabled(True)
        lbl_estado.setText(resultado.mensaje)
        _registrar(ctx, "drivers", resultado.mensaje if resultado.ok else
                   f"Actualización de drivers fallida: {resultado.mensaje}")

    def _al_terminar_punto(resultado: ResultadoModulo):
        if not resultado.ok:
            # Sin punto de restauración NO se instala nada.
            barra.terminar()
            btn_escanear.setEnabled(True)
            lbl_estado.setText(resultado.mensaje)
            _registrar(ctx, "drivers",
                       f"Actualización de drivers no realizada: "
                       f"{resultado.mensaje}")
            return
        barra.fijar_etapas(2, 2, "Instalando con Windows Update "
                                 "(Windows no informa el porcentaje)")
        lbl_estado.setText("Punto de restauración creado. Instalando con "
                           "Windows Update… puede tardar unos minutos.")
        gestor.lanzar(svc.instalar_drivers_wu, _al_terminar_actualizacion)

    def _actualizar():
        if not _confirmar(
                pagina, "Actualizar drivers",
                "Se creará primero un punto de restauración. Después, "
                "Windows Update descargará e instalará los drivers nuevos "
                "que ofrece para esta PC (solo firmados). Windows pedirá "
                "permiso de administrador. ¿Seguir?"):
            return
        barra.setVisible(True)
        barra.fijar_etapas(1, 2, "Creando punto de restauración")
        btn_escanear.setEnabled(False)
        lbl_estado.setText("Creando el punto de restauración…")
        gestor.lanzar(svc.crear_punto_para_drivers, _al_terminar_punto)

    def _pintar_tabla(estados):
        tabla.setRowCount(len(estados))
        for i, est in enumerate(estados):
            d = est.driver
            nombre = d.dispositivo
            if not d.firmado:
                nombre += "  (sin firma)"
            item_nombre = QTableWidgetItem(nombre)
            item_nombre.setToolTip(nombre)  # nombre completo, sin cortar
            tabla.setItem(i, 0, item_nombre)
            tabla.setItem(i, 1, QTableWidgetItem(d.version or "—"))
            tabla.setItem(i, 2, QTableWidgetItem(d.fecha or "—"))
            texto, color = _TEXTOS_ESTADO[est.estado]
            item = QTableWidgetItem(texto)
            item.setForeground(QColor(color))
            tabla.setItem(i, 3, item)
            celda = QWidget()
            fila = QHBoxLayout(celda)
            fila.setContentsMargins(0, 0, 0, 0)
            if drivers_logic.puede_actualizar(est):
                btn = QPushButton("Actualizar")
                btn.clicked.connect(lambda _=False: _actualizar())
                fila.addWidget(btn)
            btn_fuentes = QPushButton("Fuentes oficiales")
            btn_fuentes.clicked.connect(
                lambda _=False, e=est: _mostrar_fuentes(pagina, e,
                                                        estado_actual["fabricante_pc"]))
            fila.addWidget(btn_fuentes)
            fila.addStretch(1)
            tabla.setCellWidget(i, 4, celda)

    escaneo = {"activo": False, "vigia": None}

    def _mostrar_fallo_escaneo(resultado: ResultadoModulo):
        """Bug 5: un fallo del escaneo se ve SIEMPRE, en rojo y con la
        causa; nunca tabla vacía en silencio ni «escaneando» eterno."""
        escaneo["activo"] = False
        tarjeta_escaner.fijar_activa(False)
        if escaneo["vigia"] is not None:
            escaneo["vigia"].stop()
        barra.terminar()
        btn_escanear.setEnabled(True)
        # v1.0.5: en pantalla solo el mensaje en español; el detalle
        # técnico crudo va SOLO al registro de actividad.
        lbl_estado.setStyleSheet(f"color: {theme.ROJO}; font-weight: 700;")
        lbl_estado.setText(f"⚠ No se pudo escanear: {resultado.mensaje}")
        _registrar(ctx, "drivers", f"Escaneo de drivers fallido: {resultado.mensaje}")
        if resultado.detalle_tecnico:
            _registrar(ctx, "drivers",
                       f"Detalle técnico del escaneo: {resultado.detalle_tecnico}")

    def _al_terminar_escaneo(resultado: ResultadoModulo):
        escaneo["activo"] = False
        tarjeta_escaner.fijar_activa(False)
        if escaneo["vigia"] is not None:
            escaneo["vigia"].stop()
        barra.terminar()
        btn_escanear.setEnabled(True)
        if not resultado.ok or not isinstance(resultado.datos, dict):
            _mostrar_fallo_escaneo(resultado)
            return
        lbl_estado.setStyleSheet("")
        lbl_estado.setText(resultado.mensaje)
        # v1.0.5: el renglón rojo enseña la causa BREVE y humana (p.
        # ej. «Windows Update no respondió en el tiempo límite»); la
        # causa cruda de Windows Update (comandos, HRESULT) va SOLO al
        # registro de actividad — nunca más volcada en la interfaz.
        from antivirus_hogar_pc.core.drivers_logic import causa_breve_drivers

        causa_wu = str(resultado.datos.get("wu_causa", "") or "")
        breve = str(resultado.datos.get("causa_breve", "") or "")
        if not breve and causa_wu:
            breve = causa_breve_drivers(causa_wu)
        if breve:
            lbl_causa_wu.setStyleSheet(f"color: {theme.ROJO}; font-weight: 600;")
            lbl_causa_wu.setText(
                f"⚠ Algunos drivers quedaron sin confirmar. Causa: {breve}")
            lbl_causa_wu.setVisible(True)
        else:
            lbl_causa_wu.setText("")
            lbl_causa_wu.setVisible(False)
        if causa_wu or resultado.detalle_tecnico:
            _registrar(ctx, "drivers",
                       "Detalle técnico de la confirmación de drivers: "
                       f"{resultado.detalle_tecnico or causa_wu}")
        estado_actual.update(resultado.datos)
        _pintar_tabla(resultado.datos["estados"])

    def _al_terminar_paso2(resultado: ResultadoModulo):
        datos1 = estado_actual.get("_paso1") or {}
        instalados = datos1.get("instalados", [])
        fabricante = datos1.get("fabricante_pc", "")
        if not resultado.ok or not isinstance(resultado.datos, dict):
            _mostrar_fallo_escaneo(resultado)
            return
        barra.fijar_etapas(3, 3, "Comparando versiones")
        lbl_estado.setText("Fuentes consultadas. Comparando versiones…")
        if isinstance(resultado.datos.get("estados"), list):
            # v1.0.5: la cadena ya comparó (Catálogo → WU → almacén);
            # los estados llegan resueltos en el propio paso 2.
            datos_final = dict(resultado.datos)
            datos_final["fabricante_pc"] = fabricante
            _al_terminar_escaneo(ResultadoModulo(
                ok=True, mensaje=resultado.mensaje, datos=datos_final,
                detalle_tecnico=resultado.detalle_tecnico))
            return
        try:
            final = svc.escanear_drivers_paso3_comparar(
                instalados, resultado.datos.get("ofrecidas", []),
                bool(resultado.datos.get("wu_consultado")), fabricante,
                str(resultado.datos.get("wu_causa", "") or ""))
        except Exception as exc:  # defensa: jamás colgar el escaneo
            final = ResultadoModulo(
                False, f"No se pudo completar la comparación: {exc}")
        _al_terminar_escaneo(final)

    def _al_terminar_paso1(resultado: ResultadoModulo):
        if not resultado.ok or not isinstance(resultado.datos, dict):
            _mostrar_fallo_escaneo(resultado)
            return
        estado_actual["_paso1"] = resultado.datos
        estado_actual.update(resultado.datos)
        barra.fijar_etapas(2, 3, "Consultando fuentes oficiales "
                                 "(Catálogo de Microsoft y Windows Update)")
        lbl_estado.setText("Drivers leídos. Confirmando contra las fuentes "
                           "oficiales (primero el Catálogo de Microsoft, "
                           "por dispositivo)…")
        gestor.lanzar(svc.escanear_drivers_paso2_buscar, _al_terminar_paso2,
                      resultado.datos["instalados"])

    def _aviso_lento():
        # Vigía anti-cuelgue (bug 5): si un paso tarda más de 2 minutos,
        # la pantalla lo DICE en vez de quedarse «escaneando» en silencio.
        if escaneo["activo"]:
            lbl_estado.setText(
                "Windows está tardando más de lo normal en responder; el "
                "escaneo sigue en curso. Si el servicio de Windows Update "
                "está ocupado puede tardar varios minutos.")

    def _escanear():
        if gestor.ocupado:
            return
        lbl_estado.setStyleSheet("")
        lbl_causa_wu.setText("")
        lbl_causa_wu.setVisible(False)
        tarjeta_escaner.fijar_activa(True)
        barra.setVisible(True)
        barra.fijar_etapas(1, 3, "Leyendo los drivers instalados")
        btn_escanear.setEnabled(False)
        lbl_estado.setText("Leyendo los drivers instalados…")
        escaneo["activo"] = True
        if escaneo["vigia"] is None:
            vigia = QTimer(pagina)
            vigia.setSingleShot(True)
            vigia.timeout.connect(_aviso_lento)
            escaneo["vigia"] = vigia
        escaneo["vigia"].start(120000)
        gestor.lanzar(svc.escanear_drivers_paso1, _al_terminar_paso1)

    btn_escanear.clicked.connect(_escanear)
    _pintar_enlaces()
    return pagina


def _mostrar_fuentes(pagina: QWidget, estado, fabricante_pc: str) -> None:
    enlaces = svc.enlaces_oficiales_driver(estado, fabricante_pc)
    texto = (f"{estado.driver.dispositivo}\n"
             f"Versión instalada: {estado.driver.version or '—'}"
             f" ({estado.driver.fecha or 'sin fecha'})\n"
             f"Fabricante: {estado.driver.fabricante or '—'}\n\n"
             f"{estado.detalle}\n\n"
             "Fuentes oficiales, en el orden de la cadena:")
    caja = QMessageBox(pagina)
    caja.setWindowTitle("Fuentes oficiales del driver")
    caja.setText(texto)
    botones = []
    for nombre, url in enlaces:
        boton = caja.addButton(nombre, QMessageBox.ButtonRole.ActionRole)
        botones.append((boton, url))
    caja.addButton("Cerrar", QMessageBox.ButtonRole.RejectRole)
    caja.exec()
    for boton, url in botones:
        if caja.clickedButton() is boton:
            _abrir(url)
            break


# === DISCOS =======================================================================
def crear_pagina_discos(ctx: ContextoModulo):
    pagina, layout = pagina_base(
        "Discos",
        "Salud SMART de cada disco y optimización con la herramienta de "
        "Windows: TRIM en discos SSD y desfragmentación solo en mecánicos. "
        "Si un disco no deja leer su salud (USB o RAID), se dice tal cual: "
        "«no se puede leer», nunca «sano».")
    gestor = _GestorTrabajos()
    datos_actuales: dict = {"fisicos": [], "volumenes": []}

    tarjeta_discos, lay_d = tarjeta("Salud de los discos")
    barra = BarraProgreso()
    barra.setVisible(False)
    lbl_estado = etiqueta("Todavía no se ha analizado ningún disco.", suave=True)
    btn_analizar = boton_principal("Analizar discos", "primario")
    contenedor_discos = QVBoxLayout()
    lay_d.addWidget(btn_analizar)
    lay_d.addWidget(barra)
    lay_d.addWidget(lbl_estado)
    lay_d.addLayout(contenedor_discos)
    layout.addWidget(tarjeta_discos)

    tarjeta_vol, lay_v = tarjeta("Optimizar volúmenes")
    lay_v.addWidget(etiqueta(
        "La optimización la hace Windows con Optimize-Volume y pedirá "
        "permiso de administrador. En un SSD jamás se desfragmenta: se "
        "aplica TRIM. El proceso corre EN SEGUNDO PLANO, sin abrir "
        "ninguna ventana: aquí verás su progreso real."))
    contenedor_volumenes = QVBoxLayout()
    lay_v.addLayout(contenedor_volumenes)
    # Barra RGB propia de la optimización (v1.0.5): refleja la salida
    # del propio comando — % por pasadas cuando lo reporta; si una fase
    # no da % fiable, va animada con el texto de la fase.
    barra_opt = BarraProgreso()
    barra_opt.setVisible(False)
    lay_v.addWidget(barra_opt)
    lbl_opt = etiqueta(
        "El progreso aparecerá aquí mientras Windows optimiza.", suave=True)
    lay_v.addWidget(lbl_opt)
    botones_opt: list[QPushButton] = []
    layout.addWidget(tarjeta_vol)

    tarjeta_mapa, lay_m = tarjeta("Mapa de uso de disco")
    lay_m.addWidget(etiqueta(
        "Cuánto ocupa cada carpeta tuya (Descargas, Documentos, Escritorio, "
        "Imágenes, Vídeos, Música) más la carpeta temporal. El porcentaje de "
        "cada una es sobre el total medido de esas carpetas, no sobre todo "
        "el disco."))
    btn_mapa = QPushButton("Calcular mapa")
    barra_mapa = BarraProgreso()
    barra_mapa.setVisible(False)
    lbl_mapa = etiqueta("Todavía no se ha calculado el mapa.", suave=True)
    contenedor_mapa = QVBoxLayout()
    lay_m.addWidget(btn_mapa)
    lay_m.addWidget(barra_mapa)
    lay_m.addWidget(lbl_mapa)
    lay_m.addLayout(contenedor_mapa)
    layout.addWidget(tarjeta_mapa)
    layout.addStretch(1)

    def _frase_smart(info) -> tuple[str, str]:
        if info.sin_datos:
            return info.detalle, theme.TEXTO_SUAVE
        partes = [f"Salud {_TEXTOS_SALUD[info.salud]}"]
        if info.temperatura_c is not None:
            partes.append(f"{info.temperatura_c} °C")
        if info.horas_encendido is not None:
            partes.append(f"{info.horas_encendido} horas encendido")
        if info.desgaste_pct is not None:
            partes.append(f"desgaste {info.desgaste_pct} %")
        if info.errores:
            partes.append(f"{info.errores} errores registrados")
        color = {"bien": theme.VERDE, "regular": theme.AMBAR,
                 "mal": theme.ROJO}.get(info.salud, theme.TEXTO_SUAVE)
        frase = " · ".join(partes)
        if info.detalle:
            frase += f" — {info.detalle}"
        return frase, color

    def _al_progreso_opt(fase, porcentaje):
        # Llega desde el hilo trabajador vía señal: progreso REAL de la
        # salida de Optimize-Volume (% de la pasada en curso o, si la
        # fase no reporta % fiable, barra animada con el texto).
        if porcentaje is None:
            barra_opt.fijar_texto(fase)
        else:
            barra_opt.fijar(porcentaje, 100)
        lbl_opt.setText(fase)

    def _trabajo_opt(emisor, letra: str, es_ssd: bool):
        return svc.optimizar_volumen(
            letra, es_ssd,
            al_progreso=lambda fase, pct: emisor(fase, pct))

    def _al_terminar_optimizacion(resultado: ResultadoModulo):
        barra_opt.terminar()
        for boton in botones_opt:
            boton.setEnabled(True)
        lbl_opt.setText(resultado.mensaje)

    def _optimizar(volumen: dict, tipo: str):
        letra = volumen.get("letra", "")
        es_ssd = tipo == "SSD"
        accion = "TRIM" if es_ssd else "la desfragmentación"
        if not _confirmar(pagina, f"Optimizar {letra}:",
                          f"Windows aplicará {accion} en la unidad {letra}: "
                          "y pedirá permiso de administrador. El proceso "
                          "irá en segundo plano, sin abrir ventanas. "
                          "Puede tardar. ¿Seguir?"):
            return
        barra_opt.setVisible(True)
        barra_opt.fijar_texto(f"Optimizando la unidad {letra}: en segundo plano…")
        for boton in botones_opt:
            boton.setEnabled(False)
        lbl_opt.setText(f"Optimizando la unidad {letra}: con Windows, "
                        "en segundo plano…")
        gestor.lanzar(_trabajo_opt, _al_terminar_optimizacion,
                      letra, es_ssd, al_progreso=_al_progreso_opt)

    def _pintar(resultado: ResultadoModulo):
        datos = resultado.datos or {}
        datos_actuales.update(datos)
        _vaciar(contenedor_discos)
        for info in datos.get("discos", []):
            frase, color = _frase_smart(info)
            titulo = info.disco + (f" ({info.tipo})" if info.tipo else "")
            contenedor_discos.addWidget(
                fila_estado("disco", "parpadeo", titulo, frase, color))
        _vaciar(contenedor_volumenes)
        botones_opt.clear()
        fisicos = datos.get("fisicos", [])
        for volumen in datos.get("volumenes", []):
            letra = volumen.get("letra", "")
            tipo = svc.tipo_de_volumen(fisicos, volumen)
            texto = (f"{letra}: {volumen.get('etiqueta') or 'Sin etiqueta'} — "
                     f"{tamano_legible(volumen.get('libre', 0))} libres de "
                     f"{tamano_legible(volumen.get('tamano', 0))}")
            fila = QHBoxLayout()
            fila.addWidget(etiqueta(texto), 1)
            if tipo in ("SSD", "HDD"):
                btn = QPushButton("Optimizar con Windows")
                btn.setToolTip("TRIM" if tipo == "SSD" else "Desfragmentar")
                btn.clicked.connect(
                    lambda _=False, v=volumen, t=tipo: _optimizar(v, t))
                botones_opt.append(btn)
                fila.addWidget(btn)
            else:
                fila.addWidget(etiqueta(
                    "No se pudo determinar si es SSD o mecánico: no se toca.",
                    suave=True))
            contenedor = QWidget()
            contenedor.setLayout(fila)
            contenedor_volumenes.addWidget(contenedor)

    def _al_terminar_analisis(resultado: ResultadoModulo):
        barra.terminar()
        tarjeta_discos.fijar_activa(False)
        btn_analizar.setEnabled(True)
        lbl_estado.setText(resultado.mensaje)
        if resultado.ok:
            _pintar(resultado)

    def _analizar():
        if gestor.ocupado:
            return
        tarjeta_discos.fijar_activa(True)
        barra.setVisible(True)
        barra.fijar_texto("Leyendo la salud SMART…")
        btn_analizar.setEnabled(False)
        lbl_estado.setText("Leyendo la salud SMART de los discos…")
        gestor.lanzar(svc.salud_discos, _al_terminar_analisis)

    def _pintar_mapa(resultado: ResultadoModulo):
        _vaciar(contenedor_mapa)
        for fila_datos in resultado.datos or []:
            nombre = fila_datos.get("nombre", "")
            pct = int(fila_datos.get("pct", 0))
            fila = QHBoxLayout()
            fila.addWidget(etiqueta(
                f"{nombre} — {tamano_legible(fila_datos.get('bytes', 0))}"), 1)
            barra_fila = BarraProgreso()
            barra_fila.fijar(pct, 100)
            fila.addWidget(barra_fila, 1)
            contenedor = QWidget()
            contenedor.setLayout(fila)
            contenedor_mapa.addWidget(contenedor)

    def _al_terminar_mapa(resultado: ResultadoModulo):
        barra_mapa.terminar()
        btn_mapa.setEnabled(True)
        lbl_mapa.setText(resultado.mensaje)
        if resultado.ok:
            _pintar_mapa(resultado)

    def _calcular_mapa():
        if gestor.ocupado:
            return
        barra_mapa.setVisible(True)
        barra_mapa.fijar_texto("Midiendo las carpetas…")
        btn_mapa.setEnabled(False)
        lbl_mapa.setText("Midiendo el tamaño de cada carpeta… puede tardar "
                         "si hay muchos archivos.")
        gestor.lanzar(svc.mapa_disco, _al_terminar_mapa,
                      al_progreso=lambda i, n: barra_mapa.fijar(
                          i, n, "carpetas"))

    btn_analizar.clicked.connect(_analizar)
    btn_mapa.clicked.connect(_calcular_mapa)
    # Ganchos para las pruebas: la barra y la etiqueta de la
    # optimización quedan accesibles desde la página.
    pagina._barra_opt = barra_opt
    pagina._lbl_opt = lbl_opt
    pagina._botones_opt = botones_opt
    return pagina


# === LIMPIEZA =======================================================================
def crear_pagina_limpieza(ctx: ContextoModulo):
    pagina, layout = pagina_base(
        "Limpieza",
        "Tune-up seguro: primero el informe de qué se borraría y cuánto "
        "ocupa; el borrado lo confirmas tú. El arranque se desactiva de "
        "forma reversible y antes de cambios tienes punto de restauración "
        "y copia del registro. Sin limpiador de registro: no aporta nada "
        "y un error ahí puede impedir que Windows arranque.")
    gestor = _GestorTrabajos()

    tarjeta_inf, lay_i = tarjeta("Temporales y papelera")
    barra = BarraProgreso()
    barra.setVisible(False)
    lbl_estado = etiqueta("Pulsa «Analizar» para ver cuánto se puede liberar. "
                          "No se borra nada sin tu confirmación.", suave=True)
    btn_analizar = boton_principal("Analizar", "primario")
    contenedor_partidas = QVBoxLayout()
    lbl_total = etiqueta("")
    btn_limpiar = QPushButton("Limpiar temporales")
    btn_limpiar.setEnabled(False)
    btn_papelera = QPushButton("Vaciar papelera")
    btn_papelera.setEnabled(False)
    lay_i.addWidget(btn_analizar)
    lay_i.addWidget(barra)
    lay_i.addWidget(lbl_estado)
    lay_i.addLayout(contenedor_partidas)
    lay_i.addWidget(lbl_total)
    fila_botones = QHBoxLayout()
    fila_botones.addWidget(btn_limpiar)
    fila_botones.addWidget(btn_papelera)
    fila_botones.addStretch(1)
    lay_i.addLayout(fila_botones)
    layout.addWidget(tarjeta_inf)

    tarjeta_arr, lay_a = tarjeta("Programas que arrancan con Windows")
    lay_a.addWidget(etiqueta(
        "Desactivar es reversible: el acceso se guarda en Respaldos y "
        "puedes restaurarlo cuando quieras; nada se borra a la primera. "
        "En esta versión solo se desactivan así los de la carpeta de "
        "inicio; el resto se enseña con su origen. Cada programa enseña "
        "su impacto al arrancar: alto en rojo, medio en ámbar, bajo en "
        "verde."))
    btn_ver_arranque = QPushButton("Ver programas de arranque")
    contenedor_arranque = QVBoxLayout()
    btn_restaurar = QPushButton("Restaurar todo lo desactivado")
    lay_a.addWidget(btn_ver_arranque)
    lay_a.addLayout(contenedor_arranque)
    lay_a.addWidget(btn_restaurar)
    layout.addWidget(tarjeta_arr)

    tarjeta_res, lay_r = tarjeta("Respaldo antes de cambios")
    lbl_respaldo = etiqueta("", suave=True)
    btn_punto = QPushButton("Crear punto de restauración")
    btn_registro = QPushButton("Hacer copia del registro")
    lay_r.addWidget(btn_punto)
    lay_r.addWidget(btn_registro)
    lay_r.addWidget(lbl_respaldo)
    lay_r.addWidget(etiqueta(
        "La copia del registro es la alternativa segura al «limpiador de "
        "registro»: se guarda una copia, no se toca nada."))
    layout.addWidget(tarjeta_res)
    layout.addStretch(1)

    def _ocupado(activo: bool, texto: str = ""):
        tarjeta_inf.fijar_activa(activo)
        if activo:
            barra.setVisible(True)
            if texto:
                barra.fijar_texto(texto)
        else:
            barra.terminar()
        btn_analizar.setEnabled(not activo)
        if texto:
            lbl_estado.setText(texto)

    def _pintar_informe(resultado: ResultadoModulo):
        informe = resultado.datos
        _vaciar(contenedor_partidas)
        for partida in informe.partidas:
            contenedor_partidas.addWidget(fila_estado(
                "limpieza", "estatico", partida.nombre,
                f"{partida.ruta} — {tamano_legible(partida.tamano)}"))
        contenedor_partidas.addWidget(fila_estado(
            "carpeta", "estatico", "Papelera de reciclaje",
            tamano_legible(informe.papelera_bytes)))
        lbl_total.setText(f"Total que se puede liberar: "
                          f"{tamano_legible(informe.total_bytes)}")
        btn_limpiar.setEnabled(bool(informe.partidas))
        btn_papelera.setEnabled(informe.papelera_bytes > 0)

    def _al_terminar_analisis(resultado: ResultadoModulo):
        _ocupado(False)
        lbl_estado.setText(resultado.mensaje)
        if resultado.ok:
            _pintar_informe(resultado)

    def _analizar():
        if gestor.ocupado:
            return
        _ocupado(True, "Analizando temporales y papelera…")
        barra.fijar_texto("Analizando temporales…")
        gestor.lanzar(svc.analizar_limpieza, _al_terminar_analisis)

    def _al_terminar_limpieza(resultado: ResultadoModulo):
        _ocupado(False)
        lbl_estado.setText(resultado.mensaje)
        _registrar(ctx, "limpieza", resultado.mensaje if resultado.ok else
                   f"Limpieza de temporales fallida: {resultado.mensaje}")
        if resultado.ok:
            _analizar()  # refresca el informe con lo que quede

    def _limpiar():
        if not _confirmar(pagina, "Limpiar temporales",
                          "Se borrará el contenido de las carpetas "
                          "temporales. Lo que esté en uso se salta solo. "
                          "¿Seguir?"):
            return
        _ocupado(True, "Limpiando temporales…")
        gestor.lanzar(svc.limpiar_con_progreso, _al_terminar_limpieza,
                      al_progreso=lambda borradas, total:
                      barra.fijar(borradas, total, "partidas"))

    def _al_terminar_papelera(resultado: ResultadoModulo):
        _ocupado(False)
        lbl_estado.setText(resultado.mensaje)
        _registrar(ctx, "papelera", resultado.mensaje if resultado.ok else
                   f"Vaciado de papelera fallido: {resultado.mensaje}")
        if resultado.ok:
            _analizar()  # refresca el informe con lo que quede

    def _papelera():
        if not _confirmar(pagina, "Vaciar papelera",
                          "Se vaciará la papelera de reciclaje. Esto sí es "
                          "definitivo. ¿Seguir?"):
            return
        _ocupado(True, "Vaciando la papelera…")
        gestor.lanzar(svc.vaciar_papelera, _al_terminar_papelera)

    def _etiqueta_impacto(elemento: dict) -> QLabel:
        nivel = elemento.get("impacto", "bajo")
        texto_nivel, color = _IMPACTO.get(nivel, _IMPACTO["bajo"])
        lbl = QLabel(f"Impacto {texto_nivel.lower()}")
        lbl.setStyleSheet(f"color: {color}; font-weight: 600;")
        motivo = elemento.get("impacto_motivo", "")
        if motivo:
            lbl.setToolTip(motivo)
        return lbl

    def _pintar_arranque(resultado: ResultadoModulo):
        _vaciar(contenedor_arranque)
        for elemento in resultado.datos or []:
            nombre = elemento.get("nombre", "")
            origen = elemento.get("ubicacion", "")
            nivel = elemento.get("impacto", "bajo")
            texto_nivel, _color = _IMPACTO.get(nivel, _IMPACTO["bajo"])
            motivo = elemento.get("impacto_motivo", "")
            if elemento.get("reversible"):
                fila = QHBoxLayout()
                fila.addWidget(etiqueta(f"{nombre} — carpeta de inicio"), 1)
                fila.addWidget(_etiqueta_impacto(elemento))
                btn = QPushButton("Desactivar (reversible)")
                btn.clicked.connect(
                    lambda _=False, arch=elemento["archivo_inicio"]:
                    _desactivar(arch))
                fila.addWidget(btn)
                contenedor = QWidget()
                contenedor.setLayout(fila)
                contenedor_arranque.addWidget(contenedor)
            else:
                frase = (f"Origen: {origen or 'registro'} — Impacto "
                         f"{texto_nivel.lower()}")
                if motivo:
                    frase += f": {motivo}"
                frase += (" Se enseña; para desactivarlo usa el "
                          "Administrador de tareas.")
                contenedor_arranque.addWidget(fila_estado(
                    "inicio", "estatico", nombre, frase))

    def _al_terminar_arranque(resultado: ResultadoModulo):
        _ocupado(False)
        lbl_estado.setText(resultado.mensaje)
        if resultado.ok:
            _pintar_arranque(resultado)

    def _ver_arranque():
        if gestor.ocupado:
            return
        _ocupado(True, "Leyendo los programas de arranque…")
        gestor.lanzar(svc.elementos_arranque, _al_terminar_arranque)

    def _desactivar(nombre_archivo: str):
        def _fin(resultado: ResultadoModulo):
            _ocupado(False)
            lbl_estado.setText(resultado.mensaje)
            if resultado.ok:
                _registrar(ctx, "arranque",
                           f"Arranque desactivado (reversible): "
                           f"{nombre_archivo}")
                _ver_arranque()

        _ocupado(True, "Desactivando el arranque (reversible)…")
        gestor.lanzar(svc.desactivar_arranque, _fin, nombre_archivo)

    def _al_terminar_arranque_simple(resultado: ResultadoModulo):
        _ocupado(False)
        lbl_estado.setText(resultado.mensaje)
        if resultado.ok:
            _ver_arranque()

    def _restaurar():
        _ocupado(True, "Restaurando los arranques desactivados…")
        gestor.lanzar(svc.restaurar_arranque, _al_terminar_arranque_simple)

    def _al_terminar_respaldo(resultado: ResultadoModulo):
        barra.terminar()
        btn_punto.setEnabled(True)
        btn_registro.setEnabled(True)
        lbl_respaldo.setText(resultado.mensaje)

    def _punto():
        if gestor.ocupado:
            return
        barra.setVisible(True)
        barra.fijar_texto("Creando el punto de restauración…")
        btn_punto.setEnabled(False)
        lbl_respaldo.setText("Creando el punto de restauración… Windows "
                             "pedirá permiso de administrador.")
        gestor.lanzar(svc.crear_punto_restauracion, _al_terminar_respaldo)

    def _registro():
        if gestor.ocupado:
            return
        barra.setVisible(True)
        barra.fijar_texto("Guardando la copia del registro…")
        btn_registro.setEnabled(False)
        lbl_respaldo.setText("Guardando la copia del registro en Respaldos… "
                             "puede tardar un poco.")
        gestor.lanzar(svc.respaldo_registro, _al_terminar_respaldo)

    btn_analizar.clicked.connect(_analizar)
    btn_limpiar.clicked.connect(_limpiar)
    btn_papelera.clicked.connect(_papelera)
    btn_ver_arranque.clicked.connect(_ver_arranque)
    btn_restaurar.clicked.connect(_restaurar)
    btn_punto.clicked.connect(_punto)
    btn_registro.clicked.connect(_registro)
    return pagina
