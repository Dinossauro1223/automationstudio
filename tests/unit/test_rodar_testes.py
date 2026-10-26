"""O atalho que o Rodar_Testes.bat chama (testsupport/rodar_testes.py) também é código, e ele decide COMO a suíte roda:
com que Qt, com que variáveis de ambiente, e principalmente quando a entrada REAL do Windows pode ser ligada. Aqui ele é
testado sem rodar nada de verdade: o plano (`montar_plano`) é uma função pura, e a execução usa comandos de mentira.
"""
import contextlib
import io
import os
import pathlib
import sys
import types

import pytest

from testsupport import rodar_testes as rt

RAIZ = pathlib.Path("/projeto")
TUDO = {"pytest", "pytest_timeout", "PySide6", "coverage"}


def _tem(*presentes):
    return lambda nome: nome in presentes


def _plano(modo, extras=(), *, presentes=TUDO, ambiente=None, sistema="linux"):
    return rt.montar_plano(modo, list(extras), ambiente=ambiente if ambiente is not None else {}, tem=_tem(*presentes),
                           sistema=sistema, raiz=RAIZ)


def _tokens(passo):
    return [str(parte) for parte in passo]


# ------------------------------------------------------------------------------------------------ argumentos
@pytest.mark.parametrize("argv,modo,extras", [
    ([], "completo", []),
    (["rapido"], "rapido", []),
    (["RAPIDO"], "rapido", []),
    (["completo", "-k", "atalho", "-x"], "completo", ["-k", "atalho", "-x"]),
    (["-k", "atalho"], "completo", ["-k", "atalho"]),          # sem modo: vale o padrão e tudo vai para o executor
    (["windows"], "windows", []),
    (["mutacoes", "--area", "motor"], "mutacoes", ["--area", "motor"])],
    ids=["vazio", "rapido", "maiusculas", "extras", "so-extras", "windows", "mutacoes"])
def test_argumentos_modo_e_extras(argv, modo, extras):
    assert rt.interpretar_argumentos(argv)[:2] == (modo, extras)


@pytest.mark.parametrize("pedido", [["--help"], ["-h"], ["help"], ["?"], ["/?"], ["--help", "x"]],
                         ids=["--help", "-h", "help", "?", "/?", "help-com-extra"])
def test_pedidos_de_ajuda_viram_o_modo_ajuda(pedido):
    assert rt.interpretar_argumentos(pedido)[0] == "ajuda"


@pytest.mark.parametrize("argv,vezes,extras", [
    (["repetir"], 10, []), (["repetir", "20"], 20, []), (["repetir", "0"], 1, []),
    (["repetir", "3", "-k", "motor"], 3, ["-k", "motor"]), (["repetir", "-x"], 10, ["-x"])],
    ids=["padrao", "vinte", "zero-vira-um", "com-extras", "so-extras"])
def test_repetir_le_o_numero_de_rodadas(argv, vezes, extras):
    modo, resto, opcoes = rt.interpretar_argumentos(argv)
    assert modo == "repetir" and opcoes["vezes"] == vezes and resto == extras


def test_o_numero_so_vale_para_o_modo_repetir():
    modo, resto, opcoes = rt.interpretar_argumentos(["completo", "20"])
    assert resto == ["20"] and opcoes["vezes"] == 10


def test_sim_e_consumido_e_nao_chega_ao_executor():
    modo, extras, opcoes = rt.interpretar_argumentos(["windows", "--sim", "-x"])
    assert modo == "windows" and extras == ["-x"] and opcoes["sim"] is True
    assert rt.interpretar_argumentos(["windows"])[2]["sim"] is False


# ------------------------------------------------------------------------------------------------ comando do executor
def test_executor_pytest_com_timeout_e_junit():
    comando = rt.comando_do_executor(["-k", "x"], tem_pytest=True, tem_timeout=True, raiz=RAIZ, timeout_s=77)
    assert comando[:3] == [sys.executable, "-m", "pytest"]
    assert "--timeout=77" in comando and "--junitxml=logs/tests_last_run.xml" in comando
    assert comando[-2:] == ["-k", "x"], "os argumentos extras vão por último"


def test_executor_pytest_sem_o_plugin_de_timeout_nao_passa_a_opcao():
    comando = rt.comando_do_executor([], tem_pytest=True, tem_timeout=False, raiz=RAIZ)
    assert not any(parte.startswith("--timeout") for parte in comando)


def test_executor_pytest_sem_junit_quando_pedido():
    comando = rt.comando_do_executor([], tem_pytest=True, tem_timeout=True, junit=False, raiz=RAIZ)
    assert not any("junitxml" in parte for parte in comando)


def test_sem_pytest_usa_o_executor_minimo_do_projeto():
    comando = _tokens(rt.comando_do_executor(["-k", "x"], tem_pytest=False, tem_timeout=False, raiz=RAIZ))
    assert comando[0] == sys.executable
    assert pathlib.PurePath(comando[1]) == RAIZ / "tests" / "testsupport" / "run_minimal.py"
    assert comando[2:] == ["-q", "-k", "x"]


# ------------------------------------------------------------------------------------------------ planos: rápido e completo
def test_rapido_usa_o_qt_de_mentira_e_so_a_logica():
    plano = _plano("rapido", ["-x"])
    assert plano.erro == "" and plano.env["AS_TEST_QT_STUB"] == "1"
    (passo,) = plano.passos
    assert "pytest" in passo and passo[-1] == "-x"
    assert plano.log == "tests_last_run.txt" and plano.confirmar == ""


