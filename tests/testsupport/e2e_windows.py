"""Ambientes dos testes e2e do Windows (tests/e2e_windows).

As verificações (testsupport/verificacoes_e2e.py) falam com um `Ambiente` e rodam em DOIS modos com o mesmo código:

  "simulado"  sempre, em qualquer sistema. O Win32InputBackend de verdade fala com um USER32 falso e uma janela de mentira
              recebe o resultado. Prova que o TESTE está certo e impede que o código e2e apodreça entre uma rodada real e outra.
  "windows"   só no Windows, e só com AS_ALLOW_REAL_INPUT=1 (Rodar_Testes.bat windows). Envia teclado e mouse REAIS a uma
              janela de teste que o próprio teste cria e traz para frente, e lê o estado do sistema (GetAsyncKeyState,
              GetCursorPos). É a única forma de saber se o Windows aceita o que o programa envia.

REGRAS DE SEGURANÇA do modo "windows" (valem para qualquer teste novo):
  - nada é enviado ao mouse sem antes confirmar que a janela de teste está em primeiro plano E sob o cursor;
  - nada é enviado ao teclado sem a janela de teste em primeiro plano, exceto SHIFT e CTRL sozinhos (inofensivos);
  - se o ambiente não permite (sem Tk, foco roubado por outro programa) o teste é PULADO e nada é enviado;
  - tudo o que um teste pressiona é solto no `finally` e, por garantia, no encerramento do ambiente.

Este módulo é importável em qualquer sistema: o que usa `ctypes.windll` só é tocado dentro de `AmbienteWindows`.
"""
from __future__ import annotations

import os
import time

from testsupport.fake_clock import FakeClock
from testsupport.fakes import FakeKernel32, FakeUser32

VARIAVEL = "AS_ALLOW_REAL_INPUT"
SIMULADO, WINDOWS = "simulado", "windows"

VK_LBUTTON, VK_RBUTTON, VK_MBUTTON, VK_XBUTTON1, VK_XBUTTON2 = 0x01, 0x02, 0x04, 0x05, 0x06
VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
_MODIFICADORES = ((VK_SHIFT, "SHIFT"), (VK_CONTROL, "CTRL"), (VK_MENU, "ALT"))


class Indisponivel(Exception):
    """O ambiente não permite este teste agora (sem Tk, janela sem foco, tecla já pressionada...). No modo real o teste é
    PULADO (e nada foi enviado); no simulado é falha, porque lá isso nunca deveria acontecer."""


def motivo_para_pular(modo: str, sistema: str | None = None, ambiente=None) -> str | None:
    """Por que o modo não pode rodar aqui (texto) ou None se pode."""
    if modo == SIMULADO:
        return None
    sistema = os.name if sistema is None else sistema
    ambiente = os.environ if ambiente is None else ambiente
    if sistema != "nt":
        return "este teste usa o Windows de verdade: o sistema atual não é o Windows"
    if ambiente.get(VARIAVEL) != "1":
        return (f"este teste envia teclado e mouse DE VERDADE; para rodá-lo use Rodar_Testes.bat windows (define {VARIAVEL}=1) "
                "e não mexa no teclado nem no mouse durante a rodada")
    return None


def rodar(verificacao, ambiente) -> None:
    """Executa uma verificação. `Indisponivel` vira SKIP no modo real e FALHA no simulado."""
    import pytest
    try:
        verificacao(ambiente)
    except Indisponivel as motivo:
        if ambiente.modo == SIMULADO:
            raise AssertionError(f"o ambiente simulado não pode ser indisponível: {motivo}") from None
        pytest.skip(str(motivo))


def criar(modo: str):
    if modo == SIMULADO:
        return AmbienteSimulado()
    if modo == WINDOWS:
        return AmbienteWindows()
    raise ValueError(f"modo desconhecido: {modo!r}")


class Ambiente:
    """O que as verificações usam. As duas implementações têm exatamente esta superfície."""
    modo = ""
    tempo_real = False   # o relógio do motor é o do sistema (então vale conferir o tempo decorrido)?
    relogio = None       # relógio que o ExecutionEngine recebe (None = o do sistema)

    def exigir(self, condicao, motivo: str) -> None:
        if not condicao:
            raise Indisponivel(motivo)

    def bombear(self) -> None:
        """Deixa a janela de teste processar as mensagens pendentes."""

    def esperar(self, condicao, limite: float = 3.0) -> bool:
        """Espera (processando as mensagens da janela) até a condição ser verdadeira ou o limite acabar."""
        fim = time.monotonic() + limite
        while True:
            self.bombear()
            if condicao():
                return True
            if time.monotonic() >= fim:
                return False
            time.sleep(0.01)

    def encerrar(self) -> None:
        pass


