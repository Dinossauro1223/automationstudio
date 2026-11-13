"""Gravar no mapa o que a edição pelo teclado decidiu (25.9, T3a): `automationstudio/teclado_aplicar.py`.

Ficha: md/FICHA_TECLADO_T3_25_9.md (decisões T3-6 e T3-13). O controlador (`teclado_edicao.py`) decide *o que* mudar e devolve um efeito
(`AplicarAlvo`, `AplicarTexto`, `AplicarTempo`, `AplicarEspera`); este módulo é o único que toca o mapa. As regras, todas provadas aqui:

- **as mesmas da barra lateral** (tecla em maiúsculas, texto com a duração recalculada...): não pode haver duas verdades sobre "o que é
  editar uma tecla". A simetria com a barra de verdade está em tests/gui/test_teclado_aplicar_simetria.py;
- **tudo ou nada**: o que é recusado deixa o mapa EXATAMENTE como estava (provado comparando `to_dict()` de todos os comandos);
- **só muda o que foi pedido**: o resto do comando e os outros comandos ficam como estavam (a barra lateral reescreve o comando inteiro;
  a edição pelo teclado, não);
- **antes de gravar, confere** que o comando ainda é o mesmo da hora em que a linha foi marcada (índice, id e tipo): se a lista mudou por
  outro caminho no meio da edição, não grava no comando errado.

Lógica pura, sem Qt: roda aqui com os três mapas reais do dono como acessório fixo.
"""
from __future__ import annotations

import copy

import pytest

from automationstudio import core
from automationstudio.core import MOUSE_BUTTON_NAMES, ActionType, AutomationMap, Command, InputType, calculate_text_duration, map_from_json
from automationstudio.teclado_aplicar import (MENSAGEM_MUDOU, Marca, Resultado, aplicar_alvo, aplicar_espera, aplicar_tempo,
                                              aplicar_texto, marcar, nome_do_processo)
from automationstudio.teclado_edicao import TETO, formatar_segundos, linha_info_de

MAPAS = ["Click genshin", "Exemplo — Primeira automação", "Flins combo"]
IDS_MAPAS = ["click-genshin", "exemplo", "flins-combo"]

K, B, T, A, M, W = InputType.KEY, InputType.MOUSE_BUTTON, InputType.TEXT, InputType.APP_OPEN, InputType.MOUSE_MOVE, InputType.WAIT
# Os índices do mapa de teste (`_misto`): um comando de cada tipo, mais as duas formas de tecla que não têm tempo apertado.
TECLA, BOTAO, TEXTO, APLICATIVO, MOVER, ESPERAR, SO_APERTA, SO_SOLTA = range(8)


def _misto() -> AutomationMap:
    """Um de cada: tecla E (0–0,2), botão (0,5), texto (1,0), Bloco de Notas com sincronização própria (1,5), movimento (3,0), espera (3,5), e
    uma tecla só apertada e uma só solta. Os campos que a edição NÃO pode tocar (descrição, grupo, sincronização...) estão preenchidos."""
    return AutomationMap(name="Misto", commands=[
        Command(id="t1", type=K, target="E", start=0.0, duration=0.2, delay=0.05, delay_suggested=0.05, description="primeira", group="G", group_id="g1"),
        Command(id="b1", type=B, target="left", start=0.5, duration=0.1, description="clique"),
        Command(id="x1", type=T, text="olá", start=1.0, duration=0.0, delay=0.1, delay_suggested=0.1),
        Command(id="a1", type=A, target="notepad.exe", wait_process="notepad.exe", wait_timeout=5.0, wait_stable_ms=700,
                wait_after_open=0.4, start=1.5, description="abre"),
        Command(id="m1", type=M, x=10, y=20, start=3.0),
        Command(id="w1", type=W, start=3.5),
        Command(id="t2", type=K, target="Q", action=ActionType.PRESS, start=4.0),
        Command(id="t3", type=K, target="Q", action=ActionType.RELEASE, start=4.5),
    ])


