# Prompt para auditoria externa (Codex)

Copie tudo daqui para baixo e cole no Codex, com o repositório aberto.

---

Você é um engenheiro sênior contratado para **auditar de fora** um repositório
que já passou por cinco rodadas de revisão interna. Seu trabalho **não é elogiar
nem confirmar** o que já foi feito: é achar o que o revisor anterior não achou.

Trate cada afirmação abaixo como **alegação a verificar**, não como fato dado.
Se eu digo "isto foi corrigido", seu trabalho é conferir se foi mesmo, se a
correção está completa, e se ela criou problema novo.

## O repositório

`C:\projetos\central-compras` — GitHub privado `josemardp/central-compras`, branch `main`.

É a **memória permanente de decisão de compra** de uma pessoa física. A premissa
do produto: preço envelhece em 48 horas, mas o par *decisão + veredito* ("por que
escolhi X" e, seis meses depois, "deu certo?") vale para sempre. Serve tanto para
um perfume de R$ 70 quanto para um carro elétrico de R$ 150.000 — o que muda é a
profundidade da pesquisa e o rigor do gate, nunca a estrutura.

O PRD v2 está resumido em `docs/plano-sprints-prd-completo.md`. Os cinco
princípios invioláveis dele, que valem como **critério de auditoria**:

1. Fato datado nunca é sobrescrito. Preço novo é linha nova, não célula editada.
2. Gate antes de score. Quem não passa nos critérios eliminatórios não entra no ranking.
3. Todo número é rastreável. Se o score é 82, dá para reconstruir os 82 a partir do CSV, à mão, com uma calculadora.
4. O "não escolhi" vale mais que o "escolhi". Registrar por que o segundo colocado perdeu é o que impede refazer a pesquisa em 2028.
5. Dado pessoal não mora em repositório versionado. Nem privado.

### Forma

- Python 3, dependência única `PyYAML`. Sem framework, sem banco.
- `scripts/central_compras.py` — arquivo único, 29 subcomandos.
- `tests/` — 140 testes. `python -m unittest discover -s tests`.
- Dados em CSV/YAML/Markdown versionados. Dashboard HTML estático gerado.
- Usado de **várias máquinas Windows**, via PowerShell e Git Bash.
- Os 29 comandos: `aguardar-preco`, `anotar`, `aprender-veredito`, `auditar`, `checar-segredos`, `cotar`, `dados-privados`, `dashboard`, `decidir`, `descartar`, `historico`, `init`, `listar-aguardando-preco`, `migrar-cotacoes`, `novo-produto`, `novo-projeto`, `novo-veredito`, `preencher-veredito`, `promover-cotacao`, `prompt-ia`, `ranking`, `reaproveitamento`, `regenerar`, `registrar-licao`, `registrar-loja`, `registrar-marca`, `resumo`, `status`, `validar`.

### Modelo de dados

- `projetos/<ano>-<compra>/cotacoes.csv` — **append-only**, uma linha = uma observação datada. É o livro-razão.
- `produtos/<categoria>/<id>/produto.yaml` — a dimensão estável (o que o produto é).
- `config/categorias.yaml` — schema e gates por categoria. Feito para ser editado e comentado à mão.
- `config/preferencias.yaml` — pesos do score, escalas, frescor, regra de parada.
- `base-conhecimento/` — marcas, lojas e lições nascidas de veredito pós-compra.
- `vereditos/` — D+30 e D+180, que retroalimentam a base.

Derivados e sobrescrevíveis: `ranking.md`, `ranking.csv`, `validacao.md`,
`historico.md`, `memoria-calculo.md`, `dashboard/`.

## O que já foi corrigido (verifique se está mesmo resolvido)

Quatro commits, de `c3c5b12` a `447aa0d`. `git log 92dff2a..HEAD` mostra todos.

**Rodada 1 — motor de decisão.** O score usava min-max dentro do projeto: com
dois candidatos, o segundo sempre tirava 0,00 em qualidade e valor, perdesse por
0,2 ou por 2 pontos. Trocado por escala absoluta (qualidade mapeada de 3,8 a 5,0;
valor por razão `menor_custo / custo`). O alerta `ANCORA` estava **invertido** —
ficava calado na âncora inflada e acusava o desconto legítimo. O `cotacoes.csv`
descartava em silêncio qualquer coluna fora do schema. O gate
`exige_rede_assistencia` era letra morta. A regra de parada (seção 7.5 do PRD)
nunca tinha sido implementada apesar de a config existir. Nenhum controle de
frescor. `decidir` fechava sem o motivo da derrota do segundo colocado. Número
mal digitado virava 0,00 e o produto parecia de graça.

**Rodada 2 — config morta e métrica falsa.** `lojas_preferidas` declarada e nunca
lida. `prompt-ia --etapa decisao` despejava o `repr` cru do CSV na IA, sem o
ranking. A métrica de reaproveitamento contava o conhecimento que o **próprio
projeto** tinha acabado de criar, dando 100% sempre.

**Rodada 3 — robustez.** `cotacoes.csv` era aberto em modo `w`, que trunca antes
de gravar: um Ctrl+C zerava a série histórica (medido, foi de 2 linhas para 0).
Toda gravação virou atômica. `--data ontem` era aceito e, sem data ISO, aquela
cotação escapava calada de toda guarda de data. `preco_teto` do produto era
ignorado pelo gate. `promover-cotacao` herdava `flag_suspeita` da linha web.

**Rodada 4 — seleção e leitura.** `latest_quotes` preferia `manual` sem olhar a
data: um preço manual de 2024 (R$ 900) rankeava no lugar de uma cotação web de
hoje (R$ 400). `aprender-veredito` não era idempotente. `registrar-licao --gate`
apagava os comentários do `categorias.yaml`. Dinheiro saía como `R$ 1234.5`.

**Rodada 5 — auditabilidade.** O princípio 3 era meia-verdade: de eixos para
score fechava, mas de CSV para eixos não, porque os pesos internos do risco
viviam cravados no código. Foram para `preferencias.yaml` (`escala.risco`) e
nasceu o comando `auditar`, que gera `memoria-calculo.md` com a conta inteira.
Um fuzz com invariantes (80 rodadas, semente fixa, metade patológica) não achou
violação nenhuma.

## Onde eu quero que você olhe

Seja **adversarial**. Prefiro um achado real e incômodo a dez observações
educadas. Priorize nesta ordem:

### 1. Correção que ficou pela metade

Para cada correção acima: ela cobre todos os caminhos, ou só o que estava sendo
testado? Exemplos do tipo de coisa que quero que você cace:

- A escrita virou atômica em **todos** os pontos que gravam dado que importa, ou sobrou algum?
- A validação de data cobre todas as portas de entrada de `data_coleta`, ou só o `--data` do CLI?
- `latest_quotes` mudou; algum outro lugar ainda escolhe cotação por conta própria com a regra antiga?
- As constantes de score saíram todas do código, ou sobrou número mágico em algum eixo?

### 2. Os cinco princípios, testados contra o código

Não contra a documentação. Especificamente:

- **Princípio 1**: existe algum caminho, por qualquer comando, em que uma linha de `cotacoes.csv` some ou seja alterada? Inclua falha de disco, execução concorrente de dois comandos, e `git checkout` no meio.
- **Princípio 2**: existe caminho em que um produto cortado no gate influencie o score de outro? (Dica: olhe como o `scoring_pool` e o `menor_custo` são formados quando *todos* são cortados.)
- **Princípio 3**: rode `auditar` e tente refazer o número na mão. Falta alguma constante para fechar a conta?
- **Princípio 4**: dá para produzir um `decisao.md` sem o motivo da derrota, por qualquer caminho?
- **Princípio 5**: `checar-segredos` tem falso-negativo? Tente CPF sem pontuação, cartão com separador incomum, chave de API em formato que o regex não pega.

### 3. Modelo de dados e evolução

O sistema tem que durar dez anos e ser usado de várias máquinas.

- O que acontece se duas máquinas editarem o mesmo `cotacoes.csv` e o Git der merge? O formato tolera merge textual ou vai corromper em silêncio?
- Adicionar uma categoria nova exige tocar em código?
- Adicionar um eixo novo ao score exige tocar em quantos lugares?
- O `produto_id` é único onde precisa ser? Dois projetos diferentes com o mesmo produto — funciona ou colide?
- `historico.md`, `memoria-calculo.md` e `ranking.csv` são derivados versionados. Isso gera conflito de merge inútil entre máquinas? Deveriam estar no `.gitignore`?

### 4. Qualidade do julgamento, não só do código

Esta é a parte que mais me interessa e a que um revisor de código normalmente pula.

- As **escalas** fazem sentido? Qualidade de 3,8 a 5,0 é a faixa certa para nota de marketplace brasileiro? Valor por razão penaliza demais ou de menos?
- Os **pesos** (0,30 / 0,25 / 0,20 / 0,15 / 0,10) produzem ranking sensato? Faça o teste de sensibilidade: mexer num peso muda o vencedor?
- O eixo que **não tem dado** entra como 0,50 neutro. Isso é honesto ou é um número inventado que contamina o score? Existe alternativa melhor?
- A **nota bayesiana** usa μ=4,3 e m=50. Esse m é adequado para marketplace onde produto popular tem 5.000 avaliações?
- O corte de **empate técnico** em 3 pontos é defensável na escala nova?
- As heurísticas de manipulação (`AVAL_SUSPEITA`, `ANCORA`, `RECICLADO`) têm falso-positivo alto? Elas rebaixam no eixo risco em vez de eliminar — é a escolha certa?

### 5. O que está faltando que ninguém notou

Olhe o PRD e pergunte o que ele promete e o código não entrega. E olhe além dele:
que buraco existe que nem o PRD viu?

## Regras da auditoria

- **Reproduza antes de reportar.** Todo achado precisa vir com o comando que o demonstra e a saída real. Achado sem reprodução eu vou descartar.
- **Não conserte nada ainda.** Quero o diagnóstico primeiro. Se propuser correção, proponha como diff comentado, separado do relatório.
- **Diga também o que está certo**, mas curto. Se você auditou os cinco princípios e três estão sólidos, diga em uma linha cada e gaste o espaço no que está torto.
- **Não invente.** Se não deu para verificar, escreva `[NÃO VERIFICADO: motivo]`. Não estime, não suponha, não complete lacuna com plausibilidade.
- Os testes passam hoje (118, `python -m unittest discover -s tests`). Se algum falhar na sua máquina, isso já é um achado — reporte o ambiente.

## Já sei disto, não precisa reportar

Para você não gastar tempo:

- `projetos/2026-fone-bluetooth-para-chamadas/cotacoes.csv` tem uma linha com
  `nota 4.8` e `n_avaliacoes 0` (o JBL). É dado de entrada errado, a validação já
  acusa, e a correção está esperando decisão do dono.
- As 4 cotações daquele projeto são `fonte=web`; nenhuma compra foi fechada ainda.
- A comparação do carro elétrico (Dolphin Mini GL, Geely EX2 Pro, King GL, Atto 2
  DM-i) ainda não foi registrada. É o próximo passo, não um esquecimento.
- `skills/central-compras/` está em inglês enquanto o resto está em português.
  É deliberado (arquivo lido por modelo), mas comente se achar que atrapalha.
- Falta a tag `v1.0`, o guia de nova categoria e a rotina semanal do Sprint 7.

## Formato da entrega

```
## Veredito em uma linha
[o sistema está pronto para uso sério? sim/não/com ressalva, e por quê]

## Achados críticos
[perda de dado, número errado, princípio violado — com reprodução]

## Achados relevantes
[funciona mas está errado conceitualmente, ou vai quebrar quando crescer]

## Julgamento sobre escalas, pesos e heurísticas
[a parte 4 acima, com sua opinião fundamentada]

## O que o revisor anterior acertou
[curto]

## O que eu não consegui verificar
[explícito]
```

Ordene os achados por **impacto na decisão de compra**, não por severidade
técnica. Um número enviesado que faz escolher o produto errado importa mais que
um `except` largo demais.
