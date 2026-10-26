"""Os ambientes dos testes e2e do Windows (testsupport/e2e_windows.py): o portão de segurança e o Windows de mentira.

O ambiente SIMULADO é um dublê: se ele estivesse errado, as verificações e2e passariam sem provar nada. Estes testes o
confrontam com o que a API do Windows documenta (códigos de botão, sinal da roda, estado do Shift...).
"""
import pytest

from testsupport import e2e_windows as e2e
from testsupport import static_checks as sc


# ----------------------------------------------------------------------------------------- portão de segurança
def test_modo_simulado_roda_em_qualquer_sistema():
    assert e2e.motivo_para_pular(e2e.SIMULADO, sistema="posix", ambiente={}) is None
    assert e2e.motivo_para_pular(e2e.SIMULADO, sistema="nt", ambiente={}) is None


def test_modo_real_fora_do_windows_e_pulado():
    motivo = e2e.motivo_para_pular(e2e.WINDOWS, sistema="posix", ambiente={e2e.VARIAVEL: "1"})
    assert motivo and "não é o Windows" in motivo


@pytest.mark.parametrize("valor", [None, "", "0", "true", "sim", "2"], ids=["ausente", "vazio", "zero", "true", "sim", "dois"])
def test_modo_real_no_windows_exige_exatamente_o_valor_1(valor):
    ambiente = {} if valor is None else {e2e.VARIAVEL: valor}
    motivo = e2e.motivo_para_pular(e2e.WINDOWS, sistema="nt", ambiente=ambiente)
    assert motivo and e2e.VARIAVEL in motivo and "DE VERDADE" in motivo


def test_modo_real_no_windows_com_a_variavel_roda():
    assert e2e.motivo_para_pular(e2e.WINDOWS, sistema="nt", ambiente={e2e.VARIAVEL: "1"}) is None


def test_modo_desconhecido_e_erro():
    with pytest.raises(ValueError):
        e2e.criar("producao")


def test_indisponivel_vira_falha_no_simulado_e_pulo_no_real():
    def verificacao(_ambiente):
        raise e2e.Indisponivel("sem foco")

    simulado = e2e.criar(e2e.SIMULADO)
    with pytest.raises(AssertionError, match="simulado não pode ser indisponível"):
        e2e.rodar(verificacao, simulado)

    class Falso:
        modo = e2e.WINDOWS

    with pytest.raises(BaseException) as erro:
        e2e.rodar(verificacao, Falso())
    assert type(erro.value).__name__ == "Skipped" and "sem foco" in str(erro.value)


# ----------------------------------------------------------------------------------------- o Windows de mentira
def _janela(ambiente):
    janela = ambiente.abrir_janela()
    return janela, ambiente.criar_backend()


def test_teclas_e_botoes_aparecem_pressionados_so_enquanto_seguros():
    ambiente = e2e.criar(e2e.SIMULADO)
    janela, backend = _janela(ambiente)
    backend.key_down("SHIFT")
    assert ambiente.tecla_pressionada(e2e.VK_SHIFT) and not ambiente.tecla_pressionada(e2e.VK_CONTROL)
    backend.key_up("SHIFT")
    assert not ambiente.tecla_pressionada(e2e.VK_SHIFT)
    backend.mouse_down("x1")
    assert ambiente.tecla_pressionada(e2e.VK_XBUTTON1) and not ambiente.tecla_pressionada(e2e.VK_XBUTTON2)
    backend.mouse_up("x1")
    backend.mouse_down("x2")
    assert ambiente.tecla_pressionada(e2e.VK_XBUTTON2) and not ambiente.tecla_pressionada(e2e.VK_XBUTTON1)
    backend.mouse_up("x2")
    assert not ambiente.tecla_pressionada(e2e.VK_XBUTTON1) and not ambiente.tecla_pressionada(e2e.VK_XBUTTON2)
    assert janela.eventos == [("tecla", "Shift_L")], "o x1/x2 não viram eventos da janela, só estado do sistema"


def test_maiusculas_dependem_do_shift_e_acentos_vem_pelo_caminho_unicode():
    ambiente = e2e.criar(e2e.SIMULADO)
    janela, backend = _janela(ambiente)
    for caractere in "Aa ç!1":
        backend.type_text(caractere)
    assert janela.texto == "Aa ç!1"
    assert not ambiente.tecla_pressionada(e2e.VK_SHIFT), "o backend solta o Shift que usou para a maiúscula"


