"""Aviso de janela de administrador (F51): a regra, os textos, a leitura do Windows (simulada) e o vigia.

Nada aqui usa o Windows de verdade. A leitura roda contra um Windows de mentira (testsupport/fakes_elevacao.py), que segue as
regras que se ACREDITA valerem no Windows (inclusive negar acesso demais a processo elevado), e o vigia roda contra uma sonda
falsa e um relógio virtual. O que só o Windows de verdade mostra está em md/ENTREGA_AVISO_ADMINISTRADOR.md.

Sem Qt: o módulo testado (automationstudio/elevacao.py) não usa Qt. A parte com Qt está em test_aviso_administrador_ui.py.
"""
import ctypes
import dataclasses
import os
import pathlib
from ctypes import wintypes

import pytest

from automationstudio import elevacao
from automationstudio.elevacao import (ARQUIVO_PARA_ADMINISTRADOR, ONDE_CURSOR, ONDE_FRENTE, Aviso, Elevacao, Situacao,
                                       SondaWindows, VigiaDeElevacao, criar_vigia, montar_aviso, situacao)
from testsupport.fake_clock import FakeClock
from testsupport.fakes_elevacao import (ERRO_ACESSO_NEGADO, ERRO_PARAMETRO_INVALIDO, PROCESS_QUERY_LIMITED_INFORMATION,
                                        TOKEN_QUERY, MundoWindows, SondaFalsa)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SIM, NAO, NEGADA, DESCONHECIDA = Elevacao.SIM, Elevacao.NAO, Elevacao.NEGADA, Elevacao.DESCONHECIDA


# ------------------------------------------------------------------------------------------------------- a regra
TABELA_DA_REGRA = {
    (SIM, SIM): Situacao.LIVRE, (SIM, NAO): Situacao.LIVRE, (SIM, NEGADA): Situacao.LIVRE, (SIM, DESCONHECIDA): Situacao.LIVRE,
    (NAO, SIM): Situacao.BLOQUEADA, (NAO, NAO): Situacao.LIVRE, (NAO, NEGADA): Situacao.PROVAVEL,
    (NAO, DESCONHECIDA): Situacao.INCERTA,
    (NEGADA, SIM): Situacao.INCERTA, (NEGADA, NAO): Situacao.INCERTA, (NEGADA, NEGADA): Situacao.INCERTA,
    (NEGADA, DESCONHECIDA): Situacao.INCERTA,
    (DESCONHECIDA, SIM): Situacao.INCERTA, (DESCONHECIDA, NAO): Situacao.INCERTA, (DESCONHECIDA, NEGADA): Situacao.INCERTA,
    (DESCONHECIDA, DESCONHECIDA): Situacao.INCERTA,
}


def test_a_tabela_da_regra_cobre_as_16_combinacoes():
    assert set(TABELA_DA_REGRA) == {(p, a) for p in Elevacao for a in Elevacao}


@pytest.mark.parametrize("programa,alvo", sorted(TABELA_DA_REGRA, key=lambda par: (par[0].value, par[1].value)))
def test_a_regra_para_cada_combinacao(programa, alvo):
    assert situacao(programa, alvo) is TABELA_DA_REGRA[(programa, alvo)]


def test_so_programa_comum_diante_de_alvo_elevado_ou_que_nega_leitura_gera_aviso():
    com_aviso = {par for par, estado in TABELA_DA_REGRA.items() if estado in (Situacao.BLOQUEADA, Situacao.PROVAVEL)}
    assert com_aviso == {(NAO, SIM), (NAO, NEGADA)}


def test_programa_elevado_nunca_e_barrado():
    assert all(situacao(SIM, alvo) is Situacao.LIVRE for alvo in Elevacao)


# ------------------------------------------------------------------------------------------------------- os textos
def test_so_bloqueada_e_provavel_tem_aviso():
    for estado in Situacao:
        aviso = montar_aviso(estado, 5, "Taskmgr.exe", ONDE_FRENTE)
        assert (aviso is not None) == (estado in (Situacao.BLOQUEADA, Situacao.PROVAVEL)), estado


