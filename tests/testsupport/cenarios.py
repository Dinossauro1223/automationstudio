"""Auxiliares dos cenários ponta a ponta (tests/scenarios): rodar um mapa inteiro e descrever o que saiu."""
from __future__ import annotations

import collections
from dataclasses import dataclass

from testsupport.helpers import events_of, join_engine, pressed_balance, run_to_end


@dataclass
class Execucao:
    eventos: list        # (tempo, ação, alvo) que o backend recebeu
    aplicativos: list    # alvos que o motor teria aberto (nunca são abertos de verdade)
    erros: list          # exceções que o motor reportou
    sobras: dict         # teclas e botões que terminaram pressionados ({} = nada preso)
    estado: object       # estado final do motor


def desligar_aplicativos(motor) -> list:
    """Troca o lançamento e a espera de aplicativos do motor por dublês e devolve a lista onde cada abertura é anotada."""
    abertos: list = []
    motor._launch_application = lambda alvo: (abertos.append(alvo), 4242)[1]
    motor._wait_for_process = lambda evento, expected_pid=None: None
    return abertos


def executar(make_engine, mapa, backend=None) -> Execucao:
    """Roda o mapa até o fim natural com o relógio virtual. Aplicativos NUNCA são abertos: o lançamento só é anotado."""
    motor, backend = make_engine(backend=backend)
    abertos = desligar_aplicativos(motor)
    terminou, erros = run_to_end(motor, mapa)
    assert terminou, "o mapa não terminou no prazo"
    join_engine(motor)
    return Execucao(events_of(backend), abertos, erros, pressed_balance(backend), motor.state.state)


def resumo(eventos) -> dict:
    """O que quem lê o golden confere de relance: total de eventos, último instante e contagem por ação."""
    por_acao = collections.Counter(acao for _t, acao, _alvo in eventos)
    return {"total": len(eventos), "ultimo_instante": max((t for t, _a, _x in eventos), default=0.0),
            "por_acao": dict(sorted(por_acao.items()))}


def juntar_texto(eventos) -> list:
    """Letras digitadas em sequência, no mesmo instante, viram uma entrada só: o golden de um texto de 186 caracteres fica
    legível. Só junta o que o motor mandou junto (mesmo instante, em seguida); letras em instantes diferentes continuam separadas."""
    juntos: list = []
    for tempo, acao, alvo in eventos:
        if juntos and acao == "type_text" and juntos[-1][1] == "type_text" and juntos[-1][0] == tempo:
            juntos[-1] = (tempo, acao, juntos[-1][2] + alvo)
        else:
            juntos.append((tempo, acao, alvo))
    return juntos


def registro(eventos, aplicativos=()) -> dict:
    """Estrutura gravada nos golden dos cenários do motor: resumo (sobre os eventos como o backend os recebeu), aplicativos
    que seriam abertos e os eventos, com o texto digitado agrupado por instante."""
    return {"resumo": resumo(eventos), "aplicativos_abertos": list(aplicativos), "eventos": juntar_texto(eventos)}
