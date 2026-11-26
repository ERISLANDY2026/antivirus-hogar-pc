"""v1.0.16 — las SIETE mejoras aprobadas en bloque por el usuario:

1. «Puesta a punto» de un clic (orquestación pura): orden,
   progreso global monótono, veredicto único, un fallo no
   detiene, la cancelación deja lo hecho hecho y lo dice.
2. Vigilante de reconexión VPN: reconecta tras una caída
   (mismo servidor, luego failover), NUNCA tras desconexión
   manual, con esperas crecientes y tope de rondas.
3. Tarjeta «Pendientes»: solo datos reales; sin dato, sin fila.
4. Tendencia de salud del disco: historial persistente,
   «bajando» probado, «sin_historial» honesto al principio.
5. Iconos 3D en las páginas: recursos nuevos (llama, carpeta,
   alerta, wifi) como PNG con alfa y mapa coherente por AST.
6. Ahorro por batería: intérprete de GetSystemPowerStatus.
7. Escala de interfaz: factor puro y persistencia de ajustes.
"""
import ast
import os
import struct
import time

import pytest

RAIZ = os.path.join(os.path.dirname(__file__), "..")
DIA = 86400.0


# --- 1. Puesta a punto -----------------------------------------------------------

def _pasos_falsos(fallos=(), cancelar_en=None):
    from antivirus_hogar_pc.core.puesta_a_punto import ETAPAS

    llamadas = []

    def hacer(clave):
        def paso(progreso, cancelado):
            llamadas.append(clave)
            progreso(0.5, f"{clave} a mitad")
            progreso(1.0, f"{clave} hecho")
            if cancelar_en == clave:
                return {"ok": False, "cancelada": True,
                        "resumen": f"{clave}: cancelado a mitad"}
            if clave in fallos:
                return {"ok": False, "resumen": f"{clave}: falló"}
            return {"ok": True, "resumen": f"{clave}: bien"}
        return paso

    return [(c, t, hacer(c)) for c, t in ETAPAS], llamadas


def test_puesta_a_punto_orden_progreso_y_veredicto():
    from antivirus_hogar_pc.core.puesta_a_punto import ejecutar_puesta_a_punto

    pasos, llamadas = _pasos_falsos()
    progresos = []
    res = ejecutar_puesta_a_punto(
        pasos, al_progreso=lambda f, e, t: progresos.append(f))
    assert llamadas == ["escaneo", "limpieza", "optimizar", "drivers"]
    assert progresos == sorted(progresos)  # monótono
    assert progresos[-1] == 1.0
    assert res["cancelada"] is False
    assert "terminada" in res["veredicto"]
    assert all(res["resultados"][c]["ok"] for c, _t, _f in pasos)


def test_puesta_a_punto_un_fallo_no_detiene_y_el_veredicto_lo_dice():
    from antivirus_hogar_pc.core.puesta_a_punto import ejecutar_puesta_a_punto

    pasos, llamadas = _pasos_falsos(fallos=("limpieza",))
    res = ejecutar_puesta_a_punto(pasos)
    assert llamadas == ["escaneo", "limpieza", "optimizar", "drivers"]
    assert res["cancelada"] is False
    assert "CON AVISOS" in res["veredicto"]
    assert "Limpieza segura" in res["veredicto"]


def test_puesta_a_punto_cancelar_entre_etapas_deja_lo_hecho():
    from antivirus_hogar_pc.core.puesta_a_punto import ejecutar_puesta_a_punto

    pasos, llamadas = _pasos_falsos()
    estado = {"n": 0}

    def cancelado():
        estado["n"] += 1
        return estado["n"] > 3  # se cancela tras la 2ª etapa

    res = ejecutar_puesta_a_punto(pasos, cancelado=cancelado)
    assert res["cancelada"] is True
    assert res["resultados"]["escaneo"]["ok"]
    assert res["resultados"]["limpieza"]["ok"]
    assert res["resultados"]["optimizar"].get("omitida")
    assert res["resultados"]["drivers"].get("omitida")
    assert "CANCELADA" in res["veredicto"]
    assert "queda hecho" in res["veredicto"]


