# PRD — Central de Compras

**Versão:** 1.0
**Autor:** Esdra (com Claude como revisor/arquiteto)
**Status:** Proposta para bootstrap

---

## 1. Objetivo

Um repositório (local + GitHub) que funciona como memória permanente do seu processo de compra: toda pesquisa feita uma vez nunca se perde, toda decisão fica documentada com o motivo, e cada nova compra aproveita o que já foi aprendido sobre marcas, lojas e categorias.

Serve tanto para uma compra de R$70 (perfume, tênis) quanto de R$150.000 (carro) — a diferença é só a profundidade da pesquisa, não a estrutura.

**Não é** um SaaS com dezenas de "agentes" fictícios. É um repositório de dados bem desenhado + um fluxo de trabalho que você já domina (você pede, Claude pesquisa em tempo real com web search, preenche os arquivos, você decide, o Claude Code — se quiser — automatiza o resto).

---

## 2. Onde este PRD corrige a proposta do ChatGPT

| Ponto do plano do GPT | Problema | O que muda aqui |
|---|---|---|
| "12 agentes especializados" (Scout, Price Hunter, Review Hunter...) | Fantasioso — não existe essa orquestração pronta; vira só nome bonito sem implementação | Um fluxo único, real: entrevista → pesquisa (Claude com busca na web) → preenchimento de arquivo → score → decisão |
| Estrutura de pastas genérica sem schema | Não responde sua pergunta real: "como as colunas variam por produto?" | Schema de colunas concreto (seção 4), com colunas fixas + colunas por categoria |
| Score "94/100" sem explicar o cálculo | Caixa-preta, não auditável | Fórmula de score explícita e ajustável (seção 6) |
| Dashboard web, mobile, radar de preço automático já na v1 | Escopo grande demais para começar; nada disso funciona sem o resto pronto primeiro | Roadmap em fases, começando pelo que dá pra usar HOJE, no chat, sem código (seção 8) |
| Guarda endereço, dados pessoais direto no repositório GitHub | Se o repo for público, vaza dado pessoal | Seção de segurança dedicada — dado sensível fica fora do Git (seção 7) |
| Ignora que ML/Amazon bloqueiam scraping automatizado | Prometia "monitoramento de preço automático" como se fosse trivial | Tratado como Fase 3, explicitamente experimental, com o caminho realista (busca via Claude em vez de bot raspando página) |
| Não conecta com o jeito que você já trabalha | Você já usa skills (foto-catálogo, mentor-central-automações) que geram prompt pra Claude Code | Fase 2 propõe exatamente isso: uma skill "central-compras" no mesmo padrão das que você já tem |

---

## 3. Estrutura do repositório

```
central-compras/
├── README.md
├── .gitignore                      # exclui dados-privados/
├── config/
│   └── preferencias.yaml           # regras gerais (lojas, notas mínimas, marcas evitadas)
├── dados-privados/                 # NUNCA vai pro GitHub (ver seção 7)
│   └── endereco.yaml
├── produtos/
│   ├── carros/
│   │   └── byd-dolphin-mini/
│   │       ├── controle.csv
│   │       ├── pesquisa.md
│   │       └── decisao.md
│   ├── celulares/
│   ├── tenis/
│   └── cosmeticos/                 # cruza com o Esdra Cosméticos, se fizer sentido
├── projetos/
│   └── 2026-comprar-carro/
│       ├── briefing.md             # respostas da entrevista inicial
│       ├── candidatos.md           # shortlist entre categorias/produtos
│       └── decisao-final.md
├── base-conhecimento/
│   ├── marcas/
│   │   └── byd.md
│   └── lojas/
│       ├── mercado-livre.md
│       └── amazon.md
└── scripts/                        # Fase 3 — automações opcionais
```

Regra simples: **produto** = uma coisa específica que você está avaliando (ex: "BYD Dolphin Mini"). **Projeto** = uma necessidade de compra que pode envolver vários produtos concorrentes (ex: "comprar um carro em 2026" compara Dolphin Mini vs Omoda 5 HEV vs outros).

---

## 4. Arquivo de controle por produto — o coração do sistema

Isso responde diretamente sua pergunta: sim, cada produto ganha um `controle.csv` (ou tabela markdown) e as colunas variam por categoria — mas sempre em cima de uma base fixa.

**Colunas fixas (todo produto tem):**

| Coluna | Descrição |
|---|---|
| loja | Mercado Livre, Amazon, etc. |
| vendedor | oficial, terceiro, loja física |
| variação | modelo/versão/cor/tamanho |
| preço | preço à vista |
| preço_promocional | se houver |
| frete | valor e prazo |
| nota | nota média de avaliação |
| n_avaliacoes | quantidade de avaliações |
| garantia | prazo e tipo (nacional/importada) |
| link | URL do anúncio |
| data_coleta | quando essa linha foi pesquisada |
| score | calculado (seção 6) |

**Colunas extras por categoria** (exemplos):

- **Carro:** ano, km, versão do motor, consumo, autonomia (elétrico/híbrido), valor de revenda estimado, ipva/seguro estimado
- **Celular:** armazenamento, RAM, bateria, câmera, compatibilidade 5G
- **Tênis:** numeração, tipo de pisada, drop, uso (corrida/dia a dia)

