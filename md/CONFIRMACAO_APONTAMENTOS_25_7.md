# Confirmação dos apontamentos do plano 25.7 contra o código real

Este relatório responde ao seu pedido de 24/10/2026: **confirmar** cada apontamento do "Planejamento de desenvolvimento da versão 25.7" no código e **integrá-lo ao roadmap** (`md/ROADMAP.md`, que foi reescrito junto com este relatório). A sua observação principal, "corrigir primeiro o visual final e só depois fazer as funções funcionarem", está aplicada no roadmap (seção 4).

**Base conferida.** É a árvore da 25.6. O código do programa é o da 25.5; só a string de versão difere. Li os módulos citados abaixo, inclusive os 3 mapas reais (`tests/data/legacy_maps.json.gz`). **Nada foi executado no Windows**, e o ambiente onde trabalho não tem o PySide6 de verdade: tudo o que depende de ver a janela está marcado como "depende do Windows". As linhas citadas (`arquivo:linha`) são as da 25.6 e mudam quando o código mudar.

**Classificação de confiança** (a mesma de sempre): *confirmada* (o código mostra), *altamente provável* (decorre do código, falta ver a tela), *provável*, *hipótese*.

## Resumo

| Apontamento | Veredito | Em uma linha |
|---|---|---|
| 2.1 Tutorial: avança com qualquer clique | **Confirmado** | Qualquer clique na janela ou qualquer tecla avança (`tutorial.py:217-225`); o balão até diz isso. |
| 2.1 Tutorial: o programa faz por você | **Confirmado, e é pior** | A camada do tutorial cobre a janela inteira e engole todo clique, e no fim o exemplo é executado sozinho (`main_window.py:1114-1120`). |
| 2.1 Anel vermelho quebrado, balão sobre a edição | **Altamente provável** | A camada não acompanha a janela ao redimensionar; o balão só evita o próprio alvo. Falta ver no Windows. |
| 2.1 Pulsação e transições suaves | **Não existe** | Não há nenhum temporizador nem animação em `tutorial.py`. |
| 2.1 Conteúdo desatualizado | **Confirmado** | Pelo menos 5 trechos errados ou incompletos (lista abaixo). |
| 2.2 Sidebar voltou a cortar | **Plausível pelo código; "voltou" não confirmado** | O mecanismo de quebra é idêntico da 25.3 à 25.6; ele nunca cobriu linhas montadas à mão. |
| 2.3 Ativação por mapa | **Não existe** | Nenhum estado por mapa: todo mapa com tecla é registrado ao abrir. A mensagem de conflito de hoje não diz de quem é a tecla. |
| 2.4 Timeline avançada | **Confirmado** | A única diferença entre Simples e Avançada é o texto do rótulo de cada linha (`timeline.py:253-255`). |
| 2.4 Teclas gravadas → Texto | **Viável, com limites que o plano não previa** | O gravador só registra letras, dígitos, Ç e teclas nomeadas; pontuação nunca é gravada. |
| 3.1 Espera por imagem | **Já existe em parte** | "⏳ Esperar" + condição de imagem: o plano descreve como novo o que é uma evolução. |
| 3.2 Grupos, repetições, condições | **Não existe** | Os grupos de hoje são visuais; o gravador cria grupos automáticos "A, B, C…" que colidem com o vocabulário do plano. |
| 4 IA | **Compatível** | Nada da 25.7 depende dela; a chave de API não pode ir para o banco de configurações de hoje. |

---

## 2.1 Tutorial inicial

Código: `tutorial.py` (253 linhas) e o roteiro em `main_window.py:916-1120`.