def test_completo_com_pyside6_usa_o_qt_de_verdade_mesmo_se_o_terminal_tinha_o_stub_ligado():
    plano = _plano("completo", ambiente={"AS_TEST_QT_STUB": "1"})
    assert "AS_TEST_QT_STUB" not in plano.env
    assert "PySide6" in plano.descricao and plano.avisos == []


def test_completo_sem_pyside6_usa_o_duble_de_widgets_e_avisa():
    plano = _plano("completo", presentes={"pytest", "pytest_timeout"})
    assert plano.env["AS_TEST_QT_STUB"] == "widgets"
    assert any("PySide6" in aviso for aviso in plano.avisos)


def test_sem_pytest_avisa_e_cai_no_executor_minimo():
    plano = _plano("completo", presentes={"PySide6"})
    (passo,) = plano.passos
    assert any("run_minimal.py" in str(parte) for parte in passo) and "pytest" not in passo
    assert any("pytest" in aviso for aviso in plano.avisos)


def test_repetir_monta_o_mesmo_plano_que_o_completo():
    assert _plano("repetir").passos == _plano("completo").passos


# ------------------------------------------------------------------------------------------------ planos: janela principal isolada
def _isolado(plano):
    (passo,) = [p for p in plano.passos if isinstance(p, rt.PassoIsolado)]
    return passo


def test_completo_com_pyside6_roda_a_janela_principal_um_teste_por_processo():
    plano = _plano("completo")
    principal, isolado = plano.passos
    tokens = _tokens(principal)
    assert tokens[-2:] == ["-m", "not isolado"], "o passo comum não leva os testes da janela principal"
    assert "--junitxml=logs/tests_last_run.xml" in tokens and "--timeout=180" in tokens
    assert isinstance(isolado, rt.PassoIsolado) and "um teste por processo" in plano.descricao


def test_o_passo_isolado_roda_um_nodeid_por_vez_sem_selecao_e_com_tempo_menor():
    isolado = _isolado(_plano("completo"))
    comando, coleta = _tokens(isolado.comando), _tokens(isolado.coleta)
    assert "-m" not in comando[3:] and not any("junitxml" in parte for parte in comando), "o nodeid é acrescentado ao fim"
    assert f"--timeout={rt.LIMITE_ISOLADO_S - 30}" in comando
    assert "--collect-only" in coleta and coleta[3:][coleta[3:].index("-m") + 1] == "isolado"
    assert isolado.limite_s == rt.LIMITE_ISOLADO_S


def test_o_tempo_do_lancador_e_maior_que_o_do_vigia_e_o_do_pytest_fica_entre_os_dois():
    vigia = rt.diag.LIMITE_PADRAO_S
    assert vigia < rt.LIMITE_ISOLADO_S - 30 < rt.LIMITE_ISOLADO_S, "vigia (relatório) < pytest-timeout < lançador (mata)"


def test_extras_valem_para_o_passo_comum_e_para_a_coleta_mas_nao_para_cada_teste_isolado():
    plano = _plano("completo", ["-k", "atalho"])
    principal, isolado = plano.passos
    assert _tokens(principal)[-4:] == ["-k", "atalho", "-m", "not isolado"]
    assert "atalho" in _tokens(isolado.coleta) and "atalho" not in _tokens(isolado.comando)


def test_um_marcador_do_usuario_e_combinado_e_nao_substituido():
    # com dois `-m` o pytest só vale o último: o passo isolado tentaria rodar a suíte inteira, um teste por processo
    assert rt.combinar_marcador(["-m", "not slow"], "isolado") == ["-m", "(not slow) and (isolado)"]
    assert rt.combinar_marcador(["-m", "gui", "-x"], "not isolado") == ["-m", "(gui) and (not isolado)", "-x"]
    assert rt.combinar_marcador(["-mgui"], "isolado") == ["-m", "(gui) and (isolado)"]
    assert rt.combinar_marcador(["-k", "x"], "isolado") == ["-k", "x", "-m", "isolado"]
    assert rt.combinar_marcador([], "isolado") == ["-m", "isolado"]


def test_sem_pyside6_ou_sem_pytest_ou_no_rapido_nada_e_isolado():
    for presentes, modo in (({"pytest", "pytest_timeout"}, "completo"), ({"PySide6"}, "completo"), (TUDO, "rapido")):
        plano = _plano(modo, presentes=presentes)
        assert not any(isinstance(passo, rt.PassoIsolado) for passo in plano.passos), (presentes, modo)
        assert not any("not isolado" in parte for passo in plano.passos for parte in _tokens(passo)), (presentes, modo)


def test_os_relatorios_de_travamento_de_uma_rodada_anterior_sao_apagados_antes_de_comecar():
    plano = _plano("completo")
    assert f"logs/{rt.diag.ARQUIVO_DO_RELATORIO}" in plano.apagar_antes
    assert f"logs/{rt.diag.ARQUIVO_DO_ALARME_NATIVO}" in plano.apagar_antes


def test_o_codigo_do_vigia_e_o_mesmo_nos_dois_lados():
    assert rt.diag.CODIGO_DE_TRAVAMENTO == 86
    assert rt.classificar(86, False, False, []) == "TRAVOU"


