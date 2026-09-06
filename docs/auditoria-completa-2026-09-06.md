# Auditoria completa — 06/09/2026

O problema principal não era a fórmula do score: era a distância entre pesquisar uma oferta, declarar que ela foi conferida, selecionar a cotação e preservar a justificativa da compra. A auditoria corrigiu falhas nesses caminhos, reforçou o painel e reduziu leituras repetidas. O motor continua sendo um assistente de decisão: os dados fornecidos podem estar completos e ainda assim estar errados.

## Escopo e método

Base de comparação: commit `feae025`. Foram revisados CLI, descoberta de candidatos, promoção de cotações, gates, score/TCO/confiança, decisão, vereditos, conhecimento, regras de parada, arquivos e travas, painel HTTP/HTML, exportação e cliente Sheets, código documentado do Apps Script, instalador e documentação operacional.

O pedido inicial restringia mudanças ao motor e aos testes. Josemar substituiu essa restrição por autorização para auditar e corrigir todos os arquivos necessários. As mudanças desta entrega preservam os CSVs históricos, fichas reais, decisões antigas, pesos e infraestrutura existente. Não houve pesquisa comercial nem reavaliação individual das compras.

Foram lidos os planos anteriores, lições e orientações de auditoria antes de classificar achados. As reproduções usam repositórios temporários com candidatos sintéticos. As proteções já existentes — append-only, gates antes do score, desconto bayesiano, frescor, confirmação explícita, idempotência por fase e travas de processo — foram consideradas ponto de partida.

## Achados e correções, por impacto acumulado

| Prioridade | Problema observado | Melhoria entregue |
|---|---|---|
| Alta | `decidir` podia escolher outra oferta do mesmo produto que aquela exibida no ranking. Empate de data reproduziu ranking de R$ 200 e snapshot de R$ 300. | A decisão usa o objeto de cotação selecionado pelo ranking, inclusive na conferência de gates e confiança. |
| Alta | Flags de exceção não eram registradas automaticamente; uma decisão excepcional podia declarar ausência de risco. | Snapshot e decisão registram exceções efetivamente necessárias, justificativa, cortes ignorados e confiança. Flag passada sem necessidade não aumenta a contagem. |
| Alta | Snapshot congelava ranking e cotação, mas perdia configuração, fichas e justificativa após mudanças posteriores. | Novas decisões preservam briefing, modelo, CSV, fichas, preferências, categorias, motor, versões Python/PyYAML, argumentos e decisão, com manifesto SHA-256. |
| Alta | Promover apenas link ou garantia podia renovar também um preço antigo; alterar preço de etiqueta podia conservar promoção velha. | Exige confirmação monetária ou `--sem-alteracao`; promoção existente precisa ser confirmada ou explicitamente encerrada com zero. |
| Alta | Regra de parada contava recotações e promoção da mesma oferta como fontes adicionais. | Conta ofertas atuais distintas por loja, vendedor e variação; informa ausência de cotação manual presencial quando exigida pela faixa. |
| Alta | Lições antigas desapareciam do contexto ao entrar a 11ª nova lição. A mesma janela contaminava a métrica histórica. | Prompt usa todas as lições relevantes; métrica consulta todo o histórico. Não há mais corte silencioso de 1.200 caracteres em marca/loja. |
| Alta | Conhecimento de uma marca só aparecia depois de ela já ter sido escolhida como candidata. | Recuperação inclui registros da categoria, mesmo sem essa marca/loja no projeto. |
| Média | Definição do modelo ficava em arquivo que o prompt não lia; gerações e variantes não eram exigidas. | Prompt incorpora `01-definir-modelo.md`, candidatos atuais e protocolo de geração, variante, evidência e conferência. Etapa modelo pede candidatos e lacunas. |
| Média | Painel repetia validação diferente do CLI: prazo `3.5` virava `3`, negativo passava e preço JSON `0` virava ausente. | Ações passam pelo parser e plano de travas do CLI. Valores estruturados impróprios são recusados. |
| Média | Arrays/nulos ou tipos errados no JSON encerravam a conexão ou eram aceitos indevidamente. Não havia restrição de Host/Origin. | Respostas HTTP controladas, validação do envelope, origem local, limite de corpo e timeout de leitura. |
| Média | Coluna TCO e artifact exibiam custo de compra. Prazo era inserido no HTML sem escape. | Exibem a base comparada pelo motor, identificada no artifact; prazo é escapado. |
| Média | Valores padrão do formulário impediam atualização automática; erro de gravação apagava o rascunho; candidato sem cotação não aparecia no seletor. | Compara com valores iniciais, preserva formulário no erro e inclui candidatos ainda sem ofertas. Labels foram associados aos controles. |
| Média | Preferências ficavam indefinidamente em cache no painel; catálogo/configuração eram interpretados repetidamente. | Cache de YAML por operação/contexto, chave por arquivo e metadados, cópias independentes e atualização entre operações. |
| Média | `regenerar` substituía funções globais, podendo suprimir alterações de outra thread. | Suspensão de alterações nas fontes usa `ContextVar`; ações do painel serializam captura de saída. |
| Média | Identificador de produto permitia escapar da pasta; resolução de projeto aceitava pasta contêiner/subpasta. | Validação do identificador e limites de caminho; projeto exige diretório imediato com briefing. |
| Média | YAML com `---` dentro de valor era separado incorretamente; listas/formatos inválidos provocavam erros pouco claros. | Delimitadores em linhas próprias, validação de mapas e mensagens com o arquivo afetado. |
| Média | Inteiros negativos, infinito em CSV legado, notas pessoais inválidas e gates desconhecidos/tipados incorretamente não tinham tratamento uniforme. | Validação de entrada e leitura, limites de notas e lista de gates implementados. Gate de aprendizado é validado antes de escrever marca/loja. |
| Média | Resumo contendo caminho Windows podia ser interpretado como escape de expressão regular. | Substituições preservam texto literal. |
| Média | Cliente Sheets aceitava sucesso não booleano e não tratava timeout/JSON de tipo inesperado; resposta de erro podia refletir credencial. | Erros controlados, `ok` estritamente booleano, remoção do corpo bruto da mensagem e ocultação de token refletido. |
| Média | Instalador apagava a skill anterior antes de copiar a nova. | Prepara cópia antes da troca, mantém backup durante substituição e restaura em falha. |

