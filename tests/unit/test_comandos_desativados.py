"""Desativar e ativar comandos (função F49): o comando desativado fica na lista, mas ninguém o executa.

O modelo (`Command.enabled`), a timeline, o motor e a Timeline desenhada já tratavam `enabled=False`. A função nova é o jeito
de ligar e desligar isso pela tabela do editor, sem apagar o comando. O que se prova aqui, sem janela:

* `AutomationMap.set_commands_enabled`: muda só o que foi pedido, não mexe em horário nem em ordem, devolve o que mudou;
* o motor ignora o desativado, inclusive a ESPERA dele (uma espera desativada não segura a execução);
* desfazer e refazer restauram o estado; salvar, abrir, copiar, colar, exportar e importar levam o estado junto;
* a lógica da tabela (`_set_enabled_ids`, `_estados_ligados`, `_fill_row`) com um `self` de mentira: ordem das chamadas, rótulo do
  histórico, nada registrado quando nada mudou, e como a linha desativada é pintada.

Fica de fora, porque só o Qt real mostra: a aparência da tabela e os menus (ver md/ENTREGA_DESATIVAR_COMANDOS.md). A ligação dos
menus ao código é conferida em tests/static/test_ligacao_desativar_comandos.py.
"""
import json
import types

import pytest

from automationstudio.conditions import WaitCondition, WaitConditionType
from automationstudio.core import AutomationMap, Command, CommandGroup, InputType, build_timeline, map_from_json, map_to_json
from automationstudio.project import MapHistory
from testsupport.fake_clock import FakeClock
from testsupport.helpers import events_of, key, make_map, run_to_end


def _estados(mapa) -> list[bool]:
    return [c.enabled for c in mapa.commands]


def _ids(mapa) -> list[str]:
    return [c.id for c in mapa.commands]


def _tres() -> AutomationMap:
    return make_map([key("A", 0.0, 0.2), key("B", 0.5, 0.2), key("C", 1.0, 0.2)])


# ------------------------------------------------------------------------------------------------- o modelo
def test_desativar_muda_so_o_comando_pedido_e_devolve_o_que_mudou():
    mapa = _tres()
    a, b, c = mapa.commands
    mudaram = mapa.set_commands_enabled({b.id}, False)
    assert [x.id for x in mudaram] == [b.id]
    assert _estados(mapa) == [True, False, True]


def test_desativar_nao_mexe_em_horario_duracao_nem_ordem_e_ativar_devolve_tudo_como_era():
    mapa = _tres()
    antes = json.loads(json.dumps(mapa.to_dict()))
    mapa.set_commands_enabled({mapa.commands[1].id}, False)
    assert [(c.start, c.duration) for c in mapa.commands] == [(0.0, 0.2), (0.5, 0.2), (1.0, 0.2)]
    assert _ids(mapa) == [d["id"] for d in antes["commands"]]
    mapa.set_commands_enabled({mapa.commands[1].id}, True)
    assert json.loads(json.dumps(mapa.to_dict())) == antes


def test_so_devolve_o_que_mudou_e_nao_mexe_em_quem_ja_estava_no_estado_pedido():
    mapa = _tres()
    a, b, c = mapa.commands
    mapa.set_commands_enabled({a.id}, False)
    mudaram = mapa.set_commands_enabled({a.id, b.id}, False)  # a já estava desativado
    assert [x.id for x in mudaram] == [b.id]
    assert mapa.set_commands_enabled({a.id, b.id}, False) == []  # nada a mudar: lista vazia
    assert mapa.set_commands_enabled({c.id}, True) == []  # c já estava ativo
    assert _estados(mapa) == [False, False, True]


def test_ids_que_nao_existem_sao_ignorados_e_aceita_lista_ou_conjunto():
    mapa = _tres()
    assert mapa.set_commands_enabled({"nao-existe"}, False) == []
    assert mapa.set_commands_enabled([], False) == []
    mudaram = mapa.set_commands_enabled([mapa.commands[0].id, "nao-existe"], False)
    assert len(mudaram) == 1 and _estados(mapa) == [False, True, True]


def test_o_comando_desativado_sai_da_timeline_da_previa_e_da_duracao_total():
    mapa = _tres()
    a, b, c = _ids(mapa)
    mapa.set_commands_enabled({c}, False)
    assert [e.target for e in build_timeline(mapa)] == ["A", "A", "B", "B"]
    assert [linha["id"] for linha in mapa.timeline_rows()] == [a, b]
    assert mapa.total_duration() == pytest.approx(0.7)
    mapa.set_commands_enabled({c}, True)
    assert mapa.total_duration() == pytest.approx(1.2)


