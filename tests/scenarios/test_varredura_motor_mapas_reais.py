"""Varredura do motor nos mapas reais: parar, pausar e retomar em qualquer ponto da execução.

O que o motor promete vale em QUALQUER evento da execução, e não só nos pontos que um teste escolhido à mão lembraria de
visitar. Este arquivo interrompe o motor logo depois de cada evento que ele envia (o gancho do `HookBackend` roda na
thread do motor, no instante exato) e confere, para cada ponto:

  1. parado (F12, botão Parar, tecla de ativação): nenhuma tecla e nenhum botão do mouse fica preso, o motor volta a IDLE,
     não avisa "terminou" (só o fim natural avisa) e depois da parada só se enviam SOLTURAS;
  2. pausado e retomado: os mesmos eventos, na mesma ordem, e cada evento seguinte deslocado exatamente pelo tempo da
     pausa (a pausa congela a linha do tempo; nada é pulado, repetido ou reordenado);
  3. pausado e depois parado: o mesmo que em 1, com as teclas seguradas durante a pausa (a pausa não solta nada; a
     parada, sim).

Os dois mapas reais com teclas e mouse são usados: 'Click genshin' (16 eventos por passada, repete sem parar) e 'Flins
combo' (2073 eventos por passada, com teclas e botões segurados ao mesmo tempo). O terceiro ('Exemplo — Primeira
automação', abrir aplicativo e digitar) só roda no Windows. Os mapas reais são o contrato permanente: se um deles um dia
mudar de forma, a varredura muda junto.

Por padrão cada teste visita uma AMOSTRA (todos os eventos do 'Click genshin'; do 'Flins combo', os 8 primeiros, os 8
últimos e um a cada 61, mais o começo da passada seguinte): cerca de 3 s no total. A varredura COMPLETA visita todos os
eventos (cerca de 6 mil execuções, 1 a 2 minutos). Rode-a antes de mexer na parada, na pausa ou na divisão do motor:

    AS_VARREDURA_COMPLETA=1 py tests/testsupport/run_minimal.py tests/scenarios/test_varredura_motor_mapas_reais.py

(ou com o pytest de verdade). A varredura completa (6 testes, 6297 execuções do motor: 2119 paradas, 2089 pausas com
retomada e 2089 pausas com parada) passou sem nenhum problema no código da 25.8 com as correções deste ramo (06/11/2026,
90 s no ambiente de desenvolvimento).
"""
from __future__ import annotations

import os
import threading

import pytest

from automationstudio.core import State, map_from_json
from automationstudio.input_system import ExecutionEngine, build_timeline
from testsupport.fake_clock import FakeClock
from testsupport.fakes import HookBackend
from testsupport.helpers import join_engine, pressed_balance

COMPLETA = os.environ.get("AS_VARREDURA_COMPLETA") == "1"
MAPAS = ["Click genshin", "Flins combo"]
SOLTURAS = ("key_up", "mouse_up")
PAUSA_S = 7.0  # tempo de relógio virtual entre pausar e retomar
PASSO_DA_AMOSTRA = 61


class _PausaObservavel(threading.Event):
    """O `_pause_event` do motor, avisando quando a thread do motor entra de verdade na espera da pausa.

    A pausa só vale quando o motor a percebe (no próximo ponto de verificação); avançar o relógio virtual antes disso
    seria "dormir" sem o motor saber, e o motor trataria os 7 s como atraso a recuperar. A thread da janela de verdade
    pausa e retoma com segundos de intervalo, então este aviso só existe para o teste não depender de um sleep."""

    def __init__(self):
        super().__init__()
        self.esperando = threading.Event()

    def wait(self, timeout=None):
        if not self.is_set():
            self.esperando.set()
        return super().wait(timeout)


def _motor():
    relogio = FakeClock()
    backend = HookBackend(clock=relogio)
    motor = ExecutionEngine(backend, clock=relogio)
    motor._pause_event = _PausaObservavel()
    motor._pause_event.set()
    return motor, backend, relogio


def _posicoes(total: int, extras: int) -> list[int]:
    """Eventos (1 a `total`, e `extras` da passada seguinte) em que o motor é interrompido."""
    if COMPLETA:
        return list(range(1, total + extras + 1))
    escolhidas = set(range(1, min(total, 8) + 1)) | set(range(max(1, total - 7), total + 1))
    escolhidas |= set(range(1, total + 1, PASSO_DA_AMOSTRA))
    escolhidas |= set(range(total + 1, total + extras + 1))
    return sorted(escolhidas)


def _mapa(legacy_maps, nome: str, uma_passada: bool):
    mapa = map_from_json(legacy_maps[nome])
    if uma_passada:
        mapa.repeat_count = 1
    return mapa


