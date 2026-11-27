"""v1.0.14 — Lista unificada multifuente, failover y sonda real.

Lo que fija esta suite (diseño A+B+C de
FACTIBILIDAD-ESCANEO-FUENTES.md, aprobado por el usuario):

1. `ServidorVPN` gana el campo `fuente` (default «vpngate»: los
   constructores posicionales de siempre no se rompen) y las
   credenciales son POR FUENTE (VPN Gate «vpn»/«vpn»; VPNBook
   «vpnbook» + la contraseña vigente, jamás quemada).
2. VPNBook se extrae por máquina: credenciales y hostnames de
   su página; configs de su endpoint oficial; semilla verificada
   de respaldo SIN contraseña.
3. Fusión deduplicada por destino real (host/puerto/proto del
   remoto, no por hostname) y validación estructural (etapa 0).
4. Caché buena en disco: un refresco fallido NUNCA la toca.
5. Veredictos con caducidad (verificado 30 min, AUTH_FAILED
   15 min) y orden «Recomendado»: verificados primero, luego
   pocas sesiones y más uptime — la velocidad deja de mandar.
6. Plan de sondas con presupuesto y saltos (veredictos vigentes
   no se re-sondean; VPNBook repartido).
7. La sonda de winapi: credenciales por parámetro escritas en
   el archivo, perfil con route-nopull y éxito al PUSH_REPLY.
8. El failover del servicio: ante familias del servidor salta
   al siguiente candidato y anota veredictos; ante un fallo
   local NO salta; si todos rechazan, el mensaje dice «llenos
   o fuera de servicio» sin culpar a la credencial.
9. El refresco de fondo respeta la cadencia de ~30 min.
10. La tabla de la página: 8 columnas, marca de fuente y sello
    de verificación por fila.
"""
import base64
import json
import os
import time

import pytest

from antivirus_hogar_pc import config
from antivirus_hogar_pc.contracts import ResultadoModulo
from antivirus_hogar_pc.core import fuentes_vpn as fuentes
from antivirus_hogar_pc.core import notas_version
from antivirus_hogar_pc.core.vpngate import ServidorVPN
from antivirus_hogar_pc.winapi import vpn_win

RAIZ = os.path.join(os.path.dirname(__file__), "..")
CLAVE_FALSA = "clave-falsa-de-prueba"


def _leer(ruta_relativa: str) -> str:
    with open(os.path.join(RAIZ, ruta_relativa), encoding="utf-8") as f:
        return f.read()


def _ovpn(host="203.0.113.7", puerto=1194, proto="udp"):
    return (f"client\ndev tun\nremote {host} {puerto} {proto}\n"
            "<ca>\n-----BEGIN CERTIFICATE-----\nX\n"
            "-----END CERTIFICATE-----\n</ca>\n")


def _servidor(hostname="vpn123.opengw.net", fuente="vpngate",
              sesiones=10, uptime=1000, velocidad_bps=50_000_000,
              ovpn=None, pais="Japan", pais_corto="JP"):
    return ServidorVPN(
        hostname=hostname, ip="203.0.113.7", puntuacion=80,
        ping_ms=20, velocidad_bps=velocidad_bps, pais=pais,
        pais_corto=pais_corto, sesiones=sesiones, uptime=uptime,
        total_usuarios=1, operador="operador", mensaje="",
        ovpn_base64=base64.b64encode(
            (ovpn or _ovpn()).encode()).decode(),
        fuente=fuente)


# === 1. Versión y campo fuente ===============================================

def test_version_1014_en_su_sitio():
    assert config.VERSION == "1.0.22"
    assert notas_version.NOTAS_VERSION[0]["version"] == "1.0.22"
    notas = notas_version.notas_de("1.0.14")
    assert notas is not None and len(notas["novedades"]) >= 3
    iss = _leer(os.path.join("packaging", "instalador.iss"))
    assert '#define AppVersion "1.0.22"' in iss


def test_fuente_por_defecto_vpngate_y_constructores_viejos():
    # 13 argumentos posicionales, como los constructores de
    # siempre (fake.py): la fuente queda «vpngate».
    s = ServidorVPN("h", "1.2.3.4", 100, 20, 3, "Japan", "JP",
                    50, 100, 1, "op", "", "b64")
    assert s.fuente == "vpngate"
    assert _servidor(fuente="vpnbook").fuente == "vpnbook"


