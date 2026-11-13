"""A lista de programas conhecidos (25.9, T3a; ficha md/FICHA_TECLADO_T3_25_9.md, decisão T3-15): uma só.

A barra lateral oferece, em "Abrir aplicativo" e em "Processo que deve aparecer", os programas comuns do Windows mais alguns que
estiverem no PATH. O seletor de programa da edição pelo teclado tem de oferecer os MESMOS: duas listas copiadas divergiriam. Por isso a
lista saiu de dentro do `CommandDialog` para `PROGRAMAS_COMUNS` e `programas_conhecidos()` (em command_editor.py), e os dois lugares leem dela.

O que aparece para o dono não muda: os seis de sempre, com os mesmos rótulos e executáveis (a primeira prova abaixo os fixa um a um).
"""
from __future__ import annotations

from automationstudio import command_editor as ce

OS_SEIS = [
    ("Microsoft Edge", "msedge.exe"),
    ("Bloco de Notas", "notepad.exe"),
    ("Explorador de Arquivos", "explorer.exe"),
    ("Calculadora", "CalculatorApp.exe;calc.exe"),
    ("Outlook (clássico)", "outlook.exe"),
    ("Outlook (novo)", "olk.exe"),
]


def test_os_programas_comuns_sao_os_seis_de_sempre_na_mesma_ordem():
    assert list(ce.PROGRAMAS_COMUNS) == OS_SEIS


def test_a_constante_e_imutavel_para_ninguem_mudar_a_lista_de_todos_por_engano():
    assert isinstance(ce.PROGRAMAS_COMUNS, tuple)
    assert all(isinstance(par, tuple) and len(par) == 2 for par in ce.PROGRAMAS_COMUNS)


def test_sem_nada_no_path_so_ha_os_comuns(monkeypatch):
    monkeypatch.setattr(ce.shutil, "which", lambda nome: None)
    assert ce.programas_conhecidos() == OS_SEIS


def test_os_do_path_entram_depois_dos_comuns_com_o_nome_do_arquivo_como_rotulo(monkeypatch):
    achados = {"python.exe": "C:\\Python314\\python.exe", "cmd.exe": "C:\\Windows\\System32\\cmd.exe",
               "powershell.exe": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe", "wt.exe": "C:\\Users\\Eu\\AppData\\Local\\Microsoft\\WindowsApps\\wt.exe"}
    monkeypatch.setattr(ce.shutil, "which", achados.get)
    lista = ce.programas_conhecidos()
    assert lista[:6] == OS_SEIS
    assert lista[6:] == [("python", achados["python.exe"]), ("cmd", achados["cmd.exe"]),
                         ("powershell", achados["powershell.exe"]), ("wt", achados["wt.exe"])]


def test_so_os_quatro_do_path_sao_procurados(monkeypatch):
    procurados = []
    monkeypatch.setattr(ce.shutil, "which", lambda nome: procurados.append(nome))
    ce.programas_conhecidos()
    assert procurados == ["python.exe", "cmd.exe", "powershell.exe", "wt.exe"]


def test_o_que_o_path_devolve_e_ja_comum_nao_se_repete(monkeypatch):
    monkeypatch.setattr(ce.shutil, "which", lambda nome: "notepad.exe" if nome == "cmd.exe" else None)
    assert ce.programas_conhecidos() == OS_SEIS


def test_a_lista_devolvida_e_nova_a_cada_chamada(monkeypatch):
    """Quem recebe a lista pode acrescentar o seu executável ("Procurar...") sem mexer na dos outros nem na constante."""
    monkeypatch.setattr(ce.shutil, "which", lambda nome: None)
    primeira = ce.programas_conhecidos()
    primeira.append(("Meu programa", "meu.exe"))
    assert ce.programas_conhecidos() == OS_SEIS
    assert list(ce.PROGRAMAS_COMUNS) == OS_SEIS
