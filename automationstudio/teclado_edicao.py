"""Edição pelo teclado (25.9, T2): o que cada tecla faz quando a janela do Studio está em primeiro plano. Lógica pura, sem Qt.

Especificação: md/ESPEC_TECLADO_25_9.md (TEC-01 a TEC-16, D1 a D16) e md/FICHA_TECLADO_T2_25_9.md (T2-1 a T2-13). Testes:
tests/unit/test_teclado_edicao.py (o controlador), test_teclado_varredura.py (sequências ao acaso contra invariantes), test_teclado_curva.py
(a seta segurada), test_espera_entre_comandos.py (o modelo).

O desenho: a janela (T3) traduz cada tecla do Qt numa `Tecla` e a entrega a `EdicaoPorTeclado.pressionar`; o controlador devolve uma
`Resposta`: se a tecla foi consumida (se não foi, a janela a deixa seguir: setas, letras e Ctrl+C continuam sendo do Qt) e a lista de
efeitos que a janela executa (marcar a linha, abrir o editor, mostrar o valor, tocar o bip, aplicar a mudança no mapa...). O relógio é
um argumento (`agora`): nada aqui dorme nem lê a hora, então a curva e o Enter duplo são provados com números. Enquanto há uma seta
apertada a janela chama `tique` umas 30 vezes por segundo (a rampa anda pelo relógio, não pela repetição de tecla do sistema, que varia
de máquina para máquina) e `soltar` quando ela é solta.

Os estados:

  NAVEGANDO   nada em edição. Só quatro atalhos são do controlador: Enter (edita o conteúdo do comando), `'` (edita a espera antes
              dele), F2 (edita a célula) e Shift+Enter (abre a barra lateral). Tudo mais volta para a janela.
  TECLA       captura a tecla de um comando de tecla: a primeira tecla vira PROPOSTA (com um bip); a MESMA de novo confirma.
  TEXTO       o texto está num editor da janela: Enter confirma, Esc cancela; o resto é do editor.
  APLICATIVO  o seletor de programa está aberto (é modal): as teclas são dele; a janela avisa o resultado em `conteudo_resolvido`.
  BOTAO       ← → percorrem os botões do mouse que o modelo conhece; Enter confirma.
  TEMPO       ← → mudam quanto tempo a tecla (ou o botão) fica apertada; Enter aceita, Esc descarta.
  ESPERA      ← → mudam a espera antes do comando (a lacuna do modelo: `AutomationMap.gap_before`); Enter aceita, Esc descarta.

Nos ajustes (BOTAO, TEMPO, ESPERA) as teclas que o controlador não usa são ENGOLIDAS (consumidas sem efeito), menos as com Ctrl ou
Alt, que seguem para os atalhos da janela: sem isso a tabela abriria um editor de célula a cada letra digitada. O valor em edição só
vai para o mapa no Enter (T2-6); Esc, o foco que sai ou a linha que muda o descartam (`descartar`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .core import MOUSE_BUTTON_NAMES, ActionType, AutomationMap, InputType, normalized_app_target

# ------------------------------------------------------------------------------------------------ a curva da seta segurada (D5)
# Uma tabela só: mudar a sensação da seta é mudar estes números (a ficha, seção 5, tem a tabela de resultados).
PASSO_TOQUE = 0.01          # um toque (apertar e soltar em menos de LIMITE_TOQUE) muda isto, na hora de apertar
LIMITE_TOQUE = 0.3          # a partir de quantos segundos apertada a seta deixa de ser toque e vira rampa
VELOCIDADE_INICIAL = 0.1    # segundos de valor por segundo de seta apertada, durante os primeiros SEGUNDOS_LENTOS
SEGUNDOS_LENTOS = 3.0       # o pedido: "os 3 primeiros segundos bem lentos"
DOBRA_A_CADA = 2.0          # depois dos lentos, a velocidade dobra a cada tantos segundos...
VELOCIDADE_MAXIMA = 60.0    # ...até este teto (1 minuto de valor por segundo)
TEMPO_MINIMO = 0.01         # o menor tempo apertado: o modelo recusa tecla ou botão com duração 0
TETO = 3600.0               # o maior valor editável: uma hora
RESOLUCAO = 0.001           # o valor é sempre em milissegundos
_CASAS = 3                  # RESOLUCAO em casas decimais
JANELA_ENTER_DUPLO = 0.4    # segundos: dois Enter tão juntos, sem outra tecla no meio, são "Enter, Enter" (D1)

_K = math.log(2.0) / DOBRA_A_CADA
_SEGUNDOS_DO_TETO = SEGUNDOS_LENTOS + DOBRA_A_CADA * math.log2(VELOCIDADE_MAXIMA / VELOCIDADE_INICIAL)  # ≈ 21,46 s


def velocidade(segundos: float) -> float:
    """Quanto o valor muda por segundo, depois de `segundos` com a seta apertada: constante nos primeiros 3 s, dobra a cada 2 s, para no teto."""
    t = max(0.0, float(segundos))
    if t <= SEGUNDOS_LENTOS:
        return VELOCIDADE_INICIAL
    if t >= _SEGUNDOS_DO_TETO:
        return VELOCIDADE_MAXIMA
    return VELOCIDADE_INICIAL * 2.0 ** ((t - SEGUNDOS_LENTOS) / DOBRA_A_CADA)


def _distancia(t: float) -> float:
    """A integral de `velocidade` de 0 a `t`: quanto o valor já andou na rampa."""
    if t <= SEGUNDOS_LENTOS:
        return VELOCIDADE_INICIAL * t
    if t > _SEGUNDOS_DO_TETO:  # `>` e não `>=`: no próprio instante do teto vale a fórmula de baixo, senão esta linha chamaria a si mesma
        return _distancia(_SEGUNDOS_DO_TETO) + VELOCIDADE_MAXIMA * (t - _SEGUNDOS_DO_TETO)
    return VELOCIDADE_INICIAL * SEGUNDOS_LENTOS + VELOCIDADE_INICIAL / _K * (2.0 ** ((t - SEGUNDOS_LENTOS) / DOBRA_A_CADA) - 1.0)


def mudanca_acumulada(segundos: float) -> float:
    """Quanto o valor mudou (sem sinal) com a seta apertada há `segundos`. O toque de PASSO_TOQUE, aplicado ao apertar, já conta; a
    rampa só começa em LIMITE_TOQUE e é contínua com o toque (em LIMITE_TOQUE as duas dão PASSO_TOQUE)."""
    t = max(0.0, float(segundos))
    if t < LIMITE_TOQUE:
        return PASSO_TOQUE
    return PASSO_TOQUE + _distancia(t) - _distancia(LIMITE_TOQUE)


def valor_apos(base: float, sentido: int, segundos: float, minimo: float, maximo: float = TETO) -> float:
    """O valor depois de `segundos` com a seta apertada, a partir de `base`: `sentido` -1 diminui, +1 aumenta; arredondado ao
    milissegundo e preso entre `minimo` e `maximo`."""
    bruto = float(base) + (1 if sentido >= 0 else -1) * mudanca_acumulada(segundos)
    return min(maximo, max(minimo, round(bruto, _CASAS)))


def formatar_segundos(valor: float) -> str:
    """"0,25 s", "-0,6 s", "1000 s": até três casas, sem zeros sobrando, vírgula decimal."""
    texto = f"{valor:.{_CASAS}f}".rstrip("0").rstrip(".")
    if texto in ("", "-0"):
        texto = "0"
    return texto.replace(".", ",") + " s"


# ------------------------------------------------------------------------------------------------ entrada: a tecla e a linha
class Estado(Enum):
    NAVEGANDO = "navegando"
    TECLA = "tecla"
    TEXTO = "texto"
    APLICATIVO = "aplicativo"
    BOTAO = "botao"
    TEMPO = "tempo"
    ESPERA = "espera"


@dataclass(frozen=True)
class Tecla:
    """Uma tecla apertada, já traduzida pela janela. `nome` é o do Studio ("A", "ENTER", "LEFT", "F13"...; vazio se a tecla não tem nome
    no Studio) e `texto` o caractere que ela digitou: o apóstrofo é reconhecido por ele, em qualquer layout de teclado (D3)."""
    nome: str
    texto: str = ""
    ctrl: bool = False
    shift: bool = False
    alt: bool = False


def chave_da_tecla(tecla: Tecla) -> str:
    """O nome da tecla com os modificadores, na ordem Ctrl, Alt, Shift: "ENTER", "SHIFT+ENTER", "'"."""
    prefixo = ("CTRL+" if tecla.ctrl else "") + ("ALT+" if tecla.alt else "") + ("SHIFT+" if tecla.shift else "")
    return prefixo + (tecla.nome.upper() or tecla.texto)


_MOTIVO_SO_APERTA = "Este comando só aperta a tecla (ou o botão) e não a solta: não tem tempo apertado para ajustar."
_MOTIVO_SO_SOLTA = "Este comando só solta a tecla (ou o botão): não tem tempo apertado para ajustar."
_MOTIVO_TEXTO = "O tempo do texto é calculado pelo comprimento dele: não há o que ajustar."
_MOTIVO_APLICATIVO = "Quem define quanto demora para abrir é o programa: não há tempo para ajustar."
_MOTIVO_OUTROS = "O tempo deste comando se ajusta na barra lateral (Shift+Enter)."


@dataclass(frozen=True)
class LinhaInfo:
    """O que o controlador precisa saber do comando da linha atual (a janela monta com `linha_info_de`)."""
    indice: int
    tipo: InputType
    acao: ActionType
    alvo: str                 # a tecla, o botão ou o programa
    texto: str
    tempo: float              # quanto a tecla (ou o botão) fica apertada; só vale quando `tempo_editavel`
    tempo_editavel: bool
    tempo_motivo: str         # por que não se edita o tempo ("" quando se edita)
    espera: float             # AutomationMap.gap_before
    espera_minima: float      # AutomationMap.min_gap_before

    @property
    def primeiro(self) -> bool:
        return self.indice == 0


def linha_info_de(mapa: AutomationMap, indice: int) -> LinhaInfo:
    """A ficha do comando `indice` do mapa. O tempo só é editável em tecla e botão de apertar e soltar (T2-4); nos outros tipos a
    ficha traz o motivo, que o controlador mostra em vez de mudar algo que não vale."""
    cmd = mapa.commands[indice]
    editavel = cmd.type in (InputType.KEY, InputType.MOUSE_BUTTON) and cmd.action == ActionType.PRESS_AND_RELEASE
    if editavel:
        motivo = ""
    elif cmd.type == InputType.TEXT:
        motivo = _MOTIVO_TEXTO
    elif cmd.type == InputType.APP_OPEN:
        motivo = _MOTIVO_APLICATIVO
    elif cmd.type in (InputType.KEY, InputType.MOUSE_BUTTON):
        motivo = _MOTIVO_SO_APERTA if cmd.action == ActionType.PRESS else _MOTIVO_SO_SOLTA
    else:
        motivo = _MOTIVO_OUTROS
    return LinhaInfo(indice=indice, tipo=cmd.type, acao=cmd.action, alvo=str(cmd.target or ""), texto=str(cmd.text or ""),
                     tempo=float(cmd.duration), tempo_editavel=editavel, tempo_motivo=motivo,
                     espera=mapa.gap_before(indice), espera_minima=mapa.min_gap_before(indice))


# ------------------------------------------------------------------------------------------------ saída: os efeitos
@dataclass(frozen=True)
class Marcar:
    """Marca (destaca) a linha que está sendo editada."""
    linha: int


@dataclass(frozen=True)
class Desmarcar:
    """Fim da edição, com o resultado já aplicado: fecha o que estiver aberto e tira a marca da linha."""


@dataclass(frozen=True)
class Cancelar:
    """Fim da edição, sem aplicar nada: fecha o que estiver aberto e tira a marca da linha."""


@dataclass(frozen=True)
class FecharEditor:
    """Fecha o editor ou a captura sem aplicar, mas a linha continua marcada (a edição passa para outro campo)."""


@dataclass(frozen=True)
class IniciarCaptura:
    linha: int
    atual: str


@dataclass(frozen=True)
class ProporTecla:
    nome: str


@dataclass(frozen=True)
class Bip:
    """O "bit" de confirmação: a tecla foi proposta; aperte a mesma de novo para valer."""


@dataclass(frozen=True)
class AbrirTexto:
    linha: int
    atual: str


@dataclass(frozen=True)
class AbrirAplicativo:
    linha: int
    atual: str


@dataclass(frozen=True)
class AplicarAlvo:
    """Grava a tecla, o botão ou o programa escolhido no comando."""
    linha: int
    valor: str


@dataclass(frozen=True)
class AplicarTexto:
    linha: int
    texto: str


@dataclass(frozen=True)
class AplicarTempo:
    """Grava o tempo apertado (duração) do comando, sem mexer nos seguintes: igual a editar a célula "Duração" da tabela."""
    linha: int
    valor: float


@dataclass(frozen=True)
class AplicarEspera:
    """Grava a espera: a janela chama `AutomationMap.set_gap_before(linha, valor)`, que empurra os seguintes junto."""
    linha: int
    valor: float


@dataclass(frozen=True)
class Dica:
    """Mostra o que se pode fazer agora (TEC-09)."""
    texto: str


@dataclass(frozen=True)
class MostrarValor:
    """Mostra o valor em edição (na barra de status)."""
    texto: str


@dataclass(frozen=True)
class AbrirBarraLateral:
    linha: int


@dataclass(frozen=True)
class EditarCelula:
    linha: int


@dataclass(frozen=True)
class Resposta:
    """O que a janela faz com a tecla: `consumida` diz se ela NÃO deve seguir para o Qt; `efeitos`, o que executar, em ordem."""
    consumida: bool
    efeitos: tuple = ()


_NADA = Resposta(False, ())


# ------------------------------------------------------------------------------------------------ a dica didática (TEC-09)
# As teclas que cada estado trata de verdade, na forma de `chave_da_tecla`. O teste prova as duas pontas: o estado faz exatamente
# isto (nada a mais, nada a menos) e cada uma está escrita na dica do estado.
TECLAS_DO_ESTADO: dict[Estado, tuple[str, ...]] = {
    Estado.NAVEGANDO: ("ENTER", "SHIFT+ENTER", "F2", "'"),
    Estado.TECLA: ("*",),  # qualquer tecla com nome vira proposta
    Estado.TEXTO: ("ENTER", "ESC"),
    Estado.APLICATIVO: (),
    Estado.BOTAO: ("LEFT", "RIGHT", "ENTER", "ESC"),
    Estado.TEMPO: ("LEFT", "RIGHT", "ENTER", "ESC", "'"),
    Estado.ESPERA: ("LEFT", "RIGHT", "ENTER", "ESC"),
}
ROTULOS: dict[str, str] = {"ENTER": "Enter", "SHIFT+ENTER": "Shift+Enter", "F2": "F2", "'": "'", "ESC": "Esc", "LEFT": "←", "RIGHT": "→"}

DICA_NAVEGANDO = "Enter edita este comando  ·  ' edita a espera antes dele  ·  F2 edita a célula  ·  Shift+Enter abre os detalhes"
DICA_SEM_CONTEUDO = "Este comando não tem tecla nem texto para editar aqui  ·  Shift+Enter abre os detalhes na barra lateral"
DICA_TEXTO_VAZIO = "O texto não pode ficar vazio: escreva algo ou aperte Esc para cancelar"
DICA_TECLA_DESCONHECIDA = "Essa tecla não pode ser usada num comando: aperte outra"
DICA_ACEITE_ANTES = "Aceite com Enter (ou descarte com Esc) o que mudou antes de editar a espera"
_ENTER_DUPLO = "  ·  Enter, Enter muda o tempo apertado"


def dica_do_estado(estado: Estado, linha: LinhaInfo | None = None, proposta: str = "") -> str:
    """A frase que diz, em cada estado, o que as teclas fazem. `proposta` é a tecla que a captura está esperando confirmar."""
    enter_duplo = _ENTER_DUPLO if linha is not None and linha.tempo_editavel else ""
    if estado == Estado.NAVEGANDO:
        return DICA_NAVEGANDO
    if estado == Estado.TECLA:
        if proposta:
            return f"{proposta} é a proposta: aperte {proposta} de novo para confirmar, outra tecla para trocar ou Esc para cancelar"
        return "Aperte a nova tecla  ·  Esc cancela (para gravar a própria Esc, aperte Shift+Esc)" + enter_duplo
    if estado == Estado.TEXTO:
        return "Digite o texto  ·  Enter confirma  ·  Esc cancela"
    if estado == Estado.APLICATIVO:
        return "Escolha o programa na janela que abriu  ·  Esc cancela"
    if estado == Estado.BOTAO:
        return "← → trocam o botão  ·  Enter confirma  ·  Esc cancela" + enter_duplo
    if estado == Estado.TEMPO:
        return "← → mudam o tempo apertado (segure para acelerar)  ·  Enter aceita  ·  Esc descarta  ·  ' vai para a espera"
    return "← → mudam a espera antes deste comando (segure para acelerar)  ·  Enter aceita  ·  Esc descarta"


_ROTULO_DO_BOTAO = {"left": "esquerdo", "right": "direito", "middle": "do meio", "x1": "lateral X1", "x2": "lateral X2"}


# ------------------------------------------------------------------------------------------------ o controlador
class EdicaoPorTeclado:
    """O estado da edição pelo teclado. Uma instância por janela; ver a docstring do módulo."""

    def __init__(self) -> None:
        self._limpar()

    # ---- leitura (os testes e a janela olham; só o controlador escreve) ----------------------------------------------
    @property
    def estado(self) -> Estado:
        return self._estado

    @property
    def linha(self) -> int | None:
        """O índice do comando em edição, ou None se nada está marcado."""
        return None if self._linha is None else self._linha.indice

    @property
    def proposta(self) -> str:
        return self._proposta

    @property
    def botao(self) -> str:
        return self._botao

    @property
    def valor(self) -> float | None:
        """O valor em edição (TEMPO ou ESPERA), que só vai para o mapa no Enter."""
        return self._valor

    def _limpar(self) -> None:
        self._estado = Estado.NAVEGANDO
        self._linha: LinhaInfo | None = None
        self._proposta = ""
        self._botao = ""
        self._valor: float | None = None
        self._inicial = 0.0
        self._minimo = 0.0
        self._maximo = TETO
        self._t_enter = 0.0     # o instante do Enter que abriu a edição do conteúdo (para o Enter duplo)
        self._outra = False     # houve outra tecla depois do Enter que abriu? Então o próximo Enter não é "duplo"
        self._seta = ""         # a seta apertada agora: "LEFT", "RIGHT" ou ""
        self._t_seta = 0.0
        self._base = 0.0        # o valor quando esta seta foi apertada

    # ---- a tecla apertada ---------------------------------------------------------------------------------------------
    def pressionar(self, tecla: Tecla, agora: float, linha: LinhaInfo | None = None, texto: str | None = None) -> Resposta:
        """Uma tecla foi apertada (não a repetição do sistema: a janela as filtra) no instante `agora`, em segundos.

        `linha` é a ficha do comando atual da tabela (só é lida em NAVEGANDO); `texto` é o que está no editor de texto agora, se
        ele estiver aberto (só é lido ao confirmar o texto)."""
        nome = tecla.nome.upper()
        simples = not (tecla.ctrl or tecla.alt or tecla.shift)
        if self._estado == Estado.NAVEGANDO:
            return self._navegando(tecla, nome, agora, linha)
        if self._estado == Estado.TECLA:
            return self._captura(tecla, nome, simples, agora)
        if self._estado == Estado.TEXTO:
            return self._texto_aberto(nome, simples, agora, texto)
        if self._estado == Estado.APLICATIVO:
            return _NADA
        if self._estado == Estado.BOTAO:
            return self._botao_aberto(tecla, nome, simples, agora)
        return self._ajuste(tecla, nome, simples, agora)

    def _navegando(self, tecla: Tecla, nome: str, agora: float, linha: LinhaInfo | None) -> Resposta:
        if linha is None or tecla.ctrl or tecla.alt:
            return _NADA
        if nome == "ENTER":
            if tecla.shift:
                return Resposta(True, (AbrirBarraLateral(linha.indice),))
            return self._abrir_conteudo(agora, linha)
        if nome == "F2" and not tecla.shift:
            return Resposta(True, (EditarCelula(linha.indice),))
        if tecla.texto == "'":
            return self._abrir_espera(linha)
        return _NADA

    def _comecar(self, estado: Estado, agora: float, linha: LinhaInfo) -> None:
        self._limpar()
        self._estado, self._linha, self._t_enter = estado, linha, agora

    def _abrir_conteudo(self, agora: float, linha: LinhaInfo) -> Resposta:
        i = linha.indice
        if linha.tipo == InputType.KEY:
            self._comecar(Estado.TECLA, agora, linha)
            return Resposta(True, (Marcar(i), IniciarCaptura(i, linha.alvo), Dica(dica_do_estado(Estado.TECLA, linha))))
        if linha.tipo == InputType.TEXT:
            self._comecar(Estado.TEXTO, agora, linha)
            return Resposta(True, (Marcar(i), AbrirTexto(i, linha.texto), Dica(dica_do_estado(Estado.TEXTO, linha))))
        if linha.tipo == InputType.APP_OPEN:
            self._comecar(Estado.APLICATIVO, agora, linha)
            return Resposta(True, (Marcar(i), AbrirAplicativo(i, linha.alvo), Dica(dica_do_estado(Estado.APLICATIVO, linha))))
        if linha.tipo == InputType.MOUSE_BUTTON:
            self._comecar(Estado.BOTAO, agora, linha)
            atual = linha.alvo.lower()
            self._botao = atual if atual in MOUSE_BUTTON_NAMES else MOUSE_BUTTON_NAMES[0]
            return Resposta(True, (Marcar(i), MostrarValor(self._texto_do_botao()), Dica(dica_do_estado(Estado.BOTAO, linha))))
        return Resposta(True, (Dica(DICA_SEM_CONTEUDO),))  # mover, rolar e esperar: sem conteúdo simples; a barra lateral edita

    # ---- captura de tecla ----------------------------------------------------------------------------------------------
    def _captura(self, tecla: Tecla, nome: str, simples: bool, agora: float) -> Resposta:
        linha = self._linha
        if nome == "ESC" and simples:
            return self._cancelar()
        if nome == "ENTER" and simples and self._enter_duplo(agora):
            return self._abrir_tempo()
        self._outra = True
        if not nome:
            return Resposta(True, (Dica(DICA_TECLA_DESCONHECIDA),))
        if nome == self._proposta:
            return self._aplicar_alvo(nome, igual=nome == linha.alvo.upper())
        self._proposta = nome
        return Resposta(True, (ProporTecla(nome), Bip(), Dica(dica_do_estado(Estado.TECLA, linha, proposta=nome))))

    def _enter_duplo(self, agora: float) -> bool:
        return not self._outra and agora <= self._t_enter + JANELA_ENTER_DUPLO

    def _abrir_tempo(self) -> Resposta:
        """O Enter duplo: se o comando tem tempo apertado, passa para ele; senão explica por que não (e a edição continua)."""
        linha = self._linha
        if not linha.tempo_editavel:
            return Resposta(True, (Dica(linha.tempo_motivo),))
        self._entrar_ajuste(Estado.TEMPO, linha.tempo, TEMPO_MINIMO, max(TETO, linha.tempo))
        return Resposta(True, (FecharEditor(), MostrarValor(self._texto_do_valor()), Dica(dica_do_estado(Estado.TEMPO, linha))))

    # ---- texto ---------------------------------------------------------------------------------------------------------
    def _texto_aberto(self, nome: str, simples: bool, agora: float, texto: str | None) -> Resposta:
        linha = self._linha
        if nome == "ESC" and simples:
            return self._cancelar()
        if nome == "ENTER" and simples:
            if self._enter_duplo(agora):
                return self._abrir_tempo()
            atual = "" if texto is None else texto
            if atual == "":
                return Resposta(True, (Dica(DICA_TEXTO_VAZIO),))
            efeitos = (Desmarcar(),) if atual == linha.texto else (AplicarTexto(linha.indice, atual), Desmarcar())
            self._limpar()
            return Resposta(True, efeitos)
        self._outra = True  # o que se digita é do editor; mas depois dele o próximo Enter confirma, não é "duplo"
        return _NADA

    # ---- seletor de aplicativo ----------------------------------------------------------------------------------------
    def conteudo_resolvido(self, valor: str | None) -> Resposta:
        """A janela avisa como o seletor de programa fechou: o programa escolhido, ou None se foi cancelado."""
        if self._estado != Estado.APLICATIVO:
            return _NADA
        if valor is None or not normalized_app_target(valor):
            return self._cancelar()
        return self._aplicar_alvo(str(valor), igual=str(valor) == self._linha.alvo)

    # ---- botão do mouse -------------------------------------------------------------------------------------------------
    def _texto_do_botao(self) -> str:
        return f"Botão do mouse: {_ROTULO_DO_BOTAO.get(self._botao, self._botao)} ({self._botao})"

    def _botao_aberto(self, tecla: Tecla, nome: str, simples: bool, agora: float) -> Resposta:
        linha = self._linha
        if nome == "ESC" and simples:
            return self._cancelar()
        if nome == "ENTER" and simples:
            if self._enter_duplo(agora):
                return self._abrir_tempo()
            return self._aplicar_alvo(self._botao, igual=self._botao == linha.alvo.lower())
        self._outra = True
        if nome in ("LEFT", "RIGHT") and simples:
            posicao = MOUSE_BUTTON_NAMES.index(self._botao) + (1 if nome == "RIGHT" else -1)
            self._botao = MOUSE_BUTTON_NAMES[max(0, min(len(MOUSE_BUTTON_NAMES) - 1, posicao))]
            return Resposta(True, (MostrarValor(self._texto_do_botao()),))
        return self._engolir(tecla)

    # ---- tempo apertado e espera: o valor com as setas ------------------------------------------------------------------
    def _entrar_ajuste(self, estado: Estado, valor: float, minimo: float, maximo: float) -> None:
        self._estado, self._proposta, self._seta = estado, "", ""
        self._valor = self._inicial = float(valor)
        self._minimo, self._maximo = float(minimo), float(maximo)

    def _abrir_espera(self, linha: LinhaInfo) -> Resposta:
        self._limpar()
        self._linha = linha
        self._entrar_ajuste(Estado.ESPERA, linha.espera, linha.espera_minima, max(TETO, linha.espera))
        return Resposta(True, (Marcar(linha.indice), MostrarValor(self._texto_do_valor()), Dica(dica_do_estado(Estado.ESPERA, linha))))

    def _texto_do_valor(self) -> str:
        valor = self._valor
        limite = " (mínimo)" if valor <= self._minimo else " (máximo)" if valor >= self._maximo else ""
        numero = formatar_segundos(valor) + limite
        if self._estado == Estado.TEMPO:
            return f"Tempo apertado: {numero}"
        if self._linha.primeiro:
            return f"Começa em {numero} (a partir do início da automação)"
        if valor < 0:
            return f"Espera antes deste comando: {numero} (começa {formatar_segundos(-valor)} antes do fim do anterior)"
        return f"Espera antes deste comando: {numero} (depois do fim do anterior)"

    def _mudou(self) -> bool:
        """O valor de agora é diferente do de quando a edição abriu? Voltar ao valor do início (já no milissegundo) vale como não mudar."""
        return self._valor != self._inicial and self._valor != round(self._inicial, _CASAS)

    def _atualizar(self, agora: float) -> bool:
        """Leva o valor ao que a curva dá no instante `agora`, se há uma seta apertada. Diz se o valor mudou."""
        if not self._seta:
            return False
        sentido = -1 if self._seta == "LEFT" else 1
        novo = valor_apos(self._base, sentido, max(0.0, agora - self._t_seta), self._minimo, self._maximo)
        mudou = novo != self._valor
        self._valor = novo
        return mudou

    def _ajuste(self, tecla: Tecla, nome: str, simples: bool, agora: float) -> Resposta:
        if nome == "ESC" and simples:
            return self._cancelar()
        if nome == "ENTER" and simples:
            return self._aceitar(agora)
        if nome in ("LEFT", "RIGHT") and simples:
            return self._apertar_seta(nome, agora)
        if tecla.texto == "'" and not (tecla.ctrl or tecla.alt) and self._estado == Estado.TEMPO:
            return self._do_tempo_para_a_espera()
        return self._engolir(tecla)

    def _apertar_seta(self, nome: str, agora: float) -> Resposta:
        if nome == self._seta:
            return Resposta(True, ())  # a repetição do sistema da mesma seta: a contagem continua a do primeiro aperto
        self._atualizar(agora)  # trocar de direção com a outra apertada: antes, o que a primeira já andou
        self._base, self._seta, self._t_seta = self._valor, nome, agora
        self._valor = valor_apos(self._base, -1 if nome == "LEFT" else 1, 0.0, self._minimo, self._maximo)  # o toque, na hora de apertar
        return Resposta(True, (MostrarValor(self._texto_do_valor()),))

    def _do_tempo_para_a_espera(self) -> Resposta:
        if self._seta or self._mudou():
            return Resposta(True, (Dica(DICA_ACEITE_ANTES),))  # nunca perder nem gravar sem o Enter
        linha = self._linha
        self._entrar_ajuste(Estado.ESPERA, linha.espera, linha.espera_minima, max(TETO, linha.espera))
        return Resposta(True, (MostrarValor(self._texto_do_valor()), Dica(dica_do_estado(Estado.ESPERA, linha))))

    def _aceitar(self, agora: float) -> Resposta:
        self._atualizar(agora)  # com a seta ainda apertada, vale o valor do instante do Enter
        linha = self._linha
        if self._mudou():
            aplicar = AplicarTempo if self._estado == Estado.TEMPO else AplicarEspera
            efeitos = (aplicar(linha.indice, self._valor), Desmarcar())
        else:
            efeitos = (Desmarcar(),)
        self._limpar()
        return Resposta(True, efeitos)

    def soltar(self, nome: str, agora: float) -> Resposta:
        """Uma tecla foi solta. Só interessa a seta que está contando: o valor vai ao que a curva dá no instante da soltura."""
        if self._estado not in (Estado.TEMPO, Estado.ESPERA) or nome.upper() != self._seta:
            return _NADA
        mudou = self._atualizar(agora)
        self._seta = ""
        return Resposta(True, (MostrarValor(self._texto_do_valor()),) if mudou else ())

    def tique(self, agora: float) -> Resposta:
        """A janela chama isto umas 30 vezes por segundo enquanto há uma seta apertada: a rampa anda sem depender da repetição do sistema."""
        if self._estado in (Estado.TEMPO, Estado.ESPERA) and self._atualizar(agora):
            return Resposta(False, (MostrarValor(self._texto_do_valor()),))
        return _NADA

    # ---- o que vale em todos os estados ------------------------------------------------------------------------------------
    @staticmethod
    def _engolir(tecla: Tecla) -> Resposta:
        """Dentro de um ajuste, a tecla que o controlador não usa é consumida sem efeito; Ctrl e Alt seguem para os atalhos da janela."""
        return _NADA if (tecla.ctrl or tecla.alt) else Resposta(True, ())

    def _aplicar_alvo(self, valor: str, igual: bool) -> Resposta:
        linha = self._linha
        efeitos = (Desmarcar(),) if igual else (AplicarAlvo(linha.indice, valor), Desmarcar())
        self._limpar()
        return Resposta(True, efeitos)

    def _cancelar(self) -> Resposta:
        self._limpar()
        return Resposta(True, (Cancelar(),))

    def descartar(self) -> Resposta:
        """O que estava em edição já não vale: o foco saiu da janela, a linha mudou, o mapa mudou por outro caminho (desfazer...)."""
        em_edicao = self._estado != Estado.NAVEGANDO
        self._limpar()
        return Resposta(False, (Cancelar(),) if em_edicao else ())
