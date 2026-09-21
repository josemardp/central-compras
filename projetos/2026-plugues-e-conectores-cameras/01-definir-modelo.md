# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

6 plugues femea 2P+T 10A e ~12 conectores de emenda de alavanca para ligar as fontes das cameras nas caixinhas.

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: 6 caixinhas no muro, cabo PP 3x1,5.
- Perguntas decisivas respondidas: quer tudo (Josemar, 21/09).
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): 2 conectores por caixinha = 12; o Fabio pode preferir outro jeito de derivar [VERIFICAR com Fabio].

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Plugue femea | 2P+T 10A, NBR 14136 | 2P+T 10A de marca conhecida | a fonte das cameras encaixa sem adaptador |
| Quantidade de plugues | 6 | 6 | 1 por camera |
| Conector de emenda | alavanca, ate 2,5 mm2 | Wago 221 (3 vias) ou similar certificado | emenda segura sem fita |
| Quantidade de conectores | 12 | 12 a 15 | 2 por caixinha + reserva |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Fita isolante | dispensavel | - | o conector de alavanca dispensa | - |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: plugue femea 2P+T 10A + conector de alavanca 3 vias.
- Alternativas descartadas: emenda com fita isolante; tomada de embutir (nao cabe em caixinha pequena).
- Motivo: instalacao limpa e segura dentro da caixinha.

## Requisitos gerados

### Obrigatorios

- NBR 14136 / certificado
- Conector para ate 2,5 mm2

### Desejaveis

- Marca conhecida (Wago, Tramontina, Pial)

### Deal-breakers

- Conector sem certificacao
