"""Página de Inicio (Carril A — REAL): salud del equipo con datos de verdad.

- El InformeSalud se lee en un hilo (winapi: Defender, firewall, CFA,
  actualizaciones COM, arranque, discos) para no bloquear la interfaz.
- Los datos del sistema (psutil) se refrescan cada 2 s con un QTimer.
- Fuera de Windows la página degrada con honestidad: lo que no se puede
  leer sale como «no disponible en este equipo de pruebas», sin inventar.
"""
from datetime import datetime

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from antivirus_hogar_pc.contracts import ContextoModulo, InformeSalud, ResultadoModulo
from antivirus_hogar_pc.core.i18n import t
from antivirus_hogar_pc.ui import theme
from antivirus_hogar_pc.ui.health_ring import AnilloSalud
from antivirus_hogar_pc.ui.paginas_base import etiqueta, fila_estado, pagina_base, tarjeta
from antivirus_hogar_pc.ui.fondo_radar import FondoRadar
from antivirus_hogar_pc.ui.widgets_v102 import Medidor
from antivirus_hogar_pc.winapi import es_windows

from .datos import animaciones_windows_permitidas, leer_datos_panel, recoger_informe


class _NavegadorPendiente(QObject):
    """Botón «Revisar» de un pendiente → su pantalla (v1.0.16).

    La navegación va por un método ligado de un QObject hijo del
    propio botón, NO por una lambda que capture el contexto:
    conectar un callable libre que captura el contexto (cuyo
    `al_navegar` es un método ligado de la ventana principal)
    dejaba la ventana entera retenida tras su destrucción en la
    suite (la ventana del test de la v1.0.5 sobrevivía y el
    conteo de tarjetas del Programador salía doble). Con un
    receptor QObject la conexión muere con el botón, como manda
    Qt, y no queda ninguna raíz fuera de la ventana.
    """

    def __init__(self, ctx, destino: str, parent=None) -> None:
        super().__init__(parent)
        self._ctx = ctx
        self._destino = destino

    def ir(self, _marcado: bool = False) -> None:
        if self._ctx is not None and self._ctx.al_navegar is not None:
            self._ctx.al_navegar(self._destino)


class _TrabajadorInforme(QThread):
    """Lee el InformeSalud fuera del hilo de la interfaz."""
    listo = Signal(object)  # ResultadoModulo con datos=InformeSalud

    def __init__(self, servicios, parent=None):
        super().__init__(parent)
        self._servicios = servicios

    def run(self) -> None:
        try:
            resultado = recoger_informe(self._servicios)
        except Exception as exc:  # nunca dejar la página colgada
            resultado = ResultadoModulo(False, f"No se pudo leer el estado: {exc}")
        self.listo.emit(resultado)


class _TrabajadorPuestaAPunto(QThread):
    """La «Puesta a punto» (v1.0.16, frente 1) fuera del hilo de
    la interfaz: emite el progreso global y el informe final."""
    progreso = Signal(float, str, str)
    listo = Signal(object)  # dict de core.puesta_a_punto

    def __init__(self, servicios, cancelar_evento, parent=None):
        super().__init__(parent)
        self._servicios = servicios
        self._cancelar = cancelar_evento

    def run(self) -> None:
        from antivirus_hogar_pc.core.puesta_a_punto import (
            ejecutar_puesta_a_punto)
        from antivirus_hogar_pc.ui.puesta_a_punto import pasos_reales

        try:
            resultado = ejecutar_puesta_a_punto(
                pasos_reales(self._servicios),
                al_progreso=lambda f, e, txt: self.progreso.emit(f, e, txt),
                cancelado=self._cancelar.is_set,
                registrar=self._servicios.registrar_actividad
                if self._servicios is not None else None)
        except Exception as exc:  # nunca dejar la tarjeta colgada
            resultado = {"cancelada": False, "resultados": {},
                         "veredicto": f"No se pudo completar: {exc}"}
        self.listo.emit(resultado)