def test_o_aviso_de_bloqueio_diz_qual_janela_o_que_acontece_e_como_resolver():
    aviso = montar_aviso(Situacao.BLOQUEADA, 500, "Taskmgr.exe", ONDE_FRENTE)
    assert (aviso.situacao, aviso.pid, aviso.nome, aviso.onde) == (Situacao.BLOQUEADA, 500, "Taskmgr.exe", ONDE_FRENTE)
    assert "administrador" in aviso.curto and "Taskmgr.exe" in aviso.curto
    assert "Taskmgr.exe" in aviso.longo and "não mostra nenhum erro" in aviso.longo
    assert "atalho" in aviso.longo and "parar" in aviso.longo      # a tecla de parada também pode ficar muda
    assert ARQUIVO_PARA_ADMINISTRADOR in aviso.longo


def test_o_aviso_de_provavel_diz_que_pode_ser_e_nao_afirma():
    aviso = montar_aviso(Situacao.PROVAVEL, 500, "Taskmgr.exe", ONDE_FRENTE)
    assert aviso.curto.startswith("⚠ Pode ser") and "Taskmgr.exe" in aviso.curto
    assert "Não deu para ler" in aviso.longo and "pode acontecer" in aviso.longo
    assert ARQUIVO_PARA_ADMINISTRADOR in aviso.longo
    assert not aviso.longo.startswith("A janela") and "não mostra nenhum erro" not in aviso.longo  # afirmar é do aviso de bloqueio


@pytest.mark.parametrize("onde,frase", [(ONDE_FRENTE, "da frente"), (ONDE_CURSOR, "sob o mouse")])
def test_sem_nome_o_aviso_diz_onde_esta_a_janela(onde, frase):
    for estado in (Situacao.BLOQUEADA, Situacao.PROVAVEL):
        aviso = montar_aviso(estado, 7, "", onde)
        assert f"A janela {frase}" in aviso.longo or f"da janela {frase}" in aviso.longo, aviso.longo
        assert "()" not in aviso.curto and "(" not in aviso.curto


def test_o_nome_so_com_espacos_conta_como_sem_nome():
    assert montar_aviso(Situacao.BLOQUEADA, 7, "   ", ONDE_FRENTE) == montar_aviso(Situacao.BLOQUEADA, 7, "", ONDE_FRENTE)


def test_os_textos_nao_tem_travessao_nem_quebra_de_linha():
    for estado in (Situacao.BLOQUEADA, Situacao.PROVAVEL):
        for nome in ("Taskmgr.exe", ""):
            for onde in (ONDE_FRENTE, ONDE_CURSOR):
                aviso = montar_aviso(estado, 7, nome, onde)
                for texto in (aviso.curto, aviso.longo):
                    assert not {"—", "–", "\n", "\r"} & set(texto), texto
                    assert " - " not in texto, texto


def test_o_texto_curto_cabe_na_barra_de_status():
    for estado in (Situacao.BLOQUEADA, Situacao.PROVAVEL):
        aviso = montar_aviso(estado, 7, "AplicativoDeNomeBemComprido.exe", ONDE_FRENTE)
        assert len(aviso.curto) <= 100, (estado, len(aviso.curto))


def test_o_arquivo_que_o_aviso_manda_abrir_existe_na_pasta_do_programa():
    assert (RAIZ / ARQUIVO_PARA_ADMINISTRADOR).is_file(), "o aviso mandaria o usuário abrir um arquivo que não existe"


def test_o_aviso_e_imutavel():
    aviso = montar_aviso(Situacao.BLOQUEADA, 7, "x.exe", ONDE_FRENTE)
    assert isinstance(aviso, Aviso)
    with pytest.raises(dataclasses.FrozenInstanceError):
        aviso.pid = 8


# ------------------------------------------------------------------------------------- a leitura (Windows simulado)
def _mundo_com_processo(**ajustes):
    """Um mundo com o processo 500 (nome Taskmgr.exe, comum) ajustado por `ajustes`, e a sonda que lê esse mundo."""
    mundo = MundoWindows(eu_elevado=ajustes.pop("eu_elevado", False))
    configuracao = {"nome": "Taskmgr.exe", "elevado": False, "abrir": 0, "token": 0, "info": 0}
    configuracao.update(ajustes)
    mundo.adicionar_processo(500, **configuracao)
    return mundo, mundo.criar_sonda()


