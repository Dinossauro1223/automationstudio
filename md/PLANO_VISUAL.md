# Plano da frente visual: menos botões, mais interação e a mesma cara no Android

Escrito pela conta de integração em 31/10/2026, a pedido do dono. A frente visual **fica sempre**: é ela que cuida da aparência hoje e que, depois, leva o programa ao Android. O que o dono pediu: o programa precisa **continuar parecendo o mesmo nas duas plataformas**, e a interface deve ter **menos botões e ser mais interativa**, sem que nenhuma função se perca ou fique inacessível. Este plano diz como fazer isso em passos pequenos, cada um testável. A frente refina o plano; o que ela não pode é deixar uma função sem endereço.

## 1. Antes de mexer: a rede de segurança

`md/FUNCOES_DO_USUARIO.md` é o catálogo do que o programa faz: 45 funções, cada uma com um **ID que não muda** (F01, F02...) e com o endereço de onde o usuário a aciona hoje. Dois testes abrem a janela de verdade e conferem o catálogo:

- `tests/gui/test_funcoes_acessiveis.py`: em cada tela (lista, editor com uma automação aberta, timeline) toda função tem pelo menos um endereço **visível**; e nenhum controle da janela está fora do catálogo.
- `tests/unit/test_funcoes_do_usuario_catalogo.py`: o catálogo é bem-formado, o documento em md acompanha e os endereços de menu de contexto, diálogo e tecla ainda existem.

Verificado em 31/10/2026 que o teste pega os quatro jeitos de perder uma função: o botão sai do código, muda de nome, continua no código mas fica escondido, ou um botão novo aparece sem entrar no catálogo.

Regras:

1. **Mover ou renomear um controle**: mude a linha da função em `tests/testsupport/funcoes_do_usuario.py` e regenere o documento (`python tests/testsupport/funcoes_do_usuario.py > md/FUNCOES_DO_USUARIO.md`), no mesmo commit.
2. **Retirar uma função de vez**: só com decisão do dono. O commit diz "função F__ retirada por decisão do dono em <data>: <motivo>".
3. **Controle novo**: função nova no catálogo, com ID novo (nunca reaproveite um ID).
4. **Botão que alterna** (Executar vira Parar, Gravar vira Parar gravação): a função do estado que não está à vista também precisa de endereço conferido. Quem criar o botão acrescenta ao teste as telas "executando" e "gravando" (a janela posta nesses estados com o motor de mentira) e declara no catálogo o endereço de F11, F18 e F19 nelas.
5. Achado: o botão "Começar a usar" fica numa página do tutorial antigo (índice 0 da pilha de páginas) que nenhum código mais exibe; é código morto, não função. Pode sair junto com a página (P1).

## 2. Princípios

1. **Uma ação principal por tela**, bem à vista; o resto some até ser preciso.
2. **Ação no objeto**: duplo clique abre; arrastar reordena; clique direito (no Android, segurar) abre o menu do que se pode fazer ali. O mesmo menu nas duas plataformas.
3. **O botão muda com o estado**, em vez de dois botões: Executar vira Parar; Gravar vira Parar gravação.
4. **O que é perigoso fica sempre à vista e inconfundível** (Parar tudo). **O que é raro vai para "Mais"**.
5. **Navegação por destinos** (Automações, Editor, Timeline, Monitor), não por "← Voltar" em cada tela.
6. **Resposta imediata e reversível**: estado sempre visível; aviso curto com "Desfazer" em vez de caixa de confirmação.
7. **Toda função é encontrável pelo nome** (paleta de comandos): nenhuma depende de achar um botão.
8. **Mesmo vocabulário, mesmos ícones, mesmas cores nas duas plataformas** (tokens, seção 5).

## 3. Inventário atual e proposta

Levantado no código em 31/10/2026 (`main_window.py`, `command_editor.py`, `timeline.py`). A coluna "ID" aponta a função no catálogo: nenhuma some, só muda de endereço.

### Barra principal: 15 ações hoje, 8 controles visíveis na proposta

| Hoje | Proposta | Onde a função fica | ID |
|---|---|---|---|
| ＋ Nova automação | fica, é a ação principal | barra; Ctrl+N | F01 |
| 💾 Salvar | fica, com marca de "alterações não salvas" | barra; Ctrl+S | F04 |
| ▶ Executar e ■ Parar | **um** botão que alterna | o mesmo botão; tecla de parada | F10, F11 |
| 🛑 Parar tudo | fica sempre visível, cor de perigo, separado dos demais | barra; tecla global | F12 |
| ● Iniciar gravação, ✕ Cancelar gravação e ▶ Pré-visualizar gravação | **um** botão "Gravar" com estados; ao terminar, uma faixa "Gravação pronta: Pré-visualizar · Descartar" | botão e faixa; Esc cancela | F17, F18, F19 |
| ↶ Desfazer e ↷ Refazer | só ícones, juntos | barra; Ctrl+Z e Ctrl+Y | F07, F08 |
| ⚙ Configurações | menu "⋯ Mais" | Mais | F33 |
| ▣ Monitor de execução | vira destino de navegação | abas | F13 |
| ❔ Tutorial | Mais | Mais | F34 |
| ⌨ Mostrar teclado e 🖱 Mostrar mouse | submenu "Exibir" dentro de Mais | Mais, Exibir | F35, F36 |

