"""VPN Gate en Windows: delegación en SoftEther VPN Client u OpenVPN Connect.

La app genera el .ovpn desde la API de VPN Gate y lo abre con el cliente
instalado. No implementa el túnel (eso exigiría un driver firmado).
"""
import os
import subprocess
import sys
import time

from . import WindowsNoDisponible, es_windows

RUTAS_SOFTETHER = [
    r"C:\Program Files\SoftEther VPN Client\vpncmgr.exe",
    r"C:\Program Files (x86)\SoftEther VPN Client\vpncmgr.exe",
]
RUTAS_OPENVPN_CONNECT = [
    r"C:\Program Files\OpenVPN Connect\OpenVPNConnect.exe",
    r"C:\Program Files (x86)\OpenVPN Connect\OpenVPNConnect.exe",
]
RUTAS_OPENVPN_GUI = [
    r"C:\Program Files\OpenVPN\bin\openvpn-gui.exe",
]


def clientes_vpn_instalados() -> list[dict]:
    """Clientes VPN conocidos presentes en el equipo.

    v1.0.7: SoftEther se detecta también en la carpeta INCORPORADA
    (junto al .exe de la app, donde lo deja nuestro instalador) y por
    cualquiera de sus nombres de binario (con y sin sufijo _x64); la
    entrada lleva «softether»: True para que la capa de servicios
    use la ruta vpncmd en vez de entregar un .ovpn.
    """
    encontrados = []
    if carpeta_softether():
        encontrados.append({
            "nombre": "SoftEther VPN Client (recomendado por VPN Gate)",
            "ruta": ruta_vpncmgr() or ruta_vpncmd(),
            "softether": True,
        })
    for nombre, rutas in (
        ("OpenVPN Connect", RUTAS_OPENVPN_CONNECT),
        ("OpenVPN GUI (Community)", RUTAS_OPENVPN_GUI),
    ):
        for ruta in rutas:
            if os.path.isfile(ruta):
                encontrados.append({"nombre": nombre, "ruta": ruta})
                break
    return encontrados


def guardar_ovpn(contenido: str, carpeta: str, nombre_archivo: str) -> str:
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, nombre_archivo)
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(contenido)
    return ruta


def abrir_perfil_vpn(ruta_ovpn: str, ruta_cliente: str = "") -> bool:
    """Abre el .ovpn con el cliente elegido (o con la asociación de Windows)."""
    if not es_windows():
        raise WindowsNoDisponible("La delegación VPN se hace en Windows.")
    try:
        if ruta_cliente and os.path.isfile(ruta_cliente):
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen([ruta_cliente, ruta_ovpn], creationflags=flags)
        else:
            os.startfile(ruta_ovpn)  # noqa: S606 - abre el cliente asociado
        return True
    except OSError:
        return False


def ip_publica_actual(timeout: int = 15) -> str:
    """IP pública actual (para enseñar el cambio tras conectar la VPN)."""
    import urllib.request

    try:
        req = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "AntivirusHogarPC"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("ascii", errors="replace").strip()
    except Exception:
        return ""


def procesos_openvpn() -> list[dict]:
    """Procesos del motor OpenVPN en marcha (uno por conexión activa).

    OpenVPN Connect y OpenVPN GUI lanzan un proceso openvpn por túnel:
    si hay alguno, hay una conexión OpenVPN viva. Se lee con psutil
    (multiplataforma); sin psutil o sin permisos, devuelve []."""
    try:
        import psutil
    except ImportError:
        return []
    encontrados = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            nombre = (proc.info.get("name") or "").lower()
        except Exception:
            continue
        if "openvpn" in nombre:
            encontrados.append({"pid": proc.info.get("pid"), "nombre": nombre})
    return encontrados


def hay_tunel_openvpn() -> bool:
    return bool(procesos_openvpn())