# cenário -> (ajustes do processo 500, (nome, elevação) esperados)
CENARIOS_DE_PROCESSO = {
    "elevado": ({"elevado": True}, ("Taskmgr.exe", SIM)),
    "comum": ({"elevado": False}, ("Taskmgr.exe", NAO)),
    "abrir negado": ({"abrir": ERRO_ACESSO_NEGADO}, ("", NEGADA)),
    "abrir com outro erro": ({"abrir": ERRO_PARAMETRO_INVALIDO}, ("", DESCONHECIDA)),
    "token negado": ({"token": ERRO_ACESSO_NEGADO}, ("Taskmgr.exe", NEGADA)),
    "token com outro erro": ({"token": ERRO_PARAMETRO_INVALIDO}, ("Taskmgr.exe", DESCONHECIDA)),
    "informação do token falha": ({"info": ERRO_PARAMETRO_INVALIDO}, ("Taskmgr.exe", DESCONHECIDA)),
    "nome ilegível": ({"nome": None, "elevado": True}, ("", SIM)),
}


@pytest.mark.parametrize("cenario", list(CENARIOS_DE_PROCESSO))
def test_ler_processo_em_cada_cenario(cenario):
    ajustes, esperado = CENARIOS_DE_PROCESSO[cenario]
    _mundo, sonda = _mundo_com_processo(**ajustes)
    assert sonda.ler_processo(500) == esperado


@pytest.mark.parametrize("cenario", list(CENARIOS_DE_PROCESSO))
def test_nenhuma_alca_fica_aberta_nem_e_fechada_duas_vezes(cenario):
    ajustes, _esperado = CENARIOS_DE_PROCESSO[cenario]
    mundo, sonda = _mundo_com_processo(**ajustes)
    sonda.ler_processo(500)
    assert mundo.alcas_abertas() == [], "ficou alça aberta (vazamento)"
    assert mundo.fechamentos_invalidos == [], "fechou uma alça que não era dele (ou duas vezes)"


def test_processo_que_nao_existe_e_desconhecido_e_nao_deixa_alca():
    mundo, sonda = _mundo_com_processo()
    assert sonda.ler_processo(999) == ("", DESCONHECIDA)
    assert mundo.alcas_abertas() == [] and mundo.fechamentos_invalidos == []


def test_o_nome_devolvido_e_so_o_do_executavel_sem_a_pasta():
    _mundo, sonda = _mundo_com_processo(nome="notepad.exe")
    assert sonda.ler_processo(500)[0] == "notepad.exe"


def test_pede_o_minimo_de_acesso_ao_processo_e_ao_token():
    """Pedir mais (PROCESS_ALL_ACCESS, TOKEN_ALL_ACCESS) falharia justamente com os processos elevados, que são os que
    interessam. O Windows simulado nega acesso demais a processo elevado, então ler como SIM prova que o pedido foi o mínimo."""
    mundo, sonda = _mundo_com_processo(elevado=True)
    assert sonda.ler_processo(500) == ("Taskmgr.exe", SIM)
    assert mundo.pedidos_de_acesso == [("processo", PROCESS_QUERY_LIMITED_INFORMATION), ("token", TOKEN_QUERY)]
    assert (PROCESS_QUERY_LIMITED_INFORMATION, TOKEN_QUERY) == (SondaWindows.PROCESS_QUERY_LIMITED_INFORMATION,
                                                                SondaWindows.TOKEN_QUERY) == (0x1000, 0x0008)


def test_controle_o_windows_simulado_nega_acesso_demais_a_processo_elevado():
    """Sem este controle o teste acima não provaria nada: aqui o pedido grande é negado de fato (e o pequeno passa)."""
    mundo, _sonda = _mundo_com_processo(elevado=True)
    assert mundo.kernel32.OpenProcess(0x1F0FFF, False, 500) == 0 and mundo.erro == ERRO_ACESSO_NEGADO
    assert mundo.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, 500) != 0
    comum, _ = _mundo_com_processo(elevado=False)
    assert comum.kernel32.OpenProcess(0x1F0FFF, False, 500) != 0   # processo comum: o pedido grande passa
    dono, _ = _mundo_com_processo(elevado=True, eu_elevado=True)
    assert dono.kernel32.OpenProcess(0x1F0FFF, False, 500) != 0    # programa elevado: também passa


@pytest.mark.parametrize("elevado,esperado", [(True, SIM), (False, NAO)])
def test_le_a_elevacao_do_proprio_programa(elevado, esperado):
    mundo = MundoWindows(eu_elevado=elevado)
    assert mundo.criar_sonda().elevacao_do_programa() is esperado
    assert mundo.alcas_abertas() == [] and mundo.fechamentos_invalidos == []


