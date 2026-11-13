"""O passo a passo (função F52): executar a automação um comando por vez, para testar e consertar sem rodar tudo de novo.

Como funciona, do ponto de vista de quem usa:
    * "Executar passo a passo" (menu do editor) começa a execução PARADA, antes do primeiro comando;
    * "Próximo passo" executa o próximo comando e para de novo antes do seguinte. A espera PLANEJADA entre os comandos (o
      intervalo entre um comando e o seguinte na linha do tempo) não é cumprida: quem escolhe a hora do próximo passo é você.
      As esperas que fazem parte do próprio comando continuam valendo e acontecem quando o passo roda: o comando "Esperar", as
      condições de um comando (atraso, imagem, aplicativo pronto) e o aguardo do aplicativo que acabou de abrir;
    * "Continuar sem parar" termina a automação de uma vez, na velocidade de sempre; "Parar" encerra tudo;
    * é uma volta só: a repetição e o encadeamento da automação não valem no passo a passo;
    * a automação do usuário não muda: o passo a passo roda uma CÓPIA dela.

Como funciona por dentro: o motor (`ExecutionEngine`) tem um gancho, `passo_a_passo`, que é None na execução normal. Com um
`PassoAPasso` ali, o motor pergunta, antes do primeiro evento de cada comando, se deve parar (`parar_antes`) e então usa a
pausa que já existe: o estado vira PAUSED, `resume()` é o "próximo passo" e `stop()` encerra. `ControleDePassos` é o que a
janela chama (começar, próximo, continuar, parar). Este módulo não importa o Qt; a janelinha de controle e a ligação com a
janela principal estão em passo_a_passo_ui.py.
"""
from __future__ import annotations

import copy

from .conditions import WaitConditionType
from .core import (ActionType, AutomationMap, Command, InputType, State, _append_runtime_log, _next_id, build_timeline)

PREFIXO_DO_NOME = "__passo__ "  # o nome da cópia que roda (como o "__teste__" de testar selecionados): nunca é uma automação do usuário
MOTIVO_EM_EXECUCAO = "Pare a automação em execução antes de usar o passo a passo."
MOTIVO_GRAVANDO = "Termine ou cancele a gravação antes de usar o passo a passo."
MOTIVO_OCUPADO = "O programa ainda está terminando o que fazia. Tente de novo em um instante."
MOTIVO_SEM_COMANDOS = "Não há nenhum comando ativo para executar passo a passo."
TAMANHO_DO_TEXTO = 40  # quanto de um texto digitado aparece na descrição do passo

_BOTOES_DO_MOUSE = {"left": "esquerdo", "right": "direito", "middle": "do meio", "x1": "lateral 1", "x2": "lateral 2"}


def _numero(valor) -> str:
    """2.0 vira "2" e 1.5 vira "1,5" (vírgula, como o usuário escreve)."""
    return f"{float(valor):g}".replace(".", ",")


def _o_que_faz(cmd: Command) -> str:
    tipo, acao, alvo = cmd.type, cmd.action, str(cmd.target or "")
    if tipo == InputType.KEY:
        if acao == ActionType.PRESS:
            return f"Segurar a tecla {alvo}"
        if acao == ActionType.RELEASE:
            return f"Soltar a tecla {alvo}"
        return f"Apertar e soltar a tecla {alvo}"
    if tipo == InputType.MOUSE_BUTTON:
        botao = _BOTOES_DO_MOUSE.get(alvo.lower(), alvo)
        if acao == ActionType.PRESS:
            return f"Segurar o botão {botao} do mouse"
        if acao == ActionType.RELEASE:
            return f"Soltar o botão {botao} do mouse"
        return f"Clicar com o botão {botao} do mouse"
    if tipo == InputType.MOUSE_MOVE:
        if cmd.merged_move and cmd.mouse_path:
            return "Mover o mouse seguindo o percurso gravado"
        x, y = (cmd.x if cmd.x is not None else 0), (cmd.y if cmd.y is not None else 0)
        if cmd.relative:
            return f"Mover o mouse ({x}, {y}) a partir de onde ele está"
        return f"Mover o mouse para ({x}, {y})"
    if tipo == InputType.MOUSE_SCROLL:
        return f"Rolar a roda do mouse (horizontal {cmd.scroll_dx}, vertical {cmd.scroll_dy})"
    if tipo == InputType.TEXT:
        texto = " ".join(str(cmd.text or "").split())
        if len(texto) > TAMANHO_DO_TEXTO:
            texto = texto[:TAMANHO_DO_TEXTO] + "…"
        return f'Digitar "{texto}"'
    if tipo == InputType.APP_OPEN:
        return f"Abrir o aplicativo {alvo}"
    if tipo == InputType.WAIT:
        return _descrever_espera(cmd)
    return str(getattr(tipo, "value", tipo))


