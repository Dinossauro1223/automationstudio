"""Ponto 2 — testes de REPRODUÇÃO dos defeitos que a própria infraestrutura de testes encontrou (suíte de regressão permanente).

Complementa `test_ponto1_reproducao.py`. Estes dois achados apareceram quando a medição de cobertura mostrou que as operações
de edição do mapa (mover, reordenar, pré-visualizar) não eram executadas por nenhum teste.

    2.09  A pré-visualização (`AutomationMap.timeline_rows`) ALTERAVA o mapa aberto: reescrevia o início dos comandos.
    2.10  Mover/reordenar comandos (e o `reflow_timeline`) cortavam em zero a distância entre comandos sobrepostos.
          Num mapa gravado a sobreposição é o normal (o mouse se move enquanto a tecla está pressionada), então UM arraste
          de linha reescrevia o início de todos os comandos do mapa.

Legenda dos comentários
-----------------------
[VERMELHO]  falha no AS 25.3 / 25.4 (reproduz o defeito) e passa no 25.5; não pode voltar a falhar.
[VERDE]     já passava e protege o comportamento que a correção não pode quebrar (mapas sem sobreposição).

Os testes de mapa real usam os 3 mapas que o usuário enviou (tests/data/legacy_maps.json.gz). Tudo roda sem GUI e sem input real.
"""
from __future__ import annotations

import copy

import pytest

from automationstudio.core import AutomationMap, Command, InputType, map_from_json

MAPAS = ["Click genshin", "Exemplo — Primeira automação", "Flins combo"]
IDS_MAPAS = ["click-genshin", "exemplo", "flins-combo"]
TOLERANCIA = 1e-9


def _tecla(id_, alvo, inicio, duracao, **extra):
    return Command(id=id_, type=InputType.KEY, target=alvo, start=inicio, duration=duracao, **extra)


def _inicios(mapa):
    return {c.id: c.start for c in mapa.commands}


def _sobreposto():
    """A (0–1,0) e B (0,4–1,4) se sobrepõem em 0,6 s: é o formato de uma gravação (tecla mantida + outra tecla)."""
    return AutomationMap(name="Sobreposto", commands=[
        _tecla("A", "A", 0.0, 1.0), _tecla("B", "B", 0.4, 1.0), _tecla("C", "C", 1.4, 0.5), _tecla("D", "D", 2.0, 0.5)])


def _sem_sobreposicao():
    """A (0–1,0), B (1,5–2,0), C (2,2–2,4): lacunas de 0,0 / 0,5 / 0,2 s."""
    return AutomationMap(name="Sequencial", commands=[
        _tecla("A", "A", 0.0, 1.0), _tecla("B", "B", 1.5, 0.5), _tecla("C", "C", 2.2, 0.2)])


def _arredondado(mapa):
    return [(c.id, round(c.start, 6)) for c in mapa.commands]


# ============================================================================ 2.09 a pré-visualização altera o mapa
@pytest.mark.parametrize("nome", MAPAS, ids=IDS_MAPAS)
def test_p2_09_previsualizar_um_mapa_real_nao_altera_os_inicios(legacy_maps, nome):  # [VERMELHO] Flins combo e Exemplo
    mapa = map_from_json(legacy_maps[nome])
    antes, duracao = _inicios(mapa), mapa.total_duration()
    mapa.timeline_rows()
    mudaram = sorted(i for i, inicio in _inicios(mapa).items() if abs(inicio - antes[i]) > TOLERANCIA)
    assert not mudaram, f"{len(mudaram)} de {len(antes)} comandos mudaram de início só por pré-visualizar (ex.: {mudaram[:3]})"
    assert mapa.total_duration() == pytest.approx(duracao, abs=TOLERANCIA)


