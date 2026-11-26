"""Autodiagnóstico de integridad de la aplicación (v1.0.19, nota 7;
auto-reparación segura en la v1.0.20).

Pedido del usuario: un botón «Diagnosticar integridad de la
aplicación» que corra un autodiagnóstico de TODAS las funciones
buscando fallas y códigos erróneos, con un informe en pantalla
que se pueda copiar y exportar. En la v1.0.20 el usuario pidió
el paso siguiente («Hazlo»): el diagnóstico además REPARA lo
seguro, no solo detecta.

Este módulo es el motor, sin Qt: una lista de comprobaciones
independientes — cada una devuelve {nombre, estado, detalle}
con estado «ok» | «aviso» | «error» — y el constructor del
informe en texto. `diagnosticar()` es puro: no escribe ni
repara nada. `diagnosticar_y_reparar()` corre las mismas
comprobaciones y, tras cada fallo con reparación segura
registrada, la aplica y VUELVE A COMPROBAR: el resultado solo
se dice «reparado» si la comprobación pasa después.

Las reparaciones seguras son SOLO estas cinco (REPARACIONES):
ajustes dañados → valores de fábrica guardando copia del
archivo dañado; bloque del hosts dañado → restaurar la copia
que la propia app guarda; activos visuales dañados → copia
íntegra local si existe; servicio de OpenVPN parado →
arrancarlo y dejarlo automático POR LA VÍA DEL SERVICIO (sin
elevar jamás por cuenta propia); restos de descargas de
actualización viejos o sin identidad → quitarlos. Todo lo
demás —conectar una VPN, borrar datos del usuario, tocar la
seguridad de Windows/Defender o el registro— NUNCA se
auto-repara: sale como «pendiente de tu orden» con su motivo.

Una comprobación o una reparación que explota se convierte
en error/pendiente con su excepción: el diagnóstico nunca se
cae por la falla que vino a buscar.
"""
import hashlib
import json
import os
import shutil
import sys
import time

from .. import config
from .i18n import t

# Huella del radar INTOCABLE (la misma que vigila la suite
# desde la v1.0.6): si el archivo difiere, algo lo tocó.
HUELLA_RADAR = (
    "ec21a7b8044b90f6cdb4915aa8ec2affa98d7f74059bb4e742dbfe1109629bea")


def _ok(nombre: str, detalle: str) -> dict:
    return {"nombre": nombre, "estado": "ok", "detalle": detalle}


def _aviso(nombre: str, detalle: str) -> dict:
    return {"nombre": nombre, "estado": "aviso", "detalle": detalle}


def _error(nombre: str, detalle: str) -> dict:
    return {"nombre": nombre, "estado": "error", "detalle": detalle}


def _raiz_app() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _chk_version() -> dict:
    version = getattr(config, "VERSION", "")
    if version:
        return _ok(t("Versión de la aplicación"),
                   t("La aplicación informa la versión {v}.",
                     v=version))
    return _error(t("Versión de la aplicación"),
                  t("La aplicación no informa su versión."))


def _chk_modulos() -> dict:
    from ..modules import descubrir_modulos, errores_descubrimiento
    registros = descubrir_modulos()
    errores = errores_descubrimiento()
    if errores:
        return _error(
            t("Módulos de la aplicación"),
            t("{n} módulos cargados, pero hay fallos: {e}",
              n=len(registros), e="; ".join(errores[:3])))
    if not registros:
        return _error(t("Módulos de la aplicación"),
                      t("No cargó ningún módulo."))
    return _ok(t("Módulos de la aplicación"),
               t("{n} módulos cargados sin errores.",
                 n=len(registros)))


