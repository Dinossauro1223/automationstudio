"""O relógio virtual (testsupport/fake_clock.py) é a base de todos os testes de tempo: ele mesmo precisa ser confiável."""
import threading

import pytest

from testsupport.fake_clock import FakeClock


def test_comeca_no_valor_pedido():
    assert FakeClock().monotonic() == 0.0 and FakeClock(start=100.5).monotonic() == 100.5


def test_sleep_avanca_o_tempo_e_fica_registrado():
    relogio = FakeClock()
    relogio.sleep(0.25)
    relogio.sleep(1.0)
    assert relogio.monotonic() == 1.25 and relogio.sleeps == [0.25, 1.0]


def test_advance_avanca_sem_contar_como_espera_do_motor():
    relogio = FakeClock()
    relogio.advance(2.5)
    assert relogio.monotonic() == 2.5 and relogio.sleeps == []


def test_chamar_o_relogio_como_funcao_devolve_o_tempo_atual():
    relogio = FakeClock()  # o Recorder recebe `clock=` como função sem argumentos
    relogio.advance(3.0)
    assert relogio() == 3.0 and relogio.__call__ == relogio.monotonic


@pytest.mark.parametrize("pedido", [0, 1e-17, -1.0, -1e-9])
def test_toda_espera_avanca_pelo_menos_um_nanossegundo(pedido):
    # Sem isto um laço do motor com sleep(1e-17) giraria para sempre: o tempo nunca chegaria ao fim.
    relogio = FakeClock()
    antes = relogio.monotonic()
    relogio.sleep(pedido)
    assert relogio.monotonic() > antes


def test_o_tempo_nunca_anda_para_tras_com_esperas_negativas_ou_zero():
    relogio = FakeClock()
    leituras = []
    for pedido in (0.5, 0, -2.0, 1e-12, 0.1):
        relogio.sleep(pedido)
        leituras.append(relogio.monotonic())
    assert leituras == sorted(leituras)


def test_soma_de_muitas_esperas_pequenas_nao_acumula_erro_de_ponto_flutuante():
    relogio = FakeClock()
    for _ in range(10_000):
        relogio.sleep(0.001)
    assert relogio.monotonic() == 10.0  # com float somaria 9.999999999999831


def test_varias_threads_dormindo_somam_exatamente():
    relogio = FakeClock()

    def dormir():
        for _ in range(1000):
            relogio.sleep(0.001)

    threads = [threading.Thread(target=dormir) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert relogio.monotonic() == 8.0 and len(relogio.sleeps) == 8000