def test_puesta_a_punto_cancelar_durante_una_etapa():
    from antivirus_hogar_pc.core.puesta_a_punto import ejecutar_puesta_a_punto

    pasos, _llamadas = _pasos_falsos(cancelar_en="limpieza")
    res = ejecutar_puesta_a_punto(pasos)
    assert res["cancelada"] is True
    assert res["resultados"]["escaneo"]["ok"]
    assert res["resultados"]["optimizar"].get("omitida")
    assert res["resultados"]["drivers"].get("omitida")


def test_puesta_a_punto_registra_cada_etapa():
    from antivirus_hogar_pc.core.puesta_a_punto import ejecutar_puesta_a_punto

    pasos, _llamadas = _pasos_falsos()
    registro = []
    ejecutar_puesta_a_punto(
        pasos, registrar=lambda tipo, det: registro.append((tipo, det)))
    assert len(registro) == 4
    assert all(tipo == "puesta-a-punto" for tipo, _ in registro)


# --- 2. Vigilante VPN --------------------------------------------------------------

class _RelojFalso:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def avanzar(self, s):
        self.t += s


def _vigilante(reconectar, reloj, **kw):
    from antivirus_hogar_pc.modules.net.servicios_red import VigilanteVPN

    estado = {"conectada": True, "objetivo": {
        "hostname": "vpn123", "pais": "Japan", "desde": 500.0}}
    avisos = []
    vig = VigilanteVPN(
        leer_conectada=lambda: estado["conectada"],
        leer_objetivo=lambda: dict(estado["objetivo"]),
        reconectar=reconectar,
        avisar=lambda ev, ob: avisos.append(ev),
        reloj=reloj, **kw)
    return vig, estado, avisos


def test_vigilante_sin_verla_arriba_no_reconecta():
    reloj = _RelojFalso()
    intentos = []
    vig, estado, _a = _vigilante(
        lambda ob, r: intentos.append(r) or True, reloj)
    estado["conectada"] = False  # nunca se vio establecida
    assert vig.ciclo() == "esperando"
    assert intentos == []


def test_vigilante_reconecta_al_mismo_servidor_tras_una_caida():
    reloj = _RelojFalso()
    intentos = []

    def reconectar(ob, ronda):
        intentos.append(ronda)
        return True

    vig, estado, avisos = _vigilante(reconectar, reloj)
    assert vig.ciclo() == "conectado"
    estado["conectada"] = False
    assert vig.ciclo() == "reconectado"
    assert intentos == [0]  # ronda 0: el MISMO servidor
    assert avisos == ["caida", "reconectada"]


def test_vigilante_failover_en_la_siguiente_ronda_y_tope():
    reloj = _RelojFalso()
    intentos = []
    vig, estado, avisos = _vigilante(
        lambda ob, r: intentos.append(r) or False, reloj,
        max_rondas=3, esperas=(10.0, 20.0, 30.0))
    assert vig.ciclo() == "conectado"
    estado["conectada"] = False
    assert vig.ciclo() == "reintento_fallido"     # ronda 0
    assert vig.ciclo() == "esperando_reintento"   # espera creciente
    reloj.avanzar(11)
    assert vig.ciclo() == "reintento_fallido"     # ronda 1 (failover)
    reloj.avanzar(21)
    assert vig.ciclo() == "reintento_fallido"     # ronda 2
    reloj.avanzar(31)
    assert vig.ciclo() == "agotado"               # tope: sin bucle
    assert vig.ciclo() == "agotado"
    assert intentos == [0, 1, 2]
    assert avisos == ["caida", "agotado"]         # agotado se avisa una vez