def test_espejo_jsdelivr_es_la_cuarta_ruta_vpngate():
    assert len(config.VPNGATE_APIS) == 4
    assert "cdn.jsdelivr.net/gh/GeorgeXie2333/vpngate-list-mirror" \
        in config.VPNGATE_APIS[3]
    # Las tres oficiales de siempre van primero.
    assert config.VPNGATE_APIS[0].startswith("https://www.vpngate.net")


def test_credenciales_por_fuente():
    assert fuentes.credenciales_de(_servidor()) == ("vpn", "vpn")
    libro = _servidor(hostname="us16.vpnbook.com", fuente="vpnbook")
    assert fuentes.credenciales_de(libro, CLAVE_FALSA) == (
        "vpnbook", CLAVE_FALSA)
    # Sin clave vigente conocida, VPNBook no inventa ninguna.
    assert fuentes.credenciales_de(libro, "") == ("vpnbook", "")


# === 2. Etapa 0: remoto y validez estructural ================================

def test_extraer_remoto():
    from antivirus_hogar_pc.core.vpngate import extraer_remoto
    assert extraer_remoto(_ovpn()) == {
        "host": "203.0.113.7", "puerto": 1194, "proto": "udp"}
    assert extraer_remoto(
        "client\nproto tcp-client\nremote ejemplo.net 443\n") == {
            "host": "ejemplo.net", "puerto": 443, "proto": "tcp"}
    assert extraer_remoto("client\ndev tun\n") is None
    assert extraer_remoto("") is None


def test_validez_estructural():
    from antivirus_hogar_pc.core.vpngate import (
        config_estructuralmente_valida)
    assert config_estructuralmente_valida(_ovpn()) is True
    assert config_estructuralmente_valida("remote 1.2.3.4 443\n") \
        is False  # sin «client» no es un perfil de cliente
    assert config_estructuralmente_valida("client\ndev tun\n") \
        is False  # sin destino no hay a dónde conectar


# === 3. VPNBook: extracción, endpoint y semilla ==============================

_HTML_VPNBOOK = """
<html><head><script type="application/ld+json">
{"@type":"ItemList","itemListElement":[
 {"@type":"ListItem","name":"us16.vpnbook.com"},
 {"@type":"ListItem","name":"ca149.vpnbook.com"},
 {"@type":"ListItem","name":"uk205.vpnbook.com"}]}
</script></head><body>
<p>OpenVPN Username: vpnbook. Password: {clave}.</p>
<p>Servers: us16.vpnbook.com, ca149.vpnbook.com, uk205.vpnbook.com
and the site www.vpnbook.com itself.</p>
</body></html>
""".replace("{clave}", CLAVE_FALSA)


def test_extraer_credenciales_vpnbook():
    assert fuentes.extraer_credenciales_vpnbook(_HTML_VPNBOOK) == (
        "vpnbook", CLAVE_FALSA)
    assert fuentes.extraer_credenciales_vpnbook("<html></html>") \
        is None


def test_extraer_hostnames_vpnbook():
    hosts = fuentes.extraer_hostnames_vpnbook(_HTML_VPNBOOK)
    assert hosts == ["us16.vpnbook.com", "ca149.vpnbook.com",
                     "uk205.vpnbook.com"]
    assert fuentes.pais_de_hostname_vpnbook("de20.vpnbook.com") == (
        "Germany", "DE")
    assert fuentes.pais_de_hostname_vpnbook("xx1.vpnbook.com") == (
        "", "")


def test_servidor_vpnbook_roundtrip():
    s = fuentes.servidor_vpnbook("us16.vpnbook.com", _ovpn(
        host="us16.vpnbook.com", puerto=443, proto="tcp"))
    assert s.fuente == "vpnbook" and s.pais == "United States"
    assert s.generar_ovpn().startswith("client")


def test_semilla_vpnbook_verificada_y_sin_clave():
    semilla = fuentes.leer_semilla_vpnbook(config.carpeta_activos())
    assert len(semilla) == 10
    assert all(s.fuente == "vpnbook" for s in semilla)
    assert {s.pais_corto for s in semilla} == {
        "US", "CA", "UK", "DE", "FR"}
    from antivirus_hogar_pc.core.vpngate import (
        config_estructuralmente_valida)
    assert all(config_estructuralmente_valida(s.generar_ovpn())
               for s in semilla)
    crudo = _leer(os.path.join(
        "antivirus_hogar_pc", "assets", "vpnbook_seed.json"))
    datos = json.loads(crudo)
    assert "password" not in crudo.lower()
    assert datos["fuente"] == "vpnbook"
    assert len(datos["servidores"]) == 10


