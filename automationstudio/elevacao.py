"""Aviso de janela de administrador (função F51, item "Aviso de elevação" do md/PLANO_FUNCOES.md).

O problema. O Windows separa os programas por "nível de integridade" (isolamento de privilégios, UIPI). Um programa comum,
como o Automation Studio aberto do jeito normal, NÃO consegue entregar teclado nem mouse simulados à janela de um programa
aberto como administrador, e o Windows não avisa: o `SendInput` conta como enviado e a janela simplesmente não recebe nada.
A automação "roda" e não faz nada. O mesmo isolamento pode impedir que o gancho de teclado do programa enxergue as teclas
enquanto essa janela está na frente, e então os atalhos (inclusive o de parar) podem não funcionar. Isso é o que a
documentação do Windows e a experiência de outros programas indicam; não foi conferido num Windows de verdade (ver
md/ENTREGA_AVISO_ADMINISTRADOR.md).

Como não existe erro para ler depois, a detecção é feita ANTES: durante a execução olha-se de quem é a janela que vai receber
a entrada (a da frente, para o teclado, e a que está sob o cursor, para o mouse) e se o dono dela roda elevado enquanto o
programa não. O motor de execução não é tocado.

Este módulo não usa Qt. Tem três partes:
    * a REGRA, em funções puras (`situacao`) e os TEXTOS (`montar_aviso`);
    * a LEITURA do Windows (`SondaWindows`, só ctypes, sem psutil), com user32/kernel32/advapi32 injetáveis para os testes;
    * o VIGIA (`VigiaDeElevacao`): lembra o que já olhou, avisa uma vez por programa em cada execução e olha no máximo
      algumas vezes por segundo, para custar quase nada.
A ligação com a janela principal (rótulo na barra de status) está em elevacao_ui.py.
"""
from __future__ import annotations

import enum
import ntpath
import os
import time
from dataclasses import dataclass
from typing import Callable

ARQUIVO_PARA_ADMINISTRADOR = "Iniciar como administrador.bat"
INTERVALO_ENTRE_OLHADAS = 0.25  # segundos; entre uma olhada e outra o vigia não toca no Windows


class Elevacao(enum.Enum):
    """Se um processo roda elevado (como administrador)."""
    SIM = "sim"
    NAO = "nao"
    NEGADA = "negada"            # o processo abriu, mas o Windows negou a leitura do token (acesso negado)
    DESCONHECIDA = "desconhecida"  # não deu para saber, por qualquer outro motivo


class Situacao(enum.Enum):
    """O que a combinação (programa, janela alvo) significa para a entrada simulada."""
    LIVRE = "livre"          # sem problema: o programa é elevado, ou o alvo é comum
    BLOQUEADA = "bloqueada"  # alvo elevado e programa comum: o Windows barra a entrada sem avisar
    PROVAVEL = "provavel"    # o alvo não deixou ser lido (acesso negado): provavelmente é elevado
    INCERTA = "incerta"      # não deu para saber: sem aviso, só registro no log


def situacao(programa: Elevacao, alvo: Elevacao) -> Situacao:
    """A regra. Só há problema quando o PROGRAMA é comum e o ALVO é elevado (ou nega a leitura). Quando o programa é elevado,
    a entrada passa. Qualquer dúvida sobre o programa ou sobre o alvo vira INCERTA: avisar sem ter certeza assustaria à toa."""
    if programa is Elevacao.SIM:
        return Situacao.LIVRE
    if programa is not Elevacao.NAO:
        return Situacao.INCERTA
    if alvo is Elevacao.SIM:
        return Situacao.BLOQUEADA
    if alvo is Elevacao.NEGADA:
        return Situacao.PROVAVEL
    if alvo is Elevacao.NAO:
        return Situacao.LIVRE
    return Situacao.INCERTA


ONDE_FRENTE = "frente"   # a janela em primeiro plano (recebe o teclado)
ONDE_CURSOR = "cursor"   # a janela sob o cursor do mouse (recebe o mouse)


@dataclass(frozen=True)
class Aviso:
    """O que mostrar ao usuário. `curto` cabe no rótulo da barra de status; `longo` é a dica do rótulo e a linha do log."""
    situacao: Situacao
    pid: int
    nome: str    # "Taskmgr.exe", ou "" se o nome não pôde ser lido
    onde: str    # ONDE_FRENTE ou ONDE_CURSOR
    curto: str
    longo: str


