"""Escala de la interfaz (v1.0.16, frente 7).

Dos tamaños, en Ajustes → Vista: «Normal» (el de siempre) y
«Grande» (factor 1.22 sobre la letra base y sobre el ancho de
la barra lateral, para pantallas como la de la Toughbook,
donde todo se ve justo). El «letra grande» anterior (×1.125)
sigue valiendo cuando la escala es «normal»: el factor
efectivo es el MAYOR de los dos caminos, nunca la suma.

Aplicación honesta: la letra de la aplicación se fija en
ui.main al arrancar (como ya se hacía con letra_grande) y la
ventana lee el mismo factor para su barra lateral; desde
Ajustes, cambiar la escala la guarda y aplica la letra AL
MOMENTO sobre la aplicación viva, y la propia página avisa de
que el resto de tamaños (barra, espaciados ya creados) termina
de ajustarse al reabrir la ventana.
"""
FACTOR_GRANDE = 1.22
FACTOR_LETRA_GRANDE = 1.125

ESCALAS = ("normal", "grande")


def factor_de(ajustes) -> float:
    """El factor efectivo según los ajustes (puro, probado)."""
    factor = 1.0
    if getattr(ajustes, "escala_interfaz", "normal") == "grande":
        factor = FACTOR_GRANDE
    if getattr(ajustes, "letra_grande", False):
        factor = max(factor, FACTOR_LETRA_GRANDE)
    return factor


def aplicar_escala(app, ajustes) -> float:
    """Fija la letra de la aplicación según el factor. Guarda el
    tamaño base la primera vez (propiedad de la app) para que
    reaplicar no componga factores. Devuelve el factor."""
    factor = factor_de(ajustes)
    fuente = app.font()
    base = app.property("_ahogar_fuente_base")
    if not base:
        base = fuente.pointSizeF()
        if base and base > 0:
            app.setProperty("_ahogar_fuente_base", base)
    if base and base > 0:
        fuente.setPointSizeF(float(base) * factor)
        app.setFont(fuente)
    return factor
