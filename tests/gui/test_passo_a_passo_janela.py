"""Passo a passo (F52) com o PySide6 REAL: a janelinha de controle e a ligação com a janela principal.

Estes testes foram escritos sem poder rodar o Qt (o ambiente de desenvolvimento não o tem): usam só nomes conferidos no
código e passos simples. Se algum falhar na sua máquina, a mensagem mostra o estado real; me envie a saída. Eles NÃO rodam
com o dublê (a janelinha usa `setFocusPolicy`, `move` e `adjustSize`, que o dublê estrito não tem): são pulados.

O que SÓ eles provam, e nada mais no repositório prova:
* a janelinha de verdade é uma janela de ferramenta, sempre por cima, que não aceita o foco, e fechá-la pelo X para a execução;
* os avisos do motor chegam ao controlador na thread da janela (sinal entre threads do Qt) e o passo a passo anda do começo ao
  fim pelos botões, com o motor de verdade (backend de input falso, sem enviar nada ao Windows).

O que NENHUM teste daqui prova, porque exige o Windows de verdade: que clicar na janelinha NÃO tira o foco do programa de
destino. Está na conferência rápida da ficha (md/ENTREGA_PASSO_A_PASSO.md).

Marcador `isolado`: cada teste deste arquivo roda num PROCESSO PRÓPRIO, com tempo limite (ver test_main_window_smoke.py).
"""
import time

import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QInputDialog  # noqa: E402

from automationstudio.core import State  # noqa: E402
from automationstudio.passo_a_passo_ui import ControladorPassoAPasso, PainelPassoAPasso  # noqa: E402
from testsupport.gui_helpers import processar_eventos  # noqa: E402
from testsupport.helpers import events_of, key  # noqa: E402

pytestmark = [pytest.mark.gui, pytest.mark.isolado]


def _esperar(condicao, limite: float = 10.0) -> bool:
    """Processa os eventos do Qt (é assim que os sinais do motor, que vêm de outra thread, chegam) até `condicao()` ou o limite."""
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        processar_eventos(20)
        if condicao():
            return True
    return False


def _nova_automacao_com_duas_teclas(janela, monkeypatch):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Mapa", True)))
    janela._new_map()
    mapa = janela._current_map
    assert mapa is not None and mapa.name == "Mapa"
    mapa.add_command(key("F", 0.0, 0.05))
    mapa.add_command(key("G", 3.0, 0.05))
    janela._on_map_edited()
    return mapa


def _eventos(janela):
    return [(acao, alvo) for _t, acao, alvo in events_of(janela.engine._backend)]


