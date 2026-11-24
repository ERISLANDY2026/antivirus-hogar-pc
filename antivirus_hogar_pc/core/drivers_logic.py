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
    drivers: list[DriverInstalado], actualizaciones_wu: list[dict],
    consulta_completada: bool = False,
) -> list[EstadoDriver]:
    """actualizaciones_wu: lista de dicts con al menos «titulo» (y si la hay,
    «version»). Un driver se marca «hay uno más nuevo» si alguna actualización
    de driver ofrecida por Windows Update menciona su dispositivo o su
    fabricante y (si hay versión) es mayor que la instalada.

    `consulta_completada` (v1.0.3): True SOLO si la búsqueda en Windows
    Update terminó con éxito (aunque ofrezca 0 actualizaciones). En ese
    caso, un driver sin coincidencia queda «al_dia»: la consulta SÍ se
    hizo y no hay nada más nuevo. Sin ese dato (False, comportamiento
    histórico), una lista vacía no confirma nada y el estado queda
    «sin_datos»: jamás se marca «al día» sin consulta exitosa real."""
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
            if not actualizaciones_wu and not consulta_completada:
                estado.detalle = "Sin datos de Windows Update todavía: pulsa «Escanear drivers»."
        if estado.estado == "sin_datos" and (actualizaciones_wu or consulta_completada):
            estado.estado = "al_dia"
            estado.detalle = ("Windows Update completó la consulta y no "
                              "ofrece una versión más nueva para este "
                              "dispositivo.")
        estados.append(estado)
    return estados


def _contiene_token(titulo: str, nombre_dispositivo: str) -> bool:
    """Coincidencia prudente: alguna palabra significativa (>=4 letras) del
    nombre del dispositivo aparece en el título de la actualización."""
    for token in re.findall(r"[a-z0-9áéíóúñ]{4,}", nombre_dispositivo):
        if token in titulo:
            return True
    return False


# --- Cadena de confirmación v1.0.5: Catálogo → Windows Update → almacén -------
#
# En la Toughbook del usuario (2026-11-24) la ÚNICA fuente era la
# búsqueda COM de Windows Update con 900 s de límite: agotó el tiempo
# y los 196 drivers quedaron «Sin confirmar», con el comando crudo de
# PowerShell volcado en la línea de «Causa». La cadena nueva confirma
# por la primera fuente oficial que responda con datos reales:
# (a) Catálogo de Microsoft por ID de hardware (por dispositivo,
#     mucho más rápido que el escaneo WU completo);
# (b) Windows Update COM con límite corto (240 s) y un reintento;
# (c) el almacén de drivers de la propia PC (pnputil): si ya hay un
#     paquete más nuevo preparado para el dispositivo, es un dato
#     real y local. «Sin confirmar» solo si TODAS fallan.

def extraer_hwid(device_id: str) -> str:
    """El ID de hardware buscable desde el DeviceID de instancia.

    «PCI\\VEN_8086&DEV_15B7&SUBSYS_833110F7&REV_31\\3&1158…» →
    «PCI\\VEN_8086&DEV_15B7&SUBSYS_833110F7» (sin revisión ni
    instancia: es el HWID que el Catálogo indexa). Sin formato de
    instancia reconocible devuelve el texto tal cual.
    """
    texto = (device_id or "").strip()
    if "\\" not in texto:
        return texto
    partes = texto.split("\\")
    if len(partes) < 2:
        return texto
    segmentos = []
    for seg in partes[1].split("&"):
        if seg.upper().startswith("REV_"):
            break
        segmentos.append(seg)
    return partes[0] + "\\" + "&".join(segmentos)


def es_hwid_buscable(hwid: str) -> bool:
    """Un HWID de verdad lleva bus y parámetros (PCI\\VEN_…&DEV_…)."""
    return "\\" in (hwid or "") and "&" in (hwid or "")


