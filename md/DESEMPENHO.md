# Desempenho: como medir, onde está o custo e como otimizar

Escrito pela conta de integração em 31/10/2026, para todas as frentes. A integração **mede, aponta onde está o custo e confere que o comportamento não mudou**; quem muda o código é a frente dona do arquivo (visual: aparência e interação; funções: núcleo, motor, banco e visão). Este documento é o plano permanente de otimização: quando uma frente ficar sem tarefa atribuída, o ciclo da seção 7 diz o que fazer.

## 1. A regra

1. Meça antes. 2. Mude **uma** coisa. 3. Meça de novo. 4. Rode a suíte completa **e** o teste das funções do usuário (`tests/gui/test_funcoes_acessiveis.py`): otimizar não pode mudar o que o programa faz nem tirar uma função do alcance. 5. Coloque a tabela antes/depois na mensagem do commit.

Um ganho que não aparece na medição não existe. Um ganho com teste vermelho não vale. Um ganho abaixo de 10% que deixa o código mais difícil de ler se descarta. Nunca se remove uma verificação de segurança (parada de emergência, validação do mapa, aviso de tecla ocupada) para ganhar tempo.

## 2. Como medir

```
python tests/testsupport/medir_desempenho.py --json antes.json        # mede e guarda
# ... mude UMA coisa ...
python tests/testsupport/medir_desempenho.py --comparar antes.json    # mostra a diferença
```

O script mede 16 cenários com os 3 mapas reais dos testes (o maior tem 933 comandos e 1,1 MB): importar o programa, ler, gravar e validar o mapa, montar a linha do tempo, banco, motor com relógio virtual, comparação de imagens e, com Qt real, criar a janela, abrir o mapa grande no editor, abrir e pintar a timeline e reaplicar o tema. Opções: `--sem-gui` (só o núcleo), `--repetir N` (padrão 5). Não envia teclado nem mouse.

Para a comparação ser justa: mesma máquina, mesma versão do Python e do PySide6, nada pesado aberto ao lado, e sempre a **mediana** (a primeira repetição costuma ser a mais lenta, com o cache frio). Os números do Linux de integração não são os do Windows do dono: peço que o dono rode o script no Windows e guarde o resultado em `md/desempenho/base_windows_<data>.json`; a partir daí a comparação passa a valer para a máquina que importa.

## 3. Linha de base (31/10/2026)

Linux, Python 3.14.4, PySide6 6.12.0, Qt sem janela visível, 5 repetições (3 na importação). Arquivo: `md/desempenho/base_linux_2026-10-31.json`.

| Cenário | Mediana (ms) | Mín | Máx |
|---|---:|---:|---:|
| Importar a janela principal (processo novo) | 333.6 | 331.0 | 373.5 |
| Ler o mapa 'Flins combo' do JSON (1124 KB) | 25.2 | 24.3 | 25.5 |
| Gravar o mapa 'Flins combo' em JSON | 21.5 | 20.2 | 23.1 |
| Validar o mapa 'Flins combo' (933 comandos) | 1.5 | 1.4 | 1.7 |
| Montar a linha do tempo de 'Flins combo' | 12.7 | 12.4 | 13.6 |
| Gravar os 3 mapas no banco (SQLite) | 67.3 | 60.9 | 76.2 |
| Abrir o banco e carregar os 3 mapas | 34.4 | 32.5 | 44.2 |
| Executar 'Flins combo' uma vez no motor (relógio virtual, sem enviar nada) | 68.5 | 42.2 | 78.5 |
| Comparar duas imagens de 400x300 (vision.compare_images) | 41.9 | 41.0 | 57.9 |
| Comparar duas imagens de 1920x1080 (vision.compare_images) | 211.2 | 196.8 | 276.6 |
| Criar a janela principal (3 automações salvas) | 1006.1 | 340.5 | 2261.9 |
| Abrir 'Flins combo' no editor (933 comandos) | 242.9 | 224.5 | 329.5 |
| Pintar a janela inteira (editor com o mapa grande) | 27.4 | 16.4 | 32.1 |
| Abrir a timeline do mapa grande | 161.6 | 128.6 | 244.2 |
| Pintar a janela inteira (timeline do mapa grande) | 117.3 | 116.8 | 121.3 |
| Reaplicar o tema visual (_apply_visual_settings) | 280.9 | 262.6 | 360.4 |

