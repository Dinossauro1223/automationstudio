"""Operações de edição do modelo: o que a tabela, a Timeline e o menu "Mais…" chamam (copiar, colar, exportar, importar,
remover, mover) e as validações que ficavam sem teste.

Até a 25.5 nenhum teste executava estas funções (a medição de cobertura mostrou 0% nelas) e dois defeitos moravam ali
(achados 2.09 e 2.10, reproduzidos em tests/regression/test_ponto2_achados.py). Os valores esperados foram calculados à mão
a partir da regra de cada função, não copiados da saída do código.

Mapa de exemplo (`_mapa`): A (0,0–1,0 s), B (1,5–2,0 s), C (2,2–2,4 s).
"""
from __future__ import annotations

import json
import sys
import types

import pytest

from automationstudio import core
from automationstudio.conditions import WaitCondition, WaitConditionType
from automationstudio.core import (COMMAND_EXPORT_VERSION, ActionType, AutomationMap, Command, CommandGroup, EventKind,
                                   InputType, InvalidStateTransition, State, StateManager, _IdCounter, build_timeline,
                                   resolve_key_labels)


def _tecla(id_, alvo, inicio, duracao, **extra):
    return Command(id=id_, type=InputType.KEY, target=alvo, start=inicio, duration=duracao, **extra)


def _mapa():
    return AutomationMap(name="M", commands=[_tecla("A", "A", 0.0, 1.0), _tecla("B", "B", 1.5, 0.5), _tecla("C", "C", 2.2, 0.2)])


def _ids(mapa):
    return [c.id for c in mapa.commands]


def _inicios(mapa):
    return [(c.id, round(c.start, 6)) for c in mapa.commands]


# ================================================================================================ consultas
def test_get_command_acha_pelo_id_e_devolve_none_se_nao_existe():
    mapa = _mapa()
    assert mapa.get_command("B") is mapa.commands[1]
    assert mapa.get_command("Z") is None


def test_get_commands_by_ids_devolve_na_ordem_do_mapa_e_ignora_o_que_nao_existe():
    mapa = _mapa()
    assert [c.id for c in mapa.get_commands_by_ids(["C", "A", "Z"])] == ["A", "C"]
    assert [c.id for c in mapa.get_commands_by_ids(("B",))] == ["B"]
    assert mapa.get_commands_by_ids(set()) == []


def test_command_ids_in_order_segue_a_ordem_do_mapa():
    assert _mapa().command_ids_in_order() == ["A", "B", "C"]


def test_group_name_devolve_o_nome_do_grupo_ou_vazio():
    mapa = _mapa()
    mapa.groups = {"g1": CommandGroup(id="g1", name="Combo")}
    assert mapa.group_name("g1") == "Combo"
    assert mapa.group_name("g2") == ""


# ================================================================================================ inserir e remover um
def test_add_command_acrescenta_no_fim():
    mapa, novo = _mapa(), _tecla("N", "N", 3.0, 0.1)
    mapa.add_command(novo)
    assert mapa.commands[-1] is novo and len(mapa.commands) == 4


@pytest.mark.parametrize("indice,posicao", [(None, 3), (0, 0), (1, 1), (3, 3), (-5, 0), (99, 3)],
                         ids=["sem-indice", "inicio", "meio", "fim", "negativo", "alem-do-fim"])
def test_insert_command_devolve_o_indice_final_e_limita_ao_intervalo(indice, posicao):
    mapa, novo = _mapa(), _tecla("N", "N", 9.0, 0.1)
    assert mapa.insert_command(novo, indice) == posicao
    assert mapa.commands[posicao] is novo and len(mapa.commands) == 4
    assert novo.start == 9.0  # inserir não mexe nos tempos de ninguém


def test_remove_command_devolve_se_removeu():
    mapa = _mapa()
    assert mapa.remove_command("B") is True
    assert _ids(mapa) == ["A", "C"]
    assert mapa.remove_command("B") is False
    assert _ids(mapa) == ["A", "C"]


# ================================================================================================ copiar e colar
def test_copy_commands_copia_com_ids_novos_e_inicios_relativos_a_selecao():
    mapa = _mapa()
    copias = mapa.copy_commands({"C", "B"})
    assert [c.target for c in copias] == ["B", "C"]  # ordem do mapa, não a da seleção
    assert [round(c.start, 6) for c in copias] == [0.0, 0.7]  # 1,5 vira 0 e 2,2 vira 0,7
    assert len({c.id for c in copias}) == 2 and not ({c.id for c in copias} & {"A", "B", "C"})
    assert _inicios(mapa) == [("A", 0.0), ("B", 1.5), ("C", 2.2)]  # o mapa não muda


