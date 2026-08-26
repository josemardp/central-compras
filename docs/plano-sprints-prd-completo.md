# Plano de sprints - PRD completo

Objetivo: evoluir a Central de Compras do bootstrap atual ate o PRD v2 completo, mantendo cada sprint com uma entrega utilizavel e um gate objetivo.

## Visao geral

| Sprint | Tema | Resultado esperado |
|---|---|---|
| 0 | Fundacao versionada | Repo privado, estrutura, CLI inicial, testes e primeiro processo real |
| 1 | Fluxo de compra completo | Processo guiado de ponta a ponta, com decisao e veredito manual |
| 2 | Motor de decisao robusto | Gates, nota bayesiana, score aberto, cortes e ranking reproduzivel |
| 3 | Base de conhecimento | Marcas, lojas, licoes e reaproveitamento entre compras |
| 4 | Assistente IA operacional | Prompts/skill local para conduzir briefing, pesquisa e decisao |
| 5 | Reconsulta e vereditos | Itens aguardando preco, D+30, D+180 e aprendizado retroalimentado |
| 6 | Dashboard local | Visao HTML das compras, candidatos, decisoes, arrependimentos e economia |
| 7 | Hardening | Privacidade, validacoes, docs finais e rotina de uso |

## Sprint 0 - Fundacao versionada

Status: concluida.

Entregas:
- Repositorio Git local.
- Repositorio GitHub privado.
- Estrutura de pastas do PRD.
- Templates base.
- CLI `scripts/central_compras.py`.
- Primeiro projeto real: fone bluetooth para chamadas.
- Teste automatizado do fluxo principal.

Gate de saida:
- `git push` feito para repo privado.
- `python -m unittest discover -s tests` passando.
- Primeiro ranking gerado com cotacoes `fonte=web`.

## Sprint 1 - Fluxo de compra completo

Meta: validar uma compra pequena do inicio ao fim.

Status: automacao implementada; falta fechar uma compra real com cotacao manual para cumprir o gate de negocio.

Entregas:
- [x] Comando `status` mais detalhado por etapa.
- [x] Checklist atualizado automaticamente em `processo.md`.
- [x] Comando para promover cotacao `web` para `manual`.
- [x] Comando para marcar candidato como descartado com motivo obrigatorio.
- [ ] Compra do fone fechada com `decisao.md` real.
- [x] Arquivo de veredito criado no ato da decisao.

Gate de saida:
- Uma compra real concluida.
- Segundo colocado registrado com motivo de derrota.
- Pelo menos uma cotacao manual usada na decisao.

## Sprint 2 - Motor de decisao robusto

Meta: deixar score e gates confiaveis para compras de valor maior.

Status: concluida.

Entregas:
- [x] Validacao de schema por categoria.
- [x] Relatorio de campos faltantes por produto/cotacao.
- [x] Ranking com vetores de score, cortes e empate tecnico.
- [x] Suporte a TCO para categorias acima de R$ 20.000.
- [x] Deteccao inicial de flags `AVAL_SUSPEITA`, `ANCORA` e `RECICLADO`.
- [x] Testes de gates, nota ajustada e score.
- [x] Testes de TCO.

Gate de saida:
- Score reproduzivel por teste automatizado.
- Produto cortado nunca aparece como elegivel.
- Ranking explica todos os cortes.

## Sprint 3 - Base de conhecimento

Meta: fazer compras novas reaproveitarem aprendizado antigo.

Status: concluida como base operacional.

Entregas:
- [x] Comando para registrar licao.
- [x] Comando para atualizar reputacao de loja.
- [x] Comando para atualizar experiencia com marca.
- [x] Leitura da base de conhecimento no prompt de IA.
- [x] Relatorio de reaproveitamento por categoria.

Gate de saida:
- Pelo menos 3 lojas e 3 marcas com registro.
- Uma regra de `base-conhecimento/licoes.md` convertida em gate de categoria.

## Sprint 4 - Assistente IA operacional

Meta: reduzir edicao manual e transformar a Central em assistente guiado.

Entregas:
- Skill local `central-compras`.
- Entrevista guiada para briefing.
- Prompt de pesquisa por categoria.
- Prompt de comparacao de reviews.
- Prompt de decisao final com "por que escolhi" e "por que nao escolhi".
- Guardrails: IA pode sugerir `fonte=web`, mas nao fecha compra sem `fonte=manual`.

Gate de saida:
- Uma compra criada do briefing ate a decisao sem editar arquivos manualmente.

## Sprint 5 - Reconsulta e vereditos

Meta: fechar o ciclo de aprendizado pos-compra.

Entregas:
- Estado `aguardando_preco`.
- Campos `preco_alvo` e `preco_teto` por produto/projeto.
- Comando para listar itens aguardando preco.
- Veredito D+30 e D+180 com perguntas padrao.
- Comando para transformar veredito em licoes de marca/loja/categoria.

Gate de saida:
- Um veredito D+30 registrado.
- Uma licao gerada a partir de veredito.

## Sprint 6 - Dashboard local

Meta: enxergar a memoria acumulada sem abrir arquivo por arquivo.

Entregas:
- Gerador HTML local.
- Pagina inicial com projetos ativos, aguardando preco e comprados.
- Pagina de ranking por projeto.
- Pagina de marcas, lojas e licoes.
- Indicadores: reaproveitamento, arrependimento, tempo ate decisao e aderencia ao gate.

Gate de saida:
- Dashboard abre localmente.
- Dados carregam dos CSV/YAML reais.
- Nenhum dado pessoal exposto.

## Sprint 7 - Hardening e rotina

Meta: preparar uso continuo por anos.

Entregas:
- Validacao contra dados sensiveis antes de commit.
- Documentacao de rotina semanal.
- Guia de nova categoria.
- Guia de recuperacao se dado sensivel for commitado.
- Testes ampliados.
- Tag `v1.0`.

Gate de saida:
- `pre-commit` ou comando equivalente bloqueia padroes sensiveis.
- README cobre o uso diario.
- Release `v1.0` publicada no GitHub privado.

## Backlog posterior ao PRD

- Modulo separado para compras B2B/estoque do Esdra Cosmeticos.
- Importacao semiautomatica de planilhas.
- Integracao com calendario para vereditos.
- App ou interface web com formulario.
