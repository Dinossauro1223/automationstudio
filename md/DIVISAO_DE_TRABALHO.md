# Divisão de trabalho entre as duas frentes

Para o dono do projeto e para quem trabalha na frente visual. Escrito pela frente de funções ao abrir o ramo `funcoes/ativacao-mapas`; **é uma proposta**: o dono muda o que quiser, e o que ficar combinado vale para as duas frentes.

## 1. As duas frentes

| | **Visual** | **Funções** |
|---|---|---|
| Cuida de | Aparência: tema, folha de estilo, hierarquia de botões, as telas da 25.7 | Comportamento: lógica, motor, persistência, atalhos, e os testes |
| Ramos | `visual/...` (hoje `visual/novo-tema`) | `funcoes/...` (hoje `funcoes/ativacao-mapas`) |
| Não mexe em | Regra de automação, gravação, execução, atalho, arquivo de mapa (é a regra do próprio `md/REDESIGN_VISUAL.md`, que está no ramo deles) | Cor, tamanho, layout, tema |

Princípios: **cada frente trabalha no seu ramo**, ninguém escreve no ramo do outro, e **nada vai direto para `main`**: o dono junta tudo por *pull request*, depois de olhar.

## 2. Quem é dono de quê

| Onde | Dono | Regra para o outro |
|---|---|---|
| `core.py`: tema (`_COLOR_*`, `_theme_tokens`, `_APP_QSS`, `_build_app_stylesheet`, `_apply_application_palette`) | Visual | Funções não mexe |
| `core.py`: o resto (modelo, validação, formato dos mapas, `parse_combo`, constantes de execução) | Funções | Visual não mexe; se precisar de algo, pede |
| `ativacao.py`, `controle_ui.py`, `input_system.py`, `project.py`, `conditions.py`, `vision.py` | Funções | Visual não mexe |
| `ativacao_ui.py`: o controlador | Funções | Visual usa o contrato da seção 4 |
| `ativacao_ui.py`: o **desenho** da faixa (`PainelAtivacao`) | Visual | pode restilizar e reposicionar; a lógica fica no controlador |
| `overlays.py`, `timeline.py` (aparência), `command_editor.py` (aparência) | Visual | Funções só toca para lógica, em mudança pequena |
| `main_window.py`, `command_editor.py`, `timeline.py`, `tutorial.py` | **Compartilhado** | Seção 3 |
| `tests/` (a infraestrutura e os testes de função) | Funções | Visual escreve os testes de aparência (`tests/unit/test_tema_visual.py`, no ramo deles) |
| `md/` | Cada um nos seus documentos | `REDESIGN_VISUAL.md` é do visual; `ESPEC_*`, `ENTREGA_*` e este são das funções |

## 3. Arquivos compartilhados: pequenas mudanças, localizadas

`main_window.py` (e, em menor grau, `command_editor.py`, `timeline.py`, `tutorial.py`) recebe mudanças das duas frentes. Para não gerar conflito:

1. **Mudança pequena e no lugar.** Não reformate, não mova blocos, não renomeie o que não é seu. Cada linha trocada é uma chance de conflito.
2. **O que cada frente já tocou em `main_window.py`** (para ninguém pisar):
   - Visual: botão × da barra de comandos, divisor do workspace, "CRIAR NOVA AUTOMAÇÃO", "▶ Executar" e "🛑 Parar tudo" (propriedades e folhas de estilo, em torno das linhas 452, 538, 557 e 577 da versão deles).
   - Funções: o `import` de `ativacao_ui`; em `__init__`, a criação de `self.ativacao` e a chamada `montar_painel`; e os métodos `_reload_map_list`, `_delete_current_map`, `_refresh_map_config_labels`, `_configure_current_map`, `_register_all_hotkeys` e `_on_hotkey_triggered`.
   - Funções (pausar/continuar, ramo `funcoes/pausar-continuar-teclas`): o `import` de `controle_ui`; em `__init__`, a criação de `self.controle` logo depois de `self.ativacao`; e, em `_on_hotkey_triggered`, os ramos `control:pause` e `control:resume`.
3. **Trechos que as duas frentes vão querer** (combinem antes, no comentário do pull request): a construção do editor (`_build_body`, onde está a frase de instrução e a linha de baixo com a tecla, a repetição e a velocidade), `_refresh_map_config_labels` e `_reload_map_list`.
4. **A rede de proteção:** `tests/static/test_ligacao_ativacao.py` confere que as chamadas `self.ativacao.*` continuam nos 7 pontos da janela, e `tests/static/test_ligacao_controle.py` confere que toda tecla de controle registrada tem ramo em `_on_hotkey_triggered` e que F9 e F10 chamam `self.controle.*`. Se um deles falhar depois de uma junção, uma chamada ou um ramo sumiu: devolva-o (a mensagem diz qual). E `tests/unit/test_tema_visual.py` vigia o tema.

**Ensaio feito:** juntei, só para teste e sem tocar em ramo nenhum, `funcoes/ativacao-mapas` com `visual/novo-tema` (na versão `6e42294`): **zero conflitos**, e as duas suítes na árvore juntada dão o mesmo resultado de cada frente sozinha (só as 3 falhas antigas dos `.bat` em clone novo, ver `md/ENTREGA_25_8.md`).

