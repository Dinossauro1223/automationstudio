"""Diagnóstico de travamento dos testes de janela (Qt): o que registrar quando um teste NÃO termina.

Por que existe: na rodada de 18/10/2026 (Windows, Python 3.14, PySide6 de verdade) um teste da janela principal ficou
parado dentro de `QApplication.processEvents()` por 180 s; o pytest-timeout matou o processo e a rodada acabou sem dizer
o que o Qt estava fazendo (a thread principal estava em código nativo: a pilha do Python só mostrava a linha do teste).
Este módulo faz o PRÓXIMO travamento deixar provas em `logs/travamento_qt.txt`:

    AnelDeEventos       os últimos eventos que o Qt entregou (receptor, tipo, nome), mais contadores. Alimentado por um
                        filtro de eventos da QApplication (Qt, na thread principal). Diz se o processo está BLOQUEADO
                        (nenhum evento passa) ou num LAÇO (eventos passam sem parar, algo se reativa) e quem é o culpado.
    RegistroDeMensagens as mensagens que o próprio Qt imprime (qWarning, qCritical...), que o pytest só mostra no fim
                        de um teste que terminou. Alimentado por `qInstallMessageHandler` (Qt).
    Vigia               uma thread que, passado o limite do teste, grava o relatório e encerra o processo com o código
                        86 (o lançador reconhece). Mais um alarme NATIVO (faulthandler) que ainda dispara se a thread
                        do Python não conseguir rodar (por exemplo, GIL preso numa chamada nativa).
    montar_relatorio    o texto do relatório: função pura, testada sem Qt.

Regra de ouro: NADA aqui pode derrubar um teste. Toda chamada ao Qt está protegida, e a thread do vigia nunca chama o Qt
(só lê estruturas do Python): chamar o Qt fora da thread da interface pode travar ou derrubar o processo.
"""
from __future__ import annotations

import collections
import datetime
import faulthandler
import os
import pathlib
import platform
import sys
import threading
import time
import traceback

CODIGO_DE_TRAVAMENTO = 86          # código de saída do processo encerrado pelo vigia
ARQUIVO_DO_RELATORIO = "travamento_qt.txt"
ARQUIVO_DO_ALARME_NATIVO = "travamento_qt_nativo.txt"   # só existe se o alarme NATIVO disparou (ver Vigia)
LIMITE_PADRAO_S = 60.0             # um teste de janela normal leva menos de 3 s; 60 s é folga para máquina lenta
FOLGA_DO_ALARME_NATIVO_S = 15.0    # o alarme nativo dispara esta folga DEPOIS do vigia do Python
TIPO_DE_MARCO = -1                 # "tipo de evento" dos marcos que os testes anotam no anel (não é um evento do Qt)
MARCA_DO_TESTE = "TESTE: "         # linha do relatório que o lançador lê para saber QUAL teste travou
MARCA_DE_FIM = "FIM DO RELATORIO"


