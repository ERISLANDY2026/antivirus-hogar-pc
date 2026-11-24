"""Auto-actualizador del SoftEther incorporado (v1.0.7, punto 7).

La app comprueba en segundo plano, UNA VEZ CADA 3 DÍAS (al abrir,
si pasaron ≥3 días del último chequeo, sin bloquear la interfaz),
si el proyecto SoftEther publicó una versión estable más nueva que
la instalada. Fuentes OFICIALES, verificadas en vivo el 2026-11-24
antes de cablearlas (si una falla, se pasa a la siguiente):

1. GitHub del proyecto (repo SoftEtherVPN_Stable, etiquetas):
   https://api.github.com/repos/SoftEtherVPN/SoftEtherVPN_Stable/tags?per_page=5
   (ojo: su «último release» de GitHub está atrasado; las ETIQUETAS
   sí van al día: v4.44-9807-rtm).
2. Historial oficial de versiones:
   https://www.softether.org/5-download/history
3. Listado oficial de descargas (da también la carpeta con la
   fecha de publicación, que hace falta para construir la URL):
   https://www.softether-download.com/files/softether/
4. El listado de la carpeta del cliente de esa versión (nombre
   exacto del instalador y su tamaño, para verificar la descarga).

Si hay versión nueva: se descarga el instalador oficial, se
verifica (tamaño del listado oficial y, sobre todo, la estructura:
los archivos del cliente se extraen de sus recursos DATAFILE y
cada .exe debe descomprimir a un PE x64 válido), y la actualización
se aplica EN SEGUNDO PLANO y sin molestar: parar el servicio,
sustituir los archivos de {app}\\softether y rearrancarlo — eso
exige UNA elevación de administrador (UAC), es el mínimo honesto
en Windows —. Si hay un TÚNEL VPN ACTIVO no se aplica: queda
anotada como pendiente y se aplica al cerrar la conexión o en el
siguiente arranque sin túnel. Nunca se corta una conexión activa.

Tras aplicar, la app se RE-SINCRONIZA sola con la versión nueva
(complemento del punto 7): re-detecta vpncmd (la ruta pudo
cambiar), verifica que responde, que el servicio quedó registrado
y arrancable, que la tarjeta virtual y la conexión de VPN Gate
siguen vivas (si la actualización las borró, las recrea igual que
en la instalación inicial) y corre la mini-diagnóstico. Todo queda
en el registro de actividad; el globito de la bandeja solo avisa
cuando actualiza (o si la re-sincronización falló).

Si las fuentes fallan todas: se anota y se reintenta en el
siguiente ciclo (3 días), sin mensajes repetidos.
"""
from __future__ import annotations

import json
import os
import re
import struct
import time
import urllib.request
import zlib

from . import vpn_win
from .powershell import ejecutar_elevado, es_windows

CADA_DIAS = 3
_BASE_DESCARGAS = "https://www.softether-download.com/files/softether"

FUENTES = [
    {"nombre": "GitHub oficial (etiquetas de SoftEtherVPN_Stable)",
     "url": "https://api.github.com/repos/SoftEtherVPN/SoftEtherVPN_Stable/tags?per_page=5",
     "tipo": "github_tags"},
    {"nombre": "Historial oficial de softether.org",
     "url": "https://www.softether.org/5-download/history",
     "tipo": "historia"},
    {"nombre": "Listado oficial de softether-download.com",
     "url": _BASE_DESCARGAS + "/",
     "tipo": "listado"},
]

_UA = {"User-Agent": "AntivirusHogarPC-SoftEtherUpdate"}


# --- Versiones ---------------------------------------------------------------

def _tupla(mayor, menor, build) -> tuple[int, int, int]:
    return (int(mayor), int(menor), int(build))


def version_desde_tag(tag: str):
    """«v4.44-9807-rtm» → (4, 44, 9807); None si no es RTM estable."""
    m = re.fullmatch(r"v(\d+)\.(\d+)-(\d+)-rtm", (tag or "").strip())
    return _tupla(*m.groups()) if m else None