def test_copy_commands_e_uma_copia_profunda():
    mapa = _mapa()
    mapa.commands[1].mouse_path = [{"t": 0.0, "x": 1, "y": 2}]
    copia = mapa.copy_commands({"B"})[0]
    copia.mouse_path[0]["x"] = 99
    assert mapa.commands[1].mouse_path[0]["x"] == 1


def test_copy_commands_sem_selecao_valida_devolve_lista_vazia():
    assert _mapa().copy_commands(set()) == []
    assert _mapa().copy_commands({"Z"}) == []


def _bloco():
    return [_tecla("X", "X", 0.0, 0.3), _tecla("Y", "Y", 0.5, 0.3)]


def test_insert_commands_no_fim_encosta_o_bloco_no_fim_do_ultimo_comando():
    mapa, bloco = _mapa(), _bloco()
    inseridos = mapa.insert_commands(bloco)
    assert [c.target for c in mapa.commands] == ["A", "B", "C", "X", "Y"]
    assert [round(c.start, 6) for c in inseridos] == [2.4, 2.9]  # fim de C (2,4) + 0 e + 0,5
    assert all(a is b for a, b in zip(inseridos, mapa.commands[3:]))
    assert not ({c.id for c in inseridos} & {"X", "Y"})  # IDs novos
    assert [(c.id, c.start) for c in bloco] == [("X", 0.0), ("Y", 0.5)]  # o bloco original não é alterado


def test_insert_commands_no_meio_nao_desloca_os_comandos_seguintes():
    mapa = _mapa()
    inseridos = mapa.insert_commands(_bloco(), index=1)
    assert [c.target for c in mapa.commands] == ["A", "X", "Y", "B", "C"]
    assert [round(c.start, 6) for c in inseridos] == [1.0, 1.5]  # fim de A (1,0)
    assert [round(c.start, 6) for c in mapa.commands[3:]] == [1.5, 2.2]  # B e C ficam onde estavam (podem se sobrepor)


def test_insert_commands_no_inicio_comeca_em_zero():
    mapa = _mapa()
    inseridos = mapa.insert_commands(_bloco(), index=0)
    assert _ids(mapa)[2:] == ["A", "B", "C"]
    assert [round(c.start, 6) for c in inseridos] == [0.0, 0.5]


def test_insert_commands_sem_ancora_comeca_em_zero_mesmo_no_fim():
    mapa = _mapa()
    inseridos = mapa.insert_commands(_bloco(), anchor_to_previous=False)
    assert [c.target for c in mapa.commands][-2:] == ["X", "Y"]
    assert [round(c.start, 6) for c in inseridos] == [0.0, 0.5]


@pytest.mark.parametrize("indice,posicao", [(-3, 0), (50, 3)], ids=["negativo", "alem-do-fim"])
def test_insert_commands_limita_o_indice_ao_intervalo(indice, posicao):
    mapa = _mapa()
    inseridos = mapa.insert_commands(_bloco(), index=indice)
    assert mapa.commands[posicao] is inseridos[0] and len(mapa.commands) == 5


def test_insert_commands_com_lista_vazia_nao_faz_nada():
    mapa = _mapa()
    assert mapa.insert_commands([]) == []
    assert _ids(mapa) == ["A", "B", "C"]


def test_duplicate_commands_sem_selecao_valida_devolve_lista_vazia():
    mapa = _mapa()
    assert mapa.duplicate_commands(set()) == [] and mapa.duplicate_commands({"Z"}) == []
    assert _ids(mapa) == ["A", "B", "C"]


def test_duplicate_commands_no_meio_encosta_a_copia_no_fim_do_comando_anterior():
    mapa = _mapa()
    copias = mapa.duplicate_commands({"B"}, insert_at=1)
    assert [c.target for c in mapa.commands] == ["A", "B", "B", "C"]
    assert mapa.commands[1] is copias[0] and copias[0].id != "B"
    assert round(copias[0].start, 6) == 1.0  # fim de A


def test_duplicate_commands_com_indice_negativo_comeca_em_zero():
    mapa = _mapa()
    copias = mapa.duplicate_commands({"B"}, insert_at=-4)
    assert mapa.commands[0] is copias[0] and copias[0].start == 0.0


