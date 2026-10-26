# Automation Studio — Histórico da V22

Documento consolidado dos registros de mudanças presentes na base 22.63 auditada.

## 22.5

# AS 22.5

## Correção
- Corrigido o erro de inicialização na aplicação do tema causado por `QColor`/string: `_resolve_theme_mode()` já retorna a cor do accent como string, portanto o código não deve chamar `.name()` nesse valor.
- Mantidos os ajustes de UX da AS 22.4.

---

## 22.12

# AS 22.12

## Objetivo
Correção da regressão visual introduzida na 22.11 e compactação do layout, usando a AS 22.10 como base.

## Interface
- Descartada a estrutura de distribuição vertical que criava grandes áreas vazias.
- Cabeçalho e faixa rolável superior ficaram mais compactos.
- A área do editor continua usando o espaço vertical disponível.
- Tabela de comandos recebe política de expansão para ocupar a área restante.
- Margens e espaçamentos do editor e da seleção de automações foram reduzidos sem usar posicionamento absoluto.
- A identidade AS permanece integrada ao topo.

## Correção de regressão
- `QGroupBox` passou a ser importado explicitamente no editor de comandos, evitando o `NameError` observado ao abrir Configurações.
- Não foi incorporada a chamada inexistente `_update_table_content_height`, evitando a regressão da 22.11.

## Regra de UX
O conteúdo deve começar próximo ao topo, ocupar naturalmente o espaço útil e nunca criar espaços verticais artificiais para centralizar componentes.

---

## 22.13

# AS 22.13

## UX — reorganização das configurações

- A primeira aba de configurações passa a se chamar **Aparência**.
- Cores do programa, teclado virtual e mouse virtual ficam organizadas por tema em dois grupos: **Modo escuro** e **Modo claro**.
- O teclado e mouse virtuais deixam de misturar cores e comportamento na mesma seção.
- A aba **Teclado e mouse virtuais** passa a concentrar apenas modo de teclado, tempos, opacidade e comportamento de exibição.
- Mantido o seletor de cores clicável com paleta nativa.
- Explicações continuam disponíveis por tooltip, sem ocupar espaço permanente.

---

## 22.14

# AS 22.15

## Seleção por área — padrão Windows

- Implementada seleção múltipla por retângulo na tabela principal de comandos.
- O retângulo de seleção aparece em tempo real enquanto o botão esquerdo permanece pressionado.
- A seleção é atualizada em tempo real conforme o retângulo atravessa as linhas.
- A seleção passa a ser tratada por linha, facilitando ações em vários comandos simultaneamente.
- A coluna `#` continua reservada ao gesto de reordenação para evitar conflito entre seleção e arraste.
- Implementada seleção por área também na Timeline.
- Na Timeline, o gesto começa em uma área vazia e pode atravessar várias linhas/comandos.
- A seleção visual utiliza azul no tema claro e amarelo no tema escuro, respeitando o padrão visual definido para o Automation Studio.
- O comportamento existente de mover, redimensionar e reordenar comandos da Timeline foi preservado.

## Validação

- Compilação de todos os módulos Python: OK.
- Análise sintática dos módulos: OK.

---

## 22.15

# AS 22.15

## Correção — seleção por área

- Corrigido o conflito de duas definições de `eventFilter` no `CommandTableWidget` que fazia o filtro de mouse da seleção por área ser sobrescrito pelo filtro de teclado.
- A tabela agora mantém um único `eventFilter` responsável por teclado e seleção por área.
- O viewport da tabela recebe mouse tracking para atualizar o retângulo durante o arraste.
- A seleção por área passa a selecionar linhas inteiras.
- O retângulo visual continua usando azul no tema claro e amarelo no tema escuro.
- `Ctrl`/seleção existente e a alça de reordenação da coluna `#` permanecem preservados.

## Validação

- Compilação dos módulos Python concluída sem erros.
- Nenhuma segunda definição de `eventFilter` permanece em `CommandTableWidget`.

---

## 22.16

# AS 22.16

## Correção — seleção por área visível

- Corrigido o defeito em que o retângulo de seleção era criado e exibido, mas permanecia sem pintura porque o estado interno do `SelectionRubberBand` não era atualizado quando `setGeometry()` era chamado diretamente.
- A camada visual agora desenha o próprio `rect()` local do widget, tornando a renderização independente da forma como a geometria foi atualizada.
- A tabela principal e a Timeline passam a usar `set_rect()` durante todo o gesto de seleção.
- A seleção das linhas continua sendo atualizada em tempo real enquanto o botão esquerdo permanece pressionado.
- Mantida a cor azul no tema claro e a cor de destaque do tema escuro conforme o sistema visual existente.
- Removida a mensagem permanente de ajuda da tabela principal (`Arraste pelo número...`), deixando a área de trabalho limpa.
- O arraste pelo número `#` para reordenar e o arraste sobre as barras da Timeline para mover/redimensionar/reordenar continuam preservados.

## Validação interna

