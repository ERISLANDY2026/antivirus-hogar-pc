# INFORME — Antivirus Hogar PC v1.0.8 (VÍA RÁPIDA)

**Fecha:** 2026-11-25 · **Orden del usuario (llamada de voz):** construir
y entregar la corrección SIN diagnósticos ni batería de pruebas —
**él prueba en su PC real**.

**Estado: ENTREGADA — NO VERIFICADA, por decisión expresa del usuario.**
No se corrió la suite en local (solo `py_compile` de los módulos
tocados), no hubo puerta de diagnóstico VPN ni puerta final anónima
del canal, y no se verificaron descargas. La compilación en la nube
sí corrió su paso interno de pytest como parte del pipeline (ver
«Problemas», punto 1) y terminó en SUCCESS. El túnel real y la
creación de la tarjeta en su Toughbook quedan pendientes de SU
prueba, como él ordenó.

---

## Lo que trae (alcance exacto pedido)

### 1. La tarjeta virtual de SoftEther se crea EN LA INSTALACIÓN
Causa raíz (investigación 2026-11-25): la 1.0.7 nunca instalaba el
driver de la tarjeta virtual; la app intentaba crearla al conectar,
sin elevar y en oculto, y Windows no lo permite. Ahora el instalador
—que ya corre elevado e interactivo— tras registrar e iniciar el
servicio SEVPNCLIENT ejecuta `NicCreate VPN` con el vpncmd
incorporado, lo verifica con `NicList` y deja TODO (incluida la
salida exacta de vpncmd) en **`{app}\softether-nic-instalacion.txt`**.
Si NicCreate falla, la instalación NO se aborta: queda registrado
para que el usuario lo reporte.

### 2. Reserva al conectar + registro del detalle real
Si al darle a «Conectar» la tarjeta no existe, `conectar_softether`
la crea con la nueva `crear_nic_elevada()`: ELEVADO y VISIBLE vía
`winapi/powershell.py::ejecutar_elevado`, nunca oculto, y verificado
después con NicList. Y cada intento de conexión de VPN Gate (éxito o
fallo) queda escrito en `actividad.jsonl` vía `core.actividad`, con
el mensaje y el detalle técnico real de vpncmd (antes se perdía).

### 3. Globo terráqueo en la esquina de la tabla de VPN Gate
Widget `GloboEsquina` sobre la celda de esquina de la tabla de
servidores: esfera dibujada por código (QPainter, sin imágenes),
girando a **1 vuelta por segundo**, colgada del RELOJ compartido de
50 ms y de la puerta global de animaciones (interruptor
`fondo_animado` de Ajustes). Según `DISENO-GLOBO-VPNGATE.md`.

### 4. Versión 1.0.8
`config.VERSION`, `#define AppVersion` del instalador y entrada
nueva al frente de `core/notas_version.py`.

## Problemas encontrados por el camino

1. **Run 45605854559 — FAILURE en el paso «Pruebas» del propio
   workflow** (248 pasaron, 4 fallaron, todos en
   `tests/test_v107.py`): dos pines de versión («1.0.7» en
   config/iss) y dos flujos de conexión cuyo vpncmd falso nacía SIN
   tarjeta (el flujo nuevo ya no la crea en oculto: la trae el
   instalador o se crea elevada). Mantenimiento mínimo de esos tests
   históricos (pines a 1.0.8; el falso nace con la tarjeta creada,
   como la deja el instalador) y la corrida siguiente,
   **45606361973, SUCCESS completa**. No se corrió ninguna prueba en
   local, como se ordenó: el ajuste fue de aserciones, no una
   batería nueva.

## Datos de la entrega

- **Compilación:** GitHub Actions run **45606361973 SUCCESS**
  (commits remotos `6ab0199` —cambios— y `9250544` —mantenimiento de
  tests—). La corrida fallida fue la 45605854559.
- **Instalador:** `Instalador-AntivirusHogarPC-1.0.8.exe` —
  **63.697.527 bytes** · MD5 `fdfdfe0fd52fe3d87515fc4b13424873` ·
  SHA-256 `4644d7c6254fb2779686592e30918e8cc8761dfc1b6b0895d54a320329f0dc88`.
- **Zip del canal:** 63.187.469 bytes · MD5
  `fad7e199655d33db7ffbe72305d064d5`.
- **Canal de Drive** (carpeta `1I7V-Zabmiov8ttDHMkuJL8dlP1GeukHM`),
  actualizado **en sitio** y renombrado a 1.0.8: .exe
  `1zmtcu-NL-PvCbGisbAXbFwVwyBlI5_ql` (63.697.527 B), zip
  `1ZHiCO9lInsLv6GJBCdCj6GtTMjGf6hTG` (63.187.469 B),
  version-pc.json `1Kfd_pELWJhp37fO1iaERdSIzpRkAqK4R` (1.090 B;
  versión 1.0.8, URL del .exe con `&confirm=t`, SHA-256 del
  instalador nuevo).
- **Copia visible nueva:** «INSTALADOR Antivirus Hogar PC
  v1.0.8.zip», ID `1QDmUjyqPsKFwiqNC2B3ULW_i4WP-D6Rf`
  (63.187.469 B). La copia visible de la 1.0.7
  (`1ahTzOaE3KqBZSCnqHqeERpDBNAucBBHA`) quedó **en la papelera**.
- Paquete local en `build-nube-v108/` (instalador, zip,
  version-pc.json y el artefacto de CI).

## Pendiente (del usuario, por su orden)

- **Su prueba en la Toughbook:** instalar la 1.0.8 (por el botón
  desde la 1.0.7 o a mano desde la copia visible), revisar
  `softether-nic-instalacion.txt` si algo falla, y probar
  «Conectar» en VPN Gate: la tarjeta ya debe existir desde la
  instalación y el botón debe ponerse verde «Conectado». El globo
  de la esquina debe girar a una vuelta por segundo.
