# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

Maquina de lavar roupa 13 kg, so lava, abertura superior, 127V. Electrolux como favorita, comparando com Brastemp, Consul, Midea e Panasonic. Teto R$ 2.300 com frete (decisao do Josemar em 12/10/2026).

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: tomada padrao 127V (220V so em ponto especifico); interior de SP, clima quente e sol forte (roupa seca rapido no varal, entao centrifugacao alta pesa pouco); compra online com entrega no interior (prazo e frete contam); garantia nacional pesa.
- Perguntas decisivas respondidas (Josemar, 12/10/2026): tensao 127V; so lava, abertura superior (nao lava e seca); Electrolux como favorita, mas comparar com Brastemp, Consul, Midea e Panasonic; teto R$ 2.300 com frete.
- Suposicoes adotadas (sem resposta, a IA propos o padrao): maquina para a casa dele, em lavanderia coberta que ja tem ponto de agua, esgoto e tomada; substitui ou ocupa o lugar de uma lavadora de abertura superior. [VERIFICAR: medir largura, profundidade e altura livre acima da maquina, porque a tampa abre para cima.]

## Especificacao tecnica para o meu contexto

Referencia de mercado: ficha oficial da Electrolux LED13 lida em 12/10/2026 na loja.electrolux.com.br (dados de fabricante marcados "ficha"); o resto e inferencia.

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Capacidade | 13 kg de roupa seca | 13 kg | pedido dele; 13 kg cobre edredom de casal [inferencia; VERIFICAR programa edredom no manual] |
| Tensao | 127V (versao propria) | 127V | lavadora nao e bivolt; versao 220V na tomada 127V nao funciona direito, e o inverso queima |
| Tipo | abertura superior, so lava | abertura superior | decisao dele; lava e seca custa mais e gasta mais energia |
| Eficiencia energetica | classe A no selo INMETRO | classe A, ate 0,40 kWh/ciclo | LED13 declara 0,4 kWh/ciclo e classe A (ficha) |
| Consumo de agua | ate 150 L/ciclo | abaixo de 150 L/ciclo | LED13 declara 150 L/ciclo (ficha); agua pesa na conta todo mes |
| Centrifugacao | 600 rpm | 630 a 750 rpm | sol forte seca no varal; acima disso e pouco ganho [inferencia] |
| Cesto | polipropileno aceito | inox | inox resiste melhor a risco e acumulo de residuo; plastico tambem dura [inferencia] |
| Filtro de fiapos | presente | filtro facil de limpar | roupa escura sem bolinha de fiapo |
| Dimensoes | cabe no espaco medido | LED13: 59,5 x 66,5 x 105,5 cm; LED15: 66,2 x 72,4 x 105,2 cm (L x P x A, ficha) | tampa aberta: LED13 139 cm, LED15 143 cm (guia rapido Electrolux) |
| Peso da maquina | - | LED13: 40 kg (ficha) | entrega no interior: confirmar se a entrega leva ate o local de uso |
| Pressao de agua | 0,02 a 0,8 MPa (2 a 81 m.c.a.) | base da caixa d'agua 2,4 m acima da entrada da lavadora | manual Electrolux; abaixo disso enche devagar |
| Plugue e disjuntor | plugue 10A com terra; disjuntor EXCLUSIVO de 20A na fase (127V) | - | manual Electrolux: disjuntor exclusivo e obrigatorio; ficha da loja: plugue 10A |
| Garantia | 12 meses nacional de fabrica | 12 meses + rede autorizada na regiao de Aracatuba | conserto e feito em casa por tecnico da marca; LED13 tem 1 ano (ficha) |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Tomada 2P+T no ponto da lavanderia | obrigatorio se o ponto atual nao tiver terra | NBR 14136, 10A (plugue da LED13/LED15) | sem terra ha risco de choque na carcaca | junto (loja local) |
| Disjuntor exclusivo para a lavadora | obrigatorio se o circuito for compartilhado | 20A na fase (127V), conforme manual Electrolux | o manual exige circuito exclusivo; compartilhar pode desarmar ou perder garantia [VERIFICAR o quadro] | junto (loja local) |
| Torneira com bico para lavadora | obrigatorio se o ponto nao tiver | rosca 26,5 mm (3/4"), 14 fios por polegada (manual) | a mangueira de entrada (com filtro) ja vem conectada na maquina | junto (loja local) |
| Capa protetora | recomendado so se a maquina ficar em area aberta | capa para 13 kg, medida da maquina escolhida | sol forte resseca o painel e a tampa | - |
| Base com rodinhas | dispensavel | - | piora o nivelamento e aumenta a vibracao na centrifugacao [inferencia] | - |
| Protetor eletronico / estabilizador | dispensavel | - | lavadora nao precisa de estabilizador; protecao contra surto e no quadro de energia [inferencia] | - |
| Garantia estendida da loja | dispensavel | - | so vale se o preco for baixo; decidir no checkout | - |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: lavadora de abertura superior 13 kg, 127V, classe A. Candidatas Electrolux em estoque na loja oficial em 12/10/2026: LED13 (Essential Care, cesto inox), LDA13 (Efficient, cesto inox), LET13 (Efficient) e LEM13 (Efficient). Concorrentes de 13 kg a levantar: Brastemp, Consul, Midea e Panasonic.
- Alternativas descartadas: lava e seca (decisao dele); LAC13, LES13, LPR13 e LWI13 fora de estoque na loja oficial em 12/10/2026 (voltam se aparecerem em outra loja dentro do teto).
- Motivo: o pedido e uma 13 kg que so lava; o que separa os modelos e consumo de agua e energia, cesto, filtro e preco, nao a quantidade de programas.

## Requisitos gerados

### Obrigatorios

- Pagamento em 10x no cartao; o preco que conta e o TOTAL pago em 10x, nao o do Pix (mudanca do Josemar em 12/10/2026)
- 13 kg, abertura superior, versao 127V
- Classe A de energia no selo INMETRO
- Garantia nacional de fabrica de 12 meses e rede autorizada na regiao
- Cabe no espaco medido, com a tampa aberta

### Desejaveis

- Cesto inox
- Consumo de agua abaixo de 150 L/ciclo
- Filtro de fiapos e dispenser que nao acumula sabao
- Frete gratis e entrega ate o local de uso

### Deal-breakers

- Versao 220V (ou anuncio sem tensao clara)
- Vendedor sem nota ou sem garantia de fabrica
- Total em 10x, com frete, acima de R$ 2.300
