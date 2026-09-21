# Fluxo da Central de Compras

Use these commands from `C:\projetos\central-compras`.

## Start a Purchase

```powershell
python scripts\central_compras.py novo-projeto "fone bluetooth para chamadas" --categoria fone --valor-estimado 400 --preco-teto 600 --necessidade "Quero um fone para chamadas longas."
python scripts\central_compras.py prompt-ia projetos\2026-fone-bluetooth-para-chamadas --etapa modelo
python scripts\central_compras.py anotar projetos\2026-fone-bluetooth-para-chamadas --etapa modelo --decisao "Pesquisar headphone over-ear" --porque "Conforto e microfone importam mais que portabilidade."
```

## Specify for His Context (before any candidate)

`prompt-ia --etapa modelo` carries `config/perfil.yaml` and the category guide
(`base-conhecimento/especificacoes/<categoria>.md`). Fill the spec and
accessory tables in `01-definir-modelo.md`; `status` shows them as PENDENTE
until they have rows. An accessory worth comparing prices becomes its own
purchase, linked to the main one:

```powershell
python scripts\central_compras.py novo-projeto "cartao microsd camera" --categoria generico --valor-estimado 80 --acessorio-de projetos\2026-camera-externa
```

## Quoting on the Web (what works, measured 2026-09-21)

- Mercado Livre blocks automated reading everywhere: WebFetch, headless browser
  (403 even on the home page) and its public API (now requires auth). Leroy
  Merlin also returns 403. Ask Josemar to check ML on his phone when it matters.
- Amazon.com.br and KaBuM work in the headless browser without login (read
  only). On an Amazon page, `fetch('/dp/<ASIN>')` from the page context returns
  other listings' HTML for image/price extraction in one call.
- Buscape/Zoom work through WebFetch but show no rating, reviews or warranty:
  the gate will cut those quotes. Use them only as a price floor.
- Sites that mirror ML listings (gooseguardian, megsegurancaeletronica) have
  invalid TLS certificates: never a place to buy; cite the MLB id instead.
- Record `--origem-dados observacao_direta` only for pages actually read in the
  browser, `relatorio_ia` for search/aggregator summaries, and put in
  `--evidencia` everything that was NOT verified (seller, warranty, freight).
- Check listing photos: an Amazon listing for a Steck DR showed a smart switch
  in every photo. Wrong photos mean risk of receiving the wrong item.
- Manufacturer manuals beat listings. The PPA DZ Rio manual corrected speed,
  breaker size and added a mandatory DR; `pdftotext -layout` reads PPA PDFs.
- One project per item. Complementary items (DPS + breaker, plug + connector)
  never share a ranking; quantity purchases quote the TOTAL for the quantity.

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

State every field checked now. When the listing was checked and nothing changed,
use `--sem-alteracao` explicitly. Promotion never silently refreshes an old web
observation.

For expensive purchases, include TCO:

```powershell
python scripts\central_compras.py cotar projetos\2026-comprar-carro --produto-id byd-dolphin-mini --loja "Concessionaria" --vendedor "Loja fisica" --vendedor-tipo fisica --preco 150000 --nota 4.7 --avaliacoes 1000 --garantia-meses 36 --garantia-tipo nacional --fonte manual --custo-operacional-mensal 300 --valor-revenda-estimado 85000 --link "https://..."
```

## Price History

```powershell
python scripts\central_compras.py historico projetos\2026-fone-bluetooth-para-chamadas
```

The price series is the only defense against an inflated "de R$ X" anchor. With a
single observation the report says so explicitly - do not call a discount real
until there are at least two dated observations.

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

`decidir` creates the verdict file automatically, already filled with brand,
store and category so `aprender-veredito` can export the learning without
retyping anything.

`decidir` refuses to close when:

- the chosen quote is not `fonte=manual` (use `--permitir-web` to override);
- the quote is past its freshness window (`--permitir-vencida` to override);
- the selected product fails a gate (`--permitir-cortado` to record a conscious exception);
- required score axes are missing or confidence is below the configured minimum
  (`--permitir-incompleto` to record a conscious exception);
