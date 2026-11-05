# Robustez do modelo e do banco: condição de imagem com valor ilegível (validação e editor), lacunas de teste e a medição da F4 (versão 25.9)

Frente de funções, 04 e 05/11/2026. Quatro coisas saíram de uma medição de cobertura de linhas feita em 03/11 nas áreas da frente (modelo, motor, banco) e da medição pedida pela F4 (otimizações): (1) a validação das condições de espera por imagem passa a nunca lançar exceção; (2) o editor de comandos passa a abrir um comando cuja condição de imagem tem valor ilegível (é por onde o usuário corrige o valor que a validação agora aponta); (3) testes para as lacunas pequenas que a cobertura apontou; (4) a medição do custo de gravar um mapa, que **não sustenta a F-O2**. Ramo `funcoes/robustez-modelo`, **empilhado** sobre `funcoes/validacao-lacunas` (seção 7). Marcado `Versão: 25.9 (nova)`: nada daqui entra na 25.8.

## 1. O que muda para quem usa

Só muda para quem tiver uma condição de espera por imagem com um valor fora do comum, num JSON editado à mão, por exemplo: um valor que não é número (a validação e o editor) ou uma precisão zero ou nula (só o rótulo do editor). A interface não produz isso: ela usa caixas numéricas.

| Valor na condição | Antes | Agora |
|---|---|---|
| `"confidence": "0,9"` (vírgula decimal) ou `"alto"` | o `validate()` **lançava** `ValueError: could not convert string to float: '0,9'` na hora de iniciar, sem dizer de qual comando | o mapa não começa: `[cmd_...] Precisão da imagem precisa ser um número entre 0 e 1 (recebi '0,9'). Use ponto como separador decimal (0.9, não 0,9).` |
| `"interval": "x"` | idem (`ValueError`) | `[cmd_...] Intervalo de verificação da imagem precisa ser um número, em segundos (recebi 'x').` |
| `"region": {"x": "abc", ...}` (ou `y`; também `null`, lista, e em qualquer das quatro chaves um texto decimal como `"10.5"`, infinito ou NaN) | **passava** na validação e falhava no meio da execução, dentro da captura (`int('abc')`) | o mapa não começa: `[cmd_...] Região da imagem: 'x' precisa ser um número inteiro (recebi 'abc').` |
| `"region": {"w": "abc", ...}` (ou `h`; também `null`, lista) | era recusado, mas com a mensagem errada ("Largura/altura da região não podem ser negativas"), porque por dentro o valor ilegível virava -1 | a mesma mensagem do `x`, com o nome da chave e o valor recebido |

**O que não muda.** Tudo o que o executor converte continua valendo: `"0.9"` (texto com número), `true`, `null` e `0` (viram o padrão), `x` e `y` negativos (monitor à esquerda ou acima da tela principal), largura e altura positivas ou zero. Largura ou altura negativa continua recusada, com a mensagem de antes. Os 3 mapas reais (`tests/data/legacy_maps.json.gz`) e o `AutomationStudio.db` de 08/10 (3 mapas, 943 comandos) **não têm nenhuma condição de imagem**, então nada neles muda: conferi validando os seis (os 3 do banco, numa cópia, e os 3 do arquivo de testes) com o código de antes (`f74f324`) e com o deste ramo, e as mensagens são idênticas (0 erros em todos).

**Um caso de borda que muda.** Largura ou altura entre -1 e 0 (exclusivos, por exemplo `-0.5`) era recusada e agora vale: o executor faz `int(-0.5)`, que dá 0, e 0 significa "usar o tamanho da imagem de referência". A validação passa a concordar com o executor.

**No editor de comandos** (mesma condição de uso: valor que não é número, vindo de JSON editado à mão). Descoberto ao conferir quem mais lê esses parâmetros: o editor também os converte sem proteção, e é por ele que o usuário corrigiria o valor que a validação agora aponta.

