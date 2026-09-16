# Validacao

Gerado em 2026-09-15T20:28:44.

## Erros

- cotacoes.csv linha 4 (jbl-tune-770nc): `nota` informada com `n_avaliacoes` zerado: nota sem volume nao e evidencia

## Avisos

- cotacoes.csv linha 3 (edifier-w820nb-plus): alertas AVAL_SUSPEITA
- Nenhum produto tem cotacao manual; decisao final ainda nao deve ser fechada.
- edifier-w820nb-plus: cotacao usada no ranking tem 20 dias (limite 14 para fonte=web). Recote antes de decidir.
- jbl-tune-770nc: cotacao usada no ranking tem 17 dias (limite 14 para fonte=web). Recote antes de decidir.
- qcy-h3-anc: cotacao usada no ranking tem 20 dias (limite 14 para fonte=web). Recote antes de decidir.
- soundcore-anker-life-q30: cotacao usada no ranking tem 20 dias (limite 14 para fonte=web). Recote antes de decidir.
- cotacoes.csv esta num schema antigo, sem as colunas: estoque, proveniencia. Rode `migrar-cotacoes` para atualizar o cabecalho.

## Criterio

- Erro: impede decisao confiavel ou viola schema.
- Aviso: nao impede pesquisa, mas precisa ser considerado antes de comprar.
