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

Status: skill local instalada e versionada; gate operacional depende de usar em uma compra real do inicio ao fim.

Entregas:
- [x] Skill local `central-compras`.
- [x] Entrevista guiada para briefing.
- [x] Prompt de pesquisa por categoria.
- [x] Prompt de comparacao de reviews.
- [x] Prompt de decisao final com "por que escolhi" e "por que nao escolhi".
- [x] Guardrails: IA pode sugerir `fonte=web`, mas nao fecha compra sem `fonte=manual`.

Gate de saida:
- Uma compra criada do briefing ate a decisao sem editar arquivos manualmente.

## Sprint 5 - Reconsulta e vereditos

Meta: fechar o ciclo de aprendizado pos-compra.

Status: concluida como automacao local.

Entregas:
- [x] Estado `aguardando_preco`.
- [x] Campos `preco_alvo` e `preco_teto` por produto/projeto.
- [x] Comando para listar itens aguardando preco.
- [x] Veredito D+30 e D+180 com perguntas padrao.
- [x] Comando para transformar veredito em licoes de marca/loja/categoria.

Gate de saida:
- Um veredito D+30 registrado.
- Uma licao gerada a partir de veredito.

## Sprint 6 - Dashboard local

Meta: enxergar a memoria acumulada sem abrir arquivo por arquivo.

Status: concluida como dashboard HTML local gerado a partir dos dados reais do repositorio.

Entregas:
- [x] Gerador HTML local.
- [x] Pagina inicial com projetos ativos, aguardando preco e comprados.
- [x] Pagina de ranking por projeto.
- [x] Pagina de marcas, lojas e licoes.
- [x] Indicadores: reaproveitamento, arrependimento, tempo ate decisao e aderencia ao gate.

Gate de saida:
- [x] Dashboard abre localmente.
- [x] Dados carregam dos CSV/YAML reais.
- [x] Nenhum dado pessoal exposto.

## Sprint 7 - Hardening e rotina

Meta: preparar uso continuo por anos.

Status: quase fechada. Falta so a tag `v1.0`.

Entregas:
- [x] Validacao contra dados sensiveis antes de commit (`checar-segredos --strict`).
- [x] Guia de recuperacao se dado sensivel for commitado (README, secao de seguranca).
- [x] Pasta de dados pessoais fora da arvore do repositorio (`dados-privados`).
- [x] Testes ampliados: 58 testes, cobrindo integridade de CSV, escala do score,
      frescor, regra de parada, gates, travas de decisao e varredura de segredo.
- [ ] Documentacao de rotina semanal.
- [ ] Guia de nova categoria.
- [ ] Tag `v1.0`.

Gate de saida:
- [x] Comando equivalente ao pre-commit bloqueia padroes sensiveis.
- [x] README cobre o uso diario.
- [ ] Release `v1.0` publicada no GitHub privado.

## Sprint 8 - Correcao do motor de decisao

Meta: fazer o numero significar o que ele promete significar.

Status: concluida.

O que estava errado e foi corrigido:

- **Score min-max mentia com poucos candidatos.** Com dois finalistas, o segundo
  sempre tirava 0,00 em qualidade e valor, mesmo perdendo por 0,2 ponto de nota.
  No projeto real do fone, isso virava 80,6 contra 23,1 para uma diferenca que
  na verdade era 75,4 contra 57,9. Agora a escala e absoluta e comparavel entre
  projetos.
- **Alerta `ANCORA` estava invertido.** Ficava calado na ancora inflada e
  acusava o desconto legitimo.
- **`cotacoes.csv` perdia coluna em silencio.** O arquivo e reescrito inteiro a
  cada gravacao, e qualquer coluna fora do schema era descartada. Contradizia o
  principio 1 do PRD.
- **Gate `exige_rede_assistencia` era letra morta.** Declarado em
  `categorias.yaml` e nunca lido. Agora ha teste que falha se qualquer gate
  declarado deixar de ser aplicado.
- **Regra de parada (secao 7.5) nunca foi implementada.** A config existia e
  ninguem lia.
- **Nenhum controle de frescor.** Cotacao de dois anos rankeava como preco de
  hoje, num sistema cujo lema e que preco envelhece em 48 horas.
- **`decidir` fechava sem o motivo da derrota do segundo colocado**, contra o
  principio 4 do PRD.
- **Numero mal digitado virava 0,00** e o produto parecia de graca.
- **`nota_ajustada` era lida congelada do CSV**, entao mudar os pesos da nota
  bayesiana nao mexia no gate.
- **Dashboard so tinha tema claro** e esmagava as tabelas no celular.

## Backlog posterior ao PRD

- Modulo separado para compras B2B/estoque do Esdra Cosmeticos.
- Importacao semiautomatica de planilhas.
- Integracao com calendario para vereditos.
- App ou interface web com formulario.