def _fecha_a_date(texto: str):
    """Texto de fecha de Windows/Catálogo → date (o None).

    Formatos: ISO (2023-07-14), dd/mm/aaaa (la app) y m/d/aaaa (el
    Catálogo sirve en formato de EE. UU. por defecto)."""
    import datetime as _dt

    t = (texto or "").strip()
    if not t:
        return None
    t = t.split(" ")[0].split("T")[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return _dt.datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


class _FilasHTML:
    """Extractor mínimo de filas de tabla HTML (sin dependencias)."""

    def __init__(self):
        from html.parser import HTMLParser

        filas: list[list[str]] = []

        class _P(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.en_tr = False
                self.en_td = False
                self.fila: list[str] = []
                self.celda: list[str] = []

            def handle_starttag(self, tag, attrs):
                if tag == "tr":
                    self.en_tr, self.fila = True, []
                elif tag in ("td", "th") and self.en_tr:
                    self.en_td, self.celda = True, []

            def handle_endtag(self, tag):
                if tag in ("td", "th") and self.en_td:
                    self.fila.append(" ".join("".join(self.celda).split()))
                    self.en_td = False
                elif tag == "tr" and self.en_tr:
                    if self.fila:
                        filas.append(self.fila)
                    self.en_tr = False

            def handle_data(self, data):
                if self.en_td:
                    self.celda.append(data)

        self._parser = _P()
        self.filas = filas

    def alimentar(self, html: str) -> list[list[str]]:
        self._parser.feed(html or "")
        return self.filas


def parsear_catalogo_html(html: str) -> list[dict]:
    """Resultados de una búsqueda del Microsoft Update Catalog.

    La página de resultados es una tabla: Título | Productos |
    Clasificación | Última actualización | Versión | Tamaño. Devuelve
    [{titulo, fecha, version}] solo de filas con esa forma; «sin
    resultados» o HTML irreconocible → lista vacía (no confirma nada).
    """
    resultados: list[dict] = []
    for fila in _FilasHTML().alimentar(html):
        if len(fila) < 5:
            continue
        titulo = fila[0]
        if not titulo or titulo.lower() in ("title", "título"):
            continue
        fecha_txt, version = fila[3], fila[4]
        if _fecha_a_date(fecha_txt) is None and not version:
            continue  # fila de cabecera u otra tabla de la página
        resultados.append({"titulo": titulo, "fecha": fecha_txt,
                           "version": version})
    return resultados


def veredicto_catalogo(driver: DriverInstalado,
                       resultados: list[dict]) -> EstadoDriver | None:
    """Veredicto del Catálogo para UN driver (o None = no confirma).

    - La versión instalada figura entre las publicadas para este
      hardware → «al día».
    - El resultado más reciente es posterior a la fecha del driver
      instalado y no es su misma versión → «hay uno más nuevo».
    - Sin resultados o datos ambiguos → None (sigue la cadena).
    """
    if not resultados:
        return None
    versiones = [str(r.get("version") or "") for r in resultados]
    if driver.version and driver.version in versiones:
        return EstadoDriver(
            driver=driver, estado="al_dia", fuente="Catálogo de Microsoft",
            detalle=("El Catálogo de Microsoft publica tu versión "
                     f"({driver.version}) para este hardware: estás al día."))
    con_fecha = [(r, _fecha_a_date(str(r.get("fecha") or "")))
                 for r in resultados]
    con_fecha = [(r, f) for r, f in con_fecha if f is not None]
    fecha_inst = _fecha_a_date(driver.fecha)
    if con_fecha and fecha_inst is not None:
        reciente, fecha_rec = max(con_fecha, key=lambda par: par[1])
        version_rec = str(reciente.get("version") or "")
        if fecha_rec > fecha_inst and version_rec != driver.version:
            return EstadoDriver(
                driver=driver, estado="hay_uno_mas_nuevo",
                fuente="Catálogo de Microsoft",
                detalle=(f"El Catálogo de Microsoft publica una versión "
                         f"más reciente para este hardware "
                         f"({reciente.get('titulo', '')}, "
                         f"{reciente.get('fecha', '')})."))
    return None


def descargar_catalogo(consulta: str, timeout: int = 20, abridor=None) -> str:
    """HTML de la búsqueda del Catálogo para una consulta (HWID).

    `abridor(url, timeout) -> str` inyectable para tests; por defecto
    urllib con un User-Agent de navegador (el Catálogo lo exige)."""
    import urllib.request

    url = consulta_catalogo(consulta)

    def _abrir(u: str, t: int) -> str:
        req = urllib.request.Request(u, headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AntivirusHogarPC"),
            "Accept-Language": "en-US,en;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=t) as resp:
            return resp.read().decode("utf-8", errors="replace")

    return (abridor or _abrir)(url, timeout)


def causa_breve_drivers(texto: str, fuente: str = "Windows Update") -> str:
    """La causa de un fallo, en español BREVE y humano para la UI.

    El detalle técnico crudo (comandos, HRESULT, trazas) va SOLO al
    registro de actividad: aquí jamás se devuelve texto que contenga
    el comando de PowerShell ni volcados del sistema.
    """
    t = (texto or "").lower()
    if any(clave in t for clave in ("timed out", "timeout", "agotó",
                                    "timeoutexpired", "tiempo límite")):
        return f"{fuente} no respondió en el tiempo límite."
    if any(clave in t for clave in ("0x8024", "0x800", "hresult", "com")):
        return f"{fuente} devolvió un error al buscar."
    if any(clave in t for clave in ("urlerror", "name resolution",
                                    "getaddrinfo", "connection",
                                    "conexión", "network", "ssl")):
        return "No hubo conexión con el servidor de Microsoft."
    if "no devolvió una respuesta" in t or "no completó" in t:
        return f"{fuente} no completó la consulta."
    return f"{fuente} no pudo completar la consulta."


def parsear_pnputil(texto: str) -> list[dict]:
    """Salida de `pnputil /enum-drivers` → paquetes del almacén.

    Bloques «Published Name: oem12.inf / Original Name: … / Provider
    Name: … / Driver Version: 07/14/2023 10.60.615.2022» (también en
    español: Nombre publicado / Nombre original / Proveedor / Versión
    del controlador). Devuelve [{inf, original, proveedor, version}].
    """
    paquetes: list[dict] = []
    actual: dict = {}

    def _cerrar():
        if actual.get("inf"):
            paquetes.append(dict(actual))

    claves = {
        "inf": ("published name", "nombre publicado"),
        "original": ("original name", "nombre original"),
        "proveedor": ("provider name", "nombre del proveedor", "proveedor"),
        "version": ("driver version", "versión del controlador",
                    "version del controlador"),
    }
    for linea in (texto or "").splitlines():
        if ":" not in linea:
            continue
        clave, _, valor = linea.partition(":")
        clave_l, valor = clave.strip().lower(), valor.strip()
        for campo, nombres in claves.items():
            if clave_l in nombres:
                if campo == "inf":
                    _cerrar()
                    actual = {}
                if campo == "version":
                    # «07/14/2023 10.60.615.2022»: la versión es el
                    # último token con puntos y dígitos.
                    tokens = valor.split()
                    actual["version"] = tokens[-1] if tokens else ""
                    actual["fecha"] = tokens[0] if len(tokens) > 1 else ""
                else:
                    actual[campo] = valor
                break
    _cerrar()
    return paquetes


def veredicto_almacen(driver: DriverInstalado,
                      paquetes: list[dict]) -> EstadoDriver | None:
    """Si el almacén de drivers ya guarda un paquete del MISMO .inf
    original con versión mayor que la instalada → «hay uno más nuevo»
    (dato local real). En otro caso None: el almacén no confirma."""
    if not driver.inf:
        return None
    for paq in paquetes:
        nombres_inf = {(paq.get("original") or "").lower(),
                       (paq.get("inf") or "").lower()}
        if driver.inf.lower() not in nombres_inf:
            continue
        version_paq = str(paq.get("version") or "")
        if version_paq and hay_version_mas_nueva(driver.version, version_paq):
            return EstadoDriver(
                driver=driver, estado="hay_uno_mas_nuevo",
                fuente="Almacén de drivers de Windows",
                detalle=(f"Ya hay un paquete más nuevo ({version_paq}) "
                         "preparado en el almacén de drivers de esta PC."))
    return None


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
