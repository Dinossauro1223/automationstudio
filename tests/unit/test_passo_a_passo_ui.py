"""A ligação do passo a passo (F52) com a janela: o controlador de automationstudio/passo_a_passo_ui.py.

Dois níveis. Primeiro, o controlador com motor, janelinha, tabela e ponte FALSOS: o que ele mostra para cada pedido e para cada
mudança de estado. Depois, uma execução de verdade: motor real, relógio virtual e o aviso de estado ligado direto ao controlador,
para provar o caminho inteiro (pedido, parada em cada passo, botões, fim) sem Qt.

A janelinha de verdade (sempre por cima, sem foco) só existe com o PySide6 de verdade: tests/gui/test_passo_a_passo_janela.py. As
propriedades dela que dá para conferir sem Qt estão em tests/static/test_ligacao_passo_a_passo.py.
"""
import contextlib

import pytest

from automationstudio.core import Event, EventKind, State
from automationstudio.passo_a_passo import ControleDePassos, MOTIVO_EM_EXECUCAO, MOTIVO_SEM_COMANDOS
from automationstudio.passo_a_passo_ui import ControladorPassoAPasso, posicao_no_canto
from testsupport.fakes_passo_a_passo import JanelaFalsa, MotorFalso, PainelFalso, PonteFalsa, TabelaFalsa
from testsupport.helpers import key, make_map

PASSO_1 = "Passo 1 de 3: Apertar e soltar a tecla A"


def _tres():
    return make_map([key("A", 0.0, 0.2), key("B", 5.0, 0.2), key("C", 10.0, 0.2)], name="Minha automação")


class Montagem:
    """Tudo ligado com dublês: motor falso, janela falsa, janelinha falsa e uma lista dos avisos mostrados ao usuário."""

    def __init__(self, mapa=None, estado=State.IDLE, com_mapa=True) -> None:
        self.motor = MotorFalso(estado)
        self.janela = JanelaFalsa(self.motor, (mapa or _tres()) if com_mapa else None)
        self.paineis: list[PainelFalso] = []
        self.avisos: list[str] = []
        self.registro: list[str] = []
        self.controlador = ControladorPassoAPasso(self.janela, criar_painel=self._criar_painel, avisar=self.avisos.append,
                                                  registrar=self.registro.append)

    def _criar_painel(self, ao_proximo, ao_continuar, ao_parar) -> PainelFalso:
        painel = PainelFalso(ao_proximo, ao_continuar, ao_parar)
        self.paineis.append(painel)
        return painel

    @property
    def painel(self) -> PainelFalso:
        assert len(self.paineis) == 1, f"{len(self.paineis)} janelinhas criadas"
        return self.paineis[0]

    def _evento_do_primeiro_comando(self) -> Event:
        comando = self.controlador.controle.sessao.mapa.commands[0]
        return Event(time=0.0, kind=EventKind.KEY_DOWN, target=comando.target, command_id=comando.id)

    def parar_no_primeiro_comando(self) -> None:
        self.motor.parar_num_passo(self.controlador.controle, self._evento_do_primeiro_comando())


# ------------------------------------------------------------------------------------------------ construção e ligação
def test_o_controle_padrao_usa_o_motor_da_janela_e_o_log_padrao(runtime_log):
    janela = JanelaFalsa(MotorFalso(), _tres())
    controlador = ControladorPassoAPasso(janela, criar_painel=PainelFalso, avisar=lambda texto: None)
    assert isinstance(controlador.controle, ControleDePassos) and controlador.controle.motor is janela.engine
    assert controlador.iniciar(set()) is None
    assert runtime_log == ["PASSO A PASSO iniciado mapa=Minha automação passos=3"]


def test_ligar_conecta_o_pedido_do_editor_e_o_aviso_de_estado_do_motor():
    montagem = Montagem()
    tabela, ponte = TabelaFalsa(), PonteFalsa()
    montagem.controlador.ligar(tabela, ponte)
    assert tabela.passo_a_passo_requested.ligados == [montagem.controlador.iniciar]
    assert ponte.state_changed.ligados == [montagem.controlador.estado_mudou]


def test_o_pedido_do_editor_chega_ao_controlador_com_os_ids_escolhidos():
    montagem = Montagem()
    tabela, ponte = TabelaFalsa(), PonteFalsa()
    montagem.controlador.ligar(tabela, ponte)
    segundo = montagem.janela._current_map.commands[1].id
    tabela.passo_a_passo_requested.emit({segundo})
    assert montagem.controlador.controle.sessao.total == 2  # do segundo comando em diante
    assert montagem.motor.executados[0].name == "__passo__ Minha automação"


