"""Captura de la TABLA de VPN Gate (v1.0.10, botones de la tabla)."""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import QApplication  # noqa: E402

from antivirus_hogar_pc.contracts import ContextoModulo, ResultadoModulo  # noqa: E402
from antivirus_hogar_pc.modules.net import page as net_page  # noqa: E402
from antivirus_hogar_pc.modules.net import servicios_red as srv  # noqa: E402
from antivirus_hogar_pc.modules.net.fake import servidores_fake  # noqa: E402
from antivirus_hogar_pc.ui import theme  # noqa: E402

SALIDA = os.path.join(os.path.dirname(__file__), "..", "evidencia-v1010")

app = QApplication([])
app.setStyleSheet(theme.QSS)
srv.informe_wifi = lambda: ResultadoModulo(ok=False, mensaje="sin wifi")
srv.descargar_servidores_completos = lambda: ResultadoModulo(
    ok=False, mensaje="sin red (captura)")
srv.estado_vpn = lambda: ResultadoModulo(ok=True, datos={})
widget = net_page.crear_pagina_red(ContextoModulo(servicios=None))
pagina = widget._pagina_controladora
pagina._servidores_cargados(ResultadoModulo(ok=True, datos=servidores_fake()))
pagina._servidor_conectado = pagina._visibles[0].hostname
pagina._repintar_servidores()
widget.resize(880, 900)
widget.show()
fin = time.time() + 0.5
while time.time() < fin:
    app.processEvents()
    time.sleep(0.01)
tabla = pagina._tabla_vpn
tabla.resize(860, 130)
tabla.grab().save(os.path.join(SALIDA, "vpngate-tabla-fila-conectada.png"))
print("ok")
