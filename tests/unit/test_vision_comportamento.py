"""Comportamento de `automationstudio/vision.py` (espera por imagem), sem tela de verdade e sem esperar em tempo real.

Até a integração de 30/10/2026 o módulo tinha 18% de cobertura e nenhum teste de comportamento (ROADMAP, Ponto 6).
Estes testes são de CARACTERIZAÇÃO: fixam o que o código faz hoje, para que o Ponto 6 (captura segura entre threads,
escala do Windows, região, desempenho) e a fase 7.A (casamento de imagem de verdade) possam mexer com uma rede embaixo.

- `compare_images` roda com QImage de verdade (precisa do Qt real: sem ele, os testes são pulados).
- `wait_for_image` roda com a captura trocada por uma sequência de imagens e com o relógio virtual: um teste de 2 s de
  espera leva milissegundos e conta exatamente quantas capturas e quantas pausas houve.
- Uma lacuna conhecida (F4 do roadmap) fica como `xfail` estrito, com o critério da fase 7.A: quando o casamento de
  imagem for corrigido, o teste \"passa\", o executor reclama e o marcador sai.
"""
import types

import pytest

pytest.importorskip("PySide6.QtGui")

from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402

from automationstudio import vision  # noqa: E402

pytestmark = pytest.mark.gui


# ------------------------------------------------------------------------------------------------- ferramentas
def _imagem(largura, altura, rgb=(255, 255, 255), formato=None):
    imagem = QImage(largura, altura, formato or QImage.Format.Format_RGB888)
    imagem.fill(QColor(*rgb))
    return imagem


def _com_retangulo(imagem, x, y, largura, altura, rgb):
    pintor = QPainter(imagem)
    pintor.fillRect(x, y, largura, altura, QColor(*rgb))
    pintor.end()
    return imagem


def _grava(imagem, pasta, nome="modelo.png"):
    caminho = pasta / nome
    assert imagem.save(str(caminho))
    return str(caminho)


def _relogio_virtual(monkeypatch, fake_clock):
    """O `time` que o vision enxerga passa a ser o relógio virtual (só dentro do módulo; o `time` global fica intacto)."""
    monkeypatch.setattr(vision, "time", types.SimpleNamespace(monotonic=fake_clock.monotonic, sleep=fake_clock.sleep))


def _capturas(monkeypatch, imagens):
    """Troca `capture_region` por uma fila de imagens (a última se repete). Devolve a lista de chamadas (region, default_size)."""
    fila, chamadas = list(imagens), []

    def falsa(region=None, default_size=None):
        chamadas.append((region, default_size))
        return fila.pop(0) if len(fila) > 1 else fila[0]

    monkeypatch.setattr(vision, "capture_region", falsa)
    return chamadas


class _EventoFalso:
    """Faz o papel de `threading.Event` com o relógio virtual: `wait` só avança o tempo."""

    def __init__(self, relogio, parado=False, parar_depois_de_esperas=None):
        self._relogio, self._parado, self._limite = relogio, parado, parar_depois_de_esperas

    def is_set(self):
        return self._parado or (self._limite is not None and len(self._relogio.sleeps) >= self._limite)

    def wait(self, segundos):
        self._relogio.sleep(segundos)


class _TelaFalsa:
    def __init__(self, imagem):
        self.chamadas, self._imagem = [], imagem

    def grabWindow(self, *argumentos):
        self.chamadas.append(argumentos)
        return _PixmapFalso(self._imagem)


class _PixmapFalso:
    def __init__(self, imagem):
        self._imagem = imagem

    def isNull(self):
        return self._imagem.isNull()

    def toImage(self):
        return self._imagem


def _aplicacao_com_tela(monkeypatch, tela):
    aplicacao = types.SimpleNamespace(primaryScreen=lambda: tela)
    monkeypatch.setattr(vision, "QGuiApplication", types.SimpleNamespace(instance=lambda: aplicacao))