def _foto(mapa: AutomationMap) -> list[dict]:
    """O estado completo de todos os comandos, para comparar antes e depois."""
    return copy.deepcopy([c.to_dict() for c in mapa.commands])


def _mudou(antes: list[dict], depois: list[dict]) -> dict:
    """{(índice, campo): (antes, depois)} só do que difere. Vazio = nada mudou."""
    assert len(antes) == len(depois), "o número de comandos mudou"
    achados = {}
    for i, (a, d) in enumerate(zip(antes, depois)):
        for campo in a:
            if a[campo] != d[campo]:
                achados[(i, campo)] = (a[campo], d[campo])
    return achados


def _recusa(mapa: AutomationMap, antes: list[dict], resultado: Resultado) -> None:
    """O que toda recusa tem: ok falso, uma frase para a barra de status, nenhum aviso de sucesso, e o mapa EXATAMENTE como estava."""
    assert isinstance(resultado, Resultado)
    assert resultado.ok is False
    assert resultado.mensagem.strip(), "a recusa precisa dizer por quê (a barra de status mostra esta frase)"
    assert resultado.aviso == ""
    assert _foto(mapa) == antes, "uma gravação recusada não pode mudar nada"


def _sucesso(resultado: Resultado) -> None:
    assert isinstance(resultado, Resultado)
    assert resultado.ok is True
    assert resultado.mensagem == ""


# ------------------------------------------------------------------------------------------------ a marca da linha
def test_marcar_guarda_o_indice_o_id_e_o_tipo_do_comando():
    mapa = _misto()
    assert marcar(mapa, TEXTO) == Marca(indice=TEXTO, id="x1", tipo=T)
    assert marcar(mapa, BOTAO) == Marca(indice=BOTAO, id="b1", tipo=B)


@pytest.mark.parametrize("indice", [-1, 8, 99], ids=["negativo", "logo-depois-do-fim", "longe"])
def test_marcar_recusa_indice_fora_do_mapa(indice):
    """O índice negativo do Python (-1 = o último) valeria em silêncio: aqui é erro, como em `gap_before`."""
    with pytest.raises(IndexError):
        marcar(_misto(), indice)


def test_marcar_num_mapa_vazio_recusa():
    with pytest.raises(IndexError):
        marcar(AutomationMap(name="Vazio", commands=[]), 0)


# ------------------------------------------------------------------------------------------------ a conferência antes de gravar
CHAMADAS = {
    "alvo": (TECLA, lambda mapa, marca: aplicar_alvo(mapa, marca, "Z")),
    "texto": (TEXTO, lambda mapa, marca: aplicar_texto(mapa, marca, "novo")),
    "tempo": (TECLA, lambda mapa, marca: aplicar_tempo(mapa, marca, 0.5)),
    "espera": (BOTAO, lambda mapa, marca: aplicar_espera(mapa, marca, 1.0)),
}
QUATRO = sorted(CHAMADAS)


@pytest.mark.parametrize("quem", QUATRO)
def test_as_quatro_gravacoes_funcionam_quando_a_marca_confere(quem):
    """A linha de base dos testes de conferência: sem mudança nenhuma no mapa, a mesma chamada grava."""
    indice, chamar = CHAMADAS[quem]
    mapa = _misto()
    antes = _foto(mapa)
    _sucesso(chamar(mapa, marcar(mapa, indice)))
    assert _foto(mapa) != antes


@pytest.mark.parametrize("quem", QUATRO)
def test_a_lista_encolheu_e_a_linha_marcada_nao_existe_mais(quem):
    """A linha 7 foi marcada quando o mapa tinha oito comandos; agora tem três (apagaram, ou desfizeram) e o índice não existe."""
    _indice, chamar = CHAMADAS[quem]
    mapa = _misto()
    marca = marcar(mapa, SO_SOLTA)
    del mapa.commands[3:]
    antes = _foto(mapa)
    resultado = chamar(mapa, marca)
    _recusa(mapa, antes, resultado)
    assert resultado.mensagem == MENSAGEM_MUDOU


