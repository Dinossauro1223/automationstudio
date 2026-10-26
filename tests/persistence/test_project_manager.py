"""ProjectManager: os mapas no SQLite (salvar, carregar, apagar, exportar, importar e migrar o que veio de antes).

Cada teste usa uma pasta própria (tmp_path); nenhum toca o banco real do usuário.
"""
import json
import threading

import pytest

from automationstudio.core import ActionType, AutomationMap, Command, CommandGroup, InputType, map_from_json
from automationstudio.project import ProjectManager
from testsupport.helpers import insert_raw_map, key, legacy_database, make_map, raw_exec, raw_rows


def _mapa_variado(nome="Variado", **kwargs):
    """Mapa com um comando de cada família relevante para a persistência."""
    grupo = CommandGroup(name="Combo", color="#112233")
    comandos = [
        key("A", 0.0, 0.2, group_id=grupo.id),
        Command(type=InputType.MOUSE_MOVE, x=10, y=20, start=0.3),
        Command(type=InputType.MOUSE_BUTTON, target="x1", start=0.4, duration=0.1),
        Command(type=InputType.TEXT, text="olá, ação!", start=0.6, duration=0.1),
        Command(type=InputType.MOUSE_SCROLL, scroll_dy=-2, start=0.8),
        Command(type=InputType.KEY, target="X", action=ActionType.PRESS, start=0.9),
    ]
    return AutomationMap(name=nome, commands=comandos, groups={grupo.id: grupo}, hotkey="F6", repeat_count=3,
                         repeat_interval=0.5, speed=1.5, description="descrição", **kwargs)


# ----------------------------------------------------------------------------------------- criação e ida-e-volta
def test_pasta_nova_cria_o_banco_vazio(tmp_path):
    pasta = tmp_path / "dados" / "interna"
    gerente = ProjectManager(pasta)
    assert gerente.db_path == (pasta / "AutomationStudio.db").resolve() and gerente.db_path.exists()
    assert gerente.load_all() == [] and gerente.maps == {} and gerente.load_errors == []


def test_salvar_e_reabrir_devolve_o_mesmo_mapa(tmp_path):
    original = _mapa_variado()
    ProjectManager(tmp_path).save_map(original)
    reaberto = ProjectManager(tmp_path)
    (lido,) = reaberto.load_all()
    assert lido.to_dict() == original.to_dict()
    assert reaberto.load_errors == []


def test_salvar_devolve_o_caminho_do_banco_e_registra_o_mapa_na_memoria(tmp_path):
    gerente = ProjectManager(tmp_path)
    mapa = make_map([key("A", 0.0, 0.1)], name="M")
    assert gerente.save_map(mapa) == gerente.db_path
    assert gerente.maps["M"] is mapa


def test_salvar_o_mesmo_nome_substitui_sem_duplicar(tmp_path):
    gerente = ProjectManager(tmp_path)
    gerente.save_map(make_map([key("A", 0.0, 0.1)], name="M"))
    gerente.save_map(make_map([key("A", 0.0, 0.1), key("B", 0.5, 0.1)], name="M"))
    assert [nome for nome, _ in raw_rows(gerente.db_path)] == ["M"]
    (lido,) = ProjectManager(tmp_path).load_all()
    assert [c.target for c in lido.commands] == ["A", "B"]


def test_salvar_um_mapa_nao_mexe_nos_outros(tmp_path):
    gerente = ProjectManager(tmp_path)
    gerente.save_map(make_map([key("A", 0.0, 0.1)], name="Um"))
    antes = dict(raw_rows(gerente.db_path))["Um"]
    gerente.save_map(make_map([key("B", 0.0, 0.1)], name="Dois"))
    assert dict(raw_rows(gerente.db_path))["Um"] == antes


def test_nomes_que_diferem_so_na_caixa_sao_mapas_distintos(tmp_path):
    gerente = ProjectManager(tmp_path)
    gerente.save_map(make_map([key("A", 0.0, 0.1)], name="Abc"))
    gerente.save_map(make_map([key("B", 0.0, 0.1)], name="abc"))
    assert sorted(m.name for m in ProjectManager(tmp_path).load_all()) == ["Abc", "abc"]


