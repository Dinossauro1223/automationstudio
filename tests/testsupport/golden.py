"""Resultados de referência ("golden") dos cenários: o que o programa produz, congelado em arquivo para comparar depois.

Um cenário roda um fluxo inteiro (mapa → linha do tempo → motor → backend) e entrega a sequência de eventos. `comparar`
confere essa sequência com o arquivo `tests/data/golden/<nome>.json`. Se qualquer evento, tempo ou alvo mudar, o teste
falha e mostra a PRIMEIRA diferença.

Atualizar um golden é uma decisão, não um conserto:
    AS_ATUALIZAR_GOLDEN=1 py tests\\testsupport\\run_minimal.py tests\\scenarios      (ou pytest com a mesma variável)
só quando a mudança de comportamento é INTENCIONAL; depois leia o diff dos arquivos .json. Atualizar sem ler o diff
transforma o teste em carimbo. Por isso a rodada de atualização GRAVA os arquivos mas reprova cada cenário: ela nunca
conta como verificação, e a rodada seguinte (sem a variável) é que confirma. A suíte rápida e a completa não definem a variável.
"""
from __future__ import annotations

import json
import os
import pathlib

GOLDEN = pathlib.Path(__file__).resolve().parents[1] / "data" / "golden"
VARIAVEL = "AS_ATUALIZAR_GOLDEN"
_LARGURA_DA_LINHA = 100


def normalizar(valor, casas: int = 6):
    """Valor pronto para virar JSON e ser comparado: tuplas viram listas e os decimais perdem o ruído de ponto flutuante."""
    if isinstance(valor, bool) or valor is None or isinstance(valor, (int, str)):
        return valor
    if isinstance(valor, float):
        arredondado = round(valor, casas)
        return 0.0 if arredondado == 0 else arredondado  # nunca "-0.0"
    if isinstance(valor, dict):
        return {str(chave): normalizar(item, casas) for chave, item in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [normalizar(item, casas) for item in valor]
    if hasattr(valor, "value"):  # Enum
        return normalizar(valor.value, casas)
    raise TypeError(f"golden: tipo não suportado {type(valor).__name__}: {valor!r}")


def _formatar(valor, nivel: int = 0) -> str:
    """JSON legível e estável: cada evento em uma linha, para o diff do arquivo mostrar só o que mudou."""
    curto = json.dumps(valor, ensure_ascii=False)
    if not isinstance(valor, (dict, list)) or len(curto) <= _LARGURA_DA_LINHA:
        return curto
    recuo, interno = " " * nivel, " " * (nivel + 1)
    if isinstance(valor, dict):
        itens = [f"{interno}{json.dumps(chave, ensure_ascii=False)}: {_formatar(item, nivel + 1)}" for chave, item in valor.items()]
        return "{\n" + ",\n".join(itens) + "\n" + recuo + "}"
    return "[\n" + ",\n".join(interno + _formatar(item, nivel + 1) for item in valor) + "\n" + recuo + "]"


def serializar(obtido) -> str:
    return _formatar(normalizar(obtido)) + "\n"


def primeira_diferenca(esperado, obtido, caminho: str = "") -> str | None:
    """Descreve onde dois valores já normalizados divergem (None se iguais)."""
    if isinstance(esperado, dict) and isinstance(obtido, dict):
        for chave in list(esperado) + [k for k in obtido if k not in esperado]:
            if chave not in esperado:
                return f"{caminho}.{chave}: não existia no golden e agora existe ({obtido[chave]!r})"
            if chave not in obtido:
                return f"{caminho}.{chave}: existia no golden e sumiu"
            achado = primeira_diferenca(esperado[chave], obtido[chave], f"{caminho}.{chave}")
            if achado:
                return achado
        return None
    if isinstance(esperado, list) and isinstance(obtido, list):
        for indice, (a, b) in enumerate(zip(esperado, obtido)):
            achado = primeira_diferenca(a, b, f"{caminho}[{indice}]")
            if achado:
                return achado
        if len(esperado) != len(obtido):
            return f"{caminho}: o golden tem {len(esperado)} itens e agora são {len(obtido)}"
        return None
    return None if esperado == obtido else f"{caminho}: golden {esperado!r} x obtido {obtido!r}"


def caminho_do(nome: str) -> pathlib.Path:
    return GOLDEN / f"{nome}.json"


def carregar(nome: str):
    """Conteúdo de um golden já gravado (para um cenário reaproveitar a referência de outro)."""
    return json.loads(caminho_do(nome).read_text(encoding="utf-8"))


def nomes_existentes() -> list[str]:
    return sorted(p.stem for p in GOLDEN.glob("*.json"))


def comparar(nome: str, obtido) -> None:
    """Confere `obtido` com o golden `nome`. Com AS_ATUALIZAR_GOLDEN=1 grava o arquivo e reprova o teste (ver o topo do módulo)."""
    caminho = caminho_do(nome)
    texto = serializar(obtido)
    if os.environ.get(VARIAVEL) == "1":
        GOLDEN.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8", newline="\n")
        raise AssertionError(f"golden {caminho.name} GRAVADO (modo de atualização). Leia o diff do arquivo e rode de novo SEM "
                             f"{VARIAVEL}: uma rodada de atualização nunca conta como verificação.")
    assert caminho.exists(), (f"o golden {caminho.name} não existe. Se este cenário é novo, gere o arquivo com {VARIAVEL}=1, "
                              f"LEIA o conteúdo (é a referência de todas as rodadas futuras) e só então o inclua no projeto.")
    esperado = json.loads(caminho.read_text(encoding="utf-8"))
    achado = primeira_diferenca(esperado, json.loads(texto))
    assert achado is None, f"o resultado do cenário mudou em relação ao golden {caminho.name}: primeira diferença em {achado}"