| O que o editor encontra | Antes | Agora |
|---|---|---|
| precisão `"0,9"`, `"alto"` ou lista (ou `null`) na condição de imagem, ao abrir o comando | `ValueError`/`TypeError` ao montar a lista de condições (`command_editor.py:453`): o diálogo **não abre** e o usuário não consegue corrigir pela interface | o comando abre; a linha da condição mostra `Imagem: botao.png · precisão ilegível ('0,9')` |
| o mesmo valor, ao clicar em "Editar selecionada" (também intervalo `"x"`, região `"abc"`, infinito, NaN ou região que não é objeto) | exceção | o formulário abre com o que dá para ler e o padrão no campo ilegível (95%, 0,5 s, 0 px); o usuário corrige e adiciona de novo |
| precisão nula ou zero (o executor trata como 95%) | o rótulo mostrava `precisão 0%` (e o `null` lançava exceção) | o rótulo mostra `precisão 95%`, o que vai valer de fato |

Abrir o comando e salvar sem mexer **não altera** a condição (regra central do editor, `tests/gui/test_command_dialog.py`): o valor ilegível continua lá até o usuário corrigir; quem avisa é a validação do mapa.

## 2. De onde veio: a medição de cobertura

O ambiente de desenvolvimento não tem o `coverage.py` nem acesso ao PyPI, então medi linhas com o `sys.monitoring` do próprio Python (um script de 60 linhas, fora do projeto), rodando a suíte inteira no dublê de widgets (1776 passam, igual à rodada normal). O dublê não cobre a interface nem a visão (precisam do Qt de verdade: o Actions mede isso), então só olhei as áreas da frente:

| Arquivo | Linhas executáveis | Cobertas | % | O que falta |
|---|---:|---:|---:|---|
| `core.py` | 1041 | 958 | 92,0 | 83 linhas: 79 de cores e tema (`QColor`, `QPalette`, esquema de cores do sistema: precisam do Qt de verdade), 1 de `sys._MEIPASS` (só existe no executável empacotado) e 3 resguardos sem Qt (abaixo) |
| `project.py` | 293 | 286 | 97,6 | 7 linhas: três `except` defensivos e `_path_for` |
| `conditions.py` | 78 | 77 | 98,7 | 1 linha: o `except` que a seção 1 reescreve |
| `input_system.py` | 1404 | 1104 | 78,6 | 300 linhas: 218 da `WindowsProcessReadiness` (a espera por processo, com ctypes do Windows), 34 de `_wait_for_process` e `configure_readiness` (que a usam), 7 do `import` do pynput e 41 ramos soltos (retornos antecipados e `except` defensivos) |
| `ativacao.py`, `controle_ui.py` | 285 | 285 | 100 | nada |

As lacunas sem Qt eram pequenas, mas seis delas guardavam comportamento. No modelo: o `"="` de um mapa sem tecla, a duração de um mapa vazio (ou só com comandos desativados) e o reparo de IDs que sorteia de novo. No banco: uma configuração gravada como texto puro por versão antiga, a migração do padrão antigo que não consegue regravar e o tamanho de um snapshot que não serializa. Para cada uma há agora um teste e um defeito plantado. A medição também achou uma coisa que **não** é lacuna de teste: `ProjectManager._path_for` (`project.py:44`) não tem nenhum chamador no pacote nem nos testes; é código morto da época dos mapas em arquivos (limpeza do Ponto 4, não mexi).

O que a cobertura **não** achou de pior: nenhuma parte do modelo ou do banco com comportamento importante sem teste. O que há de falta real está no Windows: a espera por processo (a `WindowsProcessReadiness` e a parte do motor que a usa, cerca de 250 linhas), que só roda com o Windows de verdade.

## 3. Como foi feito

