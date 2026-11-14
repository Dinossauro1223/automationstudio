"""A ligação do controlador da edição pelo teclado com a janela (25.9, T3a). Lógica pura: este módulo NÃO importa o Qt.

Ficha: md/FICHA_TECLADO_T3_25_9.md (T3-1, T3-3, T3-4, T3-7, T3-8, T3-12, T3-13, T3-14). Testes: tests/unit/test_teclado_ligacao.py.

O controlador (`teclado_edicao.py`, T2) decide o que cada tecla faz e devolve EFEITOS; `teclado_ui.py`, a única peça com Qt, é a janela de
verdade. Entre os dois está esta ligação. A janela lhe entrega o que acontece (tecla apertada, tecla solta, o tique do relógio, a seleção que
mudou, o foco que saiu) e ela:

- decide se a tecla é consumida (a janela a retém) ou segue para o Qt;
- executa os efeitos do controlador, na ordem, chamando a PORTA (o que a janela de verdade oferece; `Porta`);
- depois de CADA chamada ao controlador compara o estado de antes com o de agora e acerta dois interruptores: os atalhos de automação ficam
  suspensos enquanto o estado é a captura de tecla (T3-7), e o relógio de ~30 Hz fica ligado enquanto é tempo ou espera (T3-3). Quem manda é o
  ESTADO, não o efeito: toda saída da captura (confirmar, Esc, Enter duplo, descartar) retoma os atalhos, inclusive as que ninguém previu;
- diz o que aconteceu na barra de status (a dica do estado, o valor em edição, a frase do que mudou mais "Ctrl+Z desfaz", ou a recusa);
- segura qualquer erro (T3-13): uma exceção num filtro de eventos não pode escapar para o Qt nem deixar a tabela presa numa edição.

O que a janela de verdade chama, e só isto: do filtro de eventos, `tecla_pressionada(tecla, repeticao)` e `tecla_solta(nome)`; do relógio,
`tique()`; da janela do programa, `aplicativo_resolvido(valor)`; da tabela, `selecao_mudou()`, `perdeu_foco()` e `ganhou_foco()`; de tudo o mais
que invalide a edição (a janela desativada, o mapa trocado), `descartar()`. E o que ela pergunta: `editando()` (o Esc do aplicativo cede enquanto
houver edição) e `capturando()` (só a captura distingue o teclado numérico).

As regras sobre quais teclas a ligação consome:

- Ctrl e Alt voltam inteiros para a janela, em qualquer estado, e nem chegam ao controlador (Ctrl+Z desfaz mesmo no meio de uma edição, e isso a
  descarta: T3-8);
- navegando, só quatro teclas são dela (Enter, Shift+Enter, F2 e o apóstrofo: `TECLAS_DO_ESTADO`), e só elas consultam a porta. Sem linha
  selecionada seguem o caminho antigo; com duas ou mais, são consumidas com uma dica (T3-4);
- a REPETIÇÃO do sistema (tecla segurada) nunca chega ao controlador e é consumida SE o aperto que a originou foi consumido; senão segue para o
  Qt. É um refinamento do T3-3, no mesmo espírito, que cobre todos os estados com uma regra só: segurar ↓ continua rolando as linhas, segurar a
  tecla que confirmou não vira busca por letra na tabela, e segurar o Esc que cancelou não chega ao Esc do aplicativo (T3-9). Quem decide é
  sempre o último aperto da tecla; a soltura apenas encerra o consumo.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from .core import _append_runtime_log
from .teclado_aplicar import Resultado, nome_do_processo
from .teclado_edicao import (DICA_NAVEGANDO, TECLAS_DO_ESTADO, AbrirAplicativo, AbrirBarraLateral, AbrirTexto, AplicarAlvo, AplicarEspera, AplicarTempo,
                             AplicarTexto, Bip, Cancelar, Desmarcar, Dica, EdicaoPorTeclado, EditarCelula, Estado, FecharEditor, IniciarCaptura, LinhaInfo,
                             Marcar, MostrarValor, ProporTecla, Resposta, Tecla, chave_da_tecla, formatar_segundos, rotulo_do_botao)

SEGUNDOS_DA_MENSAGEM = 6.0  # quanto tempo a frase de "o que mudou" fica na barra de status (T3-12)
MENSAGEM_DO_ERRO = "Algo deu errado na edição pelo teclado; nada foi gravado."
MENSAGEM_DO_ERRO_GRAVADO = "Algo deu errado na edição pelo teclado, mas a mudança foi gravada: confira (Ctrl+Z desfaz)."
_NADA_GRAVADO = "Nada foi gravado."

_NAVEGACAO = frozenset(TECLAS_DO_ESTADO[Estado.NAVEGANDO])
_AJUSTES = frozenset({Estado.TEMPO, Estado.ESPERA})  # os estados em que o relógio roda

# Os rótulos do histórico (T3-14) e a frase de cada gravação de tecla, botão e programa: quem os distingue é o ESTADO de onde a gravação veio.
_ALVO_POR_ESTADO: dict[Estado, tuple[str, Callable[[str], str]]] = {
    Estado.TECLA: ("Editar tecla", lambda valor: f"Tecla trocada para {valor}"),
    Estado.BOTAO: ("Editar botão", lambda valor: f"Botão do mouse trocado para {rotulo_do_botao(valor)}"),
    Estado.APLICATIVO: ("Editar programa", lambda valor: f"Programa trocado para {nome_do_processo(valor) or valor}"),
}
ROTULO_TEXTO, ROTULO_TEMPO, ROTULO_ESPERA = "Editar texto", "Editar tempo apertado", "Editar espera"

# Cada efeito do controlador tem UM tratamento (o nome do método). Um teste confere que são exatamente as 17 classes do T2.
_TRATAMENTO: dict[type, str] = {
    Marcar: "_marcar", Desmarcar: "_fim_da_edicao", Cancelar: "_fim_da_edicao", FecharEditor: "_fechar_editor", IniciarCaptura: "_iniciar_captura",
    ProporTecla: "_propor_tecla", Bip: "_bip", AbrirTexto: "_abrir_texto", AbrirAplicativo: "_abrir_aplicativo", AplicarAlvo: "_aplicar_alvo",
    AplicarTexto: "_aplicar_texto", AplicarTempo: "_aplicar_tempo", AplicarEspera: "_aplicar_espera", Dica: "_dica", MostrarValor: "_mostrar_valor",
    AbrirBarraLateral: "_abrir_barra_lateral", EditarCelula: "_editar_celula",
}
EFEITOS_TRATADOS: tuple[type, ...] = tuple(_TRATAMENTO)


@runtime_checkable
class Porta(Protocol):
    """O que a janela de verdade (`teclado_ui.py`) oferece à ligação. Os testes usam uma porta falsa que cumpre a mesma lista.

    As quatro `aplicar_*` gravam no mapa pelas regras da barra lateral (`teclado_aplicar.py`), conferindo antes que o comando ainda é o que foi
    marcado, e devolvem o `Resultado`; `rotulo` é o nome do passo no histórico (o que o Ctrl+Z desfaz). `dica(texto, segundos)` com `segundos`
    igual a 0 é a dica que fica até ser trocada; com mais que 0 é uma mensagem passageira, e a dica que ficou volta depois."""

    # ---- leitura
    def quantas_linhas_selecionadas(self) -> int: ...
    def linha_atual(self) -> LinhaInfo | None: ...        # a ficha do comando da única linha selecionada
    def texto_do_editor(self) -> str: ...                  # o que está no editor de texto em linha agora
    # ---- ação
    def marcar(self, linha: int) -> None: ...              # destaca a linha em edição (e guarda o que a conferência da gravação precisa)
    def desmarcar(self) -> None: ...                       # fim da edição: fecha o que estiver aberto, tira a marca e o valor mostrado
    def fechar_editor(self) -> None: ...                   # fecha o editor de texto sem aplicar, a linha segue marcada
    def abrir_texto(self, linha: int, atual: str) -> None: ...
    def abrir_aplicativo(self, linha: int, atual: str) -> None: ...  # janela NÃO bloqueante: o resultado volta por `aplicativo_resolvido`
    def propor_tecla(self, nome: str) -> None: ...
    def bip(self) -> None: ...
    def aplicar_alvo(self, linha: int, valor: str, rotulo: str) -> Resultado: ...
    def aplicar_texto(self, linha: int, texto: str, rotulo: str) -> Resultado: ...
    def aplicar_tempo(self, linha: int, valor: float, rotulo: str) -> Resultado: ...
    def aplicar_espera(self, linha: int, valor: float, rotulo: str) -> Resultado: ...
    def dica(self, texto: str, segundos: float = 0.0) -> None: ...
    def mostrar_valor(self, texto: str) -> None: ...
    def limpar_dica(self) -> None: ...                     # a barra de status só é limpa se a mensagem ainda for a nossa
    def abrir_barra_lateral(self, linha: int) -> None: ...
    def editar_celula(self, linha: int) -> None: ...
    def suspender_atalhos(self, suspender: bool) -> None: ...
    def ligar_relogio(self, ligar: bool) -> None: ...


class LigacaoDoTeclado:
    """Uma por janela. Ver a docstring do módulo; os métodos públicos são o que a janela de verdade chama."""

    def __init__(self, porta: Porta, relogio: Callable[[], float] = time.monotonic, controlador: EdicaoPorTeclado | None = None) -> None:
        self._porta = porta
        self._relogio = relogio
        self._controlador = controlador if controlador is not None else EdicaoPorTeclado()
        self._estado = self._controlador.estado   # o estado para o qual os interruptores já foram acertados
        self._seguradas: set[str] = set()         # as teclas cujo último aperto foi consumido
        self._pendente = ""                       # a frase de "o que mudou", à espera do fim da edição para aparecer depois da dica da navegação
        self._gravou = False                      # alguma gravação deu certo na chamada em curso (o aviso de erro precisa saber)
        self._fundo = 0                           # a profundidade das chamadas aninhadas (o Qt pode nos chamar de volta no meio de um efeito)
        self._geracao = 0                         # sobe a cada edição descartada: o que sobrou dos efeitos dela já não vale

    # ---- o que a janela pergunta -----------------------------------------------------------------------------------------
    def editando(self) -> bool:
        """Há uma edição em curso? (o Esc do aplicativo cede enquanto houver: T3-9)"""
        return self._controlador.estado != Estado.NAVEGANDO

    def capturando(self) -> bool:
        """O estado é a captura de tecla? É quando o teclado numérico tem nomes próprios (NUM5, NUMENTER...)."""
        return self._controlador.estado == Estado.TECLA

    # ---- o que a janela conta --------------------------------------------------------------------------------------------
    def tecla_pressionada(self, tecla: Tecla, repeticao: bool = False) -> bool:
        """Uma tecla foi apertada. Devolve se a janela deve RETÊ-LA (verdadeiro) ou deixá-la seguir para o Qt (falso)."""
        if tecla.ctrl or tecla.alt:
            return False
        identidade = tecla.nome.upper() or tecla.texto or "?"
        if repeticao:
            return identidade in self._seguradas
        consumida = self._guardado(lambda: self._processar(tecla))
        if consumida:
            self._seguradas.add(identidade)
        else:
            self._seguradas.discard(identidade)
        return consumida

    def tecla_solta(self, nome: str) -> bool:
        """Uma tecla foi solta: a seta que estava contando fixa o valor do instante."""
        self._seguradas.discard(nome.upper())
        return self._guardado(lambda: self._entregar(self._controlador.soltar(nome, self._relogio())))

    def tique(self) -> None:
        """O relógio de ~30 Hz (ligado só em tempo e espera): a rampa da seta segurada anda pelo relógio, não pela repetição de tecla do sistema."""
        self._guardado(lambda: self._entregar(self._controlador.tique(self._relogio())))

    def aplicativo_resolvido(self, valor: str | None) -> None:
        """A janela do programa fechou: o programa escolhido, ou None se foi cancelada."""
        self._guardado(lambda: self._entregar(self._controlador.conteudo_resolvido(valor)))

    def descartar(self) -> None:
        """O que estava em edição já não vale (T3-8): a janela foi desativada, o mapa mudou por baixo, o editor perdeu o foco..."""
        self._guardado(self._descartando)

    def selecao_mudou(self) -> None:
        """A seleção da tabela mudou (inclui o `refresh` de um desfazer e a linha do tempo selecionando): descarta."""
        self.descartar()

    def perdeu_foco(self) -> None:
        """A tabela perdeu o foco (a janela só chama quando não foi para o editor de texto nem para a janela do programa): descarta e limpa a dica."""
        self.descartar()
        self._tentar("limpar a dica", self._porta.limpar_dica)

    def ganhou_foco(self) -> None:
        """A tabela ganhou o foco: a dica da navegação, se não há edição em curso."""
        if not self.editando():
            self._tentar("mostrar a dica", lambda: self._porta.dica(DICA_NAVEGANDO, 0.0))

    # ---- o miolo ----------------------------------------------------------------------------------------------------------
    def _guardado(self, trabalho: Callable[[], bool]) -> bool:
        """Roda `trabalho` e acerta os interruptores. Qualquer exceção, de qualquer peça, vira o caminho do T3-13 e a tecla é consumida."""
        if self._fundo == 0:
            self._gravou = False
        self._fundo += 1
        try:
            consumida = trabalho()
            self._sincronizar()
        except Exception as erro:  # noqa: BLE001 - tudo o que sair de um efeito, da porta ou do controlador
            self._falhou(erro)
            consumida = True
        finally:
            self._fundo -= 1
        return consumida

    def _processar(self, tecla: Tecla) -> bool:
        estado = self._controlador.estado
        linha: LinhaInfo | None = None
        texto: str | None = None
        if estado == Estado.NAVEGANDO:
            if chave_da_tecla(tecla) not in _NAVEGACAO:
                return False  # a digitação comum não custa uma consulta à janela
            selecionadas = self._porta.quantas_linhas_selecionadas()
            if selecionadas == 0:
                return False
            if selecionadas > 1:
                self._porta.dica(f"Escolha um só comando para editar com o teclado (há {selecionadas} selecionados)", SEGUNDOS_DA_MENSAGEM)
                return True
            linha = self._porta.linha_atual()
            if linha is None:
                return False
        elif estado == Estado.TEXTO and tecla.nome.upper() == "ENTER":
            texto = self._porta.texto_do_editor()  # só o Enter confirma: as outras teclas são do editor
        return self._entregar(self._controlador.pressionar(tecla, self._relogio(), linha, texto))

    def _entregar(self, resposta: Resposta) -> bool:
        self._executar(resposta.efeitos)
        return resposta.consumida

    def _descartando(self) -> bool:
        resposta = self._controlador.descartar()
        if resposta.efeitos:
            self._geracao += 1  # havia uma edição: se este descarte veio no meio dos efeitos de outra chamada, o resto deles já não vale
        return self._entregar(resposta)

    def _executar(self, efeitos: tuple) -> None:
        geracao = self._geracao
        for efeito in efeitos:
            if self._geracao != geracao:
                break  # a edição foi descartada no meio (um evento do Qt causado pelo próprio efeito): não abrir editor para uma edição que acabou
            tratamento = _TRATAMENTO.get(type(efeito))
            if tratamento is None:
                raise TypeError(f"efeito sem tratamento: {type(efeito).__name__}")
            getattr(self, tratamento)(efeito)
        self._mostrar_pendente()

    def _sincronizar(self, protegido: bool = False) -> None:
        """Acerta os dois interruptores pelo estado do controlador, comparando com o último estado acertado (T3-7 e T3-3)."""
        antes, agora = self._estado, self._controlador.estado
        self._estado = agora  # antes de chamar a porta: uma porta que falha não faz o mesmo pedido de novo na limpeza
        fazer = self._tentar if protegido else (lambda _o_que, chamada: chamada())
        if (antes == Estado.TECLA) != (agora == Estado.TECLA):
            fazer("acertar a suspensão dos atalhos", lambda: self._porta.suspender_atalhos(agora == Estado.TECLA))
        if (antes in _AJUSTES) != (agora in _AJUSTES):
            fazer("acertar o relógio", lambda: self._porta.ligar_relogio(agora in _AJUSTES))

    def _falhou(self, erro: BaseException) -> None:
        """T3-13: registra, descarta a edição, tira a marca, avisa e acerta os interruptores. Nada aqui pode levantar de novo."""
        _append_runtime_log(f"TECLADO_EDICAO erro={type(erro).__name__}: {erro} estado={self._estado.value}")
        gravou, self._pendente = self._gravou, ""
        self._tentar("descartar a edição", self._controlador.descartar)
        self._tentar("tirar a marca", self._porta.desmarcar)
        self._tentar("mostrar a dica da navegação", lambda: self._porta.dica(DICA_NAVEGANDO, 0.0))
        self._tentar("avisar o erro", lambda: self._porta.dica(MENSAGEM_DO_ERRO_GRAVADO if gravou else MENSAGEM_DO_ERRO, SEGUNDOS_DA_MENSAGEM))
        self._tentar("acertar os interruptores", lambda: self._sincronizar(protegido=True))

    @staticmethod
    def _tentar(o_que: str, chamada: Callable[[], object]) -> None:
        try:
            chamada()
        except Exception as erro:  # noqa: BLE001 - a limpeza de um erro não pode ter erro que escape
            _append_runtime_log(f"TECLADO_EDICAO falha ao {o_que}: {type(erro).__name__}: {erro}")

    def _mostrar_pendente(self) -> None:
        if self._pendente:
            frase, self._pendente = self._pendente, ""
            self._porta.dica(frase, SEGUNDOS_DA_MENSAGEM)

    def _gravado(self, descricao: str, resultado: Resultado) -> None:
        """A frase do que aconteceu fica pendente até o fim da edição, para aparecer DEPOIS da dica da navegação (senão a dica a cobriria)."""
        if resultado.ok:
            self._gravou = True
            aviso = f" {resultado.aviso}" if resultado.aviso else ""
            self._pendente = f"{descricao}.{aviso} Ctrl+Z desfaz."
        else:
            self._pendente = resultado.mensagem or _NADA_GRAVADO

    # ---- um tratamento por efeito ---------------------------------------------------------------------------------------
    def _marcar(self, efeito: Marcar) -> None:
        self._porta.marcar(efeito.linha)

    def _fim_da_edicao(self, _efeito: Desmarcar | Cancelar) -> None:
        self._porta.desmarcar()
        self._porta.dica(DICA_NAVEGANDO, 0.0)
        self._mostrar_pendente()

    def _fechar_editor(self, _efeito: FecharEditor) -> None:
        self._porta.fechar_editor()

    def _iniciar_captura(self, _efeito: IniciarCaptura) -> None:
        """A captura não tem campo: é a tabela mesma que recebe a tecla (T3-5). Quem a acompanha é a suspensão dos atalhos, decidida pelo estado."""

    def _propor_tecla(self, efeito: ProporTecla) -> None:
        self._porta.propor_tecla(efeito.nome)

    def _bip(self, _efeito: Bip) -> None:
        self._porta.bip()

    def _abrir_texto(self, efeito: AbrirTexto) -> None:
        self._porta.abrir_texto(efeito.linha, efeito.atual)

    def _abrir_aplicativo(self, efeito: AbrirAplicativo) -> None:
        self._porta.abrir_aplicativo(efeito.linha, efeito.atual)

    def _aplicar_alvo(self, efeito: AplicarAlvo) -> None:
        if self._estado not in _ALVO_POR_ESTADO:
            raise RuntimeError(f"AplicarAlvo vindo do estado {self._estado.value}: só a captura, o botão e o programa gravam um alvo")
        rotulo, frase = _ALVO_POR_ESTADO[self._estado]
        self._gravado(frase(efeito.valor), self._porta.aplicar_alvo(efeito.linha, efeito.valor, rotulo))

    def _aplicar_texto(self, efeito: AplicarTexto) -> None:
        self._gravado("Texto trocado", self._porta.aplicar_texto(efeito.linha, efeito.texto, ROTULO_TEXTO))

    def _aplicar_tempo(self, efeito: AplicarTempo) -> None:
        self._gravado(f"Tempo apertado: {formatar_segundos(efeito.valor)}", self._porta.aplicar_tempo(efeito.linha, efeito.valor, ROTULO_TEMPO))

    def _aplicar_espera(self, efeito: AplicarEspera) -> None:
        numero = formatar_segundos(efeito.valor)
        descricao = f"Começa em {numero}" if efeito.linha == 0 else f"Espera antes do comando: {numero}"
        self._gravado(descricao, self._porta.aplicar_espera(efeito.linha, efeito.valor, ROTULO_ESPERA))

    def _dica(self, efeito: Dica) -> None:
        self._porta.dica(efeito.texto, 0.0)

    def _mostrar_valor(self, efeito: MostrarValor) -> None:
        self._porta.mostrar_valor(efeito.texto)

    def _abrir_barra_lateral(self, efeito: AbrirBarraLateral) -> None:
        self._porta.abrir_barra_lateral(efeito.linha)

    def _editar_celula(self, efeito: EditarCelula) -> None:
        self._porta.editar_celula(efeito.linha)
