# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

6 cartoes microSD de alta resistencia, 1 para cada Tapo C320WS, para gravar sem assinatura.

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: 6 Tapo C320WS em 2K gravando 24h.
- Perguntas decisivas respondidas: 6 cartoes, 1 por camera (Josemar, 21/09).
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): 128 GB (cerca de 7 dias de 2K continuo por cartao, estimativa de guia de terceiros), dentro do limite de qualquer fonte da camera.

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Capacidade | 64 GB | 128 GB | cerca de 7 dias de gravacao 2K continua; 256 GB fica no limite de algumas fontes da C320WS |
| Resistencia | High Endurance | High, Max ou Pro Endurance | gravacao continua mata cartao comum |
| Velocidade | Classe 10 / U1 | U3 / V30 | a camera grava a 2 a 4 MB/s; velocidade alta e secundaria |
| Formato | microSDXC | microSDXC | padrao da camera |
| Garantia | nacional | nacional, 2 anos ou mais | troca facil se falhar |
| Vendedor | loja oficial ou vendido pela loja | idem | falsificado e o golpe mais comum nesta categoria |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Leitor de cartao USB | dispensavel | - | a propria camera formata e o app mostra as gravacoes | - |
| Adaptador SD | dispensavel | - | nao usado na camera | - |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: microSDXC 128 GB de alta resistencia (candidatos: SanDisk High Endurance, Samsung PRO Endurance, Kingston High Endurance) [VERIFICAR disponibilidade no Brasil].
- Alternativas descartadas: cartao comum (Ultra/EVO), 256 GB ou mais.
- Motivo: resistencia a gravacao continua importa mais que velocidade.

## Requisitos gerados

### Obrigatorios

- Linha Endurance de marca conhecida
- 128 GB
- Garantia nacional
- Loja oficial ou vendido pela propria loja

### Desejaveis

- Pacote com varias unidades mais barato
- U3/V30

### Deal-breakers

- Marca desconhecida ou preco bom demais
- Vendedor terceiro de marketplace
- Cartao comum (nao Endurance)
