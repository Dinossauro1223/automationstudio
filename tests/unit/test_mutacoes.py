"""O verificador de mutações (testsupport/mutacoes.py) também é código: se ele estivesse quebrado, "nenhum defeito
sobreviveu" não significaria nada. Aqui ele é testado SEM rodar a suíte inteira (isso é o que ele mesmo faz): a troca de
texto, a recusa de defeito ambíguo, a leitura da saída do executor, a classificação morto/sobreviveu/inválido, o
ambiente das rodadas (nunca envia entrada de verdade) e o catálogo contra o código real.
"""
import contextlib
import io
import json
import os
import pathlib

import pytest

from testsupport import mutacoes as mut
from testsupport.mutacoes import ErroDeMutante, Mutante

ROOT = pathlib.Path(os.environ.get("AS_ROOT") or pathlib.Path(__file__).resolve().parents[2])


def _m(**campos) -> Mutante:
    base = dict(id="T01", area="teste", descricao="d", protege="p", arquivo="x.py")
    base.update(campos)
    return Mutante(**base)


# ------------------------------------------------------------------------------------------------ troca de texto
def test_troca_o_trecho_exato():
    assert mut.aplicar_no_texto("a b c", _m(antes="b", depois="X")) == "a X c"


def test_trecho_ausente_e_recusado():
    with pytest.raises(ErroDeMutante, match="0 vez"):
        mut.aplicar_no_texto("a b c", _m(antes="z", depois="X"))


def test_trecho_ambiguo_e_recusado_em_vez_de_plantado_no_lugar_errado():
    with pytest.raises(ErroDeMutante, match="2 vez"):
        mut.aplicar_no_texto("b b", _m(antes="b", depois="X"))


def test_ocorrencia_escolhe_qual_trocar():
    assert mut.aplicar_no_texto("b b b", _m(antes="b", depois="X", total=3, ocorrencia=1)) == "X b b"
    assert mut.aplicar_no_texto("b b b", _m(antes="b", depois="X", total=3, ocorrencia=3)) == "b b X"


def test_ocorrencia_inexistente_e_recusada():
    with pytest.raises(ErroDeMutante, match="ocorrência 3"):
        mut.aplicar_no_texto("b b", _m(antes="b", depois="X", total=2, ocorrencia=3))


def test_defeito_que_nao_muda_nada_e_recusado():
    with pytest.raises(ErroDeMutante, match="não muda nada"):
        mut.aplicar_no_texto("a b", _m(antes="b", depois="b"))


def test_acrescentar_e_funcao():
    assert mut.aplicar_no_texto("x = 1\n", _m(acrescentar="y = 2")) == "x = 1\n\ny = 2\n"
    assert mut.aplicar_no_texto("abc", _m(funcao=lambda t: t.upper())) == "ABC"


def test_defeito_sem_trecho_nem_funcao_e_recusado():
    with pytest.raises(ErroDeMutante, match="sem trecho"):
        mut.aplicar_no_texto("abc", _m())


