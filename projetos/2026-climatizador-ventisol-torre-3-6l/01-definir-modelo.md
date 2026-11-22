# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

Analisar custo-beneficio do Climatizador Ventisol Torre 3,6L (CLIT3.6-01/02, link TikTok Shop enviado pela Esdra a R$ 330,01) comparado a ventilador torre, CLIN16 e concorrentes na faixa.

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: região de Araçatuba/Guararapes/Valparaíso (interior de SP, clima quente com sol forte, estiagem seca e chuvas de verão úmidas); tensão padrão 127 V (220 V só em ponto específico); compra online com entrega no interior (frete e devolução contam); preferência por garantia nacional e rede de assistência local.
- Perguntas decisivas respondidas: ainda em aberto ([VERIFICAR: cômodo e m², uso por horas/dia, tensão exata da tomada, se a Esdra quer umidificar/aromatizar ou só ventilar, e orçamento máximo]).
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): comparação base em **127 V** (padrão da casa segundo `config/perfil.yaml`), uso doméstico em quarto ou escritório pequeno (até 12 a 15 m²), 8 h/dia, tarifa residencial CPFL Paulista (~R$ 0,87/kWh com impostos). As variantes 220 V também foram levantadas para referência caso o ponto seja 220 V.

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Tensao eletrica | 127 V ou 220 V exata na embalagem | 127 V (padrão da casa, salvo ponto 220 V) | Aparelhos nao sao bivolt; "110V" no TikTok Shop gera risco de erro |
| Tipo de aparelho | Ventilador torre (se o clima estiver úmido) ou climatizador evaporativo | Climatizador com tanque removivel ou ventilador torre silencioso | Em chuva de verão úmida, climatizador satura o ar fechado e abafa; no seco, umidifica bem |
| Capacidade do tanque | 3,5 L (5 a 8 h) | 4,5 L a 8,5 L removível (ou 16 L com dreno se não precisar de silêncio) | 3,6 L do CLIT3.6 tem relato de braçadeira no tanque dificultando limpeza |
| Controle e timer | Botões físicos | Controle remoto + timer 7 h a 12 h | Uso noturno sem precisar levantar da cama; CLIT3.6 e CLIN16 não têm controle |
| Potencia / Consumo | Até 130 W | 60 a 100 W | 75 W custa ~R$ 15,66/mês em 8 h/dia (~R$ 0,87/kWh), contra ~R$ 27,14/mês em 130 W |
| Ruido | Aceitável em vel. 1 e 2 | Silencioso em vel. 1 e 2 | CLIN16 (130 W) tem relato de 62 dB na velocidade mínima |
| Garantia e suporte | 12 meses nacional com NF-e | 12 meses + posto autorizado na região | Ventisol tem posto em Guararapes, Araçatuba e Birigui |

## Acessorios

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Blocos de gelo reutilizaveis (gelol) | recomendado | 2 placas compactas que caibam no reservatório | CLIT3.6 não vem com blocos de gelo; água em temperatura ambiente refresca pouco | junto ou mercado local |
| Sabão neutro / vinagre branco | obrigatorio | Limpeza semanal de tanque e colmeia | Evita lodo, bactérias e cheiro de mofo na colmeia | em casa |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: comparação direta entre o alvo **Ventisol CLIT3.6-01 (127V)**, o ventilador torre **Ventisol Fênix 75W**, o **Ventisol CLIN16-01 16L**, e 3 concorrentes de mercado (**Midea Liva AKAF1**, **WAP Control Digital Torre 8,5L**, **Mondial Flash Air CL-03**).
- Alternativas descartadas: modelos industriais/comerciais (35 L a 125 L, acima de R$ 600 e ruidosos para quarto/sala pequena) e Britânia BCL05FI (subiu para R$ 687,14 no Magalu/Zoom, nota 3,9 em 342 aval., fora da faixa).
- Motivo: responder objetivamente se o CLIT3.6 a R$ 330,01 no TikTok Shop vale a pena ou se há opção melhor pelo mesmo valor ou pouco mais.

## Requisitos gerados

### Obrigatorios

- Tensão exata confirmada (127 V padrão ou 220 V se for ponto específico)
- Garantia nacional de 12 meses com NF-e

### Desejaveis

- Controle remoto e timer programável
- Reservatório de fácil higienização (removível ou sem braçadeiras)
- Compartimento de gelo / blocos térmicos inclusos
- Baixo ruído em velocidades 1 e 2
- Rede de assistência técnica na região

### Deal-breakers

- Compra sem confirmar tensão real (127 V x 220 V)
- Preço acima das lojas grandes (Amazon / Magalu) para o mesmo vendedor
- Expectativa de substituir ar-condicionado em cômodo grande ou úmido
