"""A ligação do aviso de administrador (F51) com a janela: o controlador de automationstudio/elevacao_ui.py.

Dois níveis. Primeiro, o controlador com rótulo, barra de status, ponte e vigia FALSOS: o que ele faz com cada aviso e com cada
mudança de estado. Depois, uma execução de verdade: motor real, relógio virtual, vigia real e Windows simulado, para provar que o
aviso aparece quando a automação chega a uma janela de administrador e some quando outra execução começa.

O que só o Qt e o Windows de verdade mostram (o rótulo na barra, a barra de tarefas piscando) está em
md/ENTREGA_AVISO_ADMINISTRADOR.md. As funções usadas aqui não dependem do tipo de dublê de Qt do ambiente de teste.
"""
import pytest

from automationstudio import elevacao_ui
from automationstudio.core import State
from automationstudio.elevacao import ONDE_CURSOR, ONDE_FRENTE, Situacao, VigiaDeElevacao, montar_aviso
from automationstudio.elevacao_ui import NOME_DO_ROTULO, ControladorElevacao
from testsupport.fakes_elevacao import MundoWindows
from testsupport.helpers import join_engine, key, make_map, run_to_end


class RotuloFalso:
    def __init__(self, ordem) -> None:
        self.ordem = ordem
        self.nome, self.texto, self.dica, self.visivel = "", "", "", True   # um QLabel novo é visível
        ordem.append(("rotulo criado",))

    def setObjectName(self, nome):
        self.nome = nome
        self.ordem.append(("setObjectName", nome))

    def setText(self, texto):
        self.texto = texto

    def setToolTip(self, dica):
        self.dica = dica

    def setVisible(self, visivel):
        self.visivel = bool(visivel)
        self.ordem.append(("setVisible", bool(visivel)))


class BarraFalsa:
    def __init__(self, ordem) -> None:
        self.ordem, self.permanentes = ordem, []

    def addPermanentWidget(self, widget):
        self.permanentes.append(widget)
        self.ordem.append(("addPermanentWidget",))


class SinalFalso:
    def __init__(self) -> None:
        self.ligados = []

    def connect(self, funcao):
        self.ligados.append(funcao)

    def emit(self, *argumentos):
        for funcao in list(self.ligados):
            funcao(*argumentos)


class PonteFalsa:
    """O que o controlador usa da EngineBridge: os sinais event_fired e state_changed."""

    def __init__(self) -> None:
        self.event_fired, self.state_changed = SinalFalso(), SinalFalso()


class VigiaFalso:
    def __init__(self, avisos=()) -> None:
        self.avisos, self.olhadas, self.rodadas = list(avisos), 0, 0

    def olhar(self):
        self.olhadas += 1
        return self.avisos.pop(0) if self.avisos else None

    def nova_rodada(self):
        self.rodadas += 1


def _aviso(pid=500, nome="Taskmgr.exe", onde=ONDE_FRENTE, estado=Situacao.BLOQUEADA):
    return montar_aviso(estado, pid, nome, onde)


def _controlador(vigia):
    """(controlador, ordem do que foi feito no rótulo e na barra, linhas do log, vezes que a barra de tarefas piscou)."""
    ordem, registro, piscadas = [], [], []
    controlador = ControladorElevacao(object(), vigia=vigia, criar_rotulo=lambda: RotuloFalso(ordem),
                                      piscar=lambda: piscadas.append("piscou"), registrar=registro.append)
    return controlador, ordem, registro, piscadas


def _ligado(vigia):
    controlador, ordem, registro, piscadas = _controlador(vigia)
    barra, ponte = BarraFalsa(ordem), PonteFalsa()
    controlador.ligar(barra, ponte)
    return controlador, ponte, barra, ordem, registro, piscadas


# --------------------------------------------------------------------------------------------------- ligar
def test_sem_vigia_o_controlador_nao_faz_nada():
    controlador, ordem, registro, piscadas = _controlador(None)
    barra, ponte = BarraFalsa(ordem), PonteFalsa()
    controlador.ligar(barra, ponte)
    controlador.olhar()
    controlador.estado_mudou(State.IDLE, State.RUNNING)
    assert barra.permanentes == [] and ordem == [] and registro == [] and piscadas == []
    assert ponte.event_fired.ligados == [] and ponte.state_changed.ligados == []


