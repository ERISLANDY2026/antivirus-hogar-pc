"""Declaración de los módulos del Carril B. Sin imports de Qt."""
from antivirus_hogar_pc.contracts import RegistroModulo

REGISTROS = [
    RegistroModulo(
        id="escaner", titulo="Escanear", icono="lupa", orden=20,
        carril="B", ola=1,
        pagina="antivirus_hogar_pc.modules.security.page:crear_pagina_escaner",
    ),
    RegistroModulo(
        id="proteccion", titulo="Protección", icono="escudo", orden=30,
        carril="B", ola=2,
        pagina="antivirus_hogar_pc.modules.security.page:crear_pagina_proteccion",
    ),
    RegistroModulo(
        id="informes", titulo="Informes", icono="informe", orden=90,
        carril="B", ola=2,
        pagina="antivirus_hogar_pc.modules.security.page:crear_pagina_informes",
    ),
]
