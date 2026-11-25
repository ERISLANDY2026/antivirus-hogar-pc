"""VPN Gate en Windows: motor OpenVPN (Community) INCORPORADO.

v1.0.10 — CAMBIO DE MOTOR (decisión del usuario, 2026-11-25):
SoftEther quedó descartado. Su controlador de tarjeta virtual
(Neo6, de 2018) es bloqueado por Windows al instalar el dispositivo
(«Error code: 31» de vpncmd) aun con el paquete almacenado en el
DriverStore, el servicio corriendo y la Integridad de memoria
apagada (evidencia: el softether-nic-instalacion.txt de la 1.0.9 en
su Toughbook). El motor pasa a ser **OpenVPN Community**: su
instalador oficial (MSI) lo instala el instalador de la app en
silencio, dejando su servicio interactivo y su tarjeta TAP-Windows
con controladores firmados y aceptados por Windows.

La app maneja OpenVPN EN SEGUNDO PLANO, con la misma experiencia
que tenía con SoftEther: lanza `openvpn.exe` con el perfil .ovpn
del servidor de VPN Gate elegido y lo controla por su INTERFAZ DE
GESTIÓN local (127.0.0.1), sin ventanas ni avisos: cuando el
servicio interactivo de OpenVPN está presente, openvpn.exe le
delega las operaciones con privilegios (rutas y tarjeta) sin pedir
UAC al usuario. El túnel se confirma leyendo el estado real de la
interfaz de gestión («CONNECTED,SUCCESS»), no suponiéndolo.
"""
import os
import re
import socket
import subprocess
import sys
import time

from . import WindowsNoDisponible, es_windows

RUTAS_OPENVPN_CONNECT = [
    r"C:\Program Files\OpenVPN Connect\OpenVPNConnect.exe",
    r"C:\Program Files (x86)\OpenVPN Connect\OpenVPNConnect.exe",
]
RUTAS_OPENVPN_GUI = [
    r"C:\Program Files\OpenVPN\bin\openvpn-gui.exe",
]
RUTAS_OPENVPN_EXE = [
    r"C:\Program Files\OpenVPN\bin\openvpn.exe",
    r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe",
]

USUARIO_VPNGATE = "vpn"
CLAVE_VPNGATE = "vpn"
SERVICIO_INTERACTIVO_OPENVPN = "OpenVPNServiceInteractive"
SERVICIO_OPENVPN = "OpenVPNService"
# Literal del estado de la interfaz de gestión con el túnel arriba.
_MARCA_CONECTADO_MGMT = "CONNECTED,SUCCESS"


def clientes_vpn_instalados() -> list[dict]:
    """Clientes VPN conocidos presentes en el equipo.

    v1.0.10: la primera entrada es el OpenVPN INCORPORADO (el que
    instala la propia app), con «openvpn»: True para que la capa de
    servicios use el motor en segundo plano en vez de entregar un
    .ovpn a una ventana ajena.
    """
    encontrados = []
    ruta = ruta_openvpn_exe()
    if ruta:
        encontrados.append({
            "nombre": "OpenVPN (incluido con la app)",
            "ruta": ruta,
            "openvpn": True,
        })
    for ruta in RUTAS_OPENVPN_GUI:
        if os.path.isfile(ruta):
            encontrados.append(
                {"nombre": "OpenVPN GUI (Community)", "ruta": ruta})
            break
    for ruta in RUTAS_OPENVPN_CONNECT:
        if os.path.isfile(ruta):
            encontrados.append(
                {"nombre": "OpenVPN Connect", "ruta": ruta})
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

    OpenVPN Connect, OpenVPN GUI y el motor de la app lanzan un
    proceso openvpn por túnel: si hay alguno, hay una conexión
    OpenVPN viva. Se lee con psutil (multiplataforma); sin psutil o
    sin permisos, devuelve []."""
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

    MECANISMO HONESTO: los clientes OpenVPN no ofrecen un comando de
    desconexión limpio para terceros; lo que sí cierra la conexión
    de forma inmediata es terminar su proceso openvpn (el cliente
    lo relanza al volver a conectar). La conexión del motor de la
    app se baja antes por su interfaz de gestión
    (desconectar_openvpn); esto queda de respaldo. Devuelve cuántos
    procesos se cerraron."""
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