def _descrever_espera(cmd: Command) -> str:
    """O comando "Esperar" é feito só de condições (atraso, imagem, aplicativo pronto). No passo a passo elas valem: a espera
    acontece quando o passo roda, e a janelinha diz qual é."""
    partes = []
    for condicao in getattr(cmd, "conditions", None) or []:
        if condicao.type == WaitConditionType.DELAY:
            partes.append(f"esperar {_numero(condicao.timeout or condicao.after or 0.0)} s")
        elif condicao.type == WaitConditionType.IMAGE:
            partes.append("esperar uma imagem aparecer na tela")
        elif condicao.type == WaitConditionType.PROCESS:
            alvo = str(condicao.target or "").strip()
            partes.append(f"esperar o aplicativo {alvo} ficar pronto" if alvo else "esperar o aplicativo ficar pronto")
    if not partes:
        return "Esperar"
    texto = ", depois ".join(partes)
    return texto[0].upper() + texto[1:]


def descrever_comando(cmd: Command) -> str:
    """O que o comando faz, em palavras simples, para a janelinha do passo a passo. Se o usuário escreveu uma descrição para o
    comando, ela vai entre parênteses no fim."""
    base = _o_que_faz(cmd)
    nota = str(getattr(cmd, "description", "") or "").strip()
    return f"{base} ({nota})" if nota and nota != base else base


def ids_a_partir_daqui(comandos, ids) -> list[str]:
    """Os ids dos comandos do passo a passo: do primeiro de `ids` (na ordem da LISTA, que é a sequência da automação) até o fim,
    sem os desativados (a execução os ignora de qualquer jeito). Sem `ids` (nada selecionado) é a automação inteira. Vazio se
    nenhum de `ids` está na lista."""
    comandos = list(comandos)
    ids = {str(i) for i in (ids or ())}
    inicio = 0
    if ids:
        inicio = next((posicao for posicao, cmd in enumerate(comandos) if cmd.id in ids), None)
        if inicio is None:
            return []
    return [cmd.id for cmd in comandos[inicio:] if getattr(cmd, "enabled", True)]


def montar_mapa_de_passos(mapa: AutomationMap, ids=()) -> AutomationMap | None:
    """A cópia da automação que o passo a passo executa: só os comandos de `ids_a_partir_daqui`, com ids novos, começando em
    t=0, uma volta só e sem encadear outra automação. Nunca mexe em `mapa`. None se não sobra nenhum comando."""
    escolhidos = mapa.get_commands_by_ids(ids_a_partir_daqui(mapa.commands, ids))
    if not escolhidos:
        return None
    copia = AutomationMap(name=f"{PREFIXO_DO_NOME}{mapa.name}", hotkey=None, repeat_count=1, speed=mapa.speed)
    base = min(float(cmd.start) for cmd in escolhidos)
    copia.commands = [copy.deepcopy(cmd) for cmd in escolhidos]
    for cmd in copia.commands:
        cmd.id = _next_id()
        cmd.start = max(0.0, float(cmd.start) - base)
    return copia


def _ids_na_ordem_do_motor(eventos) -> list[str]:
    """Os ids dos comandos na ordem em que o motor chega ao primeiro evento de cada um."""
    vistos: dict[str, None] = {}
    for evento in eventos:
        vistos.setdefault(evento.command_id, None)
    return list(vistos)


class PassoAPasso:
    """Uma sessão de passo a passo: o que o motor consulta (`parar_antes`) e o que a janela mostra (`texto_do_passo`).

    Um passo é um comando: o motor para antes do primeiro evento de cada comando. Os eventos que só terminam um comando já
    começado (soltar a tecla que está segurada) acontecem no tempo planejado, no caminho até o próximo passo.
    `parar_antes` roda na thread do motor; `numero`, `comando_id` e `ativo` são lidos pela janela depois que o motor
    ficou parado (o aviso de estado chega só depois), então não precisam de trava."""

    def __init__(self, mapa: AutomationMap) -> None:
        self.mapa = mapa
        self.ativo = True
        self.ordem = _ids_na_ordem_do_motor(build_timeline(mapa))
        self.total = len(self.ordem)
        self._descricoes = {cmd.id: descrever_comando(cmd) for cmd in mapa.commands}
        self._vistos: set[str] = set()
        self.numero = 0       # o passo em que a execução está parada (1 a total); 0 enquanto não chegou ao primeiro
        self.comando_id = ""  # o comando desse passo

    def parar_antes(self, evento, mapa_em_execucao) -> bool:
        """Chamada pelo motor antes de cada evento. True se é o primeiro evento de um comando que ainda não teve a sua vez.
        Só vale para a execução da cópia que esta sessão criou, e só enquanto ativa."""
        if not self.ativo or mapa_em_execucao is not self.mapa:
            return False
        comando = evento.command_id
        if comando in self._vistos:
            return False
        self._vistos.add(comando)
        self.comando_id = comando
        self.numero = len(self._vistos)
        return True

    def descricao(self) -> str:
        return self._descricoes.get(self.comando_id, "")

    def texto_do_passo(self) -> str:
        return f"Passo {self.numero} de {self.total}: {self.descricao()}"