def test_falha_ao_ler_o_proprio_token_e_desconhecida_e_nao_negada():
    mundo = MundoWindows()
    mundo.token_proprio_falha = ERRO_ACESSO_NEGADO
    assert mundo.criar_sonda().elevacao_do_programa() is DESCONHECIDA


def test_a_pseudo_alca_do_programa_nao_e_fechada():
    mundo = MundoWindows()
    mundo.criar_sonda().elevacao_do_programa()
    assert mundo.fechamentos_invalidos == [], "CloseHandle na pseudo-alça do processo atual"


def test_meu_pid_e_o_do_processo_atual():
    assert MundoWindows().criar_sonda().meu_pid() == os.getpid()


def test_janela_da_frente():
    mundo = MundoWindows()
    sonda = mundo.criar_sonda()
    assert sonda.pid_da_janela_da_frente() is None          # nenhuma janela em primeiro plano
    mundo.adicionar_janela(11, 500, na_frente=True)
    assert sonda.pid_da_janela_da_frente() == 500
    mundo.frente = 99                                       # uma janela que o Windows não sabe de quem é
    assert sonda.pid_da_janela_da_frente() is None


def test_janela_sob_o_cursor_usa_o_ponto_onde_o_cursor_esta():
    mundo = MundoWindows()
    mundo.adicionar_janela(21, 111, sob_o_cursor=(0, 0))         # isca: o que haveria num ponto qualquer (0, 0)
    mundo.adicionar_janela(22, 222, sob_o_cursor=(321, 654))     # o cursor está aqui (a última chamada põe o cursor)
    assert mundo.cursor == (321, 654)
    assert mundo.criar_sonda().pid_da_janela_sob_o_cursor() == 222


def test_cursor_ilegivel_ou_sem_janela_embaixo_nao_tem_pid():
    mundo = MundoWindows()
    mundo.adicionar_janela(23, 333, sob_o_cursor=(0, 0))         # isca: a janela que estaria num ponto (0, 0) qualquer
    mundo.adicionar_janela(22, 222, sob_o_cursor=(5, 6))
    sonda = mundo.criar_sonda()
    mundo.cursor = (50, 60)                                      # nenhuma janela neste ponto
    assert sonda.pid_da_janela_sob_o_cursor() is None
    mundo.cursor, mundo.cursor_falha = (5, 6), True              # GetCursorPos falha
    assert sonda.pid_da_janela_sob_o_cursor() is None


def test_as_assinaturas_declaradas_sao_de_64_bits():
    """Sem `restype` o ctypes devolve int de 32 bits e corta alças e ponteiros no Windows de 64 bits: bug que o simulado, sozinho,
    não mostra. Por isso o teste confere o que a sonda declarou em cada função."""
    mundo = MundoWindows()
    mundo.criar_sonda()
    W = wintypes
    esperado = {
        mundo.user32.GetForegroundWindow: ([], W.HWND),
        mundo.user32.GetWindowThreadProcessId: ([W.HWND, W.LPDWORD], W.DWORD),
        mundo.user32.GetCursorPos: ([W.LPPOINT], W.BOOL),
        mundo.user32.WindowFromPoint: ([W.POINT], W.HWND),
        mundo.kernel32.GetCurrentProcess: ([], W.HANDLE),
        mundo.kernel32.OpenProcess: ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
        mundo.kernel32.CloseHandle: ([W.HANDLE], W.BOOL),
        mundo.kernel32.QueryFullProcessImageNameW: ([W.HANDLE, W.DWORD, W.LPWSTR, W.LPDWORD], W.BOOL),
        mundo.advapi32.OpenProcessToken: ([W.HANDLE, W.DWORD, ctypes.POINTER(W.HANDLE)], W.BOOL),
        mundo.advapi32.GetTokenInformation: ([W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD, W.LPDWORD], W.BOOL),
    }
    for funcao, (argumentos, retorno) in esperado.items():
        assert funcao.argtypes == argumentos, funcao.nome
        assert funcao.restype is retorno, funcao.nome
    for funcao in (mundo.user32.GetForegroundWindow, mundo.user32.WindowFromPoint, mundo.kernel32.GetCurrentProcess,
                   mundo.kernel32.OpenProcess):
        assert ctypes.sizeof(funcao.restype) == ctypes.sizeof(ctypes.c_void_p), f"{funcao.nome} devolve menos que um ponteiro"