# ------------------------------------------------------------------------------------------------ iniciar
def test_iniciar_abre_a_janelinha_com_o_texto_de_comecando_e_sem_proximo():
    montagem = Montagem()
    montagem.controlador.iniciar(set())
    assert montagem.painel.mostrados == [("Começando...", False)] and montagem.painel.visivel
    assert montagem.avisos == []


def test_iniciar_com_a_automacao_rodando_avisa_e_nao_abre_a_janelinha():
    montagem = Montagem(estado=State.RUNNING)
    montagem.controlador.iniciar(set())
    assert montagem.avisos == [MOTIVO_EM_EXECUCAO]
    assert montagem.paineis == [] and montagem.motor.executados == []


def test_iniciar_sem_comando_ativo_avisa():
    montagem = Montagem(make_map([key("A", 0.0, enabled=False)]))
    montagem.controlador.iniciar(set())
    assert montagem.avisos == [MOTIVO_SEM_COMANDOS] and montagem.paineis == []


def test_iniciar_sem_automacao_aberta_nao_faz_nada():
    montagem = Montagem(com_mapa=False)
    montagem.controlador.iniciar(set())
    assert montagem.avisos == [] and montagem.paineis == [] and montagem.motor.executados == []


def test_a_janelinha_e_criada_uma_vez_e_reaproveitada_no_passo_a_passo_seguinte():
    montagem = Montagem()
    montagem.controlador.iniciar(set())
    montagem.motor.state.force_to_idle()
    montagem.controlador.estado_mudou(State.RUNNING, State.IDLE)  # acabou
    montagem.controlador.iniciar(set())
    assert len(montagem.paineis) == 1
    assert [t for t, _ in montagem.painel.mostrados] == ["Começando...", "Começando..."]


# ------------------------------------------------------------------------------------------------ mudanças de estado
def test_parado_num_passo_a_janelinha_mostra_o_passo_e_libera_o_proximo():
    montagem = Montagem()
    montagem.controlador.iniciar(set())
    montagem.parar_no_primeiro_comando()
    montagem.controlador.estado_mudou(State.RUNNING, State.PAUSED)
    assert montagem.painel.mostrados[-1] == (PASSO_1, True)


def test_pausado_antes_do_primeiro_comando_a_janelinha_nao_libera_o_proximo():
    # PAUSED por outro caminho (a tecla de pausa) antes de o motor chegar ao primeiro comando: ainda não há passo esperando.
    montagem = Montagem()
    montagem.controlador.iniciar(set())
    montagem.motor.ficar_pausado()
    montagem.controlador.estado_mudou(State.RUNNING, State.PAUSED)
    assert montagem.painel.mostrados[-1] == ("Começando...", False)


def test_executando_o_passo_a_janelinha_diz_qual_e_trava_o_proximo():
    montagem = Montagem()
    montagem.controlador.iniciar(set())
    montagem.parar_no_primeiro_comando()
    montagem.controlador.estado_mudou(State.RUNNING, State.PAUSED)
    montagem.painel.ao_proximo()
    montagem.controlador.estado_mudou(State.PAUSED, State.RUNNING)
    assert montagem.painel.mostrados[-1] == ("Executando o passo 1 de 3...", False)


def test_ao_terminar_a_janelinha_some_o_gancho_e_solto_e_a_barra_avisa():
    montagem = Montagem()
    montagem.controlador.iniciar(set())
    montagem.parar_no_primeiro_comando()
    montagem.controlador.estado_mudou(State.RUNNING, State.PAUSED)
    montagem.motor.state.force_to_idle()
    montagem.controlador.estado_mudou(State.STOPPING, State.IDLE)
    assert montagem.painel.visivel is False and montagem.painel.escondidos == 1
    assert montagem.motor.passo_a_passo is None and montagem.controlador.controle.sessao is None
    assert montagem.janela.status_bar.mensagens == [("Passo a passo encerrado.", 5000)]
    assert montagem.registro[-1] == "PASSO A PASSO encerrado no passo=1 de 3"


def test_depois_de_encerrado_os_avisos_de_estado_nao_fazem_nada():
    montagem = Montagem()
    montagem.controlador.iniciar(set())
    montagem.controlador.estado_mudou(State.RUNNING, State.IDLE)
    escondidos, mensagens, mostrados = montagem.painel.escondidos, list(montagem.janela.status_bar.mensagens), list(montagem.painel.mostrados)
    for anterior, novo in ((State.IDLE, State.RUNNING), (State.RUNNING, State.PAUSED), (State.RUNNING, State.IDLE)):
        montagem.controlador.estado_mudou(anterior, novo)  # uma execução comum, de outra automação
    assert montagem.painel.escondidos == escondidos == 1
    assert montagem.janela.status_bar.mensagens == mensagens and montagem.painel.mostrados == mostrados


