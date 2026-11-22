# 10. Pendências e melhorias

Estado detalhado por funcionalidade: [11-matriz-de-status.md](11-matriz-de-status.md).

## Bloqueios (dependem de você ou de acesso que não existe)

- [ ] **Telegram com sua conta:** falta o login (passo seu). Adaptador pronto e testado com leitor falso. Procedimento exato em 09.
- [ ] **WhatsApp, leitor de grupos:** lista de autorização criada e vazia. O leitor só será escrito com um grupo que você autorize e numa janela sem relatório (abrir conversa marca como lida e disputa a aba com os envios).
- [ ] **X, Instagram, Facebook:** sem via gratuita e sustentável (429, 429 e 400 sem login). Alternativas: API paga do X; Graph API "Business Discovery" do Instagram com conta comercial **sua** (nunca a institucional da 5ª Cia). Recomendado não investir agora: os perfis de ofertas republicam em fontes já cobertas.
- [ ] **Keepa:** chave de API paga.
- [ ] **Validação de cupom no carrinho:** exige login nas lojas e arrisca a conta; `VALIDADO` continua manual (`radar validar`).
- [ ] **Homologação dos alertas urgentes:** ainda em sombra por decisão de segurança. Precisa de ofertas reais dos seus produtos para ser exercitado de ponta a ponta.

## Adições da fase 3 (21/11/2026, tarde)

Relatório completo: [13-relatorio-fase-3.md](13-relatorio-fase-3.md).

- [ ] **Autorizar o commit do radar**, separando o projeto climatizador (outra sessão) e usando `git add -p STATUS.md`. Enquanto não houver commit, o pacote `radar/` só existe na árvore de trabalho (backup: `python -m radar git-escopo --backup`).
- [ ] **Testar `BLACK150` no carrinho da Amazon** (Elgin 12k ou Philco 18k): único candidato de economia que o cruzamento achou (R$ 150 em compras acima de R$ 1.499); `radar validar` depois.
- [ ] **Hisense 12.000 BTU a R$ 1.710** (8,3% abaixo do seu melhor 12k): decidir se abre pesquisa de qualidade/garantia (`radar equivalentes`).
- [x] **`limite_diario` (6, por ordem de chegada):** resolvido na fase 4 com priorização por pontuação e orçamento (ver adições da fase 4).
- [ ] **Corpus:** acrescentar cada oferta real nova dos 12 produtos, rotulada (hoje só 3 positivos independentes; IC95 inferior da recuperação 0,44).
- [ ] **Alerta ao vivo ainda não exercitado:** nenhuma oferta ao vivo dos 12 produtos apareceu (0 de 140).
- [ ] Melhorias (priorização por qualidade: feita na fase 4): incluir cupons de loja CANDIDATO no relatório das 08h/14h/20h; revalidação também para Pelando e HardMOB.

## Adições da fase 4 (21/11/2026, tarde/noite)

Relatório completo: [14-relatorio-fase-4.md](14-relatorio-fase-4.md). O `limite_diario` por ordem de chegada foi substituído por prioridade e orçamento (o item de decisão acima agora é sobre os NÚMEROS do orçamento).

- [ ] **Decidir o orçamento de alertas** (seção `prioridade` em `config/radar_regras.yaml`): hoje 6 comuns, 3 críticos, 2 de exceção, 2 por varredura, pontuação mínima 40. São valores propostos, sem histórico de uso. Conferir antes com `python -m radar prioridade` (em sombra).
- [ ] **Promobit cobre só ~18 min com ciclo de 10 min:** margem curta, pior na Black Friday. Decidir ciclo mais curto ou paginação mais funda. `python -m radar lacunas` mostra se alguma janela já perdeu ofertas.
- [ ] **Recall de mercado não provado:** 7 positivos reais independentes (IC95 da recuperação 64,6% a 100%). Rotular cada oferta real nova dos 12 produtos como `conjunto: independente`.
- [ ] **Estimativa do HardMOB** (`cobertura_estimada_min: 120`): não medida, a fonte não informa hora. Se quiser medir, comparar com os ids dos tópicos por 1 semana.
- [ ] **Testar `BLACK150` no carrinho** (até a tela de pagamento, sem finalizar) e registrar com `radar validar`. O radar não faz isso sozinho.
- [ ] **Commit do radar** (ver a contagem atual em `radar git-escopo --manifesto`), só com sua autorização; STATUS.md pelo patch, nunca inteiro.

## Adições da fase 6 (21/11/2026, noite)

Relatório: [18-relatorio-fase-6.md](18-relatorio-fase-6.md). Piloto: [17-piloto-controlado.md](17-piloto-controlado.md). **Recomendação: APTO PARA PILOTO, condicionado aos passos abaixo.** A regra de 3 ofertas reais deixou de ser exigência: o risco residual está explícito no doc 17.

