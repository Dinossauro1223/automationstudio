"""Verificações e2e do Windows. Cada função recebe um `Ambiente` (testsupport/e2e_windows.py) e usa SÓ a superfície dele.

Elas rodam em dois modos (ver e2e_windows.py): "simulado" (sempre) e "windows" (opt-in, entrada de verdade). A cabeça de cada
função diz qual PREMISSA sobre o Windows ela confirma: são as coisas que o programa assume e que nenhum teste sem o Windows
consegue provar. Se uma verificação FALHAR no modo "windows", a premissa estava errada: me envie a saída, ela é o dado.

  P1  GetAsyncKeyState enxerga o que o SendInput injeta (teclado e botões do mouse, inclusive laterais).
  P2  SetCursorPos é exato; um movimento relativo vai para o lado certo (a aceleração do ponteiro pode ampliá-lo).
  P3  O texto digitado pelo backend chega inteiro à janela em primeiro plano (teclas reais, teclas mortas do layout e,
      para o que o layout não tem, o caminho Unicode).
  P4  Clique esquerdo, do meio e direito e a roda chegam à janela que está sob o cursor, com o sinal e o tamanho certos.
  P5  O motor inteiro (mapa → linha do tempo → backend → Windows) produz o efeito esperado na janela.
  P6  O monitor global do pynput enxerga a entrada enviada pelo próprio programa e o atalho global dispara.
  P7  A leitura da lista de processos (Toolhelp32 + psapi, via ctypes) funciona neste Python de 64 bits.
"""
from __future__ import annotations

import os
import sys
import threading
import time

from automationstudio.core import AutomationMap, Command, InputType
from automationstudio.input_system import ExecutionEngine
from testsupport.e2e_windows import VK_CONTROL, VK_SHIFT, VK_XBUTTON1, VK_XBUTTON2

TEXTO_DO_LAYOUT = "Olá, ação! Ç é ü"
TEXTO_FORA_DO_LAYOUT = "→ ★"  # nenhum layout de teclado brasileiro tem estes: o backend precisa cair no caminho Unicode


# -------------------------------------------------------------------------------------------------- auxiliares
def _ir_para(amb, janela, backend, nome: str) -> None:
    """Leva o cursor ao centro de um widget da janela de teste, mas só depois de confirmar que ela está em primeiro plano
    sobre aquele ponto: nenhum clique pode cair em outro programa."""
    x, y = janela.centro(nome)
    amb.exigir(janela.sob_o_cursor_e_na_frente(x, y),
               "a janela de teste não está em primeiro plano sobre esse ponto da tela; nenhum clique foi enviado")
    backend.mouse_move(x, y)
    assert amb.esperar(lambda: amb.cursor() == (x, y)), f"o cursor não chegou em {(x, y)}: está em {amb.cursor()}"
    amb.exigir(janela.sob_o_cursor_e_na_frente(x, y), "a janela de teste perdeu o primeiro plano; nenhum clique foi enviado")


def _digitar_e_ler(amb, texto: str) -> str:
    janela, backend = amb.abrir_janela(), amb.criar_backend()
    amb.definir_intervalo_de_texto(0.01)  # o intervalo por caractere do produto
    janela.focar_entrada()
    amb.exigir(janela.em_primeiro_plano(), "a janela de teste perdeu o primeiro plano; nada foi digitado")
    for caractere in texto:  # como o motor faz: um caractere por vez
        backend.type_text(caractere)
    amb.esperar(lambda: len(janela.texto) >= len(texto), 3.0)
    return janela.texto


# ------------------------------------------------------------------------------------------------------- P1, P2
def teclas_modificadoras_mudam_o_estado_do_sistema(amb) -> None:
    """P1: SHIFT e CTRL sozinhos (inofensivos em qualquer programa) aparecem como pressionados enquanto seguradas."""
    backend = amb.criar_backend()
    try:
        for nome, vk in (("SHIFT", VK_SHIFT), ("CTRL", VK_CONTROL)):
            amb.exigir(not amb.tecla_pressionada(vk), f"{nome} está pressionada agora (solte-a e rode de novo)")
            backend.key_down(nome)
            assert amb.esperar(lambda: amb.tecla_pressionada(vk)), f"{nome} enviada, mas o Windows não a vê pressionada"
            backend.key_up(nome)
            assert amb.esperar(lambda: not amb.tecla_pressionada(vk)), f"{nome} solta, mas o Windows ainda a vê pressionada"
    finally:
        backend.key_up("SHIFT")
        backend.key_up("CTRL")


