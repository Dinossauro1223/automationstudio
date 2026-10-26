"""A catraca de cobertura (testsupport/catraca_cobertura.py) decide se a cobertura caiu. Como é ela que avisa quando um teste some
ou quando o código novo chega sem teste, ela mesma é testada: aqui com relatórios de mentira no formato do `coverage json`, sem rodar
o coverage.py (que o ambiente de desenvolvimento deste projeto não tem). O formato do relatório real é a premissa que só a primeira
rodada de `Rodar_Testes.bat cobertura` na sua máquina confirma.
"""
import json
import pathlib

import pytest

from automationstudio import core
from testsupport import catraca_cobertura as cc


def _arquivo(cobertas, instrucoes, ramos_cobertos=0, ramos=0):
    return {"summary": {"covered_lines": cobertas, "num_statements": instrucoes, "covered_branches": ramos_cobertos,
                        "num_branches": ramos, "percent_covered": 0.0}}


def _relatorio(caminhos):
    """`caminhos`: caminho como o coverage o escreve -> o resumo do arquivo."""
    return {"meta": {"version": "7.6.0"}, "files": dict(caminhos)}


def _simples(**modulos):
    return _relatorio({f"automationstudio/{nome}.py": dados for nome, dados in modulos.items()})


def _linha(percentual):
    return {"cobertas": 0, "total": 0, "percentual": percentual}


# ------------------------------------------------------------------------------------------------ resumir
def test_resumir_soma_instrucoes_e_ramos_de_cada_grupo_e_calcula_o_total():
    resumo = cc.resumir(_simples(core=_arquivo(60, 80, 20, 40), main_window=_arquivo(30, 100), command_editor=_arquivo(70, 100)))
    assert resumo["core"] == {"cobertas": 80, "total": 120, "percentual": 66.67}
    assert resumo["interface"] == {"cobertas": 100, "total": 200, "percentual": 50.0}
    assert resumo["total"] == {"cobertas": 180, "total": 320, "percentual": 56.25}
    assert sorted(resumo) == ["core", "interface", "total"]


@pytest.mark.parametrize("caminho", [
    "automationstudio/core.py", "automationstudio\\core.py", "C:\\Users\\eu\\Automation Studio\\automationstudio\\core.py",
    "/home/eu/projeto/automationstudio/core.py", "automationstudio/automationstudio/core.py"],
    ids=["relativo", "windows", "windows-absoluto", "linux-absoluto", "pasta-com-o-mesmo-nome"])
def test_o_caminho_do_relatorio_e_reconhecido_como_o_modulo_core(caminho):
    assert cc.modulo_do_pacote(caminho) == "core"
    assert cc.resumir(_relatorio({caminho: _arquivo(1, 2)}))["core"]["percentual"] == 50.0


@pytest.mark.parametrize("caminho", ["tests/conftest.py", "automationstudio/sub/y.py", "automationstudio/dados.txt", "outro/core.py"],
                         ids=["teste", "subpasta", "nao-python", "fora-do-pacote"])
def test_arquivo_que_nao_e_um_modulo_do_pacote_nao_conta(caminho):
    assert cc.modulo_do_pacote(caminho) is None


def test_init_e_arquivos_de_fora_do_pacote_nao_entram_na_conta():
    resumo = cc.resumir(_relatorio({"automationstudio/__init__.py": _arquivo(1, 1), "tests/x.py": _arquivo(0, 50),
                                    "automationstudio/core.py": _arquivo(3, 4)}))
    assert resumo["total"] == {"cobertas": 3, "total": 4, "percentual": 75.0}


def test_modulo_novo_que_nenhum_grupo_conhece_cai_em_outros_e_entra_no_total():
    resumo = cc.resumir(_simples(core=_arquivo(1, 2), modulo_novo=_arquivo(0, 2)))
    assert resumo["outros"]["percentual"] == 0.0
    assert resumo["total"] == {"cobertas": 1, "total": 4, "percentual": 25.0}


