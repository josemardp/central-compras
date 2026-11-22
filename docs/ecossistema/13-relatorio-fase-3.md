# 13. Relatório da fase 3: comprovação da efetividade e homologação (21/11/2026)

## Veredito

**O radar consegue transformar uma oferta real descoberta em uma oportunidade corretamente identificada? Sim, com a ressalva abaixo.**

- 24 ofertas **reais e documentadas** dos seus 12 produtos foram reencenadas pela cadeia de produção, com o **seu histórico real de preços**. Todas foram reconhecidas no produto certo (24 de 24). Depois de corrigir a regra de urgência, 12 ficaram em ALTA (6 geraram mensagem; 3 foram barradas por duplicidade e 3 pelo limite diário de 6) e 12 ficaram sem alerta. A separação bate com o que é novidade e o que é só o preço que o relatório das 08h já mostra (seção 5).
- **Ressalva que não escondo:** desde que o radar existe, **nenhuma oferta ao vivo dos seus 12 produtos apareceu** nas fontes (0 de 140 títulos de oferta lidos ao vivo hoje; 0 de 328 antes). Portanto a cadeia **não foi exercitada com uma oferta ao vivo**. A prova é por reencenação de ofertas reais, cenários sintéticos, um envio real de teste e mutação, não por um alerta real. Ausência de ofertas **não** é usada como prova de eficácia em nenhum ponto deste relatório.
- Os alertas reais seguem **desligados** (`enviar: false`, `homologado_em: null`) e as rotinas das 08h, 14h e 20h foram preservadas (a de 14h e a de 20h continuam no Agendador; a das 08h foi recuperada às 09:54).

A fase 3 achou e corrigiu **14 defeitos**, vários deles com impacto direto em "avisar certo". A tabela está logo abaixo porque é a evidência mais honesta de como a eficácia foi medida: cada um foi achado ao testar contra dado real, não ao reler o código.

| # | Defeito achado | Como apareceu | Correção |
|--:|---|---|---|
| 1 | **Falso negativo:** "Dreame F10 Robô Aspirador **e Passa Pano** ... Limpeza **de** Sujeiras" (Amazon, R$ 1.136,50) rejeitado como acessório | título real do histórico | acessório só se a palavra for o núcleo do título; teste com o caso real |
| 2 | Oferta sem voltagem no título (K800 existe em 127V e 220V) reconhecida **sem aviso** | casos ambíguos: 2 de 7 corretos | avisos `tensao_nao_informada`, `sku_nao_confirmado`, `nome_alternativo`; 7 de 7 |
| 3 | Nome alternativo "HW Inverter Elgin **Eco III**" (Amazon, R$ 1.895) não casava | título real | alias fraco, limitado a classe MÉDIA |
| 4 | URLs reais escrevem "**agrato**" e "**air volution**" (só o SKU salvava) | slugs reais independentes | padrões tolerantes às duas grafias |
| 5 | `elegibilidade()` testava "clientes selecionados" **antes** de "primeira compra/app" | cupom real `25PRIMEBF` | restrição impeditiva conhecida vence a incerteza |
| 6 | **Cruzamento marcava 268 pares como "aplicável"** (ex.: "20% em produtos Amazon" para tudo, economia de R$ 400) | rodada real com 298 publicações | regra estrita: 4 candidatos, todos o mesmo cupom real |
| 7 | `radar validar` era **sobrescrito** no ciclo seguinte: o alerta CRÍTICA (VALIDADO) **nunca aconteceria** | cenário S03 | tabela `validacoes_manuais` (migração 3) |
| 8 | Motivo contraditório: "no mínimo histórico **validado** ... (**não validado**)" | mensagem real de teste lida no WhatsApp | texto reescrito |
| 9 | Mensagem dizia "Preço final **entregue**" mesmo sem frete informado | revisão da cadeia | "Preço final SEM frete (a fonte não informa)" |
| 10 | Pelando lia **GUID "894d" como 894 dias**: item de 4 min vira "antigo" e não alerta | cobertura de 1,28 milhão de minutos na medição | tag descartada e regex ancorada; teste com o GUID real |
| 11 | **HardMOB nunca poderia alertar:** a lista não traz hora, então nenhum item é "fresco" | 0% de hora na medição | hora da primeira vista, só para ids novos |
| 12 | **Promobit: `?page=N` devolvia sempre os mesmos 12 itens** (cobertura de 9 min para ciclo de 10) | medição de cobertura | paginação por cursor (`?after=`): 42 min; o radar passa a medir e avisar |
| 13 | **Ofertas no preço que já monitoramos viravam ALTA** (8 de 24 reais; ALTA passou de 20 para 12) | reencenação das ofertas reais | exige 3% de melhora sobre o melhor preço atual (seção 5) |
| 14 | Limite diário de 6 barrava até CRÍTICA validada; harness vazava conexão de banco | revisão e teste de mutação | CRÍTICA ignora o limite; harness robusto |

