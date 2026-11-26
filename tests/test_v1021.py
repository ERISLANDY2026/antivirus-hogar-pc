"""Pruebas de la v1.0.21: las 9 piezas seguras de la investigación
open source, con sus guardas permanentes.

Guardas clave:
- Ninguna ruta de código sube archivos (VirusTotal y CIRCL solo
  consultan por huella; el módulo de VirusTotal solo hace GET).
- BYOK sin clave = función inerte («sin_configurar», sin red).
- ASR jamás se aplica sin confirmación (la guarda salta ANTES de
  tocar Windows: se prueba en cualquier sistema).
- «Conocido» (CIRCL) nunca se presenta como «seguro».
- El escaneo USB nunca es automático: el temporizador solo
  refresca la detección; escanear exige el clic del usuario.
- La contención anti-ransomware solo existe tras el diálogo de
  procesos (una sola llamada a suspender, dentro de ese diálogo).
"""
import json
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from antivirus_hogar_pc import config  # noqa: E402
from antivirus_hogar_pc.core import (  # noqa: E402
    antiransomware, asr, byovd, dominios_consulta, exclusiones,
    puntuacion, virustotal)


# --- 1. Puntuación de descargas ----------------------------------------------

def test_puntuacion_conocido_no_es_seguro():
    s = puntuacion.Senales(circl="conocido", firma="valida",
                           motw=False, entropia=4.0, es_ejecutable=True)
    p = puntuacion.puntuar(s)
    assert p.nivel == "conocido"  # jamás «seguro»
    assert p.nivel != "seguro"
    assert "circl_conocido" in p.motivos


def test_puntuacion_riesgo_acumula_senales():
    s = puntuacion.Senales(circl="no_conocido", firma="invalida",
                           motw=True, entropia=7.9, es_ejecutable=True)
    p = puntuacion.puntuar(s)
    assert p.nivel == "riesgo"
    for motivo in ("firma_invalida", "motw_internet", "entropia_muy_alta"):
        assert motivo in p.motivos


def test_puntuacion_entropia_solo_en_ejecutables():
    # Un .zip legítimo tiene entropía alta: no debe sumar.
    s = puntuacion.Senales(circl="sin_respuesta", firma="no_disponible",
                           motw=False, entropia=7.99, es_ejecutable=False)
    p = puntuacion.puntuar(s)
    assert "entropia_muy_alta" not in p.motivos
    assert "entropia_alta" not in p.motivos


def test_circl_solo_manda_la_huella(monkeypatch):
    vistas = {}

    class Respuesta:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"FileName": "notepad.exe"}).encode()

    def falso_urlopen(peticion, timeout=0):
        vistas["url"] = peticion.full_url
        return Respuesta()

    monkeypatch.setattr(puntuacion.urllib.request, "urlopen",
                        falso_urlopen)
    estado, nombre = puntuacion.consultar_circl("a" * 64)
    assert estado == "conocido" and nombre == "notepad.exe"
    assert vistas["url"].endswith("/" + "a" * 64)


def test_circl_404_es_no_conocido(monkeypatch):
    import urllib.error

    def falso_urlopen(peticion, timeout=0):
        raise urllib.error.HTTPError(
            peticion.full_url, 404, "no", None, None)

    monkeypatch.setattr(puntuacion.urllib.request, "urlopen",
                        falso_urlopen)
    assert puntuacion.consultar_circl("b" * 64)[0] == "no_conocido"


def test_motw_fuera_de_windows_es_no_comprobable(tmp_path):
    if os.name == "nt":
        pytest.skip("fuera de Windows la marca no se puede comprobar")
    ruta = tmp_path / "x.bin"
    ruta.write_bytes(b"123")
    presente, _origen = puntuacion.leer_motw(str(ruta))
    assert presente is None


# --- 2. Dominios con atribución ------------------------------------------------

@pytest.fixture()
def bases_tmp(tmp_path, monkeypatch):
    datos = tmp_path / "datos"
    activos = tmp_path / "activos"
    datos.mkdir()
    activos.mkdir()
    (activos / "dominios_phishing_db.txt").write_text(
        "# comentario\nmalo-phish.example.com\n", encoding="utf-8")
    (activos / "dominios_feodo.txt").write_text(
        "203.0.113.7\nc2.ejemplo-mal.net\n", encoding="utf-8")
    (activos / "dominios_fusionados.txt").write_text(
        "fusionado.example.org\n", encoding="utf-8")
    (activos / "malware_seed.txt").write_text("", encoding="utf-8")
    (activos / "adblock_seed.txt").write_text("", encoding="utf-8")
    monkeypatch.setattr(config, "carpeta_datos", lambda: str(datos))
    monkeypatch.setattr(config, "carpeta_activos", lambda: str(activos))
    dominios_consulta.invalidar_cache()
    yield
    dominios_consulta.invalidar_cache()


