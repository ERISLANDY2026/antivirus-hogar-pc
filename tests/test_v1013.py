"""v1.0.13 — La app ya no se mata su propio intento.

La prueba de la 1.0.12 en la Toughbook REFUTÓ la conexión con
un patrón nuevo, probado con TRES registros reales (12:44,
12:48 y 12:50): cada intento murió EN SU PRIMER SEGUNDO con
«MANAGEMENT: CMD 'signal SIGTERM'» en su propio registro, y la
auditoría (INVESTIGACION-VPN-V1010.md, «PRUEBA v1.0.12»)
probó que el SIGTERM lo enviaba la propia app:

1. El servicio lanza openvpn ELEVADO y la app, sin elevar, no
   siempre puede inspeccionar ese proceso (permiso denegado);
   la comprobación de vida de la 1.0.12 colapsaba «no pude
   mirarlo» en «está muerto», el bucle declaraba la muerte en
   la primera vuelta y el finally apagaba por gestión a un
   OpenVPN vivo — con un «código de salida 0» fabricado.
2. El titular culpó al TLS porque la advertencia rutinaria
   «No server certificate verification method…» trae la
   palabra «certificate», marca de esa familia.
3. El detalle pintó el registro fósil de las 11:31 porque
   caía a openvpn-arranque.txt, un archivo que la 1.0.12 ya
   no escribe.

Esta suite fija la 1.0.13:

- vida en TRES estados (vivo/muerto/no_comprobable): «no
  comprobable» jamás es muerte ni dispara limpieza; la muerte
  exige dos pruebas positivas;
- los tres registros reales como fixtures: familia
  «detenido» (la app detuvo el intento), jamás TLS;
- un intento «vivo pero no comprobable» NO recibe SIGTERM
  antes del timeout real, y el timeout se reporta como lo que
  es: la app detuvo el intento;
- el detalle es hermético: solo el registro de ESTE intento;
  el fósil de arranque no se filtra aunque exista en disco;
- el código de salida solo se pinta si es real: muerte
  probada con código ilegible → «no disponible», nunca 0;
- la puerta previa manda: conectar honra su vía.
"""
import ctypes
import os
import time
from ctypes import wintypes

import pytest

from antivirus_hogar_pc.winapi import vpn_win


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    vpn_win._PROCESO = None
    vpn_win._VIA_PREFERIDA = ""
    yield
    vpn_win._PROCESO = None
    vpn_win._VIA_PREFERIDA = ""


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    """Config de la app en un temporal (patrón de la suite)."""
    local = tmp_path / "Local"
    roaming = tmp_path / "Roaming"
    local.mkdir()
    roaming.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("AHOGAR_LOCAL", str(local))
    monkeypatch.setenv("AHOGAR_ROAMING", str(roaming))
    return tmp_path


def _exe_falso(tmp_path, monkeypatch):
    exe = tmp_path / "openvpn.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(vpn_win, "ruta_openvpn_exe",
                        lambda: str(exe))
    return str(exe)


PERFIL = ("client\n"
          "dev tun\n"
          "remote 203.0.113.7 1194 udp\n"
          "ca [inline]\n")

# === Los TRES registros reales de la Toughbook (fotos del usuario) ============
#
# Cada intento de la 1.0.12 murió en su primer segundo con el
# SIGTERM de la propia app. Se reproducen fieles a las fotos de
# openvpn-conexion.log del 2026-11-25.

_CABECERA = [
    "Note: cipher 'AES-128-CBC' in --data-ciphers is not supported "
    "by ovpn-dco, disabling data channel offload.",
    "WARNING: Using --management on a TCP port WITHOUT passwords "
    "is STRONGLY discouraged and considered insecure",
    "OpenVPN 2.7.9 [git:v2.7.9/7b60c2aa34992639] Windows [SSL "
    "(OpenSSL)] [LZO] [LZ4] [PKCS11] [AEAD] [DCO] built on "
    "Nov 12 2026",
    "Windows version: 10.0.19045,amd64",
    "library versions: OpenSSL 3.6.5 29 Sep 2026, LZO 2.10",
    "DCO version: 2.8.15",
]

