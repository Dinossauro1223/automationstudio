"""Varredura do controlador da edição pelo teclado: aperta teclas ao acaso e confere o que NUNCA pode acontecer.

A seção 6 de md/ESPEC_TECLADO_25_9.md prometeu, para o T2, uma "varredura de sequências aleatórias de teclas contra invariantes". Os testes de
test_teclado_edicao.py provam cada caso que alguém pensou; este prova o que vale para qualquer sequência, inclusive as que ninguém pensou.

Cada sequência parte de um comando dos três mapas reais (a linha é a ficha que a janela entregaria, `linha_info_de`) e mistura teclas que o
controlador usa, as que ele engole e as que deixa passar, setas soltas, "tiques" do relógio, o seletor de programa respondendo, o foco saindo
e a linha mudando, com instantes que só andam para a frente. A semente é fixa: a varredura é a mesma em toda máquina e uma falha diz a semente e
o passo. Depois de cada passo, o que se confere:

  * a resposta é bem formada e o estado, a linha e o valor em edição são coerentes entre si;
  * quem mexe no mapa (os efeitos `Aplicar...`) só aparece com o Enter, com a mesma tecla de novo na captura ou com a resposta do seletor, e
    sempre fecha a edição (`Desmarcar`) e volta a navegar; Esc nunca aplica;
  * o valor em edição nunca sai de [mínimo, máximo] e o que é aplicado tem a resolução de 1 ms;
  * **o que o controlador aplica ao mapa nunca o invalida**: o mapa continua sem erro novo de `validate()` e `set_gap_before` aceita a espera;
  * navegando, a tecla com Ctrl ou Alt volta inteira para a janela;
  * a varredura chega a todos os estados e produz todos os efeitos (senão ela seria mais fraca do que parece).
"""
from __future__ import annotations

import copy
import random

import pytest

from automationstudio.core import MOUSE_BUTTON_NAMES, InputType, map_from_json
from automationstudio.teclado_edicao import (TEMPO_MINIMO, TETO, AbrirAplicativo, AbrirBarraLateral, AbrirTexto, AplicarAlvo,
                                             AplicarEspera, AplicarTempo, AplicarTexto, Bip, Cancelar, Desmarcar, Dica, EdicaoPorTeclado,
                                             EditarCelula, Estado, FecharEditor, IniciarCaptura, Marcar, MostrarValor, ProporTecla,
                                             Resposta, Tecla, linha_info_de)

EFEITOS = (Marcar, Desmarcar, Cancelar, FecharEditor, IniciarCaptura, ProporTecla, Bip, AbrirTexto, AbrirAplicativo, AplicarAlvo,
           AplicarTexto, AplicarTempo, AplicarEspera, Dica, MostrarValor, AbrirBarraLateral, EditarCelula)
APLICAR = (AplicarAlvo, AplicarTexto, AplicarTempo, AplicarEspera)

# As teclas do sorteio: as que o controlador usa (com mais peso, para a sequência chegar fundo), as que ele engole e as que deixa passar.
ALFABETO = (
    [Tecla("ENTER")] * 8 + [Tecla("LEFT")] * 6 + [Tecla("RIGHT")] * 6 + [Tecla("ESC")] * 2 + [Tecla("", "'")] * 3
    + [Tecla("A"), Tecla("E"), Tecla("1"), Tecla("SPACE"), Tecla("F13"), Tecla("TAB"), Tecla("UP"), Tecla("DOWN"), Tecla("F2"),
       Tecla("SHIFT"), Tecla("CTRL"), Tecla("ALT"), Tecla(""), Tecla("", '"'),
       Tecla("ENTER", shift=True), Tecla("ESC", shift=True), Tecla("ESC", ctrl=True), Tecla("A", ctrl=True), Tecla("LEFT", ctrl=True),
       Tecla("ENTER", ctrl=True), Tecla("ENTER", alt=True), Tecla("", "'", ctrl=True), Tecla("LEFT", shift=True)])
TEXTOS = [None, None, "", " ", "olá", "outro texto"]
RESPOSTAS_DO_SELETOR = [None, "", "notepad.exe", "C:\\Programas\\Meu App\\app.exe"]
AVANCOS = [0.0, 0.0, 0.01, 0.05, 0.1, 0.3, 0.39, 0.4, 0.41, 1.0, 1.0, 5.0]
SEMENTES = 120
PASSOS = 70


