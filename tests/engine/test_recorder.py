"""Gravador: do evento físico ao Command, com relógio virtual e um monitor falso (sem hooks globais).

Cada teste dirige o monitor falso (`mon.press`, `mon.click`, `mon.move`...) e avança o relógio virtual: o tempo
gravado é exato e nenhum teste depende do agendador do sistema.
"""
import pytest

from automationstudio.core import ActionType, AutomationMap, Command, InputType, State, StateManager, build_timeline
from automationstudio.input_system import Recorder, RecorderError, RecorderFilters
from testsupport.helpers import events_of, run_to_end


def _resumo(comandos):
    return [(c.type.value, c.target, round(c.start, 3), round(c.duration, 3), c.group) for c in comandos]


# ----------------------------------------------------------------------------------------- teclado
def test_teclas_sobrepostas_viram_comandos_do_mesmo_grupo(gravar, fake_clock):
    rec, mon, _ = gravar()
    rec.start()
    mon.press("SHIFT"); fake_clock.advance(0.1)
    mon.press("E"); fake_clock.advance(0.1)
    mon.release("E"); fake_clock.advance(0.3)
    mon.release("SHIFT"); fake_clock.advance(0.1)
    mon.press("F"); fake_clock.advance(0.2)
    mon.release("F")
    assert _resumo(rec.stop()) == [
        ("key", "SHIFT", 0.0, 0.5, "A"), ("key", "E", 0.1, 0.1, "A"), ("key", "F", 0.6, 0.2, "B")]


def test_repeticao_automatica_do_sistema_conta_so_a_primeira_pressao(gravar, fake_clock):
    rec, mon, _ = gravar()
    rec.start()
    mon.press("A"); fake_clock.advance(0.05); mon.press("A"); fake_clock.advance(0.05); mon.press("A")
    fake_clock.advance(0.1); mon.release("A")
    assert _resumo(rec.stop()) == [("key", "A", 0.0, 0.2, "A")]


def test_soltar_sem_ter_visto_a_pressao_e_ignorado(gravar):
    rec, mon, _ = gravar()
    rec.start()
    mon.release("Q")
    assert rec.stop() == []


def test_tecla_ainda_pressionada_ao_parar_e_fechada_no_instante_da_parada(gravar, fake_clock):
    rec, mon, _ = gravar()
    rec.start()
    mon.press("A"); fake_clock.advance(0.4)
    assert _resumo(rec.stop()) == [("key", "A", 0.0, 0.4, "A")]


def test_filtros_de_teclado(gravar, fake_clock):
    rec, mon, _ = gravar(RecorderFilters(record_key_duration=False, ignored_keys=frozenset({"F8"})))
    rec.start()
    mon.press("A"); fake_clock.advance(0.3); mon.release("A")
    mon.press("F8"); fake_clock.advance(0.1); mon.release("F8")
    assert _resumo(rec.stop()) == [("key", "A", 0.0, 0.0, "A")]  # F8 ignorada; duração zerada


def test_com_captura_de_teclado_desligada_nada_e_gravado(gravar):
    rec, mon, _ = gravar(RecorderFilters(capture_keyboard=False))
    rec.start()
    mon.press("A"); mon.release("A")
    assert rec.stop() == []


# ----------------------------------------------------------------------------------------- mouse
def test_botoes_do_mouse_usam_o_nome_cru_e_em_minusculas(gravar, fake_clock):
    # D1 (25.5): o gravador guarda o nome do sistema ("x1"), não o nome trocado da exibição.
    rec, mon, _ = gravar(RecorderFilters(ignored_mouse_buttons=frozenset({"middle"})))
    rec.start()
    mon.click("x1", True); fake_clock.advance(0.1); mon.click("x1", False)
    mon.click("middle", True); mon.click("middle", False)
    mon.click("LEFT", True); fake_clock.advance(0.05); mon.click("LEFT", False)
    assert _resumo(rec.stop()) == [("mouse_button", "x1", 0.0, 0.1, "A"), ("mouse_button", "left", 0.1, 0.05, "B")]