def test_arquivo_sem_nenhuma_instrucao_conta_como_totalmente_coberto():
    assert cc.resumir(_simples(vision=_arquivo(0, 0)))["vision"]["percentual"] == 100.0


@pytest.mark.parametrize("relatorio", [
    {}, {"files": []}, {"files": {}}, {"files": {"tests/x.py": _arquivo(1, 2)}}, [],
    {"files": {"automationstudio/core.py": {}}}, {"files": {"automationstudio/core.py": {"summary": {"covered_lines": 1}}}},
    {"files": {"automationstudio/core.py": {"summary": {"covered_lines": "x", "num_statements": 2}}}}],
    ids=["vazio", "lista-no-lugar-de-dict", "sem-arquivos", "so-arquivo-de-fora", "nao-e-objeto", "sem-resumo", "sem-instrucoes",
         "texto-no-lugar-do-numero"])
def test_relatorio_que_nao_serve_levanta_erro_em_vez_de_inventar_numeros(relatorio):
    with pytest.raises(ValueError):
        cc.resumir(relatorio)


def test_todo_modulo_do_pacote_pertence_a_um_grupo_da_catraca():
    # Um módulo novo precisa dizer a que grupo pertence; senão ele cai em "outros" e a régua dele fica misturada com as demais.
    modulos = {arquivo.stem for arquivo in pathlib.Path(core.__file__).resolve().parent.glob("*.py")} - cc.IGNORADOS
    sem_grupo = sorted(modulo for modulo in modulos if cc.grupo_do_modulo(modulo) == cc.OUTROS)
    assert sem_grupo == [], f"módulos do pacote sem grupo em catraca_cobertura.GRUPOS: {sem_grupo}"
    assert all(modulo in modulos for modulos_do_grupo in cc.GRUPOS.values() for modulo in modulos_do_grupo), \
        "um grupo da catraca cita um módulo que não existe mais no pacote"


# ------------------------------------------------------------------------------------------------ comparar
BASELINE = {"core": _linha(80.0), "project": _linha(70.0), "total": _linha(60.0)}


def _agora(core_=80.0, project=70.0, total=60.0):
    return {"core": _linha(core_), "project": _linha(project), "total": _linha(total)}


@pytest.mark.parametrize("agora", [_agora(), _agora(95.0, 99.0, 90.0), _agora(79.0), _agora(80.0, 69.0, 59.0)],
                         ids=["igual", "melhor", "queda-dentro-da-tolerancia", "queda-exata-na-tolerancia-em-varias"])
def test_nada_que_cai_ate_a_tolerancia_e_problema(agora):
    assert cc.comparar(BASELINE, agora, 1.0) == []


def test_queda_acima_da_tolerancia_e_problema_e_o_texto_diz_qual_parte():
    problemas = cc.comparar(BASELINE, _agora(core_=78.9), 1.0)
    assert len(problemas) == 1 and problemas[0].startswith("core:") and "78.9" in problemas[0] and "80.0" in problemas[0]


def test_cada_parte_que_caiu_aparece_uma_vez():
    problemas = cc.comparar(BASELINE, _agora(core_=50.0, project=10.0, total=40.0), 1.0)
    assert [p.split(":")[0] for p in problemas] == ["core", "project", "total"]


def test_parte_que_sumiu_da_medicao_e_problema():
    problemas = cc.comparar(BASELINE, {"core": _linha(80.0), "total": _linha(60.0)}, 1.0)
    assert len(problemas) == 1 and problemas[0].startswith("project:") and "sumiu" in problemas[0]


def test_parte_nova_que_o_baseline_nao_tinha_nao_e_problema():
    assert cc.comparar(BASELINE, {**_agora(), "vision": _linha(0.0)}, 1.0) == []


def test_a_tolerancia_pedida_vale():
    assert cc.comparar(BASELINE, _agora(core_=75.0), 5.0) == []
    assert cc.comparar(BASELINE, _agora(core_=74.9), 5.0) != []


