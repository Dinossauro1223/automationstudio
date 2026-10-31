"""O catálogo das funções do usuário (tests/testsupport/funcoes_do_usuario.py) está bem-formado e o documento em md acompanha.

São testes puros (sem Qt): rodam também no modo rápido. A conferência na janela de verdade está em
tests/gui/test_funcoes_acessiveis.py. Por que tudo isso existe: md/PLANO_VISUAL.md, seção "Nenhuma função se perde".
"""
import re
from pathlib import Path

from testsupport import funcoes_do_usuario as catalogo

RAIZ = Path(__file__).resolve().parents[2]
TIPOS = {"acao": 3, "botao": 3, "painel": 3, "fonte": 3, "teste": 2}


def test_o_catalogo_de_funcoes_tem_ids_e_nomes_unicos_e_toda_funcao_tem_endereco():
    ids = [f.id for f in catalogo.FUNCOES]
    assert len(ids) == len(set(ids)), "ID repetido no catálogo de funções"
    assert all(re.fullmatch(r"F\d{2}", i) for i in ids), "ID fora do padrão F00"
    nomes = [f.nome for f in catalogo.FUNCOES]
    assert len(nomes) == len(set(nomes)), "duas funções com o mesmo nome"
    for f in catalogo.FUNCOES:
        assert f.acessos, f"{f.id} ({f.nome}) não tem nenhum endereço: função sem como ser acionada"
        for acesso in f.acessos:
            assert acesso[0] in TIPOS and len(acesso) == TIPOS[acesso[0]], f"{f.id}: endereço malformado {acesso!r}"
            if acesso[0] in ("acao", "botao", "painel"):
                assert acesso[2] in catalogo.TELAS, f"{f.id}: tela desconhecida {acesso[2]!r} (use uma de {catalogo.TELAS})"


def test_o_documento_funcoes_do_usuario_acompanha_o_catalogo():
    documento = (RAIZ / "md" / "FUNCOES_DO_USUARIO.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert documento == catalogo.markdown(), (
        "md/FUNCOES_DO_USUARIO.md está desatualizado. Regenere com: "
        "python tests/testsupport/funcoes_do_usuario.py > md/FUNCOES_DO_USUARIO.md")


def test_os_enderecos_de_codigo_e_de_teste_do_catalogo_existem():
    for f in catalogo.FUNCOES:
        for acesso in f.acessos:
            if acesso[0] == "fonte":
                texto = (RAIZ / "automationstudio" / acesso[1]).read_text(encoding="utf-8")
                assert acesso[2] in texto, f"{f.id}: o texto {acesso[2]!r} não existe mais em {acesso[1]}"
            elif acesso[0] == "teste":
                caminho, nome = acesso[1].split("::")
                assert f"def {nome}(" in (RAIZ / caminho).read_text(encoding="utf-8"), f"{f.id}: o teste {nome} sumiu"
