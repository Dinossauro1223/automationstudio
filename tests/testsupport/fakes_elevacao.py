"""Um Windows de mentira para os testes do aviso de administrador (automationstudio/elevacao.py).

`MundoWindows` guarda processos e janelas e entrega três "DLLs" falsas (user32, kernel32, advapi32) com as funções que a
`SondaWindows` chama, e a função que devolve o último erro. As regras do mundo são o que se ACREDITA valer no Windows de
verdade (isso NÃO foi conferido nele; ver md/ENTREGA_AVISO_ADMINISTRADOR.md):
    * abrir um processo elevado, estando o programa sem elevação, pedindo MAIS do que PROCESS_QUERY_LIMITED_INFORMATION é
      negado (erro 5); o mesmo vale para pedir mais do que TOKEN_QUERY no token dele;
    * todo o resto depende do que o teste configurar (processo que nega a abertura, token que nega a leitura etc.).
Cada função falsa é um objeto que aceita `argtypes` e `restype`, como as da DLL de verdade, para o teste conferir as
assinaturas. O mundo também registra as chamadas, os acessos pedidos e as alças que ficaram abertas.

`SondaFalsa` é a versão de alto nível (sem ctypes) para testar só o vigia.
"""
from __future__ import annotations

import os

from automationstudio.elevacao import Elevacao

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
CLASSE_TOKEN_ELEVATION = 20
ERRO_ACESSO_NEGADO = 5
ERRO_ALCA_INVALIDA = 6
ERRO_PARAMETRO_INVALIDO = 87
ERRO_BUFFER_PEQUENO = 122
PSEUDO_ALCA_DO_PROCESSO_ATUAL = -1


class _Funcao:
    """Função de DLL falsa: chamável, registra a chamada no mundo e tem `argtypes` e `restype` como as de verdade."""

    def __init__(self, mundo, nome, implementacao) -> None:
        self._mundo, self.nome, self._implementacao = mundo, nome, implementacao
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        self._mundo.chamadas.append(self.nome)
        return self._implementacao(*args)


class _Dll:
    def __init__(self, mundo, **funcoes) -> None:
        for nome, implementacao in funcoes.items():
            setattr(self, nome, _Funcao(mundo, nome, implementacao))