def test_p2_09_a_previsualizacao_mostra_o_plano_que_o_motor_executa():  # [VERMELHO]
    mapa = _sobreposto()
    linhas = mapa.timeline_rows()
    assert [(r["id"], r["start"], r["duration"], r["end"]) for r in linhas] == [
        ("A", 0.0, 1.0, 1.0), ("B", 0.4, 1.0, 1.4), ("C", 1.4, 0.5, 1.9), ("D", 2.0, 0.5, 2.5)]


def test_p2_09_a_previsualizacao_so_lista_comandos_ativos():  # [VERDE]
    mapa = _sem_sobreposicao()
    mapa.commands[1].enabled = False
    assert [r["id"] for r in mapa.timeline_rows()] == ["A", "C"]


# ============================================================================ 2.10 sobreposição cortada em zero
@pytest.mark.parametrize("nome", MAPAS, ids=IDS_MAPAS)
def test_p2_10_reordenar_para_a_mesma_ordem_nao_muda_nenhum_inicio(legacy_maps, nome):  # [VERMELHO] Flins combo
    mapa = map_from_json(legacy_maps[nome])
    antes = _inicios(mapa)
    assert mapa.reorder_to_ids([c.id for c in mapa.commands]) is True
    mudaram = sorted(i for i, inicio in _inicios(mapa).items() if abs(inicio - antes[i]) > TOLERANCIA)
    assert not mudaram, f"{len(mudaram)} de {len(antes)} comandos mudaram de início sem a ordem mudar"


@pytest.mark.parametrize("nome", MAPAS, ids=IDS_MAPAS)
def test_p2_10_o_reflow_que_preserva_lacunas_e_a_identidade_em_mapas_reais(legacy_maps, nome):  # [VERMELHO] Flins combo
    mapa = map_from_json(legacy_maps[nome])
    antes = _inicios(mapa)
    mapa.reflow_timeline(True)
    mudaram = sorted(i for i, inicio in _inicios(mapa).items() if abs(inicio - antes[i]) > TOLERANCIA)
    assert not mudaram, f"{len(mudaram)} de {len(antes)} comandos mudaram de início"


def test_p2_10_mover_um_comando_do_mapa_real_so_reajusta_o_trecho_entre_a_posicao_antiga_e_a_nova(legacy_maps):  # [VERMELHO]
    mapa = map_from_json(legacy_maps["Flins combo"])
    ordem, antes, duracao = [c.id for c in mapa.commands], _inicios(mapa), mapa.total_duration()
    de, para = 600, 596  # sobe o comando 600 quatro posições
    assert mapa.move_commands({ordem[de]}, para) == (para, para)
    nova = [c.id for c in mapa.commands]
    assert nova == ordem[:para] + [ordem[de]] + ordem[para:de] + ordem[de + 1:]
    depois = _inicios(mapa)
    fora_do_trecho = [i for i in ordem[:para] + ordem[de + 1:] if abs(depois[i] - antes[i]) > TOLERANCIA]
    assert not fora_do_trecho, f"{len(fora_do_trecho)} comandos fora do trecho movido mudaram de início"
    assert mapa.total_duration() == pytest.approx(duracao, abs=TOLERANCIA)


def test_p2_10_mover_para_o_mesmo_lugar_nao_muda_nenhum_inicio(legacy_maps):  # [VERMELHO]
    mapa = map_from_json(legacy_maps["Flins combo"])
    antes = _inicios(mapa)
    assert mapa.move_commands({mapa.commands[300].id}, 300) == (300, 300)
    assert _inicios(mapa) == antes


def test_p2_10_o_reflow_que_preserva_lacunas_mantem_a_sobreposicao():  # [VERMELHO]
    mapa = _sobreposto()
    mapa.reflow_timeline(True)
    assert [c.start for c in mapa.commands] == [0.0, 0.4, 1.4, 2.0]


def test_p2_10_reordenar_na_mesma_ordem_mantem_a_sobreposicao():  # [VERMELHO]
    mapa = _sobreposto()
    assert mapa.reorder_to_ids(["A", "B", "C", "D"]) is True
    assert [c.start for c in mapa.commands] == [0.0, 0.4, 1.4, 2.0]