def _relatar(problemas: list) -> str:
    return f"{len(problemas)} ponto(s) com problema; os primeiros: " + "; ".join(str(p) for p in problemas[:5])


@pytest.mark.parametrize("nome", MAPAS, ids=MAPAS)
def test_parado_depois_de_qualquer_evento_nada_fica_preso(legacy_maps, nome):
    mapa = _mapa(legacy_maps, nome, uma_passada=False)  # repete sem parar: o começo da passada seguinte também é visitado
    total = len(build_timeline(mapa))
    problemas = []
    for k in _posicoes(total, extras=15 if COMPLETA else 2):
        motor, backend, _relogio = _motor()
        fins = []
        motor.on_finished.append(lambda fins=fins: fins.append(1))
        backend.hooks[k] = motor.stop  # na thread do motor, logo depois do k-ésimo evento enviado
        motor.run(mapa)
        join_engine(motor, timeout=60)
        presas = {alvo: n for alvo, n in pressed_balance(backend).items() if n > 0}
        enviado_depois = [e for e in backend.events[k:] if e[1] not in SOLTURAS]
        if presas or enviado_depois or fins or motor.state.state != State.IDLE or len(backend.events) < k:
            problemas.append((k, presas, enviado_depois[:2], len(fins), motor.state.state.name))
    assert not problemas, _relatar(problemas)


@pytest.mark.parametrize("nome", MAPAS, ids=MAPAS)
def test_pausado_depois_de_qualquer_evento_a_retomada_continua_do_mesmo_ponto(legacy_maps, nome):
    mapa = _mapa(legacy_maps, nome, uma_passada=True)
    motor_ref, backend_ref, _relogio_ref = _motor()
    motor_ref.run(mapa)
    join_engine(motor_ref, timeout=60)
    ref = [(round(t, 6), acao, alvo) for t, acao, alvo in backend_ref.events]
    assert len(ref) == len(build_timeline(mapa))
    problemas = []
    for k in _posicoes(len(ref), extras=0):
        motor, backend, relogio = _motor()
        pausou = threading.Event()
        backend.hooks[k] = lambda motor=motor, pausou=pausou: (motor.pause(), pausou.set())
        motor.run(mapa)
        assert pausou.wait(30), f"o motor não chegou ao evento {k}"
        if k < len(ref):  # pausa no último evento: a execução termina sem chegar a esperar a pausa
            assert motor._pause_event.esperando.wait(30), f"o motor não percebeu a pausa no evento {k}"
        relogio.advance(PAUSA_S)
        motor.resume()
        join_engine(motor, timeout=60)
        obtido = [(round(t, 6), acao, alvo) for t, acao, alvo in backend.events]
        esperado = [(t if i < k else round(t + PAUSA_S, 6), acao, alvo) for i, (t, acao, alvo) in enumerate(ref)]
        if obtido != esperado or pressed_balance(backend) or motor.state.state != State.IDLE:
            primeiro = next((i for i, (o, e) in enumerate(zip(obtido, esperado)) if o != e), None)
            problemas.append((k, len(obtido), len(esperado), primeiro, dict(pressed_balance(backend))))
    assert not problemas, _relatar(problemas)


@pytest.mark.parametrize("nome", MAPAS, ids=MAPAS)
def test_pausado_depois_de_qualquer_evento_e_parado_nada_fica_preso(legacy_maps, nome):
    mapa = _mapa(legacy_maps, nome, uma_passada=True)
    total = len(build_timeline(mapa))
    problemas = []
    for k in _posicoes(total, extras=0):
        motor, backend, _relogio = _motor()
        pausou = threading.Event()
        backend.hooks[k] = lambda motor=motor, pausou=pausou: (motor.pause(), pausou.set())
        motor.run(mapa)
        assert pausou.wait(30), f"o motor não chegou ao evento {k}"
        motor.stop(wait=True)
        viva = motor._thread is not None and motor._thread.is_alive()
        if k == total:
            # Pausado no último evento, a execução acaba sozinha ao mesmo tempo em que a parada chega: se o fim natural
            # venceu, `stop` encontra o motor em IDLE e volta sem esperar, e a thread ainda está nos últimos passos
            # (os observadores de fim). Só nesse ponto a thread pode estar viva na volta de `stop(wait=True)`.
            join_engine(motor, timeout=30)
            viva = motor._thread.is_alive()
        presas = {alvo: n for alvo, n in pressed_balance(backend).items() if n > 0}
        if presas or viva or motor.state.state != State.IDLE:
            problemas.append((k, presas, viva, motor.state.state.name))
    assert not problemas, _relatar(problemas)
