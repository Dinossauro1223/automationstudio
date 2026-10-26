"""Cenários com os 3 mapas REAIS do usuário (formato v1, como estavam no banco): do mapa até a sequência de eventos.

Cada cenário roda o fluxo inteiro (leitura do mapa → linha do tempo → motor → backend), com o relógio virtual, e compara o
resultado com um arquivo de referência (tests/data/golden). Eles têm duas funções:
  1. pegar qualquer mudança involuntária de tempo, ordem, alvo ou liberação de teclas no motor;
  2. servir de GARANTIA para o Ponto 3 (novo formato de mapa): ler o mapa pelo formato novo precisa dar EXATAMENTE a mesma
     sequência de eventos que o formato antigo dá hoje.
Para atualizar um golden de propósito, veja testsupport/golden.py.
"""
import pytest

from automationstudio.core import State, map_from_json
from automationstudio.input_system import GlobalHotkeyManager
from automationstudio.project import ProjectManager
from testsupport import golden
from testsupport.cenarios import executar, registro
from testsupport.fakes import FakeMonitor
from testsupport.helpers import events_of, join_engine, legacy_database, pressed_balance

GOLDEN_DO_MAPA = {
    "Click genshin": "mapa_real_click_genshin",
    "Exemplo — Primeira automação": "mapa_real_exemplo_primeira_automacao",
    "Flins combo": "mapa_real_flins_combo",
}
NOMES = list(GOLDEN_DO_MAPA)
IDS = list(GOLDEN_DO_MAPA.values())


def _uma_passada(mapa):
    """Dois dos mapas reais repetem para sempre (repeat_count = -1): o golden guarda UMA passada."""
    mapa.repeat_count = 1
    return mapa


@pytest.mark.parametrize("nome", NOMES, ids=IDS)
def test_mapa_real_gera_sempre_a_mesma_sequencia_de_eventos(legacy_maps, make_engine, nome):
    execucao = executar(make_engine, _uma_passada(map_from_json(legacy_maps[nome])))
    assert execucao.erros == [] and execucao.sobras == {}, "o mapa real não pode falhar nem deixar tecla presa"
    assert execucao.estado == State.IDLE
    golden.comparar(GOLDEN_DO_MAPA[nome], registro(execucao.eventos, execucao.aplicativos))


def test_o_mapa_de_exemplo_abre_o_aplicativo_antes_de_digitar_e_nada_e_aberto_de_verdade(legacy_maps, make_engine):
    execucao = executar(make_engine, map_from_json(legacy_maps["Exemplo — Primeira automação"]))
    assert len(execucao.aplicativos) == 1 and execucao.aplicativos[0].lower().endswith(".exe"), execucao.aplicativos
    assert execucao.eventos and {acao for _t, acao, _a in execucao.eventos} == {"type_text"}
    texto = "".join(alvo for _t, _a, alvo in execucao.eventos)
    assert len(texto) == 186 and texto.startswith("Já pensou nas possibilidades?"), "o texto do exemplo chega inteiro, com acento, um caractere por vez"


@pytest.mark.parametrize("nome", NOMES, ids=IDS)
def test_o_mapa_vindo_do_banco_legado_gera_a_mesma_sequencia_de_eventos(tmp_path, make_engine, nome):
    # Fluxo do usuário: o banco que uma versão antiga gravou é aberto pela versão nova e o mapa é executado.
    legacy_database(tmp_path)
    gerente = ProjectManager(tmp_path)
    assert gerente.load_all() and gerente.load_errors == []
    execucao = executar(make_engine, _uma_passada(gerente.maps[nome]))
    assert execucao.erros == [] and execucao.sobras == {}
    golden.comparar(GOLDEN_DO_MAPA[nome], registro(execucao.eventos, execucao.aplicativos))