def test_melhorias_listam_so_o_que_subiu_mais_que_a_margem():
    assert cc.melhorias(BASELINE, _agora(core_=82.1, project=71.9, total=60.0), 2.0) == ["core: 80.0% -> 82.1%"]
    assert cc.melhorias(BASELINE, _agora(core_=82.0), 2.0) == []
    assert cc.melhorias(BASELINE, {**_agora(), "vision": _linha(90.0)}, 2.0) == []


# ------------------------------------------------------------------------------------------------ baseline em arquivo
def test_baseline_gravado_e_lido_volta_igual(tmp_path):
    resumo = cc.resumir(_simples(core=_arquivo(60, 80, 20, 40)))
    cc.gravar_baseline(tmp_path / "sub" / "base.json", resumo, "7.6.0")
    gravado = json.loads((tmp_path / "sub" / "base.json").read_text(encoding="utf-8"))
    assert gravado["formato"] == 1 and gravado["coverage"] == "7.6.0" and gravado["grupos"] == resumo
    assert cc.ler_baseline(tmp_path / "sub" / "base.json") == resumo


def test_baseline_que_nao_existe_e_none(tmp_path):
    assert cc.ler_baseline(tmp_path / "nao_existe.json") is None


@pytest.mark.parametrize("texto", ["", "{ nao e json", "[]", "{}", '{"grupos": []}', '{"grupos": {}}', '{"grupos": {"core": 3}}',
                                   '{"grupos": {"core": {"percentual": "x"}}}', '{"grupos": {"core": {}}}'],
                         ids=["vazio", "nao-json", "lista", "sem-grupos", "grupos-lista", "grupos-vazio", "grupo-numero",
                              "percentual-texto", "grupo-sem-percentual"])
def test_baseline_ilegivel_levanta_erro_que_diz_como_resolver(tmp_path, texto):
    (tmp_path / "base.json").write_text(texto, encoding="utf-8")
    with pytest.raises(ValueError) as info:
        cc.ler_baseline(tmp_path / "base.json")
    assert "--gravar" in str(info.value) and "base.json" in str(info.value)


# ------------------------------------------------------------------------------------------------ o script de ponta a ponta
class _Cobertura:
    """Uma pasta de trabalho com um relatório do coverage de mentira e a saída capturada do script."""

    def __init__(self, pasta):
        self.json, self.baseline = pasta / "coverage.json", pasta / "baseline.json"
        self.saida = []

    def escrever(self, **modulos):
        self.json.write_text(json.dumps(_simples(**modulos)), encoding="utf-8")

    def rodar(self, *extras):
        self.saida.clear()
        codigo = cc.principal(["--json", str(self.json), "--baseline", str(self.baseline), *extras], saida=self.saida.append)
        return codigo, "\n".join(self.saida)


def test_primeira_rodada_grava_o_baseline_e_passa(tmp_path):
    c = _Cobertura(tmp_path)
    c.escrever(core=_arquivo(80, 100), project=_arquivo(70, 100))
    codigo, texto = c.rodar()
    assert codigo == 0 and "Baseline gravado" in texto
    assert cc.ler_baseline(c.baseline)["core"]["percentual"] == 80.0


def test_rodada_igual_passa_sem_mexer_no_baseline(tmp_path):
    c = _Cobertura(tmp_path)
    c.escrever(core=_arquivo(80, 100))
    c.rodar()
    antes = c.baseline.read_bytes()
    codigo, texto = c.rodar()
    assert codigo == 0 and "OK" in texto and c.baseline.read_bytes() == antes