- a product marked `aguardando_preco` is still above its target
  (`--permitir-aguardando` to record a conscious exception);
- any other candidate with a quote has no recorded reason for losing
  (`--perdedores "produto_id: motivo"`, or `--sem-perdedores` when there really
  was no competitor).

That last one is principle 4 of the PRD: the "why I did not choose it" is what
stops the whole research from being redone in two years.

The total score is comparable only inside this purchase. Missing axes stay out
of the calculation and reduce `confianca`; they never count as neutral 0.50.
Every decision stores immutable `ranking.md`, `ranking.csv`, and quote metadata
under the project's `snapshots/` directory.

## Star Classification (on demand, after the gate has run)

The dashboard's side-by-side comparison table can show a 1-5 star rating per
attribute row, absolute against the market (never "best of these N
candidates"). Filling `atributos_classificacao` in a candidate's
`produto.yaml` is real research work (official datasheets, not guesses), so
only do it for candidates that are already `elegiveis` after `ranking` has
run, and only when Josemar explicitly asks for the star classification.
Never front-load this research when a candidate is first registered - most
candidates get cut by price or gate before reaching the decision table, and
that research would be wasted. The code itself will never render a star for
a gate-cut candidate even if `atributos_classificacao` happens to have data
(`spec_comparison_section` in `scripts/central_compras.py`), but skipping the
research early is on the agent's judgment, not something the code enforces.

## Verdict Learning

```powershell
python scripts\central_compras.py preencher-veredito vereditos\2026-09-25-projeto-produto.md --fase d30 --nota-arrependimento 1 --compraria-de-novo sim --resumo "Chegou certo e resolveu chamadas." --chegou-no-prazo sim --produto-conforme sim --defeito nao --licao "Compraria de novo de vendedor confiavel."
python scripts\central_compras.py aprender-veredito vereditos\2026-09-25-projeto-produto.md --fase d30
python scripts\central_compras.py preencher-veredito vereditos\2026-09-25-projeto-produto.md --fase d180 --nota-arrependimento 0 --compraria-de-novo sim --resumo "Continua funcionando." --ainda-usa sim --valeu-o-que-pagou sim --o-que-aprendi "Durabilidade confirmou a escolha."
python scripts\central_compras.py aprender-veredito vereditos\2026-09-25-projeto-produto.md --fase d180
```

`aprender-veredito` exports each phase once into brand/store notes and
`base-conhecimento/licoes.md`. D+30 does not block D+180.

## Knowledge Base

```powershell
python scripts\central_compras.py registrar-marca QCY --categoria fone --projeto projetos\2026-fone-bluetooth-para-chamadas --nota 8 --compraria-de-novo talvez --resumo "Boa relacao custo-beneficio; falta veredito proprio."
python scripts\central_compras.py registrar-loja Amazon --categoria fone --projeto projetos\2026-fone-bluetooth-para-chamadas --nota 9 --compraria-de-novo sim --resumo "Entrega e devolucao reduzem risco."
python scripts\central_compras.py registrar-licao "Fone para chamadas precisa de relato especifico de microfone." --categoria fone
python scripts\central_compras.py reaproveitamento --categoria fone
```

`prompt-ia` automatically includes relevant lessons, brands, and stores.

## Maintenance

```powershell
python scripts\central_compras.py migrar-cotacoes
python scripts\central_compras.py dados-privados
python scripts\central_compras.py checar-segredos --strict
```

`migrar-cotacoes` upgrades an old `cotacoes.csv` header without losing rows or
hand-written columns. `dados-privados` creates the personal-data folder OUTSIDE
the repository tree - address, CPF, order numbers live there, never in Git.

## Local Dashboard

```powershell
python scripts\central_compras.py dashboard
```

Open `dashboard\index.html` to inspect active projects, waiting-price items, per-project rankings, brand/store lessons, regret notes, gate adherence, and decision time.
