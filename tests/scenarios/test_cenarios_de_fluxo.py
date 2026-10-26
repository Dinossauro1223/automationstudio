"""Cenários de fluxo: o caminho que um usuário percorre, atravessando várias camadas do programa de uma vez.

  - gravar → salvar no banco → reabrir o banco → executar;
  - exportar e importar um mapa real por arquivo;
  - abrir um aplicativo → esperar → digitar → atalho de teclado (com condição de atraso);
  - um mapa completo executado pelo backend do Windows (USER32.SendInput FALSO).

Cada cenário compara a saída com um arquivo de referência (tests/data/golden) e, onde o valor importa para o usuário,
também afirma o que se espera de forma explícita (assim um golden atualizado sem leitura não "carimba" um valor errado).
"""
import pytest

from automationstudio.conditions import WaitCondition, WaitConditionType
from automationstudio.core import ActionType, AutomationMap, Command, InputType, map_from_json
from automationstudio.input_system import RecorderFilters, Win32InputBackend
from automationstudio.project import ProjectManager
from testsupport import golden
from testsupport.cenarios import desligar_aplicativos, executar, registro
from testsupport.fakes import FakeKernel32, FakeUser32Abnt2
from testsupport.helpers import events_of, join_engine, run_to_end

MASCARA_32 = 0xFFFFFFFF  # mouseData é DWORD no Windows (32 bits); no Linux o c_ulong tem 64: o golden guarda o valor de 32


# ----------------------------------------------------------------------------------------- gravar → banco → executar
def _gravar_uma_sessao(gravar, fake_clock):
    """O usuário aperta Ctrl+C, arrasta o mouse em linha reta, clica com o botão lateral 1 e rola a roda duas linhas."""
    gravador, monitor, _estado = gravar(RecorderFilters(mouse_jitter_px=3, mouse_sample_interval_ms=0))
    gravador.start()
    monitor.press("CTRL"); fake_clock.advance(0.2)
    monitor.press("C"); fake_clock.advance(0.1); monitor.release("C"); fake_clock.advance(0.1); monitor.release("CTRL")
    fake_clock.advance(0.3)
    for x in (100, 140, 180, 220):
        monitor.move(x, 300); fake_clock.advance(0.05)
    monitor.click("x1", True); fake_clock.advance(0.05); monitor.click("x1", False)
    fake_clock.advance(0.2)
    monitor.scroll(0, -2)
    return gravador.stop()


def test_gravar_salvar_reabrir_e_executar_reproduz_o_que_foi_gravado(gravar, fake_clock, make_engine, tmp_path):
    comandos = _gravar_uma_sessao(gravar, fake_clock)
    mapa = AutomationMap(name="Gravada", commands=comandos, hotkey="F6", repeat_count=1)
    assert mapa.validate() == []
    direto = executar(make_engine, mapa)

    ProjectManager(tmp_path).save_map(mapa)  # fecha o programa...
    reaberto = ProjectManager(tmp_path)      # ...e abre de novo: a única ponte é o arquivo do banco
    assert reaberto.load_all() and reaberto.load_errors == []
    pelo_banco = executar(make_engine, reaberto.maps["Gravada"])

    assert direto.erros == pelo_banco.erros == [] and direto.sobras == pelo_banco.sobras == {}
    assert pelo_banco.eventos == direto.eventos, "salvar e reabrir não pode mudar o que o motor executa"
    sem_movimento = [e for e in pelo_banco.eventos if e[1] != "mouse_move"]
    assert sem_movimento == [
        (0.0, "key_down", "CTRL"), (0.2, "key_down", "C"), (0.3, "key_up", "C"), (0.4, "key_up", "CTRL"),
        (0.9, "mouse_down", "x1"), (0.95, "mouse_up", "x1"), (1.15, "mouse_scroll", (0, -2))], "o que o usuário fez, no instante em que fez"
    movimentos = [e for e in pelo_banco.eventos if e[1] == "mouse_move"]
    assert (movimentos[0][0], movimentos[0][2][:2]) == (0.7, (100, 300)), "o arrasto começa onde o mouse estava, no instante em que começou"
    assert (movimentos[-1][0], movimentos[-1][2][:2]) == (0.9, (220, 300)), "e termina no destino, quando o clique o fecha"
    golden.comparar("gravacao_salva_reaberta_e_executada", registro(pelo_banco.eventos))


def test_exportar_e_importar_o_mapa_real_mantem_a_execucao(legacy_maps, make_engine, tmp_path):
    original = map_from_json(legacy_maps["Flins combo"])
    origem = ProjectManager(tmp_path / "origem")
    origem.save_map(original)
    arquivo = origem.export_map("Flins combo", tmp_path / "flins.json")
    destino = ProjectManager(tmp_path / "destino")
    importado = destino.import_map(arquivo)
    assert [c.id for c in importado.commands] == [c.id for c in original.commands]
    importado.repeat_count = 1
    execucao = executar(make_engine, importado)
    assert execucao.erros == [] and execucao.sobras == {}
    golden.comparar("mapa_real_flins_combo", registro(execucao.eventos))  # a MESMA referência da execução direta


