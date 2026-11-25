"""Páginas REALES del Carril B: Escanear, Protección e Informes.

- Escanear: core.scanner en hilo (progreso y cancelación), decisiones del
  usuario por hallazgo (cuarentena / eliminar / Defender / ignorar) y
  gestión de la cuarentena. La app nunca actúa sola.
- Protección: bloqueador hosts real (core.seguridad + winapi), revisión de
  instalaciones bajo demanda y escaneo semanal con el Programador de tareas.
- Informes: privacidad/persistencia desde winapi.system_info, exportable.
"""
import os
import string
import sys

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from antivirus_hogar_pc import config
from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
from antivirus_hogar_pc.core.i18n import t
from antivirus_hogar_pc.core import seguridad
from antivirus_hogar_pc.core.hashing import tamano_legible
from antivirus_hogar_pc.core.scanner import Hallazgo, ResultadoEscaneo, analizar_archivo, escanear
from antivirus_hogar_pc.core.textos_error import mensaje_para_usuario
from antivirus_hogar_pc.core.threats_update import descargar_firmas_recientes, escribir_archivo_firmas
from antivirus_hogar_pc.ui import theme
from antivirus_hogar_pc.ui.paginas_base import boton_principal, etiqueta, fila_estado, pagina_base, tarjeta
from antivirus_hogar_pc.ui.services import seguro
from antivirus_hogar_pc.ui.widgets_v102 import BarraProgreso
from antivirus_hogar_pc.winapi import defender, tasks, tuneup_win


# ---------------------------------------------------------------------------
# Hilos de trabajo
# ---------------------------------------------------------------------------

class _Trabajador(QThread):
    """Ejecuta una función en segundo plano y entrega su resultado."""

    terminado = Signal(object)

    def __init__(self, funcion, padre=None):
        super().__init__(padre)
        self._funcion = funcion

    def run(self):
        try:
            resultado = self._funcion()
        except Exception as exc:  # nunca dejar morir la app por un hilo
            resultado = ResultadoModulo(False, f"Error inesperado: {exc}",
                                        detalle_tecnico=repr(exc))
        self.terminado.emit(resultado)


class _TrabajadorEscaneo(QThread):
    progreso = Signal(str, int, int)
    terminado = Signal(object)

    def __init__(self, servicios, raices, forzar_rehash, padre=None):
        super().__init__(padre)
        self._servicios = servicios
        self._raices = raices
        self._forzar = forzar_rehash
        self._cancelado = False

    def cancelar(self):
        self._cancelado = True

    def run(self):
        # v1.0.3: si escanear() lanza, «terminado» llega IGUAL con el
        # error dentro del resultado; antes la excepción mataba el hilo
        # en silencio y la barra quedaba en «Escaneando…» para siempre.
        try:
            resultado = escanear(
                self._raices,
                self._servicios.base_firmas,
                self._servicios.cache,
                solo_ejecutables=True,
                forzar_rehash_en=self._forzar,
                progreso=lambda ruta, n, total: self.progreso.emit(ruta, n, total or 0),
                debe_cancelar=lambda: self._cancelado,
            )
        except Exception as exc:
            # v1.0.4: en pantalla, frase clara en español; el detalle
            # técnico crudo (p. ej. el de sqlite) va solo al registro.
            try:
                self._servicios.registrar_actividad(
                    "escaneo", f"Error técnico del escaneo: {exc!r}")
            except Exception:
                pass
            resultado = ResultadoEscaneo(
                errores=1, error=mensaje_para_usuario(exc))
        try:
            self._servicios.registrar_escaneo(resultado)
        except Exception:
            pass  # el registro es un extra; el resultado ya viaja a la UI
        self.terminado.emit(resultado)


def _soltar_trabajadores(pagina: QWidget) -> None:
    """Despadrea los hilos registrados de la página (v1.0.6)."""
    for t in list(getattr(pagina, "_trabajadores", []) or []):
        try:
            t.setParent(None)
        except RuntimeError:
            pass


