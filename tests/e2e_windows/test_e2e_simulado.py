"""e2e do Windows, MODO SIMULADO: as mesmas verificações que rodam no Windows de verdade, contra um USER32 falso.

Rodam SEMPRE, em qualquer sistema, porque provam duas coisas: que a verificação em si está certa (assim uma rodada real
no Windows só falha por causa do Windows) e que o código e2e não apodrece entre uma rodada real e outra. Elas NÃO provam
nada sobre o Windows: para isso existe test_e2e_windows_real.py.
"""
from testsupport import e2e_windows as e2e
from testsupport import verificacoes_e2e as v


def test_teclas_modificadoras_mudam_o_estado_do_sistema(ambiente_simulado):
    e2e.rodar(v.teclas_modificadoras_mudam_o_estado_do_sistema, ambiente_simulado)


def test_cursor_absoluto_e_relativo_move_o_cursor(ambiente_simulado):
    e2e.rodar(v.cursor_absoluto_e_relativo_move_o_cursor, ambiente_simulado)


def test_botoes_laterais_do_mouse_chegam_ao_sistema(ambiente_simulado):
    e2e.rodar(v.botoes_laterais_do_mouse_chegam_ao_sistema, ambiente_simulado)


def test_texto_com_acentos_chega_inteiro_na_janela(ambiente_simulado):
    e2e.rodar(v.texto_com_acentos_chega_inteiro_na_janela, ambiente_simulado)


def test_caractere_fora_do_layout_chega_pelo_caminho_unicode(ambiente_simulado):
    e2e.rodar(v.caractere_fora_do_layout_chega_pelo_caminho_unicode, ambiente_simulado)


def test_cliques_e_rolagem_chegam_a_janela_sob_o_cursor(ambiente_simulado):
    e2e.rodar(v.cliques_e_rolagem_chegam_a_janela_sob_o_cursor, ambiente_simulado)


def test_o_motor_executa_um_mapa_pequeno_de_verdade(ambiente_simulado):
    e2e.rodar(v.o_motor_executa_um_mapa_pequeno_de_verdade, ambiente_simulado)
