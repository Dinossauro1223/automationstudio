"""Janela de mentira para testar os controladores da janela principal (automationstudio/ativacao_ui.py e controle_ui.py) sem ela.

Só tem o que os controladores usam da MainWindow: as configurações de verdade (AppSettings numa pasta temporária), mapas
simples (nome e tecla), o gerenciador de atalhos VERDADEIRO ligado a um monitor falso, o motor (o que o teste passar, em
`engine`; sem ele, nenhum) e listas onde os disparos, os avisos e as mensagens da barra de status caem. Serve com ou sem Qt:
não cria nenhum widget.
"""
from __future__ import annotations

from types import SimpleNamespace

from automationstudio.ativacao_ui import ControladorAtivacao
from automationstudio.controle_ui import ControladorDeExecucao
from automationstudio.input_system import GlobalHotkeyManager
from automationstudio.project import AppSettings
from testsupport.fakes import FakeMonitor

# Os 3 mapas reais: nome -> tecla (tests/data/legacy_maps.json.gz).
REAIS = {"Click genshin": "MOUSE_X1", "Exemplo — Primeira automação": "=", "Flins combo": "MOUSE_X2"}


class JanelaFalsa:
    """Só o que os controladores usam da MainWindow."""

    def __init__(self, pasta, mapas, engine=None):
        self.settings = AppSettings(pasta)
        self.engine = engine
        self.project_manager = SimpleNamespace(maps={n: SimpleNamespace(name=n, hotkey=t) for n, t in mapas.items()})
        self.monitor = FakeMonitor()
        self.hotkey_manager = GlobalHotkeyManager(self.monitor)
        self.disparos, self.avisos, self.status = [], [], []
        self.registros = self.rotulos = 0
        self.hotkey_bridge = SimpleNamespace(make_callback=lambda acao: (lambda: self.disparos.append(acao)))
        self.status_bar = SimpleNamespace(showMessage=lambda texto, ms=0: self.status.append(texto))
        self._current_map = None
        self.map_list = None
        self.ativacao = ControladorAtivacao(self, avisar=lambda titulo, texto: self.avisos.append((titulo, texto)))
        self.controle = ControladorDeExecucao(self)
        self.hotkey_manager.start()

    # As duas funções da janela que o controlador chama depois de mudar alguma coisa.
    def _register_all_hotkeys(self):
        self.registros += 1
        self.ativacao.registrar()

    def _refresh_map_config_labels(self):
        self.rotulos += 1
        self.ativacao.atualizar_painel()

    def apertar(self, tecla):
        self.monitor.press(tecla)
        self.monitor.release(tecla)

    def clicar(self, botao):
        self.monitor.click(botao, True)
        self.monitor.click(botao, False)


def abrir(pasta, mapas=None, engine=None) -> JanelaFalsa:
    """A janela como fica depois de `__init__`: sincroniza a ativação e registra os atalhos. `engine`: o motor da janela."""
    janela = JanelaFalsa(pasta, REAIS if mapas is None else mapas, engine)
    janela.ativacao.sincronizar()
    janela._register_all_hotkeys()
    return janela
