"""Puntuación de salud (core.health) con los pesos congelados (CONTRATOS.md §2):
Defender 30 (20 activo + 10 firmas) · firewall 15 · Windows 15 (8 al día +
7 con soporte) · CFA 10 · hallazgos 15 · disco 10 · arranque 5. Total 100.

Los componentes sin datos (None) se excluyen del máximo y la puntuación se
normaliza sobre el máximo conocido.
"""
from antivirus_hogar_pc.core.health import EstadoSalud, calcular_salud

TODO_BIEN = EstadoSalud(
    defender_activo=True, defender_firmas_al_dia=True, firewall_activo=True,
    windows_al_dia=True, windows_con_soporte=True, cfa_activo=True,
    hallazgos_recientes=0, disco_sano=True, entradas_arranque=9,
)
TODO_MAL = EstadoSalud(
    defender_activo=False, defender_firmas_al_dia=False, firewall_activo=False,
    windows_al_dia=False, windows_con_soporte=False, cfa_activo=False,
    hallazgos_recientes=3, disco_sano=False, entradas_arranque=30,
)


def test_todo_bien_da_100_sobre_100():
    r = calcular_salud(TODO_BIEN)
    assert r.puntuacion == 100
    assert r.maximo_conocido == 100
    assert r.motivos == []


def test_todo_mal_da_0_con_todos_los_motivos():
    r = calcular_salud(TODO_MAL)
    assert r.puntuacion == 0
    assert r.maximo_conocido == 100
    assert len(r.motivos) == 9  # un motivo por cada subcomponente fallado


def test_sin_datos_no_puntua():
    r = calcular_salud(EstadoSalud())
    assert r.puntuacion == 0
    assert r.maximo_conocido == 0
    assert r.motivos  # explica que aún no hay datos


def test_los_pesos_son_los_congelados():
    # Solo Defender perfecto: 30 conocidos, 30 ganados → 100 normalizado.
    r = calcular_salud(EstadoSalud(defender_activo=True, defender_firmas_al_dia=True))
    assert r.maximo_conocido == 30
    assert r.puntuacion == 100
    # Defender activo pero firmas atrasadas: 20 de 30 → 67.
    r = calcular_salud(EstadoSalud(defender_activo=True, defender_firmas_al_dia=False))
    assert r.maximo_conocido == 30
    assert r.puntuacion == 67
    # Solo firewall apagado: 0 de 15.
    r = calcular_salud(EstadoSalud(firewall_activo=False))
    assert r.maximo_conocido == 15
    assert r.puntuacion == 0
    # Windows: al día pero sin soporte: 8 de 15 → 53.
    r = calcular_salud(EstadoSalud(windows_al_dia=True, windows_con_soporte=False))
    assert r.maximo_conocido == 15
    assert r.puntuacion == 53
    # CFA 10, hallazgos 15, disco 10, arranque 5.
    assert calcular_salud(EstadoSalud(cfa_activo=True)).maximo_conocido == 10
    assert calcular_salud(EstadoSalud(hallazgos_recientes=0)).maximo_conocido == 15
    assert calcular_salud(EstadoSalud(disco_sano=True)).maximo_conocido == 10
    assert calcular_salud(EstadoSalud(entradas_arranque=0)).maximo_conocido == 5


def test_escenario_del_fake_del_panel_da_75():
    # El mismo EstadoSalud que usa modules/panel/fake.py en la Ola 0:
    # pierde Windows al día (8), soporte (7) y CFA (10) → 75 puntos, 3 motivos.
    estado = EstadoSalud(
        defender_activo=True, defender_firmas_al_dia=True, firewall_activo=True,
        windows_al_dia=False, windows_con_soporte=False, cfa_activo=False,
        hallazgos_recientes=0, disco_sano=True, entradas_arranque=9,
    )
    r = calcular_salud(estado)
    assert r.puntuacion == 75
    assert r.maximo_conocido == 100
    assert len(r.motivos) == 3


def test_umbral_de_arranque():
    assert calcular_salud(EstadoSalud(entradas_arranque=12)).puntuacion == 100
    r = calcular_salud(EstadoSalud(entradas_arranque=13))
    assert r.puntuacion == 0
    assert r.motivos  # «Hay 13 programas que arrancan con Windows.»