def _chk_carpeta_datos() -> dict:
    carpeta = config.carpeta_datos()
    sonda = os.path.join(carpeta, ".sonda_diagnostico")
    try:
        os.makedirs(carpeta, exist_ok=True)
        with open(sonda, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(sonda)
    except OSError as exc:
        return _error(t("Carpeta de datos"),
                      t("No se puede escribir en {c}: {e}",
                        c=carpeta, e=exc))
    return _ok(t("Carpeta de datos"),
               t("Se puede leer y escribir en {c}.", c=carpeta))


def _chk_ajustes() -> dict:
    ruta = os.path.join(config.carpeta_datos(), "ajustes.json")
    if not os.path.isfile(ruta):
        return _aviso(t("Ajustes guardados"),
                      t("Aún no hay ajustes guardados; se usan "
                        "los valores de fábrica."))
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        if not isinstance(datos, dict):
            raise ValueError("la raíz no es un objeto")
    except (OSError, ValueError) as exc:
        return _error(t("Ajustes guardados"),
                      t("El archivo de ajustes está dañado: {e}",
                        e=exc))
    return _ok(t("Ajustes guardados"),
               t("El archivo de ajustes se lee bien ({n} claves).",
                 n=len(datos)))


def _chk_registro_actividad() -> dict:
    ruta = config.ruta_actividad()
    if not os.path.isfile(ruta):
        return _aviso(t("Registro de actividad"),
                      t("Aún no hay registro de actividad."))
    try:
        with open(ruta, encoding="utf-8") as f:
            lineas = sum(1 for linea in f if linea.strip())
    except OSError as exc:
        return _error(t("Registro de actividad"),
                      t("No se puede leer el registro: {e}", e=exc))
    return _ok(t("Registro de actividad"),
               t("El registro se lee bien ({n} entradas).",
                 n=lineas))


# Activos visuales que la app necesita íntegros, con su tamaño
# mínimo sano (la heurística de siempre)…
_ACTIVOS_ESPERADOS = {
    "espartano_radar.png": 100_000,
    "espartano_animado.webp": 1_000_000,
    "icono_app.png": 1_000,
}

# …y su huella exacta (v1.0.20): un archivo que difiere está
# dañado o fue sustituido, aunque su tamaño parezca sano. La
# suite exige que estas huellas coincidan con los archivos del
# repo: si un activo cambia, se actualizan aquí a la vez.
HUELLAS_ACTIVOS = {
    "espartano_radar.png":
        "1056a6aae9aec751f42e93997305984082c5b83d6dc72427b8e76bf55718e402",
    "espartano_animado.webp":
        "c1e4ca62cfad2839f4175a08504b1a437f92658508467cfab38a223ed9a2101e",
    "icono_app.png":
        "4ec05e1205403c8b75634316af1ad91618c7d4b4fb790b06084cd4bd65e996e6",
}


def _huella_de(ruta: str) -> str:
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _activos_problematicos() -> tuple[list, list]:
    """(faltan o dañados, sospechosos) sobre la carpeta de
    activos: falta el archivo, su huella no coincide con la
    esperada o no se puede leer; sospechoso = tamaño raro en
    un archivo sin huella registrada."""
    carpeta = config.carpeta_activos()
    mal: list[str] = []
    sospechosos: list[str] = []
    for nombre, minimo in _ACTIVOS_ESPERADOS.items():
        ruta = os.path.join(carpeta, nombre)
        if not os.path.isfile(ruta):
            mal.append(nombre)
            continue
        esperada = HUELLAS_ACTIVOS.get(nombre)
        if esperada:
            try:
                if _huella_de(ruta) != esperada:
                    mal.append(nombre)
            except OSError:
                mal.append(nombre)
        elif os.path.getsize(ruta) < minimo:
            sospechosos.append(nombre)
    return mal, sospechosos


def _chk_activos() -> dict:
    mal, sospechosos = _activos_problematicos()
    if mal:
        return _error(t("Archivos de la interfaz"),
                      t("Faltan archivos o están dañados: {n}",
                        n=", ".join(mal)))
    if sospechosos:
        return _aviso(t("Archivos de la interfaz"),
                      t("Archivos con tamaño sospechoso: {n}",
                        n=", ".join(sospechosos)))
    return _ok(t("Archivos de la interfaz"),
               t("Los archivos visuales están completos."))


def _chk_radar() -> dict:
    ruta = os.path.join(_raiz_app(), "ui", "fondo_radar.py")
    try:
        with open(ruta, "rb") as f:
            huella = hashlib.sha256(f.read()).hexdigest()
    except OSError as exc:
        return _error(t("Diseño del radar"),
                      t("No se puede leer el radar: {e}", e=exc))
    if huella != HUELLA_RADAR:
        return _error(t("Diseño del radar"),
                      t("El archivo del radar difiere del diseño "
                        "aprobado."))
    return _ok(t("Diseño del radar"),
               t("El radar conserva su diseño aprobado."))


def _chk_openvpn() -> dict:
    from ..winapi import es_windows
    if not es_windows():
        return _aviso(t("OpenVPN (VPN)"),
                      t("No aplica fuera de Windows."))
    from ..winapi.vpn_win import (openvpn_instalado,
                                  _servicio_interactivo_activo)
    if not openvpn_instalado():
        return _error(t("OpenVPN (VPN)"),
                      t("OpenVPN no aparece instalado."))
    if _servicio_interactivo_activo():
        return _ok(t("OpenVPN (VPN)"),
                   t("OpenVPN está instalado y su servicio "
                     "interactivo está activo."))
    return _aviso(t("OpenVPN (VPN)"),
                  t("OpenVPN está instalado, pero su servicio "
                    "interactivo no está activo."))


def _chk_bloqueador() -> dict:
    from ..winapi import es_windows
    if not es_windows():
        return _aviso(t("Bloqueador de dominios"),
                      t("No aplica fuera de Windows."))
    from ..core.hosts_blocker import analizar_bloque, contar_bloqueados
    from ..winapi.tuneup_win import leer_hosts
    try:
        texto_hosts = leer_hosts()
        analisis = analizar_bloque(texto_hosts)
    except Exception as exc:  # el hosts puede estar bloqueado
        return _aviso(t("Bloqueador de dominios"),
                      t("No se pudo leer el archivo hosts: {e}",
                        e=exc))
    if analisis.get("danado"):
        return _error(t("Bloqueador de dominios"),
                      t("El bloque del archivo hosts está dañado "
                        "({m}) y conviene restaurarlo.",
                        m=analisis.get("motivo", "")))
    return _ok(t("Bloqueador de dominios"),
               t("El archivo hosts está íntegro "
                 "({n} dominios bloqueados).",
                 n=contar_bloqueados(texto_hosts)))


def _chk_optimizar() -> dict:
    """El testigo de la nota 5: el registro de eventos de ESTA
    máquina conoce al optimizador (proveedor correcto)."""
    from ..winapi import es_windows
    if not es_windows():
        return _aviso(t("Optimizar con Windows"),
                      t("No aplica fuera de Windows."))
    from ..winapi.disks import consultar_eventos_optimizacion
    eventos = consultar_eventos_optimizacion(
        "C", time.time() - 30 * 24 * 3600)
    if eventos:
        return _ok(t("Optimizar con Windows"),
                   t("El registro de eventos de este equipo sí "
                     "guarda las optimizaciones "
                     "({n} en 30 días).", n=len(eventos)))
    return _aviso(t("Optimizar con Windows"),
                  t("El registro de eventos no guarda "
                    "optimizaciones recientes; el veredicto se "
                    "apoyará en el resultado del ayudante."))


def _chk_puesta_a_punto() -> dict:
    from ..core.puesta_a_punto import (componer_veredicto,
                                       ejecutar_puesta_a_punto)
    if callable(ejecutar_puesta_a_punto) and \
            callable(componer_veredicto):
        return _ok(t("Puesta a punto"),
                   t("El motor de la rutina está íntegro."))
    return _error(t("Puesta a punto"),
                  t("El motor de la rutina no responde."))


def _chk_actualizaciones() -> dict:
    url = getattr(config, "UPDATE_VERSION_URL", "")
    if url:
        return _ok(t("Canal de actualizaciones"),
                   t("El canal de actualizaciones está "
                     "configurado."))
    return _error(t("Canal de actualizaciones"),
                  t("El canal de actualizaciones no está "
                    "configurado."))


def _carpeta_actualizaciones() -> str:
    """La carpeta de descargas de actualización (la misma que
    usa el actualizador: datos del usuario/actualizaciones)."""
    return os.path.join(config.carpeta_datos(), "actualizaciones")


# Un parcial con identidad válida es una descarga reanudable
# del último clic: se respeta. Pasada una semana ya es un
# resto viejo: la próxima actualización bajaría limpia igual.
DIAS_PARCIAL_VIEJO = 7


def identificar_parciales_problematicos(
        carpeta: str | None = None,
        ahora: float | None = None) -> list[str]:
    """Rutas de restos de descargas de actualización que se
    pueden limpiar sin riesgo (decisión pura, probada):

    - parciales «actualizacion-*.part» SIN identidad, con la
      identidad ilegible o incompleta (el resto ajeno que
      causó el fallo de huella de la v1.0.17 y anteriores), o
      más viejos de DIAS_PARCIAL_VIEJO días;
    - archivos «.identidad.json» huérfanos (su parcial ya no
      está).

    Un parcial reciente CON identidad válida NO se toca: es
    la descarga reanudable de la actualización en curso. Y
    jamás se mira fuera de esos dos patrones: el instalador
    ya descargado y cualquier otro archivo quedan intactos.
    """
    from .updater import _leer_identidad, _ruta_identidad

    carpeta = _carpeta_actualizaciones() if carpeta is None else carpeta
    ahora = time.time() if ahora is None else ahora
    if not os.path.isdir(carpeta):
        return []
    problematicos: list[str] = []
    for nombre in sorted(os.listdir(carpeta)):
        ruta = os.path.join(carpeta, nombre)
        if nombre.endswith(".part.identidad.json"):
            if not os.path.isfile(ruta[:-len(".identidad.json")]):
                problematicos.append(ruta)
            continue
        if not nombre.endswith(".part"):
            continue
        identidad = _leer_identidad(ruta)
        valida = bool(identidad.get("url")
                      and identidad.get("sha256")
                      and identidad.get("version"))
        try:
            viejo = (ahora - os.path.getmtime(ruta)
                     ) > DIAS_PARCIAL_VIEJO * 86400
        except OSError:
            viejo = False
        if not valida or viejo:
            problematicos.append(ruta)
            ruta_identidad = _ruta_identidad(ruta)
            if os.path.isfile(ruta_identidad):
                problematicos.append(ruta_identidad)
    return problematicos


def _chk_parciales_actualizacion() -> dict:
    rutas = identificar_parciales_problematicos()
    if not rutas:
        return _ok(t("Restos de descargas"),
                   t("La carpeta de actualizaciones no guarda "
                     "parciales viejos ni ajenos."))
    nombres = ", ".join(sorted(os.path.basename(r) for r in rutas))
    return _aviso(t("Restos de descargas"),
                  t("Hay restos de descargas de actualización "
                    "viejos o sin identidad: {n}", n=nombres))


COMPROBACIONES = [
    _chk_version, _chk_modulos, _chk_carpeta_datos, _chk_ajustes,
    _chk_registro_actividad, _chk_activos, _chk_radar,
    _chk_openvpn, _chk_bloqueador, _chk_optimizar,
    _chk_puesta_a_punto, _chk_actualizaciones,
    _chk_parciales_actualizacion,
]


# ---------------------------------------------------------------------------
# Auto-reparación segura (v1.0.20)
#
# Cada reparación devuelve (hecho, detalle): «hecho» True si
# aplicó su arreglo, False si lo intentó y no pudo, y None si
# no era aplicable o ya no había nada que reparar (no tocó
# nada). TODAS revalidan su precondición antes de tocar nada.
# Lo que no está en REPARACIONES no se auto-repara JAMÁS
# (conectar una VPN, borrar datos del usuario, la seguridad
# de Windows/Defender, el registro): sale como «pendiente de
# tu orden».
# ---------------------------------------------------------------------------

def reparar_ajustes() -> tuple[bool | None, str]:
    """Ajustes ilegibles o que no son un objeto: se guarda una
    copia del archivo dañado (para el informe) y el archivo
    vuelve a los valores sanos de fábrica."""
    ruta = os.path.join(config.carpeta_datos(), "ajustes.json")
    if not os.path.isfile(ruta):
        return None, t("No hay archivo de ajustes que reparar.")
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        if isinstance(datos, dict):
            return None, t("El archivo de ajustes se lee bien: "
                           "no se tocó nada.")
    except (OSError, ValueError):
        pass  # dañado de verdad: se repara abajo
    marca = time.strftime("%Y%m%d-%H%M%S")
    copia = os.path.join(
        config.carpeta_datos(), f"ajustes_danado_{marca}.json")
    try:
        shutil.copyfile(ruta, copia)
    except OSError as exc:
        return False, t("No se pudo guardar la copia del "
                        "archivo dañado: {e}", e=exc)
    try:
        from ..ui.services import Ajustes
        Ajustes(_ruta=ruta).guardar()
    except Exception:
        # Sin la fachada de servicios: los valores esenciales.
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"url_actualizacion":
                       config.UPDATE_VERSION_URL},
                      f, ensure_ascii=False, indent=1)
    return True, t("El archivo dañado se guardó como {c} y los "
                   "ajustes volvieron a los valores de fábrica.",
                   c=os.path.basename(copia))


