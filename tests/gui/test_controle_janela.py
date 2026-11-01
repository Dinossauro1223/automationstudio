"""Pausar e continuar pelas teclas de controle (F9 e F10) na janela principal (MainWindow) com o PySide6 REAL.

Estes testes foram escritos sem poder rodar o Qt (o ambiente de desenvolvimento não o tem), como os de test_main_window_smoke.py e
test_ativacao_janela.py: usam só nomes conferidos no código e passos simples. Se algum falhar na sua máquina, a mensagem mostra o
estado real; me envie a saída. Não rodam com o dublê (a janela principal não cabe nele): são pulados.

O que eles confirmam e nenhum outro teste confirma: o disparo da tecla (`_on_hotkey_triggered`, ou o callback que o gerente de
atalhos chama ao apertar F9/F10) chega ao motor da janela, o título mostra o estado, a barra de status recebe a mensagem, e uma
automação de verdade (com o relógio de verdade) para de enviar entradas na pausa e termina o que falta depois. A lógica, os textos
e as corridas estão em tests/unit/test_controle_execucao.py e tests/engine/test_engine_control.py; a ligação no código-fonte, em
tests/static/test_ligacao_controle.py.

As mensagens são conferidas pelas chamadas a `status_bar.showMessage` (uma espiã), não pelo texto que está na barra: enquanto a
automação executa, a janela escreve ali cada tecla ou clique executado ("[0.05s] key_up F"), e uma dessas linhas, ainda na fila
do Qt, pode cobrir a mensagem sem que isso seja defeito.

Critérios da ficha (md/ESPEC_PAUSA_TECLAS.md): PAU-01, PAU-02, PAU-03 e PAU-06 (a parte com a janela).
Isolamento e marcador `isolado`: como em test_main_window_smoke.py.
"""
import time

import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtWidgets import QInputDialog  # noqa: E402

from automationstudio.core import State, parse_combo  # noqa: E402
from testsupport.helpers import events_of, join_engine, key, pressed_balance  # noqa: E402

pytestmark = [pytest.mark.gui, pytest.mark.isolado]

PAUSADA = "Automação pausada. Aperte F10 para continuar."
RETOMADA = "Automação retomada."


def _nova_automacao(janela, monkeypatch, nome="Mapa"):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: (nome, True)))
    janela._new_map()
    assert janela._current_map is not None and janela._current_map.name == nome, janela._current_map
    return janela._current_map


def _espiar_mensagens(janela, monkeypatch) -> list[str]:
    """Todas as mensagens que a janela manda para a barra de status, em ordem (a barra em si mostra só a última)."""
    mensagens, original = [], janela.status_bar.showMessage

    def espia(texto, prazo=0):
        mensagens.append(texto)
        return original(texto, prazo)

    monkeypatch.setattr(janela.status_bar, "showMessage", espia)
    return mensagens


def _processar():
    QCoreApplication.processEvents()


def _acoes(janela) -> list[tuple]:
    return [(acao, alvo) for _t, acao, alvo in events_of(janela.engine._backend)]


def _esperar(condicao, prazo=5.0) -> bool:
    """Espera a condição sem deixar a fila de eventos do Qt parada (o motor manda sinais para a janela)."""
    fim = time.monotonic() + prazo
    while time.monotonic() < fim:
        _processar()
        if condicao():
            return True
        time.sleep(0.01)
    return condicao()


def _exigir_atalhos(janela):
    """Os atalhos globais só são registrados quando o pynput está disponível (a janela pula o registro sem ele)."""
    if not janela.hotkey_manager.available:
        pytest.skip("o gerenciador de atalhos não está disponível (pynput não instalado): nada é registrado")


# ------------------------------------------------------------------------------------------------ PAU-01 / PAU-02
def test_f9_pausa_a_automacao_executando_e_f10_termina_o_que_faltava(abrir_janela, monkeypatch):                          # PAU-01 / PAU-02
    janela = abrir_janela()
    mensagens = _espiar_mensagens(janela, monkeypatch)
    mapa = _nova_automacao(janela, monkeypatch)
    mapa.repeat_count = 1  # o mapa criado pelo botão repete para sempre
    mapa.add_command(key("F", 0.0, 0.3))  # F fica apertada de 0 a 0,3 s
    mapa.add_command(key("G", 0.5, 0.05))
    janela._on_map_edited()
    janela._run_current_map()
    assert _esperar(lambda: ("key_down", "F") in _acoes(janela)), _acoes(janela)

    janela._on_hotkey_triggered("control:pause")  # o que a janela faz quando F9 dispara
    _processar()
    assert janela.state.state == State.PAUSED, janela.state.state
    assert "PAUSADO" in janela.windowTitle(), janela.windowTitle()
    assert PAUSADA in mensagens, mensagens
    time.sleep(0.2)  # o motor segue até o ponto de controle (a soltura de F, em 0,3 s) e para ali
    _processar()
    parado = _acoes(janela)
    time.sleep(0.45)  # com a anterior, mais que o tempo que faltava para a soltura de F e para G: um motor que ignorasse a pausa já teria enviado os dois
    _processar()
    assert _acoes(janela) == parado == [("key_down", "F")], "nada novo na pausa, e F continua apertada: " + str(_acoes(janela))

    janela._on_hotkey_triggered("control:resume")  # F10
    _processar()
    assert RETOMADA in mensagens, mensagens
    join_engine(janela.engine, timeout=10.0)
    assert _acoes(janela) == [("key_down", "F"), ("key_up", "F"), ("key_down", "G"), ("key_up", "G")], \
        "a retomada termina o que faltava: nada repetido, nada pulado"
    assert janela.state.state == State.IDLE


