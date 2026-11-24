# Antivirus Hogar PC — Subida a GitHub, compilación y entrega (2026-11-24)

## Credencial
- Conector custom.github verificado con llamada real: `get-user` → 200, login **ERISLANDY2026** (id 360665495). `get-repo` → 200, `default_branch: main`.
- El primer PAT guardado había dado 401; el vigente es el clásico (repo+workflow) guardado por la vía segura tras la reconexión. El valor no se guarda en ningún archivo.

## Subida del código (Git Data API)
- Repo destino: **ERISLANDY2026/antivirus-hogar-pc** (estaba vacío, contents 404).
- Nota técnica: un repo vacío rechaza blobs de la Git Data API con 409 «Git Repository is empty». Se creó primero un commit semilla con la Contents API (`.github/workflows/build-windows.yml`, commit `2a3023748934b188ba92e1d229a67964e1ab0d2f`) y encima el commit completo.
- Blobs: **82/82 archivos** tracked del commit local 91c3c6f; cada SHA devuelto por la API coincidió con el SHA local del objeto.
- Commit final: **`2c96970e1f27dd712c0d9819e12c34d976ec7dff`** en `refs/heads/main`.
- Tree remoto: `5e37b8e75ae6262abf15096db0d419d56ced4df3` — **idéntico al tree del commit local** (`git rev-parse HEAD^{tree}`), prueba de que el contenido subido es byte a byte el verificado (suite 57/57).

## Compilación (GitHub Actions)
- Workflow `build-windows.yml` («Construir instalador Windows») disparado por `workflow_dispatch` → 204.
- Run **45405966752**: estado `completed`, conclusión **`success`**.
- URL: https://github.com/ERISLANDY2026/antivirus-hogar-pc/actions/runs/45405966752

## Artefacto e instalador (verificados)
- Artefacto `Instalador-AntivirusHogarPC` (id 14925154017): zip de **36,127,779 bytes** (coincide con el tamaño reportado por GitHub).
- Dentro: **`Instalador-AntivirusHogarPC-1.0.0.exe` — 36,670,590 bytes**, cabecera MZ, `file`: PE32 executable (GUI) Intel 80386, for MS Windows; cadenas internas «Inno Setup Setup Data (6.7.0)» — instalador Inno Setup real.
- MD5 del .exe: `3f03f90a2cf9a613eac1c0bf2acf18d7`.
- Copia local: `~/workspace/antivirus-hogar-pc/build-nube/extraido/Instalador-AntivirusHogarPC-1.0.0.exe`.
- Pendiente honesto: el instalador no se ha ejecutado en un Windows 10 real; la verificación es de formato/origen (compilado por el runner Windows del propio workflow, con las pruebas del proyecto en verde dentro del run).

## Entrega en Drive
- Paquete final: **`AntivirusHogarPC-Instalador-v1.zip`** (36,121,389 bytes) con el instalador .exe y `LEEME.md`. MD5: `09c02a996a40205273584c665a7abcc6`.
- Subido a la carpeta **«Antivirus Hogar PC»** de Google Drive y verificado con `files get`: tamaño 36,121,389 y MD5 idéntico al local.
- Enlace: https://drive.google.com/file/d/1ChNn0DiIj2E_9ZsePoifztBAx_Tmwzf1/view?usp=drivesdk
- En esa misma carpeta ya estaba el zip del código fuente (`antivirus-hogar-pc-v1.zip`, 1,103,299 bytes); el paquete nuevo no lo reemplaza.
- El archivo no se trajo por el chat, como ordenó Erislandy. Su puerta final sigue vigente: él decide si se pone en uso.