@pytest.mark.parametrize("quem", QUATRO)
def test_indice_negativo_nao_vale_mesmo_que_o_ultimo_comando_combine(quem):
    """`commands[-1]` existe e pode até ter o mesmo id e tipo: ainda assim a marca é inválida."""
    _indice, chamar = CHAMADAS[quem]
    mapa = _misto()
    ultimo = mapa.commands[-1]
    antes = _foto(mapa)
    resultado = chamar(mapa, Marca(indice=-1, id=ultimo.id, tipo=ultimo.type))
    _recusa(mapa, antes, resultado)
    assert resultado.mensagem == MENSAGEM_MUDOU


@pytest.mark.parametrize("quem", QUATRO)
def test_outro_comando_ocupa_a_linha_marcada(quem):
    """A lista mudou por outro caminho (apagar, mover, desfazer) e agora a linha é de outro comando: não grava nele."""
    indice, chamar = CHAMADAS[quem]
    mapa = _misto()
    marca = marcar(mapa, indice)
    mapa.commands[indice].id = "outro"  # o mesmo tipo, mas já não é o comando que foi marcado
    antes = _foto(mapa)
    resultado = chamar(mapa, marca)
    _recusa(mapa, antes, resultado)
    assert resultado.mensagem == MENSAGEM_MUDOU


@pytest.mark.parametrize("quem", QUATRO)
def test_o_comando_marcado_mudou_de_tipo(quem):
    indice, chamar = CHAMADAS[quem]
    mapa = _misto()
    marca = marcar(mapa, indice)
    mapa.commands[indice].type = M if mapa.commands[indice].type != M else K
    antes = _foto(mapa)
    resultado = chamar(mapa, marca)
    _recusa(mapa, antes, resultado)
    assert resultado.mensagem == MENSAGEM_MUDOU


# ------------------------------------------------------------------------------------------------ tecla
@pytest.mark.parametrize("valor, esperado", [("q", "Q"), ("Q", "Q"), (" q ", "Q"), ("ç", "Ç"), ("f13", "F13"), ("numenter", "NUMENTER"),
                                             ("pageup", "PAGEUP"), ("7", "7")],
                         ids=["minuscula", "maiuscula", "com-espacos", "cedilha", "f13", "numenter", "pageup", "digito"])
def test_a_tecla_vai_em_maiusculas_como_na_barra_lateral(valor, esperado):
    mapa = _misto()
    antes = _foto(mapa)
    _sucesso(aplicar_alvo(mapa, marcar(mapa, TECLA), valor))
    assert mapa.commands[TECLA].target == esperado
    assert _mudou(antes, _foto(mapa)) == ({(TECLA, "target"): ("E", esperado)} if esperado != "E" else {})


@pytest.mark.parametrize("indice", [TECLA, SO_APERTA, SO_SOLTA], ids=["apertar-e-soltar", "so-aperta", "so-solta"])
def test_so_a_tecla_muda_em_qualquer_forma_de_tecla(indice):
    """O comportamento (apertar, soltar, os dois), o tempo, a descrição, o grupo: nada disso é tocado."""
    mapa = _misto()
    antes = _foto(mapa)
    _sucesso(aplicar_alvo(mapa, marcar(mapa, indice), "Z"))
    assert _mudou(antes, _foto(mapa)) == {(indice, "target"): (antes[indice]["target"], "Z")}


def test_a_mesma_tecla_e_aceita_e_nada_muda():
    mapa = _misto()
    antes = _foto(mapa)
    _sucesso(aplicar_alvo(mapa, marcar(mapa, TECLA), "E"))
    assert _foto(mapa) == antes


@pytest.mark.parametrize("valor", ["", "   ", "\t\n", None], ids=["vazia", "espacos", "tabulacao", "nada"])
def test_tecla_vazia_e_recusada(valor):
    mapa = _misto()
    antes = _foto(mapa)
    _recusa(mapa, antes, aplicar_alvo(mapa, marcar(mapa, TECLA), valor))


