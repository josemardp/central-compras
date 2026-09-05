# Prompt para o Kimi — Google Sheets premium, Versão 9

Kimi, trabalhe no repositório `C:\projetos\central-compras` e transforme a
planilha **Central de Compras - Cotacoes e Comparacoes** na melhor versão que
o Google Sheets consegue oferecer como instrumento pessoal de decisão de
compra.

Não quero apenas “mais cor”. Quero um produto visual maduro: hierarquia forte,
leitura rápida, comparações honestas, estados claros, boa densidade de
informação, interação útil e acabamento consistente no desktop e no celular.
O resultado deve parecer um painel executivo feito por alguém que entende de
design de informação, não uma planilha decorada.

## Missão

Evolua a **Versão 8**, que já está implantada e funcional, para uma proposta de
**Versão 9 top de linha**. Inspecione o que existe, planeje, implemente e teste.
Não pare na análise nem entregue apenas um mockup.

Ao abrir a planilha, o Josemar deve conseguir:

1. entender em poucos segundos quais compras exigem atenção;
2. entrar num projeto e identificar líder, empate ou bloqueio imediatamente;
3. comparar preço, qualidade, risco, aderência e conveniência sem ambiguidade;
4. distinguir dado confirmado, dado vencido e dado ausente;
5. navegar entre visão geral e projetos sem se perder;
6. confiar que o visual não distorce a lógica registrada no repositório.

## Leia antes de alterar

Leia integralmente, nesta ordem:

1. `CLAUDE.md`
2. `docs/infraestrutura-externa.md`
3. `docs/aprendizados-google-sheets.md`
4. `docs/integracao-google-sheets.md`
5. `README.md`, especialmente a explicação do score
6. `STATUS.md`
7. `scripts/central_compras.py`, funções do payload do Sheets
8. testes relacionados à integração e ao `Code.gs`

A ausência de configuração local não significa que a infraestrutura não
existe. Não crie outra planilha, pasta, Apps Script ou implantação.

## Estado atual que você deve preservar

- A implantação ativa é a **Versão 8**, no projeto `Central de Compras - Sync`,
  sob a conta proprietária `conta-comercial@exemplo.com`.
- O código implantável é o bloco `Code.gs` de
  `docs/integracao-google-sheets.md`.
- O Python envia o payload por `sheets_export_payload()`.
- A planilha é um espelho descartável. A fonte da verdade continua sendo o
  `cotacoes.csv` de cada projeto.
- O fluxo atual trabalha com `Visao Geral` e uma aba por projeto.
- A suíte tinha 284 testes passando em 05/09/2026. Rode-a e informe a contagem
  real encontrada; não suponha que esse número continua igual.

Não altere produtos, preços, cotações, decisões, pesos ou regras de score para
“melhorar” a aparência. Este trabalho é de apresentação, interação e, somente
se indispensável, contrato aditivo de dados.

## Método de trabalho obrigatório

### 1. Diagnóstico real

Antes de codificar, abra a planilha existente quando tiver acesso e examine:

- a primeira tela da `Visao Geral`;
- uma aba com dois ou três candidatos;
- uma aba com quatro ou mais candidatos;
- uma aba com empate técnico;
- estados vazios, bloqueados, vencidos ou sem dados;
- comportamento em viewport de desktop e de celular.

Compare o que aparece com o payload e com os arquivos do repositório. Registre
em poucas linhas o que já funciona, o que confunde e o que falta. Se não tiver
acesso ao navegador autenticado, marque a análise visual como não verificada e
continue com a inspeção estática; não invente observações.

### 2. Plano de design

Apresente um plano curto antes de editar, cobrindo:

- arquitetura da informação;
- hierarquia visual;
- gráficos e a pergunta que cada um responde;
- interações nativas do Sheets;
- comportamento para dados ausentes e diferentes quantidades de candidatos;
- estratégia de validação e compatibilidade.

Depois implemente o plano. Se descobrir que uma ideia não funciona bem no
Sheets, adapte-a e explique a decisão no fechamento.

### 3. Implementação completa

Edite o `Code.gs` versionado. Mude o Python apenas quando o visual realmente
precisar de um dado que o payload ainda não fornece. Nesse caso, a mudança deve
ser aditiva, compatível com o receptor antigo e coberta por testes.

## Direção visual

### Linguagem

- Aparência editorial e executiva, silenciosa e precisa.
- Fundo branco, superfícies neutras, espaço suficiente e divisórias discretas.
- Sem gradientes, clip-art, sombras pesadas, arco-íris, bordas em todas as
  células ou grandes blocos de cor saturada.
- Ícones e símbolos servem ao estado ou à navegação; não são decoração.
- Nada pode depender só da cor. Estado sempre combina cor, símbolo e texto.
- O líder recebe destaque; os demais recuam sem perder legibilidade.
- Texto à esquerda, números à direita e cabeçalho alinhado ao conteúdo.
- Use Inter na interface e Roboto Mono apenas em números tabulares.
- Garanta quebra de texto, alturas e larguras estáveis. Nenhum rótulo pode
  ficar cortado ou sobrepor outro conteúdo.

