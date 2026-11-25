"""v1.0.9 — La solución del «Error 31» de SoftEther + 2 cambios.

1. El controlador de la tarjeta virtual (Neo6_x64_VPN, Windows 10
   x64) viaja con la app y el INSTALADOR lo almacena en el
   DriverStore con pnputil /add-driver, VISIBLE (SW_SHOW) y ANTES
   de NicCreate, verificando con /enum-drivers; el registro
   acumulado va a softether-nic-instalacion.txt. La compilación en
   la nube lo extrae del hamcore del instalador oficial (o del
   árbol oficial de la etiqueta) verificando sus huellas SHA-256.
2. Respaldo al conectar: crear_nic_elevada corre INTERACTIVO (sin
   -NonInteractive), vuelve a almacenar el controlador con pnputil
   y guarda la salida REAL (su línea de error va en el detalle).
3. Cambio 1: la fila del servidor conectado lleva «Conectado»
   (verde, deshabilitado) y «Desconectar» (rojo) a su derecha.
4. Cambio 2: la calificación de salud sale del centro del anillo:
   AnilloSalud ya no dibuja texto y expone texto_puntuacion() +
   señal valor_cambiado para la esquina inferior izquierda del
   radar de Inicio.
"""
import os

import pytest

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def _leer(ruta_relativa: str) -> str:
    with open(os.path.join(RAIZ, ruta_relativa), encoding="utf-8") as f:
        return f.read()


# === 1. Instalador: pnputil visible, antes de NicCreate =======================

def test_instalador_109_almacena_el_controlador_antes_de_crear():
    iss = _leer(os.path.join("packaging", "instalador.iss"))
    assert '#define AppVersion "1.0.9"' in iss
    assert "pnputil" in iss and "/add-driver" in iss
    assert "Neo6_x64_VPN.inf" in iss
    assert "/enum-drivers" in iss  # verificación de que quedó almacenado
    # El paso de pnputil va VISIBLE: tras «/add-driver», el primer
    # modo de ventana que aparece es SW_SHOW (el SW_HIDE de la
    # sección es solo el de la verificación /enum-drivers).
    seccion = iss.split("procedure InstalarControladorTarjetaVirtual();")[1]
    seccion = seccion.split("procedure ")[0]
    i_add = seccion.index("/add-driver")
    assert seccion.index("SW_SHOW", i_add) < seccion.index("SW_HIDE", i_add)
    # Orden en la preparación: primero el controlador, después NicCreate.
    envoltura = iss.split("procedure PrepararTarjetaVirtualSoftEther();")[1]
    envoltura = envoltura.split("procedure ")[0]
    assert envoltura.index("InstalarControladorTarjetaVirtual();") < \
        envoltura.index("CrearTarjetaVirtualSoftEther();")
    # Y la preparación es lo que corre al terminar de instalar.
    assert "PrepararTarjetaVirtualSoftEther();" in iss
    # El registro es ACUMULADO (las dos secciones en un solo archivo).
    assert "AgregarLogNic" in iss
    assert "softether-nic-instalacion.txt" in iss


def test_workflow_109_extrae_y_verifica_el_controlador():
    yml = _leer(os.path.join(".github", "workflows", "build-windows.yml"))
    assert "Neo6_Win10" in yml  # la carpeta del controlador en el hamcore
    for huella in (
        "8F049A53BAB3F1A16F118C91C15569CCEEF4B2955905C8F7C70F7952F9C175B8",
        "54E74A7906AF47C2B07F0EA171973D6ABB123549A1C66CF0CC6F24EC5E55A237",
        "162C56608532EF7C699520194FD2231550BAB6D0A32C1BBB6866F22DA8C45AED",
    ):
        assert huella in yml  # huellas fijadas del paquete oficial
    assert "v4.44-9807-rtm" in yml  # respaldo: árbol oficial de la etiqueta
    assert "Get-ChildItem -Recurse se-extract" in yml  # forense completa


# === 2. Respaldo al conectar: interactivo y con la salida real ================

def test_elevado_interactivo_sin_noninteractive_en_el_proceso_elevado():
    fuente = _leer(os.path.join(
        "antivirus_hogar_pc", "winapi", "powershell.py"))
    funcion = fuente.split("def ejecutar_elevado_interactivo")[1]
    funcion = funcion.split("\ndef ")[0]
    assert "ArgumentList" in funcion
    argument_list = funcion.split("ArgumentList")[1].split(";")[0]
    # El proceso ELEVADO no lleva -NonInteractive (el aviso de
    # Windows debe poder aparecer); el lanzador no elevado sí, y es
    # otra cosa: va fuera del ArgumentList.
    assert "NonInteractive" not in argument_list
    assert "-EncodedCommand" in argument_list