def test_vigilante_desconexion_manual_no_reconecta_jamas():
    reloj = _RelojFalso()
    intentos = []
    vig, estado, _a = _vigilante(
        lambda ob, r: intentos.append(r) or True, reloj)
    assert vig.ciclo() == "conectado"
    vig.marcar_desconexion_manual()
    estado["conectada"] = False
    assert vig.ciclo() == "manual"
    reloj.avanzar(10000)
    assert vig.ciclo() == "manual"
    assert intentos == []
    # Una conexión NUEVA (otra hora de inicio) levanta la marca:
    estado["objetivo"] = {"hostname": "vpn999", "pais": "Spain",
                          "desde": 900.0}
    estado["conectada"] = True
    assert vig.ciclo() == "conectado"
    estado["conectada"] = False
    assert vig.ciclo() == "reconectado"
    assert intentos == [0]


def test_vigilante_desactivado_no_actua():
    reloj = _RelojFalso()
    intentos = []
    vig, estado, _a = _vigilante(
        lambda ob, r: intentos.append(r) or True, reloj)
    assert vig.ciclo() == "conectado"
    estado["conectada"] = False
    assert vig.ciclo(activado=False) == "desactivado"
    assert intentos == []


def test_desconectar_vpn_marca_la_desconexion_manual():
    from antivirus_hogar_pc.modules.net import servicios_red

    class FalsoVigilante:
        def __init__(self):
            self.marcado = False

        def marcar_desconexion_manual(self):
            self.marcado = True

    falso = FalsoVigilante()
    anterior = servicios_red._VIGILANTE
    servicios_red._VIGILANTE = falso
    try:
        servicios_red.desconectar_vpn()
    finally:
        servicios_red._VIGILANTE = anterior
    assert falso.marcado


# --- 3. Pendientes -------------------------------------------------------------------

def test_pendientes_solo_datos_reales():
    from antivirus_hogar_pc.core.pendientes import calcular_pendientes

    ahora = 1_700_000_000.0
    # Sin ningún dato: solo el escaneo (su ausencia SÍ es un dato).
    lista = calcular_pendientes(ahora=ahora)
    assert [p.clave for p in lista] == ["escaneo_nunca"]
    # Escaneo reciente y nada más: todo al día.
    lista = calcular_pendientes(ahora=ahora, ultimo_escaneo=ahora - DIA)
    assert lista == []
    # Escaneo viejo.
    lista = calcular_pendientes(ahora=ahora,
                                ultimo_escaneo=ahora - 9 * DIA)
    assert [p.clave for p in lista] == ["escaneo_viejo"]
    assert lista[0].dias == 9 and lista[0].destino == "escaner"


def test_pendientes_cada_regla():
    from antivirus_hogar_pc.core.pendientes import calcular_pendientes

    ahora = 1_700_000_000.0
    base = dict(ahora=ahora, ultimo_escaneo=ahora)
    lista = calcular_pendientes(
        revision_drivers={"desactualizados": 3, "total": 20,
                          "confirmado": True}, **base)
    assert [p.clave for p in lista] == ["drivers"]
    assert lista[0].cantidad == 3 and lista[0].destino == "drivers"
    # Revisión NO confirmada (falló Windows Update): no es dato.
    lista = calcular_pendientes(
        revision_drivers={"desactualizados": 3, "total": 20,
                          "confirmado": False}, **base)
    assert lista == []
    # Optimización vieja / sin dato.
    lista = calcular_pendientes(
        ultima_optimizacion={"cuando": ahora - 40 * DIA, "ok": True},
        **base)
    assert [p.clave for p in lista] == ["optimizar"]
    lista = calcular_pendientes(ultima_optimizacion=None, **base)
    assert lista == []
    # Windows y VPN.
    lista = calcular_pendientes(actualizaciones_windows=2, **base)
    assert [p.clave for p in lista] == ["windows"]
    lista = calcular_pendientes(
        vpn={"total": 100, "verificados": 30}, **base)
    assert [p.clave for p in lista] == ["vpn_sin_verificar"]
    assert lista[0].cantidad == 70
    lista = calcular_pendientes(
        vpn={"total": 100, "verificados": 100}, **base)
    assert lista == []
    # El disco bajando va primero y como aviso.
    lista = calcular_pendientes(
        tendencia_disco={"bajando": True, "dias": 30},
        actualizaciones_windows=1, **base)
    assert lista[0].clave == "disco_bajando" and lista[0].aviso