def test_ligar_poe_o_rotulo_escondido_na_barra_e_liga_os_dois_sinais():
    controlador, ponte, barra, ordem, _registro, _piscadas = _ligado(VigiaFalso())
    assert controlador.rotulo.nome == NOME_DO_ROTULO == "AvisoElevacao"
    assert barra.permanentes == [controlador.rotulo]
    # esconder vem DEPOIS de adicionar: a barra pode mostrar o que entra nela
    assert ordem == [("rotulo criado",), ("setObjectName", NOME_DO_ROTULO), ("addPermanentWidget",), ("setVisible", False)]
    assert controlador.rotulo.visivel is False
    assert ponte.event_fired.ligados == [controlador.olhar]
    assert ponte.state_changed.ligados == [controlador.estado_mudou]


# --------------------------------------------------------------------------------------------------- o aviso
def test_o_aviso_aparece_no_rotulo_na_dica_e_no_log_e_a_barra_de_tarefas_pisca():
    aviso = _aviso()
    controlador, ponte, _barra, _ordem, registro, piscadas = _ligado(VigiaFalso([aviso]))
    ponte.event_fired.emit(object())
    assert controlador.rotulo.visivel is True
    assert controlador.rotulo.texto == aviso.curto and controlador.rotulo.dica == aviso.longo
    assert controlador.aviso_atual is aviso
    assert piscadas == ["piscou"]
    assert registro == [f"AVISO ELEVACAO situacao=bloqueada pid=500 nome=Taskmgr.exe onde=frente texto={aviso.longo}"]


def test_o_log_diz_que_o_nome_e_desconhecido_e_de_onde_veio_a_janela():
    aviso = _aviso(pid=7, nome="", onde=ONDE_CURSOR, estado=Situacao.PROVAVEL)
    _controlador_, ponte, _barra, _ordem, registro, _piscadas = _ligado(VigiaFalso([aviso]))
    ponte.event_fired.emit(object())
    assert registro[0].startswith("AVISO ELEVACAO situacao=provavel pid=7 nome=? onde=cursor texto=")


def test_cada_evento_do_motor_chama_o_vigia_mas_so_um_aviso_aparece():
    aviso = _aviso()
    vigia = VigiaFalso([None, aviso, None, None])
    controlador, ponte, _barra, _ordem, registro, piscadas = _ligado(vigia)
    ponte.event_fired.emit("evento 1")
    assert controlador.rotulo.visivel is False and vigia.olhadas == 1
    ponte.event_fired.emit("evento 2")
    assert controlador.rotulo.visivel is True and vigia.olhadas == 2
    ponte.event_fired.emit("evento 3")
    ponte.event_fired.emit("evento 4")
    assert vigia.olhadas == 4 and controlador.rotulo.visivel is True and controlador.rotulo.texto == aviso.curto
    assert piscadas == ["piscou"] and len(registro) == 1


def test_um_aviso_novo_troca_o_texto_do_rotulo():
    primeiro, segundo = _aviso(500, "Taskmgr.exe"), _aviso(501, "regedit.exe", ONDE_CURSOR)
    controlador, ponte, _barra, _ordem, _registro, piscadas = _ligado(VigiaFalso([primeiro, segundo]))
    ponte.event_fired.emit(None)
    ponte.event_fired.emit(None)
    assert controlador.rotulo.texto == segundo.curto and controlador.aviso_atual is segundo and len(piscadas) == 2


def test_se_piscar_falhar_o_aviso_continua_valendo():
    aviso = _aviso()
    ordem, registro = [], []

    def piscar_quebrado():
        raise RuntimeError("sem barra de tarefas")
    controlador = ControladorElevacao(object(), vigia=VigiaFalso([aviso]), criar_rotulo=lambda: RotuloFalso(ordem),
                                      piscar=piscar_quebrado, registrar=registro.append)
    controlador.ligar(BarraFalsa(ordem), PonteFalsa())
    controlador.olhar()
    assert controlador.rotulo.visivel is True and controlador.rotulo.texto == aviso.curto
    assert any("ELEVACAO PISCAR FALHOU" in linha and "sem barra de tarefas" in linha for linha in registro)


def test_sem_ligar_o_aviso_ainda_vai_para_o_log_e_para_de_piscar():
    """`olhar` antes de `ligar` (sem rótulo) não pode quebrar: o aviso vai para o log e a barra de tarefas pisca."""
    controlador, _ordem, registro, piscadas = _controlador(VigiaFalso([_aviso()]))
    controlador.olhar()
    assert len(registro) == 1 and piscadas == ["piscou"] and controlador.rotulo is None


