# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller --onedir de Antivirus Hogar PC (Carril E).

Se ejecuta desde la raíz del proyecto (lo hace Construir-en-Windows.bat y
el workflow de GitHub Actions):

    pyinstaller packaging/antivirus-hogar-pc.spec --noconfirm

Produce dist/AntivirusHogarPC/AntivirusHogarPC.exe (+ carpeta _internal),
que es lo que empaqueta packaging/instalador.iss con Inno Setup.

Notas:
- Los módulos de la app se importan por nombre en tiempo de ejecución
  (modules/__init__.py, registro explícito desde v1.0.1), así que se
  fuerza la inclusión de TODOS los submódulos del paquete como
  hiddenimports.
- Los activos (semillas de dominios y firmas) van a
  «antivirus_hogar_pc/assets» dentro del bundle: es la primera ruta que
  busca config.carpeta_activos() en modo congelado.
- smartctl.exe NO se incluye aquí: lo añade el instalador (Inno) si el
  paquete de smartmontools está en packaging/smartctl/ (ver instalador.iss).
"""
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

RAIZ = os.path.dirname(SPECPATH)  # packaging/ -> raíz del proyecto

# BUG v1.0.0 (corregido en v1.0.1): al ejecutarse el .spec, sys.path NO
# incluye la raíz del proyecto (ni siquiera con cwd en la raíz), así que
# collect_submodules no encontraba el paquete y devolvía [] EN SILENCIO:
# los subpaquetes de módulos no entraban en el ejecutable y la app abría
# sin Panel, Escáner ni herramientas. Se mete la raíz a mano y se EXIGE
# que la recolección traiga los registros: si no, la compilación falla
# en voz alta en vez de entregar un instalador vacío.
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

hiddenimports = collect_submodules("antivirus_hogar_pc")
_REGISTROS_ESPERADOS = [
    "antivirus_hogar_pc.modules.panel.registro",
    "antivirus_hogar_pc.modules.security.registro",
    "antivirus_hogar_pc.modules.system.registro",
    "antivirus_hogar_pc.modules.net.registro",
]
_faltantes = [m for m in _REGISTROS_ESPERADOS if m not in hiddenimports]
if _faltantes:
    raise SystemExit(
        f"collect_submodules incompleto; faltan {_faltantes}. "
        "La compilación se detiene: el .exe saldría sin módulos."
    )

a = Analysis(
    [os.path.join(RAIZ, "AntivirusHogarPC.py")],
    pathex=[RAIZ],
    binaries=[],
    datas=[
        (os.path.join(RAIZ, "antivirus_hogar_pc", "assets"),
         os.path.join("antivirus_hogar_pc", "assets")),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AntivirusHogarPC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # app de ventana; el modo --escaneo-programado no la necesita
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Icono de la app (v1.0.5): el espartano cyborg dentro del escudo,
    # aprobado por el usuario el 2026-11-24; .ico multirresolución
    # generado desde packaging/icono-espartano.webp.
    icon=os.path.join(RAIZ, "packaging", "icono.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AntivirusHogarPC",
)