---

## 1. Evidências de reconhecimento de ofertas reais

**Amostra rotulada:** `tests/corpus/radar_ofertas_rotuladas.yaml`, 85 itens, cada um com a origem declarada.

| Origem | Itens | O que é |
|---|--:|---|
| `real_historico` | 16 (13 + 3 ambíguos) | títulos reais de ofertas do Promobit vistos pelos seus rastreadores (14-21/11), sem o nome de quem postou |
| `real_ao_vivo` | 8 | títulos reais lidos ao vivo no Pelando em 21/11 (todos negativos genuínos) |
| `real_cotacao_independente` | 8 | slugs de links reais em `projetos/*/cotacoes.csv`, coletados em 05/10 e 18/11 por **outras sessões**, com `produto_id` rotulado por elas **antes do catálogo do radar** |
| `documentado` | 11 | ofertas reais do `STATUS.md` (preço e loja reais; **o título foi reconstruído**) |
| `construido` | 42 (38 + 4 ambíguos) | variações que escrevi para exercitar cada regra (otimista: não é dado de mercado) |
| ambíguos (total) | 7 | 3 reais + 4 construídos, contados à parte (fora de precisão e recuperação) |

**Reencenação de ofertas reais pela cadeia de produção** (`python -m radar homologar --reais`): banco temporário semeado com o **histórico real** de preços desta máquina, alertas ligados só em memória, nada enviado.

| Oferta real | Loja | Preço | Reconheceu | Melhor atual conhecido | Decisão do radar |
|---|---|--:|---|--:|---|
| Dreame F10 (anúncio com "Passa Pano") | ML / Amazon | R$ 1.102,00 / 1.136,50 | `dreame_f10` | R$ 1.994,05 | **ALTA**, alerta |
| K800 Pro **127V** relâmpago (18/11, durou menos de 10 min) | KaBuM | R$ 959,00 | `k800_pro_127v` | R$ 1.199,98 | **ALTA**, alerta |
| K800 Pro **sem voltagem no título** | KaBuM | R$ 1.079,00 | `k800_pro_127v` + aviso | R$ 1.199,98 | MÉDIA (aviso de voltagem barra o alerta) |
| K800 Pro **220V** (`Ksar81020pt`) | Amazon | R$ 1.066,97 | **não reconhece** | | nada (voltagem errada, certo) |
| Elgin Eco Inverter III 12k | Amazon | R$ 1.799,00 | `elgin_12k` | R$ 1.865,60 | **ALTA** (3,6% melhor) |
| Elgin "Eco III" (nome alternativo) | Amazon | R$ 1.895,00 | `elgin_12k` + aviso | R$ 1.865,60 | BAIXA |
| Philco PAC18FTW | WebContinental / Friopeças | R$ 2.099,01 / 2.299,00 / 2.248,00 | `philco_18k` | R$ 2.569,00 | **ALTA** nas três (2 geraram mensagem; 1 suprimida por duplicidade de 24 h) |
| Chuveiro Loren Shower | ML | R$ 87,16 / 76,49 / 79,00 | `loren_shower_6800_220v` | R$ 111,89 | **ALTA** nas três, **mas sem mensagem** na reencenação (2 barradas pelo limite diário de 6, já consumido por ofertas anteriores; 1 duplicada). Ver risco na seção 5 |
| K800, Tapo, S40C, Agratto, Midea Lite/Ecomaster, Elgin 18k, Philco, Dreame: **o preço que o relatório já mostra** | várias | = ao monitorado | corretos | = ao preço | **sem alerta** (não é novidade) |