def test_a_validacao_continua_olhando_tambem_os_comandos_desativados():
    # Decisão da função (ver md/ENTREGA_DESATIVAR_COMANDOS.md): um comando desativado com defeito continua sendo apontado,
    # para que ele já volte certo quando for ativado de novo. Se a decisão mudar, mude este teste junto.
    quebrado = Command(type=InputType.KEY, target="", start=0.0, duration=0.1, enabled=False)
    assert make_map([quebrado]).validate() != []


# ------------------------------------------------------------------------------------------------- o motor
def _rodar(mapa) -> list[tuple]:
    """Roda o mapa com um relógio virtual NOVO (os horários saem a partir de zero) e devolve os eventos."""
    from automationstudio.input_system import ExecutionEngine, MockInputBackend
    relogio = FakeClock()
    backend = MockInputBackend(clock=relogio)
    terminou, erros = run_to_end(ExecutionEngine(backend, None, clock=relogio), mapa)
    assert terminou and not erros, erros
    return events_of(backend)


def test_o_motor_pula_o_desativado_e_os_outros_mantem_os_horarios():
    mapa = _tres()
    mapa.set_commands_enabled({mapa.commands[1].id}, False)
    assert _rodar(mapa) == [(0.0, "key_down", "A"), (0.2, "key_up", "A"), (1.0, "key_down", "C"), (1.2, "key_up", "C")]


def test_ativar_de_novo_volta_a_executar_o_comando_no_horario_dele():
    mapa = _tres()
    b = mapa.commands[1].id
    mapa.set_commands_enabled({b}, False)
    mapa.set_commands_enabled({b}, True)
    assert [alvo for _t, _acao, alvo in _rodar(mapa)] == ["A", "A", "B", "B", "C", "C"]


def test_a_espera_de_um_comando_desativado_nao_segura_a_execucao():
    espera = Command(type=InputType.WAIT, start=0.0, conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=0.5)])
    mapa = make_map([espera, key("A", 0.1, 0.2)])
    assert _rodar(mapa) == [(0.6, "key_down", "A"), (0.8, "key_up", "A")]  # controle: ativa, a espera de 0,5 s empurra o A
    mapa.set_commands_enabled({espera.id}, False)
    assert _rodar(mapa) == [(0.1, "key_down", "A"), (0.3, "key_up", "A")]


def test_a_condicao_anexada_a_um_comando_desativado_nao_atrasa_os_seguintes():
    atrasada = key("A", 0.0, 0.2, conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=0.5)])
    mapa = make_map([atrasada, key("B", 0.3, 0.2)])
    mapa.set_commands_enabled({atrasada.id}, False)
    assert _rodar(mapa) == [(0.3, "key_down", "B"), (0.5, "key_up", "B")]


def test_mapa_com_todos_os_comandos_desativados_termina_sem_erro_e_sem_enviar_nada():
    mapa = _tres()
    mapa.set_commands_enabled(set(_ids(mapa)), False)
    assert _rodar(mapa) == []


# ------------------------------------------------------------------------------------------------- histórico e arquivos
def test_desativar_e_ativar_entram_no_historico_e_desfazer_e_refazer_restauram_o_estado():
    mapa = _tres()
    b = mapa.commands[1].id
    historico = MapHistory()
    historico.prime(mapa)
    mapa.set_commands_enabled({b}, False)
    historico.commit(mapa, "Desativar comandos")
    assert historico.can_undo(mapa) and historico.undo_label(mapa) == "Desativar comandos"

    historico.undo(mapa)
    assert _estados(mapa) == [True, True, True]
    assert historico.can_redo(mapa) and historico.redo_label(mapa) == "Desativar comandos"

    historico.redo(mapa)
    assert _estados(mapa) == [True, False, True]


def test_o_estado_desativado_vai_e_volta_pelo_arquivo_do_mapa():
    mapa = _tres()
    mapa.set_commands_enabled({mapa.commands[1].id}, False)
    assert _estados(map_from_json(map_to_json(mapa))) == [True, False, True]


def test_mapa_antigo_sem_o_campo_enabled_continua_todo_ativo():
    dados = key("A", 0.0).to_dict()
    dados.pop("enabled")
    assert Command.from_dict(dados).enabled is True


