"""Validação das condições de espera por imagem: nunca lança exceção e recusa o que o executor recusaria.

Os parâmetros da condição (`confidence`, `interval`, `region`) são um dicionário que a leitura do mapa copia sem converter.
Um valor mal digitado num JSON editado à mão (`"confidence": "0,9"`, com vírgula) passava pela leitura e o `validate()`
LANÇAVA ValueError/TypeError na hora de iniciar, em vez de devolver uma mensagem: o usuário via "could not convert string to
float" sem saber de qual comando. E um valor de região que o executor não consegue converter (`"x": "abc"`) passava na
validação e só falhava no meio da execução, dentro de `vision.capture_region`.

Princípio (o mesmo da F2, `test_validation_gaps.py`): a validação devolve uma mensagem para exatamente o que o executor
recusaria, nem mais nem menos, e nunca lança. As contas do executor são:
    confiança e intervalo   float(parametros.get(chave, padrão) or padrão)          (input_system, espera por imagem)
    região                  int(regiao.get(chave, 0)) para x, y, w e h              (vision.capture_region)
"""
import pytest

from automationstudio.conditions import WaitCondition, WaitConditionType
from automationstudio.core import Command, InputType, State
from testsupport.helpers import make_map

ERROS_DE_CONTA = (TypeError, ValueError, OverflowError, AttributeError)


def _imagem(**parametros) -> WaitCondition:
    return WaitCondition(type=WaitConditionType.IMAGE, parameters={"image_path": "a.png", **parametros})


def _o_executor_converte(parametros: dict) -> bool:
    """As mesmas contas do executor, copiadas aqui porque `vision.py` só importa com o Qt de verdade."""
    try:
        float(parametros.get("confidence", 0.95) or 0.95)
        float(parametros.get("interval", 0.5) or 0.5)
        regiao = parametros.get("region") or {}
        for chave in ("x", "y", "w", "h"):
            int(regiao.get(chave, 0))
    except ERROS_DE_CONTA:
        return False
    return True


# ------------------------------------------------------------------------------------------------ nunca lança
@pytest.mark.parametrize("chave,valor", [
    ("confidence", "alto"), ("confidence", "0,9"), ("confidence", [1]), ("confidence", 10 ** 400),
    ("interval", "x"), ("interval", "0,5"), ("interval", [0.5]), ("interval", 10 ** 400),
])
def test_valor_ilegivel_de_precisao_ou_intervalo_vira_erro_e_nao_excecao(chave, valor):
    erros = _imagem(**{chave: valor}).validate()
    assert len(erros) == 1, erros
    assert ("Precisão" if chave == "confidence" else "Intervalo") in erros[0], erros
    assert "número" in erros[0] and repr(valor)[:20] in erros[0], erros
    assert len(erros[0]) < 200, "o valor aparece truncado: 400 dígitos não cabem numa mensagem"


def test_a_mensagem_de_virgula_decimal_diz_o_que_fazer():
    # O erro de digitação mais provável de quem escreve em português: 0,9 em vez de 0.9.
    (erro,) = _imagem(confidence="0,9").validate()
    assert "'0,9'" in erro and "ponto" in erro, erro
    (erro,) = _imagem(interval="0,5").validate()
    assert "'0,5'" in erro and "ponto" in erro, erro
    (erro,) = _imagem(confidence="alto").validate()
    assert "ponto" not in erro, erro        # a dica só aparece quando o valor tem vírgula


@pytest.mark.parametrize("chave,valor", [
    ("confidence", "0.9"), ("confidence", "1"), ("confidence", True), ("confidence", None), ("confidence", 0),
    ("interval", "0.5"), ("interval", "2"), ("interval", True), ("interval", None),
])
def test_valor_que_o_executor_converte_continua_valendo(chave, valor):
    # "0.9" (texto com número) e True (1.0) convertem com float(); None e 0 viram o padrão (`valor or padrão`).
    assert _imagem(**{chave: valor}).validate() == []


@pytest.mark.parametrize("chave,valor,trecho", [
    ("confidence", 1.5, "entre 0 e 1"), ("confidence", -0.1, "entre 0 e 1"), ("confidence", float("nan"), "entre 0 e 1"),
    ("confidence", float("inf"), "entre 0 e 1"), ("interval", -1.0, "maior que zero"), ("interval", "-2", "maior que zero"),
])
def test_valor_fora_da_faixa_continua_com_a_mensagem_de_antes(chave, valor, trecho):
    (erro,) = _imagem(**{chave: valor}).validate()
    assert trecho in erro, erro


# ------------------------------------------------------------------------------------------------ região
@pytest.mark.parametrize("chave", ["x", "y", "w", "h"])
@pytest.mark.parametrize("valor", ["abc", "10,5", "10.5", None, [1], {}, float("inf"), float("nan")])
def test_valor_de_regiao_que_o_executor_nao_converte_e_recusado_com_o_nome_da_chave(chave, valor):
    erros = _imagem(region={"x": 1, "y": 2, "w": 30, "h": 40, chave: valor}).validate()
    assert len(erros) == 1, erros
    assert f"'{chave}'" in erros[0] and "número inteiro" in erros[0], erros


@pytest.mark.parametrize("valor", [0, 10, "12", 10.7, True])
def test_valor_de_regiao_que_o_executor_converte_continua_valendo(valor):
    # int("12") = 12, int(10.7) = 10 e int(True) = 1: o executor aceita, a validação também.
    assert _imagem(region={"x": valor, "y": valor, "w": valor, "h": valor}).validate() == []


