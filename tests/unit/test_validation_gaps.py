"""Validação do que o executor já exigia (F2 do DELEGACAO.md, versão 25.9).

Nome histórico: até a 25.8 este arquivo guardava 3 LACUNAS CONHECIDAS, descobertas ao escrever a suíte da 25.5, como
testes `xfail(strict=True)`: a validação do mapa não conferia o nome do botão do mouse, aceitava "abrir aplicativo"
sem alvo e aceitava qualquer `repeat_count`. As três falhavam só na execução (ou, no caso do `repeat_count`, rodavam
uma vez em silêncio). A F2 fechou as três: os marcadores saíram, os testes ficam como regressão e estes testes novos
fixam os limites de cada regra.

Princípio das três regras: a validação recusa exatamente o que o executor recusaria, nem mais nem menos. Por isso os
nomes de botão vêm da fonte única `core.MOUSE_BUTTON_NAMES` (a mesma que o resolvedor do pynput usa e que o teste de
contrato dos backends confere) e comparam sem diferenciar maiúsculas, como os backends; e o alvo de "abrir aplicativo"
passa pela mesma normalização do executor (`core.normalized_app_target`). Os 3 mapas reais continuam validando
(`test_legacy_maps.py`).
"""
import json
import types

import pytest

from automationstudio import core, input_system
from automationstudio.core import AutomationMap, Command, InputType, State, map_from_json
from testsupport.fakes import pretend_windows
from testsupport.helpers import make_map

BOTOES_QUE_O_EXECUTOR_ACEITA = ["left", "right", "middle", "x1", "x2"]


def _botao(alvo, **resto) -> Command:
    return Command(type=InputType.MOUSE_BUTTON, target=alvo, duration=0.1, **resto)


def _abrir_app(alvo, **resto) -> Command:
    return Command(type=InputType.APP_OPEN, target=alvo, **resto)


def _mapa_com(comando=None, **campos) -> AutomationMap:
    comando = comando if comando is not None else Command(type=InputType.KEY, target="A", duration=0.1)
    return AutomationMap(name="M", commands=[comando], **campos)


# ----------------------------------------------------------------------------------- as 3 lacunas originais (sem xfail)
def test_botao_de_mouse_desconhecido_deveria_ser_erro_de_validacao():
    assert Command(type=InputType.MOUSE_BUTTON, target="lefft", duration=0.1).validate()


def test_abrir_aplicativo_sem_alvo_deveria_ser_erro_de_validacao():
    assert Command(type=InputType.APP_OPEN, target="").validate()


def test_repeat_count_menor_que_menos_um_deveria_ser_invalido():
    ok = Command(type=InputType.KEY, target="A", duration=0.1)
    assert AutomationMap(name="M", commands=[ok], repeat_count=-2).validate()


# ----------------------------------------------------------------------------------- botão do mouse
def test_os_botoes_que_o_executor_aceita_sao_exatamente_estes_cinco():
    # Fixa o conjunto: acrescentar ou tirar um botão passa a ser uma decisão (e exige mexer nos backends e no editor).
    assert list(core.MOUSE_BUTTON_NAMES) == BOTOES_QUE_O_EXECUTOR_ACEITA


@pytest.mark.parametrize("nome", BOTOES_QUE_O_EXECUTOR_ACEITA + ["LEFT", "Right", "X1", "X2"])
def test_botao_do_mouse_conhecido_valida_em_qualquer_caixa(nome):
    # Os backends comparam em minúsculas (str(botao).lower()): "Left" executa, então não pode ser recusado.
    assert _botao(nome).validate() == []


@pytest.mark.parametrize("nome", ["lefft", "unknown", "mouse4", "esquerdo", "x3", "l", " left", "left "])
def test_botao_do_mouse_desconhecido_e_recusado_com_o_nome_na_mensagem(nome):
    # Espaço nas pontas também é recusado: os backends não aparam o nome, então " left" falharia na execução.
    erros = _botao(nome).validate()
    assert len(erros) == 1, erros
    assert "botão do mouse desconhecido" in erros[0] and f"'{nome}'" in erros[0], erros


def test_botao_do_mouse_vazio_continua_com_um_so_erro_o_de_alvo_nao_definido():
    erros = _botao("").validate()
    assert len(erros) == 1 and "sem tecla/botão definido" in erros[0], erros


@pytest.mark.parametrize("comando", [
    Command(type=InputType.MOUSE_SCROLL, target="left", scroll_dx=-2),
    Command(type=InputType.MOUSE_SCROLL, target="up", scroll_dy=3),
    Command(type=InputType.MOUSE_MOVE, target="", x=10, y=20),
    Command(type=InputType.KEY, target="lefft", duration=0.1),
], ids=["rolar-esquerda", "rolar-cima", "mover", "tecla-com-nome-de-botao-errado"])
def test_a_regra_do_botao_so_vale_para_comandos_de_botao_do_mouse(comando):
    # O alvo de rolagem é uma direção ("left", "up") e o de tecla é uma tecla: nenhum deles passa pela lista de botões.
    assert comando.validate() == []


def test_comando_desativado_tambem_e_validado_como_nas_outras_regras():
    # Decisão: validate() olha todos os comandos, ativos ou não (como já fazia com alvo vazio, duração negativa...).
    assert _botao("lefft", enabled=False).validate()