def terminar_procesos_openvpn() -> int:
    """Cierra los procesos openvpn: así se apaga el túnel desde la app.

    MECANISMO HONESTO: ni OpenVPN Connect ni OpenVPN GUI ofrecen un
    comando de desconexión limpio para terceros; lo que sí cierra la
    conexión de forma inmediata es terminar su proceso openvpn (el
    cliente lo relanza al volver a conectar). SoftEther VPN Client usa
    su propio servicio y NO se toca: su desconexión se hace en su
    ventana. Devuelve cuántos procesos se cerraron."""
    try:
        import psutil
    except ImportError:
        return 0
    cerrados = 0
    for datos in procesos_openvpn():
        try:
            proc = psutil.Process(datos["pid"])
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
            cerrados += 1
        except Exception:
            continue
    return cerrados


def carpeta_perfiles_vpn() -> str:
    from .. import config

    ruta = os.path.join(config.carpeta_datos(), "vpn")
    os.makedirs(ruta, exist_ok=True)
    return ruta


# --- SoftEther por vpncmd (v1.0.7) -------------------------------------------
# La app maneja el SoftEther INCORPORADO (o uno que el usuario ya
# tuviera) con su herramienta oficial de línea de comandos, vpncmd,
# contra el servicio local del cliente: crea la conexión de VPN Gate,
# la conecta en segundo plano (sin abrir la ventana de SoftEther),
# comprueba el túnel y la desconecta. Los servidores de VPN Gate son
# servidores SoftEther: aceptan la conexión SSL-VPN al hub «VPNGATE»
# por el puerto 443 con usuario y contraseña «vpn» (así lo publica
# el propio proyecto VPN Gate).

NOMBRES_VPNCMD = ("vpncmd.exe", "vpncmd_x64.exe")
NOMBRES_VPNCMGR = ("vpncmgr.exe", "vpncmgr_x64.exe")
CARPETAS_SOFTETHER_FIJAS = (
    r"C:\Program Files\SoftEther VPN Client",
    r"C:\Program Files (x86)\SoftEther VPN Client",
)
CUENTA_VPNGATE = "AntivirusHogarVPN"
NIC_VPNGATE = "VPN"
HUB_VPNGATE = "VPNGATE"
USUARIO_VPNGATE = "vpn"
CONTRASENA_VPNGATE = "vpn"
PUERTO_VPNGATE = 443
# Literal EXACTO que AccountStatusGet imprime con el túnel arriba
# (salidas reales documentadas del cliente 4.x).
_MARCA_CONECTADO = "connection completed (session established)"


def _carpetas_softether_candidatas() -> list[str]:
    carpetas = []
    try:
        base = os.path.dirname(os.path.abspath(sys.executable))
        carpetas.append(os.path.join(base, "softether"))
    except Exception:
        pass
    carpetas.extend(CARPETAS_SOFTETHER_FIJAS)
    return carpetas


def carpeta_softether() -> str:
    """Carpeta de SoftEther (incorporada o instalada), o "" si no hay."""
    for carpeta in _carpetas_softether_candidatas():
        for nombre in NOMBRES_VPNCMD + NOMBRES_VPNCMGR:
            if os.path.isfile(os.path.join(carpeta, nombre)):
                return carpeta
    return ""


def _buscar_binario(nombres) -> str:
    carpeta = carpeta_softether()
    if not carpeta:
        return ""
    for nombre in nombres:
        ruta = os.path.join(carpeta, nombre)
        if os.path.isfile(ruta):
            return ruta
    return ""


def ruta_vpncmd() -> str:
    return _buscar_binario(NOMBRES_VPNCMD)


def ruta_vpncmgr() -> str:
    return _buscar_binario(NOMBRES_VPNCMGR)


def softether_instalado() -> bool:
    """¿Hay un SoftEther manejable por vpncmd (incorporado o propio)?"""
    return bool(ruta_vpncmd())


