"""A tradução de teclas com o Qt de verdade (25.9, T3a): `automationstudio/teclado_teclas.py`.

A tabela (quem vira o quê) é provada sem Qt em tests/unit/test_teclado_teclas.py, com um Qt falso. O que o Qt falso NÃO prova e este arquivo
prova: que cada nome de atributo que o tradutor lê (`Qt.Key_Ccedilla`, `Qt.KeypadModifier`...) existe no PySide6 de verdade, e que um
QKeyEvent real, com a máscara de modificadores e o código virtual reais, chega à `Tecla` certa.

Só roda com o PySide6 real (no Actions); sem ele (stub de lógica ou dublê de widgets) o `gui_real` pula. Os testes pedem `gui` e `gui_real`
de propósito: a catraca "todo teste de janela pede o isolamento de GUI" procura o `gui` pelo nome (o `gui_real` o traz junto, mas não aparece).
"""
import pytest

pytest.importorskip("PySide6.QtWidgets")

pytestmark = pytest.mark.gui


def _qt():
    from PySide6.QtCore import Qt
    return Qt


def _evento(tecla, texto="", modificadores=None, vk=None):
    """Um QKeyEvent de pressionar. Com `vk` usa o construtor que leva o código virtual nativo (o que o Windows entrega de verdade)."""
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    Qt = _qt()
    modificadores = Qt.NoModifier if modificadores is None else modificadores
    if vk is None:
        return QKeyEvent(QEvent.KeyPress, tecla, modificadores, texto)
    return QKeyEvent(QEvent.KeyPress, tecla, modificadores, 0, vk, 0, texto)


def _tradutor():
    from automationstudio.teclado_teclas import TradutorDeTeclas
    return TradutorDeTeclas(_qt())


def test_o_tradutor_se_constroi_com_o_qt_de_verdade(gui, gui_real):
    """Um atributo `Key_*` com o nome errado levantaria AttributeError aqui."""
    _tradutor()


def test_cada_tecla_da_tabela_chega_do_evento_real_ao_nome_do_studio(gui, gui_real):
    from automationstudio import teclado_teclas as tt
    Qt = _qt()
    tradutor = _tradutor()
    for atributo, nome in (*tt._LETRAS, *tt._DIGITOS, *tt._FUNCAO, *tt._NOMEADAS):
        evento = _evento(getattr(Qt, atributo))
        esperado = "ENTER" if atributo == "Key_Enter" else nome
        assert tradutor.traduzir(evento, captura=False).nome == esperado, atributo
        assert tradutor.traduzir(evento, captura=True).nome == ("NUMENTER" if atributo == "Key_Enter" else nome), atributo


def test_o_teclado_numerico_com_o_modificador_de_verdade(gui, gui_real):
    from automationstudio import teclado_teclas as tt
    Qt = _qt()
    tradutor = _tradutor()
    for atributo, nome in tt._NUMERICO:
        evento = _evento(getattr(Qt, atributo), modificadores=Qt.KeypadModifier)
        assert tradutor.traduzir(evento, captura=True).nome == nome, atributo
        assert tradutor.traduzir(evento, captura=False).nome == ("" if atributo not in {f"Key_{i}" for i in range(10)} else atributo[-1]), atributo
    enter = _evento(Qt.Key_Enter, modificadores=Qt.KeypadModifier)
    assert tradutor.traduzir(enter, captura=False).nome == "ENTER"
    assert tradutor.traduzir(enter, captura=True).nome == "NUMENTER"


def test_shift_mais_digito_chega_como_simbolo_e_o_codigo_virtual_o_resolve(gui, gui_real):
    Qt = _qt()
    evento = _evento(Qt.Key_Exclam, "!", Qt.ShiftModifier, vk=0x31)
    tecla = _tradutor().traduzir(evento)
    assert (tecla.nome, tecla.shift, tecla.texto) == ("1", True, "!")


def test_os_modificadores_reais_viram_flags_e_o_da_propria_tecla_e_apagado(gui, gui_real):
    from automationstudio.teclado_edicao import Tecla
    Qt = _qt()
    tradutor = _tradutor()
    assert tradutor.traduzir(_evento(Qt.Key_Z, "\x1a", Qt.ControlModifier)) == Tecla("Z", "", ctrl=True)
    assert tradutor.traduzir(_evento(Qt.Key_Return, "\r", Qt.ShiftModifier)) == Tecla("ENTER", "", shift=True)
    assert tradutor.traduzir(_evento(Qt.Key_F4, "", Qt.AltModifier)) == Tecla("F4", "", alt=True)
    assert tradutor.traduzir(_evento(Qt.Key_Control, "", Qt.ControlModifier)) == Tecla("CTRL")
    assert tradutor.traduzir(_evento(Qt.Key_Shift, "", Qt.ShiftModifier)) == Tecla("SHIFT")
    assert tradutor.traduzir(_evento(Qt.Key_Alt, "", Qt.AltModifier)) == Tecla("ALT")
    combinado = Qt.ControlModifier | Qt.AltModifier
    assert tradutor.traduzir(_evento(Qt.Key_AltGr, "", combinado)) == Tecla("ALTGR")


def test_o_apostrofo_sai_em_texto(gui, gui_real):
    from automationstudio.teclado_edicao import Tecla
    Qt = _qt()
    assert _tradutor().traduzir(_evento(Qt.Key_Apostrophe, "'")) == Tecla("", "'")


def test_tecla_que_o_studio_nao_conhece_tem_nome_vazio(gui, gui_real):
    Qt = _qt()
    tradutor = _tradutor()
    for atributo in ("Key_Semicolon", "Key_Equal", "Key_Exclam", "Key_VolumeUp", "Key_Dead_Acute"):
        assert tradutor.traduzir(_evento(getattr(Qt, atributo))).nome == "", atributo
