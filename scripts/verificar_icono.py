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
"""
import hashlib
import struct
import sys


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
    print("Icono verificado dentro del ejecutable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