# --- 4. Historial y tendencia de discos ------------------------------------------------

def _lectura(desgaste=None, salud="Healthy", sano=True, sin_datos=False,
             nombre="TIMETEC 512GB"):
    return {"nombre": nombre, "desgaste_pct": desgaste, "salud": salud,
            "sano": sano, "sin_datos": sin_datos}


def test_historial_sin_datos_no_guarda_y_sin_historial_es_honesto(tmp_path):
    from antivirus_hogar_pc.core import historial_discos as hd

    ruta = str(tmp_path / "historial.json")
    ahora = 1_700_000_000.0
    hist = hd.registrar_lecturas([_lectura(sin_datos=True)], ruta, ahora)
    assert hist == {}  # sin datos: no se guarda nada
    t = hd.tendencia_principal([_lectura(desgaste=5)], hist, ahora)
    assert t["estado"] == "sin_historial" and t["bajando"] is False


def test_historial_tendencia_bajando_y_estable(tmp_path):
    from antivirus_hogar_pc.core import historial_discos as hd

    ruta = str(tmp_path / "historial.json")
    ahora = 1_700_000_000.0
    # Hace 35 días: desgaste 2 (nivel 98). Hoy: desgaste 15 (nivel 85).
    hd.registrar_lecturas([_lectura(desgaste=2)], ruta, ahora - 35 * DIA)
    hist = hd.registrar_lecturas([_lectura(desgaste=15)], ruta, ahora)
    t = hd.tendencia_principal([_lectura(desgaste=15)], hist, ahora)
    assert t["estado"] == "bajando" and t["bajando"] is True
    assert t["delta"] == -13.0 and t["dias"] == 35
    # Estable: mismo nivel que la referencia.
    t2 = hd.tendencia_principal([_lectura(desgaste=2)],
                                {"TIMETEC 512GB": [
                                    {"cuando": ahora - 35 * DIA,
                                     "nivel": 98.0}]}, ahora)
    assert t2["estado"] == "estable" and t2["bajando"] is False


def test_historial_espaciado_y_cambio_de_nivel(tmp_path):
    from antivirus_hogar_pc.core import historial_discos as hd

    ruta = str(tmp_path / "historial.json")
    ahora = 1_700_000_000.0
    hd.registrar_lecturas([_lectura(desgaste=5)], ruta, ahora)
    # Una hora después, mismo nivel: no se duplica.
    hist = hd.registrar_lecturas([_lectura(desgaste=5)], ruta, ahora + 3600)
    assert len(hist["TIMETEC 512GB"]) == 1
    # Una hora después, nivel distinto: sí se anota.
    hist = hd.registrar_lecturas([_lectura(desgaste=9)], ruta, ahora + 3600)
    assert len(hist["TIMETEC 512GB"]) == 2


def test_nivel_salud_desde_estado_sin_desgaste():
    from antivirus_hogar_pc.core.historial_discos import nivel_salud

    assert nivel_salud(_lectura(salud="Healthy")) == 100.0
    assert nivel_salud(_lectura(salud="Warning", sano=False)) == 55.0
    assert nivel_salud(_lectura(salud="Unhealthy", sano=False)) == 10.0
    assert nivel_salud(_lectura(salud="", sano=None)) is None


# --- Estado de mantenimiento (soporte de los frentes 3 y 4) ------------------------------

def test_estado_mantenimiento_ida_y_vuelta(tmp_path):
    from antivirus_hogar_pc.core import estado_mantenimiento as em

    ruta_d = str(tmp_path / "drivers.json")
    ruta_o = str(tmp_path / "opt.json")
    assert em.leer_revision_drivers(ruta_d) is None
    em.guardar_revision_drivers(2, 18, confirmado=True, ruta=ruta_d,
                                ahora=123.0)
    datos = em.leer_revision_drivers(ruta_d)
    assert datos["desactualizados"] == 2 and datos["cuando"] == 123.0
    em.guardar_optimizacion("C", True, ruta=ruta_o, ahora=456.0)
    datos = em.leer_ultima_optimizacion(ruta_o)
    assert datos["letra"] == "C" and datos["ok"] is True


