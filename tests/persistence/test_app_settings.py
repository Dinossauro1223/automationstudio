"""AppSettings: configurações do programa, guardadas na tabela `settings` do mesmo banco dos mapas."""
import json

import pytest

from automationstudio.project import AppSettings, ProjectManager
from testsupport.helpers import key, make_map, raw_exec, raw_rows

PADRAO_GRAVACAO = {
    "capture_keyboard": True, "capture_mouse_buttons": True, "capture_mouse_move": True, "capture_mouse_scroll": True,
    "record_key_duration": True, "merge_mouse_moves": True, "mouse_jitter_px": 3, "mouse_sample_interval_ms": 8,
    "ignored_keys": [], "ignored_mouse_buttons": []}
PADRAO_ATALHOS = {"pause": "F9", "resume": "F10", "emergency": "F12", "record_toggle": "F8", "record_cancel": "F11"}
# Chaves que a interface lê de get_visual_settings(). Remover uma delas quebra a janela; acrescentar é livre.
CHAVES_VISUAIS_OBRIGATORIAS = {
    "keyboard_mode", "keyboard_timeout", "mouse_timeout", "keyboard_opacity", "mouse_opacity", "show_on_minimize",
    "show_keyboard", "show_mouse", "always_on_top", "click_virtual_keyboard", "keyboard_geometry", "mouse_geometry",
    "theme_mode", "accent_dark", "accent_light", "light_surface", "light_contrast", "virtual_surface_dark",
    "virtual_surface_light", "virtual_text_dark", "virtual_text_light", "virtual_accent", "onboarding_seen",
    "main_window_geometry", "main_window_state", "sidebar_width", "workspace_splitter_sizes", "undo_ram_mb",
    "text_char_interval", "app_stable_ms", "app_after_open", "app_wait_timeout", "app_adaptive_learning",
    "app_readiness_history"}


# ----------------------------------------------------------------------------------------- padrões
def test_padroes_de_gravacao(tmp_path):
    assert AppSettings(tmp_path).get_recording_settings() == PADRAO_GRAVACAO


def test_padroes_dos_atalhos_de_controle(tmp_path):
    assert AppSettings(tmp_path).get_control_hotkeys() == PADRAO_ATALHOS


def test_padroes_visuais_tem_todas_as_chaves_que_a_interface_le(tmp_path):
    visual = AppSettings(tmp_path).get_visual_settings()
    assert CHAVES_VISUAIS_OBRIGATORIAS <= set(visual), sorted(CHAVES_VISUAIS_OBRIGATORIAS - set(visual))


def test_padroes_visuais_de_execucao(tmp_path):
    visual = AppSettings(tmp_path).get_visual_settings()
    assert (visual["undo_ram_mb"], visual["text_char_interval"], visual["app_stable_ms"], visual["app_after_open"]) == (256, 0.01, 1000, 0.3)
    assert (visual["app_wait_timeout"], visual["app_adaptive_learning"], visual["app_readiness_history"]) == (0.0, True, {})
    assert (visual["theme_mode"], visual["keyboard_mode"], visual["onboarding_seen"]) == ("system", "compact", False)


def test_ler_os_padroes_nao_grava_nada_no_banco(tmp_path):
    configuracoes = AppSettings(tmp_path)
    configuracoes.get_recording_settings(); configuracoes.get_control_hotkeys(); configuracoes.get_visual_settings()
    assert raw_rows(configuracoes.db_path, "settings") == []


def test_cada_leitura_devolve_um_dicionario_novo(tmp_path):
    configuracoes = AppSettings(tmp_path)
    primeiro = configuracoes.get_control_hotkeys()
    primeiro["pause"] = "ALTERADO"
    assert configuracoes.get_control_hotkeys()["pause"] == "F9"


# ----------------------------------------------------------------------------------------- gravar e reabrir
def test_gravacao_ida_e_volta_mescla_com_os_padroes(tmp_path):
    AppSettings(tmp_path).set_recording_settings({"mouse_jitter_px": 7, "ignored_keys": ["F1", "F2"]})
    lido = AppSettings(tmp_path).get_recording_settings()
    assert lido["mouse_jitter_px"] == 7 and lido["ignored_keys"] == ["F1", "F2"]
    assert {k: v for k, v in lido.items() if k not in ("mouse_jitter_px", "ignored_keys")} == \
        {k: v for k, v in PADRAO_GRAVACAO.items() if k not in ("mouse_jitter_px", "ignored_keys")}


def test_atalhos_de_controle_ida_e_volta_mescla_com_os_padroes(tmp_path):
    AppSettings(tmp_path).set_control_hotkeys({"pause": "CTRL+F9", "emergency": "MOUSE_X2"})
    assert AppSettings(tmp_path).get_control_hotkeys() == {**PADRAO_ATALHOS, "pause": "CTRL+F9", "emergency": "MOUSE_X2"}


