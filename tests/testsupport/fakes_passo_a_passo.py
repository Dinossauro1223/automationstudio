"""Dublês do passo a passo (F52): motor falso, janela falsa, janelinha falsa, sinais e ponte falsos.

Existem porque o dublê de widgets do ambiente de teste é ESTRITO (um método que ele não tem levanta AttributeError) e não tem
`setFocusPolicy`, `move` nem `adjustSize`, que a janelinha de verdade usa. Com a janelinha falsa o controlador (a parte que decide
o que mostrar e quando) é testado por inteiro, em qualquer ambiente. A janelinha de verdade só roda com o PySide6 de verdade:
tests/gui/test_passo_a_passo_janela.py.
"""
from __future__ import annotations

import queue

from automationstudio.core import State, StateManager


class MotorFalso:
    """O que o controle de passos pede ao motor: estado, `run`, `resume`, `stop` e o gancho `passo_a_passo`."""

    def __init__(self, estado: State = State.IDLE, run_falha: Exception | None = None) -> None:
        self.state = StateManager(estado)
        self.passo_a_passo = None
        self.run_falha = run_falha
        self.executados: list = []
        self.retomadas = 0
        self.paradas = 0

    def run(self, mapa) -> None:
        if self.run_falha is not None:
            raise self.run_falha
        self.executados.append(mapa)
        self.state.transition_to(State.RUNNING)

    def resume(self) -> None:
        self.retomadas += 1
        if self.state.state == State.PAUSED:
            self.state.transition_to(State.RUNNING)

    def stop(self) -> None:
        self.paradas += 1

    def decidir_parar(self, controle, evento) -> None:
        """O motor chegou ao primeiro comando (`evento`) e o gancho disse para parar (o estado ainda é RUNNING)."""
        sessao = controle.sessao
        assert sessao.parar_antes(evento, sessao.mapa)

    def ficar_pausado(self) -> None:
        self.state.transition_to(State.PAUSED)

    def parar_num_passo(self, controle, evento) -> None:
        """As duas coisas, uma depois da outra: é o que o motor faz quando ninguém interfere."""
        self.decidir_parar(controle, evento)
        self.ficar_pausado()


class SinalFalso:
    def __init__(self) -> None:
        self.ligados: list = []

    def connect(self, funcao) -> None:
        self.ligados.append(funcao)

    def emit(self, *argumentos) -> None:
        for funcao in list(self.ligados):
            funcao(*argumentos)


class PonteFalsa:
    """O que o controlador usa da EngineBridge: o sinal state_changed."""

    def __init__(self) -> None:
        self.state_changed = SinalFalso()


class TabelaFalsa:
    """O que o controlador usa da tabela de comandos do editor: o sinal passo_a_passo_requested."""

    def __init__(self) -> None:
        self.passo_a_passo_requested = SinalFalso()


class BarraFalsa:
    def __init__(self) -> None:
        self.mensagens: list[tuple[str, int]] = []

    def showMessage(self, texto: str, tempo: int = 0) -> None:
        self.mensagens.append((texto, tempo))


class JanelaFalsa:
    """O que o controlador usa da janela principal: `engine`, `_current_map` e `status_bar`."""

    def __init__(self, motor, mapa=None) -> None:
        self.engine = motor
        self._current_map = mapa
        self.status_bar = BarraFalsa()


class PainelFalso:
    """A janelinha de controle sem Qt: guarda o que foi mostrado e entrega cada mudança numa fila (para os testes que rodam
    o motor de verdade e esperam, sem dormir, que a janelinha mostre o próximo passo)."""

    def __init__(self, ao_proximo, ao_continuar, ao_parar) -> None:
        self.ao_proximo, self.ao_continuar, self.ao_parar = ao_proximo, ao_continuar, ao_parar
        self.mostrados: list[tuple[str, bool]] = []
        self.escondidos = 0
        self.visivel = False
        self.fila: queue.Queue = queue.Queue()

    def mostrar_passo(self, texto: str, pode_avancar: bool) -> None:
        self.mostrados.append((texto, bool(pode_avancar)))
        self.visivel = True
        self.fila.put((texto, bool(pode_avancar)))

    def esconder(self) -> None:
        self.escondidos += 1
        self.visivel = False
        self.fila.put(None)

    def esperar(self, condicao):
        """Espera, em até 10 s, a mudança que `condicao(item)` aceita (item = (texto, pode_avancar) ou None se escondeu)."""
        while True:
            item = self.fila.get(timeout=10)
            if condicao(item):
                return item