def test_vpnbook_en_vivo_con_respaldo_de_semilla(monkeypatch):
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    def _descargar(url, timeout=20):
        if url == fuentes.VPNBOOK_PAGINA:
            return _HTML_VPNBOOK
        if "us16" in url:
            return _ovpn(host="us16.vpnbook.com", puerto=443,
                         proto="tcp") + "# config-en-vivo\n"
        raise RuntimeError("ese servidor no responde")

    monkeypatch.setattr(srv, "_descargar_texto_simple", _descargar)
    servidores, clave = srv._servidores_vpnbook_en_vivo()
    assert clave == CLAVE_FALSA
    por_host = {s.hostname: s for s in servidores}
    # us16 vino del endpoint en vivo; ca149 cayó a la semilla.
    assert "# config-en-vivo" in por_host["us16.vpnbook.com"] \
        .generar_ovpn()
    assert por_host["ca149.vpnbook.com"].fuente == "vpnbook"


# === 4. Fusión, deduplicación y etapa 0 =======================================

def test_fusion_deduplica_por_destino_real():
    gate = _servidor("vpn-a.opengw.net", ovpn=_ovpn())
    libro = _servidor("us16.vpnbook.com", fuente="vpnbook",
                      ovpn=_ovpn())  # MISMO remoto que gate
    otro = _servidor("de20.vpnbook.com", fuente="vpnbook",
                     ovpn=_ovpn(puerto=443, proto="tcp"))
    fusion = fuentes.fusionar_listas([[gate], [libro, otro]])
    assert len(fusion) == 2
    # Ante el mismo destino manda la primera lista (VPN Gate).
    assert fusion[0].hostname == "vpn-a.opengw.net"


def test_filtrar_validas_descarta_sin_destino():
    bueno = _servidor("vpn-a.opengw.net")
    malo = _servidor("vpn-b.opengw.net",
                     ovpn="client\ndev tun\n")  # sin remote
    validas, descartadas = fuentes.filtrar_validas([bueno, malo])
    assert validas == [bueno] and descartadas == 1


# === 5. Caché en disco y veredictos ===========================================

def test_cache_roundtrip(tmp_path):
    ruta = str(tmp_path / "cache.json")
    s1 = _servidor("vpn-a.opengw.net")
    s2 = _servidor("us16.vpnbook.com", fuente="vpnbook")
    veredictos = {}
    fuentes.registrar_veredicto(veredictos, s1, "verificado",
                                ahora=1000.0)
    assert fuentes.guardar_cache(ruta, [s1, s2], veredictos,
                                 CLAVE_FALSA)
    cache = fuentes.cargar_cache(ruta)
    assert [s.hostname for s in cache["servidores"]] == [
        "vpn-a.opengw.net", "us16.vpnbook.com"]
    assert cache["servidores"][1].fuente == "vpnbook"
    assert cache["clave_vpnbook"] == CLAVE_FALSA
    estado, cuando = fuentes.veredicto_de(cache["veredictos"], s1,
                                          ahora=1001.0)
    assert estado == "verificado" and cuando == 1000.0
    # Actualizar SOLO veredictos conserva servidores y clave.
    fuentes.registrar_veredicto(veredictos, s2, "auth_failed",
                                ahora=1002.0)
    assert fuentes.actualizar_veredictos_cache(ruta, veredictos)
    cache2 = fuentes.cargar_cache(ruta)
    assert len(cache2["servidores"]) == 2
    assert fuentes.veredicto_de(cache2["veredictos"], s2,
                                 ahora=1003.0)[0] == "auth_failed"


def test_caducidad_de_veredictos():
    s = _servidor()
    v = {}
    fuentes.registrar_veredicto(v, s, "verificado", ahora=1000.0)
    assert fuentes.rango_veredicto(v, s, ahora=1000.0 + 1799) == 0
    assert fuentes.rango_veredicto(v, s, ahora=1000.0 + 1801) == 2
    fuentes.registrar_veredicto(v, s, "auth_failed", ahora=1000.0)
    assert fuentes.rango_veredicto(v, s, ahora=1000.0 + 899) == 3
    # Caducado (de cualquier tipo): rango 2, peor que «sin
    # verificar» (1) y mejor que un rechazo vigente (3).
    assert fuentes.rango_veredicto(v, s, ahora=1000.0 + 901) == 2


