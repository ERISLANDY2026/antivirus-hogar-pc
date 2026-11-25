"""Auto-actualizador interno del OpenVPN incorporado (v1.0.10).

Pedido expreso del usuario (2026-11-25) con sus cuatro condiciones:

a. **Instalador interno**: la app conserva el instalador oficial
   vigente de OpenVPN (el MSI que viaja junto a la app en
   «openvpn\\») y puede instalarlo/actualizarlo por sí misma.
b. **Automático y silencioso**: chequeo en segundo plano UNA VEZ
   CADA 3 DÍAS al abrir la app (el patrón del antiguo actualizador
   de SoftEther), descarga solo de fuentes oficiales, sin que el
   usuario note nada.
c. **Sigue cumpliendo sus funciones dentro de la app**: tras
   actualizar, la integración se RE-SINCRONIZA (rutas re-detectadas,
   servicio, tarjeta TAP) y la VPN se sigue usando desde la misma
   pantalla de siempre.
d. **Que NO se rompa con una actualización** (la condición clave):
   - El paquete se VERIFICA antes de aplicar: tamaño contra el que
     anuncia el servidor oficial, estructura MSI válida y firma
     Authenticode válida de OpenVPN.
   - NUNCA se aplica con un túnel activo: queda DIFERIDO y se
     aplica al desconectar o en el siguiente arranque sin túnel.
   - Tras aplicar se VERIFICA que OpenVPN sigue sano (versión
     legible, servicio interactivo registrado, tarjeta TAP
     presente). Si la verificación falla, se REVIERTE instalando
     el instalador anterior que funcionaba, y la causa real queda
     en el registro de actividad. Ninguna actualización deja la
     VPN muerta en silencio.

Fuentes OFICIALES (verificadas en vivo el 2026-11-25):
1. Página oficial de descargas de la comunidad:
   https://openvpn.net/community-downloads/ — su enlace principal
   es el MSI amd64 vigente (p. ej. OpenVPN-2.7.9-I002-amd64.msi).
2. GitHub del proyecto (repo OpenVPN/openvpn, releases): los
   instaladores de Windows van como assets de cada release.
La descarga se construye siempre sobre el patrón oficial:
https://swupdate.openvpn.org/community/releases/<nombre del MSI>.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.request

from . import es_windows, vpn_win
from .powershell import ejecutar_elevado

CADA_DIAS = 3
_BASE_DESCARGAS = "https://swupdate.openvpn.org/community/releases"
_PATRON_MSI = re.compile(r"OpenVPN-(\d+)\.(\d+)\.(\d+)-I(\d+)-amd64\.msi")

FUENTES = [
    {"nombre": "Página oficial de descargas (openvpn.net)",
     "url": "https://openvpn.net/community-downloads/",
     "tipo": "descargas"},
    {"nombre": "GitHub oficial (releases de OpenVPN/openvpn)",
     "url": "https://api.github.com/repos/OpenVPN/openvpn/releases?per_page=5",
     "tipo": "github"},
]

_UA = {"User-Agent": "AntivirusHogarPC-OpenVPNUpdate"}
# Firma OLE de un instalador MSI válido (Windows Installer database).
_MAGIA_MSI = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# Códigos de msiexec que significan «instalado» (0) o «instalado,
# reinicio pendiente» (3010 / 1641): la actualización vale igual.
_CODIGOS_MSI_OK = (0, 3010, 1641)


# --- Versiones ---------------------------------------------------------------

def version_desde_nombre(nombre: str):
    """«OpenVPN-2.7.9-I002-amd64.msi» → (2, 7, 9, 2); None si no casa."""
    m = _PATRON_MSI.search(nombre or "")
    return tuple(int(g) for g in m.groups()) if m else None


def nombre_instalador(version) -> str:
    return (f"OpenVPN-{version[0]}.{version[1]}.{version[2]}"
            f"-I{version[3]:03d}-amd64.msi")


def comparar_versiones(a, b) -> int:
    """-1 si a<b, 0 si iguales, 1 si a>b (tuplas (mayor, menor, parche, rev))."""
    a, b = tuple(a), tuple(b)
    return (a > b) - (a < b)


def texto_version(v) -> str:
    return f"{v[0]}.{v[1]}.{v[2]} (instalador I{v[3]:03d})"


def version_instalada() -> tuple | None:
    """La versión del OpenVPN presente, por orden de fiabilidad:

    1. La que el propio actualizador aplicó (su estado).
    2. La del instalador oficial conservado junto a la app.
    3. La de `openvpn.exe --version` (sin revisión de instalador).
    """
    estado = _leer_estado()
    aplicada = estado.get("version_aplicada")
    if aplicada:
        try:
            return tuple(int(x) for x in aplicada)
        except (TypeError, ValueError):
            pass
    conservado = vpn_win.ruta_instalador_openvpn()
    if conservado:
        v = version_desde_nombre(os.path.basename(conservado))
        if v:
            return v
    texto = vpn_win.version_openvpn()
    if texto:
        partes = texto.split(".")
        try:
            return (int(partes[0]), int(partes[1]), int(partes[2]), 0)
        except (ValueError, IndexError):
            pass
    return None


# --- Estado y cadencia ---------------------------------------------------------

def _ruta_estado() -> str:
    from .. import config

    return os.path.join(config.carpeta_datos(), "openvpn_update.json")


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


def _tamano_remoto(url: str, timeout: int = 30) -> int:
    """Content-Length del instalador en el servidor oficial (HEAD)."""
    req = urllib.request.Request(url, headers=_UA, method="HEAD")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return int(resp.headers.get("Content-Length") or 0)


def consultar_fuentes(descargar=_descargar_texto) -> dict:
    """Recorre las fuentes oficiales hasta dar con el MSI vigente.

    Devuelve {"version": tupla|None, "nombre": str, "url": str,
    "fuente": nombre de la que dio la versión, "fallos": [nombres]}.
    La versión que manda es la MAYOR de las que respondan.
    """
    version = None
    fuente_version = ""
    fallos: list[str] = []
    for fuente in FUENTES:
        try:
            texto = descargar(fuente["url"])
        except Exception:
            fallos.append(fuente["nombre"])
            continue
        encontrada = None
        for m in _PATRON_MSI.finditer(texto or ""):
            candidata = tuple(int(g) for g in m.groups())
            if encontrada is None or candidata > encontrada:
                encontrada = candidata
        if encontrada is not None and (version is None
                                      or encontrada > version):
            version = encontrada
            fuente_version = fuente["nombre"]
    if version is None:
        return {"version": None, "nombre": "", "url": "",
                "fuente": "", "fallos": fallos}
    nombre = nombre_instalador(version)
    return {"version": version, "nombre": nombre,
            "url": f"{_BASE_DESCARGAS}/{nombre}",
            "fuente": fuente_version, "fallos": fallos}


# --- Verificación del paquete (condición d: antes de aplicar) ------------------

def verificar_paquete_msi(ruta: str, tamano_esperado: int = 0) -> dict:
    """Verifica un instalador de OpenVPN descargado: tamaño y MSI.

    {"ok", "causa", "tamano", "sha256"}: ok solo si el archivo
    existe, pesa lo anunciado por el servidor oficial (cuando se
    conoce) y lleva la firma OLE de una base de datos MSI válida.
    """
    salida = {"ok": False, "causa": "", "tamano": 0, "sha256": ""}
    try:
        salida["tamano"] = os.path.getsize(ruta)
    except OSError:
        salida["causa"] = "El instalador descargado no existe."
        return salida
    if tamano_esperado and salida["tamano"] != int(tamano_esperado):
        salida["causa"] = (
            f"El instalador pesa {salida['tamano']} bytes y el "
            f"servidor oficial anuncia {int(tamano_esperado)}: no "
            "se aplica.")
        return salida
    try:
        h = hashlib.sha256()
        with open(ruta, "rb") as f:
            if f.read(8) != _MAGIA_MSI:
                salida["causa"] = ("El archivo descargado no es un "
                                   "instalador MSI válido.")
                return salida
            h.update(_MAGIA_MSI)
            for trozo in iter(lambda: f.read(1024 * 512), b""):
                h.update(trozo)
        salida["sha256"] = h.hexdigest()
    except OSError as exc:
        salida["causa"] = f"No se pudo leer el instalador: {exc}"
        return salida
    salida["ok"] = True
    return salida


def interpretar_firma(salida: str) -> dict:
    """Salida JSON de Get-AuthenticodeSignature → {"valida", "firmante"}.

    Válida solo si el estado es «Valid» y el firmante es OpenVPN:
    es la garantía de que el paquete viene del proyecto oficial.
    """
    try:
        datos = json.loads(salida or "")
    except ValueError:
        return {"valida": False, "firmante": ""}
    if not isinstance(datos, dict):
        return {"valida": False, "firmante": ""}
    firmante = str(datos.get("firmante") or "")
    return {"valida": str(datos.get("estado") or "") == "Valid"
            and "openvpn" in firmante.lower(),
            "firmante": firmante}


def firma_authenticode(ruta: str) -> dict:
    """Firma Authenticode real del archivo (PowerShell, en Windows)."""
    from .powershell import ejecutar_powershell

    script = (
        "$s = Get-AuthenticodeSignature -FilePath '" + ruta + "'\n"
        "@{ estado = [string]$s.Status; firmante = "
        "[string]$s.SignerCertificate.Subject } | ConvertTo-Json")
    try:
        salida = ejecutar_powershell(script, timeout=60)
    except Exception:
        return {"valida": False, "firmante": ""}
    return interpretar_firma(salida)


# --- Salud de la integración (verificación tras aplicar) ------------------------

def verificar_integracion(version_esperada=None) -> dict:
    """¿OpenVPN sigue sano tras aplicar una actualización?

    Sano = openvpn.exe localizado y con versión legible (≥ la
    esperada cuando se pide), servicio interactivo registrado y
    tarjeta TAP presente. Es la puerta que decide si hace falta
    REVERTIR: lo que no se pueda comprobar, se dice.
    """
    diag = vpn_win.diagnostico_openvpn()
    fallos = []
    if not diag.get("instalado"):
        fallos.append("openvpn.exe no se localiza tras la actualización")
    elif not diag.get("version"):
        fallos.append("la versión de openvpn.exe no se pudo leer")
    elif version_esperada is not None:
        try:
            partes = diag["version"].split(".")
            actual = (int(partes[0]), int(partes[1]), int(partes[2]))
            if actual < tuple(version_esperada[:3]):
                fallos.append(
                    f"la versión quedó en {diag['version']} y se "
                    f"esperaba {texto_version(version_esperada)}")
        except (ValueError, IndexError):
            fallos.append("la versión de openvpn.exe no se pudo leer")
    servicio = diag.get("servicio") or {}
    if servicio.get("registrado") is False:
        fallos.append("el servicio interactivo de OpenVPN no quedó "
                      "registrado")
    if diag.get("tap") is False:
        fallos.append("la tarjeta TAP-Windows no aparece tras la "
                      "actualización")
    return {"ok": not fallos, "fallos": fallos, "diagnostico": diag}


# --- Chequeo (descarga y verificación, sin aplicar) ------------------------------

def _registrar_nada(_tipo, _detalle):
    pass


def chequear(registrar=_registrar_nada, descargar=_descargar_texto,
             tamano_remoto=_tamano_remoto, verificar_firma=None,
             ahora: float | None = None, forzar: bool = False) -> dict:
    """El chequeo de los 3 días: ¿hay OpenVPN más nuevo y sano?

    Si lo hay, lo descarga, lo VERIFICA (tamaño oficial + MSI +
    firma de OpenVPN) y lo deja PREPARADO (pendiente) en el estado;
    aplicarlo es de aplicar_pendiente(). Un paquete que no pasa la
    verificación se descarta y se anota: nunca queda pendiente.
    Devuelve un dict con el desenlace (claves «hecho», «motivo»…).
    """
    from .. import config
    from ..core import updater

    if verificar_firma is None:
        verificar_firma = firma_authenticode
    ahora = time.time() if ahora is None else ahora
    estado = _leer_estado()
    if not forzar and not toca_chequear(ahora, estado):
        return {"hecho": False, "motivo": "aun no toca",
                "detalle": "Chequeo de OpenVPN: aún no toca."}
    estado["ultimo_chequeo"] = ahora
    instalada = version_instalada()
    if instalada is None:
        _guardar_estado(estado)
        registrar("openvpn",
                  "OpenVPN: chequeo omitido (no se localiza el motor "
                  "incorporado).")
        return {"hecho": True, "motivo": "sin cliente",
                "detalle": "No se localiza el OpenVPN incorporado."}
    consulta = consultar_fuentes(descargar)
    if consulta["version"] is None:
        _guardar_estado(estado)
        registrar("openvpn",
                  "OpenVPN: el chequeo no pudo con ninguna fuente "
                  f"oficial ({len(consulta['fallos'])} fallos); se "
                  "reintenta en el siguiente ciclo.")
        return {"hecho": True, "motivo": "sin fuentes",
                "detalle": "Ninguna fuente oficial respondió."}
    if comparar_versiones(consulta["version"], instalada) <= 0:
        _guardar_estado(estado)
        registrar("openvpn",
                  f"OpenVPN: chequeo sin novedad (instalado "
                  f"{texto_version(instalada)}, último oficial "
                  f"{texto_version(consulta['version'])}).")
        return {"hecho": True, "motivo": "al dia",
                "detalle": "OpenVPN al día."}
    # Hay versión nueva: descargar y verificar ANTES de dejarla
    # pendiente. Si algo no cuadra, no se aplica ni se prepara.
    try:
        esperado = tamano_remoto(consulta["url"])
    except Exception:
        esperado = 0
    carpeta_desc = os.path.join(config.carpeta_datos(), "actualizaciones")
    os.makedirs(carpeta_desc, exist_ok=True)
    ruta_inst = os.path.join(carpeta_desc, consulta["nombre"])
    try:
        updater.descargar_archivo(consulta["url"], ruta_inst)
    except Exception as exc:
        _guardar_estado(estado)
        registrar("openvpn",
                  f"OpenVPN: la descarga de "
                  f"{texto_version(consulta['version'])} falló ({exc}); "
                  "se reintenta en el siguiente ciclo.")
        return {"hecho": True, "motivo": "descarga",
                "detalle": f"La descarga falló: {exc}"}
    verif = verificar_paquete_msi(ruta_inst, esperado)
    if not verif["ok"]:
        try:
            os.remove(ruta_inst)
        except OSError:
            pass
        _guardar_estado(estado)
        registrar("openvpn",
                  "OpenVPN: el instalador descargado NO pasó la "
                  f"verificación y se descartó. Causa: {verif['causa']}")
        return {"hecho": True, "motivo": "verificacion",
                "detalle": verif["causa"]}
    firma = verificar_firma(ruta_inst)
    if not firma.get("valida"):
        try:
            os.remove(ruta_inst)
        except OSError:
            pass
        _guardar_estado(estado)
        registrar("openvpn",
                  "OpenVPN: el instalador descargado no trae la "
                  "firma válida de OpenVPN y se descartó (firmante: "
                  f"{firma.get('firmante') or 'sin firma'}).")
        return {"hecho": True, "motivo": "firma",
                "detalle": "Firma Authenticode no válida de OpenVPN."}
    anterior = vpn_win.ruta_instalador_openvpn()
    estado["pendiente"] = {
        "version": list(consulta["version"]),
        "nombre": consulta["nombre"], "url": consulta["url"],
        "tamano": verif["tamano"], "sha256": verif["sha256"],
        "instalador": ruta_inst, "desde": texto_version(instalada),
        "anterior": anterior,
    }
    _guardar_estado(estado)
    registrar("openvpn",
              f"OpenVPN: versión nueva {texto_version(consulta['version'])} "
              f"(instalada {texto_version(instalada)}) descargada y "
              "verificada (tamaño, MSI y firma de OpenVPN); se "
              "aplicará cuando no haya un túnel VPN activo.")
    return {"hecho": True, "motivo": "pendiente",
            "detalle": "Versión nueva preparada y verificada.",
            "version": consulta["version"]}


# --- Aplicación segura (con diferido y REVERSIÓN) --------------------------------

def _script_msiexec(ruta_msi: str, ruta_resultado: str,
                    carpeta_conservada: str, nombre: str) -> str:
    """El script elevado: instala el MSI y refresca el conservado.

    Tras instalar, copia el MSI a la carpeta «openvpn» de la app
    (el instalador interno conservado pasa a ser el nuevo) y retira
    los MSI viejos de esa carpeta. Cada paso deja su resultado en
    el JSON: nada se finge.
    """
    return f"""
