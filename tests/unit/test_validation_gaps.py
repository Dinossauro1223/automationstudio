"""LACUNAS CONHECIDAS de validação, descobertas ao escrever a suíte da 25.5.

São comportamentos desejados que o código ainda NÃO tem. Ficam como xfail(strict=True): quando a lacuna for
corrigida o teste passa e o pytest manda remover o marcador. Não fixam o comportamento atual: documentam o que falta.
O formato de mapa v2 (Ponto 3) trata estas validações na leitura.
"""
import pytest

from automationstudio.core import AutomationMap, Command, InputType


@pytest.mark.xfail(strict=True, reason="lacuna: validate() não confere o nome do botão do mouse; 'lefft' só falha na execução")
def test_botao_de_mouse_desconhecido_deveria_ser_erro_de_validacao():
    assert Command(type=InputType.MOUSE_BUTTON, target="lefft", duration=0.1).validate()


@pytest.mark.xfail(strict=True, reason="lacuna: abrir aplicativo sem alvo passa na validação e falha na execução")
def test_abrir_aplicativo_sem_alvo_deveria_ser_erro_de_validacao():
    assert Command(type=InputType.APP_OPEN, target="").validate()


@pytest.mark.xfail(strict=True, reason="lacuna: repeat_count aceita qualquer inteiro; só -1 (infinito) e positivos fazem sentido")
def test_repeat_count_menor_que_menos_um_deveria_ser_invalido():
    ok = Command(type=InputType.KEY, target="A", duration=0.1)
    assert AutomationMap(name="M", commands=[ok], repeat_count=-2).validate()
