"""Mede quanto tempo o programa leva em operações do dia a dia, com os 3 mapas reais dos testes de compatibilidade.

Para que serve: toda otimização começa por medir e termina por medir de novo (md/DESEMPENHO.md). Este script é a régua.
Ele não é um teste (não falha por lentidão: tempo varia de máquina para máquina); ele imprime uma tabela e, se pedido,
grava um JSON para comparar antes e depois.

Uso, a partir da pasta do projeto:
    python tests/testsupport/medir_desempenho.py                        # tabela na tela
    python tests/testsupport/medir_desempenho.py --json antes.json      # e grava o resultado
    python tests/testsupport/medir_desempenho.py --comparar antes.json  # mostra a diferença em relação a uma medição
    python tests/testsupport/medir_desempenho.py --sem-gui              # só o núcleo (sem janela)
    python tests/testsupport/medir_desempenho.py --repetir 9            # mais repetições (padrão: 5)

Regras para a comparação ser justa: mesma máquina, mesma versão do Python e do PySide6, nada pesado aberto ao lado, e
sempre a MEDIANA (a primeira repetição costuma ser mais lenta: aquecimento de cache). Nada aqui envia teclado ou mouse:
o motor roda com o backend de mentira e o relógio virtual; a janela roda isolada como nos testes (qt_isolation).
"""
import argparse
import gc
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
for pasta in (RAIZ, RAIZ / "tests"):
    if str(pasta) not in sys.path:
        sys.path.insert(0, str(pasta))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _medir(funcao, repetir, preparar=None):
    """Roda `funcao` (com o que `preparar` devolver, se houver) `repetir` vezes e devolve os tempos em milissegundos."""
    tempos = []
    for _ in range(repetir):
        contexto = preparar() if preparar else None
        gc.collect()
        inicio = time.perf_counter()
        funcao(contexto) if preparar else funcao()
        tempos.append((time.perf_counter() - inicio) * 1000.0)
    return tempos


def _kb(texto):
    return f"{len(texto.encode('utf-8')) / 1024:.0f} KB"


# ------------------------------------------------------------------------------------------------- núcleo (sem janela)
def cenarios_do_nucleo(repetir, resultados):
    from automationstudio import core
    from automationstudio.input_system import ExecutionEngine, MockInputBackend
    from automationstudio.project import ProjectManager
    from testsupport.fake_clock import FakeClock
    from testsupport.helpers import load_legacy_maps

    mapas = load_legacy_maps()
    grande = max(mapas, key=lambda nome: len(mapas[nome]))
    texto = mapas[grande]
    mapa = core.map_from_json(texto)

    resultados[f"Ler o mapa '{grande}' do JSON ({_kb(texto)})"] = _medir(lambda: core.map_from_json(texto), repetir)
    resultados[f"Gravar o mapa '{grande}' em JSON"] = _medir(lambda: core.map_to_json(mapa), repetir)
    resultados[f"Validar o mapa '{grande}' ({len(mapa.commands)} comandos)"] = _medir(mapa.validate, repetir)
    resultados[f"Montar a linha do tempo de '{grande}'"] = _medir(lambda: core.build_timeline(mapa), repetir)

    def banco_com_os_tres():
        pasta = Path(tempfile.mkdtemp(prefix="as_desempenho_"))
        gerente = ProjectManager(pasta)
        for t in mapas.values():
            gerente.save_map(core.map_from_json(t))
        return pasta

    resultados["Gravar os 3 mapas no banco (SQLite)"] = _medir(
        lambda pasta: [ProjectManager(pasta).save_map(core.map_from_json(t)) for t in mapas.values()], repetir,
        preparar=lambda: Path(tempfile.mkdtemp(prefix="as_desempenho_")))
    resultados["Abrir o banco e carregar os 3 mapas"] = _medir(lambda pasta: ProjectManager(pasta).load_all(), repetir,
                                                              preparar=banco_com_os_tres)

    def motor():
        relogio = FakeClock()
        backend = MockInputBackend(clock=relogio)
        engine = ExecutionEngine(backend, None, clock=relogio)
        copia = core.map_from_json(texto)
        if hasattr(copia, "repeat_count"):
            copia.repeat_count = 1
        engine.run(copia)
        engine._thread.join(120)
        return backend

    try:
        resultados[f"Executar '{grande}' uma vez no motor (relógio virtual, sem enviar nada)"] = _medir(motor, repetir)
    except Exception as erro:  # o cenário não pode derrubar a medição inteira
        resultados[f"Executar '{grande}' uma vez no motor (relógio virtual, sem enviar nada)"] = f"falhou: {erro!r}"

    _cenarios_de_visao(repetir, resultados)


