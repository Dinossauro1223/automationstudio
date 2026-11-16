"""A espera entre comandos (25.9, teclado T2): `AutomationMap.gap_before`, `min_gap_before` e `set_gap_before`.

A "espera" de um comando é a lacuna do modelo: quanto ele começa depois do fim programado do anterior (o primeiro, depois do
instante 0). Tem sinal: negativa é sobreposição, o normal num mapa gravado. Mudar a espera de UM comando empurra (ou puxa) todos
os seguintes junto; os anteriores, as durações, os atrasos, a ordem e as outras esperas não mudam. É o que a tecla `'` edita
(md/FICHA_TECLADO_T2_25_9.md, seções 3 e 6). Os três mapas reais do usuário são a prova principal: linha por linha.
"""
from __future__ import annotations

import math

import pytest

from automationstudio.core import AutomationMap, Command, InputType, map_from_json

MAPAS = ["Click genshin", "Exemplo — Primeira automação", "Flins combo"]
IDS_MAPAS = ["click-genshin", "exemplo", "flins-combo"]
TOL = 1e-9


def _tecla(id_, inicio, duracao, atraso=0.0):
    return Command(id=id_, type=InputType.KEY, target="E", start=inicio, duration=duracao, delay=atraso)


def _mapa(*comandos):
    return AutomationMap(name="T", commands=list(comandos))


def _tres():
    """A 0–1,0; B começa em 1,5 (0,5 depois do fim de A); C em 2,2 (0,2 depois do fim de B)."""
    return _mapa(_tecla("A", 0.0, 1.0), _tecla("B", 1.5, 0.5), _tecla("C", 2.2, 0.2))


def _sobreposto():
    """A (0–1,0) e B (0,4–1,4) se sobrepõem em 0,6 s: é o formato de uma gravação. C começa quando B termina; D, 0,1 depois de C."""
    return _mapa(_tecla("A", 0.0, 1.0), _tecla("B", 0.4, 1.0), _tecla("C", 1.4, 0.5), _tecla("D", 2.0, 0.5))


def _fora_de_ordem():
    """C está depois de B na lista, mas começa ANTES dele (0,5 contra 1,0): mexer na espera de B não pode jogar C abaixo de zero."""
    return _mapa(_tecla("A", 0.0, 1.0), _tecla("B", 1.0, 1.0), _tecla("C", 0.5, 0.2))


def _inicios(mapa):
    return [c.start for c in mapa.commands]


def _esperas(mapa):
    return [mapa.gap_before(i) for i in range(len(mapa.commands))]


def _perto(a, b, tol=TOL):
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


def _indices(total, passo):
    """Todos os índices de um mapa pequeno; de um grande (933 comandos), um a cada `passo` mais o primeiro e o último."""
    return sorted(set(range(0, total, passo)) | {0, total - 1})


# ------------------------------------------------------------------------------------------------ gap_before
def test_a_espera_do_primeiro_comando_e_o_proprio_inicio():
    assert _tres().gap_before(0) == 0.0
    assert _mapa(_tecla("A", 0.7, 1.0)).gap_before(0) == pytest.approx(0.7, abs=TOL)


def test_a_espera_e_a_distancia_do_inicio_ao_fim_programado_do_anterior():
    assert _perto(_esperas(_tres()), [0.0, 0.5, 0.2])


def test_o_atraso_do_anterior_faz_parte_do_fim_programado():
    mapa = _tres()
    mapa.commands[0].delay = 0.2  # o fim programado de A passa a ser 1,2
    assert _perto(_esperas(mapa), [0.0, 0.3, 0.2])


def test_a_espera_negativa_e_a_sobreposicao():
    assert _perto(_esperas(_sobreposto()), [0.0, -0.6, 0.0, 0.1])


def test_a_espera_do_comando_desativado_conta_como_a_dos_outros():
    mapa = _tres()
    mapa.commands[1].enabled = False
    assert _perto(_esperas(mapa), [0.0, 0.5, 0.2])


@pytest.mark.parametrize("nome", MAPAS, ids=IDS_MAPAS)
def test_a_espera_e_a_mesma_lacuna_que_o_reflow_preserva_nos_mapas_reais(legacy_maps, nome):
    mapa = map_from_json(legacy_maps[nome])
    lacunas = mapa._gaps_before(mapa.commands)
    assert [mapa.gap_before(i) for i in range(len(mapa.commands))] == [lacunas[id(c)] for c in mapa.commands]