def test_rolagem_vira_comando_com_dx_e_dy(gravar, fake_clock):
    rec, mon, _ = gravar()
    rec.start()
    fake_clock.advance(0.2); mon.scroll(1, -2)
    (comando,) = rec.stop()
    assert (comando.type, comando.action, comando.start, comando.scroll_dx, comando.scroll_dy) == (
        InputType.MOUSE_SCROLL, ActionType.PRESS, pytest.approx(0.2), 1, -2)


def test_movimento_em_linha_reta_vira_um_unico_comando_com_trajeto_simplificado(gravar, fake_clock):
    rec, mon, _ = gravar(RecorderFilters(mouse_jitter_px=3, mouse_sample_interval_ms=8))
    rec.start()
    for i in range(11):
        mon.move(i * 10, i * 5); fake_clock.advance(0.01)
    (comando,) = rec.stop()
    assert comando.type == InputType.MOUSE_MOVE and comando.merged_move
    assert (comando.x, comando.y) == (0, 0)
    assert [(p["x"], p["y"]) for p in comando.mouse_path] == [(0, 0), (100, 50), (100, 50)]
    assert comando.mouse_path[0]["t"] == 0.0 and comando.mouse_path[-1]["t"] == 1.0


def test_amostragem_respeita_o_intervalo_e_o_cursor_termina_no_destino(gravar, fake_clock):
    # D3 (25.5): amostras mais próximas que o intervalo são descartadas, mas a última vira o fim do trajeto.
    rec, mon, _ = gravar(RecorderFilters(mouse_jitter_px=3, mouse_sample_interval_ms=100))
    rec.start()
    for x in (0, 50, 100, 150, 200):
        mon.move(x, 0); fake_clock.advance(0.001)
    (comando,) = rec.stop()
    assert [(p["x"], p["y"]) for p in comando.mouse_path] == [(0, 0), (200, 0), (200, 0)]


def test_tremor_abaixo_do_limite_de_pixels_e_ignorado(gravar, fake_clock):
    rec, mon, _ = gravar(RecorderFilters(mouse_jitter_px=5, mouse_sample_interval_ms=0))
    rec.start()
    mon.move(0, 0); fake_clock.advance(0.1)
    mon.move(1, 1); fake_clock.advance(0.1)
    mon.move(2, 0); fake_clock.advance(0.1)
    mon.move(30, 0)
    (comando,) = rec.stop()
    assert [(p["x"], p["y"]) for p in comando.mouse_path] == [(0, 0), (30, 0)]
    assert comando.duration == pytest.approx(0.3)


def test_tremor_depois_de_chegar_nao_move_o_destino(gravar, fake_clock):
    # O tremor é medido a partir do último ponto GRAVADO. Sem o filtro, o ponto a 1 px de diferença viraria o destino
    # do movimento (a simplificação do trajeto sempre preserva o último ponto que recebeu).
    rec, mon, _ = gravar(RecorderFilters(mouse_jitter_px=5, mouse_sample_interval_ms=0))
    rec.start()
    mon.move(0, 0); fake_clock.advance(0.1)
    mon.move(100, 0); fake_clock.advance(0.1)
    mon.move(101, 1)  # tremor de 1 px depois de chegar
    (comando,) = rec.stop()
    assert [(p["x"], p["y"]) for p in comando.mouse_path] == [(0, 0), (100, 0), (100, 0)]


def test_sem_mesclar_cada_movimento_vira_um_comando(gravar, fake_clock):
    rec, mon, _ = gravar(RecorderFilters(merge_mouse_moves=False))
    rec.start()
    mon.move(1, 2); fake_clock.advance(0.1); mon.move(3, 4)
    comandos = rec.stop()
    assert [(c.x, c.y, round(c.start, 3), c.merged_move) for c in comandos] == [(1, 2, 0.0, False), (3, 4, 0.1, False)]


