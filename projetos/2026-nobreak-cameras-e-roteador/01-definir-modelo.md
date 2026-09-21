# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

Nobreak para manter roteador e as 6 cameras gravando quando faltar energia.

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: casa em 127V; 6 cameras + roteador.
- Perguntas decisivas respondidas: nobreak sim (Josemar, 21/09).
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): carga total ~50 W (6 x 5,4 W + roteador/ONU ~15 W, conta da IA). Um nobreak de 600-700 VA com 1 bateria de 12V 7Ah segura cerca de 1 hora (estimativa); para mais tempo, modelo com bateria maior ou expansivel. A ONU/modem da operadora tambem precisa estar no nobreak, senao as cameras gravam no cartao mas o app nao ve ao vivo.

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Potencia | 600 VA | 700 a 1.200 VA | carga ~50 W; folga para bateria durar mais |
| Tensao de saida | 115V | 115V | circuito das cameras em 127V |
| Tensao de entrada | 127V | bivolt automatico | flexibilidade |
| Autonomia | ~1 h com 50 W | bateria expansivel ou 2 baterias | ladrao costuma cortar a energia |
| Tomadas | 3 | 4 ou mais | roteador, ONU, circuito das cameras |
| Garantia | nacional | nacional, marca com assistencia (SMS, Intelbras, APC, Ragtech) | bateria e item de troca |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Bateria extra/externa | depende | 12V selada, conforme o modelo | so se quiser mais de 1 hora | decidir depois da cotacao |
| Senoidal pura | dispensavel | - | fontes chaveadas (cameras, roteador) funcionam com onda aproximada | - |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: nobreak interativo 700-1.200 VA, saida 115V, bivolt.
- Alternativas descartadas: nobreak senoidal (caro sem necessidade); filtro de linha (nao segura falta de luz).
- Motivo: manter cameras gravando e o roteador no ar quando a energia cai.

## Requisitos gerados

### Obrigatorios

- Saida 115V
- Garantia nacional
- Marca com assistencia

### Desejaveis

- Bateria expansivel
- Bivolt automatico

### Deal-breakers

- Marca sem assistencia no Brasil