$ErrorActionPreference = 'Continue'
$codigo = -1
$copia = $false
try {{
    $p = Start-Process msiexec.exe -ArgumentList '/i','"{ruta_msi}"','/quiet','/norestart' -Wait -PassThru
    $codigo = $p.ExitCode
}} catch {{ }}
try {{
    Copy-Item -Path '{ruta_msi}' -Destination '{carpeta_conservada}\\{nombre}' -Force -ErrorAction Stop
    Get-ChildItem '{carpeta_conservada}' -Filter 'OpenVPN-*-amd64.msi' |
        Where-Object {{ $_.Name -ne '{nombre}' }} |
        Remove-Item -Force -ErrorAction SilentlyContinue
    $copia = $true
}} catch {{ }}
@{{ codigo = $codigo; copia = $copia }} | ConvertTo-Json |
    Set-Content -Path '{ruta_resultado}' -Encoding UTF8
"""


def _ejecutar_msiexec(ruta_msi: str, nombre: str) -> dict:
    """Corre el script elevado y devuelve {"codigo", "copia"}."""
    from .. import config

    ruta_resultado = os.path.join(config.carpeta_datos(),
                                  "openvpn_aplicar.json")
    if os.path.exists(ruta_resultado):
        os.remove(ruta_resultado)
    carpeta_conservada = vpn_win.carpeta_instalador_openvpn()
    script = _script_msiexec(ruta_msi, ruta_resultado,
                             carpeta_conservada, nombre)
    try:
        lanzado = ejecutar_elevado(script, timeout=600)
    except Exception:
        lanzado = False
    if lanzado and os.path.isfile(ruta_resultado):
        try:
            with open(ruta_resultado, encoding="utf-8-sig") as f:
                datos = json.load(f)
            return {"codigo": datos.get("codigo"),
                    "copia": bool(datos.get("copia"))}
        except (OSError, ValueError):
            pass
    return {"codigo": None, "copia": False}


def aplicar_pendiente(registrar=_registrar_nada, avisar=None,
                      verificar=None, ejecutar=None) -> dict:
    """Aplica la actualización preparada SIN romper la VPN.

    - Con túnel activo NO se toca nada: queda DIFERIDA (nunca
      cortar una conexión sin avisar).
    - Antes de aplicar se guarda copia del instalador anterior
      (el que funciona) para poder REVERTIR.
    - Tras aplicar se VERIFICA la integración; si no está sana,
      se REVIERTE con el instalador anterior y se verifica otra
      vez. El desenlace —con su causa real— queda en el registro.
    """
    if verificar is None:
        verificar = verificar_integracion
    if ejecutar is None:
        ejecutar = _ejecutar_msiexec
    estado = _leer_estado()
    pendiente = estado.get("pendiente")
    if not pendiente:
        return {"aplicada": False, "motivo": "sin pendiente"}
    if vpn_win.hay_tunel_openvpn():
        registrar("openvpn",
                  "OpenVPN: la actualización sigue pendiente porque "
                  "hay un túnel VPN activo; se aplicará al cerrar "
                  "la conexión.")
        return {"aplicada": False, "motivo": "tunel activo",
                "diferida": True}
    if not es_windows():
        return {"aplicada": False, "motivo": "no windows"}
    ruta_nuevo = pendiente.get("instalador") or ""
    if not ruta_nuevo or not os.path.isfile(ruta_nuevo):
        registrar("openvpn",
                  "OpenVPN: no se pudo aplicar la actualización "
                  "(el instalador preparado ya no está).")
        estado["pendiente"] = None
        _guardar_estado(estado)
        return {"aplicada": False, "motivo": "sin instalador"}
    # Re-verificación justo antes de aplicar (condición d): el
    # paquete preparado tiene que seguir siendo el verificado.
    verif = verificar_paquete_msi(ruta_nuevo,
                                  int(pendiente.get("tamano") or 0))
    if not verif["ok"] or (pendiente.get("sha256")
                          and verif["sha256"] != pendiente["sha256"]):
        registrar("openvpn",
                  "OpenVPN: el instalador preparado ya no coincide "
                  "con el verificado y NO se aplica. Causa: "
                  + (verif["causa"] or "la huella cambió."))
        estado["pendiente"] = None
        _guardar_estado(estado)
        return {"aplicada": False, "motivo": "verificacion"}
    # Respaldo del instalador ANTERIOR (el que funciona): primero
    # se copia a la carpeta de datos; es la vía de REVERSIÓN.
    from .. import config

    anterior = pendiente.get("anterior") or ""
    ruta_respaldo = ""
    if anterior and os.path.isfile(anterior):
        ruta_respaldo = os.path.join(
            config.carpeta_datos(), "openvpn-anterior.msi")
        try:
            import shutil

            shutil.copyfile(anterior, ruta_respaldo)
        except OSError:
            ruta_respaldo = ""
    version_nueva = tuple(int(x) for x in pendiente["version"])
    res = ejecutar(ruta_nuevo, pendiente["nombre"])
    codigo = res.get("codigo")
    if codigo not in _CODIGOS_MSI_OK:
        registrar("openvpn",
                  f"OpenVPN: la instalación de "
                  f"{texto_version(version_nueva)} falló (código de "
                  f"Windows Installer: {codigo}); no se aplicó y la "
                  "versión anterior sigue en su sitio.")
        return {"aplicada": False, "motivo": "msiexec",
                "codigo": codigo}
    salud = verificar(version_nueva)
    if not salud["ok"]:
        causa = "; ".join(salud["fallos"])
        registrar("openvpn",
                  f"OpenVPN: la actualización a "
                  f"{texto_version(version_nueva)} dejó la "
                  f"integración mal ({causa}): se REVIERTE a la "
                  "versión anterior que funcionaba.")
        revertido = _revertir(ruta_respaldo, pendiente, ejecutar,
                              verificar, registrar)
        estado["pendiente"] = None
        estado["ultima_reversion"] = {
            "version_fallida": list(version_nueva), "causa": causa,
            "revertido_ok": revertido, "cuando": time.time()}
        _guardar_estado(estado)
        return {"aplicada": False, "motivo": "revertida",
                "causa": causa, "revertido": revertido}
    estado["version_aplicada"] = list(version_nueva)
    estado["pendiente"] = None
    _guardar_estado(estado)
    registrar("openvpn",
              f"OpenVPN actualizado de {pendiente.get('desde', '?')} "
              f"a {texto_version(version_nueva)} y verificado.")
    resinc = resincronizar(registrar)
    if avisar is not None:
        try:
            if resinc["ok"]:
                avisar("Antivirus Hogar PC",
                       f"OpenVPN se actualizó a "
                       f"{texto_version(version_nueva)} y quedó "
                       "sincronizado con la app.")
            else:
                avisar("Antivirus Hogar PC",
                       "OpenVPN se actualizó, pero la "
                       "re-sincronización no fue completa: "
                       + resinc["detalle"])
        except Exception:
            pass
    return {"aplicada": True, "resincronizacion": resinc}


def _revertir(ruta_respaldo: str, pendiente: dict, ejecutar,
              verificar, registrar) -> bool:
    """Reinstala el instalador anterior y comprueba que quedó sano."""
    if not ruta_respaldo or not os.path.isfile(ruta_respaldo):
        registrar("openvpn",
                  "OpenVPN: no hay copia del instalador anterior "
                  "para revertir; la versión nueva queda instalada "
                  "y el fallo anotado arriba.")
        return False
    nombre_anterior = os.path.basename(pendiente.get("anterior") or
                                       "OpenVPN-anterior-amd64.msi")
    res = ejecutar(ruta_respaldo, nombre_anterior)
    if res.get("codigo") not in _CODIGOS_MSI_OK:
        registrar("openvpn",
                  "OpenVPN: la REVERSIÓN también falló (código de "
                  f"Windows Installer: {res.get('codigo')}).")
        return False
    salud = verificar(None)
    if not salud["ok"]:
        registrar("openvpn",
                  "OpenVPN: tras revertir, la integración sigue "
                  "con fallos (" + "; ".join(salud["fallos"]) + ").")
        return False
    registrar("openvpn",
              "OpenVPN: reversión completada; la versión anterior "
              "volvió a quedar instalada y sana.")
    return True


def resincronizar(registrar=_registrar_nada) -> dict:
    """Re-sincronización tras actualizar OpenVPN (condición c).

    Re-detecta openvpn.exe en su ruta (pudo cambiar), verifica que
    su versión se lee, que el servicio interactivo quedó registrado
    y que la tarjeta TAP sigue presente. En OpenVPN no hay cuentas
    persistentes que recrear: la conexión se crea al pulsar
    «Conectar», igual que antes de la actualización. Lo que no se
    pueda, se dice tal cual: no se finge.
    """
    diag = vpn_win.diagnostico_openvpn()
    if not diag["instalado"]:
        detalle = ("openvpn.exe no se localiza tras la "
                   "actualización: la integración no se pudo "
                   "comprobar.")
        registrar("openvpn", "Re-sincronización: " + detalle)
        return {"ok": False, "detalle": detalle, "diagnostico": diag}
    servicio = diag.get("servicio") or {}
    if servicio.get("registrado") is False:
        detalle = ("el servicio interactivo de OpenVPN no quedó "
                   "registrado tras la actualización.")
        registrar("openvpn", "Re-sincronización: " + detalle)
        return {"ok": False, "detalle": detalle, "diagnostico": diag}
    if diag.get("tap") is False:
        detalle = ("la tarjeta TAP-Windows no aparece tras la "
                   "actualización.")
        registrar("openvpn", "Re-sincronización: " + detalle)
        return {"ok": False, "detalle": detalle, "diagnostico": diag}
    detalle = ("todo en su sitio"
               + (f"; versión {diag['version']}" if diag.get("version")
                  else ""))
    registrar("openvpn",
              "OpenVPN re-sincronizado con la app: " + detalle + ".")
    return {"ok": True, "detalle": detalle, "diagnostico": diag}


def chequear_y_aplicar(registrar=_registrar_nada, avisar=None,
                       descargar=_descargar_texto) -> dict:
    """El gancho de arranque: chequeo (si toca) + aplicación si procede."""
    salida = {}
    try:
        salida["chequeo"] = chequear(registrar, descargar)
    except Exception as exc:  # el chequeo nunca debe romper el arranque
        registrar("openvpn", f"OpenVPN: el chequeo falló ({exc}).")
        salida["chequeo"] = {"hecho": False, "motivo": f"error: {exc}"}
    try:
        if _leer_estado().get("pendiente"):
            salida["aplicacion"] = aplicar_pendiente(registrar, avisar)
    except Exception as exc:
        registrar("openvpn",
                  f"OpenVPN: la aplicación pendiente falló ({exc}).")
        salida["aplicacion"] = {"aplicada": False, "motivo": f"error: {exc}"}
    return salida
