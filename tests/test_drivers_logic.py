"""Drivers (core.drivers_logic): comparación de versiones y contraste con WU."""
from antivirus_hogar_pc.core.drivers_logic import (
    DriverInstalado,
    comparar_versiones,
    consulta_catalogo,
    contrastar_con_windows_update,
    enlace_fabricante_chip,
    enlace_oem,
    hay_version_mas_nueva,
    parsear_version,
)


def test_parsear_version():
    assert parsear_version("10.0.22000.1") == (10, 0, 22000, 1)
    assert parsear_version("10.60.615.2022") == (10, 60, 615, 2022)
    assert parsear_version("") == (0,)
    assert parsear_version("sin numeros") == (0,)


def test_comparar_iguales():
    assert comparar_versiones("10.0.22000.1", "10.0.22000.1") == 0
    assert comparar_versiones("1.2", "1.2.0") == 0      # relleno con ceros
    assert comparar_versiones("v2.0", "2.0") == 0        # sufijos/prefijos
    assert comparar_versiones("", "0") == 0


def test_comparar_mayor_y_menor():
    assert comparar_versiones("10.60.615.2023", "10.60.615.2022") == 1
    assert comparar_versiones("10.60.615.2022", "10.60.615.2023") == -1
    assert comparar_versiones("32.0.15.6094", "10.0.22621.1") == 1
    assert comparar_versiones("9.9", "10.0") == -1       # numérica, no textual


def test_formatos_raros():
    # Estilo NVIDIA «546.33» frente a estilo Windows «32.0.15.4633»: solo
    # importa el orden numérico por componentes, sin excepciones.
    assert comparar_versiones("546.33", "546.33") == 0
    assert hay_version_mas_nueva("546.33", "551.86") is True
    assert hay_version_mas_nueva("551.86", "546.33") is False
    assert hay_version_mas_nueva("1.0", "1.0") is False


DRIVER_RED = DriverInstalado(
    "Realtek PCIe GbE Family Controller", "10.60.615.2022", "15/06/2022",
    "Realtek", "rt640x64.inf",
)
DRIVER_GPU = DriverInstalado(
    "NVIDIA GeForce RTX 4060", "32.0.15.6094", "12/08/2024",
    "NVIDIA", "nv_dispi.inf",
)


def test_contraste_sin_datos_de_wu():
    estados = contrastar_con_windows_update([DRIVER_RED], [])
    assert estados[0].estado == "sin_datos"


def test_contraste_hay_uno_mas_nuevo():
    wu = [{"titulo": "Realtek — Net — Driver Update", "version": "10.60.615.2023"}]
    estados = contrastar_con_windows_update([DRIVER_RED], wu)
    assert estados[0].estado == "hay_uno_mas_nuevo"
    assert estados[0].fuente == "Windows Update"


def test_contraste_version_de_wu_no_mayor_no_marca():
    wu = [{"titulo": "Realtek — Net — Driver Update", "version": "10.60.615.2020"}]
    estados = contrastar_con_windows_update([DRIVER_RED], wu)
    assert estados[0].estado == "al_dia"


def test_contraste_sin_relacion_queda_al_dia():
    wu = [{"titulo": "Actualización acumulativa para Windows (KB5060000)"}]
    estados = contrastar_con_windows_update([DRIVER_RED, DRIVER_GPU], wu)
    assert [e.estado for e in estados] == ["al_dia", "al_dia"]


def test_enlaces_oficiales_de_respaldo():
    nombre, url = enlace_fabricante_chip("NVIDIA")
    assert "nvidia.com" in url
    nombre, url = enlace_fabricante_chip("Advanced Micro Devices, Inc.")
    assert "amd.com" in url
    nombre, url = enlace_oem("Dell Inc.")
    assert "dell.com" in url
    assert enlace_fabricante_chip("Fabricante desconocido") is None
    assert enlace_oem("Marca inventada") is None
    assert consulta_catalogo("PCI\\VEN_10EC&DEV_8168").startswith(
        "https://www.catalog.update.microsoft.com/Search.aspx?q="
    )