**Lote ao vivo de 21/11** (140 títulos de oferta de produto em Promobit, Gatry, Pelando e HardMOB): 0 casados. Triagem ampla independente do catálogo (marca, categoria ou apelido de qualquer dos 12 produtos): 7 títulos, **todos revisados à mão**: Hisense 12.000 BTU (2), KaBuM smart hub, cooktop Philco, lava-louças Midea, Elgin Eco Inverter III de **9.000** BTU (2). **Nenhum é um dos 12 produtos.** Logo 0 falso positivo e 0 falso negativo nesse lote.

## 2. Resultados dos testes positivos e negativos

`python -m radar avaliar` (precisão = TP/(TP+FP); recuperação = TP/(TP+FN); IC 95% de Wilson):

| Grupo | TP | FP | FN | TN | Precisão | Recuperação (IC95) | Falso positivo (IC95) |
|---|--:|--:|--:|--:|--:|---|---|
| **Linha de base, antes das correções** (75 itens) | 36 | 0 | **1** | 31 | 1,00 | 0,973 | 0,0 |
| Total depois (85 itens) | 42 | 0 | 0 | 36 | 1,00 | 1,00 (0,916 a 1,0) | 0,0 (0 a 0,096) |
| **Independentes** (`real_cotacao_independente` + `real_ao_vivo`) | 3 | 0 | 0 | 13 | 1,00 | 1,00 (**0,438** a 1,0) | 0,0 (0 a **0,228**) |
| Lote ao vivo de 21/11 | n/a | 0 | 0 | 133 | n/a | n/a | 0,0 (0 a **0,028**) |
| Casos ambíguos com o comportamento esperado | | | | | | 7 de 7 (antes: 2 de 7) | |

**Como ler sem se enganar:**
- O "100%" do total **não é independente**: os itens reais do histórico eu já tinha visto ao ajustar o catálogo, 42 itens eu mesmo construí e os 11 documentados têm título reconstruído. O número que sustenta generalização é o dos **independentes**, e ele tem **só 3 positivos**: o intervalo de confiança inferior da recuperação é **0,44**. Isso significa que a amostra não consegue excluir que o radar perca mais da metade das ofertas reais que ainda não vimos.
- O que dá confiança real é o conjunto: os 3 independentes passaram (inclusive com "agrato" e "air volution" na URL), o lote ao vivo não teve falso positivo em 133 negativos (limite superior 2,8%) e a reencenação reconheceu 24 de 24 ofertas reais.
- **Para melhorar a medição:** cada oferta real nova dos 12 produtos que aparecer deve entrar no corpus rotulada. Quanto mais itens independentes, mais estreito o intervalo.

## 3. Cupons genéricos cruzados com os produtos

`python -m radar cruzar` (ao vivo: lê os cupons de loja de Promobit, Gatry, Méliuz e Pelando e cruza com o **último preço bom** de cada produto naquela loja). Rodada de 21/11 11:3x: 298 publicações, **466 pares** cupom de loja x produto com preço na loja (sem duplicatas).

