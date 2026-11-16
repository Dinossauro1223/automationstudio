# Sondas de diagnóstico do abort do Windows no GitHub Actions (01/11/2026)

**Só para consulta. Este ramo não é para juntar na `main`.** O contexto, as evidências e a correção estão em
`md/ENTREGA_PAUSA_TECLAS.md`, seção 10, no ramo `funcoes/pausar-continuar-teclas`.

São plugins do pytest que usei, num ramo temporário com o job do Windows alterado, para achar a causa de
`Fatal Python error: Aborted` no passo "testes comuns". Para usar de novo: copie os `zz_*.py` para a raiz do repositório
(ao lado de `pytest.ini`), num ramo descartável; rode o workflow com `gh workflow run tests.yml --ref <ramo>` (o arquivo do
workflow precisa existir na `main`; o log de um job só fica disponível quando a rodada inteira termina) e, no passo do
Windows, troque o comando por algo como:

    AS_DIAG_EMPURRAO=64 PYTEST_ADDOPTS="-p zz_diag_total" python tests/testsupport/rodar_testes.py completo

| Arquivo | O que faz |
|---|---|
| `zz_diag_total.py` | Tudo num plugin só, para perturbar o mínimo: guarda a captura do pytest em `logs/zz_captura_<pid>_<n>.txt` (sobra depois de um abort); instala, no Windows, um tratador de `SIGABRT` que grava a pilha nativa (módulo, deslocamento e símbolo exportado mais próximo, via `dbghelp`) em `logs/zz_pilha_nativa.txt` e repassa o sinal ao `faulthandler`; `AS_DIAG_EMPURRAO=N` segura N listas vivas, o que desloca de N alocações o ponto em que o coletor de lixo roda. |
| `zz_manter_captura.py` | Só a parte de guardar a captura e o deslocamento, trocando uma única função do pytest. |
| `zz_gcinfo.py` | Registra em `logs/diag_gcinfo.txt` cada coleta de lixo: a geração, o teste em andamento e os objetos do Qt na geração coletada. |
| `zz_coleta.py` | Desliga o coletor automático e coleta só onde mandarem (`AS_DIAG_COLETA=cada` ou `primeiro_dialogo`, `AS_DIAG_GERACAO`, `AS_DIAG_ONDE`). |
| `zz_gcprobe.py` | Força uma coleta depois de cada teste de janela e de cada teste do motor. |
| `zz_nogc.py` | Desliga a coleta automática (`gc.disable()`). |

Cuidado: qualquer sonda muda o instante em que o coletor roda e pode **esconder** o abort (efeito do observador). Por isso o
plugin completo troca o mínimo possível, e o deslocamento (`AS_DIAG_EMPURRAO`) serve para reproduzi-lo.