### Paleta-base validada

Preserve estes papéis. Só acrescente cor se houver uma função semântica nova e
se documentar contraste e comportamento para daltonismo.

| Papel | Cor |
|---|---|
| Superfície | `#ffffff` |
| Cabeçalho suave | `#f9f9f7` |
| Tinta primária | `#0b0b0b` |
| Tinta secundária | `#52514e` |
| Tinta apagada | `#898781` |
| Divisória | `#e1e0d9` |
| Borda estrutural | `#c3c2b7` |
| Líder | `#2a78d6` |
| Fundo do líder | `#eaf2fd` |
| Atenção | `#fab219` |
| Alerta | `#d03b3b` |
| Confirmação | `#0ca30c` |

Para gráficos com até três candidatos, os slots permitidos são `#2a78d6`,
`#eb6834` e `#1baf7a`. Com quatro ou mais, prefira pequenos múltiplos na mesma
escala ou uma série única com destaque seletivo. Não invente uma quarta cor.

## Experiência da `Visao Geral`

Trate a aba como um **cockpit de decisões**, não como um relatório genérico.
A primeira tela deve priorizar ação e contexto.

### Faixa superior

Mostre indicadores compactos e comparáveis, como:

- projetos ativos;
- decisões concluídas;
- aguardando confirmação de preço;
- cotações vencidas ou projetos bloqueados.

O número é protagonista; o rótulo é curto. Alerta só ganha cor forte quando há
algo a resolver.

### Fila de atenção

Crie uma leitura clara dos projetos que precisam de ação: cotação vencida,
falta de fonte manual, preço acima do teto, confiança insuficiente, empate ou
ausência de candidato elegível. Pode ser uma faixa ou uma tabela compacta, mas
deve usar apenas fatos presentes no payload. Não transforme ausência em zero e
não invente recomendação.

### Tabela principal

- Cabeçalho forte, linhas leves e filtro nativo.
- Projeto como link interno para a aba correspondente.
- Estado com símbolo, texto e cor semântica.
- Score, confiança, contagens e datas com formatação correta.
- Links, observações e textos longos devem quebrar sem aumentar a tabela de
  forma caótica.
- Use formatação condicional com parcimônia para vencimento, bloqueio e baixa
  confiança.

**Não compare score total entre projetos em gráfico.** O eixo `valor` é
relativo aos candidatos de cada compra; por isso scores de projetos diferentes
não compartilham a mesma base. Remova ou substitua o gráfico geral atual por
algo realmente comparável, como distribuição por estado, volume de pendências
ou outro indicador cuja semântica esteja comprovada.

## Experiência das abas de projeto

Cada aba deve contar uma história única: **quem está ganhando, por quê e o que
impede a decisão**.

### Cabeçalho e veredito

- Link discreto de volta para `Visao Geral`.
- Nome do projeto, categoria e data/hora da geração.
- Faixa de veredito que trate corretamente: líder claro, empate técnico,
  nenhum elegível e decisão já fechada.
- Se a diferença entre os dois primeiros for menor ou igual a 3 pontos, mostre
  “Empate técnico” nos dois; não finja precisão que o score não tem.
- Exiba alertas úteis: cotação vencida, preço não confirmado, fonte manual
  ausente, dado essencial ausente ou candidato acima do teto.

### Comparação

- Produtos em colunas de mesma largura, com o líder reconhecível em dois
  segundos.
- Seções visuais claras para preço, informações comerciais, atributos e score.
- Preço, frete, total, nota, garantia, prazo, estoque e demais valores devem
  manter o tipo correto e a unidade visível.
- Valor ausente aparece como “Sem dado” ou vazio explicado, nunca como zero.
- Candidato cortado ou inelegível continua legível, mas não parece vencedor.
- Notas de célula podem explicar score, fonte ou transformação sem poluir a
  tabela.

### Visualizações

Use gráficos somente quando responderem uma pergunta melhor que a tabela:

1. **Ranking do projeto:** score total por candidato, com o líder em azul e os
   demais em cinza. Scores só são comparados dentro do mesmo projeto.
2. **Eixos do score:** qualidade, valor, risco, aderência e conveniência na
   mesma escala de 0 a 1. Até três candidatos podem usar séries agrupadas; com
   quatro ou mais, use pequenos múltiplos sincronizados.
3. **Preço ou custo total:** inclua apenas se ajudar a explicar o resultado e
   ficar separado do score. Nunca use dois eixos Y.

Não use pizza, rosca, radar, 3D ou gráfico puramente decorativo. Não rotule
todos os pontos. Legenda, escala e unidade precisam estar claras.

## Interação que agrega valor

Use recursos nativos confiáveis do Sheets:

- filtros na tabela geral;
- links de ida e volta entre abas;
- notas de célula para explicações contextuais;
- proteção em modo de aviso, lembrando que a fonte é o repositório;
- linhas congeladas que preservem contexto;
- agrupamento de linhas ou colunas somente se melhorar a leitura no celular;
- formatação condicional para estados que exigem atenção.

Não crie botões, checkboxes ou seletores que pareçam persistir decisões se a
próxima sincronização vai apagá-los. Interação falsa é pior que ausência de
interação.