# ------------------------------------------------------------------------------------------------- compare_images
def test_vision_imagens_identicas_tem_similaridade_1(gui_real):
    assert vision.compare_images(_imagem(20, 10, (10, 200, 30)), _imagem(20, 10, (10, 200, 30))) == 1.0


def test_vision_preto_contra_branco_tem_similaridade_0(gui_real):
    assert vision.compare_images(_imagem(8, 8, (0, 0, 0)), _imagem(8, 8, (255, 255, 255))) == 0.0


def test_vision_metade_da_imagem_diferente_da_similaridade_meio(gui_real):
    modelo = _imagem(10, 10, (255, 255, 255))
    atual = _com_retangulo(_imagem(10, 10, (255, 255, 255)), 0, 0, 5, 10, (0, 0, 0))
    assert vision.compare_images(modelo, atual) == pytest.approx(0.5)


def test_vision_tamanhos_diferentes_dao_similaridade_0(gui_real):
    assert vision.compare_images(_imagem(10, 10), _imagem(10, 11)) == 0.0


def test_vision_imagem_nula_da_similaridade_0(gui_real):
    assert vision.compare_images(QImage(), _imagem(10, 10)) == 0.0
    assert vision.compare_images(QImage(), QImage()) == 0.0


def test_vision_a_comparacao_e_simetrica(gui_real):
    a = _com_retangulo(_imagem(12, 9, (200, 10, 10)), 2, 2, 4, 3, (0, 0, 255))
    b = _imagem(12, 9, (30, 60, 90))
    assert vision.compare_images(a, b) == vision.compare_images(b, a)


def test_vision_formatos_de_pixel_diferentes_com_a_mesma_cor_sao_iguais(gui_real):
    argb = _imagem(6, 4, (90, 120, 150), QImage.Format.Format_ARGB32)
    rgb = _imagem(6, 4, (90, 120, 150), QImage.Format.Format_RGB888)
    assert vision.compare_images(argb, rgb) == 1.0


def test_vision_largura_impar_nao_le_o_preenchimento_da_linha(gui_real):
    # RGB888 alinha cada linha a 4 bytes: 5 pixels = 15 bytes + 1 de preenchimento. Um pixel de 15 trocado de preto para
    # branco muda 765 de 15*3*255 possíveis. Se o código lesse o preenchimento, o número sairia diferente.
    modelo = _imagem(5, 3, (0, 0, 0))
    atual = _com_retangulo(_imagem(5, 3, (0, 0, 0)), 4, 2, 1, 1, (255, 255, 255))
    assert vision.compare_images(modelo, atual) == pytest.approx(1.0 - 765 / (45 * 255))


def test_vision_imagem_grande_usa_amostragem_e_ainda_reconhece_imagens_iguais(gui_real):
    # 1000x1000 passa de 250 mil pixels: a comparação pula pixels (passo 2) para não pesar na CPU.
    grande = _com_retangulo(_imagem(1000, 1000, (255, 255, 255)), 100, 100, 300, 300, (10, 20, 30))
    copia = QImage(grande)
    assert vision.compare_images(grande, copia) == 1.0


def test_vision_um_elemento_de_10_por_cento_da_regiao_e_distinguido_com_confianca_95(gui_real):
    modelo = _com_retangulo(_imagem(100, 100), 0, 0, 100, 10, (0, 0, 0))  # 10% da área
    similaridade = vision.compare_images(modelo, _imagem(100, 100))
    assert similaridade == pytest.approx(0.9)
    assert similaridade < 0.95, "abaixo da confiança padrão: a espera NÃO conta o elemento como encontrado"


# ------------------------------------------------------------------------------------------------- capture_region
def test_vision_captura_sem_aplicacao_qt_avisa_com_erro_claro(gui_real, monkeypatch):
    monkeypatch.setattr(vision, "QGuiApplication", types.SimpleNamespace(instance=lambda: None))
    with pytest.raises(vision.ImageWaitError, match="aplicação Qt"):
        vision.capture_region({"x": 0, "y": 0, "w": 10, "h": 10})


