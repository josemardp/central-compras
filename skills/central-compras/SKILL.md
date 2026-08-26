---
name: central-compras
description: "Use for Josemar's Central de Compras repo: opening purchase processes, guiding briefing/model definition, registering products/quotes, generating validation/ranking/decision/verdict files, and maintaining the knowledge base of brands, stores, and lessons."
metadata:
  short-description: Operate Josemar's purchase decision memory
---

# Central de Compras

Use this skill when Josemar asks to use, evolve, or operate the Central de Compras, or when he asks to start/analyze/close a purchase decision such as "quero comprar um fone", "registra essa compra", "gera ranking", "por que escolhi", "veredito", or "base de conhecimento".

Default repository:

```text
C:\projetos\central-compras
```

## Operating Rules

- Treat every purchase as a decision process, not a loose price table.
- Preserve the invariant: `cotacoes.csv` is append-only for real observations. If a web estimate is confirmed manually, create a new `fonte=manual` row instead of editing away the old `fonte=web` row.
- A final purchase decision must use at least one `fonte=manual` quote unless Josemar explicitly asks to record a provisional decision.
- Never claim that price, stock, freight, coupon, seller, or warranty was confirmed unless it was manually confirmed in the current session or provided by Josemar.
- Use `processo.md` to record "decidi X porque Y" for intermediate decisions, not only the final choice.
- Product discard requires a reason in `descartado_porque` via the CLI.
- For purchases above R$ 20,000, compare by TCO when possible, not sticker price.
- Keep personal delivery, CPF, card, password, and payment data out of the repo.
- A price older than its freshness window is not a price. Recote instead of arguing with the guard.
- Never close a decision without recording why each other candidate lost.
- The score is on an absolute scale, so 75 means the same thing in every project. Always show it decomposed into the five axes, and repeat the "score parcial" warning when an axis has no data.
- A gap of 3 points or less between finalists is a technical tie: say so out loud instead of pretending the number decided.

## Workflow

Start by checking the repo state:

```powershell
git status --short --branch
```

Use the CLI instead of hand-editing whenever it covers the operation:

```powershell
python scripts\central_compras.py --help
```

For command examples and stage routing, read [references/fluxo.md](references/fluxo.md) when you need to create or operate a purchase process.

## Expected Finish

For code/tooling changes, run:

```powershell
python -m unittest discover -s tests
```

When the user asked you to evolve the Central, commit and push completed work to the private GitHub repo unless there is a clear reason not to.