def test_lista_vem_em_ordem_alfabetica_sem_diferenciar_caixa(tmp_path):
    gerente = ProjectManager(tmp_path)
    for nome in ("banana", "Cereja", "abacate", "Damasco"):
        gerente.save_map(make_map([key("A", 0.0, 0.1)], name=nome))
    assert [m.name for m in ProjectManager(tmp_path).load_all()] == ["abacate", "banana", "Cereja", "Damasco"]


@pytest.mark.parametrize("nome", ["Ação – Ç ü", "a/b\\c", "com 'aspas' e \"duplas\"", "emoji 😀", "  com espaços  ", "UPPER", "x" * 300])
def test_nomes_com_caracteres_especiais_vao_e_voltam_exatos(tmp_path, nome):
    ProjectManager(tmp_path).save_map(make_map([key("A", 0.0, 0.1)], name=nome))
    assert [m.name for m in ProjectManager(tmp_path).load_all()] == [nome]


def test_salvar_repara_ids_duplicados_no_mapa_e_no_banco(tmp_path):
    gerente = ProjectManager(tmp_path)
    mapa = make_map([key("A", 0.0, 0.1), key("B", 0.5, 0.1)], name="Dup")
    primeiro = mapa.commands[0].id
    mapa.commands[1].id = primeiro  # o construtor já repara; aqui o defeito aparece DEPOIS (edição em memória)
    gerente.save_map(mapa)
    assert mapa.commands[0].id == primeiro and mapa.commands[1].id != primeiro
    gravado = map_from_json(dict(raw_rows(gerente.db_path))["Dup"])
    assert [(c.id, c.target) for c in gravado.commands] == [(c.id, c.target) for c in mapa.commands]


# ----------------------------------------------------------------------------------------- apagar
def test_apagar_remove_do_banco_e_da_memoria_e_diz_que_apagou(tmp_path):
    gerente = ProjectManager(tmp_path)
    gerente.save_map(make_map([key("A", 0.0, 0.1)], name="Some"))
    assert gerente.delete_map("Some") is True
    assert "Some" not in gerente.maps and raw_rows(gerente.db_path) == []


def test_apagar_nome_inexistente_devolve_falso_e_nao_mexe_em_nada(tmp_path):
    gerente = ProjectManager(tmp_path)
    gerente.save_map(make_map([key("A", 0.0, 0.1)], name="Fica"))
    assert gerente.delete_map("Outro") is False
    assert [m.name for m in ProjectManager(tmp_path).load_all()] == ["Fica"]


def test_apagar_so_apaga_o_nome_exato(tmp_path):
    gerente = ProjectManager(tmp_path)
    for nome in ("Abc", "abc", "Abc 2"):
        gerente.save_map(make_map([key("A", 0.0, 0.1)], name=nome))
    assert gerente.delete_map("abc") is True
    assert sorted(m.name for m in ProjectManager(tmp_path).load_all()) == ["Abc", "Abc 2"]


# ----------------------------------------------------------------------------------------- exportar e importar
def test_exportar_e_importar_em_outro_projeto_preserva_o_mapa(tmp_path):
    origem, destino = ProjectManager(tmp_path / "a"), ProjectManager(tmp_path / "b")
    mapa = _mapa_variado("Ação para levar")
    origem.save_map(mapa)
    arquivo = tmp_path / "levar.json"
    assert origem.export_map(mapa.name, arquivo) == arquivo
    importado = destino.import_map(arquivo)
    assert importado.to_dict() == mapa.to_dict()
    assert ProjectManager(tmp_path / "b").load_all()[0].to_dict() == mapa.to_dict()  # e ficou salvo no banco do destino