def test_configuracoes_visuais_ida_e_volta_preservam_tipos(tmp_path):
    valores = {"theme_mode": "dark", "sidebar_width": 410, "keyboard_opacity": 0.5, "show_mouse": True,
               "main_window_geometry": [10, 20, 800, 600], "app_readiness_history": {"notepad.exe": {"ok": 3}}}
    AppSettings(tmp_path).set_visual_settings(valores)
    lido = AppSettings(tmp_path).get_visual_settings()
    assert {k: lido[k] for k in valores} == valores
    assert lido["undo_ram_mb"] == 256  # o que não foi gravado continua com o padrão


def test_gravar_de_novo_substitui_o_grupo_inteiro(tmp_path):
    configuracoes = AppSettings(tmp_path)
    configuracoes.set_recording_settings({"mouse_jitter_px": 7, "capture_keyboard": False})
    configuracoes.set_recording_settings({"mouse_jitter_px": 9})
    lido = AppSettings(tmp_path).get_recording_settings()
    assert lido["mouse_jitter_px"] == 9 and lido["capture_keyboard"] is True


def test_texto_com_acentos_fica_legivel_no_banco(tmp_path):
    configuracoes = AppSettings(tmp_path)
    configuracoes.set_visual_settings({"theme_mode": "ação"})
    (linha,) = [valor for chave, valor in raw_rows(configuracoes.db_path, "settings") if chave == "visual"]
    assert "ação" in linha and json.loads(linha)["theme_mode"] == "ação"


@pytest.mark.parametrize("bruto", ['"lixo"', "[1, 2]", "5", "null", "true"])
@pytest.mark.parametrize("chave,leitor,padrao", [
    ("recording", "get_recording_settings", PADRAO_GRAVACAO),
    ("control_hotkeys", "get_control_hotkeys", PADRAO_ATALHOS)])
def test_valor_gravado_de_tipo_inesperado_volta_ao_padrao(tmp_path, chave, leitor, padrao, bruto):
    configuracoes = AppSettings(tmp_path)
    raw_exec(configuracoes.db_path, "INSERT INTO settings(key,value) VALUES(?,?)", (chave, bruto))
    assert getattr(AppSettings(tmp_path), leitor)() == padrao


@pytest.mark.parametrize("bruto", ['"lixo"', "[1, 2]", "5", "null"])
def test_configuracao_visual_de_tipo_inesperado_volta_ao_padrao(tmp_path, bruto):
    configuracoes = AppSettings(tmp_path)
    raw_exec(configuracoes.db_path, "INSERT INTO settings(key,value) VALUES(?,?)", ("visual", bruto))
    assert AppSettings(tmp_path).get_visual_settings()["undo_ram_mb"] == 256


# ----------------------------------------------------------------------------------------- migração do padrão antigo
def test_padrao_antigo_de_abertura_de_aplicativo_e_migrado_e_regravado(tmp_path):
    AppSettings(tmp_path).set_visual_settings({"app_stable_ms": 250, "app_after_open": 0.375, "keyboard_mode": "full"})
    lido = AppSettings(tmp_path).get_visual_settings()
    assert (lido["app_stable_ms"], lido["app_after_open"], lido["keyboard_mode"]) == (1000, 0.3, "full")
    (linha,) = [valor for chave, valor in raw_rows(tmp_path / "AutomationStudio.db", "settings") if chave == "visual"]
    gravado = json.loads(linha)
    assert (gravado["app_stable_ms"], gravado["app_after_open"]) == (1000, 0.3), "a migração fica gravada no banco"


@pytest.mark.parametrize("estavel,depois", [(250, 0.5), (500, 0.375), (250, 0.376), (1000, 0.3), (0, 0.0)])
def test_valores_personalizados_de_abertura_nao_sao_migrados(tmp_path, estavel, depois):
    AppSettings(tmp_path).set_visual_settings({"app_stable_ms": estavel, "app_after_open": depois})
    lido = AppSettings(tmp_path).get_visual_settings()
    assert (lido["app_stable_ms"], lido["app_after_open"]) == (estavel, depois)


# ----------------------------------------------------------------------------------------- pasta de dados
def test_pasta_de_dados_sem_escolha_usa_a_padrao_e_a_cria(tmp_path):
    padrao = tmp_path / "padrao" / "interna"
    assert AppSettings(tmp_path / "cfg").get_maps_folder(padrao) == padrao and padrao.is_dir()


def test_pasta_de_dados_escolhida_ida_e_volta(tmp_path):
    escolhida = tmp_path / "minhas automações"
    AppSettings(tmp_path / "cfg").set_maps_folder(escolhida)
    lida = AppSettings(tmp_path / "cfg").get_maps_folder(tmp_path / "padrao")
    assert lida == escolhida.resolve() and lida.is_dir()
    assert not (tmp_path / "padrao").exists(), "a pasta padrão só é criada quando é usada"


