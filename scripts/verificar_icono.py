"""Verifica que el .exe construido lleva incrustado el icono del proyecto.

Uso: python scripts/verificar_icono.py <ruta.exe> <ruta.ico>

Comprueba, leyendo los recursos RT_GROUP_ICON / RT_ICON del PE con
pefile (dependencia de PyInstaller en Windows):
- que el ejecutable tiene grupo de iconos (no el de por defecto vacío);
- que la entrada mayor es de 256×256;
- que el volumen total de datos de icono es el de una imagen real
  (el icono por defecto de PyInstaller pesa unos pocos KB; el
  espartano, >100 KB);
- y compara el SHA-256 de la imagen de 256 del .exe con la del .ico
  de origen (PyInstaller la copia tal cual: si coincide, queda
  demostrado byte a byte; si el proceso la recodificara, se informa
  pero no se tumba la compilación por eso).

Sale con código 1 si falta el icono o no es el tamaño esperado.

v1.0.7: se comprueba además que el fondo es TRANSPARENTE de verdad
(el icono anterior llevaba el fondo blanco del arte pegado): la
imagen de 256 debe ser PNG con canal alfa, con las cuatro esquinas
totalmente transparentes y una parte apreciable de pixeles
transparentes. El alfa se lee con un decodificador PNG mínimo
propio (sin dependencias nuevas: en CI solo están pefile y lo de
requirements.txt).
"""
import hashlib
import struct
import sys
import zlib


