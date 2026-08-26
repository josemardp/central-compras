# Fluxo da Central de Compras

Use these commands from `C:\projetos\central-compras`.

## Start a Purchase

```powershell
python scripts\central_compras.py novo-projeto "fone bluetooth para chamadas" --categoria fone --valor-estimado 400 --preco-teto 600 --necessidade "Quero um fone para chamadas longas."
python scripts\central_compras.py prompt-ia projetos\2026-fone-bluetooth-para-chamadas --etapa modelo
python scripts\central_compras.py anotar projetos\2026-fone-bluetooth-para-chamadas --etapa modelo --decisao "Pesquisar headphone over-ear" --porque "Conforto e microfone importam mais que portabilidade."
```

## Register Candidates and Quotes

```powershell
python scripts\central_compras.py novo-produto projetos\2026-fone-bluetooth-para-chamadas "QCY H3 ANC" --marca QCY --categoria fone --produto-id qcy-h3-anc --atributo tipo=headphone --atributo conexao=bluetooth --atributo microfone=true --atributo bateria_horas=70 --atributo garantia_meses=12
python scripts\central_compras.py cotar projetos\2026-fone-bluetooth-para-chamadas --produto-id qcy-h3-anc --loja Amazon --vendedor "QCY BR Direct" --vendedor-tipo oficial --preco 296.64 --nota 4.8 --avaliacoes 5360 --garantia-meses 12 --garantia-tipo vendedor --fonte web --link "https://..."
```

`fonte=web` is a research estimate. It cannot close a purchase.

## Confirm Manually

When Josemar confirms the real price/freight/stock/seller/warranty, append a manual quote:

```powershell
python scripts\central_compras.py promover-cotacao projetos\2026-fone-bluetooth-para-chamadas --produto-id qcy-h3-anc --preco 289 --frete 10 --garantia-meses 12 --garantia-tipo nacional --link "https://..."
```

For expensive purchases, include TCO:

```powershell
python scripts\central_compras.py cotar projetos\2026-comprar-carro --produto-id byd-dolphin-mini --loja "Concessionaria" --vendedor "Loja fisica" --vendedor-tipo fisica --preco 150000 --nota 4.7 --avaliacoes 1000 --garantia-meses 36 --garantia-tipo nacional --fonte manual --custo-operacional-mensal 300 --valor-revenda-estimado 85000 --link "https://..."
```

## Rank, Validate, Decide

```powershell
python scripts\central_compras.py ranking projetos\2026-fone-bluetooth-para-chamadas
python scripts\central_compras.py validar projetos\2026-fone-bluetooth-para-chamadas
python scripts\central_compras.py status projetos\2026-fone-bluetooth-para-chamadas
python scripts\central_compras.py descartar --produto-id anker-q30 --projeto projetos\2026-fone-bluetooth-para-chamadas --porque "Passou do preco teto confirmado."
python scripts\central_compras.py aguardar-preco --produto-id qcy-h3-anc --projeto projetos\2026-fone-bluetooth-para-chamadas --preco-alvo 260 --preco-teto 330 --porque "Aprovado, mas acima do alvo."
python scripts\central_compras.py listar-aguardando-preco --categoria fone
python scripts\central_compras.py decidir projetos\2026-fone-bluetooth-para-chamadas --produto-id qcy-h3-anc --porque "Melhor equilibrio entre preco confirmado, microfone e garantia." --perdedores "anker-q30: passou do preco teto" --comprado
```

`decidir` creates the verdict file automatically.

## Verdict Learning

```powershell
python scripts\central_compras.py preencher-veredito vereditos\2026-09-25-projeto-produto.md --fase d30 --nota-arrependimento 1 --compraria-de-novo sim --resumo "Chegou certo e resolveu chamadas." --licao "Compraria de novo de vendedor confiavel."
python scripts\central_compras.py aprender-veredito vereditos\2026-09-25-projeto-produto.md --marca QCY --loja Amazon --categoria fone
```

`aprender-veredito` exports the verdict into brand/store notes and `base-conhecimento/licoes.md`.

## Knowledge Base

```powershell
python scripts\central_compras.py registrar-marca QCY --categoria fone --projeto projetos\2026-fone-bluetooth-para-chamadas --nota 8 --compraria-de-novo talvez --resumo "Boa relacao custo-beneficio; falta veredito proprio."
python scripts\central_compras.py registrar-loja Amazon --categoria fone --projeto projetos\2026-fone-bluetooth-para-chamadas --nota 9 --compraria-de-novo sim --resumo "Entrega e devolucao reduzem risco."
python scripts\central_compras.py registrar-licao "Fone para chamadas precisa de relato especifico de microfone." --categoria fone
python scripts\central_compras.py reaproveitamento --categoria fone
```

`prompt-ia` automatically includes relevant lessons, brands, and stores.
