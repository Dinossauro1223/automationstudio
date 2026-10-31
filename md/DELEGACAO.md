# Delegação e protocolo de integração

Escrito pela conta de **integração** (a que junta os ramos na `main`), em 30/10/2026 e atualizado em 31/10/2026. Complementa `md/DIVISAO_DE_TRABALHO.md`, que descreve as frentes visual e de funções: onde os dois documentos diferirem sobre **como algo entra na `main`**, vale este. Cada conta lê a seção 3 e o plano da sua frente (seção 4).

## 1. Contas e papéis

| Conta | Ramos | Cuida de | Plano | Estado em 31/10/2026 |
|---|---|---|---|---|
| **Integração** | `main` | Junta os ramos, roda a suíte antes e depois, mantém este quadro, o `ROADMAP.md`, os testes e a infraestrutura transversais, e mede o desempenho | este documento | Integrou `visual/novo-tema` e `funcoes/ativacao-mapas` (30/10); criou o `.gitattributes`, os testes do `vision.py`, o GitHub Actions, o catálogo de funções com seus testes, o script de medição e os planos das frentes (31/10) |
| **Visual** | `visual/<assunto>` | Aparência e interação: tema, telas, simplificação, e depois o app Android | `md/PLANO_VISUAL.md` | `visual/novo-tema` na `main`; próximo: P1 |
| **Funções** | `funcoes/<assunto>` | Comportamento: lógica, motor, formato, banco, atalhos | `md/PLANO_FUNCOES.md` | `funcoes/ativacao-mapas` na `main`; o achado 2.11 (F9 e F10) está com outra frente |
| **Visão** (conta ainda não aberta) | `visao/<assunto>` | Captura de tela e casamento de imagem (`vision.py`) | `md/PLANO_FUNCOES.md` (seções 4 e 5) e `md/DESEMPENHO.md` (F-O1) | Tarefas Z1 e Z2 prontas para quem entrar |

Prompts de partida para colar em cada conta (e o que cada uma faz ao receber "continuar"): `md/PROMPTS_DAS_FRENTES.md`.

### Publicação autônoma da integração

O dono autorizou em 31/10/2026 que a integração publique na `main` por conta própria, **desde que**:

1. a suíte completa passe num clone novo (Python 3.14, PySide6 de verdade, display virtual);
2. `tests/gui/test_funcoes_acessiveis.py` passe: **nenhuma função se perdeu nem ficou inacessível** (catálogo em `md/FUNCOES_DO_USUARIO.md`);
3. nenhuma função tenha sido retirada sem decisão registrada do dono (um ID que some do catálogo bloqueia a publicação);
4. `APP_VERSION` e o changelog só mudem quando o dono fechar a versão.

Condição técnica: a integração precisa de acesso de escrita ao repositório. Numa conversa do claude.ai ela lê o repositório público mas **não tem credencial para escrever**; nesse caso entrega a `main` pronta como pacote `git bundle` e o dono aplica (quatro comandos). No Claude Code ligado ao repositório (a frente de funções registra `Claude-Session` nos commits) ela pode publicar sozinha; o prompt dessa sessão está em `md/PROMPTS_DAS_FRENTES.md`.

## 2. O que a integração faz a cada ramo novo

1. `git fetch` e lista dos ramos com commits à frente da `main` (`git log origin/main..origin/<ramo>`).
2. Roda a suíte **do ramo sozinho** (modo `completo`). Se já falha, devolve ao dono do ramo.
3. Junta com `git merge --no-ff`: a junção fica visível no histórico e se desfaz com `git revert -m 1 <commit>`. Conflito trivial (linhas vizinhas, formatação): resolve e diz no commit. Conflito de lógica: **não resolve**; devolve ao dono do ramo com os arquivos e as linhas.
4. Roda a suíte **na árvore junta**. Para entrar na `main`: nenhuma falha nova; nenhum `xfail` estrito virou erro sem o marcador sair; `tests/static/test_ligacao_ativacao.py`, `tests/unit/test_tema_visual.py` e **`tests/gui/test_funcoes_acessiveis.py`** verdes.
5. Confere o diff de `md/FUNCOES_DO_USUARIO.md`: endereço mudado é normal; função retirada bloqueia até haver decisão do dono.
6. Se a entrega mexeu em pintura, tema ou carregamento: `python tests/testsupport/medir_desempenho.py --comparar` e anota no registro.
7. Registra a junção na seção 6 e avisa os donos de ramo: **`git fetch` e `git merge origin/main` no seu ramo antes da próxima entrega**.

