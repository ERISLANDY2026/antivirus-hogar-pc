"""v1.0.6 — Notas 6 y 7: iconos 3D con ANIMACIÓN CONTINUA visible y
acabado moderno (vidrio + bordes con movimiento) en las tarjetas.

Regresión que cubren: en la 1.0.5 el AnimadorIconoNav solo movía la
pestaña activa o la que tenía el ratón encima, ±5 %: el panel se
veía congelado («no tienen animación»). Aquí se exige que un icono
NI activo NI tocado cambie entre dos instantes, que el borde de una
tarjeta cambie entre dos instantes, y que con la puerta de Ajustes
apagada TODO quede quieto.
"""
import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from antivirus_hogar_pc.ui import animacion  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _puerta_encendida():
    animacion.fijar_animaciones_activas(True)
    yield
    animacion.fijar_animaciones_activas(True)


def _pixeles(pixmap):
    img = pixmap.toImage()
    return [img.pixel(x, y) for x in range(0, img.width(), 2)
            for y in range(0, img.height(), 2)]


def test_icono_nav_se_mueve_sin_estar_activo_ni_tocado():
    app = _app()
    from antivirus_hogar_pc.ui.iconos_nav import AnimadorIconoNav

    boton = QPushButton("Red y VPN")
    boton.show()
    animador = AnimadorIconoNav(boton, "red", animado=True, desfase=0.7)
    assert animador.animando()
    animador._tic(0.30)
    icono_a = boton.icon().pixmap(36, 36)
    animador._tic(1.35)
    icono_b = boton.icon().pixmap(36, 36)
    assert _pixeles(icono_a) != _pixeles(icono_b), (
        "el icono no cambió entre dos instantes: seguiría «sin "
        "animación» como en la 1.0.5")
    boton.deleteLater()
    app.processEvents()


def test_icono_nav_quieto_con_la_puerta_apagada():
    app = _app()
    from antivirus_hogar_pc.ui.iconos_nav import AnimadorIconoNav

    animacion.fijar_animaciones_activas(False)
    boton = QPushButton("Inicio")
    animador = AnimadorIconoNav(boton, "inicio", animado=True)
    assert not animador.animando()
    boton.deleteLater()
    app.processEvents()