def test_clique_fecha_o_movimento_mesclado_antes_de_gravar_o_botao(gravar, fake_clock):
    rec, mon, _ = gravar()
    rec.start()
    mon.move(0, 0); fake_clock.advance(0.1); mon.move(100, 0); fake_clock.advance(0.1)
    mon.click("left", True); fake_clock.advance(0.1); mon.click("left", False)
    mover, botao = rec.stop()
    assert (mover.type, round(mover.duration, 3)) == (InputType.MOUSE_MOVE, 0.2)
    assert (botao.type, round(botao.start, 3)) == (InputType.MOUSE_BUTTON, 0.2)


# ----------------------------------------------------------------------------------------- pausa
def test_pausa_nao_conta_no_tempo_e_descarta_eventos_do_periodo(gravar, fake_clock):
    rec, mon, _ = gravar()
    rec.start()
    mon.press("A"); fake_clock.advance(0.2)
    rec.pause()
    assert rec.is_paused
    fake_clock.advance(5.0)
    mon.press("B"); mon.release("B")  # durante a pausa: ignorados
    rec.resume()
    fake_clock.advance(0.1); mon.press("C"); fake_clock.advance(0.1); mon.release("C")
    assert _resumo(rec.stop()) == [("key", "A", 0.0, 0.2, "A"), ("key", "C", 0.3, 0.1, "B")]


def test_pausar_e_retomar_sem_gravacao_nao_faz_nada(gravar):
    rec, _mon, _ = gravar()
    rec.pause()
    rec.resume()
    assert not rec.is_recording and not rec.is_paused


# ----------------------------------------------------------------------------------------- ciclo de vida
def test_estados_e_monitor_no_ciclo_de_gravacao(gravar):
    rec, mon, estado = gravar()
    rec.start()
    assert estado.state == State.RECORDING and mon.running and rec.is_recording
    assert len(mon.on_key) == len(mon.on_mouse_button) == len(mon.on_mouse_move) == len(mon.on_mouse_scroll) == 1
    rec.start()  # segundo start é ignorado
    assert len(mon.on_key) == 1
    rec.stop()
    assert estado.state == State.IDLE and not rec.is_recording
    assert not (mon.on_key or mon.on_mouse_button or mon.on_mouse_move or mon.on_mouse_scroll), "callbacks vazaram"


def test_parar_sem_gravar_devolve_lista_vazia(gravar):
    rec, _mon, estado = gravar()
    assert rec.stop() == [] and estado.state == State.IDLE


@pytest.mark.parametrize("ocupado", [State.RUNNING, State.PAUSED, State.RECORDING])
def test_nao_grava_com_o_programa_ocupado(gravar, ocupado):
    rec, mon, estado = gravar(estado=StateManager(ocupado))
    with pytest.raises(RecorderError):
        rec.start()
    assert estado.state == ocupado and not mon.on_key and not rec.is_recording


def test_cancelar_descarta_tudo_e_volta_a_idle(gravar):
    rec, mon, estado = gravar()
    rec.start()
    mon.press("A")
    rec.cancel()
    assert estado.state == State.IDLE and not rec.is_recording and not mon.on_key
    assert rec.stop() == []


def test_foto_da_gravacao_inclui_pressoes_abertas_e_nao_consome(gravar, fake_clock):
    rec, mon, _ = gravar()
    rec.start()
    mon.press("A"); fake_clock.advance(0.2); mon.release("A"); mon.press("B"); fake_clock.advance(0.1)
    foto = rec.snapshot_commands()
    assert [(c.target, round(c.start, 3), round(c.duration, 3)) for c in foto] == [("A", 0.0, 0.2), ("B", 0.2, 0.1)]
    assert len(rec.stop()) == 2  # a foto não consumiu nada