## 3. Regras para os ramos

- Ramo novo nasce da `main` atualizada: `visual/<assunto>`, `funcoes/<assunto>`, `visao/<assunto>`. Um assunto por ramo.
- Primeira linha do commit com prefixo: `Visual:`, `Função:`, `Visão:`, `Testes:`, `Infra:`, `Docs:` (a integração usa `Integração:`). **Última linha** do commit: `Versão: 25.8 (em aberto)` ou `Versão: 25.9 (nova)` (política em `md/PLANO_FUNCOES.md`, seção 1: correção na mesma versão; função nova ou mudança de formato na próxima; na dúvida, a próxima).
- Antes de publicar: `Rodar_Testes.bat` (ou `python tests/testsupport/rodar_testes.py completo`). A mensagem do último commit diz **o que foi testado e o que não foi**, com os números.
- **Nenhuma função some nem fica inacessível**: ao mover ou renomear um controle, atualize `tests/testsupport/funcoes_do_usuario.py` e regenere `md/FUNCOES_DO_USUARIO.md` no mesmo commit (`md/PLANO_VISUAL.md`, seção 1).
- `git add` por nome de arquivo. Nunca `logs/`, `__pycache__/` nem um `tests/coverage_baseline.json` gerado fora do Windows do dono.
- Arquivos compartilhados (`main_window.py`, `command_editor.py`, `timeline.py`, `tutorial.py`): mudança pequena e no lugar (`DIVISAO_DE_TRABALHO.md`, seção 3). Se tocar `main_window.py` de um jeito novo, o commit diz quais trechos.
- Refatoração grande (Pontos 3 e 4 do roadmap) **não roda em paralelo** com as outras frentes nos mesmos arquivos; a integração marca a janela antes.
- `Rodar_Testes.bat windows` envia teclado e mouse de verdade: só o dono o roda, na própria máquina.
- Ambiente de teste da integração (repetível): `uv venv --python 3.14`, `uv pip install -r requirements-dev.txt` e `xvfb-run -a python tests/testsupport/rodar_testes.py completo` (Linux). Sem o display virtual, 5 testes de janela que dependem do `pynput` são pulados.

### Quando não houver tarefa atribuída (ciclo permanente)

Nenhuma frente fica parada. Em ordem, **uma coisa por rodada**:

1. Pendências do plano da sua frente (`PLANO_VISUAL.md` ou `PLANO_FUNCOES.md`) e `xfail` estritos que sejam seus (`pytest -rx`).
2. **Otimização**: o ciclo de `md/DESEMPENHO.md`, seção 7 (medir, mudar uma coisa, medir de novo). O que cada frente pode otimizar está lá, com os números.
3. Testes onde a cobertura é menor na sua área.
4. O próximo ponto do roadmap, se liberado.

Se a lista acabar, a própria frente acrescenta itens ao seu plano, **com a evidência medida** (o que custa, quanto, onde), e segue. No fim da rodada: suíte completa verde, uma linha no registro (seção 6) e o ramo publicado.

## 4. Quadro de tarefas

Cada tarefa tem um **critério de pronto**. A ordem dentro de cada conta é a prioridade. "Depende" diz o que precisa ser decidido antes (seção 5).

### Visual (`visual/<assunto>`): plano completo em `md/PLANO_VISUAL.md`