def test_p2_10_mover_um_comando_para_cima_preserva_a_distancia_de_cada_um_ao_anterior():  # [VERMELHO]
    mapa = _sobreposto()
    assert mapa.move_commands({"D"}, 2) == (2, 2)
    # D (0,1 s depois do fim de B) entra antes de C; C mantém a distância (0,0) que tinha para o comando anterior.
    assert [c.id for c in mapa.commands] == ["A", "B", "D", "C"]
    assert _arredondado(mapa) == [("A", 0.0), ("B", 0.4), ("D", 1.5), ("C", 2.0)]


def test_p2_10_mover_o_primeiro_comando_para_o_fim_nao_deixa_inicio_negativo():  # [VERDE]
    mapa = _sobreposto()
    assert mapa.move_commands({"A"}, 4) == (3, 3)
    # B passa a ser o primeiro: a sobreposição que tinha com A não pode empurrá-lo para antes do tempo zero.
    assert [c.id for c in mapa.commands] == ["B", "C", "D", "A"]
    assert _arredondado(mapa) == [("B", 0.0), ("C", 1.0), ("D", 1.6), ("A", 2.1)]
    assert all(c.start >= 0 for c in mapa.commands)


def test_p2_10_reordenar_por_ids_preserva_a_distancia_de_cada_um_ao_anterior():  # [VERMELHO]
    mapa = _sobreposto()
    assert mapa.reorder_to_ids(["A", "B", "D", "C"]) is True
    assert _arredondado(mapa) == [("A", 0.0), ("B", 0.4), ("D", 1.5), ("C", 2.0)]


# ---- sem sobreposição: o comportamento que já existia continua o mesmo
@pytest.mark.parametrize("ids,alvo,esperado_ordem,esperado_inicios,retorno", [
    ({"C"}, 0, ["C", "A", "B"], [0.2, 0.4, 1.9], (0, 0)),
    ({"A"}, 3, ["B", "C", "A"], [0.5, 1.2, 1.4], (2, 2)),
    ({"A", "B"}, 3, ["C", "A", "B"], [0.2, 0.4, 1.9], (1, 2)),
    ({"A"}, 2, ["B", "A", "C"], [0.5, 1.0, 2.2], (1, 1)),
], ids=["ultimo-para-o-inicio", "primeiro-para-o-fim", "dois-para-o-fim", "primeiro-para-o-meio"])
def test_p2_10_mover_sem_sobreposicao_continua_igual(ids, alvo, esperado_ordem, esperado_inicios, retorno):  # [VERDE]
    mapa = _sem_sobreposicao()
    assert mapa.move_commands(ids, alvo) == retorno
    assert [c.id for c in mapa.commands] == esperado_ordem
    assert [round(c.start, 6) for c in mapa.commands] == esperado_inicios


def test_p2_10_reflow_sem_preservar_lacunas_continua_encostando_cada_comando_no_anterior():  # [VERDE]
    mapa = _sobreposto()
    mapa.reflow_timeline(False)
    assert [round(c.start, 6) for c in mapa.commands] == [0.0, 1.0, 2.0, 2.5]


def test_p2_10_nenhuma_operacao_muda_o_modelo_alem_dos_inicios(legacy_maps):  # [VERDE]
    mapa = map_from_json(legacy_maps["Flins combo"])
    antes = copy.deepcopy([{**c.to_dict(), "start": 0} for c in mapa.commands])
    mapa.move_commands({mapa.commands[10].id, mapa.commands[11].id}, 20)
    mapa.reorder_to_ids([c.id for c in reversed(mapa.commands)])
    mapa.timeline_rows()
    depois = {c["id"]: c for c in ({**c.to_dict(), "start": 0} for c in mapa.commands)}
    assert sorted(depois) == sorted(c["id"] for c in antes)
    assert all(depois[c["id"]] == c for c in antes)
