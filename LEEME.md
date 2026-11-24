# Antivirus Hogar PC

Compañero doméstico de **Microsoft Defender** para Windows 10/11, en español
y gratuito. Es la versión de PC del Antivirus Hogar de Android (v6), con las
mismas reglas: Defender queda como protección en tiempo real y esta app
aporta lo demás. **Ante una amenaza decide siempre el usuario**
(cuarentena / eliminar / escanear con Defender): la app nunca actúa sola.

Qué trae (por olas):

- **Inicio** — panel de salud con puntuación explicada (Defender, firewall,
  Windows, protección de carpetas, hallazgos, disco y arranque).
- **Escanear** — escaneo bajo demanda por huellas (SHA-256/MD5) con caché
  incremental, botón «Escanear con Defender» y «Analizar ESTE archivo».
- **Protección** — protección al instalar (vigilancia en modo usuario) y
  bloqueador por archivo hosts gestionado, con respaldo y pausa.
- **Drivers** — contraste contra la cadena oficial (Windows Update /
  Microsoft Update Catalog → fabricantes de chips → marca de la PC), con
  punto de restauración antes de instalar. Sin bases de terceros.
- **Discos** — salud SMART honesta («no se puede leer» cuando no hay datos,
  nunca «sano» sin datos) y optimización con la herramienta de Windows
  (TRIM en SSD, desfragmentar en HDD).
- **Limpieza** — temporales, papelera y arranque reversible, con informe
  previo. **Sin limpiador de registro** (en su lugar: respaldo del registro
  y punto de restauración).
- **Actualizaciones** — actualizaciones de Windows pendientes y programas
  desactualizados vía `winget`.
- **Red y VPN** — informe Wi-Fi y lista de servidores VPN Gate: la app
  genera el perfil `.ovpn` y lo delega en SoftEther VPN Client u OpenVPN
  Connect (no crea el túnel).
- **Informes** — informe de privacidad/persistencia (programas instalados,
  arranque, tareas y servicios de terceros).
- Escaneo **semanal programado** que solo avisa si hay hallazgos, y canal de
  actualización propio con diálogo «Qué trae esta actualización».

## Cómo se compila el .exe

PyInstaller **no compila cruzado** desde Linux: el instalador se produce en
Windows, por una de estas dos vías (ambas usan los mismos
`packaging/antivirus-hogar-pc.spec` y `packaging/instalador.iss`):

### Vía 1 — En la PC (un doble clic)

1. Instala Python 3.11+ desde python.org (marcando «Add python.exe to
   PATH») e Inno Setup 6 desde jrsoftware.org (gratis).
2. Doble clic en **`Construir-en-Windows.bat`**: instala las dependencias,
   compila con PyInstaller y crea el instalador.
3. Resultado: `dist-instalador\Instalador-AntivirusHogarPC-1.0.2.exe`.

### Vía 2 — En la nube (GitHub Actions)

El workflow `.github/workflows/build-windows.yml` hace lo mismo en un
runner `windows-latest` y deja el instalador como artefacto descargable.
**Estado honesto: el workflow está listo pero el proyecto aún no está
subido a GitHub** (no hay cuenta del usuario vinculada), así que hoy la vía
que funciona es la 1. Subir el repositorio a GitHub activa la vía 2 sin
tocar nada más.

## Aviso de SmartScreen (sin firma)

El instalador **no lleva firma digital** (una firma comercial cuesta dinero
cada año). La primera vez que se abra, Windows mostrará la pantalla azul
«Windows protegió su PC». Es el comportamiento normal con software sin
firmar, no un error: pulsa **«Más información» → «Ejecutar de todas
formas»**. La reputación de SmartScreen para archivos sin firmar empieza
de cero en cada versión nueva.

## Límites honestos

- El escaneo por huellas solo detecta malware **conocido y sin modificar**;
  la base de fábrica trae la firma del archivo de prueba EICAR y se amplía
  con las actualizaciones de amenazas (abuse.ch: MalwareBazaar exige una
  Auth-Key gratuita que crea el usuario; URLhaus/OpenPhish son feeds
  públicos). El motor completo sigue siendo Microsoft Defender.
- La **protección al instalar** es vigilancia en modo usuario (Descargas,
  temporales y programas recién instalados), no un filtro en tiempo real:
  sin driver de kernel no puede serlo, y no se promete lo contrario.
- El **bloqueador** trabaja por dominio (archivo hosts), no por URL, y sin
  certificado local. La base por defecto es la semilla de 19.563 dominios:
  Windows se degrada con decenas de miles de líneas de hosts; la base
  fusionada de 100.776 dominios queda como opción con aviso.
- La **salud SMART** de discos tras puentes USB o RAID a menudo no se puede
  leer: la app lo dice («no se puede leer») en vez de inventar un «sano».
- El instalador de drivers solo usa **fuentes oficiales** y drivers
  firmados; el último paso en páginas de fabricantes lo puede terminar el
  instalador oficial de la marca.
- La **VPN** es delegada: los servidores de VPN Gate son de voluntarios y
  el operador puede registrar la conexión; no usar para banca ni para
  anonimato.
- El canal de actualización propio (version.json en Drive) usa la misma
  mecánica que la app de Android; la URL del canal se configura en Ajustes.

## Pruebas

La lógica pura (huellas, caché, hosts, VPN Gate, drivers, salud, registro
de módulos) tiene suite automática en `tests/`, sin interfaz:

```
pip install pytest
python -m pytest tests/ -q
```

## Desarrollo

Contratos congelados entre módulos: `CONTRATOS.md` y
`antivirus_hogar_pc/contracts.py` (versión `1.0-ola0`). Nadie cambia un
contrato sin pasar por el integrador.