def test_arquivo_exportado_e_json_legivel_com_envelope_de_versao(tmp_path):
    gerente = ProjectManager(tmp_path)
    gerente.save_map(make_map([Command(type=InputType.TEXT, text="ação", start=0.0, duration=0.1)], name="Ação"))
    arquivo = gerente.export_map("Ação", tmp_path / "saida.json")
    texto = arquivo.read_text(encoding="utf-8")
    assert "ação" in texto and "\\u00e7" not in texto  # acentos legíveis, não escapados
    bruto = json.loads(texto)
    assert bruto["format_version"] == 1 and bruto["map"]["name"] == "Ação"


def test_exportar_mapa_desconhecido_levanta_keyerror(tmp_path):
    with pytest.raises(KeyError):
        ProjectManager(tmp_path).export_map("Nao existe", tmp_path / "x.json")


def test_exportar_exige_o_mapa_carregado_ou_salvo_nesta_instancia(tmp_path):
    # export_map lê de `maps` (memória), não do banco: o programa chama load_all() ao abrir.
    ProjectManager(tmp_path).save_map(make_map([key("A", 0.0, 0.1)], name="No banco"))
    novo = ProjectManager(tmp_path)
    with pytest.raises(KeyError):
        novo.export_map("No banco", tmp_path / "x.json")
    novo.load_all()
    assert novo.export_map("No banco", tmp_path / "x.json").exists()


def test_import_map_substitui_mapa_de_mesmo_nome(tmp_path):
    # A interface pergunta antes (substituir / outro nome / cancelar); a biblioteca em si grava por cima.
    gerente = ProjectManager(tmp_path)
    gerente.save_map(make_map([key("A", 0.0, 0.1)], name="Mesmo"))
    arquivo = tmp_path / "outro.json"
    outro = make_map([key("Q", 0.0, 0.1), key("R", 0.3, 0.1)], name="Mesmo")
    arquivo.write_text(json.dumps({"format_version": 1, "map": outro.to_dict()}), encoding="utf-8")
    gerente.import_map(arquivo)
    (lido,) = ProjectManager(tmp_path).load_all()
    assert [c.target for c in lido.commands] == ["Q", "R"]


