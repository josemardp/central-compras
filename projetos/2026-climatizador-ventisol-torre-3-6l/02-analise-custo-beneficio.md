# Analise de Custo-Beneficio: Climatizador Ventisol Torre 3,6 L (CLIT3.6)

Data da coleta: **21/11/2026** (preço do TikTok Shop informado pelo Josemar em **20/11/2026**).
Todo dado sem confirmação direta ou oficial está marcado como `[VERIFICAR]`.

## 1. Ficha tecnica: fonte oficial x anuncio do TikTok Shop

- **Situação das fontes oficiais da Ventisol:**
  - O catálogo comercial direto (`ventisol.com.br`) e o portal de assistência (`assistencia.ventisol.com.br`) **não listam o modelo CLIT3.6** em páginas abertas; os links públicos de "Catálogo de Produtos" e "Download de Materiais" no site da Ventisol apontam para pastas do Google Drive que exigem login Google, de modo que **não há manual PDF aberto na web** para conferir decibéis (dB) e vazão (m³/h) `[VERIFICAR com o SAC da Ventisol: (48) 2107-9500 ou sac@ventisol.com.br]`.
  - Contudo, o **próprio vendedor do anúncio no TikTok Shop** ("Melhor Para Você" / Tech Shop) publica a ficha técnica do SKU `CLIVEN00022` (EAN `7898461978357`) no seu site oficial (`melhorparavoce.com.br`) e na Amazon (`B0GDS18VY4` / `B0GDS88TNP`), permitindo cruzar todas as divergências:

| Item | Anúncio TikTok Shop (20/11) | Ficha do produto (Amazon + Melhor Para Você) | Divergência / Risco |
|---|---|---|---|
| Código e Tensão | Opção "110V" | `CLIT3.6-01` (127 V) e `CLIT3.6-02` (220 V). Não é bivolt. | **Risco:** chamar de "110V" sem exibir o código exato (-01/-02) pode confundir quem precisa de 220 V ou gerar envio errado. |
| Reservatório | 3,6 L (um campo diz 3 L) | 3,6 litros | Provável arredondamento/limite útil abaixo da borda no campo secundário; capacidade nominal é 3,6 L. |
| Controle remoto | Não cita | Não acompanha ("Conteúdo da embalagem: 1 Climatizador, Manual, Certificado de garantia"). | **Confirmado sem controle remoto** (operação só no aparelho). |
| Potência / Consumo | 75 W | 75 W | Confirmado. |
| Área recomendada | 20 a 30 m² | 20 a 30 m² | Marketing otimista (na prática refresca no jato direto a 1,5–2 m). |
| Dimensões e peso | 996 x 235 x 220 mm; 5,2 kg | 996 x 235 x 220 mm; 5,2 kg líq. / 6,2 kg bruto | Confirmado. |
| Ruído (dB) e vazão | "Silencioso" | Não informa dB nem m³/h | `[VERIFICAR no manual/etiqueta da caixa]` |
| Garantia e origem | 12 meses, nacional, lançamento 2025 | 12 meses, produto nacional, lançamento 2025 | Confirmado. |

## 2. Eficacia real (3,6 L no clima da regiao e tamanho do comodo)

- **Clima do contexto (`config/perfil.yaml`):** região de Araçatuba/Guararapes/Valparaíso (interior de SP) tem calor forte o ano quase todo, mas alterna **estiagem seca** (outono/inverno) com **período quente e úmido de chuvas de verão** (primavera/verão, época atual).
- **Redução de temperatura real:** climatizador evaporativo é limitado pela temperatura de bulbo úmido.
  - Em **clima seco e quente**, a queda típica na saída de ar é de **5 °C a 12 °C** (referências técnicas ClimaBrisa / TopClima), aliviando bem quem está no fluxo direto.
  - Em **clima úmido (dias chuvosos de verão)**, a evaporação cai e a redução fica em **2 °C a 4 °C** (ou quase imperceptível). Em ambiente fechado e úmido, o aparelho injeta mais vapor d'água e **deixa o cômodo abafado**, passando a funcionar apenas como um ventilador mais fraco. Exige porta ou janela entreaberta para renovar o ar.