def test_exemplo_a_abertura_do_aplicativo_e_o_texto_se_sobrepoem_em_1_2_segundo(legacy_maps):
    # Abrir aplicativo ocupa 1,3 s (estabilidade 1,0 + segurança 0,3); o texto começa em 0,1: esperaria -1,2 s.
    mapa = map_from_json(legacy_maps["Exemplo — Primeira automação"])
    assert [c.type for c in mapa.commands] == [InputType.APP_OPEN, InputType.TEXT]
    assert mapa.gap_before(0) == 0.0
    assert mapa.gap_before(1) == pytest.approx(-1.2, abs=TOL)


def test_flins_o_primeiro_comando_comeca_em_0_7014_e_quase_metade_das_esperas_e_sobreposicao(legacy_maps):
    mapa = map_from_json(legacy_maps["Flins combo"])
    assert mapa.gap_before(0) == pytest.approx(0.7013775, abs=1e-6)
    assert sum(1 for g in _esperas(mapa) if g < 0) == 444  # 444 das 933 esperas são sobreposições: o motivo de a espera ter sinal


@pytest.mark.parametrize("chamada", ["gap_before", "min_gap_before"])
@pytest.mark.parametrize("indice", [-1, 3, 10 ** 6])
def test_indice_fora_do_mapa_e_recusado_na_consulta(chamada, indice):
    with pytest.raises(IndexError):
        getattr(_tres(), chamada)(indice)


def test_mapa_vazio_nao_tem_espera_para_consultar():
    with pytest.raises(IndexError):
        AutomationMap(name="vazio").gap_before(0)


# ------------------------------------------------------------------------------------------------ min_gap_before
def test_o_minimo_poe_o_comando_em_zero():
    mapa = _tres()
    assert [mapa.min_gap_before(i) for i in range(3)] == pytest.approx([0.0, -1.0, -2.0], abs=TOL)  # menos o fim do anterior


def test_o_minimo_de_um_mapa_sobreposto_e_o_fim_do_anterior():
    mapa = _sobreposto()
    assert [mapa.min_gap_before(i) for i in range(4)] == pytest.approx([0.0, -1.0, -1.4, -1.9], abs=TOL)


def test_o_minimo_considera_o_seguinte_que_comeca_antes():
    # Com B em -1,0 o C (que começa 0,5 antes de B) iria para -0,5: o piso é -0,5 e não -1,0 (o fim de A).
    assert _fora_de_ordem().min_gap_before(1) == pytest.approx(-0.5, abs=TOL)


@pytest.mark.parametrize("nome", MAPAS, ids=IDS_MAPAS)
def test_o_minimo_nunca_passa_da_espera_atual(legacy_maps, nome):
    mapa = map_from_json(legacy_maps[nome])
    for i in range(len(mapa.commands)):
        assert mapa.min_gap_before(i) <= mapa.gap_before(i) + TOL, i


def test_num_mapa_com_inicio_negativo_o_minimo_nao_obriga_a_subir():
    # Início negativo é um mapa inválido (a validação o aponta); mesmo assim o piso nunca fica acima do valor que o comando tem.
    mapa = _mapa(_tecla("A", 1.0, 1.0), _tecla("B", -0.5, 0.2))
    assert mapa.min_gap_before(1) <= mapa.gap_before(1)


# ------------------------------------------------------------------------------------------------ set_gap_before
@pytest.mark.parametrize("fabrica", [_tres, _sobreposto, _fora_de_ordem], ids=["tres", "sobreposto", "fora-de-ordem"])
def test_a_mesma_espera_nao_muda_nenhum_inicio(fabrica):
    mapa = fabrica()
    antes = _inicios(mapa)
    for i in range(len(mapa.commands)):
        mapa.set_gap_before(i, mapa.gap_before(i))
        assert _inicios(mapa) == antes, i


def test_mais_espera_empurra_o_comando_e_todos_os_seguintes():
    mapa = _tres()
    mapa.set_gap_before(1, 1.0)
    assert _perto(_inicios(mapa), [0.0, 2.0, 2.7])


