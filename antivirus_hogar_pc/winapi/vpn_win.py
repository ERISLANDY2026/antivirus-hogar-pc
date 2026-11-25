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

v1.0.11 — LA CAUSA DEL FALLO DE LA 1.0.10, confirmada en la
Toughbook del usuario (INVESTIGACION-VPN-V1010.md, cierre): la
línea `auth-user-pass` con la ruta de credenciales de Windows
que la app añadía al perfil iba con barras SIMPLES, y OpenVPN
2.7.9 las trata dentro de un
parámetro entrecomillado como escapes: al llegar a esa línea (la
221 del perfil) imprime «Bad backslash usage» y TERMINA con error
de uso — antes de abrir su --log-append y antes de cualquier red.
Resultado en la 1.0.10: muerte instantánea con TODOS los
servidores, sin registro, sin detalle técnico, y la app caía en
su mensaje genérico de «servidor apagado o saturado», que era
falso. Esta versión: (1) la ruta va ESCAPADA con barras dobles,
la forma de la documentación oficial; (2) «conectada» SOLO lo
dice la interfaz de gestión (fuera la detección por subcadena de
procesos, que contaba openvpn-gui/openvpnserv como túnel y dio
el «CONECTADA» falso de la foto); (3) la salida de arranque de
openvpn.exe se CAPTURA a un archivo y su código de salida se
guarda: si muere antes de abrir el registro, esa salida ES la
causa y viaja en el detalle; (4) el registro rota por intento
sin borrar el anterior y sus últimas líneas van al detalle y
al registro de actividad.
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


def _filtrar_procesos_openvpn(info_procesos) -> list[dict]:
    """Filtra una lista de infos de proceso a los openvpn.exe REALES.

    v1.0.11: SOLO cuenta el ejecutable del túnel, por nombre EXACTO
    «openvpn.exe». La 1.0.10 contaba cualquier nombre que contuviera
    la subcadena «openvpn» —incluidos openvpn-gui.exe y
    openvpnserv.exe, residentes desde la instalación— y de ahí
    salió el falso «VPN: CONECTADA a un servidor» de la foto del
    usuario: un proceso con «openvpn» en el nombre NO es un túnel.
    """
    encontrados = []
    for info in info_procesos or []:
        try:
            nombre = (info.get("name") or "").lower()
        except Exception:
            continue
        if nombre == "openvpn.exe":
            encontrados.append({"pid": info.get("pid"), "nombre": nombre})
    return encontrados


def procesos_openvpn() -> list[dict]:
    """Procesos openvpn.exe en marcha (el ejecutable del túnel).

    OJO (v1.0.11): que haya un openvpn.exe vivo NO prueba que el
    túnel esté arriba — puede estar conectando o reintentando—;
    sirve para localizar el proceso del motor (p. ej. al
    desconectar o para no actualizar OpenVPN con un túnel en
    curso), nunca como prueba de conexión: eso solo lo dice la
    interfaz de gestión (CONNECTED,SUCCESS). Se lee con psutil;
    sin psutil o sin permisos, devuelve []."""
    try:
        import psutil
    except ImportError:
        return []
    infos = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            infos.append(proc.info)
        except Exception:
            continue
    return _filtrar_procesos_openvpn(infos)


def hay_tunel_openvpn() -> bool:
    """¿Hay un proceso openvpn.exe vivo? (NO «¿hay túnel arriba?»)

    Nombre heredado: lo usan el auto-actualizador de OpenVPN
    (diferir si un túnel PUEDE estar en curso) y la desconexión
    como respaldo. Desde la 1.0.11 ya no cuenta la GUI ni los
    servicios residentes: solo el ejecutable del túnel. El estado
    «conectada» NO se decide aquí: ver estado_openvpn().
    """
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
      VPN Gate). v1.0.11: la ruta va ESCAPADA con barras DOBLES:
      dentro de un parámetro entrecomillado del .ovpn, OpenVPN
      trata la barra simple como escape («Bad backslash usage»)
      y en 2.7.9 eso es un error FATAL de opciones que mata el
      proceso antes de abrir su registro — fue LA causa del fallo
      de la 1.0.10 con todos los servidores. La documentación
      oficial manda barras dobles para rutas Windows en perfiles.
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
    ruta_en_perfil = (ruta_credenciales or "").replace("\\", "\\\\")
    salida.append(f'auth-user-pass "{ruta_en_perfil}"')
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

_SALIDA_ARRANQUE_FH = None  # mango del archivo de salida de arranque