def test_x_e_y_negativos_continuam_validos_porque_um_monitor_pode_ficar_a_esquerda_ou_acima():
    assert _imagem(region={"x": -1920, "y": -50, "w": 100, "h": 100}).validate() == []


@pytest.mark.parametrize("chave", ["w", "h"])
def test_largura_ou_altura_negativa_continua_recusada_com_a_mensagem_de_antes(chave):
    (erro,) = _imagem(region={"x": 0, "y": 0, "w": 10, "h": 10, chave: -1}).validate()
    assert "Largura/altura" in erro and "negativas" in erro, erro


def test_regiao_com_dois_valores_ruins_aponta_os_dois():
    erros = _imagem(region={"x": "a", "y": 0, "w": "b", "h": 5}).validate()
    assert len(erros) == 2 and "'x'" in erros[0] and "'w'" in erros[1], erros


def test_chaves_ausentes_da_regiao_valem_zero_como_no_executor():
    assert _imagem(region={"w": 10, "h": 10}).validate() == []
    assert _imagem(region={}).validate() == []


def test_regiao_que_nao_e_objeto_continua_com_a_mensagem_de_antes():
    (erro,) = _imagem(region=[1, 2]).validate()
    assert "Região da imagem inválida" in erro, erro


# ------------------------------------------------------------------------------------------------ paridade com o executor
AMOSTRAS_DE_CONTA = ["abc", "0,5", "0.5", "10.5", "12", 7, 10.7, True, None, [1], {}, "", float("inf"), float("nan"), 10 ** 400]


def _decidido_pela_faixa_de_precisao_ou_intervalo(chave, valor) -> bool:
    """True se o valor converte e quem o recusa é a faixa (confiança fora de 0 a 1; intervalo <= 0), não a conversão."""
    padrao = 0.95 if chave == "confidence" else 0.5
    try:
        numero = float(valor or padrao)
    except ERROS_DE_CONTA:
        return False
    return (not 0.0 <= numero <= 1.0) if chave == "confidence" else numero <= 0


def _decidido_pela_faixa_da_regiao(chave, valor) -> bool:
    try:
        numero = int(valor)
    except ERROS_DE_CONTA:
        return False
    return chave in ("w", "h") and numero < 0


# As amostras que a faixa decide têm testes próprios acima; aqui ficam só as que a CONVERSÃO decide.
PRECISAO_E_INTERVALO = [(c, v) for c in ("confidence", "interval") for v in AMOSTRAS_DE_CONTA
                        if not _decidido_pela_faixa_de_precisao_ou_intervalo(c, v)]
VALORES_DE_REGIAO = [(c, v) for c in ("x", "y", "w", "h") for v in AMOSTRAS_DE_CONTA
                     if v != 10 ** 400 and not _decidido_pela_faixa_da_regiao(c, v)]   # int() converte 10**400; ninguém digita isso


def test_as_amostras_de_paridade_cobrem_os_dois_lados():
    # Sem isso a paridade poderia passar "de graça" com uma lista que só tem valores bons (ou só ruins).
    for amostras, parametros_de in (
        (PRECISAO_E_INTERVALO, lambda c, v: {c: v}),
        (VALORES_DE_REGIAO, lambda c, v: {"region": {"x": 1, "y": 2, "w": 30, "h": 40, c: v}}),
    ):
        convertem = [_o_executor_converte(parametros_de(c, v)) for c, v in amostras]
        assert any(convertem) and not all(convertem)


@pytest.mark.parametrize("chave,valor", PRECISAO_E_INTERVALO)
def test_paridade_precisao_e_intervalo(chave, valor):
    parametros = {"image_path": "a.png", chave: valor}
    assert (WaitCondition(type=WaitConditionType.IMAGE, parameters=parametros).validate() == []) == _o_executor_converte(parametros)


@pytest.mark.parametrize("chave,valor", VALORES_DE_REGIAO)
def test_paridade_da_regiao(chave, valor):
    parametros = {"image_path": "a.png", "region": {"x": 1, "y": 2, "w": 30, "h": 40, chave: valor}}
    assert (WaitCondition(type=WaitConditionType.IMAGE, parameters=parametros).validate() == []) == _o_executor_converte(parametros)


# ------------------------------------------------------------------------------------------------ o efeito para o usuário
def _mapa_com(**parametros):
    espera = Command(type=InputType.WAIT, conditions=[_imagem(**parametros)])
    return make_map([espera, Command(type=InputType.KEY, target="A", start=1.0, duration=0.1)])


@pytest.mark.parametrize("parametros,trecho", [
    ({"confidence": "0,9"}, "Precisão"),
    ({"interval": "x"}, "Intervalo"),
    ({"region": {"x": "abc", "y": 0, "w": 10, "h": 10}}, "número inteiro"),
], ids=["precisao", "intervalo", "regiao"])
def test_o_mapa_valida_com_mensagem_que_aponta_o_comando(parametros, trecho):
    mapa = _mapa_com(**parametros)
    erros = mapa.validate()
    assert len(erros) == 1 and trecho in erros[0] and mapa.commands[0].id in erros[0], erros


@pytest.mark.parametrize("parametros,trecho", [
    ({"confidence": "0,9"}, "Precisão"),
    ({"region": {"x": "abc", "y": 0, "w": 10, "h": 10}}, "número inteiro"),
], ids=["precisao", "regiao"])
def test_o_motor_recusa_o_mapa_antes_de_enviar_qualquer_entrada(make_engine, parametros, trecho):
    motor, backend = make_engine()
    with pytest.raises(ValueError, match="Mapa inválido") as erro:
        motor.run(_mapa_com(**parametros))
    assert trecho in str(erro.value)
    assert backend.events == [] and motor.state.state == State.IDLE and motor._thread is None