Há duas engrenagens com nome quase igual: "⚙ Configurações" (do programa) e "⚙ Configurações da automação". Na proposta a segunda vira "Ajustes da automação".

### Lista de automações

| Hoje | Proposta | ID |
|---|---|---|
| ＋ CRIAR NOVA AUTOMAÇÃO | fica como ação principal da tela; é a mesma função da barra (F01): um endereço principal por tela | F01 |
| 📂 ABRIR / IMPORTAR MAPA EXTERNO | "Importar..." no menu da lista, e soltar um arquivo `.json` sobre a janela | F02 |
| ABRIR AUTOMAÇÃO SELECIONADA | some como botão: duplo clique ou Enter na lista abre | F03 |

### Editor

| Hoje | Proposta | ID |
|---|---|---|
| ← Escolher outra automação | vira o destino "Automações" | F05 |
| ⚙ Configurações da automação | engrenagem ao lado do nome, com o nome editável no lugar | F06 |
| ▣ Abrir Timeline | vira o seletor "Tabela · Timeline" do editor | F27 |
| Faixa de ativação (25.8) | fica; o estado aparece também na lista (tarefa V1) | F09 |
| ＋ ADICIONAR COMANDO | fica, é a ação principal da tabela | F20 |
| Editar comando | some como botão: duplo clique ou Enter na linha, e menu de contexto | F21 |
| Excluir selecionados, ▲ Subir, ▼ Descer, ● Grupos, Mais... | viram uma **barra de seleção** que só aparece com linhas selecionadas ("3 selecionados: Subir · Descer · Agrupar · Excluir · Mais"); arrastar já reordena; Alt+↑/↓ e Delete como atalhos | F22 a F26 |

### Timeline

| Hoje | Proposta | ID |
|---|---|---|
| ← Voltar ao editor | destino de navegação | F14 |
| ＋ Adicionar comando, Editar comando, Excluir selecionados (repetem os do editor) | a mesma barra de seleção do editor | F20 a F22 |
| Simples e Avançada | um controle segmentado | F28, F46 |
| − , + , Ajustar e Snap | ícones agrupados; zoom também com Ctrl+roda; Snap vira chave liga/desliga | F44, F45, F29, F30 |
| Editar linhas mescladas e Criar novo grupo (menu de contexto) | ficam no menu de contexto | F31, F32 |

Contagem: barra 15 para 8; lista 3 botões para 1 (mais o menu); editor, 3 botões de navegação viram destinos; a tabela de comandos passa de 7 botões fixos para 1 mais uma barra contextual; a timeline deixa de repetir os botões do editor.

## 4. Mais interativo

- **Duplo clique ou Enter** abre uma automação ou edita um comando.
- **Arrastar**: reordenar comandos (já existe), organizar as automações na lista, soltar um `.json` para importar.
- **Menu de contexto** (clique direito; no Android, segurar) com as mesmas ações na lista, na tabela e na timeline.
- **Edição no lugar**: o nome da automação no título; os valores nas células (já existe, `ExcelLikeDelegate`).
- **Barra de seleção** contextual (seção 3).
- **Busca**: filtro na lista de automações e na tabela de comandos (Ctrl+F).
- **Paleta de comandos (Ctrl+K)**: um campo "o que você quer fazer?" que lista **todas as funções do catálogo pelo nome**. É a rede de segurança da simplificação: mesmo que um botão suma, a função fica a uma busca de distância. No Android vira a busca do topo.
- **Aviso com Desfazer** em vez de caixa de confirmação para o que é reversível (excluir comando, trocar de automação).
- **Animações de até 150 ms** nas mudanças de estado; nada que atrase o uso.
- **Atalhos nas dicas** dos botões.

## 5. Paridade com o Android

1. **Tokens de design em um arquivo neutro.** Hoje as cores e medidas vêm de `_theme_tokens` e `_build_app_stylesheet` (`core.py`). Extrair para `design/tokens.json` (cores claro e escuro, acento, raios, espaçamentos, tamanhos e pesos de fonte, durações). O desktop lê o JSON para montar a folha de estilo; o Android lê o mesmo JSON (um script gera o tema). Primeiro passo, sem mudar a aparência: extrair e provar com teste que a folha de estilo gerada é idêntica à de hoje.
2. **Mesma arquitetura de informação**: quatro destinos (Automações, Editor, Timeline, Monitor). No desktop, abas na lateral ou no topo; no Android, barra inferior. Mesmos nomes e ícones.
3. **Mesmos componentes, com nomes iguais**: botão principal, secundário e de perigo; chip de estado (sempre ativa, só nesta sessão, desativada); cartão de automação; linha de comando; barra de seleção; menu de contexto; painel lateral (no Android, folha inferior); aviso com Desfazer. Documentar em `md/COMPONENTES.md` (nome, estados, tamanhos, tokens que usa): será o contrato com o Android.
4. **Alvos de toque**: pelo menos 44 px (48 dp no Android) nos botões principais, também no desktop.
5. **Gestos e atalhos**: duplo clique e toque duplo; clique direito e segurar; Ctrl+roda e pinça; Delete e deslizar; Ctrl+Z e o botão desfazer.
6. **O catálogo de funções é o contrato funcional**: cada ID existe nas duas plataformas, com o mesmo nome; a coluna "Android" de `md/FUNCOES_DO_USUARIO.md` acompanha. O que depende do desktop (teclas globais, ganchos de entrada) tem um equivalente definido pela frente de funções (`md/PLANO_FUNCOES.md`, seção 4).
7. **Mesmo vocabulário** nos rótulos: os nomes do catálogo são os nomes oficiais.

