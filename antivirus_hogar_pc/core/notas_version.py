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
        "version": "1.0.8",
        "fecha": "25/11/2026",
        "novedades": [
            "VPN Gate reparada de raíz: la tarjeta virtual de red de SoftEther ahora se crea DURANTE la instalación (con permisos de administrador y a la vista, que es como Windows lo exige), no al darle a «Conectar» sin permisos y en oculto, que era por lo que fallaba con todos los servidores. El instalador deja el resultado en «softether-nic-instalacion.txt», junto a la app, por si hay que revisarlo.",
            "Si la tarjeta faltara al conectar, la app la crea pidiendo permiso de administrador y a la vista, solo para ese paso.",
            "Cada intento de conexión de VPN Gate queda anotado en el registro de actividad con su mensaje y el detalle técnico real de SoftEther (antes ese detalle se perdía).",
            "Globo terráqueo girando en la esquina de la tabla de servidores de VPN Gate (una vuelta por segundo), gobernado por el mismo interruptor de animaciones de Ajustes que el resto de la app.",
        ],
    },
    {
        "version": "1.0.7",
        "fecha": "24/11/2026",
        "novedades": [
            "VPN Gate con SoftEther INCLUIDO: el instalador de la app instala también SoftEther VPN Client (el cliente recomendado por VPN Gate), ya programado para trabajar con la app y en segundo plano. No tienes que instalar nada más ni abrir ningún otro programa.",
            "Conectar de verdad desde la app: en «Red y VPN», el botón «Conectar» de cada servidor crea la conexión y la levanta desde la propia app, sin ventanas ajenas; cuando el túnel está arriba, el botón se pone VERDE y dice «Conectado». «Desconectar VPN» lo baja desde aquí mismo.",
            "Si SoftEther no estuviera en el equipo, se mantiene la vía de siempre: la app guarda el perfil .ovpn y te dice cómo abrirlo con tu cliente VPN.",
            "Discos: «Optimizar volúmenes» ahora confirma el resultado de verdad — además del aviso directo de Windows, la app comprueba el registro de eventos de Windows y la salida completa de la optimización; cuando consta que terminó, dice «Optimización finalizada», y si algo falló enseña la causa verdadera en vez de «causa desconocida».",
            "Actualizaciones: la carpeta donde se descargan las versiones nuevas se crea sola si no existe (en una PC faltaba y el botón de actualizar fallaba por eso; ya no puede volver a pasar).",
            "Protección contra falsos positivos de Defender: el instalador pide a Microsoft Defender una exclusión SOLO para las carpetas propias de la app y lo verifica leyéndola de vuelta; si Windows no lo permite, la app te avisa al abrir con el paso manual. Al arrancar, la app comprueba además que sus archivos siguen íntegros y lo anota en el registro.",
            "Icono junto al reloj: la app vive ahora en el área de notificación — doble clic para abrirla, menú con «Abrir», «Escaneo rápido» y «Salir»; al cerrar la ventana la app se queda ahí trabajando, y te avisa con un globito cuando la rutina de arranque termina o un escaneo encuentra algo.",
            "Icono del espartano nuevo: sin fondo blanco y ocupando todo el cuadro, más grande y limpio en el escritorio, la barra de tareas y la bandeja.",
            "SoftEther siempre al día: cada 3 días la app comprueba en segundo plano, contra las fuentes oficiales del proyecto, si hay una versión más nueva de SoftEther; si la hay, la descarga, la verifica y la aplica sin cortar nunca una conexión VPN activa, y después se re-sincroniza sola con la versión nueva (revisa la conexión de VPN Gate y la recrea si la actualización la hubiera borrado).",
        ],
    },
    {
        "version": "1.0.6",
        "fecha": "24/11/2026",
        "novedades": [
            "Bloqueador a prueba de fallos: quitar o restaurar el bloqueo ya no puede fallar porque el archivo hosts esté en uso — la app reintenta y, si sigue ocupado, deja el cambio programado para aplicarse al reiniciar, avisándote claro.",
            "Al activar el bloqueo, la app vacía la caché DNS y comprueba que tu navegación sigue viva; si algo fallara, restaura sola tu archivo hosts anterior. Tu internet no se toca.",
            "Autorreparación al abrir: si la app detecta su propio bloque dañado en el archivo hosts o una restauración pendiente, lo deja limpio ella misma y lo anota en el registro de actividad.",
            "Red y VPN reparada de raíz: los botones de Wi-Fi, «Medir velocidad» y «Actualizar lista de servidores» vuelven a responder al instante, y el desplegable de países de VPN Gate nace poblado con la lista de respaldo, sin esperar a la red.",
            "Programador de tareas reparado: «Guardar y aplicar» ahora sí guarda, crea la tarea de Windows y la «Próxima ejecución» se actualiza en las seis programaciones; si Windows rechaza una tarea, verás la causa en español (el detalle técnico queda en el registro).",
            "Discos: «Optimizar volúmenes» ya no termina en «causa desconocida» — enseña la causa real de Windows y guarda su salida completa en el registro de actividad; y el progreso avanza de verdad, registro a registro, en vez de saltar al 100 %.",
            "Iconos del panel con 3D de verdad (volumen, canto y brillo de cristal) y ANIMACIÓN CONTINUA y visible en todos: flotan suave y un brillo los cruza cada pocos segundos; la pestaña activa pulsa y la de Actualizaciones gira.",
            "Acabado moderno en todas las secciones: tarjetas con efecto de vidrio y bordes con un recorrido de color animado. Todo el movimiento cuelga de un solo temporizador compartido (no gasta de más) y lo gobierna el interruptor de animaciones de Ajustes.",
            "El icono del espartano cyborg ahora SÍ se ve: la app lo fija como icono de su ventana y de la barra de tareas, y el instalador recrea los accesos directos apuntando al icono y refresca la caché de iconos de Windows al actualizar.",
            "El radar de Inicio, rediseñado como pediste: pantalla futurista premium con barrido verde eléctrico que cubre la imagen entera hasta las esquinas y estela de fósforo que se apaga poco a poco, ondas de escaneo que se expanden, efecto tridimensional de cúpula de cristal y ambiente eléctrico sutil. Y los bichitos ahora MUEREN cuando el haz los toca (destello y desvanecimiento) y renacen poco después en otro punto, en un ciclo continuo.",
            "Los errores se leen en español claro; el detalle técnico queda solo en el registro de actividad, no en pantalla.",
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