# ------------------------------------------------------------------------------------------------ botão do mouse
@pytest.mark.parametrize("nome", list(MOUSE_BUTTON_NAMES))
def test_cada_botao_que_o_modelo_conhece_e_gravado(nome):
    mapa = _misto()
    antes = _foto(mapa)
    _sucesso(aplicar_alvo(mapa, marcar(mapa, BOTAO), nome))
    assert mapa.commands[BOTAO].target == nome
    assert [e for e in mapa.validate() if "botão do mouse" in e] == []
    assert set(_mudou(antes, _foto(mapa))) <= {(BOTAO, "target")}


@pytest.mark.parametrize("valor, esperado", [("X1", "x1"), (" Right ", "right"), ("MIDDLE", "middle")], ids=["maiuscula", "com-espacos", "tudo-maiusculo"])
def test_o_botao_vai_em_minusculas_como_o_motor_compara(valor, esperado):
    mapa = _misto()
    _sucesso(aplicar_alvo(mapa, marcar(mapa, BOTAO), valor))
    assert mapa.commands[BOTAO].target == esperado


@pytest.mark.parametrize("valor", ["", "x3", "esquerdo", "left;right", "middle2", None], ids=["vazio", "x3", "portugues", "dois", "sufixo", "nada"])
def test_botao_que_nao_existe_e_recusado(valor):
    mapa = _misto()
    antes = _foto(mapa)
    _recusa(mapa, antes, aplicar_alvo(mapa, marcar(mapa, BOTAO), valor))


# ------------------------------------------------------------------------------------------------ programa
def test_o_programa_e_gravado_sem_aspas_nem_espacos_nas_pontas():
    mapa = _misto()
    _sucesso(aplicar_alvo(mapa, marcar(mapa, APLICATIVO), '  "C:\\Programas\\Foo\\foo.exe"  '))
    assert mapa.commands[APLICATIVO].target == "C:\\Programas\\Foo\\foo.exe"


def test_o_processo_esperado_acompanha_quando_era_o_do_programa_antigo():
    """Trocar só o alvo deixaria a automação esperando o Bloco de Notas, que nunca abriria, até o tempo limite."""
    mapa = _misto()
    antes = _foto(mapa)
    resultado = aplicar_alvo(mapa, marcar(mapa, APLICATIVO), "msedge.exe")
    _sucesso(resultado)
    assert resultado.aviso == ""
    assert (mapa.commands[APLICATIVO].target, mapa.commands[APLICATIVO].wait_process) == ("msedge.exe", "msedge.exe")
    assert set(_mudou(antes, _foto(mapa))) == {(APLICATIVO, "target"), (APLICATIVO, "wait_process")}


def test_acompanha_sem_diferenciar_maiusculas_e_pelo_nome_do_arquivo():
    mapa = _misto()
    mapa.commands[APLICATIVO].target = "C:\\Windows\\System32\\NOTEPAD.EXE"
    mapa.commands[APLICATIVO].wait_process = "notepad.exe"
    _sucesso(aplicar_alvo(mapa, marcar(mapa, APLICATIVO), "C:\\Apps\\Foo\\foo.exe"))
    assert mapa.commands[APLICATIVO].wait_process == "foo.exe"


def test_as_aspas_do_programa_antigo_nao_enganam_a_comparacao():
    mapa = _misto()
    mapa.commands[APLICATIVO].target = '  "C:\\Apps\\Foo\\foo.exe" '
    mapa.commands[APLICATIVO].wait_process = "FOO.EXE"
    _sucesso(aplicar_alvo(mapa, marcar(mapa, APLICATIVO), "bar.exe"))
    assert mapa.commands[APLICATIVO].wait_process == "bar.exe"


def test_o_preset_da_calculadora_tem_dois_nomes_e_acompanha_inteiro():
    """O preset "Calculadora" é `CalculatorApp.exe;calc.exe` (o mesmo texto no alvo e no processo): trocá-lo leva o processo junto."""
    mapa = _misto()
    mapa.commands[APLICATIVO].target = "CalculatorApp.exe;calc.exe"
    mapa.commands[APLICATIVO].wait_process = "CalculatorApp.exe;calc.exe"
    _sucesso(aplicar_alvo(mapa, marcar(mapa, APLICATIVO), "notepad.exe"))
    assert mapa.commands[APLICATIVO].wait_process == "notepad.exe"


