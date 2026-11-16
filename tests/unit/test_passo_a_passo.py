"""Passo a passo (F52): a lógica sem motor de verdade e sem Qt (descrições, escolha dos comandos, cópia da automação, sessão e
os botões). O motor de verdade e o relógio virtual estão em tests/engine/test_passo_a_passo_motor.py."""
import copy

import pytest

from automationstudio import passo_a_passo
from automationstudio.conditions import WaitCondition, WaitConditionType
from automationstudio.core import (ActionType, Command, Event, EventKind, InputType, State, StateManager, build_timeline)
from automationstudio.passo_a_passo import (ControleDePassos, MOTIVO_EM_EXECUCAO, MOTIVO_GRAVANDO, MOTIVO_OCUPADO,
                                            MOTIVO_SEM_COMANDOS, PassoAPasso, descrever_comando, ids_a_partir_daqui,
                                            montar_mapa_de_passos)
from testsupport.fakes_passo_a_passo import MotorFalso
from testsupport.helpers import key, make_map


def _comando(tipo, **kwargs) -> Command:
    return Command(type=tipo, **kwargs)


# ------------------------------------------------------------------------------------------ descrição de um comando
@pytest.mark.parametrize("comando, esperado", [
    (key("A", 0.0, 0.2), "Apertar e soltar a tecla A"),
    (key("X", 0.0, 0.0, action=ActionType.PRESS), "Segurar a tecla X"),
    (key("X", 0.0, 0.0, action=ActionType.RELEASE), "Soltar a tecla X"),
    (_comando(InputType.MOUSE_BUTTON, target="left", duration=0.1), "Clicar com o botão esquerdo do mouse"),
    (_comando(InputType.MOUSE_BUTTON, target="right", duration=0.1), "Clicar com o botão direito do mouse"),
    (_comando(InputType.MOUSE_BUTTON, target="middle", duration=0.1), "Clicar com o botão do meio do mouse"),
    (_comando(InputType.MOUSE_BUTTON, target="left", action=ActionType.PRESS), "Segurar o botão esquerdo do mouse"),
    (_comando(InputType.MOUSE_BUTTON, target="left", action=ActionType.RELEASE), "Soltar o botão esquerdo do mouse"),
    (_comando(InputType.MOUSE_BUTTON, target="x1", duration=0.1), "Clicar com o botão lateral 1 do mouse"),
    (_comando(InputType.MOUSE_MOVE, x=10, y=20), "Mover o mouse para (10, 20)"),
    (_comando(InputType.MOUSE_MOVE, x=5, y=-7, relative=True), "Mover o mouse (5, -7) a partir de onde ele está"),
    (_comando(InputType.MOUSE_MOVE, x=1, y=2, merged_move=True, mouse_path=[{"t": 0.0, "x": 1, "y": 2}, {"t": 1.0, "x": 9, "y": 9}],
              duration=0.5), "Mover o mouse seguindo o percurso gravado"),
    (_comando(InputType.MOUSE_SCROLL, scroll_dx=0, scroll_dy=-3), "Rolar a roda do mouse (horizontal 0, vertical -3)"),
    (_comando(InputType.TEXT, text="olá mundo"), 'Digitar "olá mundo"'),
    (_comando(InputType.APP_OPEN, target="notepad.exe"), "Abrir o aplicativo notepad.exe"),
])
def test_descricao_de_cada_tipo_de_comando(comando, esperado):
    assert descrever_comando(comando) == esperado


def test_um_texto_longo_e_cortado_e_as_quebras_de_linha_viram_espaco():
    longo = _comando(InputType.TEXT, text="a" * 60)
    assert descrever_comando(longo) == 'Digitar "' + "a" * passo_a_passo.TAMANHO_DO_TEXTO + '…"'
    assert descrever_comando(_comando(InputType.TEXT, text="linha 1\n\nlinha  2")) == 'Digitar "linha 1 linha 2"'


def test_o_texto_que_cabe_no_limite_nao_ganha_reticencias():
    limite = passo_a_passo.TAMANHO_DO_TEXTO
    assert descrever_comando(_comando(InputType.TEXT, text="a" * limite)) == 'Digitar "' + "a" * limite + '"'
    assert descrever_comando(_comando(InputType.TEXT, text="a" * (limite + 1))) == 'Digitar "' + "a" * limite + '…"'


