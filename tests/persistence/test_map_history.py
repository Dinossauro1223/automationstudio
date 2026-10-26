"""MapHistory: desfazer/refazer por mapa, rótulos e orçamento de memória."""
import copy
import random

import pytest

from automationstudio.core import Command, CommandGroup, InputType
from automationstudio.project import MapHistory
from testsupport.helpers import key, make_map


def _historico_com(mapa, **kwargs):
    historico = MapHistory(**kwargs)
    historico.prime(mapa)
    return historico


# ----------------------------------------------------------------------------------------- desfazer e refazer
def test_desfazer_e_refazer_uma_alteracao():
    mapa = make_map([key("A", 0.0, 0.1)], name="M")
    historico = _historico_com(mapa)
    mapa.commands.append(key("B", 0.5, 0.1))
    historico.commit(mapa, "Adicionar B")
    assert historico.undo(mapa) is mapa and [c.target for c in mapa.commands] == ["A"]
    assert historico.redo(mapa) is mapa and [c.target for c in mapa.commands] == ["A", "B"]


def test_desfazer_sem_nada_a_desfazer_devolve_none_e_nao_mexe_no_mapa():
    mapa = make_map([key("A", 0.0, 0.1)], name="M")
    historico = _historico_com(mapa)
    antes = copy.deepcopy(mapa.to_dict())
    assert historico.undo(mapa) is None and historico.redo(mapa) is None
    assert mapa.to_dict() == antes and not historico.can_undo(mapa) and not historico.can_redo(mapa)


def test_varias_alteracoes_desfazem_em_ordem_inversa():
    mapa = make_map([key("A", 0.0, 0.1)], name="M")
    historico = _historico_com(mapa)
    for letra, instante in (("B", 0.5), ("C", 1.0), ("D", 1.5)):
        mapa.commands.append(key(letra, instante, 0.1))
        historico.commit(mapa, f"Adicionar {letra}")
    assert historico.depth(mapa) == (3, 0)
    vistos = []
    while historico.can_undo(mapa):
        historico.undo(mapa)
        vistos.append("".join(c.target for c in mapa.commands))
    assert vistos == ["ABC", "AB", "A"] and historico.depth(mapa) == (0, 3)


def test_nova_alteracao_depois_de_desfazer_apaga_o_refazer():
    mapa = make_map([key("A", 0.0, 0.1)], name="M")
    historico = _historico_com(mapa)
    mapa.commands.append(key("B", 0.5, 0.1)); historico.commit(mapa, "B")
    historico.undo(mapa)
    assert historico.can_redo(mapa)
    mapa.commands.append(key("C", 0.5, 0.1)); historico.commit(mapa, "C")
    assert not historico.can_redo(mapa) and historico.depth(mapa) == (1, 0)


def test_confirmar_sem_mudanca_nao_cria_passo():
    mapa = make_map([key("A", 0.0, 0.1)], name="M")
    historico = _historico_com(mapa)
    historico.commit(mapa, "nada mudou")
    historico.commit(mapa, "nada mudou de novo")
    assert historico.depth(mapa) == (0, 0)


def test_confirmar_sem_mudanca_depois_de_desfazer_nao_duplica_passos():
    mapa = make_map([key("A", 0.0, 0.1)], name="M")
    historico = _historico_com(mapa)
    mapa.commands.append(key("B", 0.5, 0.1)); historico.commit(mapa, "B")
    mapa.commands.append(key("C", 1.0, 0.1)); historico.commit(mapa, "C")
    historico.undo(mapa)
    historico.commit(mapa, "o programa salvou sem mudar nada")
    assert historico.depth(mapa) == (1, 1)


def test_sem_prime_o_primeiro_commit_so_marca_a_base():
    mapa = make_map([key("A", 0.0, 0.1)], name="M")
    historico = MapHistory()
    historico.commit(mapa, "base")
    assert not historico.can_undo(mapa)
    mapa.commands.append(key("B", 0.5, 0.1)); historico.commit(mapa, "B")
    assert historico.can_undo(mapa)


def test_prime_zera_o_historico_do_mapa():
    mapa = make_map([key("A", 0.0, 0.1)], name="M")
    historico = _historico_com(mapa)
    mapa.commands.append(key("B", 0.5, 0.1)); historico.commit(mapa, "B")
    historico.undo(mapa)
    historico.prime(mapa)
    assert historico.depth(mapa) == (0, 0) and historico.last_label(mapa) == "Alteração"


def test_historico_e_separado_por_mapa():
    a, b = make_map([key("A", 0.0, 0.1)], name="A"), make_map([key("B", 0.0, 0.1)], name="B")
    historico = MapHistory()
    historico.prime(a); historico.prime(b)
    a.commands.append(key("X", 0.5, 0.1)); historico.commit(a, "no A")
    assert historico.can_undo(a) and not historico.can_undo(b) and historico.depth(b) == (0, 0)
    historico.undo(a)
    assert [c.target for c in b.commands] == ["B"]


