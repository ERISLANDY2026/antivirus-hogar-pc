# Antivirus Hogar PC — Requisitos v1.0.2 (dictados por Erislandy, 2026-11-24)

Estado: **APROBADO por él el 2026-11-24 («Dale, métele») — construcción de la v1.0.2 EN CURSO.** Incluye sus requisitos (porcentajes, colores, cromados, RGB, botones animados, arreglo de la ventana de drivers) Y las propuestas del asistente que él aprobó en la misma llamada (medidores CPU/RAM/disco, registro de actividad, gestor de inicio, mapa de disco, velocidad de internet + estado VPN).

## Interfaz — su veredicto sobre la v1.0.1
- La interfaz se ve «aburrida».
- Los botones tienen casi sin colores.
- Las animaciones son muy breves / pobres.
- No hay efectos RGB por ningún lado.
- Sin efectos cromados («chrome»).

## Lo que pide
1. **Porcentaje en TODO el progreso, sin excepción:**
   - Barras de escaneo: porcentaje visible.
   - Barras de drivers: porcentaje visible.
   - Barras de actualizaciones: porcentaje visible.
   - Cualquier otra barra de progreso de la app: porcentaje visible.
2. **Colores** en los botones y en la interfaz en general.
3. **Efectos chrome / cromados.**
4. **Efectos RGB** en la interfaz.
5. **Botones con animaciones** (no estáticos ni con animación mínima).

## Ventana de Drivers — problema reportado por él (2026-11-24)
- La ventana de drivers es muy grande: la columna de botones «Actualizar» de cada driver queda muy lejos a la derecha y no se ven al final. Hay que ajustar el tamaño para que todo quepa en pantalla y los botones queden visibles.

## BUGS reportados por él en la v1.0.1 (2026-11-24, a corregir en la v1.0.2)
1. **Buscar actualizaciones de la app falla siempre:** al pulsar «Buscar actualizaciones» sale «No se pudo comprobar si hay una actualización, revisa tu conexión a internet» AUNQUE sí hay internet. **Causa raíz confirmada en el código:** `config.py` trae la URL con el id marcador `1BpcVersionJsonPendiente` — el archivo version-pc.json NUNCA se publicó en Drive, la descarga falla y la app lo disfraza de error de conexión. **Corrección obligatoria:** publicar el version-pc.json real en la carpeta «Antivirus Hogar PC» de Drive, poner su ID real en config, y que los errores digan la causa verdadera (no «revisa tu conexión» cuando la conexión está bien).
2. **VPN sin países:** en la sección VPN, el desplegable de países está vacío y la lista de servidores/abajo no muestra nada. **Causa probable verificada en el código:** la lista de servidores de VPN Gate SOLO se descarga al pulsar «Actualizar lista de servidores» (la página no la carga al abrir, solo auto-carga el Wi-Fi), y si esa descarga falla, la lista queda vacía sin un error claro. **Corrección obligatoria:** cargar la lista automáticamente al abrir la sección, poblar el desplegable de países desde la respuesta, y si la descarga falla mostrar el error real con botón de reintentar — nunca una lista vacía en silencio. **Especificación expresa de él para esa lista:** debe seguir mostrando las columnas **servidor, velocidad, ping, sesiones y acción**, y **cada servidor con su propio botón para conectarse a ese elegido**. (En el código esas columnas y el botón «Conectar» por fila ya existen en `modules/net/page.py`; lo que falla es que la lista nunca se puebla en su PC — la corrección es que la descarga/carga funcione de verdad y se verifique con prueba, no rediseñar la tabla.)

3. **Sin botón general de encender/apagar la VPN (reportado por él, 2026-11-24):** no ve ningún botón para apagar/encender la VPN en general. **Confirmado en el código:** existe `conectar_vpn` (guarda el .ovpn y abre OpenVPN GUI) y `estado_vpn`, pero NO existe ninguna función de desconectar ni botón de apagado en la página. **Corrección obligatoria:** interruptor general visible en la sección VPN que muestre el estado (conectada/desconectada, y a qué servidor/país) y permita DESCONECTAR la VPN activa desde la propia app, además del «Conectar» por servidor ya pedido.

4. **Botón «Actualizar datos de Wi-Fi» no hace nada visible (reportado por él, 2026-11-24):** en Red y Wi-Fi, tarjeta «Wi-Fi» («Tu Wi-Fi de un vistazo»), al tocarlo no pasa nada. **Revisión del código:** el botón SÍ está conectado a `_cargar_wifi`, que relanza `informe_wifi` (netsh wlan), PERO sin ninguna señal visible de trabajo: no deshabilita el botón, no muestra progreso y, si la lectura devuelve lo mismo o falla en silencio en el .exe, la pantalla queda idéntica — para el usuario está muerto. **Corrección obligatoria:** al pulsarlo, feedback visible inmediato (botón deshabilitado con «Leyendo…», barra de progreso), sello «Actualizado a las HH:MM:SS» al terminar, y error visible con causa si netsh falla; verificar el camino completo en el ejecutable congelado, no solo en fuente.

