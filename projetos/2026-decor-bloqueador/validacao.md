# Validacao

Gerado em 2026-09-21T15:07:53.

## Erros

Nenhum erro.

## Avisos

- Nenhum produto tem cotacao manual; decisao final ainda nao deve ser fechada.
- decor-bloqueador: cotacao usada no ranking tem 25 dias (limite 14 para fonte=web). Recote antes de decidir.
- Regra de parada (ate_200): minimo de 1 cotacao(oes) por candidato. Abaixo disso: decor-bloqueador.
- cotacoes.csv esta num schema antigo, sem as colunas: estoque, proveniencia. Rode `migrar-cotacoes` para atualizar o cabecalho.

## Criterio

- Erro: impede decisao confiavel ou viola schema.
- Aviso: nao impede pesquisa, mas precisa ser considerado antes de comprar.
