"""v1.0.20 — El diagnóstico también REPARA lo seguro.

Orden del usuario (2026-11-26, «Hazlo»): el botón
«Diagnosticar integridad de la aplicación» de la 1.0.19 debe
además reparar lo seguro, no solo detectar:

- ajustes dañados → valores de fábrica, con copia del dañado;
- bloque del hosts dañado → restaurar la copia que la app
  guarda (sin copia válida: pendiente, no se inventa);
- activos con huella mala → copia íntegra local si existe;
- servicio de OpenVPN parado → arrancar y dejar automático
  SOLO por la vía del servicio (sin elevar, sin UAC);
- restos de descargas viejos/sin identidad → limpiarlos.

Y lo prohibido (conectar VPN, borrar datos del usuario,
Defender/seguridad de Windows, registro) JAMÁS se
auto-repara: sale como «pendiente de tu orden». Cada
reparación se RE-COMPRUEBA: «reparado» solo si pasa después.
"""
import hashlib
import inspect
import json
import os
import shutil
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _leer(ruta_rel: str) -> str:
    with open(os.path.join(RAIZ, ruta_rel), encoding="utf-8") as f:
        return f.read()


def _por_nombre(resultados, nombre):
    for r in resultados:
        if r["nombre"] == nombre:
            return r
    raise AssertionError(f"sin resultado {nombre}: {resultados}")


def _datos_en_tmp(monkeypatch, tmp_path):
    """La carpeta de datos de la app pasa a ser un temporal."""
    carpeta = str(tmp_path / "datos")
    os.makedirs(carpeta, exist_ok=True)
    from antivirus_hogar_pc import config
    monkeypatch.setattr(config, "carpeta_datos", lambda: carpeta)
    return carpeta


# ---------------------------------------------------------------------------
# Ajustes dañados → reparados, con la copia del dañado guardada
# ---------------------------------------------------------------------------

def test_repara_ajustes_danados_y_guarda_copia(monkeypatch, tmp_path):
    from antivirus_hogar_pc.core import diagnostico

    carpeta = _datos_en_tmp(monkeypatch, tmp_path)
    ruta = os.path.join(carpeta, "ajustes.json")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("{esto no es json")
    resultados = diagnostico.diagnosticar_y_reparar()
    r = _por_nombre(resultados, "Ajustes guardados")
    assert r["estado"] == "reparado", r
    # El archivo nuevo se lee y es un objeto…
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    assert isinstance(datos, dict)
    # …y el dañado quedó guardado para el informe.
    copias = [n for n in os.listdir(carpeta)
              if n.startswith("ajustes_danado_")]
    assert len(copias) == 1
    with open(os.path.join(carpeta, copias[0]),
              encoding="utf-8") as f:
        assert f.read() == "{esto no es json"


def test_diagnosticar_a_secas_no_toca_nada(monkeypatch, tmp_path):
    """diagnosticar() sigue siendo puro: detecta, no repara."""
    from antivirus_hogar_pc.core import diagnostico

    carpeta = _datos_en_tmp(monkeypatch, tmp_path)
    ruta = os.path.join(carpeta, "ajustes.json")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("{esto no es json")
    resultados = diagnostico.diagnosticar()
    r = _por_nombre(resultados, "Ajustes guardados")
    assert r["estado"] == "error"
    with open(ruta, encoding="utf-8") as f:
        assert f.read() == "{esto no es json"
    assert not [n for n in os.listdir(carpeta)
                if n.startswith("ajustes_danado_")]


# ---------------------------------------------------------------------------
# Restos de descargas: se limpia lo viejo/ajeno, se respeta lo reanudable
# ---------------------------------------------------------------------------

def test_parciales_limpia_viejos_y_ajenos_respeta_reanudable(
        monkeypatch, tmp_path):
    from antivirus_hogar_pc.core import diagnostico, updater

    carpeta = _datos_en_tmp(monkeypatch, tmp_path)
    act = os.path.join(carpeta, "actualizaciones")
    os.makedirs(act)
    ahora = time.time()

    def _parcial(version, con_identidad=True, edad_dias=0):
        ruta = os.path.join(act, f"actualizacion-{version}.part")
        with open(ruta, "wb") as f:
            f.write(b"parcial")
        if con_identidad:
            updater._guardar_identidad(
                ruta, "https://canal/instalador.exe", "ab" * 32,
                version)
        if edad_dias:
            vieja = ahora - edad_dias * 86400
            os.utime(ruta, (vieja, vieja))
        return ruta

    fresco = _parcial("9.9.9")                      # reanudable: NO se toca
    viejo = _parcial("1.0.0", edad_dias=10)         # viejo: fuera
    ajena = _parcial("0.0.1", con_identidad=False)  # sin identidad: fuera
    huerfana = os.path.join(
        act, "actualizacion-5.5.5.part.identidad.json")
    with open(huerfana, "w", encoding="utf-8") as f:
        f.write("{}")
    instalador = os.path.join(act, "Instalador-X.exe")  # jamás se toca
    with open(instalador, "wb") as f:
        f.write(b"exe")

    problematicos = diagnostico.identificar_parciales_problematicos(
        act, ahora)
    assert viejo in problematicos
    assert ajena in problematicos
    assert huerfana in problematicos
    assert fresco not in problematicos
    assert instalador not in problematicos

    resultados = diagnostico.diagnosticar_y_reparar()
    r = _por_nombre(resultados, "Restos de descargas")
    assert r["estado"] == "reparado", r
    assert not os.path.exists(viejo)
    assert not os.path.exists(ajena)
    assert not os.path.exists(huerfana)
    assert os.path.isfile(fresco)       # el reanudable sigue ahí
    assert os.path.isfile(instalador)   # y el instalador también