def test_sem_processo_esperado_continua_sem():
    """Nunca criar uma espera que o dono não tinha."""
    mapa = _misto()
    mapa.commands[APLICATIVO].wait_process = ""
    resultado = aplicar_alvo(mapa, marcar(mapa, APLICATIVO), "msedge.exe")
    _sucesso(resultado)
    assert mapa.commands[APLICATIVO].wait_process == ""
    assert resultado.aviso == ""


def test_um_processo_esperado_diferente_continua_e_o_aviso_diz_qual():
    mapa = _misto()
    mapa.commands[APLICATIVO].wait_process = "chrome.exe"
    resultado = aplicar_alvo(mapa, marcar(mapa, APLICATIVO), "msedge.exe")
    _sucesso(resultado)
    assert mapa.commands[APLICATIVO].target == "msedge.exe"
    assert mapa.commands[APLICATIVO].wait_process == "chrome.exe", "o dono escolheu esse processo: não é do teclado trocá-lo"
    assert "chrome.exe" in resultado.aviso and "Shift+Enter" in resultado.aviso


def test_o_resto_da_sincronizacao_nao_muda():
    mapa = _misto()
    antes = _foto(mapa)
    _sucesso(aplicar_alvo(mapa, marcar(mapa, APLICATIVO), "msedge.exe"))
    comando = mapa.commands[APLICATIVO]
    assert (comando.wait_timeout, comando.wait_stable_ms, comando.wait_after_open, comando.description) == (5.0, 700, 0.4, "abre")
    assert set(_mudou(antes, _foto(mapa))) == {(APLICATIVO, "target"), (APLICATIVO, "wait_process")}


@pytest.mark.parametrize("valor", ["", "   ", '""', None], ids=["vazio", "espacos", "so-aspas", "nada"])
def test_programa_vazio_e_recusado(valor):
    mapa = _misto()
    antes = _foto(mapa)
    _recusa(mapa, antes, aplicar_alvo(mapa, marcar(mapa, APLICATIVO), valor))


@pytest.mark.parametrize("valor", ["C:\\", ".", "\\"], ids=["raiz-do-disco", "ponto", "barra"])
def test_programa_sem_nome_de_arquivo_e_recusado(valor):
    """Se o nome fosse vazio o processo esperado ficaria vazio (a sincronização sumiria em silêncio) ou o antigo (esperando para sempre)."""
    mapa = _misto()
    antes = _foto(mapa)
    _recusa(mapa, antes, aplicar_alvo(mapa, marcar(mapa, APLICATIVO), valor))


@pytest.mark.parametrize("alvo, esperado", [
    ("notepad.exe", "notepad.exe"),
    ("C:\\Windows\\System32\\notepad.exe", "notepad.exe"),
    ('"C:\\Program Files\\Foo\\foo.exe"', "foo.exe"),
    ("  msedge.exe  ", "msedge.exe"),
    ("C:/Apps/bar.exe", "bar.exe"),
    ("C:\\Apps\\Pasta\\\\", "Pasta"),
    ("CalculatorApp.exe;calc.exe", "CalculatorApp.exe;calc.exe"),
    ("", ""), (None, ""), ("C:\\", ""),
], ids=["simples", "caminho", "aspas", "espacos", "barra-normal", "barra-no-fim", "dois-nomes", "vazio", "nada", "raiz"])
def test_nome_do_processo_e_o_nome_do_arquivo_do_programa(alvo, esperado):
    assert nome_do_processo(alvo) == esperado


# ------------------------------------------------------------------------------------------------ o alvo só vale onde há alvo
@pytest.mark.parametrize("indice", [TEXTO, MOVER, ESPERAR], ids=["texto", "mover", "esperar"])
def test_tipo_sem_tecla_botao_ou_programa_e_recusado(indice):
    mapa = _misto()
    antes = _foto(mapa)
    resultado = aplicar_alvo(mapa, marcar(mapa, indice), "Z")
    _recusa(mapa, antes, resultado)
    assert "tecla" in resultado.mensagem and "programa" in resultado.mensagem