def version_desde_historia(html: str):
    """Primera «SoftEther VPN X.XX Build YYYY RTM» del historial.

    Las entradas Beta no casan (tras el build va «Beta», no «RTM»).
    """
    m = re.search(r"SoftEther VPN (\d+)\.(\d+) Build (\d+) RTM", html or "")
    return _tupla(*m.groups()) if m else None


def carpetas_desde_listado(html: str) -> dict:
    """{versión: carpeta} de las carpetas «v…-rtm-AAAA.MM.DD-tree»."""
    salida = {}
    for m in re.finditer(
            r"(v(\d+)\.(\d+)-(\d+)-rtm-(\d{4}\.\d{2}\.\d{2})-tree)", html or ""):
        salida[_tupla(m.group(2), m.group(3), m.group(4))] = m.group(1)
    return salida


def version_desde_listado(html: str):
    carpetas = carpetas_desde_listado(html)
    return max(carpetas) if carpetas else None


def comparar_versiones(a, b) -> int:
    """-1 si a<b, 0 si iguales, 1 si a>b (tuplas (mayor, menor, build))."""
    a, b = tuple(a), tuple(b)
    return (a > b) - (a < b)


def texto_version(v) -> str:
    return f"{v[0]}.{v[1]} (build {v[2]})"


def version_instalada(carpeta_softether: str | None = None) -> tuple | None:
    """La versión del SoftEther presente: la del estado de
    actualización si la app ya actualizó alguna vez; si no, la del
    marcador que la compilación dejó junto al cliente."""
    estado = _leer_estado()
    aplicada = estado.get("version_aplicada")
    if aplicada:
        try:
            return _tupla(*aplicada)
        except (TypeError, ValueError):
            pass
    carpeta = carpeta_softether or vpn_win.carpeta_softether()
    if not carpeta:
        return None
    try:
        with open(os.path.join(carpeta, "SOFTETHER-CLIENT.txt"),
                  encoding="utf-8", errors="replace") as f:
            texto = f.read()
    except OSError:
        return None
    m = re.search(r"(\d+)\.(\d+) Build (\d+)", texto)
    if not m:
        m = re.search(r"(\d+)\.(\d+)-(\d+)", texto)
    return _tupla(*m.groups()) if m else None


# --- Estado y cadencia ---------------------------------------------------------

def _ruta_estado() -> str:
    from .. import config

    return os.path.join(config.carpeta_datos(), "softether_update.json")