def _copia_hosts_valida() -> str:
    """La copia del hosts guardada por la propia app más
    reciente que sea VÁLIDA (se lee, no está vacía y su bloque
    no está dañado); "" si no hay ninguna."""
    from .hosts_blocker import analizar_bloque

    carpeta = config.ruta_respaldos()
    if not os.path.isdir(carpeta):
        return ""
    candidatos = [
        os.path.join(carpeta, n) for n in os.listdir(carpeta)
        if n.startswith("hosts_") and n.endswith(".bak")]
    candidatos.sort(key=lambda r: os.path.getmtime(r)
                    if os.path.exists(r) else 0, reverse=True)
    for ruta in candidatos:
        try:
            with open(ruta, encoding="utf-8",
                      errors="replace") as f:
                texto = f.read()
        except OSError:
            continue
        if texto.strip() and not analizar_bloque(texto)["danado"]:
            return ruta
    return ""


def reparar_hosts() -> tuple[bool | None, str]:
    """Bloque del hosts dañado: se restaura la copia válida
    que la propia app guarda, por la escritura robusta de
    siempre. Sin copia válida NO se inventa nada: pendiente."""
    from ..winapi import es_windows
    if not es_windows():
        return None, t("No aplica fuera de Windows.")
    from ..winapi.tuneup_win import (escribir_hosts_robusto,
                                     leer_hosts)
    from .hosts_blocker import analizar_bloque

    try:
        actual = leer_hosts()
    except Exception as exc:
        return False, t("No se pudo leer el archivo hosts: {e}",
                        e=exc)
    if not analizar_bloque(actual)["danado"]:
        return None, t("El bloque del archivo hosts no está "
                       "dañado: no se tocó nada.")
    copia = _copia_hosts_valida()
    if not copia:
        return False, t("No hay ninguna copia válida del "
                        "archivo hosts guardada: la restauración "
                        "queda pendiente de tu orden.")
    with open(copia, encoding="utf-8", errors="replace") as f:
        texto = f.read()
    res = escribir_hosts_robusto(texto, config.ruta_respaldos())
    if res.get("ok") and res.get("via") == "directa":
        return True, t("El archivo hosts se restauró desde su "
                       "copia {c}.", c=os.path.basename(copia))
    if res.get("ok") and res.get("via") == "programada":
        return False, t("La restauración desde la copia {c} "
                        "quedó programada para el reinicio: se "
                        "comprobará al reiniciar.",
                        c=os.path.basename(copia))
    return False, t("Windows no confirmó la restauración del "
                    "hosts: {d}", d=res.get("detalle", ""))