def test_o_callback_do_atalho_registrado_para_f9_e_f10_pausa_e_continua(abrir_janela):                                     # PAU-01 / PAU-02
    """O elo que faltava no achado 2.11: o callback que o gerente de atalhos chama ao apertar a tecla, passando pela ponte até
    a janela, chega ao motor."""
    janela = abrir_janela()
    _exigir_atalhos(janela)
    janela.state.transition_to(State.RUNNING)  # como se uma automação estivesse executando
    janela.hotkey_manager._bindings[parse_combo("F9")][1]()  # o que o gerente faz ao apertar F9
    _processar()
    assert janela.state.state == State.PAUSED, janela.state.state
    janela.hotkey_manager._bindings[parse_combo("F10")][1]()
    _processar()
    assert janela.state.state == State.RUNNING, janela.state.state
    janela.engine.stop()


def test_a_mensagem_cita_a_tecla_de_continuar_configurada(abrir_janela, monkeypatch):                                       # PAU-01
    janela = abrir_janela()
    mensagens = _espiar_mensagens(janela, monkeypatch)
    janela.settings.set_control_hotkeys({"resume": "CTRL+F10"})
    janela._register_all_hotkeys()
    janela.state.transition_to(State.RUNNING)
    janela._on_hotkey_triggered("control:pause")
    _processar()
    assert janela.state.state == State.PAUSED
    assert "Automação pausada. Aperte CTRL+F10 para continuar." in mensagens, mensagens
    janela.engine.stop()


# ------------------------------------------------------------------------------------------------ PAU-03
@pytest.mark.parametrize("caminho", [(), (State.RECORDING,)], ids=["parado", "gravando"])
def test_f9_e_f10_sem_automacao_executando_nao_fazem_nada(abrir_janela, monkeypatch, caminho):                              # PAU-03
    janela = abrir_janela()
    for passo in caminho:
        janela.state.transition_to(passo)
    _processar()
    estado, titulo = janela.state.state, janela.windowTitle()
    mensagens = _espiar_mensagens(janela, monkeypatch)
    janela._on_hotkey_triggered("control:pause")
    janela._on_hotkey_triggered("control:resume")
    _processar()
    assert janela.state.state == estado
    assert janela.windowTitle() == titulo
    assert [m for m in mensagens if m.startswith("Automação pausada") or m.startswith("Automação retomada")] == [], \
        "sem automação executando, as duas teclas não dizem nada: " + str(mensagens)
    janela.engine.emergency_stop()


# ------------------------------------------------------------------------------------------------ PAU-06
def _executar_e_pausar(janela, monkeypatch):
    """Põe uma automação para executar, espera a tecla F apertar e a pausa pela tecla F9. Devolve o mapa."""
    mapa = _nova_automacao(janela, monkeypatch)
    mapa.repeat_count = 1
    mapa.add_command(key("F", 0.0, 0.3))  # F fica apertada de 0 a 0,3 s: a pausa chega com ela ainda apertada
    mapa.add_command(key("G", 0.5, 0.05))
    janela._on_map_edited()
    janela._run_current_map()
    assert _esperar(lambda: ("key_down", "F") in _acoes(janela)), _acoes(janela)
    janela._on_hotkey_triggered("control:pause")
    _processar()
    assert janela.state.state == State.PAUSED, janela.state.state
    return mapa


@pytest.mark.parametrize("como", ["emergencia", "botao_parar", "tecla_da_automacao"])
def test_com_a_automacao_pausada_a_parada_continua_valendo_e_nada_fica_apertado(abrir_janela, monkeypatch, como):          # PAU-06
    """O que o plano da frente de funções pede (md/PLANO_FUNCOES.md, seção 2, item 4): a pausa não tira do usuário o jeito de
    parar. As três formas de parar (a tecla de parar tudo, o botão ■ Parar e a tecla da própria automação) encerram uma
    automação pausada, e a tecla que ficou apertada na pausa é solta no fim."""
    janela = abrir_janela()
    mapa = _executar_e_pausar(janela, monkeypatch)
    assert janela.btn_stop.isEnabled(), "pausada, o botão ■ Parar continua ativo"
    assert not janela.btn_run.isEnabled(), "pausada, não se começa outra execução por cima"
    if como == "emergencia":
        janela._on_hotkey_triggered("control:emergency")  # F12
    elif como == "botao_parar":
        janela.btn_stop.trigger()
    else:
        janela._on_hotkey_triggered("map:" + mapa.name)  # a tecla que inicia a automação também a para
    assert _esperar(lambda: janela.state.state == State.IDLE), janela.state.state
    join_engine(janela.engine, timeout=10.0)
    _processar()
    assert janela.state.state == State.IDLE
    assert pressed_balance(janela.engine._backend) == {}, "nada fica apertado depois de parar"
    assert ("key_down", "G") not in _acoes(janela), "uma automação parada não segue enviando entradas: " + str(_acoes(janela))
    assert janela.btn_run.isEnabled() and not janela.btn_stop.isEnabled(), "parada, os botões voltam ao estado de repouso"
