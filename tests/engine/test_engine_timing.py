"""Motor de execução: tempos, velocidade, repetição e mapas inválidos, tudo com relógio virtual.

O relógio virtual (FakeClock) não espera de verdade: um mapa de 10 s roda em milissegundos e cada evento sai no
instante exato da timeline. Por isso as asserções de tempo são exatas, sem tolerância de agendador.
"""
import time

import pytest

from automationstudio.core import AutomationMap, Command, InputType, State
from testsupport.helpers import events_of, key, make_map, run_to_end


def _rodar(make_engine, mapa):
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, mapa)
    assert terminou and not erros, erros
    return motor, backend


def test_tempos_exatos_com_relogio_virtual(make_engine, fake_clock):
    mapa = make_map([key("A", 0.0, 0.2), key("B", 0.9, 0.2), key("C", 1.0, 0.2)])
    inicio = time.perf_counter()
    _motor, backend = _rodar(make_engine, mapa)
    assert events_of(backend) == [
        (0.0, "key_down", "A"), (0.2, "key_up", "A"), (0.9, "key_down", "B"),
        (1.0, "key_down", "C"), (1.1, "key_up", "B"), (1.2, "key_up", "C")]
    assert fake_clock.monotonic() == pytest.approx(1.2, abs=1e-6)
    assert time.perf_counter() - inicio < 5.0, "o relógio virtual não pode esperar tempo real"


def test_tecla_mantem_a_duracao_e_a_lacuna_planejadas(make_engine):
    # Item 1.08 do Ponto 1, agora exato: B fica 0,2 s pressionada e C começa 0,1 s depois de B.
    _motor, backend = _rodar(make_engine, make_map([key("B", 0.9, 0.2), key("C", 1.0, 0.2)]))
    t = {(a, alvo): quando for quando, a, alvo in events_of(backend)}
    assert round(t[("key_up", "B")] - t[("key_down", "B")], 3) == 0.2
    assert round(t[("key_down", "C")] - t[("key_down", "B")], 3) == 0.1


@pytest.mark.parametrize("velocidade", [0.5, 1.0, 2.0, 4.0])
def test_velocidade_escala_todos_os_tempos(make_engine, velocidade):
    mapa = make_map([key("A", 0.0, 0.2), key("B", 1.0, 0.4)], speed=velocidade)
    _motor, backend = _rodar(make_engine, mapa)
    previsto = [(0.0, "key_down", "A"), (0.2, "key_up", "A"), (1.0, "key_down", "B"), (1.4, "key_up", "B")]
    assert [(round(t * velocidade, 3), a, alvo) for t, a, alvo in events_of(backend)] == previsto


def test_repeticao_com_intervalo_entre_as_passadas(make_engine):
    mapa = make_map([key("A", 0.0, 0.1)], repeat_count=3, repeat_interval=1.0)
    _motor, backend = _rodar(make_engine, mapa)
    assert events_of(backend) == [
        (0.0, "key_down", "A"), (0.1, "key_up", "A"),
        (1.1, "key_down", "A"), (1.2, "key_up", "A"),
        (2.2, "key_down", "A"), (2.3, "key_up", "A")]


def test_repeticao_sem_intervalo_emenda_as_passadas(make_engine):
    mapa = make_map([key("A", 0.0, 0.1)], repeat_count=2, repeat_interval=0.0)
    _motor, backend = _rodar(make_engine, mapa)
    assert events_of(backend) == [
        (0.0, "key_down", "A"), (0.1, "key_up", "A"), (0.1, "key_down", "A"), (0.2, "key_up", "A")]


def test_eventos_no_mesmo_instante_soltam_antes_de_pressionar(make_engine):
    # A termina em 0,5 e A começa em 0,5: a tecla é solta e só depois pressionada, nunca o contrário.
    _motor, backend = _rodar(make_engine, make_map([key("A", 0.0, 0.5), key("A", 0.5, 0.2)]))
    assert events_of(backend)[1:3] == [(0.5, "key_up", "A"), (0.5, "key_down", "A")]


def test_comando_desativado_nao_chega_ao_backend(make_engine):
    mapa = make_map([key("A", 0.0, 0.2, enabled=False), key("B", 0.1, 0.2)])
    _motor, backend = _rodar(make_engine, mapa)
    assert [alvo for _t, _a, alvo in events_of(backend)] == ["B", "B"]


def test_mapa_sem_comandos_nao_inicia_nada(make_engine):
    motor, backend = make_engine()
    chamadas = []
    motor.on_finished.append(lambda: chamadas.append("fim"))
    motor.run(AutomationMap(name="Vazio", commands=[]))
    assert motor._thread is None and motor.state.state == State.IDLE
    assert backend.events == [] and chamadas == []


def test_mapa_invalido_levanta_e_nao_muda_o_estado(make_engine):
    motor, backend = make_engine()
    invalido = make_map([Command(type=InputType.KEY, target="A", start=0.0, duration=0.0)])  # soltar sem duração
    with pytest.raises(ValueError, match="Mapa inválido"):
        motor.run(invalido)
    assert motor.state.state == State.IDLE and motor._thread is None and backend.events == []


def test_estados_de_um_fim_natural(make_engine):
    from testsupport.helpers import record_states
    motor, _backend = make_engine()
    vistos = record_states(motor.state)
    terminou, erros = run_to_end(motor, make_map([key("A", 0.0, 0.1)]))
    assert terminou and not erros
    assert vistos == [(State.IDLE, State.RUNNING), (State.RUNNING, State.STOPPING), (State.STOPPING, State.IDLE)]


def test_progresso_informa_tempo_do_evento_e_total(make_engine):
    motor, _backend = make_engine()
    progresso = []
    motor.on_progress.append(lambda atual, total: progresso.append((round(atual, 3), round(total, 3))))
    terminou, _ = run_to_end(motor, make_map([key("A", 0.0, 0.2), key("B", 0.5, 0.2)]))
    assert terminou
    assert progresso == [(0.0, 0.7), (0.2, 0.7), (0.5, 0.7), (0.7, 0.7)]


def test_observadores_com_erro_nao_derrubam_a_execucao(make_engine):
    motor, backend = make_engine()

    def quebra(*_args):
        raise RuntimeError("observador defeituoso")

    motor.on_event.append(quebra)
    motor.on_progress.append(quebra)
    terminou, erros = run_to_end(motor, make_map([key("A", 0.0, 0.1)]))
    assert terminou and not erros
    assert [a for _t, a, _x in events_of(backend)] == ["key_down", "key_up"]


@pytest.mark.slow
def test_timeline_com_dez_mil_eventos_termina_rapido(make_engine):
    comandos = [key("A", i * 0.01, 0.005) for i in range(5000)]  # 5.000 comandos = 10.000 eventos
    inicio = time.perf_counter()
    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, make_map(comandos), timeout=60.0)
    assert terminou and not erros
    assert len(backend.events) == 10000
    assert time.perf_counter() - inicio < 30.0
