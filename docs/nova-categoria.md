# Como abrir uma nova categoria

Guia para adicionar a 8ª categoria (ou qualquer outra) no arquivo `config/categorias.yaml`.

## Passo a passo

1. Abra `config/categorias.yaml` em um editor de texto simples.
2. Copie o bloco de uma categoria parecida e cole no fim do arquivo.
3. Troque o nome da categoria e ajuste os campos abaixo.

## Campos obrigatorios

- `atributos_obrigatorios`: lista de campos que todo produto desta categoria precisa ter. Exemplo: `tipo`, `uso`, `garantia_meses`.
- `gate`: regras que cortam um produto automaticamente.
  - `nota_minima_ajustada`: nota bayesiana minima para passar.
  - `minimo_avaliacoes`: quantidade minima de avaliacoes.
  - `garantia_tipo_aceita`: lista como `[nacional]` ou `[nacional, vendedor]`.
  - `exige_vendedor_oficial`: `true` ou `false`.
  - `exige_rede_assistencia`: `true` ou `false`.

## Campos opcionais

- `tco_meses`: numero de meses para calcular o custo total de uso. Use para produtos caros que se mantem por anos, como carro.
- `sem_frete`: `true` se a categoria nao tem sentido medir prazo de entrega, como carro. O eixo conveniencia sai da conta.
- `nota_bayesiana`:
  - `peso_ancora`: numero de avaliacoes "virtuais" que puxam a nota para a media. Categorias de nicho usam valor menor; categorias grandes usam valor maior.
  - `media_categoria_padrao`: media de referencia para ajustar a nota. Normalmente deixe `4.3`.

## Exemplo minimo

```yaml
minha_categoria:
  atributos_obrigatorios:
    - tipo
    - uso
  gate:
    nota_minima_ajustada: 4.0
    minimo_avaliacoes: 20
```

## Depois de salvar

1. Rode `python -m unittest discover -s tests`.
2. Crie um produto de teste com `python scripts/central_compras.py novo-produto ...`.
3. Adicione uma cotacao de teste e verifique se o ranking funciona.
4. Se tudo passar, commit.
