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
   SHA-256 en el registro de la corrida.
3. Lo extrae (7-Zip; segundo pase sobre el .cab interior) y copia
   la carpeta que contiene `vpnclient_x64.exe`, `vpncmd_x64.exe` y
   `hamcore.se2` a `packaging\softether\client\`, dejando dentro
   `SOFTETHER-CLIENT.txt` con la versión y la huella.
4. Si algo falta, la compilación **falla**: la 1.0.7 no sale sin
   SoftEther.

Para una compilación local con SoftEther: repetir los pasos 1–3 a
mano y después compilar el instalador como siempre. Sin la carpeta
`client\`, el .iss simplemente no lo incluye (la app lo detecta y
usa la vía del perfil .ovpn).