| Afirmação do plano | O que o código mostra | Confiança |
|---|---|---|
| Avança com clique em qualquer parte | `mousePressEvent` chama `_next()` para todo clique que não seja no link "Pular tutorial" (`tutorial.py:217-221`); `keyPressEvent` faz o mesmo com **qualquer tecla**, inclusive modificadoras (`:223-225`). O texto do balão diz "Clique em qualquer lugar ou pressione qualquer tecla para continuar" (`:114`, `:214`). | Confirmada |
| Maximizar avança a etapa sem querer | O mecanismo está confirmado: qualquer clique na área da janela ou qualquer tecla avança. **Qual gesto de maximizar** chega como clique ou tecla à área da janela no seu Windows (por exemplo Win+↑, ou o clique que sobra de um duplo clique na barra de título) eu não consegui determinar sem executar. A correção não depende disso: "só avança com a ação indicada" elimina todos os casos. | Mecanismo: confirmada. Gesto exato: provável |
| O usuário não experimenta, o programa faz por ele | (a) A camada do tutorial é filha da janela, ocupa a janela inteira (`:62`) e trata todo clique (`:217`): **enquanto o balão está aberto, o usuário não consegue clicar no controle destacado.** (b) No último passo, `_finish_tutorial_demo` pergunta a tecla e **executa o exemplo sozinho** (abre o Bloco de Notas e digita), sem o usuário apertar nada (`main_window.py:1100-1105`, `:1114-1120`). O texto do passo anuncia isso (`:962`). | Confirmada |
| Pular tutorial sem confusão com clique acidental | O link é um texto de 9 pt, 22 px de altura, encostado acima do balão (`tutorial.py:8-34`, `:174-181`); um clique nele encerra **toda** a jornada, sem confirmação (`:227-228`; `main_window.py:1049-1062`). Um clique impreciso ao lado avança a etapa. | Confirmada |
| Pulsação e transições suaves | `tutorial.py` não usa `QTimer`, `QPropertyAnimation` nem `QVariantAnimation`. O balão e o anel mudam de lugar de uma vez. | Confirmada (ausência) |
| Anel vermelho quebrado ao minimizar/maximizar | A camada não está em nenhum layout; seu tamanho só é refeito ao avançar de etapa (`_refresh`, `tutorial.py:58-65`). `MainWindow.resizeEvent` e `moveEvent` (`main_window.py:2119`, `:2125`) não a tocam e `changeEvent` (`:284`) só trata os teclados virtuais. Depois de maximizar, a camada continua do tamanho antigo, o alvo é recortado a ela (`tutorial.py:105`) e o balão fica onde estava (posição guardada em `_bubble_rect`). O resultado tem de ser um anel recortado e deslocado. **Como isso aparece na tela, só vendo no Windows.** | Altamente provável |
| Balão encobre a área de edição | `_bubble_geometry` (`tutorial.py:132-167`) tenta abaixo, acima, à direita e à esquerda do alvo e fica com a primeira posição que cabe. Só evita **o próprio alvo**; não existe a ideia de uma área que deva ficar livre. Altura de até 300 px (`:119`). | Altamente provável |
| Tutorial extenso | 24 textos de passo. Três são longos: 828 caracteres ao adicionar comando (`main_window.py:1021`), 648 em configurações (`:1038`) e 404 ao editar (`:1029`). O balão tem teto de 300 px (`tutorial.py:119`) e o texto é desenhado num retângulo (`:208`) que **corta** o que passar. Estimativa: cerca de 650 caracteres cabem; o de 828 tende a ser cortado. O de 828 também repete uma frase ("As explicações curtas… tooltip…" aparece duas vezes). | Comprimentos: confirmada. Corte: provável (depende da fonte e da escala do Windows) |

**Conteúdo desatualizado ou incorreto, confirmado:**

1. `main_window.py:978`: "A visão avançada expõe controles para ajustes mais precisos de tempos, sobreposições, grupos e movimentos". Hoje a visão avançada **não expõe controle nenhum** (ver 2.4).
2. `:942`: lista cinco tipos de comando; o editor tem sete (faltam "Abrir aplicativo" e "Esperar", `command_editor.py:91`).
3. `:944`: diz que o conteúdo da barra lateral "pode ser rolado para revelar opções que não cabem na largura". O plano 2.2 quer o contrário (reorganizar); o texto muda junto com a correção.
4. `:961-962`: o passo "escolha a tecla" aponta para um **rótulo** (`hotkey_label`), não para o botão que muda a tecla ("⚙ Configurações da automação", `:592`). Esse botão é uma variável local (`cfg`), sem atributo na janela: **não dá para destacá-lo nem validar o clique** sem antes dar a ele um nome estável. A mesma limitação vale para qualquer controle novo que o tutorial precise apontar.
5. O tutorial não cobre: diferença entre comando de teclado, texto e esperar; espera por imagem; ativação de mapas e atalhos de execução; modo avançado da timeline. São itens da sua lista de conteúdo.

