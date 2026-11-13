"""De evento do Qt para a tecla do Studio (25.9, T3a). Lógica pura: este módulo NÃO importa o Qt.

Ficha: md/FICHA_TECLADO_T3_25_9.md (T3-10 e a tabela da seção 5). Testes: tests/unit/test_teclado_teclas.py (a tabela, com um Qt falso) e
tests/gui/test_teclado_teclas_qt.py (os nomes e os códigos de verdade, com QKeyEvent real, no Actions).

O Qt entrega a tecla como um código (`Qt.Key_A`); o controlador da edição (`teclado_edicao.py`) fala em nomes do Studio ("A", "ENTER", "NUM5").
`TradutorDeTeclas` faz a ponte: recebe o espaço de nomes do Qt (`PySide6.QtCore.Qt` na janela) e lê dele, pelo NOME, cada `Key_*` e cada
`*Modifier`; `traduzir(evento, captura)` devolve a `Tecla`. Um nome de atributo errado falha na construção (AttributeError), nunca em silêncio.

As regras (decisão T3-10):

- letras, Ç, dígitos, F1 a F24 e as teclas nomeadas valem sempre. O teclado numérico (NUM0 a NUM9, NUM/ NUM* NUM- NUM+ NUM. e NUMENTER) só
  na CAPTURA: fora dela o Enter do numérico é Enter e os dígitos do numérico são dígitos. `NOMES_DA_CAPTURA` lista os 103 nomes que a captura
  pode produzir; todos existem na barra lateral (menos o FN, que nenhum teclado entrega) e o motor do Windows aperta todos;
- dígito apertado com Shift ou AltGr (que o Qt entrega como símbolo, "!" no lugar de "1") é resolvido pelo código virtual do Windows;
- tecla que o Studio não conhece (pontuação, acento morto, mídia) tem nome vazio: o controlador responde "essa tecla não pode ser usada";
- o modificador da PRÓPRIA tecla não conta (o Qt o põe na máscara do evento): apertar Ctrl sozinho é a tecla CTRL, não "Ctrl+CTRL";
- `Tecla.texto` é o caractere digitado, se for um só e imprimível (é por ele que o `'` é reconhecido, em qualquer layout).
"""
from __future__ import annotations

from .teclado_edicao import Tecla

