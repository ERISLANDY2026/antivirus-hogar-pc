"""v1.0.6 — Bloqueador hosts a prueba de fallos.

Incidente real (2026-11-24, Toughbook del usuario): con el bloqueo
activo la PC quedó «conectado, sin internet» y «Quitar bloqueo»
falló porque el Copy-Item elevado no pudo acceder al hosts («being
used by another process»); la limpieza solo se logró desde el
entorno de recuperación de Windows. La corrección:

1. Escritura/restauración robustas: reintentos ante archivo ocupado
   y, si persiste, reemplazo programado para el reinicio (MoveFileEx)
   con aviso claro en español; el error crudo nunca llega a pantalla.
2. Al activar: vaciado de caché DNS (en el script elevado) y
   autocomprobación de resolución; si falla, reversión automática al
   respaldo previo.
3. Autorreparación al abrir la app ante bloque dañado o restauración
   pendiente.
"""
import json
import os

from antivirus_hogar_pc.core import hosts_blocker as hb
from antivirus_hogar_pc.core import seguridad
from antivirus_hogar_pc.core.textos_error import mensaje_para_usuario

HOSTS_BASE = "127.0.0.1 localhost\n::1 localhost\n192.168.1.10 impresora\n"
ERROR_CRUDO = (
    "Copy-Item : The process cannot access the file "
    "'C:\\Windows\\System32\\drivers\\etc\\hosts' because it is being "
    "used by another process."
)


# === 1. Análisis de bloque dañado y retirada robusta ==========================

def test_analizar_bloque_sano_y_ausente():
    sano = hb.aplicar_bloque(HOSTS_BASE, ["malo.example"])
    assert hb.analizar_bloque(sano) == {
        "presente": True, "danado": False, "motivo": ""}
    assert hb.analizar_bloque(HOSTS_BASE) == {
        "presente": False, "danado": False, "motivo": ""}


def test_analizar_bloque_truncado_sin_fin():
    truncado = HOSTS_BASE + hb.MARCADOR_INICIO + "\n0.0.0.0 malo.example\n"
    analisis = hb.analizar_bloque(truncado)
    assert analisis["presente"] is True and analisis["danado"] is True


def test_analizar_bloque_fin_huerfano_y_duplicado():
    huerfano = HOSTS_BASE + "0.0.0.0 malo.example\n" + hb.MARCADOR_FIN + "\n"
    assert hb.analizar_bloque(huerfano)["danado"] is True
    doble = hb.aplicar_bloque(HOSTS_BASE, ["a.example"]) + \
        hb.generar_bloque(["b.example"])
    assert hb.analizar_bloque(doble)["danado"] is True


def test_quitar_robusto_truncado_restaura_el_resto():
    truncado = HOSTS_BASE + hb.MARCADOR_INICIO + "\n0.0.0.0 malo.example\n"
    assert hb.quitar_bloque_robusto(truncado) == HOSTS_BASE


def test_quitar_robusto_fin_huerfano_se_lleva_sus_entradas():
    huerfano = HOSTS_BASE + "0.0.0.0 malo.example\n" + hb.MARCADOR_FIN + "\n"
    assert hb.quitar_bloque_robusto(huerfano) == HOSTS_BASE


def test_quitar_robusto_duplicado_e_invertido():
    doble = hb.aplicar_bloque(HOSTS_BASE, ["a.example"]) + \
        hb.generar_bloque(["b.example"])
    assert hb.quitar_bloque_robusto(doble) == HOSTS_BASE
    invertido = (HOSTS_BASE + hb.MARCADOR_FIN + "\n" + hb.MARCADOR_INICIO
                 + "\n0.0.0.0 malo.example\n")
    limpio = hb.quitar_bloque_robusto(invertido)
    assert hb.MARCADOR_INICIO not in limpio and hb.MARCADOR_FIN not in limpio
    assert "malo.example" not in limpio
    assert "impresora" in limpio


def test_quitar_robusto_sano_equivale_al_clasico():
    con_bloque = hb.aplicar_bloque(HOSTS_BASE, ["a.example", "b.example"])
    assert hb.quitar_bloque_robusto(con_bloque) == hb.quitar_bloque(con_bloque)
    assert hb.quitar_bloque_robusto(HOSTS_BASE) == HOSTS_BASE


# === 2. Script elevado robusto y su corredor =================================

