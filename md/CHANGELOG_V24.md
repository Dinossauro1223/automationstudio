# Changelog V24

## 24.0 — fundação de condições e sincronização

- Nova camada independente `automationstudio.conditions`.
- Introduzido `WaitCondition` para representar condições de sincronização em um único modelo, separado da UI.
- Tipos iniciais: `PROCESS`, `DELAY` e `NONE`.
- Validação e serialização/deserialização preparadas para expansão futura.
- Mantida a compatibilidade com os campos legados de espera da V23.

Esta versão é a primeira etapa estrutural da V24. A implementação de novas condições e a integração visual serão evoluídas incrementalmente nas revisões seguintes.


## 24.1 — condições integradas ao modelo

- `Command` agora possui uma lista de `WaitCondition` serializável.
- Condições são anexadas ao primeiro evento do comando, evitando execução duplicada em comandos com duração.
- `PROCESS` e `DELAY` já podem ser executados pelo motor sem depender da UI.
- Validação e round-trip de condições foram adicionados aos testes.
- Mantida a compatibilidade com os campos legados de espera por processo.


## 24.2 — editor de condições

- A caixa de diálogo de comandos ganhou a seção “Condições antes desta ação”.
- Usuário pode cadastrar e remover condições `PROCESS` e `DELAY`.
- Condições são persistidas no comando e reaparecem ao editar.
- A seção deixa claro que a espera em tempo real é uma barreira de execução e não altera silenciosamente a Timeline.


## 24.3 — comando Esperar

- Adicionado `InputType.WAIT` e `EventKind.WAIT`.
- “Esperar” passa a ser um comando independente, podendo carregar uma ou mais condições.
- O executor processa as condições sem produzir input de teclado ou mouse.
- O editor ganhou o tipo “⏳ Esperar” e exige ao menos uma condição antes de salvar.


## 24.4 — edição e apresentação de condições

- Condições cadastradas podem ser editadas diretamente na caixa de diálogo.
- O tipo “Esperar” passa a aparecer corretamente nas listas/descrições da interface.
- Adicionada validação de fallback para tipos de condição desconhecidos, preservando compatibilidade futura.


## 24.4 — estabilização da etapa de condições

- Consolidação do núcleo `WaitCondition` com suporte a processo e atraso temporizado.
- Condições anexadas ao primeiro evento de um comando, sem duplicação em ações que geram múltiplos eventos.
- Novo comando independente “Esperar”.
- Edição, remoção, persistência e validação das condições no editor.
- Interrupção pelo usuário permanece tratada como encerramento normal também durante barreiras de prontidão.
- V24 permanece deliberadamente sem OCR, captura/comparação de imagem e condicionais `SE/SENÃO` complexas, reservados para etapas posteriores.