def _guardar_ref(pagina: QWidget, trabajador: QThread) -> None:
    """Evita que el recolector se lleve el hilo mientras trabaja.

    v1.0.6: además, si la página se destruye con hilos en curso,
    los hilos se DESPADREAN y se autoborran al terminar — un
    QThread destruido mientras corre aborta el proceso entero
    (pasó en la suite al cerrarse una ventana con trabajo vivo).
    """
    previos = []
    for t in getattr(pagina, "_trabajadores", []):
        try:
            if t.isRunning():
                previos.append(t)
        except RuntimeError:
            pass  # hilo ya destruido: fuera de la lista
    previos.append(trabajador)
    pagina._trabajadores = previos  # type: ignore[attr-defined]
    trabajador.finished.connect(trabajador.deleteLater)
    if not getattr(pagina, "_soltar_al_destruir", False):
        pagina._soltar_al_destruir = True  # type: ignore[attr-defined]
        pagina.destroyed.connect(
            lambda _=None, p=pagina: _soltar_trabajadores(p))


def _confirmar(padre: QWidget, titulo: str, texto: str) -> bool:
    return QMessageBox.question(padre, titulo, texto) == QMessageBox.StandardButton.Yes


def _fila_hallazgo(hallazgo: Hallazgo, ctx: ContextoModulo, al_resolver) -> QWidget:
    """Fila de hallazgo con las decisiones del usuario."""
    contenedor = QWidget()
    layout = QVBoxLayout(contenedor)
    layout.setContentsMargins(0, 4, 0, 4)
    layout.addWidget(fila_estado(
        "alerta", "estatico", hallazgo.etiqueta,
        f"{hallazgo.ruta} · {tamano_legible(hallazgo.tamano)}", theme.ROJO))
    fila_botones = QHBoxLayout()

    def a_cuarentena():
        r = seguro(ctx.servicios.cuarentena.poner_en_cuarentena,
                   hallazgo.ruta, hallazgo.sha256, hallazgo.md5, hallazgo.etiqueta)
        if r.ok:
            QMessageBox.information(contenedor, "Cuarentena",
                                    "El archivo se movió a la cuarentena. "
                                    "Puedes restaurarlo cuando quieras.")
            al_resolver()
        else:
            QMessageBox.warning(contenedor, "Cuarentena", r.mensaje)

    def a_eliminar():
        if not _confirmar(contenedor, "Eliminar archivo",
                          f"Se eliminará para siempre:\n{hallazgo.ruta}\n\n¿Seguro?"):
            return
        try:
            try:
                os.chmod(hallazgo.ruta, 0o600)
            except OSError:
                pass
            os.remove(hallazgo.ruta)
            al_resolver()
        except OSError as exc:
            QMessageBox.warning(contenedor, "Eliminar", f"No se pudo eliminar: {exc}")

    def a_defender():
        boton.setEnabled(False)

        def trabajo():
            codigo, salida = defender.analizar_archivo_defender(hallazgo.ruta)
            if codigo == 0:
                msg = "Defender no detecta amenaza en este archivo."
            elif codigo == 2:
                msg = "Defender TAMBIÉN detecta amenaza en este archivo."
            else:
                msg = f"Defender terminó con código {codigo}."
            return ResultadoModulo(True, msg, detalle_tecnico=salida)

        trabajador = _Trabajador(trabajo, contenedor)
        trabajador.terminado.connect(
            lambda res: (boton.setEnabled(True),
                         QMessageBox.information(contenedor, "Microsoft Defender", res.mensaje)))
        _guardar_ref(contenedor, trabajador)
        trabajador.start()

    boton = QPushButton(t("Escanear con Defender"))
    boton.clicked.connect(a_defender)
    b_cuarentena = QPushButton(t("Poner en cuarentena"))
    b_cuarentena.clicked.connect(a_cuarentena)
    b_eliminar = QPushButton(t("Eliminar"))
    b_eliminar.clicked.connect(a_eliminar)
    b_ignorar = QPushButton(t("Ignorar"))
    b_ignorar.clicked.connect(al_resolver)
    for b in (b_cuarentena, b_eliminar, boton, b_ignorar):
        fila_botones.addWidget(b)
    fila_botones.addStretch(1)
    layout.addLayout(fila_botones)
    return contenedor


# ---------------------------------------------------------------------------
# Página: Escanear
# ---------------------------------------------------------------------------

def _raices_escaneo_completo() -> list[str]:
    if sys.platform.startswith("win"):
        raices = []
        for letra in string.ascii_uppercase:
            raiz = f"{letra}:\\"
            if os.path.isdir(raiz):
                raices.append(raiz)
        return raices
    return [os.path.expanduser("~")]