| Resultado | Pares | Principais motivos |
|---|--:|---|
| **CANDIDATO** (vale testar no carrinho) | **4** | todos o mesmo cupom, `BLACK150` da Amazon |
| Indeterminado | 342 | "itens selecionados" (105), sem código (95+), 20% a 40% sem teto nem regra (72, heurística), "até X%" só teto (15), código sugere outra categoria (8, `TV200`/`TV400`) |
| Inaplicável | 120 | outra categoria/produto (83: iPhone, jogos, notebooks, processadores, bebidas), primeira compra (18), só no app (9), compra mínima (6), expirado (4) |

**Os 4 candidatos** (estimativa, **nada confirmado em carrinho**, status do cupom continua `NAO_CONFIRMADO`):

| Produto | Loja | Preço atual | Com `BLACK150` (R$ 150 em compras acima de R$ 1.499) | Supera o melhor atual? |
|---|---|--:|--:|---|
| Dreame F10 | Amazon | R$ 1.994,05 | ~R$ 1.844,05 | sim |
| Elgin 12k | Amazon | R$ 1.865,60 | ~R$ 1.715,60 | sim |
| Midea Ecomaster 12k | Amazon | R$ 2.089,05 | ~R$ 1.939,05 | sim |
| Philco 18k | Amazon | R$ 2.569,00 | ~R$ 2.419,00 | sim |

**O que isto significa:** é uma economia que o radar anterior **não detectaria** (o cupom não cita o produto). O texto do cupom diz "R$ 150 de desconto em compras acima de R$ 1.499, aplique na página do produto" e não cita categoria nem seleção. Isso **não prova** que vale para esses produtos: pode ter restrição de vendedor ou categoria que o texto não menciona. O Tapo (R$ 854) corretamente não atinge o mínimo.
**Como confirmar (só você, tem login):** no carrinho da Amazon, com o Elgin 12k ou o Philco 18k, aplicar `BLACK150` e ver o total. Se funcionar, `python -m radar validar <id> --por "carrinho Amazon 21/11"`.

**O primeiro resultado do cruzamento estava errado e eu o descartei.** A 1ª versão marcou 268 pares como "aplicável" porque lia "em produtos Amazon" (texto genérico do cartão do Promobit, sem regra nenhuma) como "escopo amplo". Os cupons reais mostram a realidade: KaBuM "itens selecionados", "processadores", "notebooks"; Amazon "primeira compra no app", "iPhone", "jogos". A versão final é estrita (candidato só com **código, valor conhecido, sem restrição e sem limitador de escopo**), tem duas heurísticas que declaro como tal (percentual de 20% ou mais sem teto; código que sugere outra categoria) e foi testada com os cupons reais (`tests/test_radar_cruzamento.py`, 18 testes).

**Produto equivalente (informativo, nunca alerta)** (`python -m radar equivalentes`): **Hisense Hi-Efficiency 12.000 BTU inverter, só frio, 220V**, Amazon, **R$ 1.710,00**, visto em Promobit, Gatry e Pelando (publicado entre 10:44 e 11:23). É R$ 155,60 (8,3%) mais barato que o seu melhor 12k (Elgin R$ 1.865,60). Ele **nunca passou pelo seu gate de qualidade** (marca, assistência, garantia nacional, nota): é uma pista para decidir se abre uma pesquisa, não uma recomendação.

## 4. Falsos positivos e falsos negativos

| Tipo | Caso | Onde | Estado |
|---|---|---|---|
| **FN** | Dreame F10 "Passa Pano ... Limpeza de ..." (R$ 1.136,50) | corpus H02 | **corrigido** (defeito 1) |
| FN potencial | "HW Inverter Elgin Eco III" sem SKU | H08, A03 | corrigido como match **fraco** (MÉDIA no máximo) |
| FN potencial | URLs com "agrato" e "air volution" sem SKU | C15, C16 | corrigido |
| **FP em massa** | cruzamento: 268 pares "aplicável" | cruzamento v1 | **corrigido** (defeito 6) |
| **FP de utilidade** | ALTA para preço igual ao já monitorado (8 de 24 ofertas reais) | reencenação | **corrigido** (defeito 13) |
| FP evitado | K800 220V, Dreame F10 Pro, RV20 Mop, S40 sem Pro, 9.000 BTU, quente/frio, 127V, acessórios, outras marcas | negativos N01 a N22, L01 a L08, I04 a I08 | corretos |
| Risco residual | oferta de **título curto sem voltagem nem SKU** de um produto que só existe numa voltagem | | reconhece com aviso e **não alerta** |
| Risco residual | produto equivalente (Hisense) fora do catálogo | | por desenho não alerta; sai em `radar equivalentes` |
| Não medido | recuperação em ofertas reais **ainda não vistas** | | só 3 independentes: IC95 de 0,44 a 1,0 |

