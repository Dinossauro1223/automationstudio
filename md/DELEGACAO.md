# Delegação e protocolo de integração

Escrito pela conta de **integração** (a que junta os ramos na `main`), em 30/10/2026. Complementa `md/DIVISAO_DE_TRABALHO.md`, que descreve as frentes visual e de funções: onde os dois documentos diferirem sobre **como algo entra na `main`**, vale este. Cada conta lê só o seu bloco da seção 4 e a seção 3.

## 1. Contas e papéis

| Conta | Ramos | Cuida de | Estado em 30/10/2026 |
|---|---|---|---|
| **Integração** | `main` | Junta os ramos, roda a suíte antes e depois, mantém este quadro e o `ROADMAP.md`, testes e infraestrutura transversais | Integrou `visual/novo-tema` e `funcoes/ativacao-mapas`; criou o `.gitattributes`, os testes do `vision.py` e o fluxo do GitHub Actions |
| **Visual** | `visual/<assunto>` | Aparência: tema, folha de estilo, telas | `visual/novo-tema` na `main`; próximo: V1 a V4 |
| **Funções** | `funcoes/<assunto>` | Comportamento: lógica, motor, persistência, atalhos | `funcoes/ativacao-mapas` na `main`; próximo: F1 e F2 |
| **Visão** (conta ainda não aberta) | `visao/<assunto>` | Captura de tela e casamento de imagem (`vision.py`) | Tarefas Z1 e Z2 prontas para quem entrar |

Na `main` só entra o que a integração testou e juntou. Hoje a integração roda numa conversa do claude.ai, que lê o repositório público mas **não tem credencial para escrever nele**: ela entrega a `main` pronta como pacote `git bundle` e o dono publica (uma linha, ver a mensagem da entrega). Se a integração passar a rodar no Claude Code (a frente de funções registra `Claude-Session` nos commits), ela mesma publica.

## 2. O que a integração faz a cada ramo novo

1. `git fetch` e lista dos ramos com commits à frente da `main` (`git log origin/main..origin/<ramo>`).
2. Roda a suíte **do ramo sozinho** (modo `completo`: Python 3.14, PySide6 de verdade, janela invisível). Se já falha, devolve ao dono do ramo.
3. Junta com `git merge --no-ff`: a junção fica visível no histórico e se desfaz com `git revert -m 1 <commit>`. Conflito trivial (linhas vizinhas, formatação): resolve e diz no commit. Conflito de lógica: **não resolve**; devolve ao dono do ramo com os arquivos e as linhas.
4. Roda a suíte **na árvore junta**. Para entrar na `main`: nenhuma falha nova; nenhum `xfail` estrito virou erro sem o marcador sair; `tests/static/test_ligacao_ativacao.py` e `tests/unit/test_tema_visual.py` verdes (são as redes das duas frentes).
5. Registra a junção na seção 6 e avisa os donos de ramo: **`git fetch` e `git merge origin/main` no seu ramo antes do próximo pull request**.
6. `APP_VERSION` e `md/CHANGELOG_V25.md`: **só o dono**, ao fechar a versão. A integração não os toca.

## 3. Regras para os ramos (o que já vale, em resumo)

- Ramo novo nasce da `main` atualizada: `visual/<assunto>`, `funcoes/<assunto>`, `visao/<assunto>`. Um assunto por ramo.
- Primeira linha do commit com prefixo: `Visual:`, `Função:`, `Visão:`, `Testes:`, `Infra:`, `Docs:` (a integração usa `Integração:`).
- Antes de publicar: `Rodar_Testes.bat` (ou `python tests/testsupport/rodar_testes.py completo`). A mensagem do último commit diz **o que foi testado e o que não foi**, com os números.
- `git add` por nome de arquivo. Nunca `logs/`, `__pycache__/` nem um `tests/coverage_baseline.json` gerado fora do Windows do dono.
- Arquivos compartilhados (`main_window.py`, `command_editor.py`, `timeline.py`, `tutorial.py`): mudança pequena e no lugar (`DIVISAO_DE_TRABALHO.md`, seção 3). Se tocar `main_window.py` de um jeito novo, o commit diz quais trechos.
- Refatoração grande (Pontos 3 e 4 do roadmap) **não roda em paralelo** com as outras frentes nos mesmos arquivos; a integração marca a janela antes (F3).
- `Rodar_Testes.bat windows` envia teclado e mouse de verdade: só o dono o roda, na própria máquina.
- Ambiente de teste da integração (repetível): `uv venv --python 3.14`, `uv pip install -r requirements-dev.txt` e `xvfb-run -a python tests/testsupport/rodar_testes.py completo` (Linux). Sem o display virtual, 5 testes de janela que dependem do `pynput` são pulados.