def _carpetas_fuente_activos() -> list[str]:
    """Carpetas locales donde puede vivir una copia íntegra de
    los activos: la ruta alternativa que config conoce en modo
    congelado y una carpeta «activos_respaldo» en los datos, si
    existe. La propia carpeta de activos nunca es su fuente."""
    destino = os.path.normpath(config.carpeta_activos())
    candidatas: list[str] = []
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS",
                       os.path.dirname(sys.executable))
        candidatas += [
            os.path.join(base, "assets"),
            os.path.join(base, "antivirus_hogar_pc", "assets"),
        ]
    candidatas.append(
        os.path.join(config.carpeta_datos(), "activos_respaldo"))
    return [c for c in candidatas
            if os.path.normpath(c) != destino and os.path.isdir(c)]


def reparar_activos() -> tuple[bool | None, str]:
    """Activos faltantes o con huella mala: se restauran desde
    una copia íntegra LOCAL verificada (huella o tamaño). Si no
    hay copia íntegra en este equipo, no se baja nada de
    fuentes no verificadas: queda pendiente (reinstalar)."""
    mal, _sospechosos = _activos_problematicos()
    if not mal:
        return None, t("Los archivos de la interfaz están "
                       "íntegros: no se tocó nada.")
    carpeta = config.carpeta_activos()
    fuentes = _carpetas_fuente_activos()
    restaurados: list[str] = []
    imposibles: list[str] = []
    for nombre in mal:
        copia = None
        for fuente in fuentes:
            candidata = os.path.join(fuente, nombre)
            if not os.path.isfile(candidata):
                continue
            esperada = HUELLAS_ACTIVOS.get(nombre)
            try:
                if esperada and _huella_de(candidata) != esperada:
                    continue
                if not esperada and os.path.getsize(
                        candidata) < _ACTIVOS_ESPERADOS[nombre]:
                    continue
            except OSError:
                continue
            copia = candidata
            break
        if copia is None:
            imposibles.append(nombre)
            continue
        try:
            shutil.copyfile(copia, os.path.join(carpeta, nombre))
            restaurados.append(nombre)
        except OSError:
            imposibles.append(nombre)
    if imposibles:
        return False, t("No se encontró una copia íntegra local "
                        "de {n}: hay que reinstalar la aplicación "
                        "para restaurarlo.",
                        n=", ".join(imposibles))
    return True, t("Se restauraron desde la copia íntegra "
                   "local: {n}.", n=", ".join(restaurados))


