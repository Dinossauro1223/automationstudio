# Automation Studio — AS 25.6

Base inicial da V23 — Editor & Motor de Automação.

## Estrutura

- `AutomationStudio.pyw`: ponto de entrada.
- `automationstudio/`: núcleo do aplicativo.
- `resources/`: identidade visual e ícones usados pelo aplicativo.
- `tests/`: testes automatizados (guia em `tests/README.md`).
- `md/`: históricos de versão (`CHANGELOG_V25.md` é o mais recente) e os relatórios de cada ponto da auditoria.
- `requirements.txt`: dependências do programa. `requirements-dev.txt`: dependências dos testes. `python_version.txt`: a versão do Python.
- arquivos `.bat`: inicialização, execução administrativa opcional, limpeza, instalação de dependências e `Rodar_Testes.bat`.

## Versão

`25.6` — correção da rodada de testes no Windows (`.bat` com pasta de usuário acentuada, testes da janela principal isolados e com diagnóstico de travamento), sobre a infraestrutura de testes 25.5 (Ponto 2 da auditoria técnica) e a estabilização 25.4. Reúne as condições de espera e sincronização da série 24.x e a espera por imagem da série 25.x; as mudanças estão em `md/CHANGELOG_V25.md`, o relatório do Ponto 2 em `md/PONTO2_IMPLEMENTACAO_25_5.md`, a revisão da 25.6 em `md/PONTO2_REVISAO_25_6.md` e o planejamento das próximas versões (inclusive a espera por imagem) em `md/ROADMAP.md`.

## Requisitos e testes

- Python **3.14**, definido em `python_version.txt` (os `.bat` usam `py -3.14`). Para mudar a versão, edite só esse arquivo.
- Dependências: `requirements.txt` (execução) e `requirements-dev.txt` (testes).
- Testes: `Rodar_Testes.bat instalar` (uma vez) e depois duplo clique em `Rodar_Testes.bat`. O resultado fica em `logs\tests_last_run.txt`. Os modos (`rapido`, `completo`, `windows`, `repetir`, `cobertura`, `mutacoes`) e o que cada um faz estão em `tests/README.md`.
- Sem o `.bat`: `py -3.14 -m pip install -r requirements-dev.txt` e `py -3.14 -m pytest -q`.


## Escopo concluído da V23

A série 23.x foi construída incrementalmente para manter o editor e o motor temporal previsíveis antes da introdução de condições e visão computacional. A 24.0 consolida: edição unificada, seleção múltipla, copiar/recortar/colar/duplicar, reordenação, histórico transacional, motor temporal, Timeline com zoom/playhead/snap, teste de seleção, pré-visualização sem input real, importação/exportação `.ascommands` e validação estrutural.