As antigas V1 a V4 foram absorvidas pelas entregas P1 a P9 do plano: V1 (estado e conflito de ativação na lista) está em P3; V2 (faixa de ativação com tokens) em P2; V3 (cores fixas, ícones, estilos inline) em P2 e P3; V4 (telas da 25.7) continua dependendo do plano 25.7 (seção 5, item 5). **Próxima: P1** (apagar o código morto do tutorial antigo e da barra), depois P2.

### Funções (`funcoes/<assunto>`): plano completo em `md/PLANO_FUNCOES.md`

| # | Tarefa | Critério de pronto | Depende |
|---|---|---|---|
| F1 | Achado 2.11: F9 e F10 pausam e continuam | Roteiro na seção 2 do plano; o `xfail` de `tests/static/test_lacunas_de_ligacao.py` sai; **em andamento com outra frente** (informado pelo dono em 31/10/2026): não duplicar | Decisão do dono sobre a pausa durante espera por aplicativo (seção 5, item 3) |
| F2 | Os 3 `xfail` de `tests/unit/test_validation_gaps.py` | Os 3 passam e saem; os 3 mapas reais continuam validando | Próxima versão |
| F3 | Pontos 3 e 4: formato v2 e arquitetura (núcleo sem Qt) | Critérios do `ROADMAP.md` e a preparação para o Android (`PLANO_FUNCOES.md`, seção 4) | Rodada do dono no Windows e janela combinada para `core.py` e `project.py` |
| F4 | Otimizações F-O1 a F-O5 | Ciclo e metas de `md/DESEMPENHO.md` | — |

### Visão (`visao/<assunto>`; conta ainda não aberta)

| # | Tarefa | Critério de pronto | Depende |
|---|---|---|---|
| Z1 | `FonteDeTela` (interface) com a implementação do Qt isolada e uma `FonteDeTelaFalsa` para testes; `vision.py` sem PySide6 no topo | `vision.py` roda e é testado sem Qt; os testes de `tests/unit/test_vision_comportamento.py` continuam passando (ou mudam com justificativa escrita) | D20 (como capturar a tela) |
| Z2 | Casamento de imagem de verdade (fase 7.A): derrubar a lacuna F4 | O `xfail` `test_vision_elemento_pequeno_ausente_nao_deveria_contar_como_encontrado` passa e sai; a espera "aparece em 7 s virtuais" do critério da 7.A | D19 (OpenCV) |

### Integração (esta conta)

| # | Tarefa | Critério de pronto | Depende |
|---|---|---|---|
| I1 | Publicar a `main` integrada | O dono aplica o pacote (ou a integração publica, no Claude Code) e o GitHub Actions fica verde no Linux | Acesso de escrita |
| I2 | Ler o primeiro resultado do GitHub Actions (Linux e Windows) e ajustar o fluxo | Linux verde; Windows com os logs anexados | I1 |
| I3 | Baseline de cobertura e de desempenho **no Windows do dono** (`Rodar_Testes.bat cobertura` e `medir_desempenho.py --json`) | `tests/coverage_baseline.json` e `md/desempenho/base_windows_<data>.json` no repositório | Dono |
| I4 | Manter o catálogo de funções e os planos em dia a cada junção | Catálogo, `PLANO_VISUAL.md`, `PLANO_FUNCOES.md` e `DESEMPENHO.md` refletem a `main` | — |
| I5 | Mais testes onde a cobertura é menor: `timeline.py` (28%), `overlays.py` (35%), `command_editor.py` (41%), `main_window.py` (48%), medidos no Linux | Só testes de comportamento que sobrevivam à divisão dos arquivos; o grosso depois do Ponto 4 | Ponto 4 |
| I6 | Revisar o `ROADMAP.md` a cada junção | O roadmap descreve o que está na `main` | — |

## 5. Fila de decisões do dono (bloqueiam tarefas acima)