Uma decisão com `--permitir-web` agora diz **estimado**, sem rotular esse custo como confirmado.

## Leitura das seis etapas do pipeline

### 1. Descoberta de candidatos

O motor pontua a amostra registrada. Não busca autonomamente gerações ou anúncios ausentes; portanto, um produto omitido nunca perde nem ganha no ranking. O protocolo do prompt foi reforçado para tornar essas lacunas visíveis. Continua cabendo à pesquisa justificar abrangência, variantes regionais e alternativas descartadas. Não foi adicionado scraping automático nem pesquisa comercial nesta auditoria.

### 2. Entrada e promoção

`web/manual` expressa o nível declarado de conferência, não o método de obtenção nem prova documental de cada campo. O CLI mantém `manual` como padrão por compatibilidade. Relatório de IA externa deve entrar explicitamente como `web`. A promoção ficou mais rigorosa para preço e desconto, mas continua sendo uma declaração de quem a executa: o código não consegue provar que alguém abriu o anúncio.

### 3. Gates, score e confiança

Os gates realmente implementados tratam preço/teto, nota e volume de avaliações, garantia, vendedor oficial, assistência, marcas vetadas, requisitos explicitamente não atendidos e descarte. Não há gate estruturado de estoque ou detector geral de instabilidade de preço. Há alertas de avaliações suspeitas, âncora e anúncio reciclado; são mecanismos diferentes.

Foi possível montar uma oferta web sintética com confiança de 100% preenchendo os campos esperados. Isso é cobertura de dados, não probabilidade de a oferta ser verdadeira. A documentação do prompt e do painel agora explicita esse limite. Atributos obrigatórios da categoria continuam produzindo avisos; requisitos do briefing em prosa não viraram critérios formais automaticamente. Categorias sem configuração própria passam a avisar que usam regras genéricas.

Qualidade e conveniência usam escalas definidas; valor continua relativo ao menor custo elegível do projeto. Essa comparação local é intencional. Não foram alterados pesos para fabricar um vencedor diferente.

### 4. Exceções e memória da decisão

As cinco flags continuam disponíveis para registrar escolhas conscientes. Novos snapshots tornam seu uso contabilizável por categoria:

```powershell
python scripts/central_compras.py auditar-decisoes --strict
python scripts/central_compras.py auditar-decisoes projetos/<projeto> --strict
```

O comando verifica a cotação e os arquivos do manifesto e falha com `--strict` se encontrar divergência. Não tenta atribuir retroativamente flags ausentes a decisões antigas. O snapshot real existente foi reconhecido como legado e seu hash de cotação conferiu.

Hashes detectam corrupção ou alteração em relação ao manifesto guardado; não são assinatura externa, garantia contra alguém que reescreva também o manifesto ou prova de que a pesquisa comercial estava certa. A captura conserva as entradas para inspeção; não cria um ambiente executável hermético para reprodução automática.

### 5. Aprendizado