Isso fica registrado uma vez em `preferencias.yaml` por categoria, então toda vez que você abrir um produto novo dessa categoria, o Claude já sabe quais colunas extras criar — sem você ter que redefinir.

---

## 5. Fluxo de pesquisa e decisão (o que acontece de fato)

1. **Você diz o que quer comprar** — "quero comprar um tênis de corrida até R$400" ou "quero comprar um carro elétrico/híbrido até R$150 mil".
2. **Entrevista curta** — orçamento, prazo, uso, é presente?, marca proibida/preferida, deal-breakers. Isso vira `briefing.md` do projeto.
3. **Pesquisa em tempo real** — Claude usa busca na web (é uma capacidade real, não fictícia) para levantar candidatos no ML e na Amazon primeiro, e amplia para outras lojas se você liberar. Preenche o `controle.csv`.
4. **Leitura de avaliações** — resume o que as avaliações dizem de fato: pontos fortes, defeitos recorrentes, reclamações de garantia. Vai para `pesquisa.md`.
5. **Score e ranking** — aplica a fórmula da seção 6 e te entrega um Top 3–5 com justificativa, não só número.
6. **Você decide** — a decisão final e o motivo (inclusive "por que não escolhi X") ficam registrados em `decisao.md`. É esse "porquê" que, daqui a 3 anos, vale mais que o produto em si.
7. **Commit** — você (ou o Claude Code, se preferir automatizar) commita os arquivos atualizados no Git.

Para compras recorrentes de baixo risco (perfume, item de cosmético) o fluxo pode ser resumido: pular a entrevista, ir direto pra pesquisa e score.

---

## 6. Motor de score — transparente, não caixa-preta

Fórmula simples, com pesos que vêm de `preferencias.yaml` e você pode ajustar por categoria:

```
score = (nota_normalizada * peso_nota)
      + (preço_invertido_normalizado * peso_preço)
      + (confiabilidade_loja * peso_loja)
      + (garantia_presente * peso_garantia)
      + (frete_rápido * peso_frete)
```

Onde cada componente é normalizado de 0 a 1 antes de multiplicar pelo peso. Exemplo de pesos default em `preferencias.yaml`:

```yaml
pesos:
  nota: 0.30
  preco: 0.25
  loja: 0.20
  garantia: 0.15
  frete: 0.10

regras:
  nota_minima: 4.5
  minimo_avaliacoes: 500
  marketplaces_preferidos: [mercado_livre, amazon]
  evitar_vendedor_nao_oficial: true
```

Toda vez que o score aparecer numa tabela, o motivo do número precisa estar rastreável — nada de "94/100" sem explicação.

---

## 7. Segurança e privacidade

Se o repositório for público no GitHub (ou mesmo privado, por precaução):

- **Endereço, CPF, dados de entrega** → ficam em `dados-privados/`, que entra no `.gitignore` e nunca é commitado. Só existe localmente.
- **`preferencias.yaml`** pode ficar público — é só regra de negócio (pesos, notas mínimas), sem dado pessoal.
- Se algum dia quiser sincronizar `dados-privados/` entre máquinas, use um repositório Git separado e privado, não o mesmo do catálogo de produtos.

---

## 8. Roadmap por fases

**Fase 0 — Hoje, sem código (validar o fluxo)**
Criar a estrutura de pastas, o `preferencias.yaml`, e testar o fluxo inteiro manualmente numa conversa com Claude, com uma compra de baixo risco (ex: um tênis). Objetivo: confirmar que o processo entrevista → pesquisa → controle.csv → score → decisão funciona antes de automatizar qualquer coisa.

**Fase 1 — Estrutura versionada**
`git init`, primeiro push pro GitHub, template padrão de `controle.csv` e `pesquisa.md`. Script simples (Python) opcional pra gerar tabela markdown a partir do CSV, se quiser visualizar melhor.

**Fase 2 — Skill dedicada**
Uma skill "central-compras", no mesmo padrão das que você já usa (`foto-catalogo`, `mentor-central-automacoes`): você diz "quero comprar X", ela conduz a entrevista, pesquisa, preenche os arquivos e — se quiser — já gera o prompt pronto pro Claude Code aplicar as mudanças no repositório e commitar.

**Fase 3 — Automações opcionais (exploratório)**
Monitoramento de preço para produtos "aguardando promoção". Aviso importante: ML e Amazon têm proteção ativa contra scraping automatizado — um bot batendo na página de tempos em tempos não é confiável nem está alinhado aos termos de uso deles. O caminho realista aqui é usar buscas pontuais (via Claude, sob demanda) em vez de um robô rodando sozinho 24/7. Dashboard local em HTML gerado a partir dos CSVs também entra aqui, só depois que já existir volume de dados real pra mostrar.

---

## 9. Próximo passo imediato

Sugestão: comece pela Fase 0 com uma compra real que você já tem em mente (o tênis ou o carro elétrico, por exemplo). Isso valida a estrutura de colunas na prática antes de você investir tempo automatizando algo que ainda pode mudar de forma.
