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

v1.0.12 — LA PRUEBA DE LA 1.0.11 EN LA TOUGHBOOK (investigación,
sección «PRUEBA v1.0.11»): el perfil ya parsea y el túnel llega a
«Initialization Sequence Completed», pero la app lanzaba
openvpn.exe por Popen SIN privilegios y SIN el Interactive
Service: Windows negó las rutas del redirect-gateway
(«route addition failed using CreateIpForwardEntry: Access is
denied», status=5) y el túnel quedó abierto pero inútil. Ese
fallo de rutas NO es fatal para OpenVPN, y el intento dejó un
openvpn.exe HUÉRFANO vivo sujetando la tarjeta TAP (confirmado
por el usuario en el Administrador de tareas): conectar_openvpn
no tenía try/finally ni guarda de un solo intento. Y el
clasificador convirtió una línea INFORMATIVA del adaptador en
el titular falso «no pudo abrir su tarjeta virtual… reinstala
la app». Esta versión: (1) openvpn se lanza a través del
**OpenVPN Interactive Service** (el tubo
``\\.\\pipe\\openvpn\\service``: el servicio, con privilegios de
sistema, ejecuta las operaciones privilegiadas —rutas, IP,
DNS— y openvpn sigue corriendo como el usuario), con reserva
ELEVADA (runas) si el servicio no responde o no autoriza;
(2) el instalador deja al usuario en el grupo «OpenVPN
Administrators» (sin eso el servicio rechaza perfiles fuera de
su carpeta) y la puerta previa detecta si la sesión aún no
refleja la pertenencia (cierre de sesión pendiente) y ofrece la
reserva elevada para ese intento; (3) UN solo intento a la vez,
limpieza garantizada con try/finally, barrido previo de
huérfanos PROPIOS (los ajenos no se tocan) y verificación
post-cierre (proceso muerto + adaptador libre); (4)
clasificador nuevo: las líneas informativas nunca son causa,
la familia «rutas/privilegios» va antes que la de adaptador, y
«Initialization Completed» con rutas fallidas se reporta como
lo que es: túnel abierto pero sin rutas.

v1.0.13 — LA PRUEBA DE LA 1.0.12 EN LA TOUGHBOOK (investigación,
sección «PRUEBA v1.0.12»): tres intentos reales (12:44, 12:48 y
12:50) murieron EN SU PRIMER SEGUNDO con «MANAGEMENT: CMD
'signal SIGTERM'» en su propio registro, y la auditoría probó
que el SIGTERM lo enviaba la propia app: el servicio lanza
openvpn ELEVADO y la app, sin elevar, no siempre puede
inspeccionar ese proceso (permiso denegado); la comprobación de
vida de la 1.0.12 colapsaba «no pude mirarlo» en «está muerto»,
así que el bucle declaraba muerto a un OpenVPN vivo en la
primera vuelta y el finally lo apagaba por gestión — con un
«código de salida 0» fabricado encima. El titular culpó al TLS
porque la advertencia rutinaria «No server certificate
verification method…» trae la palabra «certificate», marca de
esa familia; y el detalle pintó el registro fósil de las 11:31
porque caía a openvpn-arranque.txt, un archivo que la 1.0.12 ya
no escribe. Esta versión: (1) vida en TRES estados —vivo,
muerto, NO COMPROBABLE— y «no comprobable» jamás cuenta como
muerte ni dispara limpieza: la muerte exige DOS pruebas
positivas, una de ellas el silencio de la propia interfaz de
gestión; (2) si la app detiene un intento sin muerte probada
(timeout, cierre), el resultado lo dice tal cual («la app
detuvo el intento») en vez de disfrazarlo de fallo del
servidor, y el código de salida solo se pinta si se leyó del
proceso real — nunca un 0 fabricado; (3) el detalle sale SOLO
del registro de ESTE intento (prohibido el respaldo al archivo
fósil): si aún no hay registro, el detalle dice «sin registro
todavía»; (4) el clasificador gana la familia prioritaria
«detenido por la app» (un registro que termina en SIGTERM por
gestión lo detuvo la app, no el servidor) y la familia TLS
exige un error TLS real: las advertencias rutinarias de
arranque quedan marcadas como informativas expresas y la
palabra suelta «certificate» ya no es marca de TLS; (5) la
puerta previa manda de verdad: conectar honra la vía que la
puerta decidió (servicio o elevado) y cada intento anota en el
registro de actividad la vía, el aviso de la puerta y el primer
sondeo, para que el próximo fallo se diagnostique sin fotos.