# ------------------------------------------------------------------------------------------------ texto
def test_o_texto_e_gravado_com_a_duracao_recalculada():
    """Como a barra lateral: `duração = calculate_text_duration(texto)`. O intervalo por caractere é fixado para o número ser conferível à mão."""
    core.set_runtime_defaults(text_char_interval=0.05)
    mapa = _misto()
    _sucesso(aplicar_texto(mapa, marcar(mapa, TEXTO), "abcd"))
    comando = mapa.commands[TEXTO]
    assert comando.text == "abcd"
    assert comando.duration == pytest.approx(0.2)
    assert comando.duration == calculate_text_duration("abcd")


def test_so_o_texto_e_a_duracao_mudam():
    core.set_runtime_defaults(text_char_interval=0.02)  # com intervalo 0 (o padrão dos testes) a duração calculada seria 0 e não mudaria
    mapa = _misto()
    antes = _foto(mapa)
    _sucesso(aplicar_texto(mapa, marcar(mapa, TEXTO), "um texto bem mais comprido do que o de antes"))
    assert set(_mudou(antes, _foto(mapa))) == {(TEXTO, "text"), (TEXTO, "duration")}, "o atraso, o início, a descrição e os outros comandos ficam"


def test_o_texto_nao_e_aparado_nem_mexido():
    """A barra lateral grava o texto como veio: espaços, acentos e o que mais houver."""
    mapa = _misto()
    _sucesso(aplicar_texto(mapa, marcar(mapa, TEXTO), "  Olá,  mundo ção ✓ "))
    assert mapa.commands[TEXTO].text == "  Olá,  mundo ção ✓ "


def test_o_mesmo_texto_e_aceito_e_so_corrige_a_duracao_se_estava_errada():
    """O mapa real "Exemplo" guarda a duração 0 num comando de texto (o modelo calcula pelo texto): gravar o mesmo texto a acerta, como a barra lateral."""
    core.set_runtime_defaults(text_char_interval=0.05)
    mapa = _misto()
    assert mapa.commands[TEXTO].duration == 0.0
    _sucesso(aplicar_texto(mapa, marcar(mapa, TEXTO), "olá"))
    assert mapa.commands[TEXTO].text == "olá"
    assert mapa.commands[TEXTO].duration == pytest.approx(0.15)


def test_texto_vazio_e_recusado():
    mapa = _misto()
    antes = _foto(mapa)
    _recusa(mapa, antes, aplicar_texto(mapa, marcar(mapa, TEXTO), ""))
    _recusa(mapa, antes, aplicar_texto(mapa, marcar(mapa, TEXTO), None))


@pytest.mark.parametrize("indice", [TECLA, BOTAO, APLICATIVO, MOVER, ESPERAR], ids=["tecla", "botao", "aplicativo", "mover", "esperar"])
def test_texto_num_comando_que_nao_e_de_texto_e_recusado(indice):
    mapa = _misto()
    antes = _foto(mapa)
    _recusa(mapa, antes, aplicar_texto(mapa, marcar(mapa, indice), "novo"))


# ------------------------------------------------------------------------------------------------ tempo apertado
@pytest.mark.parametrize("indice", [TECLA, BOTAO], ids=["tecla", "botao"])
def test_o_tempo_apertado_vai_direto_na_duracao_sem_empurrar_ninguem(indice):
    """D4: como a célula "Duração" da tabela, o tempo de um comando não muda o início dos seguintes."""
    mapa = _misto()
    antes = _foto(mapa)
    _sucesso(aplicar_tempo(mapa, marcar(mapa, indice), 0.75))
    assert mapa.commands[indice].duration == 0.75
    assert _mudou(antes, _foto(mapa)) == {(indice, "duration"): (antes[indice]["duration"], 0.75)}


@pytest.mark.parametrize("valor, esperado", [(0.30000000000000004, 0.3), (0.1234, 0.123), (0.0996, 0.1), (3600.0, 3600.0), (0.001, 0.001)],
                         ids=["ruido-de-float", "quarta-casa", "arredonda-para-cima", "o-teto", "o-menor-do-milissegundo"])