def test_exportar_e_importar_comandos_mantem_o_estado():
    mapa = _tres()
    mapa.set_commands_enabled({mapa.commands[0].id}, False)
    carga = json.loads(json.dumps(mapa.export_commands(set(_ids(mapa)))))
    comandos, _grupos = AutomationMap.import_commands(carga)
    assert [c.enabled for c in comandos] == [False, True, True]


def test_copiar_colar_e_duplicar_levam_o_estado_junto():
    mapa = _tres()
    a = mapa.commands[0].id
    mapa.set_commands_enabled({a}, False)
    copias = mapa.copy_commands({a})
    assert [c.enabled for c in copias] == [False]
    assert [c.enabled for c in mapa.insert_commands(copias)] == [False]
    assert [c.enabled for c in mapa.duplicate_commands({a})] == [False]


# ------------------------------------------------------------------------------------------------- a tabela, sem janela
# `CommandTableWidget` não cabe no dublê de widgets, e com o Qt real exigiria uma janela. Os métodos abaixo só usam alguns
# atributos de `self`; chamados como funções com um `self` de mentira, a lógica deles roda e é conferida em qualquer ambiente.
def _editor():
    from automationstudio import command_editor
    return command_editor


class _Aviso:
    """Faz as vezes de um sinal do Qt: guarda o que foi emitido."""

    def __init__(self, chamadas):
        self._chamadas = chamadas

    def emit(self, *args):
        self._chamadas.append(("map_changed", *args))


class _TabelaDeMentira:
    def __init__(self, mapa):
        self._automation_map = mapa
        self.chamadas = []
        self.map_changed = _Aviso(self.chamadas)

    def refresh(self):
        self.chamadas.append(("refresh",))

    def _select_ids(self, ids):
        self.chamadas.append(("select", frozenset(ids)))


def test_a_tabela_ativa_e_desativa_na_ordem_certa_e_avisa_com_o_rotulo_do_historico():
    mapa = _tres()
    b = mapa.commands[1].id
    tabela = _TabelaDeMentira(mapa)
    _editor().CommandTableWidget._set_enabled_ids(tabela, {b}, False)
    assert tabela.chamadas == [("refresh",), ("select", frozenset({b})), ("map_changed", "Desativar comandos")]
    assert _estados(mapa) == [True, False, True]

    tabela.chamadas.clear()
    _editor().CommandTableWidget._set_enabled_ids(tabela, {b}, True)
    assert tabela.chamadas == [("refresh",), ("select", frozenset({b})), ("map_changed", "Ativar comandos")]
    assert _estados(mapa) == [True, True, True]


def test_a_tabela_nao_registra_alteracao_quando_nada_mudou():
    mapa = _tres()
    tabela = _TabelaDeMentira(mapa)
    editor = _editor().CommandTableWidget
    editor._set_enabled_ids(tabela, {mapa.commands[0].id}, True)  # já estava ativo
    editor._set_enabled_ids(tabela, set(), False)  # nada escolhido
    editor._set_enabled_ids(tabela, {"nao-existe"}, False)  # comando que não existe
    assert tabela.chamadas == []
    tabela._automation_map = None
    editor._set_enabled_ids(tabela, {"x"}, False)  # sem mapa aberto
    assert tabela.chamadas == []


def test_estados_ligados_segue_a_ordem_da_lista_e_ignora_o_que_nao_existe():
    mapa = _tres()
    a, b, c = _ids(mapa)
    mapa.set_commands_enabled({a}, False)  # só o primeiro: um padrão que não é igual de trás para frente
    tabela = _TabelaDeMentira(mapa)
    estados = _editor().CommandTableWidget._estados_ligados
    assert estados(tabela, {c, a, b, "nao-existe"}) == [False, True, True]
    assert estados(tabela, {a}) == [False]
    assert estados(tabela, {b}) == [True]
    assert estados(tabela, set()) == []
    tabela._automation_map = None
    assert estados(tabela, {a}) == []


@pytest.mark.parametrize("ligados, texto, novo_valor", [
    ([True], "Desativar selecionados", False),
    ([True, True, True], "Desativar selecionados", False),
    ([True, False], "Desativar selecionados", False),  # mistura: desativa tudo (uma ação só, previsível)
    ([False], "Ativar selecionados", True),
    ([False, False], "Ativar selecionados", True),
    ([], "Desativar selecionados", False),  # nada escolhido: o menu mostra o item cinza com o texto de desativar
])
def test_o_item_de_menu_diz_o_que_vai_fazer_com_a_selecao(ligados, texto, novo_valor):
    assert _editor()._acao_ativar_desativar(ligados) == (texto, novo_valor)


