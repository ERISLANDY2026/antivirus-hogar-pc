"""Páginas reales del Carril C: Drivers, Discos y Limpieza.

- Drivers: winapi.drivers_win + core.drivers_logic — cadena oficial del
  usuario (Windows Update/Catálogo → chip → marca de la PC), punto de
  restauración antes de instalar y solo drivers firmados.
- Discos: contracts.SmartInfo vía pySMART/smartctl con respaldo
  Get-PhysicalDisk; sin datos = «no se puede leer», nunca «sano».
  Optimización con Optimize-Volume (TRIM en SSD, defrag en HDD).
- Limpieza: informe antes de borrar, borrado tras confirmación, arranque
  reversible y respaldo (punto de restauración + copia del registro).
  SIN limpiador de registro.

Todo el trabajo pesado corre en un hilo (QThread) tras la barra de
progreso: la ventana nunca se congela y los procesos quedan ocultos.
"""
from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMessageBox, QProgressBar,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
from antivirus_hogar_pc.core import drivers_logic
from antivirus_hogar_pc.core.hashing import tamano_legible
from antivirus_hogar_pc.ui import theme
from antivirus_hogar_pc.ui.paginas_base import (etiqueta, fila_estado,
                                                pagina_base, tarjeta)

from . import servicios_sistema as svc

_TEXTOS_ESTADO = {
    "al_dia": ("Al día", theme.VERDE),
    "hay_uno_mas_nuevo": ("Hay uno más nuevo", theme.AMBAR),
    "sin_datos": ("Sin confirmar", theme.TEXTO_SUAVE),
}
_TEXTOS_SALUD = {"bien": "buena", "regular": "con aviso",
                 "mal": "mala", "desconocido": "sin leer"}


class _Trabajador(QThread):
    """Ejecuta una función de servicios fuera del hilo de la ventana."""
    terminado = Signal(object)

    def __init__(self, funcion, *args):
        super().__init__()
        self._funcion = funcion
        self._args = args

    def run(self):  # noqa: N802 (API de Qt)
        try:
            resultado = self._funcion(*self._args)
        except Exception as exc:  # los servicios ya no lanzan; red de seguridad
            resultado = ResultadoModulo(ok=False,
                                        mensaje=f"No se pudo completar: {exc}")
        self.terminado.emit(resultado)


class _GestorTrabajos:
    """Mantiene vivos los hilos hasta que terminan y entrega el resultado."""

    def __init__(self):
        self._activos: list[_Trabajador] = []

    def lanzar(self, funcion, al_terminar, *args) -> None:
        trabajador = _Trabajador(funcion, *args)

        def _fin(resultado):
            if trabajador in self._activos:
                self._activos.remove(trabajador)
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