def test_o_tempo_e_arredondado_ao_milissegundo(valor, esperado):
    mapa = _misto()
    _sucesso(aplicar_tempo(mapa, marcar(mapa, TECLA), valor))
    assert mapa.commands[TECLA].duration == esperado


@pytest.mark.parametrize("valor", [0.0, -1.0, 0.0004, float("nan"), float("inf"), float("-inf"), 3600.001, TETO + 1, None, "abc"],
                         ids=["zero", "negativo", "abaixo-do-milissegundo", "nan", "infinito", "menos-infinito", "acima-do-teto", "bem-acima", "nada", "texto"])
def test_tempo_invalido_e_recusado(valor):
    """Duração 0 num "apertar e soltar" é erro do modelo (a tecla ficaria presa): a barra lateral também a recusa."""
    mapa = _misto()
    antes = _foto(mapa)
    _recusa(mapa, antes, aplicar_tempo(mapa, marcar(mapa, TECLA), valor))


@pytest.mark.parametrize("indice", [SO_APERTA, SO_SOLTA, TEXTO, APLICATIVO, MOVER, ESPERAR], ids=["so-aperta", "so-solta", "texto", "aplicativo", "mover", "esperar"])
def test_comando_sem_tempo_apertado_e_recusado_com_o_motivo_do_controlador(indice):
    """O motivo é o mesmo que `linha_info_de` dá ao controlador: uma fonte só."""
    mapa = _misto()
    antes = _foto(mapa)
    resultado = aplicar_tempo(mapa, marcar(mapa, indice), 0.5)
    _recusa(mapa, antes, resultado)
    assert resultado.mensagem == linha_info_de(mapa, indice).tempo_motivo != ""


# ------------------------------------------------------------------------------------------------ espera
def _tres() -> AutomationMap:
    """A 0–1,0; B começa em 1,5 (0,5 depois do fim de A); C em 2,2 (0,2 depois do fim de B)."""
    def tecla(id_, inicio, duracao):
        return Command(id=id_, type=K, target="E", start=inicio, duration=duracao)
    return AutomationMap(name="T", commands=[tecla("A", 0.0, 1.0), tecla("B", 1.5, 0.5), tecla("C", 2.2, 0.2)])


def test_mais_espera_empurra_o_comando_e_todos_os_seguintes():
    mapa = _tres()
    _sucesso(aplicar_espera(mapa, marcar(mapa, 1), 1.0))
    assert [c.start for c in mapa.commands] == pytest.approx([0.0, 2.0, 2.7])
    assert mapa.gap_before(1) == pytest.approx(1.0)


def test_menos_espera_puxa_o_comando_e_os_seguintes():
    mapa = _tres()
    _sucesso(aplicar_espera(mapa, marcar(mapa, 1), 0.1))
    assert [c.start for c in mapa.commands] == pytest.approx([0.0, 1.1, 1.8])


def test_a_espera_so_mexe_nos_inicios():
    mapa = _tres()
    antes = _foto(mapa)
    _sucesso(aplicar_espera(mapa, marcar(mapa, 1), 1.0))
    assert {campo for (_i, campo) in _mudou(antes, _foto(mapa))} == {"start"}


def test_a_espera_do_primeiro_comando_e_o_proprio_inicio():
    mapa = _tres()
    _sucesso(aplicar_espera(mapa, marcar(mapa, 0), 0.4))
    assert [c.start for c in mapa.commands] == pytest.approx([0.4, 1.9, 2.6])


@pytest.mark.parametrize("indice", [TEXTO, MOVER, ESPERAR, APLICATIVO], ids=["texto", "mover", "esperar", "aplicativo"])
def test_a_espera_vale_para_qualquer_tipo_de_comando(indice):
    mapa = _misto()
    atual = mapa.gap_before(indice)
    _sucesso(aplicar_espera(mapa, marcar(mapa, indice), atual + 0.25))
    assert mapa.gap_before(indice) == pytest.approx(atual + 0.25)