def test_fuente_de_identifica_cada_fuente(bases_tmp):
    assert dominios_consulta.fuente_de("malo-phish.example.com") \
        == dominios_consulta.FUENTE_PHISHING_DB
    # Subdominio: hereda la fuente del dominio padre.
    assert dominios_consulta.fuente_de("sub.malo-phish.example.com") \
        == dominios_consulta.FUENTE_PHISHING_DB
    assert dominios_consulta.fuente_de("203.0.113.7") \
        == dominios_consulta.FUENTE_FEODO
    assert dominios_consulta.fuente_de(
        "https://fusionado.example.org/ruta?x=1") \
        == dominios_consulta.FUENTE_BASE_BLOQUEO
    assert dominios_consulta.fuente_de("limpio.example.com") is None


def test_extraer_feodo_puro():
    ips, hosts = dominios_consulta.extraer_feodo([
        {"ip_address": "1.2.3.4", "hostname": "c2.malo.net"},
        {"ip_address": "5.6.7.8", "hostname": None},
        {"ip_address": "", "hostname": ""},
        "basura",
    ])
    assert ips == ["1.2.3.4", "5.6.7.8"]
    assert hosts == ["c2.malo.net"]


def test_activos_de_datos_reales():
    # Los activos empaquetados existen y son los verificados.
    activos = config.carpeta_activos()
    with open(os.path.join(activos, "dominios_phishing_db.txt"),
              encoding="utf-8") as fh:
        assert sum(1 for _ in fh) > 300_000
    assert byovd.total_base() > 2_000
    manifiesto = json.load(open(
        os.path.join(activos, "fuentes_datos.json"), encoding="utf-8"))
    texto = json.dumps(manifiesto, ensure_ascii=False)
    assert "MIT" in texto and "CC0" in texto
    assert "abuse.ch" in texto  # la nota de no-redistribución


# --- 3. YARA -------------------------------------------------------------------

def _motor_disponible() -> bool:
    try:
        import yara_x  # noqa: F401
        return True
    except Exception:
        pass
    try:
        import yara  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _motor_disponible(),
                    reason="sin bindings YARA en este entorno")
def test_yara_regla_propia_con_autor_y_licencia(tmp_path, monkeypatch):
    from antivirus_hogar_pc.core import yara_scan

    datos = tmp_path / "datos"
    (datos / "yara").mkdir(parents=True)
    (datos / "yara" / "prueba.yar").write_text(
        'rule Prueba_Marcador {\n'
        '  meta:\n'
        '    author = "Equipo de Pruebas"\n'
        '    license = "CC0"\n'
        '    description = "regla de la suite"\n'
        '  strings:\n'
        '    $a = "cadena-marcador-x"\n'
        '  condition:\n'
        '    $a\n'
        '}\n', encoding="utf-8")
    activos = tmp_path / "activos"
    activos.mkdir()
    monkeypatch.setattr(config, "carpeta_datos", lambda: str(datos))
    monkeypatch.setattr(config, "carpeta_activos", lambda: str(activos))
    motor = yara_scan._Motor()
    estado = motor.asegurar()
    assert estado.disponible, estado.motivo
    halladas = motor.escanear_datos(b"xx cadena-marcador-x yy")
    assert len(halladas) == 1
    assert halladas[0].regla == "Prueba_Marcador"
    assert halladas[0].autor == "Equipo de Pruebas"
    assert halladas[0].licencia == "CC0"
    assert motor.escanear_datos(b"limpio") == []


@pytest.mark.skipif(not _motor_disponible(),
                    reason="sin bindings YARA en este entorno")
def test_yara_paquete_forge_compila():
    from antivirus_hogar_pc.core import yara_scan

    estado = yara_scan.estado_motor()
    assert estado.disponible, estado.motivo
    assert estado.archivos_reglas  # el paquete core está empaquetado


def test_yara_sin_motor_no_rompe(monkeypatch):
    from antivirus_hogar_pc.core import yara_scan

    motor = yara_scan._Motor()
    monkeypatch.setattr(motor, "_rutas_reglas", lambda: [])
    estado = motor.asegurar()
    assert not estado.disponible
    assert motor.escanear_datos(b"lo que sea") == []


# --- 4. ASR ----------------------------------------------------------------------

def test_asr_interpretar_estado():
    guid = asr.REGLAS_ASR[0]["guid"]
    estado = asr.interpretar_estado(
        {"ids": [guid], "acciones": [2]})
    assert estado[guid] == "auditoria"
    # Las no listadas quedan desactivadas.
    assert estado[asr.REGLAS_ASR[1]["guid"]] == "desactivada"
    assert asr.accion_para_modo("auditoria") == "AuditMode"
    assert asr.accion_para_modo("bloqueo") == "Block"
    assert asr.accion_para_modo("desactivada") == "Disabled"
    # El preset es conservador: todas admiten auditoría primero.
    assert all(r["auditoria"] for r in asr.REGLAS_ASR)
    assert all(asr.modo_inicial_sugerido(r) == "auditoria"
               for r in asr.REGLAS_ASR)