def _cenarios_de_visao(repetir, resultados):
    try:
        from PySide6.QtGui import QColor, QImage
        from automationstudio import vision
    except Exception as erro:
        resultados["Comparar imagens (vision.compare_images)"] = f"indisponível: {erro!r}"
        return
    for largura, altura in ((400, 300), (1920, 1080)):
        a, b = QImage(largura, altura, QImage.Format.Format_RGB888), QImage(largura, altura, QImage.Format.Format_RGB888)
        a.fill(QColor(255, 255, 255))
        b.fill(QColor(250, 250, 250))
        resultados[f"Comparar duas imagens de {largura}x{altura} (vision.compare_images)"] = _medir(
            lambda a=a, b=b: vision.compare_images(a, b), repetir)


# ------------------------------------------------------------------------------------------------- interface (Qt real)
def cenarios_da_janela(repetir, resultados):
    import pytest
    import PySide6
    if getattr(PySide6, "__as_stub__", False):
        resultados["Janela principal"] = "indisponível: PySide6 é o dublê de testes"
        return
    from automationstudio import core
    from automationstudio.main_window import MainWindow
    from automationstudio.project import AppSettings, ProjectManager
    from testsupport import gui_helpers, qt_isolation
    from testsupport.helpers import load_legacy_maps

    mapas = load_legacy_maps()
    grande = max(mapas, key=lambda nome: len(mapas[nome]))
    pequeno = min(mapas, key=lambda nome: len(mapas[nome]))
    app = gui_helpers.ensure_qapp()
    pasta = Path(tempfile.mkdtemp(prefix="as_desempenho_gui_"))
    gerente = ProjectManager(pasta / "dados")
    for t in mapas.values():
        gerente.save_map(core.map_from_json(t))
    ajustes = AppSettings(pasta / "dados")
    visuais = ajustes.get_visual_settings()
    visuais["onboarding_seen"] = True
    ajustes.set_visual_settings(visuais)

    with pytest.MonkeyPatch.context() as monkeypatch:
        qt_isolation.install(monkeypatch, pasta)
        janelas = []

        def criar(_=None):
            janela = MainWindow(project_dir=pasta / "dados")
            janelas.append(janela)
            return janela

        try:
            tempos = _medir(criar, repetir)
            resultados["Criar a janela principal (3 automações salvas)"] = tempos
            gui_helpers.descartar_janelas(janelas[:-1], app=app)
            del janelas[:-1]  # as já descartadas saem da lista (descartar duas vezes dá erro no Qt)

            janela = janelas[-1]
            janela.show()
            gui_helpers.processar_eventos(50, app=app)

            def abrir_grande():
                janela._select_map_by_name(pequeno)
                gui_helpers.processar_eventos(0, app=app)

            resultados[f"Abrir '{grande}' no editor ({len(core.map_from_json(mapas[grande]).commands)} comandos)"] = _medir(
                lambda _: (janela._select_map_by_name(grande), gui_helpers.processar_eventos(0, app=app)), repetir,
                preparar=abrir_grande)
            resultados["Pintar a janela inteira (editor com o mapa grande)"] = _medir(janela.grab, repetir)

            def abrir_timeline():
                janela._open_timeline()
                gui_helpers.processar_eventos(0, app=app)

            def voltar_ao_editor():
                janela.pages.setCurrentIndex(2)
                gui_helpers.processar_eventos(0, app=app)

            resultados["Abrir a timeline do mapa grande"] = _medir(lambda _: abrir_timeline(), repetir,
                                                                    preparar=lambda: voltar_ao_editor())
            resultados["Pintar a janela inteira (timeline do mapa grande)"] = _medir(janela.grab, repetir)
            voltar_ao_editor()
            resultados["Reaplicar o tema visual (_apply_visual_settings)"] = _medir(
                lambda: (janela._apply_visual_settings(), gui_helpers.processar_eventos(0, app=app)), repetir)
        except Exception as erro:
            resultados.setdefault("Janela principal", f"falhou: {erro!r}")
        finally:
            gui_helpers.descartar_janelas(janelas, app=app)