@pytest.mark.skipif(os.name == "nt", reason="no Windows a sonda sem dublês usa as DLLs de verdade")
def test_fora_do_windows_a_sonda_sem_dubles_se_recusa():
    with pytest.raises(RuntimeError, match="só existe no Windows"):
        SondaWindows()


# ------------------------------------------------------------------------------------------------------ o vigia
def _vigia(sonda, **argumentos):
    registro, relogio = [], FakeClock()
    vigia = VigiaDeElevacao(sonda, registrar=registro.append, relogio=relogio.monotonic, **argumentos)
    return vigia, registro, relogio


def _sonda(programa=NAO, frente=None, cursor=None, processos=None):
    sonda = SondaFalsa(programa)
    sonda.frente, sonda.cursor = frente, cursor
    sonda.processos = dict(processos or {})
    return sonda


def test_avisa_uma_vez_por_programa_e_volta_a_avisar_na_execucao_seguinte():
    sonda = _sonda(frente=500, processos={500: ("Taskmgr.exe", SIM)})
    vigia, _registro, relogio = _vigia(sonda)
    aviso = vigia.olhar()
    assert (aviso.situacao, aviso.pid, aviso.nome, aviso.onde) == (Situacao.BLOQUEADA, 500, "Taskmgr.exe", ONDE_FRENTE)
    relogio.advance(0.25)
    assert vigia.olhar() is None                       # já avisado nesta execução
    vigia.nova_rodada()
    assert vigia.olhar() == aviso                      # a primeira olhada da execução nova não espera o intervalo


def test_cada_processo_e_lido_uma_vez_por_execucao():
    sonda = _sonda(frente=600, processos={600: ("notepad.exe", NAO)})
    vigia, _registro, relogio = _vigia(sonda)
    for _ in range(5):
        assert vigia.olhar() is None
        relogio.advance(0.25)
    assert sonda.chamadas.count("ler_processo(600)") == 1
    vigia.nova_rodada()
    vigia.olhar()
    assert sonda.chamadas.count("ler_processo(600)") == 2     # outra execução: o pid pode ter outro dono agora


def test_entre_duas_olhadas_o_vigia_nao_toca_no_windows():
    sonda = _sonda(frente=600, processos={600: ("notepad.exe", NAO), 500: ("Taskmgr.exe", SIM)})
    vigia, _registro, relogio = _vigia(sonda)
    assert vigia.olhar() is None
    feitas = list(sonda.chamadas)
    sonda.frente = 500                                  # o mundo mudou, mas ainda não é hora de olhar
    assert vigia.olhar() is None and sonda.chamadas == feitas
    relogio.advance(0.24)
    assert vigia.olhar() is None and sonda.chamadas == feitas
    relogio.advance(0.01)                               # 0,25 s: agora olha
    assert vigia.olhar().pid == 500


def test_o_intervalo_entre_olhadas_pode_ser_ajustado():
    sonda = _sonda(frente=500, processos={500: ("Taskmgr.exe", SIM)})
    vigia, _registro, relogio = _vigia(sonda, intervalo=1.0)
    assert vigia.olhar() is not None
    vigia.nova_rodada()
    sonda.chamadas.clear()
    assert vigia.olhar() is not None                    # olhada da execução nova
    relogio.advance(0.5)
    sonda.chamadas.clear()
    assert vigia.olhar() is None and sonda.chamadas == []   # dentro do intervalo de 1 s


def test_programa_elevado_nao_avisa_e_nem_olha_as_janelas():
    sonda = _sonda(programa=SIM, frente=500, cursor=500, processos={500: ("Taskmgr.exe", SIM)})
    vigia, _registro, relogio = _vigia(sonda)
    for _ in range(3):
        assert vigia.olhar() is None
        relogio.advance(0.25)
    assert "frente" not in sonda.chamadas and "cursor" not in sonda.chamadas and not any(
        c.startswith("ler_processo") for c in sonda.chamadas)
    assert sonda.chamadas.count("elevacao_do_programa") == 1   # lido uma vez só


def test_a_propria_janela_na_frente_nao_gera_aviso_nem_leitura():
    sonda = _sonda(frente=100, cursor=100, processos={})      # 100 é o pid do próprio programa
    vigia, _registro, _relogio = _vigia(sonda)
    assert vigia.olhar() is None
    assert not any(c.startswith("ler_processo") for c in sonda.chamadas)


def test_sem_janela_nenhuma_nao_avisa():
    vigia, _registro, _relogio = _vigia(_sonda())
    assert vigia.olhar() is None


