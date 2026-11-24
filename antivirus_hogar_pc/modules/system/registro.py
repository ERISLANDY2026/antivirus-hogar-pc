"""Declaración de los módulos del Carril C. Sin imports de Qt."""
from antivirus_hogar_pc.contracts import RegistroModulo

REGISTROS = [
    RegistroModulo(
        id="drivers", titulo="Drivers", icono="chip", orden=40,
        carril="C", ola=2,
        pagina="antivirus_hogar_pc.modules.system.page:crear_pagina_drivers",
    ),
    RegistroModulo(
        id="limpieza", titulo="Limpieza", icono="limpieza", orden=50,
        carril="C", ola=3,
        pagina="antivirus_hogar_pc.modules.system.page:crear_pagina_limpieza",
    ),
    RegistroModulo(
        id="discos", titulo="Discos", icono="disco", orden=60,
        carril="C", ola=2,
        pagina="antivirus_hogar_pc.modules.system.page:crear_pagina_discos",
    ),
]
