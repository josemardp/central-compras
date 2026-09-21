# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

Disjuntor bipolar 10 A curva C para o circuito proprio do motor em 220V.

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: motor em 220V com circuito proprio.
- Perguntas decisivas respondidas: disjuntor proprio (Josemar, 21/09).
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): 220V fase-fase, entao bipolar [VERIFICAR com Fabio].

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Polos | bipolar | bipolar | 220V fase-fase desliga as duas fases |
| Corrente | 10 A | 10 A curva C | protege o cabo de 1,5 mm2 e o motor |
| Padrao | DIN, INMETRO | marca conhecida (Steck, WEG, Schneider) | item de seguranca |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Espaco no quadro | obrigatorio | 2 polos DIN | sem espaco precisa de quadro auxiliar | verificar com Fabio |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: disjuntor bipolar 10 A curva C.
- Alternativas descartadas: ligar em circuito compartilhado.
- Motivo: circuito proprio do motor.

## Requisitos gerados

### Obrigatorios

- 

### Desejaveis

- 

### Deal-breakers

- 