def test_sem_passo_a_passo_nenhum_aviso_cria_a_janelinha():
    montagem = Montagem()
    for anterior, novo in ((State.IDLE, State.RUNNING), (State.RUNNING, State.PAUSED), (State.PAUSED, State.RUNNING),
                           (State.RUNNING, State.IDLE)):
        montagem.controlador.estado_mudou(anterior, novo)
    assert montagem.paineis == [] and montagem.janela.status_bar.mensagens == []


def test_parando_o_estado_stopping_nao_muda_a_janelinha():
    montagem = Montagem()
    montagem.controlador.iniciar(set())
    antes = list(montagem.painel.mostrados)
    montagem.controlador.estado_mudou(State.RUNNING, State.STOPPING)
    assert montagem.painel.mostrados == antes and montagem.painel.escondidos == 0


def test_se_o_usuario_ja_pediu_para_continuar_a_pausa_e_desfeita_sem_mostrar_nada():
    montagem = Montagem()
    montagem.controlador.iniciar(set())
    montagem.motor.decidir_parar(montagem.controlador.controle, montagem._evento_do_primeiro_comando())  # o motor decidiu parar...
    montagem.controlador.continuar_sem_parar()  # ...o usuário clicou um instante depois (o estado ainda é RUNNING)...
    montagem.motor.ficar_pausado()  # ...e só então o motor ficou parado
    antes = list(montagem.painel.mostrados)
    montagem.controlador.estado_mudou(State.RUNNING, State.PAUSED)
    assert montagem.motor.retomadas == 1 and montagem.painel.mostrados == antes


# ------------------------------------------------------------------------------------------------ botões
def test_proximo_passo_libera_o_motor_parado_num_passo():
    montagem = Montagem()
    montagem.controlador.iniciar(set())
    montagem.parar_no_primeiro_comando()
    montagem.painel.ao_proximo()
    assert montagem.motor.retomadas == 1


def test_proximo_passo_fora_de_uma_parada_nao_faz_nada():
    montagem = Montagem()
    montagem.controlador.iniciar(set())
    montagem.painel.ao_proximo()
    assert montagem.motor.retomadas == 0


def test_continuar_sem_parar_libera_o_motor_e_a_janelinha_diz_que_continua():
    montagem = Montagem()
    montagem.controlador.iniciar(set())
    montagem.parar_no_primeiro_comando()
    montagem.painel.ao_continuar()
    assert montagem.motor.retomadas == 1
    assert montagem.painel.mostrados[-1] == ("Continuando sem parar...", False)


def test_continuar_sem_parar_depois_de_continuar_nao_repete():
    montagem = Montagem()
    montagem.controlador.iniciar(set())
    montagem.painel.ao_continuar()
    mostrados = list(montagem.painel.mostrados)
    montagem.painel.ao_continuar()
    assert montagem.painel.mostrados == mostrados


def test_parar_pede_a_parada_ao_motor():
    montagem = Montagem()
    montagem.controlador.iniciar(set())
    montagem.painel.ao_parar()
    assert montagem.motor.paradas == 1


def test_os_botoes_sem_passo_a_passo_nao_quebram():
    montagem = Montagem()
    montagem.controlador.proximo()
    montagem.controlador.continuar_sem_parar()
    montagem.controlador.parar()
    assert montagem.motor.retomadas == 0 and montagem.paineis == []


# ------------------------------------------------------------------------------------------------ o canto da tela
def test_a_janelinha_encosta_no_canto_de_baixo_a_direita_da_area_util():
    # área útil de 1920 x 1040 (a tela de 1080 menos a barra de tarefas): o último ponto é (1919, 1039)
    x, y = posicao_no_canto(1919, 1039, 300, 120)
    assert (x, y) == (1620, 920)
    assert x + 300 - 1 == 1919 and y + 120 - 1 == 1039, "o último ponto da janela é o último ponto da área"


def test_o_canto_vale_para_uma_area_que_nao_comeca_na_origem():
    # um segundo monitor à direita: a área vai de x = 1920 a 3839
    assert posicao_no_canto(3839, 1039, 300, 120) == (3540, 920)