# (atributo de `Qt`, nome do Studio). É a tabela da ficha, seção 5.
_LETRAS = tuple((f"Key_{c}", c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ") + (("Key_Ccedilla", "Ç"),)
_DIGITOS = tuple((f"Key_{i}", str(i)) for i in range(10))
_FUNCAO = tuple((f"Key_F{i}", f"F{i}") for i in range(1, 25))
_NOMEADAS = (
    ("Key_Escape", "ESC"), ("Key_Tab", "TAB"), ("Key_Backtab", "TAB"), ("Key_CapsLock", "CAPSLOCK"), ("Key_Shift", "SHIFT"),
    ("Key_Control", "CTRL"), ("Key_Alt", "ALT"), ("Key_AltGr", "ALTGR"), ("Key_Return", "ENTER"), ("Key_Enter", "ENTER"),
    ("Key_Backspace", "BACKSPACE"), ("Key_Space", "SPACE"), ("Key_Meta", "WIN"), ("Key_Menu", "MENU"), ("Key_Insert", "INSERT"),
    ("Key_Home", "HOME"), ("Key_PageUp", "PAGEUP"), ("Key_Delete", "DELETE"), ("Key_End", "END"), ("Key_PageDown", "PAGEDOWN"),
    ("Key_Up", "UP"), ("Key_Down", "DOWN"), ("Key_Left", "LEFT"), ("Key_Right", "RIGHT"), ("Key_Print", "PRINTSCREEN"),
    ("Key_ScrollLock", "SCROLLLOCK"), ("Key_Pause", "PAUSE"), ("Key_NumLock", "NUMLOCK"),
)
# O teclado numérico: valem só com o modificador numérico aceso e só na captura. A vírgula é o ponto decimal em layouts brasileiros.
_NUMERICO = tuple((f"Key_{i}", f"NUM{i}") for i in range(10)) + (
    ("Key_Slash", "NUM/"), ("Key_Asterisk", "NUM*"), ("Key_Minus", "NUM-"), ("Key_Plus", "NUM+"), ("Key_Period", "NUM."), ("Key_Comma", "NUM."),
)
# `Key_Enter` é, por definição do Qt, o Enter do numérico (o outro é `Key_Return`): na captura vale pelo código, com ou sem o modificador.
_ENTER_DO_NUMERICO = ("Key_Enter", "NUMENTER")

NOMES_DA_CAPTURA: tuple[str, ...] = tuple(dict.fromkeys(nome for _atributo, nome in (*_LETRAS, *_DIGITOS, *_FUNCAO, *_NOMEADAS, *_NUMERICO, _ENTER_DO_NUMERICO)))


def _inteiro(valor) -> int:
    """O código como inteiro: o PySide6 novo entrega `Qt.Key_A` como um enum (que tem `.value`), o antigo e os testes, como inteiro."""
    return int(getattr(valor, "value", valor))


def _tabela(qt, pares) -> dict[int, str]:
    """{código do Qt: nome do Studio}. `getattr` sem padrão: um atributo que o Qt não tem é erro de quem escreveu a tabela."""
    return {_inteiro(getattr(qt, atributo)): nome for atributo, nome in pares}


def _digito_do_codigo_virtual(evento) -> str:
    """O dígito da tecla pelo código virtual do Windows (0x30 a 0x39), ou "" se o evento não sabe ou o código não é de dígito."""
    leitor = getattr(evento, "nativeVirtualKey", None)
    if not callable(leitor):
        return ""
    try:
        codigo = int(leitor())
    except (TypeError, ValueError):
        return ""
    return str(codigo - 0x30) if 0x30 <= codigo <= 0x39 else ""


class TradutorDeTeclas:
    """Traduz um QKeyEvent em `Tecla`. Uma instância por janela; `qt` é o espaço de nomes `Qt` (ou um falso, nos testes)."""

    def __init__(self, qt) -> None:
        self._comuns = _tabela(qt, (*_LETRAS, *_DIGITOS, *_FUNCAO, *_NOMEADAS))
        self._numerico = _tabela(qt, _NUMERICO)
        self._enter_do_numerico = _inteiro(getattr(qt, _ENTER_DO_NUMERICO[0]))
        self._modificador_numerico = qt.KeypadModifier
        self._ctrl, self._shift, self._alt = qt.ControlModifier, qt.ShiftModifier, qt.AltModifier

    def traduzir(self, evento, captura: bool = False) -> Tecla:
        """A `Tecla` do evento. `captura` é verdadeiro só enquanto o controlador está capturando a tecla de um comando: é quando o teclado
        numérico tem nomes próprios (NUM5, NUMENTER...)."""
        codigo = _inteiro(evento.key())
        modificadores = evento.modifiers()
        nome = ""
        if captura:
            if codigo == self._enter_do_numerico:
                nome = _ENTER_DO_NUMERICO[1]
            elif modificadores & self._modificador_numerico:
                nome = self._numerico.get(codigo, "")
        if not nome:
            nome = self._comuns.get(codigo, "")
        if not nome:
            nome = _digito_do_codigo_virtual(evento)
        ctrl, shift, alt = bool(modificadores & self._ctrl), bool(modificadores & self._shift), bool(modificadores & self._alt)
        if nome == "CTRL":
            ctrl = False
        elif nome == "SHIFT":
            shift = False
        elif nome == "ALT":
            alt = False
        elif nome == "ALTGR":  # no Windows o AltGr chega como Ctrl + Alt
            ctrl = alt = False
        texto = str(evento.text() or "")
        if len(texto) != 1 or not texto.isprintable():
            texto = ""
        return Tecla(nome=nome, texto=texto, ctrl=ctrl, shift=shift, alt=alt)