# --------------------------------------------------------------------------------------------- execução nova
def test_uma_execucao_nova_esconde_o_aviso_antigo_e_zera_o_vigia():
    controlador, ponte, _barra, _ordem, _registro, _piscadas = _ligado(VigiaFalso([_aviso()]))
    ponte.event_fired.emit(None)
    assert controlador.rotulo.visivel is True
    ponte.state_changed.emit(State.IDLE, State.RUNNING)
    assert controlador.rotulo.visivel is False and controlador.rotulo.texto == "" and controlador.rotulo.dica == ""
    assert controlador.aviso_atual is None and controlador.vigia.rodadas == 1


@pytest.mark.parametrize("anterior,novo", [
    (State.PAUSED, State.RUNNING),      # continuar depois de pausar NÃO é execução nova
    (State.RUNNING, State.PAUSED), (State.RUNNING, State.STOPPING), (State.RUNNING, State.IDLE),
    (State.STOPPING, State.IDLE), (State.IDLE, State.RECORDING), (State.RECORDING, State.IDLE),
])
def test_outras_mudancas_de_estado_nao_mexem_no_aviso(anterior, novo):
    controlador, ponte, _barra, _ordem, _registro, _piscadas = _ligado(VigiaFalso([_aviso()]))
    ponte.event_fired.emit(None)
    ponte.state_changed.emit(anterior, novo)
    assert controlador.rotulo.visivel is True and controlador.vigia.rodadas == 0 and controlador.aviso_atual is not None


@pytest.mark.parametrize("anterior", [State.IDLE, State.STOPPING, State.RECORDING])
def test_toda_ida_para_executando_que_nao_vem_da_pausa_e_execucao_nova(anterior):
    controlador, ponte, _barra, _ordem, _registro, _piscadas = _ligado(VigiaFalso([_aviso()]))
    ponte.event_fired.emit(None)
    ponte.state_changed.emit(anterior, State.RUNNING)
    assert controlador.vigia.rodadas == 1 and controlador.rotulo.visivel is False


def test_nova_rodada_sem_rotulo_nem_aviso_nao_quebra():
    controlador, _ordem, _registro, _piscadas = _controlador(VigiaFalso())
    controlador.nova_rodada()
    assert controlador.vigia.rodadas == 1


# ----------------------------------------------------------------------------------------------- os padrões
def test_o_padrao_do_vigia_e_o_de_verdade_e_none_quer_dizer_sem_vigia(monkeypatch):
    marcado, chamadas = object(), []
    monkeypatch.setattr(elevacao_ui, "criar_vigia", lambda registrar: chamadas.append(registrar) or marcado)
    registro = []
    assert ControladorElevacao(object(), registrar=registro.append).vigia is marcado
    assert chamadas == [registro.append], "o vigia criado tem de gravar no mesmo registro do controlador"
    chamadas.clear()
    assert ControladorElevacao(object(), vigia=None).vigia is None and chamadas == []


def test_o_registro_padrao_grava_no_log_do_programa(runtime_log):
    """`runtime_log` é o fixture que captura o que o programa grava no log (em vez de escrever num arquivo de verdade)."""
    ordem = []
    controlador = ControladorElevacao(object(), vigia=VigiaFalso([_aviso()]), criar_rotulo=lambda: RotuloFalso(ordem),
                                      piscar=lambda: None)
    controlador.olhar()
    assert len(runtime_log) == 1 and runtime_log[0].startswith("AVISO ELEVACAO situacao=bloqueada pid=500")


def test_o_rotulo_padrao_e_um_qlabel():
    assert ControladorElevacao(object(), vigia=None)._criar_rotulo is elevacao_ui.QLabel


def test_o_padrao_de_piscar_usa_a_barra_de_tarefas_da_janela_principal(monkeypatch):
    chamadas = []

    class QApplicationFalsa:
        @staticmethod
        def alert(janela, *resto):
            chamadas.append((janela, resto))
    monkeypatch.setattr(elevacao_ui, "QApplication", QApplicationFalsa)
    janela, ordem = object(), []
    controlador = ControladorElevacao(janela, vigia=VigiaFalso([_aviso()]), criar_rotulo=lambda: RotuloFalso(ordem),
                                      registrar=lambda texto: None)
    controlador.olhar()
    assert chamadas == [(janela, ())], "tem de piscar a janela principal, sem prazo (pisca até ela ser ativada)"


# ------------------------------------------------------------------- uma execução de verdade (motor real, Windows simulado)
def _ligar_ao_motor(motor, ponte):
    motor.on_event.append(lambda evento: ponte.event_fired.emit(evento))
    motor.state.on_change(lambda anterior, novo: ponte.state_changed.emit(anterior, novo))


