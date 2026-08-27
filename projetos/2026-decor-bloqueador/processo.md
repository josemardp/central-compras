# Processo da compra

## Estado atual

- Estado: pesquisando
- Proxima acao: confirmar manualmente preco, frete, estoque, vendedor e garantia dos finalistas
- Decisao aberta: Viapol Viaplus 1000 18 kg lidera a pesquisa web, mas ainda nao fecha compra sem cotacao manual.

## Linha do tempo decisoria

| Data | Etapa | Decisao | Por que |
|---|---|---|---|
| 2026-08-27 | cotacao | Cotacao registrada para sikatop-107 | Superpro Atacado / fonte=web / custo_total=779.7 |
| 2026-08-27 | cotacao | Cotacao registrada para viaplus-1000 | LPK Home Center / fonte=web / custo_total=359.97 |
| 2026-08-27 | cotacao | Cotacao registrada para viaplus-1000 | Elos Cimento / fonte=web / custo_total=192.9 |
| 2026-08-27 | produto | Candidato registrado: Sika SikaTop 107 Cinza 18 kg | id=sikatop-107 |
| 2026-08-27 | produto | Candidato registrado: Viapol Viaplus 1000 18 kg | id=viaplus-1000 |
| 2026-08-27 | descarte | Descartado igolflex-fachada-36 | Mesma limitacao do Vedapren: pintura acrilica para fachada, pressao positiva. A propria Sika separa a linha Igolflex Fachada da linha SikaTop, que e a indicada para negativa. |
| 2026-08-27 | descarte | Descartado vedapren-parede-36 | Membrana acrilica de face positiva. Nao resiste a contrapressao: descola sob umidade negativa. A ficha do fabricante posiciona o produto contra batida de chuva na fachada, nao contra agua empurrando por tras. |
| 2026-08-27 | modelo | Classe correta: argamassa polimerica / cimenticio cristalizante. Membrana acrilica esta fora | Tinta acrilica de fachada (Vedapren, Igolflex) so trabalha sob pressao positiva: sob contrapressao a agua empurra por tras do filme e ela bolha e descola. Para negativa o sistema tem que ser cimenticio, que cristaliza dentro do substrato em vez de formar pelicula sobre ele. |
| 2026-08-27 | modelo | Requisito corrigido: o produto tem que bloquear umidade NEGATIVA (contrapressao) | Josemar corrigiu o escopo. Umidade negativa e quando a agua empurra pela face oposta a que recebe o produto: trata-se por dentro porque a face externa nao esta acessivel. Isso muda a classe do produto, nao so o modelo. |
| 2026-08-27 | cotacao | Normalizar todas as cotacoes para o mesmo servico: 15 m2 tratados | Comparar preco de embalagem esconde o rendimento, que e justamente onde o Block Total perde. Com tudo em 15 m2 a conta fica: Igolflex R$ 145,90, Vedapren R$ 193,80 e Block Total R$ 1.139,97. |
| 2026-08-27 | cotacao | Tratar o preco de R$ 69,89 do Igolflex na Redemac como suspeito, nao como preco de referencia | Mesma embalagem sai a R$ 145,90 na Casa Falci. As duas lojas estao SEM ESTOQUE. Spread de 2x com ruptura nos dois lugares sugere preco velho na pagina, nao oportunidade. O preco realista de comparacao e o de R$ 145,90. |
| 2026-08-27 | cotacao | Cotacao registrada para igolflex-fachada-36 | Casa Falci / fonte=web / custo_total=145.9 |
| 2026-08-27 | cotacao | Cotacao registrada para vedapren-parede-36 | Tosel Materiais de Construcao / fonte=web / custo_total=202.4 |
| 2026-08-27 | cotacao | Cotacao registrada para decor-bloqueador | Loja Decor Colors / fonte=web / custo_total=1139.97 |
| 2026-08-27 | cotacao | Cotacao registrada para igolflex-fachada-36 | Redemac / fonte=web / custo_total=69.89 |
| 2026-08-27 | cotacao | Cotacao registrada para vedapren-parede-36 | Joli Materiais de Construcao / fonte=web / custo_total=193.8 |
| 2026-08-27 | produto | Candidato registrado: Sika Igolflex Fachada Branco 3,6 L | id=igolflex-fachada-36 |
| 2026-08-27 | produto | Candidato registrado: Vedacit Vedapren Parede Branco 3,6 kg | id=vedapren-parede-36 |
| 2026-08-27 | modelo | Rendimento vira criterio de corte: 12 kg para 5 m2 e caro para 5-15 m2 | A R$ 379,99 por 5 m2, o Block Total sai a R$ 76/m2. Para 15 m2 seriam 3 embalagens, cerca de R$ 1.140 so na face interna. Precisa comparar custo por m2 com impermeabilizante acrilico de fachada antes de fechar. |
| 2026-08-27 | modelo | Separar a compra em duas frentes: vedacao da face externa (causa) e bloqueio da face interna (sintoma) | O problema confirmado e infiltracao externa. Bloqueador aplicado so por dentro retem a agua dentro da alvenaria e tende a descolar; a vedacao precisa comecar pela face que recebe a chuva. O Block Total continua candidato, mas para a face interna e so depois do tratamento externo. |
| 2026-08-27 | modelo | Uso confirmado pelo comprador: impermeabilizacao | Josemar confirmou que a compra e para impermeabilizar. Isso fecha a duvida entre impermeabilizante, fundo preparador e antimofo: o candidato Block Total segue valido como linha de pesquisa. |
| 2026-08-27 | cotacao | Cotacao registrada para decor-bloqueador | Loja Decor Colors / fonte=web / custo_total=379.99 |
| 2026-08-27 | modelo | Tratar como impermeabilizante para umidade em parede/rodape antes de comparar preco | A busca indica Block Total Decor Colors, 12 kg, rendimento aproximado de 5 m2; preciso confirmar se o problema real e umidade ascendente/infiltracao e se a superficie aceita o produto. |
| 2026-08-27 | produto | Candidato registrado: Impermeabilizante Block Total Decor Colors | id=decor-bloqueador |
| 2026-08-27 | produto | Candidato registrado: Decor Bloqueador | id=decor-bloqueador |
| 2026-08-27 | abertura | Compra criada | Necessidade registrada no briefing |