def test_script_robusto_reintenta_y_programa_al_reinicio():
    from antivirus_hogar_pc.winapi import tuneup_win

    script = tuneup_win.script_escribir_hosts(
        r"C:\datos\hosts_nuevo.txt", r"C:\datos\hosts_pendiente.txt",
        r"C:\datos\hosts_resultado.txt")
    assert "Start-Sleep" in script            # espera entre reintentos
    assert "for" in script                    # bucle de reintentos
    assert "MoveFileEx" in script             # vía programada al reinicio
    assert "DIRECTA" in script and "PROGRAMADA" in script
    assert "flushdns" in script               # caché DNS vaciada al copiar
    assert str(tuneup_win.INTENTOS_ESCRITURA_HOSTS) in script


def _corredor_con_desenlace(monkeypatch, tmp_path, desenlace, lanzado=True):
    from antivirus_hogar_pc.winapi import tuneup_win

    hosts_real = tmp_path / "hosts"
    hosts_real.write_text(HOSTS_BASE, encoding="utf-8")
    monkeypatch.setattr(tuneup_win, "RUTA_HOSTS", str(hosts_real))
    carpeta = tmp_path / "respaldos"
    carpeta.mkdir()

    def falso_elevado(script, timeout=180):
        if desenlace is not None:
            (carpeta / "hosts_resultado.txt").write_text(
                desenlace, encoding="utf-8")
        return lanzado

    monkeypatch.setattr(tuneup_win, "ejecutar_elevado", falso_elevado)
    return tuneup_win.escribir_hosts_robusto("nuevo texto\n", str(carpeta))


def test_escribir_robusto_via_directa(monkeypatch, tmp_path):
    res = _corredor_con_desenlace(monkeypatch, tmp_path, "DIRECTA")
    assert res["ok"] is True and res["via"] == "directa"


def test_escribir_robusto_archivo_ocupado_via_programada(monkeypatch, tmp_path):
    # El archivo «ocupado» se simula con el desenlace que deja el
    # script cuando los reintentos se agotan y MoveFileEx programa.
    res = _corredor_con_desenlace(monkeypatch, tmp_path, "PROGRAMADA")
    assert res["ok"] is True and res["via"] == "programada"


def test_escribir_robusto_sin_resultado_es_fallo(monkeypatch, tmp_path):
    res = _corredor_con_desenlace(monkeypatch, tmp_path, None, lanzado=False)
    assert res["ok"] is False and res["via"] == ""


# === 3. Servicio de seguridad con el winapi simulado ==========================

class _HostsFalso:
    """Sustituto de tuneup_win: guarda el «hosts» en memoria, aplica
    las escrituras y deja respaldo previo como el corredor real."""

    def __init__(self, texto, respaldos):
        self.texto = texto
        self.respaldos = respaldos
        self.escritos = []
        self.resultado = {"ok": True, "via": "directa", "detalle": ""}
        self.excepcion = None
        self._n_respaldo = 0

    def leer(self):
        return self.texto

    def escribir(self, nuevo_texto, _carpeta):
        if self.excepcion is not None:
            raise self.excepcion
        self._n_respaldo += 1
        ruta = os.path.join(
            self.respaldos, f"hosts_20261124-1200{self._n_respaldo:02d}.bak")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(self.texto)
        self.escritos.append(nuevo_texto)
        self.texto = nuevo_texto
        return dict(self.resultado)


def _entorno(monkeypatch, tmp_path, texto_inicial=HOSTS_BASE):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from antivirus_hogar_pc import config

    respaldos = config.ruta_respaldos()
    falso = _HostsFalso(texto_inicial, respaldos)
    monkeypatch.setattr(seguridad, "es_windows", lambda: True)
    monkeypatch.setattr(seguridad.tuneup_win, "leer_hosts", falso.leer)
    monkeypatch.setattr(
        seguridad.tuneup_win, "escribir_hosts_robusto", falso.escribir)
    dominios = tmp_path / "dominios.txt"
    dominios.write_text("malo.example\nphishing.example\n", encoding="utf-8")
    monkeypatch.setattr(
        seguridad, "rutas_base_dominios", lambda base: [str(dominios)])
    return falso


def _estado_local():
    with open(seguridad._ruta_estado_local(), "r", encoding="utf-8") as f:
        return json.load(f)


def test_activar_ok_si_la_resolucion_sigue_viva(monkeypatch, tmp_path):
    falso = _entorno(monkeypatch, tmp_path)
    res = seguridad.activar_hosts("semilla", _resolver=lambda d: True)
    assert res.ok is True
    assert hb.bloque_activo(falso.texto)
    assert hb.contar_bloqueados(falso.texto) == 2
    assert "Bloqueo activado" in res.mensaje


