"""Módulo de drivers: comparación de versiones y cadena oficial de fuentes.

Cadena ordenada por el usuario (todas oficiales, sin bases de terceros):
  1. Windows Update / Microsoft Update Catalog (prioridad 1)
  2. Fabricantes de chips: NVIDIA, AMD, Intel
  3. Página oficial de la marca de la PC (OEM)

La enumeración y la instalación viven en winapi/drivers_win.py; aquí está la
lógica pura: comparar versiones, contrastar lo instalado con lo que ofrece
Windows Update y construir los enlaces oficiales de respaldo.
"""
import re
from dataclasses import dataclass


@dataclass
class DriverInstalado:
    dispositivo: str
    version: str
    fecha: str  # ISO o texto de Windows; se usa solo para mostrar
    fabricante: str
    inf: str = ""
    device_id: str = ""
    firmado: bool = True


@dataclass
class EstadoDriver:
    driver: DriverInstalado
    estado: str  # "al_dia" | "hay_uno_mas_nuevo" | "sin_datos"
    detalle: str = ""
    fuente: str = ""  # de qué fuente salió la novedad


def parsear_version(texto: str) -> tuple[int, ...]:
    """«10.0.22000.1» → (10, 0, 22000, 1). Tolera sufijos no numéricos."""
    if not texto:
        return (0,)
    numeros = re.findall(r"\d+", str(texto))
    if not numeros:
        return (0,)
    return tuple(int(n) for n in numeros)


def comparar_versiones(a: str, b: str) -> int:
    """-1 si a<b, 0 si iguales, 1 si a>b (comparación por componentes)."""
    va, vb = parsear_version(a), parsear_version(b)
    largo = max(len(va), len(vb))
    va += (0,) * (largo - len(va))
    vb += (0,) * (largo - len(vb))
    if va < vb:
        return -1
    if va > vb:
        return 1
    return 0


def hay_version_mas_nueva(instalada: str, candidata: str) -> bool:
    return comparar_versiones(candidata, instalada) > 0


_PATRON_VERSION_TITULO = re.compile(r"\d+(?:\.\d+){1,5}")


def version_en_titulo(titulo: str) -> str:
    """Extrae la versión con puntos más completa de un título de Windows
    Update («Realtek - Net - 10.60.615.2022» → «10.60.615.2022»).

    Los títulos de driver de WU suelen terminar en la versión del paquete.
    Si hay varias candidatas se prefiere la de más componentes (y, a igual
    número, la última). Sin candidata devuelve «»."""
    candidatas = _PATRON_VERSION_TITULO.findall(titulo or "")
    if not candidatas:
        return ""
    return max(enumerate(candidatas),
               key=lambda par: (par[1].count("."), par[0]))[1]


# --- Contraste con Windows Update -------------------------------------------
def contrastar_con_windows_update(
    drivers: list[DriverInstalado], actualizaciones_wu: list[dict]
) -> list[EstadoDriver]:
    """actualizaciones_wu: lista de dicts con al menos «titulo» (y si la hay,
    «version»). Un driver se marca «hay uno más nuevo» si alguna actualización
    de driver ofrecida por Windows Update menciona su dispositivo o su
    fabricante y (si hay versión) es mayor que la instalada."""
    estados: list[EstadoDriver] = []
    for d in drivers:
        estado = EstadoDriver(driver=d, estado="sin_datos",
                              detalle="Windows Update no ofrece nada para este dispositivo.")
        nombre = d.dispositivo.lower()
        fabricante = d.fabricante.lower()
        for act in actualizaciones_wu:
            titulo = str(act.get("titulo", "")).lower()
            if not titulo:
                continue
            coincide_nombre = _contiene_token(titulo, nombre)
            coincide_fabricante = fabricante and fabricante in titulo
            if not (coincide_nombre or coincide_fabricante):
                continue
            version_candidata = str(act.get("version", "")) or version_en_titulo(titulo)
            if version_candidata and not hay_version_mas_nueva(d.version, version_candidata):
                continue
            estado = EstadoDriver(
                driver=d, estado="hay_uno_mas_nuevo",
                detalle=f"Windows Update ofrece: {act.get('titulo', '')}",
                fuente="Windows Update",
            )
            break
        else:
            if not actualizaciones_wu:
                estado.detalle = "Sin datos de Windows Update todavía: pulsa «Escanear drivers»."
        if estado.estado == "sin_datos" and actualizaciones_wu:
            estado.estado = "al_dia"
            estado.detalle = "Windows Update no ofrece una versión más nueva."
        estados.append(estado)
    return estados