## Etapas

- [x] 1. Definir o modelo certo para a necessidade
- [x] 2. Mapear candidatos
- [x] 3. Registrar produtos em `produtos/`
- [x] 4. Coletar cotacoes iniciais
- [x] 5. Aplicar gates eliminatorios
- [x] 6. Comparar finalistas
- [ ] 7. Confirmar preco/frete/estoque manualmente
- [ ] 8. Registrar decisao e por que os outros perderam
- [ ] 9. Comprar
- [ ] 10. Fazer veredito D+30
- [ ] 11. Fazer veredito D+180

## O que ja sei

- O requisito e umidade NEGATIVA: a agua vem do outro lado e o produto vai na
  face oposta, porque a face que recebe a agua nao esta acessivel.
- Isso separa a compra em duas classes, e so uma serve. Membrana acrilica
  (Vedapren, Igolflex) trabalha sob pressao positiva e descola sob
  contrapressao. Sistema cimenticio (Viaplus, SikaTop, Block Total) cristaliza
  dentro do substrato e e o que resiste a negativa.
- A area fica entre 5 e 15 m2. Todas as cotacoes foram normalizadas para 15 m2,
  o pior caso, para que o rendimento entre na comparacao.
- Custo por m2 tratado entre os cimenticios: Viaplus 1000 de R$ 13 a R$ 24,
  SikaTop 107 cerca de R$ 52, Block Total cerca de R$ 76.
- Viaplus e SikaTop sao cinza e pedem revestimento por cima. Block Total serve
  como acabamento e aceita pintura a base de agua. Essa e a unica vantagem
  real do Block Total no conjunto.
- Viaplus e SikaTop sao bicomponentes, com risco de erro de traco na obra.
  Block Total e monocomponente.
- Consumo muda com o regime. No Viaplus: 2 a 3 kg/m2 para umidade do solo,
  mas 4 a 5 kg/m2 e 4 a 5 demaos para contrapressao hidrostatica ate 10 mca.
- Avaliacao real so existe para um candidato: Viaplus 1000, 4,9 com 67
  opinioes. O sistema marcou AVAL_SUSPEITA porque nota 4,9 com menos de 150
  avaliacoes e base fina - o alerta esta correto e foi mantido.
- Block Total tem evidencia de uso real, e ela e negativa: tres reclamacoes
  no Reclame Aqui pelo produto nao segurar a umidade, uma delas com retorno
  da mancha em 2 meses e outra com 6 unidades compradas sem resultado. A
  Decor Colors tem nota 6,3 de 10 e 49,6% de quem avaliou voltaria a comprar.

## O que ainda preciso descobrir

- Medida real da area em m2. A conta de quantas embalagens comprar depende
  disso e a faixa 5-15 m2 muda o resultado por um fator de 3.
- Qual regime de consumo se aplica: umidade do solo (2-3 kg/m2) ou
  contrapressao hidrostatica (4-5 kg/m2). Isso quase dobra a quantidade e o
  custo. Depende de haver ou nao coluna d'agua empurrando, nao so umidade.
- Preco real do Viaplus 1000. As cotacoes web vao de R$ 53,50 a R$ 119,99
  pela mesma caixa de 18 kg e nenhuma pagina abriu para confirmar.
- Estado da superficie interna: se tem tinta velha descascando, reboco solto
  ou mofo, entra custo de preparo que nenhuma cotacao cobre ainda.
- Qual acabamento vai por cima do Viaplus ou do SikaTop, que sao cinza. Esse
  custo ainda nao esta em nenhuma cotacao e reduz a vantagem deles sobre o
  Block Total.

## Hipoteses descartadas

| Hipotese | Motivo do descarte |
|---|---|
| Tratar pela face externa com impermeabilizante de fachada | A face externa nao esta acessivel. A compra e de umidade negativa, e por isso Vedapren Parede e Igolflex Fachada sairam. |
| Membrana acrilica sob contrapressao | Trabalha so sob pressao positiva. Sob umidade negativa a agua empurra por tras do filme, que bolha e descola. |
| Block Total como produto principal | Atende o requisito de negativa, mas tem o pior rendimento do conjunto (5 m2 por 12 kg, R$ 76/m2, acima do teto para 15 m2) e reclamacao formal recorrente por nao segurar a umidade. |
| Preco de R$ 69,89 do Igolflex na Redemac como referencia | Mesma embalagem a R$ 145,90 em outra loja e ruptura de estoque nas duas. Candidato descartado depois por motivo tecnico. |