## 5. Estado real da homologação de alertas

| Item | Estado | Evidência |
|---|---|---|
| Alertas reais | **DESLIGADOS** | `enviar: false`, `homologado_em: null`; `python -m radar status` mostra "EM SOMBRA" |
| Cadeia de ponta a ponta com cenários sintéticos | **16 de 16** | `python -m radar homologar`: cupom válido, cupom expirado, novo menor preço (e depois validado: CRÍTICA), voltagem errada, oferta duplicada, falha de internet no envio (fila de 30 min), falha de internet na coleta, alerta vencido encerrado na fonte (descartado), alerta vencido ainda ativo (entregue rotulado), título sem voltagem, nome alternativo, oferta antiga, frete conhecido, **sem novidade**, configuração real (sombra), cupom de loja |
| O teste detecta defeitos? | **sim** | mutação: 6 sabotagens da cadeia (decidir sempre envia, revalidação sempre ativa, catálogo ignora voltagem, ranking sem teto, cupom expirado como válido, texto sem "estimado") **detectadas por 6 de 6** |
| Envio real controlado | **feito, 1 mensagem** | 21/11 (manhã), `homologar --enviar-teste-whatsapp --confirmo`; cabeçalho "TESTE DO RADAR DE COMPRAS (mensagem sintética, não é oferta real)", sem link, diz que os alertas reais seguem desligados; fila vazia depois |
| Reencenação com ofertas reais e histórico real | feita | seção 1: 24 de 24 reconhecidas; 12 ALTA (6 mensagens, 3 duplicadas, 3 barradas pelo limite); sem alerta nas que são o preço já monitorado |
| **Risco do limite diário** | decisão sua | o limite de 6/dia é por **ordem de chegada**: na reencenação, as 3 ofertas do chuveiro (R$ 76 a R$ 87, ótimas) foram barradas porque ofertas anteriores consumiram os 6. Em dia de rajada (Black Friday, 27/11) isto pode esconder a melhor oferta. `limite_diario` é configurável |
| Alerta de oferta ao vivo dos seus produtos | **NÃO exercitado** | nenhuma apareceu (0 de 140 hoje) |
| Ativação | **pendente de você** | `alertas.enviar: true` **e** `alertas.homologado_em` preenchido |

**Regra de urgência após a fase 3** (o que faz uma oferta virar alerta): produto reconhecido **e** voltagem/modelo sem aviso **e** status `PROVAVEL`/`VALIDADO` **e** oferta de até 6 h **e** **pelo menos 3% abaixo do melhor preço atual já monitorado** (ou 15% abaixo da mediana) **e** não duplicada em 24 h **e** limite diário de 6 (CRÍTICA ignora o limite). Cupom não confirmado não vira "preço final": é estimativa rotulada, e o frete só é "entregue" quando a fonte o informa.

## 6. Integridade do Git e riscos entre sessões

Verificado **só lendo** (nenhum `stash`, `checkout`, `reset`, `clean`, `restore`, `add`, `commit` ou `push`; o status do Git foi comparado antes e depois e é idêntico).

