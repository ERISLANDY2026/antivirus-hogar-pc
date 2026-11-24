"""Página «Programador de tareas» (v1.0.5): escaneos y
mantenimientos programados de verdad, con el Programador de tareas
de Windows.

Cada programación activa crea su tarea «AntivirusHogarPC-<id>» que
lanza la app con --tarea-programada <id>: corre AUNQUE LA APP ESTÉ
CERRADA, en segundo plano, y deja su resultado en
programadas/<id>.json y en el registro de actividad — la pantalla lo
enseña como «última ejecución». Las programaciones se guardan en
ajustes.json y las tareas de Windows se sincronizan al guardar cada
tarjeta. Sin Windows (o si schtasks falla) la pantalla lo dice claro.
"""
import json
import os
import time

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QTimeEdit,
    QWidget,
)

from .. import config
from ..core.programaciones import (
    DIAS_SEMANA,
    TIPOS_PROGRAMACION,
    Programacion,
    a_dicts,
    desde_dicts,
    proxima_ejecucion,
)
from ..winapi import tasks as tareas_win
from .paginas_base import etiqueta, pagina_base, tarjeta
from .services import ServiciosApp, seguro

_DIAS_UI = ("Diaria", "Semanal")


def _ruta_resultado(id_: str) -> str:
    return os.path.join(config.carpeta_datos(), "programadas", f"{id_}.json")


def leer_ultimo_resultado(id_: str) -> dict | None:
    try:
        with open(_ruta_resultado(id_), "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else None
    except (OSError, ValueError):
        return None


def _texto_ultimo_resultado(id_: str) -> str:
    res = leer_ultimo_resultado(id_)
    if not res:
        return "Última ejecución: todavía ninguna."
    cuando = time.strftime("%d/%m/%Y %H:%M",
                           time.localtime(float(res.get("cuando", 0))))
    marca = "✓" if res.get("ok") else "⚠"
    return f"Última ejecución: {cuando} — {marca} {res.get('resumen', '')}"


def _texto_proxima(prog: Programacion) -> str:
    proxima = proxima_ejecucion(prog)
    if proxima is None:
        return "Próxima ejecución: — (desactivada)"
    dia = DIAS_SEMANA[proxima.weekday()].capitalize()
    return (f"Próxima ejecución: {dia} "
            + proxima.strftime("%d/%m/%Y a las %H:%M"))


class _TarjetaProgramacion:
    """Una tarjeta por programación: interruptor, frecuencia, día,
    hora, próxima/última ejecución y guardado con sincronización."""

    def __init__(self, pagina: QWidget, prog: Programacion,
                 al_guardar):
        self.prog = prog
        self._al_guardar = al_guardar
        info = TIPOS_PROGRAMACION[prog.id]
        self.tarjeta, lay = tarjeta(info["titulo"])
        lay.addWidget(etiqueta(info["descripcion"], suave=True))
        fila = QHBoxLayout()
        self.check = QCheckBox("Activada")
        self.check.setChecked(prog.activa)
        fila.addWidget(self.check)
        self.combo_frecuencia = QComboBox()
        self.combo_frecuencia.addItems(_DIAS_UI)
        self.combo_frecuencia.setCurrentText(
            "Diaria" if prog.frecuencia == "diaria" else "Semanal")
        fila.addWidget(self.combo_frecuencia)
        self.combo_dia = QComboBox()
        self.combo_dia.addItems([d.capitalize() for d in DIAS_SEMANA])
        self.combo_dia.setCurrentText(prog.dia.capitalize())
        fila.addWidget(self.combo_dia)
        self.hora = QTimeEdit()
        self.hora.setDisplayFormat("HH:mm")
        try:
            hh, mm = (int(x) for x in prog.hora.split(":"))
        except ValueError:
            hh, mm = 10, 0
        self.hora.setTime(QTime(hh, mm))
        fila.addWidget(self.hora)
        fila.addStretch(1)
        lay.addLayout(fila)
        self.lbl_proxima = etiqueta(_texto_proxima(prog), suave=True)
        lay.addWidget(self.lbl_proxima)
        self.lbl_ultima = etiqueta(_texto_ultimo_resultado(prog.id),
                                   suave=True)
        lay.addWidget(self.lbl_ultima)
        fila_b = QHBoxLayout()
        self.boton = QPushButton("Guardar y aplicar")
        self.boton.setObjectName("primario")
        self.boton.clicked.connect(self._guardar)
        fila_b.addWidget(self.boton)
        self.lbl_estado = etiqueta("", suave=True)
        fila_b.addWidget(self.lbl_estado)
        fila_b.addStretch(1)
        lay.addLayout(fila_b)
        self.combo_frecuencia.currentTextChanged.connect(self._refrescar_dia)
        self._refrescar_dia()

    def _refrescar_dia(self) -> None:
        self.combo_dia.setEnabled(
            self.combo_frecuencia.currentText() == "Semanal")

    def widget(self) -> QWidget:
        return self.tarjeta

    def _guardar(self) -> None:
        self.prog.activa = self.check.isChecked()
        self.prog.frecuencia = (
            "diaria" if self.combo_frecuencia.currentText() == "Diaria"
            else "semanal")
        self.prog.dia = self.combo_dia.currentText().lower()
        self.prog.hora = self.hora.time().toString("HH:mm")
        self.lbl_proxima.setText(_texto_proxima(self.prog))
        self.lbl_ultima.setText(_texto_ultimo_resultado(self.prog.id))
        self.lbl_estado.setText(self._al_guardar(self.prog))


def crear_pagina_programar(ctx) -> QWidget:
    pagina, layout = pagina_base(
        "Programador de tareas",
        "Escaneos y mantenimientos automáticos, a tu hora.")
    servicios: ServiciosApp | None = ctx.servicios if ctx is not None else None

    tarjeta_nota, lay_nota = tarjeta("Cómo funciona")
    lay_nota.addWidget(etiqueta(
        "Las tareas las ejecuta el Programador de tareas de Windows: "
        "corren en segundo plano AUNQUE LA APP ESTÉ CERRADA, y dejan "
        "su resultado aquí (última ejecución) y en el registro de "
        "actividad de Inicio. Ante una amenaza la app nunca actúa "
        "sola: anota el hallazgo y te avisa para que decidas tú. La "
        "limpieza programada usa solo las categorías seguras "
        "(temporales, cachés y papelera).", suave=True))
    layout.addWidget(tarjeta_nota)

    ajustes = servicios.ajustes if servicios is not None else None
    programaciones = desde_dicts(
        ajustes.programaciones if ajustes is not None else [])

    def _al_guardar(prog: Programacion) -> str:
        # Persistir en ajustes y sincronizar la tarea de Windows.
        if ajustes is not None:
            ajustes.programaciones = a_dicts(programaciones)
            ajustes.guardar()
        if prog.activa:
            res = seguro(tareas_win.crear_tarea_programada,
                         prog.id, prog.frecuencia, prog.dia, prog.hora)
            if res.ok and res.datos:
                return "Guardada: tarea de Windows creada."
            return ("Guardada en la app, pero Windows no aceptó la "
                    "tarea (¿sin Windows o sin permiso?).")
        res = seguro(tareas_win.eliminar_tarea_programada, prog.id)
        return "Guardada: programación desactivada y tarea retirada."

    for prog in programaciones:
        tarjeta_p = _TarjetaProgramacion(pagina, prog, _al_guardar)
        layout.addWidget(tarjeta_p.widget())

    layout.addStretch(1)
    return pagina
