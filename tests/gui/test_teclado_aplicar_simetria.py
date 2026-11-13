"""A edição pelo teclado grava como a barra lateral (25.9, T3a; ficha md/FICHA_TECLADO_T3_25_9.md, decisão T3-6).

Não pode haver duas verdades sobre "o que é trocar a tecla de um comando": o que `teclado_aplicar` grava tem de ser, campo por campo,
o que o `CommandDialog` (a barra lateral) grava quando se faz a mesma troca nele. Aqui o MESMO comando é editado pelos dois caminhos e as
saídas completas (`Command.to_dict()`) são comparadas.

A única diferença de propósito: ao trocar o programa pelo teclado, o processo esperado (`wait_process`) acompanha se era o do programa
antigo; a barra lateral deixa esse campo para o dono, que o vê na tela ao lado. Por isso o programa é comparado sem esse campo, e o
acompanhamento é provado à parte (tests/unit/test_teclado_aplicar.py).

Roda com o PySide6 real e, no desenvolvimento (sem Qt), contra o dublê funcional parcial (AS_TEST_QT_STUB=widgets).
"""
import copy

import pytest

pytest.importorskip("PySide6.QtWidgets")

from automationstudio import core  # noqa: E402
from automationstudio.command_editor import PROGRAMAS_COMUNS, CommandDialog, programas_conhecidos  # noqa: E402
from automationstudio.core import ActionType, AutomationMap, Command, InputType  # noqa: E402
from automationstudio.teclado_aplicar import aplicar_alvo, aplicar_tempo, aplicar_texto, marcar  # noqa: E402

pytestmark = pytest.mark.gui

K, B, T, A = InputType.KEY, InputType.MOUSE_BUTTON, InputType.TEXT, InputType.APP_OPEN
TECLA, BOTAO, TEXTO, APLICATIVO, SO_APERTA = 0, 1, 2, 3, 4


def _mapa() -> AutomationMap:
    """Valores todos na grade do milissegundo (a barra lateral os guarda em caixas de 3 casas): assim a comparação é de verdade igual."""
    return AutomationMap(name="Simetria", commands=[
        Command(id="t1", type=K, target="E", start=0.0, duration=0.2, delay=0.05, delay_suggested=0.05, description="primeira", group="G", group_id="g1"),
        Command(id="b1", type=B, target="left", start=0.5, duration=0.1, description="clique"),
        Command(id="x1", type=T, text="olá", start=1.0, duration=0.0, delay=0.1, delay_suggested=0.1),
        Command(id="a1", type=A, target="notepad.exe", wait_process="notepad.exe", wait_timeout=5.0, wait_stable_ms=700,
                wait_after_open=0.4, start=1.5, description="abre"),
        # Duração 0,1 de propósito: a barra lateral troca uma duração 0 por 0,1 ao abrir (`_load_number(self.duration, c.duration or .1)`, um
        # padrão dela). O teclado não inventa duração: um comando só-aperta com duração 0 continua com 0 (provado em test_teclado_aplicar.py).
        Command(id="t2", type=K, target="Q", action=ActionType.PRESS, start=4.0, duration=0.1),
    ])


def _pela_barra(indice, preencher) -> dict:
    """O comando `indice` como a barra lateral o devolve depois de `preencher(dialogo)` (a janela passa o comando do próprio mapa)."""
    dialogo = CommandDialog(command=copy.deepcopy(_mapa().commands[indice]))
    preencher(dialogo)
    return dialogo.result_command().to_dict()


def _pelo_teclado(indice, gravar) -> dict:
    mapa = _mapa()
    resultado = gravar(mapa, marcar(mapa, indice))
    assert resultado.ok, resultado.mensagem
    return mapa.commands[indice].to_dict()


def _botao(dialogo, nome) -> None:
    dialogo.target_combo.setCurrentIndex(dialogo.target_combo.findData(nome))


CASOS = [
    ("tecla", TECLA, lambda d: d.target_combo.setCurrentText("Z"), lambda m, k: aplicar_alvo(m, k, "Z")),
    ("tecla-so-aperta", SO_APERTA, lambda d: d.target_combo.setCurrentText("Z"), lambda m, k: aplicar_alvo(m, k, "Z")),
    ("botao", BOTAO, lambda d: _botao(d, "x2"), lambda m, k: aplicar_alvo(m, k, "x2")),
    ("texto", TEXTO, lambda d: d.text_edit.setPlainText("novo texto com acentuação"), lambda m, k: aplicar_texto(m, k, "novo texto com acentuação")),
    ("tempo-da-tecla", TECLA, lambda d: d.duration.setValue(0.75), lambda m, k: aplicar_tempo(m, k, 0.75)),
    ("tempo-do-botao", BOTAO, lambda d: d.duration.setValue(0.75), lambda m, k: aplicar_tempo(m, k, 0.75)),
]
IDS = [caso[0] for caso in CASOS]


@pytest.mark.parametrize("nome, indice, preencher, gravar", CASOS, ids=IDS)
def test_o_comando_sai_igual_pela_barra_lateral_e_pelo_teclado(gui, nome, indice, preencher, gravar):
    core.set_runtime_defaults(text_char_interval=0.02)  # com intervalo 0 a duração do texto seria sempre 0 e a prova não valeria nada
    assert _pelo_teclado(indice, gravar) == _pela_barra(indice, preencher)


def test_o_programa_sai_igual_menos_o_processo_esperado_que_o_teclado_acompanha(gui):
    def preencher(dialogo):
        dialogo.target_combo.setCurrentIndex(dialogo.target_combo.findData("msedge.exe"))
    barra = _pela_barra(APLICATIVO, preencher)
    teclado = _pelo_teclado(APLICATIVO, lambda m, k: aplicar_alvo(m, k, "msedge.exe"))
    assert barra["target"] == teclado["target"] == "msedge.exe"
    assert barra["wait_process"] == "notepad.exe", "a barra lateral não troca o processo esperado sozinha"
    assert teclado["wait_process"] == "msedge.exe", "o teclado o leva junto: não deixa a automação esperando o Bloco de Notas"
    assert {k: v for k, v in barra.items() if k != "wait_process"} == {k: v for k, v in teclado.items() if k != "wait_process"}


def test_a_barra_lateral_oferece_os_mesmos_programas_que_o_teclado_vai_oferecer(gui):
    dialogo = CommandDialog()
    dialogo.type_combo.setCurrentIndex(dialogo.type_combo.findData(A))
    no_alvo = [dialogo.target_combo.itemData(i) for i in range(dialogo.target_combo.count())]
    assert [exe for _rotulo, exe in programas_conhecidos()] == [exe for exe in no_alvo if exe]
    esperados = [dialogo.wait_process_edit.itemData(i) for i in range(dialogo.wait_process_edit.count())]
    assert [exe for _rotulo, exe in PROGRAMAS_COMUNS] == [exe for exe in esperados if exe]