@pytest.mark.parametrize("campo,novo", [
    ("description", "outra descrição"), ("hotkey", "F7"), ("repeat_count", 5), ("repeat_interval", 2.5), ("speed", 2.0),
    ("conflict_behavior", "block"), ("next_map", "Outro mapa"), ("confirm_delete_commands", False)])
def test_desfazer_e_refazer_restauram_cada_campo_do_mapa(campo, novo):
    mapa = make_map([key("A", 0.0, 0.1)], name="Campos")
    original = getattr(mapa, campo)
    historico = _historico_com(mapa)
    setattr(mapa, campo, novo)
    historico.commit(mapa, f"mudar {campo}")
    historico.undo(mapa)
    assert getattr(mapa, campo) == original
    historico.redo(mapa)
    assert getattr(mapa, campo) == novo


def test_desfazer_e_refazer_restauram_comandos_e_grupos():
    mapa = make_map([key("A", 0.0, 0.1)], name="CG")
    historico = _historico_com(mapa)
    grupo = CommandGroup(name="G")
    mapa.groups[grupo.id] = grupo
    mapa.commands.append(key("B", 0.5, 0.1, group_id=grupo.id))
    historico.commit(mapa, "Adicionar B no grupo G")
    historico.undo(mapa)
    assert [c.target for c in mapa.commands] == ["A"] and mapa.groups == {}
    historico.redo(mapa)
    assert [c.target for c in mapa.commands] == ["A", "B"] and [g.name for g in mapa.groups.values()] == ["G"]


def test_o_snapshot_guardado_nao_muda_quando_o_mapa_vivo_muda():
    mapa = make_map([key("A", 0.0, 0.1)], name="Iso")
    historico = _historico_com(mapa)
    mapa.commands[0].target = "B"; historico.commit(mapa, "A para B")
    mapa.commands[0].target = "C"  # edição em andamento, ainda sem commit
    historico.undo(mapa)
    assert mapa.commands[0].target == "A"
    historico.redo(mapa)
    assert mapa.commands[0].target == "C", "o refazer devolve o que estava na tela quando o usuário desfez"


def test_desfazer_tudo_e_refazer_tudo_reproduzem_cada_estado_intermediario():
    rng = random.Random(20251010)
    mapa = make_map([key("A", 0.0, 0.1)], name="Modelo")
    historico = _historico_com(mapa)
    estados = [copy.deepcopy(mapa.to_dict())]
    for _passo in range(40):
        acao = rng.choice(["adicionar", "remover", "velocidade", "atalho", "texto", "repeticao"])
        if acao == "adicionar":
            mapa.commands.append(key(rng.choice("BCDEFG"), round(rng.random() * 5, 3), 0.1))
        elif acao == "remover" and len(mapa.commands) > 1:
            mapa.commands.pop(rng.randrange(len(mapa.commands)))
        elif acao == "velocidade":
            mapa.speed = rng.choice([0.5, 1.0, 2.0, 3.0])
        elif acao == "atalho":
            mapa.hotkey = rng.choice(["F5", "F6", "=", "MOUSE_X1"])
        elif acao == "texto":
            mapa.description = "d" * rng.randrange(0, 5)
        else:
            mapa.repeat_count = rng.choice([1, 2, -1])
        novo = copy.deepcopy(mapa.to_dict())
        historico.commit(mapa, acao)
        if novo != estados[-1]:
            estados.append(novo)
    assert len(estados) > 10, "a sequência sorteada precisa mexer no mapa de verdade"
    assert historico.depth(mapa) == (len(estados) - 1, 0)
    for esperado in reversed(estados[:-1]):
        assert historico.undo(mapa) is mapa
        assert mapa.to_dict() == esperado
    assert not historico.can_undo(mapa)
    for esperado in estados[1:]:
        assert historico.redo(mapa) is mapa
        assert mapa.to_dict() == esperado
    assert not historico.can_redo(mapa)


# ----------------------------------------------------------------------------------------- rótulos
def test_rotulos_seguem_a_pilha_de_desfazer_e_de_refazer():
    mapa = make_map([key("A", 0.0, 0.1)], name="M")
    historico = _historico_com(mapa)
    mapa.commands.append(key("B", 0.5, 0.1)); historico.commit(mapa, "Adicionar B")
    mapa.commands.append(key("C", 1.0, 0.1)); historico.commit(mapa, "Adicionar C")
    assert (historico.undo_label(mapa), historico.redo_label(mapa)) == ("Adicionar C", "Alteração")
    historico.undo(mapa)
    assert (historico.undo_label(mapa), historico.redo_label(mapa)) == ("Adicionar B", "Adicionar C")
    historico.undo(mapa)
    assert (historico.undo_label(mapa), historico.redo_label(mapa)) == ("Alteração", "Adicionar B")
    historico.redo(mapa)
    assert (historico.undo_label(mapa), historico.redo_label(mapa)) == ("Adicionar B", "Adicionar C")