def test_clique_so_aciona_o_botao_quando_pressionar_e_soltar_ocorrem_sobre_ele():
    ambiente = e2e.criar(e2e.SIMULADO)
    janela, backend = _janela(ambiente)
    x, y = janela.centro("botao")
    backend.mouse_move(x, y)
    backend.mouse_down("left")
    backend.mouse_up("left")
    assert janela.cliques_no_botao == 1
    backend.mouse_move(*janela.centro("lista"))
    backend.mouse_down("left")
    backend.mouse_up("left")
    assert janela.cliques_no_botao == 1, "clique fora do botão não o aciona"
    backend.mouse_move(x, y)
    backend.mouse_down("left")
    backend.mouse_move(*janela.centro("lista"))
    backend.mouse_up("left")
    assert janela.cliques_no_botao == 1, "pressionar sobre o botão e soltar fora dele não o aciona (como no Windows)"
    backend.mouse_down("right")
    backend.mouse_up("right")
    assert janela.cliques_no_botao == 1, "o botão direito não aciona o botão"


def test_roda_para_baixo_tem_sinal_negativo_e_tamanho_de_120_por_linha():
    ambiente = e2e.criar(e2e.SIMULADO)
    janela, backend = _janela(ambiente)
    backend.mouse_scroll(0, -2)
    backend.mouse_scroll(0, 1)
    assert janela.eventos == [("roda", -240), ("roda", 120)]


def test_movimento_relativo_soma_ao_cursor_e_o_absoluto_substitui():
    ambiente = e2e.criar(e2e.SIMULADO)
    backend = ambiente.criar_backend()
    backend.mouse_move(300, 300)
    assert ambiente.cursor() == (300, 300)
    backend.mouse_move(25, 15, relative=True)
    assert ambiente.cursor() == (325, 315)
    backend.mouse_move(-5, -5, relative=True)
    assert ambiente.cursor() == (320, 310)


def test_a_janela_simulada_so_esta_sob_o_cursor_dentro_do_retangulo():
    ambiente = e2e.criar(e2e.SIMULADO)
    janela = ambiente.abrir_janela()
    assert janela.em_primeiro_plano()
    for nome in ("entrada", "botao", "lista"):
        x, y = janela.centro(nome)
        assert janela.sob_o_cursor_e_na_frente(x, y), nome
    assert not janela.sob_o_cursor_e_na_frente(5, 5)
    assert not janela.sob_o_cursor_e_na_frente(10_000, 10_000)


def test_o_ambiente_simulado_usa_relogio_virtual_e_nao_e_tempo_real():
    ambiente = e2e.criar(e2e.SIMULADO)
    assert ambiente.relogio is not None and ambiente.tempo_real is False


def test_o_windows_de_verdade_nao_existe_fora_do_windows():
    # Mesmo que alguém chame `criar("windows")` direto, fora do Windows ele falha na hora, sem enviar nada.
    import os
    if os.name == "nt":
        pytest.skip("neste sistema ele existe; o teste só vale fora do Windows")
    with pytest.raises((AttributeError, OSError)):
        e2e.criar(e2e.WINDOWS)


# ----------------------------------------------------------------------------------------- guardas estáticas
def test_envio_sem_guarda_e_detectado():
    sem = "def v(amb):\n    b = amb.criar_backend()\n    b.mouse_down('left')\n"
    com = "def v(amb):\n    _ir_para(amb, j, b, 'botao')\n    b.mouse_down('left')\n"
    assert sc.envios_sem_guarda(sem) == ["v"]
    assert sc.envios_sem_guarda(com) == []
    assert sc.envios_sem_guarda(sem, isentas=frozenset({"v"})) == []
    assert sc.envios_sem_guarda("def _auxiliar(b):\n    b.type_text('x')\n") == []
    assert sc.envios_sem_guarda("def v(m):\n    m.run(mapa)\n") == ["v"]
    assert sc.envios_sem_guarda("def v(m):\n    j.sob_o_cursor_e_na_frente(1, 2)\n    m.run(mapa)\n") == []


