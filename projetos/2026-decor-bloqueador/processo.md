# Processo da compra

## Estado atual

- Estado: pesquisando
- Proxima acao: confirmar manualmente preco, frete, estoque, vendedor e garantia dos finalistas
- Decisao aberta: Sika Igolflex Fachada Branco 3,6 L lidera a pesquisa web, mas ainda nao fecha compra sem cotacao manual.

## Linha do tempo decisoria

| Data | Etapa | Decisao | Por que |
|---|---|---|---|
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

- O problema e infiltracao externa, nao umidade ascendente nem mofo de pouca
  ventilacao. Isso muda o lado da parede que recebe o produto.
- A area fica entre 5 e 15 m2. Todas as cotacoes foram normalizadas para 15 m2,
  o pior caso, para que o rendimento entre na comparacao.
- Impermeabilizante acrilico de fachada custa entre R$ 10 e R$ 14 por m2
  tratado. O bloqueador interno cotado custa R$ 76 por m2.
- Os dois candidatos de fachada aceitam pintura acrilica por cima, entao o
  acabamento nao fica preso ao produto.
- Consumo real e sempre 0,12 kg/m2 por demao nas duas marcas. O numero de
  demaos e o que muda: 2 no Igolflex, 2 a 3 no Vedapren.

## O que ainda preciso descobrir

- Medida real da area em m2. A conta de quantas embalagens comprar depende
  disso e a faixa 5-15 m2 muda o resultado por um fator de 3.
- De onde a agua entra: parede exposta a chuva, trinca, rufo, calha ou
  respingo do piso. Impermeabilizante nao corrige trinca estrutural nem
  calha entupida.
- Estoque real do Igolflex Fachada. As duas lojas cotadas estao em ruptura.
- Estado da superficie externa: se tem tinta velha descascando ou mofo,
  entra custo de preparo que nenhuma cotacao cobre ainda.
- Se a face interna vai precisar de tratamento tambem, depois que a externa
  secar.

## Hipoteses descartadas

| Hipotese | Motivo do descarte |
|---|---|
| Resolver so pela face interna com Decor Bloqueador / Block Total | O problema e infiltracao externa. Bloquear so por dentro deixa a agua na alvenaria e o revestimento tende a descolar. |
| Block Total como produto principal | Rendimento de 5 m2 por embalagem de 12 kg. Para 15 m2 sao 3 embalagens, R$ 1.139,97, acima do teto de R$ 800. Cortado pelo gate. |
| Preco de R$ 69,89 do Igolflex na Redemac como referencia | Mesma embalagem a R$ 145,90 em outra loja e ruptura de estoque nas duas. Preco tratado como desatualizado. |