D+30 e D+180 já eram exportações distintas e idempotentes. Produto e vendedor já tinham avaliações próprias. As correções desta entrega abrangem recuperação, validação, textos literais e pré-validação de gates. A métrica de reaproveitamento indica que conhecimento anterior estava disponível; não demonstra que ele foi aplicado nem que melhorou a compra.

### 6. Escala e operação

A releitura de todo o catálogo cresce com projetos × produtos. O cache por operação reduz a interpretação repetida de YAML e beneficia dashboard, painel, exportação e regeneração. O catálogo continua em arquivos, sem índice persistente ou banco de dados. O benchmark manual compara a base anterior e o código atual no mesmo conjunto temporário:

```powershell
python tests/benchmark_pipeline.py --projetos 40 --baseline feae025
```

São três produtos por projeto e uma cotação por produto. Tempos dependem da máquina e de concorrência; a contagem de interpretações de YAML é mais estável. O benchmark não modifica os projetos reais.

## Segurança, nuvem e limites remanescentes

Quatro snapshots ignorados em `.playwright-mcp/` faziam a suíte falhar no scanner de padrões sensíveis. Foram movidos, com SHA-256 conferido antes/depois, para:

`C:\Users\josem\.central-compras\dados-privados\central-compras\auditoria-2026-09-06\playwright\`

O scanner estrito passou após a movimentação. O relatório não reproduz os conteúdos encontrados.

A auditoria da integração abrangeu o cliente Python, contratos/testes e leitura integral do Apps Script documentado. **Não houve implantação ou sincronização real nesta entrega.** A Versão 9 é o último estado verificado na sessão de 05/09, conforme `infraestrutura-externa.md`; não se deve confundir esse registro com nova confirmação de disponibilidade.

Pontos para evolução posterior, com limites explícitos:

- Receptor Apps Script: validar integralmente o payload antes de qualquer limpeza, inclusive `null`; hoje há caminhos de erro e possibilidade de escrita parcial de várias abas. Revisar a limpeza de abas pelo prefixo de ano antes de permitir abas manuais nesse espelho. Não foi alterado nem publicado código na nuvem.
- Escritas em múltiplos arquivos: há travas e substituição atômica de arquivos individuais, mas não transação de projeto inteiro. Falta de espaço ou interrupção entre arquivos ainda pode deixar uma operação parcialmente concluída. O verificador de snapshots ajuda a detectar capturas incompletas.
- Produtos reutilizados entre compras: ficha mantém estado/projeto globais. Um modelo de participação por projeto seria mais adequado se o mesmo produto for pesquisado recorrentemente em compras distintas.
- Regra de parada: diferencia fontes atuais e presença física, mas orçamento de minutos/horas continua orientação, não cronômetro. Loja/vendedor/variação são aproximação de independência; não comprovam diversidade econômica das fontes.
- Proveniência: ainda não há evidência verificável por campo nem identificador formal de método/relatório externo. Estoque e garantia precisam de conferência comercial.
- Crescimento: contexto completo evita perder regras silenciosamente, mas aumenta o prompt. Uma futura seleção semântica deve preservar regras permanentes e informar omissões. Índice por projeto e separação gradual de módulos podem ser avaliados com medições, sem migrar o histórico às pressas.
- Veredito: geração de lembretes ainda se baseia na data do registro; distinguir decisão, pagamento, entrega e início de uso merece um fluxo próprio. Datas históricas não foram inferidas nem corrigidas automaticamente.

## Validação e entrega

Baseline: 287 testes; uma falha preexistente no scanner causada pelos quatro snapshots ignorados. Em cópia limpa dos arquivos versionados, os 287 passaram. A primeira rodada de correções passou em 291 testes. A rodada ampliada passou em 318; a validação final passou em **321 testes / 138,343 segundos**. Scanner estrito e `git diff --check` passaram.

No benchmark comparativo de 40 projetos e 120 produtos, a base anterior fez 15.881 interpretações de YAML em 24,303 s; o código atual fez 5.040 em 11,124 s. A carga da máquina afeta o tempo; ambos usaram o mesmo catálogo sintético. No navegador foram conferidos atualização automática para TCO, candidato sem cotação no seletor, labels associados e preservação dos valores após erro de preço.

Os testes novos cobrem seleção coerente de oferta, snapshot/exceção e adulteração, promoção monetária, histórico de lições, recuperação por categoria, cache, entradas e caminhos inválidos, HTTP, TCO, falhas de integração e instalação, e isolamento entre threads. A suíte existente também cobre concorrência de processos, invariantes do score e compatibilidade do exportador. Testes e navegador usaram somente dados sintéticos.

A publicação desta entrega é no repositório. Compras, estoque, preços, credenciais e funcionamento atual da nuvem não foram presumidos a partir de testes locais.