def test_queda_reprova_diz_qual_parte_e_nao_regrava_o_baseline(tmp_path):
    c = _Cobertura(tmp_path)
    c.escrever(core=_arquivo(80, 100), project=_arquivo(70, 100))
    c.rodar()
    antes = c.baseline.read_bytes()
    c.escrever(core=_arquivo(60, 100), project=_arquivo(70, 100))
    codigo, texto = c.rodar()
    assert codigo == 1 and "COBERTURA CAIU" in texto and "core:" in texto and "project:" not in texto
    assert c.baseline.read_bytes() == antes


def test_queda_dentro_da_tolerancia_passa(tmp_path):
    c = _Cobertura(tmp_path)
    c.escrever(core=_arquivo(80, 100))
    c.rodar()
    c.escrever(core=_arquivo(79, 100))
    assert c.rodar()[0] == 0
    assert c.rodar("--tolerancia", "0.5")[0] == 1


def test_gravar_regrava_o_baseline_mesmo_depois_de_uma_queda(tmp_path):
    c = _Cobertura(tmp_path)
    c.escrever(core=_arquivo(80, 100))
    c.rodar()
    c.escrever(core=_arquivo(60, 100))
    codigo, texto = c.rodar("--gravar")
    assert codigo == 0 and "regravado" in texto
    assert cc.ler_baseline(c.baseline)["core"]["percentual"] == 60.0
    assert c.rodar()[0] == 0


def test_melhora_grande_sugere_subir_a_catraca(tmp_path):
    c = _Cobertura(tmp_path)
    c.escrever(core=_arquivo(60, 100))
    c.rodar()
    c.escrever(core=_arquivo(90, 100))
    codigo, texto = c.rodar()
    assert codigo == 0 and "--gravar" in texto and "core: 60.0% -> 90.0%" in texto


def test_a_tabela_mostra_cada_parte_com_o_baseline_e_a_diferenca(tmp_path):
    c = _Cobertura(tmp_path)
    c.escrever(core=_arquivo(80, 100))
    c.rodar()
    c.escrever(core=_arquivo(85, 100))
    _codigo, texto = c.rodar()
    linha_do_core = next(linha for linha in texto.splitlines() if linha.strip().startswith("core"))
    assert "85.0%" in linha_do_core and "80.0%" in linha_do_core and "+5.0" in linha_do_core


def test_sem_relatorio_pede_para_rodar_a_cobertura_e_nao_grava_nada(tmp_path):
    c = _Cobertura(tmp_path)
    codigo, texto = c.rodar()
    assert codigo == 2 and "Rodar_Testes.bat cobertura" in texto and not c.baseline.exists()


def test_relatorio_que_nao_e_json_e_recusado(tmp_path):
    c = _Cobertura(tmp_path)
    c.json.write_text("isto não é json", encoding="utf-8")
    codigo, texto = c.rodar()
    assert codigo == 2 and "não é um relatório JSON" in texto and not c.baseline.exists()


def test_relatorio_sem_arquivos_do_pacote_e_recusado_sem_gravar_baseline(tmp_path):
    c = _Cobertura(tmp_path)
    c.json.write_text(json.dumps({"files": {}}), encoding="utf-8")
    codigo, texto = c.rodar()
    assert codigo == 2 and "nenhum arquivo do pacote" in texto and not c.baseline.exists()


def test_baseline_corrompido_nao_e_sobrescrito_sem_o_pedido_explicito(tmp_path):
    c = _Cobertura(tmp_path)
    c.escrever(core=_arquivo(80, 100))
    c.baseline.write_text("{ quebrado", encoding="utf-8")
    codigo, texto = c.rodar()
    assert codigo == 2 and "ilegível" in texto and c.baseline.read_text(encoding="utf-8") == "{ quebrado"
    assert c.rodar("--gravar")[0] == 0
    assert cc.ler_baseline(c.baseline)["core"]["percentual"] == 80.0


def test_caminhos_padrao_ficam_em_logs_e_em_tests():
    assert cc.JSON_PADRAO.parts[-2:] == ("logs", "coverage.json")
    assert cc.BASELINE_PADRAO.parts[-2:] == ("tests", "coverage_baseline.json")
