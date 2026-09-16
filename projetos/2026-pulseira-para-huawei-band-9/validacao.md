# Validacao

Gerado em 2026-09-15T20:28:45.

## Erros

Nenhum erro.

## Avisos

- Nenhum produto tem cotacao manual; decisao final ainda nao deve ser fechada.
- cotacoes.csv esta num schema antigo, sem as colunas: estoque, proveniencia. Rode `migrar-cotacoes` para atualizar o cabecalho.
- Categoria `pulseira-huawei-band9` sem configuracao propria: usa regras genericas. Revise atributos e gates.

## Criterio

- Erro: impede decisao confiavel ou viola schema.
- Aviso: nao impede pesquisa, mas precisa ser considerado antes de comprar.