Como ler: **o núcleo não é o gargalo.** Ler, gravar e validar um mapa de 1,1 MB custa dezenas de milissegundos ou menos, e o motor gasta menos de 0,1 ms de sobrecarga por comando (o tempo real de uma automação vem das pausas do próprio mapa). **O custo está na interface** (pintar a timeline, abrir um mapa grande no editor, reaplicar o tema, criar a janela) e **na visão** (comparar imagens em tela cheia passa do intervalo mínimo de 50 ms da espera por imagem).

Cuidado com a variação: criar a janela mediu de 340 ms (melhor caso) a 2,3 s (primeira vez, cache frio), e `compare_images` de 400x300 mediu 22 ms numa sessão e 42 ms noutra, na mesma máquina. Compare só dentro de uma mesma sessão.

## 4. Metas propostas

Proposta da integração; o dono ajusta. Referência: abaixo de 100 ms o usuário percebe a resposta como imediata; 60 quadros por segundo pedem 16 ms por quadro.

| Operação | Hoje (Linux) | Meta | Por quê |
|---|---:|---:|---|
| Pintar a timeline (cada quadro) | 117 ms | 16 ms (pior caso 50 ms) | arrastar e dar zoom precisa ser fluido |
| Abrir uma automação grande no editor | 243 ms | 100 ms | clicar numa automação deve ser imediato |
| Reaplicar o tema visual | 281 ms | 100 ms, e só quando algo mudou | trocar tema não pode congelar |
| Criar a janela principal | 340 ms a 2,3 s | 500 ms (mediana) | abrir o programa não pode parecer travado |
| Comparar imagens em 1920x1080 | 211 ms | 20 ms | tem que caber no intervalo mínimo de 50 ms da espera por imagem |
| Ler ou gravar um mapa de 1,1 MB | 25 e 21 ms | manter | já está bom |
| Motor (sobrecarga por comando) | menos de 0,1 ms | manter | já está bom |

## 5. Onde está o custo e o que fazer

### 5.1 Frente visual

**V-O1. Timeline: 117 ms por quadro** (`TimelineCanvas.paintEvent`, `timeline.py` linha 191). O código pinta **todas** as linhas a cada quadro (fundo alternado, rótulo e barra de cada um dos 933 comandos), com antialiasing ligado e sem olhar o retângulo que o Qt pediu (`_event`). Fazer, nesta ordem: (a) ler `event.rect()` e pintar só as linhas visíveis (primeira e última linha a partir de `_RULER_H` e `_ROW_H`); (b) antialiasing só nas barras; (c) criar canetas, pincéis e fontes uma vez (ao criar o widget ou ao trocar o tema), não por linha; (d) guardar a régua e o fundo numa `QPixmap`, refeita só quando tamanho, zoom ou tema mudam; (e) ao mover o *playhead* ou o mouse, `update(retângulo_pequeno)` em vez de `update()`. Conferir: cenário "Pintar a janela inteira (timeline do mapa grande)", e um teste que pinta a timeline do mapa grande num `QImage` antes e depois e compara os pixels da área visível (a otimização não pode mudar o desenho).

**V-O2. Abrir uma automação no editor: 243 ms** (`CommandTableWidget.refresh`, `command_editor.py` linha 2608). `refresh` zera a tabela e faz `insertRow` e `_fill_row` linha a linha, com a tabela se atualizando a cada passo; `_fill_row` cria 7 `QTableWidgetItem` por comando e recalcula a cor do grupo em cada célula. Fazer: (a) `setUpdatesEnabled(False)` durante o preenchimento (reabilitar em `finally`); (b) `setRowCount(n)` uma vez em vez de `insertRow` n vezes; (c) calcular a cor de cada grupo uma vez por `refresh` (um dicionário); (d) tirar o dicionário de nomes de tipo de dentro do laço; (e) no longo prazo, `QTableView` com `QAbstractTableModel` (só cria o que aparece). O item (e) é mudança grande: ramo próprio, com os testes de edição e o catálogo de funções verdes.

**V-O3. Reaplicar o tema: 281 ms** (`_apply_visual_settings`, `main_window.py` linha 2173). Cada `setStyleSheet` num widget faz o Qt reaplicar o estilo nele e em todos os filhos. Fazer: (a) só reaplicar quando a configuração mudou (guardar o que foi aplicado e comparar); (b) folha de estilo global no `QApplication` em vez de `setStyleSheet` por widget (o `REDESIGN_VISUAL.md` já aponta: tokens + folha global; tirar os `setStyleSheet` inline que sobraram); (c) agrupar as mudanças entre `setUpdatesEnabled(False)` e `True`.

