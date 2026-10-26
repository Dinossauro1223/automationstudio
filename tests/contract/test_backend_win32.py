"""Win32InputBackend: o que exatamente vai para o USER32.SendInput (usa o SendInput FALSO de testsupport/fakes.py).

Valida códigos de tecla, flags, botões laterais, rolagem, digitação com acentos e as falhas do sistema. NÃO prova que o
Windows aceita esses eventos: isso só se verifica na máquina real (tests/e2e_windows e o roteiro manual do README).
"""
import types

import pytest

from automationstudio import core, input_system
from automationstudio.input_system import Win32InputBackend
from testsupport.fakes import FakeKernel32, FakeUser32, FakeUser32Abnt2, pretend_not_windows

SUBIR, ESTENDIDA, UNICODE = 0x0002, 0x0001, 0x0004
MASCARA_32 = 0xFFFFFFFF  # o campo mouseData é DWORD (32 bits no Windows); no Linux o c_ulong é maior


def _backend(usuario=None, **kwargs):
    usuario = usuario if usuario is not None else FakeUser32()
    return Win32InputBackend(user32=usuario, **kwargs), usuario


# ----------------------------------------------------------------------------------------- construção
def test_fora_do_windows_o_backend_real_nao_existe(monkeypatch):
    pretend_not_windows(monkeypatch)
    with pytest.raises(RuntimeError, match="só está disponível no Windows"):
        Win32InputBackend()


def test_com_user32_injetado_funciona_em_qualquer_sistema_e_se_identifica():
    backend, _ = _backend()
    assert backend.name == "Windows USER32.SendInput"


# ----------------------------------------------------------------------------------------- teclado
@pytest.mark.parametrize("nome,codigo,estendida", [
    ("A", 0x41, False), ("a", 0x41, False), ("Z", 0x5A, False), ("0", 0x30, False), ("9", 0x39, False),
    ("F1", 0x70, False), ("F12", 0x7B, False), ("NUM0", 0x60, False), ("NUM9", 0x69, False),
    ("NUM*", 0x6A, False), ("NUM+", 0x6B, False), ("NUM-", 0x6D, False), ("NUM.", 0x6E, False),
    ("ENTER", 0x0D, False), ("enter", 0x0D, False), ("TAB", 0x09, False), ("BACKSPACE", 0x08, False), ("ESC", 0x1B, False),
    ("SPACE", 0x20, False), ("SHIFT", 0x10, False), ("CTRL", 0x11, False), ("ALT", 0x12, False), ("CAPSLOCK", 0x14, False),
    ("PAUSE", 0x13, False), ("NUMLOCK", 0x90, False), ("SCROLLLOCK", 0x91, False), ("PRINTSCREEN", 0x2C, False),
    ("Ç", 0xBA, False), ("ç", 0xBA, False), ("~^", 0xC0, False), ("VOLUME_MUTE", 0xAD, False), ("MEDIA_NEXT", 0xB0, False),
    # Teclas estendidas: o SendInput precisa da flag KEYEVENTF_EXTENDEDKEY para distinguir de suas gêmeas do teclado numérico.
    ("LEFT", 0x25, True), ("UP", 0x26, True), ("RIGHT", 0x27, True), ("DOWN", 0x28, True), ("HOME", 0x24, True),
    ("END", 0x23, True), ("PAGEUP", 0x21, True), ("PAGEDOWN", 0x22, True), ("INSERT", 0x2D, True), ("DELETE", 0x2E, True),
    ("WIN", 0x5B, True), ("MENU", 0x5D, True), ("ALTGR", 0xA5, True), ("NUM/", 0x6F, True)])
def test_cada_tecla_envia_o_codigo_virtual_e_a_flag_de_tecla_estendida(nome, codigo, estendida):
    backend, usuario = _backend()
    backend.key_down(nome)
    backend.key_up(nome)
    extra = ESTENDIDA if estendida else 0
    assert usuario.keys() == [(codigo, extra), (codigo, SUBIR | extra)]


def test_enter_do_teclado_numerico_envia_o_mesmo_codigo_do_enter_normal():
    # Limitação conhecida (baixa): NUMENTER usa VK_RETURN sem a flag de tecla estendida, então o aplicativo receptor
    # não distingue as duas. Quase nenhum aplicativo distingue; confirmar no hardware se algum macro depender disso.
    normal, u1 = _backend(); numerico, u2 = _backend()
    normal.key_down("ENTER"); numerico.key_down("NUMENTER")
    assert u1.keys() == u2.keys() == [(0x0D, 0)]


