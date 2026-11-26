# Reglas YARA — paquete «core» de YARA Forge

- Archivo: `yara-rules-core.yar` (5.078 reglas, paquete del 2026-11-22).
- Fuente: YARA Forge — https://github.com/YARAHQ/yara-forge
  (agrega reglas públicas con control de calidad: calidad ≥ 70,
  puntuación ≥ 65 para el paquete core).
- Licencia: LA DE CADA REGLA. El paquete conserva en el `meta` de
  cada regla su `author` y su `license` tal como los publicó su
  autor; la app enseña ambos en cada alerta y NO relicencia nada.
  Hay reglas sin licencia declarada («NO LICENSE SET» en su meta):
  se usan como datos de detección en una app doméstica gratuita.
- Uso: segundo motor de escaneo (core/yara_scan.py), junto al de
  huellas. Compilar el paquete entero tarda unos segundos; se
  compila una sola vez por sesión y en segundo plano.