- Verificação de sintaxe de todos os módulos Python.
- Verificação de que `SelectionRubberBand.set_rect()` é utilizado nos caminhos de seleção da tabela e da Timeline.
- Verificação de que a mensagem permanente de seleção não permanece configurada na tabela.
- Verificação de ausência de `eventFilter` duplicado no `CommandTableWidget`.


## FIX 16 — seleção, reordenação e inserção contextual

- Corrigido o conflito entre a caixa de seleção por área e o comportamento nativo da tabela: clicar sobre uma linha volta a selecionar normalmente.
- O arraste de uma linha da tabela fica reservado à reordenação, permitindo pressionar e arrastar o próprio comando para alterar sua posição na execução.
- A reordenação da tabela e da Timeline agora utiliza uma regra central no `AutomationMap`, preservando a ordem relativa de múltiplos comandos selecionados.
- Corrigida a movimentação pelos botões **Subir** e **Descer** para usar a mesma regra central.
- **Adicionar comando** agora insere o novo comando imediatamente abaixo da última linha selecionada.
- Sem seleção, **Adicionar comando** continua inserindo no final da automação.
- Ao inserir no meio da automação, o campo de início recebe como sugestão o término do comando anterior.
- A caixa de seleção continua visual e transparente aos eventos do mouse.


## FIX complementar — seleção, inserção e sidebar

- Corrigida a seleção por área na tabela: o retângulo agora altera efetivamente as linhas selecionadas, não apenas a representação visual.
- Reordenação de comandos pelo arraste da própria linha, preservando a seleção múltipla e a ordem relativa.
- Adição de comando passa a inserir abaixo da seleção atual; sem seleção, adiciona ao final.
- Corrigida a persistência da largura da sidebar para impedir que o fechamento grave `0 px` ou uma largura intermediária como a última largura do usuário.
- Restauração da sidebar prioriza a última largura válida escolhida manualmente.
- Formulários da sidebar usam quebra responsiva de linhas; rótulos e campos passam para linhas distintas quando a largura disponível é insuficiente.
- Aba Mapas ajustada para impedir sobreposição entre a explicação e o campo da pasta.

---

## 22.17

# AS 22.17

## FIX 17 — seleção real, tutorial global e UX responsiva

### Seleção por arraste
- A caixa de seleção só aparece durante um gesto ativo com o botão esquerdo pressionado.
- A faixa é ocultada e o estado do gesto é zerado após cada clique/soltura.
- O movimento do mouse sem botão esquerdo não inicia nem reaproveita uma seleção anterior.
- O retângulo seleciona comandos inteiros, independentemente da coluna em que o arraste começou (inclusive Tecla / botão).
- Arraste vertical iniciado sobre uma linha já selecionada continua reservado à reordenação.

### Inserção de comandos
- A última seleção válida permanece registrada mesmo quando o foco vai para o botão “Adicionar comando”.
- Com uma seleção, o novo comando é inserido imediatamente abaixo da última linha selecionada.
- Sem seleção, o comando continua sendo adicionado ao final.

### Tutorial
- “Pular tutorial” agora informa ao coordenador se o encerramento veio do botão de pular.
- Em uma jornada de primeiro uso, pular encerra todas as etapas futuras, inclusive os tutoriais dedicados de outras páginas.
- O estado de onboarding é marcado como concluído sem iniciar a demonstração automaticamente.
- Tutoriais contextuais dedicados continuam independentes quando o programa já não está na jornada inicial.

### Sidebar
- A largura manual passa a ter uma chave persistente própria (`sidebar_last_manual_width`), separada dos estados transitórios de abertura/fechamento.
- O fechamento da sidebar nunca transforma a largura lembrada em zero.

### Verificação
- `python -m py_compile automationstudio/*.py`
- `python -m pytest -q tests/test_readiness.py` → 2 testes aprovados.

---

## 22.18

# AS 22.18 — FIX 18

## Seleção por área
- Seleção real por área aplicada à linha inteira, mesmo quando o arraste começa em qualquer coluna.
- A área visual de seleção permanece transparente aos eventos do mouse.
- A seleção é atualizada em tempo real e consolidada ao soltar o botão esquerdo.

## Sidebar responsiva
- Em larguras estreitas, os formulários passam para `WrapAllRows`: explicação/rótulo fica acima do campo.
- O conteúdo abaixo é empurrado naturalmente, eliminando sobreposição em campos de configurações e no editor de comandos.
- A mesma regra vale para formulários internos e seções avançadas.

---

## 22.19

# Automation Studio — V22.19 (FIX 19)

## Correção da seleção por área no Main

- Corrigido o erro `AttributeError: 'QItemSelection' object has no attribute 'topLeft'` durante a seleção múltipla.
- A seleção por área continua selecionando linhas inteiras, independentemente da coluna em que o arraste começou.
- A célula inicial usada para posicionar a seleção agora é obtida diretamente da linha selecionada, sem depender de métodos inexistentes em `QItemSelection`.
- Mantidas as regras de reordenação e inserção contextual da V22.

---

## 22.20

# Automation Studio — V22.20 (FIX 20)