## 4. O contrato da ativação por mapa (o que a frente visual pode usar)

A função de ativação por mapa (25.8) tem três coisas que a interface mostra. A frente visual pode desenhar todas como quiser, desde que respeite isto:

1. **O texto de cada item da lista de automações é o nome do mapa**, e a janela o usa como chave (`_on_map_selected`, `_select_map_by_name`). **Não mude o texto** (por exemplo para "● Nome"): use um desenhista (*delegate*) ou os papéis abaixo.
2. **Cada item carrega o estado e o conflito em papéis de dados:** `PAPEL_ESTADO = 257` (`"sessao"`, `"sempre"` ou `"desativado"`) e `PAPEL_CONFLITO = 258` (texto do conflito de tecla, vazio se não há). A dica do item já traz a situação por extenso.
3. **A faixa "Ativação"** (`PainelAtivacao`, `objectName` `"PainelAtivacao"`; widgets `combo` e `situacao`) é o **único seletor que muda o estado**. Pode restilizá-la pela folha de estilo (`#PainelAtivacao ...`) e mudar margens e posição: para mudar de lugar, passe outra âncora a `self.ativacao.montar_painel(...)` em `MainWindow.__init__` (a âncora tem de estar num layout vertical ou horizontal; se o encaixe falhar, a janela abre sem a faixa e o motivo vai para `logs/AutomationStudio.log`). **Não crie outro seletor com outra lógica**: se precisar de um segundo controle (por exemplo, dentro do painel "Configurações da automação" da 25.7), ele chama `self.ativacao.definir_estado(nome, estado)`, que valida, grava, refaz os atalhos e atualiza a tela.
4. **O que existe para mostrar**, sem o visual precisar saber das regras: `self.ativacao.descrever(nome)` devolve `estado`, `rotulo` ("Ativo nesta sessão"), `tecla`, `funcionando` (a tecla inicia o mapa agora), `conflito`, `situacao` (linha curta) e `resumo` (frase completa). Os textos dos estados e das ajudas estão em `ativacao.ROTULOS` e `ativacao.AJUDAS`.
5. **O rótulo "Tecla para iniciar/parar" do editor** vem de `self.ativacao.rotulo_da_tecla(mapa)` (curto: `=`, `= (desativada)`, `= (em conflito)`, `= (inválida)`). A linha de baixo do editor é estreita; textos longos vão para a faixa.

Do outro lado, o que a frente de funções promete: **nenhuma cor, tamanho ou ícone** vai para o código das funções; tudo o que for desenho passa a ser da frente visual.

## 5. Como trabalhar com o Git (resumo)

- **Nomes:** `visual/<assunto>` e `funcoes/<assunto>`. Todo ramo nasce da `main` atualizada.
- **Pull request pequeno, de um assunto só.** O título começa com "Visual:" ou "Função:"; a descrição diz **o que foi testado e o que não foi**.
- **Antes de abrir o pull request:** traga a `main` para o seu ramo (`git fetch` e `git merge origin/main`) e rode a suíte. Quem junta depois atualiza antes.
- **A ordem de junção não importa** para o código de hoje (ensaiado). Se uma frente mexer em `main_window.py` de um jeito novo, ela diz no pull request.
- **Versão e changelog** (`APP_VERSION`, `md/CHANGELOG_V25.md`): **só o dono mexe, na hora de fechar a versão**. É onde as duas frentes bateriam de frente sem nenhum motivo.
- **O que não se commita:** `logs/` e `__pycache__`. Commite arquivos pelo nome (`git add caminho/do/arquivo`), não com `git add .`.

## 6. Testes: o que cada um roda

- No Windows: `Rodar_Testes.bat`. Em qualquer lugar: `python tests/testsupport/run_minimal.py tests -q` (com `AS_TEST_QT_STUB=widgets` usa o dublê de widgets; sem a variável usa o PySide6 de verdade).
- As catracas (`tests/static`) valem para todos: nenhum `import *` novo, nenhuma função nova sem uso, nenhuma queda de cobertura.
- **Falhas antigas em clone novo:** 3 testes ligados aos arquivos `.bat` acusam "fim de linha LF" porque o repositório guarda LF e o teste quer CRLF. No seu Windows (com `core.autocrlf` ligado) não aparecem. A solução limpa é um `.gitattributes` com `*.bat text eol=crlf` **na `main`**, antes de os ramos serem juntados (um arquivo só, sem risco); proponho que o dono decida.

## 7. Em aberto, para o dono decidir

1. **Quem faz o que na 25.7:** as telas da 25.7 (tutorial novo, sidebar "Configurações da automação", prévias com selo) têm parte de aparência e parte de função. Proposta: a frente visual constrói a tela com os dados de hoje; a frente de funções liga ao comportamento nas versões seguintes, pelo controlador (como foi feito com a ativação).
2. **`.gitattributes`** na `main` (seção 6).
3. **Teste automático no GitHub** (GitHub Actions, no Windows, com Python 3.14 e o PySide6 de verdade): rodaria a suíte inteira a cada pull request, inclusive os testes que hoje só rodam na sua máquina. Posso preparar.