def test_orden_recomendado_verificados_primero():
    lento_verificado = _servidor(
        "vpn-lento.opengw.net", sesiones=90, uptime=100,
        velocidad_bps=1_000_000)
    rapido_sin_verificar = _servidor(
        "vpn-rapido.opengw.net", sesiones=5, uptime=99999,
        velocidad_bps=900_000_000)
    lleno = _servidor("vpn-lleno.opengw.net", sesiones=1,
                      uptime=99999)
    v = {}
    fuentes.registrar_veredicto(v, lento_verificado, "verificado",
                                ahora=1000.0)
    fuentes.registrar_veredicto(v, lleno, "auth_failed",
                                ahora=1000.0)
    orden = fuentes.ordenar_candidatos(
        [rapido_sin_verificar, lleno, lento_verificado], v,
        ahora=1100.0)
    # El verificado MANDA aunque sea el más lento; el rechazado
    # vigente va el último aunque tenga 1 sesión.
    assert [s.hostname for s in orden] == [
        "vpn-lento.opengw.net", "vpn-rapido.opengw.net",
        "vpn-lleno.opengw.net"]


def test_plan_sondas_presupuesto_y_saltos():
    servidores = [
        _servidor(f"vpn-{i}.opengw.net", pais=f"P{i % 2}",
                  pais_corto=f"P{i % 2}") for i in range(10)]
    v = {}
    # El primero ya está verificado y vigente: no se re-sondea.
    fuentes.registrar_veredicto(v, servidores[0], "verificado",
                                ahora=time.time())
    plan = fuentes.plan_sondas(servidores, v, max_por_pais=3,
                               presupuesto_s=45, coste_est_s=20)
    assert servidores[0] not in plan
    assert len(plan) <= 2  # 45 s de presupuesto, ~20 s por sonda
    # VPNBook entra repartido (tope propio por ronda).
    libros = [_servidor(f"us{i}.vpnbook.com", fuente="vpnbook",
                        pais="United States", pais_corto="US")
              for i in range(6)]
    plan2 = fuentes.plan_sondas(libros, {}, max_vpnbook=2,
                                presupuesto_s=300)
    assert len(plan2) == 2


# === 6. El servicio: fusión, caché intocable y poblado ========================

@pytest.fixture()
def srv_limpio(monkeypatch, tmp_path):
    from antivirus_hogar_pc.modules.net import servicios_red as srv

    monkeypatch.setattr(srv.config, "carpeta_datos",
                        lambda: str(tmp_path))
    monkeypatch.setattr(srv, "_ULTIMA_LISTA", [])
    monkeypatch.setattr(srv, "_VEREDICTOS", {})
    monkeypatch.setattr(srv, "_CLAVE_VPNBOOK", "")
    monkeypatch.setattr(srv, "_ESTADO_FUENTES_CARGADO", False)
    return srv


def test_descarga_fusiona_fuentes_y_guarda_cache(srv_limpio,
                                                 monkeypatch):
    srv = srv_limpio
    gate = [_servidor("vpn-a.opengw.net")]
    libro = _servidor("us16.vpnbook.com", fuente="vpnbook",
                      ovpn=_ovpn(puerto=443, proto="tcp"))
    monkeypatch.setattr(
        srv, "descargar_lista_con_respaldo",
        lambda urls: (gate, urls[0]))
    monkeypatch.setattr(srv, "_servidores_vpnbook_en_vivo",
                        lambda: ([libro], CLAVE_FALSA))
    r = srv.descargar_servidores_completos()
    assert r.ok and r.datos["es_semilla"] is False
    assert {s.fuente for s in r.datos["servidores"]} == {
        "vpngate", "vpnbook"}
    assert "VPNBook" in r.mensaje
    # La caché quedó escrita con la clave vigente de VPNBook.
    cache = fuentes.cargar_cache(config.ruta_cache_fuentes_vpn())
    assert cache is not None and cache["clave_vpnbook"] == CLAVE_FALSA