def cenario_de_inicializacao(repetir, resultados):
    """Custo de importar a janela principal num processo NOVO (o que o usuário espera ao abrir o programa, sem a janela)."""
    codigo = "import time; t = time.perf_counter(); import automationstudio.main_window; print((time.perf_counter() - t) * 1000)"
    ambiente = dict(os.environ, PYTHONPATH=str(RAIZ), QT_QPA_PLATFORM=os.environ["QT_QPA_PLATFORM"])
    tempos = []
    for _ in range(min(repetir, 3)):
        saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, cwd=RAIZ, env=ambiente)
        try:
            tempos.append(float(saida.stdout.strip().splitlines()[-1]))
        except (ValueError, IndexError):
            resultados["Importar a janela principal (processo novo)"] = f"falhou: {saida.stderr.strip()[-200:]}"
            return
    resultados["Importar a janela principal (processo novo)"] = tempos


# ------------------------------------------------------------------------------------------------- saída
def _resumo(tempos):
    return {"mediana_ms": round(statistics.median(tempos), 2), "min_ms": round(min(tempos), 2),
            "max_ms": round(max(tempos), 2), "repeticoes": len(tempos)}


def _tabela(medicoes, anterior=None):
    cabecalho = "| Cenário | Mediana (ms) | Mín | Máx | n |" + (" Antes (ms) | Diferença |" if anterior else "")
    linhas = [cabecalho, "|---|---:|---:|---:|---:|" + ("---:|---:|" if anterior else "")]
    for nome, dados in medicoes.items():
        if isinstance(dados, str):
            linhas.append(f"| {nome} | {dados} | | | |" + (" | |" if anterior else ""))
            continue
        linha = f"| {nome} | {dados['mediana_ms']:.1f} | {dados['min_ms']:.1f} | {dados['max_ms']:.1f} | {dados['repeticoes']} |"
        if anterior:
            antes = anterior.get("medicoes", {}).get(nome)
            if isinstance(antes, dict) and antes["mediana_ms"] > 0:
                variacao = (dados["mediana_ms"] - antes["mediana_ms"]) / antes["mediana_ms"] * 100
                linha += f" {antes['mediana_ms']:.1f} | {variacao:+.0f}% |"
            else:
                linha += " | |"
        linhas.append(linha)
    return "\n".join(linhas)


def main(argv=None):
    leitor = argparse.ArgumentParser(description="Mede o desempenho do Automation Studio com os 3 mapas reais.")
    leitor.add_argument("--repetir", type=int, default=5, help="repetições por cenário (padrão: 5)")
    leitor.add_argument("--sem-gui", action="store_true", help="não mede a janela (só o núcleo)")
    leitor.add_argument("--json", metavar="ARQUIVO", help="grava o resultado neste arquivo")
    leitor.add_argument("--comparar", metavar="ARQUIVO", help="compara com um JSON gravado antes")
    opcoes = leitor.parse_args(argv)

    bruto = {}
    cenario_de_inicializacao(opcoes.repetir, bruto)
    cenarios_do_nucleo(opcoes.repetir, bruto)
    if not opcoes.sem_gui:
        cenarios_da_janela(opcoes.repetir, bruto)

    medicoes = {nome: (_resumo(v) if isinstance(v, list) else v) for nome, v in bruto.items()}
    try:
        import PySide6
        qt = PySide6.__version__
    except Exception:
        qt = "indisponível"
    ambiente = {"python": platform.python_version(), "pyside6": qt, "sistema": f"{platform.system()} {platform.release()}",
                "processador": platform.processor() or platform.machine(), "repeticoes": opcoes.repetir,
                "data": time.strftime("%Y-%m-%d")}
    anterior = None
    if opcoes.comparar:
        anterior = json.loads(Path(opcoes.comparar).read_text(encoding="utf-8"))
        print(f"Comparando com {opcoes.comparar} (ambiente de antes: {anterior.get('ambiente')})\n")
    print(f"Ambiente: {ambiente}\n")
    print(_tabela(medicoes, anterior))
    if opcoes.json:
        Path(opcoes.json).write_text(json.dumps({"ambiente": ambiente, "medicoes": medicoes}, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
        print(f"\nGravado em {opcoes.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
