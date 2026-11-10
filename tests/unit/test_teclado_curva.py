"""A curva da seta segurada (automationstudio/teclado_edicao.py): quanto o valor muda conforme o tempo que a seta fica apertada.

Lógica pura. Os números são os da tabela da seção 5 de md/FICHA_TECLADO_T2_25_9.md, que é o pedido do usuário em números:
"segurando a seta esquerda o tempo diminui cada vez mais rápido, e os 3 primeiros segundos são bem lentos". Cada constante da
curva é uma só, no módulo; estes testes dizem o que a curva FAZ, e as constantes aparecem só onde o teste precisa delas.
"""
from __future__ import annotations

import math

import pytest

from automationstudio import teclado_edicao as te
from automationstudio.teclado_edicao import (LIMITE_TOQUE, PASSO_TOQUE, SEGUNDOS_LENTOS, TETO, VELOCIDADE_INICIAL, VELOCIDADE_MAXIMA,
                                             mudanca_acumulada, valor_apos, velocidade)

# O instante em que a velocidade, que dobra a cada 2 s depois dos 3 primeiros, chega ao teto de 60 s por segundo.
T_TETO = SEGUNDOS_LENTOS + te.DOBRA_A_CADA * math.log2(VELOCIDADE_MAXIMA / VELOCIDADE_INICIAL)


def test_as_constantes_sao_as_da_ficha():
    assert (PASSO_TOQUE, LIMITE_TOQUE, VELOCIDADE_INICIAL, SEGUNDOS_LENTOS, te.DOBRA_A_CADA, VELOCIDADE_MAXIMA) == (
        0.01, 0.3, 0.1, 3.0, 2.0, 60.0)
    assert (te.TEMPO_MINIMO, TETO, te.RESOLUCAO, te.JANELA_ENTER_DUPLO) == (0.01, 3600.0, 0.001, 0.4)
    assert T_TETO == pytest.approx(21.4576, abs=1e-4)


# ------------------------------------------------------------------------------------------------ a velocidade
@pytest.mark.parametrize("segundos,esperada", [
    (0.0, 0.1), (1.0, 0.1), (3.0, 0.1),              # os 3 primeiros segundos: lentos e constantes
    (5.0, 0.2), (7.0, 0.4), (9.0, 0.8), (11.0, 1.6),  # depois dobra a cada 2 s
    (15.0, 6.4), (T_TETO, 60.0), (30.0, 60.0), (1000.0, 60.0)])  # e para no teto
def test_a_velocidade_nos_pontos_da_tabela(segundos, esperada):
    assert velocidade(segundos) == pytest.approx(esperada, abs=1e-9)


def test_a_velocidade_so_cresce_e_nunca_passa_do_teto():
    anterior = 0.0
    for decimos in range(0, 3000):
        atual = velocidade(decimos / 10)
        assert VELOCIDADE_INICIAL - 1e-12 <= atual <= VELOCIDADE_MAXIMA + 1e-12
        assert atual >= anterior - 1e-12, decimos / 10
        anterior = atual


@pytest.mark.parametrize("segundos", [SEGUNDOS_LENTOS, T_TETO])
def test_a_velocidade_nao_da_salto_nas_duas_emendas(segundos):
    assert velocidade(segundos - 1e-6) == pytest.approx(velocidade(segundos + 1e-6), rel=1e-5)


def test_tempo_negativo_vale_como_zero():
    assert velocidade(-5.0) == velocidade(0.0)
    assert mudanca_acumulada(-5.0) == mudanca_acumulada(0.0)


# ------------------------------------------------------------------------------------------------ a mudança acumulada
@pytest.mark.parametrize("segundos,esperada", [
    (0.0, 0.01), (0.1, 0.01), (0.29, 0.01), (0.3, 0.01),  # o toque: um passo só
    (0.5, 0.03), (1.0, 0.08), (2.0, 0.18), (3.0, 0.28),   # 0,1 s por segundo
    (5.0, 0.5685), (7.0, 1.1456), (9.0, 2.2998), (11.0, 4.6081), (15.0, 18.4580),
    (T_TETO, 173.1149), (30.0, 685.6566), (60.0, 2485.6566)])
def test_a_mudanca_acumulada_nos_pontos_da_tabela(segundos, esperada):
    assert mudanca_acumulada(segundos) == pytest.approx(esperada, abs=1e-3)