def cursor_absoluto_e_relativo_move_o_cursor(amb) -> None:
    """P2: o movimento absoluto leva o cursor exatamente ao ponto; o relativo vai para o lado certo."""
    backend = amb.criar_backend()
    origem = amb.cursor()
    try:
        destino = (300, 300)
        backend.mouse_move(*destino)
        assert amb.esperar(lambda: amb.cursor() == destino), f"o cursor foi para {amb.cursor()}, não para {destino}"
        antes = amb.cursor()
        backend.mouse_move(25, 15, relative=True)
        assert amb.esperar(lambda: amb.cursor() != antes), "o movimento relativo não moveu o cursor"
        depois = amb.cursor()
        # A aceleração do ponteiro do Windows ("Aprimorar a precisão do ponteiro") pode ampliar um movimento relativo:
        # só a DIREÇÃO é garantida, e é isso que se confere.
        assert depois[0] > antes[0] and depois[1] > antes[1], f"o cursor foi de {antes} para {depois}: lado errado"
    finally:
        amb.mover_cursor(*origem)


def botoes_laterais_do_mouse_chegam_ao_sistema(amb) -> None:
    """P1: os botões laterais (x1 e x2) injetados aparecem como pressionados (o cursor fica sobre a janela de teste)."""
    janela, backend = amb.abrir_janela(), amb.criar_backend()
    try:
        _ir_para(amb, janela, backend, "lista")
        for nome, vk in (("x1", VK_XBUTTON1), ("x2", VK_XBUTTON2)):
            amb.exigir(not amb.tecla_pressionada(vk), f"o botão {nome} está pressionado agora (solte-o e rode de novo)")
            backend.mouse_down(nome)
            assert amb.esperar(lambda: amb.tecla_pressionada(vk)), f"{nome} enviado, mas o Windows não o vê pressionado"
            backend.mouse_up(nome)
            assert amb.esperar(lambda: not amb.tecla_pressionada(vk)), f"{nome} solto, mas o Windows ainda o vê pressionado"
    finally:
        backend.mouse_up("x1")
        backend.mouse_up("x2")


# ------------------------------------------------------------------------------------------------------- P3
def texto_com_acentos_chega_inteiro_na_janela(amb) -> None:
    """P3: letras, acentos (teclas mortas do layout), cedilha, maiúsculas e pontuação chegam como foram escritos."""
    obtido = _digitar_e_ler(amb, TEXTO_DO_LAYOUT)
    assert obtido == TEXTO_DO_LAYOUT, f"enviei {TEXTO_DO_LAYOUT!r} e a janela recebeu {obtido!r} (layout: {amb.layout()})"


def caractere_fora_do_layout_chega_pelo_caminho_unicode(amb) -> None:
    """P3: caracteres que nenhum layout brasileiro tem chegam pelo caminho Unicode, sem virar lixo."""
    obtido = _digitar_e_ler(amb, TEXTO_FORA_DO_LAYOUT)
    assert obtido == TEXTO_FORA_DO_LAYOUT, f"enviei {TEXTO_FORA_DO_LAYOUT!r} e a janela recebeu {obtido!r} (layout: {amb.layout()})"


# ------------------------------------------------------------------------------------------------------- P4
def cliques_e_rolagem_chegam_a_janela_sob_o_cursor(amb) -> None:
    """P4: esquerdo, do meio e direito chegam nessa ordem; só o esquerdo aciona o botão; a roda soma -240 (2 linhas)."""
    janela, backend = amb.abrir_janela(), amb.criar_backend()
    try:
        _ir_para(amb, janela, backend, "botao")
        for botao in ("left", "middle", "right"):
            backend.mouse_down(botao)
            backend.mouse_up(botao)

        def botoes():
            return [numero for tipo, numero in janela.eventos if tipo == "botao"]

        assert amb.esperar(lambda: len(botoes()) >= 3), f"chegaram só os botões {botoes()}"
        assert botoes() == [1, 2, 3], f"esperava esquerdo(1), meio(2), direito(3); chegou {botoes()}"
        assert amb.esperar(lambda: janela.cliques_no_botao >= 1)
        assert janela.cliques_no_botao == 1, f"só o clique esquerdo aciona o botão; acionou {janela.cliques_no_botao} vez(es)"

        _ir_para(amb, janela, backend, "lista")
        backend.mouse_scroll(0, -2)

        def roda():
            return sum(delta for tipo, delta in janela.eventos if tipo == "roda")

        assert amb.esperar(lambda: roda() != 0), "a rolagem não chegou à janela"
        assert roda() == -240, f"rolar 2 linhas para baixo deveria somar -240 (2 x 120); somou {roda()}"
    finally:
        for botao in ("left", "middle", "right"):
            backend.mouse_up(botao)