# ======================================================================================================== simulado
class _UsuarioSimulado(FakeUser32):
    """USER32 falso (o de testsupport.fakes) que, além de registrar cada INPUT, avisa o sistema simulado."""

    def __init__(self, sistema) -> None:
        super().__init__()
        self._sistema = sistema

    def SendInput(self, count, pointer, size):  # noqa: N802
        antes = len(self.sent)
        resultado = super().SendInput(count, pointer, size)
        for item in self.sent[antes:]:
            self._sistema.receber(item)
        return resultado

    def SetCursorPos(self, x, y):  # noqa: N802
        resultado = super().SetCursorPos(x, y)
        self._sistema.receber(self.sent[-1])
        return resultado


def _com_sinal_de_32_bits(valor: int) -> int:
    valor &= 0xFFFFFFFF
    return valor - (1 << 32) if valor >= (1 << 31) else valor


class AmbienteSimulado(Ambiente):
    modo = SIMULADO

    def __init__(self) -> None:
        self.relogio = FakeClock()
        self.usuario = _UsuarioSimulado(self)
        self._teclas: set[int] = set()
        self._cursor = (500, 400)
        self._janela = None

    def criar_backend(self):
        from automationstudio.input_system import Win32InputBackend
        return Win32InputBackend(user32=self.usuario, kernel32=FakeKernel32())

    def tecla_pressionada(self, vk: int) -> bool:
        return vk in self._teclas

    def cursor(self) -> tuple[int, int]:
        return self._cursor

    def mover_cursor(self, x: int, y: int) -> None:
        self._cursor = (int(x), int(y))

    def layout(self) -> str:
        return "simulado (USER32 falso)"

    def definir_intervalo_de_texto(self, segundos: float) -> None:
        """No simulado o intervalo continua zerado: o backend dorme em tempo real entre os caracteres."""

    def abrir_janela(self):
        self._janela = _JanelaSimulada(self)
        return self._janela

    # ---- o "Windows" recebendo o que o USER32 falso registrou -------------------------------------
    def receber(self, item: tuple) -> None:
        tipo = item[0]
        if tipo == "cursor":
            self._cursor = (item[1], item[2])
        elif tipo == "key":
            _, vk, flags, scan = item
            soltar, unicode_ = bool(flags & 0x0002), bool(flags & 0x0004)
            if unicode_:
                if not soltar and self._janela is not None:
                    self._janela.digitar(chr(scan))
            elif soltar:
                self._teclas.discard(vk)
            else:
                self._teclas.add(vk)
                if self._janela is not None:
                    self._janela.tecla(vk, VK_SHIFT in self._teclas)
        else:  # ("mouse", flags, dados, dx, dy)
            _, flags, dados, dx, dy = item
            if flags & 0x0001:
                self._cursor = (self._cursor[0] + dx, self._cursor[1] + dy)
            for bit, num, vk in ((0x0002, 1, VK_LBUTTON), (0x0020, 2, VK_MBUTTON), (0x0008, 3, VK_RBUTTON)):
                if flags & bit:
                    self._teclas.add(vk)
                    if self._janela is not None:
                        self._janela.botao_baixo(num, self._cursor)
            for bit, num, vk in ((0x0004, 1, VK_LBUTTON), (0x0040, 2, VK_MBUTTON), (0x0010, 3, VK_RBUTTON)):
                if flags & bit:
                    self._teclas.discard(vk)
                    if self._janela is not None:
                        self._janela.botao_cima(num, self._cursor)
            lateral = VK_XBUTTON1 if (dados & 0xFFFFFFFF) == 1 else VK_XBUTTON2
            if flags & 0x0080:
                self._teclas.add(lateral)
            if flags & 0x0100:
                self._teclas.discard(lateral)
            if flags & 0x0800 and self._janela is not None:
                self._janela.roda(_com_sinal_de_32_bits(dados))