@pytest.mark.parametrize("condicoes, esperado", [
    ([WaitCondition(type=WaitConditionType.DELAY, timeout=2.0)], "Esperar 2 s"),
    ([WaitCondition(type=WaitConditionType.DELAY, timeout=1.5)], "Esperar 1,5 s"),
    ([WaitCondition(type=WaitConditionType.DELAY, after=0.25)], "Esperar 0,25 s"),
    # com os dois preenchidos o motor espera o `timeout` (e só usa o `after` se o `timeout` for zero): a descrição diz o mesmo
    ([WaitCondition(type=WaitConditionType.DELAY, timeout=2.0, after=1.0)], "Esperar 2 s"),
    ([WaitCondition(type=WaitConditionType.IMAGE, timeout=3.0, parameters={"image_path": "a.png"})],
     "Esperar uma imagem aparecer na tela"),
    ([WaitCondition(type=WaitConditionType.PROCESS, target="notepad.exe")], "Esperar o aplicativo notepad.exe ficar pronto"),
    ([WaitCondition(type=WaitConditionType.PROCESS)], "Esperar o aplicativo ficar pronto"),
    ([WaitCondition(type=WaitConditionType.DELAY, timeout=1.0), WaitCondition(type=WaitConditionType.IMAGE, timeout=3.0)],
     "Esperar 1 s, depois esperar uma imagem aparecer na tela"),
    ([], "Esperar"),
])
def test_o_comando_esperar_e_descrito_pelas_suas_condicoes(condicoes, esperado):
    # O "Esperar" do app é feito só de condições (a duração dele é 0): descrever pela duração dava "Esperar 0 s".
    assert descrever_comando(_comando(InputType.WAIT, conditions=condicoes)) == esperado


def test_a_descricao_que_o_usuario_escreveu_vai_entre_parenteses_no_fim():
    assert descrever_comando(key("A", 0.0, 0.2, description="abre o menu")) == "Apertar e soltar a tecla A (abre o menu)"
    assert descrever_comando(key("A", 0.0, 0.2, description="  ")) == "Apertar e soltar a tecla A"
    assert descrever_comando(key("A", 0.0, 0.2, description="Apertar e soltar a tecla A")) == "Apertar e soltar a tecla A"


# ------------------------------------------------------------------------------------------ quais comandos
def _tres():
    return [key("A", 0.0), key("B", 1.0), key("C", 2.0)]


def test_sem_selecao_sao_todos_os_comandos_ativos():
    comandos = _tres()
    comandos[1].enabled = False
    assert ids_a_partir_daqui(comandos, ()) == [comandos[0].id, comandos[2].id]
    assert ids_a_partir_daqui(comandos, None) == [comandos[0].id, comandos[2].id]
    assert ids_a_partir_daqui(comandos, set()) == [comandos[0].id, comandos[2].id]


def test_com_selecao_e_do_primeiro_da_lista_em_diante_e_nao_so_os_selecionados():
    comandos = _tres()
    assert ids_a_partir_daqui(comandos, {comandos[1].id}) == [comandos[1].id, comandos[2].id]
    assert ids_a_partir_daqui(comandos, {comandos[2].id}) == [comandos[2].id]


def test_o_primeiro_e_o_da_ordem_da_lista_e_nao_o_da_ordem_da_selecao():
    comandos = _tres()
    # um conjunto não tem ordem: vale a posição na lista
    assert ids_a_partir_daqui(comandos, {comandos[2].id, comandos[1].id}) == [comandos[1].id, comandos[2].id]


def test_comandos_desativados_ficam_de_fora_mesmo_no_meio_ou_no_comeco():
    comandos = _tres()
    comandos[0].enabled = False
    comandos[2].enabled = False
    assert ids_a_partir_daqui(comandos, {comandos[0].id}) == [comandos[1].id]
    assert ids_a_partir_daqui(comandos, {comandos[2].id}) == []


def test_ids_que_nao_estao_na_lista_nao_escolhem_nada():
    assert ids_a_partir_daqui(_tres(), {"cmd_999999"}) == []
    assert ids_a_partir_daqui([], ()) == []


# ------------------------------------------------------------------------------------------ a cópia que roda
def test_a_copia_tem_nome_proprio_uma_volta_so_e_a_mesma_velocidade():
    mapa = make_map(_tres(), name="Minha automação", repeat_count=-1, speed=1.5, next_map="Outra", hotkey="F7")
    copia = montar_mapa_de_passos(mapa)
    assert copia.name == "__passo__ Minha automação"
    assert copia.repeat_count == 1 and copia.next_map is None and copia.speed == 1.5
    assert copia.hotkey != "F7", "a cópia não leva o atalho da automação do usuário"


