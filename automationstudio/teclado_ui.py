"""A porta de verdade da edição pelo teclado (25.9, T3a): a única peça da T3a que usa o Qt.

Ficha: md/FICHA_TECLADO_T3_25_9.md. A lógica toda está fora daqui: `teclado_edicao.py` decide, `teclado_aplicar.py` grava no mapa,
`teclado_teclas.py` traduz a tecla do Qt e `teclado_ligacao.py` liga as três a uma `Porta`. Este módulo é a `Porta` que a janela principal
oferece (`TecladoDaJanela`): desenha a marca da linha em edição, o editor de texto em linha, a janela de escolher o programa, a dica na barra
de status e o bip; filtra as teclas da tabela; e põe e tira a suspensão dos atalhos de automação.

O que o Qt dá e este módulo não prova sozinho (só o Actions e a rodada do Windows provam: ver md/ENTREGA_TECLADO_T3A_25_9.md): o filtro de
eventos desta classe roda ANTES do `CommandTableWidget.eventFilter` (os filtros instalados depois rodam primeiro); `QApplication.focusChanged`
diz quando a tabela, o editor ou a janela do programa ganham e perdem o foco; o layout da tabela é adiado depois de `refresh()` (por isso o
`doItemsLayout()` antes de devolver a rolagem).

Regras que valem para o arquivo todo:

- nada daqui abre um laço de eventos aninhado (`exec`): a janela do programa é `open()`, não bloqueante. Um laço dentro do filtro de teclas
  reentraria no controlador (tests/static/test_ligacao_teclado.py cobra isso);
- nada que o Qt chama (filtro, sinais, relógio) deixa uma exceção escapar: ela vai para o log de execução e a janela continua. Os métodos da
  `Porta`, ao contrário, NÃO engolem exceção: a ligação precisa dela para dizer ao dono que algo deu errado e se algo foi gravado;
- tudo é lido da janela NA HORA (`self._janela.command_table`, `.status_bar`...), como em controle_ui e ativacao_ui: uma referência guardada na
  criação ficaria velha;
- se ligar o teclado falhar (um nome do Qt que não existe, por exemplo), a janela abre do mesmo jeito, só sem a edição pelo teclado: o erro vai
  para o log e os testes de janela, que exigem o teclado funcionando, o pegam.
"""
from __future__ import annotations

import functools
from functools import partial
from pathlib import Path, PureWindowsPath

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QSizePolicy, QVBoxLayout)

from . import teclado_aplicar
from .command_editor import programas_conhecidos
from .core import _append_runtime_log
from .teclado_edicao import LinhaInfo, linha_info_de
from .teclado_ligacao import SEGUNDOS_DA_MENSAGEM, LigacaoDoTeclado
from .teclado_teclas import TradutorDeTeclas

INTERVALO_DO_RELOGIO_MS = 33   # ~30 Hz: a rampa da seta segurada anda pelo relógio, não pela repetição de tecla do sistema (D8)
GRACA_DA_RETOMADA = 0.25       # depois de a tecla de captura voltar a ser comum, o atalho de automação ainda espera este tanto (T3-7)
COLUNA_DO_EDITOR_DE = 3        # o editor de texto em linha cobre da coluna "Tecla / botão" até a última, para ter largura de digitar
COLUNA_DO_EDITOR_ATE = 6
FRASE_COLUNA_FIXA = "Esta coluna não se edita na lista: use ← → para outra coluna ou Enter para editar o comando."

# A cor da marca e do editor: uma só, que não se confunde com a da seleção (azul no tema claro, amarelo no escuro: ver SelectionRubberBand).
_COR_CLARA, _COR_ESCURA = "#D9480F", "#22B8CF"
_FUNDO_CLARO, _FUNDO_ESCURO = "rgba(217, 72, 15, 34)", "rgba(34, 184, 207, 40)"
_ESTILO_DA_MOLDURA = "QFrame#marcaDeEdicao { border: 2px solid {cor}; background: {fundo}; }"
_ESTILO_DO_EDITOR = ("QLineEdit#editorDeTextoEmLinha { background: palette(base); color: palette(text); border: 2px solid {cor}; "
                     "selection-background-color: {cor}; selection-color: white; padding: 0px 4px; }")


