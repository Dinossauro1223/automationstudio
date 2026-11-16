"""Executar a partir daqui (função F50): rodar do comando clicado até o fim da lista, sem rodar o mapa todo de novo.

A função reaproveita o "Testar selecionados" que já existe: a tabela separa os comandos de "daqui" até o fim e entrega ao teste
da janela principal, que monta um mapa isolado (uma passada, na velocidade do mapa, começando em t=0). O que se prova aqui, sem
janela:

* a regra de quais comandos entram (`_ids_a_partir_daqui`): do primeiro dos escolhidos, na ordem da LISTA, até o fim, sem os
  desativados;
* de ponta a ponta, com o método REAL da janela principal (`_test_selected_commands`) chamado com um `self` de mentira e o motor
  de verdade com relógio virtual: o que roda é exatamente o que a execução normal rodaria dali em diante, com os mesmos intervalos,
  só que começando na hora, e o mapa aberto não é mexido.

Fica de fora, porque só o Qt real mostra: os dois menus abrindo com o item (a ligação ao código está em
tests/static/test_ligacao_executar_a_partir_daqui.py) e o teste rodando numa janela de verdade. Ver
md/ENTREGA_EXECUTAR_A_PARTIR_DAQUI.md.
"""
import types

import pytest

from automationstudio.core import State
from testsupport.fake_clock import FakeClock
from testsupport.helpers import events_of, key, make_map, run_to_end


def _editor():
    from automationstudio import command_editor
    return command_editor


def _cinco(**desativados):
    """A..E sem sobreposição: A 0,0 | B 1,0 | C 2,0 | D 3,5 | E 5,0 (cada tecla fica 0,2 s). `desativados`: nomes para desativar."""
    mapa = make_map([key("A", 0.0, 0.2), key("B", 1.0, 0.2), key("C", 2.0, 0.2), key("D", 3.5, 0.2), key("E", 5.0, 0.2)])
    for cmd in mapa.commands:
        if cmd.target in desativados:
            cmd.enabled = False
    return mapa


def _id(mapa, alvo):
    return next(c.id for c in mapa.commands if c.target == alvo)


def _alvos(mapa, ids):
    por_id = {c.id: c.target for c in mapa.commands}
    return [por_id[i] for i in ids]


# ------------------------------------------------------------------------------------------------- a regra
def test_vai_do_comando_escolhido_ate_o_fim_da_lista():
    mapa = _cinco()
    assert _alvos(mapa, _editor()._ids_a_partir_daqui(mapa.commands, {_id(mapa, "C")})) == ["C", "D", "E"]
    assert _alvos(mapa, _editor()._ids_a_partir_daqui(mapa.commands, {_id(mapa, "A")})) == ["A", "B", "C", "D", "E"]


def test_o_ultimo_comando_roda_sozinho():
    mapa = _cinco()
    assert _alvos(mapa, _editor()._ids_a_partir_daqui(mapa.commands, {_id(mapa, "E")})) == ["E"]


def test_com_varios_escolhidos_vale_o_de_cima_da_lista_e_nao_a_ordem_do_conjunto():
    mapa = _cinco()
    escolhidos = {_id(mapa, "D"), _id(mapa, "B"), _id(mapa, "E")}
    assert _alvos(mapa, _editor()._ids_a_partir_daqui(mapa.commands, escolhidos)) == ["B", "C", "D", "E"]


def test_pula_os_desativados_porque_a_execucao_os_ignoraria_de_qualquer_jeito():
    mapa = _cinco(C=True, E=True)
    assert _alvos(mapa, _editor()._ids_a_partir_daqui(mapa.commands, {_id(mapa, "B")})) == ["B", "D"]


def test_se_o_clicado_esta_desativado_comeca_no_proximo_ativo():
    mapa = _cinco(C=True)
    assert _alvos(mapa, _editor()._ids_a_partir_daqui(mapa.commands, {_id(mapa, "C")})) == ["D", "E"]


def test_vazio_quando_nao_sobra_comando_ativo_para_o_item_ficar_cinza():
    mapa = _cinco(D=True, E=True)
    assert _editor()._ids_a_partir_daqui(mapa.commands, {_id(mapa, "D")}) == []
    assert _editor()._ids_a_partir_daqui(mapa.commands, {_id(mapa, "E")}) == []


def test_vazio_quando_nada_foi_escolhido_ou_o_id_nao_existe_ou_a_lista_e_vazia():
    mapa = _cinco()
    assert _editor()._ids_a_partir_daqui(mapa.commands, set()) == []
    assert _editor()._ids_a_partir_daqui(mapa.commands, {"nao-existe"}) == []
    assert _editor()._ids_a_partir_daqui([], {_id(mapa, "A")}) == []


def test_a_ordem_e_a_da_lista_mesmo_quando_os_horarios_nao_sao_crescentes():
    # A lista é a sequência do mapa: "daqui" é o que está abaixo na tabela, não o que tem horário maior.
    mapa = make_map([key("A", 0.0, 0.2), key("B", 5.0, 0.2), key("C", 1.0, 0.2)])
    assert _alvos(mapa, _editor()._ids_a_partir_daqui(mapa.commands, {_id(mapa, "B")})) == ["B", "C"]


