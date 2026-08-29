# Prompt de implementação: pendências gerais do repositório

Cole isto no Codex (ou outro agente de código) rodando em `C:\projetos\central-compras`.

## Contexto

Central de Compras: CLI Python em arquivo único (`scripts/central_compras.py`)
mais um painel HTTP local (`scripts/painel.py`). Uma auditoria externa (3ª
rodada) já foi triada e os bugs de segurança dela já foram corrigidos numa
sessão anterior. Os 6 itens abaixo são as pendências que sobraram, não
bloqueiam nenhuma compra em andamento, mas estão em aberto desde então.

Regras do repositório, valem pra este trabalho:

- Rode `python -m unittest discover -s tests` antes de tocar em qualquer
  coisa, e de novo no fim. Os 208 testes atuais têm que continuar passando.
- `cotacoes.csv` é append-only: nunca editar ou apagar linha existente.
- Nenhum preço, ficha técnica ou avaliação entra sem fonte primária. Se um
  item pedir dado que você não consegue verificar, **não invente**, marque
  como não feito e diga por quê.
- Um commit por item da lista abaixo, mensagem em português, minúsculo, sem
  travessão (o caractere `—`).
- Não mexa em nada fora do escopo de cada item (sem refactors espontâneos,
  sem "already noticed and fixed" em arquivo vizinho).

## 1. Dado de entrada errado no JBL (não é bug de código)

`projetos/2026-fone-bluetooth-para-chamadas/cotacoes.csv`, linha do
`jbl-tune-770nc` (2026-08-26, fonte `web`): `nota=4.8` com `n_avaliacoes=0`.
Nota alta com zero avaliação é inconsistente, a validação já acusa isso.

**Isto não se conserta editando a linha** (append-only). O certo é conferir
a nota e o número de avaliações reais no anúncio
(`https://lista.mercadolivre.com.br/jbl-770nc` é busca, não anúncio
específico, pode precisar achar o anúncio exato do JBL Tune 770NC) e rodar
`cotar` de novo com `--produto-id jbl-tune-770nc` pra acrescentar uma linha
corrigida.

**Se você não tiver como abrir o Mercado Livre e conferir de verdade**, não
invente nota nem contagem de avaliação. Diga isso explicitamente no retorno
e deixe este item como não feito. É preferível a dado fabricado.

## 2. `peso_ancora` global esmaga categoria de poucas avaliações

`config/preferencias.yaml` tem `nota_bayesiana.peso_ancora: 250` global. Bom
pra marketplace grande (Amazon/ML), mas esmaga categoria de nicho, por
exemplo `material_construcao`, onde 30 avaliações já é volume alto: nota 4.8
vira 4.35, quase no piso.

**Não é pra decidir o número certo por categoria** (isso é julgamento do
Josemar, para depois). É pra **construir a alavanca**: cada categoria em
`config/categorias.yaml` pode opcionalmente ter seu próprio bloco
`nota_bayesiana: {peso_ancora: N, media_categoria_padrao: N}`; se não tiver,
usa o valor global de `preferencias.yaml` como hoje. Nenhuma categoria
existente (`carro`, `fone`, `tenis`, etc.) deve mudar de comportamento: elas
não vão ganhar o bloco novo, então o resultado tem que ficar idêntico ao de
antes.

Onde mexer:

- `adjusted_rating(nota, n)` em `scripts/central_compras.py` (~linha 472):
  aceitar um parâmetro `categoria: str | None = None`; se vier, buscar
  `category_definition(categoria).get("nota_bayesiana", {})` primeiro,
  cair pro `preferences().get("nota_bayesiana", {})` global se a categoria
  não tiver o bloco ou o campo específico.
- `current_adjusted_rating(row)` (~linha 1423): também precisa aceitar
  `categoria` e repassar. Os dois lugares que chamam essa função
  (`compute_ranking`, `audit_score`) já têm o `product`/`item.product` no
  escopo, com `product.get("categoria")` disponível: passar por ali.

**Critério de aceite:** teste novo comprovando que (a) categoria sem bloco
próprio calcula igual a antes, (b) uma categoria de teste com
`nota_bayesiana.peso_ancora` sobrescrito no `categorias.yaml` usa o valor
dela, não o global.

## 3. `artifact.html` só filtra CPF/cartão/senha/token, não CEP/endereço/nome

`SENSITIVE_PATTERNS` em `scripts/central_compras.py` (~linha 3752) não tem
padrão de CEP, e não tem como detectar endereço ou nome de pessoa por regex
de forma confiável (isso é honesto: não finja que resolve).

Duas partes, as duas pequenas:

- Adicionar um padrão CEP a `SENSITIVE_PATTERNS`: formato brasileiro
  `\d{5}-\d{3}` (com hífen). Vai ter falso positivo ocasional (algum
  código/SKU com essa forma), é aceitável, o próprio `CARTAO` já tem esse
  tipo de tolerância, e existe o marcador `ALLOW_SECRET_MARKER` pra
  exceção pontual.