# ================================================================================================ exportar e importar (.ascommands)
def _mapa_com_grupos():
    mapa = _mapa()
    mapa.groups = {"g1": CommandGroup(id="g1", name="Um"), "g2": CommandGroup(id="g2", name="Dois")}
    mapa.commands[1].group_id, mapa.commands[1].group = "g1", "Um"
    return mapa


def test_export_commands_monta_o_pacote_com_inicios_relativos_e_so_os_grupos_usados():
    mapa = _mapa_com_grupos()
    pacote = mapa.export_commands({"B", "C"})
    assert pacote["format"] == "AutomationStudio commands" and pacote["version"] == COMMAND_EXPORT_VERSION
    assert [c["id"] for c in pacote["commands"]] == ["B", "C"]
    assert [round(c["start"], 6) for c in pacote["commands"]] == [0.0, 0.7]
    assert list(pacote["groups"]) == ["g1"]  # g2 não é usado por B nem por C
    assert mapa.commands[1].start == 1.5  # exportar não altera o mapa


def test_export_commands_ignora_grupo_que_o_mapa_nao_conhece():
    mapa = _mapa()
    mapa.commands[0].group_id = "fantasma"
    assert mapa.export_commands({"A"})["groups"] == {}


def test_export_commands_sem_selecao_gera_pacote_vazio():
    pacote = _mapa().export_commands({"Z"})
    assert pacote["commands"] == [] and pacote["groups"] == {}


def test_exportar_e_importar_devolve_os_mesmos_comandos_e_grupos():
    mapa = _mapa_com_grupos()
    pacote = json.loads(json.dumps(mapa.export_commands({"B", "C"})))  # passa por texto, como no arquivo
    comandos, grupos = AutomationMap.import_commands(pacote)
    assert [c.to_dict() for c in comandos] == pacote["commands"]
    assert list(grupos) == ["g1"] and grupos["g1"].to_dict() == mapa.groups["g1"].to_dict()


@pytest.mark.parametrize("pacote", [None, [], "texto", {}, {"format": "outro"}, {"format": "automationstudio commands"}],
                         ids=["none", "lista", "texto", "vazio", "outro-formato", "caixa-diferente"])
def test_import_commands_recusa_o_que_nao_e_um_pacote_de_comandos(pacote):
    with pytest.raises(ValueError) as erro:
        AutomationMap.import_commands(pacote)
    assert "incompatível" in str(erro.value)


def test_import_commands_ignora_entradas_que_nao_sao_objetos():
    pacote = {"format": "AutomationStudio commands", "version": 1,
              "commands": [{"id": "K1", "type": "key", "target": "A", "duration": 0.1}, "lixo", 5, None],
              "groups": {"g1": {"id": "g1", "name": "Um"}, "g2": "lixo"}}
    comandos, grupos = AutomationMap.import_commands(pacote)
    assert [c.id for c in comandos] == ["K1"]
    assert list(grupos) == ["g1"] and grupos["g1"].name == "Um"


def test_import_commands_sem_comandos_nem_grupos_devolve_vazio():
    assert AutomationMap.import_commands({"format": "AutomationStudio commands"}) == ([], {})


# ================================================================================================ mover e reordenar (entradas inválidas e limites)
@pytest.mark.parametrize("ids", [set(), {"Z"}], ids=["sem-ids", "id-inexistente"])
def test_move_commands_sem_comando_valido_devolve_none_e_nao_mexe_no_mapa(ids):
    mapa = _mapa()
    assert mapa.move_commands(ids, 1) is None
    assert _inicios(mapa) == [("A", 0.0), ("B", 1.5), ("C", 2.2)]


def test_move_commands_em_mapa_vazio_devolve_none():
    assert AutomationMap(name="V").move_commands({"A"}, 0) is None


@pytest.mark.parametrize("alvo,ordem,faixa", [(-7, ["C", "A", "B"], (0, 0)), (0, ["C", "A", "B"], (0, 0)),
                                              (3, ["A", "B", "C"], (2, 2)), (99, ["A", "B", "C"], (2, 2))],
                         ids=["negativo", "zero", "fim", "alem-do-fim"])
def test_move_commands_limita_o_alvo_ao_intervalo(alvo, ordem, faixa):
    mapa = _mapa()
    assert mapa.move_commands({"C"}, alvo) == faixa
    assert _ids(mapa) == ordem