# --- Motor OpenVPN incorporado (v1.0.10) --------------------------------------
# El instalador oficial de OpenVPN (MSI) queda instalado por el
# instalador de la app en «C:\Program Files\OpenVPN» (su servicio
# interactivo + tarjeta TAP-Windows firmada) y una copia del propio
# MSI viaja junto al .exe de la app, en «openvpn\», para el
# auto-actualizador interno (winapi/openvpn_update.py).
#
# Conexión: la app escribe el perfil del servidor (el .ovpn que
# publica VPN Gate, con las credenciales «vpn»/«vpn» en un archivo
# propio) y lanza openvpn.exe SIN ventana con la interfaz de
# gestión en un puerto local libre. El estado se lee de esa
# interfaz: «CONNECTED,SUCCESS» = túnel arriba de verdad.

_PATRON_INSTALADOR = re.compile(r"OpenVPN-(\d+)\.(\d+)\.(\d+)-I(\d+)-amd64\.msi$")


def carpeta_instalador_openvpn() -> str:
    """Carpeta «openvpn» junto al .exe de la app (el MSI conservado)."""
    try:
        base = os.path.dirname(os.path.abspath(sys.executable))
    except Exception:
        return ""
    return os.path.join(base, "openvpn")


def ruta_instalador_openvpn() -> str:
    """El instalador oficial de OpenVPN conservado junto a la app.

    Si hubiera varios (no debería), manda el de versión mayor por
    el nombre. "" si no hay ninguno (instalación sin el paquete).
    """
    carpeta = carpeta_instalador_openvpn()
    if not carpeta or not os.path.isdir(carpeta):
        return ""
    candidatos = []
    for nombre in os.listdir(carpeta):
        m = _PATRON_INSTALADOR.match(nombre)
        if m:
            candidatos.append(
                (tuple(int(g) for g in m.groups()),
                 os.path.join(carpeta, nombre)))
    if not candidatos:
        return ""
    candidatos.sort()
    return candidatos[-1][1]


def ruta_openvpn_exe() -> str:
    """openvpn.exe del OpenVPN instalado (incorporado o del usuario)."""
    for ruta in RUTAS_OPENVPN_EXE:
        if os.path.isfile(ruta):
            return ruta
    return ""


def openvpn_instalado() -> bool:
    return bool(ruta_openvpn_exe())


def interpretar_version_openvpn(salida: str) -> str:
    """Primera línea de `openvpn --version` → «2.7.9» (o "")."""
    for linea in (salida or "").splitlines():
        m = re.search(r"OpenVPN\s+(\d+\.\d+\.\d+)", linea)
        if m:
            return m.group(1)
    return ""