# ---------------------------------------------------------------------------
# Activos con huella mala: restauración local o pendiente honesto
# ---------------------------------------------------------------------------

def _activos_sembrados(monkeypatch, tmp_path):
    """Carpeta de activos «instalada» con el icono corrompido
    y el espartano fijo ausente; el animado va por enlace duro
    al real (íntegro). Devuelve (instalada, fuente_pristina)."""
    from antivirus_hogar_pc import config

    reales = os.path.join(RAIZ, "antivirus_hogar_pc", "assets")
    instalada = tmp_path / "activos"
    instalada.mkdir()
    with open(instalada / "icono_app.png", "wb") as f:
        f.write(b"icono corrompido")
    shutil.copyfile(os.path.join(reales, "espartano_animado.webp"),
                    instalada / "espartano_animado.webp")
    fuente = tmp_path / "fuente"
    fuente.mkdir()
    for nombre in ("icono_app.png", "espartano_radar.png"):
        shutil.copyfile(os.path.join(reales, nombre),
                        fuente / nombre)
    monkeypatch.setattr(
        config, "carpeta_activos", lambda: str(instalada))
    return str(instalada), str(fuente)


def test_activos_se_restauran_desde_copia_integra_local(
        monkeypatch, tmp_path):
    from antivirus_hogar_pc.core import diagnostico

    instalada, fuente = _activos_sembrados(monkeypatch, tmp_path)
    monkeypatch.setattr(
        diagnostico, "_carpetas_fuente_activos", lambda: [fuente])
    resultados = diagnostico.diagnosticar_y_reparar()
    r = _por_nombre(resultados, "Archivos de la interfaz")
    assert r["estado"] == "reparado", r
    for nombre in ("icono_app.png", "espartano_radar.png"):
        with open(os.path.join(instalada, nombre), "rb") as f:
            huella = hashlib.sha256(f.read()).hexdigest()
        assert huella == diagnostico.HUELLAS_ACTIVOS[nombre]


def test_activos_sin_copia_local_quedan_pendientes(
        monkeypatch, tmp_path):
    from antivirus_hogar_pc.core import diagnostico

    instalada, _fuente = _activos_sembrados(monkeypatch, tmp_path)
    monkeypatch.setattr(
        diagnostico, "_carpetas_fuente_activos", lambda: [])
    resultados = diagnostico.diagnosticar_y_reparar()
    r = _por_nombre(resultados, "Archivos de la interfaz")
    assert r["estado"] == "pendiente", r
    assert "reinstalar" in r["detalle"]
    # Y el archivo dañado NO se sustituyó por nada inventado.
    with open(os.path.join(instalada, "icono_app.png"),
              "rb") as f:
        assert f.read() == b"icono corrompido"


