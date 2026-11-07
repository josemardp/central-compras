# PRD — Central de Compras

**Versão:** 2.0
**Autor:** Josemar de Paula (com Claude como arquiteto)
**Substitui:** PRD v1.0
**Status:** Pronto para bootstrap (Fase 0)

---

## 1. Objetivo

Um repositório (local + GitHub privado) que funciona como **memória permanente do processo de compra**: toda pesquisa feita uma vez nunca se perde, toda decisão fica documentada com o motivo, e cada compra nova aproveita o que já se aprendeu sobre marcas, lojas e categorias.

Serve para uma compra de R$ 70 (perfume) e para uma de R$ 150.000 (carro elétrico). A diferença é a **profundidade da pesquisa e o rigor do gate**, nunca a estrutura.

O ativo real do sistema não é a tabela de preços — preço envelhece em 48 horas. O ativo é o par **decisão + veredito**: por que escolhi X, e seis meses depois, deu certo? É isso que não existe em nenhum lugar hoje e é isso que a v1.0 não capturava.

---

## 2. O que a v2.0 corrige na v1.0

| Ponto da v1.0 | Problema real | Correção nesta versão |
|---|---|---|
| Um `controle.csv` por produto, com preço numa coluna | Mistura fato volátil (preço de hoje) com atributo estável (motor, RAM). Ao atualizar o preço você sobrescreve o histórico — e o histórico é o que revela se o "desconto" é real | Separação em **dimensão** (`produto.yaml`, estável) e **fato** (`cotacoes.csv`, append-only, uma linha = uma observação datada). Histórico de preço passa a existir de graça (seção 4) |
| Score somando nota e preço normalizados | Nota 5,0 com 3 avaliações vence nota 4,6 com 8.000. E "preço" não é custo: frete, garantia estendida, IPVA e seguro ficam de fora | **Nota bayesiana** (encolhimento por volume) + **custo total** no lugar de preço + **gates eliminatórios antes do score** (seção 7) |
| Score como número único | Um número esconde de onde veio a diferença. Dois produtos com 82 podem ser 82 por motivos opostos | Score decomposto em 5 eixos, sempre exibido aberto. O ranking mostra o vetor, não só o total (seção 7.4) |
| "Claude pesquisa em tempo real e preenche o CSV" | Meia-verdade. ML e Amazon bloqueiam fetch de página de anúncio com frequência. Prometer isso gera frustração na primeira vez que falhar | Divisão explícita entre **o que a IA faz bem** (mapear modelos, ler reviews, comparar especificação, faixa de preço) e **o que só você confirma** (preço final, estoque, vendedor). Protocolo de coleta na seção 9 |
| Nenhum critério de parada | Pesquisa de compra é otimização sem fim natural. Você gasta 6 horas para economizar R$ 40 num tênis | **Regra de parada por faixa de valor** — orçamento de tempo e nº de candidatos fixados antes de começar (seção 7.5) |
| Fluxo termina na compra | O aprendizado se perde exatamente onde ele nasce | **Ciclo de veredito pós-compra** em D+30 e D+180, que alimenta automaticamente a base de marcas e lojas (seção 10) |
| Sem defesa contra manipulação | Avaliação comprada, preço âncora inflado antes da promoção, anúncio reciclado (o vendedor troca o produto e mantém as 12 mil avaliações) | Seção 8 dedicada, com heurísticas concretas e campos no schema para registrar suspeita |
| `.gitignore` para dados privados | Certo, mas insuficiente: um `git add -A` distraído, ou um `.gitignore` mal escrito, e o CPF sobe. E o Git guarda para sempre | Repo **privado por padrão** + dado sensível **fora da árvore do repositório**, não só ignorado (seção 11) |
| Roadmap sem critério de saída | Fase vira "mais ou menos pronta" e você começa a próxima em cima de base torta | Cada fase com **gate de saída objetivo** (seção 12) |

---

## 3. Cinco princípios invioláveis

1. **Fato datado nunca é sobrescrito.** Preço novo é linha nova, não célula editada.
2. **Gate antes de score.** Produto que não passa nos critérios eliminatórios não entra no ranking — não existe nota alta que compense garantia inexistente.
3. **Todo número é rastreável.** Se o score é 82, é possível reconstruir os 82 a partir do CSV, à mão, com uma calculadora.
4. **O "não escolhi" vale mais que o "escolhi".** Registrar por que o segundo colocado perdeu é o que impede refazer a pesquisa em 2028.
5. **Dado pessoal não mora em repositório versionado.** Nem privado.

---

## 4. Modelo de dados — o núcleo do sistema

