"""e2e do Windows, MODO REAL: envia teclado e mouse DE VERDADE ao Windows e confere o que chegou.

NÃO RODA POR PADRÃO. Só roda no Windows e só com AS_ALLOW_REAL_INPUT=1 (Rodar_Testes.bat windows). Durante a rodada (cerca
de 15 segundos) NÃO mexa no teclado nem no mouse: o teste abre uma janela própria, a traz para frente e só envia entrada
depois de confirmar que ela está em primeiro plano; se outro programa tomar o foco, o teste é PULADO e nada é enviado.

São as únicas verificações que respondem "o Windows aceita o que o programa envia?". Cada uma declara a premissa que
confirma (testsupport/verificacoes_e2e.py). Uma FALHA aqui é informação: me envie a saída; não "conserte" o teste.
As mesmas verificações rodam sempre, em modo simulado, em test_e2e_simulado.py.
"""
import pytest

from testsupport import e2e_windows as e2e
from testsupport import verificacoes_e2e as v

pytestmark = [pytest.mark.windows_only, pytest.mark.hardware]


def test_teclas_modificadoras_mudam_o_estado_do_sistema(ambiente_real):
    e2e.rodar(v.teclas_modificadoras_mudam_o_estado_do_sistema, ambiente_real)


def test_cursor_absoluto_e_relativo_move_o_cursor(ambiente_real):
    e2e.rodar(v.cursor_absoluto_e_relativo_move_o_cursor, ambiente_real)


def test_botoes_laterais_do_mouse_chegam_ao_sistema(ambiente_real):
    e2e.rodar(v.botoes_laterais_do_mouse_chegam_ao_sistema, ambiente_real)


def test_texto_com_acentos_chega_inteiro_na_janela(ambiente_real):
    e2e.rodar(v.texto_com_acentos_chega_inteiro_na_janela, ambiente_real)


def test_caractere_fora_do_layout_chega_pelo_caminho_unicode(ambiente_real):
    e2e.rodar(v.caractere_fora_do_layout_chega_pelo_caminho_unicode, ambiente_real)


def test_cliques_e_rolagem_chegam_a_janela_sob_o_cursor(ambiente_real):
    e2e.rodar(v.cliques_e_rolagem_chegam_a_janela_sob_o_cursor, ambiente_real)


def test_o_motor_executa_um_mapa_pequeno_de_verdade(ambiente_real):
    e2e.rodar(v.o_motor_executa_um_mapa_pequeno_de_verdade, ambiente_real)


def test_o_monitor_global_enxerga_o_teclado_enviado_pelo_programa(ambiente_real):
    e2e.rodar(v.o_monitor_global_enxerga_o_teclado_enviado_pelo_programa, ambiente_real)


def test_a_lista_de_processos_enxerga_o_proprio_python_e_o_explorer(ambiente_real):
    e2e.rodar(v.a_lista_de_processos_enxerga_o_proprio_python_e_o_explorer, ambiente_real)
