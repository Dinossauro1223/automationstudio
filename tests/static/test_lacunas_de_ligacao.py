"""LACUNAS DE LIGAÇÃO conhecidas: o que a tela promete e o código ainda não faz, achado lendo o código (nenhum Qt é preciso).

Achado 2.11 (descoberto na 25.8, ao ler `_on_hotkey_triggered` para a ativação por mapa): as teclas de controle "Pausar
automação" (F9) e "Continuar automação" (F10) são registradas e aparecem em Configurações, mas a janela principal só atende
`map:`, `control:emergency`, `record:toggle` e `record:cancel`. O disparo de `control:pause` e `control:resume` chega em
`_on_hotkey_triggered`, não casa com ramo nenhum e some; `ExecutionEngine.pause()` e `resume()` existem e são testados no motor,
mas nada na interface os chama. Ou seja: apertar F9 não pausa. (Confirmado pela leitura; a janela real nunca foi acionada aqui.)

Este teste fica como xfail(strict=True), como os de `unit/test_validation_gaps.py`: quando a lacuna for corrigida ele passa, o
pytest reclama e o marcador sai. Não fixa o comportamento atual: documenta o que falta. A correção é um ponto à parte (pede
decisão: o que a barra de estado mostra, e o que acontece com uma pausa durante uma espera por aplicativo).

O verificador é testado à parte (controles abaixo): sem eles um xfail "falharia" por qualquer motivo, inclusive por o verificador
não achar o método, e a lacuna pareceria documentada sem estar.
"""
import ast
import pathlib

import pytest

JANELA = pathlib.Path(__file__).resolve().parents[2] / "automationstudio" / "main_window.py"


def _chamadas(no, nome: str) -> bool:
    return any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == nome for c in ast.walk(no))


def _compara_com(teste, texto: str) -> bool:
    return any(isinstance(c, ast.Constant) and c.value == texto for c in ast.walk(teste))


def ramo_chama(fonte: str, acao: str, chamada: str) -> bool:
    """True se `MainWindow._on_hotkey_triggered` tem um ramo para `acao` que chega a chamar `.chamada()`, direto ou por um
    método da própria janela (`self.metodo()`, um nível)."""
    arvore = ast.parse(fonte)
    janela = next(n for n in ast.walk(arvore) if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
    metodos = {n.name: n for n in janela.body if isinstance(n, ast.FunctionDef)}
    for no in ast.walk(metodos["_on_hotkey_triggered"]):
        if not (isinstance(no, ast.If) and _compara_com(no.test, acao)):
            continue
        corpo = ast.Module(body=no.body, type_ignores=[])
        if _chamadas(corpo, chamada):
            return True
        for sub in ast.walk(corpo):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and isinstance(sub.func.value, ast.Name)
                    and sub.func.value.id == "self" and sub.func.attr in metodos and _chamadas(metodos[sub.func.attr], chamada)):
                return True
    return False


# ------------------------------------------------------------------------------------------------ a lacuna (achado 2.11)
@pytest.mark.xfail(strict=True, reason="achado 2.11: as teclas F9 e F10 (pausar e continuar) são registradas mas nada as atende; "
                                       "engine.pause() e resume() nunca são chamados pela janela")
def test_as_teclas_de_pausar_e_continuar_deveriam_pausar_e_continuar_o_motor():
    fonte = JANELA.read_text(encoding="utf-8")
    assert ramo_chama(fonte, "control:pause", "pause"), "control:pause não chega a engine.pause()"
    assert ramo_chama(fonte, "control:resume", "resume"), "control:resume não chega a engine.resume()"


# ------------------------------------------------------------------------------------------------ controles do verificador
_MOLDE = '''
class MainWindow:
    def _on_hotkey_triggered(self, action_id):
        if action_id.startswith("map:"):
            self.rodar()
        elif action_id == "control:emergency":
            self._on_emergency()
{extra}
    def _on_emergency(self):
        self.engine.emergency_stop()
    def _pausar(self):
        self.engine.pause()
'''


def test_o_verificador_acha_o_ramo_que_chama_direto_e_o_que_chama_por_um_metodo_da_janela():
    direto = _MOLDE.format(extra='        elif action_id == "control:pause":\n            self.engine.pause()\n')
    por_metodo = _MOLDE.format(extra='        elif action_id == "control:pause":\n            self._pausar()\n')
    assert ramo_chama(direto, "control:pause", "pause")
    assert ramo_chama(por_metodo, "control:pause", "pause")
    assert ramo_chama(por_metodo, "control:emergency", "emergency_stop"), "a emergência chama por um método (um nível)"


def test_o_verificador_recusa_ramo_ausente_ramo_que_nao_chama_e_chamada_fora_do_ramo():
    sem_ramo = _MOLDE.format(extra="")
    assert not ramo_chama(sem_ramo, "control:pause", "pause"), "um método que chama pause() mas sem ramo para a tecla não conta"
    ramo_vazio = _MOLDE.format(extra='        elif action_id == "control:pause":\n            self.status("pausou")\n')
    assert not ramo_chama(ramo_vazio, "control:pause", "pause")
    assert not ramo_chama(ramo_vazio, "control:emergency", "pause"), "chamar outra coisa no ramo certo não conta"


def test_no_codigo_real_o_verificador_enxerga_os_ramos_que_existem():
    """Controle positivo, contra o arquivo de verdade: a emergência chega a `engine.emergency_stop()` (por `_on_emergency`) e as
    teclas de gravação chegam aos seus métodos. Sem isto, o xfail acima passaria a "falhar" também se `_on_hotkey_triggered`
    mudasse de forma e o verificador deixasse de achá-lo, e a lacuna pareceria documentada sem estar."""
    fonte = JANELA.read_text(encoding="utf-8")
    assert ramo_chama(fonte, "control:emergency", "emergency_stop")
    assert ramo_chama(fonte, "record:toggle", "_toggle_recording")
    assert ramo_chama(fonte, "record:cancel", "_cancel_recording")