def reparar_servicio_openvpn() -> tuple[bool | None, str]:
    """Servicio interactivo de OpenVPN parado o manual: se
    arranca y se deja en inicio automático SOLO por la vía del
    servicio (vpn_win.arrancar_servicio_interactivo): la app
    no eleva por su cuenta ni lanza ningún UAC."""
    from ..winapi import es_windows
    if not es_windows():
        return None, t("No aplica fuera de Windows.")
    from ..winapi.vpn_win import (arrancar_servicio_interactivo,
                                  openvpn_instalado)
    if not openvpn_instalado():
        return False, t("OpenVPN no está instalado: instalarlo "
                        "queda pendiente de tu orden.")
    res = arrancar_servicio_interactivo()
    if res.get("ok"):
        return True, t("El servicio interactivo de OpenVPN "
                       "quedó arrancado y en inicio automático.")
    return False, t("No se pudo arrancar el servicio de "
                    "OpenVPN por la vía del servicio: {d}",
                    d=res.get("detalle", ""))


def reparar_parciales() -> tuple[bool | None, str]:
    """Restos de descargas de actualización: se quitan SOLO
    los archivos identificados como parciales viejos o sin
    identidad (y sus identidades huérfanas), dentro de la
    carpeta «actualizaciones» y nada más."""
    rutas = identificar_parciales_problematicos()
    if not rutas:
        return None, t("No hay restos de descargas que limpiar.")
    quitados = 0
    fallados = 0
    for ruta in rutas:
        try:
            os.remove(ruta)
            quitados += 1
        except OSError:
            fallados += 1
    if fallados:
        return False, t("Se quitaron {n} restos, pero {m} no "
                        "se pudieron borrar.",
                        n=quitados, m=fallados)
    return True, t("Se quitaron {n} restos de descargas de "
                   "actualización.", n=quitados)


