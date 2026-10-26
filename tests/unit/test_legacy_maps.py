"""Compatibilidade: os 3 mapas reais (formato v1) gravados por versões anteriores precisam continuar abrindo."""
import collections

import pytest

from automationstudio import core
from automationstudio.core import build_timeline, map_from_json, map_to_json

ESPERADO = {
    "Click genshin": dict(comandos=8, tipos={"key": 4, "mouse_button": 4}, eventos=16, total=0.864, atalho="MOUSE_X1", repeticoes=-1),
    "Exemplo — Primeira automação": dict(comandos=2, tipos={"app_open": 1, "text": 1}, eventos=2, total=1.96, atalho="=", repeticoes=1),
    "Flins combo": dict(comandos=933, tipos={"key": 305, "mouse_move": 360, "mouse_button": 268}, eventos=2073, total=64.871, atalho="MOUSE_X2", repeticoes=-1),
}


def test_os_tres_mapas_estao_nas_fixtures(legacy_maps):
    assert sorted(legacy_maps) == sorted(ESPERADO)


@pytest.mark.parametrize("nome", list(ESPERADO))
def test_mapa_legado_carrega_valida_e_gera_a_timeline(legacy_maps, monkeypatch, nome):
    # O total do mapa "Exemplo" inclui a digitação do texto (186 caracteres × intervalo por caractere). O conftest zera
    # esse intervalo para nenhum teste dormir de verdade; aqui o valor PADRÃO do produto é fixado de propósito.
    monkeypatch.setattr(core, "TEXT_CHAR_INTERVAL", 0.01)
    esperado = ESPERADO[nome]
    mapa = map_from_json(legacy_maps[nome])
    assert len(mapa.commands) == esperado["comandos"]
    assert dict(collections.Counter(c.type.value for c in mapa.commands)) == esperado["tipos"]
    assert mapa.validate() == [] and mapa.validate_structure() == []
    assert len(build_timeline(mapa)) == esperado["eventos"]
    assert round(mapa.total_duration(), 3) == esperado["total"]
    assert (mapa.hotkey, mapa.repeat_count, mapa.speed) == (esperado["atalho"], esperado["repeticoes"], 1.0)


@pytest.mark.parametrize("nome", list(ESPERADO))
def test_mapa_legado_regravado_e_estavel(legacy_maps, nome):
    mapa = map_from_json(legacy_maps[nome])
    novamente = map_from_json(map_to_json(mapa))
    assert novamente.to_dict() == mapa.to_dict()
    assert map_to_json(novamente) == map_to_json(mapa)


def test_ids_dos_mapas_legados_nao_colidem_com_comandos_novos(legacy_maps):
    from automationstudio.core import Command, InputType
    mapa = map_from_json(legacy_maps["Flins combo"])
    novo = Command(type=InputType.KEY, target="A", duration=0.1)
    assert novo.id not in {c.id for c in mapa.commands}
