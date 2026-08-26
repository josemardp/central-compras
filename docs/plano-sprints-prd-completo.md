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

## Sprint 9 - Robustez sob entrada quebrada

Meta: aguentar arquivo editado a mao, interrupcao e dado torto sem perder nada.

Status: concluida.

O que estava errado e foi corrigido:

- **Gravacao nao era atomica.** `cotacoes.csv` era aberto em modo `w`, que
  trunca antes de escrever. Um Ctrl+C, disco cheio ou excecao no meio zerava a
  serie historica inteira. Medido: o arquivo ia de 2 linhas para 0. Agora toda
  gravacao passa por arquivo temporario e `os.replace`.
- **Data invalida escapava de todas as travas.** `--data ontem` era aceito e
  gravado. Como toda guarda de data depende de parsear `data_coleta`, aquela
  cotacao nunca vencia, nao entrava certo na deteccao de ancora e nao era
  reclamada por ninguem. Agora e barrada na entrada e na validacao.
- **`preco_teto` do produto era ignorado.** O CLI aceitava, gravava no
  `produto.yaml` e o gate so olhava o do briefing.
- **`promover-cotacao` herdava `flag_suspeita` da linha web.** A conferencia
  manual e observacao nova: ou voce reafirma a suspeita, ou ela nao se aplica.
- **Produto em `aguardando_preco` ranqueava como pronto.** O estado quer dizer
  "decidi esperar preco melhor" e aparecia liderando sem marca nenhuma. Agora o
  ranking mostra quanto falta para o alvo e `decidir` pede confirmacao.
- **YAML corrompido cuspia traceback cru.** Agora diz qual arquivo e o que fazer.

Testes: de 66 para 82.

## Sprint 10 - Selecao, idempotencia e leitura

Meta: garantir que o sistema tecnicamente funcionando entregue tambem a
resposta certa para quem le.

Status: concluida.

O que estava errado e foi corrigido:

- **Cotacao manual vencida vencia observacao recente.** `latest_quotes` preferia
  `manual` sem olhar a data: medido, um preco manual de 2024 (R$ 900) rankeava
  no lugar de uma cotacao web de hoje (R$ 400). A guarda de frescor avisava, mas
  a escolha em si continuava errada.
- **`aprender-veredito` nao era idempotente.** Rodar duas vezes duplicava marca
  e loja na base, e a base alimenta o `prompt-ia`: o aprendizado passava a
  contar dobrado. Agora recusa repetir sem `--force`.
- **`registrar-licao --gate` apagava os comentarios do `categorias.yaml`.** O
  arquivo e feito para ser editado e documentado a mao, e um `safe_dump` do
  arquivo inteiro comia toda explicacao. A edicao passou a ser cirurgica, na
  linha certa, com conferencia de que o YAML continua valido depois.
- **`--perdedores` aceitava o proprio escolhido**, gerando um `decisao.md` que
  dizia que o vencedor perdeu.
- **Dinheiro saia como `R$ 1234.5`** em ranking, historico, decisao, veredito,
  prompts e dashboard.

Verificado e sem defeito nesta rodada: escape de HTML do dashboard (conteudo
hostil sai inerte, nenhuma tag executavel injetada), dashboard com repositorio
vazio e com projeto sem cotacao, desempenho com 25 projetos (1,1s), e
`parse_pairs` com `=` dentro do valor.

Testes: de 82 para 96.

## Sprint 11 - Auditabilidade e invariantes

Meta: trocar inspecao manual por metodo. Cobertura, fuzz com invariantes e
verificacao de uma promessa do PRD que nunca tinha sido testada.

Status: concluida.

**Achado principal.** O principio 3 do PRD ("se o score e 82, e possivel
reconstruir os 82 a partir do CSV, a mao, com uma calculadora") era meia-verdade.
De eixos para score, fechava. De CSV para eixos, nao: os pesos internos do eixo
risco (0,30 vendedor / 0,35 tipo de garantia / 0,20 prazo / 0,15 loja) e as
tabelas de pontuacao viviam cravados no codigo. `risco 0,71` era um numero
impossivel de conferir.

Corrigido:
- Todas as constantes do risco foram para `preferencias.yaml`, em `escala.risco`.
- Comando `auditar` gera `memoria-calculo.md` com a conta inteira, parcela por
  parcela, incluindo a penalidade por alerta.
- Teste que confere que as parcelas do risco somam de volta no risco publicado.

**Fuzz com invariantes.** 80 rodadas geradas com semente fixa, metade com dado
patologico de proposito (preco negativo, `1e309`, `2026-13-45`, unicode,
categoria inexistente, colisao de `anuncio_id`, estado desconhecido). Zero
violacoes. As propriedades verificadas: score em 0-100, eixo em 0-1, cortado
sempre com score 0, elegivel sempre sem eliminacao, ordem decrescente, o mais
barato elegivel sempre com valor 1,00, nenhum relatorio explode, e
`write(read(x)) == x` sem perder linha.

**Cobertura.** 87% com fluxo completo e testes combinados. Os ramos que estavam
sem teste nenhum e que produziriam resposta errada em silencio ganharam teste:
`parse_scalar` (e como `--requisito r=false` vira deal-breaker), `adherence_score`
com `parcial` (que e o que os quatro produtos reais usam), `yaml_scalar`,
`waiting_gap` sem preco alvo, busca de projeto por nome parcial e ambiguo, e
`replace_or_append_bullet`. Todos ja estavam corretos: estavam sem teste, nao
com defeito.

Testes: de 96 para 118.