def test_espera_abaixo_do_minimo_e_recusada_e_a_mensagem_diz_o_minimo():
    mapa = _tres()
    antes = _foto(mapa)
    minimo = mapa.min_gap_before(1)
    resultado = aplicar_espera(mapa, marcar(mapa, 1), minimo - 0.5)
    _recusa(mapa, antes, resultado)
    assert formatar_segundos(minimo) in resultado.mensagem
    assert "instante 0" in resultado.mensagem


def test_a_espera_no_minimo_exato_e_aceita():
    mapa = _tres()
    minimo = mapa.min_gap_before(1)
    _sucesso(aplicar_espera(mapa, marcar(mapa, 1), minimo))
    assert min(c.start for c in mapa.commands[1:]) == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("valor", [float("nan"), float("inf"), float("-inf"), None, "abc"], ids=["nan", "infinito", "menos-infinito", "nada", "texto"])
def test_espera_que_nao_e_numero_finito_e_recusada(valor):
    mapa = _tres()
    antes = _foto(mapa)
    _recusa(mapa, antes, aplicar_espera(mapa, marcar(mapa, 1), valor))


# ------------------------------------------------------------------------------------------------ os mapas reais
@pytest.mark.parametrize("nome", MAPAS, ids=IDS_MAPAS)
def test_nos_mapas_reais_toda_gravacao_natural_funciona_e_o_mapa_continua_valido(legacy_maps, nome):
    """Para cada comando do mapa do dono, a edição que o teclado faria naquele tipo (tecla, botão, texto, programa, tempo e espera), uma
    depois da outra no MESMO mapa. Todas têm de gravar, e o mapa tem de continuar sem nenhum erro de validação (hoje os três não têm)."""
    mapa = map_from_json(legacy_maps[nome])
    assert mapa.validate() == []
    total = len(mapa.commands)
    for i in range(total):
        marca = marcar(mapa, i)
        tipo = mapa.commands[i].type
        if tipo == K:
            _sucesso(aplicar_alvo(mapa, marca, "z"))
        elif tipo == B:
            _sucesso(aplicar_alvo(mapa, marca, "x2"))
        elif tipo == T:
            _sucesso(aplicar_texto(mapa, marca, "outro texto"))
        elif tipo == A:
            _sucesso(aplicar_alvo(mapa, marca, "calc.exe"))
        if linha_info_de(mapa, i).tempo_editavel:
            _sucesso(aplicar_tempo(mapa, marca, 0.25))
        _sucesso(aplicar_espera(mapa, marca, mapa.gap_before(i) + 0.1))
    assert mapa.validate() == []
    assert len(mapa.commands) == total


def test_exemplo_o_programa_novo_leva_o_processo_esperado_junto(legacy_maps):
    """No mapa "Exemplo" o Bloco de Notas espera o processo `notepad.exe`: é o caso que o acompanhamento existe para proteger."""
    mapa = map_from_json(legacy_maps["Exemplo — Primeira automação"])
    indice = next(i for i, c in enumerate(mapa.commands) if c.type == A)
    assert (mapa.commands[indice].target, mapa.commands[indice].wait_process) == ("notepad.exe", "notepad.exe")
    _sucesso(aplicar_alvo(mapa, marcar(mapa, indice), "msedge.exe"))
    assert (mapa.commands[indice].target, mapa.commands[indice].wait_process) == ("msedge.exe", "msedge.exe")
    assert mapa.validate() == []


def test_flins_a_espera_de_um_comando_do_meio_empurra_exatamente_os_seguintes(legacy_maps):
    mapa = map_from_json(legacy_maps["Flins combo"])
    antes = [c.start for c in mapa.commands]
    atual = mapa.gap_before(400)
    _sucesso(aplicar_espera(mapa, marcar(mapa, 400), atual + 0.25))
    depois = [c.start for c in mapa.commands]
    assert depois[:400] == antes[:400]
    assert depois[400:] == pytest.approx([x + 0.25 for x in antes[400:]])
