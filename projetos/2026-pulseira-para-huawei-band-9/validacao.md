# Validacao

Gerado em 2026-09-21T15:15:07.

## Erros

Nenhum erro.

## Avisos

- Nenhum produto tem cotacao manual; decisao final ainda nao deve ser fechada.
- pulseira-aco-inox: cotacao usada no ranking tem 17 dias (limite 14 para fonte=web). Recote antes de decidir.
- pulseira-nylon: cotacao usada no ranking tem 17 dias (limite 14 para fonte=web). Recote antes de decidir.
- pulseira-silicone-travaclique: cotacao usada no ranking tem 17 dias (limite 14 para fonte=web). Recote antes de decidir.
- pulseira-silicone-xdfind: cotacao usada no ranking tem 17 dias (limite 14 para fonte=web). Recote antes de decidir.
- cotacoes.csv esta num schema antigo, sem as colunas: estoque, proveniencia. Rode `migrar-cotacoes` para atualizar o cabecalho.
- Categoria `pulseira-huawei-band9` sem configuracao propria: usa regras genericas. Revise atributos e gates.

## Criterio

- Erro: impede decisao confiavel ou viola schema.
- Aviso: nao impede pesquisa, mas precisa ser considerado antes de comprar.
