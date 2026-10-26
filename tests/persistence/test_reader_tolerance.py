"""CARACTERIZAÇÃO do leitor do formato v1 (map_from_json / AutomationMap.from_dict / Command.from_dict).

Estes testes registram o que o leitor aceita, corrige em silêncio ou recusa HOJE. Não são requisitos: o formato v2 do
Ponto 3 troca o leitor, e cada mudança de comportamento aqui precisa ser uma decisão, não um acidente. Quando um destes
testes falhar depois de uma alteração, leia o comentário: ele diz se a mudança é o objetivo ou um efeito colateral.

Regra de ouro que os testes protegem: o leitor nunca apaga dados em silêncio (o registro ruim fica no banco e aparece
em `load_errors`; ver test_project_manager.py).
"""
import json

import pytest

from automationstudio.core import ActionType, InputType, map_from_json, map_to_json
from testsupport.helpers import key, make_map


def _ler(**campos):
    return map_from_json(json.dumps(campos))


def _comando(**campos):
    return _ler(name="M", commands=[campos]).commands[0]


# ----------------------------------------------------------------------------------------- forma do documento
def test_envelope_e_opcional_e_a_versao_do_formato_e_ignorada():
    esperado = _ler(name="X", speed=2.0).to_dict()
    assert map_from_json(json.dumps({"format_version": 1, "map": {"name": "X", "speed": 2.0}})).to_dict() == esperado
    # Futuro: um arquivo de versão 99 abre igual, sem aviso e ignorando o que não conhece. O formato v2 deve avisar.
    assert map_from_json(json.dumps({"format_version": 99, "map": {"name": "X", "speed": 2.0}})).to_dict() == esperado


def test_documento_vazio_vira_mapa_com_os_padroes():
    mapa = map_from_json("{}")
    assert (mapa.name, mapa.hotkey, mapa.repeat_count, mapa.speed, mapa.commands, mapa.groups) == ("Sem nome", "=", -1, 1.0, [], {})


@pytest.mark.parametrize("texto,erro", [
    ("", json.JSONDecodeError), ("{ nao", json.JSONDecodeError), ("﻿{}", json.JSONDecodeError),
    ("[]", AttributeError), ("null", TypeError), ("42", TypeError), ('"abc"', AttributeError), ('"mapa"', TypeError)])
def test_documento_que_nao_e_um_objeto_json_e_recusado_com_erro(texto, erro):
    with pytest.raises(erro):
        map_from_json(texto)


def test_campos_desconhecidos_sao_ignorados_e_somem_na_regravacao():
    mapa = _ler(name="H", futuro={"x": 1}, commands=[{"type": "key", "target": "A", "duration": 0.1, "novo_campo": 7}])
    texto = map_to_json(mapa)
    assert "futuro" not in texto and "novo_campo" not in texto


# ----------------------------------------------------------------------------------------- campos do mapa
@pytest.mark.parametrize("bruto,esperado", [("", "="), (None, "="), ("F5", "F5")])
def test_atalho_vazio_ou_nulo_vira_o_atalho_padrao(bruto, esperado):
    assert _ler(name="H", hotkey=bruto).hotkey == esperado


@pytest.mark.parametrize("bruto,esperado", [(0, 1), ("3", 3), (2.7, 2), (-1, -1), (-5, -5), (7, 7)])
def test_contagem_de_repeticoes_e_convertida_para_inteiro(bruto, esperado):
    # 0 vira 1 (nunca "zero vezes"). Negativos além de -1 passam: lacuna registrada em test_validation_gaps.py.
    assert _ler(name="H", repeat_count=bruto).repeat_count == esperado


def test_intervalo_de_repeticao_negativo_vira_zero():
    assert _ler(name="H", repeat_interval=-3).repeat_interval == 0.0


@pytest.mark.parametrize("campo,bruto", [("repeat_count", "muitas"), ("speed", "x"), ("repeat_interval", "x")])
def test_numero_ilegivel_no_mapa_impede_a_carga(campo, bruto):
    with pytest.raises(ValueError):
        _ler(name="H", **{campo: bruto})


@pytest.mark.parametrize("velocidade", [0, -2])
def test_velocidade_nao_positiva_carrega_e_a_validacao_reclama(velocidade):
    mapa = _ler(name="H", speed=velocidade)
    assert any("speed" in erro for erro in mapa.validate())


@pytest.mark.parametrize("campo", ["commands", "groups"])
def test_lista_nula_impede_a_carga_mas_campo_ausente_nao(campo):
    assert _ler(name="H").commands == []
    with pytest.raises(TypeError):
        _ler(name="H", **{campo: None})


def test_nome_ausente_vira_sem_nome_e_nome_vazio_ou_nulo_carrega_e_a_validacao_reclama():
    assert _ler().name == "Sem nome"
    for nome in ("", None):
        assert "Mapa sem nome." in _ler(name=nome).validate()