@pytest.mark.parametrize("ordem", [[], ["A", "B"], ["A", "B", "C", "D"], ["A", "B", "Z"], ["A", "A", "B"]],
                         ids=["vazia", "faltando-um", "sobrando-um", "id-desconhecido", "id-repetido"])
def test_reorder_to_ids_recusa_ordem_que_nao_e_uma_permutacao_dos_comandos(ordem):
    mapa = _mapa()
    assert mapa.reorder_to_ids(ordem) is False
    assert _ids(mapa) == ["A", "B", "C"] and _inicios(mapa) == [("A", 0.0), ("B", 1.5), ("C", 2.2)]


def test_reorder_to_ids_sem_sobreposicao_reencadeia_a_partir_da_lacuna_de_cada_um():
    mapa = _mapa()  # lacunas: A 0,0 / B 0,5 / C 0,2
    assert mapa.reorder_to_ids(["C", "B", "A"]) is True
    # C abre em 0,2 (a lacuna que tinha); B = fim de C (0,4) + 0,5; A = fim de B (0,9 + 0,5) + 0,0
    assert _inicios(mapa) == [("C", 0.2), ("B", 0.9), ("A", 1.4)]


def test_reflow_em_mapa_vazio_nao_faz_nada():
    mapa = AutomationMap(name="V")
    mapa.reflow_timeline(True)
    mapa.reflow_timeline(False)
    assert mapa.commands == []


def test_mover_nunca_deixa_inicio_negativo_no_meio_da_sequencia():
    # B está 0,5 s sobreposto a A (lacuna -0,5). Colocado logo depois de Z, que termina em 0,1, B cairia em -0,4.
    mapa = AutomationMap(name="M", commands=[_tecla("A", "A", 0.0, 0.5), _tecla("B", "B", 0.0, 0.2), _tecla("Z", "Z", 0.2, 0.1)])
    assert mapa.reorder_to_ids(["Z", "B", "A"]) is True
    assert _inicios(mapa) == [("Z", 0.0), ("B", 0.0), ("A", 0.2)]
    assert all(c.start >= 0 for c in mapa.commands)


# ================================================================================================ remover vários
def test_remove_commands_com_ids_inexistentes_nao_remove_nem_desloca():
    mapa = _mapa()
    assert mapa.remove_commands({"Z"}) == []
    assert _inicios(mapa) == [("A", 0.0), ("B", 1.5), ("C", 2.2)]


def test_remove_commands_sem_compactar_nao_desloca_ninguem():
    mapa = _mapa()
    removidos = mapa.remove_commands({"A"}, compact=False)
    assert [c.id for c in removidos] == ["A"]
    assert _inicios(mapa) == [("B", 1.5), ("C", 2.2)]


def test_remove_commands_compactando_desloca_quem_comeca_depois_do_trecho_removido():
    mapa = _mapa()
    mapa.remove_commands({"A"}, compact=True)  # o trecho removido (0–1,0) tinha 1,0 s
    assert _inicios(mapa) == [("B", 0.5), ("C", 1.2)]


def test_remove_commands_une_os_trechos_removidos_que_se_sobrepoem():
    mapa = AutomationMap(name="M", commands=[
        _tecla("A", "A", 0.0, 1.0), _tecla("B", "B", 0.5, 1.0), _tecla("D", "D", 1.0, 0.2), _tecla("C", "C", 2.0, 0.5)])
    removidos = mapa.remove_commands({"B", "A"}, compact=True)
    assert [c.id for c in removidos] == ["A", "B"]
    # A e B cobrem 0–1,5 (1,5 s, e não 2,0). D começa dentro desse trecho (1,0), então não se move; C (2,0) volta 1,5.
    assert _inicios(mapa) == [("D", 1.0), ("C", 0.5)]


def test_remove_commands_soma_os_trechos_removidos_separados():
    mapa = AutomationMap(name="M", commands=[
        _tecla("A", "A", 0.0, 1.0), _tecla("B", "B", 2.0, 1.0), _tecla("C", "C", 4.0, 1.0), _tecla("D", "D", 6.0, 1.0)])
    mapa.remove_commands({"A", "C"}, compact=True)
    assert _inicios(mapa) == [("B", 1.0), ("D", 4.0)]  # B perde o trecho de A (1,0); D perde os de A e de C (2,0)


# ================================================================================================ validação do mapa e do comando
@pytest.mark.parametrize("campos,trecho", [({"name": "  "}, "sem nome"), ({"repeat_count": 0}, "repeat_count"),
                                           ({"repeat_interval": -0.1}, "repeat_interval"), ({"speed": 0.0}, "speed"),
                                           ({"speed": -1.0}, "speed")],
                         ids=["sem-nome", "repeticao-zero", "intervalo-negativo", "velocidade-zero", "velocidade-negativa"])
