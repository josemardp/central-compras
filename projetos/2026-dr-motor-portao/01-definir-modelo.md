# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

Interruptor DR 30 mA exigido pelo manual PPA para alimentar o motor; Tipo A por causa do inversor de frequencia da central Jetflex.

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: motor em 220V com central de inversor (Jetflex).
- Perguntas decisivas respondidas: manual tecnico PPA DZ Rio (P08665 REV1) exige DR de 30 mA.
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): o quadro nao tem DR geral [VERIFICAR com Fabio: se ja houver DR 30 mA geral, este item sai]. Tipo A e recomendacao tecnica (carga com eletronica), nao exigencia do manual.

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Sensibilidade | 30 mA | 30 mA | exigencia do manual PPA |
| Tipo | AC | A | central com inversor pode gerar fuga com componente continua pulsante; o tipo A detecta |
| Polos e corrente | 2P 25 A | 2P 25 A | 220V fase-fase; acima do disjuntor de 6 A |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Espaco no quadro | obrigatorio | 2 polos DIN | junto do disjuntor e dos DPS | verificar com Fabio |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: DR 2P 25 A 30 mA Tipo A (Steck SDR22530A).
- Alternativas descartadas: DR tipo AC.
- Motivo: exigencia do manual + inversor na central.

## Requisitos gerados

### Obrigatorios

- 

### Desejaveis

- 

### Deal-breakers

- 