class _JanelaSimulada:
    """Janela de mentira com a mesma superfície da janela Tk do modo real."""
    _RETANGULOS = {"raiz": (140, 140, 600, 470), "entrada": (150, 150, 590, 176),
                   "botao": (150, 186, 590, 236), "lista": (150, 246, 590, 460)}
    _NOMES_DE_TECLA = {0x0D: "Return", 0x10: "Shift_L", 0x11: "Control_L", 0x20: "space"}

    def __init__(self, ambiente) -> None:
        self._ambiente = ambiente
        self.eventos: list[tuple] = []
        self._letras: list[str] = []
        self._cliques = 0
        self._foco = "entrada"
        self._pressionado_em = None

    @property
    def texto(self) -> str:
        return "".join(self._letras)

    @property
    def cliques_no_botao(self) -> int:
        return self._cliques

    def centro(self, nome: str) -> tuple[int, int]:
        x0, y0, x1, y1 = self._RETANGULOS[nome]
        return (x0 + x1) // 2, (y0 + y1) // 2

    def _dentro(self, nome: str, ponto) -> bool:
        x0, y0, x1, y1 = self._RETANGULOS[nome]
        return x0 <= ponto[0] < x1 and y0 <= ponto[1] < y1

    def em_primeiro_plano(self) -> bool:
        return True

    def sob_o_cursor_e_na_frente(self, x: int, y: int) -> bool:
        return self._dentro("raiz", (x, y))

    def focar_entrada(self) -> None:
        self._foco = "entrada"

    def digitar(self, caractere: str) -> None:
        if self._foco == "entrada":
            self._letras.append(caractere)

    def tecla(self, vk: int, shift: bool) -> None:
        nome = self._NOMES_DE_TECLA.get(vk, f"vk{vk:02X}")
        if 0x41 <= vk <= 0x5A:
            nome = chr(vk).upper() if shift else chr(vk).lower()
            self.digitar(nome)
        elif 0x30 <= vk <= 0x39:
            nome = chr(vk)
            self.digitar(nome)
        elif vk == 0x20:
            self.digitar(" ")
        self.eventos.append(("tecla", nome))

    def botao_baixo(self, num: int, ponto) -> None:
        self.eventos.append(("botao", num))
        if self._dentro("entrada", ponto):
            self._foco = "entrada"
        self._pressionado_em = "botao" if self._dentro("botao", ponto) else None

    def botao_cima(self, num: int, ponto) -> None:
        if num == 1 and self._pressionado_em == "botao" and self._dentro("botao", ponto):
            self._cliques += 1
        self._pressionado_em = None

    def roda(self, delta: int) -> None:
        self.eventos.append(("roda", delta))


# ========================================================================================================= windows
class AmbienteWindows(Ambiente):
    modo = WINDOWS
    tempo_real = True

    def __init__(self) -> None:
        import ctypes
        self._ct = ctypes

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        self._POINT = POINT
        # Instância PRÓPRIA do user32: configurar tipos aqui não altera as funções que o programa usa (`ctypes.windll.user32`).
        u = ctypes.WinDLL("user32")
        u.GetAsyncKeyState.argtypes, u.GetAsyncKeyState.restype = [ctypes.c_int], ctypes.c_short
        u.GetCursorPos.argtypes, u.GetCursorPos.restype = [ctypes.POINTER(POINT)], ctypes.c_int
        u.SetCursorPos.argtypes, u.SetCursorPos.restype = [ctypes.c_int, ctypes.c_int], ctypes.c_int
        u.GetForegroundWindow.argtypes, u.GetForegroundWindow.restype = [], ctypes.c_void_p
        u.WindowFromPoint.argtypes, u.WindowFromPoint.restype = [POINT], ctypes.c_void_p
        u.GetAncestor.argtypes, u.GetAncestor.restype = [ctypes.c_void_p, ctypes.c_uint], ctypes.c_void_p
        u.GetKeyboardLayout.argtypes, u.GetKeyboardLayout.restype = [ctypes.c_uint], ctypes.c_void_p
        self._u = u
        self._janelas: list = []
        self._backends: list = []

    def criar_backend(self):
        from automationstudio.input_system import Win32InputBackend
        backend = Win32InputBackend()
        self._backends.append(backend)
        return backend

    def tecla_pressionada(self, vk: int) -> bool:
        return bool(self._u.GetAsyncKeyState(vk) & 0x8000)

    def cursor(self) -> tuple[int, int]:
        ponto = self._POINT()
        self._u.GetCursorPos(self._ct.byref(ponto))
        return ponto.x, ponto.y

    def mover_cursor(self, x: int, y: int) -> None:
        self._u.SetCursorPos(int(x), int(y))

    def layout(self) -> str:
        hkl = self._u.GetKeyboardLayout(0) or 0
        return f"idioma 0x{hkl & 0xFFFF:04X} (hkl 0x{hkl:08X}; 0x0416 = português do Brasil, 0x0409 = inglês dos EUA)"

    def definir_intervalo_de_texto(self, segundos: float) -> None:
        from automationstudio import core
        core.set_runtime_defaults(segundos)  # o conftest restaura o valor original no fim do teste

    def abrir_janela(self):
        try:
            import tkinter
        except Exception as erro:  # noqa: BLE001
            raise Indisponivel(f"tkinter indisponível ({erro}): instale o componente tcl/tk do Python") from None
        janela = _JanelaTk(self, tkinter)
        self._janelas.append(janela)
        return janela

    def bombear(self) -> None:
        for janela in self._janelas:
            janela.atualizar()

    def encerrar(self) -> None:
        for janela in self._janelas:
            janela.destruir()
        # Garantia final: nada que um teste pressionou fica pressionado, mesmo que ele tenha falhado no meio.
        if self._backends:
            backend = self._backends[0]
            for vk, nome in _MODIFICADORES:
                if self.tecla_pressionada(vk):
                    backend.key_up(nome)
            for botao in ("left", "right", "middle", "x1", "x2"):
                try:
                    backend.mouse_up(botao)
                except Exception:  # noqa: BLE001
                    pass