**Testes que existem hoje:** um (`test_primeiro_uso_prepara_a_demonstracao_sem_executar_nada`, `tests/gui/test_main_window_smoke.py:65`), e a fábrica `abrir_janela` **dispensa** o tutorial por padrão (`tests/conftest.py:208-226`). Nenhum teste cobre clique, tecla, redimensionar, passos ou limpeza. **TUT-01 a TUT-05 são todos novos.**

**O que isto exige no desenho** (entra no roadmap, seção 4):

- A camada precisa **deixar o clique passar na região do alvo** (hoje engole tudo) e observar a ação real do controle, para só então liberar a etapa.
- Cada passo precisa de um **alvo com nome estável** e de uma **condição de conclusão verificável** (uma função pura, testável sem janela).
- A janela precisa avisar a camada quando muda de tamanho, de posição ou de estado (maximizada, restaurada, minimizada).
- O balão precisa de **áreas proibidas** (o alvo, a área de edição e os próximos controles).
- Textos curtos por passo; o que hoje é um texto de 800 caracteres vira vários passos.
- Ao pular ou fechar, nenhuma camada, animação ou temporizador do tutorial pode ficar vivo (TUT-04). Hoje não há animações, mas já houve um defeito de fechar a camada errada (comentário em `main_window.py:1041-1043`).
- O fim do tutorial **não executa nada**: oferece o botão "Executar o exemplo" e o usuário decide.

---

## 2.2 Sidebar responsiva

| Afirmação do plano | O que o código mostra | Confiança |
|---|---|---|
| "Algumas informações voltaram a ficar cortadas" | O mecanismo de reorganização é **idêntico** na 25.3, 25.4, 25.5 e 25.6: comparei as linhas de `_standardize_field`, `resizeEvent` e `_apply_responsive_forms` das quatro árvores. **Não tenho versões anteriores à 25.3**; se a correção antiga estava fora desse mecanismo, não consigo vê-la. Então o relato é plausível pelo código (causas abaixo), mas **"voltou por mudança de código" não está confirmado**. | Relato plausível; regressão de código, não confirmada |
| Campos e ícones deviam passar para a linha de baixo | A quebra que existe é `QFormLayout.WrapAllRows`, ligada quando a largura é menor que 390 px (Configurações: 430), e só reorganiza **rótulo → campo** (`command_editor.py:284-293`, `:1262-1263`). Linhas montadas à mão com `QHBoxLayout` **não quebram**: "aplicativo + Procurar executável…" (`:95`), "imagem + Procurar…" (`:163-165`) e os botões da condição (`:179`). | Confirmada |
| Campos espremidos | `_standardize_field` fixa **mínimo de 160 px e máximo de 380 px** em todo campo, inclusive nos contêineres de linha (`command_editor.py:270-278`). Com a coluna mais estreita que 160 px mais o botão, o Qt espreme ou recorta. | Confirmada (o código); o efeito, altamente provável |
| Largura definida pelo usuário | A barra principal admite largura mínima de 160 px (`main_window.py:782`) e o conteúdo **rola na horizontal** (`DragScrollArea`, `command_editor.py:843-934`): o desenho atual escolheu rolar, não reorganizar. As larguras salvas são `sidebar_width`, `sidebar_last_manual_width` e `workspace_splitter_sizes` (`project.py:212`). | Confirmada |

**Achado que o plano não previa: há duas barras laterais.** A da janela principal e a **da timeline**, que tem largura **fixa de 340 px** (`timeline.py:823`) e contêiner com mínimo de 160 px (`:830`). A correção precisa cobrir as duas, mais a tela de linhas mescladas e as Configurações.

**Testes que existem hoje:** os de janela abrem e gravam; **nenhum mede corte ou sobreposição**. UI-01 e UI-02 são novos. Na sua máquina o teste roda com a plataforma `offscreen`, que calcula o layout de verdade: a **geometria** (cada controle dentro da área visível, sem sobreposição, rótulo ao lado ou acima do seu campo) pode ser conferida automaticamente. O **aspecto** (texto cortado por fonte e escala) pede captura de imagem (modo `visual`, roadmap 4.6).

---

## 2.3 Seleção de mapas e ativação

