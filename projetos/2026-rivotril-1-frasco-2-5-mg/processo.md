# Processo da compra

## Estado atual

- Estado: pesquisando
- Proxima acao: confirmar manualmente preco, frete, estoque, vendedor e garantia dos finalistas
- Decisao aberta: Rivotril gotas (clonazepam) 2,5 mg/mL, 20 mL lidera a pesquisa web, mas ainda nao fecha compra sem cotacao manual.

## Linha do tempo decisoria

| Data | Etapa | Decisao | Por que |
|---|---|---|---|
| 2026-11-04 | modelo | Comprar exclusivamente o medicamento de referencia (marca Rivotril) | Decisao informada pelo Josemar: prefere a marca de referencia em vez do generico. |
| 2026-11-04 | descarte | Descartado clonazepam-gotas-2-5mg-ml-20ml-generico | Decisao do Josemar em 04/11: quer o medicamento de marca de referencia (Rivotril), nao o generico. |
| 2026-11-04 | cotacao | Cotacao registrada para clonazepam-gotas-2-5mg-ml-20ml-generico | Drogaria Sao Paulo / fonte=web / custo_total=13.99 |
| 2026-11-04 | cotacao | Cotacao registrada para clonazepam-gotas-2-5mg-ml-20ml-generico | Drogasil / fonte=web / custo_total=14.9 |
| 2026-11-04 | produto | Candidato registrado: Clonazepam gotas 2,5 mg/mL, 20 mL (Generico) | id=clonazepam-gotas-2-5mg-ml-20ml-generico |
| 2026-11-04 | cotacao | Cotacao registrada para rivotril-gotas-2-5mg-ml-20ml | Drogaria Sao Paulo / fonte=web / custo_total=25.51 |
| 2026-11-04 | cotacao | Cotacao registrada para rivotril-gotas-2-5mg-ml-20ml | Drogasil / fonte=web / custo_total=25.51 |
| 2026-11-04 | produto | Candidato registrado: Rivotril gotas (clonazepam) 2,5 mg/mL, 20 mL | id=rivotril-gotas-2-5mg-ml-20ml |
| 2026-11-04 | modelo | Pesquisar somente Rivotril gotas (clonazepam) 2,5 mg/mL, frasco de 20 mL | A rotulagem da Anvisa identifica esta apresentação; a compra deve coincidir com a receita válida, sem substituir medicamento, concentração ou forma farmacêutica. |
| 2026-11-04 | abertura | Compra criada | Necessidade registrada no briefing |

## Etapas

- [x] 1. Definir o modelo e a especificacao tecnica para o meu contexto (com acessorios)
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

- Medicamento sujeito a controle especial (Portaria SVS/MS 344/98, Lista B1 - Substancias Psicotropicas). Tarja preta.
- Exige retencao da Notificacao de Receita B (receita azul) valida na farmacia. Nao e despachado por frete comum (Correios/transportadora).
- Compra remota so funciona com entrega expressa local da drogaria (motoboy retem a receita na entrega) ou compra pelo app/site com retirada na loja fisica (Click & Collect).
- Preco de referencia (Rivotril Biopas/Roche 2,5 mg/mL gotas 20 mL): ~R$ 25,51 (Drogasil / Drogaria Sao Paulo).
- Alternativa generica (Clonazepam 2,5 mg/mL gotas 20 mL - EMS, Medley, Germed): ~R$ 13,99 a R$ 14,90.

## O que ainda preciso descobrir

- Se a receita medica prescreveu expressamente a marca de referencia (Rivotril) sem autorizacao de substituicao, ou se autoriza o generico (clonazepam).
- Se a compra sera feita para retirada presencial na farmacia ou entrega expressa local.

## Hipoteses descartadas

| Hipotese | Motivo do descarte |
|---|---|