# ------------------------------------------------------------------------------------------------ com o motor de verdade
@contextlib.contextmanager
def mundo(make_engine):
    """`with mundo(make_engine) as (controlador, janela, backend, paineis, avisos):` Motor real com relógio virtual e o aviso de
    estado ligado direto ao controlador (na thread do motor, que no app é a ponte entregando na thread da janela: a lógica é a
    mesma). Ao sair o motor é parado, passando ou falhando. (Não é fixture: o projeto só aceita fixtures no conftest.py.)"""
    motor, backend = make_engine()
    janela = JanelaFalsa(motor, _tres())
    paineis, avisos = [], []

    def criar(ao_proximo, ao_continuar, ao_parar):
        paineis.append(PainelFalso(ao_proximo, ao_continuar, ao_parar))
        return paineis[-1]

    controlador = ControladorPassoAPasso(janela, criar_painel=criar, avisar=avisos.append, registrar=lambda texto: None)
    motor.state.on_change(controlador.estado_mudou)
    try:
        yield controlador, janela, backend, paineis, avisos
    finally:
        motor.stop(wait=True)


def _com_texto(prefixo):
    return lambda item: item is not None and item[0].startswith(prefixo)


def test_de_verdade_o_botao_proximo_anda_um_comando_por_vez_ate_o_fim(make_engine):
    with mundo(make_engine) as (controlador, janela, backend, paineis, _avisos):
        controlador.iniciar(set())
        painel = paineis[0]
        assert painel.esperar(_com_texto("Passo 1")) == (PASSO_1, True)
        assert backend.events == []
        painel.ao_proximo()
        assert painel.esperar(_com_texto("Passo 2")) == ("Passo 2 de 3: Apertar e soltar a tecla B", True)
        assert [e[1:] for e in backend.events] == [("key_down", "A"), ("key_up", "A")]
        painel.ao_proximo()
        painel.esperar(_com_texto("Passo 3"))
        painel.ao_proximo()
        assert painel.esperar(lambda item: item is None) is None  # a janelinha sumiu: acabou
        assert [e[1:] for e in backend.events] == [("key_down", "A"), ("key_up", "A"), ("key_down", "B"), ("key_up", "B"),
                                                    ("key_down", "C"), ("key_up", "C")]
        assert janela.engine.passo_a_passo is None and controlador.controle.sessao is None
        assert janela.status_bar.mensagens == [("Passo a passo encerrado.", 5000)]


def test_de_verdade_parar_encerra_no_meio_e_a_janelinha_some(make_engine):
    with mundo(make_engine) as (controlador, janela, backend, paineis, _avisos):
        controlador.iniciar(set())
        painel = paineis[0]
        painel.esperar(_com_texto("Passo 1"))
        painel.ao_proximo()
        painel.esperar(_com_texto("Passo 2"))
        painel.ao_parar()
        assert painel.esperar(lambda item: item is None) is None
        assert [e[1:] for e in backend.events] == [("key_down", "A"), ("key_up", "A")]
        assert janela.engine.state.state == State.IDLE and janela.engine.passo_a_passo is None


def test_de_verdade_continuar_sem_parar_termina_o_resto_e_a_janelinha_some(make_engine):
    with mundo(make_engine) as (controlador, janela, backend, paineis, _avisos):
        controlador.iniciar(set())
        painel = paineis[0]
        painel.esperar(_com_texto("Passo 1"))
        painel.ao_proximo()
        painel.esperar(_com_texto("Passo 2"))
        painel.ao_continuar()
        assert painel.esperar(lambda item: item is None) is None
        assert [e[1:] for e in backend.events] == [("key_down", "A"), ("key_up", "A"), ("key_down", "B"), ("key_up", "B"),
                                                    ("key_down", "C"), ("key_up", "C")]
        assert janela.engine.state.state == State.IDLE


def test_de_verdade_comecar_do_meio_e_depois_de_novo_do_comeco(make_engine):
    with mundo(make_engine) as (controlador, janela, backend, paineis, _avisos):
        segundo = janela._current_map.commands[1].id
        controlador.iniciar({segundo})
        painel = paineis[0]
        assert painel.esperar(_com_texto("Passo 1")) == ("Passo 1 de 2: Apertar e soltar a tecla B", True)
        painel.ao_continuar()
        painel.esperar(lambda item: item is None)
        controlador.iniciar(set())  # de novo, agora a automação toda
        assert painel.esperar(_com_texto("Passo 1")) == (PASSO_1, True)
        assert len(paineis) == 1
        painel.ao_parar()
        painel.esperar(lambda item: item is None)
