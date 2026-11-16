"""A parte com Qt do aviso de janela de administrador (função F51): liga o vigia (elevacao.py) aos sinais do motor e mostra o
aviso num rótulo da barra de status da janela principal. Regra, textos e leitura do Windows estão em elevacao.py.

Como funciona, do ponto de vista de quem usa:
    * durante a execução, a cada evento do motor o vigia pode olhar (no máximo umas 4 vezes por segundo) de quem é a janela
      que recebe a entrada. Se for de administrador e o programa não, aparece o rótulo "⚠ Janela de administrador ..." à direita
      da barra de status, com a explicação completa na dica (passe o mouse). A mesma explicação vai para o log;
    * o rótulo fica até começar a próxima execução (continuar de uma pausa não conta como execução nova);
    * a barra de tarefas do Windows pisca (sem roubar o foco), para quem está com outro programa na frente. Não há caixa de
      mensagem: ela tiraria o foco da janela onde a automação está trabalhando;
    * nada disso muda o que a execução faz. O aviso nunca bloqueia nem interrompe a automação.

Fora do Windows o vigia não existe (`criar_vigia` devolve None) e o controlador não faz nada.
"""
from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLabel

from .core import State, _append_runtime_log
from .elevacao import Aviso, criar_vigia

NOME_DO_ROTULO = "AvisoElevacao"
_PADRAO = object()  # "crie o vigia de verdade"; None quer dizer "sem vigia"


class ControladorElevacao:
    """Liga o vigia à janela principal. Os argumentos opcionais existem para os testes: `vigia` (padrão: o de verdade, ou None
    fora do Windows), `criar_rotulo` (padrão: QLabel), `piscar` (padrão: pisca a barra de tarefas) e `registrar` (padrão: o
    log do programa)."""

    def __init__(self, janela, vigia=_PADRAO, criar_rotulo=None, piscar=None, registrar=None) -> None:
        self.janela = janela
        self._registrar = registrar if registrar is not None else _append_runtime_log
        self.vigia = criar_vigia(self._registrar) if vigia is _PADRAO else vigia
        self._criar_rotulo = criar_rotulo if criar_rotulo is not None else QLabel
        self._piscar = piscar if piscar is not None else (lambda: QApplication.alert(self.janela))
        self.rotulo = None
        self.aviso_atual: Aviso | None = None

    def ligar(self, barra_de_status, ponte) -> None:
        """Põe o rótulo (escondido) na barra de status e liga os dois sinais do motor. Sem vigia, não faz nada."""
        if self.vigia is None:
            return
        self.rotulo = self._criar_rotulo()
        self.rotulo.setObjectName(NOME_DO_ROTULO)
        barra_de_status.addPermanentWidget(self.rotulo)
        self.rotulo.setVisible(False)  # depois de adicionar: a barra pode mostrar o que entra nela
        ponte.event_fired.connect(self.olhar)
        ponte.state_changed.connect(self.estado_mudou)

    def olhar(self, _evento=None) -> None:
        """Chamada a cada evento do motor (o evento não importa). O vigia decide se há o que olhar agora."""
        if self.vigia is None:
            return
        aviso = self.vigia.olhar()
        if aviso is not None:
            self._mostrar(aviso)

    def estado_mudou(self, anterior, novo) -> None:
        """Uma execução nova começa quando o estado vira RUNNING sem ter vindo de PAUSED (continuar não é execução nova)."""
        if novo == State.RUNNING and anterior != State.PAUSED:
            self.nova_rodada()

    def nova_rodada(self) -> None:
        self.aviso_atual = None
        if self.vigia is not None:
            self.vigia.nova_rodada()
        if self.rotulo is not None:
            self.rotulo.setVisible(False)
            self.rotulo.setText("")
            self.rotulo.setToolTip("")

    def _mostrar(self, aviso: Aviso) -> None:
        self.aviso_atual = aviso
        self._registrar(f"AVISO ELEVACAO situacao={aviso.situacao.value} pid={aviso.pid} nome={aviso.nome or '?'} "
                        f"onde={aviso.onde} texto={aviso.longo}")
        if self.rotulo is not None:
            self.rotulo.setText(aviso.curto)
            self.rotulo.setToolTip(aviso.longo)
            self.rotulo.setVisible(True)
        try:
            self._piscar()
        except Exception as erro:  # piscar é só um reforço: se falhar, o rótulo e o log já avisaram
            self._registrar(f"ELEVACAO PISCAR FALHOU erro={type(erro).__name__}: {erro}")
