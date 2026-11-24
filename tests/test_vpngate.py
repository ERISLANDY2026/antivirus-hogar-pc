"""Parser CSV de VPN Gate (core.vpngate).

Fixture (tests/fixtures/vpngate_api.csv): respuesta tipo de la API con
líneas «*», cabecera «#» y la trampa contratada — el campo Message del
primer servidor lleva comas SIN entrecomillar, así que la fila cruda tiene
17 campos y el Base64 debe seguir cayendo en la última columna (índice 14
tras la recomposición).
"""
import base64
import os

import pytest

from antivirus_hogar_pc.core.vpngate import (
    ordenar_servidores,
    paises_disponibles,
    parsear_csv_vpngate,
)

FIXTURE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixtures", "vpngate_api.csv"
)
B64_1 = ("Y2xpZW50CmRldiB0dW4KcHJvdG8gdWRwCnJlbW90ZSB2cG4tZWplbXBsby0x"
         "Lm9wZW5ndy5uZXQgMTE5NAo=")


@pytest.fixture()
def servidores():
    with open(FIXTURE, encoding="utf-8") as f:
        return parsear_csv_vpngate(f.read())


def test_fixture_base64_es_valido():
    # La columna 14 del fixture decodifica a un perfil .ovpn reconocible.
    texto = base64.b64decode(B64_1).decode()
    assert texto.startswith("client\n")
    assert "remote vpn-ejemplo-1.opengw.net 1194" in texto


def test_parsea_solo_las_filas_validas(servidores):
    # La fila rota (2 campos) se descarta; comentarios y cabecera no cuentan.
    assert [s.hostname for s in servidores] == [
        "vpn-ejemplo-1.opengw.net", "vpn-ejemplo-2.opengw.net",
    ]


def test_message_con_comas_se_recompone(servidores):
    s = servidores[0]
    assert s.mensaje == "Bienvenido, servidor rapido, sin registros"
    assert s.operador == "operador-uno"
    # …y el Base64 queda intacto en su sitio pese a las comas extra.
    assert s.ovpn_base64 == B64_1


def test_campos_numericos_y_texto(servidores):
    s = servidores[0]
    assert (s.ip, s.pais, s.pais_corto) == ("203.0.113.10", "Japan", "JP")
    assert (s.puntuacion, s.ping_ms, s.velocidad_bps) == (812345, 18, 450_000_000)
    assert (s.sesiones, s.uptime, s.total_usuarios) == (12, 123456, 3400)
    assert s.velocidad_mbps == pytest.approx(450.0)


def test_generar_ovpn_decodifica_el_base64(servidores):
    ovpn = servidores[0].generar_ovpn()
    assert ovpn.startswith("client\n")
    assert "remote vpn-ejemplo-1.opengw.net 1194" in ovpn


def test_segundo_servidor_sin_trampa(servidores):
    s = servidores[1]
    assert s.mensaje == "Servidor sencillo"
    assert s.generar_ovpn().startswith("client\n")


def test_ordenar_y_paises(servidores):
    assert ordenar_servidores(servidores, "velocidad")[0].hostname.startswith("vpn-ejemplo-1")
    assert ordenar_servidores(servidores, "ping")[0].hostname.startswith("vpn-ejemplo-1")
    assert ordenar_servidores(servidores, "puntuacion")[0].hostname.startswith("vpn-ejemplo-1")
    assert paises_disponibles(servidores) == ["Japan", "United States"]


def test_entradas_vacias_o_basura():
    assert parsear_csv_vpngate("") == []
    assert parsear_csv_vpngate("*solo comentarios\n*otra linea\n") == []
