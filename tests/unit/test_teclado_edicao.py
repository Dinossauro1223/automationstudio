"""O controlador de edição pelo teclado (automationstudio/teclado_edicao.py): teclas abstratas entram, efeitos saem.

Lógica pura, sem Qt e sem relógio: o instante de cada tecla é um número que o teste entrega (`agora`). Especificação:
md/ESPEC_TECLADO_25_9.md (TEC-01 a TEC-16, decisões D1 a D16) e md/FICHA_TECLADO_T2_25_9.md (decisões T2-1 a T2-13).
Quem liga isto à tabela e ao Qt é o T3; aqui se prova só o que o controlador decide.

O desenho em uma frase: no estado NAVEGANDO só as teclas do atalho são "consumidas"; as outras voltam para a janela (setas,
letras, Ctrl+C...). Dentro de uma edição o controlador manda: ele consome o que usa e, nos ajustes de valor, engole o resto
(menos Ctrl e Alt) para a tabela não abrir um editor de célula por engano.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from automationstudio import teclado_edicao as te
from automationstudio.core import ActionType, AutomationMap, Command, InputType, map_from_json
from automationstudio.teclado_edicao import (JANELA_ENTER_DUPLO, LIMITE_TOQUE, ROTULOS, TECLAS_DO_ESTADO, TEMPO_MINIMO, TETO,
                                             AbrirAplicativo, AbrirBarraLateral, AbrirTexto, AplicarAlvo, AplicarEspera,
                                             AplicarTempo, AplicarTexto, Bip, Cancelar, Desmarcar, Dica, EdicaoPorTeclado,
                                             EditarCelula, Estado, FecharEditor, IniciarCaptura, LinhaInfo, Marcar,
                                             MostrarValor, ProporTecla, Resposta, Tecla, chave_da_tecla, dica_do_estado,
                                             formatar_segundos, linha_info_de, mudanca_acumulada, valor_apos)

T0 = 100.0
ENTER, ESC = Tecla("ENTER"), Tecla("ESC")
ESQUERDA, DIREITA, CIMA, BAIXO = Tecla("LEFT"), Tecla("RIGHT"), Tecla("UP"), Tecla("DOWN")
APOSTROFO = Tecla("", "'")


def _info(**mudancas):
    """Um comando de tecla "apertar e soltar" na linha 2 (a configuração mais comum); `mudancas` troca campos."""
    campos = dict(indice=2, tipo=InputType.KEY, acao=ActionType.PRESS_AND_RELEASE, alvo="E", texto="", tempo=0.1,
                  tempo_editavel=True, tempo_motivo="", espera=0.5, espera_minima=-1.0)
    campos.update(mudancas)
    return LinhaInfo(**campos)


def _texto_info(**mudancas):
    campos = dict(tipo=InputType.TEXT, alvo="", texto="olá", tempo=0.0, tempo_editavel=False, tempo_motivo="o tempo do texto é calculado")
    campos.update(mudancas)
    return _info(**campos)


def _app_info(**mudancas):
    campos = dict(tipo=InputType.APP_OPEN, alvo="notepad.exe", tempo=0.0, tempo_editavel=False, tempo_motivo="o programa define")
    campos.update(mudancas)
    return _info(**campos)


def _botao_info(**mudancas):
    campos = dict(tipo=InputType.MOUSE_BUTTON, alvo="left")
    campos.update(mudancas)
    return _info(**campos)


def _tipos(resposta):
    return [type(e) for e in resposta.efeitos]


def _efeito(resposta, classe):
    achados = [e for e in resposta.efeitos if isinstance(e, classe)]
    assert len(achados) == 1, f"esperava um {classe.__name__} em {resposta.efeitos}"
    return achados[0]


# Controladores já dentro de cada estado, levados até lá pelas teclas de verdade (nada de mexer em atributos internos).
def _em_tecla(linha=None, t=T0):
    c, linha = EdicaoPorTeclado(), linha or _info()
    c.pressionar(ENTER, t, linha)
    assert c.estado == Estado.TECLA
    return c


def _em_texto(linha=None, t=T0):
    c, linha = EdicaoPorTeclado(), linha or _texto_info()
    c.pressionar(ENTER, t, linha)
    assert c.estado == Estado.TEXTO
    return c


def _em_aplicativo(linha=None, t=T0):
    c, linha = EdicaoPorTeclado(), linha or _app_info()
    c.pressionar(ENTER, t, linha)
    assert c.estado == Estado.APLICATIVO
    return c


def _em_botao(linha=None, t=T0):
    c, linha = EdicaoPorTeclado(), linha or _botao_info()
    c.pressionar(ENTER, t, linha)
    assert c.estado == Estado.BOTAO
    return c


def _em_tempo(linha=None, t=T0):
    c, linha = EdicaoPorTeclado(), linha or _info()
    c.pressionar(ENTER, t, linha)
    c.pressionar(ENTER, t + 0.2, linha)
    assert c.estado == Estado.TEMPO
    return c


def _em_espera(linha=None, t=T0):
    c, linha = EdicaoPorTeclado(), linha or _info()
    c.pressionar(APOSTROFO, t, linha)
    assert c.estado == Estado.ESPERA
    return c


def _em(estado, linha=None):
    if estado == Estado.NAVEGANDO:
        return EdicaoPorTeclado()
    return {Estado.TECLA: _em_tecla, Estado.TEXTO: _em_texto, Estado.APLICATIVO: _em_aplicativo, Estado.BOTAO: _em_botao,
            Estado.TEMPO: _em_tempo, Estado.ESPERA: _em_espera}[estado](linha)


def _linha_do_estado(estado):
    return {Estado.TEXTO: _texto_info(), Estado.APLICATIVO: _app_info(), Estado.BOTAO: _botao_info()}.get(estado, _info())


# ================================================================================================ navegando
def test_comecar_parado_sem_nada_marcado():
    c = EdicaoPorTeclado()
    assert c.estado == Estado.NAVEGANDO and c.linha is None and c.proposta == ""


def test_sem_comando_o_enter_volta_para_a_janela():
    r = EdicaoPorTeclado().pressionar(ENTER, T0, None)
    assert r == Resposta(False, ())


def test_enter_numa_tecla_marca_a_linha_e_abre_a_captura():
    c = EdicaoPorTeclado()
    r = c.pressionar(ENTER, T0, _info())
    assert r.consumida and _tipos(r) == [Marcar, IniciarCaptura, Dica]
    assert _efeito(r, Marcar).linha == 2
    assert (_efeito(r, IniciarCaptura).linha, _efeito(r, IniciarCaptura).atual) == (2, "E")
    assert _efeito(r, Dica).texto == dica_do_estado(Estado.TECLA, _info())
    assert c.estado == Estado.TECLA and c.linha == 2


def test_enter_num_texto_abre_o_editor_com_o_texto_de_hoje():
    c = EdicaoPorTeclado()
    r = c.pressionar(ENTER, T0, _texto_info(texto="olá mundo"))
    assert r.consumida and _tipos(r) == [Marcar, AbrirTexto, Dica]
    assert (_efeito(r, AbrirTexto).linha, _efeito(r, AbrirTexto).atual) == (2, "olá mundo")
    assert c.estado == Estado.TEXTO


def test_enter_num_aplicativo_abre_o_seletor_com_o_programa_de_hoje():
    c = EdicaoPorTeclado()
    r = c.pressionar(ENTER, T0, _app_info(alvo="calc.exe"))
    assert r.consumida and _tipos(r) == [Marcar, AbrirAplicativo, Dica]
    assert (_efeito(r, AbrirAplicativo).linha, _efeito(r, AbrirAplicativo).atual) == (2, "calc.exe")
    assert c.estado == Estado.APLICATIVO


def test_enter_num_botao_do_mouse_comeca_no_botao_de_hoje():
    c = EdicaoPorTeclado()
    r = c.pressionar(ENTER, T0, _botao_info(alvo="Right"))  # o modelo aceita "Right" (a comparação é em minúsculas)
    assert r.consumida and _tipos(r) == [Marcar, MostrarValor, Dica]
    assert "direito" in _efeito(r, MostrarValor).texto.lower()
    assert c.estado == Estado.BOTAO and c.botao == "right"


def test_botao_com_nome_que_o_modelo_nao_conhece_comeca_no_esquerdo():
    c = EdicaoPorTeclado()
    c.pressionar(ENTER, T0, _botao_info(alvo="botao-inexistente"))
    assert c.estado == Estado.BOTAO and c.botao == "left"


@pytest.mark.parametrize("tipo", [InputType.MOUSE_MOVE, InputType.MOUSE_SCROLL, InputType.WAIT],
                         ids=["mover", "rolar", "esperar"])
def test_enter_nos_comandos_sem_conteudo_simples_nao_marca_e_manda_para_a_barra_lateral(tipo):
    c = EdicaoPorTeclado()
    r = c.pressionar(ENTER, T0, _info(tipo=tipo, alvo="", tempo_editavel=False, tempo_motivo="x"))
    assert r.consumida and _tipos(r) == [Dica]
    assert "Shift+Enter" in _efeito(r, Dica).texto
    assert c.estado == Estado.NAVEGANDO and c.linha is None


def test_shift_enter_abre_a_barra_lateral_da_linha():
    c = EdicaoPorTeclado()
    r = c.pressionar(Tecla("ENTER", shift=True), T0, _info(indice=7))
    assert r.consumida and r.efeitos == (AbrirBarraLateral(7),)
    assert c.estado == Estado.NAVEGANDO


def test_f2_edita_a_celula_da_linha():
    r = EdicaoPorTeclado().pressionar(Tecla("F2"), T0, _info(indice=4))
    assert r.consumida and r.efeitos == (EditarCelula(4),)


@pytest.mark.parametrize("tecla", [Tecla("ENTER", shift=True), Tecla("F2"), APOSTROFO])
def test_sem_comando_nenhum_atalho_da_navegacao_e_consumido(tecla):
    assert EdicaoPorTeclado().pressionar(tecla, T0, None) == Resposta(False, ())


def test_o_apostrofo_abre_a_espera_com_o_valor_de_hoje():
    c = EdicaoPorTeclado()
    r = c.pressionar(APOSTROFO, T0, _info(espera=0.5))
    assert r.consumida and _tipos(r) == [Marcar, MostrarValor, Dica]
    assert c.estado == Estado.ESPERA and c.linha == 2 and c.valor == 0.5
    assert "0,5" in _efeito(r, MostrarValor).texto


def test_a_espera_do_primeiro_comando_se_chama_inicio():
    r = EdicaoPorTeclado().pressionar(APOSTROFO, T0, _info(indice=0, espera=0.7, espera_minima=0.0))
    assert "Começa em" in _efeito(r, MostrarValor).texto and "0,7" in _efeito(r, MostrarValor).texto


def test_a_espera_negativa_diz_quanto_comeca_antes_do_fim_do_anterior():
    r = EdicaoPorTeclado().pressionar(APOSTROFO, T0, _info(espera=-0.6))
    texto = _efeito(r, MostrarValor).texto
    assert "-0,6" in texto and "começa 0,6 s antes do fim do anterior" in texto


def test_o_apostrofo_vale_pelo_caractere_digitado_e_nao_pela_posicao_da_tecla():
    # Em ABNT2 o apóstrofo é a tecla à esquerda do 1; em teclado americano, a da direita do ponto e vírgula (D3).
    for nome in ("", "QUOTE", "BACKQUOTE", "APOSTROPHE"):
        assert EdicaoPorTeclado().pressionar(Tecla(nome, "'"), T0, _info()).consumida, nome


def test_o_apostrofo_com_shift_continua_sendo_o_caractere_apostrofo():
    assert EdicaoPorTeclado().pressionar(Tecla("", "'", shift=True), T0, _info()).consumida


@pytest.mark.parametrize("texto", ['"', "`", "´", "’", ",", ";"], ids=["aspas", "crase", "agudo", "tipografico", "virgula", "ponto-virgula"])
def test_os_outros_sinais_nao_abrem_a_espera(texto):
    assert EdicaoPorTeclado().pressionar(Tecla("", texto), T0, _info()) == Resposta(False, ())


@pytest.mark.parametrize("tecla", [Tecla("ENTER", ctrl=True), Tecla("ENTER", alt=True), Tecla("F2", ctrl=True), Tecla("F2", shift=True),
                                   Tecla("", "'", ctrl=True), Tecla("", "'", alt=True), Tecla("ENTER", ctrl=True, shift=True)],
                         ids=["ctrl-enter", "alt-enter", "ctrl-f2", "shift-f2", "ctrl-apostrofo", "alt-apostrofo", "ctrl-shift-enter"])
def test_os_atalhos_da_navegacao_com_ctrl_ou_alt_voltam_para_a_janela(tecla):
    c = EdicaoPorTeclado()
    assert c.pressionar(tecla, T0, _info()) == Resposta(False, ())
    assert c.estado == Estado.NAVEGANDO


@pytest.mark.parametrize("tecla", [Tecla("LEFT"), Tecla("DOWN"), Tecla("TAB"), Tecla("DELETE"), Tecla("A"), Tecla("SPACE"), Tecla("ESC"),
                                   Tecla("C", ctrl=True), Tecla("Z", ctrl=True), Tecla("HOME"), Tecla("F5"), Tecla("1")],
                         ids=["esquerda", "baixo", "tab", "delete", "a", "espaco", "esc", "ctrl-c", "ctrl-z", "home", "f5", "um"])
def test_o_que_a_navegacao_nao_usa_volta_para_a_janela_sem_efeito(tecla):
    c = EdicaoPorTeclado()
    assert c.pressionar(tecla, T0, _info()) == Resposta(False, ())
    assert c.estado == Estado.NAVEGANDO and c.linha is None


# ================================================================================================ captura de tecla
def test_a_primeira_tecla_vira_proposta_com_bip_e_a_edicao_continua():
    c = _em_tecla()
    r = c.pressionar(Tecla("F"), T0 + 1.0, _info())
    assert r.consumida and _tipos(r) == [ProporTecla, Bip, Dica]
    assert _efeito(r, ProporTecla).nome == "F" and c.proposta == "F" and c.estado == Estado.TECLA
    assert "F" in _efeito(r, Dica).texto and "de novo" in _efeito(r, Dica).texto
    assert _efeito(r, Dica).texto == dica_do_estado(Estado.TECLA, _info(), proposta="F")


def test_a_mesma_tecla_de_novo_confirma_aplica_e_desmarca():
    c = _em_tecla()
    c.pressionar(Tecla("F"), T0 + 1.0, _info())
    r = c.pressionar(Tecla("F"), T0 + 1.5, _info())
    assert r.consumida and r.efeitos == (AplicarAlvo(2, "F"), Desmarcar())
    assert c.estado == Estado.NAVEGANDO and c.proposta == "" and c.linha is None


def test_outra_tecla_troca_a_proposta_e_a_confirmacao_passa_a_ser_dela():
    c = _em_tecla()
    c.pressionar(Tecla("F"), T0 + 1.0, _info())
    r = c.pressionar(Tecla("G"), T0 + 1.5, _info())
    assert _tipos(r) == [ProporTecla, Bip, Dica] and c.proposta == "G" and c.estado == Estado.TECLA
    assert c.pressionar(Tecla("F"), T0 + 2.0, _info()).efeitos[0] == ProporTecla("F")  # F não é mais a proposta
    assert c.pressionar(Tecla("F"), T0 + 2.5, _info()).efeitos == (AplicarAlvo(2, "F"), Desmarcar())


def test_a_confirmacao_ignora_ctrl_shift_e_alt():
    c = _em_tecla()
    c.pressionar(Tecla("F", ctrl=True), T0 + 1.0, _info())
    assert c.proposta == "F"
    assert c.pressionar(Tecla("F", shift=True), T0 + 1.5, _info()).efeitos == (AplicarAlvo(2, "F"), Desmarcar())


def test_confirmar_a_tecla_que_o_comando_ja_tem_nao_grava_nada():
    c = _em_tecla(_info(alvo="E"))
    c.pressionar(Tecla("E"), T0 + 1.0, _info(alvo="E"))
    r = c.pressionar(Tecla("E"), T0 + 1.5, _info(alvo="E"))
    assert r.efeitos == (Desmarcar(),) and c.estado == Estado.NAVEGANDO


def test_teclas_especiais_tambem_podem_ser_o_alvo():
    c = _em_tecla()
    for nome in ("SPACE", "SHIFT", "F13", "LEFT", "TAB", "BACKSPACE"):
        c.pressionar(Tecla(nome), T0 + 1.0, _info())
        assert c.proposta == nome
        c.pressionar(Tecla(nome), T0 + 1.2, _info())
        assert c.estado == Estado.NAVEGANDO
        c = _em_tecla()


def test_esc_cancela_a_captura_sem_aplicar():
    c = _em_tecla()
    r = c.pressionar(ESC, T0 + 1.0, _info())
    assert r.consumida and r.efeitos == (Cancelar(),) and c.estado == Estado.NAVEGANDO


def test_esc_cancela_tambem_com_uma_proposta_pendente():
    c = _em_tecla()
    c.pressionar(Tecla("F"), T0 + 1.0, _info())
    assert c.pressionar(ESC, T0 + 1.5, _info()).efeitos == (Cancelar(),)
    assert c.estado == Estado.NAVEGANDO and c.proposta == ""


def test_na_captura_todas_as_teclas_com_nome_sao_consumidas():
    for tecla in (Tecla("A"), Tecla("C", ctrl=True), Tecla("F4", alt=True), Tecla("TAB"), Tecla("DELETE"), Tecla("1", shift=True),
                  Tecla("S", ctrl=True), Tecla("UP"), Tecla("F5")):
        assert _em_tecla().pressionar(tecla, T0 + 1.0, _info()).consumida, tecla


def test_tecla_sem_nome_nao_vira_proposta_e_diz_porque():
    c = _em_tecla()
    r = c.pressionar(Tecla("", ";"), T0 + 1.0, _info())
    assert r.consumida and _tipos(r) == [Dica] and c.proposta == "" and c.estado == Estado.TECLA


def test_o_enter_duplo_na_captura_abre_o_tempo_apertado():
    linha = _info(tempo=0.25)
    c = _em_tecla(linha)  # a edição usa a ficha de quando ela abriu (a `linha` das teclas seguintes só é lida em NAVEGANDO)
    r = c.pressionar(ENTER, T0 + 0.2, None)
    assert r.consumida and _tipos(r) == [FecharEditor, MostrarValor, Dica]
    assert c.estado == Estado.TEMPO and c.valor == 0.25 and c.linha == 2
    assert _efeito(r, Dica).texto == dica_do_estado(Estado.TEMPO, linha)
    assert "0,25" in _efeito(r, MostrarValor).texto


def test_a_janela_do_enter_duplo_vai_ate_0_4_segundo_inclusive():
    assert JANELA_ENTER_DUPLO == 0.4
    c = _em_tecla(t=T0)
    c.pressionar(ENTER, T0 + JANELA_ENTER_DUPLO, _info())
    assert c.estado == Estado.TEMPO  # no limite exato ainda é o duplo


def test_depois_da_janela_o_enter_e_a_tecla_enter_proposta():
    c = _em_tecla(t=T0)
    r = c.pressionar(ENTER, T0 + JANELA_ENTER_DUPLO + 1e-6, _info())
    assert _tipos(r) == [ProporTecla, Bip, Dica] and c.proposta == "ENTER" and c.estado == Estado.TECLA


def test_enter_depois_de_outra_tecla_nunca_e_duplo():
    c = _em_tecla(t=T0)
    c.pressionar(Tecla("A"), T0 + 0.1, _info())
    r = c.pressionar(ENTER, T0 + 0.2, _info())
    assert c.proposta == "ENTER" and c.estado == Estado.TECLA and ProporTecla("ENTER") in r.efeitos


def test_o_enter_duplo_precisa_de_enter_sem_modificadores():
    c = _em_tecla(t=T0)
    c.pressionar(Tecla("ENTER", shift=True), T0 + 0.2, _info())
    assert c.estado == Estado.TECLA and c.proposta == "ENTER"


def test_o_enter_duplo_numa_tecla_sem_tempo_apertado_explica_e_continua_na_captura():
    linha = _info(acao=ActionType.PRESS, tempo_editavel=False, tempo_motivo="este comando só aperta a tecla")
    c = _em_tecla(linha, t=T0)
    r = c.pressionar(ENTER, T0 + 0.2, linha)
    assert r.consumida and _tipos(r) == [Dica] and "só aperta a tecla" in _efeito(r, Dica).texto
    assert c.estado == Estado.TECLA and c.proposta == ""


def test_a_dica_da_captura_so_oferece_o_enter_duplo_quando_o_tempo_pode_ser_editado():
    assert "Enter, Enter" in dica_do_estado(Estado.TECLA, _info(tempo_editavel=True))
    assert "Enter, Enter" not in dica_do_estado(Estado.TECLA, _info(tempo_editavel=False, tempo_motivo="x"))


# ================================================================================================ editor de texto
def test_enter_depois_da_janela_confirma_o_texto_digitado():
    c = _em_texto(_texto_info(texto="olá"), t=T0)
    r = c.pressionar(ENTER, T0 + 2.0, _texto_info(texto="olá"), texto="olá mundo")
    assert r.consumida and r.efeitos == (AplicarTexto(2, "olá mundo"), Desmarcar())
    assert c.estado == Estado.NAVEGANDO and c.linha is None


def test_texto_igual_ao_de_hoje_so_desmarca():
    c = _em_texto(_texto_info(texto="olá"), t=T0)
    assert c.pressionar(ENTER, T0 + 2.0, _texto_info(texto="olá"), texto="olá").efeitos == (Desmarcar(),)


@pytest.mark.parametrize("texto", ["", None], ids=["vazio", "desconhecido"])
def test_texto_vazio_nao_e_aplicado_e_a_edicao_continua(texto):
    c = _em_texto(t=T0)
    r = c.pressionar(ENTER, T0 + 2.0, _texto_info(), texto=texto)
    assert r.consumida and _tipos(r) == [Dica] and "vazio" in _efeito(r, Dica).texto
    assert c.estado == Estado.TEXTO


def test_um_espaco_e_um_texto_valido():
    c = _em_texto(t=T0)
    assert c.pressionar(ENTER, T0 + 2.0, _texto_info(), texto=" ").efeitos == (AplicarTexto(2, " "), Desmarcar())


def test_esc_cancela_o_texto_sem_aplicar():
    c = _em_texto()
    r = c.pressionar(ESC, T0 + 1.0, _texto_info(), texto="qualquer coisa")
    assert r.consumida and r.efeitos == (Cancelar(),) and c.estado == Estado.NAVEGANDO


@pytest.mark.parametrize("tecla", [Tecla("A"), Tecla("SPACE"), Tecla("BACKSPACE"), Tecla("LEFT"), Tecla("DELETE"), Tecla("A", ctrl=True),
                                   Tecla("Z", ctrl=True), Tecla("HOME"), Tecla("1", shift=True), Tecla("ENTER", shift=True),
                                   Tecla("ENTER", ctrl=True), APOSTROFO, Tecla("TAB"), Tecla("F2")])
def test_o_que_se_digita_no_texto_volta_para_o_editor(tecla):
    c = _em_texto()
    assert c.pressionar(tecla, T0 + 1.0, _texto_info(), texto="x") == Resposta(False, ())
    assert c.estado == Estado.TEXTO


def test_o_apostrofo_digitado_no_texto_nao_abre_a_espera():
    c = _em_texto()
    c.pressionar(APOSTROFO, T0 + 1.0, _texto_info(), texto="x'")
    assert c.estado == Estado.TEXTO


def test_enter_logo_depois_de_digitar_confirma_e_nao_e_duplo():
    c = _em_texto(t=T0)
    c.pressionar(Tecla("A"), T0 + 0.1, _texto_info(), texto="a")
    r = c.pressionar(ENTER, T0 + 0.2, _texto_info(), texto="a")  # dentro de 0,4 s, mas houve uma tecla no meio
    assert r.efeitos == (AplicarTexto(2, "a"), Desmarcar())


def test_o_enter_duplo_num_texto_explica_que_o_tempo_e_calculado_e_nao_confirma():
    c = _em_texto(t=T0)
    r = c.pressionar(ENTER, T0 + 0.2, _texto_info(), texto="olá")
    assert r.consumida and _tipos(r) == [Dica] and "calculado" in _efeito(r, Dica).texto
    assert c.estado == Estado.TEXTO
    assert c.pressionar(ENTER, T0 + 1.0, _texto_info(), texto="novo").efeitos == (AplicarTexto(2, "novo"), Desmarcar())


# ================================================================================================ seletor de aplicativo
@pytest.mark.parametrize("tecla", [ENTER, ESC, Tecla("A"), ESQUERDA, Tecla("F2"), APOSTROFO, Tecla("C", ctrl=True)])
def test_com_o_seletor_aberto_as_teclas_sao_dele(tecla):
    c = _em_aplicativo()
    assert c.pressionar(tecla, T0 + 0.1, _app_info()) == Resposta(False, ())
    assert c.estado == Estado.APLICATIVO


def test_o_programa_escolhido_e_aplicado_e_a_linha_desmarcada():
    c = _em_aplicativo()
    r = c.conteudo_resolvido(r"C:\Windows\notepad.exe")
    assert r.efeitos == (AplicarAlvo(2, r"C:\Windows\notepad.exe"), Desmarcar())
    assert c.estado == Estado.NAVEGANDO and c.linha is None


@pytest.mark.parametrize("escolha", [None, "", "   ", '""'], ids=["cancelou", "vazio", "so-espacos", "so-aspas"])
def test_sem_programa_escolhido_a_edicao_e_cancelada(escolha):
    c = _em_aplicativo()
    assert c.conteudo_resolvido(escolha).efeitos == (Cancelar(),)
    assert c.estado == Estado.NAVEGANDO


def test_escolher_o_mesmo_programa_nao_grava_nada():
    c = _em_aplicativo(_app_info(alvo="notepad.exe"))
    assert c.conteudo_resolvido("notepad.exe").efeitos == (Desmarcar(),)


@pytest.mark.parametrize("estado", [Estado.NAVEGANDO, Estado.TECLA, Estado.TEXTO, Estado.BOTAO, Estado.TEMPO, Estado.ESPERA])
def test_uma_resposta_atrasada_do_seletor_fora_do_estado_nao_faz_nada(estado):
    c = _em(estado, _linha_do_estado(estado))
    assert c.conteudo_resolvido("x.exe") == Resposta(False, ()) and c.estado == estado


# ================================================================================================ botão do mouse
def test_as_setas_percorrem_os_botoes_do_modelo_e_param_nas_pontas():
    c = _em_botao(_botao_info(alvo="left"))
    vistos = []
    for _ in range(6):
        c.pressionar(DIREITA, T0 + 1.0, _botao_info())
        vistos.append(c.botao)
    assert vistos == ["right", "middle", "x1", "x2", "x2", "x2"]
    for esperado in ["x1", "middle", "right", "left", "left"]:
        c.pressionar(ESQUERDA, T0 + 2.0, _botao_info())
        assert c.botao == esperado


def test_cada_troca_de_botao_mostra_o_botao():
    c = _em_botao()
    r = c.pressionar(DIREITA, T0 + 1.0, _botao_info())
    assert r.consumida and _tipos(r) == [MostrarValor] and "direito" in _efeito(r, MostrarValor).texto.lower()


def test_enter_confirma_o_botao_escolhido():
    c = _em_botao(_botao_info(alvo="left"))
    c.pressionar(DIREITA, T0 + 1.0, _botao_info())
    r = c.pressionar(ENTER, T0 + 2.0, _botao_info())
    assert r.efeitos == (AplicarAlvo(2, "right"), Desmarcar()) and c.estado == Estado.NAVEGANDO


def test_enter_no_mesmo_botao_so_desmarca():
    c = _em_botao(_botao_info(alvo="Left"))
    assert c.pressionar(ENTER, T0 + 2.0, _botao_info()).efeitos == (Desmarcar(),)


def test_esc_cancela_a_troca_de_botao():
    c = _em_botao()
    c.pressionar(DIREITA, T0 + 1.0, _botao_info())
    assert c.pressionar(ESC, T0 + 2.0, _botao_info()).efeitos == (Cancelar(),)
    assert c.estado == Estado.NAVEGANDO


def test_o_enter_duplo_no_botao_abre_o_tempo_apertado():
    c = _em_botao(_botao_info(tempo=0.12), t=T0)
    r = c.pressionar(ENTER, T0 + 0.2, None)
    assert _tipos(r) == [FecharEditor, MostrarValor, Dica] and c.estado == Estado.TEMPO and c.valor == 0.12


def test_enter_depois_de_trocar_o_botao_nunca_e_duplo():
    c = _em_botao(t=T0)
    c.pressionar(DIREITA, T0 + 0.1, _botao_info())
    assert c.pressionar(ENTER, T0 + 0.2, _botao_info()).efeitos == (AplicarAlvo(2, "right"), Desmarcar())


def test_no_botao_o_resto_e_engolido_menos_ctrl_e_alt():
    c = _em_botao()
    for tecla in (CIMA, BAIXO, Tecla("A"), Tecla("TAB"), Tecla("F2"), APOSTROFO, Tecla("SPACE")):
        assert c.pressionar(tecla, T0 + 1.0, _botao_info()) == Resposta(True, ()), tecla
    for tecla in (Tecla("Z", ctrl=True), Tecla("S", ctrl=True), Tecla("F4", alt=True)):
        assert c.pressionar(tecla, T0 + 1.0, _botao_info()) == Resposta(False, ()), tecla
    assert c.estado == Estado.BOTAO


# ================================================================================================ tempo apertado e espera: a seta
@pytest.mark.parametrize("fabrica,campo", [(_em_tempo, "tempo"), (_em_espera, "espera")], ids=["tempo", "espera"])
def test_ao_abrir_o_valor_e_o_de_hoje(fabrica, campo):
    c = fabrica(_info(tempo=0.35, espera=-0.4))
    assert c.valor == (0.35 if campo == "tempo" else -0.4)


@pytest.mark.parametrize("fabrica", [_em_tempo, _em_espera], ids=["tempo", "espera"])
def test_um_toque_muda_um_passo_na_hora_e_so_vale_no_enter(fabrica):
    c = fabrica(_info(tempo=0.5, espera=0.5))
    r = c.pressionar(ESQUERDA, T0 + 5.0, _info())
    assert r.consumida and _tipos(r) == [MostrarValor] and c.valor == 0.49
    c.soltar("LEFT", T0 + 5.1)
    c.pressionar(DIREITA, T0 + 6.0, _info())
    c.soltar("RIGHT", T0 + 6.1)
    c.pressionar(DIREITA, T0 + 7.0, _info())
    c.soltar("RIGHT", T0 + 7.1)
    assert c.valor == 0.51


@pytest.mark.parametrize("segundos", [1.0, 3.0, 5.0, 9.0, 15.0, 30.0])
def test_segurar_a_seta_aplica_a_curva_ao_soltar(segundos):
    c = _em_tempo(_info(tempo=1000.0))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    c.soltar("LEFT", T0 + 5.0 + segundos)
    assert c.valor == valor_apos(1000.0, -1, segundos, TEMPO_MINIMO)
    assert c.valor == pytest.approx(1000.0 - mudanca_acumulada(segundos), abs=5e-4)


def test_os_tiques_levam_ao_mesmo_valor_que_soltar_de_uma_vez():
    c = _em_tempo(_info(tempo=1000.0))
    c.pressionar(DIREITA, T0 + 5.0, _info())
    for passo in range(1, 301):  # 10 s a 30 tiques por segundo
        c.tique(T0 + 5.0 + passo / 30)
    assert c.valor == valor_apos(1000.0, +1, 10.0, TEMPO_MINIMO)  # antes mesmo de soltar
    c.soltar("RIGHT", T0 + 15.0)
    assert c.valor == valor_apos(1000.0, +1, 10.0, TEMPO_MINIMO)


def test_os_tiques_so_dizem_o_valor_quando_ele_muda():
    c = _em_tempo(_info(tempo=1000.0))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    r = c.tique(T0 + 5.0 + LIMITE_TOQUE / 2)  # ainda no toque: nada mudou
    assert r.efeitos == ()
    r = c.tique(T0 + 5.0 + 1.0)
    assert _tipos(r) == [MostrarValor] and c.valor == valor_apos(1000.0, -1, 1.0, TEMPO_MINIMO)
    assert c.tique(T0 + 5.0 + 1.0).efeitos == ()  # o mesmo instante de novo: igual, nada a dizer


def test_a_repeticao_do_sistema_da_mesma_seta_e_ignorada():
    c = _em_tempo(_info(tempo=1000.0))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    antes = c.valor
    r = c.pressionar(ESQUERDA, T0 + 5.5, _info())  # o Qt repete a tecla enquanto ela está apertada
    assert r == Resposta(True, ()) and c.valor == antes
    c.soltar("LEFT", T0 + 6.0)
    assert c.valor == valor_apos(1000.0, -1, 1.0, TEMPO_MINIMO)  # a contagem continua a do primeiro aperto


def test_apertar_a_outra_seta_troca_a_direcao_e_zera_a_contagem():
    c = _em_tempo(_info(tempo=1000.0))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    c.tique(T0 + 7.0)  # 2 s segurando: 1000 - 0,18
    depois_de_esquerda = c.valor
    assert depois_de_esquerda == valor_apos(1000.0, -1, 2.0, TEMPO_MINIMO)
    c.pressionar(DIREITA, T0 + 7.0, _info())  # troca: toque de +0,01 sobre o que já tinha
    assert c.valor == round(depois_de_esquerda + 0.01, 3)
    c.soltar("RIGHT", T0 + 8.0)  # 1 s segurando a direita
    assert c.valor == valor_apos(depois_de_esquerda, +1, 1.0, TEMPO_MINIMO)


def test_trocar_de_direcao_sem_tique_no_meio_conta_o_que_a_primeira_seta_ja_andou():
    c = _em_tempo(_info(tempo=1000.0))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    c.pressionar(DIREITA, T0 + 7.0, _info())  # 2 s depois, sem nenhum tique entre as duas: o que a esquerda andou não pode se perder
    assert c.valor == round(valor_apos(1000.0, -1, 2.0, TEMPO_MINIMO) + 0.01, 3)


def test_soltar_a_seta_que_nao_esta_ativa_nao_faz_nada():
    c = _em_tempo(_info(tempo=1000.0))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    c.pressionar(DIREITA, T0 + 5.1, _info())
    valor = c.valor
    assert c.soltar("LEFT", T0 + 9.0).efeitos == ()
    assert c.valor == valor
    assert c.tique(T0 + 6.0).efeitos != ()  # a direita segue ativa e andando


def test_depois_de_soltar_os_tiques_nao_mudam_mais_nada():
    c = _em_tempo(_info(tempo=1000.0))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    c.soltar("LEFT", T0 + 6.0)
    valor = c.valor
    assert c.tique(T0 + 60.0) == Resposta(False, ()) and c.valor == valor


def test_o_relogio_que_anda_para_tras_vale_como_zero_segundo():
    c = _em_tempo(_info(tempo=1000.0))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    c.soltar("LEFT", T0 + 4.0)
    assert c.valor == 999.99


@pytest.mark.parametrize("fabrica,minimo", [(_em_tempo, TEMPO_MINIMO), (_em_espera, -1.0)], ids=["tempo", "espera"])
def test_segurar_a_esquerda_para_no_minimo(fabrica, minimo):
    c = fabrica(_info(tempo=0.5, espera=0.5, espera_minima=-1.0))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    c.soltar("LEFT", T0 + 500.0)
    assert c.valor == minimo
    r = c.pressionar(ESQUERDA, T0 + 600.0, _info())  # no mínimo, o toque também só mostra o valor
    assert c.valor == minimo and "mínimo" in _efeito(r, MostrarValor).texto


@pytest.mark.parametrize("fabrica", [_em_tempo, _em_espera], ids=["tempo", "espera"])
def test_segurar_a_direita_para_no_teto_de_uma_hora(fabrica):
    c = fabrica(_info(tempo=0.5, espera=0.5))
    c.pressionar(DIREITA, T0 + 5.0, _info())
    c.soltar("RIGHT", T0 + 500.0)
    assert c.valor == TETO
    r = c.pressionar(DIREITA, T0 + 600.0, _info())
    assert c.valor == TETO and "máximo" in _efeito(r, MostrarValor).texto


@pytest.mark.parametrize("fabrica,campo", [(_em_tempo, "tempo"), (_em_espera, "espera")], ids=["tempo", "espera"])
def test_enter_aceita_e_aplica_o_valor(fabrica, campo):
    c = fabrica(_info(tempo=0.5, espera=0.5))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    c.soltar("LEFT", T0 + 5.1)
    r = c.pressionar(ENTER, T0 + 9.0, _info())
    aplicar = AplicarTempo if campo == "tempo" else AplicarEspera
    assert r.consumida and r.efeitos == (aplicar(2, 0.49), Desmarcar())
    assert c.estado == Estado.NAVEGANDO and c.linha is None


def test_o_enter_com_a_seta_ainda_apertada_aplica_o_valor_do_instante():
    c = _em_espera(_info(espera=1000.0))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    r = c.pressionar(ENTER, T0 + 7.0, _info())  # 2 s segurando
    assert r.efeitos == (AplicarEspera(2, valor_apos(1000.0, -1, 2.0, -1.0)), Desmarcar())
    assert c.soltar("LEFT", T0 + 8.0).efeitos == ()  # a soltura que chega depois não faz nada


@pytest.mark.parametrize("fabrica", [_em_tempo, _em_espera], ids=["tempo", "espera"])
def test_enter_sem_mudar_nada_so_desmarca(fabrica):
    c = fabrica(_info(tempo=0.123456, espera=0.654321))
    assert c.pressionar(ENTER, T0 + 9.0, _info()).efeitos == (Desmarcar(),)


def test_voltar_ao_valor_do_inicio_equivale_a_nao_mudar():
    # O valor de uma gravação tem precisão de microssegundo; a edição é em milissegundos. Ir e voltar não pode gravar um arredondamento.
    c = _em_espera(_info(espera=0.09325159506108416))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    c.soltar("LEFT", T0 + 5.1)
    c.pressionar(DIREITA, T0 + 6.0, _info())
    c.soltar("RIGHT", T0 + 6.1)
    assert c.valor == 0.093
    assert c.pressionar(ENTER, T0 + 7.0, _info()).efeitos == (Desmarcar(),)


@pytest.mark.parametrize("fabrica", [_em_tempo, _em_espera], ids=["tempo", "espera"])
def test_esc_descarta_o_valor(fabrica):
    c = fabrica()
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    c.soltar("LEFT", T0 + 5.1)
    r = c.pressionar(ESC, T0 + 6.0, _info())
    assert r.consumida and r.efeitos == (Cancelar(),) and c.estado == Estado.NAVEGANDO


@pytest.mark.parametrize("fabrica", [_em_tempo, _em_espera], ids=["tempo", "espera"])
def test_nos_ajustes_cima_baixo_e_o_resto_sao_engolidos_menos_ctrl_e_alt(fabrica):
    c = fabrica()
    estado = c.estado
    for tecla in (CIMA, BAIXO, Tecla("A"), Tecla("TAB"), Tecla("F2"), Tecla("1"), Tecla("SPACE"), Tecla("DELETE"), Tecla("LEFT", shift=True),
                  Tecla("ENTER", shift=True)):
        assert c.pressionar(tecla, T0 + 5.0, _info()) == Resposta(True, ()), tecla
    for tecla in (Tecla("Z", ctrl=True), Tecla("S", ctrl=True), Tecla("F4", alt=True), Tecla("LEFT", ctrl=True)):
        assert c.pressionar(tecla, T0 + 5.0, _info()) == Resposta(False, ()), tecla
    assert c.estado == estado and c.valor == (0.1 if estado == Estado.TEMPO else 0.5)


# ================================================================================================ de um ajuste para o outro
def test_o_apostrofo_no_tempo_sem_mudanca_passa_para_a_espera():
    c = _em_tempo(_info(tempo=0.3, espera=0.8))
    r = c.pressionar(APOSTROFO, T0 + 5.0, _info(tempo=0.3, espera=0.8))
    assert r.consumida and _tipos(r) == [MostrarValor, Dica]
    assert c.estado == Estado.ESPERA and c.valor == 0.8 and c.linha == 2
    assert _efeito(r, Dica).texto == dica_do_estado(Estado.ESPERA, _info())


def test_o_apostrofo_no_tempo_ja_alterado_e_recusado_para_nao_perder_nem_gravar_sem_querer():
    c = _em_tempo(_info(tempo=0.5))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    c.soltar("LEFT", T0 + 5.1)
    r = c.pressionar(APOSTROFO, T0 + 6.0, _info())
    assert r.consumida and _tipos(r) == [Dica] and "Enter" in _efeito(r, Dica).texto and "Esc" in _efeito(r, Dica).texto
    assert c.estado == Estado.TEMPO and c.valor == 0.49


def test_o_apostrofo_com_a_seta_ainda_apertada_tambem_e_recusado():
    c = _em_tempo(_info(tempo=0.5))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    assert _tipos(c.pressionar(APOSTROFO, T0 + 5.1, _info())) == [Dica] and c.estado == Estado.TEMPO


def test_o_apostrofo_com_a_seta_apertada_mesmo_sem_mudar_o_valor_e_recusado():
    c = _em_tempo(_info(tempo=TEMPO_MINIMO))  # já no mínimo: a seta esquerda não muda o valor, mas está apertada
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    assert c.valor == TEMPO_MINIMO
    assert _tipos(c.pressionar(APOSTROFO, T0 + 5.1, _info())) == [Dica] and c.estado == Estado.TEMPO


def test_o_apostrofo_na_espera_e_engolido():
    c = _em_espera()
    assert c.pressionar(APOSTROFO, T0 + 5.0, _info()) == Resposta(True, ()) and c.estado == Estado.ESPERA


# ================================================================================================ foco, descarte e mapa que mudou
@pytest.mark.parametrize("estado", [Estado.TECLA, Estado.TEXTO, Estado.APLICATIVO, Estado.BOTAO, Estado.TEMPO, Estado.ESPERA])
def test_descartar_cancela_qualquer_edicao_em_andamento(estado):
    c = _em(estado, _linha_do_estado(estado))
    r = c.descartar()
    assert r.efeitos == (Cancelar(),) and not r.consumida
    assert c.estado == Estado.NAVEGANDO and c.linha is None and c.proposta == ""


def test_descartar_navegando_nao_faz_nada():
    assert EdicaoPorTeclado().descartar() == Resposta(False, ())


def test_descartar_com_a_seta_apertada_zera_tudo():
    c = _em_tempo(_info(tempo=1000.0))
    c.pressionar(ESQUERDA, T0 + 5.0, _info())
    c.descartar()
    assert c.soltar("LEFT", T0 + 9.0).efeitos == () and c.tique(T0 + 20.0).efeitos == ()
    c.pressionar(ENTER, T0 + 30.0, _info(tempo=1000.0))  # e a mesma instância serve para uma edição nova, do zero
    c.pressionar(ENTER, T0 + 30.2, _info(tempo=1000.0))
    assert c.estado == Estado.TEMPO and c.valor == 1000.0


def test_depois_de_aplicar_a_proxima_edicao_nao_herda_nada_da_anterior():
    c = _em_tecla()
    c.pressionar(Tecla("F"), T0 + 1.0, _info())
    c.pressionar(Tecla("F"), T0 + 1.5, _info())
    r = c.pressionar(ENTER, T0 + 3.0, _info(indice=5, alvo="Q"))
    assert (_efeito(r, IniciarCaptura).linha, _efeito(r, IniciarCaptura).atual) == (5, "Q") and c.proposta == ""


def test_uma_edicao_nova_comeca_limpa_mesmo_depois_de_uma_em_que_se_digitou():
    c = _em_texto(t=T0)
    c.pressionar(Tecla("A"), T0 + 0.1, _texto_info(), texto="a")  # digitou: "houve outra tecla"
    c.pressionar(ENTER, T0 + 0.2, _texto_info(), texto="a")       # e confirmou
    c.pressionar(ENTER, T0 + 5.0, _info())                        # abre a captura de uma tecla...
    c.pressionar(ENTER, T0 + 5.2, _info())                        # ...e Enter, Enter logo em seguida
    assert c.estado == Estado.TEMPO


def test_o_enter_duplo_so_conta_a_partir_do_enter_que_abriu_esta_edicao():
    c = _em_tecla(t=T0)
    c.pressionar(ESC, T0 + 0.1, _info())
    c.pressionar(ENTER, T0 + 10.0, _info())  # abre outra captura
    c.pressionar(ENTER, T0 + 10.3, _info())  # 0,3 s depois do Enter DESTA captura
    assert c.estado == Estado.TEMPO


# ================================================================================================ a ficha de cada linha
@pytest.mark.parametrize("tipo,acao,editavel,trecho", [
    (InputType.KEY, ActionType.PRESS_AND_RELEASE, True, ""),
    (InputType.MOUSE_BUTTON, ActionType.PRESS_AND_RELEASE, True, ""),
    (InputType.KEY, ActionType.PRESS, False, "só aperta"),
    (InputType.KEY, ActionType.RELEASE, False, "só solta"),
    (InputType.MOUSE_BUTTON, ActionType.PRESS, False, "só aperta"),
    (InputType.MOUSE_BUTTON, ActionType.RELEASE, False, "só solta"),
    (InputType.TEXT, ActionType.PRESS_AND_RELEASE, False, "calculado"),
    (InputType.APP_OPEN, ActionType.PRESS_AND_RELEASE, False, "programa"),
    (InputType.MOUSE_MOVE, ActionType.PRESS_AND_RELEASE, False, "barra lateral"),
    (InputType.MOUSE_SCROLL, ActionType.PRESS_AND_RELEASE, False, "barra lateral"),
    (InputType.WAIT, ActionType.PRESS_AND_RELEASE, False, "barra lateral")],
    ids=["tecla", "botao", "tecla-so-aperta", "tecla-so-solta", "botao-so-aperta", "botao-so-solta", "texto", "aplicativo", "mover", "rolar", "esperar"])
def test_so_tecla_e_botao_de_apertar_e_soltar_tem_tempo_editavel_e_os_outros_dizem_porque(tipo, acao, editavel, trecho):
    mapa = AutomationMap(name="T", commands=[Command(id="A", type=tipo, action=acao, target="E", text="x", duration=0.2, x=1, y=1, scroll_dy=1)])
    info = linha_info_de(mapa, 0)
    assert info.tempo_editavel is editavel
    assert (info.tempo_motivo == "") is editavel
    assert trecho in info.tempo_motivo


def test_a_ficha_traz_o_que_o_comando_tem():
    mapa = AutomationMap(name="T", commands=[
        Command(id="A", type=InputType.KEY, target="E", start=0.0, duration=1.0),
        Command(id="B", type=InputType.TEXT, text="olá", start=1.5, duration=0.0),
        Command(id="C", type=InputType.APP_OPEN, target="calc.exe", start=1.6)])
    a, b, c = (linha_info_de(mapa, i) for i in range(3))
    assert (a.indice, a.tipo, a.acao, a.alvo, a.tempo, a.espera, a.primeiro) == (0, InputType.KEY, ActionType.PRESS_AND_RELEASE, "E", 1.0, 0.0, True)
    assert (b.indice, b.tipo, b.texto, b.primeiro) == (1, InputType.TEXT, "olá", False)
    assert b.espera == pytest.approx(0.5, abs=1e-9) and b.espera_minima == pytest.approx(-1.0, abs=1e-9)
    assert (c.tipo, c.alvo) == (InputType.APP_OPEN, "calc.exe")


def test_a_ficha_de_uma_linha_que_nao_existe_e_um_erro():
    mapa = AutomationMap(name="T", commands=[Command(id="A", type=InputType.KEY, target="E", duration=0.1)])
    with pytest.raises(IndexError):
        linha_info_de(mapa, 1)


@pytest.mark.parametrize("nome", ["Click genshin", "Exemplo — Primeira automação", "Flins combo"], ids=["click-genshin", "exemplo", "flins-combo"])
def test_a_ficha_de_cada_comando_dos_mapas_reais_e_coerente_com_o_modelo(legacy_maps, nome):
    mapa = map_from_json(legacy_maps[nome])
    for i, cmd in enumerate(mapa.commands):
        info = linha_info_de(mapa, i)
        assert (info.indice, info.tipo, info.acao) == (i, cmd.type, cmd.action)
        assert info.espera == mapa.gap_before(i) and info.espera_minima == mapa.min_gap_before(i)
        assert info.espera_minima <= info.espera
        editavel = cmd.type in (InputType.KEY, InputType.MOUSE_BUTTON) and cmd.action == ActionType.PRESS_AND_RELEASE
        assert info.tempo_editavel is editavel, (nome, i)
        if editavel:
            assert info.tempo == cmd.duration and info.tempo > 0
        assert info.primeiro is (i == 0)


# ================================================================================================ os mapas reais, de ponta a ponta
@pytest.mark.parametrize("nome,passo", [("Click genshin", 1), ("Exemplo — Primeira automação", 1), ("Flins combo", 11)],
                         ids=["click-genshin", "exemplo", "flins-combo"])
def test_segurar_a_esquerda_na_espera_de_cada_comando_real_nunca_passa_do_minimo_e_o_modelo_aceita(legacy_maps, nome, passo):
    mapa = map_from_json(legacy_maps[nome])
    original = [cmd.start for cmd in mapa.commands]
    for i in sorted(set(range(0, len(mapa.commands), passo)) | {len(mapa.commands) - 1}):
        linha = linha_info_de(mapa, i)
        c = EdicaoPorTeclado()
        c.pressionar(APOSTROFO, T0, linha)
        c.pressionar(ESQUERDA, T0 + 1.0, linha)
        r = c.pressionar(ENTER, T0 + 600.0, linha)  # 10 minutos segurando
        if linha.espera_minima in (linha.espera, round(linha.espera, 3)):
            assert r.efeitos == (Desmarcar(),)  # já está no mínimo (o primeiro comando de um mapa que começa em 0): nada a gravar
            continue
        aplicar = _efeito(r, AplicarEspera)
        assert aplicar.linha == i and aplicar.valor == linha.espera_minima  # 10 minutos de seta chegam ao piso, e só a ele
        mapa.set_gap_before(aplicar.linha, aplicar.valor)  # o modelo aceita tudo o que o controlador propõe
        assert min(cmd.start for cmd in mapa.commands) >= 0.0
        mapa.set_gap_before(i, linha.espera)
        assert all(abs(a - b) < 1e-9 for a, b in zip([cmd.start for cmd in mapa.commands], original))


@pytest.mark.parametrize("nome,passo", [("Click genshin", 1), ("Flins combo", 11)], ids=["click-genshin", "flins-combo"])
def test_segurar_a_direita_na_espera_de_cada_comando_real_para_no_teto_de_uma_hora(legacy_maps, nome, passo):
    mapa = map_from_json(legacy_maps[nome])
    for i in range(0, len(mapa.commands), passo):
        linha = linha_info_de(mapa, i)
        c = EdicaoPorTeclado()
        c.pressionar(APOSTROFO, T0, linha)
        c.pressionar(DIREITA, T0 + 1.0, linha)
        assert _efeito(c.pressionar(ENTER, T0 + 1000.0, linha), AplicarEspera).valor == TETO


@pytest.mark.parametrize("nome,passo", [("Click genshin", 1), ("Flins combo", 11)], ids=["click-genshin", "flins-combo"])
def test_segurar_a_esquerda_no_tempo_de_cada_tecla_ou_botao_real_para_em_0_01(legacy_maps, nome, passo):
    mapa = map_from_json(legacy_maps[nome])
    quantos = 0
    for i in range(0, len(mapa.commands), passo):
        linha = linha_info_de(mapa, i)
        if not linha.tempo_editavel:
            continue
        c = EdicaoPorTeclado()
        c.pressionar(ENTER, T0, linha)
        c.pressionar(ENTER, T0 + 0.2, linha)  # Enter, Enter: o tempo apertado
        assert c.estado == Estado.TEMPO
        c.pressionar(ESQUERDA, T0 + 1.0, linha)
        assert _efeito(c.pressionar(ENTER, T0 + 600.0, linha), AplicarTempo).valor == TEMPO_MINIMO
        quantos += 1
    assert quantos > 0


def test_o_exemplo_o_aplicativo_e_o_texto_do_mapa_real_seguem_as_regras_do_tipo(legacy_maps):
    mapa = map_from_json(legacy_maps["Exemplo — Primeira automação"])
    app, texto = linha_info_de(mapa, 0), linha_info_de(mapa, 1)
    c = EdicaoPorTeclado()
    assert c.pressionar(ENTER, T0, app).efeitos[1] == AbrirAplicativo(0, mapa.commands[0].target)
    c.descartar()
    r = c.pressionar(ENTER, T0 + 5.0, texto)
    assert _efeito(r, AbrirTexto).atual == mapa.commands[1].text
    r = c.pressionar(ENTER, T0 + 5.2, texto, texto=mapa.commands[1].text)  # Enter duplo: o tempo do texto é calculado
    assert "calculado" in _efeito(r, Dica).texto and c.estado == Estado.TEXTO


# ================================================================================================ a dica didática (TEC-09)
UNIVERSO = ([Tecla(n, **m) for n in ([chr(c) for c in range(65, 91)] + list("0123456789") + [f"F{i}" for i in range(1, 25)] + [
    "ENTER", "ESC", "TAB", "SPACE", "BACKSPACE", "DELETE", "INSERT", "HOME", "END", "PAGEUP", "PAGEDOWN", "UP", "DOWN", "LEFT", "RIGHT",
    "SHIFT", "CTRL", "ALT"]) for m in (dict(), dict(shift=True), dict(ctrl=True), dict(alt=True), dict(ctrl=True, shift=True))]
            + [APOSTROFO, Tecla("", "'", ctrl=True), Tecla("", "'", alt=True), Tecla("", '"'), Tecla("", ","), Tecla("", "´")])


def _tratadas(estado):
    """As teclas que o estado trata de verdade: consumidas E com efeito (ou mudando de estado). Engolir sem efeito não conta."""
    linha = _linha_do_estado(estado)
    achadas = set()
    for tecla in UNIVERSO:
        c = _em(estado, linha)
        r = c.pressionar(tecla, T0 + 5.0, linha, texto="x")  # 5 s depois: fora da janela do Enter duplo
        if r.consumida and (c.estado != estado or r.efeitos):
            achadas.add(chave_da_tecla(tecla))
    return achadas


@pytest.mark.parametrize("estado", [Estado.NAVEGANDO, Estado.TEXTO, Estado.APLICATIVO, Estado.BOTAO, Estado.TEMPO, Estado.ESPERA],
                         ids=["navegando", "texto", "aplicativo", "botao", "tempo", "espera"])
def test_a_tabela_de_teclas_de_cada_estado_e_exatamente_o_que_o_estado_faz(estado):
    assert _tratadas(estado) == set(TECLAS_DO_ESTADO[estado])


def test_na_captura_toda_tecla_com_nome_e_tratada():
    assert TECLAS_DO_ESTADO[Estado.TECLA] == ("*",)
    for tecla in UNIVERSO:
        if tecla.nome:
            c = _em_tecla()
            r = c.pressionar(tecla, T0 + 5.0, _info())
            assert r.consumida and r.efeitos, tecla


@pytest.mark.parametrize("estado", list(Estado), ids=[e.name.lower() for e in Estado])
def test_toda_tecla_que_o_estado_trata_aparece_na_dica_do_estado(estado):
    dica = dica_do_estado(estado, _linha_do_estado(estado))
    assert dica
    for chave in TECLAS_DO_ESTADO[estado]:
        if chave != "*":
            assert ROTULOS[chave] in dica, f"{estado.name}: a tecla {chave} ({ROTULOS[chave]}) não está na dica: {dica!r}"


def test_na_captura_o_esc_cancela_e_o_shift_esc_grava_a_tecla_esc():
    # O Esc cancela (é o gesto de todo mundo); para a automação apertar Esc, a captura aceita Shift+Esc, duas vezes.
    c = _em_tecla()
    r = c.pressionar(Tecla("ESC", shift=True), T0 + 1.0, _info())
    assert _tipos(r) == [ProporTecla, Bip, Dica] and c.proposta == "ESC"
    assert c.pressionar(Tecla("ESC", shift=True), T0 + 1.5, _info()).efeitos == (AplicarAlvo(2, "ESC"), Desmarcar())
    assert "Shift+Esc" in dica_do_estado(Estado.TECLA, _info())
    for ruido in (Tecla("ESC", ctrl=True), Tecla("ESC", alt=True)):
        assert _em_tecla().pressionar(ruido, T0 + 1.0, _info()).efeitos[0] == ProporTecla("ESC")


def test_na_captura_a_dica_diz_que_esc_cancela():
    assert "Esc" in dica_do_estado(Estado.TECLA, _info()) and "cancela" in dica_do_estado(Estado.TECLA, _info())


def test_a_dica_da_captura_com_proposta_diz_qual_tecla_confirmar_e_como_cancelar():
    dica = dica_do_estado(Estado.TECLA, _info(), proposta="F7")
    assert "F7" in dica and "de novo" in dica and "Esc" in dica


def test_o_rotulo_de_cada_tecla_declarada_existe():
    for estado, chaves in TECLAS_DO_ESTADO.items():
        for chave in chaves:
            assert chave == "*" or chave in ROTULOS, (estado, chave)


@pytest.mark.parametrize("tecla,chave", [(Tecla("ENTER"), "ENTER"), (Tecla("ENTER", shift=True), "SHIFT+ENTER"), (Tecla("F", ctrl=True), "CTRL+F"),
                                         (Tecla("F", ctrl=True, shift=True, alt=True), "CTRL+ALT+SHIFT+F"), (APOSTROFO, "'"), (Tecla("", ","), ","),
                                         (Tecla("left"), "LEFT")])
def test_a_chave_de_uma_tecla(tecla, chave):
    assert chave_da_tecla(tecla) == chave


def test_a_dica_da_navegacao_cita_os_quatro_atalhos():
    dica = dica_do_estado(Estado.NAVEGANDO)
    for trecho in ("Enter", "'", "F2", "Shift+Enter"):
        assert trecho in dica


# ================================================================================================ o texto dos segundos e a pureza do módulo
@pytest.mark.parametrize("valor,texto", [(0.5, "0,5 s"), (0.25, "0,25 s"), (0.01, "0,01 s"), (1.234, "1,234 s"), (10.0, "10 s"), (100.0, "100 s"),
                                         (1000.0, "1000 s"), (3600.0, "3600 s"), (-0.6, "-0,6 s"), (0.0, "0 s"), (-0.0004, "0 s")])
def test_os_segundos_aparecem_com_virgula_e_sem_zeros_sobrando(valor, texto):
    assert formatar_segundos(valor) == texto


def test_o_modulo_e_puro_sem_qt_sem_relogio_sem_threads():
    # A promessa do módulo: o relógio é o argumento `agora`; nada aqui dorme, lê a hora ou abre janela. É isso que deixa a curva e o
    # Enter duplo provados com números, e o controlador funcionando igual com ou sem o Qt.
    arvore = ast.parse(pathlib.Path(te.__file__).read_text(encoding="utf-8"))
    proibidos = {"PySide6", "time", "threading", "datetime", "random", "os", "subprocess", "asyncio"}
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes = {alias.name.split(".")[0] for alias in no.names}
        elif isinstance(no, ast.ImportFrom) and no.level == 0:
            nomes = {(no.module or "").split(".")[0]}
        else:
            continue
        assert not (nomes & proibidos), f"teclado_edicao.py importa {sorted(nomes & proibidos)}"