def test_menos_espera_puxa_o_comando_e_os_seguintes():
    mapa = _tres()
    mapa.set_gap_before(1, 0.0)
    assert _perto(_inicios(mapa), [0.0, 1.0, 1.7])


def test_so_a_espera_do_comando_muda():
    mapa = _tres()
    mapa.set_gap_before(1, 1.0)
    assert _perto(_esperas(mapa), [0.0, 1.0, 0.2])


def test_a_sobreposicao_dos_outros_comandos_e_mantida():
    mapa = _sobreposto()
    mapa.set_gap_before(2, 0.3)
    assert _perto(_inicios(mapa), [0.0, 0.4, 1.7, 2.3])
    assert _perto(_esperas(mapa), [0.0, -0.6, 0.3, 0.1])


def test_o_primeiro_comando_recebe_o_proprio_inicio_como_espera():
    mapa = _tres()
    mapa.set_gap_before(0, 0.25)
    assert _perto(_inicios(mapa), [0.25, 1.75, 2.45])


def test_o_atraso_do_anterior_e_respeitado():
    mapa = _tres()
    mapa.commands[0].delay = 0.2
    mapa.set_gap_before(1, 0.5)  # B começa 0,5 depois do fim programado de A (1,0 + 0,2)
    assert mapa.commands[1].start == pytest.approx(1.7, abs=TOL)


def test_o_comando_desativado_tambem_anda_com_os_outros():
    mapa = _tres()
    mapa.commands[2].enabled = False
    mapa.set_gap_before(1, 1.0)
    assert mapa.commands[2].start == pytest.approx(2.7, abs=TOL)


def test_a_ordem_as_duracoes_e_os_atrasos_nao_mudam():
    mapa = _sobreposto()
    mapa.commands[1].delay = 0.05
    antes = [(c.id, c.duration, c.delay, c.target, c.enabled) for c in mapa.commands]
    mapa.set_gap_before(2, 0.75)
    assert [(c.id, c.duration, c.delay, c.target, c.enabled) for c in mapa.commands] == antes


def test_no_minimo_o_comando_comeca_em_zero_e_os_seguintes_mantem_as_esperas():
    mapa = _tres()
    mapa.set_gap_before(1, -1.0)
    assert _perto(_inicios(mapa), [0.0, 0.0, 0.7])
    assert _perto(_esperas(mapa), [0.0, -1.0, 0.2])


def test_abaixo_do_minimo_e_recusado_e_nada_muda():
    mapa = _tres()
    antes = _inicios(mapa)
    with pytest.raises(ValueError):
        mapa.set_gap_before(1, -1.0 - 1e-6)
    assert _inicios(mapa) == antes


def test_o_minimo_vale_tambem_para_o_seguinte_que_comeca_antes():
    mapa = _fora_de_ordem()
    antes = _inicios(mapa)
    with pytest.raises(ValueError):
        mapa.set_gap_before(1, -0.6)  # C iria para -0,1
    assert _inicios(mapa) == antes
    mapa.set_gap_before(1, -0.5)
    assert _perto(_inicios(mapa), [0.0, 0.5, 0.0])


@pytest.mark.parametrize("valor", [math.nan, math.inf, -math.inf], ids=["nan", "mais-infinito", "menos-infinito"])
def test_valor_que_nao_e_numero_finito_e_recusado(valor):
    mapa = _tres()
    antes = _inicios(mapa)
    with pytest.raises(ValueError):
        mapa.set_gap_before(1, valor)
    assert _inicios(mapa) == antes


@pytest.mark.parametrize("indice", [-1, 3, 10 ** 6])
def test_indice_fora_do_mapa_e_recusado_na_alteracao(indice):
    mapa = _tres()
    antes = _inicios(mapa)
    with pytest.raises(IndexError):
        mapa.set_gap_before(indice, 1.0)
    assert _inicios(mapa) == antes


def test_a_duracao_total_acompanha_o_empurrao():
    mapa = _tres()
    total = mapa.total_duration()
    mapa.set_gap_before(1, 1.0)
    assert mapa.total_duration() == pytest.approx(total + 0.5, abs=TOL)