def test_refresco_fallido_no_toca_la_cache(srv_limpio, monkeypatch):
    srv = srv_limpio
    marcador = _servidor("vpn-marcador.opengw.net")
    ruta = config.ruta_cache_fuentes_vpn()
    assert fuentes.guardar_cache(ruta, [marcador], {}, "")
    antes = open(ruta, "rb").read()

    def _caida(urls):
        raise RuntimeError("sin red")

    monkeypatch.setattr(srv, "descargar_lista_con_respaldo", _caida)

    def _caida_libro():
        raise RuntimeError("sin red")

    monkeypatch.setattr(srv, "_servidores_vpnbook_en_vivo",
                        _caida_libro)
    r = srv.descargar_servidores_completos()
    # VPN Gate cae a su semilla (el comportamiento de siempre) y
    # VPNBook a la suya: la lista no queda vacía…
    assert r.ok and r.datos["es_semilla"] is True
    assert any(s.fuente == "vpnbook"
               for s in r.datos["servidores"])
    # …pero la CACHÉ buena anterior queda intacta, byte a byte.
    assert open(ruta, "rb").read() == antes


def test_poblado_inicial_cache_o_semilla(srv_limpio):
    srv = srv_limpio
    # Sin caché: semillas fusionadas (VPN Gate + VPNBook).
    r = srv.servidores_cache_o_semilla()
    assert r.ok and r.datos["es_semilla"] is True
    assert any(s.fuente == "vpnbook" for s in r.datos["servidores"])
    # Con caché: la caché manda y no es «semilla».
    marcador = _servidor("vpn-cache.opengw.net")
    fuentes.guardar_cache(config.ruta_cache_fuentes_vpn(),
                          [marcador], {}, "")
    r2 = srv.servidores_cache_o_semilla()
    assert r2.ok and r2.datos["es_cache"] is True
    assert [s.hostname for s in r2.datos["servidores"]] == [
        "vpn-cache.opengw.net"]


# === 7. La sonda y las credenciales en el motor ===============================

@pytest.fixture()
def entorno_vpn(tmp_path, monkeypatch):
    local = tmp_path / "Local"
    roaming = tmp_path / "Roaming"
    local.mkdir()
    roaming.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("AHOGAR_LOCAL", str(local))
    monkeypatch.setenv("AHOGAR_ROAMING", str(roaming))
    vpn_win._PROCESO = None
    vpn_win._VIA_PREFERIDA = ""
    exe = tmp_path / "openvpn.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(vpn_win, "ruta_openvpn_exe",
                        lambda: str(exe))
    monkeypatch.setattr(
        vpn_win, "puerta_previa_openvpn",
        lambda: {"listo": True, "via": "servicio", "aviso": "",
                 "motivo": ""})
    monkeypatch.setattr(vpn_win, "_procesos_openvpn_detalle",
                        lambda: [])
    yield tmp_path
    vpn_win._PROCESO = None
    vpn_win._VIA_PREFERIDA = ""


class _ProcVivo:
    pid = 4321
    returncode = None
    via = "servicio"
    aviso = ""

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 0

    def kill(self):
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode


_ESTADO_CONECTANDO = (">STATE:1700000000,CONNECTING,PROBE,,"
                      "198.51.100.7,1194\nEND")


def test_sonda_push_reply_verifica_y_no_deja_tunel(
        entorno_vpn, monkeypatch):
    def _lanzar(argumentos, carpeta, ruta_salida=""):
        with open(os.path.join(carpeta, "openvpn-conexion.log"),
                  "w", encoding="utf-8") as f:
            f.write("TLS: Initial packet\n"
                    "PUSH: Received control message: 'PUSH_REPLY,"
                    "redirect-gateway def1'\n")
        return _ProcVivo()

    monkeypatch.setattr(vpn_win, "_lanzar_openvpn", _lanzar)
    monkeypatch.setattr(
        vpn_win, "_mgmt_enviar",
        lambda p, c, timeout=5: (_ESTADO_CONECTANDO
                                 if c == "state" else
                                 "SUCCESS: signal SIGTERM thrown"))
    res = vpn_win.conectar_openvpn(
        _ovpn(), "us16.vpnbook.com", espera=10,
        usuario="vpnbook", clave=CLAVE_FALSA, sonda=True)
    assert res["ok"] is True
    assert res["datos"]["sonda"] is True
    assert res["datos"]["verificado"] is True
    # La sonda no deja túnel ni sesión: el intento se bajó.
    assert vpn_win._PROCESO is None
    assert vpn_win._leer_sesion() == {}
    carpeta = vpn_win.carpeta_perfiles_vpn()
    # Credenciales DE LA FUENTE en el archivo…
    with open(os.path.join(carpeta, "vpngate-credenciales.txt"),
              encoding="utf-8") as f:
        assert f.read() == f"vpnbook\n{CLAVE_FALSA}\n"
    # …y el perfil de la sonda lleva route-nopull.
    with open(os.path.join(carpeta, "vpngate-activo.ovpn"),
              encoding="utf-8") as f:
        assert "route-nopull" in f.read()