@pytest.mark.parametrize("rotulo,esperado", [("", "Alteração"), ("   ", "Alteração"), (None, "Alteração"), ("  Mover  ", "Mover")])
def test_rotulo_vazio_vira_alteracao_e_espacos_sao_aparados(rotulo, esperado):
    mapa = make_map([key("A", 0.0, 0.1)], name="M")
    historico = _historico_com(mapa)
    mapa.commands.append(key("B", 0.5, 0.1))
    historico.commit(mapa, rotulo)
    assert historico.undo_label(mapa) == esperado and historico.last_label(mapa) == esperado


def test_sem_mapa_tudo_responde_com_o_valor_neutro():
    historico = MapHistory()
    assert historico.depth(None) == (0, 0) and not historico.can_undo(None) and not historico.can_redo(None)
    assert historico.undo_label(None) == historico.redo_label(None) == historico.last_label(None) == "Alteração"


# ----------------------------------------------------------------------------------------- orçamento de memória
@pytest.mark.parametrize("pedido,esperado", [(1, 16), (0, 16), (-5, 16), (16, 16), (64, 64), ("64", 64), (8192, 8192), (100000, 8192)])
def test_orcamento_de_ram_e_limitado_entre_o_minimo_e_o_maximo(pedido, esperado):
    assert MapHistory(pedido).ram_mb == esperado
    historico = MapHistory()
    historico.set_ram_mb(pedido)
    assert historico.ram_mb == esperado and historico.budget_bytes == esperado * 1024 * 1024


def test_orcamento_de_ram_nao_numerico_e_recusado():
    with pytest.raises(ValueError):
        MapHistory("muito")


def test_uso_de_memoria_aparece_em_texto_legivel():
    mapa = make_map([key("A", 0.0, 0.1)], name="M")
    historico = _historico_com(mapa, ram_mb=64)
    assert historico.usage_bytes() == 0 and historico.usage_text() == "0.0 MB / 64 MB"
    mapa.commands.append(key("B", 0.5, 0.1)); historico.commit(mapa, "B")
    assert historico.usage_bytes() > 0 and historico.usage_text().endswith(" MB / 64 MB")


def _mapa_grande():
    return make_map([Command(type=InputType.TEXT, text="0" * 300_000, start=0.0, duration=0.1)], name="Grande")


def test_estourar_o_orcamento_descarta_os_snapshots_mais_antigos(monkeypatch):
    monkeypatch.setattr(MapHistory, "MIN_RAM_MB", 1)  # só para o teste não precisar de dezenas de MB
    mapa = _mapa_grande()
    historico = _historico_com(mapa, ram_mb=1)
    for versao in range(1, 9):
        mapa.commands[0].text = str(versao) * 300_000
        historico.commit(mapa, f"versão {versao}")
    desfazer, refazer = historico.depth(mapa)
    assert refazer == 0 and 1 <= desfazer < 8, "8 versões de ~300 KB não cabem em 1 MB"
    assert historico.usage_bytes() <= historico.budget_bytes
    while historico.can_undo(mapa):
        historico.undo(mapa)
    # o que sobrou são as versões MAIS NOVAS: 8 - desfazer .. 7. Desfazer tudo termina na mais antiga retida.
    assert mapa.commands[0].text[0] == str(8 - desfazer)


def test_o_estado_atual_nunca_e_descartado_mesmo_sem_orcamento(monkeypatch):
    monkeypatch.setattr(MapHistory, "MIN_RAM_MB", 0)
    mapa = _mapa_grande()
    historico = _historico_com(mapa, ram_mb=0)
    mapa.commands[0].text = "1" * 300_000
    historico.commit(mapa, "mudou")
    assert not historico.can_undo(mapa) and historico.usage_bytes() == 0
    assert mapa.commands[0].text == "1" * 300_000


def test_reduzir_o_orcamento_enxuga_o_historico_na_hora(monkeypatch):
    monkeypatch.setattr(MapHistory, "MIN_RAM_MB", 1)
    mapa = _mapa_grande()
    historico = _historico_com(mapa, ram_mb=8)
    for versao in range(1, 7):
        mapa.commands[0].text = str(versao) * 300_000
        historico.commit(mapa, f"versão {versao}")
    assert historico.depth(mapa) == (6, 0)
    historico.set_ram_mb(1)
    assert historico.depth(mapa)[0] < 6 and historico.usage_bytes() <= historico.budget_bytes
    assert historico.can_undo(mapa), "ainda sobra pelo menos o passo mais recente"


def test_o_refazer_tambem_conta_no_orcamento(monkeypatch):
    monkeypatch.setattr(MapHistory, "MIN_RAM_MB", 1)
    mapa = _mapa_grande()
    historico = _historico_com(mapa, ram_mb=1)
    for versao in range(1, 4):
        mapa.commands[0].text = str(versao) * 300_000
        historico.commit(mapa, f"versão {versao}")
    while historico.can_undo(mapa):
        historico.undo(mapa)
    desfazer, refazer = historico.depth(mapa)
    assert desfazer == 0 and refazer >= 1
    assert historico.usage_bytes() <= historico.budget_bytes