## Corrigido

- Seleção por retângulo da tela Main agora seleciona todas as linhas que intersectam a área, independentemente da coluna onde o arraste começou.
- O gesto de seleção impede que o QTableWidget execute simultaneamente seu drag nativo, evitando que apenas a linha sob o cursor permaneça selecionada.
- Clique simples, Ctrl+clique e Shift+clique continuam selecionando linhas completas.
- Mantida a reordenação ao arrastar uma linha já selecionada verticalmente.

## Validação

- Compilação dos módulos Python realizada com sucesso.

---

## 22.21

# Automation Studio — V22.21 (FIX 21)

## Timeline
- Seleção múltipla preservada ao clicar/arrastar qualquer comando já selecionado.
- Arraste horizontal move todos os comandos selecionados juntos no tempo.
- Duplo clique e edição/add na Timeline usam sidebar interna, sem popup modal.
- Adicionados atalhos Ctrl+A, Ctrl+C, Ctrl+X, Ctrl+V, Ctrl+Z, Ctrl+Y e Delete na Timeline.

## Editor principal
- Ctrl+A e Ctrl+X adicionados ao editor de comandos.
- Colar agora respeita a posição da seleção, inserindo após o último comando selecionado.
- Ctrl+Z/Ctrl+Y delegam ao histórico central.

## Navegação
- A seleção feita na Timeline é sincronizada com a tabela principal para que as ações de edição reutilizem o mesmo núcleo.

---

## 22.22

# Automation Studio — V22.22 (FIX 22)

## Seleção e reordenação do editor

- Clique simples só confirma a seleção ao soltar o botão esquerdo.
- Quando já existe uma linha/célula selecionada, arrastar a partir dessa linha não inicia a caixa de seleção: o gesto passa a reordenar a seleção existente.
- Quando não existe nenhuma seleção, manter o botão esquerdo pressionado por 450 ms ativa a seleção por área a partir do ponto inicial.
- Movimento rápido sem seleção também pode iniciar a seleção por área.
- O retângulo de seleção continua selecionando linhas inteiras por interseção vertical.
- A caixa de seleção e a reordenação deixam de disputar o mesmo gesto.

---

## 22.55

# AS 22.55 — FIX 55

## Arraste do editor
- Reordenação manual permanece responsiva e atualiza a posição visual em tempo real.
- Cálculo do slot ignora as linhas em movimento e usa a geometria das linhas restantes.
- O espaço abaixo do último comando representa explicitamente o último slot.
- Autoscroll em 10%/5% da área permanece ativo durante o arraste.
- Reutilização dos QTableWidgetItems com atualizações bloqueadas durante cada troca para reduzir custo visual.
- O modelo real só é confirmado no release.

---

## 22.56

# AS 22.56 — FIX 56

- Reordenação visual do editor por trocas adjacentes de linhas, evitando reconstrução de linhas durante o arraste.
- Mantido o arraste manual e o autoscroll existentes.
- Seleção preservada por ID durante o movimento.
- Versão atualizada para 22.56.

---

## 22.57

# AS 22.57 — FIX 57

## Reordenação do editor
- acompanhamento contínuo por timer de 16 ms durante o arraste;
- garante atualização mesmo quando o mouse permanece em áreas sem células;
- autoscroll e reposicionamento visual usam o mesmo ciclo;
- mantém o arraste manual fora do QDrag nativo.

## Estabilidade
- versão interna atualizada para 22.57.

---

## 22.58

# AS 22.58 — FIX 58

## Arraste: identidade visual acompanha a linha

- Corrigida a identificação da linha em arraste: usa o ID persistente armazenado na própria célula, não o índice do modelo original.
- A cor de arraste agora acompanha o comando para a nova posição visual.
- A cor do grupo continua vinculada à linha/célula e acompanha o comando durante a reordenação.
- Não altera o modelo durante o movimento; a confirmação continua no soltamento.

---

## 22.61

# AS 22.63 — FIX 62

## Tempo de início após reordenação

Ao mover comandos no editor, o horário de início não permanece mais preso ao valor absoluto da posição antiga.

A regra agora é preservar o intervalo temporal de cada comando em relação ao comando anterior:

`intervalo = início do comando - término efetivo do anterior`

Depois da reordenação, os comandos são recalculados na nova ordem usando esse mesmo intervalo. Isso mantém a distância antes de cada comando e faz com que os comandos afetados depois do ponto de inserção também acompanhem corretamente a nova sequência.

Para um bloco selecionado, os intervalos internos são preservados, mantendo o ritmo temporal do bloco durante a movimentação.

---



## 22.64

### FIX 64 — seleção por intervalo e commit exato da posição ao soltar
- Shift+clique no editor usa a âncora pelo ID do comando e seleciona explicitamente todo o intervalo de linhas.
- O término do arraste aplica a ordem visual completa diretamente ao modelo, eliminando a conversão por índice que causava o retorno de uma linha.
- O recálculo temporal é aplicado após a ordem visual definitiva, preservando os intervalos de cada comando.
