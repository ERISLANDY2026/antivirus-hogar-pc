"""Declaración de los módulos del Carril D. Sin imports de Qt."""
from antivirus_hogar_pc.contracts import RegistroModulo

REGISTROS = [
    RegistroModulo(
        id="actualizaciones", titulo="Actualizaciones", icono="actualizar", orden=70,
        carril="D", ola=2,
        pagina="antivirus_hogar_pc.modules.net.page:crear_pagina_actualizaciones",
    ),
    RegistroModulo(
        id="red", titulo="Red y VPN", icono="red", orden=80,
        carril="D", ola=3,
        pagina="antivirus_hogar_pc.modules.net.page:crear_pagina_red",
    ),
]