def test_vision_captura_sem_tela_disponivel_avisa_com_erro_claro(gui_real, monkeypatch):
    _aplicacao_com_tela(monkeypatch, None)
    with pytest.raises(vision.ImageWaitError, match="Nenhuma tela"):
        vision.capture_region({"x": 0, "y": 0, "w": 10, "h": 10})


def test_vision_captura_com_regiao_pede_exatamente_aquela_regiao(gui_real, monkeypatch):
    tela = _TelaFalsa(_imagem(30, 20))
    _aplicacao_com_tela(monkeypatch, tela)
    imagem = vision.capture_region({"x": 5, "y": "6", "w": 30, "h": 20}, default_size=(99, 99))
    assert tela.chamadas == [(0, 5, 6, 30, 20)], "texto numérico vira inteiro e a região vence o tamanho padrão"
    assert (imagem.width(), imagem.height()) == (30, 20)


def test_vision_captura_sem_regiao_usa_o_tamanho_padrao_na_origem(gui_real, monkeypatch):
    tela = _TelaFalsa(_imagem(8, 6))
    _aplicacao_com_tela(monkeypatch, tela)
    vision.capture_region(None, default_size=(8, 6))
    vision.capture_region({"x": 3, "y": 4, "w": 0, "h": 0}, default_size=(8, 6))
    assert tela.chamadas == [(0, 0, 0, 8, 6), (0, 3, 4, 8, 6)], "largura ou altura 0 na região cai no tamanho padrão"


def test_vision_captura_sem_regiao_e_sem_tamanho_pega_a_tela_inteira(gui_real, monkeypatch):
    tela = _TelaFalsa(_imagem(8, 6))
    _aplicacao_com_tela(monkeypatch, tela)
    vision.capture_region(None)
    vision.capture_region({}, default_size=(0, 5))
    assert tela.chamadas == [(0,), (0,)]


def test_vision_captura_nula_da_erro_em_vez_de_imagem_vazia(gui_real, monkeypatch):
    _aplicacao_com_tela(monkeypatch, _TelaFalsa(QImage()))
    with pytest.raises(vision.ImageWaitError, match="Não foi possível capturar"):
        vision.capture_region({"x": 0, "y": 0, "w": 4, "h": 4})


# ------------------------------------------------------------------------------------------------- template_match
def test_vision_sem_opencv_o_casamento_volta_para_a_comparacao_simples(gui_real, monkeypatch):
    monkeypatch.setattr(vision, "_OPENCV_AVAILABLE", False)
    modelo = _com_retangulo(_imagem(10, 10), 0, 0, 5, 10, (0, 0, 0))
    atual = _imagem(10, 10)
    assert vision.template_match(modelo, atual, 0.95) == vision.compare_images(modelo, atual)


def test_vision_com_opencv_acha_o_modelo_dentro_de_uma_imagem_maior(gui_real):
    pytest.importorskip("cv2")
    fundo = _com_retangulo(_imagem(60, 40, (255, 255, 255)), 20, 10, 10, 8, (20, 40, 200))
    recorte = fundo.copy(18, 8, 14, 12)
    assert vision.template_match(recorte, fundo, 0.95) == pytest.approx(1.0, abs=1e-3)


def test_vision_com_opencv_modelo_maior_que_a_imagem_da_zero(gui_real):
    pytest.importorskip("cv2")
    assert vision.template_match(_imagem(30, 30), _imagem(10, 10), 0.95) == 0.0


# ------------------------------------------------------------------------------------------------- wait_for_image
def test_vision_imagem_inexistente_avisa_com_o_caminho(gui_real, tmp_path):
    with pytest.raises(vision.ImageWaitError, match="Imagem não encontrada"):
        vision.wait_for_image(str(tmp_path / "nao_existe.png"))