def test_envio_antes_da_guarda_e_detectado_mesmo_com_outra_guarda_mais_adiante():
    # Achado do verificador de mutações (NET16): a função tinha duas guardas; sem a primeira, o clique do começo saía
    # sem conferência e a checagem antiga ("há alguma guarda na função?") continuava satisfeita.
    tarde = "def v(amb):\n    b.mouse_down('left')\n    _ir_para(amb, j, b, 'lista')\n    b.mouse_up('left')\n"
    assert sc.envios_sem_guarda(tarde) == ["v"]
    cedo = "def v(amb):\n    _ir_para(amb, j, b, 'botao')\n    b.mouse_down('left')\n    _ir_para(amb, j, b, 'lista')\n    b.mouse_up('left')\n"
    assert sc.envios_sem_guarda(cedo) == []
    assert sc.envios_sem_guarda("def v(m):\n    m.exigir(j.sob_o_cursor_e_na_frente(1, 2), 'x')\n    m.run(mapa)\n") == []
    assert sc.envios_sem_guarda("def v(m):\n    m.run(mapa)\n    m.exigir(j.sob_o_cursor_e_na_frente(1, 2), 'x')\n") == ["v"]


def test_toda_verificacao_e2e_confere_a_janela_antes_de_enviar_mouse_texto_ou_mapa():
    import pathlib
    caminho = pathlib.Path(e2e.__file__).with_name("verificacoes_e2e.py")
    assert sc.envios_sem_guarda(caminho.read_text(encoding="utf-8")) == []


def test_o_que_roda_simulado_tambem_roda_de_verdade_e_cada_modulo_usa_o_seu_portao():
    import ast
    import pathlib
    pasta = pathlib.Path(e2e.__file__).parents[1] / "e2e_windows"
    simulado = (pasta / "test_e2e_simulado.py").read_text(encoding="utf-8")
    real = (pasta / "test_e2e_windows_real.py").read_text(encoding="utf-8")
    assert sc.chamadas_a_verificacoes(simulado) <= sc.chamadas_a_verificacoes(real), "toda verificação simulada precisa existir no modo real"
    assert len(sc.chamadas_a_verificacoes(real)) >= 5
    for fonte, fixture in ((simulado, "ambiente_simulado"), (real, "ambiente_real")):
        assert sc.tests_without_fixture(fonte, {fixture}) == [], fixture
    marcas = [n for n in ast.walk(ast.parse(real)) if isinstance(n, ast.Attribute) and n.attr in ("windows_only", "hardware")]
    assert {n.attr for n in marcas} == {"windows_only", "hardware"}, "o módulo real precisa dos dois marcadores"
    assert "windows_only" not in simulado and "hardware" not in simulado


def test_as_verificacoes_so_usam_nomes_que_existem_nas_duas_implementacoes_e_no_programa():
    # O ambiente do Windows de verdade e o código das verificações NÃO podem ser executados aqui. Esta conferência pega o erro
    # de digitação que só apareceria na máquina do usuário: cada nome usado por uma verificação existe em AMBAS as
    # implementações (a que roda aqui e a que roda lá) e no código do produto.
    import pathlib
    testes = pathlib.Path(e2e.__file__).parent
    produto = testes.parents[1] / "automationstudio"
    verificacoes = (testes / "verificacoes_e2e.py").read_text(encoding="utf-8")
    suporte = (testes / "e2e_windows.py").read_text(encoding="utf-8")
    entrada = (produto / "input_system.py").read_text(encoding="utf-8")
    core = (produto / "core.py").read_text(encoding="utf-8")
    achados = []
    for variaveis, fonte, classes in (
            ({"amb", "ambiente"}, suporte, ["AmbienteSimulado", "AmbienteWindows"]),
            ({"janela"}, suporte, ["_JanelaSimulada", "_JanelaTk"]),
            ({"backend"}, entrada, ["Win32InputBackend"]),
            ({"motor"}, entrada, ["ExecutionEngine"]),
            ({"monitor"}, entrada, ["GlobalInputMonitor"]),
            ({"gerente"}, entrada, ["GlobalHotkeyManager"]),
            ({"leitor"}, entrada, ["WindowsProcessReadiness"]),
            ({"mapa"}, core, ["AutomationMap"])):
        usados = sc.attributes_used_on(verificacoes, variaveis)
        assert usados, variaveis
        for classe in classes:
            faltam = usados - sc.class_member_names(fonte, classe)
            if faltam:
                achados.append(f"{classe} não define {sorted(faltam)} (usado como {sorted(variaveis)})")
    assert achados == []


def test_conferencia_de_nomes_das_classes_funciona():
    fonte = "class Base:\n    def a(self):\n        self.x = 1\nclass Filha(Base):\n    y = 2\n    def b(self):\n        pass\n"
    assert sc.class_member_names(fonte, "Filha") == {"a", "x", "y", "b"}
    assert sc.class_member_names(fonte, "Base") == {"a", "x"}
    assert sc.attributes_used_on("amb.cursor()\nbackend.key_down('A')\njanela.texto", {"amb", "janela"}) == {"cursor", "texto"}
