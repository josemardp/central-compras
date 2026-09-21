# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

50 m de cabo PP 3x1,5 mm2 para levar energia pelos conduites ate as cameras (e, se o Fabio confirmar, ao motor).

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: conduites ja passados no muro; tensao 127V.
- Perguntas decisivas respondidas: 50 m de PP 3x1,5 (lista do Fabio).
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): o cabo alimenta as cameras; se tambem for alimentar o motor, o ideal e o motor ter circuito e disjuntor proprios [VERIFICAR com Fabio].

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Tipo | cabo PP flexivel 3 vias | PP 3x1,5 mm2 300/500V, condutor classe 5 | duplo isolamento, proprio para conduite externo |
| Condutor | cobre | cobre eletrolitico | CCA (aluminio cobreado) esquenta e da mau contato |
| Bitola | 1,5 mm2 real | 1,5 mm2 | 6 cameras de ~5,4 W somam pouco; sobra folga |
| Certificacao | INMETRO | INMETRO + marca conhecida (Sil, Corfio, Cobrecom, Conduspar) | bitola menor que a anunciada e golpe comum |
| Comprimento | 50 m | rolo fechado de 50 m | medida do Fabio |
| Cobertura | PVC preta | PVC preta antichama | resiste melhor ao sol nas pontas expostas |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Plugue femea 2P+T 10A (6 un) | obrigatorio | NBR 14136, 10A | liga a fonte de cada camera dentro da caixinha | junto |
| Conector de emenda tipo alavanca (~12 un) | recomendado | 3 vias, ate 2,5 mm2 | derivacao limpa e segura | junto |
| Fita isolante | dispensavel | - | o conector de alavanca dispensa | - |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: cabo PP 3x1,5 mm2 500V, cobre, INMETRO, rolo de 50 m.
- Alternativas descartadas: cabo paralelo (sem duplo isolamento), cabo CCA.
- Motivo: e o cabo indicado pelo Fabio e o correto para conduite externo.

## Requisitos gerados

### Obrigatorios

- Cobre, INMETRO, 3x1,5 mm2
- 50 m continuos

### Desejaveis

- Marca conhecida
- Antichama

### Deal-breakers

- CCA / aluminio cobreado
- Sem INMETRO
- Vendido como 1,5 mm2 com bitola menor
