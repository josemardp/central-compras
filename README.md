# Central de Compras

Sistema local para transformar cada compra em um processo decisorio rastreavel.

A ideia principal e simples: preco envelhece rapido, mas a memoria da decisao continua valendo. Para cada compra, o repositorio guarda o que voce queria comprar, quais modelos foram considerados, quais cotacoes foram vistas, quais criterios eliminaram candidatos e por que a decisao final fez sentido naquele momento.

## Fluxo de uma compra

Cada compra vira um projeto em `projetos/`.

1. `briefing.md` - necessidade, faixa de valor, preco teto, criterios obrigatorios.
2. `processo.md` - checklist vivo das etapas e registro do que ja foi decidido.
3. `01-definir-modelo.md` - conversa com IA para transformar "quero um fone" em requisitos tecnicos.
4. `cotacoes.csv` - observacoes datadas e append-only.
5. `ranking.md` - gates, score aberto e motivos de corte.
6. `decisao.md` - escolhido, motivo, segundo colocado e por que perdeu.
7. `vereditos/` - D+30 e D+180 para fechar o aprendizado.

## Comandos

```powershell
python scripts/central_compras.py init
python scripts/central_compras.py novo-projeto "fone bluetooth para chamadas" --categoria fone --valor-estimado 400 --preco-teto 600
python scripts/central_compras.py novo-produto projetos/2026-fone-bluetooth-para-chamadas "QCY H3" --marca QCY --categoria fone --atributo tipo=headphone --atributo cancelamento_ruido=anc
python scripts/central_compras.py anotar projetos/2026-fone-bluetooth-para-chamadas --etapa modelo --decisao "Pesquisar headphone over-ear com bom microfone" --porque "A prioridade e chamada longa, nao uso esportivo."
python scripts/central_compras.py cotar projetos/2026-fone-bluetooth-para-chamadas --produto-id qcy-h3 --loja Amazon --vendedor "Loja oficial" --vendedor-tipo oficial --preco 299 --frete 0 --nota 4.6 --avaliacoes 1200 --garantia-meses 12 --garantia-tipo nacional --fonte manual --link "https://..."
python scripts/central_compras.py promover-cotacao projetos/2026-fone-bluetooth-para-chamadas --produto-id qcy-h3 --preco 289 --frete 10 --garantia-meses 12 --garantia-tipo nacional
python scripts/central_compras.py ranking projetos/2026-fone-bluetooth-para-chamadas
python scripts/central_compras.py prompt-ia projetos/2026-fone-bluetooth-para-chamadas --etapa modelo
python scripts/central_compras.py descartar --produto-id anker-q30 --projeto projetos/2026-fone-bluetooth-para-chamadas --porque "Melhor ANC, mas passou do preco teto."
python scripts/central_compras.py decidir projetos/2026-fone-bluetooth-para-chamadas --produto-id qcy-h3 --porque "Melhor equilibrio entre microfone, garantia nacional e preco confirmado." --perdedores "anker-q30: melhor ANC, mas passou do preco teto" --comprado
python scripts/central_compras.py resumo projetos/2026-fone-bluetooth-para-chamadas
python scripts/central_compras.py status projetos/2026-fone-bluetooth-para-chamadas
```

## Principios

- Cotacao nova e linha nova. Nao sobrescreva historico.
- Gate vem antes de score.
- Linha com `fonte=web` ajuda a pesquisar; linha com `fonte=manual` e que fecha compra.
- Produto descartado precisa de motivo.
- Decisao final cria veredito automaticamente para D+30 e D+180.
- Dado pessoal fica fora do repositorio, em `~/.central-compras/dados-privados/`.

## Estrutura

```text
config/
  categorias.yaml
  preferencias.yaml
projetos/
  <ano>-<compra>/
produtos/
  <categoria>/
base-conhecimento/
  lojas/
  marcas/
  licoes.md
vereditos/
scripts/
templates/
```

## Como a IA entra

A IA ajuda principalmente em tres momentos:

- definir o modelo certo a partir de uma necessidade vaga;
- mapear candidatos e problemas recorrentes em reviews;
- explicar a decisao, inclusive por que os finalistas perderam.

Ela nao deve fingir que confirmou preco, estoque, frete ou cupom quando isso depende do site no momento da compra. Esses dados entram como `fonte=manual`.

## Testes

```powershell
python -m unittest discover -s tests
```