def test_asr_jamas_sin_confirmacion():
    from antivirus_hogar_pc.winapi import defender

    guid = asr.REGLAS_ASR[0]["guid"]
    res = defender.fijar_regla_asr(guid, "bloqueo", confirmar=False)
    assert res["ok"] is False
    assert res["codigo"] == "sin_confirmacion"
    # La guarda va ANTES de cualquier llamada a Windows: también
    # con una regla inventada se corta primero por confirmación.
    res2 = defender.fijar_regla_asr("NO-EXISTE", "bloqueo",
                                    confirmar=False)
    assert res2["codigo"] == "sin_confirmacion"
    res3 = defender.fijar_regla_asr("NO-EXISTE", "bloqueo",
                                    confirmar=True)
    assert res3["codigo"] == "regla_invalida"


# --- 5. Anti-ransomware ----------------------------------------------------------

def test_senuelos_crear_y_verificar(tmp_path, monkeypatch):
    datos = tmp_path / "datos"
    datos.mkdir()
    carpeta = tmp_path / "docs"
    carpeta.mkdir()
    monkeypatch.setattr(config, "carpeta_datos", lambda: str(datos))
    sembrados = antiransomware.crear_senuelos([str(carpeta)])
    assert sembrados[str(carpeta)]
    assert antiransomware.verificar_senuelos() == []
    # Tocar un señuelo se detecta.
    ruta = sembrados[str(carpeta)][0]
    with open(ruta, "a", encoding="utf-8") as fh:
        fh.write("cifrado")
    assert ruta in antiransomware.verificar_senuelos()


def test_senuelo_no_pisa_archivo_del_usuario(tmp_path, monkeypatch):
    datos = tmp_path / "datos"
    datos.mkdir()
    carpeta = tmp_path / "docs"
    carpeta.mkdir()
    nombre = antiransomware.NOMBRES_SENUELO[0]
    propio = carpeta / nombre
    propio.write_text("contenido del usuario", encoding="utf-8")
    monkeypatch.setattr(config, "carpeta_datos", lambda: str(datos))
    antiransomware.crear_senuelos([str(carpeta)])
    assert propio.read_text(encoding="utf-8") == "contenido del usuario"


def test_rafaga_entropia_alta_dispara_y_baja_no(tmp_path):
    carpeta = tmp_path / "docs"
    carpeta.mkdir()
    rutas = []
    for i in range(antiransomware.UMBRAL_RAFAGA + 2):
        ruta = carpeta / f"f{i}.bin"
        ruta.write_bytes(os.urandom(4096))
        rutas.append(str(ruta))
    ahora = max(os.path.getmtime(r) for r in rutas)
    despues = {r: (os.path.getmtime(r), os.path.getsize(r))
               for r in rutas}
    antes = {r: (m - 10, s - 1) for r, (m, s) in despues.items()}
    alerta = antiransomware.analizar_cambios(antes, despues, ahora=ahora)
    assert alerta is not None and alerta.motivo == "rafaga"
    # Con texto plano (entropía baja) no hay alerta.
    for r in rutas:
        with open(r, "wb") as fh:
            fh.write(b"texto plano repetido " * 200)
    despues2 = {r: (os.path.getmtime(r), os.path.getsize(r))
                for r in rutas}
    assert antiransomware.analizar_cambios(
        antes, despues2, ahora=ahora) is None


def test_antiransomware_nace_en_solo_avisar():
    from antivirus_hogar_pc.ui.services import Ajustes

    assert Ajustes().antiransomware_modo == "avisar"
    # La suspensión solo se invoca desde el diálogo de procesos de
    # la ventana principal (decisión del usuario en el aviso).
    fuente = open(os.path.join(
        RAIZ, "antivirus_hogar_pc", "ui", "main_window.py"),
        encoding="utf-8").read()
    assert fuente.count("suspender_proceso") == 1
    assert fuente.index("suspender_proceso") > fuente.index(
        "def _dialogo_procesos_sospechosos")


# --- 6. Exclusiones ---------------------------------------------------------------