def test_activar_con_resolucion_fallida_revierte_al_respaldo(
        monkeypatch, tmp_path):
    falso = _entorno(monkeypatch, tmp_path)
    res = seguridad.activar_hosts("semilla", _resolver=lambda d: False)
    assert res.ok is False
    # Reversión automática: el hosts final es el de antes, sin bloque.
    assert falso.texto == HOSTS_BASE
    assert hb.bloque_activo(falso.texto) is False
    assert "se restauró" in res.mensaje
    assert "being used by another process" not in res.mensaje


def test_quitar_con_archivo_ocupado_queda_programado(monkeypatch, tmp_path):
    con_bloque = hb.aplicar_bloque(HOSTS_BASE, ["malo.example"])
    falso = _entorno(monkeypatch, tmp_path, con_bloque)
    falso.resultado = {"ok": True, "via": "programada",
                       "detalle": "hosts en uso"}
    res = seguridad.quitar_hosts()
    assert res.ok is True
    assert "al reiniciar" in res.mensaje
    assert "Copy-Item" not in res.mensaje
    assert _estado_local().get("pendiente") == "quitar"


def test_error_crudo_de_copy_item_nunca_llega_a_pantalla(
        monkeypatch, tmp_path):
    con_bloque = hb.aplicar_bloque(HOSTS_BASE, ["malo.example"])
    falso = _entorno(monkeypatch, tmp_path, con_bloque)
    falso.excepcion = RuntimeError(ERROR_CRUDO)
    res = seguridad.quitar_hosts()
    assert res.ok is False
    assert "Copy-Item" not in res.mensaje
    assert "being used by another process" not in res.mensaje
    assert "en uso por otro programa" in res.mensaje
    assert "Copy-Item" in (res.detalle_tecnico or "")


def test_texto_error_hosts_en_uso_es_breve():
    mensaje = mensaje_para_usuario(RuntimeError(ERROR_CRUDO))
    assert "en uso por otro programa" in mensaje
    assert "The process cannot access" not in mensaje


# === 4. Autorreparación al inicio =============================================

def test_autorreparar_bloque_danado_lo_deja_limpio(monkeypatch, tmp_path):
    danado = HOSTS_BASE + hb.MARCADOR_INICIO + "\n0.0.0.0 malo.example\n"
    falso = _entorno(monkeypatch, tmp_path, danado)
    registros = []
    resumen = seguridad.autorreparar_al_inicio(
        lambda tipo, detalle: registros.append((tipo, detalle)))
    assert resumen != ""
    assert falso.texto == HOSTS_BASE
    assert registros and registros[0][0] == "sistema"
    assert "dañado" in registros[0][1]


def test_autorreparar_pendiente_quitar_ya_aplicado(monkeypatch, tmp_path):
    falso = _entorno(monkeypatch, tmp_path)
    seguridad._actualizar_estado_local(pendiente="quitar")
    registros = []
    resumen = seguridad.autorreparar_al_inicio(
        lambda tipo, detalle: registros.append((tipo, detalle)))
    assert resumen != ""
    assert falso.escritos == []  # ya estaba limpio: no se escribe nada
    assert _estado_local().get("pendiente") == ""


def test_autorreparar_pendiente_quitar_sigue_presente(monkeypatch, tmp_path):
    con_bloque = hb.aplicar_bloque(HOSTS_BASE, ["malo.example"])
    falso = _entorno(monkeypatch, tmp_path, con_bloque)
    seguridad._actualizar_estado_local(pendiente="quitar")
    resumen = seguridad.autorreparar_al_inicio(lambda tipo, detalle: None)
    assert resumen != ""
    assert falso.texto == HOSTS_BASE


def test_autorreparar_sin_nada_que_reparar_no_toca(monkeypatch, tmp_path):
    falso = _entorno(monkeypatch, tmp_path)
    resumen = seguridad.autorreparar_al_inicio(lambda tipo, detalle: None)
    assert resumen == ""
    assert falso.escritos == []


# === 5. Notas de la versión ====================================================

def test_notas_y_version_106():
    # v1.0.7: la entrada 1.0.6 queda como HISTORIAL (la versión
    # vigente la fija el test de la entrega en curso).
    from antivirus_hogar_pc.core import notas_version

    notas = notas_version.notas_de("1.0.6")
    assert notas is not None and len(notas["novedades"]) >= 3