def _preparar_vpn_win_falso(monkeypatch, tmp_path, nic_presente: bool,
                            salida_elevada: str):
    """vpn_win con vpncmd falso y el paso elevado grabado."""
    from antivirus_hogar_pc.winapi import powershell, vpn_win

    carpeta_soft = tmp_path / "softether"
    (carpeta_soft / "driver").mkdir(parents=True)
    (carpeta_soft / "driver" / "Neo6_x64_VPN.inf").write_text(
        "[Version]", encoding="utf-8")
    carpeta_datos = tmp_path / "datos"
    carpeta_datos.mkdir()
    monkeypatch.setattr(vpn_win, "ruta_vpncmd",
                        lambda: r"C:\fake\vpncmd_x64.exe")
    monkeypatch.setattr(vpn_win, "carpeta_softether",
                        lambda: str(carpeta_soft))
    monkeypatch.setattr(vpn_win, "carpeta_perfiles_vpn",
                        lambda: str(carpeta_datos))
    grabado = {}

    def falso_interactivo(script, timeout=240):
        grabado["script"] = script
        (carpeta_datos / "salida-crear-nic.txt").write_text(
            salida_elevada, encoding="utf-8")
        return True

    monkeypatch.setattr(powershell, "ejecutar_elevado_interactivo",
                        falso_interactivo)
    if nic_presente:
        tabla = ("Virtual Network Adapter Name | Status\n"
                 "VPN | Connected\n")
    else:
        tabla = "Virtual Network Adapter Name | Status\n"
    monkeypatch.setattr(vpn_win, "_ejecutar_vpncmd",
                        lambda args, timeout=30: (0, tabla))
    return vpn_win, grabado


def test_crear_nic_elevada_109_almacena_controlador_y_crea(monkeypatch,
                                                          tmp_path):
    vpn_win, grabado = _preparar_vpn_win_falso(
        monkeypatch, tmp_path, nic_presente=True, salida_elevada="ok")
    res = vpn_win.crear_nic_elevada()
    assert res["ok"] is True
    script = grabado["script"]
    # La receta completa, en orden: pnputil primero, NicCreate después.
    assert "pnputil" in script and "/add-driver" in script
    assert "Neo6_x64_VPN.inf" in script
    assert script.index("pnputil") < script.index("NicCreate")
    # La salida real se guarda en la carpeta de datos de la app.
    assert "salida-crear-nic.txt" in script


def test_crear_nic_elevada_109_detalle_con_la_salida_real(monkeypatch,
                                                          tmp_path):
    vpn_win, _grabado = _preparar_vpn_win_falso(
        monkeypatch, tmp_path, nic_presente=False,
        salida_elevada=(
            "VPN Client>NicCreate VPN\n"
            "Error occurred. (Error code: 31)\n"
            "Installation of the Virtual Network Adapter device "
            "driver failed.\n"))
    res = vpn_win.crear_nic_elevada()
    assert res["ok"] is False
    # El detalle trae la línea REAL de vpncmd, no un texto inventado.
    assert "Error code: 31" in res["detalle"]


# === 3. Cambio 1: botones por fila en VPN Gate ================================

def test_fila_conectada_lleva_conectado_verde_y_desconectar_rojo():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QPushButton

    from antivirus_hogar_pc import config
    from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo
    from antivirus_hogar_pc.modules.net import page as netpage
    from antivirus_hogar_pc.modules.net import servicios_red as srv
    from antivirus_hogar_pc.modules.net.fake import servidores_fake
    from antivirus_hogar_pc.ui import theme

    app = QApplication.instance() or QApplication([])
    pagina = netpage._PaginaRed(ContextoModulo(servicios=None))
    pagina._servidores_cargados(
        ResultadoModulo(ok=True, datos=servidores_fake()))
    assert pagina._tabla_vpn.rowCount() == 2
    conectado = pagina._visibles[0].hostname
    pagina._servidor_conectado = conectado
    pagina._repintar_servidores()

    celda0 = pagina._tabla_vpn.cellWidget(0, 5)
    botones0 = {b.text(): b for b in celda0.findChildren(QPushButton)}
    assert set(botones0) == {"Conectado", "Desconectar"}
    assert theme.VERDE_BOTON in botones0["Conectado"].styleSheet()
    assert botones0["Conectado"].isEnabled() is False
    assert theme.ROJO_BOTON in botones0["Desconectar"].styleSheet()
    assert botones0["Desconectar"].isEnabled() is True

    celda1 = pagina._tabla_vpn.cellWidget(1, 5)
    botones1 = {b.text(): b for b in celda1.findChildren(QPushButton)}
    assert set(botones1) == {"Conectar"}
    assert config.VERSION == "1.0.9"
    pagina.deleteLater()
    app.processEvents()


# === 4. Cambio 2: la cifra fuera del centro del anillo ========================

def test_anillo_109_sin_cifra_central_y_con_texto_para_la_esquina():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from antivirus_hogar_pc.ui import theme
    from antivirus_hogar_pc.ui.health_ring import AnilloSalud

    app = QApplication.instance() or QApplication([])
    anillo = AnilloSalud()
    # Sin fijar: la esquina enseña «…», nunca un 0 en rojo.
    cifra, _color, leyenda = anillo.texto_puntuacion()
    assert cifra == "…" and leyenda == "Salud del equipo"
    recibidos = []
    anillo.valor_cambiado.connect(recibidos.append)
    anillo.fijar_puntuacion(71, animado=False)
    assert recibidos and recibidos[-1] == 71.0
    cifra, color, leyenda = anillo.texto_puntuacion()
    # 71 cae en la banda ámbar del semáforo de la app (≥80 verde).
    assert cifra == "71" and color == theme.AMBAR.lower()
    assert leyenda == "Salud del equipo"
    anillo.fijar_sin_datos()
    cifra, _color, leyenda = anillo.texto_puntuacion()
    assert cifra == "—" and leyenda == "Sin datos de Windows"
    # La cifra ya NO se pinta dentro del anillo.
    fuente = _leer(os.path.join(
        "antivirus_hogar_pc", "ui", "health_ring.py"))
    assert "drawText" not in fuente
    anillo.deleteLater()
    app.processEvents()
