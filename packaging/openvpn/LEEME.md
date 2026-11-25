# OpenVPN INCORPORADO (v1.0.10) — qué es esta carpeta

Desde la 1.0.10 el motor VPN de la app es **OpenVPN Community**
(SoftEther quedó descartado: Windows bloquea su controlador de
tarjeta virtual de 2018 al instalar el dispositivo, «Error 31»).

Aquí viaja el **instalador oficial de OpenVPN para Windows**
(MSI amd64), tal como lo publica el proyecto:

- **Archivo:** `OpenVPN-2.7.9-I002-amd64.msi`
- **Origen oficial:** https://swupdate.openvpn.org/community/releases/OpenVPN-2.7.9-I002-amd64.msi
  (es el instalador que enlaza la página oficial
  https://openvpn.net/community-downloads/, verificado en vivo el
  2026-11-25: «Supported on all Windows platforms from Windows 10
  onward»).
- **Tamaño:** 5.939.200 bytes (Content-Length del servidor oficial).
- **SHA-256:** `d050efadc6cabc4e304eb810dd7fedfc54b859d34730ab9cdcb22d61eb86ab7a`

La compilación en la nube (workflow `build-windows.yml`) lo
descarga de esa URL en cada corrida, EXIGE que tamaño y huella
coincidan con los fijados arriba, escribe el marcador
`OPENVPN-INSTALADOR.txt` con el origen y FALLA si algo no cuadra:
la 1.0.10 no sale sin su OpenVPN verificado. Una compilación local
sin el paquete produce la app sin el instalador conservado (el
instalador de la app lo detecta y lo anota en su registro).

Qué hace con él el instalador de la app (`packaging/instalador.iss`):

1. Lo deja en `{app}\openvpn\` — es el **instalador interno
   conservado** que usa el auto-actualizador de la app
   (`winapi/openvpn_update.py`) como versión conocida buena y
   referencia de la instalada.
2. Si el equipo no tiene ya OpenVPN, lo **instala en silencio**
   (`msiexec /i … /quiet /norestart`): deja su servicio
   interactivo y su tarjeta virtual TAP-Windows, con los
   controladores firmados que Windows acepta. El resultado queda
   en `{app}\openvpn-instalacion.txt`.
3. Al actualizar desde versiones con SoftEther (≤1.0.9), retira
   sus restos: el servicio SEVPNCLIENT **solo si lo registró esta
   app** (marca en el registro), la carpeta `{app}\softether`, su
   registro de instalación y el paquete de su controlador en el
   DriverStore. Si el usuario tenía SU propio SoftEther, no se
   toca su servicio.

La app maneja OpenVPN en segundo plano por su interfaz de gestión
local (ver `winapi/vpn_win.py`): el usuario no ve OpenVPN por
ningún lado; es el motor interno de la pantalla «Red y VPN».