def test_caractere_fora_da_tabela_usa_o_codigo_que_o_layout_informa_sem_o_shift():
    backend, usuario = _backend(FakeUser32Abnt2())
    backend.key_down("^")  # no layout falso '^' é SHIFT+tecla 0xDE; só o código da tecla segue (sem SHIFT implícito)
    assert usuario.keys() == [(0xDE, 0)]


@pytest.mark.parametrize("nome", ["TECLA_INEXISTENTE", "", "??", "@"])
def test_tecla_sem_codigo_levanta_valueerror_com_o_nome(nome):
    backend, usuario = _backend()
    with pytest.raises(ValueError, match="não suportada pelo backend Win32"):
        backend.key_down(nome)
    assert usuario.sent == []


def test_soltar_tecla_sem_codigo_e_ignorado_em_silencio():
    backend, usuario = _backend()
    backend.key_up("TECLA_INEXISTENTE")
    assert usuario.sent == []


def test_cada_evento_de_teclado_e_um_unico_sendinput():
    backend, usuario = _backend()
    backend.key_down("A"); backend.key_up("A")
    assert usuario.send_calls == 2


# ----------------------------------------------------------------------------------------- mouse: botões
@pytest.mark.parametrize("botao,baixar,soltar,dado", [
    ("left", 0x0002, 0x0004, 0), ("right", 0x0008, 0x0010, 0), ("middle", 0x0020, 0x0040, 0),
    ("x1", 0x0080, 0x0100, 1), ("x2", 0x0080, 0x0100, 2), ("LEFT", 0x0002, 0x0004, 0), ("X2", 0x0080, 0x0100, 2)])
def test_cada_botao_envia_as_flags_de_descer_e_subir(botao, baixar, soltar, dado):
    backend, usuario = _backend()
    backend.mouse_down(botao)
    backend.mouse_up(botao)
    assert usuario.mouse() == [(baixar, dado, 0, 0), (soltar, dado, 0, 0)]


def test_botoes_laterais_seguem_o_nome_cru_x1_e_xbutton1_x2_e_xbutton2():
    # D1 (25.5): o comando "x1" vira XBUTTON1 e "x2" vira XBUTTON2, sem troca no caminho de execução.
    backend, usuario = _backend()
    backend.mouse_down("x1"); backend.mouse_down("x2")
    assert [dado for _flags, dado, _dx, _dy in usuario.mouse()] == [1, 2]


# ----------------------------------------------------------------------------------------- mouse: movimento e rolagem
def test_movimento_absoluto_posiciona_o_cursor_sem_enviar_input_de_mouse():
    backend, usuario = _backend()
    backend.mouse_move(120, -30)  # coordenadas negativas existem em monitores à esquerda do principal
    assert usuario.sent == [("cursor", 120, -30)]


def test_movimento_relativo_envia_um_input_de_movimento_com_o_deslocamento():
    backend, usuario = _backend()
    backend.mouse_move(-3, 4, relative=True)
    assert usuario.mouse() == [(0x0001, 0, -3, 4)]


def test_coordenadas_decimais_sao_truncadas():
    backend, usuario = _backend()
    backend.mouse_move(10.9, 20.2)
    assert usuario.sent == [("cursor", 10, 20)]


@pytest.mark.parametrize("dx,dy,esperado", [
    (0, 1, [(0x0800, 120)]), (0, -3, [(0x0800, (-360) & MASCARA_32)]), (2, 0, [(0x1000, 240)]),
    (-1, 0, [(0x1000, (-120) & MASCARA_32)]), (1, -2, [(0x0800, (-240) & MASCARA_32), (0x1000, 120)]), (0, 0, [])])
def test_rolagem_multiplica_por_120_e_manda_a_vertical_antes_da_horizontal(dx, dy, esperado):
    backend, usuario = _backend()
    backend.mouse_scroll(dx, dy)
    assert [(flags, dado & MASCARA_32) for flags, dado, _dx, _dy in usuario.mouse()] == esperado


# ----------------------------------------------------------------------------------------- texto
@pytest.mark.parametrize("texto,esperado", [
    ("a", [(0x41, 0), (0x41, 2)]),
    ("A", [(0x10, 0), (0x41, 0), (0x41, 2), (0x10, 2)]),  # maiúscula: SHIFT envolve a tecla
    (" ", [(0x20, 0), (0x20, 2)]),
    ("1", [(0x31, 0), (0x31, 2)]),
    ("aB 1", [(0x41, 0), (0x41, 2), (0x10, 0), (0x42, 0), (0x42, 2), (0x10, 2), (0x20, 0), (0x20, 2), (0x31, 0), (0x31, 2)])])
