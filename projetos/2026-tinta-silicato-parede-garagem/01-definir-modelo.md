# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

Acabamento mineral de silicato ou sol-silicato, muito aberto ao vapor, para a faixa recuperada da parede umida da garagem (area interna) e do muro externo, ~10 m lineares. Vai sobre reboco de saneamento novo ou reboco mineral firme limpo de sais. Sem selador acrilico. Precisa de ficha tecnica e compatibilidade aprovada pelo fabricante do reboco.

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil: parede de garagem em bloco de seis furos, ~5 m na area interna + ~5 m no muro externo, umidade lateral vinda do terreno vizinho, sem escorrimento relatado (`config/perfil.yaml`).
- Perguntas decisivas respondidas: Josemar escolheu em 17/10 o Caminho A (parede que respira): reboco de saneamento so onde estiver podre + tinta mineral. Quer resiliencia e saida de vapor, nao barrar agua.
- Suposicoes adotadas: area de pintura = faixa recuperada (hipotese 1,40 m x 10 m = 14 m2) [VERIFICAR apos o teste da parede]; cor clara; mesmo produto dentro e fora se a ficha permitir.

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Ligante | Silicato de potassio ou sol-silicato, declarado na ficha | Sol-silicato (silica sol + silicato de potassio) | Reage com base mineral e deixa o vapor sair; ficha KEIM Soldalit |
| Resistencia ao vapor | sd declarado <= 0,1 m (classe V1, EN 1062-1) | sd <= 0,01 m | Reboco de saneamento exige acabamento muito aberto; KEIM pede sd do acabamento < 0,2 m sobre Porosan |
| Teor organico | Declarado na ficha | <= 5% (padrao DIN 18363 2.4.1 para tinta de dispersao-silicato) | Polimero demais vira pelicula e prende vapor e sal [VERIFICAR na ficha do candidato nacional] |
| Uso externo | Indicado para fachada | Fachada e interno | Muro externo pega chuva |
| Compatibilidade | Aprovada por escrito pelo fabricante do reboco escolhido | Tinta do mesmo sistema ou listada na ficha do reboco | Tinta errada anula o reboco de saneamento |
| Consumo | Declarado em kg/m2 ou m2/L | ~0,35 a 0,50 kg/m2 em 2 demaos (Soldalit) | 14 m2 dariam ~5,4 a 7,7 kg com 10% de sobra |
| Ficha tecnica | Obrigatoria, do SKU vendido | Ficha em portugues com ensaios EN/ISO | Criterio de exclusao do Josemar |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Fundo/diluente mineral do mesmo fabricante | Condicional | So o indicado na ficha (ex.: Soldalit-Fixativ na KEIM) | Base muito absorvente; nunca selador acrilico | junto |
| Escova de cerda dura | Obrigatorio | Cerda de nylon ou aco, uso a seco | Remover sal antes de pintar e na manutencao | junto |
| Fita e lona de protecao | Recomendado | Proteger piso, vidro e metal | Silicato mancha vidro, aluminio e pedra | junto |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: tinta de silicato ou sol-silicato com ficha tecnica.
- Alternativas descartadas: acrilica, emborrachada, antimofo, textura acrilica, selador acrilico.
- Motivo: fecham o vapor e seguram sal atras da pelicula; contrariam o Caminho A.
- Candidatos iniciais: KEIM Soldalit (Alemanha, distribuidor BR nao confirmado) e Kroten Ecossilica (fabricante nacional; ficha completa, sd e teor organico [VERIFICAR]).
- Compra depende do projeto principal: so pintar depois do reboco curado e com aprovacao do fabricante do reboco.

## Requisitos gerados

### Obrigatorios

- Ficha tecnica do SKU com ligante, sd/classe de vapor e uso externo.
- Compatibilidade escrita com o reboco escolhido no projeto principal.

### Desejaveis

- Fabricante ou distribuidor no Brasil, com nota fiscal e suporte.
- Teor organico declarado <= 5%.

### Deal-breakers

- Sem ficha tecnica; pelicula acrilica; exigencia de selador acrilico; promessa de zero mofo como argumento principal.