| Afirmação do plano | O que o código mostra | Confiança |
|---|---|---|
| Hoje não há controle de ativação | `AutomationMap` não tem campo de ativação (`core.py:727-750`) e `AppSettings` guarda só gravação, atalhos de controle, aparência e pasta (`project.py:195-240`). **Todo mapa com tecla é registrado ao abrir** e a cada alteração (`_register_all_hotkeys`, `main_window.py:243`, `:1529-1538`; 11 pontos de chamada). | Confirmada |
| A tela mostra o estado de cada mapa | A seleção é uma lista de **nomes** (`main_window.py:530`, `:1241-1253`); não há coluna de tecla, de estado nem de conflito. | Confirmada |
| Detectar conflito com mensagem clara | O conflito só é detectado **no registro** (`input_system.py:624-638`): quem chega depois perde em silêncio e **um único aviso** lista os problemas (`main_window.py:1555-1559`). O texto é "O atalho '=' usa a(s) mesma(s) tecla(s) que '=', já em uso." (`input_system.py:634-637`): repete a tecla e **não diz qual automação a usa**. A checagem `validate_all`, que acusa teclas repetidas entre mapas (`project.py:107-117`), **não é chamada por nenhuma tela** (só pelos testes). | Confirmada |
| Mapas desativados não executam por atalho | Hoje não existe o estado "desativado". Um mapa sem tecla ou cujo registro falhou não executa por atalho; isso não é o mesmo que desativar. | Confirmada (a ausência) |
| — | **Todo mapa novo nasce com a tecla "="** (`main_window.py:1300`, `core.py:757`). Nos 3 mapas reais as teclas são distintas (`MOUSE_X1`, `=`, `MOUSE_X2`), então hoje não há conflito na abertura; mas **criar um quarto mapa já conflita com o exemplo ("=")**. | Confirmada |
| — | A tecla de iniciação, a repetição, o intervalo, a velocidade, a "próxima automação" e o comportamento de conflito são editados por **6 caixas de diálogo em sequência** (`main_window.py:1418-1509`). Não há onde mostrar o estado de ativação nem o conflito. | Confirmada |

**Consequências para o desenho:**

- A preferência permanente cabe no banco de **configurações**, por nome de mapa (renomear e excluir a acompanham). **Isso não muda o formato dos mapas**, que é o que o plano pede para manter bloqueado. Se algum dia virar campo do mapa, a lista fixa de campos que o desfazer restaura (`project.py:340-343`) precisa ser atualizada.
- A regra "ativação temporária não altera a preferência" tem uma **ambiguidade** que o plano não resolve: de "Sempre ativo" para "Ativo nesta sessão". Está na decisão D26 do roadmap, com recomendação.
- O estado de atalhos é refeito também depois de desfazer e refazer (`main_window.py:1396`): a regra de ativação precisa valer nesse caminho.

---

## 2.4 Timeline: modo avançado

| Afirmação do plano | O que o código mostra | Confiança |
|---|---|---|
| O modo avançado não faz diferença funcional | **Confirmado, e a diferença é só o rótulo.** `_simple_mode` é lido em um único lugar (`timeline.py:253-255`): na visão simples a linha mostra o número; na avançada, o alvo (ou o tipo) mais o `[grupo]`. Mover, redimensionar, reordenar, seleção por retângulo e menu de contexto são **iguais** nos dois modos. Além disso, abrir a timeline volta sempre para "Simples" (`main_window.py:892-894`). | Confirmada |
| Arrastar e soltar para mesclar | Já existem três gestos de arrasto: mover no tempo, redimensionar e **reordenar na vertical** (começa depois de 10 px ou 35% da altura da linha, `timeline.py:502-506`). Soltar uma barra sobre outra **não tem significado próprio**; mesclar disputaria o mesmo gesto da reordenação e precisa de um alvo de soltar distinto (ou de um botão). | Confirmada |
| Desfazer e refazer | Cada gesto vira uma transação (`_on_timeline_edited`, `main_window.py:1366-1374`, rótulo "Edição temporal"); o histórico guarda cópias do mapa inteiro (`project.py:291-305`). Mesclar pode seguir o mesmo caminho, **numa transação só**. | Confirmada |
| Converter teclas gravadas em Texto | Existe o comando Texto (`InputType.TEXT`, `core.py:258`). Não existe a operação "trocar N comandos por 1" no modelo (há inserir, remover, mover e duplicar); ela entra como operação pura do mapa, testável sem janela. | Confirmada (a ausência) |