def test_mapa_invalido_aponta_o_campo(campos, trecho):
    mapa = AutomationMap(**{"name": "M", "commands": [_tecla("A", "A", 0.0, 0.1)], **campos})
    erros = mapa.validate()
    assert len(erros) == 1 and trecho in erros[0]
    assert mapa.is_valid() is False


def test_mapa_valido_nao_tem_erros():
    mapa = _mapa()
    assert mapa.validate() == [] and mapa.is_valid() is True


def test_rolagem_sem_direcao_nem_quantidade_e_erro():
    assert any("rolagem do mouse sem direção" in e for e in Command(type=InputType.MOUSE_SCROLL).validate())
    assert Command(type=InputType.MOUSE_SCROLL, scroll_dx=-2).validate() == []


def test_atraso_negativo_e_erro():
    assert any("atraso negativo" in e for e in _tecla("K", "A", 0.0, 0.1, delay=-0.1).validate())


def test_valores_negativos_da_espera_de_processo_so_sao_conferidos_com_um_processo():
    campos = dict(type=InputType.APP_OPEN, target="x.exe", wait_timeout=-1.0, wait_stable_ms=-1, wait_after_open=-1.0)
    assert Command(**campos).validate() == []  # sem `wait_process` a barreira legada não existe
    erros = Command(wait_process="x.exe", **campos).validate()
    assert len(erros) == 3
    assert any("timeout" in e for e in erros) and any("estabilidade" in e for e in erros) and any("após abertura" in e for e in erros)


def test_erros_da_condicao_vem_prefixados_com_o_id_do_comando():
    comando = Command(id="K", type=InputType.WAIT, conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=-1.0)])
    assert comando.validate() == ["[K] Timeout da condição não pode ser negativo."]


@pytest.mark.parametrize("bruto,esperado", [("InputType.MOUSE_MOVE", InputType.MOUSE_MOVE), ("mouse_scroll", InputType.MOUSE_SCROLL),
                                            ("KEY", InputType.KEY), ("zzz", InputType.KEY), (None, InputType.KEY)],
                         ids=["com-prefixo", "minusculo", "maiusculo", "desconhecido", "none"])
def test_command_normaliza_o_tipo_recebido_como_texto(bruto, esperado):
    assert Command(type=bruto).type == esperado


@pytest.mark.parametrize("bruto,esperado", [("ActionType.PRESS", ActionType.PRESS), ("release", ActionType.RELEASE),
                                            ("press_and_release", ActionType.PRESS_AND_RELEASE),
                                            ("zzz", ActionType.PRESS_AND_RELEASE)],
                         ids=["com-prefixo", "minusculo", "completo", "desconhecido"])
def test_command_normaliza_a_acao_recebida_como_texto(bruto, esperado):
    assert Command(action=bruto).action == esperado


def test_from_dict_com_valores_de_espera_ilegiveis_volta_ao_padrao():
    comando = Command.from_dict({"type": "app_open", "target": "x.exe", "wait_stable_ms": "abc", "wait_after_open": "x"})
    assert comando.wait_stable_ms == 1000 and comando.wait_after_open == pytest.approx(0.30)


# ================================================================================================ condições de espera
def _imagem(**parametros):
    return WaitCondition(type=WaitConditionType.IMAGE, parameters={"image_path": "a.png", **parametros})


@pytest.mark.parametrize("condicao,trecho", [
    (WaitCondition(type=WaitConditionType.DELAY, timeout=-1.0), "Timeout"),
    (WaitCondition(type=WaitConditionType.DELAY, stable_ms=-1, after=1.0), "Estabilidade"),
    (WaitCondition(type=WaitConditionType.DELAY, after=-1.0, timeout=1.0), "Atraso posterior"),
    (WaitCondition(type=WaitConditionType.DELAY), "precisa de um valor maior que zero"),
    (WaitCondition(type=WaitConditionType.PROCESS), "sem comando de referência"),
    (WaitCondition(type=WaitConditionType.IMAGE), "sem arquivo"),
    (_imagem(confidence=1.5), "Precisão"),
    (_imagem(search="sim"), "Modo de busca"),
    (_imagem(interval=-1.0), "Intervalo"),
    (_imagem(region="x"), "Região da imagem inválida"),
    (_imagem(region={"w": -1}), "Largura/altura"),
], ids=["timeout", "estabilidade", "atraso", "atraso-zerado", "processo-sem-alvo", "imagem-sem-arquivo", "precisao", "busca",
        "intervalo", "regiao-nao-e-objeto", "regiao-negativa"])