| Fato | Valor |
|---|---|
| HEAD | `0b84a7a` (19/11), em dia com `origin/main` (0 à frente, 0 atrás); 0 stashes; sem `index.lock`, merge ou rebase em andamento |
| Do radar (meu) | 83 caminhos: `radar/` (pacote), `config/radar_*.yaml`, `docs/ecossistema/`, `tests/test_radar_*.py`, `tests/corpus/`, `scripts/rastrear_*.py`, `scripts/rodar_rastreador_robos.ps1`, `requirements.txt`, `tests/test_rastrear_chuveiro_bf.py` |
| **De outra sessão (não toquei)** | 30 caminhos do projeto **climatizador**: `config/categorias.yaml` (bloco `climatizador`, +19 linhas), `base-conhecimento/especificacoes/climatizador.md`, `produtos/climatizador/`, `projetos/2026-climatizador-ventisol-torre-3-6l/`. Último arquivo escrito às 10:22; nada novo desde então |
| **Arquivo misto** | `STATUS.md` tem a seção "Climatizador Ventisol" (da outra sessão) **e** as minhas. `git add STATUS.md` inteiro levaria o trabalho dela junto |

**Riscos entre sessões e o que fiz:**

| Risco | Gravidade | Mitigação |
|---|---|---|
| Os scripts **rastreados** já fazem `import radar`, mas `radar/` e `config/radar_*.yaml` estão **sem versionar**. Um `git stash -u`, `git clean` ou `git checkout -- .` feito por outra sessão **apagaria o pacote e quebraria os relatórios das 14h e 20h** | **alta** | backup do código **fora do Git**: `python -m radar git-escopo --backup` (zip em `...\dados-privados\radar\backups\`; mantém os 6 mais recentes). O commit é a proteção definitiva |
| Commit misturando o climatizador | média | `python -m radar git-escopo` classifica tudo e imprime os comandos para **o seu** commit; para o `STATUS.md`, `git add -p` aceitando só as seções do radar |
| `config/categorias.yaml` está com CRLF na cópia de trabalho (aviso do Git) | baixa | é da outra sessão; não toquei |
| Outra máquina rodando o fluxo antigo ou duplicando | média | só `LAPTOP-3NSQG27T` é oficial (`config/radar_maquina.yaml`). **Provado com a configuração real:** fingindo ser "OUTRO-NOTEBOOK", `executar_job('relatorios')`, `executar_job('varredura')`, `varredura.executar()` e o script de relatório direto retornam sem coletar, enviar nem gravar (contagens do banco idênticas). Só existem 2 tarefas de compras no Windows desta máquina |
| A outra máquina só passa a ter a trava **depois do commit e do pull** | média | até lá nada roda lá (o estado de 19/11 dela não registra tarefa de compras); não toquei nela |

## 7. Pendências que dependem exclusivamente de você

1. **Autorizar o commit** do radar (e decidir o que fazer com o climatizador). Comandos sugeridos: `python -m radar git-escopo`. **Enquanto não houver commit, o backup local é a única proteção do código.**
2. **Testar o `BLACK150` no carrinho da Amazon** (Elgin 12k ou Philco 18k): é a única economia nova que o cruzamento achou; só você tem o login.
3. **Decidir sobre o Hisense 12k a R$ 1.710** (8,3% abaixo do seu melhor): abrir ou não uma pesquisa de qualidade/garantia.
4. **Telegram:** o procedimento está em [12-telegram-passo-a-passo.md](12-telegram-passo-a-passo.md) (5 minutos, no seu PC; criar `api_id`/`api_hash`, `python -m radar telegram-login`, `telegram-listar`, colar os canais). O radar **só lê** os canais que você escolher; nunca conversa privada nem o bot do Coral.
5. **Homologar os alertas** quando decidir: preencher `homologado_em` em `config/radar_regras.yaml` e `enviar: true`. Recomendo antes rodar uns dias em sombra e conferir `python -m radar alertas`.
6. **Confirmar duas leituras** que são suas: o `robots.txt` do Gatry (a API `/v1/` é permitida) e o uso do HTML público do Pelando.
7. **Alimentar o corpus** com ofertas reais novas dos 12 produtos (ou me avisar quando vir uma) para estreitar o intervalo de confiança.

---

## Anexo A. Qualidade e estabilidade dos 5 coletores (medida ao vivo em 21/11, `python -m radar qualidade-fontes`)

| Fonte | Ofertas | Cupons | Preço | URL | Hora | Frescas 6 h | Cobertura da lista | Latência | Valor marginal (itens só dela) |
|---|--:|--:|--:|--:|--:|--:|---|--:|--:|
| Promobit | 95 | 64 | 98% | 100% | 100% | 75% | **42 min** (antes 9) | 7,9 s | 85% |
| Gatry | 30 | 10 | 100% | 100% | 100% | 30% | 16 h | 1,2 s | 93% |
| Pelando | 18 | 2 | 100% | 100% | 100% | 100% | 61 min | 0,8 s | 61% |
| HardMOB | 32 | 0 | 91% | 100% | **0%** (hora estimada pela 1ª vista) | n/d | n/d | 1,7 s | 100% |
| Méliuz | 0 | 110 | | | 100% | | | 2,8 s | só cupom de loja |

- **Estabilidade:** nos ciclos medidos, 100% de disponibilidade nas 5 fontes e 0 erros; **a janela é curta (poucas horas)**, então isto mostra ausência de falha recente, não confiabilidade de longo prazo. Variação de itens por ciclo: 0% a 3%.
- **Cobertura** = até onde a lista alcança para trás; precisa ser maior que o intervalo entre ciclos (10 a 15 min). O radar agora **mede isso a cada ciclo** e o relatório de efetividade avisa se a lista cobrir menos que o intervalo.
- **Novas fontes:** nenhuma foi adicionada. Critério medido (em `radar/qualidade.py`): só entra se trouxer itens que as demais não trazem, tiver preço/URL/hora confiáveis e for estável. As 4 fontes de oferta já se complementam (61% a 100% de itens exclusivos), mas **nenhuma candidata nova** foi medida com vantagem; X, Instagram e Facebook continuam inviáveis sem login/API paga (429, 429, 400).
- **Frescor do Gatry (30%)** é esperado: a lista `approved` mistura promoções recentes e antigas.

## Anexo B. Testes e comandos desta fase

**Suíte completa: 798 testes, 0 falhas** (337 s; eram 750 ao fim da fase 2). `python scripts/central_compras.py checar-segredos --strict`: limpo.
Arquivos novos: `test_radar_cruzamento` (18), `test_radar_cenarios` (6), `test_radar_equivalentes` (5), `test_radar_git_escopo` (5) e ampliações em `test_radar_gatry_pelando` (Pelando GUID e cursor do Promobit), `test_radar_resiliencia` (hora por primeira vista), `test_radar_homologacao` (cobertura, limite), `test_radar_fontes_e_alertas` (novidade) e `test_radar_cupons_catalogo` (elegibilidade).

## Comandos

`python -m radar avaliar` (precisão/recuperação) | `cruzar` (cupons de loja x produtos) | `equivalentes` | `homologar` (16 cenários) | `homologar --reais` | `homologar --enviar-teste-whatsapp --confirmo` | `qualidade-fontes` | `git-escopo [--backup]` | `telegram-status`.
Banco: migração 3 (`validacoes_manuais`) aplicada com backup automático.

## Anexo C. Limites do que foi provado

- Nenhuma oferta **ao vivo** dos 12 produtos apareceu: a cadeia ao vivo ainda não viu um caso positivo.
- A recuperação em ofertas reais ainda não vistas tem **IC95 inferior de 0,44** (3 positivos independentes).
- Os 11 itens `documentado` têm **título reconstruído** (preço e loja são reais).
- A estabilidade dos coletores foi medida em poucas horas.
- O cruzamento de cupons é **estimativa**; nenhum cupom foi confirmado em carrinho.
- Telegram e leitor de grupos do WhatsApp continuam sem teste real (dependem de você).
