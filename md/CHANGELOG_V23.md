# Automation Studio — V23

A V23 foi desenvolvida em revisões pequenas para evitar acumular alterações estruturais em uma única entrega. O objetivo é fechar Editor, Timeline, histórico e motor temporal antes de avançar para condições e visão computacional.

## 23.10 — consolidação final da V23
- Editor e Timeline usam o mesmo `AutomationMap` como fonte de verdade.
- Operações de copiar, recortar, colar, duplicar, excluir e inserir foram mantidas centralizadas no modelo.
- Histórico mantém rótulos das transações e permite consultar profundidade de Undo/Redo.
- Motor temporal expõe linhas calculadas para a pré-visualização e usa duração calculada para texto.
- Timeline recebeu playhead por clique na régua, snap opcional e indicador de duração total.
- Editor recebeu menu “Mais…” com clipboard, importação/exportação `.ascommands`, validação, teste de selecionados e pré-visualização.
- Validação estrutural verifica IDs, tipos, ações, tempos e grupos.
- Teste de comandos selecionados usa um mapa temporário e não altera o mapa persistido.
- Pré-visualização não envia teclado ou mouse.

## 23.2 — seleção e edição unificadas
- Operações de seleção e edição passaram a usar IDs estáveis do modelo.
- Adição, duplicação e exclusão foram mantidas independentes da ordenação visual.

## 23.3 — reordenação robusta
- Reordenação vertical preserva ordem relativa e reconstrói os horários em cascata.
- O feedback de inserção permanece visual até a confirmação do release.

## 23.4 — histórico transacional
- Undo/Redo passou a registrar operações por rótulo.
- O orçamento de RAM dos snapshots continua configurável.

## 23.5 — motor temporal
- `reflow_timeline()` tornou explícita a relação entre duração, intervalo e início calculado.
- Inserção, movimentação, exclusão e duplicação usam o mesmo modelo temporal.

## 23.6 — Timeline 2.0
- Zoom, ajuste à área, playhead, seleção por faixa e edição temporal foram consolidados.
- Snap temporal tornou-se opcional.

## 23.7 — teste de comandos
- Inclusão de teste isolado para comandos selecionados.

## 23.8 — pré-visualização
- Inclusão de pré-visualização textual da sequência e da duração total sem input real.

## 23.9 — troca de blocos de comandos
- Clipboard interno e formato `.ascommands` permitem transportar trechos de automação com offsets relativos preservados.

## 23.1 — correção de import no editor
- Corrigido `QAbstractButton` ausente nos imports de `command_editor.py`.

## 23.0 — base inicial
- Início da etapa principal V23 sobre a base auditada 22.64.
