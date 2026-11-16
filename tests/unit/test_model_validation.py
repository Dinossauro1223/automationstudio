"""Validação do modelo: Command.validate() e AutomationMap.validate()."""
import pytest

from automationstudio.conditions import WaitCondition, WaitConditionType
from automationstudio import core
from automationstudio.core import ActionType, AutomationMap, Command, InputType


def _espera() -> list:
    return [WaitCondition(type=WaitConditionType.DELAY, timeout=0.5)]


TIPOS_SEM_DURACAO = [
    (InputType.MOUSE_MOVE, {"x": 5, "y": 6}),
    (InputType.MOUSE_SCROLL, {"scroll_dy": 2}),
    (InputType.WAIT, {"conditions": None}),  # preenchido no teste
    (InputType.TEXT, {"text": "a"}),
    (InputType.APP_OPEN, {"target": "notepad.exe"}),
]


@pytest.mark.parametrize("tipo,extra", TIPOS_SEM_DURACAO, ids=[t[0].value for t in TIPOS_SEM_DURACAO])
def test_tipos_sem_tempo_pressionado_aceitam_duracao_zero(tipo, extra):
    extra = {**extra, "conditions": _espera()} if tipo == InputType.WAIT else extra
    assert Command(type=tipo, duration=0.0, **extra).validate() == []


@pytest.mark.parametrize("tipo,alvo", [(InputType.KEY, "A"), (InputType.MOUSE_BUTTON, "left")])
def test_pressionar_e_soltar_com_duracao_zero_e_erro(tipo, alvo):
    erros = Command(type=tipo, target=alvo, duration=0.0).validate()
    assert len(erros) == 1 and "duração igual a 0" in erros[0]


@pytest.mark.parametrize("acao", [ActionType.PRESS, ActionType.RELEASE])
def test_pressionar_ou_soltar_isolado_aceita_duracao_zero(acao):
    assert Command(type=InputType.KEY, target="A", action=acao, duration=0.0).validate() == []


@pytest.mark.parametrize("tipo", [InputType.KEY, InputType.MOUSE_BUTTON])
def test_tecla_e_botao_exigem_alvo(tipo):
    erros = Command(type=tipo, target="", duration=0.1).validate()
    assert len(erros) == 1 and "sem tecla/botão" in erros[0]


def test_duracao_e_inicio_negativos_sao_erros():
    assert any("duração negativa" in e for e in Command(type=InputType.KEY, target="A", duration=-1).validate())
    assert any("início negativo" in e for e in Command(type=InputType.KEY, target="A", start=-1, duration=0.1).validate())


def test_mover_exige_posicao_texto_exige_conteudo_e_espera_exige_condicao():
    assert any("sem posição" in e for e in Command(type=InputType.MOUSE_MOVE).validate())
    assert any("sem conteúdo" in e for e in Command(type=InputType.TEXT, text="").validate())
    assert any("nenhuma condição" in e for e in Command(type=InputType.WAIT).validate())


@pytest.mark.parametrize("campos", [{"x": 5}, {"y": 6}], ids=["so-x", "so-y"])
def test_mover_com_so_um_dos_eixos_definido_e_erro(campos):
    assert any("sem posição" in e for e in Command(type=InputType.MOUSE_MOVE, **campos).validate())


def test_mover_para_a_origem_ou_com_trajeto_mesclado_e_valido():
    assert Command(type=InputType.MOUSE_MOVE, x=0, y=0).validate() == [], "(0, 0) é uma posição, não a falta dela"
    trajeto = [{"t": 0.0, "x": 1, "y": 2}, {"t": 1.0, "x": 3, "y": 4}]
    assert Command(type=InputType.MOUSE_MOVE, merged_move=True, mouse_path=trajeto).validate() == []


def test_erros_citam_o_id_do_comando():
    comando = Command(type=InputType.KEY, target="", duration=0.1)
    assert comando.validate()[0].startswith(f"[{comando.id}]")


def test_mapa_valido_e_mapa_sem_nome_ou_com_velocidade_invalida():
    ok = Command(type=InputType.KEY, target="A", duration=0.1)
    assert AutomationMap(name="M", commands=[ok]).validate() == []
    assert any("sem nome" in e for e in AutomationMap(name="  ", commands=[ok]).validate())
    assert any("speed" in e for e in AutomationMap(name="M", commands=[ok], speed=0).validate())


def test_mapa_agrega_os_erros_dos_comandos():
    ruim = Command(type=InputType.KEY, target="", duration=0.1)
    erros = AutomationMap(name="M", commands=[ruim]).validate()
    assert any(ruim.id in e for e in erros)
    assert AutomationMap(name="M", commands=[ruim]).is_valid() is False


def test_ids_duplicados_sao_reparados_na_construcao():
    a = Command(type=InputType.KEY, target="A", duration=0.1, id="x")
    b = Command(type=InputType.KEY, target="B", duration=0.1, id="x")
    ids = [c.id for c in AutomationMap(name="M", commands=[a, b]).commands]
    assert len(set(ids)) == 2 and ids[0] == "x"


# ----------------------------------------------------------------------------------- tecla padrão, duração e IDs do mapa
@pytest.mark.parametrize("tecla", [None, ""], ids=["nula", "vazia"])
def test_mapa_criado_sem_tecla_recebe_a_tecla_padrao(tecla):
    # core.py: "Toda automação nova começa com '=' como tecla de iniciação. Também migra mapas antigos que foram salvos
    # sem tecla definida."
    assert AutomationMap(name="M", hotkey=tecla).hotkey == "="


def test_mapa_com_tecla_mantem_a_tecla():
    # A leitura de mapa sem tecla (ausente, nula, vazia) já tem teste em persistence/test_reader_tolerance.py.
    assert AutomationMap(name="M", hotkey="F5").hotkey == "F5"
    assert AutomationMap.from_dict({"name": "M", "hotkey": "F5"}).hotkey == "F5"


def test_duracao_total_de_mapa_vazio_ou_so_com_comandos_desativados_e_zero():
    assert AutomationMap(name="M").total_duration() == 0.0
    desativado = Command(type=InputType.KEY, target="A", duration=1.0, enabled=False)
    assert AutomationMap(name="M", commands=[desativado]).total_duration() == 0.0


def test_a_duracao_total_ignora_os_comandos_desativados_e_pega_o_fim_do_ultimo_ativo():
    ativo = Command(type=InputType.KEY, target="A", start=0.0, duration=0.5)
    desativado = Command(type=InputType.KEY, target="B", start=2.0, duration=1.0, enabled=False)
    assert AutomationMap(name="M", commands=[ativo, desativado]).total_duration() == pytest.approx(ativo.effective_end)


def test_reparo_de_ids_tenta_de_novo_se_o_novo_id_ja_esta_em_uso(monkeypatch):
    # O contador de IDs é sincronizado com o mapa, então isto não acontece na prática; se um dia acontecer, o reparo não
    # pode entregar dois comandos com o mesmo ID.
    a = Command(type=InputType.KEY, target="A", duration=0.1, id="dup")
    b = Command(type=InputType.KEY, target="B", duration=0.1, id="dup")
    entregues = iter(["dup", "novo"])
    monkeypatch.setattr(core, "_next_id", lambda: next(entregues))
    mapa = AutomationMap(name="M", commands=[a, b])
    assert [c.id for c in mapa.commands] == ["dup", "novo"]