def test_sin_sonda_no_hay_route_nopull(entorno_vpn, monkeypatch):
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

    monkeypatch.setattr(vpn_win, "_lanzar_openvpn",
                        lambda a, c, r="": _ProcMuerto())
    monkeypatch.setattr(vpn_win, "_mgmt_enviar",
                        lambda p, c, timeout=5: "")
    res = vpn_win.conectar_openvpn(_ovpn(), "vpn123.opengw.net",
                                   espera=5)
    assert res["ok"] is False
    # Todo fallo del motor trae su familia para el failover.
    assert "familia" in res["datos"]
    carpeta = vpn_win.carpeta_perfiles_vpn()
    with open(os.path.join(carpeta, "vpngate-activo.ovpn"),
              encoding="utf-8") as f:
        assert "route-nopull" not in f.read()
    with open(os.path.join(carpeta, "vpngate-credenciales.txt"),
              encoding="utf-8") as f:
        assert f.read() == "vpn\nvpn\n"  # las de VPN Gate


def test_mensaje_auth_failed_no_culpa_a_la_credencial():
    mensaje, _causa = vpn_win._mensaje_familia(
        "credenciales", "AUTH_FAILED", "vpn123.opengw.net")
    assert "autenticación" in mensaje
    assert "No es tu credencial" in mensaje
    assert "lleno" in mensaje


# === 8. El failover del servicio ==============================================

def _motor_falso(respuestas):
    llamadas = []

    def falso(contenido, hostname, **kw):
        llamadas.append((hostname, kw))
        return respuestas[hostname]

    return falso, llamadas


_FALLO_AUTH = {"ok": False, "mensaje": "El servidor rechazó el "
               "inicio de sesión (autenticación).",
               "detalle": "AUTH_FAILED",
               "datos": {"familia": "credenciales"}}
_OK_MOTOR = {"ok": True, "mensaje": "", "detalle": "",
             "datos": {"via": "openvpn"}}


@pytest.fixture()
def srv_motor(srv_limpio, monkeypatch):
    srv = srv_limpio
    monkeypatch.setattr(srv.vpn_win, "openvpn_instalado",
                        lambda: True)
    monkeypatch.setattr(srv, "_registrar_intento_vpn",
                        lambda detalle: None)
    return srv


def test_failover_salta_al_siguiente_y_anota(srv_motor, monkeypatch):
    srv = srv_motor
    a = _servidor("vpn-lleno.opengw.net", sesiones=100)
    b = _servidor("us16.vpnbook.com", fuente="vpnbook",
                  ovpn=_ovpn(puerto=443, proto="tcp"))
    monkeypatch.setattr(srv, "_CLAVE_VPNBOOK", CLAVE_FALSA)
    falso, llamadas = _motor_falso(
        {a.hostname: dict(_FALLO_AUTH), b.hostname: dict(_OK_MOTOR)})
    monkeypatch.setattr(srv.vpn_win, "conectar_openvpn", falso)
    r = srv.conectar_vpn(a, [a, b])
    assert r.ok and r.datos["conectado"] is True
    assert r.datos["hostname"] == b.hostname
    assert "no aceptó la conexión" in r.mensaje
    assert [h for h, _ in llamadas] == [a.hostname, b.hostname]
    # Cada intento fue con las credenciales de SU fuente.
    assert llamadas[0][1]["usuario"] == "vpn"
    assert llamadas[1][1]["usuario"] == "vpnbook"
    assert llamadas[1][1]["clave"] == CLAVE_FALSA
    # Veredictos: A rechazado, B verificado.
    assert fuentes.veredicto_de(srv._VEREDICTOS, a)[0] == \
        "auth_failed"
    assert fuentes.veredicto_de(srv._VEREDICTOS, b)[0] == \
        "verificado"


