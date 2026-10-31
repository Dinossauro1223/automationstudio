"""A parte com Qt da ativação por mapa (25.8): o controlador que liga a lógica (ativacao.py) à janela principal e a faixa
(PainelAtivacao) com que o usuário escolhe o estado de uma automação. Especificação: md/ESPEC_ATIVACAO_25_8.md.

O controlador lê os mapas e as configurações NA HORA, sempre pela janela (`janela.settings`, `janela.project_manager`): o editor
de configurações troca esses dois objetos por outros novos quando a pasta de dados muda, e uma referência guardada ficaria velha.

Contrato com a frente visual (ver md/DIVISAO_DE_TRABALHO.md):
    * esta faixa é o ÚNICO seletor funcional da ativação: a frente visual pode mudar o visual dela (cores, margens, ícones,
      objectName "PainelAtivacao"), mas não deve criar outro seletor com outra lógica;
    * cada item da lista de automações carrega o estado (papel PAPEL_ESTADO) e o texto do conflito (PAPEL_CONFLITO, vazio se
      não há) para ser desenhado como quiser; o texto do item continua sendo o nome do mapa, que a janela usa como chave;
    * `ControladorAtivacao.descrever(nome)` devolve tudo o que há para mostrar sobre um mapa (ativacao.Descricao).
"""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QMessageBox, QVBoxLayout, QWidget

from .ativacao import (AJUDAS, ESTADO_DESATIVADO, ESTADOS, ROTULOS, AtivacaoMapas, Descricao, Plano, recusa_de_tecla,
                       recusa_de_tecla_invalida, registrar_plano, tecla_valida)
from .core import _append_runtime_log

PAPEL_ESTADO = 257    # Qt.UserRole + 1: "sessao", "sempre" ou "desativado"
PAPEL_CONFLITO = 258  # Qt.UserRole + 2: texto do conflito de tecla ("" se não há)