Aqui está a resposta direta à sua pergunta original ("vai criando as colunas com variações de marca, preço etc.?"): **sim, mas em dois arquivos diferentes, porque são duas naturezas diferentes de informação.**

### 4.1 `produto.yaml` — a dimensão (o que o produto É)

Muda raramente. Um arquivo por produto avaliado.

```yaml
id: byd-dolphin-mini-gl
categoria: carro
nome: BYD Dolphin Mini GL
marca: BYD
estado: pesquisando        # backlog | pesquisando | aguardando_preco | comprado | descartado
projeto: 2026-comprar-carro

atributos:                 # schema definido pela categoria (seção 4.3)
  motorizacao: eletrico
  autonomia_km: 380
  bateria_kwh: 38
  potencia_cv: 75
  garantia_bateria: "8 anos / 150.000 km"
  porta_malas_l: 230

requisitos_atendidos:      # cruzamento direto com o briefing do projeto
  cabe_familia: true
  rota_valparaiso_sp: parcial   # exige 1 parada de recarga

descartado_porque: null
```

### 4.2 `cotacoes.csv` — o fato (quanto custou, onde, quando)

**Append-only.** Cada linha é uma observação de um instante. Nunca se apaga linha; nunca se edita preço.

**Colunas fixas (toda categoria):**

| Coluna | Observação |
|---|---|
| `data_coleta` | ISO 8601. Obrigatória |
| `produto_id` | Chave para o `produto.yaml` |
| `loja` | Mercado Livre, Amazon, concessionária, loja física |
| `vendedor` | Nome exato do vendedor/loja no marketplace |
| `vendedor_tipo` | `oficial` \| `terceiro` \| `fisica` |
| `anuncio_id` | MLB..., ASIN. **Crítico** — é o que detecta anúncio reciclado |
| `variacao` | Cor, tamanho, versão, capacidade |
| `preco` | À vista, sem frete |
| `preco_promocional` | Se houver |
| `frete_valor` | R$ |
| `frete_prazo_dias` | Nº |
| `custo_extra` | Itens obrigatórios não inclusos (emplacamento, capa, cabo de recarga) |
| `custo_total` | `preco_efetivo + frete + custo_extra`. **É este que entra no score, não `preco`** |
| `nota` | Média bruta exibida |
| `n_avaliacoes` | Nº |
| `nota_ajustada` | Calculada (seção 7.2) |
| `garantia_meses` | Nº |
| `garantia_tipo` | `nacional` \| `importada` \| `vendedor` \| `nenhuma` |
| `link` | URL |
| `flag_suspeita` | Vazio, ou código da seção 8 (`AVAL_SUSPEITA`, `ANCORA`, `RECICLADO`) |
| `fonte` | `web` (Claude pesquisou) \| `manual` (você conferiu no site) |
| `score` | Recalculado a cada rodada de ranking |

O campo `fonte` é o que mantém o sistema honesto: linha marcada como `web` é **estimativa de faixa**, não preço confirmado. Só linha `manual` vale para decisão de compra.

### 4.3 Schema por categoria — definido uma vez, em `config/categorias.yaml`

```yaml
carro:
  atributos_obrigatorios: [motorizacao, autonomia_km, potencia_cv, porta_malas_l, garantia_bateria]
  custo_extra_tipico: [emplacamento, seguro_ano_1, carregador_wallbox]
  tco_meses: 60
  gate:
    garantia_minima_meses: 36
    exige_rede_assistencia: true

celular:
  atributos_obrigatorios: [armazenamento_gb, ram_gb, bateria_mah, versao_5g, anos_update]
  gate:
    nota_minima_ajustada: 4.3
    minimo_avaliacoes: 300
    garantia_tipo_aceita: [nacional]

tenis:
  atributos_obrigatorios: [numeracao, tipo_pisada, drop_mm, uso]
  gate:
    nota_minima_ajustada: 4.2
    minimo_avaliacoes: 150

cosmetico:
  atributos_obrigatorios: [volume_ml, validade_meses, lacre]
  gate:
    exige_vendedor_oficial: true    # falsificação é o risco dominante da categoria
```

Você cadastra a categoria uma vez. Da segunda compra daquela categoria em diante, as colunas extras e os gates já vêm prontos.

---

## 5. Estrutura do repositório