# --- 6. Batería ---------------------------------------------------------------------------

def test_interpretar_estado_energia():
    from antivirus_hogar_pc.winapi.system_info import (
        interpretar_estado_energia)

    assert interpretar_estado_energia(1, 1, 80) == {
        "con_cargador": True, "bateria_pct": 80, "sin_bateria": False}
    assert interpretar_estado_energia(0, 1, 55)["con_cargador"] is False
    assert interpretar_estado_energia(255, 255, 255) == {
        "con_cargador": None, "bateria_pct": None, "sin_bateria": False}
    sobremesa = interpretar_estado_energia(1, 128, 255)
    assert sobremesa["sin_bateria"] is True
    assert sobremesa["bateria_pct"] is None


# --- 7. Escala y ajustes nuevos --------------------------------------------------------------

def test_factor_de_escala():
    from antivirus_hogar_pc.ui.escala import factor_de
    from antivirus_hogar_pc.ui.services import Ajustes

    a = Ajustes()
    assert a.vpn_reconectar_auto is True       # frente 2: por defecto sí
    assert a.escala_interfaz == "normal"       # frente 7
    assert factor_de(a) == 1.0
    a.escala_interfaz = "grande"
    assert factor_de(a) == 1.22
    a.escala_interfaz = "normal"
    a.letra_grande = True
    assert factor_de(a) == 1.125               # el de siempre sigue valiendo
    a.escala_interfaz = "grande"
    assert factor_de(a) == 1.22                # el mayor, nunca la suma


def test_ajustes_nuevos_persisten(tmp_path):
    from antivirus_hogar_pc.ui.services import Ajustes

    a = Ajustes(_ruta=str(tmp_path / "ajustes.json"))
    a.vpn_reconectar_auto = False
    a.escala_interfaz = "grande"
    a.guardar()
    import json as _json

    datos = _json.loads((tmp_path / "ajustes.json").read_text("utf-8"))
    assert datos["vpn_reconectar_auto"] is False
    assert datos["escala_interfaz"] == "grande"


# --- 5. Iconos 3D en las páginas -------------------------------------------------------------

def test_iconos_pagina_recursos_y_mapa():
    """Los 4 iconos generados para las páginas existen como PNG
    192×192 con alfa, y el mapa de iconos_pagina (leído por AST,
    sin importar Qt) es coherente con los recursos en disco."""
    carpeta = os.path.join(RAIZ, "antivirus_hogar_pc", "assets",
                           "iconos3d")
    for nombre in ("llama", "carpeta", "alerta", "wifi"):
        datos = open(os.path.join(
            carpeta, "paginas", f"{nombre}.png"), "rb").read()
        assert datos[:8] == b"\x89PNG\r\n\x1a\n", nombre
        ancho, alto = struct.unpack(">II", datos[16:24])
        assert (ancho, alto) == (192, 192), nombre
        assert datos[25] == 6, nombre  # color type 6 = RGBA (con alfa)

    ruta_py = os.path.join(RAIZ, "antivirus_hogar_pc", "ui",
                           "iconos_pagina.py")
    arbol = ast.parse(open(ruta_py, encoding="utf-8").read())
    mapa = propios = None
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "MAPA_RECURSOS_NAV"
                for t in nodo.targets):
            mapa = {c.value for c in nodo.value.values}
        if isinstance(nodo, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "PROPIOS_PAGINA"
                for t in nodo.targets):
            propios = {c.value for c in nodo.value.elts}
    en_disco = {os.path.splitext(f)[0]
                for f in os.listdir(carpeta) if f.endswith(".png")}
    assert mapa and mapa <= en_disco          # todo lo mapeado existe
    assert propios == {"llama", "carpeta", "alerta", "wifi"}


