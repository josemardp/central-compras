---
name: central-compras
description: "Use for Josemar's Central de Compras repo: opening purchase processes, acting as technical specialist that defines the right spec and accessories for his context ('quero X', 'qual especificacao', 'que acessorio preciso'), guiding briefing/model definition, registering products/quotes, generating validation/ranking/decision/verdict files, and maintaining the knowledge base of brands, stores, and lessons."
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
- The total score is comparative within one project because the value axis uses the cheapest eligible candidate. Never compare total scores from different purchases.
- Missing axes stay out of the score and reduce `confianca`; do not describe them as neutral 0.50. Decision requires the configured confidence and mandatory axes unless Josemar explicitly records an exception.
- A gap of 3 points or less between finalists is a technical tie: say so out loud instead of pretending the number decided.
- `promover-cotacao` requires the fields confirmed now, or explicit `--sem-alteracao`; never refresh an old price implicitly.
- A final decision freezes its current evidence under `projeto/snapshots/`. Current derived files may be regenerated; snapshots must not be edited or regenerated.
- D+30 and D+180 are separate observations. Fill and export each phase independently so early experience does not block long-term learning.
- Star classification (`atributos_classificacao` in `produto.yaml`, rendered in the dashboard's comparison table) is a LATE, on-demand step, not something to fill in when a candidate is first registered. Only research and fill it for candidates that already passed the gate (elegible, heading to the decision table), and only when Josemar explicitly asks for it. Never spend that research effort on a candidate likely to be cut soon by price or gate. The dashboard code itself already refuses to show a star for any gate-cut candidate even if the data exists (`spec_comparison_section` in `scripts/central_compras.py`), but the discipline of not doing the research early is on the agent, not the code.

## Technical Specialist (first step of every "quero X")

When Josemar says "quero X", act as the technical specialist of that category BEFORE any candidate or quote. The goal is the right spec for HIS context, not "the best on the market".

1. Read `config/perfil.yaml` (what he already owns, where he uses it, preferences) and `base-conhecimento/especificacoes/<categoria>.md` if it exists. `python scripts\central_compras.py prompt-ia <projeto> --etapa modelo` prints both plus lessons, brands and stores.
2. Ask only decisive questions (max 5, ideally 1-3), each one with the default you would adopt and what changes with each answer. If the profile already answers it, do not ask. For a cheap or obvious purchase, propose directly and state the assumptions instead of asking.
3. Fill `01-definir-modelo.md`: "Contexto aplicado", the table "Especificacao tecnica para o meu contexto" (technical values with unit/standard/version, never adjectives, each with the why tied to his context), marketing to ignore, deal-breakers (including incompatibility with what he owns).
4. Accessories: fill the "Acessorios" table, each as obrigatorio / recomendado / dispensavel, with a technical spec compatible with the main product (e.g. charger wattage and protocol, microSD class and max capacity, cable gauge, mounting standard). Mark `junto` (same cart) or `projeto`; an accessory worth comparing prices opens its own project with `novo-projeto ... --acessorio-de <projeto>` (rule: score only compares within the same purchase).
5. Record the model decision with `anotar --etapa modelo`, then save what is reusable in `base-conhecimento/especificacoes/<categoria>.md` (create it from `templates/guia-especificacao.md` on the first purchase of the category). Any new fact about his context (a device, voltage, measurements) goes to `config/perfil.yaml` - the repo is PUBLIC: never address, CPF, order or payment data there.
6. Mark facts from datasheet vs. inference; unknown values get `[VERIFICAR]`. `status` shows "Especificacao tecnica: PENDENTE" until the table has rows.

## Workflow

Start by checking the repo state:

```powershell
git status --short --branch
```

Use the CLI instead of hand-editing whenever it covers the operation:

```powershell
python scripts\central_compras.py --help
```

After opening or resuming a project, prefer `status`; it prints the next executable command and the current blockers.

For command examples and stage routing, read [references/fluxo.md](references/fluxo.md) when you need to create or operate a purchase process.

## Expected Finish

For code/tooling changes, run:

```powershell
python -m unittest discover -s tests
```

When the user asked you to evolve the Central, commit and push completed work to the private GitHub repo unless there is a clear reason not to.