```
central-compras/
├── README.md
├── .gitignore
├── config/
│   ├── preferencias.yaml        # pesos do score, lojas preferidas, marcas vetadas
│   └── categorias.yaml          # schema + gates por categoria (seção 4.3)
├── projetos/
│   └── 2026-comprar-carro/
│       ├── briefing.md          # entrevista inicial — o contrato da decisão
│       ├── cotacoes.csv         # TODAS as cotações do projeto, todos os candidatos
│       ├── ranking.md           # gerado, sobrescrevível
│       └── decisao.md           # escolhido + POR QUE os outros perderam
├── produtos/
│   └── carros/
│       └── byd-dolphin-mini-gl/
│           ├── produto.yaml
│           └── pesquisa.md      # o que as avaliações e reviews dizem de fato
├── base-conhecimento/
│   ├── marcas/byd.md
│   ├── lojas/mercado-livre.md
│   └── licoes.md                # regras nascidas de erro próprio
├── vereditos/
│   └── 2026-03-tenis-asics.md   # D+30 e D+180 pós-compra (seção 10)
└── scripts/                     # Fase 3
```

**Mudança relevante ante a v1.0:** o `cotacoes.csv` vive no **projeto**, não no produto. Comparar Dolphin Mini com Geely EX2 exige as duas cotações no mesmo arquivo, sob os mesmos gates e a mesma normalização. Um CSV por produto forçaria consolidação manual toda vez.

- **Produto** = uma coisa específica sendo avaliada (BYD Dolphin Mini GL).
- **Projeto** = uma necessidade de compra que compara produtos concorrentes (comprar um carro em 2026).
- Compra avulsa e barata (um perfume) dispensa projeto: vai direto num `projetos/avulsas-2026/cotacoes.csv`.

---

## 6. Ciclo de vida — os cinco estados

```
backlog → pesquisando → aguardando_preco → comprado → [veredito D+30 → veredito D+180]
                     ↘ descartado (com motivo obrigatório)
```

`aguardando_preco` é o estado que a v1.0 não tinha e que resolve seu caso mais comum: produto aprovado, gate passado, mas acima do preço-alvo. Ele fica ali com `preco_alvo` e `preco_teto` definidos, e você reconsulta quando quiser — sem refazer pesquisa nenhuma.

`descartado` **exige** preencher `descartado_porque`. Sem motivo, o descarte não vale: daqui a um ano você reconsidera o mesmo produto do zero.

---

## 7. Motor de decisão

Três camadas, nesta ordem. Nunca pule para a camada 2 sem passar pela 1.

### 7.1 Camada 1 — Gates eliminatórios (binário)

Vindos de `categorias.yaml` + do briefing do projeto. Reprovou em qualquer um, sai do ranking:

- `custo_total > preco_teto`
- `nota_ajustada < nota_minima_ajustada`
- `n_avaliacoes < minimo_avaliacoes`
- `garantia_tipo` fora da lista aceita
- `vendedor_tipo = terceiro` quando a categoria exige oficial
- marca em `marcas_vetadas`
- qualquer `requisito_atendido = false` marcado como deal-breaker no briefing

Sai da lista com o motivo do corte registrado. Isso já elimina 70% do trabalho.

### 7.2 Camada 2 — Nota ajustada (correção do maior defeito da v1.0)

```
nota_ajustada = (n × nota + m × μ) / (n + m)
```

- `n` = número de avaliações
- `μ` = média histórica da categoria naquele marketplace (use 4,3 como default)
- `m` = peso da âncora (use 50)

Efeito prático: 5,0 com 4 avaliações vira **4,35**; 4,7 com 6.000 avaliações continua **4,70**. Volume passa a ser tratado como o que é — evidência.

### 7.3 Camada 3 — Score de valor (0 a 100)

Todos os componentes normalizados min-max **dentro do conjunto de elegíveis daquele projeto** (comparar tênis com tênis, não com o universo).

| Eixo | Peso default | O que entra |
|---|---|---|
| `qualidade` | 0,30 | `nota_ajustada` + sinal qualitativo das reviews lidas |
| `valor` | 0,25 | `custo_total` invertido — ou **TCO** quando a categoria define `tco_meses` |
| `risco` | 0,20 | `vendedor_tipo`, reputação da loja, `garantia_tipo` e `garantia_meses` |
| `aderencia` | 0,15 | % de `requisitos_atendidos` do briefing (fit, não preço) |
| `conveniencia` | 0,10 | `frete_prazo_dias`, política de devolução, retirada |

O eixo **aderência** não existia na v1.0 e é o que impede o sistema de recomendar o produto mais barato e bem avaliado que não resolve seu problema.

**TCO (custo total de posse)** — obrigatório acima de R$ 20.000:

```
TCO = custo_total + Σ(custo_operacional_mensal × tco_meses) − valor_revenda_estimado
```

No carro elétrico, é exatamente aqui que a conta muda de figura: energia contra combustível, IPVA reduzido, manutenção menor, contra depreciação ainda mal estabelecida da categoria no Brasil e custo do seguro, que costuma ser mais alto. Comparar preço de etiqueta entre um elétrico e um híbrido plug-in não decide nada.