def crear_pagina_escaner(ctx: ContextoModulo):
    servicios = ctx.servicios
    pagina, layout = pagina_base(
        t("Escanear"), t("Escaneo por huellas contra la base de malware conocido. Ante un hallazgo decides tú: la app nunca actúa sola."))

    # --- tarjeta de escaneo -------------------------------------------------
    tarjeta_escaneo, lay = tarjeta(t("Escaneo"))
    barra = BarraProgreso()
    lay.addWidget(barra)
    lbl_estado = etiqueta("Listo. La base local tiene "
                          f"{servicios.base_firmas.total} huellas conocidas.")
    lay.addWidget(lbl_estado)
    lbl_actual = etiqueta("", suave=True)
    lay.addWidget(lbl_actual)

    fila1 = QHBoxLayout()
    b_rapido = boton_principal(t("Escaneo rápido"), "primario")
    b_completo = QPushButton(t("Escaneo completo"))
    b_carpeta = QPushButton(t("Elegir carpeta…"))
    b_cancelar = QPushButton(t("Cancelar"))
    b_cancelar.setEnabled(False)
    for b in (b_rapido, b_completo, b_carpeta, b_cancelar):
        fila1.addWidget(b)
    fila1.addStretch(1)
    lay.addLayout(fila1)
    fila2 = QHBoxLayout()
    b_defender = QPushButton(t("Escanear con Defender"))
    b_archivo = QPushButton(t("Analizar ESTE archivo"))
    fila2.addWidget(b_defender)
    fila2.addWidget(b_archivo)
    fila2.addStretch(1)
    lay.addLayout(fila2)
    layout.addWidget(tarjeta_escaneo)

    # --- tarjeta de hallazgos -------------------------------------------------
    tarjeta_hallazgos, lay_h = tarjeta(t("Hallazgos"))
    lbl_sin = etiqueta(t("Sin hallazgos todavía."))
    lay_h.addWidget(lbl_sin)
    layout.addWidget(tarjeta_hallazgos)

    # --- tarjeta de cuarentena ------------------------------------------------
    tarjeta_cuarentena, lay_c = tarjeta(t("Cuarentena"))
    lbl_cuarentena = etiqueta("")
    lay_c.addWidget(lbl_cuarentena)
    contenedor_cuarentena = QVBoxLayout()
    lay_c.addLayout(contenedor_cuarentena)
    b_refrescar_c = QPushButton(t("Actualizar lista"))
    lay_c.addWidget(b_refrescar_c)
    layout.addWidget(tarjeta_cuarentena)
    layout.addStretch(1)

    estado = {"trabajador": None, "ultimo_revisados": 0, "ultimo_total": 0}

    def _limpiar_layout(lay_out: QVBoxLayout):
        while lay_out.count():
            item = lay_out.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _mostrar_hallazgos(hallazgos: list[Hallazgo]):
        _limpiar_layout(lay_h)
        if not hallazgos:
            lay_h.addWidget(etiqueta("Sin hallazgos: nada coincide con la base."))
            return
        lay_h.addWidget(etiqueta(
            f"{len(hallazgos)} hallazgo(s). Tú decides qué hacer con cada uno:"))
        for h in hallazgos:
            holder: dict = {}

            def al_resolver(holder=holder):
                fila = holder.get("fila")
                if fila is not None:
                    fila.setParent(None)
                    fila.deleteLater()
                refrescar_cuarentena()

            fila = _fila_hallazgo(h, ctx, al_resolver)
            holder["fila"] = fila
            lay_h.addWidget(fila)

    def refrescar_cuarentena():
        _limpiar_layout(contenedor_cuarentena)
        entradas = servicios.cuarentena.listar()
        lbl_cuarentena.setText(
            f"{len(entradas)} archivo(s) en cuarentena." if entradas
            else "La cuarentena está vacía.")
        for entrada in entradas:
            fila = QHBoxLayout()
            fila.addWidget(etiqueta(
                f"{os.path.basename(entrada.ruta_original)} — {entrada.etiqueta}"))
            b_rest = QPushButton(t("Restaurar"))

            def restaurar(e=entrada):
                r = seguro(servicios.cuarentena.restaurar, e.id)
                if r.ok:
                    QMessageBox.information(pagina, "Cuarentena",
                                            f"Archivo restaurado en:\n{e.ruta_original}")
                else:
                    QMessageBox.warning(pagina, "Cuarentena", r.mensaje)
                refrescar_cuarentena()

            b_borrar = QPushButton(t("Eliminar definitivo"))

            def borrar(e=entrada):
                if _confirmar(pagina, "Eliminar definitivo",
                              "Se borrará para siempre el archivo en cuarentena "
                              f"«{os.path.basename(e.ruta_original)}». ¿Seguro?"):
                    r = seguro(servicios.cuarentena.eliminar_definitivo, e.id)
                    if not r.ok:
                        QMessageBox.warning(pagina, "Cuarentena", r.mensaje)
                    refrescar_cuarentena()

            b_rest.clicked.connect(restaurar)
            b_borrar.clicked.connect(borrar)
            fila.addWidget(b_rest)
            fila.addWidget(b_borrar)
            contenedor = QWidget()
            contenedor.setLayout(fila)
            contenedor_cuarentena.addWidget(contenedor)

    b_refrescar_c.clicked.connect(refrescar_cuarentena)
    refrescar_cuarentena()

    def _al_progreso(ruta: str, revisados: int, total: int):
        lbl_actual.setText(ruta)
        estado["ultimo_revisados"] = revisados
        estado["ultimo_total"] = total
        if total > 0:
            barra.fijar(revisados, total, "archivos")
        else:
            barra.fijar_texto("Contando archivos…")

    def _al_terminar(resultado):
        b_cancelar.setEnabled(False)
        tarjeta_escaneo.fijar_activa(False)
        for b in (b_rapido, b_completo, b_carpeta, b_defender, b_archivo):
            b.setEnabled(True)
        if getattr(resultado, "error", ""):
            barra.fijar_texto("El escaneo falló")
            lbl_actual.setText("")
            lbl_estado.setText(
                f"⚠ El escaneo no se pudo completar: {resultado.error}")
            return
        if resultado.cancelado:
            if estado["ultimo_total"] > 0:
                barra.fijar(resultado.archivos_revisados,
                            estado["ultimo_total"], "archivos")
            else:
                barra.fijar_texto(
                    f"Cancelado: {resultado.archivos_revisados} archivos revisados")
        else:
            barra.terminar()
        lbl_actual.setText("")
        texto = (f"Escaneo terminado: {resultado.archivos_revisados} archivos revisados "
                 f"({resultado.archivos_desde_cache} desde la caché), "
                 f"{resultado.errores} sin poder leer.")
        if resultado.cancelado:
            texto = "Escaneo cancelado. " + texto
        lbl_estado.setText(texto)
        _mostrar_hallazgos(resultado.hallazgos)
        refrescar_cuarentena()

    def _lanzar_escaneo(raices: list[str], forzar: list[str]):
        if not raices:
            QMessageBox.information(pagina, "Escanear",
                                    "No se encontró ninguna carpeta para escanear.")
            return
        trabajador = _TrabajadorEscaneo(servicios, raices, forzar, pagina)
        trabajador.progreso.connect(_al_progreso)
        trabajador.terminado.connect(_al_terminar)
        estado["trabajador"] = trabajador
        _guardar_ref(pagina, trabajador)
        for b in (b_rapido, b_completo, b_carpeta, b_defender, b_archivo):
            b.setEnabled(False)
        b_cancelar.setEnabled(True)
        estado["ultimo_revisados"] = 0
        estado["ultimo_total"] = 0
        tarjeta_escaneo.fijar_activa(True)
        barra.fijar_texto("Escaneando…")
        lbl_estado.setText("Escaneando…")
        trabajador.start()

    def escaneo_rapido():
        descargas = servicios.carpeta_descargas()
        _lanzar_escaneo(servicios.carpetas_riesgo(),
                        [descargas] if descargas else [])

    def escaneo_completo():
        _lanzar_escaneo(_raices_escaneo_completo(), [])

    def elegir_carpeta():
        carpeta = QFileDialog.getExistingDirectory(pagina, "Carpeta a escanear")
        if carpeta:
            _lanzar_escaneo([carpeta], [carpeta])

    def cancelar():
        if estado["trabajador"] is not None:
            estado["trabajador"].cancelar()
            lbl_estado.setText("Cancelando…")

    def escanear_defender():
        def trabajo():
            r = seguro(defender.escanear_con_defender, "rapido")
            return ResultadoModulo(r.ok, r.mensaje or r.datos or "Escaneo de Defender lanzado.")
        trabajador = _Trabajador(trabajo, pagina)
        trabajador.terminado.connect(
            lambda res: QMessageBox.information(pagina, "Microsoft Defender", res.mensaje))
        _guardar_ref(pagina, trabajador)
        trabajador.start()

    def analizar_un_archivo():
        ruta, _filtro = QFileDialog.getOpenFileName(pagina, "Archivo a analizar")
        if not ruta:
            return
        try:
            hallazgo = analizar_archivo(ruta, servicios.base_firmas)
        except OSError as exc:
            QMessageBox.warning(pagina, "Analizar archivo", f"No se pudo leer: {exc}")
            return
        if hallazgo is None:
            QMessageBox.information(
                pagina, "Analizar archivo",
                "Este archivo NO coincide con la base de malware conocido.\n\n"
                "Ojo: la base local solo conoce malware ya catalogado; "
                "para un análisis completo usa «Escanear con Defender».")
            _limpiar_layout(lay_h)
            lay_h.addWidget(etiqueta("Sin hallazgos en el archivo analizado."))
        else:
            _mostrar_hallazgos([hallazgo])

    b_rapido.clicked.connect(escaneo_rapido)
    b_completo.clicked.connect(escaneo_completo)
    b_carpeta.clicked.connect(elegir_carpeta)
    b_cancelar.clicked.connect(cancelar)
    b_defender.clicked.connect(escanear_defender)
    b_archivo.clicked.connect(analizar_un_archivo)
    # Gancho para la bandeja del sistema (v1.0.7): su «Escaneo
    # rápido» llama a la MISMA función que el botón de la página.
    pagina.escaneo_rapido = escaneo_rapido
    return pagina