def test_vision_arquivo_que_nao_e_imagem_avisa(gui_real, tmp_path):
    falso = tmp_path / "falso.png"
    falso.write_text("isto não é um PNG", encoding="utf-8")
    with pytest.raises(vision.ImageWaitError, match="Não foi possível abrir"):
        vision.wait_for_image(str(falso))


def test_vision_encontra_na_primeira_captura_sem_esperar(gui_real, monkeypatch, fake_clock, tmp_path):
    _relogio_virtual(monkeypatch, fake_clock)
    modelo = _imagem(10, 10, (30, 120, 60))
    chamadas = _capturas(monkeypatch, [_imagem(10, 10, (30, 120, 60))])
    resultado = vision.wait_for_image(_grava(modelo, tmp_path), timeout=5)
    assert resultado.found and resultado.similarity >= 0.95 and resultado.elapsed == 0.0
    assert len(chamadas) == 1 and fake_clock.sleeps == []


def test_vision_a_imagem_aparece_depois_de_duas_tentativas(gui_real, monkeypatch, fake_clock, tmp_path):
    # A automação segue no instante em que a imagem aparece (critério da fase 7.A): 2 pausas de 0,5 s, na 3ª captura.
    _relogio_virtual(monkeypatch, fake_clock)
    modelo = _com_retangulo(_imagem(10, 10), 0, 0, 10, 10, (200, 0, 0))
    vazio = _imagem(10, 10)
    chamadas = _capturas(monkeypatch, [vazio, vazio, QImage(modelo)])
    resultado = vision.wait_for_image(_grava(modelo, tmp_path), interval=0.5, timeout=30)
    assert resultado.found
    assert len(chamadas) == 3 and fake_clock.sleeps == [0.5, 0.5]
    assert resultado.elapsed == pytest.approx(1.0)


def test_vision_estourar_o_tempo_devolve_nao_encontrado_com_a_ultima_similaridade(gui_real, monkeypatch, fake_clock, tmp_path):
    _relogio_virtual(monkeypatch, fake_clock)
    chamadas = _capturas(monkeypatch, [_imagem(10, 10, (255, 255, 255))])
    resultado = vision.wait_for_image(_grava(_imagem(10, 10, (0, 0, 0)), tmp_path), interval=0.5, timeout=2.0)
    assert not resultado.found and resultado.similarity == 0.0
    assert resultado.elapsed == pytest.approx(2.0)
    assert len(chamadas) == 5 and fake_clock.sleeps == [0.5] * 4, "capturas em 0; 0,5; 1; 1,5 e 2 s"


def test_vision_evento_de_parada_ja_ativo_nao_captura_nada(gui_real, monkeypatch, fake_clock, tmp_path):
    _relogio_virtual(monkeypatch, fake_clock)
    chamadas = _capturas(monkeypatch, [_imagem(10, 10)])
    resultado = vision.wait_for_image(_grava(_imagem(10, 10), tmp_path), stop_event=_EventoFalso(fake_clock, parado=True))
    assert (resultado.found, resultado.similarity, resultado.elapsed) == (False, 0.0, 0.0)
    assert chamadas == []


def test_vision_sem_limite_de_tempo_so_o_evento_de_parada_encerra_a_espera(gui_real, monkeypatch, fake_clock, tmp_path):
    _relogio_virtual(monkeypatch, fake_clock)
    chamadas = _capturas(monkeypatch, [_imagem(10, 10, (255, 255, 255))])
    parada = _EventoFalso(fake_clock, parar_depois_de_esperas=3)
    resultado = vision.wait_for_image(_grava(_imagem(10, 10, (0, 0, 0)), tmp_path), interval=0.5, timeout=0.0, stop_event=parada)
    assert not resultado.found and resultado.similarity == 0.0
    assert len(chamadas) == 3 and resultado.elapsed == pytest.approx(1.5)