def test_pasta_de_dados_grava_as_duas_chaves_para_versoes_anteriores(tmp_path):
    configuracoes = AppSettings(tmp_path)
    configuracoes.set_maps_folder(tmp_path / "x")
    chaves = dict(raw_rows(configuracoes.db_path, "settings"))
    assert json.loads(chaves["maps_folder"]) == json.loads(chaves["data_folder"]) == str((tmp_path / "x").resolve())


def test_pasta_de_dados_so_com_a_chave_antiga_data_folder(tmp_path):
    configuracoes = AppSettings(tmp_path)
    antiga = tmp_path / "antiga"
    raw_exec(configuracoes.db_path, "INSERT INTO settings(key,value) VALUES(?,?)", ("data_folder", json.dumps(str(antiga))))
    assert AppSettings(tmp_path).get_maps_folder(tmp_path / "padrao") == antiga


def test_pasta_de_dados_impossivel_cai_na_padrao(tmp_path):
    arquivo = tmp_path / "arquivo.txt"
    arquivo.write_text("sou um arquivo, não uma pasta", encoding="utf-8")
    configuracoes = AppSettings(tmp_path / "cfg")
    configuracoes.set_maps_folder(arquivo / "dentro")
    padrao = tmp_path / "padrao"
    assert configuracoes.get_maps_folder(padrao) == padrao and padrao.is_dir()


def test_mapas_e_configuracoes_convivem_no_mesmo_banco(tmp_path):
    gerente, configuracoes = ProjectManager(tmp_path), AppSettings(tmp_path)
    gerente.save_map(make_map([key("A", 0.0, 0.1)], name="M"))
    configuracoes.set_control_hotkeys({"pause": "F5"})
    assert gerente.db_path == configuracoes.db_path
    assert [m.name for m in ProjectManager(tmp_path).load_all()] == ["M"]
    assert AppSettings(tmp_path).get_control_hotkeys()["pause"] == "F5"
    assert [nome for nome, _ in raw_rows(gerente.db_path)] == ["M"]


# ----------------------------------------------------------------------------------------- settings.json legado (V18)
def test_settings_json_legado_e_migrado_para_o_banco_e_renomeado(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"visual": {"keyboard_mode": "full"}}), encoding="utf-8")
    configuracoes = AppSettings(tmp_path)
    assert configuracoes.get_visual_settings()["keyboard_mode"] == "full"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["AutomationStudio.db", "settings.json.migrado"]
    assert AppSettings(tmp_path).get_visual_settings()["keyboard_mode"] == "full", "veio do banco, não do arquivo"


def test_settings_json_legado_corrompido_e_ignorado_sem_erro(tmp_path):
    (tmp_path / "settings.json").write_text("{ não é json", encoding="utf-8")
    configuracoes = AppSettings(tmp_path)
    assert configuracoes.get_control_hotkeys() == PADRAO_ATALHOS
    assert (tmp_path / "settings.json").exists() and not (tmp_path / "settings.json.migrado").exists()


def test_settings_json_legado_so_vale_com_o_banco_sem_configuracoes(tmp_path):
    AppSettings(tmp_path).set_control_hotkeys({"pause": "F5"})
    (tmp_path / "settings.json").write_text(json.dumps({"control_hotkeys": {"pause": "F1"}}), encoding="utf-8")
    assert AppSettings(tmp_path).get_control_hotkeys()["pause"] == "F5"
    assert (tmp_path / "settings.json").exists()


# ----------------------------------------------------------------------------------------- limitação conhecida
def test_atalho_de_controle_apagado_volta_ao_padrao_nao_existe_atalho_desligado(tmp_path):
    # Achado 2.05 (caracterização): a tela de configurações deixa o campo em branco, set_control_hotkeys descarta o
    # valor vazio e a leitura devolve o padrão. Hoje não há como DESLIGAR um atalho de controle; o formato novo (Ponto 3)
    # precisa decidir se isso é desejado.
    configuracoes = AppSettings(tmp_path)
    configuracoes.set_control_hotkeys({"pause": "", "resume": "F2"})
    lido = AppSettings(tmp_path).get_control_hotkeys()
    assert lido["pause"] == "F9" and lido["resume"] == "F2"


def test_gravar_configuracao_e_idempotente(tmp_path):
    configuracoes = AppSettings(tmp_path)
    configuracoes.set_control_hotkeys({"pause": "F5"})
    antes = raw_rows(configuracoes.db_path, "settings")
    configuracoes.save(); configuracoes.save()
    assert raw_rows(configuracoes.db_path, "settings") == antes