# ---------------------------------------------------------------------------
# Página: Protección
# ---------------------------------------------------------------------------

def crear_pagina_proteccion(ctx: ContextoModulo):
    servicios = ctx.servicios
    pagina, layout = pagina_base(
        t("Protección"), t("Bloqueador de dominios peligrosos y de anuncios, protección al instalar y escaneo semanal."))

    # --- bloqueador hosts -----------------------------------------------------
    tarjeta_hosts, lay = tarjeta(t("Bloqueador (archivo hosts)"))
    lbl_hosts = etiqueta(t("Consultando el estado del bloqueo…"))
    lay.addWidget(lbl_hosts)
    lay.addWidget(etiqueta(t(
        "Bloquea por dominio, no por dirección completa: es el límite de esta vía, sin certificado local. Antes de tocar el archivo hosts se guarda una copia de seguridad."), suave=True))
    fila_h1 = QHBoxLayout()
    b_activar = QPushButton(t("Activar bloqueo"))
    b_activar.setObjectName("primario")
    b_fusionada = QPushButton(t("Usar base fusionada (100.776)"))
    b_pausar = QPushButton(t("Pausar"))
    b_reanudar = QPushButton(t("Reanudar"))
    for b in (b_activar, b_fusionada, b_pausar, b_reanudar):
        fila_h1.addWidget(b)
    fila_h1.addStretch(1)
    lay.addLayout(fila_h1)
    fila_h2 = QHBoxLayout()
    b_quitar = QPushButton(t("Quitar el bloqueo"))
    b_restaurar = QPushButton(t("Restaurar copia del hosts"))
    b_dns = QPushButton(t("Modo reforzado (DNS)"))
    for b in (b_quitar, b_restaurar, b_dns):
        fila_h2.addWidget(b)
    fila_h2.addStretch(1)
    lay.addLayout(fila_h2)
    layout.addWidget(tarjeta_hosts)

    def refrescar_hosts():
        r = seguro(seguridad.estado_hosts)
        if not r.ok:
            lbl_hosts.setText(f"Bloqueador: {r.mensaje}")
            return
        estado = r.datos
        if estado.activo:
            texto = (f"Bloqueo ACTIVO: {estado.dominios_bloqueados} dominios "
                     f"bloqueados (base {estado.base_usada}).")
            if seguridad.esta_pausado():
                texto += " (en pausa)"
        else:
            texto = "Bloqueo desactivado."
        if estado.ruta_respaldo:
            texto += f"\nÚltima copia del hosts: {os.path.basename(estado.ruta_respaldo)}"
        lbl_hosts.setText(texto)

    def operacion_hosts(funcion, *args):
        trabajador = _Trabajador(lambda: funcion(*args), pagina)
        trabajador.terminado.connect(
            lambda res: (QMessageBox.information(pagina, "Bloqueador", res.mensaje)
                         if res.mensaje else None, refrescar_hosts()))
        _guardar_ref(pagina, trabajador)
        trabajador.start()

    def activar_fusionada():
        if _confirmar(pagina, "Base fusionada",
                      "La base fusionada bloquea 100.776 dominios, pero Windows "
                      "se puede volver lento con un archivo hosts tan grande.\n\n"
                      "La recomendada es la base semilla (19.563).\n\n¿Usar la fusionada?"):
            operacion_hosts(seguridad.activar_hosts, "fusionada")

    def abrir_dns():
        seguro(tuneup_win.abrir_configuracion_dns)
        QMessageBox.information(
            pagina, "Modo reforzado (DNS)",
            "Se abrió la configuración de red de Windows. Ahí puedes poner un "
            "DNS filtrante (por ejemplo Quad9, 9.9.9.9, contra malware; o "
            "AdGuard DNS, 94.140.14.14, contra anuncios y rastreo). "
            "La app no cambia tu DNS por su cuenta.")

    b_activar.clicked.connect(lambda: operacion_hosts(seguridad.activar_hosts, "semilla"))
    b_fusionada.clicked.connect(activar_fusionada)
    b_pausar.clicked.connect(lambda: operacion_hosts(seguridad.pausar_hosts))
    b_reanudar.clicked.connect(lambda: operacion_hosts(seguridad.reanudar_hosts))
    b_quitar.clicked.connect(lambda: operacion_hosts(seguridad.quitar_hosts))
    b_restaurar.clicked.connect(lambda: operacion_hosts(seguridad.restaurar_respaldo_hosts))
    b_dns.clicked.connect(abrir_dns)
    refrescar_hosts()

    # --- base de amenazas -------------------------------------------------------
    tarjeta_base, lay_b = tarjeta(t("Base de amenazas"))
    lbl_base = etiqueta(f"Huellas conocidas en la base local: {servicios.base_firmas.total}.")
    lay_b.addWidget(lbl_base)
    lay_b.addWidget(etiqueta(
        "La actualización consulta VARIAS fuentes gratuitas independientes "
        "y fusiona lo que trae cada una: malicious-hash (huellas, sin "
        "clave), URLhaus, Phishing.Database, OpenPhish y CERT.PL; "
        "abuse.ch suma huellas si tienes su Auth-Key en Ajustes, pero ya "
        "no hace falta. Si una fuente falla, las demás siguen; la base "
        "local incluida queda siempre como respaldo sin conexión.", suave=True))
    lbl_fuentes = etiqueta("", suave=True)
    lay_b.addWidget(lbl_fuentes)
    barra_base = BarraProgreso()
    barra_base.setVisible(False)
    lay_b.addWidget(barra_base)
    b_actualizar_base = boton_principal(t("Actualizar firmas (varias fuentes)"))
    lay_b.addWidget(b_actualizar_base)

    def actualizar_base():
        b_actualizar_base.setEnabled(False)
        tarjeta_base.fijar_activa(True)
        barra_base.setVisible(True)
        barra_base.fijar_texto(t("Consultando las fuentes…"))
        lbl_fuentes.setText(t("Consultando las fuentes… puede tardar un poco."))

        def trabajo():
            from antivirus_hogar_pc.core.threats_update import (
                actualizar_firmas_multifuente, escribir_archivo_dominios)
            resultado = actualizar_firmas_multifuente(
                servicios.ajustes.auth_key_abusech)
            resumen = resultado.resumen()
            if not resultado.ok:
                return ResultadoModulo(
                    False,
                    "Ninguna fuente pudo aportar firmas nuevas. " + resumen +
                    ". La base local incluida en la app sigue protegiendo "
                    "como respaldo sin conexión.",
                    datos={"resumen": resumen})
            n_hashes = 0
            if resultado.hashes:
                ruta_extra = os.path.join(config.carpeta_datos(), "firmas_extra.txt")
                n_hashes = escribir_archivo_firmas(ruta_extra, resultado.hashes)
                servicios.base_firmas.cargar_archivo(ruta_extra)
            n_dominios = 0
            if resultado.dominios:
                ruta_dom = os.path.join(config.carpeta_datos(), "dominios_extra.txt")
                n_dominios = escribir_archivo_dominios(ruta_dom, resultado.dominios)
            return ResultadoModulo(
                True,
                f"Base actualizada: {n_hashes} huellas y {n_dominios} "
                f"dominios nuevos fusionados. {resumen}.",
                datos={"resumen": resumen})

        def _al_terminar_base(res: ResultadoModulo):
            b_actualizar_base.setEnabled(True)
            tarjeta_base.fijar_activa(False)
            barra_base.terminar()
            datos = res.datos if isinstance(res.datos, dict) else {}
            lbl_fuentes.setText(datos.get("resumen", res.mensaje))
            lbl_base.setText(
                f"Huellas conocidas en la base local: {servicios.base_firmas.total}.")
            QMessageBox.information(pagina, "Base de amenazas", res.mensaje)

        trabajador = _Trabajador(trabajo, pagina)
        trabajador.terminado.connect(_al_terminar_base)
        _guardar_ref(pagina, trabajador)
        trabajador.start()

    b_actualizar_base.clicked.connect(actualizar_base)
    layout.addWidget(tarjeta_base)

    # --- protección al instalar --------------------------------------------------
    tarjeta_instalar, lay_i = tarjeta(t("Protección al instalar (modo usuario)"))
    lay_i.addWidget(etiqueta(t(
        "Vigila Descargas, Escritorio y la carpeta temporal, y los programas recién instalados, y los contrasta con la base. No es tiempo real de kernel: la protección en tiempo real la hace Defender.")))
    b_revisar = QPushButton(t("Revisar ahora"))
    lay_i.addWidget(b_revisar)
    lbl_revision = etiqueta("")
    lay_i.addWidget(lbl_revision)
    contenedor_revision = QVBoxLayout()
    lay_i.addLayout(contenedor_revision)
    layout.addWidget(tarjeta_instalar)

    def al_revisar(res: ResultadoModulo):
        lbl_revision.setText(res.mensaje)
        while contenedor_revision.count():
            item = contenedor_revision.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if not res.ok or not res.datos:
            return
        datos = res.datos
        for p in datos["programas_nuevos"]:
            contenedor_revision.addWidget(etiqueta(
                f"Programa nuevo: {p.nombre}" + (f" ({p.editor})" if p.editor else "")))
        for ruta in datos["ejecutables_nuevos"]:
            contenedor_revision.addWidget(etiqueta(f"Archivo nuevo: {ruta}", suave=True))
        for h in datos["hallazgos"]:
            holder: dict = {}

            def al_resolver(holder=holder):
                fila = holder.get("fila")
                if fila is not None:
                    fila.setParent(None)
                    fila.deleteLater()

            fila = _fila_hallazgo(h, ctx, al_resolver)
            holder["fila"] = fila
            contenedor_revision.addWidget(fila)

    def revisar():
        lbl_revision.setText("Revisando…")
        trabajador = _Trabajador(
            lambda: seguridad.revisar_instalaciones(
                servicios.base_firmas, servicios.carpetas_riesgo()), pagina)
        trabajador.terminado.connect(al_revisar)
        _guardar_ref(pagina, trabajador)
        trabajador.start()

    b_revisar.clicked.connect(revisar)

    # --- escaneo semanal ------------------------------------------------------------
    tarjeta_semanal, lay_s = tarjeta(t("Escaneo automático semanal"))
    lay_s.addWidget(etiqueta(t(
        "Una vez por semana, en silencio; solo avisa si encuentra algo. Usa el Programador de tareas de Windows.")))
    lbl_semanal = etiqueta("")
    lay_s.addWidget(lbl_semanal)
    fila_s = QHBoxLayout()
    b_semanal_on = QPushButton(t("Activar escaneo semanal"))
    b_semanal_off = QPushButton(t("Desactivar"))
    fila_s.addWidget(b_semanal_on)
    fila_s.addWidget(b_semanal_off)
    fila_s.addStretch(1)
    lay_s.addLayout(fila_s)
    layout.addWidget(tarjeta_semanal)
    layout.addStretch(1)

    def refrescar_semanal():
        r = seguro(tasks.existe_tarea_semanal)
        if r.ok:
            lbl_semanal.setText("Estado: ACTIVADO (lunes, 10:00)." if r.datos
                                else "Estado: desactivado.")
        else:
            lbl_semanal.setText(f"Estado: {r.mensaje}")

    def semanal(activo: bool):
        def trabajo():
            if activo:
                ok = tasks.crear_tarea_semanal()
            else:
                ok = tasks.eliminar_tarea_semanal()
            if ok:
                servicios.ajustes.escaneo_semanal = activo
                servicios.ajustes.guardar()
                return ResultadoModulo(
                    True, "Escaneo semanal activado." if activo
                    else "Escaneo semanal desactivado.")
            return ResultadoModulo(False, "Windows no confirmó el cambio de la tarea.")
        trabajador = _Trabajador(trabajo, pagina)
        trabajador.terminado.connect(
            lambda res: (QMessageBox.information(pagina, "Escaneo semanal", res.mensaje),
                         refrescar_semanal()))
        _guardar_ref(pagina, trabajador)
        trabajador.start()

    b_semanal_on.clicked.connect(lambda: semanal(True))
    b_semanal_off.clicked.connect(lambda: semanal(False))
    refrescar_semanal()
    return pagina