def _registrar(onde: str, erro: BaseException) -> None:
    _append_runtime_log(f"TECLADO_EDICAO erro={type(erro).__name__}: {erro} onde={onde}")


def _seguro(padrao=None):
    """Decorador dos métodos que o Qt chama (sinais, relógio, filtro): nenhuma exceção sai deles. O que `padrao` for é o que o Qt recebe de volta."""
    def decorador(metodo):
        @functools.wraps(metodo)
        def embrulho(self, *args, **kwargs):
            try:
                return metodo(self, *args, **kwargs)
            except Exception as erro:  # noqa: BLE001 - um slot do Qt que levanta pode derrubar o aplicativo inteiro
                _registrar(metodo.__name__, erro)
                return padrao
        return embrulho
    return decorador


class SeletorDePrograma(QDialog):
    """A janela de escolher o programa de um comando de "abrir aplicativo" pelo teclado. NÃO bloqueante: quem a abre usa `open()` e ouve `finished`.

    ↑ ↓ escolhem na lista, Enter confirma, Esc cancela (o `reject` de todo QDialog). "Procurar executável…" abre o seletor de arquivos e, com um
    arquivo escolhido, confirma na hora. A lista é a mesma da barra lateral (`programas_conhecidos`); o programa que o comando já tem entra como
    item extra quando a lista não o conhece, para continuar escolhível."""

    def __init__(self, pai, atual: str, programas: list[tuple[str, str]]) -> None:
        super().__init__(pai)
        self.setObjectName("seletorDePrograma")
        self.setWindowTitle("Escolher o programa a abrir")
        self.resize(480, 360)
        self._aceito = False
        self._de_fora = ""
        self._atual = str(atual or "")
        itens = list(programas)
        if self._atual and not any(exe == self._atual for _, exe in itens):
            itens.append((PureWindowsPath(self._atual).stem or self._atual, self._atual))
        self._lista = QListWidget(self)
        self._lista.setObjectName("listaDeProgramas")
        escolhido = 0
        for posicao, (rotulo, exe) in enumerate(itens):
            item = QListWidgetItem(f"{rotulo} — {exe}")
            item.setData(Qt.UserRole, exe)
            self._lista.addItem(item)
            if exe == self._atual:
                escolhido = posicao
        self._lista.setCurrentRow(escolhido)
        self._lista.itemActivated.connect(self._ativado)
        dica = QLabel("↑ ↓ escolhem   ·   Enter confirma   ·   Esc cancela", self)
        procurar = QPushButton("&Procurar executável…", self)
        procurar.setAutoDefault(False)
        procurar.clicked.connect(self._procurar)
        cancelar = QPushButton("Cancelar", self)
        cancelar.setAutoDefault(False)
        cancelar.clicked.connect(self.reject)
        confirmar = QPushButton("Escolher", self)
        confirmar.setDefault(True)
        confirmar.clicked.connect(self.accept)
        botoes = QHBoxLayout()
        botoes.addWidget(procurar)
        botoes.addStretch(1)
        botoes.addWidget(cancelar)
        botoes.addWidget(confirmar)
        corpo = QVBoxLayout(self)
        corpo.addWidget(dica)
        corpo.addWidget(self._lista, 1)
        corpo.addLayout(botoes)
        self._lista.setFocus()

    @property
    def aceito(self) -> bool:
        """Se o diálogo terminou em "Escolher" (Enter, duplo clique ou o arquivo achado em "Procurar")."""
        return self._aceito

    def accept(self) -> None:
        self._aceito = True
        super().accept()

    def valor(self) -> str:
        """O programa escolhido: o arquivo que "Procurar" achou, ou o item da lista; vazio se a lista está vazia."""
        if self._de_fora:
            return self._de_fora
        item = self._lista.currentItem()
        return str(item.data(Qt.UserRole) or "") if item is not None else ""

    def _ativado(self, *_args) -> None:
        self.accept()

    def _procurar(self, *_args) -> None:
        inicio = str(Path(self._atual).parent) if self._atual and Path(self._atual).exists() else str(Path.home())
        caminho, _filtro = QFileDialog.getOpenFileName(self, "Selecionar executável do aplicativo", inicio, "Executáveis (*.exe);;Todos os arquivos (*.*)")
        if not caminho:
            return
        self._de_fora = str(Path(caminho).resolve())
        self.accept()