# ------------------------------------------------------------------------------------------------ a janelinha sozinha
def test_a_janelinha_e_de_ferramenta_fica_por_cima_e_nao_aceita_o_foco(gui, gui_real):
    painel = PainelPassoAPasso(lambda: None, lambda: None, lambda: None)
    try:
        assert painel.windowType() == Qt.Tool
        assert bool(painel.windowFlags() & Qt.WindowStaysOnTopHint)
        assert bool(painel.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        assert painel.testAttribute(Qt.WA_ShowWithoutActivating)
        assert painel.objectName() == "PainelPassoAPasso" and painel.rotulo.objectName() == "PassoRotulo"  # a frente visual estiliza por eles
        for botao in (painel.botao_proximo, painel.botao_continuar, painel.botao_parar):
            assert botao.focusPolicy() == Qt.NoFocus, botao.text()
    finally:
        painel.close()


def test_a_janelinha_mostra_o_passo_libera_ou_trava_o_proximo_e_chama_cada_botao(gui, gui_real):
    cliques = []
    painel = PainelPassoAPasso(lambda: cliques.append("proximo"), lambda: cliques.append("continuar"), lambda: cliques.append("parar"))
    try:
        assert not painel.isVisible()
        painel.mostrar_passo("Passo 1 de 3: Apertar e soltar a tecla A", True)
        processar_eventos(50)
        assert painel.isVisible() and painel.rotulo.text() == "Passo 1 de 3: Apertar e soltar a tecla A"
        assert painel.botao_proximo.isEnabled()
        painel.botao_proximo.click()
        painel.botao_continuar.click()
        painel.botao_parar.click()
        assert cliques == ["proximo", "continuar", "parar"]
        painel.mostrar_passo("Executando o passo 1 de 3...", False)
        assert painel.rotulo.text() == "Executando o passo 1 de 3..." and not painel.botao_proximo.isEnabled()
        painel.esconder()
        assert not painel.isVisible()
    finally:
        painel.close()


def test_a_janelinha_abre_dentro_da_area_util_da_tela(gui, gui_real):
    painel = PainelPassoAPasso(lambda: None, lambda: None, lambda: None)
    try:
        painel.mostrar_passo("Passo 1 de 1: Apertar e soltar a tecla A", True)
        processar_eventos(50)
        area = QGuiApplication.primaryScreen().availableGeometry()
        assert area.contains(painel.geometry().center()), (painel.geometry(), area)
    finally:
        painel.close()


def test_fechar_a_janelinha_pelo_x_para_a_execucao(gui, gui_real):
    paradas = []
    painel = PainelPassoAPasso(lambda: None, lambda: None, lambda: paradas.append(1))
    painel.mostrar_passo("Passo 1 de 1: Apertar e soltar a tecla A", True)
    processar_eventos(50)
    painel.close()
    assert paradas == [1]


# ------------------------------------------------------------------------------------------------ com a janela principal
def test_a_janela_principal_tem_o_passo_a_passo_ligado(abrir_janela):
    janela = abrir_janela()
    assert isinstance(janela.passo, ControladorPassoAPasso)
    assert janela.passo.controle.motor is janela.engine
    assert janela.passo.painel is None, "a janelinha só nasce no primeiro pedido"


def test_o_pedido_do_editor_abre_a_janelinha_parada_antes_do_primeiro_comando(abrir_janela, monkeypatch):
    janela = abrir_janela()
    _nova_automacao_com_duas_teclas(janela, monkeypatch)
    janela.command_table.passo_a_passo_requested.emit(set())  # o mesmo sinal que os dois menus do editor emitem
    assert _esperar(lambda: janela.passo.painel is not None and janela.passo.painel.rotulo.text().startswith("Passo 1 de 2"))
    painel = janela.passo.painel
    assert painel.isVisible() and painel.rotulo.text() == "Passo 1 de 2: Apertar e soltar a tecla F"
    assert painel.botao_proximo.isEnabled()
    assert janela.state.state == State.PAUSED and _eventos(janela) == []
    painel.botao_parar.click()
    assert _esperar(lambda: janela.state.state == State.IDLE and not painel.isVisible())


def test_o_passo_a_passo_anda_um_comando_por_vez_pelos_botoes_ate_o_fim(abrir_janela, monkeypatch):
    janela = abrir_janela()
    mapa = _nova_automacao_com_duas_teclas(janela, monkeypatch)
    janela.passo.iniciar(set())
    assert _esperar(lambda: janela.passo.painel is not None and janela.passo.painel.rotulo.text().startswith("Passo 1 de 2"))
    painel = janela.passo.painel
    painel.botao_proximo.click()
    assert _esperar(lambda: painel.rotulo.text().startswith("Passo 2 de 2") and painel.botao_proximo.isEnabled())
    assert _eventos(janela) == [("key_down", "F"), ("key_up", "F")], "o passo 1 inteiro, e nada do passo 2"
    painel.botao_proximo.click()
    assert _esperar(lambda: janela.state.state == State.IDLE and not painel.isVisible())
    assert _eventos(janela) == [("key_down", "F"), ("key_up", "F"), ("key_down", "G"), ("key_up", "G")]
    assert janela.engine.passo_a_passo is None and janela.passo.controle.sessao is None
    assert [c.target for c in mapa.commands] == ["F", "G"], "a automação do usuário não mudou"
    assert mapa.repeat_count == -1 and mapa.name == "Mapa"


def test_continuar_sem_parar_pela_janelinha_termina_o_resto(abrir_janela, monkeypatch):
    janela = abrir_janela()
    _nova_automacao_com_duas_teclas(janela, monkeypatch)
    janela.passo.iniciar(set())
    assert _esperar(lambda: janela.passo.painel is not None and janela.passo.painel.rotulo.text().startswith("Passo 1 de 2"))
    painel = janela.passo.painel
    painel.botao_continuar.click()
    assert _esperar(lambda: janela.state.state == State.IDLE and not painel.isVisible())
    assert _eventos(janela) == [("key_down", "F"), ("key_up", "F"), ("key_down", "G"), ("key_up", "G")]


def test_a_execucao_normal_com_o_passo_a_passo_aberto_para_o_passo_a_passo(abrir_janela, monkeypatch):
    # O motor roda uma automação por vez: executar de verdade enquanto o passo a passo espera para o passo a passo.
    janela = abrir_janela()
    _nova_automacao_com_duas_teclas(janela, monkeypatch)
    janela._current_map.repeat_count = 1
    janela.passo.iniciar(set())
    assert _esperar(lambda: janela.passo.painel is not None and janela.passo.painel.rotulo.text().startswith("Passo 1 de 2"))
    painel = janela.passo.painel
    janela._run_current_map()
    assert _esperar(lambda: janela.state.state == State.IDLE and not painel.isVisible())
    assert _eventos(janela)[-4:] == [("key_down", "F"), ("key_up", "F"), ("key_down", "G"), ("key_up", "G")]