_ADVERTENCIA_CERT = (
    "WARNING: No server certificate verification method has been "
    "enabled.  See http://openvpn.net/howto.html#mitm for more "
    "info.")

REGISTRO_REAL_1244 = [
    f"2026-11-25 12:44:45 {linea}" for linea in _CABECERA
] + [
    "2026-11-25 12:44:45 MANAGEMENT: TCP Socket listening on "
    "[AF_INET]127.0.0.1:64124",
    f"2026-11-25 12:44:45 {_ADVERTENCIA_CERT}",
    "2026-11-25 12:44:45 TCP/UDP: Preserving recently used "
    "remote address: [AF_INET]27.130.33.137:1974",
    "2026-11-25 12:44:45 Socket Buffers: R=[65536->65536] "
    "S=[65536->65536]",
    "2026-11-25 12:44:45 UDPv4 link local: (not bound)",
    "2026-11-25 12:44:45 UDPv4 link remote: "
    "[AF_INET]27.130.33.137:1974",
    "2026-11-25 12:44:45 TLS: Initial packet from "
    "[AF_INET]27.130.33.137:1974, sid=dfe2c668 2bc8b7fa",
    "2026-11-25 12:44:45 WARNING: this configuration may cache "
    "passwords in memory -- use the auth-nocache option to "
    "prevent this",
    "2026-11-25 12:44:45 MANAGEMENT: Client connected from "
    "[AF_INET]127.0.0.1:64125",
    "2026-11-25 12:44:45 MANAGEMENT: CMD 'signal SIGTERM'",
    "2026-11-25 12:44:45 SIGTERM[hard,] received, process exiting",
]

REGISTRO_REAL_1248 = [
    f"2026-11-25 12:48:47 {linea}" for linea in _CABECERA
] + [
    "2026-11-25 12:48:47 MANAGEMENT: TCP Socket listening on "
    "[AF_INET]127.0.0.1:64179",
    f"2026-11-25 12:48:47 {_ADVERTENCIA_CERT}",
    "2026-11-25 12:48:47 TCP/UDP: Preserving recently used "
    "remote address: [AF_INET]110.163.142.88:5555",
    "2026-11-25 12:48:47 Socket Buffers: R=[65536->65536] "
    "S=[65536->65536]",
    "2026-11-25 12:48:47 Attempting to establish TCP connection "
    "with [AF_INET]110.163.142.88:5555",
    "2026-11-25 12:48:47 TCP connection established with "
    "[AF_INET]110.163.142.88:5555",
    "2026-11-25 12:48:47 Socket flags: TCP_NODELAY=1 succeeded",
    "2026-11-25 12:48:47 TCPv4_CLIENT link local: (not bound)",
    "2026-11-25 12:48:47 TCPv4_CLIENT link remote: "
    "[AF_INET]110.163.142.88:5555",
    "2026-11-25 12:48:47 MANAGEMENT: Client connected from "
    "[AF_INET]127.0.0.1:64180",
    "2026-11-25 12:48:47 MANAGEMENT: CMD 'signal SIGTERM'",
    "2026-11-25 12:48:47 SIGTERM[hard,] received, process exiting",
]

REGISTRO_REAL_1250 = [
    f"2026-11-25 12:50:29 {linea}" for linea in _CABECERA
] + [
    "2026-11-25 12:50:29 MANAGEMENT: TCP Socket listening on "
    "[AF_INET]127.0.0.1:64201",
    f"2026-11-25 12:50:29 {_ADVERTENCIA_CERT}",
    "2026-11-25 12:50:29 TCP/UDP: Preserving recently used "
    "remote address: [AF_INET]113.23.60.86:995",
    "2026-11-25 12:50:29 Socket Buffers: R=[65536->65536] "
    "S=[65536->65536]",
    "2026-11-25 12:50:29 Attempting to establish TCP connection "
    "with [AF_INET]113.23.60.86:995",
    "2026-11-25 12:50:29 TCP connection established with "
    "[AF_INET]113.23.60.86:995",
    "2026-11-25 12:50:29 Socket flags: TCP_NODELAY=1 succeeded",
    "2026-11-25 12:50:29 TCPv4_CLIENT link local: (not bound)",
    "2026-11-25 12:50:29 TCPv4_CLIENT link remote: "
    "[AF_INET]113.23.60.86:995",
    "2026-11-25 12:50:29 MANAGEMENT: Client connected from "
    "[AF_INET]127.0.0.1:64202",
    "2026-11-25 12:50:29 MANAGEMENT: CMD 'signal SIGTERM'",
    "2026-11-25 12:50:29 SIGTERM[hard,] received, process exiting",
]