# ----------------------------------------------------------------------------------------- aplicativo, espera e atalho
def test_abrir_aplicativo_esperar_digitar_e_salvar(make_engine):
    # O fluxo mais comum: abre o Bloco de Notas, espera ele ficar pronto, espera mais 1,5 s (condição de atraso), digita e
    # aperta Ctrl+S. A espera empurra TUDO o que vem depois dela; o aplicativo é só anotado, nunca aberto de verdade.
    espera = Command(type=InputType.WAIT, start=0.2, conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=1.5)])
    comandos = [
        Command(type=InputType.APP_OPEN, target="notepad.exe", start=0.0, duration=0.1, wait_process="notepad.exe"),
        espera,
        Command(type=InputType.TEXT, text="Olá, mundo! Ação concluída.", start=0.3, duration=0.1, wait_process="notepad.exe"),
        Command(type=InputType.KEY, target="CTRL", start=2.0, duration=0.4),
        Command(type=InputType.KEY, target="S", start=2.1, duration=0.1),
    ]
    execucao = executar(make_engine, AutomationMap(name="Bloco", commands=comandos, repeat_count=1))
    assert execucao.erros == [] and execucao.sobras == {}
    assert execucao.aplicativos == ["notepad.exe"]
    texto = [e for e in execucao.eventos if e[1] == "type_text"]
    assert {t for t, _a, _c in texto} == {1.8}, "o texto sai em 0,3 s + 1,5 s de espera = 1,8 s, de uma vez"
    assert "".join(c for _t, _a, c in texto) == "Olá, mundo! Ação concluída."
    assert [e for e in execucao.eventos if e[1] != "type_text"] == [
        (3.5, "key_down", "CTRL"), (3.6, "key_down", "S"), (3.7, "key_up", "S"), (3.9, "key_up", "CTRL")], "Ctrl+S: 2,0 s + 1,5 s = 3,5 s"
    golden.comparar("abrir_aplicativo_esperar_digitar_e_salvar", registro(execucao.eventos, execucao.aplicativos))


# ----------------------------------------------------------------------------------------- backend do Windows
def _mapa_completo_do_windows():
    return AutomationMap(name="Windows", repeat_count=1, commands=[
        Command(type=InputType.KEY, target="CTRL", start=0.0, duration=0.5),
        Command(type=InputType.KEY, target="C", start=0.1, duration=0.1),
        Command(type=InputType.MOUSE_MOVE, x=640, y=360, start=0.6),
        Command(type=InputType.MOUSE_BUTTON, target="left", start=0.7, duration=0.05),
        Command(type=InputType.MOUSE_BUTTON, target="x1", start=0.9, duration=0.05),
        Command(type=InputType.MOUSE_BUTTON, target="x2", start=1.0, duration=0.05),
        Command(type=InputType.MOUSE_SCROLL, scroll_dy=-2, start=1.1),
        Command(type=InputType.MOUSE_MOVE, x=10, y=-5, relative=True, start=1.2),
        Command(type=InputType.KEY, target="RIGHT", start=1.3, duration=0.1),
        Command(type=InputType.TEXT, text="ação!", start=1.5, duration=0.1),
    ])


def test_mapa_completo_pelo_backend_do_windows_envia_o_que_o_windows_espera(make_engine):
    usuario = FakeUser32Abnt2()
    backend = Win32InputBackend(user32=usuario, kernel32=FakeKernel32())
    motor, _ = make_engine(backend=backend)
    desligar_aplicativos(motor)
    terminou, erros = run_to_end(motor, _mapa_completo_do_windows())
    assert terminou and not erros, erros
    join_engine(motor)
    enviado = [(s[0], s[1], s[2] & MASCARA_32, *s[3:]) if s[0] == "mouse" else s for s in usuario.sent]

    SUBIR, ESTENDIDA, UNICODE = 0x0002, 0x0001, 0x0004
    teclado = [(vk, flags) for tipo, vk, flags, *_ in enviado if tipo == "key" and flags & UNICODE == 0]
    assert teclado[:4] == [(0x11, 0), (0x43, 0), (0x43, SUBIR), (0x11, SUBIR)], "Ctrl+C: 0x11 e 0x43, soltando na ordem inversa"
    assert (0x27, ESTENDIDA) in teclado and (0x27, ESTENDIDA | SUBIR) in teclado, "seta para a direita é tecla estendida"
    mouse = [m[1:] for m in enviado if m[0] == "mouse"]  # (flags, dados, dx, dy)
    assert (0x0002, 0, 0, 0) in mouse and (0x0004, 0, 0, 0) in mouse, "botão esquerdo: LEFTDOWN 0x0002 e LEFTUP 0x0004"
    assert (0x0080, 1, 0, 0) in mouse and (0x0100, 1, 0, 0) in mouse, "lateral 1 (x1): XDOWN/XUP com XBUTTON1 = 1"
    assert (0x0080, 2, 0, 0) in mouse and (0x0100, 2, 0, 0) in mouse, "lateral 2 (x2): XDOWN/XUP com XBUTTON2 = 2"
    assert (0x0800, (-240) & MASCARA_32, 0, 0) in mouse, "rolagem de 2 linhas para baixo: WHEEL com -2 x 120"
    assert (0x0001, 0, 10, -5) in mouse, "movimento relativo: MOVE com dx e dy"
    assert ("cursor", 640, 360) in enviado, "movimento absoluto posiciona o cursor"
    golden.comparar("windows_mapa_completo_pelo_sendinput", {"enviado": enviado})