# El registro de lo ÚNICO que el diagnóstico auto-repara. Todo
# fallo cuyo nombre no esté aquí sale como aviso o como
# «pendiente de tu orden», jamás se arregla por su cuenta.
REPARACIONES = {
    _chk_ajustes: reparar_ajustes,
    _chk_bloqueador: reparar_hosts,
    _chk_activos: reparar_activos,
    _chk_openvpn: reparar_servicio_openvpn,
    _chk_parciales_actualizacion: reparar_parciales,
}


def _correr_comprobacion(funcion) -> dict:
    """Una comprobación aislada: la que explota sale como
    error con su excepción, como siempre."""
    try:
        return funcion()
    except Exception as exc:  # a propósito: se informa
        return _error(
            getattr(funcion, "__name__", "comprobación"),
            f"{type(exc).__name__}: {exc}")


def diagnosticar() -> list[dict]:
    """Corre TODAS las comprobaciones, sin tocar nada."""
    return [_correr_comprobacion(f) for f in COMPROBACIONES]


def diagnosticar_y_reparar() -> list[dict]:
    """Diagnóstico + auto-reparación SEGURA (v1.0.20).

    Por cada comprobación que no sale «ok»:

    - sin reparación registrada → el aviso se queda aviso y
      el error pasa a «pendiente» (pendiente de tu orden);
    - con reparación registrada → se aplica (aislada: si
      explota, cuenta como intento fallido y no tumba a las
      demás) y se VUELVE A COMPROBAR: solo si la comprobación
      pasa después, el resultado es «reparado», con lo que se
      hizo escrito; si sigue fallando, es «pendiente» con el
      motivo real del intento y de la nueva comprobación.
    """
    resultados: list[dict] = []
    for funcion in COMPROBACIONES:
        r = _correr_comprobacion(funcion)
        if r["estado"] == "ok":
            resultados.append(r)
            continue
        reparacion = REPARACIONES.get(funcion)
        if reparacion is None:
            if r["estado"] == "error":
                r = {"nombre": r["nombre"], "estado": "pendiente",
                     "detalle": r["detalle"]}
            resultados.append(r)
            continue
        try:
            hecho, detalle_rep = reparacion()
        except Exception as exc:  # la reparación tampoco tumba
            hecho, detalle_rep = False, f"{type(exc).__name__}: {exc}"
        r2 = _correr_comprobacion(funcion)
        if r2["estado"] == "ok":
            if hecho:
                resultados.append({
                    "nombre": r["nombre"], "estado": "reparado",
                    "detalle": t(
                        "{antes} Reparación: {rep} Al comprobar "
                        "de nuevo: {despues}",
                        antes=r["detalle"], rep=detalle_rep,
                        despues=r2["detalle"])})
            else:
                # La comprobación ya pasa (p. ej. otro proceso
                # lo dejó bien entre tanto): se cuenta como está.
                resultados.append(r2)
        elif hecho is None:
            # La reparación no era aplicable o ya no había
            # nada que reparar: el resultado se queda como
            # salió (el error, eso sí, pasa a «pendiente»).
            if r["estado"] == "error":
                r = {"nombre": r["nombre"], "estado": "pendiente",
                     "detalle": r["detalle"]}
            resultados.append(r)
        else:
            # Se intentó y la comprobación sigue sin pasar:
            # pendiente del usuario, con el motivo real del
            # intento y de la nueva comprobación.
            resultados.append({
                "nombre": r["nombre"], "estado": "pendiente",
                "detalle": t(
                    "{antes} Reparación intentada: {rep} Al "
                    "comprobar de nuevo: {despues}",
                    antes=r["detalle"], rep=detalle_rep,
                    despues=r2["detalle"])})
    return resultados


