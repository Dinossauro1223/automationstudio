"""Ativação por mapa (25.8): quais automações respondem à tecla, e por quê.

Lógica pura: sem Qt e sem leitura de disco. Recebe os mapas (nome -> tecla), o estado de cada um e os atalhos de controle, e
devolve um PLANO: quais teclas registrar, para qual ação, e quem ficou sem a tecla (e por quê). A janela só executa o plano
(`registrar_plano`). Especificação: md/ESPEC_ATIVACAO_25_8.md.

Três estados, exclusivos:
    sessao      a tecla funciona agora; ao reabrir o programa o mapa volta desativado (nunca é gravado);
    sempre      a tecla funciona agora e em toda abertura;
    desativado  a tecla não inicia o mapa (o botão ▶ Executar e a "próxima automação" continuam funcionando).
Só `sempre` e `desativado` são gravados: é a PREFERÊNCIA, no banco de configurações (AppSettings), por nome de mapa. O formato
do mapa não muda.

Regras de tecla:
    * só mapas ATIVOS e atalhos de controle ocupam teclas; um mapa desativado nunca conflita;
    * os atalhos de controle têm prioridade e a parada de emergência vem primeiro: um mapa nunca a engole;
    * ativar um mapa, ou mudar a tecla de um mapa ativo, para uma tecla ocupada é RECUSADO, e quem já usa a tecla nunca a perde
      para quem chega depois (mesmo que o nome de quem chega venha antes na ordem alfabética);
    * dados antigos com a mesma tecla em dois mapas ativos: o primeiro pelo nome, como até a 25.6, fica com a tecla; o outro
      continua ativo, sem a tecla, e a situação aparece na tela.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .core import parse_combo

ESTADO_SESSAO = "sessao"
ESTADO_SEMPRE = "sempre"
ESTADO_DESATIVADO = "desativado"
ESTADOS = (ESTADO_SESSAO, ESTADO_SEMPRE, ESTADO_DESATIVADO)
PREFERENCIAS = (ESTADO_SEMPRE, ESTADO_DESATIVADO)  # o que pode ser gravado

ROTULOS = {
    ESTADO_SESSAO: "Ativo nesta sessão",
    ESTADO_SEMPRE: "Sempre ativo ao iniciar",
    ESTADO_DESATIVADO: "Desativado",
}
AJUDAS = {
    ESTADO_SESSAO: "A tecla funciona agora. Quando o programa for aberto de novo, esta automação começa desativada.",
    ESTADO_SEMPRE: "A tecla funciona agora e toda vez que o programa for aberto.",
    ESTADO_DESATIVADO: "A tecla não inicia esta automação. O botão ▶ Executar continua funcionando.",
}
AVISO_DE_SEMPRE_PARA_SESSAO = "Na próxima abertura do programa esta automação ficará desativada."

# Os atalhos de controle, na ordem de prioridade: a parada de emergência primeiro.
ORDEM_CONTROLE = ("emergency", "pause", "resume", "record_toggle", "record_cancel")
# A ação que a janela entende (`MainWindow._on_hotkey_triggered`) para cada atalho de controle.
ACAO_DO_CONTROLE = {
    "emergency": "control:emergency", "pause": "control:pause", "resume": "control:resume",
    "record_toggle": "record:toggle", "record_cancel": "record:cancel",
}
ROTULOS_CONTROLE = {
    "emergency": "Parar tudo agora", "pause": "Pausar automação", "resume": "Continuar automação",
    "record_toggle": "Iniciar/finalizar gravação", "record_cancel": "Cancelar gravação",
}

_MINUSCULAS_ASCII = {ord(letra): ord(letra) + 32 for letra in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}


def ordem_dos_nomes(nome: str) -> tuple[str, str]:
    """Chave de ordenação igual à do banco (`ORDER BY name COLLATE NOCASE`): só as letras A-Z são igualadas às minúsculas.

    É a ordem em que os mapas chegam à janela e, portanto, a ordem em que, até a 25.6, o primeiro mapa a registrar levava a
    tecla repetida. O nome inteiro desempata (dois nomes que só diferem na caixa)."""
    return nome.translate(_MINUSCULAS_ASCII), nome


def tecla_valida(tecla: Any) -> bool:
    """Texto que vira uma combinação de teclas (`parse_combo`). Vazio, só espaços, só "+" e o que não é texto não valem."""
    if not isinstance(tecla, str) or not tecla.strip():
        return False
    try:
        parse_combo(tecla.strip())
    except ValueError:
        return False
    return True


# ------------------------------------------------------------------------------------------------ mensagens
def _mensagem_de_conflito(tecla: str, perdedor: str, perdedor_e_mapa: bool, vencedor: str, vencedor_e_mapa: bool) -> str:
    if perdedor_e_mapa and vencedor_e_mapa:
        return f"A tecla “{tecla}” de “{perdedor}” já é usada pela automação ativa “{vencedor}”."
    if perdedor_e_mapa:
        return f"A tecla “{tecla}” de “{perdedor}” é a do atalho de controle “{vencedor}”."
    return f"Os atalhos de controle “{perdedor}” e “{vencedor}” usam a mesma tecla “{tecla}”; só “{vencedor}” foi ativado."


def _mensagem_de_invalido(nome: str, tecla: str, e_mapa: bool) -> str:
    if e_mapa:
        return f"A tecla “{tecla}” de “{nome}” não é válida; a automação ficou sem atalho."
    return f"O atalho de controle “{nome}” tem uma tecla inválida (“{tecla}”) e não foi ativado."


def _continua(nome: str, atual: Any) -> str:
    texto = atual.strip() if isinstance(atual, str) else ""
    return f" A tecla de “{nome}” continua “{texto}”." if texto else ""


def recusa_de_ativacao(conflito: "Conflito") -> str:
    """O que mostrar quando alguém pede para ATIVAR um mapa cuja tecla está ocupada."""
    if conflito.vencedor_e_mapa:
        return f"{conflito.mensagem} Desative “{conflito.vencedor}” ou mude uma das teclas em ⚙ Configurações da automação."
    return f"{conflito.mensagem} Mude a tecla de “{conflito.perdedor}” em ⚙ Configurações da automação."


def recusa_de_tecla(conflito: "Conflito", atual: Any) -> str:
    """O que mostrar quando alguém pede uma tecla ocupada para um mapa ativo (a tecla `atual` é mantida)."""
    sugestao = f"Escolha outra tecla ou desative “{conflito.vencedor}”." if conflito.vencedor_e_mapa else "Escolha outra tecla."
    return f"{conflito.mensagem}{_continua(conflito.perdedor, atual)} {sugestao}"


def recusa_de_tecla_invalida(tecla: Any, nome: str, atual: Any) -> str:
    """O que mostrar quando a tecla pedida não existe (vazia, só "+")."""
    texto = tecla.strip() if isinstance(tecla, str) else ""
    primeira = f"A tecla “{texto}” não é válida." if texto else "Nenhuma tecla foi digitada."
    return f"{primeira} Digite uma tecla ou uma combinação, como F6 ou CTRL+F6.{_continua(nome, atual)}"


# ------------------------------------------------------------------------------------------------ o plano
@dataclass(frozen=True)
class Registro:
    """Uma tecla a registrar no gerente de atalhos globais."""
    tecla: str     # como foi escrita (sem espaços nas pontas)
    acao: str      # "map:<nome>", "control:emergency", "record:toggle"...
    nome: str      # nome do mapa ou rótulo do atalho de controle
    e_mapa: bool


@dataclass(frozen=True)
class Conflito:
    """Quem ficou sem a tecla (`perdedor`) e para quem ela ficou (`vencedor`)."""
    tecla: str     # como o perdedor a escreveu
    perdedor: str
    vencedor: str
    perdedor_e_mapa: bool
    vencedor_e_mapa: bool
    mensagem: str


@dataclass(frozen=True)
class Invalido:
    """Um mapa ativo ou atalho de controle cuja tecla não vira uma combinação."""
    nome: str
    tecla: str
    e_mapa: bool
    mensagem: str


@dataclass
class Plano:
    registros: list[Registro] = field(default_factory=list)
    conflitos: list[Conflito] = field(default_factory=list)
    invalidos: list[Invalido] = field(default_factory=list)
    sem_tecla: list[str] = field(default_factory=list)  # mapas ativos sem tecla nenhuma
    _donos: dict = field(default_factory=dict, init=False, repr=False, compare=False)  # combinação -> Registro

    def dono(self, tecla: Any) -> Registro | None:
        """Quem está com `tecla` neste plano (escrita de qualquer jeito equivalente), ou None."""
        if not tecla_valida(tecla):
            return None
        return self._donos.get(parse_combo(tecla.strip()))

    def registro_do_mapa(self, nome: str) -> Registro | None:
        return next((r for r in self.registros if r.e_mapa and r.nome == nome), None)

    def conflito_do_mapa(self, nome: str) -> Conflito | None:
        return next((c for c in self.conflitos if c.perdedor_e_mapa and c.perdedor == nome), None)

    def invalido_do_mapa(self, nome: str) -> Invalido | None:
        return next((i for i in self.invalidos if i.e_mapa and i.nome == nome), None)

    def mensagens(self) -> list[str]:
        """Tudo o que o usuário precisa saber deste plano: conflitos e teclas inválidas."""
        return [c.mensagem for c in self.conflitos] + [i.mensagem for i in self.invalidos]


def _ocupar(plano: Plano, tecla: Any, nome: str, acao: str, e_mapa: bool) -> None:
    texto = tecla.strip() if isinstance(tecla, str) else ""
    if not texto:
        if e_mapa:
            plano.sem_tecla.append(nome)
        return
    try:
        combinacao = parse_combo(texto)
    except ValueError:
        plano.invalidos.append(Invalido(nome, texto, e_mapa, _mensagem_de_invalido(nome, texto, e_mapa)))
        return
    dono = plano._donos.get(combinacao)
    if dono is not None:
        mensagem = _mensagem_de_conflito(texto, nome, e_mapa, dono.nome, dono.e_mapa)
        plano.conflitos.append(Conflito(texto, nome, dono.nome, e_mapa, dono.e_mapa, mensagem))
        return
    registro = Registro(texto, acao, nome, e_mapa)
    plano._donos[combinacao] = registro
    plano.registros.append(registro)


def montar_plano(mapas: Mapping[str, Any], estados: Mapping[str, str], controles: Mapping[str, Any] | None = None) -> Plano:
    """Quem leva cada tecla. `mapas`: nome -> tecla; `estados`: nome -> estado (mapa sem estado conta como desativado);
    `controles`: os atalhos de controle como `AppSettings.get_control_hotkeys()` os devolve.

    Os atalhos de controle entram primeiro, na ordem de ORDEM_CONTROLE. Depois os mapas ativos, na ordem do banco
    (`ordem_dos_nomes`): em dados antigos com a mesma tecla em dois mapas, o primeiro fica com ela."""
    plano = Plano()
    controles = controles or {}
    for chave in ORDEM_CONTROLE:
        _ocupar(plano, controles.get(chave), ROTULOS_CONTROLE[chave], ACAO_DO_CONTROLE[chave], False)
    for nome in sorted(mapas, key=ordem_dos_nomes):
        if estados.get(nome) in (ESTADO_SESSAO, ESTADO_SEMPRE):
            _ocupar(plano, mapas[nome], nome, f"map:{nome}", True)
    return plano


def registrar_plano(plano: Plano, gerente: Any, criar_callback: Callable[[str], Callable[[], None]]) -> list[str]:
    """Refaz do zero os atalhos do `gerente` (GlobalHotkeyManager) conforme o plano. Nunca levanta: o que o gerente recusar
    (não deveria, o plano já não tem conflitos) volta como texto. `criar_callback(acao)` devolve o callback da ação."""
    gerente.clear()
    erros: list[str] = []
    for registro in plano.registros:
        try:
            gerente.register(registro.tecla, criar_callback(registro.acao))
        except (RuntimeError, ValueError) as exc:  # HotkeyConflictError é um RuntimeError
            erros.append(f"Não foi possível ativar a tecla “{registro.tecla}” de “{registro.nome}”: {exc}")
    return erros


# ------------------------------------------------------------------------------------------------ o estado
@dataclass(frozen=True)
class Resultado:
    ok: bool
    mensagem: str = ""  # na recusa, o motivo; no sucesso, um aviso opcional


@dataclass(frozen=True)
class Sincronizacao:
    mudou: bool  # a preferência gravada mudou: é preciso gravar de novo
    avisos: tuple[str, ...] = ()  # mapas que nasceram desativados por conflito


@dataclass(frozen=True)
class Descricao:
    """Tudo o que a tela mostra sobre a ativação de um mapa."""
    nome: str
    estado: str
    rotulo: str                  # "Ativo nesta sessão"
    tecla: str                   # a tecla do mapa ("" se não tem)
    funcionando: bool            # a tecla está registrada e inicia o mapa agora
    conflito: Conflito | None    # perdeu a tecla para outro
    invalido: str                # texto do problema, se a tecla não é válida
    situacao: str                # linha curta: rótulo + o que impede a tecla de funcionar
    resumo: str                  # frase completa, para a faixa e a dica


class AtivacaoMapas:
    """O estado de ativação dos mapas: a preferência gravada e o que vale só nesta sessão. Não lê nem grava nada: quem usa
    pega `dados()` e grava onde quiser (a janela usa o AppSettings)."""

    def __init__(self, dados: Any = None) -> None:
        self._migrado = False
        self._prefs: dict[str, str] = {}
        self._sessao: set[str] = set()
        # Leitor tolerante: o que não for do formato esperado é ignorado (o programa nunca deixa de abrir por isto).
        if isinstance(dados, Mapping):
            self._migrado = dados.get("migrated") is True
            prefs = dados.get("prefs")
            if isinstance(prefs, Mapping):
                for nome, valor in prefs.items():
                    if isinstance(nome, str) and nome and valor in PREFERENCIAS:
                        self._prefs[nome] = valor

    def dados(self) -> dict[str, Any]:
        """O que vai para o banco: só `sempre` e `desativado`. "Ativo nesta sessão" nunca é gravado."""
        return {"migrated": self._migrado, "prefs": dict(self._prefs)}

    def estado(self, nome: str) -> str:
        if self._prefs.get(nome) == ESTADO_SEMPRE:
            return ESTADO_SEMPRE
        if nome in self._sessao:
            return ESTADO_SESSAO
        return ESTADO_DESATIVADO

    def esta_ativo(self, nome: str) -> bool:
        return self.estado(nome) != ESTADO_DESATIVADO

    def estados(self, nomes) -> dict[str, str]:
        return {nome: self.estado(nome) for nome in nomes}

    def plano(self, mapas: Mapping[str, Any], controles: Mapping[str, Any] | None = None) -> Plano:
        return montar_plano(mapas, self.estados(mapas), controles)

    def sincronizar(self, mapas: Mapping[str, Any], controles: Mapping[str, Any] | None = None) -> Sincronizacao:
        """Alinha o estado com os mapas que existem agora. NÃO apaga a preferência de um mapa que não veio nesta lista (um
        mapa que não carregou desta vez continua no banco): quem exclui um mapa chama `esquecer`.

        Primeira abertura da 25.8 (nada gravado ainda): todo mapa existente vira "sempre", que é o que valia até a 25.6.
        Depois disso, um mapa que ainda não tem preferência é NOVO: nasce "ativo nesta sessão" (preferência gravada:
        desativado), ou desativado se a tecla dele já for de um mapa ativo ou de um atalho de controle."""
        mudou, avisos = False, []
        if not self._migrado:
            for nome in mapas:
                self._prefs.setdefault(nome, ESTADO_SEMPRE)
            self._migrado = True
            mudou = True
        for nome in sorted((n for n in mapas if n not in self._prefs), key=ordem_dos_nomes):
            mudou = True
            self._prefs[nome] = ESTADO_DESATIVADO
            conflito = self.verificar_tecla(nome, mapas[nome], mapas, controles)
            if conflito is None:
                self._sessao.add(nome)
            else:
                avisos.append(f"{conflito.mensagem} Por isso “{nome}” começou desativada.")
        return Sincronizacao(mudou, tuple(avisos))

    def definir(self, nome: str, novo: str, mapas: Mapping[str, Any], controles: Mapping[str, Any] | None = None) -> Resultado:
        """Muda o estado de `nome`. Ativar um mapa desativado exige que a tecla dele esteja livre; senão é recusado e nada
        muda. De "sempre" para "só nesta sessão" a preferência gravada vira "desativado" (os estados são exclusivos) e o
        resultado traz o aviso."""
        if novo not in ESTADOS:
            raise ValueError(f"estado de ativação desconhecido: {novo!r}")
        atual = self.estado(nome)
        if novo == atual:
            return Resultado(True)
        if atual == ESTADO_DESATIVADO:  # passa a valer a tecla: ninguém mais pode estar com ela
            conflito = self.verificar_tecla(nome, mapas.get(nome), mapas, controles)
            if conflito is not None:
                return Resultado(False, recusa_de_ativacao(conflito))
        aviso = ""
        if novo == ESTADO_SESSAO:
            if self._prefs.get(nome) == ESTADO_SEMPRE:
                aviso = AVISO_DE_SEMPRE_PARA_SESSAO
            self._prefs[nome] = ESTADO_DESATIVADO
            self._sessao.add(nome)
        else:
            self._prefs[nome] = novo
            self._sessao.discard(nome)
        return Resultado(True, aviso)

    def verificar_tecla(self, nome: str, tecla: Any, mapas: Mapping[str, Any],
                        controles: Mapping[str, Any] | None = None) -> Conflito | None:
        """O conflito que `tecla` teria se `nome` a usasse ATIVO, contra os OUTROS mapas ativos e os atalhos de controle; None
        se está livre (ou se a tecla é vazia ou inválida: isso não é conflito). Quem já usa a tecla nunca a perde para `nome`."""
        if not tecla_valida(tecla):
            return None
        outros = {n: t for n, t in mapas.items() if n != nome}
        dono = montar_plano(outros, self.estados(outros), controles).dono(tecla)
        if dono is None:
            return None
        texto = tecla.strip()
        return Conflito(texto, nome, dono.nome, True, dono.e_mapa, _mensagem_de_conflito(texto, nome, True, dono.nome, dono.e_mapa))

    def esquecer(self, nome: str) -> bool:
        """Apaga a preferência e o estado de sessão de um mapa excluído. True se havia algo a apagar."""
        havia = nome in self._prefs or nome in self._sessao
        self._prefs.pop(nome, None)
        self._sessao.discard(nome)
        return havia

    def descrever(self, nome: str, mapas: Mapping[str, Any], controles: Mapping[str, Any] | None = None,
                  plano: Plano | None = None) -> Descricao:
        plano = plano if plano is not None else self.plano(mapas, controles)
        estado = self.estado(nome)
        rotulo = ROTULOS[estado]
        bruta = mapas.get(nome)
        tecla = bruta.strip() if isinstance(bruta, str) else ""
        if estado == ESTADO_DESATIVADO:
            if tecla:
                resumo = f"A tecla “{tecla}” não inicia esta automação. O botão ▶ Executar continua funcionando."
            else:
                resumo = "Sem tecla definida. O botão ▶ Executar continua funcionando."
            return Descricao(nome, estado, rotulo, tecla, False, None, "", rotulo, resumo)
        if plano.registro_do_mapa(nome) is not None:
            return Descricao(nome, estado, rotulo, tecla, True, None, "", rotulo, f"A tecla “{tecla}” inicia e para esta automação.")
        conflito = plano.conflito_do_mapa(nome)
        if conflito is not None:
            resumo = f"{conflito.mensagem} Esta automação continua ativa, mas sem a tecla enquanto o conflito durar."
            return Descricao(nome, estado, rotulo, tecla, False, conflito, "", f"{rotulo} (sem a tecla: conflito)", resumo)
        invalido = plano.invalido_do_mapa(nome)
        if invalido is not None:
            return Descricao(nome, estado, rotulo, tecla, False, None, invalido.mensagem, f"{rotulo} (tecla inválida)", invalido.mensagem)
        resumo = "Não há tecla para iniciar esta automação. Defina uma em ⚙ Configurações da automação."
        return Descricao(nome, estado, rotulo, tecla, False, None, "", f"{rotulo} (sem tecla)", resumo)