## 4. Quadro de tarefas

Cada tarefa tem um **critério de pronto**. A ordem dentro de cada conta é a prioridade. "Depende" diz o que precisa ser decidido antes (seção 5).

### Visual (`visual/<assunto>`)

| # | Tarefa | Critério de pronto | Depende |
|---|---|---|---|
| V1 | Desenhar o estado e o conflito de cada automação na lista, por *delegate*, com os papéis de dados 257 e 258 (contrato em `DIVISAO_DE_TRABALHO.md`, seção 4) | Ativo, só nesta sessão, desativado e em conflito se distinguem nos temas claro e escuro; o texto do item continua sendo o nome do mapa; `test_ligacao_ativacao.py` e `test_tema_visual.py` verdes | — |
| V2 | Restilizar a faixa `#PainelAtivacao` com os tokens do tema novo | Nenhum `#hex` solto (cor nova = token novo); acompanha o acento escolhido; a faixa continua sendo o único seletor de estado | — |
| V3 | "Próximos PRs sugeridos" do `REDESIGN_VISUAL.md`: textos secundários de cor fixa (`#8f96a3`, `#9aa0aa`) viram token (contraste no tema claro); ícones no lugar dos emojis da barra; `setStyleSheet` inline para a folha global | Checklist do `REDESIGN_VISUAL.md` conferido nos dois temas; os testes de tema ganham os casos novos | — |
| V4 | Telas da 25.7 (tutorial novo, sidebar "Configurações da automação", prévias com selo) | A definir | Plano 25.7 no repositório e decisão de quem faz o quê (seção 5, itens 5 e 2) |

### Funções (`funcoes/<assunto>`)

| # | Tarefa | Critério de pronto | Depende |
|---|---|---|---|
| F1 | Achado 2.11: ligar F9 e F10 a `engine.pause()` e `engine.resume()` em `_on_hotkey_triggered`, com o que a barra de estado mostra | O `xfail` estrito de `tests/static/test_lacunas_de_ligacao.py` passa e o marcador sai; teste de janela real | Decisão do dono sobre a pausa durante uma espera por aplicativo (seção 5, item 3) |
| F2 | Resolver, com teste, o que os `xfail` de `tests/unit/test_validation_gaps.py` esperam: botão de mouse desconhecido, "abrir aplicativo" sem alvo e `repeat_count` menor que -1 | Os 3 `xfail` passam e saem; os 3 mapas reais continuam validando (cenários em `tests/scenarios`) | — (faz parte do Ponto 3; pode entrar antes dele) |
| F3 | Ponto 3: formato v2 (TOML), exportar e importar; achados 2.03, 2.04 e 2.05 | Critérios do `ROADMAP.md` | Rodada do dono no Windows (o roadmap pede a rodada antes do Ponto 3) e janela combinada para `core.py` e `project.py` |

### Visão (`visao/<assunto>`; conta ainda não aberta)

| # | Tarefa | Critério de pronto | Depende |
|---|---|---|---|
| Z1 | `FonteDeTela` (interface) com a implementação do Qt isolada e uma `FonteDeTelaFalsa` para testes; `vision.py` sem PySide6 no topo | `vision.py` roda e é testado sem Qt; os testes de `tests/unit/test_vision_comportamento.py` continuam passando (ou mudam com justificativa escrita) | D20 (como capturar a tela) |
| Z2 | Casamento de imagem de verdade (fase 7.A): derrubar a lacuna F4 | O `xfail` `test_vision_elemento_pequeno_ausente_nao_deveria_contar_como_encontrado` passa e sai; a espera "aparece em 7 s virtuais" do critério da 7.A | D19 (OpenCV) |

### Integração (esta conta)