REGISTROS_REALES = (REGISTRO_REAL_1244, REGISTRO_REAL_1248,
                    REGISTRO_REAL_1250)


# === 1. Los registros reales: «detenido por la app», jamás TLS =================

@pytest.mark.parametrize("registro", REGISTROS_REALES)
def test_registro_real_es_detenido_no_tls(registro):
    analisis = vpn_win._analizar_registro(registro)
    assert analisis["familia"] == "detenido"
    mensaje, _detalle = vpn_win._mensaje_familia(
        analisis["familia"], analisis["causa"],
        "vpn855688522.opengw.net")
    assert "La propia app detuvo" in mensaje
    assert "TLS" not in mensaje
    assert "certificados" not in mensaje
    assert "saturado" not in mensaje


def test_advertencia_certificado_a_solas_no_es_tls():
    # La línea que engañó al clasificador de la 1.0.12: es una
    # advertencia rutinaria de arranque, informativa expresa.
    assert vpn_win._es_linea_error(_ADVERTENCIA_CERT) is False
    assert vpn_win._familia_de_linea(_ADVERTENCIA_CERT) == ""
    analisis = vpn_win._analizar_registro([_ADVERTENCIA_CERT])
    assert analisis["familia"] != "tls"


def test_advertencias_rutinarias_nunca_son_causa():
    for linea in (
            _ADVERTENCIA_CERT,
            "WARNING: this configuration may cache passwords in "
            "memory -- use the auth-nocache option to prevent "
            "this",
            "DEPRECATED OPTION: --persist-key option ignored. "
            "Keys are now always persisted across restarts.",
            "NOTE: --persist-key is deprecated",
            "Note: cipher 'AES-128-CBC' in --data-ciphers is not "
            "supported by ovpn-dco, disabling data channel "
            "offload."):
        assert vpn_win._es_linea_error(linea) is False, linea
        assert vpn_win._familia_de_linea(linea) == "", linea


def test_tls_exige_error_tls_real():
    for linea in ("TLS Error: TLS key negotiation failed to "
                  "occur within 60 seconds (check your network "
                  "connectivity)",
                  "TLS handshake failed",
                  "VERIFY ERROR: depth=0, error=unable to get "
                  "local issuer certificate",
                  "Authenticate/Decrypt packet error: bad packet "
                  "ID"):
        analisis = vpn_win._analizar_registro([linea])
        assert analisis["familia"] == "tls", linea


# === 2. Vida en tres estados ===================================================

class _KernelVida:
    """kernel32 falso para la costura del SO de _estado_pid."""

    def __init__(self, error_apertura=0, codigo=259,
                 lectura_ok=True):
        self.error_apertura = error_apertura
        self.codigo = codigo
        self.lectura_ok = lectura_ok

    def _funciones(self):
        def OpenProcess(*args):
            if self.error_apertura:
                return 0
            return 777

        def GetLastError():
            return self.error_apertura

        def GetExitCodeProcess(handle, puntero):
            if not self.lectura_ok:
                return 0
            destino = ctypes.cast(
                puntero, ctypes.POINTER(ctypes.c_ulong))
            destino.contents.value = self.codigo
            return 1

        def CloseHandle(handle):
            return 1

        ns = type("K", (), {})()
        ns.OpenProcess = OpenProcess
        ns.GetLastError = GetLastError
        ns.GetExitCodeProcess = GetExitCodeProcess
        ns.CloseHandle = CloseHandle
        return ns


def _con_kernel(monkeypatch, kernel):
    monkeypatch.setattr(vpn_win, "es_windows", lambda: True)
    monkeypatch.setattr(vpn_win, "_kernel32", kernel._funciones)