def test_foto_do_movimento_em_andamento_termina_onde_o_cursor_parou(gravar, fake_clock):
    # D3 (25.5): a regra de `stop()` (a última amostra descartada pelo intervalo vira o fim do trajeto) vale também
    # para a pré-visualização ao vivo da tabela; sem ela, o trecho final do movimento só apareceria ao parar.
    rec, mon, _ = gravar(RecorderFilters(mouse_jitter_px=3, mouse_sample_interval_ms=100))
    rec.start()
    for x in (0, 50, 100, 150, 200):
        mon.move(x, 0); fake_clock.advance(0.001)
    (foto,) = rec.snapshot_commands()
    assert foto.merged_move
    assert [(p["x"], p["y"]) for p in foto.mouse_path] == [(0, 0), (200, 0)]
    (final,) = rec.stop()  # a foto não consumiu nada
    assert [(p["x"], p["y"]) for p in final.mouse_path] == [(0, 0), (200, 0), (200, 0)]


def test_contagem_de_eventos(gravar, fake_clock):
    rec, mon, _ = gravar()
    rec.start()
    mon.press("A"); mon.release("A"); mon.scroll(0, 1); mon.move(1, 1); mon.move(50, 50)
    assert rec.event_count == 4  # 1 tecla + 1 rolagem + 2 amostras de mouse
    rec.cancel()


# ----------------------------------------------------------------------------------------- unidades puras
def test_letras_de_grupo_seguem_a_ordem_a_z_aa_ab():
    # Comandos que não se sobrepõem ganham um grupo novo cada um: A..Z, depois AA, AB...
    comandos = [Command(type=InputType.KEY, target="A", start=i * 1.0, duration=0.5) for i in range(28)]
    Recorder._assign_groups(comandos)
    letras = [c.group for c in comandos]
    assert letras[:3] == ["A", "B", "C"] and letras[25:28] == ["Z", "AA", "AB"]


def test_comandos_todos_sobrepostos_ficam_no_mesmo_grupo():
    comandos = [Command(type=InputType.KEY, target="A", start=0.0, duration=10.0) for _ in range(27)]
    Recorder._assign_groups(comandos)
    assert {c.group for c in comandos} == {"A"}


def test_simplificacao_de_trajeto_preserva_extremos_e_curvas():
    reta = [(0.0, 0, 0), (0.1, 10, 10), (0.2, 20, 20), (0.3, 30, 30)]
    assert Recorder._simplify_mouse_path(reta, 3.0) == [reta[0], reta[-1]]
    curva = [(0.0, 0, 0), (0.1, 50, 0), (0.2, 50, 50)]
    assert Recorder._simplify_mouse_path(curva, 3.0) == curva  # só 3 pontos e uma esquina: nada a remover
    esquina = [(0.0, 0, 0), (0.1, 25, 0), (0.2, 50, 0), (0.3, 50, 25), (0.4, 50, 50)]
    assert (50, 0) in [(x, y) for _t, x, y in Recorder._simplify_mouse_path(esquina, 3.0)]


# ----------------------------------------------------------------------------------------- ida e volta
def test_gravar_e_reproduzir_devolve_os_mesmos_tempos(gravar, fake_clock, make_engine):
    rec, mon, _ = gravar(RecorderFilters(mouse_jitter_px=3, mouse_sample_interval_ms=0))
    rec.start()
    mon.press("CTRL"); fake_clock.advance(0.2)
    mon.press("C"); fake_clock.advance(0.1); mon.release("C"); fake_clock.advance(0.1); mon.release("CTRL")
    fake_clock.advance(0.3)
    mon.click("left", True); fake_clock.advance(0.05); mon.click("left", False)
    comandos = rec.stop()

    motor, backend = make_engine()
    terminou, erros = run_to_end(motor, AutomationMap(name="Gravado", commands=comandos, repeat_count=1))
    assert terminou and not erros
    previsto = [(round(e.time, 3), e.kind.value, e.target) for e in build_timeline(AutomationMap(name="x", commands=comandos))]
    assert events_of(backend) == previsto
    assert previsto == [
        (0.0, "key_down", "CTRL"), (0.2, "key_down", "C"), (0.3, "key_up", "C"), (0.4, "key_up", "CTRL"),
        (0.7, "mouse_down", "left"), (0.75, "mouse_up", "left")]