def test_pixmap_nav_3d_flotacion_y_barrido_cambian_el_dibujo():
    _app()
    from antivirus_hogar_pc.ui.iconos_nav import pixmap_nav

    base = pixmap_nav("proteccion")
    flotando = pixmap_nav("proteccion", dy=1.6)
    barrido = pixmap_nav("proteccion", barrido=0.5)
    assert _pixeles(base) != _pixeles(flotando)
    assert _pixeles(base) != _pixeles(barrido)
    # Volumen: la parte baja del cuerpo es más oscura que la alta
    # (extrusión + gradiente de tres paradas).
    img = base.toImage()
    from PySide6.QtGui import QColor

    def brillo(y):
        c = QColor(img.pixel(img.width() // 2, y))
        return c.red() + c.green() + c.blue()

    alto = max(brillo(y) for y in range(6, 16))
    bajo = max(brillo(y) for y in range(img.height() - 16,
                                        img.height() - 4))
    assert bajo < alto


def test_tarjeta_borde_animado_cambia_entre_dos_instantes():
    app = _app()
    from antivirus_hogar_pc.ui.widgets_v102 import TarjetaAnimada

    tarjeta = TarjetaAnimada()
    tarjeta.resize(300, 120)
    tarjeta.show()
    app.processEvents()
    tarjeta._al_tic(0.2)
    foto_a = tarjeta.grab()
    tarjeta._al_tic(2.4)
    foto_b = tarjeta.grab()
    assert _pixeles(foto_a) != _pixeles(foto_b), (
        "el borde de la tarjeta no se movió entre dos instantes")
    tarjeta.deleteLater()
    app.processEvents()


def test_tarjeta_quieta_con_la_puerta_apagada():
    app = _app()
    from antivirus_hogar_pc.ui.widgets_v102 import TarjetaAnimada

    animacion.fijar_animaciones_activas(False)
    tarjeta = TarjetaAnimada()
    tarjeta.resize(300, 120)
    tarjeta.show()
    app.processEvents()
    foto_a = tarjeta.grab()
    tarjeta._al_tic(2.4)  # aunque llegara un tic, no debe moverse
    foto_b = tarjeta.grab()
    # Sin animación el único cambio posible sería el borde: quieto.
    assert _pixeles(foto_a) == _pixeles(foto_b)
    tarjeta.deleteLater()
    app.processEvents()


def test_reloj_compartido_un_solo_temporizador():
    """Rendimiento: el reloj es único y cuenta sus suscriptores."""
    _app()
    antes = animacion.RELOJ._suscriptores
    animacion.RELOJ.suscribir()
    assert animacion.RELOJ.en_marcha()
    assert animacion.RELOJ._suscriptores == antes + 1
    animacion.RELOJ.desuscribir()
    assert animacion.RELOJ._suscriptores == antes


# === Nota 9: radar futurista — barrido completo y ciclo morir/renacer ==========

def test_radar_barrido_cambia_entre_dos_instantes_y_llega_a_la_esquina():
    app = _app()
    from antivirus_hogar_pc.ui.fondo_radar import FondoRadar

    radar = FondoRadar(animado=False)
    radar.resize(760, 300)
    radar.show()
    app.processEvents()
    radar._angulo = 20.0
    radar.update()
    app.processEvents()
    foto_a = radar.grab()
    radar._angulo = 130.0
    radar._t += 0.7
    radar.update()
    app.processEvents()
    foto_b = radar.grab()
    assert _pixeles(foto_a) != _pixeles(foto_b)
    # El haz llega a la ESQUINA (radio = distancia a la esquina):
    # apuntando el borde líder a la esquina superior izquierda
    # (ángulo según la convención del propio radar), junto a ella
    # hay píxeles verdes del haz/estela que sin ese alcance no
    # existirían (el disco inscrito queda a ~400 px de la esquina).
    import math

    from PySide6.QtGui import QColor

    cx, cy = 760 / 2, 300 / 2
    radar._angulo = math.degrees(math.atan2(-(0 - cy), 0 - cx)) % 360
    radar.update()
    app.processEvents()
    img = radar.grab().toImage()
    verdes = 0
    for x in range(0, 90, 3):
        for y in range(0, 90, 3):
            c = QColor(img.pixel(x, y))
            if c.green() > 85 and c.green() > c.red() + 25:
                verdes += 1
    assert verdes >= 3, "el barrido no llega a la esquina de la imagen"
    radar.deleteLater()
    app.processEvents()


def test_radar_las_amenazas_mueren_y_renacen():
    app = _app()
    from antivirus_hogar_pc.ui.fondo_radar import FondoRadar

    radar = FondoRadar(animado=False)
    radar.resize(600, 300)
    radar.show()
    app.processEvents()
    am = radar._amenazas[0]
    # Se coloca la amenaza justo DELANTE del haz (ángulo 90° = arriba
    # del centro: x=centro, y=arriba) y el haz a 80° avanzando.
    am.x, am.y = 0.5, 0.2
    am.vx = am.vy = 0.0
    am.estado = "viva"
    radar._angulo = 80.0
    estados = []
    for _ in range(40):
        radar._avanzar()
        estados.append(am.estado)
    assert "muriendo" in estados, "el haz no mató a la amenaza"
    i_muerte = estados.index("muriendo")
    assert "renaciendo" in estados[i_muerte:], "la amenaza no renació"
    i_renace = estados.index("renaciendo")
    assert estados[-1] == "viva" or "viva" in estados[i_renace:], \
        "la amenaza renacida no volvió a estar viva"
    radar.deleteLater()
    app.processEvents()


def test_radar_respeta_el_interruptor_de_animacion():
    app = _app()
    from antivirus_hogar_pc.ui.fondo_radar import FondoRadar

    radar = FondoRadar(animado=False)
    radar.show()
    assert not radar.animando()
    radar.activar_animacion(True)
    assert radar.animando()
    radar.activar_animacion(False)
    assert not radar.animando()
    radar.deleteLater()
    app.processEvents()
