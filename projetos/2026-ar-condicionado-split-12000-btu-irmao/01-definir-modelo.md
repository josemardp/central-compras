# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

Split hi-wall 12.000 BTU, so frio, inverter, 220V para o irmao do Josemar (Floreal-SP). Instalador e ponto 220V ja existem. Criterio: melhor custo-beneficio entre marcas de qualidade bem avaliadas; referencia LG Dual Inverter. Entrega na casa dele.

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Compra para o irmao do Josemar, casa dele em Floreal-SP (cidade pequena do noroeste paulista; endereco so em dados-privados). Clima quente, uso so de resfriamento. O perfil do Josemar (127V/220V da casa dele) nao se aplica aqui.
- Perguntas decisivas respondidas em 05/10/2026: comodo cabe em 12.000 BTU (ate ~18 m2); so frio; instalador e ponto 220V ja existem; criterio e melhor custo-beneficio entre marcas de qualidade bem avaliadas, referencia LG; entrega na casa dele.
- Suposicoes: tubulacao ate 7,5 m (comprimento sem recarga de gas do LG); instalador do irmao [VERIFICAR se e credenciado da marca escolhida, condicao da garantia estendida nas quatro marcas].

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Capacidade | 12.000 BTU/h | 12.000 BTU/h | Comodo de ate ~18 m2 informado; maior gasta e liga/desliga a toa |
| Tensao | 220 V monofasico | 220 V | Ponto 220V ja existe na casa dele |
| Ciclo | So frio | So frio | Interior quente; quente/frio custa R$ 200 a 300 a mais sem uso |
| Compressor | Inverter (velocidade variavel) | Inverter com rotor duplo ou equivalente | Economia real vem do compressor modulando; "eco" sem inverter nao serve |
| Eficiencia (etiqueta INMETRO) | Classe A, IDRS >= 7,0 Wh/Wh | IDRS >= 7,5 | IDRS e o numero sazonal; classe B/C (IDRS ~5) gasta 25 a 40% mais. Limite de 7,0 para classe A em 2026 [VERIFICAR portaria] |
| Consumo anual | <= 420 kWh/ano | <= 385 kWh/ano | Diferenca de 30 kWh/ano vale ~R$ 30/ano [estimativa, tarifa VERIFICAR]: pesa pouco perto de garantia |
| Gas | R-32 | R-32 | Padrao atual; R-410A e linha velha |
| Serpentina | Cobre | Cobre | Aluminio corroi e e mais dificil de reparar |
| Garantia | 24 meses total + 10 anos compressor, fabricante | 60 meses total + 10 anos compressor | Peca de placa/ventilador e o que mais quebra fora do compressor |
| Assistencia | Autorizada da marca alcanca Floreal | Credenciado em Votuporanga/Rio Preto/Aracatuba | Sem credenciado, garantia estendida nao vale [VERIFICAR por marca] |
| Tubulacao | 1/4" e 3/8" | 1/4" e 3/8" | Bitolas do 12.000 BTU nas fichas LG/Midea; instalador precisa saber |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Kit de instalacao (tubos de cobre 1/4" e 3/8", isolamento, cabo PP, dreno) | obrigatorio | Cobre na bitola do aparelho, comprimento real da obra | Nao vem com o aparelho; instalador do irmao costuma fornecer | instalador |
| Suporte da condensadora | obrigatorio | Suporte para >= 25 kg (condensadora ~19 kg) ou base no piso | Unidade externa pesa ~19 kg | instalador |
| Disjuntor dedicado | obrigatorio | Bipolar 220V, corrente pela ficha (~5,2 A nominal; 10 A tipico) [VERIFICAR com o instalador] | Ponto ja existe; conferir se tem disjuntor proprio | instalador |
| Wi-Fi/app | dispensavel | Ja integrado nos 4 finalistas | Nao paga a mais por isso | - |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: split hi-wall 12.000 BTU so frio inverter 220V, classe A, marcas LG, Midea, Gree, Samsung.
- Alternativas descartadas: Electrolux MaxComfort N12F (classe C, IDRS 5,3, 541 kWh/ano); LG AI Smart Inverter S3-Q12JA31E (classe B, 484,7 kWh/ano); LG Dual Compact S3-Q12JAQAL (484,6 kWh/ano, 1 ano de garantia, mais caro); Elgin, Philco, TCL, Agratto, EOS (fora do criterio "marca de qualidade bem avaliada" e/ou poucas avaliacoes).
- Motivo: garantia e eficiencia filtram mais que preco; entre classe A a diferenca de conta de luz e pequena.

## Requisitos gerados

### Obrigatorios

- 12.000 BTU, 220V, so frio, inverter, classe A (IDRS >= 7,0), R-32, cobre
- Garantia nacional do fabricante com 10 anos no compressor

### Desejaveis

- Garantia total de 60 meses
- IDRS >= 7,5

### Deal-breakers

- Classe B ou pior
- Marca sem assistencia autorizada que atenda Floreal
- Vendedor sem nota fiscal ou anuncio com modelo divergente nas fotos 
