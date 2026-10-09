# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

Bateria externa de 20.000 mAh para o Galaxy S20 FE com o melhor custo-beneficio. Teto inicial de R$ 200, aceita passar um pouco. Carga rapida de 25W exige USB-PD com PPS.

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: celular Galaxy S20 FE (bateria 4.500 mAh, Super Fast Charging 25W = USB-PD 3.0 com PPS); Huawei Band 11 Pro (carga 5V, consumo irrelevante); preferencia por garantia nacional.
- Perguntas decisivas respondidas: capacidade 20.000 mAh (pedido dele); teto R$ 200 aceitando passar um pouco (09/10/2026) -> teto do projeto R$ 260, elevado para R$ 270 em 09/10/2026; criterio = melhor custo-beneficio, nao o mais potente.
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): uso em bolsa/mochila (viagem, curso em SP, plantao), nao em bolso; nao precisa carregar notebook (IdeaPad Slim 3 e K14 pedem 65W, fora da faixa de preco); 1 aparelho por vez, as vezes 2 (celular + band).

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Capacidade nominal | 20.000 mAh (74 Wh) | 20.000 mAh | pedido dele; rende ~3 cargas do S20 FE (4.500 mAh, ~60-65% de eficiencia real) [inferencia] |
| Saida USB-C | USB-PD 3.0, 25W | PD 3.0 30W | 25W e o teto do S20 FE; 30W da folga e e o padrao atual da faixa |
| PPS na porta USB-C | obrigatorio, faixa cobrindo ~9-10V/2,5-3A | PPS 3,3-11V/3A | sem PPS o S20 FE cai para ~15W; e o que separa "carga rapida" de "super rapida" no Samsung |
| Entrada (recarga da bateria) | USB-C PD 18W | USB-C PD 30W | 20.000 mAh a 18W leva ~5h; a 30W ~3h |
| Portas | 1 USB-C + 1 USB-A | 2 USB-C + 1 USB-A | carregar celular e band juntos |
| Peso | ate 450 g | ~350 g | vai na bolsa; acima disso incomoda [inferencia] |
| Certificacao | Anatel no anuncio | Anatel + marca com ficha oficial | lei exige; capacidade falsa e golpe comum |
| Garantia | 12 meses | 18-24 meses nacional | preferencia do perfil |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Cabo USB-C/USB-C | obrigatorio (se nao vier embutido nem na caixa) | 3A (60W), USB 2.0 basta | PPS exige cabo C-C; cabo USB-A para C nao faz PD/PPS | junto |
| Carregador de parede para a bateria | dispensavel | PD 25W+ | o carregador 25W do S20 FE (se ele tiver) recarrega a bateria [VERIFICAR se tem] | - |
| Capa/estojo | dispensavel | - | - | - |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: power bank 20.000 mAh com PD 3.0 + PPS 25-30W, de marca com ficha oficial (Anker, Ugreen, Baseus, Samsung, Xiaomi).
- Alternativas descartadas: Baseus Bipow2 Pro 22,5W (sem PPS na ficha: S20 FE fica em ~15W); power bank 45W/65W para notebook (preco fora da faixa); 10.000 mAh (ele pediu 20.000).
- Motivo: no S20 FE quem define a velocidade e o PPS, nao a potencia nominal; acima de 30W ele nao aproveita.

## Requisitos gerados

### Obrigatorios

- 20.000 mAh nominal
- USB-C com PD 3.0 e PPS, 25W ou mais
- Anatel
- Vendedor com historico; terceiro aceito (decisao de 09/10/2026), de preferencia com envio pela Amazon

### Desejaveis

- 30W, 2 portas USB-C, recarga em 30W
- Cabo embutido
- Display de porcentagem
- Garantia nacional 18 meses ou mais

### Deal-breakers

- Ficha sem PPS ou sem protocolos detalhados
- Marca desconhecida / capacidade "100.000 mAh" e afins
- Vendedor sem historico ou fora do envio pela Amazon
