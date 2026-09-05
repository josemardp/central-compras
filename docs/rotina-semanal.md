# Rotina semanal

Checklist para rodar toda semana e manter o repositorio saudavel.

## Antes de fechar a semana

- [ ] Rode `python scripts/central_compras.py status` em cada projeto ativo.
- [ ] Rode `python scripts/central_compras.py validar --strict` em cada projeto ativo.
- [ ] Rode `python scripts/central_compras.py checar-segredos --strict`.
- [ ] Rode `python -m unittest discover -s tests`.
- [ ] Se dados ou integração mudaram, rode `sincronizar-planilha` duas vezes e
      abra a planilha; `ok` no terminal não valida gráficos nem formatação.
- [ ] Verifique `git status --short`: nada deveria ficar por commitar.
- [ ] Commit e push do que ficou pendente.

## Quando uma cotacao venceu

- [ ] Reveja o preco no site.
- [ ] Rode `cotar` de novo com a data atual; nunca edite a linha antiga.
- [ ] Atualize o ranking e a decisao, se houver.

## Lembretes

- `cotacoes.csv` e append-only: preco novo e linha nova.
- Nunca deixe CPF, endereco, nome de terceiros ou dados de pagamento no repo.
- Decisao final precisa de pelo menos uma cotacao `fonte=manual`.
- O resumo do `unittest` sai em stderr; confira o exit code, não use pipe como
  prova de sucesso.