class _JanelaTk:
    """Janela Tk (a mesma que acompanha o instalador do Python) que registra tudo o que recebe."""

    def __init__(self, ambiente: AmbienteWindows, tk) -> None:
        self._amb = ambiente
        self.eventos: list[tuple] = []
        self._cliques = 0
        try:
            self.raiz = tk.Tk()
        except Exception as erro:  # noqa: BLE001
            raise Indisponivel(f"não foi possível abrir a janela de teste: {erro}") from None
        raiz = self.raiz
        raiz.title("Automation Studio - teste automatico: nao mexa no teclado nem no mouse")
        raiz.geometry("460x330+140+140")
        raiz.attributes("-topmost", True)
        self.entrada = tk.Entry(raiz, width=44)
        self.entrada.pack(padx=10, pady=(10, 6), fill="x")
        self.botao = tk.Button(raiz, text="alvo do clique", command=self._clicou)
        self.botao.pack(padx=10, pady=6, fill="x", ipady=10)
        self.lista = tk.Listbox(raiz, height=6)
        for i in range(60):
            self.lista.insert("end", f"linha {i}")
        self.lista.pack(padx=10, pady=6, fill="both", expand=True)
        raiz.bind_all("<KeyPress>", lambda e: self.eventos.append(("tecla", e.keysym)))
        raiz.bind_all("<KeyRelease>", lambda e: self.eventos.append(("tecla_solta", e.keysym)))
        raiz.bind_all("<ButtonPress>", lambda e: self.eventos.append(("botao", e.num)))
        raiz.bind_all("<MouseWheel>", lambda e: self.eventos.append(("roda", e.delta)))
        self.atualizar()
        if not self._trazer_para_frente():
            self.destruir()
            raise Indisponivel("a janela de teste não ficou em primeiro plano (outro programa está com o foco): nada foi "
                               "enviado. Deixe o computador quieto durante a rodada e tente de novo.")
        self.entrada.focus_force()
        self.atualizar()

    def _clicou(self) -> None:
        self._cliques += 1

    @property
    def texto(self) -> str:
        return self.entrada.get()

    @property
    def cliques_no_botao(self) -> int:
        return self._cliques

    def atualizar(self) -> None:
        try:
            self.raiz.update()
        except Exception:  # noqa: BLE001  (janela já destruída)
            pass

    def destruir(self) -> None:
        try:
            self.raiz.destroy()
        except Exception:  # noqa: BLE001
            pass

    def centro(self, nome: str) -> tuple[int, int]:
        widget = {"entrada": self.entrada, "botao": self.botao, "lista": self.lista}[nome]
        self.raiz.update_idletasks()
        return widget.winfo_rootx() + widget.winfo_width() // 2, widget.winfo_rooty() + widget.winfo_height() // 2

    def _topo(self):
        return self._amb._u.GetAncestor(self.raiz.winfo_id(), 2)  # GA_ROOT: a janela de nível superior

    def em_primeiro_plano(self) -> bool:
        topo = self._topo()
        return bool(topo) and self._amb._u.GetForegroundWindow() == topo

    def sob_o_cursor_e_na_frente(self, x: int, y: int) -> bool:
        """Verdadeiro só se a janela de teste está em primeiro plano E é a janela que existe no ponto (x, y) da tela."""
        if not self.em_primeiro_plano():
            return False
        sob = self._amb._u.WindowFromPoint(self._amb._POINT(int(x), int(y)))
        return bool(sob) and self._amb._u.GetAncestor(sob, 2) == self._topo()

    def focar_entrada(self) -> None:
        self.entrada.focus_force()
        self.atualizar()

    def _trazer_para_frente(self, tentativas: int = 15) -> bool:
        for _ in range(tentativas):
            self.raiz.deiconify()
            self.raiz.lift()
            self.raiz.attributes("-topmost", True)
            self.raiz.focus_force()
            self.atualizar()
            if self.em_primeiro_plano():
                return True
            time.sleep(0.1)
        return False