# ----------------------------------------------------------------------------------- abrir aplicativo
@pytest.mark.parametrize("alvo", ["", "   ", '""', '"', None])
def test_abrir_aplicativo_sem_nada_para_abrir_e_recusado(alvo):
    # Mesma conta do executor (_launch_application): sem espaços nas pontas e sem aspas externas, vazio é erro.
    erros = _abrir_app(alvo).validate()
    assert len(erros) == 1 and "abrir aplicativo sem" in erros[0], erros


@pytest.mark.parametrize("alvo", ["notepad.exe", '"C:\\Program Files\\App\\app.exe"', "  calc  ", "C:\\Apps\\a b.exe"])
def test_abrir_aplicativo_com_alvo_valida(alvo):
    assert _abrir_app(alvo).validate() == []


@pytest.mark.parametrize("alvo,esperado", [("notepad.exe", "notepad.exe"), ('  "C:\\a b\\x.exe"  ', "C:\\a b\\x.exe"),
                                           ("", ""), (None, ""), ('""', "")])
def test_normalizacao_do_alvo_e_a_mesma_do_executor(alvo, esperado):
    assert core.normalized_app_target(alvo) == esperado


def test_o_executor_abre_o_programa_ja_normalizado_e_recusa_o_que_a_validacao_recusa(make_engine, monkeypatch):
    # O executor (_launch_application) e a validação usam a mesma conta (core.normalized_app_target). Se um dia a
    # validação aceitasse um alvo que o executor recusa, ou o contrário, este teste mostra: o último elo da corrente.
    pretend_windows(monkeypatch)
    abertos = []
    monkeypatch.setattr(input_system.subprocess, "Popen",
                        lambda comando, **opcoes: (abertos.append(comando), types.SimpleNamespace(pid=4242))[1])
    motor, _backend = make_engine()
    assert motor._launch_application('  "C:\\Program Files\\App\\app.exe"  ') == 4242
    assert abertos == [["C:\\Program Files\\App\\app.exe"]]
    for vazio in ("", "   ", '""', None):
        assert _abrir_app(vazio).validate()                      # a validação recusa...
        with pytest.raises(RuntimeError, match="Nenhum aplicativo"):
            motor._launch_application(vazio)                     # ...e o executor também
    assert len(abertos) == 1


def test_a_regra_do_alvo_so_vale_para_abrir_aplicativo():
    # Texto, espera e movimento podem ter alvo vazio; só "abrir aplicativo" depende dele.
    assert Command(type=InputType.TEXT, text="olá", target="").validate() == []
    assert Command(type=InputType.MOUSE_MOVE, target="", x=1, y=2).validate() == []


# ----------------------------------------------------------------------------------- repeat_count
@pytest.mark.parametrize("n", [-1, 1, 2, 9999, 10 ** 6])
def test_repeat_count_infinito_ou_positivo_valida(n):
    assert _mapa_com(repeat_count=n).validate() == []


@pytest.mark.parametrize("n", [-2, -5, -100])
def test_repeat_count_menor_que_menos_um_e_recusado_com_o_valor_na_mensagem(n):
    erros = _mapa_com(repeat_count=n).validate()
    assert len(erros) == 1, erros
    assert "repeat_count" in erros[0] and str(n) in erros[0], erros


def test_repeat_count_zero_continua_recusado_com_a_mensagem_propria():
    erros = _mapa_com(repeat_count=0).validate()
    assert len(erros) == 1 and "não pode ser 0" in erros[0], erros


def test_mapa_lido_com_repeat_count_menor_que_menos_um_carrega_igual_e_a_validacao_recusa():
    # A leitura não corrige o valor (regra de ouro: o leitor não altera dados do usuário em silêncio); quem recusa é a
    # validação, na hora de executar.
    texto = json.dumps({"name": "H", "repeat_count": -5, "commands": [{"type": "key", "target": "A", "duration": 0.1}]})
    mapa = map_from_json(texto)
    assert mapa.repeat_count == -5
    assert any("repeat_count" in erro and "-5" in erro for erro in mapa.validate())


# ----------------------------------------------------------------------------------- efeito para o usuário: o motor recusa
@pytest.mark.parametrize("mapa,trecho", [
    (make_map([_botao("lefft")]), "botão do mouse desconhecido"),
    (make_map([_abrir_app("")]), "abrir aplicativo sem"),
    (make_map([Command(type=InputType.KEY, target="A", duration=0.1)], repeat_count=-2), "repeat_count"),
], ids=["botao-desconhecido", "app-sem-alvo", "repeat-count--2"])
def test_o_motor_recusa_o_mapa_antes_de_enviar_qualquer_entrada(make_engine, mapa, trecho):
    # Antes da F2: o botão errado e o aplicativo sem alvo falhavam no meio da execução (depois de outras entradas já
    # enviadas) e o repeat_count -2 rodava uma vez em silêncio. Agora o mapa nem começa, e a mensagem diz o motivo.
    motor, backend = make_engine()
    with pytest.raises(ValueError, match="Mapa inválido") as erro:
        motor.run(mapa)
    assert trecho in str(erro.value)
    assert backend.events == [] and motor.state.state == State.IDLE and motor._thread is None