class ControleDePassos:
    """O que a janela chama: começa o passo a passo e responde aos botões. Fala com o motor só pela API pública (`run`,
    `resume`, `stop`, `state`) e pelo gancho `passo_a_passo`."""

    def __init__(self, motor, registrar=None) -> None:
        self.motor = motor
        self._registrar = registrar if registrar is not None else _append_runtime_log
        self.sessao: PassoAPasso | None = None

    def iniciar(self, mapa: AutomationMap, ids=()) -> str:
        """Começa o passo a passo de `mapa` (do primeiro de `ids` até o fim; sem `ids`, a automação inteira). Devolve "" se
        começou; senão, o motivo, em palavras para o usuário."""
        estado = self.motor.state.state
        if estado in (State.RUNNING, State.PAUSED):
            return MOTIVO_EM_EXECUCAO
        if estado == State.RECORDING:
            return MOTIVO_GRAVANDO
        if estado != State.IDLE:  # parando ou com erro, por um instante
            return MOTIVO_OCUPADO
        copia = montar_mapa_de_passos(mapa, ids)
        if copia is None:
            return MOTIVO_SEM_COMANDOS
        sessao = PassoAPasso(copia)
        if sessao.total == 0:
            return MOTIVO_SEM_COMANDOS
        erros = copia.validate()
        if erros:
            return "A automação não pode ser executada:\n" + "\n".join(erros)
        self.motor.passo_a_passo = sessao
        self.sessao = sessao
        try:
            self.motor.run(copia)
        except Exception as erro:  # noqa: BLE001 - mapa inválido (ValueError) ou motor ocupado (gravando)
            self._soltar()
            return f"Não foi possível começar o passo a passo: {erro}"
        self._registrar(f"PASSO A PASSO iniciado mapa={mapa.name} passos={sessao.total}")
        return ""

    def parado_num_passo(self) -> bool:
        """True se a execução está parada esperando o "próximo passo"."""
        sessao = self.sessao
        return sessao is not None and sessao.ativo and sessao.numero > 0 and self.motor.state.state == State.PAUSED

    def proximo(self) -> bool:
        """O botão "Próximo passo": executa o próximo comando. False (e nada acontece) se não há passo esperando: o motor
        está no meio de um passo, ou o passo a passo acabou."""
        if not self.parado_num_passo():
            return False
        self.motor.resume()
        return True

    def continuar_sem_parar(self) -> bool:
        """O botão "Continuar sem parar": o resto da automação roda de uma vez, na velocidade de sempre."""
        sessao = self.sessao
        if sessao is None or not sessao.ativo:
            return False
        sessao.ativo = False
        self._registrar(f"PASSO A PASSO continuar sem parar no passo={sessao.numero} de {sessao.total}")
        if self.motor.state.state == State.PAUSED:
            self.motor.resume()
        return True

    def parar(self) -> None:
        """O botão "Parar": encerra a automação (o mesmo que o ■ Parar da barra)."""
        self.motor.stop()

    def ao_ficar_pausado(self) -> bool:
        """A janela chama quando o motor ficou PAUSED. Se o usuário já tinha escolhido "Continuar sem parar" um instante antes
        de o motor parar, libera o motor de novo e devolve True (nada para mostrar). Senão devolve False."""
        sessao = self.sessao
        if sessao is not None and not sessao.ativo and self.motor.state.state == State.PAUSED:
            self.motor.resume()
            return True
        return False

    def terminou(self) -> None:
        """A janela chama quando o motor voltou a IDLE (fim natural, parada ou erro): solta o gancho."""
        sessao = self.sessao
        if sessao is not None:
            self._registrar(f"PASSO A PASSO encerrado no passo={sessao.numero} de {sessao.total}")
        self._soltar()

    def texto(self) -> str:
        """O que a janelinha mostra agora."""
        sessao = self.sessao
        if sessao is None:
            return ""
        if self.parado_num_passo():
            return sessao.texto_do_passo()
        if not sessao.ativo:
            return "Continuando sem parar..."
        if sessao.numero == 0:
            return "Começando..."
        return f"Executando o passo {sessao.numero} de {sessao.total}..."

    def _soltar(self) -> None:
        if self.motor.passo_a_passo is self.sessao:
            self.motor.passo_a_passo = None
        self.sessao = None