def test_menos_de_0_3_segundo_e_so_um_toque_de_um_passo():
    for centesimos in range(0, 30):
        assert mudanca_acumulada(centesimos / 100) == PASSO_TOQUE


def test_a_mudanca_so_cresce_e_cresce_de_verdade_depois_do_toque():
    anterior = 0.0
    for centesimos in range(0, 8000):
        atual = mudanca_acumulada(centesimos / 100)
        assert atual >= anterior, centesimos / 100
        if centesimos / 100 > LIMITE_TOQUE:
            assert atual > anterior, centesimos / 100
        anterior = atual


@pytest.mark.parametrize("segundos", [1.0, 4.0, 8.0, 14.0, 19.0, 25.0, 40.0])
def test_a_mudanca_e_a_integral_da_velocidade(segundos):
    h = 1e-4
    derivada = (mudanca_acumulada(segundos + h) - mudanca_acumulada(segundos)) / h
    assert derivada == pytest.approx(velocidade(segundos + h / 2), rel=1e-3)


@pytest.mark.parametrize("segundos", [LIMITE_TOQUE, SEGUNDOS_LENTOS, T_TETO])
def test_a_mudanca_nao_da_salto_nas_emendas(segundos):
    # Sem salto: entre um instante antes e um depois da emenda o valor só anda o que a velocidade da emenda permite (no teto, 60 s por s).
    h = 1e-6
    anda = mudanca_acumulada(segundos + h) - mudanca_acumulada(segundos - h)
    assert 0.0 <= anda <= 2 * h * velocidade(segundos + h) * 1.01 + 1e-12


def test_ate_os_3_segundos_a_mudanca_total_e_pequena():
    # O pedido: "os 3 primeiros segundos bem lentos". Segurar 3 s muda menos de 0,3 s no valor.
    assert mudanca_acumulada(SEGUNDOS_LENTOS) < 0.3


# ------------------------------------------------------------------------------------------------ o valor, preso e arredondado
def test_o_valor_depois_de_segurar_e_a_base_mais_ou_menos_a_mudanca():
    assert valor_apos(2.0, -1, 1.0, minimo=0.01) == pytest.approx(1.92, abs=1e-9)
    assert valor_apos(2.0, +1, 1.0, minimo=0.01) == pytest.approx(2.08, abs=1e-9)


def test_o_toque_muda_exatamente_um_passo():
    assert valor_apos(0.5, -1, 0.0, minimo=0.01) == 0.49
    assert valor_apos(0.5, +1, 0.2, minimo=0.01) == 0.51


def test_o_valor_e_arredondado_ao_milissegundo():
    assert valor_apos(0.09325159506108416, -1, 0.0, minimo=0.0) == 0.083
    assert valor_apos(1.0, +1, 0.3333, minimo=0.0) == round(valor_apos(1.0, +1, 0.3333, minimo=0.0), 3)


def test_o_valor_nao_passa_do_minimo_nem_do_teto():
    assert valor_apos(0.05, -1, 10.0, minimo=0.01) == 0.01
    assert valor_apos(0.05, -1, 0.0, minimo=-2.0) == 0.04
    assert valor_apos(-1.995, -1, 1000.0, minimo=-2.0) == -2.0
    assert valor_apos(3500.0, +1, 1000.0, minimo=0.01) == TETO
    assert valor_apos(3500.0, +1, 1000.0, minimo=0.01, maximo=3501.0) == 3501.0


def test_no_limite_o_toque_nao_anda():
    assert valor_apos(0.01, -1, 0.0, minimo=0.01) == 0.01
    assert valor_apos(TETO, +1, 0.0, minimo=0.01) == TETO


def test_o_minimo_pode_ser_negativo_para_a_espera_com_sobreposicao():
    assert valor_apos(-0.6, -1, 1.0, minimo=-1.0) == pytest.approx(-0.68, abs=1e-9)
    assert valor_apos(-0.6, -1, 100.0, minimo=-1.0) == -1.0


def test_segurar_uma_hora_leva_ao_teto_em_menos_de_100_segundos():
    segundos = 0.0
    while valor_apos(0.01, +1, segundos, minimo=0.01) < TETO:
        segundos += 0.5
        assert segundos < 100.0
    assert segundos == pytest.approx(79.0, abs=2.0)  # 21,5 s de rampa até 60 s/s e o resto em linha reta