- **Tamanho do cômodo e autonomia:**
  - Não resfria uma sala de 20 a 30 m² inteira como ar-condicionado. Relatos reais de compradores do `CLIT3.6` (Amazon) confirmam bom efeito em espaço pequeno ou perto do usuário (até 2–3 m no nível 3), e queixa de baixa eficácia quando se espera resfriamento do ambiente todo.
  - **Autonomia:** o fabricante não publica taxa de evaporação em L/h (`[VERIFICAR no manual]`). Na prática da categoria (3,2 a 4,5 L), relatos de usuários indicam cerca de **5 a 8 horas** por abastecimento em velocidade baixa/média (exigindo reabastecimento diário). O `CLIT3.6` não vem com blocos de gelo dedicados (`Ice Box`), diferente do WAP, Midea e Mondial.

## 3. Comparacao tecnica e de mercado (base 127 V)

| Modelo | Tipo | Preco visto 127V (menor loja) | Preco 220V (ref.) | Potencia | Reservatorio | Controle remoto / Timer | Ruido | Garantia | Nota (avaliacoes) |
|---|---|---|---|---|---|---|---|---|---|
| **Ventisol CLIT3.6-01** | Climatizador torre | **R$ 302,17** Magalu/Zoom; **R$ 315,90** Amazon Pix (`R$ 330,01` TikTok) | R$ 344,00 Amazon Pix | 75 W | 3,6 L (preso c/ bracadeira) | Nao / Nao | Silencioso vel. 1-2 (sem dB; barulho de agua) | 12 meses nacional | **4,2** (45 Amazon 127V) / 4,7 (128 TikTok) |
| **Ventisol Fênix 75W** | Ventilador torre (sem agua) | **R$ 245,98** Amazon Pix (`R$ 377,90` TikTok) | R$ 329,00 Melhor Para Voce | 75 W | Sem agua | **Sim / Timer 12h** | Muito silencioso (relatos) | 12 meses nacional | **4,9** (26 Amazon) |
| **Ventisol CLIN16-01** | Climatizador portatil | **R$ 379,90** Amazon (`R$ 424,46` TikTok) | R$ 358,93 Amazon Pix | 130 W | **16,0 L** (c/ gelo) | Nao / Nao | Barulhento (~62 dB na minima, relato) | 12 meses nacional | **4,2** (1.203 Amazon 127V) / **4,4** (1.452 em 220V) |
| **Midea Liva AKAF1** | Climatizador portatil | **R$ 404,11** Amazon Pix | R$ 404,10 WebContinental / R$ 521,55 Amazon | **60 W** | **4,5 L util / 7 L** (removivel + 2 gelos) | **Sim / Timer 7h** | Silencioso vel. 1; normal vel. 3 | 12 meses nacional | **4,6** (**8.193** Amazon 127V) |
| **WAP Clima Control Digital** | Climatizador torre | **R$ 429,90** Amazon | R$ 398,90 Magalu/Zoom / R$ 458,10 Amazon | 100 W | **8,5 L** (~5 L uteis + 2 gelos) | **Sim / Timer 12h** | Silencioso vel. 1-2; vento forte vel. 3 | 12 meses nacional | **4,4** (937 Amazon 127V) |
| **Mondial Flash Air CL-03** | Climatizador portatil | **R$ 386,90** Amazon | R$ 251,91 Zoom / R$ 279,90 Amazon | 80 W | 3,2 L (+ 2 tubos gelo) | **Sim / Timer 7h30** | Barulho moderado/audivel | 12 meses nacional | **4,2** (2.392 Amazon 127V) |

## 4. Pesquisa de precos do CLIT3.6 e checagem da ancora (-26%)

1. **Magazine Luiza (via Zoom e Buscapé, 21/11/2026):** **R$ 302,17** à vista (ou 6x R$ 53,01) — frete/tensão exata `[VERIFICAR no checkout da Magalu]`.
2. **Amazon (`B0GDS18VY4` 127V, 21/11/2026):** **R$ 315,90** no Pix (10% off) / R$ 351,00 em 7x s/ juros, entrega grátis exibida na página, **Vendido por FULL MELHOR PARA VOCE e Enviado por Amazon**. Versão 220V (`B0GDS88TNP`): **R$ 344,00** Pix / R$ 362,11 em 7x.
3. **TikTok Shop ("Melhor Para Você", visto pelo Josemar em 20/11/2026):** **R$ 330,01** ("de R$ 445,90, -26%"), opção "110V", frete `[VERIFICAR no app]`.
4. **Site próprio Melhor Para Você (`melhorparavoce.com.br`, 21/11/2026):** **R$ 339,00** preço normal (6x R$ 56,50; promessa de 5% no Pix no site = ~R$ 322,05), frete `[VERIFICAR]`.
5. **Outras lojas verificadas:** KaBuM sem estoque do CLIT3.6; Mercado Livre bloqueia leitura automática (HTTP 403) `[VERIFICAR no app do ML]`; Casas Bahia e Leroy Merlin sem anúncio indexado aberto `[VERIFICAR]`.

