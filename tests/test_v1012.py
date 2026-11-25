"""v1.0.12 — La VPN por el Interactive Service, sin huérfanos.

La prueba de la 1.0.11 en la Toughbook cerró el diagnóstico: el
túnel abría («Initialization Sequence Completed») pero Windows
negaba las rutas (CreateIpForwardEntry, Access is denied,
status=5) porque la app lanzaba openvpn.exe por Popen sin
privilegios ni servicio; ese fallo NO es fatal para OpenVPN y el
intento dejó un openvpn.exe HUÉRFANO sujetando la TAP; y el
clasificador convirtió una línea informativa del adaptador en el
titular falso «no pudo abrir su tarjeta virtual». Esta suite
fija la 1.0.12:

- el protocolo del tubo del Interactive Service contra un
  servicio FALSO (mensaje de arranque byte a byte en UNA sola
  escritura: directorio, opciones sin argv[0] y stdin, en UTF-16
  con nulos; la respuesta con el PID y los errores Win32 y
  propios del servicio 0x2000000x);
- el clasificador con el registro REAL de la Toughbook: rutas →
  familia «rutas», jamás «tarjeta»;
- el ciclo de vida con procesos falsos: excepción en la espera,
  doble clic, timeout y cierre → cero procesos vivos y sesión
  borrada; el barrido solo cierra huérfanos PROPIOS (perfil de
  la app o PID de sesión), nunca ajenos;
- la puerta previa (servicio/grupo/adaptador) y su aviso de
  cierre de sesión pendiente;
- el instalador: grupo «OpenVPN Administrators», servicio
  interactivo y el script grupo_openvpn.ps1.
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
    yield
    vpn_win._PROCESO = None


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

# El registro REAL del intento de la 1.0.11 en la Toughbook del
# usuario (foto del 2026-11-25): el túnel inicializó y SOLO
# fallaron las rutas, por privilegios.
REGISTRO_REAL_TOUGHBOOK = [
    "2026-11-25 11:30:02 NOTE: --persist-key is deprecated",
    "2026-11-25 11:30:03 OpenVPN 2.7.9 built on Oct 2026",
    "2026-11-25 11:30:04 Opening TAP-Windows adapter "
    "'OpenVPN TAP-Windows6' succeeded",
    "2026-11-25 11:30:05 TAP-Windows MTU=1500",
    "2026-11-25 11:30:06 C:\\Windows\\system32\\route.exe ADD "
    "0.0.0.0 MASK 128.0.0.0 10.211.1.46",
    "2026-11-25 11:30:06 route addition failed using "
    "CreateIpForwardEntry: Access is denied. [status=5 if_index=60]",
    "2026-11-25 11:30:06 C:\\Windows\\system32\\route.exe ADD "
    "128.0.0.0 MASK 128.0.0.0 10.211.1.46",
    "2026-11-25 11:30:06 route addition failed using "
    "CreateIpForwardEntry: Access is denied. [status=5 if_index=60]",
    "2026-11-25 11:30:07 Initialization Sequence Completed",
]


# === 1. El protocolo del tubo, byte a byte ====================================

def test_mensaje_arranque_byte_a_byte():
    datos = vpn_win._mensaje_arranque_servicio(
        "C:\\carpeta", "--config perfil.ovpn --management 127.0.0.1 9", "")
    esperado = ("C:\\carpeta\0--config perfil.ovpn "
                "--management 127.0.0.1 9\0\0").encode("utf-16-le")
    assert datos == esperado


def test_opciones_sin_argv0_y_con_comillas():
    opciones = vpn_win._opciones_desde_argumentos(
        ["C:\\Program Files\\OpenVPN\\bin\\openvpn.exe",
         "--config", "C:\\Users\\NEW USER\\vpn\\vpngate-activo.ovpn"])
    assert "openvpn.exe" not in opciones.split("--config")[0]
    assert opciones.startswith("--config")
    # La ruta con espacios va entrecomillada para el parseo del servicio.
    assert '"C:\\Users\\NEW USER\\vpn\\vpngate-activo.ovpn"' in opciones


def test_respuesta_servicio_pid():
    datos = "0x00000000\n0x00001A2B\nProcess ID".encode("utf-16-le")
    resp = vpn_win._interpretar_respuesta_servicio(datos)
    assert resp["ok"] is True
    assert resp["pid"] == 0x1A2B
    assert resp["codigo"] == 0


def test_respuesta_servicio_error_win32():
    datos = ("0x00000005\nCreateFile\nAccess is denied."
             ).encode("utf-16-le")
    resp = vpn_win._interpretar_respuesta_servicio(datos)
    assert resp["ok"] is False
    assert resp["codigo"] == 5
    assert resp["funcion"] == "CreateFile"
    assert "denied" in resp["mensaje"]


def test_respuesta_servicio_error_propio():
    datos = ("0x20000000\nOpenVPNServiceInteractive\n"
             "No se pudo arrancar").encode("utf-16-le")
    resp = vpn_win._interpretar_respuesta_servicio(datos)
    assert resp["ok"] is False
    assert resp["codigo"] == 0x20000000
    assert vpn_win.ERRORES_SERVICIO_OPENVPN[0x20000000]


class _KernelFalso:
    """Un kernel32 falso que se comporta como el tubo del servicio."""

    def __init__(self, respuesta: bytes, error_apertura: int = 0):
        self.respuesta = respuesta
        self.error_apertura = error_apertura
        self.escrituras = []
        self.cerrado = False

    def _funciones(self):
        def CreateFileW(*args):
            if self.error_apertura:
                return ctypes.c_void_p(-1).value
            return 4242

        def GetLastError():
            return self.error_apertura

        def WaitNamedPipeW(*args):
            return 1

        def SetNamedPipeHandleState(*args):
            return 1

        def WriteFile(handle, datos, n, escritos, overlapped):
            self.escrituras.append(bytes(datos))
            puntero = ctypes.cast(
                escritos, ctypes.POINTER(wintypes.DWORD))
            puntero.contents.value = n
            return 1

        def ReadFile(handle, buffer, n, leidos, overlapped):
            ctypes.memmove(buffer, self.respuesta,
                           len(self.respuesta))
            puntero = ctypes.cast(
                leidos, ctypes.POINTER(wintypes.DWORD))
            puntero.contents.value = len(self.respuesta)
            return 1

        def CloseHandle(handle):
            self.cerrado = True
            return 1

        ns = type("K", (), {})()
        ns.CreateFileW = CreateFileW
        ns.GetLastError = GetLastError
        ns.WaitNamedPipeW = WaitNamedPipeW
        ns.SetNamedPipeHandleState = SetNamedPipeHandleState
        ns.WriteFile = WriteFile
        ns.ReadFile = ReadFile
        ns.CloseHandle = CloseHandle
        return ns


def test_lanzar_por_servicio_contra_servicio_falso(monkeypatch):
    respuesta = "0x00000000\n0x00001A2B\nProcess ID".encode("utf-16-le")
    falso = _KernelFalso(respuesta)
    monkeypatch.setattr(vpn_win, "_kernel32", falso._funciones)
    monkeypatch.setattr(vpn_win, "es_windows", lambda: True)
    proceso = vpn_win._lanzar_por_servicio(
        ["C:\\OpenVPN\\bin\\openvpn.exe", "--config",
         "C:\\Users\\NEW USER\\vpn\\vpngate-activo.ovpn",
         "--management", "127.0.0.1", "54321"],
        "C:\\Users\\NEW USER\\vpn")
    # El PID que devuelve el servicio y la vía quedan en el proceso.
    assert proceso.pid == 0x1A2B
    assert proceso.via == "servicio"
    # UNA sola escritura, con el mensaje exacto del protocolo.
    assert len(falso.escrituras) == 1
    esperado = vpn_win._mensaje_arranque_servicio(
        "C:\\Users\\NEW USER\\vpn",
        vpn_win._opciones_desde_argumentos(
            ["x", "--config",
             "C:\\Users\\NEW USER\\vpn\\vpngate-activo.ovpn",
             "--management", "127.0.0.1", "54321"]), "")
    assert falso.escrituras[0] == esperado
    # El tubo cliente se cierra tras recibir el PID.
    assert falso.cerrado is True


def test_lanzar_por_servicio_error_del_servicio(monkeypatch):
    respuesta = ("0x00000005\nIsServiceAdmin\nAccess is denied."
                 ).encode("utf-16-le")
    falso = _KernelFalso(respuesta)
    monkeypatch.setattr(vpn_win, "_kernel32", falso._funciones)
    monkeypatch.setattr(vpn_win, "es_windows", lambda: True)
    with pytest.raises(vpn_win._ErrorServicioOpenVPN) as exc:
        vpn_win._lanzar_por_servicio(["openvpn.exe", "--config", "x"],
                                      "C:\\vpn")
    assert exc.value.codigo == 5
    assert falso.cerrado is True


def test_lanzar_por_servicio_tubo_ausente(monkeypatch):
    falso = _KernelFalso(b"", error_apertura=2)  # ERROR_FILE_NOT_FOUND
    monkeypatch.setattr(vpn_win, "_kernel32", falso._funciones)
    monkeypatch.setattr(vpn_win, "es_windows", lambda: True)
    with pytest.raises(vpn_win._ErrorServicioOpenVPN) as exc:
        vpn_win._lanzar_por_servicio(["openvpn.exe"], "C:\\vpn")
    assert exc.value.codigo == 2


def test_lanzar_openvpn_cae_a_elevado(monkeypatch, tmp_path):
    """Si el servicio no responde, la reserva elevada arranca y
    el proceso lo dice (aviso + vía)."""
    class _Elevado:
        via = "elevado"
        pid = 31337
        aviso = ""

    def _sin_servicio(argumentos, carpeta):
        raise vpn_win._ErrorServicioOpenVPN("sin tubo", codigo=2)

    monkeypatch.setattr(vpn_win, "es_windows", lambda: True)
    monkeypatch.setattr(vpn_win, "_lanzar_por_servicio", _sin_servicio)
    monkeypatch.setattr(vpn_win, "_lanzar_elevado",
                        lambda a, c: _Elevado())
    proceso = vpn_win._lanzar_openvpn(["openvpn.exe", "--config", "x"],
                                      str(tmp_path))
    assert proceso.via == "elevado"
    assert "ELEVADO" in proceso.aviso


def test_lanzar_openvpn_ambas_vias_fallan(monkeypatch, tmp_path):
    def _falla(argumentos, carpeta):
        raise vpn_win._ErrorServicioOpenVPN("causa servicio")

    def _falla2(argumentos, carpeta):
        raise vpn_win._ErrorServicioOpenVPN("causa elevado")

    monkeypatch.setattr(vpn_win, "es_windows", lambda: True)
    monkeypatch.setattr(vpn_win, "_lanzar_por_servicio", _falla)
    monkeypatch.setattr(vpn_win, "_lanzar_elevado", _falla2)
    with pytest.raises(vpn_win._ErrorServicioOpenVPN) as exc:
        vpn_win._lanzar_openvpn(["openvpn.exe"], str(tmp_path))
    assert "causa servicio" in str(exc.value)
    assert "causa elevado" in str(exc.value)


# === 2. El clasificador con el registro REAL ==================================

def test_clasificador_registro_real_es_rutas_no_tarjeta():
    analisis = vpn_win._analizar_registro(REGISTRO_REAL_TOUGHBOOK)
    assert analisis["familia"] == "rutas"
    assert analisis["rutas_fallidas"] is True
    assert analisis["inicializacion_completa"] is True
    assert "CreateIpForwardEntry" in analisis["causa"]
    mensaje, _detalle = vpn_win._mensaje_familia(
        analisis["familia"], analisis["causa"], "vpn123.opengw.net")
    assert "rutas" in mensaje
    assert "no es la tarjeta ni el servidor" in mensaje.lower() \
        or "No es la tarjeta ni el servidor" in mensaje
    assert "tarjeta virtual" not in mensaje


def test_clasificador_linea_informativa_tap_no_es_causa():
    # SOLO líneas informativas del adaptador: ninguna puede ser
    # la causa (el titular falso de la 1.0.11 nace aquí).
    lineas = ["Opening TAP-Windows adapter 'X' succeeded",
              "TAP-Windows MTU=1500",
              "Data Channel Offload (ovpn-dco) is not used"]
    analisis = vpn_win._analizar_registro(lineas)
    assert analisis["familia"] != "tarjeta"
    mensaje, _ = vpn_win._clasificar_fallo_openvpn(
        analisis["causa"], 1, "vpn123.opengw.net")
    assert "tarjeta virtual" not in mensaje


def test_clasificador_tarjeta_solo_apertura_real():
    for linea in ("Cannot open TUN/TAP device: ovpn-dco error",
                  "CreateFile failed on tap-windows6 device",
                  "All tap-windows6 adapters on this system are "
                  "currently in use or disabled."):
        analisis = vpn_win._analizar_registro([linea])
        assert analisis["familia"] == "tarjeta", linea


def test_clasificador_rutas_antes_que_tarjeta():
    lineas = ["Opening TAP-Windows adapter succeeded",
              "route addition failed using CreateIpForwardEntry: "
              "Access is denied. [status=5 if_index=60]"]
    analisis = vpn_win._analizar_registro(lineas)
    assert analisis["familia"] == "rutas"


def test_clasificador_registro_real_1131_tap_ocupada():
    """El registro REAL del intento de las 11:31:14 de la 1.0.11
    (servidor vpn312735118, foto del usuario): el TLS fue fino y
    la TAP estaba OCUPADA por el huérfano del intento de las
    11:30. La 1.0.11 lo clasificó MAL como TLS («cortó la
    conexión al comprobar los certificados… servidor caído o
    saturado»). El clasificador de la 1.0.12 debe dar la familia
    del ADAPTADOR, jamás TLS/servidor. (El caso «en uso» lo
    ataja además la capa de ciclo de vida antes de lanzar: el
    barrido cierra el huérfano propio y un openvpn ajeno con la
    tarjeta produce el aviso «Otro OpenVPN está usando la
    tarjeta virtual…» sin lanzar nada.)
    """
    registro = [
        "OPTIONS IMPORT: reading options from vpngate-activo.ovpn",
        "NOTE: --cipher is not set, using AES-128-CBC",
        "interactive service msg_channel=0",
        "ROUTE_GATEWAY 172.20.10.1 I=21",
        "open_tun",
        "CreateFile failed on tap-windows6 device: "
        "\\\\.\\Global\\{79BE79B2-4E8C-45A9-AFEF-C5B900A4A048}.tap: "
        "General failure (ERROR_GEN_FAILURE) (errno=31)",
        "create_adapter: could not talk to service: The handle is "
        "invalid. [6]",
        "All tap-windows6 adapters on this system are currently "
        "in use or disabled.",
        "Exiting due to fatal error",
    ]
    analisis = vpn_win._analizar_registro(registro)
    assert analisis["familia"] == "tarjeta"
    assert "CreateFile failed" in analisis["causa"]
    mensaje, _ = vpn_win._mensaje_familia(
        analisis["familia"], analisis["causa"],
        "vpn312735118.opengw.net")
    assert "TLS" not in mensaje
    assert "saturado" not in mensaje


# === 3. Ciclo de vida: cero huérfanos ==========================================

class _ProcVivo:
    """Un openvpn falso que nunca muere solo ni confirma."""

    def __init__(self, pid=4321):
        self.pid = pid
        self.returncode = None
        self.terminado = False
        self.matado = False
        self.via = "servicio"
        self.aviso = ""

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminado = True
        self.returncode = 0

    def kill(self):
        self.matado = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode


def _preparar_motor(monkeypatch, proceso, mgmt=""):
    monkeypatch.setattr(vpn_win, "_lanzar_openvpn",
                        lambda a, c, r="": proceso)
    monkeypatch.setattr(vpn_win, "_mgmt_enviar",
                        lambda puerto, comando, timeout=5: mgmt)


def test_excepcion_en_la_espera_no_deja_huerfano(entorno, monkeypatch):
    _exe_falso(entorno, monkeypatch)
    proceso = _ProcVivo()
    _preparar_motor(monkeypatch, proceso)

    def _mgmt_roto(puerto, comando, timeout=5):
        raise RuntimeError("la interfaz explotó")

    monkeypatch.setattr(vpn_win, "_mgmt_enviar", _mgmt_roto)
    # interpretar_estado revienta DESPUÉS de recibir la salida:
    # la excepción sale del bucle y el finally debe limpiar.
    monkeypatch.setattr(vpn_win, "_mgmt_enviar",
                        lambda p, c, timeout=5: ">STATE:x")
    monkeypatch.setattr(
        vpn_win, "interpretar_estado_mgmt",
        lambda salida: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        vpn_win.conectar_openvpn(PERFIL, "vpn123.opengw.net", espera=6)
    assert proceso.terminado or proceso.matado
    assert vpn_win._PROCESO is None
    assert vpn_win._leer_sesion() == {}


def test_doble_conectar_cierra_el_anterior(entorno, monkeypatch):
    _exe_falso(entorno, monkeypatch)
    primero = _ProcVivo(pid=1111)
    _preparar_motor(monkeypatch, primero)
    r1 = vpn_win.conectar_openvpn(PERFIL, "vpn123.opengw.net", espera=6)
    assert r1["ok"] is False
    assert primero.terminado  # el timeout ya lo bajó

    segundo = _ProcVivo(pid=2222)
    # El primero «revive» como intento en curso: el segundo
    # Conectar debe cerrarlo limpiamente ANTES de empezar.
    vpn_win._PROCESO = primero
    primero.terminado = False
    primero.returncode = None
    _preparar_motor(monkeypatch, segundo)
    r2 = vpn_win.conectar_openvpn(PERFIL, "vpn999.opengw.net", espera=6)
    assert r2["ok"] is False
    assert primero.terminado  # cerrado por la guarda de un intento
    assert segundo.terminado  # y el suyo por su propio timeout
    assert vpn_win._PROCESO is None
    assert vpn_win._leer_sesion() == {}


def test_cerrar_intento_en_curso_baja_el_proceso(entorno, monkeypatch):
    _exe_falso(entorno, monkeypatch)
    proceso = _ProcVivo()
    vpn_win._PROCESO = proceso
    vpn_win._guardar_sesion({"hostname": "vpn123.opengw.net",
                             "puerto": 54321, "pid": proceso.pid,
                             "desde": time.time(),
                             "estado": "conectando"})
    monkeypatch.setattr(vpn_win, "_mgmt_enviar",
                        lambda p, c, timeout=5: "")
    assert vpn_win.cerrar_intento_en_curso() is True
    assert proceso.terminado
    assert vpn_win._PROCESO is None
    assert vpn_win._leer_sesion() == {}
    # Un túnel CONFIRMADO no se toca.
    vpn_win._guardar_sesion({"hostname": "vpn123.opengw.net",
                             "puerto": 54321, "pid": 999,
                             "desde": time.time(),
                             "estado": "conectada"})
    assert vpn_win.cerrar_intento_en_curso() is False
    vpn_win._borrar_sesion()


def test_conectado_con_rutas_fallidas_se_baja_limpio(entorno,
                                                    monkeypatch):
    """El caso REAL de la Toughbook: gestión confirma, pero el
    registro dice que las rutas fallaron → «túnel abierto pero
    sin rutas», ok=False y proceso cerrado."""
    _exe_falso(entorno, monkeypatch)
    proceso = _ProcVivo()

    def _lanzar(argumentos, carpeta, ruta_salida=""):
        with open(os.path.join(carpeta, "openvpn-conexion.log"),
                  "w", encoding="utf-8") as f:
            f.write("\n".join(REGISTRO_REAL_TOUGHBOOK))
        return proceso

    monkeypatch.setattr(vpn_win, "_lanzar_openvpn", _lanzar)
    monkeypatch.setattr(
        vpn_win, "_mgmt_enviar",
        lambda p, c, timeout=5:
            ">STATE:1,CONNECTED,SUCCESS,10.211.1.17,1.2.3.4,1194")
    r = vpn_win.conectar_openvpn(PERFIL, "vpn123.opengw.net", espera=6)
    assert r["ok"] is False
    assert "sin rutas" in r["mensaje"]
    assert proceso.terminado  # bajado limpio por el finally
    assert vpn_win._PROCESO is None
    assert vpn_win._leer_sesion() == {}


def test_proceso_muerto_con_rutas_no_dice_tarjeta(entorno, monkeypatch):
    """El titular de la foto de la 1.0.11, al revés: muerto con el
    registro real → familia rutas, jamás «tarjeta virtual»."""
    _exe_falso(entorno, monkeypatch)

    class _ProcMuerto:
        pid = 777
        returncode = 1
        via = "servicio"
        aviso = ""

        def poll(self):
            return 1

    def _lanzar(argumentos, carpeta, ruta_salida=""):
        with open(os.path.join(carpeta, "openvpn-conexion.log"),
                  "w", encoding="utf-8") as f:
            f.write("\n".join(REGISTRO_REAL_TOUGHBOOK))
        return _ProcMuerto()

    monkeypatch.setattr(vpn_win, "_lanzar_openvpn", _lanzar)
    monkeypatch.setattr(vpn_win, "_mgmt_enviar",
                        lambda p, c, timeout=5: "")
    r = vpn_win.conectar_openvpn(PERFIL, "vpn123.opengw.net", espera=6)
    assert r["ok"] is False
    assert "sin rutas" in r["mensaje"]
    assert "tarjeta virtual" not in r["mensaje"]
    assert "Código de salida de OpenVPN: 1" in r["detalle"]


# === 4. El barrido: solo huérfanos PROPIOS =====================================

def test_barrido_solo_cierra_los_propios(entorno, monkeypatch):
    carpeta = vpn_win.carpeta_perfiles_vpn()
    perfil = os.path.join(carpeta, "vpngate-activo.ovpn")
    llamadas = {"n": 0}

    def _detalle():
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            return [
                {"pid": 777, "nombre": "openvpn.exe",
                 "cmdline": f'openvpn.exe --config "{perfil}"'},
                {"pid": 888, "nombre": "openvpn.exe",
                 "cmdline": "openvpn.exe --config "
                            "C:\\otro\\perfil-ajeno.ovpn"},
            ]
        return []

    terminados = []
    monkeypatch.setattr(vpn_win, "_procesos_openvpn_detalle", _detalle)
    monkeypatch.setattr(
        vpn_win, "_terminar_pid",
        lambda pid, forzar=False: terminados.append(pid) or True)
    cerrados = vpn_win._barrido_huerfanos()
    assert cerrados == [777]
    assert terminados == [777]  # el ajeno (888) jamás se toca


def test_ajeno_vivo_bloquea_con_aviso_honesto(entorno, monkeypatch):
    _exe_falso(entorno, monkeypatch)
    monkeypatch.setattr(
        vpn_win, "_procesos_openvpn_detalle",
        lambda: [{"pid": 888, "nombre": "openvpn.exe",
                  "cmdline": "openvpn.exe --config C:\\otro\\x.ovpn"}])
    r = vpn_win.conectar_openvpn(PERFIL, "vpn123.opengw.net", espera=6)
    assert r["ok"] is False
    assert "Otro OpenVPN" in r["mensaje"]


# === 5. La puerta previa ========================================================

def test_grupos_de_sesion_parsea_whoami():
    texto = ("Grupo                                  Tipo\r\n"
             "====================================== ================\r\n"
             "BUILTIN\\Administrators                 Alias\r\n"
             "PC\\OpenVPN Administrators              Alias\r\n")
    grupos = vpn_win._grupos_de_sesion(texto)
    assert "openvpn administrators" in grupos
    assert "administrators" in grupos


def test_puerta_fuera_de_windows_no_bloquea(monkeypatch):
    monkeypatch.setattr(vpn_win, "es_windows", lambda: False)
    puerta = vpn_win.puerta_previa_openvpn()
    assert puerta["listo"] is True
    assert puerta["via"] == "servicio"


def test_puerta_sesion_sin_reflejar_avisa_y_usa_elevado(monkeypatch):
    monkeypatch.setattr(vpn_win, "es_windows", lambda: True)
    monkeypatch.setattr(vpn_win, "openvpn_instalado", lambda: True)
    monkeypatch.setattr(vpn_win, "hay_tap_windows", lambda: True)
    monkeypatch.setattr(vpn_win, "_servicio_interactivo_activo",
                        lambda: True)
    monkeypatch.setattr(vpn_win, "_usuario_en_grupo_sesion",
                        lambda: False)
    monkeypatch.setattr(vpn_win, "_usuario_en_grupo_directorio",
                        lambda: True)
    puerta = vpn_win.puerta_previa_openvpn()
    assert puerta["listo"] is True
    assert puerta["via"] == "elevado"
    assert "CIERRA" in puerta["aviso"] and "SESIÓN" in puerta["aviso"]


def test_puerta_sin_tarjeta_no_bloquea_solo_avisa(monkeypatch):
    # La detección del adaptador es por nombre y puede fallar:
    # no bloquea (si la tarjeta falta de verdad, openvpn muere
    # con su error real y el clasificador dice «tarjeta»).
    monkeypatch.setattr(vpn_win, "es_windows", lambda: True)
    monkeypatch.setattr(vpn_win, "openvpn_instalado", lambda: True)
    monkeypatch.setattr(vpn_win, "hay_tap_windows", lambda: False)
    monkeypatch.setattr(vpn_win, "_servicio_interactivo_activo",
                        lambda: True)
    monkeypatch.setattr(vpn_win, "_usuario_en_grupo_sesion",
                        lambda: True)
    puerta = vpn_win.puerta_previa_openvpn()
    assert puerta["listo"] is True
    assert "tarjeta virtual" in puerta["aviso"]


def test_puerta_sin_openvpn_si_bloquea(monkeypatch):
    monkeypatch.setattr(vpn_win, "es_windows", lambda: True)
    monkeypatch.setattr(vpn_win, "openvpn_instalado", lambda: False)
    puerta = vpn_win.puerta_previa_openvpn()
    assert puerta["listo"] is False
    assert "no está instalado" in puerta["motivo"]


def test_diagnostico_trae_puerta_y_grupo(entorno, monkeypatch):
    _exe_falso(entorno, monkeypatch)
    diag = vpn_win.diagnostico_openvpn()
    for clave in ("servicio_interactivo", "grupo_sesion",
                  "grupo_directorio", "via"):
        assert clave in diag


# === 6. El instalador: grupo y servicio ========================================

def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def test_instalador_v1012_grupo_y_servicio():
    raiz = os.path.join(os.path.dirname(__file__), "..")
    iss = _leer(os.path.join(raiz, "packaging", "instalador.iss"))
    assert "grupo_openvpn.ps1" in iss
    assert "PrepararGrupoOpenVPN" in iss
    assert "openvpn-instalacion.txt" in iss
    ps1 = _leer(os.path.join(raiz, "packaging", "grupo_openvpn.ps1"))
    assert "OpenVPN Administrators" in ps1
    assert "Get-LocalGroup" in ps1 and "New-LocalGroup" in ps1
    assert "Add-LocalGroupMember" in ps1
    assert "OpenVPNServiceInteractive" in ps1
    assert "Get-Service" in ps1 and "Start-Service" in ps1
    # El usuario objetivo es el de la sesión interactiva, no
    # necesariamente la cuenta elevada del instalador.
    assert "Win32_ComputerSystem" in ps1


def test_pagina_un_solo_intento_y_cancelar_al_cerrar():
    raiz = os.path.join(os.path.dirname(__file__), "..")
    pagina = _leer(os.path.join(
        raiz, "antivirus_hogar_pc", "modules", "net", "page.py"))
    assert "_vpn_conectando" in pagina
    assert "cancelar_intento_vpn" in pagina
    servicios = _leer(os.path.join(
        raiz, "antivirus_hogar_pc", "modules", "net",
        "servicios_red.py"))
    assert "def cancelar_intento_vpn" in servicios
    assert "cerrar_intento_en_curso" in servicios