# ------------------------------------------------------------------------------------------------------- P5
def o_motor_executa_um_mapa_pequeno_de_verdade(amb) -> None:
    """P5: clique para focar a caixa de texto, digitar com acento e apertar ENTER, tudo pelo ExecutionEngine."""
    janela = amb.abrir_janela()
    amb.definir_intervalo_de_texto(0.01)
    x, y = janela.centro("entrada")
    amb.exigir(janela.sob_o_cursor_e_na_frente(x, y), "a janela de teste não está em primeiro plano; o mapa não foi executado")
    texto = "Olá, ação!"
    mapa = AutomationMap(name="e2e", repeat_count=1, commands=[
        Command(type=InputType.MOUSE_MOVE, x=x, y=y, start=0.0),
        Command(type=InputType.MOUSE_BUTTON, target="left", start=0.1, duration=0.05),
        Command(type=InputType.TEXT, text=texto, start=0.3, duration=0.1),
        Command(type=InputType.KEY, target="ENTER", start=0.9, duration=0.05)])
    assert mapa.validate() == []
    motor = ExecutionEngine(amb.criar_backend(), clock=amb.relogio)
    terminou, erros = threading.Event(), []
    motor.on_finished.append(terminou.set)
    motor.on_error.append(lambda erro: (erros.append(erro), terminou.set()))
    inicio = time.monotonic()
    motor.run(mapa)
    assert amb.esperar(terminou.is_set, 20.0), "o motor não terminou em 20 s"
    decorrido = time.monotonic() - inicio
    assert erros == [], erros
    assert amb.esperar(lambda: janela.texto == texto and ("tecla", "Return") in janela.eventos), (
        f"a janela recebeu {janela.texto!r} e as teclas {[e for e in janela.eventos if e[0] == 'tecla'][-4:]} (layout: {amb.layout()})")
    if amb.tempo_real:
        assert 0.9 <= decorrido < 8.0, f"o mapa planejado para ~1 s levou {decorrido:.2f} s"


# ------------------------------------------------------------------------------------------------------- P6, P7
def o_monitor_global_enxerga_o_teclado_enviado_pelo_programa(amb) -> None:
    """P6: o gancho global do pynput vê o SHIFT injetado pelo SendInput e o atalho "SHIFT" dispara."""
    from automationstudio.input_system import GlobalHotkeyManager, GlobalInputMonitor
    monitor = GlobalInputMonitor()
    amb.exigir(monitor.available, "pynput não está instalado: o monitor global não existe nesta máquina")
    amb.exigir(not amb.tecla_pressionada(VK_SHIFT), "SHIFT está pressionada agora (solte-a e rode de novo)")
    vistos, disparos = [], []
    monitor.on_key.append(lambda nome, pressionada: vistos.append((str(nome).upper(), pressionada)))
    gerente = GlobalHotkeyManager(monitor)
    gerente.register("SHIFT", lambda: disparos.append(True))
    gerente.start()
    monitor.start()
    backend = amb.criar_backend()
    try:
        time.sleep(0.3)  # o gancho global leva um instante para ficar ativo
        backend.key_down("SHIFT")
        backend.key_up("SHIFT")
        assert amb.esperar(lambda: any("SHIFT" in nome and pressionada for nome, pressionada in vistos), 3.0), (
            f"o monitor global não viu o SHIFT enviado; viu {vistos}")
        assert amb.esperar(lambda: bool(disparos), 3.0), f"o atalho SHIFT não disparou; o monitor viu {vistos}"
    finally:
        backend.key_up("SHIFT")
        gerente.stop()
        monitor.stop()


def a_lista_de_processos_enxerga_o_proprio_python_e_o_explorer(amb) -> None:
    """P7: Toolhelp32 + psapi via ctypes funcionam: o Explorer e este próprio processo aparecem, e a memória é lida."""
    from automationstudio.input_system import WindowsProcessReadiness
    leitor = WindowsProcessReadiness()
    assert leitor._find("explorer.exe"), "o Explorer não apareceu na lista de processos (a leitura via Toolhelp32 falhou?)"
    nomes = ";".join(["python.exe", "pythonw.exe", "py.exe", os.path.basename(sys.executable)])
    assert os.getpid() in [pid for pid, _nome in leitor._find(nomes)], (
        f"o próprio processo ({os.getpid()}, {os.path.basename(sys.executable)}) não está na lista")
    assert leitor._find("programa_que_nao_existe_xyz.exe") == []
    memoria = leitor._memory_bytes(os.getpid())
    assert memoria and memoria > 1_000_000, f"memória do processo lida como {memoria!r}"