- **O "-26%" é real?** **Não.** O próprio vendedor cobra **R$ 339,00** sem promoção em seu site oficial e **R$ 315,90** no Pix na Amazon FBA. A âncora de R$ 445,90 está inflada; o TikTok Shop está R$ 14,11 mais caro que a Amazon Pix e R$ 27,84 mais caro que o Magalu (Zoom).
- **Histórico de preço:** Zoom/Buscapé ainda não exibem gráfico histórico de 40 dias/6 meses para o CLIT3.6 (lançamento recente); Promobit não registrou ofertas anteriores. O piso observado hoje é **R$ 302,17** (Magalu) / **R$ 315,90** (Amazon 127V).

## 5. Custo mensal de energia

- Distribuidora da região (Araçatuba/Guararapes/Valparaíso): **CPFL Paulista** `[VERIFICAR se a unidade consumidora é CPFL Paulista ou Elektro e conferir tarifa exata na conta de luz]`.
- Referência ANEEL 2026 (Resolução 3.579/2026, bandeira verde): tarifa residencial B1 base ~R$ 0,7395/kWh; com tributos (ICMS, PIS/COFINS), média efetiva **~R$ 0,84 a R$ 0,89/kWh** (usado **R$ 0,87/kWh** abaixo).
- **Cálculo para o CLIT3.6 e Fênix (75 W = 0,075 kW):**
  - 4 h/dia × 30 dias = **9,0 kWh/mês** (~**R$ 7,83/mês**)
  - 8 h/dia × 30 dias = **18,0 kWh/mês** (~**R$ 15,66/mês**)
  - 12 h/dia × 30 dias = **27,0 kWh/mês** (~**R$ 23,49/mês**)
- Comparativo em 8 h/dia: Midea AKAF (60 W) = 14,4 kWh/mês (~R$ 12,53); Mondial CL-03 (80 W) = 19,2 kWh/mês (~R$ 16,70); WAP (100 W) = 24,0 kWh/mês (~R$ 20,88); CLIN16 (130 W) = 31,2 kWh/mês (~R$ 27,14).

## 6. Confiabilidade, reclamacoes e assistencia tecnica local

- **Ventisol no Reclame Aqui (01/05/2026 a 31/10/2026):** Selo **RA1000**, nota RA **9,0/10** (consumidor 8,31), 450 reclamações, **100% respondidas**, **93,3% resolvidas**, **83,2% voltariam a fazer negócio**, 5º lugar em Eletrodomésticos.
- **Avaliações críticas reais do CLIT3.6 (Amazon):**
  - 1★ (127V): *"estou DEVOLVENDO o produto porque a BOMBA não funciona, ou seja, não climatiza, estou só na função ventilação."*
  - 3★ (127V): *"a eficácia ficou a desejar... não refresca o ambiente, nem mesmo estando próximo."*
  - 3★ (220V): *"A base é solta e, talvez por isso, o ventilador fica meio instável e pode cair com muita facilidade... após 3 meses da compra, parou de funcionar e está na assistência."*
  - 4★ (220V): *"o reservatório que pra você tirar, tem que cortar as braçadeiras, muito chato isso."*
- **Assistência técnica autorizada oficial Ventisol (consultada em `assistencia.ventisol.com.br` em 21/11/2026 para Climatizadores Residenciais):**
  - **Guararapes:** **WL Segurança Eletrônica** (Prudente de Moraes, nº 1050, Centro, Tel: `(18) 3606-4939`).
  - **Araçatuba:** **MVM Máquinas Eletrodomésticos** (Av. Governador Mario Covas, nº 2625, São João, Tel: `(18) 3301-6249` / `(18) 98191-5455`).
  - **Birigui:** **Central Eletrodomésticos** (Rua Pedro Alvares Cabral, nº 395, Centro, Tel: `(18) 3643-7329` / `3641-1867`) e **EDB Eletrodomésticos** (Rua Tupi, nº 384, Centro, Tel: `(18) 3644-0500`).
  - **Valparaíso:** 0 postos cadastrados (usar Guararapes ou Araçatuba).

## 7. Risco do vendedor "Melhor Para Você" e do TikTok Shop