## Restrições técnicas inegociáveis

1. **Compatibilidade:** o Apps Script deve aceitar payload antigo e novo. Campo
   desconhecido gera aviso; não é ignorado em silêncio nem derruba toda a
   sincronização.
2. **Tipos:** não aplique `setNumberFormat('@')` em tudo. Texto permanece texto;
   preço, nota, score, quantidade e medida permanecem números.
3. **Desempenho:** escreva e formate em lote. Não volte a `appendRow` ou a
   chamadas célula por célula em laços grandes.
4. **Idempotência:** remova gráficos, filtros, regras e mesclagens antigas antes
   de recriar. Duas sincronizações devem produzir o mesmo resultado.
5. **Células mescladas:** não congele uma coluna se a divisória atravessar uma
   mesclagem. A Versão 8 usa zero colunas congeladas por esse motivo.
6. **Gráficos:** use tabelas-fonte contíguas, orientadas como o gráfico espera e
   posicionadas fora da área principal. Intervalos separados e transpostos já
   produziram gráficos vazios e rótulos trocados.
7. **Locale:** a planilha é `pt-BR`. Evite fórmulas frágeis a separadores; se
   usar `SPARKLINE`, teste a fórmula no arquivo real. Prefira APIs nativas de
   gráfico quando entregarem o mesmo resultado.
8. **Tempo:** mantenha timeout de 120 segundos no cliente.
9. **Segredos:** nunca copie o token para código versionado, logs, screenshots
   ou resposta. O scanner estrito é gate de commit.
10. **LF no Windows:** não regrave CSV ou YAML com CRLF. Preserve `\n`.

## Deploy

Editar `docs/integracao-google-sheets.md` não altera o que está no ar.

Se houver autorização explícita e navegador autenticado como
`conta-comercial@exemplo.com`:

1. salve o `Code.gs` no projeto existente;
2. abra **Implantar → Gerenciar implantações**;
3. edite a implantação existente e selecione **Nova versão**;
4. confirme que “Executar como eu” se refere a `conta-comercial@exemplo.com`;
5. preserve o mesmo ID e a mesma URL `/exec`.

Não publique pela conta `josemardp` ou por outro editor. Se não puder confirmar
a conta proprietária ou a autenticação em duas etapas, limite-se ao código
versionado e marque **DEPLOY PENDENTE**. Não afirme que aplicou.

## Validação obrigatória

1. Rode a suíte completa sem pipe:
   `python -m unittest discover -s tests`. O resumo sai em `stderr`; capture o
   código de saída separadamente.
2. Acrescente testes de regressão para cada risco novo ou falha corrigida.
3. Rode `python scripts/central_compras.py checar-segredos --strict`.
4. Rode `git diff --check`.
5. Se o deploy for feito, rode `sincronizar-planilha` duas vezes.
6. Abra a planilha real e confira todas as abas contra o repositório.
7. Valide desktop e celular: primeira tela, textos, larguras, mesclagens,
   filtros, links, notas, formatação numérica e gráficos renderizados.
8. Conte os gráficos e confirme as tabelas-fonte. Existência do objeto não
   prova que ele contém dados corretos.

HTTP 200, execução “Concluído” no Apps Script e retorno `ok` do terminal não
substituem a inspeção visual. O `doPost` pode capturar erro e devolver
`{ok: false, detalhe: ...}` com status HTTP 200.

## Critérios de aceite

- A `Visao Geral` mostra prioridade e pendências sem comparar scores
  incomparáveis.
- Em qualquer projeto, líder, empate, bloqueio ou ausência de elegível são
  percebidos em poucos segundos.
- Nenhum estado depende só de cor.
- Nenhum dado ausente vira zero.
- Tipos numéricos continuam ordenáveis, somáveis e utilizáveis em gráficos.
- As visualizações têm pergunta, escala, unidade e fonte corretas.
- A planilha permanece legível no desktop e no celular.
- Duas sincronizações não duplicam nem acumulam elementos.
- Payload antigo continua funcionando; campo novo não desaparece em silêncio.
- Suíte, scanner de segredos e `git diff --check` passam.
- O estado do deploy é descrito com precisão.

## Entrega final

Entregue nesta ordem:

1. diagnóstico curto da Versão 8;
2. decisões de design e o motivo de cada uma;
3. arquivos alterados e comportamento implementado;
4. antes/depois, com screenshots quando houver acesso;
5. resultados exatos dos testes, scanner e sincronizações;
6. conferência aba por aba, incluindo desktop e celular;
7. limitações ou itens não implementados;
8. estado explícito: `SOMENTE VERSIONADO`, `DEPLOY PENDENTE` ou
   `VERSÃO 9 IMPLANTADA E VERIFICADA`.

Atualize `STATUS.md`, `docs/integracao-google-sheets.md`,
`docs/infraestrutura-externa.md` e `docs/aprendizados-google-sheets.md` sempre
que o estado real mudar. Só faça commit e push se isso tiver sido autorizado na
conversa. Não misture melhoria visual com alteração de regra de negócio.
