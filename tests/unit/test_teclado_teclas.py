"""De evento do Qt para a tecla do Studio (25.9, T3a): `automationstudio/teclado_teclas.py`.

Ficha: md/FICHA_TECLADO_T3_25_9.md, decisão T3-10 e a tabela da seção 5. O Qt entrega a tecla como um código (`Qt.Key_A`...); o controlador
(`teclado_edicao.py`) fala em nomes do Studio ("A", "ENTER", "NUM5"...). `TradutorDeTeclas` faz a ponte e NÃO importa o Qt: recebe o
espaço de nomes (`PySide6.QtCore.Qt` na janela) e lê dele cada `Key_*` e cada `*Modifier` pelo nome. Aqui ele recebe um Qt FALSO, com códigos
inventados e diferentes uns dos outros: o que se prova é a TABELA (quem vira o quê), não os números do Qt. Os números e os nomes de atributo
de verdade são provados no Actions (tests/gui/test_teclado_teclas_qt.py), com QKeyEvent real.

O que a tabela promete (decisão T3-10):
- letras, Ç, dígitos, F1 a F24 e as teclas nomeadas valem sempre; o teclado numérico (NUM0..NUM9, NUM/ NUM* NUM- NUM+ NUM. e NUMENTER) só na
  CAPTURA; fora dela o Enter numérico é Enter e os dígitos do numérico são dígitos;
- dígito apertado com Shift ou AltGr (que o Qt entrega como símbolo: "!" em vez de "1") é resolvido pelo código virtual do Windows;
- tecla que o Studio não conhece (pontuação, acento morto, mídia) vira nome vazio: o controlador responde "essa tecla não pode ser usada";
- o modificador da PRÓPRIA tecla não conta (apertar Ctrl sozinho é a tecla CTRL, não "Ctrl+CTRL"), senão não se gravaria Shift, Ctrl, Alt nem AltGr;
- o caractere digitado vai em `texto` (é por ele que o `'` é reconhecido, em qualquer layout).
"""
from __future__ import annotations

import ast
import pathlib
import types
from functools import reduce
from operator import or_

import pytest

from automationstudio.core import ActionType, Command, InputType
from automationstudio.input_system import Win32InputBackend
from automationstudio import teclado_teclas
from automationstudio.teclado_edicao import Tecla
from automationstudio.teclado_teclas import NOMES_DA_CAPTURA, TradutorDeTeclas
from testsupport.fakes import FakeUser32

