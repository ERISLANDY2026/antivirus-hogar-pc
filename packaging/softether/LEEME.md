# SoftEther VPN Client incorporado (v1.0.7)

La app lleva SoftEther VPN Client **dentro de su propio instalador**
para que el usuario no instale nada más: al instalar Antivirus Hogar
PC se copian los archivos del cliente a `{app}\softether`, el
instalador registra su servicio de Windows (`SEVPNCLIENT`) si el
equipo no tiene uno, y la app lo maneja por `vpncmd` en segundo
plano (crear la conexión de VPN Gate, conectar, desconectar).

## El binario

- **Producto:** SoftEther VPN Client, **4.44 Build 9807 RTM
  (2025-04-16)**, Windows x86_x64 — la versión estable vigente.
- **Origen (único):** sitio oficial de descargas del proyecto:
  `https://www.softether-download.com/files/softether/v4.44-9807-rtm-2025.04.16-tree/Windows/SoftEther_VPN_Client/softether-vpnclient-v4.44-9807-rtm-2025.04.16-windows-x86_x64-intel.exe`
- **Tamaño del instalador oficial:** 56.249.368 bytes (listado
  oficial del directorio). Su SHA-256 lo calcula y lo deja en el
  registro la compilación en la nube en cada corrida.
- **Licencia:** SoftEther VPN es software libre (Apache License
  2.0); la redistribución de sus archivos es la vía que usa su
  comunidad para instalaciones desatendidas.

## Por qué archivos copiados y no su instalador en silencio

El instalador oficial de SoftEther es un instalador propio
(`vpnsetup`) **sin modo silencioso documentado ni fiable** (sin
`/S`, `/VERYSILENT` ni equivalente oficial; confirmado en su foro
oficial). La vía soportada por la práctica de su comunidad es:
copiar la carpeta del cliente y registrar el servicio
(`sc create SEVPNCLIENT binPath="…\vpnclient_x64.exe /service"`).
El driver de la tarjeta virtual lo instala el propio cliente la
primera vez que la app ejecuta `NicCreate` por vpncmd, dentro de la
sesión del usuario (desde un servicio en contexto SYSTEM falla:
por eso lo crea la app y no el instalador).

## Cómo llega el paquete a `client\`

La carpeta `client\` **no se guarda en el repositorio** (son
decenas de MB de binario). La compilación en la nube
(`.github/workflows/build-windows.yml`) en cada corrida:

1. Descarga el instalador de la URL oficial de arriba.
2. Verifica que pesa exactamente 56.249.368 bytes y anota su
   SHA-256 en el registro de la corrida (la del 2026-11-24:
   `AB006331F1F646BC319585088239D55BC54ECDE5C269009268E9598307DA7A44`).
3. Lo abre con 7-Zip: el instalador es un PE y su carga va como
   **recursos** en `.rsrc\0\DATAFILE\` con los nombres internos del
   fabricante. Copia a `packaging\softether\client\` las cuatro
   piezas x64 con el nombre que llevan en una instalación real:
   `VPNCLIENT_X64.EXE` → `vpnclient_x64.exe`,
   `VPNCMD_X64.EXE` → `vpncmd_x64.exe`,
   `VPNCMGR_X64.EXE` → `vpncmgr_x64.exe`,
   `RAW_HAMCORE.SE2` → `hamcore.se2`. OJO: los recursos `.exe` van
   **comprimidos** con el formato del fabricante (prefijo de 4 bytes
   + flujo zlib); la compilación los descomprime y valida el PE
   resultante por su estructura (firma «MZ», Machine 0x8664 y
   secciones dentro del archivo; el descomprimido conserva incluso
   su firma digital como overlay final). El `hamcore` sí va crudo
   — de ahí el `RAW_` — y lleva su firma real «HamCore». Deja
   dentro `SOFTETHER-CLIENT.txt` con la versión y la huella, y hace
   una prueba de humo: en la corrida 45502795985 el `vpncmd`
   incorporado arrancó en el runner, imprimió su banner oficial
   «Version 4.44 Build 9807» y solo falló al conectar (no hay
   servicio de cliente en el runner: es el resultado correcto).
4. Si algo falta, la compilación **falla**: la 1.0.7 no sale sin
   SoftEther.

Para una compilación local con SoftEther: repetir los pasos 1–3 a
mano y después compilar el instalador como siempre. Sin la carpeta
`client\`, el .iss simplemente no lo incluye (la app lo detecta y
usa la vía del perfil .ovpn).
