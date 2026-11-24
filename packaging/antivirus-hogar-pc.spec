# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller --onedir de Antivirus Hogar PC (Carril E).

Se ejecuta desde la raíz del proyecto (lo hace Construir-en-Windows.bat y
el workflow de GitHub Actions):

    pyinstaller packaging/antivirus-hogar-pc.spec --noconfirm

Produce dist/AntivirusHogarPC/AntivirusHogarPC.exe (+ carpeta _internal),
que es lo que empaqueta packaging/instalador.iss con Inno Setup.

Notas:
- Los módulos de la app se descubren en tiempo de ejecución
  (modules/__init__.py usa pkgutil + importlib), así que se fuerza la
  inclusión de TODOS los submódulos del paquete como hiddenimports.
- Los activos (semillas de dominios y firmas) van a
  «antivirus_hogar_pc/assets» dentro del bundle: es la primera ruta que
  busca config.carpeta_activos() en modo congelado.
- smartctl.exe NO se incluye aquí: lo añade el instalador (Inno) si el
  paquete de smartmontools está en packaging/smartctl/ (ver instalador.iss).
"""
import os

from PyInstaller.utils.hooks import collect_submodules

RAIZ = os.path.dirname(SPECPATH)  # packaging/ -> raíz del proyecto

hiddenimports = collect_submodules("antivirus_hogar_pc")

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
    # icon=os.path.join(RAIZ, "packaging", "icono.ico"),  # cuando exista el .ico
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