# ---------------------------------------------------------------------------
# Página: Informes
# ---------------------------------------------------------------------------

def crear_pagina_informes(ctx: ContextoModulo):
    pagina, layout = pagina_base(
        t("Informes"), t("Informe de privacidad y persistencia: qué programas hay, qué arranca con Windows y qué merece una mirada."))
    estado = {"texto": ""}

    tarjeta_gen, lay = tarjeta(t("Informe de privacidad y persistencia"))
    lay.addWidget(etiqueta(t(
        "Programas instalados, claves Run/RunOnce, carpeta de inicio, tareas programadas sospechosas y servicios de terceros. Solo lectura: la app no desactiva ni borra nada.")))
    b_generar = boton_principal(t("Generar informe"), "primario")
    lay.addWidget(b_generar)
    barra_informe = BarraProgreso()
    barra_informe.setVisible(False)
    lay.addWidget(barra_informe)
    lbl_resumen = etiqueta("")
    lay.addWidget(lbl_resumen)
    layout.addWidget(tarjeta_gen)

    tarjeta_texto, lay_t = tarjeta(t("Contenido del informe"))
    texto = QPlainTextEdit()
    texto.setReadOnly(True)
    texto.setPlaceholderText(t("Pulsa «Generar informe» para ver aquí el contenido."))
    lay_t.addWidget(texto)
    layout.addWidget(tarjeta_texto)

    tarjeta_exp, lay_e = tarjeta(t("Exportar"))
    b_guardar = QPushButton(t("Guardar informe como archivo"))
    b_guardar.setEnabled(False)
    lay_e.addWidget(b_guardar)
    layout.addWidget(tarjeta_exp)
    layout.addStretch(1)

    def al_generar(res: ResultadoModulo):
        b_generar.setEnabled(True)
        tarjeta_gen.fijar_activa(False)
        barra_informe.terminar()
        lbl_resumen.setText(res.mensaje)
        if res.ok and res.datos:
            estado["texto"] = seguridad.texto_informe(res.datos)
            texto.setPlainText(estado["texto"])
            b_guardar.setEnabled(True)

    def generar():
        b_generar.setEnabled(False)
        tarjeta_gen.fijar_activa(True)
        barra_informe.setVisible(True)
        barra_informe.fijar_texto("Generando el informe…")
        lbl_resumen.setText("Generando el informe…")
        trabajador = _Trabajador(seguridad.generar_informe, pagina)
        trabajador.terminado.connect(al_generar)
        _guardar_ref(pagina, trabajador)
        trabajador.start()

    def guardar():
        if not estado["texto"]:
            return
        ruta, _filtro = QFileDialog.getSaveFileName(
            pagina, "Guardar informe",
            os.path.join(config.ruta_informes(), "informe-privacidad.txt"),
            "Texto (*.txt)")
        if not ruta:
            return
        try:
            destino = seguridad.guardar_informe(estado["texto"], ruta)
            QMessageBox.information(pagina, "Informes",
                                    f"Informe guardado en:\n{destino}")
        except OSError as exc:
            QMessageBox.warning(pagina, "Informes", f"No se pudo guardar: {exc}")

    b_generar.clicked.connect(generar)
    b_guardar.clicked.connect(guardar)
    return pagina
