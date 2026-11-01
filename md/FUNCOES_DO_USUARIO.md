# Funções do usuário

Gerado de `tests/testsupport/funcoes_do_usuario.py`; não edite aqui. Para regenerar: `python tests/testsupport/funcoes_do_usuario.py > md/FUNCOES_DO_USUARIO.md`.

Este é o catálogo do que o programa faz. O **ID não muda** (nem quando o botão muda de lugar ou de nome) e é o mesmo no app Android: cada função daqui precisa existir lá, com o mesmo nome. `tests/gui/test_funcoes_acessiveis.py` abre a janela e confere que toda função tem pelo menos um endereço; quem muda um controle muda a linha da função no mesmo commit (regras em `md/PLANO_VISUAL.md`).

## Automações

| ID | Função | Onde está hoje | Atalho | Android |
|---|---|---|---|---|
| F01 | Criar uma automação nova | Barra (em todas as telas): ＋ Nova automação<br>Botão (tela da lista): ＋ CRIAR NOVA AUTOMAÇÃO | — | a definir |
| F02 | Abrir ou importar um mapa externo (.json ou banco) | Botão (tela da lista): 📂 ABRIR / IMPORTAR MAPA EXTERNO | — | a definir |
| F03 | Abrir a automação selecionada no editor | Botão (tela da lista): ABRIR AUTOMAÇÃO SELECIONADA | — | a definir |
| F04 | Salvar a automação | Barra (em todas as telas): 💾 Salvar | — | a definir |
| F05 | Escolher outra automação (voltar à lista) | Botão (tela do editor): ← Escolher outra automação | — | a definir |
| F06 | Ajustar a automação (nome, tecla, repetição, velocidade) | Botão (tela do editor): ⚙ Configurações da automação | — | a definir |
| F07 | Desfazer a última alteração | Barra (em todas as telas): ↶ Desfazer | Ctrl+Z | a definir |
| F08 | Refazer a alteração desfeita | Barra (em todas as telas): ↷ Refazer | Ctrl+Y | a definir |
| F09 | Escolher como a automação é ativada (sempre ativa, só nesta sessão, desativada) | Painel (tela do editor): PainelAtivacao | — | a definir |

## Execução

| ID | Função | Onde está hoje | Atalho | Android |
|---|---|---|---|---|
| F10 | Executar a automação | Barra (em todas as telas): ▶ Executar | — | a definir |
| F11 | Parar a execução | Barra (em todas as telas): ■ Parar | — | a definir |
| F12 | Parar tudo (emergência) | Barra (em todas as telas): 🛑 Parar tudo | tecla de parada | a definir |
| F13 | Ver o monitor de execução | Barra (em todas as telas): ▣ Monitor de execução | — | a definir |
| F14 | Voltar ao editor (da timeline ou do monitor) | Botão (tela da timeline): ← Voltar ao editor | — | a definir |
| F15 | Parar tudo pela tecla, mesmo que um mapa use a mesma tecla | Tecla (teste: test_a_parada_de_emergencia_continua_com_a_tecla_mesmo_que_um_mapa_use_a_mesma) | tecla de parada | a definir |
| F16 | Executar uma automação pela tecla dela (só se estiver ativa) | Tecla (teste: test_mapa_desativado_nao_executa_pela_tecla_mas_o_botao_executar_continua_funcionando) | tecla do mapa | a definir |

## Gravação

| ID | Função | Onde está hoje | Atalho | Android |
|---|---|---|---|---|
| F17 | Iniciar a gravação | Barra (em todas as telas): ● Iniciar gravação | tecla de gravação | a definir |
| F18 | Cancelar a gravação | Barra (em todas as telas): ✕ Cancelar gravação | — | a definir |
| F19 | Pré-visualizar a gravação | Barra (em todas as telas): ▶ Pré-visualizar gravação | — | a definir |

## Comandos

| ID | Função | Onde está hoje | Atalho | Android |
|---|---|---|---|---|
| F20 | Adicionar um comando | Botão (tela do editor): ＋ ADICIONAR COMANDO<br>Botão (tela da timeline): ＋ Adicionar comando | — | a definir |
| F21 | Editar um comando | Botão (tela do editor): Editar comando | — | a definir |
| F22 | Excluir os comandos selecionados | Botão (tela do editor): Excluir selecionados | Delete | a definir |
| F23 | Mover um comando para cima | Botão (tela do editor): ▲ Subir | — | a definir |
| F24 | Mover um comando para baixo | Botão (tela do editor): ▼ Descer | — | a definir |
| F25 | Agrupar comandos e gerenciar grupos | Botão (tela do editor): ● Grupos | — | a definir |
| F26 | Outras ações sobre os comandos (menu "Mais…") | Botão (tela do editor): Mais… | — | a definir |

## Timeline

| ID | Função | Onde está hoje | Atalho | Android |
|---|---|---|---|---|
| F27 | Abrir a timeline da automação | Botão (tela do editor): ▣ Abrir Timeline | — | a definir |
| F28 | Ver a timeline no modo simples | Botão (tela da timeline): Simples | — | a definir |
| F46 | Ver a timeline no modo avançado | Botão (tela da timeline): Avançada | — | a definir |
| F29 | Ajustar a timeline à janela | Botão (tela da timeline): Ajustar | — | a definir |
| F44 | Aproximar a timeline (zoom +) | Botão (tela da timeline): + | — | a definir |
| F45 | Afastar a timeline (zoom −) | Botão (tela da timeline): − | — | a definir |
| F30 | Ligar ou desligar o encaixe (Snap) | Botão (tela da timeline): Snap | — | a definir |
| F31 | Editar as linhas mescladas | Menu ou diálogo (timeline.py): ✎ Editar linhas mescladas | — | a definir |
| F32 | Criar um grupo pela timeline | Menu ou diálogo (timeline.py): ＋ Criar novo grupo | — | a definir |

## Programa

| ID | Função | Onde está hoje | Atalho | Android |
|---|---|---|---|---|
| F33 | Abrir as configurações do programa | Barra (em todas as telas): ⚙ Configurações | — | a definir |
| F34 | Abrir o tutorial | Barra (em todas as telas): ❔ Tutorial | — | a definir |
| F35 | Mostrar ou ocultar o teclado virtual | Barra (em todas as telas): ⌨ Mostrar teclado | — | a definir |
| F36 | Mostrar ou ocultar o mouse virtual | Barra (em todas as telas): 🖱 Mostrar mouse | — | a definir |

## Configurações do programa

| ID | Função | Onde está hoje | Atalho | Android |
|---|---|---|---|---|
| F38 | Aparência (tema e cores) | Menu ou diálogo (command_editor.py): Aparência | — | a definir |
| F39 | Teclado e mouse virtuais | Menu ou diálogo (command_editor.py): Teclado e mouse virtuais | — | a definir |
| F40 | Gravação | Menu ou diálogo (command_editor.py): Gravação | — | a definir |
| F41 | Pasta das automações | Menu ou diálogo (command_editor.py): Mapas | — | a definir |
| F42 | Teclas de controle | Menu ou diálogo (command_editor.py): Controles | — | a definir |
| F43 | Execução | Menu ou diálogo (command_editor.py): Execução | — | a definir |