def test_failover_todos_llenos_mensaje_honesto(srv_motor,
                                              monkeypatch):
    srv = srv_motor
    a = _servidor("vpn-a.opengw.net")
    b = _servidor("vpn-b.opengw.net")
    falso, llamadas = _motor_falso(
        {a.hostname: dict(_FALLO_AUTH), b.hostname: dict(_FALLO_AUTH)})
    monkeypatch.setattr(srv.vpn_win, "conectar_openvpn", falso)
    r = srv.conectar_vpn(a, [a, b])
    assert r.ok is False
    assert len(llamadas) == 2
    assert "llenos o fuera de servicio" in r.mensaje
    assert "No es tu conexión ni tu credencial" in r.mensaje


def test_failover_no_salta_ante_fallo_local(srv_motor, monkeypatch):
    srv = srv_motor
    a = _servidor("vpn-a.opengw.net")
    b = _servidor("vpn-b.opengw.net")
    fallo_local = {"ok": False, "mensaje": "La tarjeta virtual "
                   "falló en este equipo.", "detalle": "",
                   "datos": {"familia": "local"}}
    falso, llamadas = _motor_falso(
        {a.hostname: fallo_local, b.hostname: dict(_OK_MOTOR)})
    monkeypatch.setattr(srv.vpn_win, "conectar_openvpn", falso)
    r = srv.conectar_vpn(a, [a, b])
    assert r.ok is False
    assert len(llamadas) == 1  # otro servidor no arregla lo local
    assert "tarjeta virtual" in r.mensaje


# === 9. Refresco de fondo: cadencia ===========================================

def test_refresco_fondo_respeta_cadencia(srv_limpio, monkeypatch):
    srv = srv_limpio
    servidor = _servidor("vpn-x.opengw.net")
    monkeypatch.setattr(srv, "_ULTIMA_LISTA", [servidor])
    monkeypatch.setattr(
        srv, "descargar_servidores_completos",
        lambda: ResultadoModulo(ok=True, mensaje="ok", datos={}))
    planes = []

    def _plan_falso(plan, presupuesto_s=180.0):
        planes.append(list(plan))
        return len(plan)

    monkeypatch.setattr(srv, "_sondear_plan", _plan_falso)
    salida = srv.refresco_y_sondas_en_fondo()
    assert salida["refresco"] is True and salida["sondas"] == 1
    # Inmediatamente después NO toca refrescar (cadencia 30 min),
    # pero las sondas pendientes sí pueden correr.
    salida2 = srv.refresco_y_sondas_en_fondo()
    assert salida2["refresco"] is False


# === 10. La página: fuente y sello por fila ====================================

def test_pagina_ocho_columnas_fuente_y_sello():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from antivirus_hogar_pc.contracts import ContextoModulo
    from antivirus_hogar_pc.modules.net import page as netpage
    from antivirus_hogar_pc.modules.net.fake import servidores_fake

    app = QApplication.instance() or QApplication([])
    pagina = netpage._PaginaRed(ContextoModulo(servicios=None))
    servidores = servidores_fake()
    veredictos = {}
    fuentes.registrar_veredicto(veredictos, servidores[0],
                                "verificado")
    pagina._servidores_cargados(ResultadoModulo(
        ok=True, datos={"servidores": servidores,
                        "veredictos": veredictos}))
    tabla = pagina._tabla_vpn
    assert tabla.columnCount() == 8
    assert tabla.rowCount() == 2
    textos = {(tabla.item(i, 1).text()): i
              for i in range(tabla.rowCount())}
    fila_ok = textos[servidores[0].hostname]
    fila_sin = textos[servidores[1].hostname]
    assert tabla.item(fila_ok, 2).text() == "VPN Gate"
    # v1.0.22: el sello positivo dice «✓ Online» (no
    # «Verificado») y va EN VERDE, como pidió el usuario.
    assert tabla.item(fila_ok, 6).text().startswith("✓ Online")
    from PySide6.QtGui import QColor

    from antivirus_hogar_pc.ui import theme as _theme

    assert tabla.item(fila_ok, 6).foreground().color() == QColor(
        _theme.VERDE)
    assert tabla.item(fila_sin, 6).text() == "Sin verificar"
    # La acción vive en la columna 7.
    assert tabla.cellWidget(fila_sin, 7) is not None
    pagina.deleteLater()
    app.processEvents()
