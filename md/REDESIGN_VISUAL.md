# Redesign visual (tema) — o que mudou e como mexer

**Escopo:** só aparência. Nenhuma regra de automação, gravação, execução, atalho ou arquivo de mapa foi alterada.
As configurações visuais do usuário (tema claro/escuro/sistema, acento, superfície clara, contraste) continuam mandando:
o tema é *derivado* delas.

## Onde fica o tema (tudo em `automationstudio/core.py`)

| Peça | Papel |
|---|---|
| `_theme_tokens(dark, accent, light_surface, light_contrast)` | Todas as cores do tema, num lugar só. |
| `_APP_QSS` | Folha de estilo global com `@tokens@` no lugar das cores. |
| `_build_app_stylesheet(tokens)` | Troca os `@tokens@` e devolve o texto final. |
| `_apply_application_palette(...)` | Monta a `QPalette` e aplica a folha (mesma assinatura de antes). |

## Tokens do tema escuro

Três camadas: **janela** (`window`), **áreas de conteúdo rebaixadas** (`base`: listas, campos, tabela, timeline) e
**controles elevados** (`button` → `hover`). O acento é a única cor "viva"; ele marca o que está ativo/selecionado/principal.

| Token | Valor | Uso |
|---|---|---|
| window | `#1a1d23` | fundo da janela e da barra |
| base / alt | `#14171c` / `#191d23` | campos, listas, tabela (e zebra) |
| button / hover / pressed | `#262b33` / `#2e343e` / `#1f242b` | botões e estados |
| border / border_strong | `#2b313a` / `#3b4350` | divisórias / contorno de controles (`palette(mid)`) |
| text / muted / disabled | `#e8ebf0` / `#9aa4b2` / `#5f6977` | texto |
| accent (+ hover/press/soft/on_accent) | do usuário | principal, seleção, foco |

No tema claro, as mesmas funções derivam tudo da superfície e do contraste escolhidos pelo usuário.

## Regras para quem mexer no visual (os testes em `tests/unit/test_tema_visual.py` vigiam várias)

1. **Não mude o tamanho dos controles.** Os paddings da folha são os de sempre; a barra de ferramentas tem altura fixa.
2. **Não estilize sub-controles nativos** (`::indicator`, `::drop-down`, `::up-button`...): sem imagem, eles somem.
3. **Não defina `selection-background-color` global:** a tabela de comandos pinta a própria seleção.
4. **Estilo no widget vence o global.** Um `setStyleSheet` num widget só precisa dizer o que é diferente.
5. **Cor nova = token novo** em `_theme_tokens`, não `#hex` solto. Para acompanhar o acento use `palette(highlight)`.
6. **Botão de destaque:** `botao.setProperty('primary', True)` *antes* de exibir. Na barra: `'primary'` ou `'danger'`.
   Em diálogos, o botão padrão (`:default`) já fica em destaque.

## Mudanças pontuais fora do `core.py`

- `main_window.py`: botão × da barra de comandos usava `#111111` (quase invisível no tema escuro) → `palette(text)`;
  divisor do workspace acompanha o acento; "CRIAR NOVA AUTOMAÇÃO" e "▶ Executar" em destaque, "🛑 Parar tudo" em vermelho.
- `command_editor.py`: abas em forma de botão ficam planas e sublinham com o acento escolhido (era âmbar fixo).
- `timeline.py` e constantes `_COLOR_*` do `core.py`: neutros do tema escuro alinhados às camadas novas.

## Próximos PRs sugeridos (não feitos aqui para não gerar conflito com as outras frentes)

- Textos secundários com cor fixa (`#8f96a3`, `#9aa0aa`) têm pouco contraste no tema claro: trocar por token.
- Rótulos da barra com emoji (💾, 🛑...) → ícones consistentes com o tema.
- Mover os `setStyleSheet` inline restantes para a folha global (por `objectName`/propriedade).

## Checklist de conferência (abrir o programa, tema escuro e claro)

- [ ] Barra de ferramentas: nenhum botão cortado; Executar em destaque; Parar tudo vermelho; desabilitados apagados.
- [ ] Campos, combos e spinboxes: sem borda dupla; altura normal; foco com contorno no acento.
- [ ] Lista de automações: seleção com tom do acento; lista de condições ainda legível.
- [ ] Abas do editor de comandos: planas, sublinhado no acento.
- [ ] Tabela de comandos: seleção não "dobra" (sem preenchimento em cima da faixa).
- [ ] Trocar o acento nas configurações visuais: botões, foco e seleção acompanham ao vivo.
- [ ] Menus de contexto, dicas (tooltips), barra de rolagem, barra de status, diálogos.
- [ ] Timeline: blocos, régua e playhead legíveis.
