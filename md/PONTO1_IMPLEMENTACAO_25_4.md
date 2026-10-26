# Ponto 1 — Implementação (AS 25.3 → 25.4)

Este documento acompanha a versão 25.4. O diagnóstico completo está em `Relatorio_Auditoria_AS_25_3_Ponto1.md`.

## Resultado

| Verificação | AS 25.3 original | AS 25.4 |
|---|---|---|
| Suíte completa (`tests/`, 48 testes) | 21 passam, 24 falham, 3 xfail | **45 passam, 0 falham, 3 xfail** |
| Estabilidade (6 execuções seguidas) | não aplicável | 45/45 em todas |
| Nomes indefinidos, métodos duplicados, chamadas `self._x()` inexistentes | 5 achados | 0 |
| Sinais declarados sem `connect` | `chain_requested` | só os 4 sinais mortos listados abaixo |

Medido num ambiente com Python 3.12.3, sem PySide6 real (stub só para importar), sem pytest (executor mínimo) e sem Windows.
**Não foi validado:** a GUI real, o Windows (`SendInput`, instância única, `.bat`), o Python 3.14 e o hardware. Veja o checklist abaixo.

## Status dos itens

| Item | Status |
|---|---|
| 1.01 `validate()` bloqueava mover, rolar e esperar | Corrigido |
| 1.02 IDs colidiam após reiniciar | Corrigido |
| 1.03 "Próxima automação" desconectada | Corrigido |
| 1.04a Miniatura da condição de imagem | Corrigido (implementada) |
| 1.04b `shutil` não importado | Corrigido |
| 1.04c Backend pynput de fallback | Corrigido (D4: consertar) |
| 1.05 Intervalo entre caracteres sem efeito | Corrigido |
| 1.06 Parada de emergência não interrompia o texto | Corrigido |
| 1.07 Pausa durante barreira | Corrigido |
| 1.08 Barreira não deslocava o relógio | Corrigido para condições V24 (a espera de processo fica para o Ponto 5, D2) |
| 1.09 Instância única | Corrigido |
| 1.10 AltGr no backend Win32 | Corrigido, **validar em Windows ABNT2** |
| 1.11 Botões laterais X1/X2 | **Pendente (D1)**, teste marcado xfail |
| 1.12 `resizeEvent` duplicado e rótulo "Total" | Corrigido |
| 1.13 Log de início com `\n` literal | Corrigido |
| 1.14 Conexões SQLite | Corrigido |
| 1.15 Amostragem do mouse do gravador | **Pendente (D3)**, teste marcado xfail |
| 1.16 `engine.run()` e transição de estado inválida | Corrigido |
| 1.17 Mapa inválido sumia em silêncio | Corrigido (aviso e log; quarentena fica para o Ponto 3) |
| 1.18 Excluir e exportar mapa sem interface | **Pendente (D5)**, vira parte do Ponto 3 |
| 1.19 Suíte de testes | Corrigida; teste de reflow em xfail (D6) com dois testes novos que documentam o comportamento atual |

## O que mudou (arquivos)

- `core.py`: validação de duração; contador de IDs (`_IdCounter`, `_sync_id_counter`); `set_runtime_defaults`; versão 25.4; remoção de `_resolve_key` e `_SPECIAL_KEYS` (quebrados).
- `input_system.py`: backend pynput; AltGr; parada, pausa e relógio de barreira no motor; texto caractere a caractere.
- `main_window.py`: sinal de encadeamento; captura de `InvalidStateTransition`; `resizeEvent` único; aviso de mapas que não carregaram; título com `APP_VERSION`.
- `command_editor.py`: miniatura de imagem; `import shutil`; configurações via `core.set_runtime_defaults`.
- `timeline.py`: rótulo "Total". `app.py`: instância única e log. `project.py`: conexões SQLite e `load_errors`.
- Projeto: `python_version.txt` (3.14), `.bat` (Python 3.14, fim de linha do Windows), README, `pytest.ini`, `requirements-dev.txt`, `tests/conftest.py`, `tests/test_ponto1_reproducao.py`.

## Decisões tomadas por falta de resposta (você pode vetar)

- **D2** adiada para o Ponto 5. **D4** consertar o fallback. **D7** encadeamento em ciclo permitido (a parada manual interrompe).
- **ALTGR**: mapeado para `VK_RMENU` (tecla estendida) sem enviar Ctrl esquerdo, porque o Windows gera o Ctrl auxiliar em layouts com AltGr. Se AltGr+Q não digitar "/" no ABNT2, a correção é enviar o par Ctrl+Alt direito.
- **Botão ou tecla desconhecida** no backend pynput agora gera erro; antes virava clique esquerdo ou outra tecla em silêncio.
- **`resizeEvent`**: o código antigo que limita a largura da lateral nunca executava; agora executa. Confira o layout ao redimensionar.

## Checklist manual no Windows (cerca de 15 minutos)

1. `Instalar_Dependencias_Global.bat` com o Python 3.14. Se falhar, o log mostra qual pacote não existe para a 3.14.
2. `Iniciar.bat` abre o programa. No log: "Python solicitado: 3.14" e o executável da 3.14, com quebras de linha reais.
3. Abrir `Iniciar.bat` de novo com o programa aberto: aparece o aviso e a segunda instância fecha.
4. Mapa com "Mover o mouse", "Rolar" e "Esperar": executa sem a mensagem de duração 0.
5. Condição de imagem: escolher o arquivo mostra a miniatura; editar a condição abre sem erro.
6. Texto com mais de 300 caracteres e parada de emergência: para na hora, sem congelar a janela.
7. Pausar durante uma espera por imagem ou processo: nada é digitado enquanto pausado.
8. "Próxima automação": o mapa A termina e o B começa; parar o A manualmente não inicia o B.
9. Timeline: o rótulo "Total" acompanha a duração ao editar comandos.
10. Redimensionar a janela e arrastar o divisor da lateral, conferindo o layout.
11. Configurações: intervalo entre caracteres 0,05 s; um comando de texto passa a durar o valor mostrado no diálogo.
12. Gravar e reproduzir com AltGr (ABNT2: AltGr+Q).
13. Comando "Abrir aplicativo": a lista inclui python, cmd, powershell e wt do PATH.
14. `py -3.14 -m pip install -r requirements-dev.txt` e `py -3.14 -m pytest -q`: esperado 45 passed e 3 xfailed.

## Pendências que dependem de você

- **D1** (botões laterais): pressione o botão lateral mais próximo da frente do mouse e diga como aparece no mouse virtual, no diálogo de atalho e numa gravação.
- **D3** (amostragem do mouse): honrar o intervalo ou remover o controle.
- **D5** (excluir e exportar mapa): resolvida pelo Ponto 3.
- **D6** (reflow): qual comportamento é o desejado. Hoje o código devolve [0; 1,5; 2,2] com `preserve_gaps=True`.

## Itens menores deixados como estão

- 4 sinais sem uso: `AppSettingsDialog.execution_requested` (nunca emitido), `rows_reordered`, `positionSelected` e o `currentChanged` próprio de uma aba. Inofensivos.
- 34 métodos nunca referenciados (código morto candidato): só removo com sua confirmação.
- `test_readiness.py` testa o texto do código-fonte e não o comportamento; troca no Ponto 2.