- **Identidade e reputação:** "Melhor Para Você" é a marca de varejo da **Tech Shop.com.br Comércio e Serviços de Informática Ltda** (CNPJ `08.351.293/0001-63`, Belo Horizonte-MG, `melhorparavoce.com.br`). No **Reclame Aqui** (01/05/2026 a 31/10/2026): **Selo RA1000**, nota **8,9/10**, 143 reclamações, **100% respondidas**, **93,6% resolvidas**, 78,2% voltariam a fazer negócio, 2º lugar em Eletroeletrônicos E-commerce. É empresa legítima.
- **Onde está o risco:** **36,04% das reclamações da Melhor Para Você no Reclame Aqui são de atraso na entrega** (pedidos via marketplace). No TikTok Shop, a política prevê devolução em até 30 dias corridos após entrega (7 dias legais de arrependimento CDC), com 14 dias para postagem reversa, e **a garantia após esse prazo é responsabilidade do vendedor/fabricante** (NF-e obrigatória).
- **Por que não comprar no TikTok Shop:** o **mesmo vendedor** ("FULL MELHOR PARA VOCE") vende o **mesmo aparelho 127 V** na **Amazon** (`B0GDS18VY4`) com **envio pela própria Amazon (FBA)**, entrega rastreável, devolução estendida até **31/01/2027** e preço **menor** (R$ 315,90 Pix x R$ 330,01).

## 8. Manutencao e pecas de reposicao

- **Rotina:** trocar a água a cada 1 a 2 dias; antes de desligar/guardar, rodar **5 a 10 minutos apenas na ventilação** para secar a colmeia e evitar mofo/mau cheiro; lavar reservatório e colmeia semanalmente com água e sabão neutro (ou água + vinagre branco 50/50 se surgir odor); nunca acionar a bomba sem água.
- **Dificuldade específica do CLIT3.6:** relato de necessidade de soltar/cortar braçadeiras para retirar o reservatório, tornando a limpeza mais trabalhosa que em modelos com gaveta removível (Midea AKAF).
- **Peças de reposição:** bombas e colmeias de modelos grandes da Ventisol (45L–70L) custam R$ 70 a R$ 260 no varejo, mas **não há venda avulsa catalogada em aberto para colmeia ou bomba do CLIT3.6** (`[VERIFICAR preço e disponibilidade com o SAC Ventisol]`).

## Fontes acessadas (21/11/2026)

- TikTok Shop (redirect resolvido): https://www.tiktok.com/view/product/1734131787988436616 (link original: https://vt.tiktok.com/ZS9PjTqcunMAX-8shI1/)
- Amazon CLIT3.6 127V: https://www.amazon.com.br/dp/B0GDS18VY4
- Amazon CLIT3.6 220V: https://www.amazon.com.br/dp/B0GDS88TNP
- Amazon Ventisol Fênix 75W 127V: https://www.amazon.com.br/dp/B0GD8QWCVG
- Amazon Ventisol CLIN16-01 127V: https://www.amazon.com.br/dp/B0CCBGXKLP
- Amazon Ventisol CLIN16-02 220V: https://www.amazon.com.br/dp/B0CCBVWFTC
- Amazon Midea Liva AKAF1 127V: https://www.amazon.com.br/dp/B08377D9YS
- Amazon Midea Liva AKAF2 220V: https://www.amazon.com.br/dp/B08SYC1QQF
- Amazon WAP Control Digital 127V: https://www.amazon.com.br/dp/B0DQ2D4DZG
- Amazon Mondial Flash Air CL-03 127V: https://www.amazon.com.br/dp/B07XQR2WNZ
- Amazon Mondial Flash Air CL-03 220V: https://www.amazon.com.br/dp/B07XQR5LR6
- Melhor Para Você (CLIT3.6 JSON oficial): https://www.melhorparavoce.com.br/products/ventilador-torre-climatizador-ventisol-clit-abastece-3-6-litros-5-em-1-silencioso
- Zoom CLIT3.6 / CLIN16 / Midea / Mondial / WAP: https://www.zoom.com.br/search?q=climatizador%20ventisol%20torre%203%2C6
- Buscapé CLIT3.6: https://www.buscape.com.br/search?q=climatizador+ventisol+torre+3%2C6
- KaBuM Ventisol: https://www.kabum.com.br/busca/climatizador-ventisol
- Ventisol Assistência Técnica: https://assistencia.ventisol.com.br/
- Reclame Aqui Ventisol: https://www.reclameaqui.com.br/empresa/ventisol/
- Reclame Aqui Melhor Para Você: https://www.reclameaqui.com.br/empresa/melhor-para-voce/
- Tarifa CPFL Paulista 2026 (via busca web ANEEL Res. 3.579/2026 / Electy / Calculadoradomundo) e política TikTok Shop Brasil (via busca web)