# --- Qt (solo CI): puertas de animación, escala y filas 3D -----------------------------------

@pytest.fixture()
def app_qt():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        # Sandbox sin las librerías de sistema de Qt (libEGL):
        # estos tests corren en la CI de Windows, como los demás
        # tests Qt de la suite.
        pytest.skip("QtWidgets no importable en este entorno")

    app = QApplication.instance() or QApplication([])
    yield app


def test_ahorro_bateria_pausa_y_reanuda_sin_tocar_el_interruptor(app_qt):
    from antivirus_hogar_pc.ui import animacion

    animacion.fijar_animaciones_activas(True)
    animacion.fijar_ahorro_bateria(False)
    assert animacion.animaciones_activas() is True
    animacion.fijar_ahorro_bateria(True)
    assert animacion.ahorro_bateria_activo() is True
    assert animacion.animaciones_activas() is False  # pausa por batería
    animacion.fijar_ahorro_bateria(False)
    assert animacion.animaciones_activas() is True   # vuelven al enchufar
    # El interruptor manual MANDA: apagado, la batería no enciende nada.
    animacion.fijar_animaciones_activas(False)
    animacion.fijar_ahorro_bateria(True)
    animacion.fijar_ahorro_bateria(False)
    assert animacion.animaciones_activas() is False
    animacion.fijar_animaciones_activas(True)  # dejar la puerta como estaba


def test_ventana_con_escala_grande_cabe_en_la_pantalla_de_la_toughbook(
        app_qt, tmp_path):
    from antivirus_hogar_pc.ui.main_window import ANCHO_BARRA, VentanaPrincipal
    from antivirus_hogar_pc.ui.services import ServiciosApp

    servicios = ServiciosApp()
    servicios.ajustes._ruta = str(tmp_path / "ajustes.json")
    servicios.ajustes.escala_interfaz = "grande"
    ventana = VentanaPrincipal(servicios)
    try:
        barra_ancho = ventana.centralWidget().layout().itemAt(0) \
            .widget().width()
        assert barra_ancho == int(ANCHO_BARRA * 1.22)
        ventana.resize(1366, 768)
        assert ventana.width() <= 1366 and ventana.height() <= 768
    finally:
        ventana.deleteLater()


def test_fila_estado_usa_el_recurso_3d_y_respaldo_svg(app_qt):
    from PySide6.QtWidgets import QWidget

    from antivirus_hogar_pc.ui.iconos_pagina import IconoEstado3D
    from antivirus_hogar_pc.ui.icons import IconoAnimado
    from antivirus_hogar_pc.ui.paginas_base import fila_estado

    fila = fila_estado("escudo", "pulso", "Defender", "Activo.")
    tipos = [type(w) for w in fila.findChildren(QWidget)]
    assert IconoEstado3D in tipos
    fila2 = fila_estado("boton", "estatico", "Otro", "Sin recurso 3D.")
    tipos2 = [type(w) for w in fila2.findChildren(QWidget)]
    assert IconoAnimado in tipos2 and IconoEstado3D not in tipos2


def test_panel_trae_pendientes_y_puesta_a_punto(app_qt, tmp_path):
    from PySide6.QtWidgets import QProgressBar

    from antivirus_hogar_pc.modules.panel.page import crear_pagina
    from antivirus_hogar_pc.contracts import ContextoModulo
    from antivirus_hogar_pc.ui.services import ServiciosApp

    servicios = ServiciosApp()
    servicios.ajustes._ruta = str(tmp_path / "ajustes.json")
    ctx = ContextoModulo(servicios=servicios, al_navegar=lambda _id: None)
    pagina = crear_pagina(ctx)
    try:
        assert pagina.findChildren(QProgressBar)  # la barra de la rutina
        hilo = getattr(pagina, "_hilo_informe", None)
        if hilo is not None:
            hilo.wait(10000)  # no dejar el QThread corriendo al salir
    finally:
        pagina.deleteLater()
