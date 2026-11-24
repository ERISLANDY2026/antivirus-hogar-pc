# Informe v1.0.1 — Bug «la app abre solo en Ajustes»

## Errores encontrados

1. **CAUSA RAÍZ A — descubrimiento por pkgutil en el congelado**
   (`antivirus_hogar_pc/modules/__init__.py`, v1.0.0): `descubrir_modulos()`
   enumeraba paquetes con `pkgutil.iter_modules(paquete.__path__)`. En el
   ejecutable de PyInstaller los paquetes viven en el PYZ y `__path__`
   apunta a `_internal/antivirus_hogar_pc/modules`, carpeta que NO existe
   en el disco → iter_modules devuelve `[]` sin error → 0 módulos.
   Solo sobrevivía «Ajustes», cableado a mano en `ui/main_window.py`.
   Evidencia: sonda congelada con el código v1 → `N_MODULOS: 0`
   (en fuente: 9); `ls` confirma que la carpeta de `__path__` no existe.

2. **CAUSA RAÍZ B — collect_submodules vacío en el .spec**
   (`packaging/antivirus-hogar-pc.spec`): al ejecutarse el .spec,
   `sys.path` no incluye la raíz del proyecto (probado con cwd en la raíz
   y el .spec en `packaging/`, idéntico al workflow) →
   `collect_submodules("antivirus_hogar_pc")` devolvía **0** en silencio →
   `hiddenimports` vacío → los subpaquetes `modules.*` (importados solo
   por cadena, invisibles al análisis estático) ni siquiera entraban en
   el PYZ. Evidencia: réplica del .spec → `HIDDENIMPORTS: 0`; el TOC del
   PYZ de la sonda solo contenía `antivirus_hogar_pc.modules`, sin hijos.

3. **Errores tragados en silencio** (mismo archivo, v1.0.0):
   `except ModuleNotFoundError: continue` — un fallo real al importar un
   `registro.py` desaparecía igual que un paquete sin registro.

4. **Fallo silencioso en la ventana** (`ui/main_window.py`): con 0 módulos
   no se mostraba página inicial ni aviso alguno; el área quedaba vacía.

5. **La suite no podía cazarlo**: los tests corren solo sobre el código
   fuente (donde el descubrimiento por disco sí funciona) y el workflow
   ejecutaba pytest antes de compilar, sin inspeccionar nunca el
   artefacto congelado. Por eso 57/57 con la app rota.

6. **Secundario (observado en la foto, NO es causa del fallo y queda
   pendiente)**: `config.py` trae `UPDATE_VERSION_URL` con un id de
   marcador literal, `1BpcVersionJsonPendiente` — el canal de
   actualización apunta a un archivo que no existe. Requiere publicar un
   `version-pc.json` real en Drive y poner su id; no se inventó ninguno.

## Correcciones (commit local 94c7abf / remoto 7506c692)

- `modules/__init__.py`: registro **explícito** (`PAQUETES_MODULOS =
  panel, security, system, net`) con import por nombre — funciona igual
  en fuente y en congelado. Los fallos de importación se anotan en
  `errores_descubrimiento()`, con traceback en `errores-modulos.log`
  (carpeta de datos) y el resto de módulos sigue cargando.
- `ui/main_window.py`: si algún módulo falla o no carga ninguno, la barra
  lateral muestra un aviso rojo visible y, sin módulos, una página que
  explica el fallo en vez del área en blanco.
- `packaging/antivirus-hogar-pc.spec`: la raíz se mete en `sys.path`
  antes de `collect_submodules` y el .spec **aborta la compilación** si
  falta alguno de los 4 registros en los hiddenimports.
- `.github/workflows/build-windows.yml`: nuevo paso que verifica con
  `pyi-archive_viewer` que los 4 `modules.*.registro` van dentro del
  ejecutable; si falta uno, el run falla.
- `tests/test_registro_congelado.py` (3 tests nuevos): simula el entorno
  congelado (`iter_modules` vacío y `__path__` inexistente) y exige los
  9 módulos; y verifica que un paquete roto quede registrado como error.
  Con el código v1, el primer test devuelve 0 módulos (falla); con la
  corrección pasa.
- Versión 1.0.1 en `__init__.py`, `config.py`, `instalador.iss`,
  `LEEME.md` y `Construir-en-Windows.bat`.

## Verificación

- Suite completa: **60/60** (57 anteriores + 3 nuevos).
- Sonda congelada con la corrección: `HIDDENIMPORTS: 58`,
  `N_MODULOS: 9`, `ERRORES: []` (antes: 0 módulos).
- GitHub Actions run **45408841604**: `completed / success` (incluye el
  nuevo paso de verificación del ejecutable).
  https://github.com/ERISLANDY2026/antivirus-hogar-pc/actions/runs/45408841604
- Artefacto `Instalador-AntivirusHogarPC` (id 14927541051, zip
  39,154,990 B) → `Instalador-AntivirusHogarPC-1.0.1.exe`:
  **39,696,851 bytes** (v1: 36,670,590 — la diferencia es consistente con
  los módulos ahora sí empaquetados), PE32 GUI Windows, Inno Setup 6.7.0,
  MD5 `646b97b2bbe076dfeab3fdc5158b286f`.
- Drive: `AntivirusHogarPC-Instalador-v1.0.1.zip` (39,142,503 B, MD5
  `6e0107ddc8585a4cf3d287c37e51b944`, verificado contra el local) en la
  carpeta «Antivirus Hogar PC», sin tocar el zip v1:
  https://drive.google.com/file/d/15nrtsXRuBLoUo_sH5SeFlz7yN2xOucfM/view?usp=drivesdk

## Pendiente honesto

- El instalador v1.0.1 aún no se ha ejecutado en el Windows real de
  Erislandy; la verificación de que los módulos van dentro es automática
  (paso del workflow + sonda congelada), pero la prueba final en su PC
  queda de su lado, como en la v1.
- El canal de actualización (punto 6) sigue con el marcador pendiente.
