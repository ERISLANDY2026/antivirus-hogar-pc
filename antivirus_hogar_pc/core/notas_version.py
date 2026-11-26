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
    "Red y VPN: datos de tu Wi-Fi con detalle, velocidad real de internet en vivo y VPN gratuita (VPN Gate y VPNBook) con autoanálisis de servidores.",
    "Actualizarse sola: el botón de actualización baja las versiones nuevas por un canal verificado (SHA-256).",
]

NOTAS_VERSION: list[dict] = [
    {
        "version": "1.0.18",
        "fecha": "26/11/2026",
        "novedades": [
            "CERO AVISOS DE ADMINISTRADOR AL ABRIR LA APP: todo el trabajo de la VPN en segundo plano va ahora SOLO por el servicio interactivo de OpenVPN, que no pide permisos — y el instalador deja tu usuario verificado dentro del grupo «OpenVPN Administrators» para que esa vía funcione en tu sesión. Si el servicio no estuviera disponible, la app espera en silencio: nunca más los avisos de «OpenVPN Daemon» en cadena al arrancar.",
            "LA VPN SOLO SE CONECTA CUANDO TÚ PULSAS «CONECTAR»: la app nunca abre un túnel por su cuenta ni cambia tu IP sin tu orden. La reconexión automática se queda, pero solo actúa sobre un túnel que TÚ abriste en esa sesión y se cayó solo.",
            "VERIFICACIÓN DE SERVIDORES AL ARRANCAR: al abrir la app, la tabla de «Red y VPN» comprueba sola TODOS los servidores con la prueba real —sin abrir ningún túnel ni tocar tu tráfico— y la columna de verificación se va llenando en vivo con su sello y su hora. Lo no comprobado dice «Sin verificar», sin inventar veredictos.",
            "ACTUALIZAR CON UN SOLO CLIC: la descarga de cada actualización lleva su propia identidad (versión y huella), nunca se mezcla con restos de otra descarga, y si la huella no cuadrara, la app vuelve a descargar limpia dentro del mismo clic. Un clic termina en instalación verificada o en un error real de red: se acabó el «falla por huella, pulsa otra vez».",
            "OPTIMIZAR VOLÚMENES CON VEREDICTO CONFIRMADO: el resultado de defrag.exe llega por un canal atómico y verificable, con el registro de eventos de Windows como testigo independiente, y si la evidencia tardara, la app la recaptura dentro del mismo clic. El mensaje «terminó sin dejar el código de salida» ha desaparecido: el veredicto sale solo con evidencia, y si algo falla, con su causa.",
            "TU ESPARTANO, MÁS NÍTIDO Y TAMBIÉN EN EL INSTALADOR: la animación de Inicio se re-hizo desde su video original con más resolución (640 de ancho frente a 440) y el doble de fluidez (24 cuadros por segundo frente a 12), con los bordes de la llave de color afinados: se acabó el aspecto difuso y ruidoso. Y el mismo espartano, fijo y a cuerpo completo, te acompaña de pie junto a la barra mientras el instalador copia los archivos.",
            "PANEL IZQUIERDO REORDENADO: el selector de idioma vive ahora arriba, justo debajo del encabezado —que luce el icono de la aplicación, el escudo con tu espartano dorado— y al final del panel tienes la nueva entrada «Historial de la aplicación».",
            "«VERSIÓN DE LA APP» LIMPIA: esa página enseña solo tu versión actual —qué es la app y qué trae de nuevo—. El historial completo de versiones, desde el desarrollo hasta hoy, se mudó a su propia pantalla: «Historial de la aplicación», la última entrada del panel izquierdo.",
        ],
    },
    {
        "version": "1.0.17",
        "fecha": "26/11/2026",
        "novedades": [
            "TU ESPARTANO YA VIVE EN INICIO: el espartano que elegiste y viste animado antes de aprobarlo está de pie en la parte izquierda del área de barrido del radar —su fondo es esa zona del radar, tal como pediste—, con su escudo «GUERRA», su electricidad lenta y su ciclo natural de guardia: alerta respirando, vigilancia escaneando, en guardia y de vuelta a la alerta, en bucle continuo. El radar conserva intacto el diseño que fijaste: no se ha tocado ni un píxel de su dibujo, y el espartano nunca tapa el anillo de salud ni la cifra de la esquina.",
            "SE MUEVE CON LAS REGLAS DE SIEMPRE: la animación del espartano obedece las mismas puertas que el resto de la interfaz —se pausa con la ventana oculta o minimizada, con tu interruptor de animaciones de Ajustes y con el ahorro por batería— y mientras está en pausa enseña su foto fija, el mismo espartano quieto. Nada nuevo que configurar: si ya tenías las animaciones apagadas, él también está quieto.",
        ],
    },
    {
        "version": "1.0.16",
        "fecha": "25/11/2026",
        "novedades": [
            "«PUESTA A PUNTO» DE UN CLIC EN INICIO: el mantenimiento completo en orden —escaneo rápido, limpieza segura, optimizar volúmenes y revisión de drivers— con una sola barra de progreso que nombra la etapa en curso, botón de cancelar que deja lo hecho hecho (y lo dice) y un veredicto final único con el detalle de cada etapa. La revisión de drivers solo revisa y cuenta: instalar sigue siendo paso a paso con tu confirmación en su pantalla, como siempre.",
            "LA VPN SE RECONECTA SOLA SI SE CAE: si un túnel establecido se corta sin que toques nada, la app lo detecta y reconecta —primero al mismo servidor y luego, si hace falta, al siguiente recomendado con el salto automático de siempre—, avisando por la bandeja de la caída y del resultado, con esperas crecientes y un tope de intentos. Si desconectas A MANO, no reconecta nunca. El interruptor «Reconectar la VPN automáticamente» vive en Ajustes y viene activado.",
            "TARJETA «PENDIENTES» EN INICIO: debajo del anillo de salud, la lista de lo que necesita atención con su botón para ir directo a su pantalla —drivers desactualizados según la última revisión, volúmenes sin optimizar desde hace un mes, el último escaneo si ya pasó una semana (o si nunca se hizo), actualizaciones de Windows pendientes y servidores VPN sin verificar—. Solo sale lo que sale de datos reales de tu equipo; si no hay nada, dice «Todo al día».",
            "LA SALUD DEL DISCO YA TIENE MEMORIA: cada lectura SMART queda guardada en un historial y el Panel enseña su TENDENCIA —«estable» o «BAJANDO» respecto a hace unos 30 días, que es el aviso que importa en un SSD—. Sin lecturas de varios días lo dice tal cual: «historial en construcción», sin inventar tendencias. Si la salud baja, el aviso aparece también en la tarjeta de Pendientes.",
            "LOS ICONOS 3D TAMBIÉN DENTRO DE LAS PÁGINAS: las filas de estado (Defender, firewall, actualizaciones de Windows, disco…) ya usan el mismo acabado gráfico de tu foto —con la llama del firewall, la carpeta de la protección contra ransomware, la alerta y el wifi generados con el mismo procedimiento— animados con el mismo reloj y las mismas puertas de siempre. El dibujo anterior queda solo de respaldo.",
            "AHORRO POR BATERÍA: si el equipo va sin cargador, las animaciones se pausan solas para no gastar batería y vuelven al enchufarlo. Tu interruptor de animaciones de Ajustes manda sobre esto: si las apagaste, no vuelven solas. En Ajustes verás si el ahorro está activo en este momento.",
            "TAMAÑO DE LA INTERFAZ: en Ajustes → Vista, «Tamaño de la interfaz» — Normal o Grande (letra y barra lateral más grandes, pensado para pantallas como la de la Toughbook)—. La letra se aplica al momento y el resto de tamaños termina de ajustarse al reabrir la ventana; tu elección queda guardada.",
        ],
    },
    {
        "version": "1.0.15",
        "fecha": "25/11/2026",
        "novedades": [
            "ICONOS 3D DE VERDAD (tu veredicto sobre la 1.0.14: «no llegaron los iconos como yo los quiero»): los iconos del panel de la izquierda ya no son glifos planos dibujados por código: son gráficos 3D generados a partir de TU foto de referencia, uno por entrada y con sus materiales —casa azul con las ventanas encendidas, lupa de cristal, escudo de metal con el check verde, chip negro con pines dorados, escoba de mango azul y cerdas doradas, disco CD con brillo iridiscente, flechas verde y azul, globo terráqueo con su anillo, portapapeles con gráfica, moneda dorada con la «i», calendario con reloj y engranaje de metal—. Siguen animados igual que antes (brillo que cruza, pulso del activo, giro de Actualizaciones) y el interruptor de animaciones de Ajustes los deja quietos en su versión 3D.",
            "OPTIMIZAR VOLÚMENES: VEREDICTO CIERTO SIEMPRE (tu orden: «ya no quiero que diga no se completó»): la optimización ya no depende de que un comando silencioso deje constancia en tres sitios distintos. Ahora la hace defrag.exe, la herramienta de Windows, con su informe y su código de resultado capturados por la propia app: si termina bien, dice «Optimización finalizada»; si algo falla, la causa sale del propio informe de Windows o de su código —incluidos dos avisos nuevos con nombre propio: si Windows tuviera el TRIM deshabilitado o el servicio «Optimize drives» apagado, eso es lo que la app te dirá. El desenlace «Windows no dio la causa» ha desaparecido.",
            "AHORA TAMBIÉN EN INGLÉS (pedido tuyo durante la construcción de la 1.0.14; sale en esta porque una versión con el mismo número no puede ofrecerse como actualización a la que ya tienes): en el panel de la izquierda hay un selector de idioma, Español / English, que cambia TODA la interfaz al momento —pantallas, botones, mensajes de la VPN, menú de la bandeja y avisos— sin reiniciar la app y sin cortar una VPN conectada. Tu elección queda guardada. Las notas de versión y el detalle técnico de OpenVPN siguen saliendo tal cual los produce la herramienta, sin traducir.",
            "NUEVO BOTÓN «VERIFICAR SERVIDORES» EN RED Y VPN (idea tuya en llamada): comprueba TODOS los servidores de la lista con la prueba real de conexión —la misma del autoanálisis— y marca cada fila con ✓ o ✗ en cuanto cae su resultado, con su causa cuando falla. Mientras corre enseña la barra con el porcentaje subiendo y el conteo de verificados y fallidos; se pausa solo si conectas la VPN y puedes detenerlo con el mismo botón. Los veredictos alimentan el orden de la lista y el salto automático de servidor, igual que los del autoanálisis.",
        ],
    },
    {
        "version": "1.0.14",
        "fecha": "25/11/2026",
        "novedades": [
            "SI UN SERVIDOR ESTÁ LLENO, LA APP SALTA SOLA AL SIGUIENTE: algunos servidores de la lista pública rechazan la conexión aunque el programa se conecte bien (están llenos o fuera de servicio, y su saludo y su certificado son perfectos: solo se descubre al intentar entrar). Ahora, cuando un servidor dice que no, la app lo marca y prueba con el siguiente candidato hasta conectar o agotar los intentos, y si ninguno acepta lo dice tal cual: «los servidores probados están llenos o fuera de servicio». Nunca es tu credencial: es la correcta de cada fuente.",
            "DOS FUENTES DE SERVIDORES, UNA SOLA LISTA: además de VPN Gate, la app trae ahora los servidores de VPNBook (Estados Unidos, Canadá, Reino Unido, Alemania y Francia), cada uno marcado con su fuente en la tabla. La contraseña de VPNBook cambia cada una o dos semanas y la app la lee de su página oficial en cada actualización de la lista: nunca va escrita dentro del programa.",
            "AUTOANÁLISIS CON PRUEBA REAL: al abrir la app, en segundo plano y sin estorbar, la lista se actualiza sola (cada media hora) y la app comprueba DE VERDAD unos pocos servidores cada vez —conecta con ellos un instante y se desconecta— para saber cuáles funcionan. Cada fila enseña su sello («✓ Verificado» con la hora, «Lleno/sin acceso», «No responde» o «Sin verificar») y el orden nuevo «Recomendado» pone primero los verificados y luego los de pocas sesiones: los más rápidos de la lista solían ser justo los llenos.",
            "LA LISTA NUNCA QUEDA VACÍA NI DESACTUALIZADA EN SILENCIO: la última lista buena queda guardada en el equipo y es la que ves al abrir, con sus sellos, mientras la nueva se busca en segundo plano. Si una actualización de la lista falla, la guardada no se toca.",
        ],
    },
    {
        "version": "1.0.13",
        "fecha": "25/11/2026",
        "novedades": [
            "VPN Gate REPARADA DE NUEVO, con la causa probada en tu PC: en la 1.0.12 cada intento de conexión se cerraba EN SU PRIMER SEGUNDO — la propia app apagaba el intento. OpenVPN arranca elevado a través de su servicio y la app, que corre normal, a veces no tiene permiso ni para mirar ese proceso; la comprobación de vida lo daba por muerto sin poder mirarlo y la app lo apagaba ella misma. Ahora la vida del proceso tiene tres estados —vivo, muerto o «no comprobable»— y lo no comprobable NUNCA cuenta como muerte: la muerte exige dos pruebas positivas, una de ellas preguntando por la propia interfaz de gestión de OpenVPN.",
            "Diagnóstico honesto de la VPN, segunda parte: si la app detiene un intento (por ejemplo, al agotar el tiempo de espera), la pantalla lo dice tal cual —«la app detuvo el intento»— en vez de culpar al servidor. El aviso de error de certificados (TLS) ya no puede salir de una advertencia rutinaria de arranque: exige un error TLS de verdad. Y el código de salida de OpenVPN solo se enseña si se leyó del proceso real; si no se conoce, se dice «no disponible» — nunca más un 0 inventado.",
            "El detalle técnico de un intento ya sale SOLO del registro de ese intento, con su hora: en la 1.0.12 la pantalla llegó a enseñar el registro de un intento anterior (el de las 11:31) como si fuera el de ahora, porque caía a un archivo que la versión ya no escribe. Si un intento aún no tiene registro, el detalle dice «sin registro todavía» y nada más.",
            "Cada intento de conexión queda anotado en el registro de actividad con la vía usada (servicio interactivo o elevado) y su primer sondeo, para poder diagnosticar sin fotos si algo vuelve a fallar.",
        ],
    },
    {
        "version": "1.0.12",
        "fecha": "25/11/2026",
        "novedades": [
            "VPN Gate REPARADA DEL TODO: en la 1.0.11 el túnel llegaba a abrir, pero Windows negaba las rutas del tráfico porque la app lanzaba OpenVPN sin los privilegios de su servicio — el túnel quedaba abierto pero inútil, y encima quedaba un OpenVPN «huérfano» vivo sujetando la tarjeta. Ahora la app conecta a través del OpenVPN Interactive Service (el servicio oficial que hace las rutas con privilegios del sistema, igual que el programa oficial de OpenVPN), con arranque elevado de reserva si el servicio no puede.",
            "El instalador deja tu usuario en el grupo «OpenVPN Administrators» y el servicio interactivo corriendo: sin ese grupo, el servicio de OpenVPN rechaza los perfiles de la app. Si Windows aún no lo aplica a tu sesión, la app te avisa de que cierres sesión una vez y, mientras tanto, conecta elevada.",
            "Ningún OpenVPN huérfano más: un solo intento de conexión a la vez, y todo intento que no termina en «conectado» se cierra y se verifica cerrado antes de decir que falló. Al abrir, la app barre los huérfanos que sean suyos (los OpenVPN de otros programas no se tocan: si uno sujeta la tarjeta, la app lo dice).",
            "Diagnóstico honesto de la VPN: si Windows niega las rutas, la pantalla lo dice tal cual («Windows negó crear las rutas del tráfico: no es la tarjeta ni el servidor») y si el túnel abre pero sin rutas, lo dice también («túnel abierto pero sin rutas: tu tráfico no sale por la VPN») y lo baja limpio. Las líneas informativas del registro ya no pueden convertirse en una causa falsa, y el detalle enseña el código de salida de OpenVPN.",
        ],
    },
    {
        "version": "1.0.11",
        "fecha": "25/11/2026",
        "novedades": [
            "VPN Gate REPARADA: en la 1.0.10 conectar fallaba con TODOS los servidores. La causa, probada en la PC real y en el código fuente de OpenVPN: la ruta del archivo de credenciales que la app escribe dentro del perfil de conexión iba con las barras normales de Windows, y OpenVPN las rechaza como error grave («Bad backslash») y se cierra antes de intentar conectar — con cualquier servidor. Ahora la ruta va escrita como manda la documentación oficial de OpenVPN y el perfil pasa entero.",
            "Estado VPN honesto: la app solo dice «CONECTADA» cuando el túnel está confirmado de verdad por OpenVPN. Antes podía decir «conectada» sin haber conectado nunca, porque contaba como túnel los programas residentes de OpenVPN (su ventana y su servicio).",
            "Si una conexión falla, la causa REAL se ve en la propia pantalla de «Red y VPN», bajo el mensaje (detalle técnico), y queda guardada en el registro de actividad con las últimas líneas del registro de OpenVPN. El aviso de «servidor apagado o saturado» ahora solo sale cuando el fallo es de verdad del servidor o de la red.",
            "El registro de cada intento de conexión ya no se borra al intentar de nuevo: se guarda con fecha y hora (los últimos 5), para poder revisar qué pasó en cada intento.",
            "Si OpenVPN no confirma la conexión a tiempo, la app cierra ese intento del todo: ya no queda ningún túnel «fantasma» reintentando en segundo plano después de un fallo.",
        ],
    },
    {
        "version": "1.0.10",
        "fecha": "25/11/2026",
        "novedades": [
            "CAMBIO DE MOTOR VPN: SoftEther sale de la app y entra OpenVPN. La causa, probada en la PC real: el controlador de la tarjeta virtual de SoftEther (del año 2018) lo bloquea Windows al instalar el dispositivo, y ninguna versión de la app puede forzarlo. El instalador de la app ahora instala en silencio el OpenVPN oficial (el de la comunidad), cuyo servicio y cuya tarjeta virtual TAP-Windows traen controladores firmados y aceptados por Windows.",
            "La VPN se usa IGUAL que antes, desde la misma pantalla de «Red y VPN»: la misma lista de servidores de VPN Gate por países, el botón «Conectar» que se pone verde y dice «Conectado» con el botón rojo «Desconectar» a su lado, y el túnel trabajando en segundo plano, sin abrir ningún otro programa. Lo que cambia es solo el motor de debajo.",
            "Al actualizar desde la 1.0.9, el instalador retira limpiamente los restos de SoftEther (su servicio, su carpeta y su controlador) sin tocar nada más.",
            "OpenVPN siempre al día, SIN romperse: cada 3 días la app comprueba en segundo plano si hay una versión más nueva en las fuentes oficiales; la descarga y la verifica ANTES de aplicarla (tamaño oficial, instalador válido y firma de OpenVPN). Nunca se aplica con una conexión VPN activa (espera a que desconectes), y tras aplicarla comprueba que OpenVPN sigue sano: si algo quedara mal, vuelve SOLA a la versión anterior que funcionaba y deja la causa en el registro de actividad.",
            "Red y VPN: los botones «Conectar» de la tabla de servidores ya se leen completos (la fila era más baja que el botón y se cortaban por abajo).",
        ],
    },
    {
        "version": "1.0.9",
        "fecha": "25/11/2026",
        "novedades": [
            "VPN Gate: LA SOLUCIÓN del fallo de la tarjeta virtual (el «Error 31» de SoftEther). La causa probada: el controlador de la tarjeta nunca quedaba instalado en el almacén de controladores de Windows (el DriverStore), y crear la tarjeta lo exigía. Ahora el instalador, ANTES de crear la tarjeta y a la vista, instala el paquete oficial del controlador de SoftEther para Windows 10 (Neo6_x64_VPN, extraído del propio paquete oficial y verificado por su huella) con la herramienta de Windows pnputil, comprueba que quedó almacenado y deja todo el resultado —salida de pnputil incluida— en «softether-nic-instalacion.txt», junto a la app.",
            "Respaldo al conectar reforzado: si la tarjeta faltara al darle a «Conectar», el paso de administrador ahora se abre INTERACTIVO en tu sesión (sin el modo no interactivo que impedía que saliera el aviso de Windows), vuelve a almacenar el controlador y guarda la salida real de SoftEther en el registro de la app.",
            "Red y VPN: en la tabla de servidores de VPN Gate, cuando un servidor está conectado, su botón se pone verde y dice «Conectado» y A SU LADO, en la misma fila, aparece el botón rojo «Desconectar» para bajar el túnel desde esa fila.",
            "Inicio: la calificación numérica de salud ya no va en el centro del radar (quedaba encima del haz); ahora se enseña en el borde inferior izquierdo de la imagen del radar, fuera del círculo. El radar y su animación no cambian.",
        ],
    },
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