def test_a_copia_nao_mexe_na_automacao_do_usuario():
    mapa = make_map(_tres(), name="Minha automação", repeat_count=-1, next_map="Outra")
    antes = copy.deepcopy(mapa)
    copia = montar_mapa_de_passos(mapa, {mapa.commands[1].id})
    assert copia is not mapa
    assert [(c.id, c.start, c.enabled) for c in mapa.commands] == [(c.id, c.start, c.enabled) for c in antes.commands]
    assert (mapa.name, mapa.repeat_count, mapa.next_map) == (antes.name, antes.repeat_count, antes.next_map)
    assert all(c1 is not c2 for c1 in copia.commands for c2 in mapa.commands)


def test_a_copia_tem_ids_novos_e_comeca_em_zero_mantendo_as_distancias():
    mapa = make_map([key("A", 3.0, 0.2), key("B", 5.0, 0.2), key("C", 9.0, 0.2)])
    copia = montar_mapa_de_passos(mapa, {mapa.commands[1].id})
    assert [c.target for c in copia.commands] == ["B", "C"]
    assert [c.start for c in copia.commands] == [0.0, 4.0]  # B em 0, C a 4 s depois (9 - 5)
    assert not {c.id for c in copia.commands} & {c.id for c in mapa.commands}


def test_a_copia_deixa_de_fora_os_desativados():
    mapa = make_map([key("A", 0.0), key("B", 1.0, enabled=False), key("C", 2.0)])
    copia = montar_mapa_de_passos(mapa)
    assert [c.target for c in copia.commands] == ["A", "C"]


def test_sem_comando_ativo_nao_ha_copia():
    assert montar_mapa_de_passos(make_map([])) is None
    assert montar_mapa_de_passos(make_map([key("A", 0.0, enabled=False)])) is None
    assert montar_mapa_de_passos(make_map(_tres()), {"cmd_999999"}) is None


# ------------------------------------------------------------------------------------------ a sessão
def _sessao(*comandos) -> PassoAPasso:
    return PassoAPasso(make_map(list(comandos) or _tres()))


def _evento(comando: Command, tipo=EventKind.KEY_DOWN) -> Event:
    return Event(time=comando.start, kind=tipo, target=comando.target, command_id=comando.id)


def test_a_sessao_conta_os_comandos_pela_ordem_do_motor_e_nao_pela_lista():
    # B começa antes de A: o motor chega a B primeiro, então B é o passo 1
    a, b = key("A", 5.0), key("B", 1.0)
    sessao = PassoAPasso(make_map([a, b]))
    assert sessao.ordem == [b.id, a.id] and sessao.total == 2
    assert sessao.parar_antes(_evento(b), sessao.mapa) and sessao.numero == 1 and sessao.comando_id == b.id
    assert sessao.parar_antes(_evento(a), sessao.mapa) and sessao.numero == 2 and sessao.comando_id == a.id


def test_so_o_primeiro_evento_de_cada_comando_e_um_passo():
    a = key("A", 0.0, 0.2)
    sessao = PassoAPasso(make_map([a]))
    assert sessao.parar_antes(_evento(a), sessao.mapa) is True
    assert sessao.parar_antes(_evento(a, EventKind.KEY_UP), sessao.mapa) is False
    assert sessao.numero == 1


def test_a_sessao_ignora_outra_automacao_e_nao_conta_nada():
    a = key("A", 0.0)
    sessao = PassoAPasso(make_map([a]))
    assert sessao.parar_antes(_evento(a), make_map([a])) is False
    assert sessao.numero == 0 and sessao.comando_id == ""


def test_a_sessao_encerrada_nao_para_mais():
    a, b = key("A", 0.0), key("B", 1.0)
    sessao = PassoAPasso(make_map([a, b]))
    sessao.ativo = False
    assert sessao.parar_antes(_evento(a), sessao.mapa) is False
    assert sessao.numero == 0


def test_o_texto_do_passo_diz_o_numero_o_total_e_o_que_o_comando_faz():
    a, b = key("A", 0.0), _comando(InputType.TEXT, text="oi", start=1.0)
    sessao = PassoAPasso(make_map([a, b]))
    sessao.parar_antes(_evento(a), sessao.mapa)
    assert sessao.texto_do_passo() == "Passo 1 de 2: Apertar e soltar a tecla A"
    sessao.parar_antes(_evento(b, EventKind.TEXT), sessao.mapa)
    assert sessao.texto_do_passo() == 'Passo 2 de 2: Digitar "oi"'