def test_nome_que_nao_e_texto_passa_pelo_leitor_e_quebra_na_validacao():
    # Lacuna do leitor v1: não confere o tipo do nome. O banco guarda o mapa e a falha só aparece em validate().
    mapa = _ler(name=123)
    assert mapa.name == 123
    with pytest.raises(AttributeError):
        mapa.validate()


def test_comportamento_de_conflito_desconhecido_passa_sem_aviso():
    assert _ler(name="H", conflict_behavior="zzz").conflict_behavior == "zzz"


# ----------------------------------------------------------------------------------------- campos dos comandos
@pytest.mark.parametrize("bruto,esperado", [
    ("key", InputType.KEY), ("TEXT", InputType.TEXT), ("InputType.TEXT", InputType.TEXT), ("mouse_button", InputType.MOUSE_BUTTON)])
def test_tipo_de_comando_aceita_caixa_e_prefixo_de_enum(bruto, esperado):
    assert _comando(type=bruto, target="A").type is esperado


def test_tipo_de_comando_desconhecido_vira_tecla_em_silencio():
    # PERIGOSO para uma ferramenta de macros: um tipo novo (de versão futura) ou com erro de digitação passa a apertar
    # a tecla que estiver em `target`. O leitor v2 deve recusar o tipo desconhecido (e mostrar em load_errors).
    comando = _comando(type="nao_existe", target="A", duration=0.1)
    assert comando.type is InputType.KEY and comando.target == "A"
    assert _ler(name="H", commands=[{"type": "nao_existe", "target": "A", "duration": 0.1}]).validate() == []


def test_acao_desconhecida_vira_pressionar_e_soltar():
    assert _comando(type="key", target="A", action="xx").action is ActionType.PRESS_AND_RELEASE


def test_comando_vazio_vira_tecla_sem_alvo_e_a_validacao_reclama():
    mapa = _ler(name="H", commands=[{}])
    assert mapa.commands[0].type is InputType.KEY
    assert any("sem tecla" in erro for erro in mapa.validate())


def test_booleano_em_texto_e_lido_pela_regra_do_python():
    # bool("false") é True: só vale para arquivos editados à mão (o programa grava true/false de verdade).
    assert _comando(type="key", target="A", enabled="false").enabled is True
    assert _comando(type="key", target="A", enabled=False).enabled is False


@pytest.mark.parametrize("campo", ["start", "duration", "delay", "scroll_dx"])
def test_numero_ilegivel_no_comando_impede_a_carga(campo):
    with pytest.raises(ValueError):
        _comando(type="key", target="A", **{campo: "x"})


def test_inicio_negativo_carrega_e_a_validacao_reclama():
    mapa = _ler(name="H", commands=[{"type": "key", "target": "A", "start": -1, "duration": 0.1}])
    assert any("negativo" in erro for erro in mapa.validate())


def test_comando_que_nao_e_objeto_impede_a_carga():
    with pytest.raises(AttributeError):
        _ler(name="H", commands=["texto solto"])


def test_ids_repetidos_sao_reparados_na_carga_mantendo_o_primeiro():
    mapa = _ler(name="H", commands=[{"id": "a", "type": "key", "target": "A", "duration": 0.1},
                                    {"id": "a", "type": "key", "target": "B", "duration": 0.1}])
    assert mapa.commands[0].id == "a" and mapa.commands[1].id != "a"


def test_comando_sem_id_recebe_um_id_novo_e_unico():
    mapa = _ler(name="H", commands=[{"type": "key", "target": "A", "duration": 0.1}, {"type": "key", "target": "B", "duration": 0.1}])
    ids = [c.id for c in mapa.commands]
    assert all(ids) and len(set(ids)) == 2


def test_padrao_antigo_de_espera_do_aplicativo_e_atualizado_na_leitura():
    migrado = _comando(type="app_open", target="x.exe", wait_stable_ms=250, wait_after_open=0.375)
    assert (migrado.wait_stable_ms, migrado.wait_after_open) == (1000, 0.3)
    personalizado = _comando(type="app_open", target="x.exe", wait_stable_ms=250, wait_after_open=0.5)
    assert (personalizado.wait_stable_ms, personalizado.wait_after_open) == (250, 0.5)


# ----------------------------------------------------------------------------------------- escrita
def test_o_que_o_programa_grava_o_leitor_devolve_igual():
    mapa = make_map([key("A", 0.0, 0.1), key("B", 0.5, 0.2)], name="Ida e volta", speed=2.0, hotkey="F4")
    assert map_from_json(map_to_json(mapa)).to_dict() == mapa.to_dict()


def test_escrita_usa_o_envelope_com_versao_1_e_acentos_legiveis():
    bruto = json.loads(map_to_json(make_map([key("Ç", 0.0, 0.1)], name="Ação")))
    assert bruto["format_version"] == 1 and bruto["map"]["name"] == "Ação"
    assert "Ação" in map_to_json(make_map([], name="Ação"))