# ------------------------------------------------------------------------------------------------ planos: entrada real
@pytest.mark.parametrize("modo", ["rapido", "completo", "repetir", "cobertura", "mutacoes"])
def test_so_o_modo_windows_pode_ligar_a_entrada_real(modo):
    sujo = {"AS_ALLOW_REAL_INPUT": "1", "AS_ATUALIZAR_GOLDEN": "1", "AS_ROOT": "/outro", "AS_MUTACAO_EM_CURSO": "1"}
    plano = _plano(modo, ambiente=sujo, sistema="win32")
    assert plano.erro == ""
    for nome in sujo:
        assert nome not in plano.env, f"o modo {modo} herdou {nome} do terminal"


def test_modo_windows_liga_a_entrada_real_so_no_windows_e_pede_confirmacao():
    plano = _plano("windows", ambiente={"AS_TEST_QT_STUB": "1"}, sistema="win32")
    assert plano.erro == ""
    assert plano.env["AS_ALLOW_REAL_INPUT"] == "1" and "AS_TEST_QT_STUB" not in plano.env
    assert plano.confirmar and "NÃO MEXA" in plano.confirmar
    (passo,) = plano.passos
    assert "tests/e2e_windows" in passo and not any("junitxml" in str(parte) for parte in passo)
    assert plano.log == "tests_windows_last_run.txt"


@pytest.mark.parametrize("sistema", ["linux", "darwin"])
def test_modo_windows_fora_do_windows_nao_roda_e_nao_liga_nada(sistema):
    plano = _plano("windows", sistema=sistema)
    assert plano.erro and "Windows" in plano.erro and plano.passos == []
    assert "AS_ALLOW_REAL_INPUT" not in plano.env


def test_o_plano_nao_altera_o_ambiente_recebido():
    ambiente = {"AS_ALLOW_REAL_INPUT": "1", "OUTRA": "x"}
    _plano("windows", ambiente=ambiente, sistema="win32")
    assert ambiente == {"AS_ALLOW_REAL_INPUT": "1", "OUTRA": "x"}


def test_o_ambiente_das_rodadas_forca_utf8():
    plano = _plano("completo")
    assert plano.env["PYTHONIOENCODING"] == "utf-8" and plano.env["PYTHONUTF8"] == "1"


# ------------------------------------------------------------------------------------------------ planos: cobertura, mutações
def test_cobertura_sem_o_pacote_coverage_explica_como_instalar():
    plano = _plano("cobertura", presentes={"pytest", "PySide6"})
    assert "coverage" in plano.erro and "requirements-dev.txt" in plano.erro and plano.passos == []


def test_cobertura_mede_linhas_e_ramos_do_pacote_e_depois_junta_os_dados_e_imprime_o_relatorio():
    plano = _plano("cobertura", ["-x"])
    rodar, isolado, juntar, relatorio = plano.passos[0], plano.passos[1], plano.passos[2], plano.passos[3]
    rodar = _tokens(rodar)
    assert rodar[1:4] == ["-m", "coverage", "run"] and "--branch" in rodar and "--source=automationstudio" in rodar
    assert "-p" in rodar, "cada processo grava o seu arquivo de dados; o `combine` os junta"
    assert "-x" in rodar and rodar[-2:] == ["-m", "not isolado"] and "pytest" in rodar
    assert isinstance(isolado, rt.PassoIsolado) and "-p" in _tokens(isolado.comando) and "coverage" in _tokens(isolado.comando)
    assert _tokens(juntar)[1:] == ["-m", "coverage", "combine"]
    assert _tokens(relatorio)[1:] == ["-m", "coverage", "report", "-m"]
    assert pathlib.PurePath(plano.env["COVERAGE_FILE"]) == RAIZ / "logs" / ".coverage"
    assert plano.log == "coverage_last_run.txt"
    assert "logs/.coverage*" in plano.apagar_antes, "dados de uma rodada anterior não podem entrar na medição desta"


def test_cobertura_inteira_gera_o_json_e_confere_a_catraca_depois_do_relatorio():
    plano = _plano("cobertura")
    rodar, isolado, juntar, relatorio, json_do_coverage, catraca = plano.passos
    assert _tokens(rodar)[1:4] == ["-m", "coverage", "run"] and _tokens(relatorio)[1:] == ["-m", "coverage", "report", "-m"]
    assert _tokens(juntar)[1:] == ["-m", "coverage", "combine"]
    json_do_coverage, catraca = _tokens(json_do_coverage), _tokens(catraca)
    assert json_do_coverage[1:4] == ["-m", "coverage", "json"] and json_do_coverage[4] == "-o"
    assert pathlib.PurePath(json_do_coverage[5]) == RAIZ / "logs" / "coverage.json"
    assert pathlib.PurePath(catraca[1]) == RAIZ / "tests" / "testsupport" / "catraca_cobertura.py"
    assert catraca[2] == "--json" and pathlib.PurePath(catraca[3]) == pathlib.PurePath(json_do_coverage[5])
    assert "catraca" in plano.descricao and plano.avisos == []


def test_cobertura_sem_pyside6_nao_tem_passo_isolado_mas_tambem_junta_os_dados():
    plano = _plano("cobertura", presentes={"pytest", "coverage"})
    assert not any(isinstance(passo, rt.PassoIsolado) for passo in plano.passos)
    assert [_tokens(passo)[3] for passo in plano.passos[:3]] == ["run", "combine", "report"]