def montar_aviso(estado: Situacao, pid: int, nome: str, onde: str) -> Aviso | None:
    """Os textos do aviso. Só BLOQUEADA e PROVAVEL têm aviso; LIVRE e INCERTA devolvem None."""
    if estado not in (Situacao.BLOQUEADA, Situacao.PROVAVEL):
        return None
    nome = str(nome or "").strip()
    qual = f"do {nome}" if nome else ("sob o mouse" if onde == ONDE_CURSOR else "da frente")
    entre_parenteses = f" ({nome})" if nome else ""
    como_resolver = f"feche o Automation Studio e abra de novo pelo “{ARQUIVO_PARA_ADMINISTRADOR}”."
    if estado is Situacao.BLOQUEADA:
        curto = f"⚠ Janela de administrador{entre_parenteses}: o Windows bloqueia a entrada"
        longo = (f"A janela {qual} está aberta como administrador e o Automation Studio não. O Windows bloqueia o teclado e "
                 "o mouse simulados nessa janela e não mostra nenhum erro: a automação parece rodar, mas nada acontece nela. "
                 "As teclas de atalho (inclusive a de parar) também podem não funcionar enquanto ela estiver na frente. "
                 f"Para resolver, {como_resolver}")
    else:
        curto = f"⚠ Pode ser janela de administrador{entre_parenteses}: a entrada pode ser bloqueada"
        longo = (f"Não deu para ler o nível de acesso da janela {qual}: o Windows negou. Isso pode acontecer quando ela está "
                 "aberta como administrador e o Automation Studio não. Se a automação não faz nada nela, é provavelmente "
                 f"isso. Para resolver, {como_resolver}")
    return Aviso(estado, int(pid), nome, onde, curto, longo)


# ------------------------------------------------------------------------------------------- a leitura do Windows
def _declarar(funcao, argtypes, restype) -> None:
    """Declara a assinatura de uma função da DLL (sem isso o ctypes corta ponteiros de 64 bits). Dublês de teste, que são
    funções comuns do Python, não aceitam esses atributos: ignora."""
    try:
        funcao.argtypes = argtypes
        funcao.restype = restype
    except AttributeError:
        pass


