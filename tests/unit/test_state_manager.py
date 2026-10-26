"""StateManager: tabela de transições e notificações."""
import pytest

from automationstudio.core import InvalidStateTransition, State, StateManager

PERMITIDAS = {
    State.IDLE: {State.RECORDING, State.RUNNING},
    State.RECORDING: {State.ERROR, State.IDLE},
    State.RUNNING: {State.ERROR, State.PAUSED, State.STOPPING},
    State.PAUSED: {State.ERROR, State.RUNNING, State.STOPPING},
    State.STOPPING: {State.ERROR, State.IDLE},
    State.ERROR: {State.IDLE},
}


@pytest.mark.parametrize("origem", list(PERMITIDAS), ids=[s.value for s in PERMITIDAS])
def test_tabela_de_transicoes(origem):
    gerente = StateManager(origem)
    assert {alvo for alvo in State if gerente.can_transition_to(alvo)} == PERMITIDAS[origem]


def test_transicao_invalida_levanta_e_nao_muda_o_estado():
    gerente = StateManager(State.RECORDING)
    with pytest.raises(InvalidStateTransition):
        gerente.transition_to(State.RUNNING)
    assert gerente.state == State.RECORDING


def test_transicao_invalida_nao_e_value_error():
    # A janela captura (ValueError, InvalidStateTransition): o motor não pode contar com herança de ValueError.
    assert not issubclass(InvalidStateTransition, ValueError)


def test_force_to_idle_funciona_de_qualquer_estado_e_notifica():
    vistos = []
    gerente = StateManager(State.RUNNING)
    gerente.on_change(lambda anterior, novo: vistos.append((anterior, novo)))  # o observador recebe (anterior, novo)
    gerente.force_to_idle()
    assert gerente.state == State.IDLE and vistos == [(State.RUNNING, State.IDLE)]