- **`conditions.py`, `WaitCondition.validate()`** (condição de imagem): `confidence` e `interval` passam pela mesma conta do executor, `float(valor or padrão)`, dentro de `try`; se não converte, a mensagem diz o campo e o valor recebido (cortado em 40 caracteres) e, quando o texto tem vírgula, a dica do ponto decimal. Cada valor da região passa por `int(...)`, também como o executor (`vision.capture_region`); se não converte, a mensagem diz a chave. As mensagens de faixa de antes (precisão entre 0 e 1, intervalo maior que zero, largura/altura negativa, região que não é objeto) continuam como estavam, na mesma ordem.
- **`command_editor.py`**: duas funções pequenas no topo (`_numero_ou_padrao`, a conta do executor com padrão quando o valor não converte, e `_valor_curto`, o valor cortado em 20 caracteres), usadas em `_append_condition_item` (o rótulo da condição de imagem) e em `_edit_condition` (precisão, intervalo e os quatro valores da região; região que não é objeto vira zeros). Nenhum controle, texto de botão ou layout mudou.
- O **executor não mudou**: `input_system.py` e `vision.py` não foram tocados (o `vision.py` só importa com o Qt de verdade, que não tenho aqui; por isso a paridade com o executor é conferida contra as contas copiadas no teste).
- Nenhum controle da janela mudou: `md/FUNCOES_DO_USUARIO.md` não muda.

## 4. Decisões (você pode vetar qualquer uma)

1. **A validação copia as contas do executor, não o contrário**, como na F2: `float()` para precisão e intervalo, `int()` para a região. Por isso `"10.5"` entre aspas na região passa a ser recusado (o executor falharia), e `10.5` sem aspas continua valendo (vira 10).
2. **Só os parâmetros que o leitor não converte.** `target`, `timeout`, `stable_ms` e `after` da condição já são convertidos na leitura (`WaitCondition.from_dict`); um valor ruim neles falha ao carregar o mapa, que fica no banco e aparece em `load_errors`, como já era. Não tratei construção direta com tipos errados (`parameters=None`, `timeout="3"`): é erro de quem programa, não de dado do usuário.
3. **A dica da vírgula só aparece quando o valor é texto com vírgula**, e só para precisão e intervalo (a região pede inteiro: "10,5" é recusado sem a dica).
4. **Nenhuma regra nova de faixa**: não inventei limite para intervalo (um intervalo de 1 hora vale) nem para a região (o monitor pode ser grande).
5. **O editor não conserta valor por conta própria.** Abrir e salvar sem mexer mantém o valor ilegível (a regra central do editor: abrir e salvar não altera o comando); a validação do mapa avisa e o usuário corrige em "Editar selecionada".
6. **O rótulo mostra a precisão que o executor vai usar** (`float(valor or 0.95)`): nulo e zero aparecem como 95%, e um valor ilegível aparece como `ilegível ('0,9')`, cortado em 20 caracteres. É a única mudança visível para um mapa "normal" com precisão zero ou nula, e só existe em JSON editado à mão (a caixa do editor vai de 0,50 a 1,00).
7. **No formulário de edição, o campo ilegível recebe o padrão** (95%, 0,5 s, 0 px) e os campos legíveis da mesma condição são carregados normalmente.

## 5. Testes e números

**Reproduzir e falhar antes de corrigir.**
- *Validação:* com o arquivo novo de testes e o código sem a correção, 86 dos 158 testes falharam (os que lançam, os que a validação deixava passar e os dois do motor); os 72 que passavam são o resguardo do que não deve mudar (valores válidos, faixa, mensagens antigas). Depois da correção: 153 passam (tirei 5 amostras redundantes de um valor enorme na região, que `int()` converte mas ninguém digita).
- *Editor:* com os 31 testes novos e o `command_editor.py` sem a correção, 19 falharam, todos com a exceção esperada (`ValueError: could not convert string to float: '0,9'` em `command_editor.py:453` ao abrir o comando; `ValueError`, `OverflowError` e `AttributeError` em `_edit_condition`; `precisão 0%` onde devia ser 95%). Os 12 que passavam guardam o que não pode mudar (abrir e salvar sem mexer com intervalo e região ilegíveis, que o editor já aceitava, e o rótulo de precisão válida).

**Cada commit, medido numa cópia limpa do próprio commit** (dublê de lógica / dublê de widgets, `.bat` em CRLF; a base da F2 tinha 1548 passam, 313 pulados / 1776 passam, 85 pulados, e 2 xfail nos dois):