def _vaciar(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        elif item.layout() is not None:
            _vaciar(item.layout())


def _formatear_encendido(horas: float | None) -> str:
    if horas is None:
        return "—"
    if horas < 1:
        return f"{round(horas * 60)} min"
    if horas < 48:
        return f"{horas:.0f} h"
    dias = int(horas // 24)
    resto = int(horas % 24)
    return t("{dias} días y {resto} h", dias=dias, resto=resto)


def _frase_defender(informe: InformeSalud) -> tuple[str, str]:
    d = informe.defender
    if not d:
        return t("No disponible en este equipo de pruebas."), theme.TEXTO_SUAVE
    if not d.get("activo"):
        return t("Microsoft Defender está DESACTIVADO: actívalo cuanto antes."), theme.ROJO
    if not d.get("tiempo_real"):
        return (t("Defender está activo, pero la protección en tiempo real "
                "está apagada.")), theme.AMBAR
    frase = t("Activo y protegiendo en tiempo real.")
    if d.get("version_firmas"):
        frase += t(" Firmas {version}", version=d['version_firmas'])
        if d.get("firmas_al_dia") is True:
            frase += t(" (al día).")
        elif d.get("firmas_al_dia") is False:
            frase += t(" (atrasadas).")
        else:
            frase += "."
    color = theme.AMBAR if d.get("firmas_al_dia") is False else theme.VERDE
    return frase, color


def _frase_firewall(informe: InformeSalud) -> tuple[str, str]:
    if informe.firewall_activo is None:
        return t("No disponible en este equipo de pruebas."), theme.TEXTO_SUAVE
    if informe.firewall_activo:
        return t("Activo en todos los perfiles (dominio, privado y público)."), theme.VERDE
    return t("Desactivado en algún perfil: revísalo cuanto antes."), theme.ROJO


def _frase_actualizaciones(informe: InformeSalud) -> tuple[str, str]:
    n = informe.actualizaciones_windows
    if n is None:
        return t("No disponible en este equipo de pruebas."), theme.TEXTO_SUAVE
    if n == 0:
        return t("Windows está al día: no hay actualizaciones pendientes."), theme.VERDE
    return t("Hay {n} actualización(es) de Windows pendiente(s) de instalar.", n=n), theme.AMBAR


def _frase_cfa(informe: InformeSalud) -> tuple[str, str]:
    if not informe.cfa:
        return t("No disponible en este equipo de pruebas."), theme.TEXTO_SUAVE
    texto = informe.cfa.get("texto", "")
    color = theme.VERDE if informe.cfa.get("activo") else theme.AMBAR
    return t("Protección de carpetas contra ransomware: {texto}.", texto=texto), color


def _frase_disco(informe: InformeSalud) -> tuple[str, str]:
    p = informe.panel
    numeros = ""
    if p.disco_libre_gb is not None and p.disco_total_gb is not None:
        numeros = t(" {libre:.0f} GB libres de {total:.0f} GB.", libre=p.disco_libre_gb, total=p.disco_total_gb)
    # Tendencia (v1.0.16, frente 4): estable / bajando contra
    # ~30 días atrás, o «historial en construcción» sin datos
    # suficientes — jamás una tendencia inventada.
    tendencia_txt = ""
    tendencia = getattr(informe, "tendencia_disco", None) or {}
    if tendencia.get("estado") == "bajando":
        tendencia_txt = t(
            " Su salud está BAJANDO respecto a hace {dias} días: "
            "haz copia de seguridad cuanto antes.",
            dias=tendencia.get("dias") or 30)
    elif tendencia.get("estado") == "estable":
        tendencia_txt = t(
            " Su salud se mantiene estable respecto a hace "
            "{dias} días.", dias=tendencia.get("dias") or 30)
    elif tendencia.get("estado") == "sin_historial":
        tendencia_txt = t(
            " Historial de salud en construcción: su tendencia "
            "se verá cuando haya lecturas de varios días.")
    if any("disco principal está sano" in a for a in informe.salud.aciertos):
        color = theme.ROJO if tendencia.get("bajando") else theme.VERDE
        return t("Sano.") + numeros + tendencia_txt, color
    if any("disco principal reporta problemas" in m for m in informe.salud.motivos):
        return t("Reporta problemas de salud: haz copia de seguridad ya.") + numeros + tendencia_txt, theme.ROJO
    return t("No se pudo leer la salud del disco en este equipo.") + numeros + tendencia_txt, theme.TEXTO_SUAVE


def crear_pagina(ctx: ContextoModulo):
    pagina, layout = pagina_base(
        t("¿Estoy protegido?"),
        t("La salud de tu equipo, con datos reales y cada punto explicado."),
    )
    servicios = ctx.servicios if ctx is not None else None
    estado: dict = {"trabajador": None}

    def _soltar_lectura(_=None) -> None:
        # v1.0.6: si la página muere con la lectura del informe en
        # curso (en Windows tarda: PowerShell), el hilo se despadrea
        # y termina solo — destruirlo en curso aborta el proceso.
        t = estado.get("trabajador")
        if t is not None:
            try:
                t.setParent(None)
            except RuntimeError:
                pass

    pagina.destroyed.connect(_soltar_lectura)

    lbl_estado = etiqueta(t("Leyendo el estado del equipo…"), suave=True)
    layout.addWidget(lbl_estado)

    if not es_windows():
        tarjeta_aviso, lay_aviso = tarjeta(t("Aviso"))
        lay_aviso.addWidget(fila_estado(
            "alerta", "estatico", t("Equipo de pruebas sin Windows"),
            t("Defender, el firewall y las actualizaciones de Windows no se "
              "pueden leer aquí: saldrán como «no disponible» y la puntuación "
              "solo contará lo comprobable. En tu PC con Windows se verá todo."),
            theme.AMBAR))
        layout.addWidget(tarjeta_aviso)

    # --- Fila superior: anillo + estado de la protección ----------------------
    # Fondo futurista (v1.0.2): banda de radar con el anillo ENCIMA.
    # Se anima solo si el usuario no lo apagó en Ajustes Y Windows no
    # pide reducir animaciones; si no, queda como fondo fijo.
    _quiere_animacion = True
    if servicios is not None:
        _quiere_animacion = bool(getattr(servicios.ajustes, "fondo_animado", True))
    banda_radar = FondoRadar(
        animado=_quiere_animacion and animaciones_windows_permitidas())
    anillo = AnilloSalud()
    anillo.fijar_girando(True)
    # v1.0.9 (pedido del usuario): la calificación numérica SALE del
    # centro del radar y va al BORDE INFERIOR IZQUIERDO de la banda,
    # fuera del círculo. Rejilla de UNA celda: el anillo sigue
    # centrado en la banda (alineado con el radar, que no cambia) y
    # la etiqueta se ancla abajo a la izquierda de la misma celda.
    lay_banda = QGridLayout(banda_radar)
    lay_banda.setContentsMargins(12, 6, 12, 10)
    lay_banda.addWidget(anillo, 0, 0, Qt.AlignmentFlag.AlignCenter)
    lbl_puntuacion = QLabel()
    lbl_puntuacion.setTextFormat(Qt.TextFormat.RichText)
    lay_banda.addWidget(
        lbl_puntuacion, 0, 0,
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

    def _sincronizar_puntuacion_esquina() -> None:
        cifra, color, leyenda = anillo.texto_puntuacion()
        lbl_puntuacion.setText(
            f'<span style="font-size: 30px; font-weight: 700; '
            f'color: {color};">{cifra}</span>'
            f'<span style="font-size: 12px; '
            f'color: {theme.TEXTO_SUAVE};">  {leyenda}</span>')

    anillo.valor_cambiado.connect(
        lambda _v: _sincronizar_puntuacion_esquina())
    _sincronizar_puntuacion_esquina()
    layout.addWidget(banda_radar)

    fila_superior = QHBoxLayout()
    tarjeta_estado, lay_tarjeta_estado = tarjeta(t("Estado de la protección"))
    lay_estado = QVBoxLayout()
    lay_tarjeta_estado.addLayout(lay_estado)
    lay_estado.addWidget(fila_estado(
        "lupa", "estatico", t("Comprobando…"),
        t("Estamos leyendo Defender, el firewall y las actualizaciones."),
        theme.TEXTO_SUAVE))
    fila_superior.addWidget(tarjeta_estado, 1)
    layout.addLayout(fila_superior)

    # --- Pendientes (v1.0.16, frente 3) ---------------------------------------
    # Bajo el anillo: la lista ACCIONABLE de lo que necesita
    # atención, solo con datos reales (core.pendientes). Cada
    # fila lleva a su pantalla; sin pendientes, «Todo al día».
    tarjeta_pendientes, lay_tarjeta_pendientes = tarjeta(t("Pendientes"))
    lay_pendientes = QVBoxLayout()
    lay_tarjeta_pendientes.addLayout(lay_pendientes)
    lay_pendientes.addWidget(etiqueta(t("Leyendo el estado del equipo…"),
                                      suave=True))
    layout.addWidget(tarjeta_pendientes)

    def _texto_pendiente(p) -> str:
        if p.clave == "disco_bajando":
            return t("La salud del disco está bajando respecto a "
                     "hace {dias} días: haz copia de seguridad y "
                     "revísalo.", dias=p.dias or 30)
        if p.clave == "escaneo_nunca":
            return t("Todavía no has hecho ningún escaneo con "
                     "esta aplicación.")
        if p.clave == "escaneo_viejo":
            return t("Último escaneo: hace {dias} días.",
                     dias=p.dias or 0)
        if p.clave == "drivers":
            return t("Hay {n} driver(s) desactualizado(s) según "
                     "la última revisión.", n=p.cantidad or 0)
        if p.clave == "optimizar":
            return t("Sin optimizar los volúmenes desde hace "
                     "{dias} días.", dias=p.dias or 0)
        if p.clave == "windows":
            return t("Hay {n} actualización(es) de Windows "
                     "pendiente(s).", n=p.cantidad or 0)
        if p.clave == "vpn_sin_verificar":
            return t("Hay {n} servidor(es) VPN sin verificar.",
                     n=p.cantidad or 0)
        return p.clave

    def repintar_pendientes(lista) -> None:
        _vaciar(lay_pendientes)
        if not lista:
            lay_pendientes.addWidget(etiqueta(
                t("Todo al día: no hay pendientes con los datos "
                  "de este equipo."), suave=True))
            return
        for pendiente in lista:
            fila = QHBoxLayout()
            color = theme.AMBAR if pendiente.aviso else theme.TEXTO_SUAVE
            lbl = etiqueta(_texto_pendiente(pendiente))
            lbl.setStyleSheet(f"color: {color};")
            fila.addWidget(lbl, 1)
            if ctx is not None and ctx.al_navegar is not None:
                boton = QPushButton(t("Revisar"))
                navegador = _NavegadorPendiente(
                    ctx, pendiente.destino, parent=boton)
                boton.clicked.connect(navegador.ir)
                fila.addWidget(boton)
            lay_pendientes.addLayout(fila)

    # --- Puesta a punto de un clic (v1.0.16, frente 1) -------------------------
    tarjeta_puesta, lay_puesta = tarjeta(t("Puesta a punto"))
    lay_puesta.addWidget(etiqueta(t(
        "El mantenimiento completo en un clic, en orden: escaneo "
        "rápido, limpieza segura, optimizar volúmenes y revisión "
        "de drivers (solo revisar: instalar sigue siendo paso a "
        "paso en su pantalla)."), suave=True))
    lbl_etapa_puesta = etiqueta("", suave=True)
    lay_puesta.addWidget(lbl_etapa_puesta)
    lbl_veredicto_puesta = etiqueta("")
    lay_puesta.addWidget(lbl_veredicto_puesta)
    fila_puesta = QHBoxLayout()
    boton_puesta = QPushButton(t("Puesta a punto"))
    boton_puesta.setObjectName("primario")
    boton_cancelar_puesta = QPushButton(t("Cancelar"))
    boton_cancelar_puesta.setEnabled(False)
    fila_puesta.addWidget(boton_puesta)
    fila_puesta.addWidget(boton_cancelar_puesta)
    fila_puesta.addStretch(1)
    lay_puesta.addLayout(fila_puesta)
    layout.addWidget(tarjeta_puesta)

    # --- Rutina automática al arrancar (v1.0.5) --------------------------------
    tarjeta_rutina, lay_rutina = tarjeta(t("Rutina automática al arrancar"))
    lbl_rutina = etiqueta(t(
        "Todavía no se ha ejecutado la rutina automática de arranque."),
        suave=True)
    lay_rutina.addWidget(lbl_rutina)
    layout.addWidget(tarjeta_rutina)

    def _refrescar_rutina() -> None:
        import time as _time

        from antivirus_hogar_pc.ui.rutina_auto import leer_resumen_rutina

        resumen = leer_resumen_rutina()
        if not resumen:
            lbl_rutina.setText(t(
                "Todavía no se ha ejecutado la rutina automática de "
                "arranque."))
            return
        cuando = _time.strftime(
            "%d/%m/%Y %H:%M", _time.localtime(float(resumen.get("cuando", 0))))
        nombres = {"escaneo": t("Escaneo rápido"), "drivers": t("Drivers"),
                   "limpieza": t("Limpieza segura"), "inicio": t("Inicio")}
        partes = []
        for clave, res in (resumen.get("resultados") or {}).items():
            marca = "✓" if res.get("ok") else "⚠"
            partes.append(f"{marca} {nombres.get(clave, clave)}: "
                          f"{res.get('resumen', '')}")
        lbl_rutina.setText(
            t("Última rutina: {cuando} (al arrancar Windows).", cuando=cuando)
            + "\n" + "\n".join(partes))

    _refrescar_rutina()
    pagina.refrescar_rutina = _refrescar_rutina  # gancho para la ventana

    # --- Aviso de fin de soporte (solo si el informe lo confirma) -------------
    tarjeta_soporte, lay_soporte = tarjeta(t("Aviso importante"))
    lay_soporte.addWidget(fila_estado(
        "alerta", "estatico", t("Windows 10 ya no recibe parches"),
        t("Este equipo usa Windows 10, sin soporte desde el 14 de octubre de "
          "2025. Mantener todo lo demás actualizado es aún más importante."),
        theme.AMBAR))
    tarjeta_soporte.setVisible(False)
    layout.addWidget(tarjeta_soporte)

    # --- Por qué esta puntuación ------------------------------------------------
    tarjeta_motivos, lay_tarjeta_motivos = tarjeta(t("Por qué esta puntuación"))
    lay_motivos = QVBoxLayout()
    lay_tarjeta_motivos.addLayout(lay_motivos)
    lay_motivos.addWidget(etiqueta(t("Leyendo el estado del equipo…"), suave=True))
    layout.addWidget(tarjeta_motivos)

    # --- El equipo ahora mismo (psutil, en vivo) ----------------------------------
    tarjeta_sistema, lay_sistema = tarjeta(t("El equipo ahora mismo"))
    med_cpu = Medidor(t("Procesador"))
    med_ram = Medidor(t("Memoria"))
    med_disco = Medidor(t("Disco del sistema"))
    lbl_encendido = etiqueta(t("Encendido desde hace: —"))
    for widget in (med_cpu, med_ram, med_disco, lbl_encendido):
        lay_sistema.addWidget(widget)
    layout.addWidget(tarjeta_sistema)

    # --- Último escaneo + acciones --------------------------------------------------
    tarjeta_escaneo, lay_escaneo = tarjeta(t("Escaneos con esta aplicación"))
    lbl_escaneo = etiqueta(t("Todavía no has hecho ningún escaneo con esta aplicación."))
    lay_escaneo.addWidget(lbl_escaneo)
    fila_botones = QHBoxLayout()
    boton_actualizar = QPushButton(t("Actualizar estado"))
    boton_actualizar.setObjectName("primario")
    fila_botones.addWidget(boton_actualizar)
    if ctx is not None and ctx.al_navegar is not None:
        boton_escaner = QPushButton(t("Ir al escáner"))
        boton_escaner.clicked.connect(lambda: ctx.al_navegar("escaner"))
        fila_botones.addWidget(boton_escaner)
    fila_botones.addStretch(1)
    lay_escaneo.addLayout(fila_botones)
    layout.addWidget(tarjeta_escaneo)

    # --- Registro de actividad ------------------------------------------------------
    tarjeta_actividad, lay_actividad = tarjeta(t("Registro de actividad"))
    lay_lista_actividad = QVBoxLayout()
    lay_actividad.addLayout(lay_lista_actividad)
    fila_actividad = QHBoxLayout()
    boton_refrescar_actividad = QPushButton(t("Actualizar"))
    boton_exportar_actividad = QPushButton(t("Exportar registro"))
    fila_actividad.addWidget(boton_refrescar_actividad)
    fila_actividad.addWidget(boton_exportar_actividad)
    fila_actividad.addStretch(1)
    lay_actividad.addLayout(fila_actividad)
    layout.addWidget(tarjeta_actividad)
    layout.addStretch(1)

    def repintar_actividad() -> None:
        _vaciar(lay_lista_actividad)
        entradas = []
        if servicios is not None:
            actividad = getattr(servicios, "actividad", None)
            if actividad is not None:
                try:
                    entradas = actividad.leer(8)
                except Exception:
                    entradas = []
        if not entradas:
            lay_lista_actividad.addWidget(
                etiqueta(t("Sin actividad registrada todavía."), suave=True))
            return
        for entrada in entradas:
            lay_lista_actividad.addWidget(etiqueta(
                f"{entrada.fecha_legible()} — {entrada.detalle}"))

    def exportar_actividad() -> None:
        if servicios is None:
            return
        actividad = getattr(servicios, "actividad", None)
        if actividad is None:
            return
        ruta, _filtro = QFileDialog.getSaveFileName(
            pagina, t("Exportar registro"), "registro-actividad.txt",
            t("Texto (*.txt)"))
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(actividad.exportar_texto())
        except OSError:
            pass

    boton_refrescar_actividad.clicked.connect(repintar_actividad)
    boton_exportar_actividad.clicked.connect(exportar_actividad)
    repintar_actividad()

    # --- Refresco en vivo de psutil ---------------------------------------------------
    def refrescar_sistema() -> None:
        p = leer_datos_panel()
        med_cpu.fijar(p.cpu_pct,
                      f"{p.cpu_pct:.0f} %" if p.cpu_pct is not None else "—")
        if p.ram_pct is not None and p.ram_total_gb is not None:
            detalle_ram = (f"{p.ram_pct:.0f} % "
                           f"({p.ram_usada_gb} de {p.ram_total_gb} GB)")
        elif p.ram_pct is not None:
            detalle_ram = f"{p.ram_pct:.0f} %"
        else:
            detalle_ram = "—"
        med_ram.fijar(p.ram_pct, detalle_ram)
        if p.disco_sistema_pct is not None and p.disco_total_gb is not None:
            detalle_disco = t("{pct:.0f} % usado ({libre:.0f} GB libres de "
                              "{total:.0f} GB)", pct=p.disco_sistema_pct,
                              libre=p.disco_libre_gb, total=p.disco_total_gb)
        elif p.disco_sistema_pct is not None:
            detalle_disco = t("{pct:.0f} % usado", pct=p.disco_sistema_pct)
        else:
            detalle_disco = "—"
        med_disco.fijar(p.disco_sistema_pct, detalle_disco)
        lbl_encendido.setText(t(
            "Encendido desde hace: {tiempo}",
            tiempo=_formatear_encendido(p.tiempo_encendido_h)))

    temporizador = QTimer(pagina)
    temporizador.timeout.connect(refrescar_sistema)
    temporizador.start(2000)
    refrescar_sistema()

    # --- Aplicar el informe cuando llega del hilo ---------------------------------------
    def aplicar(resultado: ResultadoModulo) -> None:
        boton_actualizar.setEnabled(True)
        anillo.fijar_girando(False)
        lbl_estado.setText(t(resultado.mensaje))
        informe = resultado.datos
        if not isinstance(informe, InformeSalud):
            return
        if informe.salud.maximo_conocido == 0:
            anillo.fijar_sin_datos()
        else:
            anillo.fijar_puntuacion(informe.salud.puntuacion)

        _vaciar(lay_estado)
        frase, color = _frase_defender(informe)
        lay_estado.addWidget(fila_estado(
            "escudo", "pulso", t("Microsoft Defender"), frase, color))
        frase, color = _frase_firewall(informe)
        lay_estado.addWidget(fila_estado(
            "llama", "llama", t("Firewall de Windows"), frase, color))
        frase, color = _frase_actualizaciones(informe)
        lay_estado.addWidget(fila_estado(
            "actualizar", "giro", t("Actualizaciones de Windows"), frase, color))
        frase, color = _frase_cfa(informe)
        lay_estado.addWidget(fila_estado(
            "carpeta", "estatico", t("Protección contra ransomware"), frase, color))
        frase, color = _frase_disco(informe)
        lay_estado.addWidget(fila_estado(
            "disco", "parpadeo", t("Disco principal"), frase, color))

        tarjeta_soporte.setVisible(bool(informe.windows_sin_soporte))

        _vaciar(lay_motivos)
        salud = informe.salud
        if 0 < salud.maximo_conocido < 100:
            lay_motivos.addWidget(etiqueta(t(
                "La puntuación se calcula sobre los {maximo} "
                "puntos que sí se pudieron comprobar en este equipo; el resto "
                "no resta, simplemente no se pudo leer.",
                maximo=salud.maximo_conocido), suave=True))
        for motivo in salud.motivos:
            lay_motivos.addWidget(etiqueta(f"•  {motivo}"))
        for acierto in salud.aciertos:
            lay_motivos.addWidget(etiqueta(f"•  {acierto}", suave=True))

        ultimo = informe.ultimo_escaneo
        if ultimo:
            fecha = datetime.fromtimestamp(
                float(ultimo.get("fecha", 0))).strftime("%d/%m/%Y a las %H:%M")
            lbl_escaneo.setText(t(
                "Último escaneo: {fecha} — {revisados} archivos "
                "revisados, {hallazgos} hallazgo(s).", fecha=fecha,
                revisados=ultimo.get('revisados', 0),
                hallazgos=ultimo.get('hallazgos', 0)))
        # v1.0.16 (frente 3): los pendientes se calculan AQUÍ,
        # en el hilo de la interfaz, con el informe recién
        # aplicado — son solo lecturas locales rápidas (registro
        # de actividad, caché de VPN, estado de mantenimiento) —
        # y así el trabajador conserva exactamente la vida que
        # tenía en la 1.0.15 (su cola alargada en un hilo
        # compartido dejaba ventanas zombis en la suite).
        try:
            from .datos import recoger_pendientes

            repintar_pendientes(recoger_pendientes(servicios, informe))
        except Exception:
            repintar_pendientes([])
        refrescar_sistema()

    def lanzar_lectura() -> None:
        trabajador = estado["trabajador"]
        try:
            if trabajador is not None and trabajador.isRunning():
                return
        except RuntimeError:
            estado["trabajador"] = None  # hilo ya destruido
        boton_actualizar.setEnabled(False)
        anillo.fijar_girando(True)
        lbl_estado.setText(t("Leyendo el estado del equipo…"))
        trabajador = _TrabajadorInforme(servicios, parent=pagina)
        trabajador.listo.connect(aplicar)
        trabajador.finished.connect(trabajador.deleteLater)
        estado["trabajador"] = trabajador
        trabajador.start()

    # Tarjetas con efecto cristal translúcido sobre el fondo (v1.0.2)
    for _nombre in ("tarjeta_aviso", "tarjeta_estado", "tarjeta_soporte",
                    "tarjeta_motivos", "tarjeta_sistema", "tarjeta_escaneo",
                    "tarjeta_actividad", "tarjeta_pendientes",
                    "tarjeta_puesta"):
        _t = locals().get(_nombre)
        if _t is not None:
            _t.setProperty("cristal", "true")

    boton_actualizar.clicked.connect(lanzar_lectura)
    lanzar_lectura()
    return pagina
