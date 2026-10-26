"""PynputInputBackend (fallback): tradução dos nomes do Studio para o pynput, ramo Windows e ramo geral (pynput SIMULADO).

O backend de produção no Windows é o Win32InputBackend; este só entra quando o SendInput não está disponível.
Mesmo assim ele não pode apertar a tecla errada nem aceitar em silêncio o que não entende.
"""
import types

import pytest

from automationstudio import command_editor, core, input_system
from automationstudio.input_system import PynputInputBackend
from testsupport.fakes import FakePynput, FakeUser32, FakeWindll, pretend_windows

TECLADO_NUMERICO = [f"NUM{i}" for i in range(10)] + ["NUM/", "NUM*", "NUM-", "NUM+", "NUM.", "NUMENTER"]


def _backend(monkeypatch):
    falso = FakePynput().install(monkeypatch)
    return PynputInputBackend(), falso


def _vocabulario_do_studio() -> list[str]:
    """Todo nome de tecla que o editor oferece ou que o monitor global pode devolver ao gravador."""
    return list(dict.fromkeys(list(command_editor.CommandDialog._key_options()) + sorted(set(core._SPECIAL_KEY_NAMES.values()))))


# ----------------------------------------------------------------------------------------- construção
def test_sem_pynput_o_backend_recusa_e_ensina_a_instalar(monkeypatch):
    monkeypatch.setattr(input_system, "_PYNPUT_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="pip install pynput"):
        PynputInputBackend()


# ----------------------------------------------------------------------------------------- teclado
@pytest.mark.parametrize("nome,esperado", [
    ("A", "<char A>"), ("a", "<char a>"), ("7", "<char 7>"), ("Ç", "<char Ç>"),
    ("ENTER", "<enter>"), ("RETURN", "<enter>"), ("enter", "<enter>"), ("ESC", "<esc>"), ("ESCAPE", "<esc>"),
    ("CTRL", "<ctrl>"), ("SHIFT", "<shift>"), ("ALT", "<alt>"), ("ALTGR", "<alt_gr>"), ("WIN", "<cmd>"), ("MENU", "<menu>"),
    ("SPACE", "<space>"), ("TAB", "<tab>"), ("BACKSPACE", "<backspace>"), ("DELETE", "<delete>"), ("INSERT", "<insert>"),
    ("HOME", "<home>"), ("END", "<end>"), ("PAGEUP", "<page_up>"), ("PAGEDOWN", "<page_down>"),
    ("UP", "<up>"), ("DOWN", "<down>"), ("LEFT", "<left>"), ("RIGHT", "<right>"), ("CAPSLOCK", "<caps_lock>"),
    ("F1", "<f1>"), ("F12", "<f12>"), ("PAUSE", "<pause>"),
    ("PRINTSCREEN", "<print_screen>"), ("SCROLLLOCK", "<scroll_lock>"), ("NUMLOCK", "<num_lock>")])
def test_nomes_do_studio_viram_as_teclas_certas_do_pynput(monkeypatch, nome, esperado):
    backend, falso = _backend(monkeypatch)
    backend.key_down(nome)
    backend.key_up(nome)
    assert falso.log == [("press", esperado), ("release", esperado)]


def test_toda_tecla_que_o_editor_e_o_gravador_usam_e_aceita_exceto_o_teclado_numerico(monkeypatch):
    # Generalização do achado 1.10 para o fallback: nome oferecido ao usuário e recusado na execução = macro quebrada.
    backend, _ = _backend(monkeypatch)
    recusadas = []
    for nome in _vocabulario_do_studio():
        try:
            backend.key_down(nome)
            backend.key_up(nome)
        except ValueError:
            recusadas.append(nome)
    assert sorted(recusadas) == sorted(TECLADO_NUMERICO), (
        "só o teclado numérico fica sem tradução fora do Windows (lá usa keybd_event); sobrou: "
        f"{sorted(set(recusadas) - set(TECLADO_NUMERICO))}")


@pytest.mark.parametrize("nome", TECLADO_NUMERICO)
def test_teclado_numerico_fora_do_windows_e_recusado_com_valueerror(monkeypatch, nome):
    backend, falso = _backend(monkeypatch)
    with pytest.raises(ValueError, match="backend pynput"):
        backend.key_down(nome)
    assert falso.log == []


@pytest.mark.parametrize("nome", ["TECLA_INEXISTENTE", "AB", ""])
def test_nome_desconhecido_nunca_vira_outra_tecla(monkeypatch, nome):
    backend, falso = _backend(monkeypatch)
    with pytest.raises(ValueError, match="não suportada pelo backend pynput"):
        backend.key_down(nome)
    with pytest.raises(ValueError):
        backend.key_up(nome)
    assert falso.log == []


def test_fn_e_ignorada_sem_erro(monkeypatch):
    backend, falso = _backend(monkeypatch)
    backend.key_down("FN"); backend.key_up("fn")
    assert falso.log == []


# ----------------------------------------------------------------------------------------- ramo Windows (ctypes falso)
@pytest.mark.parametrize("nome,codigo", [
    ("NUM0", 0x60), ("NUM7", 0x67), ("NUM9", 0x69), ("NUM*", 0x6A), ("NUM+", 0x6B), ("NUM-", 0x6D), ("NUM.", 0x6E),
    ("NUM/", 0x6F), ("NUMENTER", 0x0D), ("Ç", 0xBA), ("~^", 0xC0), ("MENU", 0x5D), ("WIN", 0x5B), ("num7", 0x67)])
def test_no_windows_estas_teclas_vao_por_keybd_event_com_o_codigo_virtual(monkeypatch, nome, codigo):
    backend, falso = _backend(monkeypatch)
    pretend_windows(monkeypatch)
    janela = FakeWindll().install(monkeypatch)
    backend.key_down(nome)
    backend.key_up(nome)
    assert janela.calls == [("keybd_event", codigo, 0), ("keybd_event", codigo, 2)]
    assert falso.log == [], "o pynput nem é chamado para estas teclas"


def test_no_windows_as_outras_teclas_continuam_no_pynput(monkeypatch):
    backend, falso = _backend(monkeypatch)
    pretend_windows(monkeypatch)
    janela = FakeWindll().install(monkeypatch)
    backend.key_down("A"); backend.key_up("A")
    assert janela.calls == [] and falso.log == [("press", "<char A>"), ("release", "<char A>")]


def test_no_windows_se_o_keybd_event_falhar_cai_para_o_pynput(monkeypatch):
    backend, falso = _backend(monkeypatch)
    pretend_windows(monkeypatch)

    class _Quebrado:
        def keybd_event(self, *_args):
            raise OSError("negado")

    import ctypes
    monkeypatch.setattr(ctypes, "windll", types.SimpleNamespace(user32=_Quebrado()), raising=False)
    with pytest.raises(ValueError):  # NUM7 não existe no pynput: o erro continua claro, não vira outra tecla
        backend.key_down("NUM7")
    backend.key_down("MENU")
    assert falso.log == [("press", "<menu>")]


# ----------------------------------------------------------------------------------------- mouse
@pytest.mark.parametrize("botao,esperado", [("left", "<left>"), ("right", "<right>"), ("middle", "<middle>"),
                                            ("x1", "<x1>"), ("x2", "<x2>"), ("LEFT", "<left>"), ("X2", "<x2>")])
def test_botoes_do_mouse_traduzem_para_os_do_pynput(monkeypatch, botao, esperado):
    backend, falso = _backend(monkeypatch)
    backend.mouse_down(botao)
    backend.mouse_up(botao)
    assert falso.log == [("mouse_press", esperado), ("mouse_release", esperado)]


@pytest.mark.parametrize("botao", ["lefft", "", "x3", "wheel"])
def test_botao_desconhecido_nunca_vira_clique_esquerdo(monkeypatch, botao):
    backend, falso = _backend(monkeypatch)
    with pytest.raises(ValueError, match="não suportado pelo backend pynput"):
        backend.mouse_down(botao)
    with pytest.raises(ValueError):
        backend.mouse_up(botao)
    assert falso.log == []


def test_movimento_absoluto_define_a_posicao_e_o_relativo_desloca(monkeypatch):
    backend, falso = _backend(monkeypatch)
    backend.mouse_move(100, 200)
    backend.mouse_move(-5, 7, relative=True)
    assert falso.log == [("position", (100, 200)), ("move", -5, 7)]


def test_rolagem_fora_do_windows_e_uma_chamada_scroll_com_dx_e_dy(monkeypatch):
    backend, falso = _backend(monkeypatch)
    backend.mouse_scroll(1, -2)
    assert falso.log == [("scroll", 1, -2)]


def test_rolagem_no_windows_usa_mouse_event_com_passos_de_120(monkeypatch):
    backend, falso = _backend(monkeypatch)
    pretend_windows(monkeypatch)
    janela = FakeWindll().install(monkeypatch)
    backend.mouse_scroll(1, -2)
    assert janela.calls == [("mouse_event", 0x0800, -240), ("mouse_event", 0x1000, 120)] and falso.log == []


def test_rolagem_no_windows_so_manda_o_eixo_que_tem_valor(monkeypatch):
    backend, _ = _backend(monkeypatch)
    pretend_windows(monkeypatch)
    janela = FakeWindll().install(monkeypatch)
    backend.mouse_scroll(0, 3)
    backend.mouse_scroll(2, 0)
    assert janela.calls == [("mouse_event", 0x0800, 360), ("mouse_event", 0x1000, 240)]


# ----------------------------------------------------------------------------------------- texto
def test_texto_e_digitado_um_caractere_por_vez_com_acentos(monkeypatch):
    backend, falso = _backend(monkeypatch)
    backend.type_text("ação!")
    assert falso.log == [("type", c) for c in "ação!"]


def test_texto_vazio_ou_nulo_nao_digita_nada(monkeypatch):
    backend, falso = _backend(monkeypatch)
    backend.type_text(""); backend.type_text(None)
    assert falso.log == []


def test_pausa_entre_caracteres_vem_da_constante_central(monkeypatch):
    backend, _ = _backend(monkeypatch)
    pausas = []
    monkeypatch.setattr(input_system, "time", types.SimpleNamespace(sleep=pausas.append, monotonic=lambda: 0.0))
    monkeypatch.setattr(core, "TEXT_CHAR_INTERVAL", 0.05)
    backend.type_text("oi")
    assert pausas == [0.05, 0.05]


# ----------------------------------------------------------------------------------------- escolha do backend
def test_no_windows_com_sendinput_disponivel_o_padrao_e_o_win32(monkeypatch):
    FakePynput().install(monkeypatch)
    pretend_windows(monkeypatch)
    usuario = FakeUser32()
    FakeWindll(user32=usuario).install(monkeypatch)
    escolhido = input_system._default_backend()
    assert isinstance(escolhido, input_system.Win32InputBackend)
    escolhido.key_down("A")
    assert usuario.keys() == [(0x41, 0)], "o backend padrão do Windows fala com o user32 de ctypes.windll"


def test_no_windows_sem_sendinput_cai_para_o_pynput(monkeypatch):
    import ctypes
    FakePynput().install(monkeypatch)
    pretend_windows(monkeypatch)
    monkeypatch.delattr(ctypes, "windll", raising=False)  # sem windll o Win32InputBackend() não consegue nascer
    assert isinstance(input_system._default_backend(), PynputInputBackend)


def test_fora_do_windows_o_padrao_e_o_pynput(monkeypatch):
    FakePynput().install(monkeypatch)  # também finge "não é Windows"
    assert isinstance(input_system._default_backend(), PynputInputBackend)


def test_sem_nada_disponivel_o_padrao_e_o_mock(monkeypatch):
    FakePynput().install(monkeypatch)
    monkeypatch.setattr(input_system, "_PYNPUT_AVAILABLE", False)
    assert isinstance(input_system._default_backend(), input_system.MockInputBackend)
