"""A ligação do controlador da edição pelo teclado com a janela (25.9, T3a): `automationstudio/teclado_ligacao.py`.

Ficha: md/FICHA_TECLADO_T3_25_9.md (T3-3, T3-4, T3-7, T3-8, T3-9, T3-12, T3-13, T3-14). O controlador (`teclado_edicao.py`, T2) decide; a
ligação é quem o entrega à janela: traduz o que ele manda (17 efeitos) em chamadas a uma PORTA (a janela de verdade, no `teclado_ui.py`),
decide o que a janela NÃO deve deixar passar ao Qt, e mantém dois interruptores atrelados ao ESTADO do controlador: os atalhos de automação
suspensos enquanto se captura a tecla, e o relógio de 30 Hz ligado enquanto se ajusta um valor.

Aqui a porta é FALSA (`PortaFalsa`): registra cada chamada, e as gravações de verdade (`teclado_aplicar`) acontecem num mapa de verdade, então os
fluxos do pedido do dono são provados de ponta a ponta sem Qt: o controlador real, a ligação, as gravações reais e o relógio (falso: o tempo é
avançado à mão, então "Enter, Enter em 0,2 s" e "segurar a seta por 3 s" são provados com números).

Uma regra refina a do T3-3 e está provada aqui: a repetição do sistema (tecla segurada) é consumida SE o aperto que a originou foi consumido
(o mesmo princípio para todos os estados), e segue para o Qt se aquele aperto seguiu. Assim segurar o Esc que cancelou uma edição não chega ao
Esc do aplicativo, segurar a tecla que confirmou não vira busca por letra na tabela, e segurar ↓ continua rolando as linhas.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from automationstudio import teclado_edicao as te
from automationstudio import teclado_ligacao as tl
from automationstudio.core import ActionType, AutomationMap, Command, InputType, map_from_json
from automationstudio.teclado_aplicar import MENSAGEM_MUDOU, aplicar_alvo, aplicar_espera, aplicar_tempo, aplicar_texto
from automationstudio.teclado_aplicar import marcar as marcar_o_comando
from automationstudio.teclado_edicao import (DICA_NAVEGANDO, DICA_TECLA_DESCONHECIDA, DICA_TEXTO_VAZIO, Estado, Resposta, Tecla, dica_do_estado,
                                             formatar_segundos, linha_info_de, valor_apos)
from automationstudio.teclado_ligacao import LigacaoDoTeclado, Porta
from testsupport.fake_clock import FakeClock

K, B, T, A, M = InputType.KEY, InputType.MOUSE_BUTTON, InputType.TEXT, InputType.APP_OPEN, InputType.MOUSE_MOVE
TECLA, TEXTO, PROGRAMA, BOTAO, SO_APERTA, MOVER = range(6)  # o índice de cada comando do mapa de teste
ENTER, ESC, ESQ, DIR, F2, CIMA, BAIXO = (Tecla("ENTER"), Tecla("ESC"), Tecla("LEFT"), Tecla("RIGHT"), Tecla("F2"), Tecla("UP"), Tecla("DOWN"))
APOSTROFO = Tecla("", "'")
SHIFT_ENTER = Tecla("ENTER", shift=True)
MENSAGEM_DO_ERRO = "Algo deu errado na edição pelo teclado; nada foi gravado."


def _mapa() -> AutomationMap:
    """Um comando de cada tipo que a edição pelo teclado trata, mais um só-aperta e um movimento (sem conteúdo simples)."""
    return AutomationMap(name="Ligação", commands=[
        Command(id="c0", type=K, target="E", start=0.0, duration=0.2),
        Command(id="c1", type=T, text="olá", start=1.0),
        Command(id="c2", type=A, target="notepad.exe", wait_process="notepad.exe", start=2.0),
        Command(id="c3", type=B, target="left", start=3.0, duration=0.1),
        Command(id="c4", type=K, target="Q", action=ActionType.PRESS, start=4.0),
        Command(id="c5", type=M, x=10, y=20, start=5.0),
    ])


class PortaFalsa:
    """O que a janela de verdade faz, em miniatura: registra cada pedido em `chamadas` (na ordem) e as gravações vão ao mapa de verdade."""

    def __init__(self, mapa: AutomationMap, selecionadas=(0,)):
        self.mapa, self.selecionadas = mapa, list(selecionadas)
        self.chamadas: list[tuple] = []
        self.leituras: list[str] = []
        self.editor = ""             # o que está no editor de texto: o teste "digita" aqui
        self.falhar_em: dict[str, Exception] = {}
        self.ao_marcar = None        # ganchos que simulam o Qt chamando a ligação de volta, no meio de um efeito
        self.ao_aplicar = None
        self.atalhos_suspensos = False
        self.relogio_ligado = False
        self._marca = None

    def _pedido(self, nome, *argumentos):
        self.chamadas.append((nome, *argumentos))
        if nome in self.falhar_em:
            raise self.falhar_em[nome]

    # ---- leitura
    def quantas_linhas_selecionadas(self) -> int:
        self.leituras.append("quantas_linhas_selecionadas")
        return len(self.selecionadas)

    def linha_atual(self):
        self.leituras.append("linha_atual")
        return linha_info_de(self.mapa, self.selecionadas[0]) if len(self.selecionadas) == 1 else None

    def texto_do_editor(self) -> str:
        self.leituras.append("texto_do_editor")
        return self.editor

    # ---- ação
    def marcar(self, linha):
        self._pedido("marcar", linha)
        self._marca = marcar_o_comando(self.mapa, linha)
        if self.ao_marcar is not None:
            self.ao_marcar()

    def desmarcar(self):
        self._pedido("desmarcar")
        self._marca = None

    def fechar_editor(self):
        self._pedido("fechar_editor")

    def abrir_texto(self, linha, atual):
        self._pedido("abrir_texto", linha, atual)
        self.editor = atual

    def abrir_aplicativo(self, linha, atual):
        self._pedido("abrir_aplicativo", linha, atual)

    def propor_tecla(self, nome):
        self._pedido("propor_tecla", nome)

    def bip(self):
        self._pedido("bip")

    def aplicar_alvo(self, linha, valor, rotulo):
        self._pedido("aplicar_alvo", linha, valor, rotulo)
        return self._gravar(lambda: aplicar_alvo(self.mapa, self._marca, valor))

    def aplicar_texto(self, linha, texto, rotulo):
        self._pedido("aplicar_texto", linha, texto, rotulo)
        return self._gravar(lambda: aplicar_texto(self.mapa, self._marca, texto))

    def aplicar_tempo(self, linha, valor, rotulo):
        self._pedido("aplicar_tempo", linha, valor, rotulo)
        return self._gravar(lambda: aplicar_tempo(self.mapa, self._marca, valor))

    def aplicar_espera(self, linha, valor, rotulo):
        self._pedido("aplicar_espera", linha, valor, rotulo)
        return self._gravar(lambda: aplicar_espera(self.mapa, self._marca, valor))

    def _gravar(self, gravar):
        resultado = gravar()
        if resultado.ok and self.ao_aplicar is not None:
            self.ao_aplicar()  # a janela de verdade refaz a tabela e a seleção aqui, e o Qt avisa que a seleção mudou
        return resultado

    def dica(self, texto, segundos=0.0):
        self._pedido("dica", texto, segundos)

    def mostrar_valor(self, texto):
        self._pedido("mostrar_valor", texto)

    def limpar_dica(self):
        self._pedido("limpar_dica")

    def abrir_barra_lateral(self, linha):
        self._pedido("abrir_barra_lateral", linha)

    def editar_celula(self, linha):
        self._pedido("editar_celula", linha)

    def suspender_atalhos(self, suspender):
        self._pedido("suspender_atalhos", suspender)
        self.atalhos_suspensos = suspender

    def ligar_relogio(self, ligar):
        self._pedido("ligar_relogio", ligar)
        self.relogio_ligado = ligar

    # ---- consulta dos testes
    def nomes(self) -> list[str]:
        return [chamada[0] for chamada in self.chamadas]

    def de(self, nome) -> list[tuple]:
        return [chamada[1:] for chamada in self.chamadas if chamada[0] == nome]

    def esquecer(self) -> None:
        self.chamadas.clear()
        self.leituras.clear()

    def ultima_dica(self, temporaria=None):
        dicas = [c for c in self.chamadas if c[0] == "dica" and (temporaria is None or (c[2] > 0) == temporaria)]
        return dicas[-1][1] if dicas else None


def _nova(mapa=None, selecionadas=(0,)):
    """(ligação, porta, relógio): o controlador de verdade, a porta falsa e o tempo na mão."""
    mapa = mapa if mapa is not None else _mapa()
    porta, relogio = PortaFalsa(mapa, selecionadas), FakeClock(100.0)
    return LigacaoDoTeclado(porta, relogio=relogio.monotonic), porta, relogio


def _apertar(ligacao, tecla, repeticao=False):
    return ligacao.tecla_pressionada(tecla, repeticao)


def _digitar(ligacao, *teclas):
    for tecla in teclas:
        _apertar(ligacao, tecla)


def _foto(porta, ligacao):
    """O que uma tecla pode mudar: as chamadas à porta, o estado do controlador e o mapa."""
    return list(porta.chamadas), ligacao._controlador.estado, [c.to_dict() for c in porta.mapa.commands]


# Cada estado, o comando do mapa de teste em que ele se testa e o caminho do usuário até ele (um número é "passou esse tempo").
ONDE = {"tecla": TECLA, "texto": TEXTO, "programa": PROGRAMA, "botao": BOTAO, "tempo": TECLA, "espera": TEXTO}
CAMINHO = {"tecla": (ENTER,), "texto": (ENTER,), "programa": (ENTER,), "botao": (ENTER,), "tempo": (ENTER, 0.1, ENTER), "espera": (APOSTROFO,)}
ESTADO_DE = {"tecla": Estado.TECLA, "texto": Estado.TEXTO, "programa": Estado.APLICATIVO, "botao": Estado.BOTAO, "tempo": Estado.TEMPO,
             "espera": Estado.ESPERA}


def _levar_ao_estado(ligacao, relogio, estado):
    for passo in CAMINHO[estado]:
        if isinstance(passo, float):
            relogio.advance(passo)
        else:
            _apertar(ligacao, passo)
    assert ligacao._controlador.estado == ESTADO_DE[estado], estado


# ================================================================================================ a construção e a porta
def test_a_porta_falsa_cumpre_a_porta():
    """`Porta` é um Protocol: o que a janela de verdade tem de oferecer. A falsa dos testes e a de verdade cumprem a mesma lista."""
    assert isinstance(PortaFalsa(_mapa()), Porta)


def test_uma_porta_que_falta_um_metodo_nao_cumpre_a_porta():
    class Incompleta(PortaFalsa):
        bip = None
    assert not isinstance(Incompleta(_mapa()), Porta)


def test_uma_ligacao_nova_nao_pede_nada_a_porta_e_nao_esta_editando():
    ligacao, porta, _ = _nova()
    assert ligacao.editando() is False and ligacao.capturando() is False
    assert porta.chamadas == [] and porta.leituras == []


def test_o_relogio_padrao_e_o_monotonico():
    import time
    assert LigacaoDoTeclado(PortaFalsa(_mapa()))._relogio is time.monotonic


def test_capturando_so_no_estado_da_captura_de_tecla():
    """É o que a janela pergunta para traduzir o teclado numérico (só a captura distingue NUM5 de 5)."""
    for estado, esperado in (("tecla", True), ("texto", False), ("programa", False), ("botao", False), ("tempo", False), ("espera", False)):
        ligacao, porta, relogio = _nova(selecionadas=(ONDE[estado],))
        assert ligacao.capturando() is False
        _levar_ao_estado(ligacao, relogio, estado)
        assert ligacao.capturando() is esperado, estado
        assert ligacao.editando() is True, estado


# ================================================================================================ a navegação: só as quatro teclas são da ligação
@pytest.mark.parametrize("tecla", [Tecla("A", "a"), CIMA, BAIXO, Tecla("HOME"), Tecla("TAB"), ESC, Tecla("DELETE"), Tecla("F3"), Tecla("SPACE", " ")],
                         ids=["letra", "cima", "baixo", "home", "tab", "esc", "delete", "f3", "espaco"])
def test_navegando_toda_outra_tecla_segue_para_o_qt_e_a_porta_nem_e_consultada(tecla):
    """Digitar numa tabela cheia não pode custar uma consulta à janela por tecla: só as quatro teclas da ligação a consultam."""
    ligacao, porta, _ = _nova()
    assert _apertar(ligacao, tecla) is False
    assert porta.chamadas == [] and porta.leituras == []


@pytest.mark.parametrize("tecla", [ENTER, SHIFT_ENTER, F2, APOSTROFO], ids=["enter", "shift+enter", "f2", "apostrofo"])
def test_sem_linha_selecionada_as_quatro_teclas_seguem_o_caminho_antigo(tecla):
    """T3-4: com zero linhas a ligação não age e o Enter da tabela de sempre continua valendo."""
    ligacao, porta, _ = _nova(selecionadas=())
    assert _apertar(ligacao, tecla) is False
    assert porta.chamadas == []


@pytest.mark.parametrize("tecla", [ENTER, SHIFT_ENTER, F2, APOSTROFO], ids=["enter", "shift+enter", "f2", "apostrofo"])
def test_com_varias_linhas_selecionadas_as_quatro_teclas_sao_consumidas_com_a_dica(tecla):
    """T3-4: editar o conteúdo de vários comandos de uma vez não tem sentido, e o silêncio seria o pior jeito de dizer isso."""
    ligacao, porta, _ = _nova(selecionadas=(0, 2, 3))
    assert _apertar(ligacao, tecla) is True
    assert porta.nomes() == ["dica"]
    texto, segundos = porta.de("dica")[0]
    assert texto == "Escolha um só comando para editar com o teclado (há 3 selecionados)"
    assert segundos == tl.SEGUNDOS_DA_MENSAGEM > 0
    assert ligacao.editando() is False


def test_com_varias_linhas_selecionadas_a_dica_conta_as_linhas():
    ligacao, porta, _ = _nova(selecionadas=(0, 1))
    _apertar(ligacao, ENTER)
    assert porta.de("dica")[0][0].endswith("(há 2 selecionados)")


def test_linha_que_a_porta_nao_sabe_dizer_nao_e_editada():
    ligacao, porta, _ = _nova()
    porta.linha_atual = lambda: None
    assert _apertar(ligacao, ENTER) is False
    assert porta.chamadas == []


def test_ctrl_e_alt_voltam_inteiros_para_a_janela_em_qualquer_estado_e_nao_tocam_o_controlador():
    """Ctrl+Z desfaz mesmo no meio de uma edição (e isso a descarta); Ctrl+A, Alt+F4, os atalhos do Windows: nada disso é do teclado da tabela."""
    for preparar in (lambda lig: None, lambda lig: _apertar(lig, ENTER)):  # navegando; capturando a tecla
        ligacao, porta, _ = _nova()
        preparar(ligacao)
        estado = ligacao._controlador.estado
        porta.esquecer()
        for tecla in (Tecla("Z", "z", ctrl=True), Tecla("A", ctrl=True), Tecla("F4", alt=True), Tecla("ENTER", ctrl=True), Tecla("ESC", alt=True)):
            assert _apertar(ligacao, tecla) is False
        assert porta.chamadas == [] and porta.leituras == []
        assert ligacao._controlador.estado == estado


# ================================================================================================ fluxo: tecla
def test_o_fluxo_da_tecla_enter_depois_a_tecla_depois_a_mesma_de_novo():
    """O pedido do dono: aperta Enter, aperta a tecla (um bip), aperta a mesma de novo e vale. Tudo no mapa de verdade, na ordem dos pedidos."""
    ligacao, porta, _ = _nova()
    linha = linha_info_de(porta.mapa, TECLA)

    assert _apertar(ligacao, ENTER) is True
    assert porta.chamadas == [("marcar", 0), ("dica", dica_do_estado(Estado.TECLA, linha), 0.0), ("suspender_atalhos", True)]
    assert ligacao.editando() is True and porta.atalhos_suspensos is True

    porta.esquecer()
    assert _apertar(ligacao, Tecla("Q", "q")) is True
    assert porta.chamadas == [("propor_tecla", "Q"), ("bip",), ("dica", dica_do_estado(Estado.TECLA, linha, proposta="Q"), 0.0)]
    assert porta.mapa.commands[TECLA].target == "E", "a proposta ainda não vale nada"

    porta.esquecer()
    assert _apertar(ligacao, Tecla("Q", "q")) is True
    assert porta.chamadas == [
        ("aplicar_alvo", 0, "Q", "Editar tecla"),
        ("desmarcar",),
        ("dica", DICA_NAVEGANDO, 0.0),
        ("dica", "Tecla trocada para Q. Ctrl+Z desfaz.", tl.SEGUNDOS_DA_MENSAGEM),
        ("suspender_atalhos", False),
    ]
    assert porta.mapa.commands[TECLA].target == "Q"
    assert ligacao.editando() is False and porta.atalhos_suspensos is False


def test_outra_tecla_na_captura_troca_a_proposta_e_so_a_igual_confirma():
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER, Tecla("Q"), Tecla("W"))
    assert porta.de("propor_tecla") == [("Q",), ("W",)] and porta.de("bip") == [(), ()]
    assert porta.de("aplicar_alvo") == []
    _digitar(ligacao, Tecla("W"))
    assert porta.de("aplicar_alvo") == [(0, "W", "Editar tecla")]


def test_esc_na_captura_cancela_sem_gravar_e_a_dica_da_navegacao_volta():
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER, Tecla("Q"))
    porta.esquecer()
    assert _apertar(ligacao, ESC) is True
    assert porta.chamadas == [("desmarcar",), ("dica", DICA_NAVEGANDO, 0.0), ("suspender_atalhos", False)]
    assert porta.mapa.commands[TECLA].target == "E"
    assert ligacao.editando() is False


def test_a_tecla_sem_nome_na_captura_so_avisa_e_a_captura_continua():
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER)
    porta.esquecer()
    assert _apertar(ligacao, Tecla("", ";")) is True
    assert porta.chamadas == [("dica", DICA_TECLA_DESCONHECIDA, 0.0)]
    assert ligacao.editando() is True


def test_a_mesma_tecla_de_antes_nao_grava_nada():
    """Propor a tecla que o comando já tem e confirmar não muda o mapa, não faz passo no histórico e não diz que trocou."""
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER, Tecla("E"), Tecla("E"))
    assert porta.de("aplicar_alvo") == []
    assert ligacao.editando() is False
    assert all("trocada" not in (c[1] or "") for c in porta.chamadas if c[0] == "dica")


# ================================================================================================ fluxo: texto
def test_o_fluxo_do_texto_o_editor_abre_enter_confirma():
    ligacao, porta, relogio = _nova(selecionadas=(TEXTO,))
    assert _apertar(ligacao, ENTER) is True
    assert porta.nomes() == ["marcar", "abrir_texto", "dica"]
    assert porta.de("abrir_texto") == [(1, "olá")]
    assert ligacao.editando() is True
    assert porta.nomes().count("suspender_atalhos") == 0, "digitar texto não é gravar tecla: os atalhos seguem valendo"

    porta.editor = "outro texto"  # a pessoa digitou no editor da linha
    relogio.advance(2.0)
    porta.esquecer()
    assert _apertar(ligacao, ENTER) is True
    assert porta.chamadas == [
        ("aplicar_texto", 1, "outro texto", "Editar texto"),
        ("desmarcar",),
        ("dica", DICA_NAVEGANDO, 0.0),
        ("dica", "Texto trocado. Ctrl+Z desfaz.", tl.SEGUNDOS_DA_MENSAGEM),
    ]
    assert porta.mapa.commands[TEXTO].text == "outro texto"
    assert ligacao.editando() is False


def test_as_letras_digitadas_no_editor_de_texto_passam_para_ele_e_ate_repetidas():
    ligacao, porta, _ = _nova(selecionadas=(TEXTO,))
    _digitar(ligacao, ENTER)
    porta.esquecer()
    assert _apertar(ligacao, Tecla("A", "a")) is False
    assert _apertar(ligacao, Tecla("A", "a"), repeticao=True) is False, "segurar uma letra no editor digita a letra repetida"
    assert _apertar(ligacao, Tecla("LEFT")) is False
    assert porta.chamadas == []


def test_texto_vazio_nao_grava_e_a_edicao_continua():
    ligacao, porta, relogio = _nova(selecionadas=(TEXTO,))
    _digitar(ligacao, ENTER)
    porta.editor = ""
    relogio.advance(2.0)
    porta.esquecer()
    assert _apertar(ligacao, ENTER) is True
    assert porta.chamadas == [("dica", DICA_TEXTO_VAZIO, 0.0)]
    assert ligacao.editando() is True


def test_o_mesmo_texto_nao_grava_nada():
    ligacao, porta, relogio = _nova(selecionadas=(TEXTO,))
    _digitar(ligacao, ENTER)  # o editor abre com "olá"
    relogio.advance(2.0)
    _digitar(ligacao, ENTER)
    assert porta.de("aplicar_texto") == []
    assert ligacao.editando() is False


def test_esc_no_editor_de_texto_cancela():
    ligacao, porta, _ = _nova(selecionadas=(TEXTO,))
    _digitar(ligacao, ENTER)
    porta.editor = "meio digitado"
    porta.esquecer()
    assert _apertar(ligacao, ESC) is True
    assert porta.chamadas == [("desmarcar",), ("dica", DICA_NAVEGANDO, 0.0)]
    assert porta.mapa.commands[TEXTO].text == "olá"


def test_o_texto_do_editor_so_e_lido_quando_o_enter_pode_confirmar_no_estado_de_texto():
    ligacao, porta, relogio = _nova(selecionadas=(TEXTO,))
    _digitar(ligacao, ENTER)
    porta.leituras.clear()
    _apertar(ligacao, Tecla("A", "a"))
    _apertar(ligacao, Tecla("B", "b"))
    assert "texto_do_editor" not in porta.leituras, "letra digitada no editor é do editor: a ligação não precisa do texto"
    relogio.advance(2.0)
    _apertar(ligacao, ENTER)
    assert porta.leituras.count("texto_do_editor") == 1
    ligacao2, porta2, _ = _nova()
    _digitar(ligacao2, ENTER)
    porta2.leituras.clear()
    _digitar(ligacao2, Tecla("Q"), Tecla("Q"))
    assert "texto_do_editor" not in porta2.leituras, "fora do estado de texto o editor nem existe"


# ================================================================================================ fluxo: programa
def test_o_fluxo_do_programa_a_janela_abre_e_a_escolha_grava_levando_o_processo_junto():
    ligacao, porta, _ = _nova(selecionadas=(PROGRAMA,))
    assert _apertar(ligacao, ENTER) is True
    assert porta.nomes() == ["marcar", "abrir_aplicativo", "dica"]
    assert porta.de("abrir_aplicativo") == [(2, "notepad.exe")]
    assert ligacao.editando() is True

    porta.esquecer()
    ligacao.aplicativo_resolvido("msedge.exe")
    assert porta.chamadas == [
        ("aplicar_alvo", 2, "msedge.exe", "Editar programa"),
        ("desmarcar",),
        ("dica", DICA_NAVEGANDO, 0.0),
        ("dica", "Programa trocado para msedge.exe. Ctrl+Z desfaz.", tl.SEGUNDOS_DA_MENSAGEM),
    ]
    comando = porta.mapa.commands[PROGRAMA]
    assert (comando.target, comando.wait_process) == ("msedge.exe", "msedge.exe")
    assert ligacao.editando() is False


def test_o_programa_escolhido_por_caminho_aparece_so_com_o_nome_do_arquivo_na_frase():
    ligacao, porta, _ = _nova(selecionadas=(PROGRAMA,))
    _digitar(ligacao, ENTER)
    ligacao.aplicativo_resolvido("C:\\Programas\\Foo\\foo.exe")
    assert porta.ultima_dica(temporaria=True) == "Programa trocado para foo.exe. Ctrl+Z desfaz."
    assert porta.mapa.commands[PROGRAMA].target == "C:\\Programas\\Foo\\foo.exe"


def test_o_aviso_do_processo_esperado_diferente_vai_na_frase_antes_do_ctrl_z():
    ligacao, porta, _ = _nova(selecionadas=(PROGRAMA,))
    porta.mapa.commands[PROGRAMA].wait_process = "chrome.exe"
    _digitar(ligacao, ENTER)
    ligacao.aplicativo_resolvido("msedge.exe")
    frase = porta.ultima_dica(temporaria=True)
    assert frase.startswith("Programa trocado para msedge.exe. A automação continua esperando o processo «chrome.exe»")
    assert frase.endswith(" Ctrl+Z desfaz.")


def test_cancelar_a_janela_do_programa_nao_grava_nada():
    ligacao, porta, _ = _nova(selecionadas=(PROGRAMA,))
    _digitar(ligacao, ENTER)
    porta.esquecer()
    ligacao.aplicativo_resolvido(None)
    assert porta.chamadas == [("desmarcar",), ("dica", DICA_NAVEGANDO, 0.0)]
    assert porta.mapa.commands[PROGRAMA].target == "notepad.exe"
    assert ligacao.editando() is False


def test_o_mesmo_programa_nao_grava_nada():
    ligacao, porta, _ = _nova(selecionadas=(PROGRAMA,))
    _digitar(ligacao, ENTER)
    ligacao.aplicativo_resolvido("notepad.exe")
    assert porta.de("aplicar_alvo") == []


def test_aplicativo_resolvido_fora_do_estado_do_programa_e_ignorado():
    ligacao, porta, _ = _nova()
    ligacao.aplicativo_resolvido("msedge.exe")
    assert porta.chamadas == []
    _digitar(ligacao, ENTER)
    porta.esquecer()
    ligacao.aplicativo_resolvido("msedge.exe")
    assert porta.chamadas == []
    assert porta.mapa.commands[TECLA].target == "E"


def test_as_teclas_com_a_janela_do_programa_aberta_sao_da_janela_dela():
    ligacao, porta, _ = _nova(selecionadas=(PROGRAMA,))
    _digitar(ligacao, ENTER)
    porta.esquecer()
    assert _apertar(ligacao, ENTER) is False
    assert _apertar(ligacao, ESC) is False
    assert porta.chamadas == []
    assert ligacao.editando() is True, "quem fecha a edição é o resultado da janela, não uma tecla da tabela"


# ================================================================================================ fluxo: botão do mouse
def test_o_fluxo_do_botao_setas_trocam_e_enter_grava():
    ligacao, porta, _ = _nova(selecionadas=(BOTAO,))
    assert _apertar(ligacao, ENTER) is True
    assert porta.nomes() == ["marcar", "mostrar_valor", "dica"]
    assert ligacao.editando() is True
    porta.esquecer()
    assert _apertar(ligacao, DIR) is True
    assert porta.nomes() == ["mostrar_valor"]
    assert "right" in porta.de("mostrar_valor")[0][0]
    porta.esquecer()
    assert _apertar(ligacao, ENTER) is True
    assert porta.chamadas == [
        ("aplicar_alvo", 3, "right", "Editar botão"),
        ("desmarcar",),
        ("dica", DICA_NAVEGANDO, 0.0),
        ("dica", "Botão do mouse trocado para direito. Ctrl+Z desfaz.", tl.SEGUNDOS_DA_MENSAGEM),
    ]
    assert porta.mapa.commands[BOTAO].target == "right"


def test_o_botao_se_diz_em_portugues_na_frase_e_o_nome_desconhecido_volta_como_veio():
    assert [te.rotulo_do_botao(b) for b in ("left", "right", "middle", "x1", "x2")] == ["esquerdo", "direito", "do meio", "lateral X1", "lateral X2"]
    assert te.rotulo_do_botao("x9") == "x9"


def test_com_o_botao_aberto_toda_outra_tecla_e_engolida_para_a_tabela_nao_andar():
    ligacao, porta, _ = _nova(selecionadas=(BOTAO,))
    _digitar(ligacao, ENTER)
    porta.esquecer()
    for tecla in (CIMA, BAIXO, Tecla("A", "a"), Tecla("HOME"), Tecla("SPACE", " ")):
        assert _apertar(ligacao, tecla) is True
    assert porta.chamadas == []


# ================================================================================================ fluxo: tempo apertado, a seta segurada e o relógio
def _abrir_o_tempo(ligacao, relogio, porta):
    """Enter, e Enter de novo logo em seguida: o Enter duplo leva da captura ao tempo apertado."""
    _apertar(ligacao, ENTER)
    relogio.advance(0.2)
    _apertar(ligacao, ENTER)
    assert ligacao._controlador.estado == Estado.TEMPO


def test_enter_duplo_vai_da_captura_ao_tempo_fecha_a_captura_solta_os_atalhos_e_liga_o_relogio():
    ligacao, porta, relogio = _nova()
    _apertar(ligacao, ENTER)
    porta.esquecer()
    relogio.advance(0.2)
    assert _apertar(ligacao, ENTER) is True
    assert porta.nomes() == ["fechar_editor", "mostrar_valor", "dica", "suspender_atalhos", "ligar_relogio"]
    assert porta.de("suspender_atalhos") == [(False,)], "saiu da captura: os atalhos voltam"
    assert porta.de("ligar_relogio") == [(True,)]
    assert "0,2 s" in porta.de("mostrar_valor")[0][0]
    assert ligacao.editando() is True and porta.relogio_ligado is True and porta.atalhos_suspensos is False


def test_enter_depois_do_prazo_do_enter_duplo_e_uma_tecla_proposta_e_nao_o_tempo():
    ligacao, porta, relogio = _nova()
    _apertar(ligacao, ENTER)
    relogio.advance(te.JANELA_ENTER_DUPLO + 0.1)
    _apertar(ligacao, ENTER)
    assert ligacao._controlador.estado == Estado.TECLA
    assert porta.de("propor_tecla") == [("ENTER",)]


def test_a_seta_segurada_anda_pelo_relogio_e_a_repeticao_do_sistema_nao_muda_nada():
    """O toque vale na hora de apertar; segurando, o valor sobe pela curva do T2 (3 s bem lentos) lendo o relógio a cada tique de 33 ms, e as
    repetições de tecla do sistema (que variam de máquina para máquina) são consumidas sem efeito."""
    ligacao, porta, relogio = _nova()
    _abrir_o_tempo(ligacao, relogio, porta)
    base = 0.2
    assert _apertar(ligacao, DIR) is True
    instante_do_aperto = relogio.monotonic()
    assert porta.de("mostrar_valor")[-1][0].startswith("Tempo apertado: " + formatar_segundos(valor_apos(base, 1, 0.0, te.TEMPO_MINIMO, te.TETO)))
    while relogio.monotonic() - instante_do_aperto < 3.3:
        relogio.advance(0.033)
        assert _apertar(ligacao, DIR, repeticao=True) is True
        ligacao.tique()
    esperado = valor_apos(base, 1, relogio.monotonic() - instante_do_aperto, te.TEMPO_MINIMO, te.TETO)
    assert esperado > base + 0.3, "depois de 3,3 s a rampa já passou dos 3 s lentos"
    assert porta.de("mostrar_valor")[-1][0] == f"Tempo apertado: {formatar_segundos(esperado)}"
    assert ligacao._controlador.valor == esperado


def test_nos_tres_primeiros_segundos_o_valor_anda_devagar_e_depois_acelera():
    """O pedido do dono: "os 3 primeiros segundos bem lentos". Provado pelo que a ligação leva ao controlador a cada tique."""
    ligacao, porta, relogio = _nova()
    _abrir_o_tempo(ligacao, relogio, porta)
    _apertar(ligacao, DIR)
    inicio = relogio.monotonic()
    vistos = {}
    for segundos in (0.5, 1.0, 2.0, 3.0, 5.0, 8.0):
        relogio.advance(inicio + segundos - relogio.monotonic())
        ligacao.tique()
        vistos[segundos] = ligacao._controlador.valor
        decorrido = relogio.monotonic() - inicio
        assert vistos[segundos] == valor_apos(0.2, 1, decorrido, te.TEMPO_MINIMO, te.TETO), segundos
    assert vistos[3.0] - 0.2 < 0.35, "os 3 primeiros segundos andam menos de 0,35 s no total"
    assert vistos[8.0] - vistos[3.0] > 0.35, "nos 5 segundos seguintes anda mais do que andou nos 3 primeiros"


def test_soltar_a_seta_fixa_o_valor_do_instante_e_enter_grava_como_um_passo_do_historico():
    ligacao, porta, relogio = _nova()
    _abrir_o_tempo(ligacao, relogio, porta)
    _apertar(ligacao, DIR)
    relogio.advance(1.0)
    assert ligacao.tecla_solta("RIGHT") is True
    valor = valor_apos(0.2, 1, 1.0, te.TEMPO_MINIMO, te.TETO)
    assert "Tempo apertado: " + formatar_segundos(valor) in porta.de("mostrar_valor")[-1][0]
    porta.esquecer()
    relogio.advance(5.0)
    ligacao.tique()  # solta: o tempo que passa não muda mais o valor
    assert porta.de("mostrar_valor") == []
    assert _apertar(ligacao, ENTER) is True
    assert porta.chamadas == [
        ("aplicar_tempo", 0, valor, "Editar tempo apertado"),
        ("desmarcar",),
        ("dica", DICA_NAVEGANDO, 0.0),
        ("dica", f"Tempo apertado: {formatar_segundos(valor)}. Ctrl+Z desfaz.", tl.SEGUNDOS_DA_MENSAGEM),
        ("ligar_relogio", False),
    ]
    assert porta.mapa.commands[TECLA].duration == valor
    assert [c.start for c in porta.mapa.commands] == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0], "o tempo apertado não empurra os seguintes (D4)"
    assert porta.relogio_ligado is False


def test_esc_no_tempo_descarta_e_desliga_o_relogio():
    ligacao, porta, relogio = _nova()
    _abrir_o_tempo(ligacao, relogio, porta)
    _apertar(ligacao, DIR)
    porta.esquecer()
    assert _apertar(ligacao, ESC) is True
    assert porta.de("ligar_relogio") == [(False,)] and porta.de("aplicar_tempo") == []
    assert porta.mapa.commands[TECLA].duration == 0.2


def test_o_relogio_so_e_ligado_uma_vez_e_o_tique_sem_seta_nao_faz_nada():
    ligacao, porta, relogio = _nova()
    _abrir_o_tempo(ligacao, relogio, porta)
    porta.esquecer()
    for _ in range(10):
        relogio.advance(0.033)
        ligacao.tique()
    assert porta.chamadas == []


def test_o_tique_fora_dos_estados_de_ajuste_nao_faz_nada():
    ligacao, porta, relogio = _nova()
    ligacao.tique()
    _apertar(ligacao, ENTER)
    porta.esquecer()
    relogio.advance(1.0)
    ligacao.tique()
    assert porta.chamadas == []


def test_soltar_uma_tecla_qualquer_nao_faz_nada():
    ligacao, porta, _ = _nova()
    assert ligacao.tecla_solta("A") is False
    _apertar(ligacao, ENTER)
    porta.esquecer()
    assert ligacao.tecla_solta("Q") is False and porta.chamadas == []


# ================================================================================================ fluxo: espera
def test_o_apostrofo_abre_a_espera_e_enter_grava_empurrando_os_seguintes():
    ligacao, porta, relogio = _nova(selecionadas=(TEXTO,))
    assert _apertar(ligacao, APOSTROFO) is True
    assert porta.nomes() == ["marcar", "mostrar_valor", "dica", "ligar_relogio"]
    assert ligacao._controlador.estado == Estado.ESPERA
    porta.esquecer()
    _apertar(ligacao, DIR)
    relogio.advance(0.5)
    ligacao.tique()
    ligacao.tecla_solta("RIGHT")
    antes = porta.mapa.gap_before(TEXTO)
    valor = valor_apos(antes, 1, 0.5, porta.mapa.min_gap_before(TEXTO), te.TETO)
    assert valor > antes
    porta.esquecer()
    _apertar(ligacao, ENTER)
    assert porta.de("aplicar_espera") == [(TEXTO, valor, "Editar espera")]
    assert porta.ultima_dica(temporaria=True) == f"Espera antes do comando: {formatar_segundos(valor)}. Ctrl+Z desfaz."
    assert porta.mapa.gap_before(TEXTO) == pytest.approx(valor)
    atraso = valor - antes
    assert [c.start for c in porta.mapa.commands] == pytest.approx([0.0] + [c + atraso for c in (1.0, 2.0, 3.0, 4.0, 5.0)], abs=1e-6)


def test_a_espera_do_primeiro_comando_diz_que_e_quando_a_automacao_comeca():
    ligacao, porta, _ = _nova(selecionadas=(TECLA,))
    _apertar(ligacao, APOSTROFO)
    _apertar(ligacao, DIR)
    ligacao.tecla_solta("RIGHT")
    _apertar(ligacao, ENTER)
    assert porta.ultima_dica(temporaria=True) == "Começa em 0,01 s. Ctrl+Z desfaz."
    assert porta.mapa.commands[TECLA].start == pytest.approx(0.01)


def test_do_tempo_para_a_espera_com_o_apostrofo_o_relogio_segue_ligado_sem_religar():
    ligacao, porta, relogio = _nova()
    _abrir_o_tempo(ligacao, relogio, porta)
    porta.esquecer()
    _apertar(ligacao, APOSTROFO)
    assert ligacao._controlador.estado == Estado.ESPERA
    assert porta.de("ligar_relogio") == [], "TEMPO e ESPERA são os dois estados do relógio: ele não é desligado e ligado de novo"
    assert porta.relogio_ligado is True


# ================================================================================================ a repetição do sistema (tecla segurada)
@pytest.mark.parametrize("tecla", [ENTER, SHIFT_ENTER, F2, APOSTROFO], ids=["enter", "shift+enter", "f2", "apostrofo"])
def test_segurar_uma_das_quatro_teclas_da_navegacao_so_age_no_primeiro_aperto(tecla):
    ligacao, porta, _ = _nova()
    assert _apertar(ligacao, tecla) is True
    depois = _foto(porta, ligacao)
    for _ in range(6):
        assert _apertar(ligacao, tecla, repeticao=True) is True
    assert _foto(porta, ligacao) == depois, "segurar Enter não abre a edição nem a reabre"


@pytest.mark.parametrize("tecla", [CIMA, BAIXO, Tecla("PAGEDOWN"), Tecla("A", "a")], ids=["cima", "baixo", "pagedown", "letra"])
def test_segurar_as_demais_teclas_da_navegacao_deixa_as_repeticoes_seguirem_para_o_qt(tecla):
    """Segurar ↓ rola as linhas: a repetição é do Qt."""
    ligacao, porta, _ = _nova()
    assert _apertar(ligacao, tecla) is False
    assert [_apertar(ligacao, tecla, repeticao=True) for _ in range(5)] == [False] * 5
    assert porta.chamadas == []


def test_sem_linha_selecionada_segurar_o_enter_segue_o_caminho_antigo():
    ligacao, porta, _ = _nova(selecionadas=())
    assert _apertar(ligacao, ENTER) is False
    assert [_apertar(ligacao, ENTER, repeticao=True) for _ in range(3)] == [False] * 3


def test_com_varias_linhas_segurar_o_enter_mostra_a_dica_uma_vez_so():
    ligacao, porta, _ = _nova(selecionadas=(0, 1))
    assert _apertar(ligacao, ENTER) is True
    assert [_apertar(ligacao, ENTER, repeticao=True) for _ in range(4)] == [True] * 4
    assert len(porta.de("dica")) == 1


def test_a_repeticao_nunca_chega_ao_controlador():
    """No estado da captura, segurar a tecla proposta NÃO a confirma: a segunda leitura seria a repetição do sistema."""
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER, Tecla("Q"))
    porta.esquecer()
    for _ in range(5):
        assert _apertar(ligacao, Tecla("Q"), repeticao=True) is True
    assert porta.chamadas == [] and porta.mapa.commands[TECLA].target == "E"
    assert ligacao.editando() is True


def test_segurar_a_tecla_que_confirmou_nao_vaza_para_a_busca_por_letra_da_tabela():
    """O aperto que confirma foi consumido; as repetições dele (a pessoa segurou um instante) também, mesmo com a edição já encerrada."""
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER, Tecla("Q"), Tecla("Q"))
    assert ligacao.editando() is False
    depois = _foto(porta, ligacao)
    assert [_apertar(ligacao, Tecla("Q"), repeticao=True) for _ in range(5)] == [True] * 5
    assert _foto(porta, ligacao) == depois


def test_segurar_o_esc_que_cancelou_nao_chega_ao_esc_do_aplicativo():
    """T3-9: o Esc cede ao aplicativo só fora da edição. Sem esta regra, segurar o Esc que cancelou voltaria de página na repetição."""
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER)
    assert _apertar(ligacao, ESC) is True and ligacao.editando() is False
    assert [_apertar(ligacao, ESC, repeticao=True) for _ in range(5)] == [True] * 5
    ligacao.tecla_solta("ESC")
    assert _apertar(ligacao, ESC) is False, "um Esc novo, fora da edição, é do aplicativo como sempre foi"
    assert _apertar(ligacao, ESC, repeticao=True) is False


def test_soltar_a_tecla_encerra_o_consumo_das_repeticoes_dela():
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER, Tecla("Q"))
    assert _apertar(ligacao, Tecla("Q"), repeticao=True) is True
    ligacao.tecla_solta("q")
    assert _apertar(ligacao, Tecla("Q"), repeticao=True) is False


def test_um_aperto_novo_decide_de_novo_mesmo_sem_a_soltura_ter_chegado():
    """A soltura pode se perder (o foco sai da janela com a tecla apertada). Quem decide é sempre o ÚLTIMO aperto da tecla."""
    ligacao, porta, _ = _nova()
    assert _apertar(ligacao, ENTER) is True                      # consumido: a edição abre
    ligacao.descartar()
    porta.selecionadas = []                                       # sem soltura; agora não há linha selecionada
    assert _apertar(ligacao, ENTER) is False                     # o aperto novo segue o caminho antigo...
    assert _apertar(ligacao, ENTER, repeticao=True) is False     # ...e as repetições dele também


def test_teclas_sem_nome_e_sem_texto_dividem_um_lugar_so():
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER)
    assert _apertar(ligacao, Tecla("")) is True, "a captura consome a tecla sem nome (e avisa)"
    assert _apertar(ligacao, Tecla(""), repeticao=True) is True


@pytest.mark.parametrize("estado", ["tecla", "botao", "tempo", "espera"])
@pytest.mark.parametrize("tecla", [ENTER, ESC, DIR, CIMA, Tecla("A", "a")], ids=["enter", "esc", "direita", "cima", "letra"])
def test_nos_estados_de_captura_e_de_ajuste_so_o_primeiro_aperto_age(estado, tecla):
    """Todas as teclas sem Ctrl/Alt são do controlador nestes estados (age ou é engolida); a repetição não muda nada."""
    ligacao, porta, relogio = _nova(selecionadas=(ONDE[estado],))
    _levar_ao_estado(ligacao, relogio, estado)
    relogio.advance(1.0)  # fora do prazo do Enter duplo
    assert _apertar(ligacao, tecla) is True
    depois = _foto(porta, ligacao)
    for _ in range(5):
        assert _apertar(ligacao, tecla, repeticao=True) is True
    assert _foto(porta, ligacao) == depois


@pytest.mark.parametrize("tecla", [ENTER, ESC], ids=["enter", "esc"])
def test_no_editor_de_texto_a_repeticao_de_enter_e_esc_e_consumida(tecla):
    ligacao, porta, relogio = _nova(selecionadas=(TEXTO,))
    _digitar(ligacao, ENTER)
    relogio.advance(1.0)
    assert _apertar(ligacao, tecla) is True and ligacao.editando() is False
    depois = _foto(porta, ligacao)
    assert [_apertar(ligacao, tecla, repeticao=True) for _ in range(5)] == [True] * 5
    assert _foto(porta, ligacao) == depois


def test_a_repeticao_de_ctrl_ou_alt_tambem_volta_inteira_para_a_janela():
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER)
    porta.esquecer()
    assert _apertar(ligacao, Tecla("Z", ctrl=True), repeticao=True) is False
    assert _apertar(ligacao, Tecla("F4", alt=True), repeticao=True) is False
    assert porta.chamadas == []


# ================================================================================================ descartar
@pytest.mark.parametrize("quem", ["selecao_mudou", "perdeu_foco", "descartar"])
@pytest.mark.parametrize("estado", sorted(ONDE))
def test_cada_caminho_que_descarta_acaba_com_a_edicao_sem_gravar_nada_e_sem_deixar_interruptor_ligado(estado, quem):
    """T3-8: a seleção muda, o foco sai, a janela é desativada, o mapa muda por baixo (desfazer): a edição já não vale. Em TODOS os estados."""
    ligacao, porta, relogio = _nova(selecionadas=(ONDE[estado],))
    mapa_antes = [c.to_dict() for c in porta.mapa.commands]
    _levar_ao_estado(ligacao, relogio, estado)
    assert ligacao.editando() is True
    porta.esquecer()
    getattr(ligacao, quem)()
    assert ligacao.editando() is False
    assert ligacao._controlador.estado == Estado.NAVEGANDO
    assert "desmarcar" in porta.nomes(), "a marca sai da linha"
    assert not any(nome.startswith("aplicar_") for nome in porta.nomes())
    assert [c.to_dict() for c in porta.mapa.commands] == mapa_antes
    assert porta.atalhos_suspensos is False and porta.relogio_ligado is False
    if estado == "tecla":
        assert porta.de("suspender_atalhos") == [(False,)], "descartar a captura devolve os atalhos de automação"
    if estado in ("tempo", "espera"):
        assert porta.de("ligar_relogio") == [(False,)], "descartar o ajuste desliga o relógio"
    if quem == "perdeu_foco":
        assert porta.nomes()[-1] == "limpar_dica", "sem foco a barra de status não fica com a dica da tabela"
    else:
        assert ("dica", DICA_NAVEGANDO, 0.0) in porta.chamadas


@pytest.mark.parametrize("quem", ["selecao_mudou", "perdeu_foco", "descartar"])
def test_descartar_sem_edicao_nao_toca_a_porta_exceto_limpar_a_dica_ao_perder_o_foco(quem):
    ligacao, porta, _ = _nova()
    getattr(ligacao, quem)()
    assert porta.nomes() == (["limpar_dica"] if quem == "perdeu_foco" else [])


def test_a_edicao_descartada_nao_deixa_o_controlador_com_a_linha_marcada():
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER)
    ligacao.descartar()
    assert ligacao._controlador.linha is None


def test_depois_de_descartar_uma_edicao_nova_comeca_do_zero():
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER, Tecla("Q"))
    ligacao.descartar()
    porta.esquecer()
    _digitar(ligacao, ENTER)
    assert porta.nomes() == ["marcar", "dica", "suspender_atalhos"]
    assert porta.de("suspender_atalhos") == [(True,)], "a captura nova suspende os atalhos de novo"
    _digitar(ligacao, Tecla("Q"))
    assert porta.de("aplicar_alvo") == [], "a proposta Q da edição descartada não vale na nova"


def test_ganhar_o_foco_mostra_a_dica_da_navegacao_so_se_nao_ha_edicao():
    ligacao, porta, _ = _nova()
    ligacao.ganhou_foco()
    assert porta.chamadas == [("dica", DICA_NAVEGANDO, 0.0)]
    _digitar(ligacao, ENTER)
    porta.esquecer()
    ligacao.ganhou_foco()
    assert porta.chamadas == [], "voltar o foco para a tabela no meio de uma edição não apaga a dica dela"


def test_descartar_no_meio_dos_efeitos_interrompe_o_resto_e_nao_deixa_editor_sobrando():
    """Um evento do Qt causado pelo próprio efeito `marcar` descarta a edição: o `abrir_texto` que viria depois NÃO pode abrir um editor para uma
    edição que já não existe (ficaria um campo de texto órfão na tabela)."""
    ligacao, porta, _ = _nova(selecionadas=(TEXTO,))
    porta.ao_marcar = ligacao.selecao_mudou
    assert _apertar(ligacao, ENTER) is True
    assert ligacao.editando() is False
    assert porta.nomes() == ["marcar", "desmarcar", "dica"]
    assert porta.atalhos_suspensos is False and porta.relogio_ligado is False


def test_descartar_no_meio_dos_efeitos_da_captura_nao_deixa_os_atalhos_suspensos():
    ligacao, porta, _ = _nova()
    porta.ao_marcar = ligacao.selecao_mudou
    assert _apertar(ligacao, ENTER) is True
    assert ligacao.editando() is False
    assert porta.de("suspender_atalhos") == [] and porta.atalhos_suspensos is False


# ================================================================================================ suspensão e relógio: quem manda é o estado
def test_os_atalhos_so_ficam_suspensos_no_estado_da_captura_de_tecla():
    """T3-7: a ligação suspende ao ENTRAR no estado TECLA e retoma ao SAIR dele por qualquer caminho. Em nenhum outro estado."""
    for estado in ("texto", "programa", "botao", "espera", "tempo"):
        ligacao, porta, relogio = _nova(selecionadas=(ONDE[estado],))
        _levar_ao_estado(ligacao, relogio, estado)
        suspensoes = porta.de("suspender_atalhos")
        assert porta.atalhos_suspensos is False, estado
        if estado == "tempo":  # passa pela captura (Enter duplo) e a solta
            assert suspensoes == [(True,), (False,)], estado
        else:
            assert suspensoes == [], f"no estado {estado} apertar uma tecla de automação deve disparar a automação"


def test_so_um_pedido_de_suspender_por_captura_e_um_so_de_retomar():
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER, Tecla("Q"), Tecla("W"), Tecla("Z"), Tecla("Z"))
    assert porta.de("suspender_atalhos") == [(True,), (False,)]


def test_a_confirmacao_a_saida_pelo_enter_duplo_e_o_descarte_retomam_igual():
    caminhos = {
        "confirmar": lambda lig, rel: _digitar(lig, Tecla("Q"), Tecla("Q")),
        "esc": lambda lig, rel: _digitar(lig, ESC),
        "enter-duplo": lambda lig, rel: (rel.advance(0.1), _digitar(lig, ENTER)),
        "descartar": lambda lig, rel: lig.descartar(),
        "selecao": lambda lig, rel: lig.selecao_mudou(),
        "foco": lambda lig, rel: lig.perdeu_foco(),
    }
    for nome, sair in caminhos.items():
        ligacao, porta, relogio = _nova()
        _apertar(ligacao, ENTER)
        assert porta.atalhos_suspensos is True, nome
        sair(ligacao, relogio)
        assert porta.de("suspender_atalhos") == [(True,), (False,)], nome
        assert porta.atalhos_suspensos is False, nome


# ================================================================================================ erro dentro de um efeito (T3-13)
# (o método da porta que falha, o comando selecionado, as teclas que levam ao ponto certo, a tecla que dispara o efeito)
CENARIOS_DE_ERRO = [
    ("marcar", TECLA, (), ENTER),
    ("dica", TECLA, (), ENTER),
    ("abrir_texto", TEXTO, (), ENTER),
    ("abrir_aplicativo", PROGRAMA, (), ENTER),
    ("mostrar_valor", BOTAO, (), ENTER),
    ("propor_tecla", TECLA, (ENTER,), Tecla("Q")),
    ("bip", TECLA, (ENTER,), Tecla("Q")),
    ("aplicar_alvo", TECLA, (ENTER, Tecla("Q")), Tecla("Q")),
    ("desmarcar", TECLA, (ENTER,), ESC),
    ("suspender_atalhos", TECLA, (), ENTER),
]


@pytest.mark.parametrize("metodo, linha, antes, tecla", CENARIOS_DE_ERRO, ids=[c[0] for c in CENARIOS_DE_ERRO])
def test_erro_num_efeito_descarta_a_edicao_avisa_e_consome_a_tecla(metodo, linha, antes, tecla, runtime_log):
    """T3-13: uma exceção num filtro de eventos não pode deixar a tabela presa num estado de edição nem escapar para o Qt."""
    ligacao, porta, _ = _nova(selecionadas=(linha,))
    _digitar(ligacao, *antes)
    mapa_antes = [c.to_dict() for c in porta.mapa.commands]
    porta.falhar_em[metodo] = RuntimeError(f"falhou {metodo} de propósito")
    assert _apertar(ligacao, tecla) is True
    assert ligacao.editando() is False
    assert ligacao._controlador.estado == Estado.NAVEGANDO
    assert [c.to_dict() for c in porta.mapa.commands] == mapa_antes, "nada foi gravado"
    assert porta.ultima_dica() == MENSAGEM_DO_ERRO
    assert any(f"falhou {metodo} de propósito" in linha for linha in runtime_log), "o erro vai para o log do Studio"
    assert porta.relogio_ligado is False
    if metodo != "suspender_atalhos":
        assert porta.atalhos_suspensos is False, "mesmo com erro, os atalhos de automação voltam"


def test_erro_na_gravacao_nada_foi_gravado_e_o_dono_e_avisado(runtime_log):
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER, Tecla("Q"))
    porta.falhar_em["aplicar_alvo"] = RuntimeError("o modelo recusou")
    antes = porta.mapa.commands[TECLA].to_dict()
    assert _apertar(ligacao, Tecla("Q")) is True
    assert porta.mapa.commands[TECLA].to_dict() == antes
    assert porta.ultima_dica(temporaria=True) == MENSAGEM_DO_ERRO
    assert ligacao.editando() is False
    assert porta.de("suspender_atalhos")[-1] == (False,), "mesmo com erro, os atalhos de automação voltam"
    assert "desmarcar" in porta.nomes()
    assert any("o modelo recusou" in linha for linha in runtime_log)


def test_erro_depois_de_gravar_diz_que_a_mudanca_foi_gravada(runtime_log):
    """O T3-13 não pode mentir: se a gravação deu certo e foi a tela que falhou depois, "nada foi gravado" seria falso."""
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER, Tecla("Q"))
    porta.falhar_em["desmarcar"] = RuntimeError("a marca travou")
    assert _apertar(ligacao, Tecla("Q")) is True
    assert porta.mapa.commands[TECLA].target == "Q"
    assert porta.ultima_dica(temporaria=True) == tl.MENSAGEM_DO_ERRO_GRAVADO
    assert ligacao.editando() is False and porta.atalhos_suspensos is False


def test_erro_no_tempo_desliga_o_relogio_mesmo_assim(runtime_log):
    ligacao, porta, relogio = _nova()
    _abrir_o_tempo(ligacao, relogio, porta)
    _apertar(ligacao, DIR)
    porta.falhar_em["aplicar_tempo"] = RuntimeError("falhou")
    assert _apertar(ligacao, ENTER) is True
    assert porta.de("ligar_relogio")[-1] == (False,) and porta.relogio_ligado is False
    assert ligacao.editando() is False


def test_erro_no_tique_descarta_a_edicao_e_avisa(runtime_log):
    ligacao, porta, relogio = _nova()
    _abrir_o_tempo(ligacao, relogio, porta)
    _apertar(ligacao, DIR)
    relogio.advance(0.5)
    porta.falhar_em["mostrar_valor"] = RuntimeError("barra de status quebrou")
    ligacao.tique()  # não pode levantar: o tique vem de um QTimer
    assert ligacao.editando() is False and porta.relogio_ligado is False
    assert porta.ultima_dica(temporaria=True) == MENSAGEM_DO_ERRO


def test_erro_ao_confirmar_pela_janela_do_programa_tambem_e_tratado(runtime_log):
    ligacao, porta, _ = _nova(selecionadas=(PROGRAMA,))
    _digitar(ligacao, ENTER)
    porta.falhar_em["aplicar_alvo"] = RuntimeError("falhou")
    ligacao.aplicativo_resolvido("msedge.exe")  # não pode levantar: vem de um sinal do Qt
    assert ligacao.editando() is False and porta.ultima_dica(temporaria=True) == MENSAGEM_DO_ERRO
    assert porta.mapa.commands[PROGRAMA].target == "notepad.exe"


def test_se_ate_a_limpeza_falhar_a_excecao_nao_escapa(runtime_log):
    """O `desmarcar` da limpeza também levantar: não pode haver exceção saindo da ligação para o filtro do Qt."""
    ligacao, porta, _ = _nova()
    porta.falhar_em["marcar"] = RuntimeError("primeira")
    porta.falhar_em["desmarcar"] = RuntimeError("segunda")
    porta.falhar_em["dica"] = RuntimeError("terceira")
    assert _apertar(ligacao, ENTER) is True
    assert ligacao.editando() is False
    for palavra in ("primeira", "segunda", "terceira"):
        assert any(palavra in linha for linha in runtime_log), palavra


def test_se_nao_da_para_suspender_os_atalhos_a_captura_nao_fica_aberta(runtime_log):
    """Capturar uma tecla com os atalhos de automação ligados poderia disparar uma automação: sem a suspensão, a edição não começa."""
    ligacao, porta, _ = _nova()
    porta.falhar_em["suspender_atalhos"] = RuntimeError("sem gerenciador")
    assert _apertar(ligacao, ENTER) is True
    assert ligacao.editando() is False
    assert porta.ultima_dica(temporaria=True) == MENSAGEM_DO_ERRO
    assert any("sem gerenciador" in linha for linha in runtime_log)


def test_depois_de_um_erro_a_ligacao_segue_funcionando(runtime_log):
    ligacao, porta, _ = _nova()
    porta.falhar_em["marcar"] = RuntimeError("uma vez só")
    _apertar(ligacao, ENTER)
    del porta.falhar_em["marcar"]
    porta.esquecer()
    _digitar(ligacao, ENTER, Tecla("Q"), Tecla("Q"))
    assert porta.mapa.commands[TECLA].target == "Q"


def test_o_erro_diz_o_que_aconteceu_no_log_com_o_tipo_da_excecao(runtime_log):
    ligacao, porta, _ = _nova()
    porta.falhar_em["marcar"] = KeyError("sem a chave")
    _apertar(ligacao, ENTER)
    assert any(linha.startswith("TECLADO_EDICAO ") and "KeyError" in linha and "sem a chave" in linha for linha in runtime_log)


# ================================================================================================ cada efeito do controlador tem tratamento
EFEITOS = ["Marcar", "Desmarcar", "Cancelar", "FecharEditor", "IniciarCaptura", "ProporTecla", "Bip", "AbrirTexto", "AbrirAplicativo", "AplicarAlvo",
           "AplicarTexto", "AplicarTempo", "AplicarEspera", "Dica", "MostrarValor", "AbrirBarraLateral", "EditarCelula"]


def test_sao_exatamente_17_os_efeitos_do_controlador():
    """Se um efeito novo nascer no controlador, este teste falha e obriga a ligação a tratá-lo."""
    achados = sorted(nome for nome, objeto in vars(te).items()
                     if isinstance(objeto, type) and objeto.__module__ == te.__name__
                     and nome not in ("Estado", "Tecla", "LinhaInfo", "Resposta", "EdicaoPorTeclado"))
    assert achados == sorted(EFEITOS)
    assert sorted(cls.__name__ for cls in tl.EFEITOS_TRATADOS) == sorted(EFEITOS), "a ligação declara tratar exatamente os 17"


class ControladorDeMentira:
    """Entrega à ligação o efeito que o teste quiser, para provar o tratamento de CADA classe sem montar o fluxo que a produz."""

    def __init__(self, efeito, estado=Estado.NAVEGANDO):
        self.efeito, self.estado, self.linha = efeito, estado, None

    def pressionar(self, tecla, agora, linha=None, texto=None):
        return Resposta(True, (self.efeito,))

    def soltar(self, nome, agora):
        return Resposta(False, ())

    def tique(self, agora):
        return Resposta(False, ())

    def conteudo_resolvido(self, valor):
        return Resposta(False, ())

    def descartar(self):
        return Resposta(False, ())


def _com_mentira(efeito, estado=Estado.NAVEGANDO, linha=0):
    porta = PortaFalsa(_mapa(), selecionadas=(linha,))
    ligacao = LigacaoDoTeclado(porta, relogio=FakeClock(0.0).monotonic, controlador=ControladorDeMentira(efeito, estado))
    return ligacao, porta


# efeito -> o que a porta recebe, na ordem
TRATAMENTO = {
    "Marcar": (te.Marcar(2), [("marcar", 2)]),
    "Desmarcar": (te.Desmarcar(), [("desmarcar",), ("dica", DICA_NAVEGANDO, 0.0)]),
    "Cancelar": (te.Cancelar(), [("desmarcar",), ("dica", DICA_NAVEGANDO, 0.0)]),
    "FecharEditor": (te.FecharEditor(), [("fechar_editor",)]),
    "IniciarCaptura": (te.IniciarCaptura(0, "E"), []),  # a captura não tem campo: é a tabela que recebe a tecla (T3-5)
    "ProporTecla": (te.ProporTecla("Q"), [("propor_tecla", "Q")]),
    "Bip": (te.Bip(), [("bip",)]),
    "AbrirTexto": (te.AbrirTexto(1, "olá"), [("abrir_texto", 1, "olá")]),
    "AbrirAplicativo": (te.AbrirAplicativo(2, "notepad.exe"), [("abrir_aplicativo", 2, "notepad.exe")]),
    "Dica": (te.Dica("uma dica"), [("dica", "uma dica", 0.0)]),
    "MostrarValor": (te.MostrarValor("0,5 s"), [("mostrar_valor", "0,5 s")]),
    "AbrirBarraLateral": (te.AbrirBarraLateral(3), [("abrir_barra_lateral", 3)]),
    "EditarCelula": (te.EditarCelula(3), [("editar_celula", 3)]),
}


@pytest.mark.parametrize("nome", sorted(TRATAMENTO))
def test_cada_efeito_vira_o_pedido_certo_a_porta(nome):
    efeito, esperado = TRATAMENTO[nome]
    ligacao, porta = _com_mentira(efeito)
    assert ligacao.tecla_pressionada(ENTER) is True
    assert porta.chamadas == esperado


APLICAR = [
    ("AplicarAlvo", te.AplicarAlvo(TECLA, "Q"), Estado.TECLA, ("aplicar_alvo", 0, "Q", "Editar tecla")),
    ("AplicarAlvo", te.AplicarAlvo(BOTAO, "right"), Estado.BOTAO, ("aplicar_alvo", 3, "right", "Editar botão")),
    ("AplicarAlvo", te.AplicarAlvo(PROGRAMA, "msedge.exe"), Estado.APLICATIVO, ("aplicar_alvo", 2, "msedge.exe", "Editar programa")),
    ("AplicarTexto", te.AplicarTexto(TEXTO, "novo"), Estado.TEXTO, ("aplicar_texto", 1, "novo", "Editar texto")),
    ("AplicarTempo", te.AplicarTempo(TECLA, 0.5), Estado.TEMPO, ("aplicar_tempo", 0, 0.5, "Editar tempo apertado")),
    ("AplicarEspera", te.AplicarEspera(TEXTO, 0.9), Estado.ESPERA, ("aplicar_espera", 1, 0.9, "Editar espera")),
]


@pytest.mark.parametrize("nome, efeito, estado, chamada", APLICAR, ids=[f"{a[0]}-{a[2].value}" for a in APLICAR])
def test_os_efeitos_de_gravar_chamam_a_porta_com_o_rotulo_do_historico_do_estado_de_onde_vieram(nome, efeito, estado, chamada):
    """Tecla, botão e programa são o mesmo efeito (`AplicarAlvo`) com três rótulos de histórico: quem distingue é o estado em que a edição estava (T3-14)."""
    ligacao, porta = _com_mentira(efeito, estado, linha=efeito.linha)
    porta.marcar(efeito.linha)
    porta.esquecer()
    assert ligacao.tecla_pressionada(ENTER) is True
    assert porta.chamadas[0] == chamada


def test_os_17_efeitos_estao_cobertos_pelos_testes_acima():
    assert sorted(set(TRATAMENTO) | {a[0] for a in APLICAR}) == sorted(EFEITOS)
    assert len(TRATAMENTO) == 13 and len({a[0] for a in APLICAR}) == 4


def test_efeito_que_a_ligacao_nao_conhece_e_um_erro_tratado_como_qualquer_outro(runtime_log):
    class EfeitoNovo:
        pass
    ligacao, porta = _com_mentira(EfeitoNovo())
    assert ligacao.tecla_pressionada(ENTER) is True
    assert porta.ultima_dica() == MENSAGEM_DO_ERRO
    assert any("EfeitoNovo" in linha for linha in runtime_log)


def test_a_ordem_dos_efeitos_e_a_que_o_controlador_mandou():
    """Os efeitos do Enter duplo vêm na ordem fechar, valor, dica: a ligação não os reordena."""
    ligacao, porta, relogio = _nova()
    _apertar(ligacao, ENTER)
    porta.esquecer()
    relogio.advance(0.1)
    _apertar(ligacao, ENTER)
    nomes = porta.nomes()
    assert nomes.index("fechar_editor") < nomes.index("mostrar_valor") < nomes.index("dica")


# ================================================================================================ o resultado da gravação: sucesso, aviso e recusa
def test_gravacao_recusada_mostra_a_mensagem_da_recusa_sem_o_ctrl_z_e_termina_a_edicao():
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER, Tecla("Q"))
    porta.mapa.commands[TECLA].id = "outro"  # a lista mudou por outro caminho durante a edição
    antes = [c.to_dict() for c in porta.mapa.commands]
    porta.esquecer()
    assert _apertar(ligacao, Tecla("Q")) is True
    assert porta.ultima_dica(temporaria=True) == MENSAGEM_MUDOU
    assert "Ctrl+Z" not in porta.ultima_dica(temporaria=True)
    assert [c.to_dict() for c in porta.mapa.commands] == antes
    assert ligacao.editando() is False
    assert porta.de("suspender_atalhos") == [(False,)]
    assert porta.nomes().index("desmarcar") < len(porta.nomes()), "a marca sai mesmo com a gravação recusada"


def test_gravacao_recusada_sem_mensagem_ainda_diz_que_nada_foi_gravado():
    ligacao, porta, _ = _nova()
    _digitar(ligacao, ENTER, Tecla("Q"))
    porta.aplicar_alvo = lambda linha, valor, rotulo: tl.Resultado(False)
    _apertar(ligacao, Tecla("Q"))
    assert porta.ultima_dica(temporaria=True) == "Nada foi gravado."


def test_a_mensagem_dura_o_mesmo_tempo_em_todas_as_gravacoes():
    assert tl.SEGUNDOS_DA_MENSAGEM == 6.0


# ================================================================================================ reentrância: o Qt chama a ligação de volta
def test_o_refresh_da_tabela_depois_de_gravar_pode_chamar_a_ligacao_de_volta_sem_estragar_nada():
    """Gravar faz a janela refazer a tabela e a seleção; isso dispara `selecao_mudou` DENTRO do efeito de gravar. A janela guarda contra isso,
    mas se escapar, a ligação tem de aguentar: a edição já terminou no controlador, então é um descarte sem nada a descartar."""
    ligacao, porta, _ = _nova()
    porta.ao_aplicar = ligacao.selecao_mudou
    _digitar(ligacao, ENTER, Tecla("Q"), Tecla("Q"))
    assert porta.mapa.commands[TECLA].target == "Q"
    assert ligacao.editando() is False
    assert porta.ultima_dica(temporaria=True) == "Tecla trocada para Q. Ctrl+Z desfaz."
    assert porta.de("suspender_atalhos") == [(True,), (False,)]


# ================================================================================================ os três mapas reais
NOMES_DOS_MAPAS = ["Click genshin", "Exemplo — Primeira automação", "Flins combo"]
IDS_DOS_MAPAS = ["click-genshin", "exemplo", "flins-combo"]


def _editar_pelo_teclado(ligacao, porta, relogio, mapa, indice):
    """Edita o conteúdo do comando `indice` pelo caminho do usuário (o que o pedido descreve, tipo por tipo) e devolve o que o mapa deve ter depois."""
    comando = mapa.commands[indice]
    if comando.type == K:
        nova = "Z" if comando.target.upper() != "Z" else "Y"
        _digitar(ligacao, ENTER, Tecla(nova), Tecla(nova))
        return {"target": nova}
    if comando.type == B:
        sentido, esperado = (DIR, "right") if comando.target != "right" else (ESQ, "left")
        _digitar(ligacao, ENTER, sentido, ENTER)
        return {"target": esperado}
    if comando.type == T:
        _apertar(ligacao, ENTER)
        porta.editor = comando.text + " (editado pelo teclado)"
        relogio.advance(1.0)
        _apertar(ligacao, ENTER)
        return {"text": porta.editor}
    assert comando.type == A, comando.type
    _apertar(ligacao, ENTER)
    ligacao.aplicativo_resolvido("msedge.exe")
    return {"target": "msedge.exe"}


@pytest.mark.parametrize("nome", NOMES_DOS_MAPAS, ids=IDS_DOS_MAPAS)
def test_nos_mapas_reais_a_edicao_de_cada_tipo_de_conteudo_pelo_teclado_funciona_e_o_mapa_continua_valido(legacy_maps, nome):
    """Os 3 mapas reais juntos têm os quatro tipos com conteúdo: tecla e botão (Click genshin), programa e texto (Exemplo), tecla e movimento (Flins)."""
    mapa = map_from_json(legacy_maps[nome])
    tipos = [t for t in (K, B, T, A) if any(c.type == t for c in mapa.commands)]
    assert tipos, nome
    for tipo in tipos:
        indice = next(i for i, c in enumerate(mapa.commands) if c.type == tipo)
        ligacao, porta, relogio = _nova(mapa=mapa, selecionadas=(indice,))
        esperado = _editar_pelo_teclado(ligacao, porta, relogio, mapa, indice)
        for campo, valor in esperado.items():
            assert getattr(mapa.commands[indice], campo) == valor, (nome, tipo, campo)
        assert ligacao.editando() is False
        assert mapa.validate() == [], (nome, tipo)
        assert porta.ultima_dica(temporaria=True).endswith("Ctrl+Z desfaz."), (nome, tipo)


def test_os_tres_mapas_reais_juntos_cobrem_os_quatro_tipos_com_conteudo(legacy_maps):
    tipos = {c.type for nome in NOMES_DOS_MAPAS for c in map_from_json(legacy_maps[nome]).commands}
    assert {K, B, T, A} <= tipos


@pytest.mark.parametrize("nome", NOMES_DOS_MAPAS, ids=IDS_DOS_MAPAS)
def test_nos_mapas_reais_a_espera_do_comando_do_meio_empurra_os_seguintes_e_o_mapa_continua_valido(legacy_maps, nome):
    mapa = map_from_json(legacy_maps[nome])
    indice = len(mapa.commands) // 2
    ligacao, porta, relogio = _nova(mapa=mapa, selecionadas=(indice,))
    antes = [c.start for c in mapa.commands]
    atual = mapa.gap_before(indice)
    valor = valor_apos(atual, 1, 0.0, mapa.min_gap_before(indice), te.TETO)  # o toque, que o controlador leva ao milissegundo
    _apertar(ligacao, APOSTROFO)
    _apertar(ligacao, DIR)
    ligacao.tecla_solta("RIGHT")
    _apertar(ligacao, ENTER)
    assert mapa.gap_before(indice) == pytest.approx(valor, abs=1e-6)
    depois, atraso = [c.start for c in mapa.commands], valor - atual
    assert depois[:indice] == antes[:indice], "os anteriores não se mexem"
    assert depois[indice:] == pytest.approx([x + atraso for x in antes[indice:]], abs=1e-6)
    assert mapa.validate() == []


@pytest.mark.parametrize("nome", ["Click genshin", "Flins combo"], ids=["click-genshin", "flins-combo"])  # o Exemplo só tem programa e texto
def test_nos_mapas_reais_o_tempo_apertado_do_primeiro_comando_de_tecla_ou_botao_funciona(legacy_maps, nome):
    mapa = map_from_json(legacy_maps[nome])
    indice = next(i for i, c in enumerate(mapa.commands) if c.type in (K, B) and c.action == ActionType.PRESS_AND_RELEASE)
    ligacao, porta, relogio = _nova(mapa=mapa, selecionadas=(indice,))
    antes, duracao = [c.start for c in mapa.commands], mapa.commands[indice].duration
    _apertar(ligacao, ENTER)
    relogio.advance(0.2)
    _apertar(ligacao, ENTER)  # Enter, Enter
    _apertar(ligacao, DIR)
    ligacao.tecla_solta("RIGHT")
    _apertar(ligacao, ENTER)
    assert mapa.commands[indice].duration == pytest.approx(round(duracao, 3) + 0.01, abs=1e-6)
    assert [c.start for c in mapa.commands] == antes, "o tempo apertado não empurra os seguintes"
    assert mapa.validate() == []


# ================================================================================================ a ligação não importa o Qt
def test_o_modulo_nao_importa_o_qt():
    """Só `teclado_ui.py` tem Qt (ficha, T3-1): a ligação roda e é provada em qualquer lugar."""
    importados = set()
    for no in ast.walk(ast.parse(pathlib.Path(tl.__file__).read_text(encoding="utf-8"))):
        if isinstance(no, ast.Import):
            importados |= {alias.name.split(".")[0] for alias in no.names}
        elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
            importados.add(no.module.split(".")[0])
    assert not {"PySide6", "PyQt5", "PyQt6", "shiboken6"} & importados
