# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

4 m de cremalheira reforcada branca para o motor do portao (ou 3 m do kit + 1 m).

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: motor rapido (Jetflex), portao de correr.
- Perguntas decisivas respondidas: 4 m, reforcada, branca; ou 3 m do kit + 1 m (Josemar, 21/09).
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): o metro que faltar e do MESMO modelo/fabricante da que vier no kit.

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Comprimento | 4 m no total | 4 m, ou 1 m se o kit trouxer 3 m | acompanha o comprimento do portao |
| Material | nylon com alma de aco (reforcada) | idem, gomos M4 | motor rapido exige mais do dente |
| Compatibilidade | engrenagem Z18 do DZ Rio, padrao residencial (2,5 cm) | idem | encaixe correto no motor |
| Cor | branca | branca | pedido do Josemar |
| Fixacao | parafusos inclusos | parafusos e porcas inclusos | instalacao sem improviso |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Parafusos/porcas extras | dispensavel | - | normalmente vem com a barra | - |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: cremalheira residencial reforcada (nylon com alma de aco), branca.
- Alternativas descartadas: cremalheira industrial de aco (desnecessaria para 500 kg).
- Motivo: resistencia suficiente e cor pedida. Depende do kit do motor (3 m inclusos ou nao).

## Requisitos gerados

### Obrigatorios

- Compativel com Z18/M4 padrao residencial
- Nylon com alma de aco

### Desejaveis

- Mesma marca da que vier no kit
- Branca

### Deal-breakers

- Misturar modelos diferentes na mesma linha (o passo do dente pode nao bater na emenda)