# ------------------------------------------------------------------------------------------------ nos mapas reais, linha por linha
@pytest.mark.parametrize("nome,passo", [(MAPAS[0], 1), (MAPAS[1], 1), (MAPAS[2], 7)], ids=IDS_MAPAS)
def test_mais_meio_segundo_de_espera_em_cada_comando_do_mapa_real_empurra_so_ele_e_os_seguintes(legacy_maps, nome, passo):
    mapa = map_from_json(legacy_maps[nome])
    original = _inicios(mapa)
    ordem = [(c.id, c.duration, c.delay) for c in mapa.commands]
    total = len(original)
    for i in _indices(total, passo):
        espera = mapa.gap_before(i)
        vizinhas = range(max(0, i - 1), min(total, i + 3))
        esperas_antes = {k: mapa.gap_before(k) for k in vizinhas}
        antes = _inicios(mapa)  # logo antes da operação: voltar a espera não devolve os bits (ruído de 1e-16), então não é `original`
        mapa.set_gap_before(i, espera + 0.5)
        depois = _inicios(mapa)
        assert depois[:i] == antes[:i], f"{nome}: um comando ANTES da linha {i} mudou de início"
        assert _perto(depois[i:], [x + 0.5 for x in antes[i:]]), f"{nome}: a partir da linha {i} nem todos andaram 0,5 s"
        for k in vizinhas:  # as vizinhas: só a espera da própria linha mudou
            esperado = esperas_antes[k] + (0.5 if k == i else 0.0)
            assert mapa.gap_before(k) == pytest.approx(esperado, abs=TOL), f"{nome}: a espera da linha {k} (alterada: {i})"
        assert [(c.id, c.duration, c.delay) for c in mapa.commands] == ordem
        mapa.set_gap_before(i, espera)
        assert _perto(_inicios(mapa), original), f"{nome}: voltar a espera da linha {i} não restaurou o mapa"


@pytest.mark.parametrize("nome,passo", [(MAPAS[0], 1), (MAPAS[1], 1), (MAPAS[2], 7)], ids=IDS_MAPAS)
def test_a_espera_minima_de_cada_comando_do_mapa_real_e_aceita_e_poe_o_primeiro_inicio_em_zero(legacy_maps, nome, passo):
    mapa = map_from_json(legacy_maps[nome])
    original = _inicios(mapa)
    for i in _indices(len(original), passo):
        espera, minimo = mapa.gap_before(i), mapa.min_gap_before(i)
        mapa.set_gap_before(i, minimo)
        assert min(_inicios(mapa)[i:]) == pytest.approx(0.0, abs=TOL), f"{nome}: a espera mínima da linha {i} não zerou o mais cedo"
        assert min(_inicios(mapa)) >= 0.0
        mapa.set_gap_before(i, espera)
        assert _perto(_inicios(mapa), original)


@pytest.mark.parametrize("nome,passo", [(MAPAS[0], 1), (MAPAS[1], 1), (MAPAS[2], 7)], ids=IDS_MAPAS)
def test_um_pouco_abaixo_da_espera_minima_de_cada_comando_do_mapa_real_e_recusado(legacy_maps, nome, passo):
    mapa = map_from_json(legacy_maps[nome])
    original = _inicios(mapa)
    for i in _indices(len(original), passo):
        with pytest.raises(ValueError):
            mapa.set_gap_before(i, mapa.min_gap_before(i) - 0.001)
        assert _inicios(mapa) == original


def test_exemplo_a_espera_minima_do_texto_poe_o_texto_em_zero(legacy_maps):
    mapa = map_from_json(legacy_maps["Exemplo — Primeira automação"])
    assert mapa.min_gap_before(1) == pytest.approx(-1.3, abs=TOL)
    mapa.set_gap_before(1, -1.3)
    assert mapa.commands[1].start == 0.0
    mapa.set_gap_before(1, -1.2)
    assert mapa.commands[1].start == pytest.approx(0.1, abs=TOL)


def test_o_mapa_real_continua_valido_depois_de_mudar_a_espera(legacy_maps):
    mapa = map_from_json(legacy_maps["Click genshin"])
    assert mapa.validate() == []
    mapa.set_gap_before(3, mapa.gap_before(3) + 0.25)
    assert mapa.validate() == []
