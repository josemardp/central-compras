# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

Fotocelula anti-esmagamento para o portao de correr, ligada na central Triflex do motor PPA.

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: motor PPA DZ Rio 500 Jetflex com central Triflex.
- Perguntas decisivas respondidas: fotocelula sim (Josemar, 21/09).
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): modelo REFLETIVO, porque so precisa de fio de um lado do portao; o modelo de par (emissor + receptor) exige cabo atravessando a entrada [VERIFICAR com Fabio se ja existe conduite do outro lado].

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Tipo | refletiva (unidade + refletor) | PPA F10-R | fio so de um lado; compativel com a Triflex |
| Alcance | maior que a largura da passagem | 10 m ou mais [VERIFICAR na ficha] | portao de ~4 m |
| Compatibilidade | entrada de fotocelula da central Triflex | mesma marca do motor (PPA) | instalacao sem adaptacao |
| Protecao | uso externo | caixa vedada | fica exposta ao tempo |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Cabo da fotocelula ate a central | obrigatorio | cabo de sinal/alimentacao indicado no manual [VERIFICAR com Fabio] | liga a fotocelula na central | junto, se o Fabio nao tiver |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: fotocelula refletiva PPA F10-R.
- Alternativas descartadas: par emissor-receptor (exige cabo dos dois lados).
- Motivo: seguranca contra esmagamento com instalacao simples.

## Requisitos gerados

### Obrigatorios

- Compativel com a central PPA Triflex
- Uso externo

### Desejaveis

- Mesma marca do motor (PPA)

### Deal-breakers

- Fotocelula sem compatibilidade confirmada com a Triflex
