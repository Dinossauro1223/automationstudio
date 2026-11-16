"""Regras das teclas de automação (25.9, T1): o que não pode iniciar uma automação, o que vale com aviso e o que vale.

Lógica pura: sem Qt e sem disco. Especificação: md/ESPEC_TECLADO_25_9.md, seção 5.3. Testes: tests/unit/test_atalhos_reservados.py.

O atalho de uma automação é global e PASSIVO: a tecla continua chegando ao programa em foco. Uma automação em Ctrl+T abriria uma
aba no navegador E começaria ao mesmo tempo; em "A", começaria a cada letra digitada; no botão esquerdo do mouse, a cada clique,
inclusive os que a própria automação envia. Por isso estas regras são de segurança, não de gosto.

`avaliar(tecla)` classifica uma tecla ou combinação (`livre`, `aviso` ou `recusada`), diz qual regra decidiu e por quê.
`sugerir(usadas)` devolve a próxima combinação livre da série Ctrl+Shift+Alt+1, 2 … 9, 0, depois F1 … F12 e A … Z.

As regras valem na ordem; a primeira que se aplica decide:
 1. entrada que não é uma tecla ........................................................ recusada   (invalida)
 2. alguma parte que o monitor nunca produz (símbolo, pontuação, nome errado) .............. recusada   (desconhecida)
 3. só teclas modificadoras (Ctrl, Shift, Alt) ............................................ recusada   (sem_tecla)
 4. qualquer combinação com a tecla Windows ................................................ recusada   (win)
 5. combinação do catálogo (atalhos do Windows e dos navegadores) ......................... recusada   (catalogo)
 6. sem Ctrl/Alt (nenhum modificador, ou só Shift):
      Print Screen, Menu, Caps Lock, Num Lock ............................................. recusada   (isolada)
      botão esquerdo, direito ou do meio do mouse ......................................... recusada   (mouse)
      letra, número, Espaço, Enter, Tab, Esc, setas, Delete... ............................ recusada   (digitar)
      F1 a F12 ............................................................................ recusada   (f1_f12)
      Pause, Scroll Lock .................................................................. aviso      (isolada)
 7. F13 a F24, com qualquer combinação que passou das regras acima ........................ livre      (f13_f24)
 8. com tecla (ou botão principal do mouse) e:
      um modificador só (Ctrl ou Alt) ..................................................... recusada   (um_modificador)
      Ctrl+Alt, que é o AltGr, com letra ou número ........................................ recusada   (altgr)
      dois modificadores .................................................................. aviso      (dois_modificadores)
      três modificadores (Ctrl+Shift+Alt) ................................................. livre      (livre)
 9. só botões laterais do mouse: sozinhos aviso (lateral); com modificador, livres (livre)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .core import _SPECIAL_KEY_NAMES, parse_combo

NIVEL_LIVRE = "livre"
NIVEL_AVISO = "aviso"
NIVEL_RECUSADA = "recusada"


@dataclass(frozen=True)
class Avaliacao:
    """O que se decidiu sobre uma tecla de automação.

    `motivo` é um predicado ("abre uma nova aba do navegador"), para o texto dizer "A tecla “X” <motivo>."; vazio quando livre.
    `sugestao` é, na recusa, a próxima combinação livre; vazio nos demais casos."""
    nivel: str
    regra: str
    motivo: str = ""
    sugestao: str = ""


# --------------------------------------------------------------------------------------------------- as classes de tecla
_MODIFICADORES = frozenset({"CTRL", "SHIFT", "ALT", "ALTGR", "WIN"})
_MOUSE_PRINCIPAIS = frozenset({"MOUSE_LEFT", "MOUSE_RIGHT", "MOUSE_MIDDLE"})
_MOUSE_LATERAIS = frozenset({"MOUSE_X1", "MOUSE_X2"})
_F_BAIXAS = frozenset(f"F{n}" for n in range(1, 13))
_F_ALTAS = frozenset(f"F{n}" for n in range(13, 25))
# Teclas que têm efeito próprio no Windows ou no teclado, mesmo sozinhas: (nível, o que fazem).
_ISOLADAS = {
    "PRINTSCREEN": (NIVEL_RECUSADA, "é a tecla que o Windows usa para capturar a tela"),
    "MENU": (NIVEL_RECUSADA, "abre o menu de contexto dos programas"),
    "CAPSLOCK": (NIVEL_RECUSADA, "liga e desliga as letras maiúsculas a cada uso"),
    "NUMLOCK": (NIVEL_RECUSADA, "liga e desliga o teclado numérico (Num Lock) a cada uso"),
    "SCROLLLOCK": (NIVEL_AVISO, "é usada por alguns programas e jogos (rolagem)"),
    "PAUSE": (NIVEL_AVISO, "é usada por alguns programas e jogos (pausa)"),
}
# Tudo o que o monitor de teclado consegue produzir com nome (F1 a F24 incluídas): a fonte é a tabela do próprio monitor,
# para uma tecla nova nunca ser classificada como "desconhecida" só porque esta lista ficou para trás.
_NOMES_DO_MONITOR = frozenset(_SPECIAL_KEY_NAMES.values())


def _digita_caractere(token: str) -> bool:
    """Letra ou número: o que o AltGr (Ctrl+Alt) escreve em teclados como o ABNT2."""
    return len(token) == 1 and (token.isalnum() or token == "Ç")


def _classe(token: str) -> str | None:
    """A classe de uma tecla já normalizada, ou None se o monitor nunca a produziria (um atalho nela jamais dispararia)."""
    if token in _MODIFICADORES:
        return "mod"
    if token in _MOUSE_PRINCIPAIS:
        return "mouse"
    if token in _MOUSE_LATERAIS:
        return "lateral"
    if token in _F_BAIXAS:
        return "f_baixa"
    if token in _F_ALTAS:
        return "f_alta"
    if token in _ISOLADAS:
        return "isolada"
    if token in _NOMES_DO_MONITOR or _digita_caractere(token):
        return "digitar"
    return None


# --------------------------------------------------------------------------------------------------- o catálogo
# (combinação, o que ela faz). Só combinações IGUAIS contam: "A" está dentro de "Ctrl+A", mas dizer que a tecla A "seleciona tudo"
# seria um motivo falso (A é recusada por ser tecla de digitar). Com Win: não precisa constar, a regra do Windows recusa todas.
# A lista é de combinações que conheço com segurança nos dois sistemas; os motivos são para a pessoa entender, não exaustivos.
CATALOGO: tuple[tuple[str, str], ...] = (
    # Windows
    ("CTRL+ALT+DELETE", "abre a tela de segurança do Windows"),
    ("CTRL+SHIFT+ESC", "abre o Gerenciador de Tarefas"),
    ("CTRL+ALT+TAB", "abre o seletor de janelas do Windows"),
    ("ALT+F4", "fecha a janela em primeiro plano"),
    ("ALT+TAB", "troca de janela"),
    ("ALT+SHIFT+TAB", "troca de janela, no sentido contrário"),
    ("ALT+ESC", "troca de janela"),
    ("ALT+SPACE", "abre o menu da janela (mover, minimizar, fechar)"),
    ("ALT+ENTER", "mostra as propriedades ou alterna a tela cheia em vários programas"),
    ("CTRL+ESC", "abre o menu Iniciar"),
    ("SHIFT+F10", "abre o menu de contexto (o clique direito do teclado)"),
    ("ALT+PRINTSCREEN", "captura a janela em primeiro plano"),
    # Navegadores e programas em geral, com Ctrl+Shift
    ("CTRL+SHIFT+DELETE", "abre “Limpar dados de navegação” nos navegadores"),
    ("CTRL+SHIFT+T", "reabre a última aba fechada do navegador"),
    ("CTRL+SHIFT+N", "abre uma janela anônima no navegador (ou cria uma pasta no Explorador de Arquivos)"),
    ("CTRL+SHIFT+W", "fecha a janela do navegador"),
    ("CTRL+SHIFT+I", "abre as ferramentas do desenvolvedor do navegador"),
    ("CTRL+SHIFT+J", "abre o console do navegador"),
    ("CTRL+SHIFT+C", "inspeciona um elemento da página no navegador"),
    ("CTRL+SHIFT+R", "recarrega a página sem usar o cache"),
    ("CTRL+SHIFT+TAB", "vai para a aba anterior do navegador"),
    ("CTRL+SHIFT+B", "mostra ou esconde a barra de favoritos"),
    ("CTRL+SHIFT+O", "abre o gerenciador de favoritos"),
    ("CTRL+SHIFT+A", "pesquisa as abas abertas (navegadores) ou abre os complementos (Firefox)"),
    ("CTRL+SHIFT+Q", "fecha o navegador inteiro"),
    ("CTRL+SHIFT+PAGEUP", "move a aba do navegador para a esquerda"),
    ("CTRL+SHIFT+PAGEDOWN", "move a aba do navegador para a direita"),
    ("CTRL+SHIFT+V", "cola sem formatação"),
    ("CTRL+SHIFT+Z", "refaz a última ação"),
    ("CTRL+SHIFT+S", "salva como"),
    ("CTRL+SHIFT+P", "abre a janela privativa do Firefox ou a paleta de comandos dos editores"),
    # Ctrl + uma tecla: os atalhos que quase todo programa tem
    ("CTRL+C", "copia o que está selecionado"),
    ("CTRL+V", "cola"),
    ("CTRL+X", "recorta o que está selecionado"),
    ("CTRL+Z", "desfaz a última ação"),
    ("CTRL+Y", "refaz a última ação"),
    ("CTRL+A", "seleciona tudo"),
    ("CTRL+S", "salva"),
    ("CTRL+T", "abre uma nova aba do navegador"),
    ("CTRL+W", "fecha a aba ou a janela"),
    ("CTRL+N", "abre uma nova janela"),
    ("CTRL+F", "abre a busca"),
    ("CTRL+P", "imprime"),
    ("CTRL+R", "recarrega a página"),
    ("CTRL+L", "seleciona a barra de endereço do navegador"),
    ("CTRL+D", "adiciona a página aos favoritos"),
    ("CTRL+TAB", "vai para a próxima aba do navegador"),
    # Alt + uma tecla
    ("ALT+LEFT", "volta uma página no navegador ou uma pasta no Explorador de Arquivos"),
    ("ALT+RIGHT", "avança uma página no navegador"),
    ("ALT+HOME", "abre a página inicial do navegador"),
    ("ALT+D", "seleciona a barra de endereço do navegador"),
)
_CATALOGO_POR_COMBO = {parse_combo(combo): motivo for combo, motivo in CATALOGO}


# --------------------------------------------------------------------------------------------------- a sugestão
_SERIE = tuple(
    ["CTRL+SHIFT+ALT+" + t for t in "1234567890"]
    + [f"CTRL+SHIFT+ALT+F{n}" for n in range(1, 13)]
    + ["CTRL+SHIFT+ALT+" + t for t in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"])
_COMBO_DA_SERIE = {texto: parse_combo(texto) for texto in _SERIE}


def _combinacoes(teclas: Iterable[Any]) -> list[frozenset[str]]:
    """As combinações válidas dentre `teclas` (o que não é texto de tecla é ignorado: nunca levanta)."""
    combos = []
    for tecla in teclas:
        if isinstance(tecla, str) and tecla.strip():
            try:
                combos.append(parse_combo(tecla.strip()))
            except ValueError:
                continue
    return combos


def sugerir(usadas: Iterable[Any] = ()) -> str:
    """A primeira combinação da série Ctrl+Shift+Alt+1 … 9, 0, F1 … F12, A … Z que ninguém usa, ou "" se acabaram as 48.

    "Ninguém usa" vale para o jeito que o gerente de atalhos dispara, que é por SUBCONJUNTO: uma automação em "1" também dispara
    ao apertar Ctrl+Shift+Alt+1, e uma em Ctrl+Shift+Alt+1+2 tem as teclas de Ctrl+Shift+Alt+1 apertadas. Por isso a candidata é
    pulada quando está contida em uma tecla em uso, ou a contém, e não só quando é igual."""
    em_uso = _combinacoes(usadas)
    for candidata in _SERIE:
        combo = _COMBO_DA_SERIE[candidata]
        if not any(usada <= combo or combo <= usada for usada in em_uso):
            return candidata
    return ""


# --------------------------------------------------------------------------------------------------- a avaliação
def _recusa(regra: str, motivo: str, usadas: Iterable[Any]) -> Avaliacao:
    return Avaliacao(NIVEL_RECUSADA, regra, motivo, sugerir(usadas))


def _motivo_desconhecida(token: str) -> str:
    if len(token) == 1 and not token.isalnum():
        return f"usa “{token}”, que o programa ainda não reconhece como tecla de atalho (símbolos e pontuação ainda não funcionam)"
    return f"usa “{token}”, que o programa não reconhece como tecla de atalho (confira a escrita)"


def avaliar(tecla: Any, usadas: Iterable[Any] = ()) -> Avaliacao:
    """Classifica `tecla` (como "CTRL+SHIFT+ALT+1", "F13" ou "MOUSE_X1", em qualquer caixa e ordem) pelas regras do módulo.

    `usadas` são as teclas já em uso (para a sugestão que acompanha uma recusa). Nunca levanta: o que não é uma tecla é
    recusado como `invalida`."""
    texto = tecla.strip() if isinstance(tecla, str) else ""
    if not texto:
        return _recusa("invalida", "não é uma combinação de teclas", usadas)
    try:
        tokens = parse_combo(texto)
    except ValueError:
        return _recusa("invalida", "não é uma combinação de teclas", usadas)

    desconhecidas = sorted(t for t in tokens if _classe(t) is None)
    if desconhecidas:
        return _recusa("desconhecida", _motivo_desconhecida(desconhecidas[0]), usadas)

    modificadores = {t for t in tokens if t in _MODIFICADORES}
    principais = tokens - modificadores
    if not principais:
        return _recusa("sem_tecla", "só tem teclas modificadoras (Ctrl, Shift, Alt): a automação começaria ao usar qualquer atalho",
                       usadas)
    # O AltGr que o pynput informa é, para os programas, Ctrl+Alt.
    efetivos = (modificadores - {"ALTGR"}) | ({"CTRL", "ALT"} if "ALTGR" in modificadores else set())
    if "WIN" in efetivos:
        return _recusa("win", "usa a tecla Windows, que o próprio Windows usa para os atalhos dele", usadas)
    motivo = _CATALOGO_POR_COMBO.get(frozenset(principais | efetivos))
    if motivo is not None:
        return _recusa("catalogo", motivo, usadas)

    classes = {t: _classe(t) for t in principais}
    if efetivos <= {"SHIFT"}:  # nenhum modificador, ou só Shift: a tecla vale por si
        isoladas = sorted(t for t in principais if t in _ISOLADAS)
        for token in isoladas:
            nivel, o_que_faz = _ISOLADAS[token]
            if nivel == NIVEL_RECUSADA:
                return _recusa("isolada", o_que_faz, usadas)
        if "mouse" in classes.values():
            return _recusa("mouse", "usa um botão principal do mouse (esquerdo, direito ou do meio), que é clicado o tempo todo: "
                           "a automação começaria a cada clique, até nos da própria automação", usadas)
        if "digitar" in classes.values():
            return _recusa("digitar", "é uma tecla de digitar ou navegar: a automação começaria sempre que ela fosse usada", usadas)
        if "f_baixa" in classes.values():
            return _recusa("f1_f12", "usa uma das teclas F1 a F12 sem modificador, que têm função própria nos programas "
                           "(ajuda, atualizar, tela cheia, ferramentas do desenvolvedor)", usadas)
        for token in isoladas:  # só restam as de aviso (Pause, Scroll Lock)
            return Avaliacao(NIVEL_AVISO, "isolada", _ISOLADAS[token][1])
    if "f_alta" in classes.values():
        return Avaliacao(NIVEL_LIVRE, "f13_f24")

    teclas = [t for t, classe in classes.items() if classe in ("digitar", "f_baixa", "isolada", "mouse")]
    if teclas:
        if len(efetivos) == 1:  # só Ctrl ou só Alt (só Shift já foi decidido acima)
            return _recusa("um_modificador", "usa só Ctrl ou só Alt com uma tecla, e quase todo programa já tem um atalho assim "
                           "(copiar, nova aba, fechar)", usadas)
        if len(efetivos) == 2:
            if efetivos == {"CTRL", "ALT"} and any(_digita_caractere(t) for t in teclas):
                return _recusa("altgr", "usa Ctrl+Alt, que é o AltGr: em alguns teclados (como o ABNT2) isso digita caracteres",
                               usadas)
            return Avaliacao(NIVEL_AVISO, "dois_modificadores", "usa dois modificadores e pode colidir com atalhos de alguns "
                             "programas; com três (Ctrl+Shift+Alt) quase nunca colide")
        return Avaliacao(NIVEL_LIVRE, "livre")
    # Só botões laterais do mouse.
    if not efetivos:
        return Avaliacao(NIVEL_AVISO, "lateral", "usa um botão lateral do mouse sozinho, que os navegadores usam como Voltar e Avançar")
    return Avaliacao(NIVEL_LIVRE, "livre")