- Em `gerar_artifact()` (`scripts/painel.py`, comando `gerar-artifact`),
  depois de escrever o arquivo, imprimir um lembrete: algo como "Lembrete:
  não escreva CEP, endereço ou nome de terceiros em texto livre (campo
  `porque`, notas). O scanner de segredos não detecta isso." Isso é aviso
  de UX, não filtro técnico, e deve ficar claro no commit que é isso.

**Critério de aceite:** teste que confirma que um CEP em arquivo `.html`
dispara `scan_sensitive`; teste (pode ser leitura de string) que confirma
que o lembrete aparece na saída de `gerar-artifact`.

## 4. Painel não atualiza sozinho ("tela ao lado")

O JS do painel (`scripts/painel.py`, função `carrega()`) roda uma vez só, na
abertura da página. Se outra sessão (ex. um chat com IA) grava cotação no
repositório enquanto o painel está aberto no navegador, a tela não reflete
isso até F5.

Adicionar `setInterval(carrega, 3000)` (ou similar) pra atualizar sozinho.
**Cuidado que já foi mapeado:** `desenha()` reconstrói o `innerHTML` inteiro
do `#app`, incluindo o formulário "Nova cotação". Se o auto-refresh disparar
enquanto o usuário está no meio de preencher esse formulário, ele apaga o
que a pessoa digitou. **Isso não pode acontecer.** Duas saídas possíveis,
escolha uma:

- Pular o ciclo de auto-refresh se algum campo do formulário (`#f_*`) tiver
  valor não vazio, ou se o foco (`document.activeElement`) estiver dentro
  de `.form`.
- Separar `desenha()` em duas partes: uma que só atualiza tabela de ranking
  + KPIs + avisos (chamada pelo `setInterval`), outra que desenha o
  formulário (chamada só no `carrega()` inicial).

Não construa scraping nem WebSocket. É só polling simples.

**Critério de aceite:** `test_painel.py` já verifica strings no HTML gerado
(ex. `"prefers-color-scheme"` em `test_serves_the_page`); adicionar
verificação equivalente pra confirmar que `setInterval` está presente e que
a lógica de não sobrescrever o formulário está no JS gerado.

## 5. Skill sem instalador multi-máquina

`README.md` (linhas ~344-348) manda instalar em
`C:\Users\pc\.codex\skills\central-compras`, caminho de uma máquina
específica que não existe em outra nenhuma. O repositório roda em várias
máquinas Windows do Josemar, com Codex, Claude Code e Antigravity.

- Criar `scripts/instalar_skill.py`: detecta se existem
  `%USERPROFILE%\.codex\skills\` e `%USERPROFILE%\.claude\skills\` (cada um
  só se a pasta pai já existir, não criar do zero pra agente que a pessoa
  não usa) e copia `skills/central-compras/` pra dentro de cada um
  encontrado, substituindo o que já estiver lá (a cópia versionada em
  `skills/central-compras/` é a fonte da verdade). Imprimir o que fez e o
  que pulou.
- Atualizar `README.md`: trocar o caminho cravado por instrução de rodar
  `python scripts/instalar_skill.py` após `git pull`, em vez de caminho
  fixo.

**Critério de aceite:** teste que roda o instalador contra diretórios
temporários simulando `%USERPROFILE%` e confirma que a skill foi copiada
pros que existiam e ignorada pros que não existiam.

## 6. Falta tag `v1.0` e dois documentos

Conforme `docs/plano-sprints-prd-completo.md`, faltam:

- `docs/rotina-semanal.md`: o que rodar toda semana pra manter o
  repositório saudável. Sugestão de conteúdo: `validar` em cada projeto
  ativo, `checar-segredos`, conferir `git status` limpo antes de fechar a
  semana. Curto, é checklist, não ensaio.
- `docs/nova-categoria.md`: guia de como abrir uma 8ª categoria: editar
  `config/categorias.yaml` (atributos obrigatórios, gate, `tco_meses`,
  agora também `nota_bayesiana` opcional do item 2 acima), e se a categoria
  precisa de `sem_frete: true` (item herdado da categoria `carro`). Público
  alvo: o próprio Josemar, que não é desenvolvedor. Direto, sem jargão.
- Depois dos dois docs e com os itens 1-5 resolvidos (ou explicitamente
  registrados como não resolvidos, com o motivo): `git tag v1.0` e
  `git push origin v1.0`. Não precisa criar release no GitHub além da tag,
  a menos que o `gh` já esteja autenticado no seu ambiente e você queira.

## Critérios de aceite gerais

- `python -m unittest discover -s tests` passa (208 + os novos de cada item).
- Um commit por item, na ordem acima. Se algum item não puder ser concluído
  (ex. item 1 sem acesso a navegador), commitar os que puderem e reportar
  claramente o que ficou de fora e por quê.
- Nenhuma mudança de comportamento fora do que cada item pede.