def test_a_coluna_tipo_diz_quando_o_comando_esta_desativado():
    assert _editor()._tipo_com_estado("Teclado", True) == "Teclado"
    assert _editor()._tipo_com_estado("Teclado", False) == "Teclado (desativado)"


class _Item:
    """O que `_fill_row` pede de um item da tabela; guarda para a conferência."""

    def __init__(self, texto):
        self._texto, self.dados, self._flags, self._dica = texto, {}, 7, ""
        self.primeiro_plano = self.fundo = None

    def text(self):
        return self._texto

    def setData(self, papel, valor):
        self.dados[papel] = valor

    def flags(self):
        return self._flags

    def setFlags(self, valor):
        self._flags = valor

    def setForeground(self, cor):
        self.primeiro_plano = cor

    def setBackground(self, cor):
        self.fundo = cor

    def toolTip(self):
        return self._dica

    def setToolTip(self, texto):
        self._dica = texto


class _TabelaQueGuardaItens:
    def __init__(self, mapa):
        self._automation_map = mapa
        self.itens = {}
        self.table = self  # `_fill_row` fala com `self.table`
        self.palette = lambda: types.SimpleNamespace(color=lambda grupo, papel: ("apagada", grupo, papel))

    def setItem(self, linha, coluna, item):
        self.itens[(linha, coluna)] = item


def _preencher(monkeypatch, mapa, linha):
    """Preenche a linha `linha` da tabela com `_fill_row` e devolve {coluna: item}. Os nomes do Qt que `_fill_row` usa são
    trocados por valores simples, para a conferência valer igual com o Qt real, com o dublê e sem Qt (o que se confere aqui é
    a regra da linha, não o Qt)."""
    editor = _editor()
    monkeypatch.setattr(editor, "QTableWidgetItem", _Item)
    monkeypatch.setattr(editor, "Qt", types.SimpleNamespace(UserRole=256, ItemIsEditable=2))
    monkeypatch.setattr(editor, "QPalette", types.SimpleNamespace(Disabled="Disabled", Text="Text"))
    monkeypatch.setattr(editor, "_normalized_color", lambda cor: ("fundo-do-grupo", cor))
    monkeypatch.setattr(editor, "_text_color_for_background", lambda fundo: ("texto-do-grupo", fundo[1]))
    tabela = _TabelaQueGuardaItens(mapa)
    editor.CommandTableWidget._fill_row(tabela, linha, mapa.commands[linha])
    return {coluna: tabela.itens[(linha, coluna)] for coluna in range(7)}


def test_a_linha_de_um_comando_ativo_continua_exatamente_como_era(monkeypatch):
    itens = _preencher(monkeypatch, _tres(), 0)
    assert itens[2].text() == "Teclado"
    assert all(i.primeiro_plano is None and i.toolTip() == "" for i in itens.values())


def test_a_linha_do_comando_desativado_fica_apagada_e_diz_que_esta_desativada(monkeypatch):
    mapa = _tres()
    mapa.set_commands_enabled({mapa.commands[1].id}, False)
    itens = _preencher(monkeypatch, mapa, 1)
    assert itens[2].text() == "Teclado (desativado)"
    assert all(i.primeiro_plano == ("apagada", "Disabled", "Text") for i in itens.values())
    assert all("desativado" in i.toolTip() and "Ativar selecionados" in i.toolTip() for i in itens.values())
    # A descrição é uma célula editável (o texto vira `cmd.description`): nada de marca dentro dela.
    assert "desativado" not in itens[1].text()


def test_o_numero_da_linha_de_um_grupo_mantem_a_cor_do_grupo_mesmo_desativado(monkeypatch):
    mapa = _tres()
    grupo = CommandGroup(name="Abertura", color="#336699")
    mapa.groups[grupo.id] = grupo
    comando = mapa.commands[0]
    comando.group_id = grupo.id
    mapa.set_commands_enabled({comando.id}, False)
    itens = _preencher(monkeypatch, mapa, 0)
    assert itens[0].primeiro_plano == ("texto-do-grupo", "#336699")  # o # tem fundo colorido e texto próprio
    assert all(itens[c].primeiro_plano == ("apagada", "Disabled", "Text") for c in range(1, 7))
    assert itens[0].toolTip().startswith(grupo.description or grupo.name) and "desativado" in itens[0].toolTip()