class _Vistos:
    """O que a varredura já viu: os estados e os efeitos."""

    def __init__(self) -> None:
        self.estados: set[Estado] = set()
        self.efeitos: set[type] = set()


def _aplicar(mapa, efeito) -> None:
    """O que a janela faz com o efeito (T3), sem Qt: grava no mapa pelo mesmo caminho das edições de hoje."""
    comando = mapa.commands[efeito.linha]
    if isinstance(efeito, AplicarEspera):
        mapa.set_gap_before(efeito.linha, efeito.valor)  # o modelo aceita? se recusar, é falha do controlador
    elif isinstance(efeito, AplicarTempo):
        comando.duration = efeito.valor
    elif isinstance(efeito, AplicarAlvo):
        comando.target = efeito.valor
    else:
        comando.text = efeito.texto


def _limites(estado: Estado, ficha):
    """(mínimo, máximo) do ajuste, a partir da ficha de quando a edição abriu. O mínimo da espera é o piso EXATO do modelo (não é múltiplo de 1 ms)."""
    if estado == Estado.TEMPO:
        return TEMPO_MINIMO, max(TETO, ficha.tempo)
    return ficha.espera_minima, max(TETO, ficha.espera)


def _inicial(estado: Estado, ficha) -> float:
    return ficha.tempo if estado == Estado.TEMPO else ficha.espera