| Commit | Dublê de lógica | Dublê de widgets |
|---|---|---|
| base da F2 (`f74f324`) | 1548 passam, 0 falham, 313 pulados | 1776 passam, 0 falham, 85 pulados |
| 1. validação da condição de imagem (`35a6339`) | 1701 passam, 0 falham, 313 pulados | 1929 passam, 0 falham, 85 pulados |
| 2. editor de comandos (`0b3e786`) | 1701 passam, 0 falham, 344 pulados | 1960 passam, 0 falham, 85 pulados |
| 3. testes das lacunas (`59dc04a`) | **1710 passam, 0 falham, 344 pulados** | **1969 passam, 0 falham, 85 pulados** |

Os 2 xfail são os mesmos em todas as linhas. Os 31 testes novos do editor ficam pulados no dublê de lógica (não tem widgets): é por isso que os pulados da lógica vão de 313 para 344. Em relação à base da F2, a árvore final tem **+162 testes no dublê de lógica e +193 no de widgets**.

**Testes novos (193).**
- `unit/test_wait_condition_validation.py` (153): nunca lança com valor ilegível; mensagem com o campo, o valor cortado e a dica; o que o executor converte continua valendo; faixa com a mensagem de antes; região (cada chave, cada tipo de lixo); x e y negativos; dois valores ruins apontam os dois; **paridade** com as contas do executor para as amostras que a conversão decide (as que a faixa decide têm teste próprio); o mapa valida com a mensagem apontando o comando; o motor recusa o mapa antes de enviar qualquer entrada.
- `unit/test_model_validation.py` (6): mapa criado sem tecla ganha `"="`, com tecla mantém; duração total de mapa vazio e só com desativados; reparo de IDs que repete o sorteio.
- `persistence/test_app_settings.py` (2): pasta de dados gravada como texto puro por versão antiga continua valendo; a migração do padrão antigo não derruba a leitura se não consegue regravar.
- `persistence/test_map_history.py` (1): snapshot que não serializa conta 4096 bytes.
- `gui/test_command_dialog.py` (31): o comando abre com cada valor ilegível (precisão com vírgula, texto e lista; intervalo; região com texto, infinito, NaN e lista); abrir e salvar sem mexer não altera a condição; o rótulo mostra o valor ilegível e corta o valor longo; o rótulo mostra a precisão que o executor vai usar (número, texto com número, nulo, zero); editar carrega o padrão no campo ilegível; corrigir pelo editor deixa o comando válido. Rodam no dublê de widgets aqui e com o Qt de verdade no Actions.

**Defeitos plantados.** O catálogo vai de 391 para **414** (+23): `MOD57` a `MOD64` (a validação de imagem: cada `except` desfeito, `float` no lugar de `int`, dica sem efeito, valor sem corte, x/y negativos recusados, largura/altura negativa aceita), `EDI32` a `EDI38` (o editor: o rótulo e a edição voltando a lançar exceção, a regra do executor no rótulo, a região que não é objeto, o padrão que vira 0, o valor escondido ou sem corte no rótulo), `MOD65` a `MOD69` (tecla padrão nas duas camadas, duração vazia e só com desativados, reparo de IDs) e `PER17` a `PER19` (os três resguardos do banco). Cada grupo foi rodado à parte quando nasceu (os 16 do modelo e do banco: 16 de 16 mortos). **Rodada completa:** os 407 do catálogo daquele momento (os 391 da base, `MOD57` a `MOD64` e os 8 das lacunas), numa cópia com os commits 1 e 3 (sem o do editor, que difere da árvore final só em `command_editor.py`, `tests/gui/test_command_dialog.py` e nas linhas novas do catálogo, conferido com `diff`): **407 mortos, 0 sobreviveram, 0 inválidos**, 100% dos defeitos pegos. A rodada foi retomada três vezes depois de o ambiente a interromper (no 28º, no 160º e no 184º defeito; cerca de 70 min no total, 35 min na última parte). A área do editor (38 defeitos, `EDI01` a `EDI38`), refeita numa cópia limpa da árvore final, que já tem o commit do editor: **38 mortos, 0 sobreviveram, 0 inválidos** (6,6 min), e os 7 novos foram mortos por testes que apontam o motivo. `--validar` confirma que os 399, 406 e 414 defeitos de cada commit se aplicam ao código dele.