def test_texto_comum_vira_teclas_reais_do_layout(texto, esperado):
    backend, usuario = _backend()
    backend.type_text(texto)
    assert usuario.keys() == esperado


class _User32ComModificadores(FakeUser32):
    """Layout fictício com caracteres que só saem com CTRL e/ou ALT (o AltGr do ABNT2 chega como CTRL+ALT).

    O VkKeyScanExW devolve o estado dos modificadores no byte alto: 1 = SHIFT, 2 = CTRL, 4 = ALT.
    """

    TABELA = {"²": (6, 0x32),   # AltGr+2 no ABNT2: CTRL+ALT
              "\x01": (2, 0x41),  # só CTRL (no Windows real é o que o VkKeyScan informa para Ctrl+A)
              "@": (4, 0x51),    # só ALT (fictício)
              "§": (7, 0x31)}    # SHIFT+CTRL+ALT (fictício)

    @classmethod
    def _scan(cls, code: int) -> int:
        estado_e_vk = cls.TABELA.get(chr(code))
        return (estado_e_vk[0] << 8) | estado_e_vk[1] if estado_e_vk else FakeUser32._scan(code)


@pytest.mark.parametrize("caractere,esperado", [
    ("²", [(0x11, 0), (0x12, 0), (0x32, 0), (0x32, 2), (0x12, 2), (0x11, 2)]),                              # AltGr = CTRL+ALT
    ("\x01", [(0x11, 0), (0x41, 0), (0x41, 2), (0x11, 2)]),                                                 # só CTRL
    ("@", [(0x12, 0), (0x51, 0), (0x51, 2), (0x12, 2)]),                                                    # só ALT
    ("§", [(0x10, 0), (0x11, 0), (0x12, 0), (0x31, 0), (0x31, 2), (0x12, 2), (0x11, 2), (0x10, 2)])],       # os três
    ids=["altgr", "so-ctrl", "so-alt", "os-tres"])
def test_caractere_que_o_layout_faz_com_ctrl_e_alt_envia_cada_modificador_em_volta_da_tecla(caractere, esperado):
    # Os modificadores descem na ordem SHIFT, CTRL, ALT, a tecla desce e sobe, e eles sobem na ordem inversa; tudo
    # em UMA chamada do SendInput. Sem isso o AltGr do teclado brasileiro (², £, ¢, ¬, /, ?, °) sairia como o dígito.
    backend, usuario = _backend(_User32ComModificadores())
    backend.type_text(caractere)
    assert usuario.keys() == esperado
    assert usuario.send_calls == 1


def test_cada_caractere_e_enviado_em_uma_unica_chamada_do_sendinput():
    backend, usuario = _backend()
    backend.type_text("abc")
    assert usuario.send_calls == 3
    backend2, usuario2 = _backend()
    backend2.type_text("A")  # SHIFT + tecla + soltar tudo: 4 eventos, 1 chamada (ninguém se intromete no meio)
    assert usuario2.send_calls == 1 and len(usuario2.keys()) == 4


def test_caractere_sem_tecla_no_layout_vai_como_unicode():
    backend, usuario = _backend()
    backend.type_text("ç")
    assert usuario.sent == [("key", 0, UNICODE, 0xE7), ("key", 0, UNICODE | SUBIR, 0xE7)]
    assert usuario.send_calls == 1


def test_caractere_fora_do_plano_basico_vai_como_par_substituto_utf16():
    backend, usuario = _backend()
    backend.type_text("😀")  # U+1F600 = D83D DE00
    assert [(flags, scan) for _t, _vk, flags, scan in usuario.sent] == [
        (UNICODE, 0xD83D), (UNICODE | SUBIR, 0xD83D), (UNICODE, 0xDE00), (UNICODE | SUBIR, 0xDE00)]


@pytest.mark.parametrize("letra,esperado", [
    ("ã", [(0xDE, 0), (0xDE, 2), (0x41, 0), (0x41, 2)]),                              # ~ depois a
    ("é", [(0xDB, 0), (0xDB, 2), (0x45, 0), (0x45, 2)]),                              # ´ depois e
    ("â", [(0x10, 0), (0xDE, 0), (0xDE, 2), (0x10, 2), (0x41, 0), (0x41, 2)]),        # ^ (SHIFT+tecla) depois a
    ("Ã", [(0xDE, 0), (0xDE, 2), (0x10, 0), (0x41, 0), (0x41, 2), (0x10, 2)]),        # ~ depois SHIFT+a
    ("ü", [(0x10, 0), (0x36, 0), (0x36, 2), (0x10, 2), (0x55, 0), (0x55, 2)])])       # ¨ (SHIFT+tecla) depois u
