"""Base de firmas (core.signatures) y la semilla de fábrica incluida."""
import os

from antivirus_hogar_pc.core.signatures import BaseFirmas

EICAR_SHA256 = "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f"


def test_cargar_formato_y_buscar(tmp_path):
    ruta = tmp_path / "firmas.txt"
    ruta.write_text(
        "# comentario\n"
        f"{EICAR_SHA256}  EICAR-Test-File\n"
        "44d88612fea8a8f36de82e1278abb02f EICAR por MD5\n"
        "linea-invalida\n",
        encoding="utf-8",
    )
    base = BaseFirmas()
    assert base.cargar_archivo(str(ruta)) == 2
    assert base.total == 2
    assert base.buscar(sha256=EICAR_SHA256) == "EICAR-Test-File"
    assert base.buscar(sha256=EICAR_SHA256.upper()) == "EICAR-Test-File"
    assert base.buscar(md5="44d88612fea8a8f36de82e1278abb02f") == "EICAR por MD5"
    assert base.buscar(sha256="0" * 64) is None
    assert base.cargar_archivo(str(tmp_path / "no_existe.txt")) == 0


def test_semilla_de_fabrica_trae_el_eicar():
    activos = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "antivirus_hogar_pc", "assets",
    )
    base = BaseFirmas()
    assert base.cargar_semilla(activos) == 1
    assert base.buscar(sha256=EICAR_SHA256) is not None
