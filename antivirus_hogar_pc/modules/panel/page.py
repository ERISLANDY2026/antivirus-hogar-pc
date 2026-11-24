"""Página de Inicio (Carril A — REAL): salud del equipo con datos de verdad.

- El InformeSalud se lee en un hilo (winapi: Defender, firewall, CFA,
  actualizaciones COM, arranque, discos) para no bloquear la interfaz.
- Los datos del sistema (psutil) se refrescan cada 2 s con un QTimer.
- Fuera de Windows la página degrada con honestidad: lo que no se puede
  leer sale como «no disponible en este equipo de pruebas», sin inventar.
"""
from datetime import datetime

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QPushButton, QVBoxLayout

from antivirus_hogar_pc.contracts import ContextoModulo, InformeSalud, ResultadoModulo
from antivirus_hogar_pc.ui import theme
from antivirus_hogar_pc.ui.health_ring import AnilloSalud
from antivirus_hogar_pc.ui.paginas_base import etiqueta, fila_estado, pagina_base, tarjeta
from antivirus_hogar_pc.ui.fondo_radar import FondoRadar
from antivirus_hogar_pc.ui.widgets_v102 import Medidor
from antivirus_hogar_pc.winapi import es_windows

from .datos import animaciones_windows_permitidas, leer_datos_panel, recoger_informe


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
    return f"{dias} días y {resto} h"


def _frase_defender(informe: InformeSalud) -> tuple[str, str]:
    d = informe.defender
    if not d:
        return "No disponible en este equipo de pruebas.", theme.TEXTO_SUAVE
    if not d.get("activo"):
        return "Microsoft Defender está DESACTIVADO: actívalo cuanto antes.", theme.ROJO
    if not d.get("tiempo_real"):
        return ("Defender está activo, pero la protección en tiempo real "
                "está apagada."), theme.AMBAR
    frase = "Activo y protegiendo en tiempo real."
    if d.get("version_firmas"):
        frase += f" Firmas {d['version_firmas']}"
        if d.get("firmas_al_dia") is True:
            frase += " (al día)."
        elif d.get("firmas_al_dia") is False:
            frase += " (atrasadas)."
        else:
            frase += "."
    color = theme.AMBAR if d.get("firmas_al_dia") is False else theme.VERDE
    return frase, color


def _frase_firewall(informe: InformeSalud) -> tuple[str, str]:
    if informe.firewall_activo is None:
        return "No disponible en este equipo de pruebas.", theme.TEXTO_SUAVE
    if informe.firewall_activo:
        return "Activo en todos los perfiles (dominio, privado y público).", theme.VERDE
    return "Desactivado en algún perfil: revísalo cuanto antes.", theme.ROJO


def _frase_actualizaciones(informe: InformeSalud) -> tuple[str, str]:
    n = informe.actualizaciones_windows
    if n is None:
        return "No disponible en este equipo de pruebas.", theme.TEXTO_SUAVE
    if n == 0:
        return "Windows está al día: no hay actualizaciones pendientes.", theme.VERDE
    return f"Hay {n} actualización(es) de Windows pendiente(s) de instalar.", theme.AMBAR


def _frase_cfa(informe: InformeSalud) -> tuple[str, str]:
    if not informe.cfa:
        return "No disponible en este equipo de pruebas.", theme.TEXTO_SUAVE
    texto = informe.cfa.get("texto", "")
    color = theme.VERDE if informe.cfa.get("activo") else theme.AMBAR
    return f"Protección de carpetas contra ransomware: {texto}.", color


def _frase_disco(informe: InformeSalud) -> tuple[str, str]:
    p = informe.panel
    numeros = ""
    if p.disco_libre_gb is not None and p.disco_total_gb is not None:
        numeros = f" {p.disco_libre_gb:.0f} GB libres de {p.disco_total_gb:.0f} GB."
    if any("disco principal está sano" in a for a in informe.salud.aciertos):
        return "Sano." + numeros, theme.VERDE
    if any("disco principal reporta problemas" in m for m in informe.salud.motivos):
        return "Reporta problemas de salud: haz copia de seguridad ya." + numeros, theme.ROJO
    return "No se pudo leer la salud del disco en este equipo." + numeros, theme.TEXTO_SUAVE