def test_estado_pid_acceso_denegado_es_no_comprobable(monkeypatch):
    # EL mecanismo del fallo real: el proceso elevado no se deja
    # abrir (ERROR_ACCESS_DENIED=5) → «no_comprobable», con el
    # error viajando. La 1.0.12 devolvía «no vivo» y la app
    # mataba el intento.
    _con_kernel(monkeypatch, _KernelVida(error_apertura=5))
    estado, error = vpn_win._estado_pid_con_error(1234)
    assert estado == "no_comprobable"
    assert error == 5
    assert vpn_win._estado_pid(1234) == "no_comprobable"
    assert vpn_win._pid_vivo(1234) is False  # ojo: NO es muerte


def test_estado_pid_inexistente_es_muerto(monkeypatch):
    # ERROR_INVALID_PARAMETER (87): ese PID no existe — prueba
    # positiva de muerte.
    _con_kernel(monkeypatch, _KernelVida(error_apertura=87))
    assert vpn_win._estado_pid(1234) == "muerto"


def test_estado_pid_vivo_y_muerto_por_codigo(monkeypatch):
    _con_kernel(monkeypatch, _KernelVida(codigo=259))
    assert vpn_win._estado_pid(1234) == "vivo"
    assert vpn_win._pid_vivo(1234) is True
    _con_kernel(monkeypatch, _KernelVida(codigo=1))
    assert vpn_win._estado_pid(1234) == "muerto"


def test_estado_pid_lectura_fallida_es_no_comprobable(monkeypatch):
    _con_kernel(monkeypatch, _KernelVida(lectura_ok=False))
    assert vpn_win._estado_pid(1234) == "no_comprobable"


def test_poll_no_comprobable_devuelve_none_no_cero(monkeypatch):
    """poll() con la inspección denegada devuelve None (sigue
    en curso) y returncode queda en None: imposible fabricar
    el código de salida 0 de la 1.0.12."""
    anotaciones = []
    monkeypatch.setattr(vpn_win, "_anotar_actividad_vpn",
                        anotaciones.append)
    monkeypatch.setattr(vpn_win, "_estado_pid_con_error",
                        lambda pid: ("no_comprobable", 5))
    proceso = vpn_win._ProcesoPorPid(2468)
    assert proceso.poll() is None
    assert proceso.returncode is None
    assert vpn_win._codigo_para_pintar(proceso) is None
    # La primera «no comprobable» queda anotada, con su error.
    assert anotaciones and "5" in anotaciones[0]


def test_poll_muerto_sin_codigo_no_fabrica_cero(monkeypatch):
    monkeypatch.setattr(vpn_win, "_estado_pid_con_error",
                        lambda pid: ("muerto", None))
    monkeypatch.setattr(vpn_win, "_codigo_salida_pid",
                        lambda pid: None)
    proceso = vpn_win._ProcesoPorPid(2468)
    assert proceso.poll() == vpn_win._CODIGO_SALIDA_DESCONOCIDO
    assert proceso.poll() != 0
    assert proceso.returncode is None
    assert vpn_win._codigo_para_pintar(proceso) is None


def test_poll_muerto_con_codigo_real(monkeypatch):
    monkeypatch.setattr(vpn_win, "_estado_pid_con_error",
                        lambda pid: ("muerto", None))
    monkeypatch.setattr(vpn_win, "_codigo_salida_pid",
                        lambda pid: 3)
    proceso = vpn_win._ProcesoPorPid(2468)
    assert proceso.poll() == 3
    assert proceso.returncode == 3
    assert vpn_win._codigo_para_pintar(proceso) == 3


def test_poll_elevado_no_fabrica_cero(monkeypatch):
    """El mango elevado: WAIT_OBJECT_0 prueba la muerte; si el
    código no se puede leer, returncode queda en None (la
    1.0.12 ponía 0). WAIT_TIMEOUT = sigue en curso."""
    class _KernelElevado:
        def __init__(self, espera, lectura_ok):
            self.espera = espera
            self.lectura_ok = lectura_ok

        def _funciones(self):
            def WaitForSingleObject(handle, ms):
                return self.espera

            def GetExitCodeProcess(handle, puntero):
                return 1 if self.lectura_ok else 0

            ns = type("K", (), {})()
            ns.WaitForSingleObject = WaitForSingleObject
            ns.GetExitCodeProcess = GetExitCodeProcess
            return ns

    monkeypatch.setattr(
        vpn_win, "_kernel32",
        _KernelElevado(258, True)._funciones)  # WAIT_TIMEOUT
    proceso = vpn_win._ProcesoElevado(999, 1357)
    assert proceso.poll() is None

    monkeypatch.setattr(
        vpn_win, "_kernel32",
        _KernelElevado(0, False)._funciones)  # murió, código ilegible
    assert proceso.poll() == vpn_win._CODIGO_SALIDA_DESCONOCIDO
    assert proceso.returncode is None
    assert vpn_win._codigo_para_pintar(proceso) is None