def version_openvpn() -> str:
    """Versión del openvpn.exe instalado («2.7.9»), o "" si no se sabe."""
    ruta = ruta_openvpn_exe()
    if not ruta:
        return ""
    try:
        proc = subprocess.run(
            [ruta, "--version"], capture_output=True, text=True,
            errors="replace", timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return interpretar_version_openvpn(
            (proc.stdout or "") + (proc.stderr or ""))
    except Exception:
        return ""


def preparar_perfil_vpngate(contenido: str, ruta_credenciales: str) -> str:
    """Prepara el .ovpn de VPN Gate para el motor de la app.

    - Quita las líneas que la app controla (auth-user-pass,
      management, log/log-append) para que no choquen con las suyas.
    - Añade `auth-user-pass` apuntando al archivo de credenciales
      de la app («vpn»/«vpn», lo que aceptan los servidores de
      VPN Gate).
    - Si el perfil fija un `cipher` y no trae `data-ciphers`,
      añade `data-ciphers-fallback` con ese cifrado: en OpenVPN
      2.5+ el `cipher` antiguo quedó en desuso y sin el respaldo
      la negociación con servidores viejos de VPN Gate puede
      fallar. No se toca nada más del perfil.
    """
    salida = []
    cifrado = ""
    trae_data_ciphers = False
    for linea in (contenido or "").splitlines():
        limpia = linea.strip()
        baja = limpia.lower()
        if baja.startswith(("auth-user-pass", "management ",
                            "management-", "log ", "log-append ")):
            continue
        if baja.startswith("cipher "):
            partes = limpia.split(None, 1)
            if len(partes) == 2:
                cifrado = partes[1].strip()
        if baja.startswith("data-ciphers"):
            trae_data_ciphers = True
        salida.append(linea.rstrip())
    while salida and not salida[-1].strip():
        salida.pop()
    salida.append(f'auth-user-pass "{ruta_credenciales}"')
    if cifrado and not trae_data_ciphers:
        salida.append(f"data-ciphers-fallback {cifrado}")
    return "\n".join(salida) + "\n"


# --- Sesión del motor (qué conexión lanzó la app) ------------------------------

_PROCESO = None  # Popen de la conexión viva lanzada por la app


def _ruta_sesion() -> str:
    return os.path.join(carpeta_perfiles_vpn(), "openvpn_sesion.json")


def _guardar_sesion(datos: dict) -> None:
    import json as _json

    try:
        with open(_ruta_sesion(), "w", encoding="utf-8") as f:
            _json.dump(datos, f, ensure_ascii=False)
    except OSError:
        pass


def _leer_sesion() -> dict:
    import json as _json

    try:
        with open(_ruta_sesion(), "r", encoding="utf-8") as f:
            datos = _json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _borrar_sesion() -> None:
    try:
        os.remove(_ruta_sesion())
    except OSError:
        pass


def _puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


# --- Puertas únicas a proceso y a la interfaz de gestión -----------------------
# Los tests las sustituyen: son la ÚNICA vía del motor a openvpn.exe
# y a su interfaz de gestión.

def _lanzar_openvpn(argumentos: list[str], carpeta: str):
    """Lanza openvpn.exe SIN ventana y devuelve el proceso (Popen)."""
    if not es_windows():
        raise WindowsNoDisponible("OpenVPN solo se maneja en Windows.")
    return subprocess.Popen(
        argumentos, cwd=carpeta,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _mgmt_enviar(puerto: int, comando: str, timeout: int = 10) -> str:
    """Envía un comando a la interfaz de gestión y lee su respuesta.

    La respuesta de `state` termina en una línea «END». Las
    notificaciones en tiempo real llegan como líneas «>STATE:…» y
    también se recogen: el llamante interpreta el conjunto.
    """
    with socket.create_connection(("127.0.0.1", int(puerto)),
                                  timeout=timeout) as sock:
        sock.settimeout(timeout)
        datos = b""
        # Saludo inicial de la interfaz (línea >INFO:…).
        try:
            while b"\n" not in datos:
                trozo = sock.recv(4096)
                if not trozo:
                    break
                datos += trozo
        except socket.timeout:
            pass
        sock.sendall((comando.strip() + "\r\n").encode("ascii"))
        respuesta = b""
        limite = time.time() + timeout
        while time.time() < limite:
            try:
                trozo = sock.recv(4096)
            except socket.timeout:
                break
            if not trozo:
                break
            respuesta += trozo
            texto = respuesta.decode("utf-8", errors="replace")
            if comando.strip().lower() == "state" and (
                    "\nEND" in texto or texto.rstrip().endswith("END")):
                break
            if comando.strip().lower() != "state" and len(respuesta) > 0:
                break
        return (datos + respuesta).decode("utf-8", errors="replace")


def interpretar_estado_mgmt(salida: str) -> dict:
    """Salida de `state` → {"conectado", "estado", "ip_local"}.

    La línea de estado es «<tiempo>,<ESTADO>,<detalle>,<ip local>,
    <ip remota>,…»; con el túnel arriba: «…,CONNECTED,SUCCESS,…».
    Las notificaciones «>STATE:» llevan la misma línea tras el
    prefijo. Sin línea de estado: conectado=False, estado="".
    """
    estado = ""
    ip_local = ""
    for linea in (salida or "").splitlines():
        texto = linea.strip()
        if texto.startswith(">STATE:"):
            texto = texto[len(">STATE:"):]
        partes = texto.split(",")
        if len(partes) >= 3 and partes[0].strip().isdigit():
            estado = partes[1].strip().upper()
            if len(partes) >= 4:
                ip_local = partes[3].strip()
    return {"conectado": estado == "CONNECTED"
            and _MARCA_CONECTADO_MGMT in (salida or "").upper(),
            "estado": estado, "ip_local": ip_local}


def _causa_del_registro(ruta_log: str) -> str:
    """La línea de causa del registro de openvpn (para el detalle).

    Busca por PRIORIDAD de causa, de la más específica a la más
    genérica (autenticación, tarjeta TAP, TLS, red, error fatal):
    un «AUTH_FAILED» seguido de «Exiting due to fatal error» debe
    reportar la autenticación, que es lo accionable, no la
    despedida genérica del proceso. Si ninguna marca aparece, la
    última línea con contenido del registro.
    """
    try:
        with open(ruta_log, "r", encoding="utf-8", errors="replace") as f:
            lineas = [ln.strip() for ln in f if ln.strip()]
    except OSError:
        return ""
    prioridades = ("auth_failed", "cannot open tun/tap", "tun/tap",
                   "tls error", "tls handshake", "certificate",
                   "private key", "connection reset", "no route to host",
                   "network is unreachable", "fatal error", "error")
    for marca in prioridades:
        for linea in lineas:
            if marca in linea.lower():
                return linea[-300:]
    return lineas[-1][-300:] if lineas else ""


def estado_openvpn() -> dict:
    """{"instalado": bool, "conectado": bool, "hostname": str}.

    «conectado» es REAL: la interfaz de gestión de la sesión de la
    app dice CONNECTED,SUCCESS, o (si la app se reabrió y perdió el
    control de la interfaz) hay un proceso openvpn vivo y una
    sesión anotada. Seguro en cualquier plataforma: sin OpenVPN o
    sin sesión devuelve enseguida.
    """
    estado = {"instalado": openvpn_instalado(), "conectado": False,
              "hostname": ""}
    sesion = _leer_sesion() if estado["instalado"] else {}
    if not sesion:
        return estado
    estado["hostname"] = str(sesion.get("hostname") or "")
    puerto = sesion.get("puerto")
    if puerto:
        try:
            salida = _mgmt_enviar(int(puerto), "state", timeout=5)
            if interpretar_estado_mgmt(salida)["conectado"]:
                estado["conectado"] = True
                return estado
        except Exception:
            pass
    # Respaldo: proceso vivo + sesión anotada (la app se reabrió).
    if hay_tunel_openvpn():
        estado["conectado"] = True
    return estado


def conectar_openvpn(contenido_ovpn: str, hostname: str,
                     espera: int = 45) -> dict:
    """Conecta con un servidor de VPN Gate por el motor OpenVPN.

    Todo en segundo plano, sin abrir ninguna ventana de OpenVPN:
    escribe el perfil preparado y las credenciales, lanza
    openvpn.exe oculto con la interfaz de gestión en un puerto
    local y espera a que el estado confirme el túnel
    (CONNECTED,SUCCESS). Si openvpn muere por el camino o el túnel
    no se confirma a tiempo, el detalle trae la causa REAL de su
    registro, no un texto inventado.

    Devuelve {"ok", "mensaje", "detalle", "datos"}.
    """
    global _PROCESO
    hostname = (hostname or "").strip()
    if not hostname:
        return {"ok": False, "mensaje": "Falta el servidor al que conectar.",
                "detalle": "", "datos": {}}
    ruta_exe = ruta_openvpn_exe()
    if not ruta_exe:
        return {"ok": False,
                "mensaje": "OpenVPN no está en este equipo.",
                "detalle": "openvpn.exe no encontrado.", "datos": {}}
    if not (contenido_ovpn or "").strip():
        return {"ok": False,
                "mensaje": "El servidor no trajo su perfil de conexión "
                           "(.ovpn): elige otro de la lista.",
                "detalle": "", "datos": {}}
    carpeta = carpeta_perfiles_vpn()
    ruta_cred = os.path.join(carpeta, "vpngate-credenciales.txt")
    with open(ruta_cred, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{USUARIO_VPNGATE}\n{CLAVE_VPNGATE}\n")
    ruta_perfil = os.path.join(carpeta, "vpngate-activo.ovpn")
    with open(ruta_perfil, "w", encoding="utf-8", newline="\n") as f:
        f.write(preparar_perfil_vpngate(contenido_ovpn, ruta_cred))
    ruta_log = os.path.join(carpeta, "openvpn-conexion.log")
    try:
        os.remove(ruta_log)  # nunca leer la causa de un intento viejo
    except OSError:
        pass
    puerto = _puerto_libre()
    argumentos = [ruta_exe, "--config", ruta_perfil,
                  "--management", "127.0.0.1", str(puerto),
                  "--log-append", ruta_log]
    try:
        _PROCESO = _lanzar_openvpn(argumentos, carpeta)
    except Exception as exc:
        return {"ok": False,
                "mensaje": "No se pudo arrancar el motor de OpenVPN.",
                "detalle": str(exc), "datos": {}}
    _guardar_sesion({"hostname": hostname, "puerto": puerto,
                     "pid": getattr(_PROCESO, "pid", None),
                     "desde": time.time()})
    limite = time.time() + max(5, int(espera))
    while time.time() < limite:
        if _PROCESO is not None and _PROCESO.poll() is not None:
            causa = _causa_del_registro(ruta_log)
            _borrar_sesion()
            bajo = causa.lower()
            if "auth" in bajo:
                return {"ok": False,
                        "mensaje": ("El servidor rechazó el inicio de "
                                    "sesión (autenticación): VPN Gate "
                                    "acepta usuario y contraseña «vpn»; "
                                    "si este servidor pide otra cosa, "
                                    "elige otro de la lista."),
                        "detalle": causa, "datos": {}}
            if "tun/tap" in bajo or "tap" in bajo:
                return {"ok": False,
                        "mensaje": ("OpenVPN no pudo abrir su tarjeta "
                                    "virtual (TAP-Windows). Reinstala "
                                    "la app para repararla: su "
                                    "instalador vuelve a dejar la "
                                    "tarjeta en su sitio."),
                        "detalle": causa, "datos": {}}
            return {"ok": False,
                    "mensaje": (f"El servidor {hostname} no respondió o "
                                "cortó la conexión. Suele ser un "
                                "servidor apagado o saturado: elige "
                                "otro de la lista e inténtalo de nuevo."),
                    "detalle": causa, "datos": {}}
        try:
            salida = _mgmt_enviar(puerto, "state", timeout=5)
        except Exception:
            salida = ""
        if salida and interpretar_estado_mgmt(salida)["conectado"]:
            return {"ok": True,
                    "mensaje": (f"Conectado a {hostname} con OpenVPN: "
                                "el túnel está arriba y trabaja en "
                                "segundo plano."),
                    "detalle": "",
                    "datos": {"hostname": hostname, "via": "openvpn",
                              "puerto_mgmt": puerto}}
        time.sleep(2)
    causa = _causa_del_registro(ruta_log)
    return {"ok": False,
            "mensaje": ("OpenVPN aceptó la orden de conectar, pero el "
                        "túnel no se confirmó a tiempo. El servidor "
                        "puede estar saturado: elige otro de la lista "
                        "e inténtalo de nuevo."),
            "detalle": causa, "datos": {}}


def desconectar_openvpn() -> dict:
    """Baja la conexión del motor por su interfaz de gestión.

    Orden limpia primero (signal SIGTERM a la interfaz); si el
    proceso no responde o la app se había reabierto, se termina el
    proceso openvpn de la sesión (mecanismo de respaldo honesto).
    """
    global _PROCESO
    sesion = _leer_sesion()
    puerto = sesion.get("puerto")
    senal_enviada = False
    if puerto:
        try:
            _mgmt_enviar(int(puerto), "signal SIGTERM", timeout=5)
            senal_enviada = True
        except Exception:
            senal_enviada = False
    if _PROCESO is not None:
        try:
            _PROCESO.wait(timeout=8)
        except Exception:
            try:
                _PROCESO.terminate()
            except Exception:
                pass
        _PROCESO = None
    elif senal_enviada:
        # Sin mango del proceso (app reabierta): dar tiempo a que
        # la señal baje el túnel y comprobar; si sigue vivo, respaldo.
        for _ in range(4):
            if not hay_tunel_openvpn():
                break
            time.sleep(1)
    if hay_tunel_openvpn():
        terminar_procesos_openvpn()
    _borrar_sesion()
    return {"ok": True,
            "mensaje": "VPN desconectada: OpenVPN bajó el túnel.",
            "detalle": "", "datos": {}}


# --- Servicios y tarjeta (diagnóstico y re-sincronización) ---------------------

def interpretar_sc_query(salida: str) -> dict:
    """Salida de `sc query <servicio>` → {"registrado", "corriendo"}.

    Sin servicio, sc devuelve error 1060 («The specified service
    does not exist» / «no existe el servicio especificado»).
    """
    texto = salida or ""
    bajo = texto.lower()
    if "1060" in texto or "does not exist" in bajo or "no existe" in bajo:
        return {"registrado": False, "corriendo": False}
    return {"registrado": True,
            "corriendo": "running" in bajo or "en ejecución" in bajo
                         or "ejecutando" in bajo}


def interpretar_sc_qc(salida: str) -> dict:
    """Salida de `sc qc <servicio>` → {"inicio": auto|manual|desactivado|""}."""
    bajo = (salida or "").lower()
    if "auto_start" in bajo or "inicio automático" in bajo \
            or "inicio automatico" in bajo:
        inicio = "auto"
    elif "disabled" in bajo or "desactivado" in bajo:
        inicio = "desactivado"
    elif "demand_start" in bajo or "inicio manual" in bajo:
        inicio = "manual"
    else:
        inicio = ""
    return {"inicio": inicio}


def estado_servicio(nombre: str) -> dict:
    """¿El servicio está registrado y cómo está?

    {"registrado": bool|None, "corriendo": bool, "inicio": str}
    registrado=None si ni siquiera se pudo consultar (no Windows).
    """
    from .powershell import ejecutar_comando

    estado = {"registrado": None, "corriendo": False, "inicio": ""}
    try:
        _rc, out, err = ejecutar_comando(["sc", "query", nombre],
                                         timeout=30)
        estado.update(interpretar_sc_query(out + err))
        if estado["registrado"]:
            _rc, out, err = ejecutar_comando(["sc", "qc", nombre],
                                             timeout=30)
            estado.update(interpretar_sc_qc(out + err))
    except Exception:
        pass
    return estado


def interpretar_adaptadores_tap(salida: str) -> bool:
    """¿La lista de adaptadores (Get-NetAdapter) trae la TAP-Windows?

    La tarjeta del OpenVPN comunitario se describe como «TAP-Windows
    Adapter V9» (tap-windows6) —y en instalaciones con DCO puede
    aparecer además «OpenVPN Data Channel Offload»—: basta que la
    salida nombre TAP-Windows u OpenVPN en una descripción.
    """
    bajo = (salida or "").lower()
    return "tap-windows" in bajo or "openvpn" in bajo


def hay_tap_windows() -> bool:
    """¿La tarjeta virtual de OpenVPN está presente en el equipo?"""
    from .powershell import ejecutar_powershell

    try:
        salida = ejecutar_powershell(
            "Get-NetAdapter | ForEach-Object { "
            "$_.Name + '|' + $_.InterfaceDescription }",
            timeout=30)
    except Exception:
        return False
    return interpretar_adaptadores_tap(salida)


def diagnostico_openvpn() -> dict:
    """Mini-diagnóstico de integración del motor OpenVPN.

    Reúne la evidencia de que el OpenVPN incorporado está bien
    integrado: openvpn.exe localizado en su ruta real, su versión,
    el servicio interactivo registrado, la tarjeta TAP presente y
    si hay túnel. No conecta nada: solo comprueba.
    """
    diag = {"instalado": False, "ruta_exe": "", "version": "",
            "servicio": {}, "tap": None, "conectado": False,
            "instalador_conservado": ""}
    diag["ruta_exe"] = ruta_openvpn_exe()
    diag["instalado"] = bool(diag["ruta_exe"])
    diag["instalador_conservado"] = ruta_instalador_openvpn()
    if not diag["instalado"]:
        return diag
    diag["version"] = version_openvpn()
    diag["servicio"] = estado_servicio(SERVICIO_INTERACTIVO_OPENVPN)
    try:
        diag["tap"] = hay_tap_windows()
    except Exception:
        diag["tap"] = None
    diag["conectado"] = estado_openvpn()["conectado"]
    return diag


_ = sys  # (compatibilidad de imports en empaquetado)