def _ejecutar_vpncmd(argumentos: list[str], timeout: int = 60) -> tuple[int, str]:
    """Corre `vpncmd localhost /CLIENT /CMD <argumentos>` OCULTO.

    Devuelve (código de salida, salida completa). Si vpncmd no está,
    (-1, ""). Los tests sustituyen esta función por un simulador: es
    la ÚNICA puerta a SoftEther de todo el módulo.
    """
    ruta = ruta_vpncmd()
    if not ruta:
        return -1, ""
    if not es_windows():
        raise WindowsNoDisponible("SoftEther solo se maneja en Windows.")
    try:
        proc = subprocess.run(
            [ruta, "localhost", "/CLIENT", "/CMD", *argumentos],
            capture_output=True, text=True, errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return -2, "vpncmd tardó demasiado en responder."
    except OSError as exc:
        return -1, f"No se pudo ejecutar vpncmd: {exc}"


def _vpncmd_ok(codigo: int, salida: str) -> bool:
    """¿El comando vpncmd terminó bien? (éxito literal o sin error)."""
    bajo = (salida or "").lower()
    if "error code" in bajo or "error occurred" in bajo:
        return False
    if codigo not in (0,):
        return False
    return True


def _linea_error_vpncmd(salida: str) -> str:
    """La línea de error de vpncmd, para el detalle técnico."""
    for linea in (salida or "").splitlines():
        if "error" in linea.lower():
            return linea.strip()
    return (salida or "").strip()[-300:]


def interpretar_estado_cuenta(salida: str) -> bool:
    """¿AccountStatusGet dice que el túnel está ARRIBA?

    El literal del cliente con la sesión establecida es «Connection
    Completed (Session Established)» en la fila «Session Status».
    """
    return _MARCA_CONECTADO in (salida or "").lower()


def _nombres_de_tabla(salida: str, cabeceras: tuple[str, ...]) -> list[str]:
    """Primeras celdas de una tabla de vpncmd (NicList/AccountList).

    Las tablas de vpncmd separan columnas con «|» y traen una fila
    de cabecera y una de guiones: se saltan las cabeceras conocidas
    y las filas de separación.
    """
    nombres = []
    for linea in (salida or "").splitlines():
        if "|" not in linea:
            continue
        primera = linea.split("|", 1)[0].strip()
        if not primera or set(primera) <= set("-+ "):
            continue
        if any(primera.lower().startswith(c) for c in cabeceras):
            continue
        nombres.append(primera)
    return nombres


def _nombres_nic(salida: str) -> list[str]:
    return _nombres_de_tabla(
        salida, ("virtual network adapter name", "name"))


def _nombres_cuentas(salida: str) -> list[str]:
    return _nombres_de_tabla(
        salida, ("vpn connection setting name", "name"))


def estado_softether() -> dict:
    """{"instalado": bool, "conectado": bool, "cuenta": str}."""
    estado = {"instalado": False, "conectado": False,
              "cuenta": CUENTA_VPNGATE}
    if not softether_instalado():
        return estado
    estado["instalado"] = True
    codigo, salida = _ejecutar_vpncmd(
        ["AccountStatusGet", CUENTA_VPNGATE], timeout=30)
    if codigo >= 0 and interpretar_estado_cuenta(salida):
        estado["conectado"] = True
    return estado


def conectar_softether(hostname: str, puerto: int = PUERTO_VPNGATE,
                       hub: str = HUB_VPNGATE,
                       usuario: str = USUARIO_VPNGATE,
                       contrasena: str = CONTRASENA_VPNGATE,
                       espera: int = 45) -> dict:
    """Crea/actualiza la conexión de VPN Gate y la conecta por vpncmd.

    Todo en segundo plano, sin abrir la ventana de SoftEther:
    asegura la tarjeta virtual (NicCreate la primera vez: Windows
    puede enseñar UNA vez su aviso de instalación del driver),
    recrea la cuenta «AntivirusHogarVPN» contra el servidor elegido
    (hub VPNGATE, usuario/contraseña «vpn», como publica VPN Gate),
    la conecta y espera a que AccountStatusGet confirme el túnel.

    Devuelve {"ok", "mensaje", "detalle", "datos"}: el mensaje es la
    frase clara para el usuario; el detalle, la causa técnica.
    """
    hostname = (hostname or "").strip()
    if not hostname:
        return {"ok": False, "mensaje": "Falta el servidor al que conectar.",
                "detalle": "", "datos": {}}
    if not softether_instalado():
        return {"ok": False,
                "mensaje": "SoftEther no está en este equipo.",
                "detalle": "vpncmd no encontrado.", "datos": {}}

    def _fallo(paso: str, salida: str) -> dict:
        return {"ok": False,
                "mensaje": (f"No se pudo conectar con SoftEther ({paso}). "
                            "Revisa tu conexión a internet e inténtalo "
                            "de nuevo; si el servidor no responde, elige "
                            "otro de la lista."),
                "detalle": _linea_error_vpncmd(salida), "datos": {}}

    # 1. Tarjeta virtual: sin ella no hay túnel.
    codigo, salida = _ejecutar_vpncmd(["NicList"], timeout=30)
    if not _vpncmd_ok(codigo, salida):
        return _fallo("no se pudo hablar con el servicio de SoftEther",
                      salida)
    if NIC_VPNGATE.lower() not in [n.lower() for n in _nombres_nic(salida)]:
        codigo, salida = _ejecutar_vpncmd(["NicCreate", NIC_VPNGATE],
                                          timeout=120)
        if not _vpncmd_ok(codigo, salida):
            return _fallo("no se pudo crear la tarjeta virtual de red",
                          salida)
    # 2. Cuenta: se recrea para apuntar al servidor elegido.
    codigo, salida = _ejecutar_vpncmd(["AccountList"], timeout=30)
    if _vpncmd_ok(codigo, salida) and CUENTA_VPNGATE in _nombres_cuentas(salida):
        _ejecutar_vpncmd(["AccountDisconnect", CUENTA_VPNGATE], timeout=30)
        _ejecutar_vpncmd(["AccountDelete", CUENTA_VPNGATE], timeout=30)
    codigo, salida = _ejecutar_vpncmd(
        ["AccountCreate", CUENTA_VPNGATE,
         f"/SERVER:{hostname}:{int(puerto)}", f"/HUB:{hub}",
         f"/USERNAME:{usuario}", f"/NICNAME:{NIC_VPNGATE}"], timeout=30)
    if not _vpncmd_ok(codigo, salida):
        return _fallo("no se pudo crear la conexión", salida)
    codigo, salida = _ejecutar_vpncmd(
        ["AccountPasswordSet", CUENTA_VPNGATE,
         f"/PASSWORD:{contrasena}", "/TYPE:standard"], timeout=30)
    if not _vpncmd_ok(codigo, salida):
        return _fallo("no se pudo fijar la contraseña de la conexión",
                      salida)
    # 3. Conectar y esperar la confirmación del túnel.
    codigo, salida = _ejecutar_vpncmd(["AccountConnect", CUENTA_VPNGATE],
                                      timeout=60)
    if not _vpncmd_ok(codigo, salida):
        return _fallo("el servidor rechazó la conexión", salida)
    limite = time.time() + max(5, int(espera))
    ultimo = ""
    while time.time() < limite:
        codigo, ultimo = _ejecutar_vpncmd(
            ["AccountStatusGet", CUENTA_VPNGATE], timeout=30)
        if codigo >= 0 and interpretar_estado_cuenta(ultimo):
            return {"ok": True,
                    "mensaje": (f"Conectado a {hostname} con SoftEther: "
                                "el túnel está arriba y trabaja en "
                                "segundo plano."),
                    "detalle": "",
                    "datos": {"cuenta": CUENTA_VPNGATE, "nic": NIC_VPNGATE,
                              "hostname": hostname, "via": "softether"}}
        time.sleep(2)
    return {"ok": False,
            "mensaje": ("SoftEther aceptó la orden de conectar, pero el "
                        "túnel no se confirmó a tiempo. El servidor "
                        "puede estar saturado: elige otro de la lista e "
                        "inténtalo de nuevo."),
            "detalle": _linea_error_vpncmd(ultimo), "datos": {}}


def desconectar_softether() -> dict:
    """Baja la conexión de la app por vpncmd (AccountDisconnect)."""
    if not softether_instalado():
        return {"ok": False, "mensaje": "SoftEther no está en este equipo.",
                "detalle": "", "datos": {}}
    codigo, salida = _ejecutar_vpncmd(
        ["AccountDisconnect", CUENTA_VPNGATE], timeout=30)
    if _vpncmd_ok(codigo, salida):
        return {"ok": True,
                "mensaje": "VPN desconectada: SoftEther bajó el túnel.",
                "detalle": "", "datos": {}}
    return {"ok": False,
            "mensaje": "No se pudo desconectar SoftEther desde la app.",
            "detalle": _linea_error_vpncmd(salida), "datos": {}}


_ = sys  # (compatibilidad de imports en empaquetado)
