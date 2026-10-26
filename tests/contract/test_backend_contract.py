"""CONTRATO dos backends de entrada: a mesma bateria roda no Mock, no pynput (simulado) e no Win32 (SendInput simulado).

O motor só conhece a interface `InputBackend`. Qualquer backend novo (ou refatoração dos atuais) precisa passar aqui.
Dois perfis de rigor:
  * ESTRITOS (pynput, Win32): recusam nome desconhecido com ValueError e NÃO enviam nada ao sistema nesse caso;
  * Mock: aceita e registra tudo (é o dublê dos testes do motor).
O que cada backend envia em detalhe (flags do SendInput, teclas mortas, ...) fica nos arquivos test_backend_win32.py e
test_backend_pynput.py.
"""
import pytest

from automationstudio import core
from automationstudio.input_system import InputBackend, MockInputBackend, PynputInputBackend, Win32InputBackend
from testsupport.fakes import FakePynput, FakeUser32

PERFIS = ["mock", "pynput", "win32"]
ESTRITOS = ["pynput", "win32"]

_VERBOS_PYNPUT = {"press": "key_down", "release": "key_up", "type": "type_text", "mouse_press": "mouse_down",
                  "mouse_release": "mouse_up", "position": "mouse_move", "move": "mouse_move", "scroll": "mouse_scroll"}
_BAIXAR = {0x0002, 0x0008, 0x0020, 0x0080}   # LEFT/RIGHT/MIDDLE/X DOWN
_SUBIR = {0x0004, 0x0010, 0x0040, 0x0100}    # ... UP


class _Alvo:
    """Backend sob teste + o que ele mandou ao 'sistema', traduzido para verbos comuns (key_down, mouse_up, ...)."""

    def __init__(self, nome, backend, fonte):
        self.nome, self.backend, self._fonte = nome, backend, fonte

    @property
    def estrito(self) -> bool:
        return self.nome != "mock"

    def verbos(self) -> list[str]:
        if self.nome == "mock":
            return [evento[1] for evento in self._fonte.events]
        if self.nome == "pynput":
            return [_VERBOS_PYNPUT[entrada[0]] for entrada in self._fonte.log]
        resultado = []
        for entrada in self._fonte.sent:
            if entrada[0] == "key":
                resultado.append("key_up" if entrada[2] & 0x0002 else "key_down")
            elif entrada[0] == "cursor":
                resultado.append("mouse_move")
            else:
                flags = entrada[1]
                resultado.append("mouse_down" if flags in _BAIXAR else "mouse_up" if flags in _SUBIR
                                 else "mouse_scroll" if flags in (0x0800, 0x1000) else "mouse_move")
        return resultado


def _alvo(perfil, monkeypatch, fake_clock) -> _Alvo:
    monkeypatch.setattr(core, "TEXT_CHAR_INTERVAL", 0.0)  # digitação sem pausas reais
    if perfil == "mock":
        backend = MockInputBackend(clock=fake_clock)
        return _Alvo(perfil, backend, backend)
    if perfil == "pynput":
        falso = FakePynput().install(monkeypatch)
        return _Alvo(perfil, PynputInputBackend(), falso)
    usuario = FakeUser32()
    return _Alvo(perfil, Win32InputBackend(user32=usuario), usuario)


# ----------------------------------------------------------------------------------------- a interface
def test_a_interface_tem_exatamente_os_sete_metodos_abstratos():
    assert set(InputBackend.__abstractmethods__) == {
        "key_down", "key_up", "mouse_down", "mouse_up", "mouse_move", "mouse_scroll", "type_text"}