_SIMBOLOS = {"ok": "✓", "aviso": "⚠", "error": "✗",
             "reparado": "🔧", "pendiente": "✗"}


def construir_informe(resultados: list[dict],
                      cuando: float | None = None) -> str:
    """El informe en texto plano: listo para enseñar, copiar
    y exportar tal cual. Tres bloques (v1.0.20): «Correcto»,
    «Reparado» y «Pendiente de tu orden»; un bloque vacío no
    se imprime."""
    cuando = time.time() if cuando is None else cuando
    fecha = time.strftime("%Y-%m-%d %H:%M", time.localtime(cuando))
    bloques = [
        (t("Correcto"),
         [r for r in resultados if r["estado"] in ("ok", "aviso")]),
        (t("Reparado"),
         [r for r in resultados if r["estado"] == "reparado"]),
        (t("Pendiente de tu orden"),
         [r for r in resultados
          if r["estado"] in ("pendiente", "error")]),
    ]
    lineas = [
        t("Diagnóstico de integridad de la aplicación"),
        t("Antivirus Hogar PC {v} — {f}",
          v=getattr(config, "VERSION", "?"), f=fecha),
        "",
    ]
    for titulo, items in bloques:
        if not items:
            continue
        lineas.append(f"{titulo}:")
        for r in items:
            lineas.append(f"{_SIMBOLOS.get(r['estado'], '?')} "
                          f"{r['nombre']}: {r['detalle']}")
        lineas.append("")
    bien = sum(1 for r in resultados if r["estado"] == "ok")
    avisos = sum(1 for r in resultados if r["estado"] == "aviso")
    reparados = sum(1 for r in resultados
                    if r["estado"] == "reparado")
    pendientes = sum(1 for r in resultados
                     if r["estado"] in ("pendiente", "error"))
    lineas.append(t(
        "Resumen: {ok} bien · {av} avisos · {rep} reparados · "
        "{pen} pendientes de tu orden",
        ok=bien, av=avisos, rep=reparados, pen=pendientes))
    return "\n".join(lineas)