# === 3. El intento «vivo pero no comprobable» no se toca =======================

_ESTADO_CONECTANDO = (">STATE:1700000000,CONNECTING,PROBE,,"
                      "198.51.100.7,1194\nEND")


def test_no_comprobable_sin_sigterm_antes_del_timeout(
        entorno, monkeypatch):
    """LA regresión del fallo real, de punta a punta: el mango
    es un _ProcesoPorPid de verdad cuya vida da siempre «no
    comprobable» (el caso del openvpn elevado que la app no
    puede mirar) y la gestión responde CONNECTING. El bucle NO
    puede enviar SIGTERM antes del timeout real ni clasificar
    TLS: al vencer la espera, el resultado dice que LA APP
    detuvo el intento."""
    _exe_falso(entorno, monkeypatch)
    estado = {"valor": "no_comprobable"}
    monkeypatch.setattr(
        vpn_win, "_estado_pid_con_error",
        lambda pid: (estado["valor"], 5))
    monkeypatch.setattr(vpn_win, "_codigo_salida_pid",
                        lambda pid: None)

    def _terminar(pid, forzar=False):
        estado["valor"] = "muerto"
        return True

    monkeypatch.setattr(vpn_win, "_terminar_pid", _terminar)
    proceso = vpn_win._ProcesoPorPid(987654)
    proceso.via = "servicio"
    monkeypatch.setattr(vpn_win, "_lanzar_openvpn",
                        lambda a, c, r="": proceso)
    comandos = []

    def _mgmt(puerto, comando, timeout=5):
        comandos.append((time.monotonic(), comando))
        if comando == "state":
            return _ESTADO_CONECTANDO
        return "SUCCESS: signal SIGTERM thrown"

    monkeypatch.setattr(vpn_win, "_mgmt_enviar", _mgmt)
    inicio = time.monotonic()
    res = vpn_win.conectar_openvpn(PERFIL, "vpn123.opengw.net",
                                   espera=5)
    assert res["ok"] is False
    # Honestidad: la app detuvo el intento; ni TLS ni saturado.
    assert "La app detuvo el intento" in res["mensaje"]
    assert "TLS" not in res["mensaje"]
    assert "saturado" not in res["mensaje"]
    # Ningún SIGTERM antes del timeout real (~5 s): durante la
    # espera solo se preguntó «state».
    sigterms = [t for t, c in comandos if "SIGTERM" in c]
    assert sigterms, "la limpieza final sí debe bajar el proceso"
    assert all(t - inicio >= 4.5 for t in sigterms)
    assert all(c == "state" for t, c in comandos
               if t - inicio < 4.5)
    # Y el proceso quedó cerrado por la limpieza, sin huérfano.
    assert proceso.poll() is not None
    assert vpn_win._PROCESO is None
    assert vpn_win._leer_sesion() == {}


# === 4. Detalle hermético y timeout honesto ====================================

class _ProcVivo:
    """Un openvpn falso que nunca muere solo ni confirma."""

    def __init__(self, pid=4321):
        self.pid = pid
        self.returncode = None
        self.terminado = False
        self.via = "servicio"
        self.aviso = ""

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminado = True
        self.returncode = 0

    def kill(self):
        self.terminado = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode


class _ProcMuerto:
    pid = 777
    returncode = 1
    via = "servicio"
    aviso = ""

    def poll(self):
        return 1

    def wait(self, timeout=None):
        return 1

    def terminate(self):
        pass

    def kill(self):
        pass