def _barra_progreso() -> QProgressBar:
    barra = QProgressBar()
    barra.setRange(0, 0)  # indeterminada: trabajo en curso
    barra.setVisible(False)
    return barra


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
    barra = _barra_progreso()
    lbl_estado = etiqueta("Todavía no se ha escaneado. Pulsa «Escanear drivers».",
                          suave=True)
    tabla = QTableWidget(0, 5)
    tabla.setHorizontalHeaderLabels(
        ["Dispositivo", "Versión instalada", "Fecha", "Estado", "Acción"])
    tabla.horizontalHeader().setStretchLastSection(True)
    btn_escanear = QPushButton("Escanear drivers")
    lay_e.addWidget(btn_escanear)
    lay_e.addWidget(barra)
    lay_e.addWidget(lbl_estado)
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
        barra.setVisible(False)
        btn_escanear.setEnabled(True)
        lbl_estado.setText(resultado.mensaje)

    def _actualizar():
        if not _confirmar(
                pagina, "Actualizar drivers",
                "Se creará primero un punto de restauración. Después, "
                "Windows Update descargará e instalará los drivers nuevos "
                "que ofrece para esta PC (solo firmados). Windows pedirá "
                "permiso de administrador. ¿Seguir?"):
            return
        barra.setVisible(True)
        btn_escanear.setEnabled(False)
        lbl_estado.setText("Creando el punto de restauración e instalando "
                           "con Windows Update… puede tardar unos minutos.")
        gestor.lanzar(svc.actualizar_drivers, _al_terminar_actualizacion)

    def _pintar_tabla(estados):
        tabla.setRowCount(len(estados))
        for i, est in enumerate(estados):
            d = est.driver
            nombre = d.dispositivo
            if not d.firmado:
                nombre += "  (sin firma)"
            tabla.setItem(i, 0, QTableWidgetItem(nombre))
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
        tabla.resizeColumnsToContents()

    def _al_terminar_escaneo(resultado: ResultadoModulo):
        barra.setVisible(False)
        btn_escanear.setEnabled(True)
        lbl_estado.setText(resultado.mensaje)
        if resultado.ok and isinstance(resultado.datos, dict):
            estado_actual.update(resultado.datos)
            _pintar_tabla(resultado.datos["estados"])

    def _escanear():
        if gestor.ocupado:
            return
        barra.setVisible(True)
        btn_escanear.setEnabled(False)
        lbl_estado.setText("Leyendo los drivers instalados y consultando "
                           "Windows Update… puede tardar unos minutos.")
        gestor.lanzar(svc.escanear_drivers, _al_terminar_escaneo)

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
    barra = _barra_progreso()
    lbl_estado = etiqueta("Todavía no se ha analizado ningún disco.", suave=True)
    btn_analizar = QPushButton("Analizar discos")
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
        "aplica TRIM."))
    contenedor_volumenes = QVBoxLayout()
    lay_v.addLayout(contenedor_volumenes)
    layout.addWidget(tarjeta_vol)
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

    def _al_terminar_optimizacion(resultado: ResultadoModulo):
        barra.setVisible(False)
        btn_analizar.setEnabled(True)
        lbl_estado.setText(resultado.mensaje)

    def _optimizar(volumen: dict, tipo: str):
        letra = volumen.get("letra", "")
        es_ssd = tipo == "SSD"
        accion = "TRIM" if es_ssd else "la desfragmentación"
        if not _confirmar(pagina, f"Optimizar {letra}:",
                          f"Windows aplicará {accion} en la unidad {letra}: "
                          "y pedirá permiso de administrador. Puede tardar. "
                          "¿Seguir?"):
            return
        barra.setVisible(True)
        btn_analizar.setEnabled(False)
        lbl_estado.setText(f"Optimizando la unidad {letra}: con Windows…")
        gestor.lanzar(svc.optimizar_volumen, _al_terminar_optimizacion,
                      letra, es_ssd)

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
                fila.addWidget(btn)
            else:
                fila.addWidget(etiqueta(
                    "No se pudo determinar si es SSD o mecánico: no se toca.",
                    suave=True))
            contenedor = QWidget()
            contenedor.setLayout(fila)
            contenedor_volumenes.addWidget(contenedor)

    def _al_terminar_analisis(resultado: ResultadoModulo):
        barra.setVisible(False)
        btn_analizar.setEnabled(True)
        lbl_estado.setText(resultado.mensaje)
        if resultado.ok:
            _pintar(resultado)

    def _analizar():
        if gestor.ocupado:
            return
        barra.setVisible(True)
        btn_analizar.setEnabled(False)
        lbl_estado.setText("Leyendo la salud SMART de los discos…")
        gestor.lanzar(svc.salud_discos, _al_terminar_analisis)

    btn_analizar.clicked.connect(_analizar)
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
    barra = _barra_progreso()
    lbl_estado = etiqueta("Pulsa «Analizar» para ver cuánto se puede liberar. "
                          "No se borra nada sin tu confirmación.", suave=True)
    btn_analizar = QPushButton("Analizar")
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
        "inicio; el resto se enseña con su origen."))
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
        barra.setVisible(activo)
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
        gestor.lanzar(svc.analizar_limpieza, _al_terminar_analisis)

    def _al_terminar_limpieza(resultado: ResultadoModulo):
        _ocupado(False)
        lbl_estado.setText(resultado.mensaje)
        if resultado.ok:
            _analizar()  # refresca el informe con lo que quede

    def _limpiar():
        if not _confirmar(pagina, "Limpiar temporales",
                          "Se borrará el contenido de las carpetas "
                          "temporales. Lo que esté en uso se salta solo. "
                          "¿Seguir?"):
            return
        _ocupado(True, "Limpiando temporales…")
        gestor.lanzar(svc.limpiar_temporales, _al_terminar_limpieza)

    def _papelera():
        if not _confirmar(pagina, "Vaciar papelera",
                          "Se vaciará la papelera de reciclaje. Esto sí es "
                          "definitivo. ¿Seguir?"):
            return
        _ocupado(True, "Vaciando la papelera…")
        gestor.lanzar(svc.vaciar_papelera, _al_terminar_limpieza)

    def _pintar_arranque(resultado: ResultadoModulo):
        _vaciar(contenedor_arranque)
        for elemento in resultado.datos or []:
            nombre = elemento.get("nombre", "")
            origen = elemento.get("ubicacion", "")
            if elemento.get("reversible"):
                fila = QHBoxLayout()
                fila.addWidget(etiqueta(f"{nombre} — carpeta de inicio"), 1)
                btn = QPushButton("Desactivar (reversible)")
                btn.clicked.connect(
                    lambda _=False, arch=elemento["archivo_inicio"]:
                    _desactivar(arch))
                fila.addWidget(btn)
                contenedor = QWidget()
                contenedor.setLayout(fila)
                contenedor_arranque.addWidget(contenedor)
            else:
                contenedor_arranque.addWidget(fila_estado(
                    "inicio", "estatico", nombre,
                    f"Origen: {origen or 'registro'} — se enseña; para "
                    "desactivarlo usa el Administrador de tareas."))

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
        _ocupado(True, "Desactivando el arranque (reversible)…")
        gestor.lanzar(svc.desactivar_arranque, _al_terminar_arranque_simple,
                      nombre_archivo)

    def _al_terminar_arranque_simple(resultado: ResultadoModulo):
        _ocupado(False)
        lbl_estado.setText(resultado.mensaje)
        if resultado.ok:
            _ver_arranque()

    def _restaurar():
        _ocupado(True, "Restaurando los arranques desactivados…")
        gestor.lanzar(svc.restaurar_arranque, _al_terminar_arranque_simple)

    def _al_terminar_respaldo(resultado: ResultadoModulo):
        barra.setVisible(False)
        btn_punto.setEnabled(True)
        btn_registro.setEnabled(True)
        lbl_respaldo.setText(resultado.mensaje)

    def _punto():
        if gestor.ocupado:
            return
        barra.setVisible(True)
        btn_punto.setEnabled(False)
        lbl_respaldo.setText("Creando el punto de restauración… Windows "
                             "pedirá permiso de administrador.")
        gestor.lanzar(svc.crear_punto_restauracion, _al_terminar_respaldo)

    def _registro():
        if gestor.ocupado:
            return
        barra.setVisible(True)
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