class ControladorAtivacao:
    """Liga o estado de ativação (AtivacaoMapas) à janela principal. `avisar(titulo, texto)` mostra um aviso ao usuário; sem
    ele, uma caixa de mensagem do Qt (os testes trocam por uma lista)."""

    def __init__(self, janela, avisar=None) -> None:
        self.janela = janela
        self.painel: PainelAtivacao | None = None
        self._avisar = avisar
        self._ajustes = None  # o AppSettings do qual o estado foi lido: muda quando a pasta de dados muda
        self._logica: AtivacaoMapas | None = None
        self._avisados: set[str] = set()  # conflitos já mostrados e ainda valendo (cada um é avisado uma vez)
        self._dica = ""

    # ---- leitura na hora ------------------------------------------------------------------------------------------
    def _estado(self) -> AtivacaoMapas:
        ajustes = self.janela.settings
        if self._logica is None or ajustes is not self._ajustes:
            self._ajustes = ajustes
            self._logica = AtivacaoMapas(ajustes.get_map_activation())
            self._avisados = set()
        return self._logica

    def mapas(self) -> dict[str, str]:
        """nome do mapa -> tecla, como estão agora na janela."""
        return {nome: (mapa.hotkey or "") for nome, mapa in self.janela.project_manager.maps.items()}

    def controles(self) -> dict[str, str]:
        return self.janela.settings.get_control_hotkeys()

    def _gravar(self) -> None:
        self.janela.settings.set_map_activation(self._estado().dados())

    def _mostrar(self, titulo: str, texto: str) -> None:
        if self._avisar is not None:
            self._avisar(titulo, texto)
        else:
            QMessageBox.warning(self.janela, titulo, texto)

    # ---- consultas ------------------------------------------------------------------------------------------------
    def plano(self) -> Plano:
        return self._estado().plano(self.mapas(), self.controles())

    def descrever(self, nome: str) -> Descricao:
        return self._estado().descrever(nome, self.mapas(), self.controles())

    def acao_permitida(self, acao: str) -> bool:
        """Guarda de `_on_hotkey_triggered`: o disparo de um mapa desativado é ignorado, mesmo que já estivesse na fila do Qt
        quando o usuário o desativou. Os atalhos de controle sempre passam."""
        if not acao.startswith("map:"):
            return True
        return self._estado().esta_ativo(acao[len("map:"):])

    def rotulo_da_tecla(self, mapa) -> str:
        """O rótulo "Tecla para iniciar/parar" da linha de baixo do editor. Fica curto (essa linha é estreita): a tecla e,
        só quando algo impede que ela inicie a automação, o motivo entre parênteses. O detalhe está na faixa de ativação."""
        descricao = self.descrever(mapa.name)
        if descricao.estado == ESTADO_DESATIVADO:
            aviso = " (desativada)"
        elif descricao.conflito is not None:
            aviso = " (em conflito)"
        elif descricao.invalido:
            aviso = " (inválida)"
        else:
            aviso = ""
        return f"Tecla para iniciar/parar: {mapa.hotkey or '—'}{aviso}"

    def validar_tecla(self, nome: str, tecla: str) -> str:
        """"" se `tecla` pode ser a tecla de `nome` agora; senão o texto da recusa (a tecla anterior é mantida). Uma tecla
        que não existe é recusada em qualquer estado; uma tecla ocupada só vale a recusa se o mapa está ativo (mapa
        desativado aceita qualquer tecla: o conflito é conferido quando ele for ativado)."""
        atual = self.mapas().get(nome, "")
        if not tecla_valida(tecla):
            return recusa_de_tecla_invalida(tecla, nome, atual)
        logica = self._estado()
        if not logica.esta_ativo(nome):
            return ""
        conflito = logica.verificar_tecla(nome, tecla, self.mapas(), self.controles())
        return recusa_de_tecla(conflito, atual) if conflito is not None else ""

    def mudar_tecla(self, mapa, tecla: str) -> bool:
        """Dá `tecla` ao `mapa` se ela serve (`validar_tecla`); senão avisa o motivo e o mapa fica com a que tinha. Devolve
        se a tecla mudou. Só muda o objeto do mapa: quem chama grava e refaz os atalhos, como já fazia."""
        motivo = self.validar_tecla(mapa.name, tecla)
        if motivo:
            self._mostrar("Tecla não alterada", motivo)
            return False
        mapa.hotkey = tecla
        return True

    # ---- ações ----------------------------------------------------------------------------------------------------
    def sincronizar(self) -> None:
        """Alinha o estado com os mapas que existem agora (chamado ao recarregar a lista): migra na primeira abertura, faz
        os mapas novos nascerem e grava o que mudou. Mapa que nasceu desativado por conflito é avisado."""
        resultado = self._estado().sincronizar(self.mapas(), self.controles())
        if resultado.mudou:
            self._gravar()
        if resultado.avisos:
            self._mostrar("Atalho em conflito", "\n\n".join(resultado.avisos))

    def registrar(self) -> None:
        """Refaz os atalhos globais conforme o plano: só mapas ativos, atalhos de controle com prioridade. Cada conflito é
        avisado uma única vez enquanto durar (se sumir e voltar, é avisado de novo)."""
        self.sincronizar()
        plano = self.plano()
        erros = registrar_plano(plano, self.janela.hotkey_manager, self.janela.hotkey_bridge.make_callback)
        atuais = plano.mensagens() + erros
        novos = [mensagem for mensagem in atuais if mensagem not in self._avisados]
        self._avisados = set(atuais)
        if novos:
            self._mostrar("Conflito de atalhos", "Alguns atalhos não foram ativados por conflito:\n\n" + "\n".join(novos))

    def definir_estado(self, nome: str, estado: str) -> bool:
        """Aplica o estado escolhido. Devolve False (e mostra o motivo) se foi recusado; nada muda nesse caso."""
        resultado = self._estado().definir(nome, estado, self.mapas(), self.controles())
        if not resultado.ok:
            self._mostrar("Não foi possível ativar", resultado.mensagem)
            return False
        self._gravar()
        self.janela._register_all_hotkeys()
        self.decorar_lista()
        self.janela._refresh_map_config_labels()
        if resultado.mensagem:
            self.janela.status_bar.showMessage(resultado.mensagem, 8000)
        return True

    def esquecer(self, nome: str) -> None:
        """Um mapa foi excluído: a preferência dele também."""
        if self._estado().esquecer(nome):
            self._gravar()

    # ---- a lista e a faixa ----------------------------------------------------------------------------------------
    def decorar_lista(self, dica: str | None = None) -> None:
        """Põe em cada item da lista o estado e o conflito (papéis de dados) e a dica. `dica` é a frase de abrir a
        automação, que vai na primeira linha da dica; sem ela vale a última recebida."""
        if dica is not None:
            self._dica = dica
        lista = getattr(self.janela, "map_list", None)
        if lista is None:
            return
        logica, mapas, controles = self._estado(), self.mapas(), self.controles()
        plano = logica.plano(mapas, controles)
        for linha in range(lista.count()):
            item = lista.item(linha)
            descricao = logica.descrever(item.text(), mapas, controles, plano)
            item.setData(PAPEL_ESTADO, descricao.estado)
            item.setData(PAPEL_CONFLITO, descricao.conflito.mensagem if descricao.conflito is not None else "")
            item.setToolTip(f"{self._dica}\n\n{descricao.situacao}\n{descricao.resumo}")

    def montar_painel(self, ancora) -> None:
        """Cria a faixa e a encaixa no editor, logo abaixo de `ancora` (um widget que já está no layout do editor: o
        encaixe acompanha a âncora, não a posição numérica). A faixa é um acréscimo: se o editor mudou de forma e o encaixe
        falha, a janela abre sem ela e o motivo vai para o log; se a âncora não está direto nesse layout (foi para dentro de
        outro), a faixa vai para o fim do editor em vez de sumir, porque é por ela que o estado se muda."""
        try:
            layout = ancora.parentWidget().layout()
            painel = PainelAtivacao(self)
            posicao = layout.indexOf(ancora)
            layout.insertWidget(posicao + 1 if posicao >= 0 else layout.count(), painel)
        except Exception as exc:  # noqa: BLE001  (um acréscimo visual nunca pode impedir o programa de abrir)
            self.painel = None
            _append_runtime_log(f"FAIXA DE ATIVACAO NAO MONTADA erro={type(exc).__name__}: {exc}")
            return
        self.painel = painel
        if posicao < 0:
            _append_runtime_log("FAIXA DE ATIVACAO NO FIM DO EDITOR: a ancora nao esta direto no layout do editor")

    def atualizar_painel(self) -> None:
        """Mostra na faixa a automação aberta no editor (ou a esconde se não há)."""
        if self.painel is not None:
            mapa = getattr(self.janela, "_current_map", None)
            self.painel.mostrar(mapa.name if mapa is not None else None)