def test_condicao_invalida_aponta_o_problema(condicao, trecho):
    assert any(trecho in erro for erro in condicao.validate())


@pytest.mark.parametrize("condicao", [
    WaitCondition(type=WaitConditionType.DELAY, after=0.2),
    WaitCondition(type=WaitConditionType.PROCESS, target="notepad.exe"),
    WaitCondition(type=WaitConditionType.PROCESS, parameters={"command_id": "cmd_1"}),
    _imagem(),
    _imagem(confidence=0.8, interval=0.2, search=True, region={"x": 1, "y": 2, "w": 30, "h": 40}),
], ids=["atraso", "processo-por-alvo", "processo-por-comando", "imagem-padrao", "imagem-completa"])
def test_condicao_valida_nao_tem_erros(condicao):
    assert condicao.validate() == []


@pytest.mark.parametrize("dados", [None, "texto", 5, []], ids=["none", "texto", "numero", "lista"])
def test_wait_condition_from_dict_recusa_o_que_nao_e_objeto(dados):
    assert WaitCondition.from_dict(dados) is None


# ================================================================================================ propriedades de tempo
def test_texto_conta_a_duracao_calculada_e_o_atraso():
    core.set_runtime_defaults(text_char_interval=0.05)  # o ajuste volta ao fim do teste (fixture automática)
    comando = Command(type=InputType.TEXT, text="abcd", delay=0.5, duration=9.0)
    assert comando.computed_duration == pytest.approx(0.2)
    assert comando.total_duration == comando.computed_duration
    assert comando.computed_delay_after == pytest.approx(0.7)
    assert comando.effective_end == pytest.approx(0.2)


def test_tecla_soltar_isolado_so_espera_o_atraso():
    comando = Command(type=InputType.KEY, target="A", action=ActionType.RELEASE, duration=5.0, delay=0.1, start=2.0)
    assert comando.computed_delay_after == pytest.approx(0.1) and comando.effective_end == 2.0


def test_abrir_aplicativo_espera_estabilidade_mais_seguranca_mais_atraso():
    comando = Command(type=InputType.APP_OPEN, target="x.exe", wait_stable_ms=1000, wait_after_open=0.3, delay=0.2, start=2.0)
    assert comando.computed_delay_after == pytest.approx(1.5) and comando.effective_end == pytest.approx(3.5)


def test_duracao_calculada_de_tecla_nunca_e_negativa():
    assert _tecla("K", "A", 0.0, -1.0).computed_duration == 0.0


# ================================================================================================ eventos da timeline
def test_trajeto_mesclado_ignora_pontos_ilegiveis_e_usa_a_posicao_do_comando_no_que_falta():
    comando = Command(id="M", type=InputType.MOUSE_MOVE, x=5, y=6, start=1.0, duration=2.0, merged_move=True,
                      mouse_path=[{"t": 0.0, "x": 1, "y": 2}, {"t": "lixo"}, {"t": 0.5}, {"t": 2.0, "x": 3, "y": 4}])
    eventos = build_timeline(AutomationMap(name="M", commands=[comando]))
    assert [(e.kind, round(e.time, 6), e.x, e.y) for e in eventos] == [
        (EventKind.MOUSE_MOVE, 1.0, 1, 2), (EventKind.MOUSE_MOVE, 2.0, 5, 6), (EventKind.MOUSE_MOVE, 3.0, 3, 4)]


def test_trajeto_mesclado_todo_ilegivel_vira_um_movimento_so_para_a_posicao_do_comando():
    comando = Command(id="M", type=InputType.MOUSE_MOVE, x=5, y=6, start=1.0, duration=2.0, merged_move=True,
                      mouse_path=[{"t": "a"}, {"t": "b"}])
    eventos = build_timeline(AutomationMap(name="M", commands=[comando]))
    assert [(e.kind, e.time, e.x, e.y) for e in eventos] == [(EventKind.MOUSE_MOVE, 1.0, 5, 6)]


def test_comando_de_tipo_desconhecido_nao_gera_eventos():
    comando = _tecla("K", "A", 0.0, 0.1)
    comando.type = "tipo-que-nao-existe"  # só acontece se alguém atribuir direto: o construtor normaliza para tecla
    assert build_timeline(AutomationMap(name="M", commands=[comando])) == []


