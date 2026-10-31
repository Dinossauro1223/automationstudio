"""Pausar e continuar a automação pelas teclas de controle (F9 e F10 por padrão). Especificação: md/ESPEC_PAUSA_TECLAS.md.

Até a 25.8 as duas teclas eram registradas e nada as atendia (achado 2.11): `MainWindow._on_hotkey_triggered` não tinha ramo
para elas e a janela nunca chamava `ExecutionEngine.pause()` nem `resume()`. O controlador é o que a janela chama quando elas
disparam: pede ao motor e diz ao usuário, na barra de status, o que aconteceu. Fica fora da janela (como o controlador da
ativação, em ativacao_ui.py) para poder ser testado sem Qt, e não importa nada do Qt.

Lê o motor, as configurações e o plano de atalhos NA HORA, sempre pela janela: o editor de configurações troca `janela.settings`
por outro objeto quando a pasta de dados muda, e uma referência guardada na criação ficaria velha.
"""
from __future__ import annotations

PRAZO_DA_MENSAGEM_PAUSADA = 8000    # ms: longo para dar tempo de ler, finito para não sobrar na barra depois de parar a automação
PRAZO_DA_MENSAGEM_RETOMADA = 3000   # ms

ACAO_DE_CONTINUAR = "control:resume"  # a ação que `ativacao.ACAO_DO_CONTROLE` dá ao atalho "Continuar automação"


class ControladorDeExecucao:
    """Liga as teclas "Pausar automação" e "Continuar automação" ao motor da janela principal."""

    def __init__(self, janela) -> None:
        self.janela = janela

    def tecla_de_continuar(self) -> str:
        """A tecla que continua a automação AGORA, como o usuário a escreveu; "" se nenhuma está ativa (inválida, ou repetida
        e perdida para um atalho de controle de mais prioridade: a ativação por mapa já avisou isso ao abrir)."""
        registro = next((r for r in self.janela.ativacao.plano().registros if r.acao == ACAO_DE_CONTINUAR), None)
        return registro.tecla if registro is not None else ""

    def pausar(self) -> bool:
        """Tecla de pausar. Pausa a automação em execução e diz como continuar. Devolve se pausou; sem execução em andamento
        (ou se ela acabou no mesmo instante) não faz nada, sem mensagem."""
        if not self.janela.engine.pause():
            return False
        tecla = self.tecla_de_continuar()
        if tecla:
            texto = f"Automação pausada. Aperte {tecla} para continuar."
        else:
            texto = "Automação pausada. A tecla de continuar não está ativa; use o botão de parar para encerrar."
        self.janela.status_bar.showMessage(texto, PRAZO_DA_MENSAGEM_PAUSADA)
        return True

    def retomar(self) -> bool:
        """Tecla de continuar. Continua a automação pausada do ponto onde parou. Devolve se continuou; sem pausa (ou se a
        automação foi parada no mesmo instante) não faz nada, sem mensagem."""
        if not self.janela.engine.resume():
            return False
        self.janela.status_bar.showMessage("Automação retomada.", PRAZO_DA_MENSAGEM_RETOMADA)
        return True