def test_janela_comum_nao_avisa():
    vigia, registro, _relogio = _vigia(_sonda(frente=600, cursor=600, processos={600: ("notepad.exe", NAO)}))
    assert vigia.olhar() is None
    assert not any("INCERTA" in linha for linha in registro)


def test_a_janela_sob_o_cursor_tambem_e_olhada():
    sonda = _sonda(frente=600, cursor=500, processos={600: ("notepad.exe", NAO), 500: ("Taskmgr.exe", SIM)})
    vigia, _registro, _relogio = _vigia(sonda)
    aviso = vigia.olhar()
    assert (aviso.pid, aviso.onde) == (500, ONDE_CURSOR)


def test_duas_janelas_elevadas_geram_um_aviso_cada_uma_e_depois_nada():
    sonda = _sonda(frente=500, cursor=501, processos={500: ("Taskmgr.exe", SIM), 501: ("regedit.exe", SIM)})
    vigia, _registro, relogio = _vigia(sonda)
    primeiro = vigia.olhar()
    relogio.advance(0.25)
    segundo = vigia.olhar()
    relogio.advance(0.25)
    assert (primeiro.pid, primeiro.onde, segundo.pid, segundo.onde) == (500, ONDE_FRENTE, 501, ONDE_CURSOR)
    assert vigia.olhar() is None


def test_frente_e_cursor_no_mesmo_processo_avisam_uma_vez():
    sonda = _sonda(frente=500, cursor=500, processos={500: ("Taskmgr.exe", SIM)})
    vigia, _registro, relogio = _vigia(sonda)
    assert vigia.olhar().onde == ONDE_FRENTE
    relogio.advance(0.25)
    assert vigia.olhar() is None


def test_acesso_negado_vira_aviso_de_provavel():
    sonda = _sonda(frente=500, processos={500: ("", NEGADA)})
    aviso = _vigia(sonda)[0].olhar()
    assert aviso.situacao is Situacao.PROVAVEL and aviso.nome == "" and aviso.curto.startswith("⚠ Pode ser")


def test_sem_saber_o_alvo_nao_avisa_mas_registra_uma_vez():
    sonda = _sonda(frente=500, processos={500: ("Taskmgr.exe", DESCONHECIDA)})
    vigia, registro, relogio = _vigia(sonda)
    for _ in range(4):
        assert vigia.olhar() is None
        relogio.advance(0.25)
    incertas = [linha for linha in registro if "ELEVACAO INCERTA" in linha]
    assert len(incertas) == 1 and "pid=500" in incertas[0] and "nome=Taskmgr.exe" in incertas[0]


def test_programa_duvidoso_nao_avisa_e_e_lido_de_novo_na_execucao_seguinte():
    sonda = _sonda(programa=DESCONHECIDA, frente=500, processos={500: ("Taskmgr.exe", SIM)})
    vigia, registro, relogio = _vigia(sonda)
    assert vigia.olhar() is None                           # sem saber se o programa é elevado, não assusta
    assert any("ELEVACAO INCERTA" in linha for linha in registro)
    sonda.programa = NAO                                   # numa leitura melhor, ele é comum
    relogio.advance(0.25)
    assert vigia.olhar() is None                           # dentro da mesma execução não relê
    vigia.nova_rodada()
    assert vigia.olhar().situacao is Situacao.BLOQUEADA
    assert sonda.chamadas.count("elevacao_do_programa") == 2


def test_programa_com_leitura_certa_nao_e_lido_de_novo():
    sonda = _sonda(programa=NAO, frente=600, processos={600: ("notepad.exe", NAO)})
    vigia, _registro, _relogio = _vigia(sonda)
    vigia.olhar()
    vigia.nova_rodada()
    vigia.olhar()
    assert sonda.chamadas.count("elevacao_do_programa") == 1


def test_o_vigia_registra_se_o_programa_e_elevado():
    sonda = _sonda(programa=NAO, frente=600, processos={600: ("notepad.exe", NAO)})
    vigia, registro, _relogio = _vigia(sonda)
    vigia.olhar()
    assert registro == ["ELEVACAO programa=nao"]