# ================================================================================================ estado e contador de IDs
def test_um_observador_que_levanta_excecao_nao_impede_a_transicao_nem_os_outros():
    gerente, vistos = StateManager(State.IDLE), []

    def com_defeito(anterior, novo):
        raise RuntimeError("defeito do observador")

    gerente.on_change(com_defeito)
    gerente.on_change(lambda anterior, novo: vistos.append((anterior, novo)))
    gerente.transition_to(State.RUNNING)
    assert gerente.state == State.RUNNING and vistos == [(State.IDLE, State.RUNNING)]


def test_force_to_idle_tolera_observador_com_defeito():
    gerente, vistos = StateManager(State.RUNNING), []

    def com_defeito(anterior, novo):
        raise RuntimeError("defeito do observador")

    gerente.on_change(com_defeito)
    gerente.on_change(lambda anterior, novo: vistos.append((anterior, novo)))
    gerente.force_to_idle()
    assert gerente.state == State.IDLE and vistos == [(State.RUNNING, State.IDLE)]


def test_transicao_invalida_nao_chama_observadores():
    gerente, vistos = StateManager(State.IDLE), []
    gerente.on_change(lambda anterior, novo: vistos.append(novo))
    with pytest.raises(InvalidStateTransition):
        gerente.transition_to(State.PAUSED)
    assert vistos == []


def test_contador_de_ids_so_avanca_e_e_iteravel():
    contador = _IdCounter(1)
    assert iter(contador) is contador
    assert (next(contador), next(contador)) == (1, 2)
    contador.advance_past(10)
    assert next(contador) == 11
    contador.advance_past(5)  # nunca recua
    assert next(contador) == 12
    contador.advance_past(12)  # o próximo (13) já está além
    assert next(contador) == 13


# ================================================================================================ rótulos e layout do teclado
@pytest.mark.parametrize("alvo,esperado", [
    ("", []), (None, []), ("SHIFT", ["ShiftLeft", "ShiftRight"]), ("shift", ["ShiftLeft", "ShiftRight"]), ("ShiftLeft", ["ShiftLeft"]),
    ("NUM3", ["Num3"]), ("a", ["A"]), (";", [";"]), ("Ç", ["Ç"]), ("^~", ["^~"]), ("VOLUME_UP", []), ("FOO", []), ("  enter ", ["Enter"]),
], ids=["vazio", "none", "shift", "shift-minusculo", "shift-esquerdo", "numpad", "letra", "ponto-e-virgula", "cedilha", "til", "volume",
        "desconhecida", "com-espacos"])
def test_resolve_key_labels(alvo, esperado):
    assert resolve_key_labels(alvo) == esperado


def test_layout_do_teclado_sempre_tem_teclas():
    layout = core._load_keyboard_layout()  # do arquivo, se o pacote o trouxer; senão o ABNT2 embutido
    assert layout["keys"] and layout["ref_w"] > 0 and layout["ref_h"] > 0


def test_layout_do_teclado_usa_o_arquivo_quando_ele_existe(monkeypatch, tmp_path):
    arquivo = tmp_path / "layout.json"
    arquivo.write_text(json.dumps({"ref_w": 10, "ref_h": 5, "keys": [{"label": "X", "x": 0, "y": 0, "w": 1, "h": 1}]}), encoding="utf-8")
    monkeypatch.setattr(core, "_LAYOUT_PATH", arquivo)
    assert core._load_keyboard_layout()["keys"] == [{"label": "X", "x": 0, "y": 0, "w": 1, "h": 1}]


@pytest.mark.parametrize("conteudo", [None, "{isto nao e json"], ids=["arquivo-ausente", "arquivo-corrompido"])
def test_layout_do_teclado_cai_no_abnt2_embutido_se_o_arquivo_nao_serve(monkeypatch, tmp_path, conteudo):
    arquivo = tmp_path / "layout.json"
    if conteudo is not None:
        arquivo.write_text(conteudo, encoding="utf-8")
    monkeypatch.setattr(core, "_LAYOUT_PATH", arquivo)
    layout = core._load_keyboard_layout()
    rotulos = [tecla["label"] for tecla in layout["keys"]]
    assert (layout["ref_w"], layout["ref_h"], len(rotulos)) == (900, 290, 75)
    assert rotulos[0] == "Esc" and rotulos.count("Space") == 1 and "Ç" in rotulos and "AltGr" in rotulos


