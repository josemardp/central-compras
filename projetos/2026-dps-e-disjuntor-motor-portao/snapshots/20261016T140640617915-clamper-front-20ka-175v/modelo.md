# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

DPS e disjuntor bipolar para o circuito proprio do motor em 220V.

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: regiao com tempestade; central do motor com inversor.
- Perguntas decisivas respondidas: motor em 220V, com DPS e disjuntor proprio (Josemar, 21/09).
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): o 220V da casa e fase-fase (duas fases de 127V). Nesse caso o disjuntor e bipolar e vai 1 DPS por fase, com tensao para 127V fase-terra (ex.: 175V). Se o 220V for fase-neutro, muda para disjuntor + DPS de 275V [VERIFICAR com Fabio antes de comprar].

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Disjuntor | bipolar 10 A | bipolar 10 A curva C, padrao DIN, INMETRO | protege o cabo PP 1,5 mm2 e o motor |
| DPS: classe | classe II | classe II | protecao no quadro da casa |
| DPS: tensao (Uc) | conforme o sistema | 175V por fase se 220V fase-fase; 275V se fase-neutro | DPS errado nao protege ou queima |
| DPS: corrente | 20 kA | 20 kA nominal / 40 kA maxima | padrao residencial |
| DPS: quantidade | 1 por condutor vivo | 2 (fase-fase) | depende do sistema |
| Certificacao | INMETRO | marca conhecida (Steck, Schneider, WEG, Clamper) | item de seguranca |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Espaco no quadro (trilho DIN) | obrigatorio | 2 polos para o disjuntor + 2 para os DPS | sem espaco, precisa de quadro auxiliar | verificar com Fabio |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: disjuntor bipolar 10 A curva C + 2 DPS classe II (tensao conforme o sistema).
- Alternativas descartadas: ligar o motor em tomada/circuito compartilhado.
- Motivo: circuito proprio e protecao da central contra surto.

## Requisitos gerados

### Obrigatorios

- INMETRO
- Tensao do DPS correta para o sistema da casa

### Desejaveis

- Marca conhecida
- DPS com indicador de fim de vida

### Deal-breakers

- Comprar DPS antes de confirmar se o 220V e fase-fase ou fase-neutro