# ------------------------------------------------------------------------------------------------ o que a ficha promete (escrito à mão)
LETRAS = {f"Key_{c}": c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"} | {"Key_Ccedilla": "Ç"}
DIGITOS = {f"Key_{i}": str(i) for i in range(10)}
FUNCAO = {f"Key_F{i}": f"F{i}" for i in range(1, 25)}
NOMEADAS = {
    "Key_Escape": "ESC", "Key_Tab": "TAB", "Key_Backtab": "TAB", "Key_CapsLock": "CAPSLOCK", "Key_Shift": "SHIFT", "Key_Control": "CTRL",
    "Key_Alt": "ALT", "Key_AltGr": "ALTGR", "Key_Return": "ENTER", "Key_Backspace": "BACKSPACE", "Key_Space": "SPACE", "Key_Meta": "WIN",
    "Key_Menu": "MENU", "Key_Insert": "INSERT", "Key_Home": "HOME", "Key_PageUp": "PAGEUP", "Key_Delete": "DELETE", "Key_End": "END",
    "Key_PageDown": "PAGEDOWN", "Key_Up": "UP", "Key_Down": "DOWN", "Key_Left": "LEFT", "Key_Right": "RIGHT", "Key_Print": "PRINTSCREEN",
    "Key_ScrollLock": "SCROLLLOCK", "Key_Pause": "PAUSE", "Key_NumLock": "NUMLOCK",
}
NUMERICO = {f"Key_{i}": f"NUM{i}" for i in range(10)} | {"Key_Slash": "NUM/", "Key_Asterisk": "NUM*", "Key_Minus": "NUM-", "Key_Plus": "NUM+",
                                                          "Key_Period": "NUM.", "Key_Comma": "NUM.", "Key_Enter": "NUMENTER"}
# Teclas do Qt que o Studio NÃO conhece: têm código no Qt falso para o teste provar que viram nome vazio.
DESCONHECIDAS = ["Key_Apostrophe", "Key_Exclam", "Key_At", "Key_Equal", "Key_Dead_Acute", "Key_Clear", "Key_Super_L", "Key_VolumeUp",
                 "Key_MediaPlay", "Key_onesuperior", "Key_Semicolon", "Key_Backslash", "Key_BracketLeft"]
MODIFICADORES = ["ShiftModifier", "ControlModifier", "AltModifier", "MetaModifier", "KeypadModifier"]


def _qt_falso():
    """Um `Qt` com todos os Key_* acima (cada um com um código diferente e inventado) e os modificadores como máscaras de bits."""
    nomes = set(LETRAS) | set(DIGITOS) | set(FUNCAO) | set(NOMEADAS) | set(NUMERICO) | set(DESCONHECIDAS) | {"Key_Enter"}
    atributos = {nome: 0x2000 + i for i, nome in enumerate(sorted(nomes))}
    atributos.update({modificador: 1 << (20 + i) for i, modificador in enumerate(MODIFICADORES)})
    atributos["NoModifier"] = 0
    return types.SimpleNamespace(**atributos)


QT = _qt_falso()
TRADUTOR = TradutorDeTeclas(QT)


class EventoFalso:
    """O que o tradutor lê de um QKeyEvent: key(), text(), modifiers() e nativeVirtualKey()."""

    def __init__(self, tecla, texto="", modificadores=(), vk=0, codigo=None):
        self._codigo = getattr(QT, tecla) if codigo is None else codigo
        self._texto, self._vk = texto, vk
        self._modificadores = reduce(or_, (getattr(QT, m) for m in modificadores), 0)

    def key(self):
        return self._codigo

    def text(self):
        return self._texto

    def modifiers(self):
        return self._modificadores

    def nativeVirtualKey(self):
        return self._vk


class EventoSemCodigoVirtual(EventoFalso):
    """Um evento que não sabe o código virtual (outros sistemas): o método nem existe."""
    nativeVirtualKey = None


def _traduzir(tecla, captura=False, **kwargs):
    return TRADUTOR.traduzir(EventoFalso(tecla, **kwargs), captura=captura)


# ------------------------------------------------------------------------------------------------ os 103 nomes
def test_a_captura_pode_produzir_exatamente_103_nomes_sem_repeticao():
    assert len(NOMES_DA_CAPTURA) == 103 == len(set(NOMES_DA_CAPTURA))


def test_os_103_nomes_sao_os_grupos_da_ficha():
    esperados = set(LETRAS.values()) | set(DIGITOS.values()) | set(FUNCAO.values()) | set(NOMEADAS.values()) | set(NUMERICO.values())
    assert set(NOMES_DA_CAPTURA) == esperados
    assert (len(set(LETRAS.values())), len(set(DIGITOS.values())), len(set(FUNCAO.values())), len(set(NOMEADAS.values())),
            len(set(NUMERICO.values()))) == (27, 10, 24, 26, 16)


@pytest.mark.parametrize("atributo, nome", sorted((LETRAS | DIGITOS | FUNCAO | NOMEADAS).items()))
@pytest.mark.parametrize("captura", [False, True], ids=["navegando", "captura"])
def test_cada_tecla_comum_vira_o_seu_nome_nos_dois_modos(atributo, nome, captura):
    assert _traduzir(atributo, captura=captura).nome == nome


def test_toda_tecla_que_o_tradutor_produz_esta_nos_103_e_os_103_sao_todos_produzidos():
    produzidos = set()
    for atributo in set(LETRAS) | set(DIGITOS) | set(FUNCAO) | set(NOMEADAS) | {"Key_Enter"}:
        for captura in (False, True):
            produzidos.add(_traduzir(atributo, captura=captura).nome)
    for atributo in NUMERICO:
        produzidos.add(_traduzir(atributo, captura=True, modificadores=["KeypadModifier"]).nome)
    assert produzidos == set(NOMES_DA_CAPTURA)


# ------------------------------------------------------------------------------------------------ o teclado numérico
@pytest.mark.parametrize("atributo, nome", sorted(NUMERICO.items()))
def test_o_numerico_so_vale_na_captura(atributo, nome):
    assert _traduzir(atributo, captura=True, modificadores=["KeypadModifier"]).nome == nome


@pytest.mark.parametrize("digito", range(10))
def test_fora_da_captura_o_digito_do_numerico_e_um_digito(digito):
    tecla = _traduzir(f"Key_{digito}", captura=False, modificadores=["KeypadModifier"])
    assert tecla.nome == str(digito)


def test_o_digito_da_fileira_de_cima_nao_vira_numerico_nem_na_captura():
    assert _traduzir("Key_5", captura=True).nome == "5"


def test_o_enter_do_numerico_e_enter_fora_da_captura_e_numenter_nela():
    numerico = ["KeypadModifier"]
    assert _traduzir("Key_Enter", captura=False, modificadores=numerico).nome == "ENTER"
    assert _traduzir("Key_Enter", captura=True, modificadores=numerico).nome == "NUMENTER"
    assert _traduzir("Key_Return", captura=True).nome == "ENTER", "o Enter de cima continua Enter na captura"


@pytest.mark.parametrize("atributo", ["Key_Slash", "Key_Asterisk", "Key_Minus", "Key_Plus", "Key_Period", "Key_Comma"])
def test_a_pontuacao_so_e_do_numerico_com_o_modificador_numerico(atributo):
    assert _traduzir(atributo, captura=True).nome == "", "a mesma tecla fora do numérico é pontuação: o Studio não a conhece"
    assert _traduzir(atributo, captura=False, modificadores=["KeypadModifier"]).nome == ""


def test_o_ponto_decimal_do_numerico_chega_como_virgula_ou_como_ponto():
    """Em layouts brasileiros o ponto decimal do numérico digita vírgula: as duas viram NUM."""
    assert _traduzir("Key_Comma", captura=True, modificadores=["KeypadModifier"]).nome == "NUM."
    assert _traduzir("Key_Period", captura=True, modificadores=["KeypadModifier"]).nome == "NUM."


@pytest.mark.parametrize("atributo, nome", [("Key_Left", "LEFT"), ("Key_Right", "RIGHT"), ("Key_Up", "UP"), ("Key_Down", "DOWN"),
                                            ("Key_Home", "HOME"), ("Key_End", "END"), ("Key_PageUp", "PAGEUP"), ("Key_PageDown", "PAGEDOWN"),
                                            ("Key_Insert", "INSERT"), ("Key_Delete", "DELETE")])
@pytest.mark.parametrize("captura", [False, True], ids=["navegando", "captura"])
def test_as_setas_e_as_de_navegacao_do_numerico_com_numlock_desligado_sao_as_mesmas(atributo, nome, captura):
    """Com o NumLock desligado o numérico manda setas, Home, End...: com ou sem o modificador numérico, o nome é o da tecla de navegação."""
    assert _traduzir(atributo, captura=captura, modificadores=["KeypadModifier"]).nome == nome
    assert _traduzir(atributo, captura=captura).nome == nome


# ------------------------------------------------------------------------------------------------ o que o Studio não conhece
@pytest.mark.parametrize("atributo", DESCONHECIDAS)
@pytest.mark.parametrize("captura", [False, True], ids=["navegando", "captura"])
def test_tecla_que_o_studio_nao_conhece_tem_nome_vazio(atributo, captura):
    assert _traduzir(atributo, captura=captura).nome == ""


@pytest.mark.parametrize("codigo", [0, -1, 0x7FFFFFFF, 0x01FFFFFF])
def test_codigo_que_o_qt_nunca_deu_tem_nome_vazio(codigo):
    assert TRADUTOR.traduzir(EventoFalso("Key_A", codigo=codigo)).nome == ""


# ------------------------------------------------------------------------------------------------ dígito com Shift ou AltGr: o código virtual
@pytest.mark.parametrize("digito", range(10))
def test_o_digito_com_shift_chega_como_simbolo_e_o_codigo_virtual_o_devolve(digito):
    """No ABNT2, Shift+1 é "!" e o Qt dá Key_Exclam; o código virtual da tecla continua 0x31."""
    tecla = _traduzir("Key_Exclam", texto="!", modificadores=["ShiftModifier"], vk=0x30 + digito)
    assert tecla.nome == str(digito)
    assert tecla.shift is True


def test_o_digito_com_altgr_tambem_e_resolvido_e_os_modificadores_ficam_para_a_janela_decidir():
    tecla = _traduzir("Key_onesuperior", texto="¹", modificadores=["ControlModifier", "AltModifier"], vk=0x31)
    assert (tecla.nome, tecla.ctrl, tecla.alt) == ("1", True, True)


@pytest.mark.parametrize("vk", [0x2F, 0x3A, 0x00, 0x41, 0x5A, 0x60, 0x69, 0xBA, 0x1B])
def test_so_os_codigos_virtuais_0x30_a_0x39_valem_como_digito(vk):
    """Só os dígitos têm esta saída. Letras e o numérico (0x60 a 0x69) não: uma tecla sem nome continua sem nome."""
    assert _traduzir("Key_Exclam", texto="!", vk=vk).nome == ""


def test_o_codigo_do_qt_manda_quando_ele_conhece_a_tecla():
    assert _traduzir("Key_A", texto="a", vk=0x31).nome == "A"


def test_sem_codigo_virtual_a_tecla_continua_sem_nome():
    evento = EventoSemCodigoVirtual("Key_Exclam", texto="!")
    assert TRADUTOR.traduzir(evento).nome == ""


def test_codigo_virtual_zero_ou_ausente_nao_inventa_digito():
    assert _traduzir("Key_Exclam", texto="!", vk=0).nome == ""


# ------------------------------------------------------------------------------------------------ os modificadores
def test_shift_ctrl_alt_sao_lidos_do_evento():
    tecla = _traduzir("Key_Z", texto="\x1a", modificadores=["ControlModifier"])
    assert tecla == Tecla("Z", "", ctrl=True)
    tecla = _traduzir("Key_Return", texto="\r", modificadores=["ShiftModifier"])
    assert tecla == Tecla("ENTER", "", shift=True)
    tecla = _traduzir("Key_F4", modificadores=["AltModifier"])
    assert tecla == Tecla("F4", "", alt=True)


def test_sem_modificadores_e_tudo_falso():
    tecla = _traduzir("Key_Q", texto="q")
    assert (tecla.ctrl, tecla.shift, tecla.alt) == (False, False, False)


def test_a_tecla_meta_e_o_modificador_numerico_nao_sao_modificadores_do_controlador():
    tecla = _traduzir("Key_Return", texto="\r", modificadores=["MetaModifier", "KeypadModifier"])
    assert (tecla.ctrl, tecla.shift, tecla.alt) == (False, False, False)


@pytest.mark.parametrize("atributo, modificador, nome", [("Key_Control", "ControlModifier", "CTRL"), ("Key_Shift", "ShiftModifier", "SHIFT"),
                                                          ("Key_Alt", "AltModifier", "ALT")])
def test_apertar_um_modificador_sozinho_e_a_tecla_dele_nao_um_modificador_aceso(atributo, modificador, nome):
    """O Qt já põe o modificador na máscara do próprio evento. Sem este cuidado a janela devolveria a captura de CTRL ao Qt (a regra "Ctrl e
    Alt voltam inteiros") e ninguém gravaria Shift, Ctrl nem Alt como tecla de um comando."""
    tecla = _traduzir(atributo, modificadores=[modificador])
    assert tecla == Tecla(nome)


def test_o_altgr_chega_como_ctrl_mais_alt_e_isso_nao_conta_para_a_propria_tecla():
    tecla = _traduzir("Key_AltGr", modificadores=["ControlModifier", "AltModifier"])
    assert tecla == Tecla("ALTGR")


def test_so_o_modificador_da_propria_tecla_e_apagado():
    """Segurando Ctrl e apertando Shift: SHIFT com Ctrl aceso (a janela devolve ao Qt). Segurando Shift e apertando Ctrl, o inverso."""
    assert _traduzir("Key_Shift", modificadores=["ControlModifier", "ShiftModifier"]) == Tecla("SHIFT", ctrl=True)
    assert _traduzir("Key_Control", modificadores=["ControlModifier", "ShiftModifier"]) == Tecla("CTRL", shift=True)
    assert _traduzir("Key_Alt", modificadores=["ControlModifier", "AltModifier"]) == Tecla("ALT", ctrl=True)


def test_a_tecla_de_letra_com_o_modificador_da_outra_nao_e_apagada():
    assert _traduzir("Key_A", texto="A", modificadores=["ShiftModifier"]) == Tecla("A", "A", shift=True)


# ------------------------------------------------------------------------------------------------ o caractere digitado
def test_o_apostrofo_vem_em_texto_mesmo_sem_nome_no_studio():
    tecla = _traduzir("Key_Apostrophe", texto="'")
    assert tecla == Tecla("", "'")


def test_o_apostrofo_digitado_por_uma_tecla_com_nome_tambem_e_visto():
    """Em outro layout o apóstrofo pode estar numa tecla que o Studio nomeia: o `texto` é a identificação (D3)."""
    assert _traduzir("Key_Q", texto="'").texto == "'"


@pytest.mark.parametrize("atributo, texto", [("Key_Return", "\r"), ("Key_Escape", "\x1b"), ("Key_Tab", "\t"), ("Key_Backspace", "\x08"),
                                             ("Key_Delete", "\x7f"), ("Key_Z", "\x1a")])
def test_caractere_de_controle_nao_e_texto(atributo, texto):
    assert _traduzir(atributo, texto=texto).texto == ""


@pytest.mark.parametrize("texto, esperado", [("a", "a"), ("ç", "ç"), (" ", " "), ("'", "'"), ("", ""), ("ab", ""), ("´a", "")],
                         ids=["letra", "cedilha", "espaco", "apostrofo", "vazio", "dois-caracteres", "composicao-de-dois"])
def test_o_texto_e_um_caractere_imprimivel_ou_nada(texto, esperado):
    assert _traduzir("Key_Q", texto=texto).texto == esperado


# ------------------------------------------------------------------------------------------------ construção e vocabulário
def test_se_o_qt_nao_tem_um_atributo_esperado_a_construcao_falha_e_nomeia_o_atributo():
    """Um nome de `Key_*` errado não pode passar em silêncio: a tecla correspondente nunca seria reconhecida."""
    incompleto = types.SimpleNamespace(**{k: v for k, v in vars(QT).items() if k != "Key_Ccedilla"})
    with pytest.raises(AttributeError, match="Key_Ccedilla"):
        TradutorDeTeclas(incompleto)
    sem_modificador = types.SimpleNamespace(**{k: v for k, v in vars(QT).items() if k != "KeypadModifier"})
    with pytest.raises(AttributeError, match="KeypadModifier"):
        TradutorDeTeclas(sem_modificador)


def test_os_codigos_do_qt_podem_ser_enums_com_valor_inteiro():
    """No PySide6 novo `Qt.Key_A` é um enum de inteiros: o que se compara é o `.value`."""
    class Enumerado:
        def __init__(self, valor):
            self.value = valor
    qt_enum = types.SimpleNamespace(**{k: Enumerado(v) if k.startswith("Key_") else v for k, v in vars(QT).items()})  # os modificadores seguem como máscaras
    tradutor = TradutorDeTeclas(qt_enum)

    class Evento(EventoFalso):
        def key(self):
            return Enumerado(self._codigo)
    assert tradutor.traduzir(Evento("Key_A", texto="a")).nome == "A"
    assert tradutor.traduzir(Evento("Key_Return", texto="\r")).nome == "ENTER"


def test_todo_nome_da_captura_existe_na_barra_lateral_menos_o_fn_e_os_f13_a_f24():
    """A captura só grava o que a barra lateral mostra (e o motor aperta). Diferenças permitidas e explicadas: a barra tem FN, que nenhum
    teclado entrega ao Qt; e o motor sabe F13 a F24 (T1), que a barra não lista."""
    from automationstudio.command_editor import CommandDialog
    barra = set(CommandDialog._key_options())
    captura = set(NOMES_DA_CAPTURA)
    assert barra - captura == {"FN"}
    assert captura - barra == {f"F{i}" for i in range(13, 25)}


def test_o_motor_do_windows_aperta_cada_um_dos_103_nomes():
    backend = Win32InputBackend(user32=FakeUser32())
    for nome in NOMES_DA_CAPTURA:
        backend.key_down(nome)
        backend.key_up(nome)  # um nome que o motor não conhece levantaria aqui


@pytest.mark.parametrize("nome", NOMES_DA_CAPTURA)
def test_cada_nome_da_captura_e_um_alvo_valido_de_comando_de_tecla(nome):
    comando = Command(id="c", type=InputType.KEY, target=nome, action=ActionType.PRESS_AND_RELEASE, duration=0.1)
    assert comando.validate() == []


def test_o_modulo_nao_importa_o_qt():
    """Só `teclado_ui.py` tem Qt (ficha, T3-1): este módulo roda e é provado em qualquer lugar."""
    importados = set()
    for no in ast.walk(ast.parse(pathlib.Path(teclado_teclas.__file__).read_text(encoding="utf-8"))):
        if isinstance(no, ast.Import):
            importados |= {alias.name.split(".")[0] for alias in no.names}
        elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
            importados.add(no.module.split(".")[0])
    assert not {"PySide6", "PyQt5", "PyQt6", "shiboken6"} & importados