def test_aceita_qualquer_sequencia_e_nao_mexe_na_lista():
    mapa = _cinco()
    antes = [(c.id, c.enabled) for c in mapa.commands]
    ids = (c.id for c in [mapa.commands[2]])  # um gerador, não um conjunto
    assert _alvos(mapa, _editor()._ids_a_partir_daqui(iter(mapa.commands), set(ids))) == ["C", "D", "E"]
    assert [(c.id, c.enabled) for c in mapa.commands] == antes


# ------------------------------------------------------------------------------------------------- de ponta a ponta
class _Motor:
    def __init__(self):
        self.mapas = []

    def run(self, mapa):
        self.mapas.append(mapa)


class _Barra:
    def __init__(self):
        self.mensagens = []

    def showMessage(self, texto, *_args):
        self.mensagens.append(texto)


class _JanelaDeMentira:
    """O mínimo que `MainWindow._test_selected_commands` usa de `self`."""

    def __init__(self, mapa):
        self._current_map = mapa
        self.state = types.SimpleNamespace(state=State.IDLE)
        self.engine = _Motor()
        self.status_bar = _Barra()

    def _show_detailed_error(self, titulo, exc):
        raise exc  # um erro de verdade tem de derrubar o teste, não sumir numa caixa de diálogo


def _executar_daqui(mapa, alvo):
    """Faz o que o item do menu faz: separa os comandos de "daqui" e entrega ao teste da janela principal (método real).
    Devolve (janela de mentira, mapa de teste montado ou None)."""
    from automationstudio.main_window import MainWindow
    janela = _JanelaDeMentira(mapa)
    ids = _editor()._ids_a_partir_daqui(mapa.commands, {_id(mapa, alvo)})
    MainWindow._test_selected_commands(janela, set(ids))
    return janela, (janela.engine.mapas[0] if janela.engine.mapas else None)


def _rodar(mapa) -> list[tuple]:
    """Roda o mapa com um relógio virtual NOVO (os horários saem a partir de zero) e devolve os eventos."""
    from automationstudio.input_system import ExecutionEngine, MockInputBackend
    relogio = FakeClock()
    backend = MockInputBackend(clock=relogio)
    terminou, erros = run_to_end(ExecutionEngine(backend, None, clock=relogio), mapa)
    assert terminou and not erros, erros
    return events_of(backend)


def _a_partir_de(eventos, alvos, inicio):
    """Os eventos da execução normal só dos `alvos`, com o horário contado a partir de `inicio`."""
    return [(round(t - inicio, 6), acao, alvo) for t, acao, alvo in eventos if alvo in alvos]


def test_de_ponta_a_ponta_roda_o_que_a_execucao_normal_rodaria_dali_em_diante_com_os_mesmos_intervalos():
    mapa = _cinco()
    janela, teste = _executar_daqui(mapa, "C")
    assert teste is not None
    assert [(round(t, 6), a, x) for t, a, x in _rodar(teste)] == _a_partir_de(_rodar(_cinco()), {"C", "D", "E"}, 2.0)
    assert [c.target for c in teste.commands] == ["C", "D", "E"]
    assert [round(c.start, 6) for c in teste.commands] == [0.0, 1.5, 3.0]  # começa na hora, intervalos de antes


def test_o_teste_e_isolado_uma_passada_na_velocidade_do_mapa_e_sem_mexer_no_mapa_aberto():
    mapa = _cinco()
    mapa.speed, mapa.repeat_count = 2.0, 7
    antes = mapa.to_dict()
    janela, teste = _executar_daqui(mapa, "C")
    assert (teste.repeat_count, teste.speed) == (1, 2.0)
    assert mapa.to_dict() == antes
    assert not {c.id for c in teste.commands} & {c.id for c in mapa.commands}  # cópias com ids novos


def test_de_ponta_a_ponta_com_um_desativado_no_meio_os_intervalos_dos_outros_nao_mudam():
    mapa = _cinco(D=True)
    janela, teste = _executar_daqui(mapa, "C")
    eventos = [(round(t, 6), a, x) for t, a, x in _rodar(teste)]
    assert eventos == _a_partir_de(_rodar(_cinco(D=True)), {"C", "E"}, 2.0)
    assert [(a, x) for _t, a, x in eventos] == [("key_down", "C"), ("key_up", "C"), ("key_down", "E"), ("key_up", "E")]
    assert [round(c.start, 6) for c in teste.commands] == [0.0, 3.0]


def test_se_o_clicado_esta_desativado_o_teste_nao_comeca_com_uma_espera():
    mapa = _cinco(C=True)
    janela, teste = _executar_daqui(mapa, "C")
    assert [c.target for c in teste.commands] == ["D", "E"]
    assert [t for t, _a, _x in _rodar(teste)][0] == 0.0  # o D roda na hora, sem esperar o lugar do C desativado


def test_o_status_conta_so_o_que_vai_rodar():
    mapa = _cinco(D=True)
    janela, _teste = _executar_daqui(mapa, "B")
    assert janela.status_bar.mensagens == ["Testando 3 comando(s) selecionado(s)."]  # B, C e E (o D está desativado)


def test_sem_comandos_a_executar_nada_e_enviado_ao_motor():
    mapa = _cinco(D=True, E=True)
    janela, teste = _executar_daqui(mapa, "D")
    assert teste is None and janela.engine.mapas == [] and janela.status_bar.mensagens == []