**GitHub Actions** (Qt de verdade, PySide6 6.12.0), execução 41961289396, disparada à mão no commit `41ec636` (a ponta do ramo na hora: a árvore de código é a dos commits 1 a 3, e o commit seguinte só altera este documento) em 05/11/2026:
- **Linux** (Python 3.14.10): passo comum com **1998 passam, 11 pulados, 3 xfail** (51 s); janela principal, um processo por teste, **44 de 44**; sucesso.
- **Windows** (Python 3.14.10, informativo): passo comum com **1997 passam, 12 pulados, 3 xfail** (56 s); janela principal **44 de 44**; sucesso.
- Em relação à execução da F2 (Linux 1805, Windows 1804, 3 xfail nas duas), os passam sobem **193 nos dois**, que é exatamente a conta dos testes novos (153 + 6 + 2 + 1 + 31), e os **pulados não mudaram** (11 e 12): nenhum teste novo foi pulado, inclusive os 31 do editor, que o dublê de lógica pula e que aqui rodaram com os widgets de verdade. Os 3 xfail são os mesmos de antes (achados 2.03 e 2.04 da persistência e a F4 da visão, fase 7.A); os dublês pulam o da visão, que exige o Qt de verdade, e por isso a tabela acima mostra 2.

## 6. A medição da F4: a F-O2 não se sustenta no Linux

O `md/DESEMPENHO.md` (F-O2, seção 5.2) diz "cerca de 22 ms por `save_map`" e descreve o que cada gravação faz ("abre uma conexão, liga `PRAGMA journal_mode=WAL`, grava e fecha"); propõe ligar o `journal_mode=WAL` uma vez só e, depois de um teste que encerra o processo no meio da gravação, usar `synchronous=NORMAL`. Medi onde o tempo vai, com o mapa grande ('Flins combo', 933 comandos, 1124 KB), três execuções de 25 repetições cada (mediana de cada uma), Linux, Python 3.13, disco do ambiente, máquina livre:

| O que | Mediana (as 3 execuções) |
|---|---:|
| `save_map` inteiro, como hoje | 10,5 a 12,2 ms |
| `map_to_json` (só serializar o mapa) | 8,1 a 11,1 ms |
| só o SQLite, como hoje (conexão nova + `PRAGMA WAL` + `INSERT` + commit) | **0,9 a 1,0 ms** |
| SQLite sem repetir o `PRAGMA journal_mode=WAL` | 0,9 ms |
| SQLite com `synchronous=NORMAL` | 0,9 ms |
| `repair_duplicate_command_ids` | 0,11 a 0,13 ms |

O SQLite, com tudo o que a premissa acusa (conexão nova, `PRAGMA`, commit), é **cerca de 8% da gravação** (0,9 de 10,5 a 12,2 ms); **quase todo o resto é serializar o JSON de 1,1 MB**. Repetir o PRAGMA ou trocar o `synchronous` não muda nada medível aqui: abaixo dos 10% que a regra da seção 1 do `DESEMPENHO.md` exige, e nem na faixa de ruído de uma execução para outra. Então **não mexi no banco**. A forma de reduzir esse custo é o formato v2 do Ponto 3 (de 1,15 MB para no máximo 100 KB, a meta do roadmap). (Uma primeira medição, feita com a máquina ocupada, deu números maiores, 13 a 15 ms na serialização, com a mesma proporção; a tabela acima é a da máquina livre.)

Duas ressalvas: (a) isto é Linux; o `fsync` do Windows pode ser bem mais caro e o `synchronous=NORMAL` poderia valer lá. Quem decide é a medição do seu computador (tarefa I3 do `DELEGACAO.md`: `medir_desempenho.py --json`, cenário "Gravar os 3 mapas no banco"); só nesse caso valeria escrever antes o teste de queda no meio da gravação que a F-O2 exige. (b) A F-O1 (comparação de imagens) e a F-O4/F-O5 (importação e dependência) **não dá para medir aqui**: precisam do Qt, do OpenCV e do ambiente de verdade, que só o Actions e o seu Windows têm. A F-O3 (núcleo e motor) a integração mandou não mexer, e a medição acima confirma.

