# 06. Banco e histórico

## Armazenamento

| O quê | Onde | Observação |
|---|---|---|
| Histórico original dos rastreadores | `~/.central-compras/dados-privados/rastreador-{robos,ares,chuveiro}/historico.jsonl` | append-only, **nunca reescrito** |
| Último estado bom | `estado.json` do mesmo diretório | só é atualizado por coleta **não degradada** |
| Banco do radar | `~/.central-compras/dados-privados/radar/radar.db` (SQLite, WAL) | esquema versionado |
| Backups do banco | `.../radar/backups/radar-AAAAMMDD-HHMMSS-<motivo>.db` | automático antes de migração |
| Backup da tarefa do Windows | `.../radar/backups/tarefa-...original.xml` | estado anterior ao cutover |
| Correções de leituras erradas | `config/radar_correcoes.yaml` (no Git) | aplicadas em memória; ver abaixo |

Fica fora do Git por regra do repositório (dado privado e por máquina). Consequência: **cada máquina tem sua série**; se a rotina
rodar em outro notebook, a série dele começa do zero (ver 10).

## Esquema (migração 1)

`observacoes` (série própria validada, `UNIQUE(hash)`; índice `(produto, coletado_em)`), `ofertas` (publicações de comunidade, `UNIQUE(fonte, canal, id_externo)`),
`alertas` (`chave` = família + exata; índice por chave/data), `execucoes`, `jobs_estado`, `fontes_saude`, `outbox`, `schema_migracoes`.

- **Migração e rollback:** `python -m radar migrar` (sobe), `python -m radar migrar --reverter N` (desce; faz backup antes). Testado em `BancoTest`.
- **Importação do histórico:** `python -m radar migrar --importar-historico`, idempotente por hash. Em 20/11: robôs 8 registros (34 observações), ares 9 (54), chuveiro 2 (2).

## Preços distintos que o sistema separa

| Conceito | Onde fica |
|---|---|
| Preço atual anunciado | `ofertas.preco_anunciado` |
| Preço final entregue (anúncio - desconto elegível + frete) | `ofertas.preco_final`, `final_estimado` |
| Preço com cupom validado / estimado | mesmo campo + `status_cupom` (`VALIDADO` = não estimado) |
| Menor/maior/mediana validados (total, 7, 30, 90 dias) | `radar.historico.estatisticas()` (`python -m radar estatisticas`) |
| Menor preço comunitário | `ofertas` (nunca entra nas estatísticas validadas) |

Estatística sem dados suficientes devolve `n: 0` e `null`; nenhuma série é fabricada. A cobertura em 20/11 é de ~2 dias (desde 18/11):
por isso o ranking exige pelo menos 3 observações e 1 dia antes de falar em "mínimo".

## Dados corrompidos e como foram tratados

1. Rodadas degradadas (rede lenta, `Timeout`): continuam no JSONL (honestidade), marcadas `degradada` no banco e **excluídas** das estatísticas e do "último estado bom".
2. Leitura da Leroy R$ 60,65 (20/11 08:03): corrigida por `radar_correcoes.yaml` para R$ 122,45 (Amazon, da mesma coleta), com motivo e `[VERIFICAR]` declarado.

## Integridade e auditoria (fase 2)

**Princípio:** o JSONL bruto é a verdade portátil e nunca muda. O banco guarda o **bruto** em `preco_entregue` e a correção como campos
de auditoria: `invalida`, `preco_corrigido`, `correcao_motivo` (migração 2). Estatísticas, ranking e alertas usam
`COALESCE(preco_corrigido, preco_entregue)` e ignoram `invalida=1`, rodadas degradadas e coletas que não são `COLETA_PROPRIA`.
`python -m radar migrar --reconstruir` recria `observacoes` a partir dos JSONL + `config/radar_correcoes.yaml`, de forma idempotente.

**Varredura de suspeitos** (`python -m radar auditar`, só leitura): `isolado` (melhor preço muito abaixo dos demais valores da mesma coleta),
`salto` (variação ≥ 35% em relação à última coleta boa), `abaixo_do_historico` e `degradada`. Resultado em 21/11 sobre os 3 históricos
(22 coletas, 102 observações, na auditoria de 21/11 por volta das 09:55): **1 leitura suspeita real, a R$ 60,65 do chuveiro (Leroy, 20/11 08:03)**, já corrigida em
`radar_correcoes.yaml` para R$ 122,45 (Amazon, da própria coleta) com `[VERIFICAR]` declarado: a página daquele horário não foi preservada,
então a causa é inferida. Rodadas degradadas (rede lenta) ficam marcadas e fora das estatísticas. O sinal `salto` de 20:03 (R$ 60,65 para R$ 111,89)
desapareceu porque a série de comparação usa o valor corrigido. Menor preço validado do chuveiro naquela auditoria: **R$ 111,89** (Amazon, 20/11 20:03); sem a correção seria R$ 60,65.

Garantia testada: `InvalidacaoNaoContaminaTest` insere uma leitura de R$ 60,65 num produto de R$ 1.200, invalida-a e confirma que o mínimo
volta a R$ 1.199,98, o valor bruto permanece e o ranking não usa o lixo como base.

## Paraguai e moeda

O Xiaomi S40 Pro (Paraguai) fica no catálogo com `moeda: USD`. O tracker guarda o valor já convertido (cotação do Compras Paraguai no dia).
O radar **não compara** ofertas em BRL de comunidade com ele: classifica BAIXA ("fora do escopo"). Custo efetivo de aquisição (dólar datado, cota) continua sendo análise manual.