def test_cobertura_com_argumentos_extras_e_parcial_entao_a_catraca_nao_roda_e_o_aviso_diz_por_que():
    plano = _plano("cobertura", ["-k", "atalho"])
    comuns = [passo for passo in plano.passos if not isinstance(passo, rt.PassoIsolado)]
    assert len(comuns) == 3, "rodar, juntar e relatório"
    assert not any("catraca_cobertura" in parte for passo in comuns for parte in _tokens(passo))
    assert any("catraca" in aviso and "parcial" in aviso for aviso in plano.avisos)


def test_mutacoes_chama_o_verificador_com_os_argumentos_extras():
    plano = _plano("mutacoes", ["--area", "motor"])
    (passo,) = _tokens(plano.passos[0]),
    assert pathlib.PurePath(passo[1]) == RAIZ / "tests" / "testsupport" / "mutacoes.py"
    assert passo[2:] == ["--area", "motor"]
    assert plano.log == "mutacoes_last_run_console.txt"


def test_instalar_chama_o_pip_com_o_requirements_de_teste_e_nao_reclama_do_pytest_ausente():
    plano = _plano("instalar", presentes=set())
    passo = _tokens(plano.passos[0])
    assert passo == [sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"]
    assert plano.avisos == [] and plano.log == "instalar_last_run.txt"


def test_o_requirements_de_teste_pede_o_que_o_atalho_usa():
    texto = (pathlib.Path(__file__).resolve().parents[2] / "requirements-dev.txt").read_text(encoding="utf-8")
    pedidos = {linha.split(">")[0].split("=")[0].strip() for linha in texto.splitlines() if linha.strip() and not linha.startswith("-")}
    assert {"pytest", "pytest-timeout", "coverage"} <= pedidos, pedidos


def test_modo_desconhecido_e_recusado_com_a_lista_de_modos():
    plano = _plano("inventado")
    assert "inventado" in plano.erro and all(modo in plano.erro for modo in rt.MODOS) and plano.passos == []


# ------------------------------------------------------------------------------------------------ execução
def _passo(codigo_python):
    return [sys.executable, "-c", codigo_python]


def _ambiente_utf8():
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def _capturando(funcao, *args):
    """(resultado, o que foi impresso): a captura do pytest (`capsys`) não existe no executor mínimo do projeto."""
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        resultado = funcao(*args)
    return resultado, saida.getvalue()


def test_executar_mostra_a_saida_grava_o_log_e_devolve_o_codigo(tmp_path):
    plano = rt.Plano(passos=[_passo("print('olá, é ç')")], env=_ambiente_utf8(), log="saida.txt")
    codigo, impresso = _capturando(rt.executar_passos, plano, tmp_path)
    assert codigo == 0
    assert "olá, é ç" in impresso
    assert "olá, é ç" in (tmp_path / "logs" / "saida.txt").read_text(encoding="utf-8")


def test_executar_devolve_o_primeiro_codigo_que_falhou_mas_roda_os_passos_seguintes(tmp_path):
    # na cobertura, o relatório precisa sair mesmo quando algum teste falhou
    plano = rt.Plano(passos=[_passo("import sys; print('um'); sys.exit(3)"), _passo("print('dois')"),
                             _passo("import sys; sys.exit(5)")], env=_ambiente_utf8(), log="saida.txt")
    codigo, _impresso = _capturando(rt.executar_passos, plano, tmp_path)
    assert codigo == 3
    log = (tmp_path / "logs" / "saida.txt").read_text(encoding="utf-8")
    assert "um" in log and "dois" in log


def test_executar_roda_na_raiz_do_projeto(tmp_path):
    plano = rt.Plano(passos=[_passo("import os; print(os.getcwd())")], env=_ambiente_utf8(), log="x.txt")
    _capturando(rt.executar_passos, plano, tmp_path)
    primeira_linha = (tmp_path / "logs" / "x.txt").read_text(encoding="utf-8").splitlines()[0]
    assert os.path.samefile(primeira_linha, tmp_path)


# ------------------------------------------------------------------------------------------------ execução: isolamento, retomada, resumo
# O "teste" de mentira: o nome do nodeid, depois de `::`, diz o que o processo filho faz.
_FILHO = """
import pathlib, sys, threading
nodeid = sys.argv[1]
raiz = pathlib.Path.cwd()


def relatorio(arquivo, texto):
    (raiz / "logs").mkdir(exist_ok=True)
    with open(raiz / "logs" / arquivo, "a", encoding="utf-8") as saida:
        saida.write(texto)


fim = nodeid.rsplit("::", 1)[1]
if fim == "ok":
    print("1 passed in 0.01s")
elif fim == "pulado":
    print("1 skipped in 0.01s")
elif fim == "falha":
    print("F")
    sys.exit(1)
elif fim.startswith("vigia"):
    relatorio("travamento_qt.txt", "TESTE: " + nodeid + " (call)\\n")
    sys.exit(86)
elif fim == "nativo":
    relatorio("travamento_qt_nativo.txt", "Thread 0x1 (most recent call first):\\n")
    sys.exit(1)
elif fim == "queda":
    sys.exit(3)
elif fim == "para_sempre":
    threading.Event().wait(60)
"""


def _coleta(*nomes):
    return [sys.executable, "-c", "print(" + repr("\n".join(f"tests/x.py::{nome}" for nome in nomes)) + ")"]


def _isolado_de_mentira(*nomes, limite_s=30):
    return rt.PassoIsolado(comando=[sys.executable, "-c", _FILHO], coleta=_coleta(*nomes), limite_s=limite_s)


def _rodar_isolado(passo, raiz):
    raiz.mkdir(parents=True, exist_ok=True)
    with open(raiz / "log.txt", "w", encoding="utf-8") as arquivo:
        return _capturando(rt.executar_isolado, passo, raiz, _ambiente_utf8(), arquivo)[0]


def test_isolado_classifica_cada_teste_e_continua_depois_de_uma_falha_ou_travamento(tmp_path):
    passo = _isolado_de_mentira("ok", "falha", "vigia", "nativo", "queda", "pulado")
    codigo, registros = _rodar_isolado(passo, tmp_path)
    assert [(r["nodeid"].split("::")[1], r["estado"]) for r in registros] == [
        ("ok", "OK"), ("falha", "FALHOU"), ("vigia", "TRAVOU"), ("nativo", "TRAVOU"), ("queda", "QUEDA"), ("pulado", "PULADO")]
    assert codigo == 1, "houve falha de teste: o código é o da falha, e não o do travamento"


@pytest.mark.parametrize("nomes", [("vigia", "falha"), ("falha", "vigia"), ("vigia", "queda"), ("queda", "ok", "vigia")],
                         ids=["travou-e-depois-falhou", "falhou-e-depois-travou", "travou-e-depois-caiu", "caiu-e-depois-travou"])
def test_isolado_uma_falha_vale_mais_que_um_travamento_seja_qual_for_a_ordem(tmp_path, nomes):
    codigo, _registros = _rodar_isolado(_isolado_de_mentira(*nomes), tmp_path)
    assert codigo == 1, "o código 86 só vale quando NADA falhou além dos travamentos (o RESUMO lista os dois)"


def test_isolado_so_com_travamento_devolve_o_codigo_do_vigia(tmp_path):
    codigo, registros = _rodar_isolado(_isolado_de_mentira("ok", "vigia"), tmp_path)
    assert codigo == rt.diag.CODIGO_DE_TRAVAMENTO and [r["estado"] for r in registros] == ["OK", "TRAVOU"]


def test_isolado_desiste_depois_de_tres_travamentos_seguidos_e_conta_os_que_nao_rodaram(tmp_path):
    passo = _isolado_de_mentira("vigia1", "vigia2", "vigia3", "ok", "ok2")
    codigo, registros = _rodar_isolado(passo, tmp_path)
    assert [(r["nodeid"].split("::")[1], r["estado"]) for r in registros] == [
        ("vigia1", "TRAVOU"), ("vigia2", "TRAVOU"), ("vigia3", "TRAVOU"), ("ok", "NAO_RODOU"), ("ok2", "NAO_RODOU")]
    assert codigo == rt.diag.CODIGO_DE_TRAVAMENTO
    assert rt.LIMITE_DE_TRAVAMENTOS_SEGUIDOS == 3
    log = (tmp_path / "log.txt").read_text(encoding="utf-8")
    assert "3 travamentos seguidos" in log and "2 testes NÃO RODARAM" in log
    assert "1 passed" not in log, "os testes que faltavam não podem ter rodado"


def test_isolado_travamentos_que_nao_sao_seguidos_nao_param_o_passo(tmp_path):
    passo = _isolado_de_mentira("vigia1", "vigia2", "ok", "vigia3", "vigia4", "ok2")
    _codigo, registros = _rodar_isolado(passo, tmp_path)
    assert [r["estado"] for r in registros] == ["TRAVOU", "TRAVOU", "OK", "TRAVOU", "TRAVOU", "OK"], \
        "um teste que passa zera a contagem de travamentos seguidos"


def test_isolado_o_terceiro_travamento_no_ultimo_teste_nao_deixa_nada_sem_rodar(tmp_path):
    _codigo, registros = _rodar_isolado(_isolado_de_mentira("ok", "vigia1", "vigia2", "vigia3"), tmp_path)
    assert [r["estado"] for r in registros] == ["OK", "TRAVOU", "TRAVOU", "TRAVOU"]


def test_o_resumo_do_passo_isolado_conta_os_que_nao_rodaram_sem_listar_um_por_um():
    registros = [{"nodeid": "tests/x.py::a", "estado": "TRAVOU", "segundos": 60.0},
                 {"nodeid": "tests/x.py::b", "estado": "TRAVOU", "segundos": 60.0},
                 {"nodeid": "tests/x.py::c", "estado": "TRAVOU", "segundos": 60.0},
                 {"nodeid": "tests/x.py::d", "estado": "NAO_RODOU", "segundos": 0.0},
                 {"nodeid": "tests/x.py::e", "estado": "NAO_RODOU", "segundos": 0.0}]
    resultado = rt._resultado_do_isolado(rt.PassoIsolado(comando=[], coleta=[]), registros)
    assert resultado.estado == "TRAVOU"
    assert "3 TRAVOU" in resultado.resumo and "2 NÃO RODOU" in resultado.resumo and "(de 5)" in resultado.resumo
    assert len(resultado.detalhes) == 4, "os 3 que travaram, um por um, e uma só linha para os que não rodaram"
    assert "2 testes NÃO RODARAM" in resultado.detalhes[-1] and "tests/x.py::d" not in "\n".join(resultado.detalhes)


def test_isolado_tudo_certo_devolve_zero(tmp_path):
    assert _rodar_isolado(_isolado_de_mentira("ok", "pulado"), tmp_path)[0] == 0


def test_isolado_mata_o_processo_que_passa_do_tempo_e_segue_para_o_proximo(tmp_path):
    codigo, registros = _rodar_isolado(_isolado_de_mentira("para_sempre", "ok", limite_s=1), tmp_path)
    assert [r["estado"] for r in registros] == ["TRAVOU", "OK"], "o teste que passou do tempo não pode levar o seguinte junto"
    assert codigo == rt.diag.CODIGO_DE_TRAVAMENTO
    assert registros[0]["segundos"] < 20


def test_isolado_junta_o_relatorio_do_alarme_nativo_ao_relatorio_principal_e_apaga_o_dele(tmp_path):
    _rodar_isolado(_isolado_de_mentira("nativo"), tmp_path)
    logs = tmp_path / "logs"
    assert not (logs / rt.diag.ARQUIVO_DO_ALARME_NATIVO).exists()
    texto = (logs / rt.diag.ARQUIVO_DO_RELATORIO).read_text(encoding="utf-8")
    assert "ALARME NATIVO" in texto and "Thread 0x1" in texto


def test_isolado_sem_nenhum_teste_coletado_nao_e_falha(tmp_path):
    passo = rt.PassoIsolado(comando=[sys.executable, "-c", _FILHO], coleta=[sys.executable, "-c", "print('no tests collected')"])
    assert _rodar_isolado(passo, tmp_path) == (0, [])


def test_isolado_coleta_que_falha_e_falha_da_rodada(tmp_path):
    passo = rt.PassoIsolado(comando=[sys.executable, "-c", _FILHO], coleta=[sys.executable, "-c", "import sys; print('ERRO de importacao'); sys.exit(2)"])
    codigo, registros = _rodar_isolado(passo, tmp_path)
    assert codigo == 2 and [(r["nodeid"], r["estado"]) for r in registros] == [("(coleta)", "FALHOU")]


def test_o_relatorio_so_devolve_o_texto_novo(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    relatorio = logs / rt.diag.ARQUIVO_DO_RELATORIO
    relatorio.write_text("velho\n", encoding="utf-8")
    tamanho = relatorio.stat().st_size
    assert rt._recolher_relatorios(tmp_path, tamanho) == ""
    with open(relatorio, "a", encoding="utf-8") as saida:
        saida.write("novo\n")
    assert rt._recolher_relatorios(tmp_path, tamanho) == "novo\n"


# --- passo comum que trava: roda de novo sem o teste que travou
_RETOMADA = """
import pathlib, sys
raiz = pathlib.Path.cwd()
(raiz / "logs").mkdir(exist_ok=True)
marca = raiz / "chamadas.txt"
chamadas = (int(marca.read_text()) if marca.exists() else 0) + 1
marca.write_text(str(chamadas))
(raiz / f"argumentos_{chamadas}.txt").write_text(" | ".join(sys.argv[1:]), encoding="utf-8")
if "--deselect" in sys.argv and not "teimoso" in sys.argv:
    print("1 passed in 0.01s")
    sys.exit(0)
with open(raiz / "logs" / "travamento_qt.txt", "a", encoding="utf-8") as saida:
    saida.write("TESTE: tests/x.py::test_y[a (b)] (call)\\n")
print("travou")
sys.exit(86)
"""


def _passo_que_trava(*extras):
    return [sys.executable, "-c", _RETOMADA, "pytest", *extras]  # o "pytest" solto marca o passo como do pytest


def test_passo_que_trava_roda_de_novo_sem_o_teste_que_travou_e_a_rodada_nao_fica_limpa(tmp_path):
    plano = rt.Plano(passos=[_passo_que_trava()], env=_ambiente_utf8(), log="saida.txt")
    codigo, impresso = _capturando(rt.executar_passos, plano, tmp_path)
    assert (tmp_path / "chamadas.txt").read_text() == "2"
    assert (tmp_path / "argumentos_2.txt").read_text(encoding="utf-8") == "pytest | --deselect | tests/x.py::test_y[a (b)]"
    assert codigo == rt.diag.CODIGO_DE_TRAVAMENTO, "o que sobrou passou, mas houve travamento: não é uma rodada limpa"
    assert "TRAVOU" in impresso and "tests/x.py::test_y[a (b)]" in impresso and "RESUMO DA RODADA" in impresso


def test_passo_que_trava_sempre_desiste_depois_das_tentativas(tmp_path):
    plano = rt.Plano(passos=[_passo_que_trava("teimoso")], env=_ambiente_utf8(), log="saida.txt")
    codigo, _impresso = _capturando(rt.executar_passos, plano, tmp_path)
    assert (tmp_path / "chamadas.txt").read_text() == str(rt.TENTATIVAS_DE_RETOMADA + 1)
    assert codigo == rt.diag.CODIGO_DE_TRAVAMENTO


def test_passo_que_nao_e_do_pytest_nao_e_repetido_quando_deixa_relatorio(tmp_path):
    passo = [sys.executable, "-c", _RETOMADA]  # sem o "pytest": `--deselect` não significaria nada
    plano = rt.Plano(passos=[passo], env=_ambiente_utf8(), log="saida.txt")
    codigo, _impresso = _capturando(rt.executar_passos, plano, tmp_path)
    assert (tmp_path / "chamadas.txt").read_text() == "1" and codigo == rt.diag.CODIGO_DE_TRAVAMENTO


def test_relatorios_de_uma_rodada_anterior_sao_apagados_antes_de_comecar(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / rt.diag.ARQUIVO_DO_RELATORIO).write_text("TESTE: velho (call)\n", encoding="utf-8")
    (logs / ".coverage.maquina.1.2").write_text("x", encoding="utf-8")
    plano = rt.Plano(passos=[_passo("print('ok')")], env=_ambiente_utf8(), log="saida.txt",
                     apagar_antes=[f"logs/{rt.diag.ARQUIVO_DO_RELATORIO}", "logs/.coverage*"])
    codigo, _ = _capturando(rt.executar_passos, plano, tmp_path)
    assert codigo == 0
    assert not (logs / rt.diag.ARQUIVO_DO_RELATORIO).exists() and not (logs / ".coverage.maquina.1.2").exists()


def test_rodada_completa_comum_mais_isolado_imprime_o_resumo_e_grava_no_log(tmp_path):
    plano = rt.Plano(passos=[[sys.executable, "-c", "print('1353 passed, 31 skipped in 61.2s')", "pytest"],
                             _isolado_de_mentira("ok", "falha", "para_sempre", limite_s=1)],
                     env=_ambiente_utf8(), log="saida.txt")
    codigo, impresso = _capturando(rt.executar_passos, plano, tmp_path)
    assert codigo == 1
    log = (tmp_path / "logs" / "saida.txt").read_text(encoding="utf-8")
    for texto in (impresso, log):
        assert "RESUMO DA RODADA" in texto
        assert "1353 passed, 31 skipped in 61.2s" in texto
        assert "1 OK, 1 FALHOU, 1 TRAVOU (de 3)" in texto
        assert "FALHOU  tests/x.py::falha" in texto and "TRAVOU  tests/x.py::para_sempre" in texto
        assert "Código de saída: 1" in texto and "travamento_qt.txt" in texto


def test_codigo_5_do_pytest_so_e_falha_se_nada_rodou_em_lugar_nenhum(tmp_path):
    vazio = [sys.executable, "-c", "import sys; print('no tests ran in 0.01s'); sys.exit(5)", "pytest"]
    com_isolado = rt.Plano(passos=[vazio, _isolado_de_mentira("ok")], env=_ambiente_utf8(), log="a.txt")
    assert _capturando(rt.executar_passos, com_isolado, tmp_path)[0] == 0, "o passo comum vazio, mas o isolado rodou um teste"
    so_vazio = rt.Plano(passos=[vazio], env=_ambiente_utf8(), log="b.txt")
    assert _capturando(rt.executar_passos, so_vazio, tmp_path)[0] == 5
    nada = rt.Plano(passos=[vazio, rt.PassoIsolado(comando=[sys.executable, "-c", _FILHO], coleta=[sys.executable, "-c", "print('x')"])],
                    env=_ambiente_utf8(), log="c.txt")
    assert _capturando(rt.executar_passos, nada, tmp_path)[0] == 5


@pytest.mark.parametrize("codigo,estourou,relatorio,linhas,esperado", [
    (0, False, False, ["1 passed in 0.5s"], "OK"),
    (0, False, False, ["1 skipped in 0.5s"], "PULADO"),
    (0, False, False, ["1 passed, 1 skipped in 0.5s"], "OK"),
    (0, False, False, [], "OK"),
    (1, False, False, ["1 failed in 0.5s"], "FALHOU"),
    (86, False, False, [], "TRAVOU"),
    (None, True, False, [], "TRAVOU"),
    (-9, True, False, [], "TRAVOU"),
    (1, False, True, [], "TRAVOU"),
    (3221225477, False, False, [], "QUEDA"),
    (5, False, False, [], "QUEDA")],
    ids=["ok", "pulado", "ok-com-pulado", "ok-sem-resumo", "falhou", "vigia", "estourou", "morto", "alarme-nativo-sai-com-1",
         "queda-do-qt", "nada-coletado"])
def test_classificar_o_resultado_de_um_teste_isolado(codigo, estourou, relatorio, linhas, esperado):
    assert rt.classificar(codigo, estourou, relatorio, linhas) == esperado


@pytest.mark.parametrize("linhas,esperado", [
    (["tests/a.py ..", "1353 passed, 31 skipped, 5 xfailed in 61.2s"], "1353 passed, 31 skipped, 5 xfailed in 61.2s"),
    (["=========== 5 passed, 2 skipped in 1.20s ==========="], "5 passed, 2 skipped in 1.20s"),
    (["no tests ran in 0.01s"], "no tests ran in 0.01s"),
    (["1 failed, 3 passed in 0.50s", "lixo depois"], "1 failed, 3 passed in 0.50s"),
    (["nada que pareça resumo"], ""),
    ([], "")],
    ids=["q", "enfeitado", "nada-rodou", "ultima-linha-valida", "sem-resumo", "vazio"])
def test_ultima_linha_de_resumo_do_pytest(linhas, esperado):
    assert rt.ultima_linha_de_resumo(linhas) == esperado


def test_resumo_mostra_cada_passo_o_codigo_e_o_que_enviar():
    texto = rt.montar_resumo([rt.ResultadoDePasso("testes comuns", "OK", "10 passed in 1s"),
                              rt.ResultadoDePasso("janela principal", "TRAVOU", "2 OK, 1 TRAVOU (de 3)", ["TRAVOU  tests/x.py::t  (61.0 s)"])],
                             "tests_last_run.txt", 86)
    assert "[OK    ] testes comuns: 10 passed in 1s" in texto
    assert "[TRAVOU] janela principal: 2 OK, 1 TRAVOU (de 3)" in texto and "TRAVOU  tests/x.py::t  (61.0 s)" in texto
    assert "Código de saída: 86" in texto and "tests_last_run.txt" in texto and "travamento_qt.txt" in texto
    sem_travamento = rt.montar_resumo([rt.ResultadoDePasso("testes", "OK", "1 passed in 1s")], "tests_last_run.txt", 0)
    assert "travamento_qt.txt" not in sem_travamento


# ------------------------------------------------------------------------------------------------ principal
def _trocar_a_execucao(monkeypatch, codigos=()):
    """Troca a execução de verdade por um registro; `codigos` é a fila de códigos de saída a devolver."""
    registro = types.SimpleNamespace(planos=[], codigos=list(codigos))

    def falso(plano, raiz=rt.RAIZ):
        registro.planos.append(plano)
        return registro.codigos.pop(0) if registro.codigos else 0

    monkeypatch.setattr(rt, "executar_passos", falso)
    return registro


def _como_sistema(monkeypatch, nome):
    """A partir daí o plano é montado como se o programa rodasse nesse sistema."""
    original = rt.montar_plano
    monkeypatch.setattr(rt, "montar_plano", lambda modo, extras, **kw: original(modo, extras, sistema=nome, **kw))


def _responder(monkeypatch, resposta):
    def entrada(*_):
        if isinstance(resposta, BaseException):
            raise resposta
        return resposta

    monkeypatch.setattr("builtins.input", entrada)


def test_principal_ajuda_mostra_os_modos_e_nao_executa_nada(monkeypatch):
    execucoes = _trocar_a_execucao(monkeypatch)
    codigo, impresso = _capturando(rt.principal, ["--help"])
    assert codigo == 0
    assert all(modo in impresso for modo in ("rapido", "completo", "windows", "repetir", "cobertura", "mutacoes"))
    assert execucoes.planos == []


def test_principal_modo_impossivel_devolve_2_e_nao_executa(monkeypatch):
    execucoes = _trocar_a_execucao(monkeypatch)
    _como_sistema(monkeypatch, "linux")
    codigo, impresso = _capturando(rt.principal, ["windows"])
    assert codigo == 2 and "Não dá para rodar" in impresso and execucoes.planos == []


def test_principal_devolve_o_codigo_da_execucao(monkeypatch):
    execucoes = _trocar_a_execucao(monkeypatch, [4])
    assert _capturando(rt.principal, ["rapido"])[0] == 4 and len(execucoes.planos) == 1


@pytest.mark.parametrize("resposta", ["nao", "", "sim?", "s", "SIM SIM"], ids=["nao", "vazio", "quase", "s", "dobrado"])
def test_modo_windows_so_comeca_depois_do_SIM(monkeypatch, resposta):
    execucoes = _trocar_a_execucao(monkeypatch)
    _como_sistema(monkeypatch, "win32")
    _responder(monkeypatch, resposta)
    codigo, impresso = _capturando(rt.principal, ["windows"])
    assert codigo == 2 and "Cancelado" in impresso
    assert execucoes.planos == [], "enviou entrada de verdade sem confirmação"


def test_modo_windows_sem_terminal_para_responder_cancela(monkeypatch):
    execucoes = _trocar_a_execucao(monkeypatch)
    _como_sistema(monkeypatch, "win32")
    _responder(monkeypatch, EOFError())
    assert _capturando(rt.principal, ["windows"])[0] == 2 and execucoes.planos == []


@pytest.mark.parametrize("resposta", ["SIM", "sim", "  Sim  "], ids=["maiusculo", "minusculo", "com-espacos"])
def test_modo_windows_roda_depois_do_SIM(monkeypatch, resposta):
    execucoes = _trocar_a_execucao(monkeypatch)
    _como_sistema(monkeypatch, "win32")
    _responder(monkeypatch, resposta)
    assert _capturando(rt.principal, ["windows"])[0] == 0
    (plano,) = execucoes.planos
    assert plano.env["AS_ALLOW_REAL_INPUT"] == "1"


def test_modo_windows_com_sim_na_linha_de_comando_nao_pergunta(monkeypatch):
    execucoes = _trocar_a_execucao(monkeypatch)
    _como_sistema(monkeypatch, "win32")
    _responder(monkeypatch, AssertionError("perguntou apesar do --sim"))
    assert _capturando(rt.principal, ["windows", "--sim"])[0] == 0 and len(execucoes.planos) == 1


def test_repetir_roda_n_vezes_seguidas(monkeypatch):
    execucoes = _trocar_a_execucao(monkeypatch)
    codigo, impresso = _capturando(rt.principal, ["repetir", "4"])
    assert codigo == 0 and len(execucoes.planos) == 4 and "OK: 4 rodadas" in impresso


def test_repetir_para_na_primeira_falha(monkeypatch):
    execucoes = _trocar_a_execucao(monkeypatch, [0, 0, 1, 0, 0])
    codigo, impresso = _capturando(rt.principal, ["repetir", "5"])
    assert codigo == 1 and "FALHOU na rodada 3" in impresso
    assert len(execucoes.planos) == 3, "continuou depois da falha"