def test_vision_intervalo_zero_ou_negativo_vira_o_minimo_de_50_ms(gui_real, monkeypatch, fake_clock, tmp_path):
    _relogio_virtual(monkeypatch, fake_clock)
    _capturas(monkeypatch, [_imagem(10, 10, (255, 255, 255))])
    caminho = _grava(_imagem(10, 10, (0, 0, 0)), tmp_path)
    vision.wait_for_image(caminho, interval=0.0, timeout=0.1)
    vision.wait_for_image(caminho, interval=-3.0, timeout=0.1)
    assert fake_clock.sleeps == [0.05] * 4


def test_vision_similaridade_igual_a_confianca_conta_como_encontrado(gui_real, monkeypatch, fake_clock, tmp_path):
    _relogio_virtual(monkeypatch, fake_clock)
    modelo = _imagem(10, 10, (40, 40, 40))
    _capturas(monkeypatch, [QImage(modelo)])
    assert vision.wait_for_image(_grava(modelo, tmp_path), confidence=1.0, timeout=1).found


def test_vision_a_regiao_e_o_tamanho_do_modelo_chegam_a_captura(gui_real, monkeypatch, fake_clock, tmp_path):
    _relogio_virtual(monkeypatch, fake_clock)
    modelo = _imagem(12, 7, (1, 2, 3))
    caminho = _grava(modelo, tmp_path)
    regiao = {"x": 1, "y": 2, "w": 3, "h": 4}
    chamadas = _capturas(monkeypatch, [QImage(modelo)])
    vision.wait_for_image(caminho, region=regiao, timeout=1)
    vision.wait_for_image(caminho, region=regiao, timeout=1, search=True)
    assert chamadas[0] == (regiao, (12, 7)), "comparação direta: captura do tamanho do modelo"
    assert chamadas[1] == (regiao, None), "busca (search): captura sem tamanho padrão, a imagem pode ser maior que o modelo"


def test_vision_modo_busca_usa_o_casamento_de_modelo_e_nao_a_comparacao_direta(gui_real, monkeypatch, fake_clock, tmp_path):
    _relogio_virtual(monkeypatch, fake_clock)
    _capturas(monkeypatch, [_imagem(10, 10)])
    usadas = []
    monkeypatch.setattr(vision, "template_match", lambda modelo, atual, confianca: usadas.append(confianca) or 0.99)

    def proibida(*argumentos):
        raise AssertionError("o modo busca não deve usar compare_images")

    monkeypatch.setattr(vision, "compare_images", proibida)
    resultado = vision.wait_for_image(_grava(_imagem(10, 10), tmp_path), confidence=0.9, timeout=1, search=True)
    assert resultado.found and resultado.similarity == 0.99 and usadas == [0.9]


def test_vision_o_resultado_da_espera_e_imutavel(gui_real):
    resultado = vision.ImageMatchResult(True, 1.0, 0.0)
    with pytest.raises(Exception, match="assign|frozen|cannot"):
        resultado.found = False


# ------------------------------------------------------------------------------------------------- lacuna conhecida
@pytest.mark.xfail(strict=True, reason="F4 do roadmap (fase 7.A): a comparação é uma média; um elemento de 4% da região que "
                   "falta na tela dá 0,96, acima da confiança padrão 0,95, e a espera termina como se ele estivesse lá. "
                   "Critério da 7.A: um elemento de 4% da região é distinguido.")
def test_vision_elemento_pequeno_ausente_nao_deveria_contar_como_encontrado(gui_real, monkeypatch, fake_clock, tmp_path):
    _relogio_virtual(monkeypatch, fake_clock)
    modelo = _com_retangulo(_imagem(100, 100), 40, 40, 20, 20, (0, 0, 0))  # botão escuro de 20x20 = 4% da região
    _capturas(monkeypatch, [_imagem(100, 100)])  # na tela o botão NÃO está
    resultado = vision.wait_for_image(_grava(modelo, tmp_path), confidence=0.95, timeout=0.1)
    assert not resultado.found
