"""Bloqueador hosts (core.hosts_blocker): bloque marcado, merge y retirada.

La generación del bloque es lógica pura: la app solo escribe entre sus
marcadores, conserva el resto del hosts intacto y puede dejar el archivo
como estaba (eso, junto con la copia de seguridad previa que hace winapi,
es la «pausa/restauración» contratada).
"""
import os

from antivirus_hogar_pc.core import hosts_blocker as hb

HOSTS_BASE = "127.0.0.1 localhost\n::1 localhost\n192.168.1.10 impresora\n"


def test_generar_bloque_estructura():
    bloque = hb.generar_bloque(["malo.example", "phishing.example"])
    lineas = bloque.splitlines()
    assert lineas[0] == hb.MARCADOR_INICIO
    assert lineas[-1] == hb.MARCADOR_FIN
    assert "0.0.0.0 malo.example" in lineas
    assert "0.0.0.0 phishing.example" in lineas
    assert bloque.endswith("\n")


def test_aplicar_bloque_conserva_el_hosts_original():
    resultado = hb.aplicar_bloque(HOSTS_BASE, ["malo.example"])
    assert resultado.startswith(HOSTS_BASE)
    assert hb.bloque_activo(resultado) is True
    assert hb.contar_bloqueados(resultado) == 1


def test_quitar_bloque_restaura_el_hosts_exacto():
    con_bloque = hb.aplicar_bloque(HOSTS_BASE, ["a.example", "b.example"])
    assert hb.quitar_bloque(con_bloque) == HOSTS_BASE


def test_aplicar_dos_veces_no_duplica_el_bloque():
    una = hb.aplicar_bloque(HOSTS_BASE, ["a.example"])
    dos = hb.aplicar_bloque(una, ["a.example", "b.example"])
    assert dos.count(hb.MARCADOR_INICIO) == 1
    assert hb.contar_bloqueados(dos) == 2
    assert hb.quitar_bloque(dos) == HOSTS_BASE


def test_sin_bloque_no_hay_nada_que_quitar():
    assert hb.bloque_activo(HOSTS_BASE) is False
    assert hb.quitar_bloque(HOSTS_BASE) == HOSTS_BASE
    assert hb.contar_bloqueados(HOSTS_BASE) == 0


def test_hosts_vacio_o_sin_salto_final():
    resultado = hb.aplicar_bloque("", ["a.example"])
    assert hb.contar_bloqueados(resultado) == 1
    sin_salto = hb.aplicar_bloque("127.0.0.1 localhost", ["a.example"])
    assert "localhost\n" in sin_salto
    assert hb.contar_bloqueados(sin_salto) == 1


def test_cargar_dominios_formatos(tmp_path):
    ruta = tmp_path / "lista.txt"
    ruta.write_text(
        "# comentario\n"
        "\n"
        "Malo.EXAMPLE\n"                 # se normaliza a minúsculas
        "0.0.0.0 phishing.example\n"     # formato hosts: se extrae el dominio
        "127.0.0.1 ads.example\n"
        "sinpuntos\n"                    # sin punto: no es dominio, fuera
        "malo.example\n",                # duplicado: una sola vez
        encoding="utf-8",
    )
    assert hb.cargar_dominios([str(ruta)]) == [
        "ads.example", "malo.example", "phishing.example",
    ]


def test_cargar_dominios_rutas_inexistentes_se_ignoran(tmp_path):
    assert hb.cargar_dominios([str(tmp_path / "no.txt"), ""]) == []


def test_activos_reales_del_proyecto():
    """Verificación de assets/: conteos contratados de las bases incluidas."""
    activos = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "antivirus_hogar_pc", "assets",
    )
    semilla = hb.cargar_dominios([os.path.join(activos, "malware_seed.txt")])
    assert len(semilla) == 19563  # semilla Android v6 (CONTRATOS.md §2)
    fusionados = hb.cargar_dominios([os.path.join(activos, "dominios_fusionados.txt")])
    assert len(fusionados) == 100776  # StevenBlack ∪ semilla (CONTRATOS.md §4)
    anuncios = hb.cargar_dominios([os.path.join(activos, "adblock_seed.txt")])
    assert len(anuncios) > 0
    # La fusionada contiene a la semilla.
    assert set(semilla) <= set(fusionados)