### 7.4 Saída do ranking — sempre aberta

```
1. BYD Dolphin Mini GL — 84
   qualidade 0.88 · valor 0.71 · risco 0.95 · aderência 0.80 · conveniência 0.90
   ↑ rede de assistência e garantia de bateria
   ↓ autonomia obriga parada na rota até São Paulo

2. Geely EX2 Pro — 81
   qualidade 0.85 · valor 0.83 · risco 0.72 · aderência 0.85 · conveniência 0.80
   ↑ custo total menor, mais espaço
   ↓ rede de assistência mais nova no interior paulista
```

Três pontos de diferença com vetores opostos significa **empate técnico** — e aí quem decide é o critério humano, não a planilha. O sistema tem que dizer isso em voz alta, não fingir precisão que não tem.

### 7.5 Regra de parada

| Faixa | Tempo máx. de pesquisa | Candidatos | Cotações mín. por candidato |
|---|---|---|---|
| até R$ 200 | 20 min | 3 | 1 |
| R$ 200 – 2.000 | 2 h | 5 | 2 |
| R$ 2.000 – 20.000 | 1 semana | 5 | 3 |
| acima de R$ 20.000 | 30 dias, com data-limite no briefing | 4 | 3 + 1 presencial |

Estourou o orçamento de tempo, decide com o que tem. A regra existe para proteger você de si mesmo.

---

## 8. Defesa contra manipulação

Três armadilhas concretas, com detecção viável:

**`AVAL_SUSPEITA`** — avaliação inflada. Sinais: distribuição em U extrema (só 5 e 1 estrela, quase nada no meio); pico de avaliações concentrado em poucos dias; textos genéricos sem menção ao uso; nota altíssima com contagem baixa. Regra prática: leia sempre as de **3 estrelas** — são as menos manipuladas e as mais informativas.

**`ANCORA`** — preço "de" inflado antes da promoção. Sinal: `preco_promocional` com desconto acima de 40% sobre um `preco` que nunca apareceu nas suas cotações anteriores. Sua própria série histórica no `cotacoes.csv` é a defesa — e ela só existe porque o arquivo é append-only. Em duas ou três coletas espaçadas você já sabe qual é o preço real.

**`RECICLADO`** — o vendedor edita um anúncio antigo, troca o produto e herda milhares de avaliações. Sinal: `anuncio_id` já visto no seu CSV com produto diferente, ou avaliações antigas descrevendo outro item. É por isso que `anuncio_id` é coluna obrigatória.

Cotação com flag não é descartada automaticamente — é rebaixada no eixo `risco` e sinalizada no ranking.

---

## 9. O que a pesquisa automatizada faz e o que não faz

Esta seção existe para o sistema não prometer o que não entrega.

**Funciona bem (Claude com busca na web):**
- mapear quais produtos existem numa categoria e faixa de preço;
- comparar especificação técnica entre modelos;
- levantar problemas recorrentes reportados em reviews, fóruns e vídeos;
- identificar quais lojas e vendedores costumam trabalhar com aquele item;
- estimar faixa de preço praticada.

**Não funciona de forma confiável:**
- ler o preço exato de um anúncio específico de ML/Amazon agora (proteção anti-bot bloqueia com frequência);
- confirmar estoque, prazo real de entrega no seu CEP, cupom aplicável;
- monitorar preço 24/7 sozinho — um robô raspando essas páginas é frágil e desalinhado com os termos de uso.

**Protocolo prático:** a IA levanta e preenche as linhas com `fonte: web`; você abre os 3–5 finalistas, confere e cola de volta os números reais, virando `fonte: manual`. Só linha `manual` fecha compra. Isso leva 5 minutos e elimina 100% do risco de decidir sobre preço fantasma.

---

## 10. Veredito pós-compra — o loop que fecha o sistema

Nenhuma ferramenta de compra faz isso, e é aqui que está o retorno composto. Duas checagens curtas, 5 minutos cada:

**D+30** — chegou no prazo? Produto conforme o anúncio? Embalagem/lacre ok? Já apareceu defeito? Vendedor respondeu bem?

**D+180** — ainda usa? Vale o que pagou? Compraria de novo do mesmo vendedor? O que você não sabia na hora e agora sabe?

O veredito escreve de volta:
- em `base-conhecimento/lojas/*.md` → reputação real medida por você, não pela plataforma;
- em `base-conhecimento/marcas/*.md` → durabilidade observada;
- em `base-conhecimento/licoes.md` → regra nova, que vira gate na próxima compra.