def _varrer(texto_do_mapa: str, sementes: range, vistos: _Vistos) -> None:
    original = map_from_json(texto_do_mapa)
    erros_base = set(original.validate())
    for semente in sementes:
        rng = random.Random(semente)
        mapa = copy.deepcopy(original)
        indice = rng.randrange(len(mapa.commands))
        c, agora = EdicaoPorTeclado(), 1000.0
        ficha = None  # a ficha da linha de quando a edição abriu
        for passo in range(PASSOS):
            onde = f"semente {semente}, passo {passo}"
            agora += rng.choice(AVANCOS)
            antes = c.estado
            sorteio = rng.random()
            tecla = None
            if sorteio < 0.70:
                tecla, texto = rng.choice(ALFABETO), rng.choice(TEXTOS)
                linha = linha_info_de(mapa, indice)
                resposta = c.pressionar(tecla, agora, linha, texto=texto)
                if antes == Estado.NAVEGANDO and c.estado != Estado.NAVEGANDO:
                    ficha = linha
            elif sorteio < 0.82:
                resposta = c.soltar(rng.choice(["LEFT", "RIGHT", "UP"]), agora)
            elif sorteio < 0.92:
                resposta = c.tique(agora)
            elif sorteio < 0.95:
                resposta = c.descartar()
                if rng.random() < 0.5:  # a linha mudou: a janela descarta e a seleção vai para outra
                    indice = rng.randrange(len(mapa.commands))
            else:
                resposta = c.conteudo_resolvido(rng.choice(RESPOSTAS_DO_SELETOR))
            depois = c.estado
            vistos.estados.add(depois)

            # ---- a resposta e o estado são coerentes
            assert isinstance(resposta, Resposta) and isinstance(resposta.efeitos, tuple), onde
            assert all(isinstance(e, EFEITOS) for e in resposta.efeitos), (onde, resposta.efeitos)
            vistos.efeitos.update(type(e) for e in resposta.efeitos)
            assert (c.linha is None) == (depois == Estado.NAVEGANDO), (onde, depois, c.linha)
            assert (c.valor is None) == (depois not in (Estado.TEMPO, Estado.ESPERA)), (onde, depois, c.valor)
            assert c.proposta == "" or depois == Estado.TECLA, (onde, depois, c.proposta)
            assert depois != Estado.BOTAO or c.botao in MOUSE_BUTTON_NAMES, (onde, c.botao)
            if tecla is not None and resposta.efeitos:
                assert resposta.consumida, (onde, tecla, resposta.efeitos)  # tecla que faz algo nunca volta para a janela
            tipos = [type(e) for e in resposta.efeitos]
            if Cancelar in tipos or Desmarcar in tipos:
                assert depois == Estado.NAVEGANDO, (onde, resposta.efeitos)
            if Marcar in tipos:
                assert antes == Estado.NAVEGANDO and tecla is not None, (onde, antes)
            if FecharEditor in tipos:
                assert depois in (Estado.TEMPO, Estado.TEXTO, Estado.TECLA, Estado.BOTAO) or depois == Estado.TEMPO, (onde, depois)

            # ---- navegando, o que tem Ctrl ou Alt é da janela
            if tecla is not None and antes == Estado.NAVEGANDO and (tecla.ctrl or tecla.alt):
                assert resposta == Resposta(False, ()), (onde, tecla)

            # ---- Esc simples nunca aplica
            if tecla is not None and tecla.nome == "ESC" and not (tecla.ctrl or tecla.shift or tecla.alt):
                assert not any(isinstance(e, APLICAR) for e in resposta.efeitos), onde
                if antes not in (Estado.NAVEGANDO, Estado.APLICATIVO):
                    assert tipos == [Cancelar] and depois == Estado.NAVEGANDO, (onde, resposta.efeitos)

            # ---- o valor em edição respeita os limites da ficha de quando abriu
            if depois in (Estado.TEMPO, Estado.ESPERA):
                minimo, maximo = _limites(depois, ficha)
                inicial = _inicial(depois, ficha)  # um valor de hoje fora dos limites (duração 0 de um mapa antigo) continua valendo até mudar
                assert min(minimo, inicial) - 1e-9 <= c.valor <= max(maximo, inicial) + 1e-9, (onde, depois, c.valor, minimo, maximo)

            # ---- o que se aplica: quando, com que valor e o que o mapa diz depois
            aplicados = [e for e in resposta.efeitos if isinstance(e, APLICAR)]
            for efeito in aplicados:
                assert resposta.efeitos[-1] == Desmarcar() and depois == Estado.NAVEGANDO, (onde, resposta.efeitos)
                assert efeito.linha == ficha.indice, (onde, efeito, ficha.indice)
                if tecla is None:
                    assert isinstance(efeito, AplicarAlvo) and antes == Estado.APLICATIVO, (onde, efeito, antes)  # a resposta do seletor
                elif isinstance(efeito, (AplicarTempo, AplicarEspera, AplicarTexto)):
                    assert tecla == Tecla("ENTER") and antes in (Estado.TEMPO, Estado.ESPERA, Estado.TEXTO), (onde, tecla, antes)
                else:  # a tecla ou o botão: a mesma tecla de novo na captura, ou o Enter no botão
                    assert antes in (Estado.TECLA, Estado.BOTAO), (onde, antes)
                    assert antes == Estado.TECLA or tecla == Tecla("ENTER"), (onde, tecla)
                if isinstance(efeito, (AplicarTempo, AplicarEspera)):
                    minimo, maximo = _limites(antes, ficha)
                    assert minimo - 1e-9 <= efeito.valor <= maximo + 1e-9, (onde, efeito, minimo, maximo)
                    # a resolução é de 1 ms, menos nas duas pontas: o piso do modelo e o teto são valores exatos, que o ajuste alcança sem arredondar
                    assert efeito.valor == round(efeito.valor, 3) or efeito.valor in (minimo, maximo), (onde, efeito, minimo, maximo)
                if isinstance(efeito, AplicarTempo):
                    assert ficha.tempo_editavel and efeito.valor >= TEMPO_MINIMO, (onde, efeito, ficha)
                if isinstance(efeito, AplicarTexto):
                    assert efeito.texto != "" and ficha.tipo == InputType.TEXT, (onde, efeito)
                _aplicar(mapa, efeito)
                assert set(mapa.validate()) <= erros_base, (onde, efeito, set(mapa.validate()) - erros_base)
                assert all(float(cmd.start) >= -1e-9 for cmd in mapa.commands), (onde, efeito)  # nenhum início cortado no zero


@pytest.mark.parametrize("nome", ["Click genshin", "Exemplo — Primeira automação", "Flins combo"], ids=["click_genshin", "exemplo", "flins_combo"])
def test_varredura_nos_mapas_reais(legacy_maps, nome):
    _varrer(legacy_maps[nome], range(SEMENTES if nome != "Flins combo" else SEMENTES // 3), _Vistos())


def test_a_varredura_chega_a_todos_os_estados_e_produz_todos_os_efeitos(legacy_maps):
    vistos = _Vistos()
    for nome in ("Click genshin", "Exemplo — Primeira automação", "Flins combo"):
        _varrer(legacy_maps[nome], range(SEMENTES // 2), vistos)
    assert vistos.estados == set(Estado), set(Estado) - vistos.estados
    assert vistos.efeitos == set(EFEITOS), set(EFEITOS) - vistos.efeitos
