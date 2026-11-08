# Entrega: desativar e ativar comandos (função F49)

Registro de entrega de uma função da frente de funções (item do `md/PLANO_FUNCOES.md`: desativar um passo sem apagar).

**Onde está:** ramo `funcoes/desativar-comandos`, a partir da `main` atualizada. A `main`, a versão (`APP_VERSION`) e o changelog **não foram tocados**. Nenhum formato de arquivo mudou: o campo `enabled` do comando já existia no arquivo do mapa.

## 1. O que muda para quem usa

- Na tabela de comandos, clique com o botão direito (ou **Mais…**) e escolha **Desativar selecionados**. O comando continua na lista, no mesmo lugar e com o mesmo horário, mas **não é executado**: nem no ▶ Executar, nem no ▶ Testar selecionados, nem na pré-visualização. A Timeline já pintava o comando desativado em cinza.
- Para voltar, selecione e escolha **Ativar selecionados**. É o mesmo item do menu, que troca de nome sozinho: se algum dos selecionados está ativo, ele desativa todos; só quando todos já estão desativados ele ativa.
- Na tabela, a linha desativada fica com o texto apagado e a coluna **Tipo** passa a dizer, por exemplo, "Teclado (desativado)". A dica da linha explica como voltar. A seleção é mantida depois de ativar ou desativar, para dar para desfazer o gesto logo em seguida.
- **Desfazer e Refazer** (Ctrl+Z e Ctrl+Y) cobrem a mudança. O botão passa a dizer "Desfazer: Desativar comandos" (ou "Ativar comandos").
- Copiar, colar, duplicar, exportar e importar comandos levam o estado junto. Mapas salvos antes continuam todos ativos.

## 2. Decisões que você pode querer mudar

1. **Desativar não puxa os outros comandos.** Os horários dos demais continuam os mesmos, então fica um vazio no tempo no lugar do comando desativado. Escolhi assim porque ativar de novo devolve tudo exatamente como estava. Se preferir que os seguintes subam para fechar o vazio, é uma mudança pequena, mas ela muda o que "ativar de novo" significa.
2. **A espera de um comando desativado não segura a execução.** Isso o motor já fazia; agora tem teste (um comando de espera de 0,5 s desativado deixa de atrasar o seguinte).
3. **A validação continua olhando também os desativados.** Se um comando desativado estiver com defeito (uma tecla sem alvo, por exemplo), o aviso de mapa inválido continua aparecendo. Deixei assim para ele já voltar certo quando for ativado. Se preferir que a validação ignore os desativados, é uma linha no modelo, mas aí um comando quebrado só aparece quando for ativado.
4. **Todos os comandos desativados:** o ▶ Executar termina na hora, sem enviar nada e sem erro. Não há aviso.
5. **▶ Testar selecionados** fica cinza quando todos os selecionados estão desativados (não haveria o que testar). Com uma mistura, testa só os ativos.
6. **Só menu, sem atalho de teclado.** Um atalho precisaria de conferência com o Qt de verdade e pode conflitar com o que está em outros ramos. Fica como próximo passo possível.

## 3. O que foi mexido

| Arquivo | Mudança |
|---|---|
| `automationstudio/core.py` | Método novo `AutomationMap.set_commands_enabled` (19 linhas). Nada mais. |
| `automationstudio/command_editor.py` | Só a tabela `CommandTableWidget`: duas funções pequenas no topo (o texto do item de menu e o texto da coluna Tipo), a pintura da linha em `_fill_row`, os itens nos dois menus (clique direito e Mais…) e três métodos novos (`_estados_ligados`, `_set_enabled_ids`, `_select_ids`). |
| `tests/testsupport/funcoes_do_usuario.py` e `md/FUNCOES_DO_USUARIO.md` | Função **F49** no catálogo (o documento foi regenerado). Pulei F47 e F48 de propósito: são do ramo `funcoes/pausar-continuar-teclas`, ainda não juntado. |
| Testes novos | `tests/unit/test_comandos_desativados.py` e `tests/static/test_ligacao_desativar_comandos.py` |