def test_o_total_de_passos_e_o_da_linha_do_tempo_do_motor():
    mapa = make_map([key("A", 0.0, 0.2), key("B", 1.0, 0.2, enabled=False), _comando(InputType.TEXT, text="x", start=2.0)])
    sessao = PassoAPasso(mapa)
    assert sessao.total == 2 == len({e.command_id for e in build_timeline(mapa)})


# ------------------------------------------------------------------------------------------ o controle (botões)
def _para_no_primeiro(motor, controle) -> None:
    """O motor chegou ao primeiro comando da cópia e parou ali, como o gancho dele faria."""
    motor.parar_num_passo(controle, _evento(controle.sessao.mapa.commands[0]))


def _controle(motor=None) -> tuple[ControleDePassos, MotorFalso, list]:
    """O controle sobre um motor falso e a lista onde ele registra as linhas do log."""
    motor = motor or MotorFalso()
    registro: list[str] = []
    return ControleDePassos(motor, registrar=registro.append), motor, registro


def test_iniciar_roda_a_copia_prende_o_gancho_e_registra_no_log():
    controle, motor, registro = _controle()
    mapa = make_map(_tres(), name="Minha automação")
    assert controle.iniciar(mapa) == ""
    assert len(motor.executados) == 1 and motor.executados[0].name == "__passo__ Minha automação"
    assert motor.passo_a_passo is controle.sessao and controle.sessao.mapa is motor.executados[0]
    assert registro == ["PASSO A PASSO iniciado mapa=Minha automação passos=3"]


@pytest.mark.parametrize("estado, motivo", [
    (State.RUNNING, MOTIVO_EM_EXECUCAO), (State.PAUSED, MOTIVO_EM_EXECUCAO), (State.RECORDING, MOTIVO_GRAVANDO),
    (State.STOPPING, MOTIVO_OCUPADO), (State.ERROR, MOTIVO_OCUPADO)])
def test_iniciar_recusa_com_o_motor_ocupado_e_diz_por_que(estado, motivo):
    controle, motor, registro = _controle(MotorFalso(estado))
    assert controle.iniciar(make_map(_tres())) == motivo
    assert motor.executados == [] and motor.passo_a_passo is None and controle.sessao is None and registro == []


def test_iniciar_sem_comando_ativo_diz_que_nao_ha_o_que_executar():
    controle, motor, _ = _controle()
    assert controle.iniciar(make_map([])) == MOTIVO_SEM_COMANDOS
    assert controle.iniciar(make_map([key("A", 0.0, enabled=False)])) == MOTIVO_SEM_COMANDOS
    assert controle.iniciar(make_map(_tres()), {"cmd_999999"}) == MOTIVO_SEM_COMANDOS
    assert motor.executados == [] and motor.passo_a_passo is None


def test_iniciar_com_automacao_invalida_mostra_os_erros_e_nao_roda():
    invalido = key("A", 0.0)
    invalido.duration = -1.0
    controle, motor, _ = _controle()
    texto = controle.iniciar(make_map([invalido]))
    assert texto.startswith("A automação não pode ser executada:") and "duração negativa" in texto
    assert motor.executados == [] and motor.passo_a_passo is None and controle.sessao is None


def test_iniciar_solta_o_gancho_se_o_motor_recusar():
    controle, motor, registro = _controle(MotorFalso(run_falha=RuntimeError("motor ocupado")))
    texto = controle.iniciar(make_map(_tres()))
    assert texto == "Não foi possível começar o passo a passo: motor ocupado"
    assert motor.passo_a_passo is None and controle.sessao is None and registro == []


def test_o_passo_a_passo_comeca_sem_parar_antes_de_o_motor_chegar_ao_primeiro_comando():
    controle, motor, _ = _controle()
    controle.iniciar(make_map(_tres()))
    assert not controle.parado_num_passo()
    assert controle.texto() == "Começando..."
    assert controle.proximo() is False and motor.retomadas == 0