## 6. Plano de execução

Um ramo por entrega (`visual/<assunto>`), nesta ordem. Cada uma mexe em poucos arquivos e termina com a suíte completa e o catálogo verdes.

| # | Assunto | Entrega | Critério de pronto |
|---|---|---|---|
| P1 | `visual/limpeza` | Apagar a página do tutorial antigo e o botão "Começar a usar"; `size_toolbar` e `toolbar_hint` (código morto do roadmap) | Catálogo verde; "Começar a usar" sai de `CONTROLES_QUE_NAO_SAO_FUNCOES` |
| P2 | `visual/tokens` | Tokens em JSON gerando a folha de estilo; tarefa V2 (faixa de ativação com tokens) | Teste: folha gerada idêntica à de antes; aparência igual |
| P3 | `visual/barra` | Executar e Parar num botão, Gravar com estados, Mais, Desfazer e Refazer em ícones; tarefa V1 (estado e conflito na lista) | Catálogo atualizado com as telas "executando" e "gravando"; 15 para 8 controles; F10, F11, F12, F17 a F19 conferidos |
| P4 | `visual/lista` | Duplo clique e Enter abrem; importar por soltar arquivo; um botão principal | F01 a F03 com o endereço novo |
| P5 | `visual/navegacao` | Destinos Automações, Editor, Timeline e Monitor no lugar dos "← Voltar" | F05, F13, F14, F27 com o endereço novo |
| P6 | `visual/selecao` | Barra de seleção contextual na tabela e na timeline | F20 a F26 com o endereço novo |
| P7 | `visual/paleta` | Paleta de comandos (Ctrl+K) | Teste: toda função do catálogo aparece na paleta |
| P8 | `visual/desempenho` | V-O1 a V-O4 de `md/DESEMPENHO.md` (pintura da timeline, abrir mapa grande, tema, criar a janela) | Metas da seção 4 do `DESEMPENHO.md` atingidas ou justificadas; `--comparar` na mensagem |
| P9 | `visual/android-base` | `md/COMPONENTES.md` e exportação dos tokens para o Android | Revisado pelo dono |

P1 e P2 vêm primeiro porque não mudam o que o usuário vê. De P3 a P6, uma por vez (todas mexem em `main_window.py`; a integração junta uma de cada vez). P8 pode andar em paralelo com P3 a P6 nos arquivos próprios (`timeline.py`; só o trecho de `refresh` em `command_editor.py`). P9 por último.

## 7. Regras para cada entrega da frente visual

1. **Antes e depois**: capturas (`janela.grab().save("...")`) dos dois temas nas telas lista, editor e timeline, na descrição da entrega.
2. Suíte completa e catálogo de funções verdes. Ao tocar pintura ou tema: `python tests/testsupport/medir_desempenho.py --comparar antes.json` na mensagem do commit.
3. **Nenhum `#hex` solto**: cor nova é token novo.
4. O que muda de lugar atualiza o catálogo e o documento no mesmo commit (seção 1).
5. `main_window.py`: mudanças pequenas e localizadas, dizendo no commit quais trechos mexeu. Os pontos de ligação da ativação (frente de funções) são protegidos por `tests/static/test_ligacao_ativacao.py`.
6. Dúvida de design que envolva retirar algo: pergunte ao dono (seção 8); não decida sozinha.
7. Quando não houver tarefa atribuída, siga o ciclo permanente de `md/DESEMPENHO.md` (seção 7) e a lista de interatividade da seção 4.

## 8. Decisões que dependem do dono

1. Aprovar a simplificação da barra (15 para 8) e o botão único Executar e Parar.
2. Gravar: um botão com estados está bem? (Cancelar passa a ser a tecla Esc.)
3. Paleta de comandos no Ctrl+K.
4. O nome "Ajustes da automação" para a engrenagem da automação (a outra continua "Configurações").
5. **Android: nativo (Kotlin e Compose) ou reaproveitando Python (Kivy, BeeWare)?** Isso define o formato dos tokens e quanto do núcleo (sem Qt) é reaproveitado (`md/PLANO_FUNCOES.md`, seção 4).
