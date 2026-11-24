"""Notas de versión de la app (v1.0.5).

Estructura de datos para la pantalla «Versión de la app» del panel
izquierdo: cada versión añade su entrada AQUÍ (la más reciente
primero) y la pantalla la enseña sin tocar la interfaz. Incluye el
resumen de qué es y qué hace la aplicación.
"""

RESUMEN_APP = (
    "Antivirus Hogar PC es el compañero de Microsoft Defender para "
    "Windows 10/11: Defender sigue siendo el escudo en vivo y esta "
    "app aporta lo demás — escaneo de archivos con base de firmas "
    "propia, protección e informes de privacidad, actualización de "
    "drivers solo por fuentes oficiales, limpieza y tune-up, salud "
    "de discos (SMART), copias del estado de la red, medidor de "
    "velocidad y VPN gratuita vía VPN Gate. Es gratuita, para la "
    "familia, y ante cualquier amenaza decides TÚ: la app nunca "
    "borra ni desinstala nada por su cuenta."
)

QUE_HACE = [
    "Escanear: análisis rápido o completo con firmas de malware y phishing que se actualizan por varias fuentes.",
    "Proteger: vigilancia de instalaciones, bloqueo de dominios peligrosos e informes de privacidad por app.",
    "Drivers: confirmación contra el Catálogo de Microsoft, Windows Update y el almacén local; instalación solo oficial, con punto de restauración antes.",
    "Discos y limpieza: salud SMART, optimización de volúmenes en segundo plano y limpieza de temporales y papelera.",
    "Red y VPN: datos de tu Wi-Fi con detalle, velocidad real de internet en vivo y VPN gratuita de VPN Gate.",
    "Actualizarse sola: el botón de actualización baja las versiones nuevas por un canal verificado (SHA-256).",
]

NOTAS_VERSION: list[dict] = [
    {
        "version": "1.0.6",
        "fecha": "24/11/2026",
        "novedades": [
            "Bloqueador a prueba de fallos: quitar o restaurar el bloqueo ya no puede fallar porque el archivo hosts esté en uso — la app reintenta y, si sigue ocupado, deja el cambio programado para aplicarse al reiniciar, avisándote claro.",
            "Al activar el bloqueo, la app vacía la caché DNS y comprueba que tu navegación sigue viva; si algo fallara, restaura sola tu archivo hosts anterior. Tu internet no se toca.",
            "Autorreparación al abrir: si la app detecta su propio bloque dañado en el archivo hosts o una restauración pendiente, lo deja limpio ella misma y lo anota en el registro de actividad.",
            "Los errores del bloqueador se leen en español claro; el detalle técnico queda solo en el registro de actividad, no en pantalla.",
        ],
    },
    {
        "version": "1.0.5",
        "fecha": "24/11/2026",
        "novedades": [
            "Iconos del panel izquierdo nuevos: uno por pestaña, más grandes, en colores 3D modernos y animados (la de Actualizaciones gira al comprobar).",
            "Nuevo icono de la app: el espartano cyborg dentro del escudo, en el ejecutable, el instalador y los accesos directos.",
            "Tema de cristal en toda la app: paneles semitransparentes con bordes luminosos, adiós al azul oscuro triste.",
            "Radar de Inicio militar: verde visión nocturna y las bolitas ahora son amenazas (virus, bichitos y archivos rotos) que se encienden cuando el haz las toca.",
            "Drivers: confirmación mucho más rápida — primero el Catálogo de Microsoft por dispositivo, luego Windows Update con límite corto y reintento, y el almacén local; las causas se leen en español breve, sin volcados técnicos en pantalla.",
            "Optimizar volúmenes: trabaja oculto en segundo plano y la barra RGB de la app enseña el progreso real de Windows, fase a fase.",
            "Velocidad de internet de verdad: mide descarga y subida en vivo contra Cloudflare, con los números en colores mientras mide.",
            "Wi-Fi interactivo: ves el nombre de tu red y, al tocarla, señal, banda, canal, frecuencia, velocidad de enlace, seguridad, IP, puerta de enlace y DNS.",
            "VPN Gate corregido de raíz: la lista de respaldo puebla los países al instante y la lista en vivo la reemplaza al llegar; barra de progreso durante la actualización y aviso final con servidores, países y fuente.",
            "Canal de actualizaciones que se repara solo: si un ajuste antiguo apuntaba a un archivo equivocado, la app lo corrige al abrirse.",
            "Descarga de actualizaciones resistente: reintentos automáticos y reanudación desde donde se cortó, con el SHA-256 de siempre.",
            "Nueva pantalla «Versión de la app» (esta): versión actual, sus novedades y el historial reciente.",
            "Arranque con Windows: la app abre minimizada y corre sola su rutina de arranque (escaneo rápido, drivers, limpieza segura y revisión de inicio), con el resumen en Inicio. Se apaga en Ajustes.",
            "«Programador de tareas»: programa escaneos y mantenimientos (drivers, limpieza, firmas, actualizaciones) con frecuencia, día y hora; los ejecuta Windows aunque la app esté cerrada.",
        ],
    },
    {
        "version": "1.0.4",
        "fecha": "24/11/2026",
        "novedades": [
            "Corregido el fallo del «Escaneo rápido» (la caché se usaba desde otro hilo y el escaneo moría): conexión por hilo y errores en español claro.",
        ],
    },
    {
        "version": "1.0.3",
        "fecha": "24/11/2026",
        "novedades": [
            "Firmas: nueva fuente sin clave (135.195 huellas y 485.045 dominios reales); abuse.ch sin clave pasa a «opcional».",
            "Escaneo rápido con progreso de verdad desde el primer archivo.",
            "Efectos y barras con porcentaje en todas las páginas, no solo en Inicio.",
            "Drivers: la consulta a Windows Update enseña su resultado real («Al día» / «Hay uno más nuevo») y la causa si falla.",
            "VPN: cadena de descarga con reintentos y lista semilla de 35 servidores reales (9 países) incluida en la app.",
        ],
    },
    {
        "version": "1.0.2",
        "fecha": "24/11/2026",
        "novedades": [
            "Interfaz con color: botones cromados y con pulso, barras de progreso RGB con porcentaje en todo, fondo radar animado en Inicio.",
            "Medidores de CPU/RAM/disco, registro de actividad, gestor de inicio, mapa de disco y velocidad de internet + VPN.",
            "Corregidos: buscar actualizaciones, VPN sin países ni interruptor, botón de Wi-Fi mudo, escaneo de drivers y firmas con varios respaldos.",
        ],
    },
]


def notas_de(version: str) -> dict | None:
    for entrada in NOTAS_VERSION:
        if entrada.get("version") == version:
            return entrada
    return None