@pytest.mark.parametrize("perfil", PERFIS)
def test_todo_backend_e_uma_implementacao_completa_da_interface(perfil, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    assert isinstance(alvo.backend, InputBackend)
    assert all(callable(getattr(alvo.backend, nome)) for nome in InputBackend.__abstractmethods__ | {"release_all"})


# ----------------------------------------------------------------------------------------- teclado
@pytest.mark.parametrize("nome", ["A", "7", "F5", "ENTER", "SHIFT", "SPACE", "LEFT", "ESC"])
@pytest.mark.parametrize("perfil", PERFIS)
def test_apertar_e_soltar_uma_tecla_gera_um_par(perfil, nome, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    alvo.backend.key_down(nome)
    alvo.backend.key_up(nome)
    assert alvo.verbos() == ["key_down", "key_up"]


@pytest.mark.parametrize("perfil", ESTRITOS)
def test_a_tecla_fn_nao_existe_para_o_sistema_e_e_ignorada_sem_erro(perfil, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    alvo.backend.key_down("FN")
    alvo.backend.key_up("FN")
    assert alvo.verbos() == []


@pytest.mark.parametrize("perfil", ESTRITOS)
def test_tecla_desconhecida_e_recusada_com_o_nome_e_sem_enviar_nada(perfil, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    with pytest.raises(ValueError, match="TECLA_INEXISTENTE"):
        alvo.backend.key_down("TECLA_INEXISTENTE")
    assert alvo.verbos() == [], "recusar não pode, em hipótese alguma, apertar outra tecla no lugar"


@pytest.mark.parametrize("perfil", ESTRITOS)
def test_soltar_tecla_desconhecida_nunca_envia_outra_tecla(perfil, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    try:
        alvo.backend.key_up("TECLA_INEXISTENTE")  # ignorar em silêncio (Win32) ou recusar (pynput): os dois servem
    except ValueError:
        pass
    assert alvo.verbos() == []


def test_o_mock_aceita_e_registra_qualquer_nome(monkeypatch, fake_clock):
    alvo = _alvo("mock", monkeypatch, fake_clock)
    alvo.backend.key_down("QUALQUER COISA")
    assert [(a, t) for _t, a, t in alvo.backend.events] == [("key_down", "QUALQUER COISA")]


# ----------------------------------------------------------------------------------------- mouse
@pytest.mark.parametrize("botao", ["left", "right", "middle", "x1", "x2"])
@pytest.mark.parametrize("perfil", PERFIS)
def test_cada_botao_do_mouse_aperta_e_solta_um_par(perfil, botao, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    alvo.backend.mouse_down(botao)
    alvo.backend.mouse_up(botao)
    assert alvo.verbos() == ["mouse_down", "mouse_up"]


@pytest.mark.parametrize("botao", ["LEFT", "Right", "X1", "X2"])
@pytest.mark.parametrize("perfil", ESTRITOS)
def test_nome_de_botao_aceita_qualquer_caixa(perfil, botao, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    alvo.backend.mouse_down(botao)
    alvo.backend.mouse_up(botao)
    assert alvo.verbos() == ["mouse_down", "mouse_up"]


@pytest.mark.parametrize("perfil", ESTRITOS)
def test_botao_desconhecido_nunca_vira_clique_em_outro_botao(perfil, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    for chamada in (alvo.backend.mouse_down, alvo.backend.mouse_up):
        with pytest.raises(ValueError, match="lefft"):
            chamada("lefft")
    assert alvo.verbos() == []


def test_o_mock_recebe_os_botoes_laterais_com_o_nome_cru(monkeypatch, fake_clock):
    # D1 (25.5): o nome que o comando carrega chega intacto; nenhum backend troca x1 por x2.
    alvo = _alvo("mock", monkeypatch, fake_clock)
    alvo.backend.mouse_down("x1"); alvo.backend.mouse_up("x1")
    assert [(a, t) for _t, a, t in alvo.backend.events] == [("mouse_down", "x1"), ("mouse_up", "x1")]


@pytest.mark.parametrize("perfil", PERFIS)
def test_mover_o_mouse_em_modo_absoluto_e_relativo(perfil, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    alvo.backend.mouse_move(100, 200)
    alvo.backend.mouse_move(-5, 7, relative=True)
    assert alvo.verbos() == ["mouse_move", "mouse_move"]


@pytest.mark.parametrize("quantidade", [(0, 3), (2, 0), (0, -1)])
@pytest.mark.parametrize("perfil", PERFIS)
def test_rolagem_em_um_so_eixo_e_um_so_evento(perfil, quantidade, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    alvo.backend.mouse_scroll(*quantidade)
    assert alvo.verbos() == ["mouse_scroll"]


@pytest.mark.parametrize("perfil", ESTRITOS)
def test_rolagem_zero_por_zero_nao_envia_nada_no_win32_e_um_evento_no_pynput(perfil, monkeypatch, fake_clock):
    # Diferença deliberada e inofensiva: o pynput recebe scroll(0, 0); o Win32 não manda INPUT vazio.
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    alvo.backend.mouse_scroll(0, 0)
    assert alvo.verbos() == ([] if perfil == "win32" else ["mouse_scroll"])


# ----------------------------------------------------------------------------------------- texto
@pytest.mark.parametrize("perfil", PERFIS)
def test_texto_simples_envia_alguma_coisa(perfil, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    alvo.backend.type_text("abc")
    assert alvo.verbos()


@pytest.mark.parametrize("vazio", ["", None])
@pytest.mark.parametrize("perfil", ESTRITOS)
def test_texto_vazio_nao_envia_nada(perfil, vazio, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    alvo.backend.type_text(vazio)
    assert alvo.verbos() == []


# ----------------------------------------------------------------------------------------- liberação de segurança
@pytest.mark.parametrize("perfil", PERFIS)
def test_release_all_solta_tudo_o_que_foi_pedido(perfil, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    alvo.backend.release_all({"A", "SHIFT"}, {"left", "x1"})
    verbos = alvo.verbos()
    assert verbos.count("key_up") == 2 and verbos.count("mouse_up") == 2 and len(verbos) == 4


@pytest.mark.parametrize("perfil", PERFIS)
def test_release_all_vazio_nao_faz_nada(perfil, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    alvo.backend.release_all(set(), set())
    assert alvo.verbos() == []


@pytest.mark.parametrize("perfil", ESTRITOS)
def test_release_all_ignora_itens_invalidos_e_solta_os_validos(perfil, monkeypatch, fake_clock):
    alvo = _alvo(perfil, monkeypatch, fake_clock)
    alvo.backend.release_all({"A", "TECLA_RUIM"}, {"lefft", "left"})  # nunca levanta
    verbos = alvo.verbos()
    assert verbos.count("key_up") == 1 and verbos.count("mouse_up") == 1


# ----------------------------------------------------------------------------------------- o Mock em si
def test_mock_registra_tempo_relativo_ao_proprio_inicio(fake_clock):
    fake_clock.advance(100.0)  # o relógio já andou antes de o backend existir
    backend = MockInputBackend(clock=fake_clock)
    fake_clock.advance(0.1234567)
    backend.key_down("A")
    assert backend.events == [(0.123, "key_down", "A")], "tempo em segundos desde a criação, com 3 casas"


def test_mock_sem_relogio_usa_o_relogio_do_sistema():
    backend = MockInputBackend()
    backend.key_down("A")
    assert isinstance(backend._clock, core.SystemClock) and backend.events[0][1:] == ("key_down", "A")
    assert backend.actions() == ["key_down"]