**O que o gravador realmente registra** (isto limita a conversão e o plano não previa):

- `key_to_name` (`core.py:646-663`) aceita **teclas nomeadas** (Shift, Enter, Espaço, F1 a F12…, tabela em `core.py:95-109`) e caracteres que sejam **letras ou dígitos, mais o Ç**, sempre em **MAIÚSCULA**. Qualquer outro caractere (vírgula, ponto, hífen, símbolos) **retorna vazio e o evento é descartado: nunca é gravado**.
- A maiúscula não é gravada: o **Shift** (e o **CapsLock**) viram comandos próprios, sobrepostos no tempo ao da letra (`input_system.py:1787-1794`, `:1868-1879`).
- Cada tecla vira `Command(KEY, PRESS_AND_RELEASE, início, duração)`; teclas mantidas pressionadas contam uma vez só (a repetição automática do sistema é ignorada, `:1855-1859`).
- O gravador marca com **letras A, B, C… os comandos que se sobrepõem** (`:1884-1920`).
- Letras acentuadas e símbolos com Shift dependem de como o pynput entrega a tecla morta e o caractere com Shift: **hipótese**, é uma das verificações que precisam do Windows.

**Consequências para a conversão (entram na decisão D28):**

1. A conversão só pode devolver o que o gravador capturou. Uma frase com vírgula já saiu **incompleta** da gravação; a prévia precisa **avisar** disso, e não prometer "o que foi digitado".
2. Maiúsculas: precisam olhar o Shift sobreposto. O **estado inicial do CapsLock é desconhecido**; se houver CapsLock no trecho, a regra segura é não converter e avisar.
3. Teclas especiais (Backspace, Enter, setas…) e qualquer modificador diferente de Shift (Ctrl, Alt, Win) **encerram o trecho convertível**; atalhos nunca viram texto.
4. Tecla **mantida** além do tempo de repetição do sistema pode ter gerado várias letras na digitação original; converter para uma letra mudaria o resultado: avisar ou recusar.
5. **Pausa significativa**: o Texto digita com intervalo **fixo** entre caracteres (`calculate_text_duration`, `core.py:221-231`; padrão de 10 ms, configuração global `text_char_interval`, `project.py:214`). O comando Texto **não tem intervalo próprio** (`core.py:299-355`): o requisito "revisar o intervalo entre caracteres" só pode apontar para a configuração global, a menos que se acrescente um campo ao comando (mudança de formato, bloqueada).
6. **Tempo**: o motor agenda por tempo absoluto (`_play_timeline`, `input_system.py:1222-1257`) e mover/reordenar recalcula em cascata preservando as lacunas (`core.py:930-960`); `remove_commands` pode compactar o tempo (`:973-996`). Para não perder informação de tempo, o Texto assume o início da 1ª tecla e **os comandos seguintes não se movem**: a diferença vira uma lacuna explícita, e a prévia mostra "gravado: X s → texto: Y s".
7. O Texto digita pelo layout de teclado **ativo na hora** (`input_system.py:424-444`, com composição de acentos do ABNT2): ele não reproduz a digitação física; reproduz os caracteres.

**Testes que existem hoje:** operações do mapa (`tests/unit/test_map_operations.py`), gravador (`tests/engine/test_recorder.py`) e a timeline abrindo com os 3 mapas reais. **Nenhum para conversão.**

---

## 3.1 Espera por imagem

O plano descreve um comando novo. **Ele já existe em parte**: o tipo "⏳ Esperar" (`command_editor.py:91`) com condição de **imagem** (`WaitConditionType.IMAGE`, `conditions.py:8-12`), executada por `wait_for_image` (`vision.py:108-133`). Os achados F1 a F9 do roadmap continuam valendo.