class PainelAtivacao(QWidget):
    """Faixa do editor: a caixa com os três estados e a frase do que isso significa para a automação aberta."""

    def __init__(self, controlador: ControladorAtivacao, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainelAtivacao")
        self._controlador = controlador
        self._nome: str | None = None
        self._ajustando = False  # True enquanto a faixa mexe na caixa por conta própria (não é uma escolha do usuário)
        self.combo = QComboBox()
        for estado in ESTADOS:
            self.combo.addItem(ROTULOS[estado], estado)
        self.situacao = QLabel("")
        self.situacao.setWordWrap(True)
        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        linha.addWidget(QLabel("Ativação:"))
        linha.addWidget(self.combo)
        linha.addStretch()
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 2)
        raiz.setSpacing(2)
        raiz.addLayout(linha)
        raiz.addWidget(self.situacao)
        self.combo.currentIndexChanged.connect(self._ao_escolher)
        self.setVisible(False)  # só aparece quando há uma automação aberta (ver `mostrar`)

    def mostrar(self, nome: str | None) -> None:
        """Mostra o estado verdadeiro de `nome` (ou esconde a faixa com None). Não conta como escolha do usuário."""
        self._nome = nome
        self.setVisible(nome is not None)
        if nome is None:
            return
        descricao = self._controlador.descrever(nome)
        self._ajustando = True
        try:
            self.combo.setCurrentIndex(ESTADOS.index(descricao.estado))
        finally:
            self._ajustando = False
        self.combo.setToolTip(AJUDAS[descricao.estado])
        self.situacao.setText(descricao.resumo)

    def _ao_escolher(self, indice: int) -> None:
        if self._ajustando or self._nome is None or not 0 <= indice < len(ESTADOS):
            return
        self._controlador.definir_estado(self._nome, ESTADOS[indice])
        self.mostrar(self._nome)  # mostra o estado verdadeiro: se a escolha foi recusada, a caixa volta ao que era