# ================================================================================================ pasta de dados (registro do Windows)
class _Chave:
    def __enter__(self):
        return self

    def __exit__(self, *erro):
        return False


def _winreg_falso(valores=None, falha=False):
    """winreg falso: nenhum teste toca o registro de verdade, em nenhum sistema."""
    gravado = {}

    def abrir(raiz, caminho):
        if falha:
            raise OSError("sem acesso")
        gravado["lido_de"] = caminho
        return _Chave()

    def consultar(chave, nome):
        if nome not in (valores or {}):
            raise FileNotFoundError(nome)
        return valores[nome], 1

    def criar(raiz, caminho):
        if falha:
            raise OSError("sem acesso")
        gravado["criado_em"] = caminho
        return _Chave()

    def gravar(chave, nome, reservado, tipo, valor):
        gravado[nome] = (reservado, tipo, valor)

    falso = types.SimpleNamespace(HKEY_CURRENT_USER="HKCU", REG_SZ=1, OpenKey=abrir, QueryValueEx=consultar, CreateKey=criar,
                                  SetValueEx=gravar)
    return falso, gravado


def _como_windows(monkeypatch, falso):
    monkeypatch.setattr(core, "os", types.SimpleNamespace(name="nt"))
    monkeypatch.setitem(sys.modules, "winreg", falso)


def test_pasta_de_dados_vem_do_registro_e_e_criada(monkeypatch, tmp_path):
    destino = tmp_path / "meus dados"
    falso, gravado = _winreg_falso({"DataDir": str(destino)})
    _como_windows(monkeypatch, falso)
    assert core._registered_data_dir(tmp_path / "padrao") == destino.resolve()
    assert destino.is_dir() and "AutomationStudio" in gravado["lido_de"]


@pytest.mark.parametrize("valores,falha", [({"DataDir": ""}, False), ({}, False), (None, True)],
                         ids=["valor-vazio", "sem-valor", "sem-acesso"])
def test_pasta_de_dados_usa_a_padrao_se_o_registro_nao_ajuda(monkeypatch, tmp_path, valores, falha):
    falso, _ = _winreg_falso(valores, falha)
    _como_windows(monkeypatch, falso)
    assert core._registered_data_dir(tmp_path / "padrao") == (tmp_path / "padrao").resolve()


def test_pasta_de_dados_fora_do_windows_e_sempre_a_padrao(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "os", types.SimpleNamespace(name="posix"))  # nunca chega ao winreg, nem no Windows de verdade
    assert core._registered_data_dir(tmp_path) == tmp_path.resolve()
    core._set_registered_data_dir(tmp_path)  # não faz nada e não levanta


def test_gravar_a_pasta_de_dados_escreve_o_valor_no_registro(monkeypatch, tmp_path):
    falso, gravado = _winreg_falso()
    _como_windows(monkeypatch, falso)
    core._set_registered_data_dir(tmp_path / "dados")
    assert gravado["DataDir"] == (0, 1, str((tmp_path / "dados").resolve())) and "AutomationStudio" in gravado["criado_em"]


def test_gravar_a_pasta_de_dados_tolera_falha_do_registro(monkeypatch, tmp_path):
    falso, gravado = _winreg_falso(falha=True)
    _como_windows(monkeypatch, falso)
    core._set_registered_data_dir(tmp_path / "dados")  # não levanta
    assert "DataDir" not in gravado


# ================================================================================================ log de execução
def test_log_de_execucao_acrescenta_linhas_ao_lado_do_script(monkeypatch, tmp_path):
    monkeypatch.undo()  # desfaz o patch automático do log (fixture runtime_log) para exercitar a função de verdade
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "app.pyw")])
    core._append_runtime_log("primeira")
    core._append_runtime_log("segunda")
    linhas = (tmp_path / "logs" / "AutomationStudio.log").read_text(encoding="utf-8").splitlines()
    assert [linha.split("] ", 1)[1] for linha in linhas] == ["primeira", "segunda"]
    assert all(linha.startswith("[20") for linha in linhas)  # data e hora no início


def test_log_de_execucao_nunca_levanta_excecao(monkeypatch, tmp_path):
    monkeypatch.undo()
    arquivo = tmp_path / "arquivo.txt"
    arquivo.write_text("x", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [str(arquivo / "app.pyw")])  # a "pasta" é um arquivo: não dá para criar logs/ dentro
    core._append_runtime_log("não deve levantar")