def test_detalle_hermetico_el_fosil_no_se_filtra(entorno,
                                                monkeypatch):
    """Con un openvpn-arranque.txt FOSILIZADO en disco (con su
    texto marcador), el resultado de un intento por la vía
    servicio NO puede contener ese marcador: el detalle sale
    solo del registro de ESTE intento — y si este intento no
    dejó registro, lo dice («sin registro»)."""
    _exe_falso(entorno, monkeypatch)
    carpeta = vpn_win.carpeta_perfiles_vpn()
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, "openvpn-arranque.txt"),
              "w", encoding="utf-8") as f:
        f.write("MARCADOR-FOSIL-1131 CreateFile failed on "
                "tap-windows6 device\nExiting due to fatal error\n")
    monkeypatch.setattr(vpn_win, "_lanzar_openvpn",
                        lambda a, c, r="": _ProcMuerto())
    monkeypatch.setattr(vpn_win, "_mgmt_enviar",
                        lambda p, c, timeout=5: "")
    res = vpn_win.conectar_openvpn(PERFIL, "vpn123.opengw.net",
                                   espera=5)
    assert res["ok"] is False
    assert "MARCADOR-FOSIL-1131" not in res["detalle"]
    assert "MARCADOR-FOSIL-1131" not in res["mensaje"]
    assert "sin dejar registro" in res["mensaje"]
    assert res["datos"]["codigo_salida"] == 1


def test_timeout_sin_registro_dice_sin_registro(entorno,
                                                monkeypatch):
    _exe_falso(entorno, monkeypatch)
    monkeypatch.setattr(vpn_win, "_lanzar_openvpn",
                        lambda a, c, r="": _ProcVivo())
    monkeypatch.setattr(
        vpn_win, "_mgmt_enviar",
        lambda p, c, timeout=5: _ESTADO_CONECTANDO)
    res = vpn_win.conectar_openvpn(PERFIL, "vpn123.opengw.net",
                                   espera=5)
    assert res["ok"] is False
    assert "La app detuvo el intento" in res["mensaje"]
    assert res["detalle"] == vpn_win._DETALLE_SIN_REGISTRO
    assert "Sin registro todavía" in res["detalle"]


def test_timeout_con_registro_detalle_de_este_intento(
        entorno, monkeypatch):
    """El detalle del timeout sale del registro de ESTE
    intento (sus últimas líneas), no de ningún fósil."""
    _exe_falso(entorno, monkeypatch)

    def _lanzar(argumentos, carpeta, ruta_salida=""):
        with open(os.path.join(carpeta, "openvpn-conexion.log"),
                  "w", encoding="utf-8") as f:
            f.write("\n".join(REGISTRO_REAL_1244))
        return _ProcVivo()

    monkeypatch.setattr(vpn_win, "_lanzar_openvpn", _lanzar)
    monkeypatch.setattr(
        vpn_win, "_mgmt_enviar",
        lambda p, c, timeout=5: _ESTADO_CONECTANDO)
    res = vpn_win.conectar_openvpn(PERFIL, "vpn123.opengw.net",
                                   espera=5)
    assert res["ok"] is False
    assert "La app detuvo el intento" in res["mensaje"]
    assert "TLS: Initial packet" in res["detalle"]
    assert "12:44:45" in res["detalle"]


def test_muerte_con_codigo_ilegible_dice_no_disponible(
        entorno, monkeypatch):
    """Muerte probada pero código de salida ilegible: el
    detalle dice «no disponible» y datos lo trae como None —
    jamás el 0 fabricado de la 1.0.12."""
    _exe_falso(entorno, monkeypatch)
    monkeypatch.setattr(vpn_win, "_estado_pid_con_error",
                        lambda pid: ("muerto", None))
    monkeypatch.setattr(vpn_win, "_codigo_salida_pid",
                        lambda pid: None)
    proceso = vpn_win._ProcesoPorPid(31337)
    proceso.via = "servicio"

    def _lanzar(argumentos, carpeta, ruta_salida=""):
        with open(os.path.join(carpeta, "openvpn-conexion.log"),
                  "w", encoding="utf-8") as f:
            f.write("Cannot open TUN/TAP device: ovpn-dco "
                    "error\nExiting due to fatal error\n")
        return proceso

    monkeypatch.setattr(vpn_win, "_lanzar_openvpn", _lanzar)
    monkeypatch.setattr(vpn_win, "_mgmt_enviar",
                        lambda p, c, timeout=5: "")
    res = vpn_win.conectar_openvpn(PERFIL, "vpn123.opengw.net",
                                   espera=5)
    assert res["ok"] is False
    assert "tarjeta virtual" in res["mensaje"]
    assert "Código de salida de OpenVPN: no disponible." \
        in res["detalle"]
    assert "Código de salida de OpenVPN: 0" not in res["detalle"]
    assert res["datos"]["codigo_salida"] is None


