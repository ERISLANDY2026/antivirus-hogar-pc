"""Declaración del módulo Panel. Sin imports de Qt (descubrimiento headless)."""
from antivirus_hogar_pc.contracts import RegistroModulo

REGISTROS = [
    RegistroModulo(
        id="panel", titulo="Inicio", icono="inicio", orden=10,
        carril="A", ola=1,
        pagina="antivirus_hogar_pc.modules.panel.page:crear_pagina",
    ),
]