class TecladoDaJanela(QObject):
    """A `Porta` da ligação do teclado (`teclado_ligacao.Porta`) para a janela principal, mais o filtro das teclas da tabela.

    Quem o cria é o `MainWindow` (`self.teclado`), depois de a tabela e a barra de status existirem. O que a janela pergunta é só `editando()`: o Esc
    do aplicativo cede enquanto houver edição (T3-9)."""

    def __init__(self, janela) -> None:
        super().__init__(janela)
        self._janela = janela
        self._ativo = False
        self._ligacao: LigacaoDoTeclado | None = None
        self._tradutor: TradutorDeTeclas | None = None
        self._marca: teclado_aplicar.Marca | None = None   # o comando da linha em edição, como era quando foi marcado
        self._mexendo = False                              # as mudanças da própria janela do teclado na tabela não contam como "a seleção mudou"
        self._moldura: QFrame | None = None
        self._editor: QLineEdit | None = None
        self._seletor: SeletorDePrograma | None = None
        self._minha_mensagem = ""                          # a última mensagem passageira que NÓS pusemos na barra de status
        self._rotulo_dica: QLabel | None = None
        self._rotulo_valor: QLabel | None = None
        self._relogio: QTimer | None = None
        try:
            self._ligar()
        except Exception as erro:  # noqa: BLE001 - a janela tem de abrir mesmo que o teclado não ligue
            self._ativo = False
            _registrar("ligar o teclado à janela", erro)

    def _ligar(self) -> None:
        self._tradutor = TradutorDeTeclas(Qt)
        self._ligacao = LigacaoDoTeclado(self)
        self._relogio = QTimer(self)
        self._relogio.setInterval(INTERVALO_DO_RELOGIO_MS)
        self._relogio.timeout.connect(self._tique)
        self._montar_a_barra_de_status()
        tabela = self._tabela.table
        tabela.installEventFilter(self)
        tabela.selectionModel().selectionChanged.connect(self._selecao_mudou)   # o modelo, não `itemSelectionChanged`: a linha do tempo bloqueia o da tabela
        tabela.verticalScrollBar().valueChanged.connect(self._reposicionar)
        tabela.horizontalScrollBar().valueChanged.connect(self._reposicionar)
        tabela.horizontalHeader().sectionResized.connect(self._reposicionar)
        QApplication.instance().focusChanged.connect(self._foco_mudou)
        self._ativo = True

    def _montar_a_barra_de_status(self) -> None:
        """Dois rótulos na barra: a dica (widget comum, que some enquanto há mensagem passageira e volta depois) e o valor em edição (permanente)."""
        barra = self._janela.status_bar
        dica = QLabel("")
        dica.setObjectName("dicaDoTeclado")
        dica.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)   # uma dica comprida não pode alargar a janela
        dica.setMinimumWidth(0)
        valor = QLabel("")
        valor.setObjectName("valorDoTeclado")
        valor.hide()
        barra.addWidget(dica, 1)
        barra.addPermanentWidget(valor)
        self._rotulo_dica, self._rotulo_valor = dica, valor

    # ------------------------------------------------------------------------------------------------ o que a janela pergunta
    def editando(self) -> bool:
        """Há uma edição pelo teclado em curso? O Esc do aplicativo (MainWindow.eventFilter) cede enquanto houver."""
        return bool(self._ativo and self._ligacao is not None and self._ligacao.editando())

    @property
    def _tabela(self):
        return self._janela.command_table

    def _mapa(self):
        """O mapa que a tabela mostra e que a janela salva (`_on_map_edited`). None se não há, ou se os dois não são o mesmo objeto: aí não se edita."""
        mapa = getattr(self._janela, "_current_map", None)
        if mapa is None or mapa is not getattr(self._tabela, "_automation_map", None):
            return None
        return mapa

    def _linhas_selecionadas(self) -> list[int]:
        mapa = self._mapa()
        if mapa is None:
            return []
        indices = self._tabela.table.selectionModel().selectedIndexes()
        return [linha for linha in sorted({indice.row() for indice in indices}) if 0 <= linha < len(mapa.commands)]   # a pré-visualização da gravação fica de fora

    # ------------------------------------------------------------------------------------------------ a Porta: leituras
    def quantas_linhas_selecionadas(self) -> int:
        return len(self._linhas_selecionadas())

    def linha_atual(self) -> LinhaInfo | None:
        linhas, mapa = self._linhas_selecionadas(), self._mapa()
        if len(linhas) != 1 or mapa is None:
            return None
        return linha_info_de(mapa, linhas[0])

    def texto_do_editor(self) -> str:
        return self._editor.text() if self._editor is not None else ""

    # ------------------------------------------------------------------------------------------------ a Porta: a marca e os editores
    def marcar(self, linha: int) -> None:
        mapa = self._mapa()
        if mapa is None:
            raise RuntimeError("não há mapa para marcar a linha")
        self._marca = teclado_aplicar.marcar(mapa, linha)
        self._apagar_minha_mensagem()   # uma edição nova: a confirmação da anterior não pode esconder a dica desta
        tabela = self._tabela.table
        item = tabela.item(linha, 0)
        if item is not None:
            tabela.scrollToItem(item)
        if self._moldura is None:
            moldura = QFrame(tabela.viewport())
            moldura.setObjectName("marcaDeEdicao")
            moldura.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self._moldura = moldura
        self._moldura.setStyleSheet(self._estilo(_ESTILO_DA_MOLDURA))
        self._reposicionar()
        self._moldura.show()
        self._moldura.raise_()

    def desmarcar(self) -> None:
        """Fim da edição: tira a marca, fecha o editor de texto e a janela do programa se estiverem abertos e limpa o valor da barra. Pode ser chamada à toa."""
        self._marca = None
        if self._moldura is not None:
            self._moldura.hide()
        self._descartar_editor()
        self._fechar_seletor()
        self._mostrar_o_valor("")

    def fechar_editor(self) -> None:
        self._descartar_editor()

    def abrir_texto(self, linha: int, atual: str) -> None:
        self._descartar_editor()
        tabela = self._tabela.table
        editor = QLineEdit(tabela.viewport())
        editor.setObjectName("editorDeTextoEmLinha")
        editor.setStyleSheet(self._estilo(_ESTILO_DO_EDITOR))
        editor.setText(atual)
        editor.installEventFilter(self)
        self._editor = editor   # antes de pedir o foco: quem ouve `focusChanged` precisa reconhecê-lo
        self._reposicionar()
        editor.show()
        editor.raise_()
        editor.setFocus(Qt.OtherFocusReason)
        editor.selectAll()

    def abrir_aplicativo(self, linha: int, atual: str) -> None:
        """Abre a janela do programa SEM bloquear; o resultado volta por `_seletor_fechou` -> `aplicativo_resolvido`."""
        self._fechar_seletor()
        dialogo = SeletorDePrograma(self._janela, atual, programas_conhecidos())
        dialogo.finished.connect(partial(self._seletor_fechou, dialogo))
        self._seletor = dialogo   # antes de abrir: o foco vai para ela e `focusChanged` precisa reconhecê-la
        dialogo.open()

    def _descartar_editor(self) -> None:
        """Fecha o editor de texto em linha, se houver. `_editor` vira None ANTES de o foco voltar à tabela: assim `focusChanged` não toma o fechamento por
        "o editor perdeu o foco" (que descartaria a edição que acabou de começar, no Enter duplo)."""
        editor, self._editor = self._editor, None
        if editor is None:
            return
        self._tabela.table.setFocus(Qt.OtherFocusReason)
        editor.hide()
        editor.deleteLater()   # nunca dentro do filtro do próprio editor: o objeto ainda está tratando a tecla

    def _fechar_seletor(self) -> None:
        dialogo, self._seletor = self._seletor, None
        if dialogo is None:
            return
        dialogo.reject()   # emite `finished`, que `_seletor_fechou` ignora: esta janela já não é a atual
        dialogo.deleteLater()

    @_seguro()
    def _seletor_fechou(self, dialogo, _resultado=0) -> None:
        if dialogo is not self._seletor:
            return   # fomos nós que a fechamos (o teclado descartou a edição): quem decidiu já cuidou de tudo
        self._seletor = None
        valor = dialogo.valor() if dialogo.aceito else None
        dialogo.deleteLater()
        self._ligacao.aplicativo_resolvido(valor)

    # ------------------------------------------------------------------------------------------------ a Porta: gravar
    def aplicar_alvo(self, linha: int, valor, rotulo: str) -> teclado_aplicar.Resultado:
        return self._gravar(linha, rotulo, lambda mapa, marca: teclado_aplicar.aplicar_alvo(mapa, marca, valor))

    def aplicar_texto(self, linha: int, texto: str, rotulo: str) -> teclado_aplicar.Resultado:
        return self._gravar(linha, rotulo, lambda mapa, marca: teclado_aplicar.aplicar_texto(mapa, marca, texto))

    def aplicar_tempo(self, linha: int, valor: float, rotulo: str) -> teclado_aplicar.Resultado:
        return self._gravar(linha, rotulo, lambda mapa, marca: teclado_aplicar.aplicar_tempo(mapa, marca, valor))

    def aplicar_espera(self, linha: int, valor: float, rotulo: str) -> teclado_aplicar.Resultado:
        return self._gravar(linha, rotulo, lambda mapa, marca: teclado_aplicar.aplicar_espera(mapa, marca, valor))

    def _gravar(self, linha: int, rotulo: str, aplicar) -> teclado_aplicar.Resultado:
        """Grava no mapa (`teclado_aplicar` confere antes que o comando é o que foi marcado) e, se deu certo, faz o que a barra lateral faz ao salvar:
        refaz a tabela, reaponta a linha e avisa a janela (`map_changed` -> `_on_map_edited`: validação, arquivo e histórico do Ctrl+Z)."""
        marca = self._marca
        if marca is None or marca.indice != linha:
            raise RuntimeError(f"gravação sem a linha {linha} marcada (marca={marca})")
        mapa = self._mapa()
        if mapa is None:
            return teclado_aplicar.Resultado(False, teclado_aplicar.MENSAGEM_MUDOU)
        resultado = aplicar(mapa, marca)
        if resultado.ok:
            self._refazer_a_tabela(linha)
            self._tabela.map_changed.emit(rotulo)
        return resultado

    def _refazer_a_tabela(self, linha: int) -> None:
        """`refresh()` zera a seleção e a rolagem. Aqui as duas voltam: a seleção na mesma linha (e coluna) e a rolagem de antes. O layout da tabela é
        adiado depois de inserir linhas, e a faixa da barra de rolagem só se atualiza com ele: por isso o `doItemsLayout()` antes de devolver o valor."""
        tabela = self._tabela
        grade = tabela.table
        vertical, horizontal = grade.verticalScrollBar().value(), grade.horizontalScrollBar().value()
        coluna = max(0, grade.currentColumn())
        self._mexendo = True
        try:
            tabela.refresh()
            grade.doItemsLayout()
            grade.verticalScrollBar().setValue(vertical)
            grade.horizontalScrollBar().setValue(horizontal)
            grade.selectRow(linha)
            grade.setCurrentCell(linha, coluna)
        finally:
            self._mexendo = False

    # ------------------------------------------------------------------------------------------------ a Porta: dica, valor, bip
    def dica(self, texto: str, segundos: float = 0.0) -> None:
        """`segundos` 0: a dica que fica na barra até ser trocada. Maior que 0: uma mensagem passageira, e a dica que ficou volta depois (o rótulo da
        dica é um widget comum da barra, que o Qt esconde enquanto há mensagem). Uma dica nova NÃO apaga a mensagem passageira: depois da gravação
        a confirmação ("Tecla trocada...") precisa sobreviver à dica da navegação que vem logo atrás."""
        if segundos > 0:
            self._minha_mensagem = texto
            self._janela.status_bar.showMessage(texto, int(segundos * 1000))
            return
        self._rotulo_dica.setText(texto)
        self._rotulo_dica.setToolTip(texto)

    def mostrar_valor(self, texto: str) -> None:
        self._mostrar_o_valor(texto)

    def propor_tecla(self, nome: str) -> None:
        self._mostrar_o_valor(f"Tecla proposta: {nome}")

    def limpar_dica(self) -> None:
        """A tabela perdeu o foco: some a dica, o valor e a mensagem passageira, mas só esta se ainda for a nossa (outra tela pode ter posto a dela)."""
        self._rotulo_dica.setText("")
        self._rotulo_dica.setToolTip("")
        self._apagar_minha_mensagem()
        self._mostrar_o_valor("")

    def _mostrar_o_valor(self, texto: str) -> None:
        self._rotulo_valor.setText(texto)
        self._rotulo_valor.setVisible(bool(texto))

    def _apagar_minha_mensagem(self) -> None:
        barra = self._janela.status_bar
        if self._minha_mensagem and barra.currentMessage() == self._minha_mensagem:
            barra.clearMessage()
        self._minha_mensagem = ""

    def bip(self) -> None:
        QApplication.beep()

    # ------------------------------------------------------------------------------------------------ a Porta: o resto
    def abrir_barra_lateral(self, linha: int) -> None:
        """O mesmo sinal do duplo clique: a janela abre a barra lateral do comando."""
        mapa = self._mapa()
        if mapa is None:
            raise RuntimeError("não há mapa para abrir a barra lateral")
        self._tabela.command_editor_requested.emit(mapa.commands[linha], linha)

    def editar_celula(self, linha: int) -> None:
        """A F2: edita a célula atual da tabela (o que o Enter de planilha sempre fez). Numa coluna que não se edita, a frase diz o que fazer."""
        grade = self._tabela.table
        if grade.currentRow() != linha:
            grade.setCurrentCell(linha, max(0, grade.currentColumn()))
        if not self._tabela.editar_celula_atual():
            self.dica(FRASE_COLUNA_FIXA, SEGUNDOS_DA_MENSAGEM)

    def suspender_atalhos(self, suspender: bool) -> None:
        """Enquanto uma tecla é capturada, as teclas de ativação das automações calam (T3-7); a de parar e a de pausar continuam valendo."""
        gerente = self._janela.hotkey_manager
        if suspender:
            gerente.suspender()
        else:
            gerente.retomar(graca=GRACA_DA_RETOMADA)

    def ligar_relogio(self, ligar: bool) -> None:
        if ligar:
            self._relogio.start()
        else:
            self._relogio.stop()

    @_seguro()
    def _tique(self, *_args) -> None:
        self._ligacao.tique()

    # ------------------------------------------------------------------------------------------------ o Qt chama
    def eventFilter(self, objeto, evento) -> bool:
        if not self._ativo:
            return False
        try:
            tipo = evento.type()
            if tipo == QEvent.KeyPress:
                return self._tecla_apertada(objeto, evento)
            if tipo == QEvent.KeyRelease:
                return self._tecla_solta(objeto, evento)
            if tipo == QEvent.Resize and objeto is self._tabela.table:
                self._reposicionar()
        except Exception as erro:  # noqa: BLE001 - nada escapa de um filtro de eventos
            _registrar("filtro de teclas", erro)
        return False

    def _tecla_apertada(self, objeto, evento) -> bool:
        """As teclas da tabela (só com ela em foco: sem editor de célula aberto) e as do editor de texto em linha. Devolve se a tecla é retida."""
        na_tabela = objeto is self._tabela.table
        if not na_tabela and (self._editor is None or objeto is not self._editor):
            return False
        if na_tabela:
            foco = QApplication.focusWidget()
            if foco is not None and foco is not objeto:
                return False   # uma tecla que o editor de célula não quis e subiu até a tabela não é desta edição (sem foco algum, como num teste sem janela ativa, vale)
        tecla = self._tradutor.traduzir(evento, captura=self._ligacao.capturando())
        return bool(self._ligacao.tecla_pressionada(tecla, evento.isAutoRepeat()))

    def _tecla_solta(self, objeto, evento) -> bool:
        if objeto is not self._tabela.table or evento.isAutoRepeat():   # a repetição do sistema (que no X11 vem como solta+aperta) não solta nada
            return False
        return bool(self._ligacao.tecla_solta(self._tradutor.traduzir(evento).nome))

    @_seguro()
    def _selecao_mudou(self, *_args) -> None:
        if self._mexendo or not self._ativo:
            return
        self._ligacao.selecao_mudou()

    @_seguro()
    def _foco_mudou(self, antigo, novo) -> None:
        """O foco do aplicativo mudou de `antigo` para `novo` (qualquer um pode ser None, por exemplo ao trocar de janela).

        Descarta a edição quando: o editor de texto perde o foco por qualquer motivo que não seja o fechamento dele mesmo; um editor de célula da tabela
        o toma; ou o foco sai da tabela para fora dela e da janela do programa (que o toma de propósito). Mostra a dica da navegação quando o foco
        volta para a tabela."""
        if self._mexendo or not self._ativo:
            return
        tabela = self._tabela.table
        if self._editor is not None and antigo is self._editor and novo is not self._editor:
            self._ligacao.descartar()
            return
        dentro_antes, dentro_agora = self._dentro(antigo, tabela), self._dentro(novo, tabela)
        if dentro_agora and novo is not tabela and novo is not self._editor:
            self._ligacao.descartar()   # um editor de célula abriu: as teclas dele não são nossas
        elif dentro_antes and not dentro_agora and not self._dentro(novo, self._seletor):
            self._ligacao.perdeu_foco()
        elif dentro_agora and not dentro_antes:
            self._ligacao.ganhou_foco()

    @staticmethod
    def _dentro(widget, ancestral) -> bool:
        """`widget` é `ancestral` ou está dentro dele? Pelo pai, não pela identidade do objeto do Python: o viewport, por exemplo, é recriado a cada acesso."""
        if widget is None or ancestral is None:
            return False
        return widget is ancestral or bool(ancestral.isAncestorOf(widget))

    # ------------------------------------------------------------------------------------------------ geometria e aparência
    @_seguro()
    def _reposicionar(self, *_args) -> None:
        """Põe a marca sobre a linha em edição e o editor de texto sobre as colunas dele; roda a cada rolagem, mudança de largura e redimensionamento."""
        marca = self._marca
        if marca is None:
            return
        tabela = self._tabela.table
        topo, altura = tabela.rowViewportPosition(marca.indice), tabela.rowHeight(marca.indice)
        if self._moldura is not None:
            self._moldura.setGeometry(0, topo, tabela.viewport().width(), altura)
        if self._editor is not None:
            esquerda = tabela.columnViewportPosition(COLUNA_DO_EDITOR_DE)
            direita = tabela.columnViewportPosition(COLUNA_DO_EDITOR_ATE) + tabela.columnWidth(COLUNA_DO_EDITOR_ATE)
            self._editor.setGeometry(esquerda, topo, max(40, direita - esquerda), altura)

    def _estilo(self, modelo: str) -> str:
        """Preenche `{cor}` e `{fundo}` do modelo de folha de estilo pelo tema de agora (lido na hora: o tema pode ter mudado desde a última edição)."""
        escuro = bool(getattr(self._janela, "_dark_theme", False))
        return modelo.replace("{cor}", _COR_ESCURA if escuro else _COR_CLARA).replace("{fundo}", _FUNDO_ESCURO if escuro else _FUNDO_CLARO)