def test_pausado_antes_de_chegar_ao_primeiro_comando_nao_e_um_passo_esperando():
    # O motor pode ficar PAUSED por outro caminho (a tecla de pausa) antes de chegar ao primeiro comando: ainda não há passo.
    controle, motor, _ = _controle()
    assert controle.iniciar(make_map(_tres())) == ""
    motor.ficar_pausado()
    assert controle.sessao.numero == 0
    assert not controle.parado_num_passo()
    assert controle.proximo() is False and motor.retomadas == 0
    assert controle.texto() == "Começando..."


def test_proximo_so_age_com_o_motor_parado_num_passo():
    controle, motor, _ = _controle()
    controle.iniciar(make_map(_tres()))
    _para_no_primeiro(motor, controle)
    assert controle.parado_num_passo()
    assert controle.proximo() is True and motor.retomadas == 1
    # o motor voltou a RUNNING (está executando o passo): um segundo clique não faz nada
    assert controle.proximo() is False and motor.retomadas == 1


def test_o_texto_acompanha_o_que_esta_acontecendo():
    controle, motor, _ = _controle()
    assert controle.texto() == ""
    controle.iniciar(make_map(_tres()))
    _para_no_primeiro(motor, controle)
    assert controle.texto() == "Passo 1 de 3: Apertar e soltar a tecla A"
    controle.proximo()
    assert controle.texto() == "Executando o passo 1 de 3..."
    controle.continuar_sem_parar()
    assert controle.texto() == "Continuando sem parar..."


def test_continuar_sem_parar_libera_o_motor_parado_e_registra():
    controle, motor, registro = _controle()
    controle.iniciar(make_map(_tres()))
    _para_no_primeiro(motor, controle)
    assert controle.continuar_sem_parar() is True
    assert controle.sessao.ativo is False and motor.retomadas == 1
    assert registro[-1] == "PASSO A PASSO continuar sem parar no passo=1 de 3"
    assert controle.continuar_sem_parar() is False  # já continuou
    assert controle.proximo() is False


def test_continuar_sem_parar_com_o_motor_rodando_so_marca_a_sessao():
    controle, motor, _ = _controle()
    controle.iniciar(make_map(_tres()))
    assert controle.continuar_sem_parar() is True
    assert controle.sessao.ativo is False and motor.retomadas == 0


def test_ao_ficar_pausado_com_continuar_ja_pedido_libera_o_motor_de_novo():
    controle, motor, _ = _controle()
    controle.iniciar(make_map(_tres()))
    controle.continuar_sem_parar()  # o motor ainda rodava
    motor.state.transition_to(State.PAUSED)  # ...e então parou
    assert controle.ao_ficar_pausado() is True and motor.retomadas == 1


def test_ao_ficar_pausado_numa_sessao_ativa_nao_libera_nada():
    controle, motor, _ = _controle()
    controle.iniciar(make_map(_tres()))
    _para_no_primeiro(motor, controle)
    assert controle.ao_ficar_pausado() is False and motor.retomadas == 0
    assert ControleDePassos(MotorFalso()).ao_ficar_pausado() is False  # sem sessão


def test_parar_pede_a_parada_ao_motor():
    controle, motor, _ = _controle()
    controle.iniciar(make_map(_tres()))
    controle.parar()
    assert motor.paradas == 1


def test_terminou_solta_o_gancho_e_registra_onde_acabou():
    controle, motor, registro = _controle()
    controle.iniciar(make_map(_tres()))
    _para_no_primeiro(motor, controle)
    controle.terminou()
    assert motor.passo_a_passo is None and controle.sessao is None
    assert registro[-1] == "PASSO A PASSO encerrado no passo=1 de 3"
    controle.terminou()  # de novo não faz mal nem registra outra vez
    assert registro.count("PASSO A PASSO encerrado no passo=1 de 3") == 1


def test_terminou_nao_solta_o_gancho_de_outra_sessao():
    controle, motor, _ = _controle()
    controle.iniciar(make_map(_tres()))
    outro = object()
    motor.passo_a_passo = outro  # outro dono do gancho
    controle.terminou()
    assert motor.passo_a_passo is outro and controle.sessao is None


def test_o_modulo_da_logica_nao_importa_o_qt():
    import ast
    import pathlib
    arvore = ast.parse(pathlib.Path(passo_a_passo.__file__).read_text(encoding="utf-8"))
    importados = {n.module.split(".")[0] for n in ast.walk(arvore) if isinstance(n, ast.ImportFrom) and n.module}
    importados |= {a.name.split(".")[0] for n in ast.walk(arvore) if isinstance(n, ast.Import) for a in n.names}
    assert "PySide6" not in importados, importados
