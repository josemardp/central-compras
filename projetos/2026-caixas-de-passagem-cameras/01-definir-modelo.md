# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

6 caixinhas vedadas, 1 no ponto de cada camera, para abrigar a fonte de 9V e as emendas.

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: muro externo, sol forte; camera C320WS branca.
- Perguntas decisivas respondidas: 6 caixinhas, 1 por camera (lista do Fabio).
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): caixa branca com tampa para fixar a camera; medida interna a confirmar medindo a fonte que veio com a camera.

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Grau de protecao | IP65 | IP66 | muro externo, chuva batendo |
| Espaco interno | cabe fonte 9V plugada + emendas | [VERIFICAR: medir a fonte da C320WS em maos] | a fonte original nao e cortada |
| Entrada de cabo | furo por baixo com vedacao | prensa-cabo | agua nao escorre para dentro |
| Material | plastico com protecao UV | ABS/PVC com UV | sol forte racha plastico comum |
| Fixacao da camera | tampa com furacao para camera bullet | furacao compativel com a base da C320WS [VERIFICAR] | caixinha fica atras da camera e esconde os fios |
| Cor | branca | branca | combina com a camera |
| Quantidade | 6 | 6 | 1 por camera |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Prensa-cabo PG (se a caixa nao trouxer) | recomendado | PG7 ou PG9 conforme o diametro do cabo PP (~8,4 mm) | veda a entrada do cabo | junto |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: caixa de passagem para CFTV, uso externo, IP65 ou mais.
- Alternativas descartadas: caixa de passagem eletrica comum sem vedacao.
- Motivo: fica no tempo e abriga a fonte ligada em 127V.
- Pergunta para o Fabio: qual modelo de caixinha ele costuma usar?

## Requisitos gerados

### Obrigatorios

- Vedacao (borracha) e grau IP65 ou mais
- Cabe a fonte 9V plugada
- 6 unidades

### Desejaveis

- Branca
- Tampa com furacao para camera

### Deal-breakers

- Sem vedacao
- Plastico sem protecao UV