# ------------------------------------------------------------------------------------------------ arquivos
def test_codigo_que_nao_compila_e_recusado(tmp_path):
    (tmp_path / "x.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    with pytest.raises(ErroDeMutante, match="não compila"):
        mut.aplicar(tmp_path, _m(antes="    return 1", depois="  return ("))


def test_fim_de_linha_do_windows_e_preservado_e_o_trecho_de_varias_linhas_confere(tmp_path):
    (tmp_path / "x.py").write_bytes(b"a = 1\r\nb = 2\r\nc = 3\r\n")
    mut.aplicar(tmp_path, _m(antes="a = 1\nb = 2", depois="a = 10\nb = 20"))
    assert (tmp_path / "x.py").read_bytes() == b"a = 10\r\nb = 20\r\nc = 3\r\n"


def test_arquivo_binario_e_arquivo_novo_e_apagar(tmp_path):
    (tmp_path / "x.bat").write_bytes(b"a\r\nb\r\n")
    mut.aplicar(tmp_path, _m(arquivo="x.bat", binario=True, funcao=lambda b: b.replace(b"\r\n", b"\n")))
    assert (tmp_path / "x.bat").read_bytes() == b"a\nb\n"
    mut.aplicar(tmp_path, _m(arquivo="novo/y.txt", novos_arquivos=(("novo/y.txt", "oi"),)))
    assert (tmp_path / "novo" / "y.txt").read_text(encoding="utf-8") == "oi"
    mut.aplicar(tmp_path, _m(arquivo="novo/y.txt", apagar=True))
    assert not (tmp_path / "novo" / "y.txt").exists()


def test_arquivo_que_nao_existe_e_recusado(tmp_path):
    with pytest.raises(ErroDeMutante, match="não existe"):
        mut.aplicar(tmp_path, _m(antes="a", depois="b"))


# ------------------------------------------------------------------------------------------------ saída do executor
_SAIDA = (
    "FALHOU  engine/test_a.py::test_um[x-1]\n          -> AssertionError: 1 != 2  [test_a.py:9]\n"
    "FALHOU  unit/test_b.py (erro de coleta)\n          -> ImportError: x\n"
    "PULADO  gui/test_c.py::test_tres\n          -> sem Qt\n"
    "XFAIL   persistence/test_d.py::test_quatro\n          -> defeito conhecido\n"
    "\nRESUMO: 800 passou, 2 falhou, 30 pulado, 5 xfail (esperado), 0 xpass\n")


def test_a_saida_do_executor_vira_conjunto_de_falhas_e_contagens():
    falhas, contagens = mut.analisar_saida(_SAIDA)
    assert falhas == {"engine/test_a.py::test_um[x-1]", "unit/test_b.py (erro de coleta)"}
    assert contagens == {"passou": 800, "falhou": 2, "pulado": 30, "xfail": 5}


def test_saida_cortada_sem_resumo_nao_tem_contagens():
    falhas, contagens = mut.analisar_saida("FALHOU  a.py::t\n")
    assert falhas == {"a.py::t"} and contagens is None


# ------------------------------------------------------------------------------------------------ classificação
_OK = {"passou": 10, "falhou": 0, "pulado": 0, "xfail": 0}


def test_morto_quando_algum_teste_que_passava_passa_a_falhar():
    assert mut.classificar({"a::t1"}, set(), _OK, False) == ("morto", ["a::t1"])


def test_sobreviveu_quando_nenhum_teste_novo_falha():
    assert mut.classificar(set(), set(), _OK, False) == ("sobreviveu", [])


def test_o_que_ja_falhava_sem_defeito_nao_conta_como_defeito_pego():
    assert mut.classificar({"a::velho"}, {"a::velho"}, _OK, False) == ("sobreviveu", [])
    assert mut.classificar({"a::velho", "a::novo"}, {"a::velho"}, _OK, False) == ("morto", ["a::novo"])


def test_rodada_que_nao_terminou_e_invalida_e_a_que_travou_e_morta():
    assert mut.classificar(set(), set(), None, False) == ("invalido", [])
    status, quem = mut.classificar(set(), set(), None, True)
    assert status == "morto" and "travou" in quem[0]


# ------------------------------------------------------------------------------------------------ ambiente da rodada
def test_as_rodadas_nunca_enviam_entrada_de_verdade_nem_regravam_referencias(monkeypatch, tmp_path):
    for nome in ("AS_ALLOW_REAL_INPUT", "AS_ATUALIZAR_GOLDEN"):
        monkeypatch.setenv(nome, "1")
    monkeypatch.setenv("AS_ROOT", "/outro/lugar")
    monkeypatch.setenv("AS_TEST_QT_STUB", "widgets")
    env = mut.ambiente_da_rodada(tmp_path, mut.LOGICA)
    assert "AS_ALLOW_REAL_INPUT" not in env and "AS_ATUALIZAR_GOLDEN" not in env
    assert env["AS_ROOT"] == str(tmp_path), "a rodada precisa usar a cópia com o defeito, não outro projeto"
    assert env["AS_TEST_QT_STUB"] == "1" and env["AS_MUTACAO_EM_CURSO"] == "1" and env["AS_FORCE_MINIMAL_RUNNER"] == "1"


def test_defeito_de_interface_usa_o_duble_ou_o_qt_de_verdade_conforme_o_modo(monkeypatch, tmp_path):
    monkeypatch.setattr(mut, "modo_da_interface", lambda: "widgets")
    assert mut.ambiente_da_rodada(tmp_path, mut.INTERFACE)["AS_TEST_QT_STUB"] == "widgets"
    monkeypatch.setattr(mut, "modo_da_interface", lambda: "")
    assert "AS_TEST_QT_STUB" not in mut.ambiente_da_rodada(tmp_path, mut.INTERFACE)


def test_o_padrao_da_interface_e_o_duble_e_o_qt_de_verdade_so_com_o_pedido_explicito(monkeypatch):
    # Na rodada de 18/10/2026 um teste da janela principal travou no Qt de verdade; o verificador não isola testes um por
    # processo, então o Qt de verdade só entra quando alguém pede (AS_MUTACOES_QT_REAL=1) e o PySide6 existe.
    import importlib.util
    monkeypatch.delenv("AS_MUTACOES_QT_REAL", raising=False)
    assert mut.modo_da_interface() == "widgets", "mesmo com o PySide6 instalado, o padrão é o dublê"
    for valor in ("0", "", "sim", "true"):
        monkeypatch.setenv("AS_MUTACOES_QT_REAL", valor)
        assert mut.modo_da_interface() == "widgets", valor
    monkeypatch.setenv("AS_MUTACOES_QT_REAL", "1")
    tem_pyside6 = importlib.util.find_spec("PySide6") is not None
    assert mut.modo_da_interface() == ("" if tem_pyside6 else "widgets")


# ------------------------------------------------------------------------------------------------ orquestração
def _projeto_de_mentira(tmp_path):
    raiz = tmp_path / "proj"
    (raiz / "automationstudio").mkdir(parents=True)
    (raiz / "automationstudio" / "x.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    return raiz


def _referencia(falhas=()):
    return {mut.LOGICA: {"falhas": set(falhas), "contagens": _OK}}


def test_executar_um_classifica_morto_sobreviveu_e_invalido(tmp_path, monkeypatch):
    raiz = _projeto_de_mentira(tmp_path)
    defeito = _m(arquivo="automationstudio/x.py", antes="return 1", depois="return 2")
    monkeypatch.setattr(mut, "importa_sem_erro", lambda copia, modo: "")

    monkeypatch.setattr(mut, "rodar_suite", lambda copia, modo: ({"t::falhou"}, _OK, False, ""))
    r = mut.executar_um(raiz, defeito, _referencia())
    assert (r.status, r.mortos_por) == ("morto", ["t::falhou"])

    monkeypatch.setattr(mut, "rodar_suite", lambda copia, modo: (set(), _OK, False, ""))
    assert mut.executar_um(raiz, defeito, _referencia()).status == "sobreviveu"

    monkeypatch.setattr(mut, "importa_sem_erro", lambda copia, modo: "NameError: x")
    r = mut.executar_um(raiz, defeito, _referencia())
    assert r.status == "invalido" and "NameError" in r.detalhe

    monkeypatch.setattr(mut, "importa_sem_erro", lambda copia, modo: "")
    r = mut.executar_um(raiz, _m(arquivo="automationstudio/x.py", antes="nao existe", depois="y"), _referencia())
    assert r.status == "invalido" and "0 vez" in r.detalhe


def test_o_codigo_original_nunca_e_tocado_pela_rodada(tmp_path, monkeypatch):
    raiz = _projeto_de_mentira(tmp_path)
    original = (raiz / "automationstudio" / "x.py").read_text(encoding="utf-8")
    monkeypatch.setattr(mut, "importa_sem_erro", lambda copia, modo: "")
    vistos = []

    def suite(copia, modo):
        vistos.append((copia / "automationstudio" / "x.py").read_text(encoding="utf-8"))
        return set(), _OK, False, ""

    monkeypatch.setattr(mut, "rodar_suite", suite)
    mut.executar_um(raiz, _m(arquivo="automationstudio/x.py", antes="return 1", depois="return 2"), _referencia())
    assert vistos == ["def f():\n    return 2\n"], "a suíte deve ver o defeito"
    assert (raiz / "automationstudio" / "x.py").read_text(encoding="utf-8") == original, "o original não pode mudar"


def test_a_copia_descartavel_e_apagada_ao_fim(tmp_path, monkeypatch):
    raiz = _projeto_de_mentira(tmp_path)
    copias = []
    monkeypatch.setattr(mut, "importa_sem_erro", lambda copia, modo: "")
    monkeypatch.setattr(mut, "rodar_suite", lambda copia, modo: (copias.append(copia), (set(), _OK, False, ""))[1])
    mut.executar_um(raiz, _m(arquivo="automationstudio/x.py", antes="return 1", depois="return 2"), _referencia())
    assert copias and not copias[0].exists()


# ------------------------------------------------------------------------------------------------ progresso e retomada
def _projeto_para_main(tmp_path):
    raiz = _projeto_de_mentira(tmp_path)
    (raiz / "automationstudio" / "__init__.py").write_text('__version__ = "9.9"\n', encoding="utf-8")
    return raiz


def _main_com_dubles(monkeypatch, raiz, *args, falha_em=None):
    """Roda `main` sem rodar suíte nenhuma. Devolve (código, executados, rodadas_de_referência, o que foi impresso)."""
    executados, referencias, saida = [], [], io.StringIO()

    def executar_um(raiz_, m, refs, manter=False):
        if falha_em == m.id:
            raise KeyboardInterrupt
        executados.append(m.id)
        return mut.Resultado(m, "morto", ["t::x"], "", 0.5)

    def referencia(raiz_, modos):
        referencias.append(sorted(modos))
        return {modo: {"falhas": set(), "contagens": _OK} for modo in modos}

    monkeypatch.setattr(mut, "validar", lambda raiz_, catalogo: [])
    monkeypatch.setattr(mut, "executar_um", executar_um)
    monkeypatch.setattr(mut, "rodada_de_referencia", referencia)
    with contextlib.redirect_stdout(saida):
        codigo = mut.main(["--raiz", str(raiz), "--paralelo", "1", *args])
    return codigo, executados, referencias, saida.getvalue()


def _linhas_do_progresso(raiz):
    return [json.loads(linha) for linha in (raiz / "logs" / "mutacoes_progresso.jsonl").read_text(encoding="utf-8").splitlines()]


def test_cada_resultado_e_gravado_no_progresso_assim_que_sai(tmp_path, monkeypatch):
    raiz = _projeto_para_main(tmp_path)
    codigo, executados, _refs, _saida = _main_com_dubles(monkeypatch, raiz, "--so", "MOT01,MOT02")
    assert codigo == 0 and sorted(executados) == ["MOT01", "MOT02"]
    linhas = _linhas_do_progresso(raiz)
    assert [l["tipo"] for l in linhas] == ["cabecalho", "referencia", "resultado", "resultado"]
    assert linhas[0]["impressao"] == mut.impressao_digital(raiz)
    assert sorted(l["id"] for l in linhas if l["tipo"] == "resultado") == ["MOT01", "MOT02"]
    assert linhas[1]["modo"] == "logica" and linhas[1]["contagens"] == _OK


def test_retomar_nao_repete_o_que_ja_tem_resultado_nem_a_rodada_de_referencia(tmp_path, monkeypatch):
    raiz = _projeto_para_main(tmp_path)
    _main_com_dubles(monkeypatch, raiz, "--so", "MOT01,MOT02,MOT03")
    codigo, executados, referencias, saida = _main_com_dubles(monkeypatch, raiz, "--retomar", "--so", "MOT01,MOT02,MOT03,MOT04")
    assert codigo == 0
    assert executados == ["MOT04"], "só o que faltava pode rodar"
    assert referencias == [], "a referência gravada vale para o mesmo projeto"
    assert "Retomando: 3 defeitos" in saida and "Retomada: 3 dos 4 resultados" in saida
    relatorio = (raiz / "logs" / "mutacoes_last_run.txt").read_text(encoding="utf-8")
    assert all(id_ in relatorio for id_ in ("MOT01", "MOT02", "MOT03", "MOT04")), "o relatório tem os quatro"
    assert sorted(l["id"] for l in _linhas_do_progresso(raiz) if l["tipo"] == "resultado") == ["MOT01", "MOT02", "MOT03", "MOT04"]


def test_retomar_so_conta_os_defeitos_pedidos(tmp_path, monkeypatch):
    raiz = _projeto_para_main(tmp_path)
    _main_com_dubles(monkeypatch, raiz, "--so", "MOT01,MOT02,MOT03")
    codigo, executados, _refs, saida = _main_com_dubles(monkeypatch, raiz, "--retomar", "--so", "MOT02")
    assert codigo == 0 and executados == [] and "RESUMO: 1 mortos, 0 sobreviveram, 0 inválidos (de 1)" in saida


def test_retomar_e_recusado_quando_o_projeto_mudou_desde_o_progresso(tmp_path, monkeypatch):
    raiz = _projeto_para_main(tmp_path)
    _main_com_dubles(monkeypatch, raiz, "--so", "MOT01")
    (raiz / "automationstudio" / "x.py").write_text("def f():\n    return 3\n", encoding="utf-8")  # mudou um arquivo
    codigo, executados, referencias, saida = _main_com_dubles(monkeypatch, raiz, "--retomar", "--so", "MOT01,MOT02")
    assert codigo == 2 and executados == [] and referencias == []
    assert "Não dá para retomar" in saida and "mutacoes_progresso.jsonl" in saida


def test_retomar_aguenta_a_ultima_linha_cortada_por_uma_rodada_morta_no_meio_da_gravacao(tmp_path, monkeypatch):
    raiz = _projeto_para_main(tmp_path)
    _main_com_dubles(monkeypatch, raiz, "--so", "MOT01")
    with open(raiz / "logs" / "mutacoes_progresso.jsonl", "a", encoding="utf-8") as arquivo:
        arquivo.write('{"tipo": "resultado", "id": "MOT0')  # cortada
    codigo, executados, _refs, saida = _main_com_dubles(monkeypatch, raiz, "--retomar", "--so", "MOT01,MOT02")
    assert codigo == 0 and executados == ["MOT02"] and "Retomando: 1 defeitos" in saida


def test_retomar_sem_progresso_comeca_do_zero(tmp_path, monkeypatch):
    raiz = _projeto_para_main(tmp_path)
    codigo, executados, _refs, saida = _main_com_dubles(monkeypatch, raiz, "--retomar", "--so", "MOT01,MOT02")
    assert codigo == 0 and sorted(executados) == ["MOT01", "MOT02"] and "Nada a retomar" in saida


def test_sem_retomar_a_rodada_recomeca_e_o_progresso_antigo_e_descartado(tmp_path, monkeypatch):
    raiz = _projeto_para_main(tmp_path)
    _main_com_dubles(monkeypatch, raiz, "--so", "MOT01,MOT02")
    _codigo, executados, referencias, _saida = _main_com_dubles(monkeypatch, raiz, "--so", "MOT01")
    assert executados == ["MOT01"] and referencias == [["logica"]]
    assert [l.get("id") for l in _linhas_do_progresso(raiz) if l["tipo"] == "resultado"] == ["MOT01"]


def test_interrupcao_devolve_130_e_o_que_ja_saiu_fica_gravado_para_a_retomada(tmp_path, monkeypatch):
    raiz = _projeto_para_main(tmp_path)
    codigo, executados, _refs, saida = _main_com_dubles(monkeypatch, raiz, "--so", "MOT01,MOT02,MOT03", falha_em="MOT02")
    assert codigo == 130 and executados[0] == "MOT01" and "Interrompido" in saida and "--retomar" in saida
    # (o terceiro pode ter começado na thread antes de o laço principal ver a interrupção; o que conta é o que foi gravado)
    assert [l["id"] for l in _linhas_do_progresso(raiz) if l["tipo"] == "resultado"] == ["MOT01"]
    codigo, executados, _refs, _saida = _main_com_dubles(monkeypatch, raiz, "--retomar", "--so", "MOT01,MOT02,MOT03")
    assert codigo == 0 and sorted(executados) == ["MOT02", "MOT03"]


def test_a_impressao_digital_muda_com_o_conteudo_e_ignora_logs_e_caches(tmp_path):
    raiz = _projeto_de_mentira(tmp_path)
    antes = mut.impressao_digital(raiz)
    assert mut.impressao_digital(raiz) == antes, "determinística"
    (raiz / "logs").mkdir()
    (raiz / "logs" / "saida.txt").write_text("ruído", encoding="utf-8")
    (raiz / "automationstudio" / "__pycache__").mkdir()
    (raiz / "automationstudio" / "__pycache__" / "x.pyc").write_bytes(b"\0\1")
    assert mut.impressao_digital(raiz) == antes, "logs e caches não contam"
    (raiz / "automationstudio" / "x.py").write_text("def f():\n    return 1  \n", encoding="utf-8")
    assert mut.impressao_digital(raiz) != antes, "um espaço a mais já conta"
    (raiz / "automationstudio" / "x.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    assert mut.impressao_digital(raiz) == antes
    (raiz / "novo.py").write_text("", encoding="utf-8")
    assert mut.impressao_digital(raiz) != antes, "arquivo novo conta"


def test_o_progresso_de_um_defeito_que_saiu_do_catalogo_e_ignorado(tmp_path):
    raiz = _projeto_de_mentira(tmp_path)
    impressao = mut.impressao_digital(raiz)
    arquivo = tmp_path / "progresso.jsonl"
    mut.iniciar_progresso(arquivo, impressao, "9.9")
    conhecido = _m(id="K1")
    mut.gravar_no_progresso(arquivo, mut.dados_do_resultado(mut.Resultado(conhecido, "sobreviveu", [], "", 1.0)))
    mut.gravar_no_progresso(arquivo, mut.dados_do_resultado(mut.Resultado(_m(id="SUMIU"), "morto", ["t"], "", 1.0)))
    (resultado,), _refs = mut.ler_progresso(arquivo, impressao, {"K1": conhecido})
    assert (resultado.mutante.id, resultado.status) == ("K1", "sobreviveu")


# ------------------------------------------------------------------------------------------------ relatório
def test_o_relatorio_destaca_os_sobreviventes_e_conta_os_mortos():
    a, b = _m(id="A1"), _m(id="B2", protege="o que importa")
    resultados = [mut.Resultado(a, "morto", ["t1", "t2", "t3", "t4"], "", 1.0), mut.Resultado(b, "sobreviveu", [], "", 2.0)]
    texto = mut.relatorio(resultados, {mut.LOGICA: {"falhas": set(), "contagens": _OK}}, 60.0, "9.9")
    assert "RESUMO: 1 mortos, 1 sobreviveram, 0 inválidos (de 2)" in texto
    assert "SOBREVIVENTES: B2" in texto and "BURACO NA SUÍTE" in texto and "o que importa" in texto
    assert "(+1)" in texto, "só os três primeiros testes são listados"
    assert texto.index("SOBREVIVEU") < texto.index("MORTO"), "o que sobreviveu vem primeiro"


# ------------------------------------------------------------------------------------------------ o catálogo
def test_o_catalogo_tem_ids_unicos_areas_conhecidas_e_explicacao():
    catalogo = mut.catalogo()
    ids = [m.id for m in catalogo]
    assert len(catalogo) >= 150 and len(ids) == len(set(ids))
    areas = {"motor", "win32", "pynput", "atalhos", "botoes", "gravador", "modelo", "persistencia", "editor", "redes", "estatico",
             "ativacao", "controle"}
    assert {m.area for m in catalogo} <= areas and {m.area for m in catalogo} == areas, "toda área tem defeitos"
    assert all(m.descricao and m.protege for m in catalogo)
    assert {m.modo for m in catalogo} == {mut.LOGICA, mut.INTERFACE}


def test_a_tabela_em_markdown_tem_uma_linha_por_defeito():
    catalogo = mut.catalogo()
    linhas = mut.tabela_markdown(catalogo).strip().splitlines()
    assert len(linhas) == len(catalogo) + 2 and linhas[0].startswith("| Id |")


def test_todo_defeito_do_catalogo_ainda_se_aplica_ao_codigo_atual():
    # Sem isto o catálogo apodreceria em silêncio: o código muda, o trecho some e o defeito deixaria de ser plantado.
    # Não roda dentro de uma rodada do próprio verificador (o código ali já tem um defeito) nem contra outra versão do código.
    if os.environ.get("AS_MUTACAO_EM_CURSO"):
        pytest.skip("dentro de uma rodada do verificador de mutações")
    if os.environ.get("AS_ROOT"):
        pytest.skip("AS_ROOT aponta para outra versão do código: o catálogo descreve a versão deste pacote")
    assert mut.validar(ROOT, mut.catalogo()) == []


def test_o_catalogo_nao_planta_defeito_em_arquivo_que_nao_e_do_projeto():
    for m in mut.catalogo():
        caminho = pathlib.PurePosixPath(m.arquivo)
        assert not caminho.is_absolute() and ".." not in caminho.parts, m.id
        assert caminho.parts[0] in {"automationstudio", "tests", "Iniciar.bat", "Instalar_Dependencias_Global.bat", "pytest.ini"}, (m.id, m.arquivo)


def test_nenhum_defeito_mira_o_proprio_verificador():
    assert not any(m.arquivo.endswith("mutacoes.py") for m in mut.catalogo())