v1.0.14 — LISTA UNIFICADA Y SONDA (investigaciones del
2026-11-25): (1) las credenciales ya NO son fijas de VPN Gate:
conectar recibe las de la FUENTE del servidor (VPN Gate
«vpn»/«vpn»; VPNBook «vpnbook» + la contraseña vigente leída de
su página), porque la lista ahora mezcla fuentes
(core.fuentes_vpn); (2) MODO SONDA (`sonda=True`): el perfil
lleva `route-nopull` (la sonda nunca secuestra el tráfico del
usuario) y el éxito es la ACEPTACIÓN del servidor —el
PUSH_REPLY del registro o el CONNECTED,SUCCESS de la gestión—,
tras lo cual el intento se baja al instante: es la prueba real
de «este servidor funciona» del autoanálisis, la única que
distingue un nodo sano de uno lleno (esos pasan el TLS y
rechazan en la autenticación, AUTH_FAILED); (3) cada resultado
de fallo trae datos["familia"] (la familia del clasificador):
el failover de la capa de servicios salta al siguiente
candidato SOLO ante familias del servidor.
"""
import atexit
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
# v1.0.12: el tubo del Interactive Service y el grupo local que
# autoriza a usarlo con perfiles fuera de su carpeta de
# configuración (documentación oficial del Interactive Service).
TUBO_SERVICIO_OPENVPN = r"\\.\pipe\openvpn\service"
GRUPO_ADMIN_OPENVPN = "OpenVPN Administrators"
# Códigos propios del Interactive Service (además de los Win32).
ERRORES_SERVICIO_OPENVPN = {
    0x20000000: "el servicio no pudo arrancar OpenVPN",
    0x20000001: "el servicio rechazó los datos de arranque",
    0x20000002: "el servicio rechazó los datos del mensaje",
    0x20000003: "el servicio rechazó el tipo de mensaje",
}
# Nombre del perfil que la app escribe para el servidor elegido:
# es la marca que distingue a NUESTROS openvpn.exe de los ajenos.
NOMBRE_PERFIL_ACTIVO = "vpngate-activo.ovpn"
_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


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
    return [{"pid": d["pid"], "nombre": d["nombre"]}
            for d in _procesos_openvpn_detalle()]


def _procesos_openvpn_detalle() -> list[dict]:
    """openvpn.exe vivos CON su línea de comandos (v1.0.12).

    La línea de comandos es lo que permite distinguir un proceso
    PROPIO (lanzado con nuestro vpngate-activo.ovpn) de uno AJENO
    (el OpenVPN GUI del usuario con su perfil): el barrido de
    huérfanos solo puede cerrar los propios. Sin psutil o sin
    permiso para leer la línea, «cmdline» queda "".
    """
    try:
        import psutil
    except ImportError:
        return []
    infos = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            info = dict(proc.info)
        except Exception:
            continue
        if (info.get("name") or "").lower() != "openvpn.exe":
            continue
        try:
            info["cmdline"] = " ".join(proc.cmdline())
        except Exception:
            info["cmdline"] = ""
        infos.append(info)
    cmdlines = {i.get("pid"): i.get("cmdline", "") for i in infos}
    detalle = []
    for info in _filtrar_procesos_openvpn(infos):
        detalle.append({"pid": info["pid"], "nombre": info["nombre"],
                        "cmdline": cmdlines.get(info["pid"], "")})
    return detalle


def _es_proceso_propio(info: dict, pids_propios=()) -> bool:
    """¿Este openvpn.exe es de ESTA app? (v1.0.12)

    Propio si su PID consta en una sesión de la app o si su línea
    de comandos trae nuestro perfil (vpngate-activo.ovpn). Un
    openvpn ajeno (otro perfil, el GUI del usuario) NUNCA es
    propio: no se cierra, se avisa.
    """
    try:
        if info.get("pid") in set(pids_propios or ()):
            return True
    except Exception:
        pass
    return NOMBRE_PERFIL_ACTIVO in (info.get("cmdline") or "")


def _anotar_actividad_vpn(texto: str) -> None:
    """Anota un hecho del motor VPN en actividad.jsonl (v1.0.12).

    El barrido de huérfanos y la verificación post-cierre pasan
    aquí, en el motor: sin esta anotación, un proceso cerrado por
    la app no dejaría rastro en ningún sitio. Nunca rompe nada.
    """
    try:
        from .. import config as _config
        from ..core.actividad import RegistroActividad

        RegistroActividad(_config.ruta_actividad()).registrar(
            "red", texto)
    except Exception:
        pass


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


def preparar_perfil_vpngate(contenido: str, ruta_credenciales: str,
                            lineas_extra=()) -> str:
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
    - v1.0.14: `lineas_extra` añade directivas al final (la sonda
      pasa «route-nopull» para no tocar el tráfico del usuario).
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
    for extra in lineas_extra or ():
        if str(extra).strip():
            salida.append(str(extra).strip())
    return "\n".join(salida) + "\n"


# --- Sesión del motor (qué conexión lanzó la app) ------------------------------

_PROCESO = None  # Popen de la conexión viva lanzada por la app
# v1.0.13: la vía que la puerta previa decidió para el intento
# en curso ("servicio" | "elevado" | "" = orden por defecto).
# conectar_openvpn la fija antes de lanzar y _lanzar_openvpn la
# honra: en la 1.0.12 la puerta calculaba la vía pero el motor
# siempre probaba el servicio primero.
_VIA_PREFERIDA = ""


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


# --- v1.0.12: lanzamiento por el Interactive Service (y reserva elevada) -------
#
# La documentación oficial del Interactive Service describe el
# protocolo del tubo \\.\pipe\openvpn\service: el cliente (como
# usuario normal) le envía UN mensaje de arranque —tres cadenas
# UTF-16 terminadas en nulo: directorio de trabajo, opciones sin
# argv[0] y stdin— en UNA sola escritura; el servicio valida al
# usuario (el perfil debe estar en su carpeta de configuración o
# el usuario debe ser administrador o estar en el grupo
# «OpenVPN Administrators»), lanza openvpn.exe COMO EL USUARIO
# conservando un tubo de servicio con él, y responde con un
# mensaje de tres cadenas UTF-16 separadas por LF: si el código
# es 0, la segunda trae el PID («0x»+hex) y la tercera dice
# «Process ID»; si no, es un error (código Win32 o propio del
# servicio, 0x20000000+), con la función que falló y su texto.

class _ErrorServicioOpenVPN(Exception):
    """El Interactive Service (o la reserva elevada) no lanzó
    openvpn. Lleva el código (Win32 o propio del servicio) para
    poder enseñar la causa sin disfrazarla."""

    def __init__(self, mensaje: str, codigo=None):
        super().__init__(mensaje)
        self.codigo = codigo


def _mensaje_arranque_servicio(carpeta_trabajo: str, opciones: str,
                               stdin: str = "") -> bytes:
    """El mensaje de arranque del tubo, byte a byte (v1.0.12)."""
    texto = ((carpeta_trabajo or "") + "\0" + (opciones or "") + "\0"
             + (stdin or "") + "\0")
    return texto.encode("utf-16-le")


def _opciones_desde_argumentos(argumentos) -> str:
    """Argumentos sin argv[0] → la cadena de opciones del servicio.

    Se entrecomillan como en la línea de comandos de Windows
    (subprocess.list2cmdline): las rutas con espacios («NEW
    USER», «Program Files») sobreviven al parseo del servicio.
    """
    return subprocess.list2cmdline(
        [str(a) for a in (argumentos or [])[1:]])


def _interpretar_respuesta_servicio(datos: bytes) -> dict:
    """Respuesta del tubo → {"ok", "pid", "codigo", "funcion",
    "mensaje"} (formato oficial de tres cadenas separadas por LF).
    """
    texto = (datos or b"").decode("utf-16-le", errors="replace")
    partes = [p.strip().strip("\x00")
              for p in texto.replace("\r\n", "\n").split("\n")]
    partes = [p for p in partes if p != ""]
    if len(partes) < 3:
        return {"ok": False, "pid": None, "codigo": None,
                "funcion": "", "mensaje": texto.strip()}
    try:
        codigo = int(partes[0], 16)
    except ValueError:
        return {"ok": False, "pid": None, "codigo": None,
                "funcion": "", "mensaje": texto.strip()}
    if codigo == 0:
        try:
            pid = int(partes[1], 16)
        except ValueError:
            pid = None
        return {"ok": pid is not None, "pid": pid, "codigo": 0,
                "funcion": "", "mensaje": partes[2]}
    return {"ok": False, "pid": None, "codigo": codigo,
            "funcion": partes[1], "mensaje": "\n".join(partes[2:])}


def _estado_pid_con_error(pid) -> tuple:
    """El estado de un PID: ("vivo"|"muerto"|"no_comprobable",
    error_de_windows|None). v1.0.13.

    La 1.0.12 colapsaba TODO fallo de inspección en «no vivo» y
    el bucle declaraba muerto a un openvpn ELEVADO que la app no
    podía ni mirar (OpenProcess denegado): la propia app lo
    apagaba por gestión en su primer segundo. Ahora «no
    comprobable» es un estado propio y JAMÁS cuenta como
    muerte: «muerto» solo sale de una prueba positiva — el
    código de salida leído de verdad (distinto de STILL_ACTIVE)
    o un OpenProcess que falla porque ese PID NO EXISTE
    (ERROR_INVALID_PARAMETER, 87). El acceso denegado (5) y
    cualquier otro fallo de inspección son «no_comprobable» y
    el error viaja para poder anotarlo.
    """
    if not pid:
        return ("no_comprobable", None)
    if es_windows():
        try:
            import ctypes

            kernel32 = _kernel32()
            kernel32.OpenProcess.restype = ctypes.c_void_p
            handle = kernel32.OpenProcess(0x1000, False, int(pid))
            if not handle:
                error = kernel32.GetLastError()
                if error == 87:  # ERROR_INVALID_PARAMETER
                    return ("muerto", error)
                return ("no_comprobable", error)
            try:
                codigo = ctypes.c_ulong(0)
                if not kernel32.GetExitCodeProcess(
                        handle, ctypes.byref(codigo)):
                    return ("no_comprobable",
                            kernel32.GetLastError())
                if codigo.value == 259:  # STILL_ACTIVE
                    return ("vivo", None)
                return ("muerto", None)
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return ("no_comprobable", None)
    try:
        import psutil

        return ("vivo" if psutil.pid_exists(int(pid))
                else "muerto", None)
    except Exception:
        return ("no_comprobable", None)


def _estado_pid(pid) -> str:
    """«vivo» | «muerto» | «no_comprobable» (v1.0.13)."""
    return _estado_pid_con_error(pid)[0]


def _pid_vivo(pid) -> bool:
    """True SOLO con prueba positiva de vida (v1.0.13).

    Compatibilidad: un False aquí significa «muerto O no
    comprobable» — NUNCA usarlo para declarar una muerte; para
    eso está _estado_pid, que distingue los tres estados.
    """
    return _estado_pid(pid) == "vivo"


def _codigo_salida_pid(pid):
    """El código de salida REAL de un proceso terminado (o None
    si no se pudo leer: jamás se fabrica un 0)."""
    if not pid or not es_windows():
        return None
    try:
        import ctypes

        kernel32 = _kernel32()
        kernel32.OpenProcess.restype = ctypes.c_void_p
        handle = kernel32.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return None
        try:
            codigo = ctypes.c_ulong(0)
            if not kernel32.GetExitCodeProcess(
                    handle, ctypes.byref(codigo)):
                return None
            if codigo.value == 259:  # STILL_ACTIVE: no ha salido
                return None
            return codigo.value
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None


def _terminar_pid(pid, forzar: bool = False) -> bool:
    """Termina un proceso por su PID (psutil; si no, la API)."""
    if not pid:
        return False
    try:
        import psutil

        proc = psutil.Process(int(pid))
        if forzar:
            proc.kill()
        else:
            proc.terminate()
        return True
    except Exception:
        pass
    if es_windows():
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.OpenProcess.restype = ctypes.c_void_p
            handle = kernel32.OpenProcess(0x0001, False, int(pid))
            if handle:
                try:
                    return bool(kernel32.TerminateProcess(handle, 1))
                finally:
                    kernel32.CloseHandle(handle)
        except Exception:
            pass
    return False


# v1.0.13: marca INTERNA de «muerto probado, código ilegible».
# poll() la devuelve para que el bucle distinga la muerte, pero
# NO es un código de salida: _codigo_para_pintar la traduce a
# None («no disponible») y jamás se enseña en pantalla. Los
# códigos de Windows son DWORD sin signo: el -1 no colisiona
# con ninguno real.
_CODIGO_SALIDA_DESCONOCIDO = -1


def _codigo_para_pintar(proceso):
    """El código de salida REAL y enseñable de un proceso.

    None si el proceso sigue vivo, si su código no se pudo leer
    o si el mango solo trae la marca interna de «muerto sin
    código»: la pantalla dice entonces «no disponible» en vez
    del 0 fabricado de la 1.0.12.
    """
    if proceso is None:
        return None
    codigo = getattr(proceso, "returncode", None)
    if codigo is None or codigo == _CODIGO_SALIDA_DESCONOCIDO:
        return None
    return codigo


class _ProcesoPorPid:
    """Mango de un openvpn.exe conocido por su PID (v1.0.12).

    Interfaz tipo Popen (poll/wait/terminate/kill/returncode)
    para los procesos que NO lanzó Popen: los del Interactive
    Service y los de una sesión de una apertura anterior de la
    app. poll() lee el estado real del proceso en Windows.

    v1.0.13: poll() trabaja con la vida en TRES estados. Solo
    declara muerte con la prueba positiva de _estado_pid
    («muerto»); «vivo» y «no_comprobable» devuelven None (el
    proceso se trata como en curso y la gestión manda). Si la
    muerte está probada pero el código de salida no se puede
    leer, returncode queda en None y poll() devuelve la marca
    interna _CODIGO_SALIDA_DESCONOCIDO: el 0 fabricado de la
    1.0.12 desaparece. La primera vez que la vida resulta «no
    comprobable» queda anotada en el registro de actividad, con
    el error de Windows que la causó.
    """

    via = "pid"

    def __init__(self, pid):
        self.pid = pid
        self.returncode = None
        self.aviso = ""
        self._muerto_probado = False
        self._no_comprobable_anotado = False

    def poll(self):
        if self._muerto_probado:
            return (self.returncode if self.returncode is not None
                    else _CODIGO_SALIDA_DESCONOCIDO)
        estado, error = _estado_pid_con_error(self.pid)
        if estado == "muerto":
            self._muerto_probado = True
            self.returncode = _codigo_salida_pid(self.pid)
            return (self.returncode if self.returncode is not None
                    else _CODIGO_SALIDA_DESCONOCIDO)
        if estado == "no_comprobable" \
                and not self._no_comprobable_anotado:
            self._no_comprobable_anotado = True
            _anotar_actividad_vpn(
                "La vida del OpenVPN con PID "
                f"{self.pid} no se pudo comprobar"
                + (f" (error de Windows {error} al inspeccionar "
                   "el proceso)" if error else "")
                + ": se trata como vivo y manda su interfaz de "
                  "gestión.")
        return None

    def wait(self, timeout=None):
        limite = time.time() + (timeout if timeout is not None
                                else 31_536_000)
        while time.time() < limite:
            codigo = self.poll()
            if codigo is not None:
                return codigo
            time.sleep(0.2)
        raise TimeoutError(
            f"El proceso {self.pid} no terminó a tiempo.")

    def terminate(self):
        _terminar_pid(self.pid, forzar=False)

    def kill(self):
        _terminar_pid(self.pid, forzar=True)


class _ProcesoElevado:
    """Mango del openvpn.exe lanzado ELEVADO (ShellExecuteEx).

    La interfaz de gestión sigue siendo la vía de desconexión
    (es TCP local y no pide privilegios); terminate/kill sobre
    el mango solo funcionan si la app también va elevada, y por
    eso el cierre ordenado va siempre primero por la gestión.
    """

    via = "elevado"

    def __init__(self, handle, pid):
        self._handle = handle
        self.pid = pid
        self.returncode = None
        self.aviso = ""
        self._muerto_probado = False

    def poll(self):
        # v1.0.13: la muerte solo la prueba WAIT_OBJECT_0 sobre
        # el mango PROPIO de ShellExecuteEx; el código se lee de
        # ese mango y, si la lectura falla, returncode queda en
        # None y poll() devuelve la marca interna de «sin
        # código» — la 1.0.12 fabricaba un 0 también aquí. Todo
        # lo demás (sigue corriendo, espera fallida, excepción)
        # es «no muerto»: None.
        if self._muerto_probado:
            return (self.returncode if self.returncode is not None
                    else _CODIGO_SALIDA_DESCONOCIDO)
        try:
            import ctypes

            kernel32 = _kernel32()
            if kernel32.WaitForSingleObject(self._handle, 0) == 0:
                self._muerto_probado = True
                codigo = ctypes.c_ulong(0)
                if kernel32.GetExitCodeProcess(
                        self._handle, ctypes.byref(codigo)):
                    self.returncode = codigo.value
                return (self.returncode
                        if self.returncode is not None
                        else _CODIGO_SALIDA_DESCONOCIDO)
        except Exception:
            pass
        return None

    def wait(self, timeout=None):
        limite = time.time() + (timeout if timeout is not None
                                else 31_536_000)
        while time.time() < limite:
            codigo = self.poll()
            if codigo is not None:
                return codigo
            time.sleep(0.2)
        raise TimeoutError("El OpenVPN elevado no terminó a "
                           "tiempo.")

    def terminate(self):
        try:
            import ctypes

            ctypes.windll.kernel32.TerminateProcess(self._handle, 1)
        except Exception:
            pass

    def kill(self):
        self.terminate()


def _kernel32():
    """El kernel32 de Windows (costura para las pruebas del tubo:
    el protocolo se ejercita en CI contra un servicio falso)."""
    import ctypes

    return ctypes.windll.kernel32


def _lanzar_por_servicio(argumentos: list[str], carpeta: str):
    """Lanza openvpn.exe a través del Interactive Service.

    Devuelve un _ProcesoPorPid con via="servicio" y el PID que
    el servicio devuelve por el tubo. Lanza
    _ErrorServicioOpenVPN si el tubo no responde o el servicio
    devuelve un error (p. ej. el usuario no está autorizado
    porque su perfil queda fuera de la carpeta del servicio y
    no está en «OpenVPN Administrators»).
    """
    if not es_windows():
        raise WindowsNoDisponible("OpenVPN solo se maneja en Windows.")
    import ctypes
    from ctypes import wintypes

    kernel32 = _kernel32()
    kernel32.CreateFileW.restype = ctypes.c_void_p
    invalido = ctypes.c_void_p(-1).value
    mensaje = _mensaje_arranque_servicio(
        carpeta, _opciones_desde_argumentos(argumentos), "")
    handle = invalido
    for _intento in range(10):
        handle = kernel32.CreateFileW(
            TUBO_SERVICIO_OPENVPN, 0x80000000 | 0x40000000, 0, None,
            3, 0, None)  # GENERIC_READ|GENERIC_WRITE, OPEN_EXISTING
        if handle != invalido:
            break
        error = kernel32.GetLastError()
        if error == 231:  # ERROR_PIPE_BUSY: esperar y reintentar
            kernel32.WaitNamedPipeW(TUBO_SERVICIO_OPENVPN, 5000)
            continue
        raise _ErrorServicioOpenVPN(
            "El servicio interactivo de OpenVPN no respondió "
            f"(error de Windows {error} al abrir su tubo).",
            codigo=error)
    if handle == invalido:
        raise _ErrorServicioOpenVPN(
            "El servicio interactivo de OpenVPN está ocupado y no "
            "respondió.", codigo=231)
    try:
        modo = wintypes.DWORD(0x00000002)  # PIPE_READMODE_MESSAGE
        if not kernel32.SetNamedPipeHandleState(
                handle, ctypes.byref(modo), None, None):
            error = kernel32.GetLastError()
            raise _ErrorServicioOpenVPN(
                "No se pudo hablar con el servicio interactivo de "
                f"OpenVPN (error de Windows {error}).", codigo=error)
        escritos = wintypes.DWORD(0)
        if not kernel32.WriteFile(handle, mensaje, len(mensaje),
                                  ctypes.byref(escritos), None) \
                or escritos.value != len(mensaje):
            error = kernel32.GetLastError()
            raise _ErrorServicioOpenVPN(
                "El servicio interactivo de OpenVPN no aceptó la "
                f"orden de arranque (error de Windows {error}).",
                codigo=error)
        buffer = ctypes.create_string_buffer(65536)
        for _lectura in range(5):
            leidos = wintypes.DWORD(0)
            ok = kernel32.ReadFile(handle, buffer, len(buffer),
                                   ctypes.byref(leidos), None)
            if not ok and kernel32.GetLastError() != 234:
                error = kernel32.GetLastError()
                raise _ErrorServicioOpenVPN(
                    "El servicio interactivo de OpenVPN cerró el "
                    f"tubo sin responder (error de Windows {error}).",
                    codigo=error)
            resp = _interpretar_respuesta_servicio(
                buffer.raw[:leidos.value])
            if resp["ok"]:
                proceso = _ProcesoPorPid(resp["pid"])
                proceso.via = "servicio"
                return proceso
            if resp["codigo"] is not None:
                raise _ErrorServicioOpenVPN(
                    "El servicio interactivo de OpenVPN devolvió "
                    f"un error en {resp['funcion'] or 'el arranque'}"
                    f": {resp['mensaje']}",
                    codigo=resp["codigo"])
        raise _ErrorServicioOpenVPN(
            "El servicio interactivo de OpenVPN respondió algo que "
            "no se pudo interpretar.")
    finally:
        kernel32.CloseHandle(handle)


def _lanzar_elevado(argumentos: list[str], carpeta: str):
    """Reserva: openvpn.exe ELEVADO (ShellExecuteEx, «runas»).

    En la Toughbook del usuario su cuenta eleva sin mostrar UAC
    (probado en la era SoftEther). Si el usuario cancela la
    elevación (error 1223) o Windows la rechaza, lanza
    _ErrorServicioOpenVPN con la causa.
    """
    if not es_windows():
        raise WindowsNoDisponible("OpenVPN solo se maneja en Windows.")
    import ctypes
    from ctypes import wintypes

    class _SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", wintypes.ULONG),
            ("hwnd", ctypes.c_void_p),
            ("lpVerb", ctypes.c_wchar_p),
            ("lpFile", ctypes.c_wchar_p),
            ("lpParameters", ctypes.c_wchar_p),
            ("lpDirectory", ctypes.c_wchar_p),
            ("nShow", ctypes.c_int),
            ("hInstApp", ctypes.c_void_p),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", ctypes.c_wchar_p),
            ("hkeyClass", ctypes.c_void_p),
            ("dwHotKey", wintypes.DWORD),
            ("hIcon", ctypes.c_void_p),
            ("hProcess", ctypes.c_void_p),
        ]

    info = _SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x00000040  # SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = argumentos[0]
    info.lpParameters = _opciones_desde_argumentos(argumentos)
    info.lpDirectory = carpeta
    info.nShow = 0  # SW_HIDE
    shell32 = ctypes.windll.shell32
    shell32.ShellExecuteExW.restype = wintypes.BOOL
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        error = ctypes.windll.kernel32.GetLastError()
        raise _ErrorServicioOpenVPN(
            "Windows no dejó arrancar OpenVPN elevado (error "
            f"{error}).", codigo=error)
    pid = ctypes.windll.kernel32.GetProcessId(info.hProcess)
    return _ProcesoElevado(info.hProcess, pid or None)


def _lanzar_openvpn(argumentos: list[str], carpeta: str,
                    ruta_salida_arranque: str = "",
                    solo_servicio: bool = False):
    """Puerta única de lanzamiento del motor (v1.0.12).

    Orden: (1) el **Interactive Service** —la vía del GUI
    oficial: el servicio ejecuta rutas/IP/DNS con privilegios
    del sistema y openvpn corre como el usuario—; (2) **elevado**
    (runas) si el servicio no responde o no autoriza al usuario.
    La 1.0.11 lanzaba con Popen a secas: sin tubo de servicio ni
    elevación, Windows negaba las rutas (status=5) y el túnel
    quedaba abierto pero inútil.

    El proceso devuelto trae la interfaz que usa el motor
    (poll/wait/terminate/kill/pid/returncode) y el atributo
    «via» ("servicio" | "elevado"). Por estas vías el stdout de
    openvpn va a NUL: la causa vive en su registro
    (--log-append), que openvpn abre tras parsear el perfil — y
    el parseo lo vigila la puerta de CI con el exe real desde la
    1.0.11. `ruta_salida_arranque` queda por compatibilidad de
    la puerta (las pruebas la sustituyen y la usan).

    v1.0.13: el orden honra `_VIA_PREFERIDA`, la vía que la
    puerta previa decidió para este intento (si la puerta dice
    «elevado» —p. ej. la sesión aún no refleja el grupo—, se
    lanza elevado PRIMERO y el servicio queda de reserva).

    v1.0.18 (nota 1 del usuario): con ``solo_servicio=True`` la
    vía elevada DESAPARECE del orden — ningún trabajo en segundo
    plano (sondas del arranque, reconexión automática) puede
    provocar un aviso de administrador (UAC) por su cuenta: si
    el servicio interactivo no responde o no autoriza, el
    lanzamiento falla aquí y el llamante espera en silencio.
    """
    if not es_windows():
        raise WindowsNoDisponible("OpenVPN solo se maneja en Windows.")
    if solo_servicio:
        orden = ("servicio",)
    else:
        orden = (("elevado", "servicio") if _VIA_PREFERIDA == "elevado"
                 else ("servicio", "elevado"))
    errores = {}
    for via in orden:
        try:
            if via == "servicio":
                proceso = _lanzar_por_servicio(argumentos, carpeta)
            else:
                proceso = _lanzar_elevado(argumentos, carpeta)
        except Exception as exc:
            errores[via] = exc
            continue
        if via == "elevado" and "servicio" in errores:
            proceso.aviso = (
                "El servicio interactivo de OpenVPN no se pudo "
                f"usar ({errores['servicio']}); OpenVPN se lanzó "
                "ELEVADO como reserva.")
        elif via == "elevado":
            proceso.aviso = (
                "OpenVPN se lanzó ELEVADO: así lo decidió la "
                "puerta previa para este intento.")
        elif "elevado" in errores:
            proceso.aviso = (
                "La reserva elevada no se pudo usar "
                f"({errores['elevado']}); OpenVPN se lanzó por "
                "su servicio interactivo.")
        return proceso
    if solo_servicio:
        raise _ErrorServicioOpenVPN(
            "El servicio interactivo de OpenVPN no se pudo usar "
            f"({errores.get('servicio')}): la vía elevada está "
            "prohibida para el trabajo en segundo plano (v1.0.18).")
    raise _ErrorServicioOpenVPN(
        "No se pudo arrancar OpenVPN ni por su servicio "
        f"interactivo ({errores.get('servicio')}) ni elevado "
        f"({errores.get('elevado')}).")


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


# --- Clasificador de causa (nuevo en la 1.0.12) -------------------------------
#
# La 1.0.11 elegía la causa por marcas sueltas en CUALQUIER línea,
# y en la prueba real de la Toughbook una línea INFORMATIVA de
# apertura del adaptador («Opening TAP-Windows…» trae «tap») se
# convirtió en el titular falso «no pudo abrir su tarjeta
# virtual… reinstala la app» sobre un intento cuyo único fallo
# era de RUTAS por privilegios. Reglas de la 1.0.12:
# (1) una línea informativa NUNCA es causa: solo cuentan las que
#     traen marca de error/fatal/warning (o failed/denied/cannot);
# (2) la familia «rutas/privilegios» se evalúa ANTES que la de
#     adaptador (el error de rutas de la foto real trae status=5);
# (3) la familia «tarjeta» solo casa con fallos REALES de apertura
#     («Cannot open TUN/TAP», «CreateFile failed on tap», «All
#     tap-windows6 adapters…»), jamás con «tap» suelto;
# (4) «Initialization Sequence Completed» con rutas fallidas es su
#     propio estado: túnel abierto pero sin rutas.

# Marcas de que una línea HABLA de un problema (no de un paso más).
_MARCAS_ERROR_LINEA = ("error", "fatal", "warning", "failed",
                       "denied", "cannot", "unable")

# v1.0.13: advertencias RUTINARIAS de arranque de OpenVPN. Traen
# «WARNING» (y hasta la palabra «certificate») pero no anuncian
# ningún fallo: son informativas EXPRESAS y jamás pueden ser la
# causa. En la prueba real de la 1.0.12, «No server certificate
# verification method has been enabled» bastó para culpar al
# servidor de un «error TLS» sobre un intento que la propia app
# había detenido.
_MARCAS_INFORMATIVAS_EXPRESAS = (
    "no server certificate verification method",
    "this configuration may cache passwords",
    "deprecated option",
    "--persist-key",
    "not supported by ovpn-dco",
)


def _es_linea_informativa_expresa(linea: str) -> bool:
    baja = (linea or "").lower()
    return any(marca in baja
               for marca in _MARCAS_INFORMATIVAS_EXPRESAS)


# Familias en orden de evaluación: (familia, marcas en minúsculas).
# v1.0.13: «detenido» va PRIMERA — un registro que termina en un
# SIGTERM enviado por la interfaz de gestión lo detuvo la propia
# app (es el único cliente de gestión), y esa verdad va por
# delante de cualquier familia de red. Y «tls» pierde la marca
# suelta «certificate»: exige un error TLS real.
_FAMILIAS_REGISTRO = (
    ("detenido", ("signal sigterm", "sigterm[hard")),
    ("opciones", ("bad backslash", "options error",
                  "options warning")),
    ("rutas", ("route addition failed", "createipforwardentry",
               "access is denied", "status=5", "route.exe failed",
               "error opening registry")),
    ("credenciales", ("auth_failed",)),
    ("tarjeta", ("cannot open tun/tap", "cannot open tap",
                 "createfile failed on tap",
                 "all tap-windows6 adapters",
                 "tap device open failed", "no usable tap")),
    ("dco", ("ovpn-dco error", "dco device failed",
             "data channel offload failed")),
    ("servicio", ("interactive service", "iservice")),
    ("tls", ("tls error", "verify error", "tls handshake failed",
             "tls key negotiation failed",
             "authenticate/decrypt packet error")),
    ("saturado", ("connection reset", "connection refused",
                  "connection timed out", "recvfrom", "read udp")),
    ("red", ("no route to host", "network is unreachable",
             "cannot resolve", "name resolution")),
)


def _es_linea_error(linea: str) -> bool:
    if _es_linea_informativa_expresa(linea):
        return False
    baja = (linea or "").lower()
    return any(marca in baja for marca in _MARCAS_ERROR_LINEA)


def _familia_de_linea(linea: str) -> str:
    if _es_linea_informativa_expresa(linea):
        return ""
    baja = (linea or "").lower()
    for familia, marcas in _FAMILIAS_REGISTRO:
        if any(marca in baja for marca in marcas):
            return familia
    return ""


def _analizar_registro(lineas) -> dict:
    """Analiza el registro de un intento (función pura, v1.0.12).

    Devuelve {"causa", "familia", "rutas_fallidas",
    "inicializacion_completa"}:
    - «causa»: la primera línea DE ERROR cuya familia se conoce;
      si ninguna línea de error trae familia, la primera línea
      de error a secas; solo si no hay NI una línea de error se
      cae al respaldo histórico (la última línea con contenido).
      Una línea informativa jamás gana a una de error.
    - «rutas_fallidas»: el registro trae un fallo de rutas
      (aunque el túnel haya llegado a inicializar).
    - «inicializacion_completa»: aparece «Initialization
      Sequence Completed» (el túnel SÍ abrió).
    """
    lista = [str(l).strip() for l in (lineas or []) if str(l).strip()]
    inicializacion = any("initialization sequence completed"
                         in l.lower() for l in lista)
    rutas = any(_familia_de_linea(l) == "rutas"
                for l in lista if _es_linea_error(l))
    causa = ""
    familia = ""
    for linea in lista:
        if not _es_linea_error(linea):
            continue
        fam = _familia_de_linea(linea)
        if fam:
            causa, familia = linea[-300:], fam
            break
    if not causa:
        # Respaldo por familias sobre TODAS las líneas: hay
        # eventos reales que no traen palabra de error (el
        # «Connection reset, restarting» de un servidor saturado
        # va seguido de un «fatal error» genérico que no debe
        # ganarle). Las marcas de cada familia son de fallo real
        # (la de tarjeta, solo de apertura), así que una línea
        # informativa sigue sin poder convertirse en causa.
        for fam, _marcas in _FAMILIAS_REGISTRO:
            for linea in lista:
                if _familia_de_linea(linea) == fam:
                    causa, familia = linea[-300:], fam
                    break
            if causa:
                break
    if not causa:
        for linea in lista:
            if _es_linea_error(linea):
                causa = linea[-300:]
                break
    if not causa and lista:
        causa = lista[-1][-300:]
        familia = _familia_de_linea(causa)
    return {"causa": causa, "familia": familia,
            "rutas_fallidas": rutas,
            "inicializacion_completa": inicializacion}


def _elegir_causa(lineas) -> str:
    """La línea de causa entre unas líneas de OpenVPN (o "").

    v1.0.12: delega en _analizar_registro — las líneas
    informativas ya no pueden convertirse en la causa.
    """
    return _analizar_registro(lineas)["causa"]


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


def _mensaje_familia(familia: str, causa: str,
                     hostname: str) -> tuple[str, str]:
    """(mensaje en español, detalle) por FAMILIA de causa (v1.0.12).

    El texto «servidor apagado o saturado» SOLO se usa para
    causas reales de red/TLS (familias saturado/red/tls), como
    mandó la 1.0.11. La familia «rutas» tiene su propio mensaje:
    es un problema de privilegios en ESTE equipo, no de la
    tarjeta ni del servidor.
    """
    if familia == "detenido":
        return ("La propia app detuvo este intento de OpenVPN "
                "antes de que conectara (le envió la orden de "
                "apagado por su interfaz de gestión): no fue el "
                "servidor ni tu red. La línea real está en el "
                "detalle y el intento quedó anotado en el "
                "registro de actividad.", causa)
    if familia == "opciones":
        return ("OpenVPN rechazó el perfil de conexión de este "
                "servidor (error de opciones en el perfil): el fallo "
                "está en el perfil, no en el servidor. La línea real "
                "está en el detalle y en el registro de actividad.",
                causa)
    if familia == "rutas":
        return ("Windows negó crear las rutas del tráfico de la "
                "VPN: no es la tarjeta ni el servidor, es un "
                "problema de permisos en este equipo. La línea real "
                "está en el detalle; si se repite, reinstala la app "
                "para que su instalador deje los permisos en su "
                "sitio.", causa)
    if familia == "credenciales":
        # v1.0.14 (investigación A): con las credenciales
        # correctas de su fuente, un AUTH_FAILED es el servidor
        # diciendo «no» — está lleno o fuera de servicio aunque
        # siga anunciado. Jamás se culpa a la credencial.
        return ("El servidor rechazó el inicio de sesión "
                "(autenticación). No es tu credencial: es la "
                "correcta de su fuente. Ese servidor está lleno "
                "o fuera de servicio en este momento; la app lo "
                "marca y prueba con el siguiente.", causa)
    if familia == "tarjeta":
        return ("OpenVPN no pudo abrir su tarjeta virtual "
                "(TAP-Windows/DCO). Reinstala la app para repararla: "
                "su instalador vuelve a dejar la tarjeta en su "
                "sitio.", causa)
    if familia == "dco":
        return ("OpenVPN no pudo usar su tarjeta virtual rápida "
                "(DCO). Reinstala la app para repararla: su "
                "instalador vuelve a dejar la tarjeta en su sitio.",
                causa)
    if familia == "servicio":
        return ("OpenVPN no pudo apoyarse en su servicio (OpenVPN "
                "Interactive Service): puede estar parado. Reinicia "
                "el equipo y vuelve a intentarlo; si sigue igual, "
                "reinstala la app para repararlo.", causa)
    if familia == "tls":
        return (f"El servidor {hostname} cortó la conexión al "
                "comprobar los certificados (error TLS): suele ser "
                "un servidor de VPN Gate caído o saturado; elige "
                "otro de la lista e inténtalo de nuevo.", causa)
    if familia in ("saturado", "red"):
        return (f"El servidor {hostname} no respondió o cortó la "
                "conexión. Suele ser un servidor apagado o saturado: "
                "elige otro de la lista e inténtalo de nuevo.", causa)
    return ("OpenVPN se cerró antes de conectar. La causa real "
            "está en el detalle de esta pantalla y en el registro "
            "de actividad de la app.", causa)


def _clasificar_fallo_openvpn(causa: str, codigo_salida,
                              hostname: str) -> tuple[str, str]:
    """(mensaje en español, detalle) para un openvpn que murió solo.

    v1.0.12: la familia sale de _familia_de_linea sobre la línea
    de causa (que ya viene filtrada por _analizar_registro: las
    informativas no llegan aquí como «tap» suelto). Una causa
    VACÍA se declara como tal, como mandó la 1.0.11.

    v1.0.13: el código de salida puede ser None («no
    disponible»): se dice tal cual, jamás se pinta un número
    fabricado.
    """
    if not (causa or "").strip():
        codigo_txt = (f"código de salida {codigo_salida}"
                      if codigo_salida is not None
                      else "código de salida no disponible")
        return (f"OpenVPN se cerró sin dejar registro en este "
                f"intento ({codigo_txt}). No es que el servidor "
                f"{hostname} esté apagado: el programa se cerró en "
                "este equipo antes de poder anotar su causa; lo "
                "que se sabe quedó en el registro de actividad de "
                "la app.",
                f"OpenVPN se cerró sin dejar registro en este "
                f"intento; {codigo_txt}.")
    return _mensaje_familia(_familia_de_linea(causa), causa, hostname)


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


def _lineas_archivo(ruta: str) -> list:
    """Las líneas de un archivo de texto (o [] si no se puede)."""
    try:
        with open(ruta, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except OSError:
        return []


def _cerrar_proceso(proceso, puerto=None) -> bool:
    """Cierra un openvpn del motor SIN dejar huérfanos (v1.0.12).

    Orden: SIGTERM por la interfaz de gestión (la vía limpia,
    que deshace rutas e IP) → espera → terminate → kill. Verifica
    con poll() al final y devuelve si quedó cerrado. Cada paso va
    protegido: los procesos de las pruebas (y los reales) no
    siempre traen todos los métodos.
    """
    if proceso is None:
        return True
    if puerto:
        try:
            _mgmt_enviar(int(puerto), "signal SIGTERM", timeout=5)
        except Exception:
            pass
    try:
        proceso.wait(timeout=8)
    except Exception:
        pass
    try:
        if proceso.poll() is None:
            try:
                proceso.terminate()
            except Exception:
                pass
            try:
                proceso.wait(timeout=5)
            except Exception:
                pass
    except Exception:
        pass
    try:
        if proceso.poll() is None:
            matar = getattr(proceso, "kill", None)
            if callable(matar):
                matar()
            try:
                proceso.wait(timeout=3)
            except Exception:
                pass
    except Exception:
        pass
    try:
        return proceso.poll() is not None
    except Exception:
        return False


def _cerrar_intento_previo() -> None:
    """Cierra limpiamente el intento anterior, si lo hay (v1.0.12).

    Un solo intento a la vez: el «Conectar» nuevo no comparte
    _PROCESO, sesión ni perfil con el anterior (la 1.0.11 dejaba
    al anterior inalcanzable y vivo).
    """
    global _PROCESO
    sesion = _leer_sesion()
    proceso = _PROCESO
    if proceso is None and sesion.get("pid"):
        proceso = _ProcesoPorPid(sesion["pid"])
    if proceso is not None:
        _cerrar_proceso(proceso, sesion.get("puerto"))
    _PROCESO = None
    if sesion:
        _borrar_sesion()


def cerrar_intento_en_curso() -> bool:
    """Baja el proceso de un intento AÚN «conectando» (v1.0.12).

    Para el cierre de la app y la destrucción de la página de
    Red: un túnel CONFIRMADO no se toca (bajarlo es la orden
    expresa de desconectar), pero un intento a medias jamás se
    queda vivo sin dueño, como pasó en la 1.0.11.
    """
    global _PROCESO
    sesion = _leer_sesion()
    if sesion.get("estado") != "conectando":
        return False
    proceso = _PROCESO
    if proceso is None and sesion.get("pid"):
        proceso = _ProcesoPorPid(sesion["pid"])
    if proceso is not None:
        _cerrar_proceso(proceso, sesion.get("puerto"))
    _PROCESO = None
    _borrar_sesion()
    return True


def _al_salir_cerrar_intento() -> None:
    try:
        cerrar_intento_en_curso()
    except Exception:
        pass


atexit.register(_al_salir_cerrar_intento)


def _barrido_huerfanos() -> list:
    """Cierra los openvpn.exe HUÉRFANOS de ESTA app (v1.0.12).

    Huérfano propio = su PID consta en la sesión guardada o su
    línea de comandos trae nuestro vpngate-activo.ovpn. Un
    openvpn AJENO no se toca jamás: si sujeta la tarjeta, la
    pantalla lo dirá. El barrido queda anotado en el registro de
    actividad. Devuelve los PID cerrados.
    """
    sesion = _leer_sesion()
    pids_sesion = {sesion["pid"]} if sesion.get("pid") else set()
    try:
        detalle = _procesos_openvpn_detalle()
    except Exception:
        detalle = []
    cerrados = []
    for info in detalle:
        pid = info.get("pid")
        if not pid:
            continue
        if _PROCESO is not None and pid == getattr(_PROCESO, "pid",
                                                   None):
            continue
        if _es_proceso_propio(info, pids_sesion):
            if _terminar_pid(pid, forzar=True):
                cerrados.append(pid)
    if cerrados:
        _anotar_actividad_vpn(
            "Barrido previo de la VPN: se cerraron los OpenVPN "
            "huérfanos de la app con PID "
            + ", ".join(str(p) for p in cerrados) + ".")
        time.sleep(1)
    return cerrados


def _propios_vivos(pids_extra=()) -> list:
    """Los openvpn.exe vivos que son de esta app (post-cierre)."""
    sesion = _leer_sesion()
    pids_sesion = {sesion["pid"]} if sesion.get("pid") else set()
    pids_sesion |= set(pids_extra or ())
    try:
        detalle = _procesos_openvpn_detalle()
    except Exception:
        return []
    return [i for i in detalle if _es_proceso_propio(i, pids_sesion)]


def _ajenos_vivos() -> list:
    """Los openvpn.exe vivos que NO son de esta app."""
    sesion = _leer_sesion()
    pids_sesion = {sesion["pid"]} if sesion.get("pid") else set()
    try:
        detalle = _procesos_openvpn_detalle()
    except Exception:
        return []
    return [i for i in detalle
            if not _es_proceso_propio(i, pids_sesion)]


# v1.0.13: el detalle de un intento sin registro propio lo dice
# tal cual — jamás se rellena con el registro de otro intento ni
# con el fósil openvpn-arranque.txt de la 1.0.11.
_DETALLE_SIN_REGISTRO = (
    "Sin registro todavía: OpenVPN no llegó a crear su registro "
    "en este intento.")


def _esperar_asentamiento_registro(ruta_log: str,
                                   espera_max: float = 1.5) -> None:
    """Espera breve a que el registro del intento se asiente.

    Tras una muerte probada, openvpn puede estar aún volcando
    sus últimas líneas: se espera a que el tamaño del archivo
    deje de cambiar (con tope) antes de leerlo, para no analizar
    un registro a medias (en la 1.0.12 el titular y el detalle
    llegaron a salir de dos lecturas distintas en plena
    carrera).
    """
    try:
        anterior = os.path.getsize(ruta_log)
    except OSError:
        return
    limite = time.time() + espera_max
    while time.time() < limite:
        time.sleep(0.25)
        try:
            actual = os.path.getsize(ruta_log)
        except OSError:
            return
        if actual == anterior:
            return
        anterior = actual


def _registro_anuncia_salida(ruta_log: str) -> bool:
    """¿El propio registro de openvpn anuncia su salida?"""
    for linea in _lineas_archivo(ruta_log):
        baja = linea.lower()
        if "process exiting" in baja \
                or "exiting due to fatal error" in baja:
            return True
    return False


def _muerte_probada(proceso, puerto, ruta_log: str = "") -> bool:
    """¿La muerte del proceso está PROBADA? (v1.0.13)

    Exige DOS pruebas positivas: (1) el mango declara la muerte
    con su prueba positiva (poll() no-None: en los mangos de la
    1.0.13 eso ya significa código leído de verdad, PID
    inexistente confirmado o WAIT_OBJECT_0 — «no comprobable»
    devuelve None y aquí ni se entra); y (2) UNA de estas dos:
    el propio registro de openvpn anuncia su salida («process
    exiting» / «Exiting due to fatal error»), o la interfaz de
    gestión CALLA ante un `state` y una segunda lectura de
    poll(), separada en el tiempo, sigue declarando la muerte.
    Si la gestión responde con cualquier estado, el proceso
    está vivo, punto.
    """
    if proceso is None:
        return False
    try:
        if proceso.poll() is None:
            return False
    except Exception:
        return False
    if ruta_log and _registro_anuncia_salida(ruta_log):
        return True
    if puerto:
        try:
            salida = _mgmt_enviar(int(puerto), "state", timeout=3)
            if salida and interpretar_estado_mgmt(salida)["estado"]:
                return False
        except Exception:
            pass
    time.sleep(1.0)
    try:
        return proceso.poll() is not None
    except Exception:
        return False


def conectar_openvpn(contenido_ovpn: str, hostname: str,
                     espera: int = 45, usuario: str | None = None,
                     clave: str | None = None,
                     sonda: bool = False,
                     solo_servicio: bool = False) -> dict:
    """Conecta con un servidor de VPN Gate por el motor OpenVPN.

    v1.0.14: `usuario`/`clave` son las credenciales DE LA FUENTE
    del servidor (por defecto las de VPN Gate, «vpn»/«vpn»: el
    comportamiento de siempre). Con `sonda=True` no se busca un
    túnel para el usuario: se comprueba que el servidor ACEPTA
    (PUSH_REPLY o CONNECTED,SUCCESS) con un perfil route-nopull
    y el intento se baja al instante — el resultado trae
    datos["sonda"]=True y datos["verificado"]=True si aceptó.
    Todo fallo trae datos["familia"] para el failover.


    v1.0.12: openvpn se lanza por el **Interactive Service**
    (rutas/IP/DNS con privilegios del servicio; reserva elevada
    si el servicio no autoriza), tras la puerta previa y el
    barrido de huérfanos propios, con UN solo intento a la vez y
    limpieza garantizada: TODA salida que no sea éxito confirmado
    baja el proceso y borra la sesión (try/finally) — nunca más
    un openvpn huérfano sujetando la tarjeta. Si el túnel
    inicializa pero Windows negó las rutas, se reporta como lo
    que es («túnel abierto pero sin rutas») y se baja limpio.

    v1.0.13: la espera manda por la interfaz de gestión y la
    muerte solo se declara con _muerte_probada (dos pruebas
    positivas; «no comprobable» jamás es muerte — la 1.0.12 se
    apagaba su propio intento en el primer segundo). El detalle
    sale SOLO del registro de este intento (fuera el respaldo al
    fósil openvpn-arranque.txt), el código de salida solo se
    pinta si es real, y si la app detiene el intento (timeout)
    el resultado lo dice tal cual en vez de culpar al servidor.

    Devuelve {"ok", "mensaje", "detalle", "datos"}.
    """
    global _PROCESO, _VIA_PREFERIDA
    hostname = (hostname or "").strip()
    if not hostname:
        return {"ok": False, "mensaje": "Falta el servidor al que conectar.",
                "detalle": "", "datos": {"familia": "local"}}
    ruta_exe = ruta_openvpn_exe()
    if not ruta_exe:
        return {"ok": False,
                "mensaje": "OpenVPN no está en este equipo.",
                "detalle": "openvpn.exe no encontrado.",
                "datos": {"familia": "local"}}
    if not (contenido_ovpn or "").strip():
        return {"ok": False,
                "mensaje": "El servidor no trajo su perfil de conexión "
                           "(.ovpn): elige otro de la lista.",
                "detalle": "", "datos": {"familia": "local"}}
    # v1.0.12: un solo intento a la vez + barrido de huérfanos
    # propios antes de tocar nada.
    _cerrar_intento_previo()
    _barrido_huerfanos()
    if _ajenos_vivos():
        return {"ok": False,
                "mensaje": "Otro OpenVPN está usando la tarjeta "
                           "virtual en este equipo (no es de esta "
                           "app): ciérralo y vuelve a intentarlo.",
                "detalle": "Hay un proceso openvpn.exe ajeno a la "
                           "app con la tarjeta TAP-Windows en uso.",
                "datos": {"familia": "local"}}
    puerta = puerta_previa_openvpn()
    if not puerta["listo"]:
        return {"ok": False, "mensaje": puerta["motivo"],
                "detalle": "", "datos": {"familia": "local"}}
    if solo_servicio and puerta.get("via") != "servicio":
        # v1.0.18 (nota 1): el trabajo en segundo plano JAMÁS se
        # eleva. Si la puerta previa solo deja la vía elevada
        # (servicio parado o sesión sin el grupo reflejado), la
        # operación se difiere en silencio: ni un solo UAC sale
        # de aquí. El llamante lo deja «sin verificar» o lo
        # reintenta más tarde.
        return {"ok": False,
                "mensaje": "El servicio interactivo de OpenVPN no "
                           "está disponible para esta sesión "
                           "todavía: el trabajo en segundo plano "
                           "no se eleva y espera en silencio.",
                "detalle": puerta.get("aviso", ""),
                "datos": {"familia": "local", "diferido": True}}
    aviso_puerta = puerta.get("aviso", "")
    carpeta = carpeta_perfiles_vpn()
    ruta_cred = os.path.join(carpeta, "vpngate-credenciales.txt")
    # v1.0.14: las credenciales son las de la FUENTE del servidor
    # (parámetros); sin parámetros, las de VPN Gate de siempre.
    usuario_efectivo = USUARIO_VPNGATE if usuario is None else usuario
    clave_efectiva = CLAVE_VPNGATE if clave is None else clave
    with open(ruta_cred, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{usuario_efectivo}\n{clave_efectiva}\n")
    ruta_perfil = os.path.join(carpeta, "vpngate-activo.ovpn")
    with open(ruta_perfil, "w", encoding="utf-8", newline="\n") as f:
        f.write(preparar_perfil_vpngate(
            contenido_ovpn, ruta_cred,
            lineas_extra=("route-nopull",) if sonda else ()))
    ruta_log = os.path.join(carpeta, "openvpn-conexion.log")
    # v1.0.11: el registro del intento anterior NO se borra: rota
    # con fecha/hora (se conservan los últimos 5).
    _rotar_registro_openvpn(ruta_log)
    # v1.0.13: el detalle de ESTE intento sale solo de su propio
    # registro (ruta_log). El parámetro de salida de arranque se
    # sigue pasando al lanzador por compatibilidad de su firma,
    # pero su archivo YA NO se lee: en la 1.0.12 nadie lo
    # escribía y su fósil de la 1.0.11 se sirvió como si fuera
    # el intento en curso.
    ruta_salida = os.path.join(carpeta, "openvpn-arranque.txt")
    puerto = _puerto_libre()
    argumentos = [ruta_exe, "--config", ruta_perfil,
                  "--management", "127.0.0.1", str(puerto),
                  "--log-append", ruta_log]
    # v1.0.13: la puerta previa MANDA: la vía que decidió es la
    # que el lanzador prueba primero.
    _VIA_PREFERIDA = puerta.get("via", "") or ""
    try:
        if solo_servicio:
            _PROCESO = _lanzar_openvpn(
                argumentos, carpeta, ruta_salida,
                solo_servicio=True)
        else:
            _PROCESO = _lanzar_openvpn(argumentos, carpeta,
                                       ruta_salida)
    except Exception as exc:
        _VIA_PREFERIDA = ""
        return {"ok": False,
                "mensaje": "No se pudo arrancar el motor de OpenVPN.",
                "detalle": str(exc), "datos": {"familia": "local"}}
    _VIA_PREFERIDA = ""
    proceso = _PROCESO
    via = getattr(proceso, "via", "") or ""
    aviso = aviso_puerta or getattr(proceso, "aviso", "") or ""
    # v1.0.13: el intento queda anotado con su vía y el aviso de
    # la puerta — el próximo fallo se diagnostica desde el
    # registro de actividad, sin fotos.
    _anotar_actividad_vpn(
        f"Conexión VPN a {hostname}: vía de la puerta previa "
        f"«{puerta.get('via', '')}», vía usada «{via}», PID "
        f"{getattr(proceso, 'pid', None)}, puerto de gestión "
        f"{puerto}." + (f" Aviso: {aviso}" if aviso else ""))
    exito = False
    try:
        # La sesión nace «conectando»: solo pasa a «conectada»
        # cuando la interfaz de gestión confirma el túnel.
        _guardar_sesion({"hostname": hostname, "puerto": puerto,
                         "pid": getattr(proceso, "pid", None),
                         "via": via,
                         "desde": time.time(), "estado": "conectando"})
        limite = time.time() + max(5, int(espera))
        sondeo_anotado = False
        while time.time() < limite:
            # v1.0.13: la muerte solo se declara con
            # _muerte_probada (dos pruebas positivas, una por la
            # propia gestión o por el registro del proceso); un
            # «no comprobable» jamás entra aquí. Después manda la
            # interfaz de gestión, la única que confirma el
            # túnel.
            if proceso is not None and proceso.poll() is not None \
                    and _muerte_probada(proceso, puerto, ruta_log):
                # Muerte PROBADA: el detalle sale SOLO del
                # registro de este intento, ya asentado, y el
                # código de salida solo si es real.
                codigo = _codigo_para_pintar(proceso)
                _esperar_asentamiento_registro(ruta_log)
                lineas = _lineas_archivo(ruta_log)
                analisis = _analizar_registro(lineas)
                ultimas = _ultimas_lineas(ruta_log)
                if analisis["inicializacion_completa"] \
                        and analisis["rutas_fallidas"]:
                    mensaje = (
                        "El túnel de OpenVPN abrió pero sin rutas: "
                        "Windows negó crear las rutas del tráfico "
                        "y tu tráfico NO sale por la VPN. No es la "
                        "tarjeta ni el servidor: es un problema de "
                        "permisos en este equipo (la línea real "
                        "está en el detalle).")
                    detalle = ultimas or analisis["causa"]
                elif not analisis["causa"] and not ultimas:
                    mensaje, detalle = _clasificar_fallo_openvpn(
                        "", codigo, hostname)
                else:
                    mensaje, detalle = _mensaje_familia(
                        analisis["familia"], analisis["causa"],
                        hostname)
                    detalle = ultimas or detalle
                if codigo is not None:
                    detalle = (detalle
                               + f"\nCódigo de salida de OpenVPN: "
                                 f"{codigo}.").strip()
                else:
                    detalle = (detalle
                               + "\nCódigo de salida de OpenVPN: "
                                 "no disponible.").strip()
                return {"ok": False, "mensaje": mensaje,
                        "detalle": detalle,
                        "datos": {"codigo_salida": codigo,
                                  "ultimas_lineas": ultimas,
                                  "via": via,
                                  "familia": analisis["familia"]}}
            try:
                salida = _mgmt_enviar(puerto, "state", timeout=5)
            except Exception:
                salida = ""
            if not sondeo_anotado:
                sondeo_anotado = True
                _anotar_actividad_vpn(
                    f"Primer sondeo del intento a {hostname}: la "
                    "gestión "
                    + ("respondió." if salida else "no respondió.")
                    + f" poll()={proceso.poll()!r}.")
            if salida and interpretar_estado_mgmt(salida)["conectado"]:
                if sonda:
                    # v1.0.14: la sonda ya probó lo que venía a
                    # probar (el servidor ACEPTA y el túnel se
                    # levanta en esta máquina): se devuelve el
                    # veredicto y el finally baja el intento al
                    # instante — la sonda nunca deja un túnel
                    # puesto ni toca el tráfico (route-nopull).
                    return {"ok": True,
                            "mensaje": (f"Sonda: el servidor "
                                        f"{hostname} acepta y "
                                        "conecta."),
                            "detalle": aviso,
                            "datos": {"sonda": True,
                                      "verificado": True,
                                      "hostname": hostname,
                                      "via": via}}
                # v1.0.12: confirmado el túnel, se revisa el
                # registro: si las rutas fallaron, el túnel está
                # abierto pero INÚTIL — se dice tal cual y el
                # finally lo baja limpio por gestión.
                analisis = _analizar_registro(
                    _lineas_archivo(ruta_log))
                if analisis["rutas_fallidas"]:
                    ultimas = _ultimas_lineas(ruta_log)
                    return {"ok": False,
                            "mensaje": (
                                "El túnel abrió pero sin rutas: "
                                "Windows negó crear las rutas del "
                                "tráfico, así que tu tráfico no "
                                "sale por la VPN. No es la tarjeta "
                                "ni el servidor: es un problema de "
                                "permisos en este equipo."),
                            "detalle": ultimas or analisis["causa"],
                            "datos": {"via": via, "familia": "rutas",
                                      "ultimas_lineas": ultimas}}
                _guardar_sesion({"hostname": hostname,
                                 "puerto": puerto,
                                 "pid": getattr(proceso, "pid", None),
                                 "via": via,
                                 "desde": time.time(),
                                 "estado": "conectada"})
                exito = True
                return {"ok": True,
                        "mensaje": (f"Conectado a {hostname} con "
                                    "OpenVPN: el túnel está arriba "
                                    "y trabaja en segundo plano."),
                        "detalle": aviso,
                        "datos": {"hostname": hostname,
                                  "via": "openvpn",
                                  "via_arranque": via,
                                  "puerto_mgmt": puerto}}
            if sonda:
                # v1.0.14: la aceptación del servidor también se
                # conoce por el registro —el PUSH_REPLY llega tras
                # autenticar, ANTES de tocar rutas ni tarjeta—:
                # la sonda decide en ese punto y el finally baja
                # el intento al instante.
                if any("push_reply" in linea.lower()
                       for linea in _lineas_archivo(ruta_log)):
                    return {"ok": True,
                            "mensaje": (f"Sonda: el servidor "
                                        f"{hostname} acepta la "
                                        "conexión."),
                            "detalle": aviso,
                            "datos": {"sonda": True,
                                      "verificado": True,
                                      "hostname": hostname,
                                      "via": via}}
            time.sleep(2)
        # Timeout SIN muerte probada: quien detiene el intento
        # es la PROPIA APP (el finally lo baja) y el resultado
        # lo dice tal cual — la 1.0.12 lo disfrazaba de «el
        # servidor puede estar saturado». El proceso NO queda
        # vivo reintentando: túnel huérfano nunca más.
        codigo = _codigo_para_pintar(proceso)
        lineas = _lineas_archivo(ruta_log)
        analisis = _analizar_registro(lineas)
        ultimas = _ultimas_lineas(ruta_log)
        _anotar_actividad_vpn(
            f"La app detuvo el intento a {hostname} por tiempo "
            "de espera agotado, sin muerte probada del proceso.")
        return {"ok": False,
                "mensaje": ("La app detuvo el intento antes de "
                            "confirmar la conexión: el túnel no "
                            "se confirmó a tiempo y la app cerró "
                            "el intento para no dejarlo corriendo "
                            "sin control. No es un fallo "
                            "confirmado del servidor "
                            f"{hostname}: elige otro de la lista "
                            "e inténtalo de nuevo."),
                "detalle": ultimas or analisis["causa"]
                           or _DETALLE_SIN_REGISTRO,
                "datos": {"codigo_salida": codigo,
                          "ultimas_lineas": ultimas,
                          "via": via,
                          # v1.0.14: para el failover, un intento
                          # de usuario sin respuesta cuenta como
                          # fallo del servidor («sin_respuesta»);
                          # para la SONDA, un timeout no condena
                          # al nodo (puede ser lentitud): sin
                          # familia, sin veredicto.
                          "familia": "" if sonda else "sin_respuesta"}}
    finally:
        if not exito:
            # Limpieza garantizada: proceso cerrado y verificado,
            # sesión borrada. La sesión solo sobrevive como
            # «conectada» confirmada.
            if proceso is not None:
                _cerrar_proceso(proceso, puerto)
            if _PROCESO is proceso:
                _PROCESO = None
            _borrar_sesion()


def desconectar_openvpn() -> dict:
    """Baja la conexión del motor por su interfaz de gestión.

    Orden limpia primero (signal SIGTERM a la interfaz); el
    proceso se localiza por el mango de la app o por el PID de la
    sesión (app reabierta) y se cierra con verificación: al final
    no debe quedar ningún openvpn PROPIO vivo (v1.0.12).
    """
    global _PROCESO
    sesion = _leer_sesion()
    puerto = sesion.get("puerto")
    pid_sesion = sesion.get("pid")
    if puerto:
        try:
            _mgmt_enviar(int(puerto), "signal SIGTERM", timeout=5)
        except Exception:
            pass
    proceso = _PROCESO
    if proceso is None and pid_sesion:
        proceso = _ProcesoPorPid(pid_sesion)
    if proceso is not None:
        _cerrar_proceso(proceso, puerto)
        if _PROCESO is proceso:
            _PROCESO = None
    if hay_tunel_openvpn():
        terminar_procesos_openvpn()
    restantes = _propios_vivos({pid_sesion} if pid_sesion else set())
    _borrar_sesion()
    detalle = ""
    if restantes:
        detalle = ("Quedó un proceso de OpenVPN de la app sin "
                   "cerrar (PID "
                   + ", ".join(str(i.get("pid")) for i in restantes)
                   + "): si la tarjeta sigue ocupada, reinicia el "
                     "equipo.")
        _anotar_actividad_vpn("Desconexión de la VPN: " + detalle)
    return {"ok": True,
            "mensaje": "VPN desconectada: OpenVPN bajó el túnel.",
            "detalle": detalle, "datos": {}}


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


def _grupos_de_sesion(texto_whoami: str) -> set:
    """Los nombres de grupo (minúsculas) de un `whoami /groups`.

    Función pura: cada línea del listado trae el nombre del
    grupo (a veces con el dominio delante, «PC\\OpenVPN
    Administrators») en su primera columna.
    """
    grupos = set()
    for linea in (texto_whoami or "").splitlines():
        # Las columnas de whoami van separadas por tabuladores o
        # por dos o más espacios.
        nombre = re.split(r"\t|\s{2,}", linea.strip())[0].strip()
        if "\\" in nombre:
            nombre = nombre.rsplit("\\", 1)[-1]
        if nombre:
            grupos.add(nombre.lower())
    return grupos


def _usuario_en_grupo_sesion() -> bool:
    """¿La SESIÓN actual ya trae el grupo «OpenVPN Administrators»?

    La pertenencia a un grupo se fija al INICIAR SESIÓN: si el
    instalador acaba de añadir al usuario, su sesión aún no lo
    refleja y el Interactive Service seguirá rechazando su
    perfil hasta que cierre sesión una vez. `whoami /groups`
    enseña la membresía EFECTIVA de esta sesión.
    """
    if not es_windows():
        return False
    try:
        r = subprocess.run(["whoami", "/groups"], capture_output=True,
                           text=True, errors="replace", timeout=15,
                           creationflags=_SIN_VENTANA)
        return GRUPO_ADMIN_OPENVPN.lower() in _grupos_de_sesion(
            r.stdout or "")
    except Exception:
        return False


def _usuario_en_grupo_directorio() -> bool:
    """¿El usuario consta en el grupo según el directorio local?

    `net localgroup "OpenVPN Administrators"`: distingue «ya
    añadido pero la sesión no lo refleja» (cierre de sesión
    pendiente) de «no está en el grupo».
    """
    if not es_windows():
        return False
    try:
        import getpass

        usuario = (getpass.getuser() or "").lower()
        if not usuario:
            return False
        r = subprocess.run(["net", "localgroup", GRUPO_ADMIN_OPENVPN],
                           capture_output=True, text=True,
                           errors="replace", timeout=15,
                           creationflags=_SIN_VENTANA)
        if r.returncode != 0:
            return False
        for linea in (r.stdout or "").splitlines():
            nombre = linea.strip()
            if "\\" in nombre:
                nombre = nombre.rsplit("\\", 1)[-1]
            if nombre.lower() == usuario:
                return True
        return False
    except Exception:
        return False


def _servicio_interactivo_activo() -> bool:
    """¿El OpenVPNServiceInteractive está corriendo?"""
    try:
        return bool(estado_servicio(
            SERVICIO_INTERACTIVO_OPENVPN).get("corriendo"))
    except Exception:
        return False


def puerta_previa_openvpn() -> dict:
    """La puerta previa a conectar (v1.0.12).

    Devuelve {"listo", "via", "aviso", "motivo"}:
    - via "servicio": el Interactive Service corre y la sesión
      ya trae el grupo — la vía principal está abierta.
    - via "elevado": el servicio no corre, o el usuario no está
      en el grupo, o está añadido pero su sesión aún no lo
      refleja (aviso de cierre de sesión pendiente): se usa la
      reserva elevada para este intento.
    - listo=False SOLO si falta el ejecutable. El adaptador NO
      bloquea: su detección es por nombre en la lista de Windows
      y puede fallar (DCO con otro nombre, permisos); si la
      tarjeta falta de verdad, openvpn muere con su error real y
      el clasificador lo reporta como familia «tarjeta». La
      ausencia detectada queda como AVISO. Fuera de Windows
      (pruebas) la puerta no bloquea.
    """
    resultado = {"listo": True, "via": "servicio", "aviso": "",
                 "motivo": ""}
    if not es_windows():
        return resultado
    if not openvpn_instalado():
        return {"listo": False, "via": "servicio", "aviso": "",
                "motivo": "OpenVPN no está instalado en este "
                          "equipo: instala (o reinstala) la app."}
    if not hay_tap_windows():
        resultado["aviso"] = (
            "Windows no muestra la tarjeta virtual de OpenVPN "
            "(TAP-Windows/DCO) en su lista de adaptadores: si la "
            "conexión falla por la tarjeta, reinstala la app para "
            "que su instalador la deje en su sitio.")
    if not _servicio_interactivo_activo():
        resultado["via"] = "elevado"
        resultado["aviso"] = (resultado["aviso"] + " " + (
            "El servicio interactivo de OpenVPN no está corriendo: "
            "este intento se lanzará elevado.")).strip()
        return resultado
    if _usuario_en_grupo_sesion():
        return resultado
    if _usuario_en_grupo_directorio():
        resultado["via"] = "elevado"
        resultado["aviso"] = (resultado["aviso"] + " " + (
            "Ya estás en el grupo «OpenVPN Administrators», pero "
            "esta sesión de Windows aún no lo refleja: CIERRA "
            "SESIÓN una vez y vuelve a entrar para que la VPN use "
            "su vía normal. Este intento se lanzará elevado "
            "mientras tanto.")).strip()
        return resultado
    resultado["via"] = "elevado"
    resultado["aviso"] = (resultado["aviso"] + " " + (
        "Tu usuario no está en el grupo «OpenVPN Administrators» "
        "(el instalador de la app lo deja hecho): este intento se "
        "lanzará elevado. Si se repite, reinstala la app.")).strip()
    return resultado


def diagnostico_openvpn() -> dict:
    """Mini-diagnóstico de integración del motor OpenVPN.

    Reúne la evidencia de que el OpenVPN incorporado está bien
    integrado: openvpn.exe localizado en su ruta real, su versión,
    el servicio interactivo registrado, la tarjeta TAP presente y
    si hay túnel. No conecta nada: solo comprueba.
    """
    diag = {"instalado": False, "ruta_exe": "", "version": "",
            "servicio": {}, "tap": None, "conectado": False,
            "instalador_conservado": "",
            "servicio_interactivo": False, "grupo_sesion": False,
            "grupo_directorio": False, "via": ""}
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
    # v1.0.12: la puerta previa también forma parte del
    # diagnóstico (servicio interactivo, grupo y vía de arranque).
    diag["servicio_interactivo"] = _servicio_interactivo_activo()
    diag["grupo_sesion"] = _usuario_en_grupo_sesion()
    diag["grupo_directorio"] = _usuario_en_grupo_directorio()
    diag["via"] = puerta_previa_openvpn()["via"]
    diag["conectado"] = estado_openvpn()["conectado"]
    return diag


_ = sys  # (compatibilidad de imports en empaquetado)