| # | Tarefa | Critério de pronto | Depende |
|---|---|---|---|
| I1 | Publicar a `main` integrada (esta entrega) | O dono aplica o pacote e o GitHub Actions fica verde no Linux | Dono |
| I2 | Ler o primeiro resultado do GitHub Actions (Linux e Windows) e ajustar o fluxo | Linux verde; Windows com os logs anexados | I1 |
| I3 | Gravar o baseline de cobertura **no Windows do dono** (`Rodar_Testes.bat cobertura`) | `tests/coverage_baseline.json` do Windows no repositório | Dono |
| I4 | Mais testes onde a cobertura é menor: `timeline.py` (28%), `overlays.py` (35%), `command_editor.py` (41%), `main_window.py` (48%), medidos no Linux | Só testes de comportamento que sobrevivam à divisão dos arquivos; o grosso depois do Ponto 4 | Ponto 4 |
| I5 | Revisar o `ROADMAP.md` a cada junção | O roadmap descreve o que está na `main` | — |

## 5. Fila de decisões do dono (bloqueiam tarefas acima)

1. **Rodada no Windows** da `main` integrada: `Rodar_Testes.bat`, a conferência de 5 minutos da ativação (`ENTREGA_25_8.md`, seção 2) e o checklist visual (`REDESIGN_VISUAL.md`). Enviar `logs\tests_last_run.txt` e, se existir, `logs\travamento_qt.txt`. Bloqueia F3.
2. **Aval ou veto** das decisões da `ENTREGA_25_8.md`, seção 6, e **quem faz o quê** nas telas da 25.7 (`DIVISAO_DE_TRABALHO.md`, seção 7.1).
3. **Achado 2.11** (F9 e F10): corrigir já (F1) ou deixar para a 25.11, e o que a pausa faz durante uma espera por aplicativo.
4. **Fechar a versão?** `APP_VERSION` continua `25.6`, com o tema novo e a ativação por mapa já na `main`. Só o dono fecha.
5. **O "plano 25.7" não está no repositório.** As entregas citam esse plano (itens MAP-01 a MAP-04, HK-01, "item 2.3", decisões D24 a D34), mas ele não está em `md/` e o `ROADMAP.md` acaba em D23. Pedido: commitar o plano em `md/` (ou colá-lo na conversa de integração). Sem ele as frentes trabalham de uma fonte que a integração não consegue conferir.
6. **D19 (OpenCV).** Verificado em 30/10/2026: há pacote para o Python 3.14 no Windows, `opencv-python-headless` 5.0.0.93 (`cp37-abi3`, serve a qualquer 3.x) e `numpy` 2.5.4 (`cp314`). Instalar é possível; **não foi testado em execução no Windows**. Decisão: adotar como dependência obrigatória (a recomendação do roadmap) ou não.
7. **Publicação.** Como a `main` integrada chega ao GitHub (seção 1): pacote aplicado pelo dono, ou a integração passa a rodar no Claude Code.
8. **`ALTERACOES_25_5_para_25_6.diff`** (230 KB, na raiz) não é cópia de nada em `md/`. Se não tiver mais uso, pode sair (o histórico do Git o guarda). Não foi removido.

## 6. Registro de integrações

Ambiente: Linux, Python 3.14.4, PySide6 6.12.0, display virtual. "Falhas antigas" são as 3 de fim de linha dos `.bat` em clone novo (`tests/static`, `tests/regression` e `tests/unit/test_mutacoes.py`), resolvidas pelo `.gitattributes`.

| Data | Ramo ou origem | Commit na `main` | Resultado |
|---|---|---|---|
| 30/10/2026 | `visual/novo-tema` (`6e42294`) | `51278c2` | Sozinho: 1490 passam e 22 de janela ok; só as falhas antigas. Zero conflitos |
| 30/10/2026 | `funcoes/ativacao-mapas` (`29e9a8c`) | `c201431` | Sozinho: 1630 passam e 34 de janela (5 pulados sem display virtual); só as falhas antigas. Junto com o visual: 1645 passam; zero conflitos |
| 30/10/2026 | `.gitattributes` | `6f7bf05` | 1648 passam e 34 de janela ok; **0 falhas** |
| 30/10/2026 | Testes do `vision.py` e fluxo do GitHub Actions | `c42b96d`, `33cd0a1` | 1677 passam, 11 pulados (9 só do Windows de verdade, 2 que pedem OpenCV), 7 `xfail` estritos, 34 de janela ok; **0 falhas**. Cobertura do `vision.py`: 18% para 85% |