# === 5. La puerta previa manda =================================================

def test_lanzar_honra_la_via_elevada_de_la_puerta(monkeypatch):
    """Con _VIA_PREFERIDA="elevado", el lanzador prueba la
    reserva elevada PRIMERO (el servicio ni se toca)."""
    monkeypatch.setattr(vpn_win, "es_windows", lambda: True)
    monkeypatch.setattr(vpn_win, "_VIA_PREFERIDA", "elevado")

    class _Elevado:
        via = "elevado"
        pid = 111
        aviso = ""

    def _servicio_prohibido(argumentos, carpeta):
        raise AssertionError("el servicio no debía tocarse")

    monkeypatch.setattr(vpn_win, "_lanzar_por_servicio",
                        _servicio_prohibido)
    monkeypatch.setattr(vpn_win, "_lanzar_elevado",
                        lambda a, c: _Elevado())
    proceso = vpn_win._lanzar_openvpn(["openvpn.exe"], "C:\\vpn")
    assert proceso.via == "elevado"
    assert "puerta previa" in proceso.aviso


def test_lanzar_elevado_fallido_cae_al_servicio(monkeypatch):
    monkeypatch.setattr(vpn_win, "es_windows", lambda: True)
    monkeypatch.setattr(vpn_win, "_VIA_PREFERIDA", "elevado")

    class _Servicio:
        via = "servicio"
        pid = 222
        aviso = ""

    def _elevado_roto(argumentos, carpeta):
        raise vpn_win._ErrorServicioOpenVPN("sin elevación",
                                            codigo=1223)

    monkeypatch.setattr(vpn_win, "_lanzar_elevado", _elevado_roto)
    monkeypatch.setattr(vpn_win, "_lanzar_por_servicio",
                        lambda a, c: _Servicio())
    proceso = vpn_win._lanzar_openvpn(["openvpn.exe"], "C:\\vpn")
    assert proceso.via == "servicio"
    assert "reserva elevada" in proceso.aviso


def test_conectar_pasa_la_via_de_la_puerta(entorno, monkeypatch):
    """conectar_openvpn fija _VIA_PREFERIDA con la vía de la
    puerta antes de lanzar y la deja limpia al salir."""
    _exe_falso(entorno, monkeypatch)
    monkeypatch.setattr(
        vpn_win, "puerta_previa_openvpn",
        lambda: {"listo": True, "via": "elevado",
                 "aviso": "", "motivo": ""})
    vistas = {}

    def _lanzar(argumentos, carpeta, ruta_salida=""):
        vistas["via"] = vpn_win._VIA_PREFERIDA
        return _ProcVivo()

    monkeypatch.setattr(vpn_win, "_lanzar_openvpn", _lanzar)
    monkeypatch.setattr(vpn_win, "_mgmt_enviar",
                        lambda p, c, timeout=5: "")
    res = vpn_win.conectar_openvpn(PERFIL, "vpn123.opengw.net",
                                   espera=5)
    assert res["ok"] is False
    assert vistas["via"] == "elevado"
    assert vpn_win._VIA_PREFERIDA == ""


# === 6. Contenido: la versión y las notas =======================================

def test_version_1013_en_su_sitio():
    raiz = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(raiz, "packaging", "instalador.iss"),
              encoding="utf-8") as f:
        iss = f.read()
    assert '#define AppVersion "1.0.22"' in iss
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.core import notas_version
    assert config.VERSION == "1.0.22"
    assert notas_version.NOTAS_VERSION[0]["version"] == "1.0.22"