def _lanzar_openvpn(argumentos: list[str], carpeta: str,
                    ruta_salida_arranque: str = ""):
    """Lanza openvpn.exe SIN ventana y devuelve el proceso (Popen).

    v1.0.11: si se pasa `ruta_salida_arranque`, la salida del
    proceso (stdout+stderr) va a ESE archivo en vez de a la nada.
    La 1.0.10 lanzaba con DEVNULL: un openvpn que muere al parsear
    el perfil (antes de abrir su --log-append) no dejaba ni una
    línea en ningún sitio y su causa se perdía para siempre.
    """
    global _SALIDA_ARRANQUE_FH
    if not es_windows():
        raise WindowsNoDisponible("OpenVPN solo se maneja en Windows.")
    destino_out = subprocess.DEVNULL
    destino_err = subprocess.DEVNULL
    if ruta_salida_arranque:
        _cerrar_salida_arranque()
        _SALIDA_ARRANQUE_FH = open(ruta_salida_arranque, "w",
                                   encoding="utf-8", errors="replace")
        destino_out = _SALIDA_ARRANQUE_FH
        destino_err = subprocess.STDOUT
    return subprocess.Popen(
        argumentos, cwd=carpeta,
        stdout=destino_out, stderr=destino_err,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _cerrar_salida_arranque() -> None:
    global _SALIDA_ARRANQUE_FH
    if _SALIDA_ARRANQUE_FH is not None:
        try:
            _SALIDA_ARRANQUE_FH.close()
        except Exception:
            pass
        _SALIDA_ARRANQUE_FH = None


def _leer_salida_arranque(ruta: str) -> str:
    """La salida capturada del arranque de openvpn ("" si no hay)."""
    try:
        with open(ruta, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return ""


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


# Marcas de causa en las líneas de OpenVPN, por PRIORIDAD: un
# «AUTH_FAILED» seguido de «Exiting due to fatal error» debe
# reportar la autenticación, que es lo accionable, no la despedida
# genérica del proceso. v1.0.11: entran el error de OPCIONES (el
# «Bad backslash» de la 1.0.10), el dispositivo DCO y el servicio
# interactivo, que la 1.0.10 no clasificaba y disfrazaba de
# «servidor apagado o saturado».
_PRIORIDADES_CAUSA = (
    "bad backslash", "options error", "auth_failed",
    "cannot open tun/tap", "tun/tap", "tap-windows", "ovpn-dco",
    "data channel offload", "interactive service", "iservice",
    "tls error", "tls handshake", "verify error", "certificate",
    "private key", "connection reset", "connection refused",
    "no route to host", "network is unreachable",
    "cannot resolve", "fatal error", "error")


def _elegir_causa(lineas) -> str:
    """La línea de causa entre unas líneas de OpenVPN (o "")."""
    limpias = [ln.strip() for ln in (lineas or []) if ln and ln.strip()]
    for marca in _PRIORIDADES_CAUSA:
        for linea in limpias:
            if marca in linea.lower():
                return linea[-300:]
    return limpias[-1][-300:] if limpias else ""


def _causa_del_registro(ruta_log: str) -> str:
    """La línea de causa del registro de openvpn (para el detalle)."""
    try:
        with open(ruta_log, "r", encoding="utf-8", errors="replace") as f:
            lineas = [ln.strip() for ln in f if ln.strip()]
    except OSError:
        return ""
    return _elegir_causa(lineas)


def _causa_en_texto(texto: str) -> str:
    """La línea de causa dentro de un texto (la salida de arranque)."""
    return _elegir_causa((texto or "").splitlines())


def _ultimas_lineas(ruta: str, maximo: int = 12,
                    tope: int = 1500) -> str:
    """Las últimas líneas con contenido de un archivo de registro.

    v1.0.11: el detalle de un fallo lleva las últimas líneas
    COMPLETAS del registro (o de la salida de arranque), no una
    sola línea elegida: el contexto es lo que permite diagnosticar.
    """
    try:
        with open(ruta, "r", encoding="utf-8", errors="replace") as f:
            lineas = [ln.rstrip() for ln in f if ln.strip()]
    except OSError:
        return ""
    return "\n".join(lineas[-maximo:])[-tope:]


def _rotar_registro_openvpn(ruta_log: str, conservar: int = 5) -> str:
    """Rota el registro del intento anterior SIN borrarlo (v1.0.11).

    La 1.0.10 borraba openvpn-conexion.log al empezar cada intento:
    si el intento nuevo moría antes de abrir su registro, la causa
    del anterior también desaparecía. Ahora el anterior se renombra
    con fecha/hora (openvpn-conexion-AAAAMMDD-HHMMSS.log) y se
    conservan los `conservar` más recientes. Devuelve la ruta del
    rotado ("" si no había registro que rotar).
    """
    if not os.path.isfile(ruta_log):
        return ""
    carpeta = os.path.dirname(ruta_log)
    sello = time.strftime("%Y%m%d-%H%M%S",
                          time.localtime(os.path.getmtime(ruta_log)))
    destino = os.path.join(carpeta, f"openvpn-conexion-{sello}.log")
    base, contador = destino, 1
    while os.path.exists(destino):
        contador += 1
        destino = f"{base[:-4]}-{contador}.log"
    try:
        os.rename(ruta_log, destino)
    except OSError:
        return ""
    try:
        rotados = sorted(
            (os.path.join(carpeta, n) for n in os.listdir(carpeta)
             if n.startswith("openvpn-conexion-")
             and n.endswith(".log")),
            key=lambda r: os.path.getmtime(r))
        for viejo in rotados[:-conservar] if conservar > 0 else rotados:
            try:
                os.remove(viejo)
            except OSError:
                pass
    except OSError:
        pass
    return destino


def _clasificar_fallo_openvpn(causa: str, codigo_salida,
                              hostname: str) -> tuple[str, str]:
    """(mensaje en español, detalle) para un openvpn que murió solo.

    v1.0.11: el texto «servidor apagado o saturado» SOLO se usa
    para causas reales de red/TLS. Cada familia de causa tiene su
    mensaje honesto, y una causa VACÍA se declara como tal («se
    cerró sin dejar registro, código de salida N») en vez de
    inventar que el servidor está apagado.
    """
    bajo = (causa or "").lower()
    if not bajo:
        return (f"OpenVPN se cerró sin dejar registro (código de "
                f"salida {codigo_salida}). No es que el servidor "
                f"{hostname} esté apagado: el programa se cerró en "
                "este equipo antes de poder anotar su causa; la "
                "salida de su arranque quedó guardada en el registro "
                "de actividad de la app.",
                f"OpenVPN se cerró sin dejar registro; código de "
                f"salida {codigo_salida}.")
    # Las opciones van ANTES que la autenticación: una línea de
    # «Options error» puede mencionar auth-user-pass sin ser un
    # rechazo del servidor.
    if "bad backslash" in bajo or "options error" in bajo \
            or ("option" in bajo and "error" in bajo):
        return ("OpenVPN rechazó el perfil de conexión de este "
                "servidor (error de opciones en el perfil): el fallo "
                "está en el perfil, no en el servidor. La línea real "
                "está en el detalle y en el registro de actividad.",
                causa)
    if "auth" in bajo:
        return ("El servidor rechazó el inicio de sesión "
                "(autenticación): VPN Gate acepta usuario y "
                "contraseña «vpn»; si este servidor pide otra cosa, "
                "elige otro de la lista.", causa)
    if "tun/tap" in bajo or "tap" in bajo or "dco" in bajo \
            or "data channel" in bajo:
        return ("OpenVPN no pudo abrir su tarjeta virtual "
                "(TAP-Windows/DCO). Reinstala la app para repararla: "
                "su instalador vuelve a dejar la tarjeta en su "
                "sitio.", causa)
    if "interactive service" in bajo or "iservice" in bajo \
            or "service" in bajo and "pipe" in bajo:
        return ("OpenVPN no pudo apoyarse en su servicio (OpenVPN "
                "Interactive Service): puede estar parado. Reinicia "
                "el equipo y vuelve a intentarlo; si sigue igual, "
                "reinstala la app para repararlo.", causa)
    if "tls" in bajo or "verify error" in bajo or "certificate" in bajo:
        return (f"El servidor {hostname} cortó la conexión al "
                "comprobar los certificados (error TLS): suele ser "
                "un servidor de VPN Gate caído o saturado; elige "
                "otro de la lista e inténtalo de nuevo.", causa)
    if any(m in bajo for m in ("connection reset", "connection refused",
                               "no route to host",
                               "network is unreachable", "cannot resolve",
                               "timed out")):
        return (f"El servidor {hostname} no respondió o cortó la "
                "conexión. Suele ser un servidor apagado o saturado: "
                "elige otro de la lista e inténtalo de nuevo.", causa)
    return ("OpenVPN se cerró antes de conectar. La causa real "
            "está en el detalle de esta pantalla y en el registro "
            "de actividad de la app.", causa)


def estado_openvpn() -> dict:
    """{"instalado": bool, "conectado": bool, "hostname": str,
    "conectando": bool}.

    v1.0.11: «conectado» SOLO lo dice la interfaz de gestión de la
    sesión (CONNECTED,SUCCESS). La 1.0.10 caía al respaldo
    «proceso vivo + sesión anotada» y, como su detección de
    procesos contaba la GUI y el servicio residente, la pantalla
    decía «CONECTADA a un servidor» sin haber conectado nunca.
    Sin confirmación de la interfaz no hay conectado: la sesión
    en curso se reporta como «conectando» y nada más. Seguro en
    cualquier plataforma: sin OpenVPN o sin sesión, enseguida.
    """
    estado = {"instalado": openvpn_instalado(), "conectado": False,
              "hostname": "", "conectando": False}
    sesion = _leer_sesion() if estado["instalado"] else {}
    if not sesion:
        return estado
    estado["hostname"] = str(sesion.get("hostname") or "")
    estado["conectando"] = sesion.get("estado") == "conectando"
    puerto = sesion.get("puerto")
    if puerto:
        try:
            salida = _mgmt_enviar(int(puerto), "state", timeout=5)
            if interpretar_estado_mgmt(salida)["conectado"]:
                estado["conectado"] = True
                estado["conectando"] = False
                return estado
        except Exception:
            pass
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
    # v1.0.11: el registro del intento anterior NO se borra: rota
    # con fecha/hora (se conservan los últimos 5).
    _rotar_registro_openvpn(ruta_log)
    # v1.0.11: la salida de arranque se captura a un archivo: si
    # openvpn muere antes de abrir su registro (p. ej. un error de
    # opciones al parsear el perfil), ESA salida es la causa.
    ruta_salida = os.path.join(carpeta, "openvpn-arranque.txt")
    puerto = _puerto_libre()
    argumentos = [ruta_exe, "--config", ruta_perfil,
                  "--management", "127.0.0.1", str(puerto),
                  "--log-append", ruta_log]
    try:
        _PROCESO = _lanzar_openvpn(argumentos, carpeta, ruta_salida)
    except Exception as exc:
        return {"ok": False,
                "mensaje": "No se pudo arrancar el motor de OpenVPN.",
                "detalle": str(exc), "datos": {}}
    # La sesión nace «conectando»: solo pasa a «conectada» cuando
    # la interfaz de gestión confirma el túnel (v1.0.11).
    _guardar_sesion({"hostname": hostname, "puerto": puerto,
                     "pid": getattr(_PROCESO, "pid", None),
                     "desde": time.time(), "estado": "conectando"})
    limite = time.time() + max(5, int(espera))
    while time.time() < limite:
        if _PROCESO is not None and _PROCESO.poll() is not None:
            codigo = getattr(_PROCESO, "returncode", None)
            _cerrar_salida_arranque()
            causa = (_causa_del_registro(ruta_log)
                     or _causa_en_texto(_leer_salida_arranque(ruta_salida)))
            ultimas = (_ultimas_lineas(ruta_log)
                       or _ultimas_lineas(ruta_salida))
            mensaje, detalle = _clasificar_fallo_openvpn(
                causa, codigo, hostname)
            if ultimas:
                detalle = ultimas
            _borrar_sesion()
            _PROCESO = None
            return {"ok": False, "mensaje": mensaje,
                    "detalle": detalle,
                    "datos": {"codigo_salida": codigo,
                              "ultimas_lineas": ultimas}}
        try:
            salida = _mgmt_enviar(puerto, "state", timeout=5)
        except Exception:
            salida = ""
        if salida and interpretar_estado_mgmt(salida)["conectado"]:
            _guardar_sesion({"hostname": hostname, "puerto": puerto,
                             "pid": getattr(_PROCESO, "pid", None),
                             "desde": time.time(),
                             "estado": "conectada"})
            return {"ok": True,
                    "mensaje": (f"Conectado a {hostname} con OpenVPN: "
                                "el túnel está arriba y trabaja en "
                                "segundo plano."),
                    "detalle": "",
                    "datos": {"hostname": hostname, "via": "openvpn",
                              "puerto_mgmt": puerto}}
        time.sleep(2)
    # Timeout: v1.0.11 — el proceso NO queda vivo reintentando en
    # segundo plano (la 1.0.10 lo dejaba: túnel huérfano que podía
    # conectar después de que la app ya dijo que falló). Se mata,
    # se borra la sesión y el detalle trae la causa real si la hay.
    codigo = None
    if _PROCESO is not None:
        try:
            _PROCESO.terminate()
            try:
                _PROCESO.wait(timeout=3)
            except Exception:
                _PROCESO.kill()
        except Exception:
            pass
        codigo = getattr(_PROCESO, "returncode", None)
        _PROCESO = None
    _cerrar_salida_arranque()
    _borrar_sesion()
    causa = (_causa_del_registro(ruta_log)
             or _causa_en_texto(_leer_salida_arranque(ruta_salida)))
    ultimas = (_ultimas_lineas(ruta_log)
               or _ultimas_lineas(ruta_salida))
    return {"ok": False,
            "mensaje": ("OpenVPN aceptó la orden de conectar, pero el "
                        "túnel no se confirmó a tiempo. El servidor "
                        "puede estar saturado: elige otro de la lista "
                        "e inténtalo de nuevo."),
            "detalle": ultimas or causa,
            "datos": {"codigo_salida": codigo,
                      "ultimas_lineas": ultimas}}


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