def test_importar_arquivo_com_defeito_nao_grava_nada(tmp_path):
    gerente = ProjectManager(tmp_path)
    arquivo = tmp_path / "ruim.json"
    arquivo.write_text("{ isto não é json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        gerente.import_map(arquivo)
    assert raw_rows(gerente.db_path) == []


# ----------------------------------------------------------------------------------------- load_map
def test_carregar_por_arquivo_json_registra_o_mapa_na_memoria(tmp_path):
    arquivo = tmp_path / "solto.json"
    arquivo.write_text(json.dumps({"format_version": 1, "map": make_map([key("A", 0.0, 0.1)], name="Do arquivo").to_dict()}),
                       encoding="utf-8")
    gerente = ProjectManager(tmp_path / "dados")
    assert gerente.load_map(arquivo).name == "Do arquivo" and "Do arquivo" in gerente.maps
    assert raw_rows(gerente.db_path) == []  # carregar não grava no banco


def test_carregar_por_nome_le_o_banco_e_nome_desconhecido_levanta(tmp_path):
    gerente = ProjectManager(tmp_path)
    gerente.save_map(make_map([key("A", 0.0, 0.1)], name="Guardado"))
    assert ProjectManager(tmp_path).load_map("Guardado").name == "Guardado"
    with pytest.raises(FileNotFoundError):
        gerente.load_map("Inexistente")


@pytest.mark.xfail(strict=True, reason="achado 2.04 (latente): load_map(nome) usa Path(nome).stem e perde tudo depois do último "
                                       "ponto; 'Mapa v1.2' vira 'Mapa v1'. A interface não usa essa rota; o Ponto 3 a substitui")
def test_carregar_por_nome_com_ponto_no_nome(tmp_path):
    gerente = ProjectManager(tmp_path)
    gerente.save_map(make_map([key("A", 0.0, 0.1)], name="Mapa v1.2"))
    assert gerente.load_map("Mapa v1.2").name == "Mapa v1.2"


# ----------------------------------------------------------------------------------------- registros com defeito
@pytest.mark.parametrize("payload", [
    "{ isto não é json",
    "[]",
    "42",
    json.dumps({"name": "X", "repeat_count": "muitas"}),
    json.dumps({"name": "X", "commands": None}),
    json.dumps({"name": "X", "groups": None}),
    json.dumps({"name": "X", "commands": ["texto solto"]}),
])
def test_registro_ilegivel_nao_derruba_os_outros_e_fica_registrado(tmp_path, runtime_log, payload):
    gerente = ProjectManager(tmp_path)
    gerente.save_map(make_map([key("A", 0.0, 0.1)], name="Bom"))
    insert_raw_map(gerente.db_path, "Quebrado", payload)
    novo = ProjectManager(tmp_path)
    assert [m.name for m in novo.load_all()] == ["Bom"]
    assert len(novo.load_errors) == 1 and novo.load_errors[0].startswith("Quebrado: ")
    assert ("Quebrado", payload) in raw_rows(novo.db_path), "o registro nunca é apagado: o usuário ainda pode recuperá-lo"
    assert any("MAPA NAO CARREGADO" in linha and "Quebrado" in linha for linha in runtime_log)


def test_erros_de_carga_sao_zerados_a_cada_carga(tmp_path):
    gerente = ProjectManager(tmp_path)
    insert_raw_map(gerente.db_path, "Quebrado", "{nao")
    gerente.load_all()
    assert len(gerente.load_errors) == 1
    raw_exec(gerente.db_path, "DELETE FROM maps WHERE name=?", ("Quebrado",))
    gerente.load_all()
    assert gerente.load_errors == []


def test_recarregar_reflete_o_que_esta_no_banco_agora(tmp_path):
    gerente = ProjectManager(tmp_path)
    gerente.save_map(make_map([key("A", 0.0, 0.1)], name="Um"))
    gerente.save_map(make_map([key("A", 0.0, 0.1)], name="Dois"))
    raw_exec(gerente.db_path, "DELETE FROM maps WHERE name=?", ("Um",))
    assert [m.name for m in gerente.load_all()] == ["Dois"] and list(gerente.maps) == ["Dois"]


def test_transacao_e_desfeita_quando_o_bloco_levanta(tmp_path):
    gerente = ProjectManager(tmp_path)
    with pytest.raises(RuntimeError, match="falha no meio"):
        with gerente._connect() as con:
            con.execute("INSERT INTO maps(name,payload) VALUES('Fantasma','{}')")
            raise RuntimeError("falha no meio")
    assert raw_rows(gerente.db_path) == []


# ----------------------------------------------------------------------------------------- validação do conjunto
def test_validate_all_junta_erros_dos_mapas_e_atalhos_repetidos(tmp_path):
    gerente = ProjectManager(tmp_path)
    gerente.save_map(make_map([key("A", 0.0, 0.1)], name="A", hotkey="F5"))
    gerente.save_map(make_map([key("B", 0.0, 0.1)], name="B", hotkey="F5"))
    gerente.save_map(make_map([key("", 0.0, 0.1)], name="C", hotkey="F6"))
    erros = gerente.validate_all()
    assert "Atalho 'F5' está duplicado entre os mapas: A, B." in erros
    assert any("sem tecla" in erro for erro in erros)
    assert len(erros) == 2


def test_validate_all_de_mapas_corretos_e_vazio(tmp_path):
    gerente = ProjectManager(tmp_path)
    gerente.save_map(make_map([key("A", 0.0, 0.1)], name="A", hotkey="F5"))
    gerente.save_map(make_map([key("B", 0.0, 0.1)], name="B", hotkey="F6"))
    assert gerente.validate_all() == []


# ----------------------------------------------------------------------------------------- o que veio de versões anteriores
def test_mapas_reais_de_versoes_anteriores_abrem_validam_e_regravam_estaveis(tmp_path, legacy_maps):
    legacy_database(tmp_path)
    gerente = ProjectManager(tmp_path)
    primeira = {m.name: m.to_dict() for m in gerente.load_all()}
    assert sorted(primeira) == sorted(legacy_maps) and gerente.load_errors == [] and gerente.validate_all() == []
    for mapa in list(gerente.maps.values()):
        gerente.save_map(mapa)
    segunda = ProjectManager(tmp_path)
    assert {m.name: m.to_dict() for m in segunda.load_all()} == primeira
    assert segunda.load_errors == []


def test_json_legado_e_importado_quando_o_banco_esta_vazio(tmp_path):
    antigo = make_map([key("Z", 0.0, 0.1)], name="Antigo")
    (tmp_path / "Antigo.json").write_text(json.dumps({"format_version": 1, "map": antigo.to_dict()}), encoding="utf-8")
    (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
    (tmp_path / "gravacao.recording_backup.json").write_text(
        json.dumps({"format_version": 1, "map": make_map([key("Y", 0.0, 0.1)], name="Backup").to_dict()}), encoding="utf-8")
    (tmp_path / "ruim.json").write_text("nada", encoding="utf-8")
    arquivos_antes = sorted(p.name for p in tmp_path.iterdir())
    gerente = ProjectManager(tmp_path)
    assert [m.name for m in gerente.load_all()] == ["Antigo"]
    assert sorted(p.name for p in tmp_path.iterdir() if p.suffix == ".json") == [n for n in arquivos_antes if n.endswith(".json")], \
        "a migração nunca apaga nem renomeia os JSON originais"


def test_json_legado_nao_e_importado_com_o_banco_ja_populado(tmp_path):
    ProjectManager(tmp_path).save_map(make_map([key("A", 0.0, 0.1)], name="Existente"))
    (tmp_path / "Novo.json").write_text(
        json.dumps({"format_version": 1, "map": make_map([key("B", 0.0, 0.1)], name="Novo").to_dict()}), encoding="utf-8")
    assert [m.name for m in ProjectManager(tmp_path).load_all()] == ["Existente"]


@pytest.mark.xfail(strict=True, reason="achado 2.03 (confirmado): a migração roda sempre que o banco está VAZIO, não 'uma única vez'; "
                                       "apagar o último mapa e reabrir traz de volta os JSON antigos da pasta. Corrigir no Ponto 3")
def test_json_legado_nao_ressuscita_mapa_apagado(tmp_path):
    (tmp_path / "Antigo.json").write_text(
        json.dumps({"format_version": 1, "map": make_map([key("Z", 0.0, 0.1)], name="Antigo").to_dict()}), encoding="utf-8")
    gerente = ProjectManager(tmp_path)
    assert [m.name for m in gerente.load_all()] == ["Antigo"]
    gerente.delete_map("Antigo")
    assert ProjectManager(tmp_path).load_all() == []


# ----------------------------------------------------------------------------------------- vários acessos ao mesmo banco
def test_dois_gerenciadores_na_mesma_pasta_veem_os_mesmos_dados(tmp_path):
    a, b = ProjectManager(tmp_path), ProjectManager(tmp_path)
    a.save_map(make_map([key("A", 0.0, 0.1)], name="Do A"))
    assert [m.name for m in b.load_all()] == ["Do A"]
    b.delete_map("Do A")
    assert a.load_all() == []


def test_gravacoes_de_varias_threads_nao_perdem_mapas(tmp_path):
    erros = []

    def trabalhar(indice):
        try:
            gerente = ProjectManager(tmp_path)
            for repeticao in range(5):
                gerente.save_map(make_map([key("A", 0.0, 0.1)], name=f"M{indice}_{repeticao}"))
        except Exception as exc:  # noqa: BLE001 - qualquer falha precisa aparecer no assert
            erros.append(repr(exc))

    ProjectManager(tmp_path)  # cria o banco antes da corrida
    threads = [threading.Thread(target=trabalhar, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert not any(t.is_alive() for t in threads) and erros == []
    assert len(ProjectManager(tmp_path).load_all()) == 30