Como medi (para repetir): num diretório temporário, `ProjectManager(pasta)`, o mapa grande de `tests/data/legacy_maps.json.gz` e, em cada caso, 25 vezes `gc.collect()` + `time.perf_counter()` ao redor de (a) `map_to_json(mapa)`, (b) `gerente.save_map(mapa)` e (c) uma conexão `sqlite3` nova que faz o mesmo `INSERT ... ON CONFLICT DO UPDATE` com ou sem o `PRAGMA journal_mode=WAL` e com `PRAGMA synchronous=NORMAL`.

## 7. Por que o ramo está empilhado

Este ramo nasce de `funcoes/validacao-lacunas` (`f74f324`) e não da `main` porque altera as mesmas linhas do `tests/README.md` (a contagem do catálogo de defeitos plantados) e o mesmo `tests/testsupport/mutacoes.py`, e a base da F2 já traz a correção do abort do Windows no Actions (`md/ENTREGA_PAUSA_TECLAS.md`, seção 10). **Ordem de junção:** `funcoes/pausar-continuar-teclas`, `funcoes/validacao-lacunas`, este. Se algum dos anteriores for vetado, este precisa ser refeito sobre a `main` (são poucos arquivos).

## 8. O que não foi verificado

- **Windows de verdade.** Nada aqui toca em entrada real nem na captura de tela.
- **A captura com a região convertida** (`vision.capture_region`) só roda com o Qt de verdade, e a paridade do meu teste é conferida contra a conta copiada, não contra o `vision.py`. O Actions (seção 5) rodou com o Qt de verdade e passou, inclusive os testes que já existiam dessa função (`test_vision_comportamento.py`: o texto numérico `"6"` vira inteiro e largura ou altura 0 cai no tamanho padrão), o que confirma essas duas contas do lado do executor. Esses testes usam uma tela falsa: a captura de uma tela de verdade continua sem teste.
- **O editor numa janela de verdade.** Os 31 testes novos do editor passaram com os widgets de verdade no Actions (seção 5; no Linux, num display virtual); ninguém abriu o diálogo e olhou o resultado numa janela de verdade (a linha 453 era Python puro, e a correção não depende do Qt).
- **Python 3.14 aqui.** O ambiente onde rodei os dublês tem o Python 3.13.16; quem roda o 3.14 é o Actions (3.14.10 nos dois sistemas, seção 5).
- **A cobertura com o Qt de verdade.** A medição da seção 2 é do dublê de widgets (por isso a visão aparece com 24,5%). O Actions roda o modo `completo` do `rodar_testes.py` e não o `cobertura`, que usa o `coverage.py` (o `requirements-dev.txt` já o instala lá) e confere a catraca contra um `tests/coverage_baseline.json` que não está no repositório. Nenhuma cobertura foi medida com o Qt de verdade; é o passo seguinte natural para achar lacunas na interface e na visão.

## 9. Para a integração

Esta entrega não altera `ROADMAP.md`, `DELEGACAO.md` nem `DESEMPENHO.md`. **Atenção à frente visual:** o `command_editor.py` é arquivo compartilhado; o que mudei nele é pouco e localizado (duas funções novas no topo, o rótulo da condição de imagem em `_append_condition_item` e as linhas de precisão, intervalo e região de `_edit_condition`; nenhum widget, texto de botão ou layout), então um conflito com a `visual/novo-tema` deve ser fácil de resolver. Para a tarefa F4 do quadro: a medição da seção 6 contradiz a premissa da F-O2 no Linux; a seção 8 do `DESEMPENHO.md` ("Registro de otimizações") continua sem nenhuma linha, porque nenhuma otimização foi feita. `ProjectManager._path_for` (sem chamadores) entra na lista de código morto do Ponto 4.