def _contiene_token(titulo: str, nombre_dispositivo: str) -> bool:
    """Coincidencia prudente: alguna palabra significativa (>=4 letras) del
    nombre del dispositivo aparece en el título de la actualización."""
    for token in re.findall(r"[a-z0-9áéíóúñ]{4,}", nombre_dispositivo):
        if token in titulo:
            return True
    return False


# --- Enlaces oficiales de respaldo (fabricantes y OEM) -----------------------
URLS_FABRICANTES_CHIP = (
    ("nvidia", "NVIDIA — Descargas oficiales de drivers",
     "https://www.nvidia.com/es-es/geforce/drivers/"),
    ("advanced micro devices", "AMD — Drivers y soporte oficial",
     "https://www.amd.com/es/support/downloads/drivers.html"),
    ("amd", "AMD — Drivers y soporte oficial",
     "https://www.amd.com/es/support/downloads/drivers.html"),
    ("intel", "Intel — Centro de descargas oficial",
     "https://www.intel.la/content/www/xl/es/download-center/detect.html"),
)

URLS_OEM = (
    ("dell", "Dell — Controladores y descargas", "https://www.dell.com/support/home/es-es?app=drivers"),
    ("hp", "HP — Software y controladores", "https://support.hp.com/es-es/drivers"),
    ("hewlett-packard", "HP — Software y controladores", "https://support.hp.com/es-es/drivers"),
    ("lenovo", "Lenovo — Controladores y software", "https://pcsupport.lenovo.com/es/es/downloads/"),
    ("asus", "ASUS — Centro de descargas", "https://www.asus.com/es/support/download-center/"),
    ("acer", "Acer — Controladores y manuales", "https://www.acer.com/es-es/support/drivers-and-manuals"),
    ("msi", "MSI — Centro de descargas", "https://es.msi.com/support/download/"),
    ("gigabyte", "GIGABYTE — Descargas", "https://www.gigabyte.com/es/Support"),
    ("toshiba", "Dynabook/Toshiba — Soporte", "https://es.dynabook.com/support/drivers/"),
    ("samsung", "Samsung — Soporte y descargas", "https://www.samsung.com/es/support/download/"),
)


def enlace_fabricante_chip(fabricante_driver: str) -> tuple[str, str] | None:
    f = (fabricante_driver or "").lower()
    for clave, nombre, url in URLS_FABRICANTES_CHIP:
        if clave in f:
            return nombre, url
    return None


def enlace_oem(fabricante_pc: str) -> tuple[str, str] | None:
    f = (fabricante_pc or "").lower()
    for clave, nombre, url in URLS_OEM:
        if clave in f:
            return nombre, url
    return None


URL_CATALOGO_MICROSOFT = "https://www.catalog.update.microsoft.com/Home.aspx"


def consulta_catalogo(device_id: str) -> str:
    """URL de búsqueda en el Microsoft Update Catalog por ID de hardware."""
    from urllib.parse import quote

    return f"https://www.catalog.update.microsoft.com/Search.aspx?q={quote(device_id)}"


# --- Cadena oficial completa para un driver concreto --------------------------
def puede_actualizar(estado: EstadoDriver) -> bool:
    """True si Windows Update ofrece una versión más nueva instalable."""
    return estado.estado == "hay_uno_mas_nuevo"


def enlaces_para_driver(estado: EstadoDriver,
                        fabricante_pc: str = "") -> list[tuple[str, str]]:
    """Enlaces oficiales en el orden de la cadena del usuario, para cuando
    Windows Update no instala directamente o se quiere el paquete a mano:
    1) Microsoft Update Catalog (por ID de hardware si lo hay),
    2) fabricante del chip (NVIDIA/AMD/Intel), 3) marca de la PC (OEM).
    Devuelve pares (nombre visible, URL); puede ir vacía tras el paso 1."""
    d = estado.driver
    enlaces: list[tuple[str, str]] = []
    if d.device_id:
        enlaces.append(("Microsoft Update Catalog — este dispositivo",
                        consulta_catalogo(d.device_id)))
    else:
        enlaces.append(("Microsoft Update Catalog — buscar este dispositivo",
                        consulta_catalogo(d.dispositivo)))
    chip = enlace_fabricante_chip(d.fabricante)
    if chip:
        enlaces.append(chip)
    oem = enlace_oem(fabricante_pc)
    if oem:
        enlaces.append(oem)
    return enlaces