- [x] **Teste único de entrega** feito em 21/11 às 21:12 (1 mensagem, 15,6 s, confirmação do mecanismo, fila 0). Falta você conferir no celular que chegou no SEU chat.
- [ ] **Confirmar o destinatário:** depois de ver o teste no SEU chat, preencher `piloto.destinatario_confirmado_em` em `config/radar_regras.yaml`. Sem isso o piloto não envia nada.
- [ ] **Philco 18k PHI200:** o preço anunciado (R$ 2.379) já embute o cupom; a loja cobra R$ 2.579. Só vira oferta se você validar o cupom no carrinho (`radar validar`). BLACK150 idem.
- [ ] **Black Friday:** criar a tarefa dedicada do Promobit (`python -m radar agendar --aplicar --job varredura_promobit_bf`; cria SÓ essa tarefa e não toca nas duas atuais). Ela só dispara de 26/11 00:05 a 01/12 00:00 e se apaga sozinha. Sem ela, a janela da configuração só vale para a varredura normal (a cada 10 min), sem ganho.
- [ ] **Ativar o piloto** (3 edições suas em `config/radar_regras.yaml`) só depois dos itens acima e do commit.
- [ ] **Commit** (escopo no relatório 18, seção 7).
- [ ] Telegram: login seu (guia 12).

## Adições da fase 5 (21/11/2026, noite)

Relatório: [15-relatorio-fase-5.md](15-relatorio-fase-5.md). Plano: [16-plano-de-ativacao.md](16-plano-de-ativacao.md). **Recomendação: NÃO APTO para ativar hoje** (faltam evidências ao vivo e o teste de entrega).

- [ ] **BLOQUEIO: evidência ao vivo.** Só 1 candidato real em sombra (Philco 18k R$ 2.379); o plano exige 3 aprovados por você, sem falso positivo. `python -m radar ativacao` mostra o estado.
- [ ] **Teste controlado de envio** (1 mensagem TESTE ao seu chat): `python -m radar homologar --enviar-teste-whatsapp --confirmo`. Fecha a latência de entrega, hoje só estimada.
- [ ] **Philco 18k a R$ 2.379 com cupom PHI200 (WebContinental):** conferir se o preço já inclui o cupom. O radar não sabe e não conta o cupom.
- [ ] **Promobit com margem curta** (pior cobertura 14 min contra ciclo de 10): decidir ciclo de 5 min só para o Promobit (e só no dia da Black Friday) em vez de aumentar tudo. Chance de ler promoção de 5 min hoje: ~50%.
- [x] **Commit e push do radar** feitos em 21/11/2026 com a sua autorização (escopo em 18-relatorio-fase-6.md, seção 7). Nas outras máquinas: `git pull` e `python -m radar migrar --reconstruir`; a trava mantém a máquina oficial como única ativa.
- [ ] Telegram: login seu, depois escolher só os canais de oferta.
- [ ] Rotular, no corpus independente, cada oferta real nova dos 12 produtos que você confirmar.

## Riscos e decisões suas

- [ ] **Gatry:** a API é pública e o `robots.txt` diz `Allow: /v1/`, mas o mesmo arquivo tem `Disallow: /*?`. Li pela regra de maior especificidade (permite). Se preferir a leitura restritiva, desligue `gatry` em `config/radar_fontes.yaml`.
- [ ] **Pelando:** só funciona porque o HTTP comum não é bloqueado; o Chrome automatizado é (e não foi contornado). Pode quebrar sem aviso; vira `erro` visível no relatório de efetividade.
- [ ] **Outra máquina (`LAPTOP-173MUN6G`):** nada foi alterado lá. Depois do commit e do `git pull`, a trava a deixa inativa. Confirmar que ela não tem tarefas antigas de compras (o estado de 19/11 não registra nenhuma).
- [ ] **Série de preços por máquina:** histórico e banco ficam fora do Git por regra (CEP/endereço). Máquina oficial: `LAPTOP-3NSQG27T`.
- [ ] **Disponibilidade:** notebook que dorme e com Wi-Fi instável. A recuperação cobre os relatórios; a varredura de 10 min não é 24 h.
- [ ] **Histórico curto:** série validada desde 18/11. O ranking exige 3 observações e 1 dia antes de falar em "mínimo", e até a Black Friday (27/11) isso ainda é fraco.
- [ ] **Causa do R$ 60,65 inferida** (`[VERIFICAR]` em `radar_correcoes.yaml`).
- [ ] **Compras Paraguai:** custo efetivo (dólar datado, cota, garantia) segue manual.

## Melhorias de próximo passo

1. Cruzar cupons de loja (Méliuz, Promobit, Gatry) com os preços atuais dos produtos na loja correspondente e alertar ("cupom X derruba o K800 para R$ ...").
2. Comentários do Promobit como sinal de funcionamento ("funcionando", "expirou"), só para ofertas que já casaram com o catálogo.
3. Revalidação para o Pelando (reabrir a página do post) e para o HardMOB (tópico).
4. Mover os três rastreadores para o pacote `radar` e compartilhar `parse_brl` e `enviar_whatsapp`.
5. Painel HTML de leitura alimentado por `radar.db` (opcional).
6. Reconexão automática do `zap-vivo` quando a aba do WhatsApp some.
7. Máquina sempre ligada (mini PC) para a varredura contínua, se o monitoramento precisar de cobertura 24 h.
