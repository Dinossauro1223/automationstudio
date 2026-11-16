"""A parte com Qt do passo a passo (função F52): a janelinha de controle e a ligação com a janela principal. A lógica está em
passo_a_passo.py; o gancho, no motor.

Como funciona, do ponto de vista de quem usa:
    * no editor, "Executar passo a passo" (menu "Mais…") e "Executar passo a passo a partir daqui" (botão direito num comando);
    * abre uma janelinha sempre por cima, no canto de baixo à direita da tela (acima da barra de tarefas, longe dos botões
      de fechar e minimizar do programa de destino), com o passo em que a execução está parada e três botões: "Próximo
      passo", "Continuar sem parar" e "Parar";
    * a janelinha NÃO aceita o foco: clicar nela não tira o foco do programa onde a automação trabalha. Sem isso as teclas do
      próximo comando iriam para o próprio Automation Studio (e poderiam apagar ou mudar a sua automação);
    * o passo a passo começa antes do primeiro comando, então dá tempo de trazer para a frente o programa de destino;
    * ao terminar, ou ao parar por qualquer meio (botão, tecla, erro), a janelinha some. Fechar a janelinha pelo X também para.

Sem cores, tamanhos nem ícones aqui (é da frente visual); os objetos têm nome (`PainelPassoAPasso`, `PassoRotulo`) para ela estilizar.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from .core import State, _append_runtime_log
from .passo_a_passo import ControleDePassos

NOME_DA_JANELINHA = "PainelPassoAPasso"
NOME_DO_ROTULO = "PassoRotulo"
TITULO = "Passo a passo"


def posicao_no_canto(direita: int, baixo: int, largura: int, altura: int) -> tuple[int, int]:
    """Onde pôr o canto de cima à esquerda de uma janela de `largura` x `altura` (contando a moldura) para ela ficar encostada
    no canto de baixo à direita de uma área cujo último ponto é (`direita`, `baixo`). Os números são pontos da tela, como os
    do `QRect`: um retângulo que começa em x e tem `largura` pontos termina em x + largura - 1."""
    return direita - largura + 1, baixo - altura + 1


class PainelPassoAPasso(QWidget):
    """A janelinha: sempre por cima e SEM aceitar o foco (clicar nela não muda a janela ativa do Windows)."""

    def __init__(self, ao_proximo, ao_continuar, ao_parar) -> None:
        super().__init__(None, Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setObjectName(NOME_DA_JANELINHA)
        self.setWindowTitle(TITULO)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._ao_parar = ao_parar
        camada = QVBoxLayout(self)
        self.rotulo = QLabel("")
        self.rotulo.setObjectName(NOME_DO_ROTULO)
        self.rotulo.setWordWrap(True)
        camada.addWidget(self.rotulo)
        linha = QHBoxLayout()
        self.botao_proximo = QPushButton("Próximo passo")
        self.botao_continuar = QPushButton("Continuar sem parar")
        self.botao_parar = QPushButton("Parar")
        for botao, acao in ((self.botao_proximo, ao_proximo), (self.botao_continuar, ao_continuar), (self.botao_parar, ao_parar)):
            botao.setFocusPolicy(Qt.NoFocus)
            botao.clicked.connect(lambda _marcado=False, fazer=acao: fazer())
            linha.addWidget(botao)
        camada.addLayout(linha)

    def mostrar_passo(self, texto: str, pode_avancar: bool) -> None:
        """Mostra `texto` e habilita (ou não) o "Próximo passo". Abre a janelinha no canto se ainda estava fechada."""
        self.rotulo.setText(texto)
        self.botao_proximo.setEnabled(bool(pode_avancar))
        if not self.isVisible():
            self.show()
            self._ir_para_o_canto()

    def esconder(self) -> None:
        self.hide()

    def closeEvent(self, evento) -> None:  # o X da janelinha: não deixa a execução parada, sem ninguém para liberá-la
        self._ao_parar()
        evento.accept()

    def _ir_para_o_canto(self) -> None:
        tela = QGuiApplication.primaryScreen()
        if tela is None:
            return
        area = tela.availableGeometry()  # a área útil da tela: sem a barra de tarefas
        self.adjustSize()
        moldura = self.frameGeometry()  # com a barra de título e as bordas, que também precisam caber na tela
        self.move(*posicao_no_canto(area.right(), area.bottom(), moldura.width(), moldura.height()))


class ControladorPassoAPasso:
    """Liga o passo a passo à janela principal: recebe o pedido do menu do editor, mostra a janelinha e a mantém em dia com o
    estado do motor. Os argumentos opcionais existem para os testes: `controle` (padrão: o de verdade, sobre o motor da
    janela), `criar_painel` (padrão: PainelPassoAPasso), `avisar` (padrão: caixa de mensagem) e `registrar` (padrão: o log)."""

    def __init__(self, janela, controle=None, criar_painel=None, avisar=None, registrar=None) -> None:
        self.janela = janela
        self._registrar = registrar if registrar is not None else _append_runtime_log
        self.controle = controle if controle is not None else ControleDePassos(janela.engine, self._registrar)
        self._criar_painel = criar_painel if criar_painel is not None else PainelPassoAPasso
        self._avisar = avisar if avisar is not None else (lambda texto: QMessageBox.information(self.janela, TITULO, texto))
        self.painel = None

    def ligar(self, tabela_de_comandos, ponte) -> None:
        """Liga o pedido do editor e o aviso de mudança de estado do motor."""
        tabela_de_comandos.passo_a_passo_requested.connect(self.iniciar)
        ponte.state_changed.connect(self.estado_mudou)

    def iniciar(self, ids=()) -> None:
        """O pedido do menu do editor: `ids` são os comandos escolhidos (vazio = a automação inteira)."""
        mapa = getattr(self.janela, "_current_map", None)
        if mapa is None:
            return
        motivo = self.controle.iniciar(mapa, ids)
        if motivo:
            self._avisar(motivo)
            return
        self._painel().mostrar_passo(self.controle.texto(), False)

    def estado_mudou(self, _anterior, novo) -> None:
        """O motor mudou de estado: mantém a janelinha em dia. IDLE encerra (fim, parada ou erro)."""
        if self.controle.sessao is None:
            return
        if novo == State.IDLE:
            self.controle.terminou()
            if self.painel is not None:
                self.painel.esconder()
            self._mensagem("Passo a passo encerrado.")
        elif novo == State.PAUSED:
            if self.controle.ao_ficar_pausado():
                return
            self._painel().mostrar_passo(self.controle.texto(), self.controle.parado_num_passo())
        elif novo == State.RUNNING:
            self._painel().mostrar_passo(self.controle.texto(), False)

    def proximo(self) -> None:
        self.controle.proximo()

    def continuar_sem_parar(self) -> None:
        if self.controle.continuar_sem_parar() and self.painel is not None:
            self.painel.mostrar_passo(self.controle.texto(), False)

    def parar(self) -> None:
        self.controle.parar()

    def _painel(self):
        if self.painel is None:
            self.painel = self._criar_painel(self.proximo, self.continuar_sem_parar, self.parar)
        return self.painel

    def _mensagem(self, texto: str) -> None:
        barra = getattr(self.janela, "status_bar", None)
        if barra is not None:
            barra.showMessage(texto, 5000)
