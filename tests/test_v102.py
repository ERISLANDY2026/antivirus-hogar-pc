"""Tests de la v1.0.2: porcentajes honestos, impacto de arranque, mapa
de disco, registro de actividad, velocidad y guardas de regresión visual.

Sin Qt y sin Windows, como el resto de la suite: la lógica vive en
core.v102 / core.actividad / core.velocidad, y lo visual se guarda con
comprobaciones sobre el código fuente de la UI (la lección de la v1.0.0:
lo que no se verifica, se rompe en silencio).
"""
import os

from antivirus_hogar_pc.core import v102
from antivirus_hogar_pc.core.actividad import RegistroActividad
from antivirus_hogar_pc.core.velocidad import medir_velocidad

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _leer(ruta_relativa: str) -> str:
    with open(os.path.join(RAIZ, ruta_relativa), encoding="utf-8") as f:
        return f.read()


# --- Porcentajes honestos -----------------------------------------------------

def test_porcentaje_real():
    assert v102.porcentaje(0, 10) == 0
    assert v102.porcentaje(5, 10) == 50
    assert v102.porcentaje(10, 10) == 100
    assert v102.porcentaje(1, 3) == 33


def test_porcentaje_sin_total_no_inventa():
    assert v102.porcentaje(5, 0) is None
    assert v102.porcentaje(5, -1) is None
    assert v102.porcentaje(5, None) is None


def test_porcentaje_acotado():
    assert v102.porcentaje(15, 10) == 100


def test_texto_porcentaje_y_etapa():
    assert v102.texto_porcentaje(12, 32, "archivos") == "38 % · 12 de 32 archivos"
    etapa = v102.texto_etapa(2, 3, "Instalando con Windows Update")
    assert etapa == "Paso 2 de 3 · Instalando con Windows Update"
    assert "%" not in etapa  # las etapas NUNCA llevan un porcentaje inventado


# --- Impacto de arranque --------------------------------------------------------

def test_impacto_arranque():
    assert v102.clasificar_impacto_arranque("Adobe Creative Cloud")[0] == "alto"
    assert v102.clasificar_impacto_arranque("Steam")[0] == "alto"
    assert v102.clasificar_impacto_arranque("Spotify")[0] == "medio"
    nivel, motivo = v102.clasificar_impacto_arranque("Bloc de notas")
    assert nivel == "bajo" and motivo


# --- Mapa de disco ----------------------------------------------------------------

def test_mapa_disco_orden_y_porcentajes():
    mapa = v102.mapa_desde_tamanos({"Descargas": 300, "Documentos": 100})
    assert [m["nombre"] for m in mapa] == ["Descargas", "Documentos"]
    assert mapa[0]["pct"] == 75 and mapa[1]["pct"] == 25


def test_mapa_disco_vacio():
    assert v102.mapa_desde_tamanos({}) == []
    assert v102.mapa_desde_tamanos({"X": 0})[0]["pct"] == 0


# --- Registro de actividad -----------------------------------------------------------

def test_registro_actividad_roundtrip(tmp_path):
    ruta = str(tmp_path / "actividad.jsonl")
    registro = RegistroActividad(ruta)
    registro.registrar("escaneo", "Escaneo: 10 archivos.", cuando=1000.0)
    registro.registrar("limpieza", "Temporales limpiados.", cuando=2000.0)
    entradas = registro.leer()
    assert [e.tipo for e in entradas] == ["limpieza", "escaneo"]  # reciente primero
    assert entradas[0].detalle == "Temporales limpiados."
    texto = registro.exportar_texto()
    assert "Escaneo: 10 archivos." in texto and "Temporales limpiados." in texto


def test_registro_actividad_sin_archivo_y_lineas_corruptas(tmp_path):
    ruta = str(tmp_path / "actividad.jsonl")
    registro = RegistroActividad(ruta)
    assert registro.leer() == []
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("esto no es json\n")
        f.write('{"cuando": 5, "tipo": "app", "detalle": "vale"}\n')
    entradas = registro.leer()
    assert len(entradas) == 1 and entradas[0].detalle == "vale"


# --- Velocidad -------------------------------------------------------------------------

def test_velocidad_con_abridor_falso():
    tiempos = iter([0.0, 0.05, 1.0, 2.0])  # ping 50 ms; bajada 1.0 s

    def abridor(url, timeout):
        return b"x" * 8_000_000 if "bytes=3000000" in url else b""

    resultado = medir_velocidad(abridor=abridor, reloj=lambda: next(tiempos))
    assert resultado["ok"] is True
    assert resultado["ping_ms"] == 50
    assert resultado["bajada_mbps"] == 64.0


def test_velocidad_sin_conexion():
    def abridor_roto(url, timeout):
        raise OSError("sin red")

    resultado = medir_velocidad(abridor=abridor_roto)
    assert resultado["ok"] is False


def test_valorar_velocidad():
    assert "excelente" in v102.valorar_velocidad(150)
    assert "lenta" in v102.valorar_velocidad(2)
    assert v102.calcular_mbps(1_000_000, 1.0) == 8.0
    assert v102.calcular_mbps(10, 0) == 0.0


# --- Guardas de regresión sobre la UI (código fuente) -----------------------------------

def test_tema_con_cromados_y_colores():
    qss = _leer("antivirus_hogar_pc/ui/theme.py")
    assert "qlineargradient" in qss  # cromados/colores, no plano como en v1.0.1


def test_widgets_v102_existen_con_su_api():
    fuente = _leer("antivirus_hogar_pc/ui/widgets_v102.py")
    for nombre in ("class BarraProgreso", "class BotonPulso", "class Medidor",
                   "class TarjetaAnimada", "def fijar(", "def fijar_etapas(",
                   "def fijar_texto(", "def terminar("):
        assert nombre in fuente, nombre


def test_drivers_sin_stretch_que_esconde_la_accion():
    fuente = _leer("antivirus_hogar_pc/modules/system/page.py")
    assert "setStretchLastSection(True)" not in fuente
    assert "BarraProgreso" in fuente
    assert "mapa_disco" in fuente


def test_panel_con_medidores_y_registro():
    fuente = _leer("antivirus_hogar_pc/modules/panel/page.py")
    assert "Medidor" in fuente
    assert "Registro de actividad" in fuente


def test_red_con_velocidad_y_barras():
    fuente = _leer("antivirus_hogar_pc/modules/net/page.py")
    assert "BarraProgreso" in fuente
    assert "Medir velocidad" in fuente
    servicios = _leer("antivirus_hogar_pc/modules/net/servicios_red.py")
    assert "medir_velocidad" in servicios and "estado_vpn" in servicios


def test_escaner_con_barra_de_porcentaje():
    fuente = _leer("antivirus_hogar_pc/modules/security/page.py")
    assert "BarraProgreso" in fuente


def test_servicios_con_registro_de_actividad():
    fuente = _leer("antivirus_hogar_pc/ui/services.py")
    assert "RegistroActividad" in fuente and "registrar_actividad" in fuente
    config = _leer("antivirus_hogar_pc/config.py")
    assert "ruta_actividad" in config
