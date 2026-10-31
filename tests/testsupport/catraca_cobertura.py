"""Catraca de cobertura: a cobertura de cada parte do pacote não pode CAIR em relação ao baseline gravado.

A medição vem do coverage.py: `Rodar_Testes.bat cobertura` roda `coverage run`, `coverage report`, `coverage json` e, por fim,
este script. O baseline fica em tests/coverage_baseline.json e é gravado na SUA máquina, na primeira vez que a catraca roda
sem ele. Ele vale para o ambiente em que foi medido: com o PySide6 de verdade a parte da interface cobre muito mais do que com
o dublê de widgets, então um baseline gravado num ambiente não serve de régua para o outro (grave de novo com --gravar).

    py tests/testsupport/catraca_cobertura.py             compara logs/coverage.json com o baseline (grava se não houver)
    py tests/testsupport/catraca_cobertura.py --gravar    grava o baseline com a medição atual (é como a catraca SOBE)
    opções: --json CAMINHO   --baseline CAMINHO   --tolerancia PONTOS (padrão 1,0)

Saída: 0 = dentro do baseline (ou baseline gravado agora); 1 = alguma parte caiu; 2 = relatório ou baseline ilegível.
Uma queda nunca regrava o baseline sozinha: baixar a régua é uma decisão (`--gravar`), não um efeito colateral.

A porcentagem é a do coverage.py: linhas e ramos juntos, (linhas cobertas + ramos cobertos) / (instruções + ramos).
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
JSON_PADRAO = RAIZ / "logs" / "coverage.json"
BASELINE_PADRAO = RAIZ / "tests" / "coverage_baseline.json"
TOLERANCIA_PADRAO = 1.0   # pontos percentuais: absorve a variação de uma rodada para outra (threads, temporizadores do Qt)
MARGEM_DE_MELHORA = 2.0   # acima disso a saída sugere subir a catraca
FORMATO = 1
TOTAL, OUTROS = "total", "outros"

# Cada módulo do pacote pertence a um grupo. Um módulo novo que ainda não está aqui cai em "outros": entra no total e não
# passa batido (e o teste da catraca falha até alguém dizer a que grupo ele pertence).
GRUPOS = {
    "core": ("core",),
    "conditions": ("conditions",),
    "project": ("project",),
    "input_system": ("input_system",),
    "vision": ("vision",),
    "ativacao": ("ativacao",),  # 25.8: a lógica pura da ativação por mapa; a parte com widgets (ativacao_ui) é da interface
    "controle": ("controle_ui",),  # pausar/continuar pelas teclas: sem widgets (não importa o Qt), coberto sem a janela
    "interface": ("app", "ativacao_ui", "command_editor", "main_window", "overlays", "timeline", "tutorial"),
}
IGNORADOS = frozenset({"__init__"})


def modulo_do_pacote(caminho: str) -> str | None:
    """O nome do módulo ("core") de um caminho do relatório do coverage ("automationstudio/core.py", com / ou \\, relativo
    ou absoluto), ou None se o arquivo não é do pacote."""
    partes = str(caminho).replace("\\", "/").split("/")
    if "automationstudio" not in partes:
        return None
    resto = partes[len(partes) - 1 - partes[::-1].index("automationstudio") + 1:]
    if len(resto) != 1 or not resto[0].endswith(".py"):
        return None
    return resto[0][:-3]


def grupo_do_modulo(modulo: str) -> str:
    for grupo, modulos in GRUPOS.items():
        if modulo in modulos:
            return grupo
    return OUTROS


def _contagens(resumo: dict, arquivo: str) -> tuple[int, int]:
    """(cobertas, total) de um arquivo: instruções e ramos juntos, como o coverage.py calcula a porcentagem."""
    try:
        cobertas = int(resumo["covered_lines"]) + int(resumo.get("covered_branches", 0) or 0)
        total = int(resumo["num_statements"]) + int(resumo.get("num_branches", 0) or 0)
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"o relatório não traz as contagens de {arquivo} (esperava covered_lines e num_statements)") from None
    return cobertas, total


def resumir(relatorio: dict) -> dict[str, dict]:
    """{grupo: {"cobertas", "total", "percentual"}} somando os módulos de cada grupo, mais o grupo "total"."""
    somas: dict[str, list[int]] = {}
    arquivos = relatorio.get("files") if isinstance(relatorio, dict) else None
    if not isinstance(arquivos, dict):
        raise ValueError("relatório de cobertura inesperado: não tem a lista de arquivos (`files`)")
    for caminho, dados in arquivos.items():
        modulo = modulo_do_pacote(caminho)
        if modulo is None or modulo in IGNORADOS:
            continue
        resumo = dados.get("summary") if isinstance(dados, dict) else None
        if not isinstance(resumo, dict):
            raise ValueError(f"o relatório não traz o resumo de {caminho}")
        cobertas, total = _contagens(resumo, caminho)
        soma = somas.setdefault(grupo_do_modulo(modulo), [0, 0])
        soma[0] += cobertas
        soma[1] += total
    if not somas:
        raise ValueError("o relatório não tem nenhum arquivo do pacote automationstudio")
    resultado = {grupo: _linha(cobertas, total) for grupo, (cobertas, total) in somas.items()}
    resultado[TOTAL] = _linha(sum(c for c, _ in somas.values()), sum(t for _, t in somas.values()))
    return resultado


def _linha(cobertas: int, total: int) -> dict:
    return {"cobertas": cobertas, "total": total, "percentual": round(100.0 * cobertas / total, 2) if total else 100.0}


def comparar(baseline: dict, atual: dict, tolerancia: float = TOLERANCIA_PADRAO) -> list[str]:
    """Os problemas: cada parte que caiu mais do que a tolerância (ou sumiu da medição) em relação ao baseline."""
    problemas = []
    for grupo, antigo in baseline.items():
        agora = atual.get(grupo)
        if agora is None:
            problemas.append(f"{grupo}: sumiu da medição (o baseline tinha {antigo['percentual']:.1f}%)")
        elif agora["percentual"] < antigo["percentual"] - tolerancia:
            problemas.append(f"{grupo}: {agora['percentual']:.1f}% e o baseline é {antigo['percentual']:.1f}% "
                             f"(caiu {antigo['percentual'] - agora['percentual']:.1f} pontos; a tolerância é {tolerancia:g})")
    return problemas


def melhorias(baseline: dict, atual: dict, margem: float = MARGEM_DE_MELHORA) -> list[str]:
    """As partes que subiram mais do que a margem: candidatas a subir a catraca (--gravar)."""
    return [f"{grupo}: {baseline[grupo]['percentual']:.1f}% -> {agora['percentual']:.1f}%"
            for grupo, agora in atual.items()
            if grupo in baseline and agora["percentual"] > baseline[grupo]["percentual"] + margem]


def ler_baseline(caminho: pathlib.Path) -> dict | None:
    """O baseline gravado (só os grupos), ou None se o arquivo não existe. ValueError se ele existe e não serve."""
    if not caminho.exists():
        return None
    try:
        grupos = json.loads(caminho.read_text(encoding="utf-8"))["grupos"]
        if not isinstance(grupos, dict) or not grupos:
            raise ValueError("sem grupos")
        for linha in grupos.values():
            float(linha["percentual"])
    except (OSError, ValueError, KeyError, TypeError) as erro:
        raise ValueError(f"o baseline {caminho.name} está ilegível ({erro}); apague-o ou grave de novo com --gravar") from None
    return grupos


def gravar_baseline(caminho: pathlib.Path, resumo: dict, versao_do_coverage: str = "") -> None:
    conteudo = {"formato": FORMATO, "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
                "python": sys.version.split()[0], "coverage": versao_do_coverage, "grupos": resumo}
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _tabela(atual: dict, baseline: dict | None) -> list[str]:
    ordem = [grupo for grupo in (*GRUPOS, OUTROS, TOTAL) if grupo in atual]
    linhas = ["Cobertura por parte do pacote (linhas e ramos):", f"  {'parte':<14}{'agora':>8}{'baseline':>10}{'diferença':>11}"]
    for grupo in ordem:
        agora = atual[grupo]["percentual"]
        antigo = baseline.get(grupo, {}).get("percentual") if baseline else None
        linhas.append(f"  {grupo:<14}{agora:>7.1f}%" + (f"{antigo:>9.1f}%{agora - antigo:>+10.1f}" if antigo is not None else f"{'—':>10}{'':>11}"))
    return linhas


def principal(argv: list[str] | None = None, saida=print) -> int:
    parser = argparse.ArgumentParser(description="Catraca de cobertura do pacote.")
    parser.add_argument("--json", type=pathlib.Path, default=JSON_PADRAO)
    parser.add_argument("--baseline", type=pathlib.Path, default=BASELINE_PADRAO)
    parser.add_argument("--tolerancia", type=float, default=TOLERANCIA_PADRAO)
    parser.add_argument("--gravar", action="store_true")
    args = parser.parse_args(argv)
    try:
        relatorio = json.loads(args.json.read_text(encoding="utf-8"))
    except OSError:
        saida(f"Não achei {args.json}. Rode antes: Rodar_Testes.bat cobertura")
        return 2
    except ValueError:
        saida(f"{args.json} não é um relatório JSON do coverage. Rode de novo: Rodar_Testes.bat cobertura")
        return 2
    try:
        atual = resumir(relatorio)
        baseline = None if args.gravar else ler_baseline(args.baseline)
    except ValueError as erro:
        saida(f"Catraca de cobertura: {erro}")
        return 2
    versao = str((relatorio.get("meta") or {}).get("version", "")) if isinstance(relatorio, dict) else ""
    for linha in _tabela(atual, baseline):
        saida(linha)
    if args.gravar or baseline is None:
        gravar_baseline(args.baseline, atual, versao)
        if args.gravar:
            saida(f"Baseline regravado em {args.baseline.name}.")
        else:
            saida(f"Baseline gravado em {args.baseline.name}: a partir de agora a cobertura de cada parte não pode cair "
                  f"mais do que {args.tolerancia:g} ponto(s).")
        return 0
    problemas = comparar(baseline, atual, args.tolerancia)
    if problemas:
        saida("\nA COBERTURA CAIU (o baseline não foi alterado):")
        for problema in problemas:
            saida(f"  - {problema}")
        saida("Código novo precisa de teste. Se a queda é esperada, regrave o baseline: py tests/testsupport/catraca_cobertura.py --gravar")
        return 1
    saida("\nOK: nenhuma parte caiu em relação ao baseline.")
    subiram = melhorias(baseline, atual)
    if subiram:
        saida("Subiram (para subir a catraca: py tests/testsupport/catraca_cobertura.py --gravar): " + "; ".join(subiram))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