def _alfa_de_png(datos: bytes) -> tuple[int, int, list[int]] | None:
    """(ancho, alto, alfás) de un PNG RGBA de 8 bits no entrelazado.

    Devuelve None si el PNG no tiene canal alfa o no se puede leer.
    """
    if datos[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos = 8
    ancho = alto = 0
    tipo_color = -1
    idat = bytearray()
    while pos + 8 <= len(datos):
        tam, tipo = struct.unpack_from(">I4s", datos, pos)
        cuerpo = datos[pos + 8:pos + 8 + tam]
        if tipo == b"IHDR":
            ancho, alto, profundidad, tipo_color, _c, _f, entrelazado = \
                struct.unpack(">IIBBBBB", cuerpo)
            if profundidad != 8 or entrelazado != 0:
                return None
        elif tipo == b"IDAT":
            idat += cuerpo
        elif tipo == b"IEND":
            break
        pos += 12 + tam
    if tipo_color != 6 or not idat or not ancho:
        return None  # sin canal alfa (RGB, paleta…)
    crudo = zlib.decompress(bytes(idat))
    paso = ancho * 4
    alfas: list[int] = []
    previo = bytearray(paso)
    i = 0
    for _y in range(alto):
        filtro = crudo[i]
        linea = bytearray(crudo[i + 1:i + 1 + paso])
        i += 1 + paso
        for x in range(paso):
            a = linea[x - 4] if x >= 4 else 0
            b = previo[x]
            c = previo[x - 4] if x >= 4 else 0
            if filtro == 1:
                linea[x] = (linea[x] + a) & 0xFF
            elif filtro == 2:
                linea[x] = (linea[x] + b) & 0xFF
            elif filtro == 3:
                linea[x] = (linea[x] + (a + b) // 2) & 0xFF
            elif filtro == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                linea[x] = (linea[x] + pr) & 0xFF
        alfas.extend(linea[3::4])
        previo = linea
    return ancho, alto, alfas


def _comprobar_transparencia(datos_png: bytes, donde: str) -> bool:
    leido = _alfa_de_png(datos_png)
    if leido is None:
        print(f"FALLO: la imagen de 256 de {donde} no es un PNG con "
              "canal alfa legible (¿fondo opaco?).")
        return False
    ancho, alto, alfas = leido
    esquinas = [alfas[0], alfas[ancho - 1],
                alfas[(alto - 1) * ancho], alfas[-1]]
    transparentes = sum(1 for a in alfas if a == 0) / len(alfas)
    print(f"Transparencia en {donde}: esquinas {esquinas} · "
          f"{transparentes:.0%} de pixeles transparentes")
    if any(a != 0 for a in esquinas):
        print(f"FALLO: las esquinas de {donde} no son transparentes "
              "(el fondo sigue pegado).")
        return False
    if transparentes < 0.10:
        print(f"FALLO: apenas hay transparencia en {donde} "
              "(¿icono con fondo?).")
        return False
    return True


def _entradas_ico(ruta: str) -> list[dict]:
    datos = open(ruta, "rb").read()
    _res, _tipo, n = struct.unpack_from("<HHH", datos, 0)
    entradas = []
    for i in range(n):
        off = 6 + i * 16
        ancho, alto, _cc, _r, _planos, _bpp, tam, pos = struct.unpack_from(
            "<BBBBHHII", datos, off)
        entradas.append({
            "ancho": ancho or 256, "alto": alto or 256,
            "datos": datos[pos:pos + tam],
        })
    return entradas


def _entradas_exe(ruta: str) -> list[dict]:
    import pefile

    pe = pefile.PE(ruta)
    grupos = {}
    sueltos = {}
    for tipo in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        nombre = tipo.id
        for recurso in tipo.directory.entries:
            for idioma in recurso.directory.entries:
                data_rva = idioma.data.struct.OffsetToData
                tam = idioma.data.struct.Size
                blob = pe.get_memory_mapped_image()[data_rva:data_rva + tam]
                if nombre == 14:  # RT_GROUP_ICON
                    grupos[recurso.id] = blob
                elif nombre == 3:  # RT_ICON
                    sueltos[recurso.id] = blob
    entradas = []
    for blob in grupos.values():
        _res, _tipo, n = struct.unpack_from("<HHH", blob, 0)
        for i in range(n):
            off = 6 + i * 14
            ancho, alto, _cc, _r, _planos, _bpp, _tam, nid = \
                struct.unpack_from("<BBBBHHIH", blob, off)
            if nid in sueltos:
                entradas.append({"ancho": ancho or 256,
                                 "alto": alto or 256,
                                 "datos": sueltos[nid]})
    return entradas


def main() -> int:
    exe, ico = sys.argv[1], sys.argv[2]
    del_exe = _entradas_exe(exe)
    del_ico = _entradas_ico(ico)
    if not del_exe:
        print("FALLO: el ejecutable no lleva grupo de iconos.")
        return 1
    mayor_exe = max(del_exe, key=lambda e: e["ancho"])
    mayor_ico = max(del_ico, key=lambda e: e["ancho"])
    total_exe = sum(len(e["datos"]) for e in del_exe)
    print(f"Entradas en el .exe: {len(del_exe)} · mayor "
          f"{mayor_exe['ancho']}x{mayor_exe['alto']} · "
          f"datos totales {total_exe} bytes")
    if mayor_exe["ancho"] != 256 or mayor_ico["ancho"] != 256:
        print("FALLO: falta la entrada de 256x256.")
        return 1
    if total_exe < 50_000:
        print("FALLO: el icono incrustado es demasiado pequeño para "
              "ser el espartano (¿el de por defecto de PyInstaller?).")
        return 1
    h_exe = hashlib.sha256(mayor_exe["datos"]).hexdigest()
    h_ico = hashlib.sha256(mayor_ico["datos"]).hexdigest()
    if h_exe == h_ico:
        print(f"La imagen de 256 del .exe COINCIDE byte a byte con "
              f"icono.ico (SHA-256 {h_exe[:16]}…).")
    else:
        print("AVISO: la imagen de 256 difiere en bytes del .ico de "
              "origen (posible recodificación de PyInstaller); tamaño "
              "y presencia verificados.")
    # v1.0.7: el fondo debe ser transparente en el .ico y en el .exe.
    if not _comprobar_transparencia(mayor_ico["datos"], "icono.ico"):
        return 1
    if not _comprobar_transparencia(mayor_exe["datos"], "el ejecutable"):
        return 1
    print("Icono verificado dentro del ejecutable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
