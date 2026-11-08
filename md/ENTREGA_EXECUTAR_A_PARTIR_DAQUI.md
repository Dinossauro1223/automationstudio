# Entrega: executar a partir daqui (função F50)

Registro de entrega de uma função da frente de funções (item do `md/PLANO_FUNCOES.md`: testar e consertar uma macro sem rodar tudo de novo).

**Onde está:** ramo `funcoes/executar-a-partir-daqui`, a partir da `main` atualizada. A `main`, a versão (`APP_VERSION`) e o changelog **não foram tocados**. O ramo **não depende** de nenhum outro: nem do `funcoes/desativar-comandos` (F49), nem dos ramos da pausa. Dá para juntar em qualquer ordem.

## 1. O que muda para quem usa

- Na tabela de comandos, clique com o botão direito num comando e escolha **▶ Executar a partir daqui** (o item também está em **Mais…**). O programa roda os comandos **dali até o fim da lista**, sem rodar o começo de novo e **sem esperar o tempo que havia antes** do comando clicado: o primeiro roda na hora, e os seguintes mantêm os mesmos intervalos de antes.
- Com vários comandos selecionados, vale o **de cima** da tabela.
- Comandos **desativados** são pulados. Se não sobra nenhum comando ativo dali para baixo, o item fica cinza.
- O mapa aberto **não é alterado** e nada entra no desfazer: o programa monta uma cópia isolada só para esse teste.

## 2. Decisões que você pode querer mudar

1. **"Daqui" segue a ordem da lista, não a do horário.** A lista é a sequência do mapa (é assim que o programa remonta os tempos). Num mapa em que um comando de baixo tem horário menor que o de cima, ele entra mesmo assim.
2. **Roda como o "Testar selecionados" que já existe:** uma passada só (a repetição do mapa não vale), na velocidade do mapa, começando na hora. Não passa pelo botão ▶ Executar. Reaproveitei esse caminho de propósito: não mexi na janela principal e a função herda as mesmas regras e avisos (por exemplo, "Pare a automação em execução antes de testar uma seleção").
3. **A barra de status diz "Testando N comando(s) selecionado(s)."** Esse é o texto do teste que já existia, e os comandos de "daqui" não foram selecionados na tabela. O N conta só o que vai rodar (sem os desativados). Preferi não mexer na janela principal só por causa do texto.
4. **Não seleciono as linhas na tabela** ao executar. Dá para fazer, mas é mais código de interface que eu não consigo conferir aqui.
5. **Só a tabela de comandos** (clique direito e Mais…). A Timeline desenhada não ganhou o item.
6. **O "Testar selecionados" continua só no Mais…** (não está no clique direito). Não mudei isso; se quiser, é uma linha.

## 3. O que foi mexido

| Arquivo | Mudança |
|---|---|
| `automationstudio/command_editor.py` | Só a tabela: uma função pequena antes de `CommandTableWidget` (`_ids_a_partir_daqui`, a regra de quais comandos entram) e um item em cada menu (clique direito e Mais…). |
| `tests/testsupport/funcoes_do_usuario.py` e `md/FUNCOES_DO_USUARIO.md` | Função **F50** no catálogo (o documento foi regenerado). Pus a linha antes da F26 para não bater com a linha da F49 numa junção. |
| Testes novos | `tests/unit/test_executar_a_partir_daqui.py` e `tests/static/test_ligacao_executar_a_partir_daqui.py` |

Não toquei em `main_window.py`, `core.py`, no tema nem nas cores.

## 4. Testes

| | Base (`main`) | Esta função |
|---|---|---|
| Dublê de widgets (`rodar_testes.py completo`) | 1651 passam, 77 pulados, 6 xfail | **1671** passam, 77 pulados, 6 xfail |
| Dublê de lógica (`AS_TEST_QT_STUB=1`) | não medi | 1444 passam, 304 pulados, 6 xfail |

- **20 testes novos.** A regra de quais comandos entram (do primeiro escolhido até o fim, pulando os desativados, na ordem da lista). **De ponta a ponta**, com o método real da janela principal chamado com um `self` de mentira e o motor de verdade com relógio virtual: o que roda é exatamente o que a execução normal rodaria dali em diante, com os mesmos intervalos, começando na hora; o mapa aberto não é mexido; a repetição e a velocidade do teste são as esperadas. E a ligação dos dois menus ao código, conferida no código-fonte, inclusive a linha da janela principal que liga o teste ao sinal da tabela.
- **Ensaio de junção** (só no meu clone, depois descartado): juntei este ramo com o `funcoes/desativar-comandos` (F49). **Sem conflitos**, e a suíte inteira passou com as duas funções juntas: 1707 passam, 77 pulados, 6 xfail no dublê de widgets, e 1480 passam no de lógica. Os menus ficam com os dois itens, cada um com a sua variável, sem se atropelar.
- **O caminho do "Testar selecionados" não tinha nenhum teste.** Agora tem (o horário que começa em zero, uma passada, a velocidade do mapa, as cópias).
- **Defeitos plantados à mão** (15), um de cada vez: **todos foram pegos** por algum teste novo. 10 estavam no código novo (regra e menus) e 5 no teste que já existia na janela principal. Foi uma conferência minha, com um script fora do repositório; não entrou no catálogo de mutações do projeto.

## 5. O que NÃO foi conferido

- **Nada com o Qt de verdade nem com o Windows.** Esta sessão não tem PySide6 e não consegue instalar. Os testes rodaram com o dublê de widgets e com o de lógica, e o motor rodou com teclado e relógio de mentira. O que só o Qt real mostra: os **dois menus abrindo com o item** e o **teste rodando de verdade numa janela**.
- Os testes de janela real (`tests/gui`) não rodaram.
- O GitHub Actions não foi disparado (esta sessão não tem como). Dá para rodar o fluxo **Tests** à mão (workflow_dispatch) no ramo.

## 6. Conferência rápida no Windows (uns 2 minutos)

| # | Faça | Deve acontecer |
|---|---|---|
| 1 | Abra uma automação com uns 5 comandos em tempos diferentes. Clique com o botão direito no 3º e escolha **▶ Executar a partir daqui** | O 3º roda **na hora** (sem esperar o tempo que tinha antes) e depois o 4º e o 5º, com os mesmos intervalos. A barra de status diz "Testando 3 comando(s) selecionado(s)." |
| 2 | Faça o mesmo no último comando | Roda só ele |
| 3 | Selecione o 2º e o 4º (Ctrl + clique), abra **Mais…** e escolha **▶ Executar a partir daqui** | Roda do 2º até o fim |
| 4 | Com uma automação em execução, escolha o item | Aparece o aviso "Pare a automação em execução antes de testar uma seleção." |
| 5 | Depois de qualquer um dos testes, olhe o botão Desfazer | Não mudou: nada foi alterado no mapa |

O item cinza (todos os comandos de "daqui" desativados) só dá para ver num mapa com comandos desativados, o que a função F49 (`funcoes/desativar-comandos`) permite pela tabela.

Se algo não bater, o mais útil é `logs\AutomationStudio.log` e a descrição do que você viu.
