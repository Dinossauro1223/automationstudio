"""A janela de escolher o programa pelo teclado (25.9, T3a) SOZINHA, com o PySide6 real: `teclado_ui.SeletorDePrograma`.

O que a janela principal faz com ela (abrir sem bloquear, a edição sobreviver ao foco que muda, a troca gravar o programa e o processo esperado) está
em tests/gui/test_teclado_janela.py. Aqui só a janela: o programa de agora vem escolhido, um programa que a lista não conhece continua escolhível,
as setas e o Enter escolhem, o Esc cancela, "Procurar executável…" aceita o arquivo achado e uma busca cancelada não fecha nada.

Só roda com o PySide6 real e o QtTest (no Actions); com os dublês (stub de lógica ou de widgets) cada teste é pulado pela fixture `gui_real`. Os testes pedem `gui` e `gui_real`
de propósito: a catraca "todo teste de janela pede o isolamento de GUI" procura o `gui` pelo nome.
"""
import contextlib
from pathlib import PureWindowsPath

import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QDialog, QFileDialog, QListWidget, QPushButton  # noqa: E402

from automationstudio.teclado_ui import SeletorDePrograma  # noqa: E402
from testsupport.gui_helpers import processar_eventos  # noqa: E402

pytestmark = pytest.mark.gui


def _qtest():
    """O módulo `QTest`, importado só na hora de usar: nenhum dos dois dublês o tem, e o executor mínimo trata o `importorskip` de um módulo como ERRO de
    coleta (o pytest o trata como pulo). Com os dublês nenhum teste chega a chamá-lo: a fixture `gui_real` o pula antes. Com o Qt REAL um QtTest ausente
    estoura aqui, alto (e em tests/gui/test_teclado_teclas_qt.py), em vez de pular em silêncio."""
    from PySide6.QtTest import QTest
    return QTest

PROGRAMAS = [("Microsoft Edge", "msedge.exe"), ("Bloco de Notas", "notepad.exe"), ("Explorador de Arquivos", "explorer.exe")]


@contextlib.contextmanager
def _aberta(atual: str, programas=PROGRAMAS):
    """A janela do programa, mostrada. Ao sair do bloco ela é fechada e destruída na hora (nenhuma sobra para o teste seguinte)."""
    dialogo = SeletorDePrograma(None, atual, list(programas))
    dialogo.show()
    processar_eventos(40)
    try:
        yield dialogo
    finally:
        dialogo.close()
        dialogo.deleteLater()
        processar_eventos(0)


def _lista(dialogo) -> QListWidget:
    lista = dialogo.findChild(QListWidget, "listaDeProgramas")
    assert lista is not None, "a janela do programa não tem a lista"
    return lista


def _botao(dialogo, trecho: str) -> QPushButton:
    botoes = [b for b in dialogo.findChildren(QPushButton) if trecho in b.text()]
    assert len(botoes) == 1, f"esperava um botão com {trecho!r}: {[b.text() for b in dialogo.findChildren(QPushButton)]}"
    return botoes[0]


def test_abre_com_o_programa_de_agora_escolhido(gui, gui_real):
    with _aberta("notepad.exe") as dialogo:
        lista = _lista(dialogo)
        assert lista.count() == len(PROGRAMAS)
        assert lista.currentItem().data(Qt.UserRole) == "notepad.exe"
        assert lista.currentItem().text() == "Bloco de Notas — notepad.exe"
        assert dialogo.valor() == "notepad.exe" and not dialogo.aceito


def test_um_programa_que_a_lista_nao_conhece_vira_um_item_a_mais_e_continua_escolhivel(gui, gui_real):
    atual = r"C:\Apps\meu.exe"
    with _aberta(atual) as dialogo:
        lista = _lista(dialogo)
        assert lista.count() == len(PROGRAMAS) + 1
        assert lista.currentItem().data(Qt.UserRole) == atual
        assert lista.currentItem().text() == f"{PureWindowsPath(atual).stem} — {atual}"
        assert dialogo.valor() == atual


def test_seta_para_baixo_e_enter_escolhem_o_programa_e_aceitam(gui, gui_real):
    with _aberta("msedge.exe") as dialogo:
        lista = _lista(dialogo)
        assert dialogo.valor() == "msedge.exe"
        _qtest().keyClick(lista, Qt.Key_Down)
        assert dialogo.valor() == "notepad.exe" and not dialogo.aceito, "escolher na lista não fecha a janela"
        _qtest().keyClick(lista, Qt.Key_Return)
        processar_eventos(40)
        assert dialogo.aceito and dialogo.result() == QDialog.Accepted
        assert dialogo.valor() == "notepad.exe"
        assert not dialogo.isVisible()


def test_esc_cancela_sem_aceitar(gui, gui_real):
    with _aberta("notepad.exe") as dialogo:
        _qtest().keyClick(_lista(dialogo), Qt.Key_Escape)
        processar_eventos(40)
        assert not dialogo.aceito and dialogo.result() == QDialog.Rejected
        assert not dialogo.isVisible()


def test_o_botao_escolher_e_o_padrao_e_o_cancelar_rejeita(gui, gui_real):
    with _aberta("notepad.exe") as dialogo:
        assert _botao(dialogo, "Escolher").isDefault()
        _botao(dialogo, "Cancelar").click()
        processar_eventos(40)
        assert not dialogo.aceito and dialogo.result() == QDialog.Rejected


def test_procurar_executavel_aceita_na_hora_com_o_arquivo_achado(gui, gui_real, monkeypatch, tmp_path):
    arquivo = tmp_path / "meu_programa.exe"
    arquivo.write_bytes(b"")
    pedidos = []

    def achar(*args, **kwargs):
        pedidos.append(args)
        return str(arquivo), "Executáveis (*.exe)"

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(achar))
    with _aberta("notepad.exe") as dialogo:
        _botao(dialogo, "Procurar").click()
        processar_eventos(40)
        assert len(pedidos) == 1, "o seletor de arquivos abre uma vez"
        assert dialogo.aceito and dialogo.result() == QDialog.Accepted
        assert dialogo.valor() == str(arquivo.resolve()), "o arquivo achado vale mais que o item da lista"


def test_procurar_cancelado_nao_fecha_a_janela_nem_muda_a_escolha(gui, gui_real, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *args, **kwargs: ("", "")))
    with _aberta("notepad.exe") as dialogo:
        _botao(dialogo, "Procurar").click()
        processar_eventos(40)
        assert dialogo.isVisible() and not dialogo.aceito
        assert dialogo.valor() == "notepad.exe"


def test_sem_programa_algum_o_valor_e_vazio(gui, gui_real):
    with _aberta("", programas=[]) as dialogo:
        assert _lista(dialogo).count() == 0
        assert dialogo.valor() == ""