Exemplo de lição virando regra: *"perfume de vendedor terceiro no ML chegou sem lacre em 2 de 3 compras"* → vira `exige_vendedor_oficial: true` na categoria cosmético. Foi assim que aquele gate da seção 4.3 nasceu.

---

## 11. Segurança e privacidade

- **Repositório privado por padrão.** Não há ganho em ser público, e há risco.
- **Dado pessoal fora da árvore do repositório**, não apenas no `.gitignore`. Endereço, CPF, dados de entrega ficam em `~/.central-compras/dados-privados/` (fora da pasta versionada) e são referenciados por caminho. Arquivo que não está na pasta não pode ser commitado por acidente.
- **Nunca** cartão, CVV ou senha — em lugar nenhum, nem local.
- `preferencias.yaml` e `categorias.yaml` são regra de negócio e podem ser versionados à vontade.
- Se um dado sensível for commitado, `git rm` **não resolve** — o histórico guarda. O procedimento é reescrever o histórico (`git filter-repo`) e trocar o que vazou.

---

## 12. Roadmap com gate de saída

**Fase 0 — Validar o fluxo, hoje, sem código**
Criar as pastas, `preferencias.yaml` e `categorias.yaml`, e rodar uma compra real de baixo risco inteira no chat.
**Gate de saída:** um `decisao.md` preenchido, com o segundo colocado e o motivo de ter perdido, para uma compra que você efetivamente fez.

**Fase 1 — Estrutura versionada**
`git init`, push para GitHub privado, templates de `cotacoes.csv`, `produto.yaml`, `briefing.md`, `decisao.md`. Script Python opcional que lê o CSV, aplica gate + score e cospe `ranking.md`.
**Gate de saída:** dois projetos e pelo menos 15 cotações no repositório, com score reproduzível fora do chat.

**Fase 2 — Skill `central-compras`**
No mesmo padrão das suas skills atuais: conduz a entrevista, pesquisa, preenche os arquivos e gera o prompt pronto para o Claude Code aplicar e commitar.
**Gate de saída:** uma compra do início ao fim sem você editar arquivo à mão.

**Fase 3 — Exploratório**
Reconsulta assistida de preço para os itens em `aguardando_preco` (sob demanda, não robô 24/7). Dashboard HTML local gerado a partir dos CSVs. Ciclo de veredito com lembrete automático em D+30/D+180.
**Gate de entrada:** só faz sentido com 50+ cotações e 5+ vereditos registrados. Antes disso, dashboard bonito de dado vazio.

---

## 13. Métricas de sucesso do próprio sistema

Sem isso, você nunca sabe se valeu construir:

1. **Reaproveitamento** — % de compras novas em que a base já tinha informação útil. Meta: >40% a partir da décima compra.
2. **Taxa de arrependimento** — % de compras com veredito D+180 negativo. Meta: queda ao longo do tempo. É a métrica mais honesta que existe aqui.
3. **Tempo médio até decisão por faixa** — deve cair conforme a base cresce.
4. **Aderência ao gate** — quantas vezes você comprou algo que o gate reprovou. Se for alto, o gate está calibrado errado (ou você está comprando por impulso — os dois são úteis de saber).

---

## 14. Fora de escopo da v1

- **Compra de estoque para o Esdra Cosméticos.** É outro problema: entra margem, giro, lote mínimo, prazo do fornecedor, capital parado. Merece módulo próprio depois, com schema separado — misturar B2C e B2B corrompe os dois.
- Integração com API de marketplace (nenhuma delas oferece o que você precisa em conta pessoal).
- App mobile, notificação push, multiusuário.

---

## 15. Próximo passo imediato

**Rode a Fase 0 em duas frentes, na mesma semana:**

1. **Compra pequena e real** (o tênis, um perfume) — valida entrevista → cotação → gate → score → decisão em menos de uma hora, com risco financeiro perto de zero.

2. **Registre retroativamente o carro elétrico.** Toda a comparação entre Dolphin Mini GL, Geely EX2 Pro, King GL e Atto 2 DM-i já foi feita — e hoje ela existe só em conversa. Transformar isso em `briefing.md` + `cotacoes.csv` + `decisao.md` faz três coisas de uma vez: preenche o repositório com o caso mais valioso que você tem em mãos, testa o schema no cenário mais difícil (TCO, financiamento, requisito de rota), e deixa registrado o "por que não o outro" — que é exatamente o que some da memória primeiro e o que a Esdra vai querer entender quando vocês fecharem a decisão.

Se o schema aguentar o carro, aguenta qualquer coisa que você comprar nos próximos dez anos.