def test_exclusiones_riesgosas():
    assert exclusiones.clasificar_ruta("C:\\")[0] == "alta"
    assert exclusiones.clasificar_ruta(
        "C:\\Users\\Ana\\AppData\\Local\\Temp")[0] == "alta"
    assert exclusiones.clasificar_extension(".exe")[0] == "alta"
    assert exclusiones.clasificar_extension("ps1")[0] == "alta"
    assert exclusiones.clasificar_proceso("powershell.exe")[0] == "alta"
    assert exclusiones.clasificar_ruta(
        "D:\\Juegos\\Mods")[0] == "baja"
    auditoria = exclusiones.auditar(
        {"ruta": ["C:\\", "D:\\Juegos\\Mods"], "extension": [".log"],
         "proceso": [], "ip": []})
    assert auditoria[0]["nivel"] == "alta"  # ordenadas por riesgo
    assert exclusiones.hay_riesgos(auditoria)


# --- 7. BYOVD -----------------------------------------------------------------------

def test_byovd_base_y_consulta():
    base = byovd.cargar_base()
    alguna = next(iter(base))
    assert byovd.revisar_hash(alguna) in ("vulnerable", "malicioso")
    assert byovd.revisar_hash("0" * 64) is None


def test_byovd_archivo_limpio(tmp_path):
    ruta = tmp_path / "driver.sys"
    ruta.write_bytes(os.urandom(2048))
    assert byovd.revisar_archivo(str(ruta)) is None


# --- 8. USB: nunca automático -------------------------------------------------------

def test_usb_nunca_automatico():
    fuente = open(os.path.join(
        RAIZ, "antivirus_hogar_pc", "modules", "security", "page.py"),
        encoding="utf-8").read()
    # El temporizador solo DETECTA (refresca la lista y ofrece);
    # escanear exige el clic en el botón de la unidad.
    assert "temporizador_usb.timeout.connect(lambda: refrescar_usb(True))" \
        in fuente
    assert "timeout.connect" in fuente
    for linea in fuente.splitlines():
        if "timeout.connect" in linea:
            assert "escanear_usb" not in linea


# --- 9. VirusTotal BYOK ---------------------------------------------------------------

def test_vt_sin_clave_es_inerte(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        virustotal.urllib.request, "urlopen",
        lambda *a, **k: llamadas.append(a) or None)
    res = virustotal.consultar_hash("a" * 64, "")
    assert res.estado == "sin_configurar"
    assert llamadas == []  # ni un intento de red


def test_vt_solo_get_por_huella(monkeypatch):
    vistas = {}

    class Respuesta:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"data": {"attributes": {
                "last_analysis_stats": {
                    "malicious": 3, "suspicious": 1,
                    "harmless": 60, "undetected": 6}}}}).encode()

    def falso_urlopen(peticion, timeout=0):
        vistas["metodo"] = peticion.get_method()
        vistas["url"] = peticion.full_url
        vistas["datos"] = peticion.data
        return Respuesta()

    monkeypatch.setattr(virustotal.urllib.request, "urlopen",
                        falso_urlopen)
    res = virustotal.consultar_hash("c" * 64, "clave-del-usuario")
    assert res.estado == "ok"
    assert res.maliciosos == 3 and res.total == 70
    assert vistas["metodo"] == "GET"
    assert vistas["datos"] is None  # sin cuerpo: nada se sube
    assert vistas["url"].endswith("/" + "c" * 64)


def test_ningun_modulo_sube_archivos():
    # Guarda global: ni VirusTotal ni la puntuación contienen vías
    # de subida (multipart, files=, POST con cuerpo de archivo).
    for modulo in ("virustotal", "puntuacion"):
        fuente = open(os.path.join(
            RAIZ, "antivirus_hogar_pc", "core", modulo + ".py"),
            encoding="utf-8").read()
        assert "multipart" not in fuente
        assert "files=" not in fuente
        assert "upload" not in fuente.lower()


def test_ajustes_clave_vt_por_defecto_vacia():
    from antivirus_hogar_pc.ui.services import Ajustes

    assert Ajustes().clave_virustotal == ""


# --- Transversales -----------------------------------------------------------------

def test_version_e_historial_coherentes():
    assert config.VERSION == "1.0.21"
    from antivirus_hogar_pc.core.notas_version import NOTAS_VERSION

    assert NOTAS_VERSION[0]["version"] == config.VERSION


def test_i18n_claves_nuevas_en_ingles():
    from antivirus_hogar_pc.core.i18n import _EN

    for clave in (
            "Protección avanzada", "Análisis a fondo",
            "Memorias USB", "Consulta de dominios e IPs",
            "Defender a fondo: reglas ASR y exclusiones",
            "Drivers vulnerables (BYOVD)", "Posible ransomware",
            "Bloquear el robo de credenciales desde LSASS",
            "Revisar los drivers instalados", "Consultar"):
        assert clave in _EN and _EN[clave].strip(), clave


def test_requirements_traen_yara():
    texto = open(os.path.join(RAIZ, "requirements.txt"),
                 encoding="utf-8").read()
    assert "yara-x" in texto and "yara-python" in texto