def _cenario(fake_clock, eu_elevado):
    mundo = MundoWindows(eu_elevado=eu_elevado)
    mundo.adicionar_processo(500, "Taskmgr.exe", elevado=True)
    mundo.adicionar_processo(600, "notepad.exe", elevado=False)
    mundo.adicionar_janela(11, 500)
    mundo.adicionar_janela(12, 600, na_frente=True)
    registro, piscadas, ordem = [], [], []
    vigia = VigiaDeElevacao(mundo.criar_sonda(), registrar=registro.append, relogio=fake_clock.monotonic)
    controlador = ControladorElevacao(object(), vigia=vigia, criar_rotulo=lambda: RotuloFalso(ordem),
                                      piscar=lambda: piscadas.append("piscou"), registrar=registro.append)
    ponte = PonteFalsa()
    controlador.ligar(BarraFalsa(ordem), ponte)
    return mundo, controlador, ponte, registro, piscadas


def _mapa_de_dois_segundos():
    return make_map([key("A", 0.0, 0.1), key("B", 0.5, 0.1), key("C", 1.0, 0.1), key("D", 1.5, 0.1), key("E", 2.0, 0.1)])


def test_execucao_de_verdade_avisa_quando_a_automacao_chega_a_uma_janela_de_administrador(make_engine, fake_clock):
    mundo, controlador, ponte, registro, piscadas = _cenario(fake_clock, eu_elevado=False)
    motor, _backend = make_engine()
    trazer_a_janela_de_administrador = {"ligado": True}

    def a_automacao_chega_ao_gerenciador_de_tarefas(evento):
        if trazer_a_janela_de_administrador["ligado"] and evento.time >= 1.0:
            mundo.frente = 11          # o bloco de notas dava lugar ao gerenciador de tarefas (processo elevado)
    motor.on_event.append(a_automacao_chega_ao_gerenciador_de_tarefas)   # antes da ponte: o vigia já vê a janela nova
    _ligar_ao_motor(motor, ponte)

    terminou, erros = run_to_end(motor, _mapa_de_dois_segundos())
    assert terminou and not erros
    join_engine(motor)
    avisos = [linha for linha in registro if linha.startswith("AVISO ELEVACAO")]
    assert len(avisos) == 1 and "pid=500 nome=Taskmgr.exe onde=frente" in avisos[0], registro
    assert controlador.rotulo.visivel is True and "Taskmgr.exe" in controlador.rotulo.texto
    assert piscadas == ["piscou"]
    assert mundo.alcas_abertas() == [] and mundo.fechamentos_invalidos == []

    # a execução seguinte começa limpa: o rótulo some na hora e, com o bloco de notas na frente, nada reaparece
    mundo.frente = 12
    trazer_a_janela_de_administrador["ligado"] = False
    terminou, erros = run_to_end(motor, _mapa_de_dois_segundos())
    assert terminou and not erros
    join_engine(motor)
    assert controlador.rotulo.visivel is False and controlador.aviso_atual is None
    assert len([linha for linha in registro if linha.startswith("AVISO ELEVACAO")]) == 1 and piscadas == ["piscou"]


def test_execucao_de_verdade_sem_janela_de_administrador_nao_avisa_nada(make_engine, fake_clock):
    _mundo, controlador, ponte, registro, piscadas = _cenario(fake_clock, eu_elevado=False)
    motor, _backend = make_engine()
    _ligar_ao_motor(motor, ponte)
    terminou, erros = run_to_end(motor, _mapa_de_dois_segundos())
    assert terminou and not erros
    join_engine(motor)
    assert controlador.rotulo.visivel is False and piscadas == []
    assert not [linha for linha in registro if linha.startswith("AVISO")]


def test_execucao_de_verdade_com_o_programa_elevado_nao_avisa(make_engine, fake_clock):
    mundo, controlador, ponte, registro, piscadas = _cenario(fake_clock, eu_elevado=True)
    mundo.frente = 11                  # janela de administrador na frente desde o começo
    motor, _backend = make_engine()
    _ligar_ao_motor(motor, ponte)
    terminou, erros = run_to_end(motor, _mapa_de_dois_segundos())
    assert terminou and not erros
    join_engine(motor)
    assert controlador.rotulo.visivel is False and piscadas == []
    assert registro == ["ELEVACAO programa=sim"]
    assert "GetForegroundWindow" not in mundo.chamadas