def crear_pagina(ctx: ContextoModulo):
    pagina, layout = pagina_base(
        "¿Estoy protegido?",
        "La salud de tu equipo, con datos reales y cada punto explicado.",
    )
    servicios = ctx.servicios if ctx is not None else None
    estado: dict = {"trabajador": None}

    lbl_estado = etiqueta("Leyendo el estado del equipo…", suave=True)
    layout.addWidget(lbl_estado)

    if not es_windows():
        tarjeta_aviso, lay_aviso = tarjeta("Aviso")
        lay_aviso.addWidget(fila_estado(
            "alerta", "estatico", "Equipo de pruebas sin Windows",
            "Defender, el firewall y las actualizaciones de Windows no se "
            "pueden leer aquí: saldrán como «no disponible» y la puntuación "
            "solo contará lo comprobable. En tu PC con Windows se verá todo.",
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
    lay_banda = QHBoxLayout(banda_radar)
    lay_banda.addStretch(1)
    lay_banda.addWidget(anillo)
    lay_banda.addStretch(1)
    layout.addWidget(banda_radar)

    fila_superior = QHBoxLayout()
    tarjeta_estado, lay_tarjeta_estado = tarjeta("Estado de la protección")
    lay_estado = QVBoxLayout()
    lay_tarjeta_estado.addLayout(lay_estado)
    lay_estado.addWidget(fila_estado(
        "lupa", "estatico", "Comprobando…",
        "Estamos leyendo Defender, el firewall y las actualizaciones.",
        theme.TEXTO_SUAVE))
    fila_superior.addWidget(tarjeta_estado, 1)
    layout.addLayout(fila_superior)

    # --- Aviso de fin de soporte (solo si el informe lo confirma) -------------
    tarjeta_soporte, lay_soporte = tarjeta("Aviso importante")
    lay_soporte.addWidget(fila_estado(
        "alerta", "estatico", "Windows 10 ya no recibe parches",
        "Este equipo usa Windows 10, sin soporte desde el 14 de octubre de "
        "2025. Mantener todo lo demás actualizado es aún más importante.",
        theme.AMBAR))
    tarjeta_soporte.setVisible(False)
    layout.addWidget(tarjeta_soporte)

    # --- Por qué esta puntuación ------------------------------------------------
    tarjeta_motivos, lay_tarjeta_motivos = tarjeta("Por qué esta puntuación")
    lay_motivos = QVBoxLayout()
    lay_tarjeta_motivos.addLayout(lay_motivos)
    lay_motivos.addWidget(etiqueta("Leyendo el estado del equipo…", suave=True))
    layout.addWidget(tarjeta_motivos)

    # --- El equipo ahora mismo (psutil, en vivo) ----------------------------------
    tarjeta_sistema, lay_sistema = tarjeta("El equipo ahora mismo")
    med_cpu = Medidor("Procesador")
    med_ram = Medidor("Memoria")
    med_disco = Medidor("Disco del sistema")
    lbl_encendido = etiqueta("Encendido desde hace: —")
    for widget in (med_cpu, med_ram, med_disco, lbl_encendido):
        lay_sistema.addWidget(widget)
    layout.addWidget(tarjeta_sistema)

    # --- Último escaneo + acciones --------------------------------------------------
    tarjeta_escaneo, lay_escaneo = tarjeta("Escaneos con esta aplicación")
    lbl_escaneo = etiqueta("Todavía no has hecho ningún escaneo con esta aplicación.")
    lay_escaneo.addWidget(lbl_escaneo)
    fila_botones = QHBoxLayout()
    boton_actualizar = QPushButton("Actualizar estado")
    boton_actualizar.setObjectName("primario")
    fila_botones.addWidget(boton_actualizar)
    if ctx is not None and ctx.al_navegar is not None:
        boton_escaner = QPushButton("Ir al escáner")
        boton_escaner.clicked.connect(lambda: ctx.al_navegar("escaner"))
        fila_botones.addWidget(boton_escaner)
    fila_botones.addStretch(1)
    lay_escaneo.addLayout(fila_botones)
    layout.addWidget(tarjeta_escaneo)

    # --- Registro de actividad ------------------------------------------------------
    tarjeta_actividad, lay_actividad = tarjeta("Registro de actividad")
    lay_lista_actividad = QVBoxLayout()
    lay_actividad.addLayout(lay_lista_actividad)
    fila_actividad = QHBoxLayout()
    boton_refrescar_actividad = QPushButton("Actualizar")
    boton_exportar_actividad = QPushButton("Exportar registro")
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
                etiqueta("Sin actividad registrada todavía.", suave=True))
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
            pagina, "Exportar registro", "registro-actividad.txt",
            "Texto (*.txt)")
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
            detalle_disco = (f"{p.disco_sistema_pct:.0f} % usado "
                             f"({p.disco_libre_gb:.0f} GB libres de "
                             f"{p.disco_total_gb:.0f} GB)")
        elif p.disco_sistema_pct is not None:
            detalle_disco = f"{p.disco_sistema_pct:.0f} % usado"
        else:
            detalle_disco = "—"
        med_disco.fijar(p.disco_sistema_pct, detalle_disco)
        lbl_encendido.setText(
            f"Encendido desde hace: {_formatear_encendido(p.tiempo_encendido_h)}")

    temporizador = QTimer(pagina)
    temporizador.timeout.connect(refrescar_sistema)
    temporizador.start(2000)
    refrescar_sistema()

    # --- Aplicar el informe cuando llega del hilo ---------------------------------------
    def aplicar(resultado: ResultadoModulo) -> None:
        boton_actualizar.setEnabled(True)
        anillo.fijar_girando(False)
        lbl_estado.setText(resultado.mensaje)
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
            "escudo", "pulso", "Microsoft Defender", frase, color))
        frase, color = _frase_firewall(informe)
        lay_estado.addWidget(fila_estado(
            "llama", "llama", "Firewall de Windows", frase, color))
        frase, color = _frase_actualizaciones(informe)
        lay_estado.addWidget(fila_estado(
            "actualizar", "giro", "Actualizaciones de Windows", frase, color))
        frase, color = _frase_cfa(informe)
        lay_estado.addWidget(fila_estado(
            "carpeta", "estatico", "Protección contra ransomware", frase, color))
        frase, color = _frase_disco(informe)
        lay_estado.addWidget(fila_estado(
            "disco", "parpadeo", "Disco principal", frase, color))

        tarjeta_soporte.setVisible(bool(informe.windows_sin_soporte))

        _vaciar(lay_motivos)
        salud = informe.salud
        if 0 < salud.maximo_conocido < 100:
            lay_motivos.addWidget(etiqueta(
                f"La puntuación se calcula sobre los {salud.maximo_conocido} "
                "puntos que sí se pudieron comprobar en este equipo; el resto "
                "no resta, simplemente no se pudo leer.", suave=True))
        for motivo in salud.motivos:
            lay_motivos.addWidget(etiqueta(f"•  {motivo}"))
        for acierto in salud.aciertos:
            lay_motivos.addWidget(etiqueta(f"•  {acierto}", suave=True))

        ultimo = informe.ultimo_escaneo
        if ultimo:
            fecha = datetime.fromtimestamp(
                float(ultimo.get("fecha", 0))).strftime("%d/%m/%Y a las %H:%M")
            lbl_escaneo.setText(
                f"Último escaneo: {fecha} — {ultimo.get('revisados', 0)} archivos "
                f"revisados, {ultimo.get('hallazgos', 0)} hallazgo(s).")
        refrescar_sistema()

    def lanzar_lectura() -> None:
        trabajador = estado["trabajador"]
        if trabajador is not None and trabajador.isRunning():
            return
        boton_actualizar.setEnabled(False)
        anillo.fijar_girando(True)
        lbl_estado.setText("Leyendo el estado del equipo…")
        trabajador = _TrabajadorInforme(servicios, parent=pagina)
        trabajador.listo.connect(aplicar)
        estado["trabajador"] = trabajador
        trabajador.start()

    # Tarjetas con efecto cristal translúcido sobre el fondo (v1.0.2)
    for _nombre in ("tarjeta_aviso", "tarjeta_estado", "tarjeta_soporte",
                    "tarjeta_motivos", "tarjeta_sistema", "tarjeta_escaneo",
                    "tarjeta_actividad"):
        _t = locals().get(_nombre)
        if _t is not None:
            _t.setProperty("cristal", "true")

    boton_actualizar.clicked.connect(lanzar_lectura)
    lanzar_lectura()
    return pagina