def test_velocidade_dobrada_e_tres_passadas_do_mapa_real(legacy_maps, make_engine):
    mapa = map_from_json(legacy_maps["Click genshin"])
    mapa.speed, mapa.repeat_count, mapa.repeat_interval = 2.0, 3, 0.25
    execucao = executar(make_engine, mapa)
    assert execucao.erros == [] and execucao.sobras == {}
    assert len(execucao.eventos) == 3 * 16, "oito comandos de tecla/botão = 16 eventos por passada, três passadas"
    golden.comparar("mapa_real_click_genshin_2x_tres_passadas", registro(execucao.eventos))


def _ligar_e_desligar_pelo_atalho(legacy_maps, make_engine, hook_backend, evento_do_segundo_aperto: int):
    """O usuário aperta o atalho do mapa (botão lateral 1), o mapa repete sem parar e, quando o backend acaba de receber o
    evento de número `evento_do_segundo_aperto`, ele aperta de novo. O aperto chega na thread do motor, no meio do envio.
    O monitor é falso, mas entrega o botão com o MESMO nome cru ("x1") que o monitor real entrega."""
    mapa = map_from_json(legacy_maps["Click genshin"])
    assert (mapa.hotkey, mapa.repeat_count) == ("MOUSE_X1", -1)
    motor, backend = make_engine(backend=hook_backend)
    monitor, estados_nos_apertos = FakeMonitor(), []

    def alternar():
        estados_nos_apertos.append(motor.state.state)
        if motor.state.state in (State.RUNNING, State.PAUSED):
            motor.stop()
        else:
            motor.run(mapa)

    gerente = GlobalHotkeyManager(monitor)
    gerente.register(mapa.hotkey, alternar)
    gerente.start()
    hook_backend.hooks[evento_do_segundo_aperto] = lambda: (monitor.click("x1", False), monitor.click("x1", True))
    monitor.click("x1", True)
    join_engine(motor)
    assert estados_nos_apertos == [State.IDLE, State.RUNNING], "o 1º aperto liga (motor parado) e o 2º desliga (motor executando)"
    assert motor.state.state == State.IDLE
    return events_of(backend), backend


def test_o_atalho_do_mapa_real_liga_e_desliga_a_repeticao_infinita(legacy_maps, make_engine, hook_backend):
    # Uma passada tem 16 eventos; o 19º é o mouse_down da 2ª passada: o atalho chega com o botão sendo pressionado.
    # O motor ainda não anotou o botão como pressionado quando a parada chega; quem solta é o `finally` da thread (item 2.01).
    eventos, backend = _ligar_e_desligar_pelo_atalho(legacy_maps, make_engine, hook_backend, 19)
    assert eventos[:16] == [tuple(e) for e in golden.carregar("mapa_real_click_genshin")["eventos"]], "a 1ª passada é a do mapa"
    assert pressed_balance(backend) == {}, "ao parar, nada pode ficar pressionado"
    assert eventos[-2:][0][1:] == ("mouse_down", "left") and eventos[-1][1:] == ("mouse_up", "left")
    golden.comparar("mapa_real_click_genshin_atalho_liga_e_desliga", registro(eventos))


def test_atalho_que_chega_no_meio_da_soltura_pode_repetir_a_soltura_mas_nunca_deixa_preso(legacy_maps, make_engine, hook_backend):
    # Caracterização: o 20º evento é o mouse_up. A parada chega ANTES de o motor anotar a soltura, então `stop` solta o botão
    # de novo (um mouse_up a mais). É inofensivo para o Windows e o motor documenta isso; o que NUNCA pode acontecer é
    # sobrar algo pressionado. Se o motor um dia evitar a soltura repetida, este teste deve mudar junto (Ponto 5).
    eventos, backend = _ligar_e_desligar_pelo_atalho(legacy_maps, make_engine, hook_backend, 20)
    ainda_pressionado = {alvo: n for alvo, n in pressed_balance(backend).items() if n > 0}
    assert ainda_pressionado == {}
    assert [e[1:] for e in eventos[-2:]] == [("mouse_up", "left")] * 2