def _leer_estado() -> dict:
    try:
        with open(_ruta_estado(), encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _guardar_estado(estado: dict) -> None:
    try:
        with open(_ruta_estado(), "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def toca_chequear(ahora: float, estado: dict,
                  dias: int = CADA_DIAS) -> bool:
    """¿Pasaron ya ≥``dias`` días del último chequeo? (el primero, sí)."""
    ultimo = estado.get("ultimo_chequeo")
    if not isinstance(ultimo, (int, float)):
        return True
    return (ahora - float(ultimo)) >= dias * 86400


# --- Fuentes -------------------------------------------------------------------

def _descargar_texto(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def consultar_fuentes(descargar=_descargar_texto) -> dict:
    """Recorre las fuentes EN ORDEN hasta reunir versión y carpeta.

    Devuelve {"version": tupla|None, "carpeta": str|None,
    "fuente": nombre de la que dio la versión, "fallos": [nombres]}.
    La versión que manda es la MAYOR de las que respondan (todas
    son oficiales); la carpeta sale del listado oficial.
    """
    version = None
    fuente_version = ""
    carpeta = None
    fallos: list[str] = []
    for fuente in FUENTES:
        if version is not None and carpeta is not None:
            break
        try:
            texto = descargar(fuente["url"])
        except Exception:
            fallos.append(fuente["nombre"])
            continue
        if fuente["tipo"] == "github_tags":
            encontrada = None
            for m in re.finditer(r'"name"\s*:\s*"([^"]+)"', texto):
                encontrada = version_desde_tag(m.group(1))
                if encontrada:
                    break
        elif fuente["tipo"] == "historia":
            encontrada = version_desde_historia(texto)
        else:  # listado
            carpetas = carpetas_desde_listado(texto)
            encontrada = max(carpetas) if carpetas else None
            if encontrada is not None:
                carpeta = carpetas.get(encontrada) or carpeta
        if encontrada is not None and (version is None
                                      or encontrada > version):
            version = encontrada
            fuente_version = fuente["nombre"]
            if fuente["tipo"] == "listado":
                carpeta = carpetas_desde_listado(texto).get(version)
    return {"version": version, "carpeta": carpeta,
            "fuente": fuente_version, "fallos": fallos}


def datos_descarga(carpeta: str, descargar=_descargar_texto) -> dict:
    """{url, nombre, tamano} del instalador del cliente en su carpeta
    oficial (cuarta fuente: el listado de la propia carpeta)."""
    url_carpeta = f"{_BASE_DESCARGAS}/{carpeta}/Windows/SoftEther_VPN_Client/"
    texto = descargar(url_carpeta)
    sin_tags = re.sub(r"<[^>]+>", " ", texto)
    m = re.search(r"(\d{6,})\s+(softether-vpnclient-\S+\.exe)", sin_tags)
    if not m:
        raise ValueError("El listado oficial no muestra el instalador.")
    return {"url": url_carpeta + m.group(2), "nombre": m.group(2),
            "tamano": int(m.group(1))}


# --- Extracción de los recursos DATAFILE del instalador oficial ----------------
# El instalador de SoftEther es un PE y su carga va como recursos de
# tipo «DATAFILE» (comprobado en la compilación de la 1.0.7): los
# .exe van comprimidos (prefijo de 4 bytes + zlib) y el hamcore va
# crudo. Este lector de recursos es Python puro, sin dependencias.

def _u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def _u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def extraer_datafile(datos: bytes) -> dict[str, bytes]:
    """{nombre: bytes} de los recursos DATAFILE de un PE (el instalador)."""
    if datos[:2] != b"MZ":
        raise ValueError("No es un ejecutable PE (sin MZ).")
    pe = _u32(datos, 0x3C)
    if datos[pe:pe + 4] != b"PE\0\0":
        raise ValueError("No es un ejecutable PE (sin firma PE).")
    n_secciones = _u16(datos, pe + 6)
    tam_opcional = _u16(datos, pe + 20)
    opt = pe + 24
    # Directorio de datos nº 2 = recursos (en el encabezado opcional).
    rva_rsrc = _u32(datos, opt + 96 + 2 * 8)
    secciones = []
    for i in range(n_secciones):
        s = opt + tam_opcional + i * 40
        nombre = datos[s:s + 8].rstrip(b"\0").decode("ascii", "replace")
        vsize, vaddr, raw_size, raw_ptr = struct.unpack_from("<IIII", datos, s + 8)
        secciones.append((nombre, vaddr, vsize, raw_ptr, raw_size))

    def a_offset(rva: int) -> int:
        for _n, vaddr, vsize, raw_ptr, _rs in secciones:
            if vaddr <= rva < vaddr + max(vsize, 1):
                return raw_ptr + (rva - vaddr)
        raise ValueError("RVA fuera de las secciones.")

    base = a_offset(rva_rsrc)

    def nombre_entrada(off_dir: int, entrada: int) -> tuple[str | int, int]:
        # Las entradas van TRAS la cabecera de 16 bytes del directorio.
        base_entrada = off_dir + 16 + entrada * 8
        crudo = _u32(datos, base_entrada)
        destino = _u32(datos, base_entrada + 4)
        if crudo & 0x80000000:
            off_str = base + (crudo & 0x7FFFFFFF)
            largo = _u16(datos, off_str)
            nombre = datos[off_str + 2:off_str + 2 + largo * 2].decode(
                "utf-16-le", "replace")
            return nombre, destino
        return crudo & 0xFFFF, destino

    def recorrer(off_dir: int, nivel: int, tipo_actual, nombre_actual):
        """Genera (tipo, nombre, bytes) de las hojas del árbol.

        El árbol PE es tipo → nombre → idioma → datos: el NOMBRE del
        recurso es la entrada del segundo nivel; la del tercero es
        el idioma, que no identifica nada aquí.
        """
        n_nombradas = _u16(datos, off_dir + 12)
        n_ids = _u16(datos, off_dir + 14)
        for i in range(n_nombradas + n_ids):
            nombre, destino = nombre_entrada(off_dir, i)
            if destino & 0x80000000:
                sub = base + (destino & 0x7FFFFFFF)
                yield from recorrer(
                    sub, nivel + 1,
                    nombre if nivel == 0 else tipo_actual,
                    nombre if nivel == 1 else nombre_actual)
            else:
                off_dato = base + destino
                rva, tam = _u32(datos, off_dato), _u32(datos, off_dato + 4)
                yield tipo_actual, nombre_actual, \
                    datos[a_offset(rva):a_offset(rva) + tam]

    salida: dict[str, bytes] = {}
    for tipo, nombre, blob in recorrer(base, 0, None, None):
        if tipo == "DATAFILE" and isinstance(nombre, str):
            salida[nombre] = blob
    if not salida:
        raise ValueError("El instalador no trae recursos DATAFILE.")
    return salida


def descomprimir_recurso(datos: bytes) -> bytes:
    """El formato del fabricante: prefijo de 4 bytes + flujo(s) zlib."""
    salida = bytearray()
    pos = 4
    while pos < len(datos):
        if datos[pos] == 0x78:
            d = zlib.decompressobj()
            salida += d.decompress(datos[pos:])
            consumido = len(datos) - pos - len(d.unused_data)
            if consumido <= 0:
                break
            pos += consumido
            if not d.eof:
                break
        else:
            pos += 4
    return bytes(salida)


def _es_pe_x64(b: bytes) -> bool:
    try:
        if b[:2] != b"MZ":
            return False
        pe = _u32(b, 0x3C)
        return b[pe:pe + 4] == b"PE\0\0" and _u16(b, pe + 4) == 0x8664
    except Exception:
        return False


_MAPA_CLIENTE = {
    "VPNCLIENT_X64.EXE": "vpnclient_x64.exe",
    "VPNCMD_X64.EXE": "vpncmd_x64.exe",
    "VPNCMGR_X64.EXE": "vpncmgr_x64.exe",
    "RAW_HAMCORE.SE2": "hamcore.se2",
}


def preparar_cliente(datos_instalador: bytes, carpeta_destino: str) -> dict:
    """Extrae el cliente de un instalador oficial a ``carpeta_destino``.

    Verifica cada .exe (descomprime a un PE x64 válido) y el
    hamcore (su firma «HamCore»). Devuelve {nombre_final: tamaño}.
    """
    recursos = extraer_datafile(datos_instalador)
    os.makedirs(carpeta_destino, exist_ok=True)
    escritos = {}
    for interno, final in _MAPA_CLIENTE.items():
        if interno not in recursos:
            raise ValueError(f"Falta {interno} en el instalador oficial.")
        blob = recursos[interno]
        if interno.endswith(".EXE"):
            blob = descomprimir_recurso(blob)
            if not _es_pe_x64(blob):
                raise ValueError(f"{interno} no descomprime a un PE x64.")
        elif not blob.startswith(b"HamCore"):
            raise ValueError("El hamcore extraído no lleva su firma.")
        with open(os.path.join(carpeta_destino, final), "wb") as f:
            f.write(blob)
        escritos[final] = len(blob)
    return escritos


# --- Chequeo, aplicación y re-sincronización -----------------------------------

def _registrar_nada(_tipo, _detalle):
    pass


def chequear(registrar=_registrar_nada, descargar=_descargar_texto,
             ahora: float | None = None, forzar: bool = False) -> dict:
    """El chequeo de los 3 días: ¿hay SoftEther más nuevo?

    Si lo hay, lo descarga, lo verifica y lo deja PREPARADO
    (pendiente) en el estado; aplicarlo es de aplicar_pendiente().
    Devuelve un dict con el desenlace (claves «hecho», «detalle»…).
    """
    from ..core import updater

    ahora = time.time() if ahora is None else ahora
    estado = _leer_estado()
    if not forzar and not toca_chequear(ahora, estado):
        return {"hecho": False, "motivo": "aun no toca",
                "detalle": "Chequeo de SoftEther: aún no toca."}
    estado["ultimo_chequeo"] = ahora
    instalada = version_instalada()
    if instalada is None:
        _guardar_estado(estado)
        registrar("softether",
                  "SoftEther: chequeo omitido (no se localiza el "
                  "cliente incorporado).")
        return {"hecho": True, "motivo": "sin cliente",
                "detalle": "No se localiza el SoftEther incorporado."}
    consulta = consultar_fuentes(descargar)
    if consulta["version"] is None:
        _guardar_estado(estado)
        registrar("softether",
                  "SoftEther: el chequeo no pudo con ninguna fuente "
                  f"oficial ({len(consulta['fallos'])} fallos); se "
                  "reintenta en el siguiente ciclo.")
        return {"hecho": True, "motivo": "sin fuentes",
                "detalle": "Ninguna fuente oficial respondió."}
    if comparar_versiones(consulta["version"], instalada) <= 0:
        _guardar_estado(estado)
        registrar("softether",
                  f"SoftEther: chequeo sin novedad (instalado "
                  f"{texto_version(instalada)}, último oficial "
                  f"{texto_version(consulta['version'])}).")
        return {"hecho": True, "motivo": "al dia",
                "detalle": "SoftEther al día."}
    # Hay versión nueva: hace falta su carpeta para descargar.
    carpeta = consulta["carpeta"]
    if carpeta is None:
        try:
            texto = descargar(FUENTES[2]["url"])
            carpeta = carpetas_desde_listado(texto).get(consulta["version"])
        except Exception:
            carpeta = None
    if carpeta is None:
        _guardar_estado(estado)
        registrar("softether",
                  f"SoftEther: hay versión nueva "
                  f"({texto_version(consulta['version'])}) pero no se "
                  "pudo localizar su carpeta oficial de descarga; se "
                  "reintenta en el siguiente ciclo.")
        return {"hecho": True, "motivo": "sin carpeta",
                "detalle": "Versión nueva sin carpeta localizable."}
    datos = datos_descarga(carpeta, descargar)
    from .. import config

    carpeta_desc = os.path.join(config.carpeta_datos(), "actualizaciones")
    os.makedirs(carpeta_desc, exist_ok=True)
    ruta_inst = os.path.join(carpeta_desc, datos["nombre"])
    updater.descargar_archivo(datos["url"], ruta_inst)
    if datos["tamano"] and os.path.getsize(ruta_inst) != datos["tamano"]:
        raise ValueError("El instalador descargado no pesa lo que "
                         "dice el listado oficial.")
    staging = os.path.join(config.carpeta_datos(), "softether-nuevo")
    escritos = preparar_cliente(open(ruta_inst, "rb").read(), staging)
    with open(os.path.join(staging, "SOFTETHER-CLIENT.txt"), "w",
              encoding="utf-8") as f:
        v = consulta["version"]
        f.write(f"SoftEther VPN Client {v[0]}.{v[1]} Build {v[2]} RTM\n"
                f"Instalador oficial: {datos['url']}\n"
                f"Tamano: {datos['tamano']} bytes\n")
    estado["pendiente"] = {
        "version": list(consulta["version"]), "carpeta": carpeta,
        "url": datos["url"], "tamano": datos["tamano"],
        "staging": staging, "instalador": ruta_inst,
        "desde": texto_version(instalada),
    }
    _guardar_estado(estado)
    registrar("softether",
              f"SoftEther: versión nueva {texto_version(consulta['version'])} "
              f"(instalada {texto_version(instalada)}) descargada y "
              f"verificada ({len(escritos)} archivos); se aplicará "
              "cuando no haya un túnel VPN activo.")
    return {"hecho": True, "motivo": "pendiente",
            "detalle": "Versión nueva preparada.",
            "version": consulta["version"]}


def aplicar_pendiente(registrar=_registrar_nada, avisar=None) -> dict:
    """Aplica la actualización preparada, si no hay túnel activo.

    Con túnel activo NO se toca nada (nunca cortar una conexión sin
    avisar): queda pendiente. La aplicación —parar el servicio,
    sustituir los archivos de {app}\\softether, rearrancar— va en UN
    script elevado (UAC): es el mínimo honesto en Windows.
    """
    estado = _leer_estado()
    pendiente = estado.get("pendiente")
    if not pendiente:
        return {"aplicada": False, "motivo": "sin pendiente"}
    if vpn_win.estado_softether().get("conectado"):
        registrar("softether",
                  "SoftEther: la actualización sigue pendiente "
                  "porque hay un túnel VPN activo; se aplicará al "
                  "cerrar la conexión.")
        return {"aplicada": False, "motivo": "tunel activo",
                "diferida": True}
    if not es_windows():
        return {"aplicada": False, "motivo": "no windows"}
    destino = vpn_win.carpeta_softether()
    staging = pendiente.get("staging") or ""
    if not destino or not os.path.isdir(staging):
        registrar("softether",
                  "SoftEther: no se pudo aplicar la actualización "
                  "(falta la carpeta del cliente o la preparada).")
        return {"aplicada": False, "motivo": "carpetas"}
    from .. import config

    ruta_resultado = os.path.join(config.carpeta_datos(),
                                  "softether_aplicar.json")
    if os.path.exists(ruta_resultado):
        os.remove(ruta_resultado)
    script = f"""
$ErrorActionPreference = 'Continue'
$ok = $false
try {{
    net stop SEVPNCLIENT | Out-Null
    Start-Sleep -Seconds 2
    Copy-Item -Path '{staging}\\*' -Destination '{destino}' -Recurse -Force -ErrorAction Stop
    net start SEVPNCLIENT | Out-Null
    $ok = $true
}} catch {{ }}
@{{ ok = $ok }} | ConvertTo-Json | Set-Content -Path '{ruta_resultado}' -Encoding UTF8
"""
    try:
        lanzado = ejecutar_elevado(script, timeout=300)
    except Exception:
        lanzado = False
    aplicado = False
    if lanzado and os.path.isfile(ruta_resultado):
        try:
            with open(ruta_resultado, encoding="utf-8-sig") as f:
                aplicado = bool(json.load(f).get("ok"))
        except (OSError, ValueError):
            aplicado = False
    if not aplicado:
        registrar("softether",
                  "SoftEther: la actualización NO se pudo aplicar "
                  "(sin permiso de administrador o el servicio no "
                  "respondió); queda pendiente para el próximo "
                  "arranque.")
        return {"aplicada": False, "motivo": "elevacion"}
    version_nueva = _tupla(*pendiente["version"])
    estado["version_aplicada"] = list(pendiente["version"])
    estado["pendiente"] = None
    _guardar_estado(estado)
    registrar("softether",
              f"SoftEther actualizado de {pendiente.get('desde', '?')} "
              f"a {texto_version(version_nueva)}.")
    resinc = resincronizar(registrar)
    if avisar is not None:
        try:
            if resinc["ok"]:
                avisar("Antivirus Hogar PC",
                       f"SoftEther se actualizó a "
                       f"{texto_version(version_nueva)} y quedó "
                       "sincronizado con la app.")
            else:
                avisar("Antivirus Hogar PC",
                       "SoftEther se actualizó, pero la "
                       "re-sincronización no fue completa: "
                       + resinc["detalle"])
        except Exception:
            pass
    return {"aplicada": True, "resincronizacion": resinc}


def resincronizar(registrar=_registrar_nada) -> dict:
    """Re-sincronización tras actualizar SoftEther (complemento p. 7).

    Re-detecta vpncmd en su ruta (pudo cambiar), verifica que
    responde y que el servicio quedó registrado, y comprueba que la
    tarjeta virtual y la conexión de VPN Gate siguen vivas; si la
    actualización las borró, las RECREA igual que en la instalación
    inicial (la cuenta, contra el último servidor usado si consta).
    Lo que no se pueda, se dice tal cual: no se finge.
    """
    diag = vpn_win.diagnostico_softether()
    if not diag["instalado"]:
        detalle = ("vpncmd no se localiza tras la actualización: la "
                   "integración con SoftEther no se pudo comprobar.")
        registrar("softether", "Re-sincronización: " + detalle)
        return {"ok": False, "detalle": detalle, "diagnostico": diag}
    servicio = diag.get("servicio") or {}
    if servicio.get("registrado") is False:
        detalle = ("el servicio SEVPNCLIENT no quedó registrado "
                   "tras la actualización.")
        registrar("softether", "Re-sincronización: " + detalle)
        return {"ok": False, "detalle": detalle, "diagnostico": diag}
    pasos = []
    # Tarjeta virtual: si la actualización la borró, se crea.
    if diag.get("nic") is False:
        codigo, salida = vpn_win._ejecutar_vpncmd(
            ["NicCreate", vpn_win.NIC_VPNGATE], timeout=120)
        if vpn_win._vpncmd_ok(codigo, salida):
            pasos.append("tarjeta virtual recreada")
        else:
            detalle = ("la tarjeta virtual no se pudo recrear: "
                       + vpn_win._linea_error_vpncmd(salida))
            registrar("softether", "Re-sincronización: " + detalle)
            return {"ok": False, "detalle": detalle,
                    "diagnostico": diag}
    # Conexión de VPN Gate: si ya no está, se recrea contra el
    # último servidor usado (si consta en el estado de la app).
    cuentas = diag.get("cuentas")
    if cuentas is not None and vpn_win.CUENTA_VPNGATE not in cuentas:
        hostname = ""
        try:
            from .. import config

            with open(os.path.join(config.carpeta_datos(),
                                   "vpn_estado.json"),
                      encoding="utf-8") as f:
                hostname = str(json.load(f).get("hostname") or "")
        except (OSError, ValueError):
            hostname = ""
        if hostname:
            res = vpn_win.asegurar_cuenta_vpngate(hostname)
            if res.get("ok"):
                pasos.append("conexión de VPN Gate recreada")
            else:
                detalle = ("la conexión de VPN Gate no se pudo "
                           "recrear: " + str(res.get("detalle", "")))
                registrar("softether", "Re-sincronización: " + detalle)
                return {"ok": False, "detalle": detalle,
                        "diagnostico": diag}
        else:
            pasos.append("sin servidor anterior: la conexión se "
                         "creará al pulsar «Conectar»")
    version = version_instalada()
    detalle = ("todo en su sitio"
               + (f"; {', '.join(pasos)}" if pasos else "")
               + (f"; versión {texto_version(version)}" if version else ""))
    registrar("softether",
              "SoftEther re-sincronizado con la app: " + detalle + ".")
    return {"ok": True, "detalle": detalle, "diagnostico": diag}


def chequear_y_aplicar(registrar=_registrar_nada, avisar=None,
                       descargar=_descargar_texto) -> dict:
    """El gancho de arranque: chequeo (si toca) + aplicación si procede."""
    salida = {}
    try:
        salida["chequeo"] = chequear(registrar, descargar)
    except Exception as exc:  # el chequeo nunca debe romper el arranque
        registrar("softether", f"SoftEther: el chequeo falló ({exc}).")
        salida["chequeo"] = {"hecho": False, "motivo": f"error: {exc}"}
    try:
        if _leer_estado().get("pendiente"):
            salida["aplicacion"] = aplicar_pendiente(registrar, avisar)
    except Exception as exc:
        registrar("softether",
                  f"SoftEther: la aplicación pendiente falló ({exc}).")
        salida["aplicacion"] = {"aplicada": False, "motivo": f"error: {exc}"}
    return salida
