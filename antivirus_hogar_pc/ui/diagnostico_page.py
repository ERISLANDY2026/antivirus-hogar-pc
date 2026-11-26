"""Página «Diagnosticar integridad de la aplicación» (v1.0.19, nota 7).

El autodiagnóstico de TODAS las funciones que pidió el
usuario: un botón corre las comprobaciones de
core/diagnostico.py en un hilo (algunas leen el registro de
eventos o el disco) y el informe queda en pantalla, listo
para COPIAR al portapapeles o EXPORTAR a un archivo de
texto. Diagnosticar no repara: dice qué está bien, qué
merece atención y qué está roto, con su detalle.
"""
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QWidget,
)

from ..core import diagnostico
from ..core.i18n import t
from .paginas_base import boton_principal, etiqueta, pagina_base, tarjeta


class _TrabajadorDiagnostico(QThread):
    listo = Signal(str)

    def run(self) -> None:  # noqa: D102 (hilo de Qt)
        resultados = diagnostico.diagnosticar()
        self.listo.emit(diagnostico.construir_informe(resultados))


def crear_pagina_diagnostico(ctx=None) -> QWidget:
    pagina, layout = pagina_base(
        t("Diagnosticar integridad de la aplicación"),
        t("Un autodiagnóstico completo de las funciones de la "
          "aplicación: busca fallas y códigos erróneos y deja "
          "el informe aquí mismo, listo para copiar o exportar."))

    tarjeta_d, lay_d = tarjeta(t("Autodiagnóstico"))
    lay_d.addWidget(etiqueta(
        t("El diagnóstico no cambia nada en tu equipo: solo "
          "comprueba y cuenta lo que encuentra."),
        suave=True))
    fila = QHBoxLayout()
    boton_correr = boton_principal(
        t("Ejecutar el diagnóstico"))
    boton_copiar = QPushButton(t("Copiar el informe"))
    boton_copiar.setEnabled(False)
    boton_exportar = QPushButton(t("Exportar el informe"))
    boton_exportar.setEnabled(False)
    fila.addWidget(boton_correr)
    fila.addWidget(boton_copiar)
    fila.addWidget(boton_exportar)
    fila.addStretch(1)
    lay_d.addLayout(fila)
    area = QPlainTextEdit()
    area.setReadOnly(True)
    area.setPlaceholderText(
        t("El informe del diagnóstico aparecerá aquí."))
    area.setMinimumHeight(380)
    lay_d.addWidget(area)
    layout.addWidget(tarjeta_d)
    layout.addStretch(1)

    estado: dict = {"trabajador": None, "informe": ""}

    def _al_listo(texto: str) -> None:
        estado["informe"] = texto
        area.setPlainText(texto)
        boton_correr.setEnabled(True)
        boton_copiar.setEnabled(True)
        boton_exportar.setEnabled(True)

    def _correr() -> None:
        boton_correr.setEnabled(False)
        boton_copiar.setEnabled(False)
        boton_exportar.setEnabled(False)
        area.setPlainText(t("Ejecutando el diagnóstico…"))
        trabajador = _TrabajadorDiagnostico(parent=pagina)
        trabajador.listo.connect(_al_listo)
        trabajador.finished.connect(trabajador.deleteLater)
        estado["trabajador"] = trabajador
        trabajador.start()

    def _copiar() -> None:
        if estado["informe"]:
            QGuiApplication.clipboard().setText(estado["informe"])

    def _exportar() -> None:
        if not estado["informe"]:
            return
        ruta, _filtro = QFileDialog.getSaveFileName(
            pagina, t("Exportar el informe"),
            "diagnostico-antivirus-hogar-pc.txt",
            t("Texto (*.txt)"))
        if ruta:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(estado["informe"])

    boton_correr.clicked.connect(_correr)
    boton_copiar.clicked.connect(_copiar)
    boton_exportar.clicked.connect(_exportar)
    pagina.boton_correr_diagnostico = boton_correr  # ancla de test
    pagina.area_informe_diagnostico = area
    return pagina