class SondaWindows:
    """Lê do Windows o que o vigia precisa. Todas as chamadas são só de LEITURA e pedem o mínimo de acesso:
    PROCESS_QUERY_LIMITED_INFORMATION no processo e TOKEN_QUERY no token (pedir mais falharia justamente com os processos
    elevados, que são os que interessam). Cada alça aberta é fechada.

    `user32`, `kernel32`, `advapi32` e `ultimo_erro` podem ser injetados (os testes põem dublês); sem eles, usa as DLLs de
    verdade, em instâncias próprias (as assinaturas daqui não interferem nas de outros trechos do programa)."""

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    TOKEN_QUERY = 0x0008
    TOKEN_ELEVATION = 20          # classe de informação TokenElevation
    ERROR_ACCESS_DENIED = 5

    def __init__(self, user32=None, kernel32=None, advapi32=None, ultimo_erro: Callable[[], int] | None = None) -> None:
        import ctypes
        from ctypes import wintypes
        if user32 is None or kernel32 is None or advapi32 is None or ultimo_erro is None:
            if os.name != "nt":
                raise RuntimeError("A leitura do nível de acesso dos processos só existe no Windows.")
            user32 = user32 if user32 is not None else ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = kernel32 if kernel32 is not None else ctypes.WinDLL("kernel32", use_last_error=True)
            advapi32 = advapi32 if advapi32 is not None else ctypes.WinDLL("advapi32", use_last_error=True)
            ultimo_erro = ultimo_erro if ultimo_erro is not None else ctypes.get_last_error
        self._ctypes = ctypes
        self._wintypes = wintypes
        self.user32, self.kernel32, self.advapi32 = user32, kernel32, advapi32
        self._ultimo_erro = ultimo_erro

        class TOKEN_ELEVATION(ctypes.Structure):
            _fields_ = [("TokenIsElevated", wintypes.DWORD)]

        self._estrutura_token = TOKEN_ELEVATION
        W = wintypes
        _declarar(user32.GetForegroundWindow, [], W.HWND)
        _declarar(user32.GetWindowThreadProcessId, [W.HWND, W.LPDWORD], W.DWORD)
        _declarar(user32.GetCursorPos, [W.LPPOINT], W.BOOL)
        _declarar(user32.WindowFromPoint, [W.POINT], W.HWND)
        _declarar(kernel32.GetCurrentProcess, [], W.HANDLE)
        _declarar(kernel32.OpenProcess, [W.DWORD, W.BOOL, W.DWORD], W.HANDLE)
        _declarar(kernel32.CloseHandle, [W.HANDLE], W.BOOL)
        _declarar(kernel32.QueryFullProcessImageNameW, [W.HANDLE, W.DWORD, W.LPWSTR, W.LPDWORD], W.BOOL)
        _declarar(advapi32.OpenProcessToken, [W.HANDLE, W.DWORD, ctypes.POINTER(W.HANDLE)], W.BOOL)
        _declarar(advapi32.GetTokenInformation, [W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD, W.LPDWORD], W.BOOL)

    # ---- o próprio programa ---------------------------------------------------------------------------------------
    def meu_pid(self) -> int:
        return os.getpid()

    def elevacao_do_programa(self) -> Elevacao:
        token, _erro = self._abrir_token(self.kernel32.GetCurrentProcess())
        if token is None:
            return Elevacao.DESCONHECIDA
        try:
            return self._elevacao_do_token(token)
        finally:
            self.kernel32.CloseHandle(token)

    # ---- janelas ---------------------------------------------------------------------------------------------------
    def pid_da_janela_da_frente(self) -> int | None:
        return self._pid_da_janela(self.user32.GetForegroundWindow())

    def pid_da_janela_sob_o_cursor(self) -> int | None:
        ponto = self._wintypes.POINT()
        if not self.user32.GetCursorPos(self._ctypes.pointer(ponto)):
            return None
        return self._pid_da_janela(self.user32.WindowFromPoint(ponto))

    def _pid_da_janela(self, janela) -> int | None:
        if not janela:
            return None
        pid = self._wintypes.DWORD(0)
        self.user32.GetWindowThreadProcessId(janela, self._ctypes.pointer(pid))
        return int(pid.value) or None

    # ---- um processo -----------------------------------------------------------------------------------------------
    def ler_processo(self, pid: int) -> tuple[str, Elevacao]:
        """(nome do executável, elevação) do processo. O nome vem vazio se não pôde ser lido."""
        processo = self.kernel32.OpenProcess(self.PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not processo:
            return "", self._negada_ou_desconhecida(self._ultimo_erro())
        try:
            nome = self._nome_do_executavel(processo)
            token, erro = self._abrir_token(processo)
            if token is None:
                return nome, self._negada_ou_desconhecida(erro)
            try:
                return nome, self._elevacao_do_token(token)
            finally:
                self.kernel32.CloseHandle(token)
        finally:
            self.kernel32.CloseHandle(processo)

    def _negada_ou_desconhecida(self, erro: int) -> Elevacao:
        return Elevacao.NEGADA if erro == self.ERROR_ACCESS_DENIED else Elevacao.DESCONHECIDA

    def _abrir_token(self, processo):
        """(alça do token como número, 0) ou (None, código do erro)."""
        token = self._wintypes.HANDLE()
        if not self.advapi32.OpenProcessToken(processo, self.TOKEN_QUERY, self._ctypes.pointer(token)):
            return None, self._ultimo_erro()
        return token.value, 0

    def _elevacao_do_token(self, token) -> Elevacao:
        info = self._estrutura_token()
        devolvidos = self._wintypes.DWORD(0)
        ok = self.advapi32.GetTokenInformation(token, self.TOKEN_ELEVATION, self._ctypes.pointer(info),
                                               self._ctypes.sizeof(info), self._ctypes.pointer(devolvidos))
        if not ok:
            return Elevacao.DESCONHECIDA
        return Elevacao.SIM if info.TokenIsElevated else Elevacao.NAO

    def _nome_do_executavel(self, processo) -> str:
        tamanho = self._wintypes.DWORD(1024)
        texto = self._ctypes.create_unicode_buffer(tamanho.value)
        if not self.kernel32.QueryFullProcessImageNameW(processo, 0, texto, self._ctypes.pointer(tamanho)):
            return ""
        return ntpath.basename(texto.value)


# ------------------------------------------------------------------------------------------- o vigia
class VigiaDeElevacao:
    """Olha, durante a execução, se a janela que recebe a entrada é de administrador e o programa não.

    * `olhar()` é barata e pode ser chamada a cada evento: entre duas olhadas há no mínimo `intervalo` segundos, e uma
      janela já conhecida não custa nenhuma chamada ao Windows (a elevação de um processo não muda enquanto ele vive).
    * Cada programa é avisado UMA vez por execução. `nova_rodada()` (início de uma execução nova) zera o que foi visto.
    * Nunca levanta erro: se a leitura do Windows falhar de um jeito inesperado, o vigia se desliga, registra o motivo uma
      vez e a execução segue como se ele não existisse.
    `registrar(texto)` recebe as linhas de diagnóstico (no programa, o log); `relogio` devolve segundos (testes injetam)."""

    def __init__(self, sonda, registrar: Callable[[str], None] | None = None,
                 relogio: Callable[[], float] = time.monotonic, intervalo: float = INTERVALO_ENTRE_OLHADAS) -> None:
        self.sonda = sonda
        self._registrar = registrar if registrar is not None else (lambda texto: None)
        self._relogio = relogio
        self._intervalo = float(intervalo)
        self._programa: Elevacao | None = None
        self._meu_pid: int | None = None
        self._proxima: float | None = None
        self._conhecidos: dict[int, tuple[str, Elevacao]] = {}
        self._tratados: set[int] = set()  # já avisados (ou registrados como incertos) nesta execução
        self.desligado = False

    def nova_rodada(self) -> None:
        self._conhecidos.clear()
        self._tratados.clear()
        self._proxima = None
        if self._programa not in (Elevacao.SIM, Elevacao.NAO):
            self._programa = None  # uma leitura duvidosa do próprio programa é refeita

    def olhar(self) -> Aviso | None:
        """Um aviso NOVO, ou None. Ver a classe."""
        if self.desligado:
            return None
        agora = self._relogio()
        if self._proxima is not None and agora < self._proxima:
            return None
        self._proxima = agora + self._intervalo
        try:
            return self._olhar()
        except Exception as erro:  # o aviso nunca pode atrapalhar a execução
            self.desligado = True
            self._registrar(f"ELEVACAO VIGIA DESLIGADO erro={type(erro).__name__}: {erro}")
            return None

    def _olhar(self) -> Aviso | None:
        if self._programa is None:
            self._programa = self.sonda.elevacao_do_programa()
            self._meu_pid = self.sonda.meu_pid()
            self._registrar(f"ELEVACAO programa={self._programa.value}")
        if self._programa is Elevacao.SIM:
            return None  # programa elevado: nada a barrar, nem precisa olhar as janelas
        for onde, pid in ((ONDE_FRENTE, self.sonda.pid_da_janela_da_frente()),
                          (ONDE_CURSOR, self.sonda.pid_da_janela_sob_o_cursor())):
            if not pid or pid == self._meu_pid or pid in self._tratados:
                continue
            if pid not in self._conhecidos:
                self._conhecidos[pid] = self.sonda.ler_processo(pid)
            nome, alvo = self._conhecidos[pid]
            estado = situacao(self._programa, alvo)
            if estado is Situacao.LIVRE:
                continue
            self._tratados.add(pid)
            if estado is Situacao.INCERTA:
                self._registrar(f"ELEVACAO INCERTA pid={pid} nome={nome or '?'} programa={self._programa.value} "
                                f"alvo={alvo.value} onde={onde}")
                continue
            return montar_aviso(estado, pid, nome, onde)
        return None


def criar_vigia(registrar: Callable[[str], None] | None = None, sistema: str | None = None) -> VigiaDeElevacao | None:
    """O vigia de verdade. Devolve None fora do Windows ou se a leitura do Windows não puder ser montada (o programa segue
    sem o aviso). `sistema` existe para os testes (padrão: `os.name`)."""
    sistema = os.name if sistema is None else sistema
    if sistema != "nt":
        return None
    try:
        return VigiaDeElevacao(SondaWindows(), registrar=registrar)
    except Exception as erro:
        if registrar is not None:
            registrar(f"ELEVACAO INDISPONIVEL erro={type(erro).__name__}: {erro}")
        return None