def test_acentos_do_abnt2_sao_digitados_como_tecla_morta_mais_letra(letra, esperado):
    backend, usuario = _backend(FakeUser32Abnt2())
    backend.type_text(letra)
    assert usuario.keys() == esperado
    assert all(flags & UNICODE == 0 for _vk, flags in usuario.keys()), "composição física, não Unicode"
    assert usuario.send_calls == 2, "a tecla morta e a letra são duas chamadas: o Windows precisa processar a morta antes"


def test_sem_a_tecla_morta_no_layout_o_acento_cai_para_unicode_com_a_letra_inteira():
    backend, usuario = _backend(FakeUser32())  # este layout falso não tem '~'
    backend.type_text("ã")
    assert usuario.sent == [("key", 0, UNICODE, 0xE3), ("key", 0, UNICODE | SUBIR, 0xE3)]
    assert usuario.send_calls == 1


def test_texto_misto_mantem_a_ordem_dos_caracteres():
    backend, usuario = _backend(FakeUser32Abnt2())
    backend.type_text("oã!")
    # 'o' (0x4F), depois ~ + a, depois '!' que o layout falso não tem -> Unicode
    assert usuario.sent[:2] == [("key", 0x4F, 0, 0), ("key", 0x4F, 2, 0)]
    assert usuario.keys()[2:6] == [(0xDE, 0), (0xDE, 2), (0x41, 0), (0x41, 2)]
    assert usuario.sent[-2:] == [("key", 0, UNICODE, 0x21), ("key", 0, UNICODE | SUBIR, 0x21)]


def test_pausa_entre_caracteres_vem_da_constante_central(monkeypatch):
    pausas = []
    monkeypatch.setattr(input_system, "time", types.SimpleNamespace(sleep=pausas.append, monotonic=lambda: 0.0))
    monkeypatch.setattr(core, "TEXT_CHAR_INTERVAL", 0.02)
    backend, _ = _backend()
    backend.type_text("abc")
    assert pausas == [0.02, 0.02, 0.02]


def test_sem_pausa_configurada_nao_dorme(monkeypatch):
    pausas = []
    monkeypatch.setattr(input_system, "time", types.SimpleNamespace(sleep=pausas.append, monotonic=lambda: 0.0))
    monkeypatch.setattr(core, "TEXT_CHAR_INTERVAL", 0.0)
    backend, _ = _backend()
    backend.type_text("abc")
    assert pausas == []


# ----------------------------------------------------------------------------------------- falhas do sistema
@pytest.mark.parametrize("acao", [
    lambda b: b.key_down("A"), lambda b: b.key_up("A"), lambda b: b.mouse_down("left"), lambda b: b.mouse_up("left"),
    lambda b: b.mouse_scroll(0, 1), lambda b: b.mouse_move(1, 1, relative=True)])
def test_sendinput_recusado_vira_oserror_com_o_codigo_do_windows(acao):
    backend, _ = _backend(FakeUser32(fail_sends=True), kernel32=FakeKernel32(5))
    with pytest.raises(OSError, match=r"SendInput falhou \(GetLastError=5\)") as info:
        acao(backend)
    assert info.value.errno == 5


def test_sendinput_recusado_na_digitacao_diz_quantos_eventos_foram():
    backend, _ = _backend(FakeUser32(fail_sends=True), kernel32=FakeKernel32(5))
    with pytest.raises(OSError, match=r"SendInput enviou 0/2 eventos \(GetLastError=5\)"):
        backend.type_text("abc")


def test_sendinput_que_aceita_so_parte_dos_eventos_tambem_e_erro():
    class Parcial(FakeUser32):
        def SendInput(self, count, pointer, size):  # noqa: N802
            super().SendInput(count, pointer, size)
            return count - 1

    backend, _ = _backend(Parcial())
    with pytest.raises(OSError, match="enviou 1/2 eventos"):
        backend.type_text("a")


def test_sem_kernel32_o_codigo_de_erro_informado_e_zero():
    backend, _ = _backend(FakeUser32(fail_sends=True))
    with pytest.raises(OSError, match=r"GetLastError=0"):
        backend.key_down("A")


def test_release_all_com_o_sistema_recusando_tudo_nao_levanta():
    backend, _ = _backend(FakeUser32(fail_sends=True), kernel32=FakeKernel32(5))
    backend.release_all({"A", "SHIFT"}, {"left", "x1"})  # nunca deve levantar: é a rede de segurança da parada