1. **Rodada no Windows** da `main` integrada: `Rodar_Testes.bat`, a conferência de 5 minutos da ativação (`ENTREGA_25_8.md`, seção 2), o checklist visual (`REDESIGN_VISUAL.md`) e `python tests/testsupport/medir_desempenho.py --json base_windows_<data>.json`. Enviar `logs\tests_last_run.txt` e, se existir, `logs\travamento_qt.txt`. Bloqueia F3.
2. **Aval ou veto** das decisões da `ENTREGA_25_8.md`, seção 6, e **quem faz o quê** nas telas da 25.7 (`DIVISAO_DE_TRABALHO.md`, seção 7.1).
3. **Achado 2.11** (F9 e F10): está com outra frente. Falta só decidir o que a pausa faz durante uma espera por aplicativo (sem resposta, a frente usa o comportamento conservador e registra no commit).
4. **Fechar a versão 25.8?** `APP_VERSION` continua `25.6`, com o tema novo e a ativação por mapa já na `main`. Só o dono fecha (a integração prepara o texto do changelog). Pergunta: depois da rodada no Windows com OK, a integração pode subir `APP_VERSION` e o changelog?
5. **O "plano 25.7" não está no repositório.** As entregas citam esse plano (itens MAP-01 a MAP-04, HK-01, "item 2.3", decisões D24 a D34), mas ele não está em `md/` e o `ROADMAP.md` acaba em D23. Pedido: commitar o plano em `md/` (ou colá-lo na conversa de integração).
6. **D19 (OpenCV).** Há pacote para o Python 3.14 no Windows (`opencv-python-headless` 5.0.0.93, `cp37-abi3`, e `numpy` 2.5.4, `cp314`); instalar é possível, **não testado em execução no Windows**. `cv2.absdiff` + `mean` mediu 3,9 ms em 1920x1080 contra 211 ms do código atual. Decisão: adotar como dependência obrigatória (recomendação do roadmap) ou não.
7. **Plano visual** (`PLANO_VISUAL.md`, seção 8): simplificação da barra (15 para 8) e botão único Executar e Parar; Gravar com estados; paleta de comandos no Ctrl+K; nome "Ajustes da automação"; e **Android nativo (Kotlin e Compose) ou reaproveitando Python (Kivy, BeeWare)?**
8. **`ALTERACOES_25_5_para_25_6.diff`** (230 KB, na raiz) não é cópia de nada em `md/`. Se não tiver mais uso, pode sair (o histórico do Git o guarda). Não foi removido.

## 6. Registro de integrações

Ambiente: Linux, Python 3.14.4, PySide6 6.12.0, display virtual. "Falhas antigas" são as 3 de fim de linha dos `.bat` em clone novo (`tests/static`, `tests/regression` e `tests/unit/test_mutacoes.py`), resolvidas pelo `.gitattributes`.

| Data | Ramo ou origem | Commit na `main` | Resultado |
|---|---|---|---|
| 30/10/2026 | `visual/novo-tema` (`6e42294`) | `51278c2` | Sozinho: 1490 passam e 22 de janela ok; só as falhas antigas. Zero conflitos |
| 30/10/2026 | `funcoes/ativacao-mapas` (`29e9a8c`) | `c201431` | Sozinho: 1630 passam e 34 de janela (5 pulados sem display virtual); só as falhas antigas. Junto com o visual: 1645 passam; zero conflitos |
| 30/10/2026 | `.gitattributes` | `6f7bf05` | 1648 passam e 34 de janela ok; **0 falhas** |
| 30/10/2026 | Testes do `vision.py` e fluxo do GitHub Actions | `c42b96d`, `33cd0a1` | 1677 passam, 11 pulados (9 só do Windows de verdade, 2 que pedem OpenCV), 7 `xfail` estritos, 34 de janela ok; **0 falhas**. Cobertura do `vision.py`: 18% para 85% |
| 31/10/2026 | Catálogo de funções (45 funções) e seus testes, script de medição, planos das frentes, `DESEMPENHO.md` | (commits seguintes) | 1680 passam, 11 pulados, 7 `xfail`, 36 de janela ok; **0 falhas**. O teste de funções foi verificado com 4 alterações simuladas (botão removido, renomeado, escondido e botão novo sem catálogo): pegou as quatro |