def test_huellas_de_activos_coinciden_con_el_repo():
    from antivirus_hogar_pc.core import diagnostico

    for nombre, esperada in diagnostico.HUELLAS_ACTIVOS.items():
        ruta = os.path.join(
            RAIZ, "antivirus_hogar_pc", "assets", nombre)
        with open(ruta, "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == esperada


# ---------------------------------------------------------------------------
# Servicio de OpenVPN: arrancar por la vía del servicio, sin elevar
# ---------------------------------------------------------------------------

def _ventana_windows_falsa(monkeypatch):
    import antivirus_hogar_pc.winapi as winapi
    from antivirus_hogar_pc.winapi import disks

    monkeypatch.setattr(winapi, "es_windows", lambda: True)
    monkeypatch.setattr(
        disks, "consultar_eventos_optimizacion",
        lambda *a, **k: [])


def test_servicio_openvpn_se_arranca_y_queda_reparado(
        monkeypatch, tmp_path):
    from antivirus_hogar_pc.core import diagnostico
    from antivirus_hogar_pc.winapi import vpn_win

    _datos_en_tmp(monkeypatch, tmp_path)
    _ventana_windows_falsa(monkeypatch)
    estado = {"activo": False}

    def _arrancar():
        estado["activo"] = True
        return {"ok": True, "detalle": ""}

    monkeypatch.setattr(vpn_win, "openvpn_instalado", lambda: True)
    monkeypatch.setattr(
        vpn_win, "_servicio_interactivo_activo",
        lambda: estado["activo"])
    monkeypatch.setattr(
        vpn_win, "arrancar_servicio_interactivo", _arrancar)
    resultados = diagnostico.diagnosticar_y_reparar()
    r = _por_nombre(resultados, "OpenVPN (VPN)")
    assert r["estado"] == "reparado", r


def test_servicio_openvpn_negado_queda_pendiente(monkeypatch,
                                                 tmp_path):
    from antivirus_hogar_pc.core import diagnostico
    from antivirus_hogar_pc.winapi import vpn_win

    _datos_en_tmp(monkeypatch, tmp_path)
    _ventana_windows_falsa(monkeypatch)
    monkeypatch.setattr(vpn_win, "openvpn_instalado", lambda: True)
    monkeypatch.setattr(
        vpn_win, "_servicio_interactivo_activo", lambda: False)
    monkeypatch.setattr(
        vpn_win, "arrancar_servicio_interactivo",
        lambda: {"ok": False, "detalle": "acceso denegado"})
    resultados = diagnostico.diagnosticar_y_reparar()
    r = _por_nombre(resultados, "OpenVPN (VPN)")
    assert r["estado"] == "pendiente", r
    assert "acceso denegado" in r["detalle"]


def test_arrancar_servicio_sin_elevar_nunca(monkeypatch):
    """La vía es sc.exe desde el propio proceso: ni runas ni
    ShellExecute; si el SCM niega, ok=False con el motivo."""
    from antivirus_hogar_pc.winapi import powershell, vpn_win

    fuente = inspect.getsource(vpn_win.arrancar_servicio_interactivo)
    assert "runas" not in fuente
    assert "ShellExecute" not in fuente
    monkeypatch.setattr(vpn_win, "es_windows", lambda: True)
    estados = iter([
        {"registrado": True, "corriendo": False, "inicio": "manual"},
        {"registrado": True, "corriendo": True, "inicio": "auto"},
    ])
    monkeypatch.setattr(
        vpn_win, "estado_servicio", lambda nombre: next(estados))
    comandos = []

    def _ejecutar(args, timeout=30):
        comandos.append(args)
        return 0, "", ""

    monkeypatch.setattr(powershell, "ejecutar_comando", _ejecutar)
    res = vpn_win.arrancar_servicio_interactivo()
    assert res["ok"] is True
    plano = [" ".join(c) for c in comandos]
    assert any("config" in c and "start=" in c for c in plano)
    assert any(c.startswith("sc start") for c in plano)


# ---------------------------------------------------------------------------
# Hosts dañado: restaurar la copia de la app (o pendiente sin copia)
# ---------------------------------------------------------------------------

_DANADO = ("127.0.0.1 localhost\n"
           "# === Antivirus Hogar INICIO (no editar a mano) ===\n"
           "0.0.0.0 malo.example\n")
_SANO = "127.0.0.1 localhost\n::1 localhost\n"


def _hosts_falso(monkeypatch, tmp_path, con_copia=True):
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.winapi import tuneup_win

    carpeta = _datos_en_tmp(monkeypatch, tmp_path)
    _ventana_windows_falsa(monkeypatch)
    estado = {"texto": _DANADO}
    if con_copia:
        respaldos = config.ruta_respaldos()
        with open(os.path.join(
                respaldos, "hosts_20260101-000000.bak"),
                "w", encoding="utf-8") as f:
            f.write(_SANO)

    def _escribir(nuevo, _carpeta):
        estado["texto"] = nuevo
        return {"ok": True, "via": "directa", "detalle": ""}

    monkeypatch.setattr(tuneup_win, "leer_hosts",
                        lambda: estado["texto"])
    monkeypatch.setattr(
        tuneup_win, "escribir_hosts_robusto", _escribir)
    return estado


def test_hosts_danado_se_restaura_desde_su_copia(monkeypatch,
                                                  tmp_path):
    from antivirus_hogar_pc.core import diagnostico

    estado = _hosts_falso(monkeypatch, tmp_path, con_copia=True)
    resultados = diagnostico.diagnosticar_y_reparar()
    r = _por_nombre(resultados, "Bloqueador de dominios")
    assert r["estado"] == "reparado", r
    assert estado["texto"] == _SANO


def test_hosts_danado_sin_copia_queda_pendiente(monkeypatch,
                                                tmp_path):
    from antivirus_hogar_pc.core import diagnostico

    estado = _hosts_falso(monkeypatch, tmp_path, con_copia=False)
    resultados = diagnostico.diagnosticar_y_reparar()
    r = _por_nombre(resultados, "Bloqueador de dominios")
    assert r["estado"] == "pendiente", r
    assert "copia válida" in r["detalle"]
    assert estado["texto"] == _DANADO  # no se inventó nada


# ---------------------------------------------------------------------------
# Lo prohibido jamás se auto-repara + aislamiento de fallos
# ---------------------------------------------------------------------------

def test_solo_las_cinco_reparaciones_seguras_existen():
    from antivirus_hogar_pc.core import diagnostico

    assert set(diagnostico.REPARACIONES) == {
        diagnostico._chk_ajustes,
        diagnostico._chk_bloqueador,
        diagnostico._chk_activos,
        diagnostico._chk_openvpn,
        diagnostico._chk_parciales_actualizacion,
    }
    fuente = inspect.getsource(diagnostico)
    # Nada de conectar VPN, ni Defender, ni registro de Windows.
    assert "conectar_openvpn" not in fuente
    assert "Set-MpPreference" not in fuente
    assert "winreg" not in fuente


def test_un_fallo_sin_reparacion_queda_pendiente_y_no_se_toca(
        monkeypatch, tmp_path):
    """El radar con huella distinta (fallo SIN reparación
    segura registrada) sale «pendiente» y su archivo no se
    toca: el diseño del radar no se auto-repara jamás."""
    from antivirus_hogar_pc.core import diagnostico

    _datos_en_tmp(monkeypatch, tmp_path)
    ruta = os.path.join(
        RAIZ, "antivirus_hogar_pc", "ui", "fondo_radar.py")
    with open(ruta, "rb") as f:
        antes = hashlib.sha256(f.read()).hexdigest()
    monkeypatch.setattr(diagnostico, "HUELLA_RADAR", "0" * 64)
    resultados = diagnostico.diagnosticar_y_reparar()
    r = _por_nombre(resultados, "Diseño del radar")
    assert r["estado"] == "pendiente", r
    with open(ruta, "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == antes


def test_una_reparacion_que_explota_no_tumba_a_las_demas(
        monkeypatch, tmp_path):
    from antivirus_hogar_pc.core import diagnostico

    carpeta = _datos_en_tmp(monkeypatch, tmp_path)
    with open(os.path.join(carpeta, "ajustes.json"),
              "w", encoding="utf-8") as f:
        f.write("{roto")

    def _explota():
        raise RuntimeError("falla sembrada")

    registro = dict(diagnostico.REPARACIONES)
    registro[diagnostico._chk_ajustes] = _explota
    monkeypatch.setattr(diagnostico, "REPARACIONES", registro)
    resultados = diagnostico.diagnosticar_y_reparar()
    assert len(resultados) == len(diagnostico.COMPROBACIONES)
    r = _por_nombre(resultados, "Ajustes guardados")
    assert r["estado"] == "pendiente", r
    assert "falla sembrada" in r["detalle"]


# ---------------------------------------------------------------------------
# El informe en tres bloques + la página usa el flujo nuevo
# ---------------------------------------------------------------------------

def test_informe_en_tres_bloques():
    from antivirus_hogar_pc.core import diagnostico

    resultados = [
        {"nombre": "A", "estado": "ok", "detalle": "bien"},
        {"nombre": "D", "estado": "aviso", "detalle": "ojo"},
        {"nombre": "B", "estado": "reparado",
         "detalle": "arreglado"},
        {"nombre": "C", "estado": "pendiente",
         "detalle": "espera tu orden"},
    ]
    informe = diagnostico.construir_informe(resultados)
    assert "Correcto:" in informe
    assert "Reparado:" in informe
    assert "Pendiente de tu orden:" in informe
    assert (informe.index("Correcto:")
            < informe.index("Reparado:")
            < informe.index("Pendiente de tu orden:"))
    assert "Resumen:" in informe
    assert "1 reparados" in informe
    assert "1 pendientes de tu orden" in informe


def test_pagina_usa_diagnosticar_y_reparar():
    pagina = _leer("antivirus_hogar_pc/ui/diagnostico_page.py")
    assert "diagnostico.diagnosticar_y_reparar()" in pagina
    assert "Copiar el informe" in pagina
    assert "Exportar el informe" in pagina


# ---------------------------------------------------------------------------
# Versión 1.0.20
# ---------------------------------------------------------------------------

def test_version_1020_en_config_notas_e_instalador():
    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.core.notas_version import NOTAS_VERSION

    assert config.VERSION == "1.0.21"
    assert NOTAS_VERSION[0]["version"] == "1.0.21"
    assert len(NOTAS_VERSION[0]["novedades"]) >= 3
    with open(os.path.join(RAIZ, "packaging", "instalador.iss"),
              encoding="utf-8") as f:
        assert '#define AppVersion "1.0.21"' in f.read()
