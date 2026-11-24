"""Registro de módulos (modules.descubrir_modulos) y fakes contra contratos.

CONTRATOS.md §1 congela 9 módulos con id/carril/ola. El descubrimiento es
headless (sin Qt): estos tests lo verifican tal cual corre en CI.
"""
import dataclasses

import pytest

from antivirus_hogar_pc import contracts
from antivirus_hogar_pc.modules import descubrir_modulos

ESPERADOS = {
    # id: (carril, ola, orden)
    "panel": ("A", 1, 10),
    "escaner": ("B", 1, 20),
    "proteccion": ("B", 2, 30),
    "drivers": ("C", 2, 40),
    "limpieza": ("C", 3, 50),
    "discos": ("C", 2, 60),
    "actualizaciones": ("D", 2, 70),
    "red": ("D", 3, 80),
    "informes": ("B", 2, 90),
}


@pytest.fixture(scope="module")
def registros():
    return descubrir_modulos()


def test_son_nueve_modulos(registros):
    assert len(registros) == 9


def test_ids_unicos_y_los_congelados(registros):
    ids = [r.id for r in registros]
    assert len(ids) == len(set(ids))
    assert set(ids) == set(ESPERADOS)


def test_orden_ascendente_y_el_congelado(registros):
    ordenes = [r.orden for r in registros]
    assert ordenes == sorted(ordenes)
    for r in registros:
        carril, ola, orden = ESPERADOS[r.id]
        assert (r.carril, r.ola, r.orden) == (carril, ola, orden)


def test_rutas_de_pagina_con_formato(registros):
    for r in registros:
        ruta, _, funcion = r.pagina.partition(":")
        assert ruta.startswith("antivirus_hogar_pc.modules.")
        assert ruta.endswith(".page")
        assert funcion.startswith("crear_pagina")


def test_version_de_contratos():
    assert contracts.VERSION_CONTRATOS == "1.0-ola0"


def test_los_fakes_devuelven_los_dataclasses_del_contrato():
    """Cada fake de la Ola 0 devuelve exactamente la forma congelada."""
    from antivirus_hogar_pc.modules.net import fake as fake_net
    from antivirus_hogar_pc.modules.panel import fake as fake_panel
    from antivirus_hogar_pc.modules.security import fake as fake_sec
    from antivirus_hogar_pc.modules.system import fake as fake_sys
    from antivirus_hogar_pc.core.drivers_logic import EstadoDriver
    from antivirus_hogar_pc.core.scanner import ResultadoEscaneo
    from antivirus_hogar_pc.core.vpngate import ServidorVPN
    from antivirus_hogar_pc.core.wifi_parse import InfoWifi
    from antivirus_hogar_pc.core.winget_parse import ProgramaDesactualizado

    informe = fake_panel.informe_fake()
    assert isinstance(informe, contracts.InformeSalud)
    assert isinstance(informe.salud, contracts.ResultadoSalud)
    assert isinstance(informe.panel, contracts.DatosPanel)

    escaneo = fake_sec.escaneo_fake()
    assert isinstance(escaneo, ResultadoEscaneo)
    assert all(isinstance(h, contracts.Hallazgo) for h in escaneo.hallazgos)
    assert isinstance(fake_sec.hosts_fake(), contracts.HostsEstado)

    smart = fake_sys.smart_fake()
    assert all(isinstance(s, contracts.SmartInfo) for s in smart)
    # Caso límite contratado: el disco USB va con sin_datos, nunca «sano».
    usb = [s for s in smart if s.sin_datos]
    assert usb and usb[0].salud == "desconocido"
    assert all(isinstance(d, EstadoDriver) for d in fake_sys.drivers_fake())
    tuneup = fake_sys.tuneup_fake()
    assert isinstance(tuneup, contracts.InformeTuneUp)
    assert tuneup.total_bytes == (
        sum(p.tamano for p in tuneup.partidas) + tuneup.papelera_bytes
    )

    assert all(isinstance(s, ServidorVPN) for s in fake_net.servidores_fake())
    assert isinstance(fake_net.wifi_fake(), InfoWifi)
    assert all(isinstance(p, ProgramaDesactualizado) for p in fake_net.winget_fake())
    assert all(
        isinstance(a, contracts.ActualizacionWindows)
        for a in fake_net.windows_update_fake()
    )


def test_resultado_modulo_es_el_sobre_unico():
    r = contracts.ResultadoModulo(ok=False, mensaje="Sin datos todavía.")
    assert r.ok is False
    assert r.datos is None
    campos = {f.name for f in dataclasses.fields(r)}
    assert campos == {"ok", "mensaje", "datos", "detalle_tecnico"}