| Item do plano | Hoje | Confiança |
|---|---|---|
| Imagem de referência escolhida pelo usuário | Arquivo escolhido por "Procurar…" (`command_editor.py:163-165`); o caminho gravado é **absoluto** (`:473`). Não há captura de tela nem de região (F8). | Confirmada |
| Tempo máximo (exemplo: 60 s) | O campo existe; o padrão atual é **0 = esperar para sempre**. | Confirmada |
| Intervalo entre verificações (padrão 1 s) | O campo existe; o padrão atual é **0,5 s** (`conditions.py:55`; `input_system.py:1358`). | Confirmada |
| Comportamento ao esgotar (padrão: parar) | **O único desfecho de hoje é parar com erro** (`input_system.py:1359-1362`): já é o padrão que o plano quer. Os outros desfechos não existem (F2). | Confirmada |
| Reinício automático com limite de tentativas | Não existe. | Confirmada |
| Indicadores de estado | Não existem; só o log registra o sucesso (`IMAGE_READY`, `input_system.py:1364`). Exigem um canal novo do motor para a interface. | Confirmada |
| Encontrar libera o próximo comando uma única vez | A espera roda uma vez, antes do primeiro evento do comando (`_attach_conditions`, `core.py:1214-1218`), e o tempo gasto desloca o relógio da timeline. | Confirmada (leitura) |
| Parada manual interrompe a busca | `stop_event.wait` entre verificações (`vision.py:130-133`); a reação leva, no máximo, uma captura mais uma comparação. | Confirmada (leitura) |
| Módulo isolado de captura e comparação | `vision.py` é separado, mas importa o PySide6 no topo (`:8`) e captura pela thread do motor (F6). | Confirmada |
| Temporários com ciclo de vida definido | **Hoje não há arquivo temporário nenhum**: a captura vive em memória e a referência é um arquivo do usuário. O ciclo de vida só passa a existir se decidirmos guardar a imagem junto do mapa e a captura da falha em `logs\` (D23). | Confirmada |
| Compatibilidade validada tecnicamente | Pendente: F5 (OpenCV não declarado), F7 (escala do Windows), F9 (custo). A "verificação opcional" do roadmap continua aberta. | — |

Os padrões novos (60 s e 1 s) só podem valer para **condições novas**: as já gravadas guardam os seus valores e um mapa antigo deve abrir idêntico.

---

## 3.2 Grupos, repetições e condições

| Item do plano | Hoje | Confiança |
|---|---|---|
| Grupo = conjunto nomeado de ações | `CommandGroup` tem nome, cor, descrição e sugestão de atraso (`core.py:698-725`): é organização visual. | Confirmada |
| Repetição de grupo ou bloco | A repetição existe **só no mapa inteiro** (`repeat_count`, `repeat_interval`, `core.py:737-738`; laço em `input_system.py:1167-1184`) e o encadeamento de mapas (`next_map`, `main_window.py:1203-1223`; `input_system.py:1456-1458`). | Confirmada |
| Condição de continuação | Só por comando (esperas por processo, tempo e imagem, `conditions.py`). Não há condição "entre grupos". | Confirmada |
| Executar só um grupo ou trecho | Não existe. O motor executa o mapa inteiro. | Confirmada |
| Indicar o grupo e a etapa em execução | O motor avisa cada evento com o `command_id` (`on_event`, `input_system.py:1326-1330`): a interface **pode** mapear para o grupo; hoje só mostra estado, último evento e progresso. | Confirmada |
| Exemplo das três guias | Hoje só com **4 mapas encadeados** (`A` com repetição 3 e "próxima automação"…). "Continuar na guia anterior" depende do navegador (ao fechar a guia ativa, ele mostra a vizinha), não do programa. | Confirmada (o que o programa faz); o navegador, hipótese |

**Achado que o plano não previa: colisão de vocabulário.** O gravador cria **grupos automáticos por sobreposição**, com nomes A, B, C… (`input_system.py:1884-1920`), e eles são gravados como grupos comuns (`core.py:1091-1101`). Nos mapas reais gravados, **100% dos grupos têm nome de uma a três letras**: "Flins combo" tem 370 grupos (365 em uso) para 933 comandos e "Click genshin", 14 (8 em uso) para 8 comandos. O "Grupo A — Abrir guias" do plano seria um grupo do mesmo tipo de dado, e o nome "A" já existe nesses mapas. Os dados de hoje **não distinguem** um grupo automático de um grupo escolhido pelo usuário. Decisão D31 do roadmap.

**A arquitetura encontrada ajuda.** `build_timeline` (`core.py:1189-1211`) é uma **função pura** que transforma o mapa em eventos ordenados, cada um com o `command_id`, e as condições já viajam no primeiro evento do comando. É o ponto natural para o **escopo** (grupo ou trecho) e a **repetição**: expandir os eventos na construção, sem tocar no laço do motor, e testar com o relógio virtual e o backend falso (GRP-01 a GRP-03). O que **exige mexer no motor** é a política por falha (hoje exceção vira estado ERRO) e "voltar/retomar" (hoje `for event in timeline`, `input_system.py:1226`).

---

## 4. Assistência por IA (versão futura)

- `AppSettings` grava **tudo em texto JSON na mesma tabela SQLite** (`project.py:154-180`): a **chave de API não pode ir ali**. Pede um cofre fora do banco, decisão da versão da IA.
- O modelo já tem **validação** (`Command.validate`, `AutomationMap.validate`, `validate_structure`, `core.py:434`, `:787`, `:862`), **duplicação** (`copy.deepcopy`, `duplicate_commands`) e **serialização** (`to_dict`/`from_dict`). Falta uma **comparação (diff) pública de mapas**: hoje só existe nos testes (`differences`, `tests/testsupport/gui_helpers.py:134`), e a validação estrutural ainda não conhece grupos e condições novos.
- Nada da 25.7 chama IA, guarda chave ou apresenta a IA como disponível.

## 5 a 8. Processo, testes, ordem e condições para começar

Mapeados no roadmap (seções 3, 5, 10 e 11). Sobre o item 8 do plano: a base é a árvore 25.6 (idêntica à 25.5 no programa), os módulos responsáveis estão identificados na seção 3 do roadmap, e **não usei versão antiga como substituta**.

---

## O que só o Windows responde

Nada abaixo foi verificado; é a lista do que precisa da sua máquina:

1. Que gesto de maximizar faz o tutorial avançar (TUT-02).
2. Como fica o anel vermelho e o balão depois de maximizar, restaurar e minimizar.
3. Se o texto de 828 caracteres é cortado no balão.
4. Quais controles da barra lateral ficam cortados, e em que largura (UI-01, UI-02), com a escala do Windows em uso.
5. Se letras acentuadas e símbolos com Shift entram na gravação, e como (limites da conversão de teclas em texto).
6. As verificações F5, F7 e F9 da espera por imagem (OpenCV no Python 3.14, escala do Windows, custo).
7. O resultado da rodada de testes da 25.6 (ainda aguardo `logs\tests_last_run.txt` e, se existir, `logs\travamento_qt.txt`).

---

## Correções de números feitas na conferência final

Ao conferir de novo os números do roadmap contra o código e os dados, achei e corrigi três imprecisões **minhas**:

1. **Sobreposição no "Flins combo".** O texto dizia que 568 dos 932 pares consecutivos de comandos se sobrepõem. Contado com a mesma definição de lacuna que o código usa para reencadear (`core.py:931-942`: início do seguinte menos o fim programado do anterior), **444** dos 932 pares se sobrepõem (488 têm folga e nenhum encosta exatamente). Os **568** são os pares que ficam no **mesmo grupo de simultâneos** do gravador, que é outra medida. A frase também estava no relatório da 25.5 (`md/PONTO2_IMPLEMENTACAO_25_5.md`, linha 102): corrigida na árvore de trabalho e entra no próximo pacote. A conclusão não muda (há muita sobreposição, e "voltar K comandos" precisa de regra explícita), só o número.
2. **Custo da comparação de imagem (F9).** Remedi o laço de `compare_images` em Python puro: cerca de 6 ms para 200×100 e **120 a 270 ms** de 800×600 a 2560×1440. O pior caso é perto de 1 milhão de pixels (por exemplo 1280×720), porque a subamostragem só começa acima de 1 milhão. Antes eu tinha escrito "150 a 200 ms".
3. **Testes de referência.** A suíte da 25.6 tem 1.514 testes, mas "verdes" são 1.267 no modo lógica (mais 5 `xfail` esperados e 242 pulados, que exigem o Qt de verdade) e 1.478 com o dublê de widgets (31 pulados). Rodei os dois modos de novo: 0 falhas.