Não toquei em `main_window.py`, no tema, nas cores nem em nada visual além da pintura da própria linha. A cor do texto apagado é a que a paleta do programa já define para o que está desativado.

## 4. Testes

| | Base (`main`) | Esta função |
|---|---|---|
| Dublê de widgets (`rodar_testes.py completo`) | 1651 passam, 77 pulados, 6 xfail | **1687** passam, 77 pulados, 6 xfail |

- **36 testes novos.** Modelo: muda só o pedido, não mexe em horário nem em ordem, devolve só o que mudou. Motor: pula o desativado, a espera dele não segura, todos desativados termina sem erro. Desfazer e refazer, salvar e abrir, copiar, colar, duplicar, exportar e importar levam o estado. A tabela: ordem das chamadas, rótulo do histórico, nada registrado quando nada mudou, e a pintura da linha (inclusive o # de um grupo, que mantém a cor do grupo). Ligação dos menus ao código, conferida no código-fonte.
- **Defeitos plantados à mão** (12 no código novo e 7 na ligação dos menus), um de cada vez: **todos foram pegos** por algum teste novo. Isso foi uma conferência minha, com um script fora do repositório; não entrou no catálogo de mutações do projeto.
- No modo só de lógica (`AS_TEST_QT_STUB=1`) a suíte inteira roda sem falhas: 1460 passam, 304 pulados (os testes de janela) e 6 xfail. Não medi esse modo na `main`, então aqui não há comparação.

## 5. O que NÃO foi conferido

- **Nada com o Qt de verdade nem com o Windows.** Esta sessão não tem PySide6 e não consegue instalar. Os testes rodaram com o dublê de widgets e com o de lógica. O dublê não consegue montar a tabela de comandos, então os métodos da tabela foram testados chamando-os com um `self` de mentira (a regra roda, a janela não).
- O que só o Qt real mostra: **a aparência da linha cinza**, os dois menus abrindo com o item certo, e a **seleção mantida** depois de ativar ou desativar (o método segue o mesmo jeito da seleção por Shift, que já existe, mas não rodou). Um detalhe provável: pelo estilo da tabela, uma linha **selecionada** pode mostrar o texto na cor normal em vez de apagado. Por isso o "(desativado)" também está escrito na coluna Tipo, para o estado não depender só da cor.
- Os testes de janela real (`tests/gui`) não rodaram.
- O GitHub Actions não foi disparado (esta sessão não tem como). Dá para rodar o fluxo **Tests** à mão (workflow_dispatch) no ramo.

## 6. Conferência rápida no Windows (uns 2 minutos)

| # | Faça | Deve acontecer |
|---|---|---|
| 1 | Abra uma automação com uns 4 comandos. Clique com o botão direito num deles e escolha **Desativar selecionados** | A linha fica com o texto apagado, a coluna Tipo diz "(desativado)" e a linha continua selecionada. Na Timeline o comando aparece em cinza |
| 2 | Aperte ▶ Executar | O comando desativado não age; os outros agem nos mesmos horários de antes (com o vazio no lugar dele) |
| 3 | Clique com o botão direito no mesmo comando | O item agora diz **Ativar selecionados**. Escolha: a linha volta ao normal |
| 4 | Aperte Ctrl+Z e depois Ctrl+Y | Desfaz (volta a desativado) e refaz. O botão mostra "Desfazer: Desativar comandos" |
| 5 | Selecione dois comandos, um ativo e um desativado, e clique com o botão direito | O item diz **Desativar selecionados** (os dois ficam desativados) |
| 6 | Selecione só um comando desativado e abra **Mais…** | **▶ Testar selecionados** está cinza |
| 7 | Feche e abra o programa | O comando continua desativado |

Se algo não bater, o mais útil é `logs\AutomationStudio.log` e a descrição do que você viu.