def test_erro_inesperado_desliga_o_vigia_sem_levantar():
    sonda = _sonda(frente=500, processos={500: ("Taskmgr.exe", SIM)})
    sonda.erro = OSError("falha de teste")
    vigia, registro, relogio = _vigia(sonda)
    assert vigia.olhar() is None and vigia.desligado
    desligados = [linha for linha in registro if "ELEVACAO VIGIA DESLIGADO" in linha]
    assert len(desligados) == 1 and "OSError" in desligados[0] and "falha de teste" in desligados[0]
    sonda.erro = None                                      # mesmo que o Windows volte ao normal, o vigia fica desligado
    feitas = list(sonda.chamadas)
    for _ in range(3):
        relogio.advance(0.25)
        assert vigia.olhar() is None
    assert sonda.chamadas == feitas
    assert len([linha for linha in registro if "DESLIGADO" in linha]) == 1


def test_nova_rodada_nao_religa_um_vigia_desligado():
    sonda = _sonda(frente=500, processos={500: ("Taskmgr.exe", SIM)})
    sonda.erro = RuntimeError("x")
    vigia, _registro, _relogio = _vigia(sonda)
    vigia.olhar()
    sonda.erro = None
    vigia.nova_rodada()
    assert vigia.olhar() is None and vigia.desligado


# ------------------------------------------------------------------------------------------- criar o vigia de verdade
def test_fora_do_windows_nao_ha_vigia():
    assert criar_vigia(sistema="posix") is None


def test_no_windows_o_vigia_usa_a_sonda_do_windows(monkeypatch):
    sonda = SondaFalsa()
    registro = []
    monkeypatch.setattr(elevacao, "SondaWindows", lambda: sonda)
    vigia = criar_vigia(registro.append, sistema="nt")
    assert isinstance(vigia, VigiaDeElevacao) and vigia.sonda is sonda
    vigia.olhar()
    assert registro == ["ELEVACAO programa=nao"], "o vigia criado tem de usar o `registrar` recebido"


def test_se_a_leitura_do_windows_nao_monta_o_programa_segue_sem_vigia(monkeypatch):
    def quebra():
        raise OSError("sem user32")
    monkeypatch.setattr(elevacao, "SondaWindows", quebra)
    registro = []
    assert criar_vigia(registro.append, sistema="nt") is None
    assert len(registro) == 1 and "ELEVACAO INDISPONIVEL" in registro[0] and "sem user32" in registro[0]
    assert criar_vigia(sistema="nt") is None             # sem `registrar` também não levanta


# ---------------------------------------------------------- a pilha inteira: vigia + sonda do Windows + Windows simulado
def test_vigia_com_a_sonda_do_windows_simulado_do_comeco_ao_fim():
    mundo = MundoWindows(eu_elevado=False)
    mundo.adicionar_processo(500, "Taskmgr.exe", elevado=True)
    mundo.adicionar_processo(600, "notepad.exe", elevado=False)
    mundo.adicionar_janela(11, 500)
    mundo.adicionar_janela(12, 600, na_frente=True, sob_o_cursor=(10, 20))
    registro, relogio = [], FakeClock()
    vigia = VigiaDeElevacao(mundo.criar_sonda(), registrar=registro.append, relogio=relogio.monotonic)
    assert vigia.olhar() is None                         # bloco de notas na frente: tudo bem
    mundo.frente = 11                                    # a automação trouxe o gerenciador de tarefas para a frente
    relogio.advance(0.25)
    aviso = vigia.olhar()
    assert (aviso.situacao, aviso.pid, aviso.nome, aviso.onde) == (Situacao.BLOQUEADA, 500, "Taskmgr.exe", ONDE_FRENTE)
    assert mundo.alcas_abertas() == [] and mundo.fechamentos_invalidos == []
    chamadas_ate_aqui = len(mundo.chamadas)
    relogio.advance(0.25)
    assert vigia.olhar() is None                         # já avisado: só pergunta quem é a janela, não lê o processo de novo
    novas = mundo.chamadas[chamadas_ate_aqui:]
    assert "OpenProcess" not in novas and "OpenProcessToken" not in novas


def test_com_o_programa_elevado_a_pilha_inteira_nao_avisa_e_nao_olha_janelas():
    mundo = MundoWindows(eu_elevado=True)
    mundo.adicionar_processo(500, "Taskmgr.exe", elevado=True)
    mundo.adicionar_janela(11, 500, na_frente=True)
    vigia = VigiaDeElevacao(mundo.criar_sonda(), relogio=FakeClock().monotonic)
    assert vigia.olhar() is None
    assert "GetForegroundWindow" not in mundo.chamadas and "OpenProcess" not in mundo.chamadas