def inteiro_do_enum(valor) -> int:
    """Os enums do PySide6 são IntEnum numa versão e Enum simples em outra: aceita os dois."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return int(getattr(valor, "value", -1))


# ------------------------------------------------------------------------------------------------ eventos
class AnelDeEventos:
    """Os últimos `capacidade` eventos entregues e a contagem de todos, por (receptor, tipo).

    Só a thread da interface escreve; o vigia só lê (e `list(deque)` é uma operação única sob o GIL)."""

    def __init__(self, capacidade: int = 500, relogio=time.monotonic) -> None:
        self._itens: collections.deque = collections.deque(maxlen=capacidade)
        self._totais: collections.Counter = collections.Counter()
        self._relogio = relogio
        self.total = 0
        self.ultimo: float | None = None

    def registrar(self, receptor: str, tipo: int, nome: str = "") -> None:
        agora = self._relogio()
        self._itens.append((agora, receptor, nome, tipo))
        self._totais[(receptor, tipo)] += 1
        self.total += 1
        self.ultimo = agora

    def marcar(self, texto: str) -> None:
        """Um marco do teste ("antes do show()"), no meio dos eventos. Não conta como evento do Qt."""
        self._itens.append((self._relogio(), "<marco>", texto, TIPO_DE_MARCO))

    def ultimos(self, quantos: int = 60) -> list[tuple]:
        return list(self._itens)[-quantos:]

    def mais_frequentes(self, agora: float, janela_s: float = 5.0, topo: int = 8) -> list[tuple[tuple[str, int], int]]:
        recentes = collections.Counter((receptor, tipo) for (instante, receptor, _nome, tipo) in list(self._itens)
                                       if tipo != TIPO_DE_MARCO and agora - instante <= janela_s)
        return recentes.most_common(topo)

    def totais(self, topo: int = 12) -> list[tuple[tuple[str, int], int]]:
        return self._totais.most_common(topo)

    def silencio_s(self, agora: float) -> float | None:
        """Há quantos segundos o Qt não entrega NENHUM evento (None: nunca entregou)."""
        return None if self.ultimo is None else max(0.0, agora - self.ultimo)


class RegistroDeMensagens:
    """As últimas mensagens que o Qt imprimiu (nível, texto)."""

    def __init__(self, capacidade: int = 200, relogio=time.monotonic) -> None:
        self._itens: collections.deque = collections.deque(maxlen=capacidade)
        self._relogio = relogio

    def registrar(self, nivel: str, texto: str) -> None:
        self._itens.append((self._relogio(), str(nivel), str(texto)))

    def ultimas(self, quantas: int = 40) -> list[tuple]:
        return list(self._itens)[-quantas:]


# ------------------------------------------------------------------------------------------------ relatório
def pilhas_das_threads() -> str:
    """A pilha do Python de TODAS as threads (a principal marcada). Só lê o interpretador: não chama o Qt."""
    nomes = {thread.ident: thread.name for thread in threading.enumerate()}
    principal = threading.main_thread().ident
    partes = []
    for ident, quadro in sorted(sys._current_frames().items()):
        etiqueta = " [PRINCIPAL]" if ident == principal else (" [o vigia]" if nomes.get(ident) == "vigia-de-travamento" else "")
        partes.append(f"--- thread {nomes.get(ident, '?')} (id {ident}){etiqueta}")
        partes.append("".join(traceback.format_stack(quadro)).rstrip())
    return "\n".join(partes)


def descrever_ambiente() -> str:
    """Versões e plataforma. Chamado na thread da interface, no começo do teste (nunca pelo vigia)."""
    linhas = [f"Python {sys.version.split()[0]} em {platform.platform()}", f"processo {os.getpid()}"]
    for nome in ("PySide6", "shiboken6"):
        modulo = sys.modules.get(nome)
        if modulo is not None:
            linhas.append(f"{nome} {getattr(modulo, '__version__', '?')}"
                          + (" (dublê de testes)" if getattr(modulo, "__as_stub__", False) else ""))
    try:
        qtcore = sys.modules.get("PySide6.QtCore")
        if qtcore is not None and hasattr(qtcore, "qVersion"):
            linhas.append(f"Qt {qtcore.qVersion()}")
        qtgui = sys.modules.get("PySide6.QtGui")
        if qtgui is not None and hasattr(qtgui, "QGuiApplication") and hasattr(qtgui.QGuiApplication, "platformName"):
            linhas.append(f"plataforma do Qt: {qtgui.QGuiApplication.platformName()}")
    except Exception as exc:  # noqa: BLE001
        linhas.append(f"(não consegui ler a versão do Qt: {type(exc).__name__}: {exc})")
    linhas.append("QT_QPA_PLATFORM=" + os.environ.get("QT_QPA_PLATFORM", "(não definida)"))
    return "\n".join(linhas)


def _evento_em_texto(registro: tuple, agora: float, nome_do_tipo) -> str:
    instante, receptor, nome, tipo = registro
    rotulo = "marco" if tipo == TIPO_DE_MARCO else nome_do_tipo(tipo)
    complemento = f" '{nome}'" if nome else ""
    return f"  {instante - agora:+9.3f} s  {receptor}{complemento}  {rotulo}"


def diagnosticar(anel: AnelDeEventos | None, agora: float, silencio_minimo_s: float = 3.0) -> str:
    """Uma frase: o processo está BLOQUEADO, em LAÇO ou não sabemos."""
    if anel is None:
        return ("Sem registro de eventos do Qt neste teste (o filtro não foi instalado). "
                "Use só as pilhas do Python abaixo.")
    silencio = anel.silencio_s(agora)
    if silencio is None:
        return ("O Qt NUNCA entregou um evento durante este teste: ou o travamento ocorreu antes do primeiro evento, "
                "ou o filtro não chegou a funcionar.")
    if silencio >= silencio_minimo_s:
        return (f"BLOQUEIO: o Qt não entrega NENHUM evento há {silencio:.1f} s. O processo está parado dentro de uma "
                "chamada nativa (ou esperando algo). O último evento entregue, e portanto o provável culpado, está "
                "no fim da lista de eventos.")
    return (f"LAÇO DE EVENTOS: o Qt continua entregando eventos (o último há {silencio:.2f} s; {anel.total} no total), "
            "mas o teste não termina: algo se reativa sem parar. Veja os eventos mais frequentes.")


def montar_relatorio(*, nome: str, decorrido_s: float, limite_s: float, anel: AnelDeEventos | None,
                     mensagens: RegistroDeMensagens | None, pilhas: str, ambiente: str, agora: float, quando: str,
                     nome_do_tipo=str, ultimos: int = 60, topo: int = 12) -> str:
    """O texto do relatório de travamento. Função pura (tudo vem por argumento)."""
    linhas = ["=" * 78,
              f"TRAVAMENTO DE TESTE DE JANELA - {quando}",
              "=" * 78,
              f"{MARCA_DO_TESTE}{nome}",
              f"DECORRIDO: {decorrido_s:.1f} s (limite {limite_s:.0f} s)",
              "",
              "DIAGNOSTICO: " + diagnosticar(anel, agora),
              ""]
    if anel is not None:
        linhas.append(f"EVENTOS DO QT: os {ultimos} ultimos (instante relativo ao momento do alarme)")
        recentes = anel.ultimos(ultimos)
        linhas += [_evento_em_texto(r, agora, nome_do_tipo) for r in recentes] or ["  (nenhum)"]
        linhas += ["", "EVENTOS MAIS FREQUENTES nos ultimos 5 s (receptor, tipo: quantidade):"]
        frequentes = anel.mais_frequentes(agora, 5.0, topo)
        linhas += [f"  {receptor}  {nome_do_tipo(tipo)}: {quantidade}" for (receptor, tipo), quantidade in frequentes] or ["  (nenhum)"]
        linhas += ["", f"TOTAIS desde o inicio do teste ({anel.total} eventos):"]
        linhas += [f"  {receptor}  {nome_do_tipo(tipo)}: {quantidade}" for (receptor, tipo), quantidade in anel.totais(topo)] or ["  (nenhum)"]
        linhas.append("")
    if mensagens is not None:
        linhas.append("MENSAGENS DO QT (as ultimas):")
        itens = mensagens.ultimas(40)
        linhas += [f"  {instante - agora:+9.3f} s  [{nivel}] {texto}" for instante, nivel, texto in itens] or ["  (nenhuma)"]
        linhas.append("")
    linhas += ["PILHAS DO PYTHON (a da thread [PRINCIPAL] mostra onde o teste parou; se terminar numa chamada do Qt,",
               "o resto aconteceu em codigo nativo):", pilhas, "", "AMBIENTE:", ambiente, MARCA_DE_FIM, ""]
    return "\n".join(linhas)


def nome_do_tipo_de_evento():
    """Função tipo -> nome (`Timer`, `Paint`...) com os nomes do `QEvent.Type`; sem Qt, o próprio número."""
    nomes: dict[int, str] = {}
    try:
        qevent = sys.modules["PySide6.QtCore"].QEvent
        for membro in qevent.Type:
            nomes.setdefault(inteiro_do_enum(membro), membro.name)
    except Exception:  # noqa: BLE001
        nomes = {}
    return lambda tipo: nomes.get(tipo, str(tipo))


# ------------------------------------------------------------------------------------------------ o vigia
class Vigia:
    """Fiscal de UM teste: se passar do limite, grava o relatório e encerra o processo."""

    def __init__(self, nome: str, limite_s: float, arquivo, *, relogio=time.monotonic, sair=os._exit,
                 passo_s: float = 0.5, ambiente: str | None = None, agora_em_texto=None, alarme_nativo: bool = True) -> None:
        self.nome = nome
        self.limite_s = float(limite_s)
        self.arquivo = pathlib.Path(arquivo)
        self.arquivo_nativo = self.arquivo.with_name(ARQUIVO_DO_ALARME_NATIVO)
        self.anel: AnelDeEventos | None = None
        self.mensagens: RegistroDeMensagens | None = None
        self.disparou = False
        self._relogio = relogio
        self._sair = sair
        self._passo_s = passo_s
        self._agora_em_texto = agora_em_texto or (lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._inicio = relogio()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._desfazer: list = []              # o que desinstalar ao encerrar (filtro de eventos, tratador de mensagens)
        self._alarme_nativo = None
        self._com_alarme_nativo = alarme_nativo
        self._nome_do_tipo = str
        self.ambiente = descrever_ambiente() if ambiente is None else ambiente

    # -- ciclo de vida
    def iniciar(self) -> "Vigia":
        self._thread = threading.Thread(target=self._laco, name="vigia-de-travamento", daemon=True)
        self._thread.start()
        self._armar_alarme_nativo()
        return self

    def encerrar(self) -> None:
        self._parar.set()
        for desfazer in reversed(self._desfazer):
            try:
                desfazer()
            except Exception:  # noqa: BLE001
                pass
        self._desfazer.clear()
        self._desarmar_alarme_nativo()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)

    def _laco(self) -> None:
        while not self._parar.wait(self._passo_s):
            if self._relogio() - self._inicio >= self.limite_s:
                self.disparar()
                return

    # -- Qt (só na thread da interface)
    def anexar_qt(self, app, *, qobject=None, qtcore=None) -> None:
        """Liga o anel de eventos e o registro de mensagens. Qualquer falha é ignorada: o diagnóstico é opcional."""
        self._nome_do_tipo = nome_do_tipo_de_evento()
        try:
            self.anel = AnelDeEventos(relogio=self._relogio)
            _filtro, remover = instalar_filtro_de_eventos(app, self.anel, qobject)
            self._desfazer.append(remover)
        except Exception as exc:  # noqa: BLE001
            self.anel = None
            self.ambiente += f"\n(o filtro de eventos não pôde ser instalado: {type(exc).__name__}: {exc})"
        try:
            self.mensagens = RegistroDeMensagens(relogio=self._relogio)
            self._desfazer.append(instalar_mensagens_do_qt(self.mensagens, qtcore))
        except Exception as exc:  # noqa: BLE001
            self.mensagens = None
            self.ambiente += f"\n(o tratador de mensagens do Qt não pôde ser instalado: {type(exc).__name__}: {exc})"

    def marcar(self, texto: str) -> None:
        if self.anel is not None:
            self.anel.marcar(texto)

    # -- alarme
    def nome_atual(self) -> str:
        """O pytest troca PYTEST_CURRENT_TEST a cada fase (setup/call/teardown): lido AGORA, diz onde o teste parou."""
        return os.environ.get("PYTEST_CURRENT_TEST") or self.nome

    def relatorio(self) -> str:
        agora = self._relogio()
        return montar_relatorio(nome=self.nome_atual(), decorrido_s=agora - self._inicio, limite_s=self.limite_s, anel=self.anel,
                                mensagens=self.mensagens, pilhas=pilhas_das_threads(), ambiente=self.ambiente, agora=agora,
                                quando=self._agora_em_texto(), nome_do_tipo=self._nome_do_tipo)

    def disparar(self) -> None:
        """Grava o relatório e encerra o processo. Roda na thread do vigia (ou direto, nos testes)."""
        if self._parar.is_set():
            return                                   # o teste terminou neste instante
        self.disparou = True
        texto = self.relatorio()
        try:
            self.arquivo.parent.mkdir(parents=True, exist_ok=True)
            with open(self.arquivo, "a", encoding="utf-8") as saida:
                saida.write(texto)
                saida.flush()
                try:
                    os.fsync(saida.fileno())
                except OSError:
                    pass
        except Exception as exc:  # noqa: BLE001
            self._avisar(f"não consegui gravar {self.arquivo}: {type(exc).__name__}: {exc}\n{texto}")
        self._avisar(f"\nTRAVAMENTO: {self.nome_atual()} passou de {self.limite_s:.0f} s. Relatório em {self.arquivo}")
        self._desarmar_alarme_nativo()               # o relatório já está gravado: o alarme nativo não tem mais o que fazer
        self._sair(CODIGO_DE_TRAVAMENTO)

    @staticmethod
    def _avisar(texto: str) -> None:
        try:
            if sys.__stderr__ is not None:
                print(texto, file=sys.__stderr__, flush=True)
        except Exception:  # noqa: BLE001
            pass

    def _armar_alarme_nativo(self) -> None:
        """O alarme do faulthandler roda numa thread NATIVA (não precisa do GIL): é a rede de segurança caso a thread do
        Python não consiga rodar (por exemplo, um impasse entre o GIL e um bloqueio interno do Qt). Despeja as pilhas do
        Python de todas as threads em `travamento_qt_nativo.txt` e encerra o processo (com o código 1: o faulthandler não
        deixa escolher). O arquivo só sobra se o alarme disparou; o lançador o procura para classificar o teste."""
        if not self._com_alarme_nativo:
            return
        try:
            self.arquivo_nativo.parent.mkdir(parents=True, exist_ok=True)
            self._alarme_nativo = open(self.arquivo_nativo, "w", encoding="utf-8")
            faulthandler.dump_traceback_later(self.limite_s + FOLGA_DO_ALARME_NATIVO_S, exit=True, file=self._alarme_nativo)
        except Exception:  # noqa: BLE001
            self._alarme_nativo = None

    def _desarmar_alarme_nativo(self) -> None:
        if self._alarme_nativo is None:
            return
        try:
            faulthandler.cancel_dump_traceback_later()
            self._alarme_nativo.close()
            self.arquivo_nativo.unlink()      # o teste terminou a tempo: o arquivo do alarme não tem o que dizer
        except Exception:  # noqa: BLE001
            pass
        self._alarme_nativo = None


# ------------------------------------------------------------------------------------------------ cola com o Qt
def instalar_filtro_de_eventos(app, anel: AnelDeEventos, qobject=None):
    """(Qt, thread da interface) Instala em `app` um filtro que anota cada evento no anel. Devolve (filtro, remover).

    O filtro nunca consome um evento (devolve False) e nunca levanta exceção. Só lê o NOME DA CLASSE do receptor e o
    `objectName()`, que é válido enquanto o objeto recebe o evento."""
    if qobject is None:
        from PySide6.QtCore import QObject as qobject  # noqa: N813

    class FiltroDeEventos(qobject):
        def eventFilter(self, objeto, evento):  # noqa: N802
            try:
                try:
                    nome = objeto.objectName()
                except Exception:  # noqa: BLE001
                    nome = ""
                anel.registrar(type(objeto).__name__, inteiro_do_enum(evento.type()), nome)
            except Exception:  # noqa: BLE001
                pass
            return False

    filtro = FiltroDeEventos()
    app.installEventFilter(filtro)

    def remover() -> None:
        try:
            app.removeEventFilter(filtro)
        except Exception:  # noqa: BLE001
            pass

    return filtro, remover


def instalar_mensagens_do_qt(registro: RegistroDeMensagens, qtcore=None):
    """(Qt) Anota no registro as mensagens do Qt e continua imprimindo-as no stderr, como o tratador padrão fazia.
    Devolve a função que restaura o tratador anterior."""
    if qtcore is None:
        from PySide6 import QtCore as qtcore

    def tratador(tipo, _contexto, mensagem):
        try:
            registro.registrar(getattr(tipo, "name", tipo), mensagem)
        except Exception:  # noqa: BLE001
            pass
        try:
            if sys.__stderr__ is not None:
                print(mensagem, file=sys.__stderr__, flush=True)
        except Exception:  # noqa: BLE001
            pass

    anterior = qtcore.qInstallMessageHandler(tratador)

    def restaurar() -> None:
        qtcore.qInstallMessageHandler(anterior)

    return restaurar


# ------------------------------------------------------------------------------------------------ o vigia "atual"
_ATUAL: Vigia | None = None


def limite_do_ambiente(padrao: float = LIMITE_PADRAO_S, ambiente: dict | None = None) -> float:
    """O limite em segundos: AS_LIMITE_TESTE_JANELA, se for um número positivo; senão o padrão."""
    bruto = (os.environ if ambiente is None else ambiente).get("AS_LIMITE_TESTE_JANELA", "")
    try:
        valor = float(bruto)
    except (TypeError, ValueError):
        return padrao
    return valor if valor > 0 else padrao


def iniciar(nome: str, pasta, limite_s: float | None = None) -> Vigia:
    """Liga o vigia do teste atual (e desliga um anterior que tenha ficado). `pasta` é a pasta logs/ do projeto."""
    global _ATUAL
    if _ATUAL is not None:
        _ATUAL.encerrar()
    _ATUAL = Vigia(nome, limite_do_ambiente() if limite_s is None else limite_s, pathlib.Path(pasta) / ARQUIVO_DO_RELATORIO).iniciar()
    return _ATUAL


def atual() -> Vigia | None:
    return _ATUAL


def encerrar_atual() -> None:
    global _ATUAL
    if _ATUAL is not None:
        _ATUAL.encerrar()
        _ATUAL = None


def marcar(texto: str) -> None:
    """Um marco do teste no anel de eventos ("antes do show()"). Não faz nada sem vigia ou sem anel."""
    if _ATUAL is not None:
        _ATUAL.marcar(texto)


def teste_que_travou(texto_do_relatorio: str) -> str:
    """O nodeid do ÚLTIMO teste citado num relatório (`TESTE: <nodeid> (fase)`), sem a fase; vazio se não houver."""
    achados = [linha[len(MARCA_DO_TESTE):].strip() for linha in texto_do_relatorio.splitlines() if linha.startswith(MARCA_DO_TESTE)]
    if not achados:
        return ""
    ultimo = achados[-1]
    return ultimo.rsplit(" (", 1)[0] if ultimo.endswith(")") and " (" in ultimo else ultimo