## Análisis del código actual (hecho por el asistente a su pedido, 2026-11-24)
Causas raíz verificadas en el código:
- **Tema plano:** un solo acento cian, botones de un color sólido oscuro (#1B2740) y chunk de progreso plano, sin gradientes, sin brillo, sin motor de animación salvo el anillo de salud. Por eso se ve «aburrida».
- **Barras sin porcentaje:** las barras de drivers/actualizaciones/limpieza usan rango indeterminado (0,0) — ruedan sin número; es imposible mostrar % así. La del escaneo de seguridad sí cuenta archivos, pero sin formato de texto reforzado.
- **Tabla de drivers:** `resizeColumnsToContents()` + `setStretchLastSection(True)` con ventana de 1120 px empuja la columna «Acción» al extremo derecho.

## Propuestas del asistente (PENDIENTES de su aprobación, no son orden todavía)
### Visualización
1. Barras determinadas donde se puede contar (archivos escaneados, MB descargados, drivers x de y) con % grande y animado; donde Windows no da % real (Windows Update), mostrar etapa + conteo de pasos, nunca un % inventado.
2. Gradiente animado tipo RGB en el chunk de progreso y en los bordes de la tarjeta activa; brillo (glow) al pasar el mouse por botones.
3. Botones por color según acción: escanear = cian, actualizar = verde, peligro = rojo, neutro = cromado; con icono, sombra y animación de pulso en la acción principal.
4. Tabla de drivers compacta: anchos proporcionales fijos, columna «Acción» pegada y siempre visible, nombre de dispositivo con corte elegante; alternativa: una tarjeta por driver.
5. Panel con medidores en vivo de CPU, RAM y disco con % y mini-gráfica; anillo de salud con gradiente RGB suave.
6. Historial visual: gráfica de escaneos y limpiezas de los últimos días en el Panel.

### Servicios nuevos posibles
7. **Registro de actividad** dentro de la app: qué se escaneó, qué se limpió, qué driver se actualizó y cuándo, con opción de exportar el informe.
8. **Gestor de programas de inicio** con impacto (alto/medio/bajo) y botón de desactivar — hoy el tune-up limpia temporales pero no muestra el inicio.
9. **Mapa de uso de disco:** qué carpetas ocupan más, en barras con % — ayuda a decidir qué limpiar.
10. **Prueba de velocidad de internet y estado VPN** con números (país/servidor, IP, ping) en la página de Red.
11. **Avisos dentro de la app** (centro de avisos): Defender apagado, disco SMART en riesgo, drivers pendientes — hoy esos datos están repartidos por páginas.

## Bugs de la v1.0.1 corregidos en la v1.0.2 (obligatorios)
1. **Actualizaciones de la app:** «Buscar actualizaciones» siempre decía «revisa tu conexión» porque el version-pc.json nunca se publicó (config traía el id marcador `1BpcVersionJsonPendiente`). Corrección: version-pc.json REAL publicado en la carpeta «Antivirus Hogar PC» de Drive (ID `1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R`, lectura pública), ID real en `UPDATE_VERSION_URL`, y errores clasificados en core/updater (`ErrorActualizacion`: sin_conexion / no_encontrado / respuesta_invalida) con mensajes distintos por causa en la página. Al entregar la v1.0.2 hay que ACTUALIZAR el contenido de ese mismo archivo (mismo ID) con version=1.0.2, la URL del instalador 1.0.2 (subido como archivo propio, ID nuevo) y su sha256.
2. **VPN sin países:** la lista solo se descargaba a mano y un fallo la dejaba vacía en silencio. Corrección: carga automática al abrir Red/VPN, combo de países y tabla (País, Servidor, Velocidad, Ping, Sesiones, Acción con «Conectar» por fila) poblados desde la API, error visible con causa y botón «Reintentar descarga».
3. **Interruptor general VPN:** no existía forma de apagar la VPN. Corrección: estado real (proceso openvpn + último perfil entregado) y botón «Desconectar VPN» que cierra el proceso openvpn del túnel (OpenVPN Connect/GUI no ofrecen comando de desconexión a terceros; SoftEther no se toca y se dice), tras lo cual el estado pasa a «Desconectada» y la IP pública se refresca.

## Notas
- Es la continuación natural de lo que ya le gustó en la maqueta original: iconos animados por fila, anillo de salud con órbita y conteo animado, bordes definidos en cian — pero llevado más lejos: más color, más animación, RGB y cromados.
- Al cerrar la lista hay que verificar cada punto contra el ejecutable congelado (lección v1.0.0/v1.0.1: la suite en fuente no basta).