class MundoWindows:
    def __init__(self, eu_elevado: bool = False, meu_pid: int | None = None) -> None:
        self.eu_elevado = eu_elevado
        self.meu_pid = meu_pid if meu_pid is not None else os.getpid()
        self.token_proprio_falha = 0          # erro a devolver ao abrir o token do próprio programa (0 = funciona)
        self.processos: dict[int, dict] = {}  # pid -> {nome, elevado, abrir, token, info}
        self.janelas: dict[int, int] = {}     # hwnd -> pid
        self.frente = 0                       # hwnd da janela em primeiro plano (0 = nenhuma)
        self.cursor = (0, 0)
        self.cursor_falha = False
        self.janela_no_ponto: dict[tuple[int, int], int] = {}  # (x, y) -> hwnd
        self.erro = 0                         # o "último erro" do Windows
        self.chamadas: list[str] = []
        self.pedidos_de_acesso: list[tuple[str, int]] = []     # ("processo" | "token", máscara pedida)
        self.alcas: dict[int, tuple] = {}     # alça aberta -> ("processo", pid) | ("token", pid ou None)
        self.fechamentos_invalidos: list[int] = []
        self._proxima_alca = 1000
        self.user32 = _Dll(self, GetForegroundWindow=self._janela_da_frente, GetWindowThreadProcessId=self._pid_da_janela,
                           GetCursorPos=self._ler_cursor, WindowFromPoint=self._janela_sob_o_ponto)
        self.kernel32 = _Dll(self, GetCurrentProcess=lambda: PSEUDO_ALCA_DO_PROCESSO_ATUAL, OpenProcess=self._abrir_processo,
                             CloseHandle=self._fechar, QueryFullProcessImageNameW=self._nome_do_executavel)
        self.advapi32 = _Dll(self, OpenProcessToken=self._abrir_token, GetTokenInformation=self._informacao_do_token)

    # ---- montagem do cenário --------------------------------------------------------------------------------------
    def adicionar_processo(self, pid: int, nome: str | None, elevado: bool = False, *, abrir: int = 0, token: int = 0,
                           info: int = 0) -> None:
        """`nome=None`: o nome do executável não pode ser lido. `abrir`, `token` e `info`: erro a devolver ao abrir o processo,
        ao abrir o token e ao ler a informação do token (0 = funciona)."""
        self.processos[pid] = {"nome": nome, "elevado": elevado, "abrir": abrir, "token": token, "info": info}

    def adicionar_janela(self, hwnd: int, pid: int, *, na_frente: bool = False, sob_o_cursor: tuple[int, int] | None = None) -> None:
        self.janelas[hwnd] = pid
        if na_frente:
            self.frente = hwnd
        if sob_o_cursor is not None:
            self.cursor = sob_o_cursor
            self.janela_no_ponto[sob_o_cursor] = hwnd

    def criar_sonda(self):
        from automationstudio.elevacao import SondaWindows
        return SondaWindows(user32=self.user32, kernel32=self.kernel32, advapi32=self.advapi32,
                            ultimo_erro=lambda: self.erro)

    def alcas_abertas(self) -> list[tuple]:
        return list(self.alcas.values())

    # ---- user32 ---------------------------------------------------------------------------------------------------
    def _janela_da_frente(self):
        return self.frente

    def _pid_da_janela(self, hwnd, ponteiro_do_pid):
        pid = self.janelas.get(hwnd, 0)
        ponteiro_do_pid.contents.value = pid
        return 1 if pid else 0  # o Windows devolve o id da thread, 0 se a janela não existe

    def _ler_cursor(self, ponteiro_do_ponto):
        if self.cursor_falha:
            self.erro = ERRO_ACESSO_NEGADO
            return 0
        ponteiro_do_ponto.contents.x, ponteiro_do_ponto.contents.y = self.cursor
        return 1

    def _janela_sob_o_ponto(self, ponto):
        return self.janela_no_ponto.get((ponto.x, ponto.y), 0)

    # ---- kernel32 -------------------------------------------------------------------------------------------------
    def _nova_alca(self, dono: tuple) -> int:
        self._proxima_alca += 1
        self.alcas[self._proxima_alca] = dono
        return self._proxima_alca

    def _abrir_processo(self, acesso, herdar, pid):
        self.pedidos_de_acesso.append(("processo", int(acesso)))
        processo = self.processos.get(pid)
        if processo is None:
            self.erro = ERRO_PARAMETRO_INVALIDO
            return 0
        if processo["abrir"]:
            self.erro = processo["abrir"]
            return 0
        if (acesso & ~PROCESS_QUERY_LIMITED_INFORMATION) and processo["elevado"] and not self.eu_elevado:
            self.erro = ERRO_ACESSO_NEGADO
            return 0
        return self._nova_alca(("processo", pid))

    def _fechar(self, alca):
        if alca in self.alcas:
            del self.alcas[alca]
        else:
            self.fechamentos_invalidos.append(alca)
        return 1

    def _nome_do_executavel(self, alca, flags, texto, ponteiro_do_tamanho):
        dono = self.alcas.get(alca)
        if dono is None or dono[0] != "processo":
            self.erro = ERRO_ALCA_INVALIDA
            return 0
        nome = self.processos[dono[1]]["nome"]
        if nome is None:
            self.erro = ERRO_ACESSO_NEGADO
            return 0
        caminho = "C:\\Windows\\System32\\" + nome
        if ponteiro_do_tamanho.contents.value < len(caminho) + 1:
            self.erro = ERRO_BUFFER_PEQUENO
            return 0
        texto.value = caminho
        ponteiro_do_tamanho.contents.value = len(caminho)
        return 1

    # ---- advapi32 -------------------------------------------------------------------------------------------------
    def _abrir_token(self, alca, acesso, ponteiro_do_token):
        self.pedidos_de_acesso.append(("token", int(acesso)))
        if alca == PSEUDO_ALCA_DO_PROCESSO_ATUAL:
            if self.token_proprio_falha:
                self.erro = self.token_proprio_falha
                return 0
            pid = None
        else:
            dono = self.alcas.get(alca)
            if dono is None or dono[0] != "processo":
                self.erro = ERRO_ALCA_INVALIDA
                return 0
            pid = dono[1]
            processo = self.processos[pid]
            if processo["token"]:
                self.erro = processo["token"]
                return 0
            if (acesso & ~TOKEN_QUERY) and processo["elevado"] and not self.eu_elevado:
                self.erro = ERRO_ACESSO_NEGADO
                return 0
        ponteiro_do_token.contents.value = self._nova_alca(("token", pid))
        return 1

    def _informacao_do_token(self, alca, classe, ponteiro_da_informacao, tamanho, ponteiro_dos_devolvidos):
        dono = self.alcas.get(alca)
        if dono is None or dono[0] != "token":
            self.erro = ERRO_ALCA_INVALIDA
            return 0
        if classe != CLASSE_TOKEN_ELEVATION:
            self.erro = ERRO_PARAMETRO_INVALIDO
            return 0
        if tamanho < 4:
            self.erro = ERRO_BUFFER_PEQUENO
            return 0
        pid = dono[1]
        if pid is None:
            elevado = self.eu_elevado
        else:
            if self.processos[pid]["info"]:
                self.erro = self.processos[pid]["info"]
                return 0
            elevado = self.processos[pid]["elevado"]
        ponteiro_da_informacao.contents.TokenIsElevated = 1 if elevado else 0
        ponteiro_dos_devolvidos.contents.value = 4
        return 1


class SondaFalsa:
    """O que o vigia chama, sem ctypes. `processos`: pid -> (nome, Elevacao). Registra cada chamada em `chamadas`."""

    def __init__(self, programa: Elevacao = Elevacao.NAO, meu_pid: int = 100) -> None:
        self.programa = programa
        self.pid_do_programa = meu_pid
        self.frente: int | None = None
        self.cursor: int | None = None
        self.processos: dict[int, tuple[str, Elevacao]] = {}
        self.chamadas: list[str] = []
        self.erro: Exception | None = None  # se definido, `pid_da_janela_da_frente` o levanta

    def meu_pid(self) -> int:
        self.chamadas.append("meu_pid")
        return self.pid_do_programa

    def elevacao_do_programa(self) -> Elevacao:
        self.chamadas.append("elevacao_do_programa")
        return self.programa

    def pid_da_janela_da_frente(self):
        self.chamadas.append("frente")
        if self.erro is not None:
            raise self.erro
        return self.frente

    def pid_da_janela_sob_o_cursor(self):
        self.chamadas.append("cursor")
        return self.cursor

    def ler_processo(self, pid: int):
        self.chamadas.append(f"ler_processo({pid})")
        return self.processos[pid]
