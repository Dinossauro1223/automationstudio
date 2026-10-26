# Auditoria da base AS 22.64

## Limpeza realizada

- Removidos diretórios e arquivos Python `__pycache__/*.pyc` gerados em versões anteriores.
- Consolidados os changelogs fragmentados da V22 em `CHANGELOG_V22.md`; os arquivos individuais foram removidos para evitar duplicidade e confusão de histórico.
- Corrigida a versão interna de `automationstudio.__version__` para `22.63`.
- Corrigido o título da janela que ainda apontava para `AS 22.12`.
- Simplificado o `README.md`, removendo históricos redundantes e mantendo apenas a documentação da base atual.

## Recursos preservados

Todos os módulos Python, scripts `.bat`, dependências, testes e recursos visuais presentes na base auditada foram preservados. Os recursos visuais existentes são referenciados pelo código e, portanto, não foram considerados órfãos.

## Critérios de integridade

- Nenhum módulo Python foi excluído por suspeita; todos participam do grafo de imports do aplicativo ou dos testes.
- Nenhum recurso visual foi excluído porque o código referencia explicitamente os oito arquivos de identidade visual.
- Arquivos `.pyc` foram excluídos por serem artefatos gerados e não fontes necessários ao funcionamento.

Atualização 22.64: âncora de seleção por ID e aplicação direta da ordem visual no drop.