**V-O4. Criar a janela: 0,3 a 2 s.** Fazer: (a) criar só no primeiro acesso as páginas que não aparecem na abertura (timeline, monitor, linhas mescladas, barra lateral de comandos); (b) carregar o logotipo e as folhas de estilo uma vez; (c) medir por trecho com `cProfile` (seção 6) antes de decidir o que adiar.

### 5.2 Frente de funções

**F-O1. `vision.compare_images`: 211 ms em 1080p.** Percorre pixel a pixel em Python. Fazer, do mais barato ao mais caro: (a) se os bytes das duas imagens são iguais, devolver 1.0 sem laço; (b) trocar `int(...)` por `math.ceil(...)` no passo da amostragem (hoje dá 518 mil amostras em 1080p, o dobro do alvo de 250 mil que o próprio código descreve; muda o valor por centésimos, e `tests/unit/test_vision_comportamento.py` mostra se algo importante mudou); (c) com a decisão D19 (OpenCV), `cv2.absdiff` + `mean` mediu **3,9 ms** em 1920x1080 neste ambiente (cerca de 50 vezes mais rápido; sem contar a conversão do `QImage` para matriz). A fase 7.A troca o casamento por inteiro; se ela demorar, (a) e (b) valem.

**F-O2. Banco: cerca de 22 ms por `save_map`.** Cada gravação abre uma conexão, liga `PRAGMA journal_mode=WAL`, grava e fecha. Fazer, só com um teste de integridade em mãos: (a) `journal_mode=WAL` fica gravado no arquivo, basta uma vez (`foreign_keys` é por conexão e continua); (b) várias gravações numa transação só quando for importação ou migração; (c) `synchronous=NORMAL` é seguro com WAL, mas **só** depois de existir um teste que encerra o processo no meio da gravação e confere que o banco abre e o último mapa íntegro está lá (hoje não existe: escrevê-lo primeiro).

**F-O3. Núcleo e motor: não mexer.** Ler e gravar o mapa de 1,1 MB (25 e 21 ms), validar (1,5 ms) e executar no motor (menos de 0,1 ms por comando) já estão bons. Otimizar aqui é risco sem retorno.

**F-O4. Importação: cerca de 330 ms para importar a janela principal num processo novo.** Medir com `python -X importtime -c "import automationstudio.main_window" 2> importtime.txt` e ver o que mais pesa; candidatos: o que é importado no topo e só serve a diálogos raros.

**F-O5. Dependência: o programa só usa `QtCore`, `QtGui` e `QtWidgets`.** O `requirements.txt` pede `PySide6`, que traz também WebEngine, PDF e outros módulos que o programa não usa: 673 MB em disco no ambiente de testes. `PySide6-Essentials` basta, em tese. Para verificar: ambiente limpo com `PySide6-Essentials`, suíte completa e compilar o `.exe` com o PyInstaller (tamanho e tempo antes e depois). Só trocar com os três verdes e atualizando juntos o `.bat` de instalação e o teste estático que confere os dois.

## 6. Como achar o próximo custo

- Importação: `python -X importtime -c "import automationstudio.main_window" 2> importtime.txt`.
- Uma operação específica: monte o cenário como em `tests/testsupport/medir_desempenho.py` e envolva a chamada:

```python
import cProfile, pstats
perfil = cProfile.Profile(); perfil.enable()
janela._select_map_by_name("Flins combo")          # o que você quer investigar
perfil.disable(); pstats.Stats(perfil).sort_stats("cumulative").print_stats(25)
```

Quando achar um custo que não está na seção 5, acrescente um item (V-O5, F-O6...) com o número medido e o que fazer.

## 7. Ciclo permanente (para quando a frente estiver sem tarefa atribuída)

1. `python tests/testsupport/medir_desempenho.py --json antes.json`.
2. Escolha o maior custo da tabela cujo item da seção 5 ainda não foi feito, ou o primeiro cenário acima da meta da seção 4.
3. Uma mudança por commit, no arquivo da sua frente (a divisão está em `md/DIVISAO_DE_TRABALHO.md`).
4. Suíte completa e catálogo de funções verdes.
5. `--comparar antes.json`; ponha a tabela antes/depois na mensagem do commit e uma linha na seção 8.
6. Publique no seu ramo. A integração confere de novo e junta na `main`.
7. Esgotada a lista, procure o próximo custo (seção 6).

## 8. Registro de otimizações

| Data | Item | Antes | Depois | Commit |
|---|---|---:|---:|---|
| | (nenhuma feita ainda) | | | |
