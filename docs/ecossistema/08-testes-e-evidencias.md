# 08. Testes e evidências (20/11/2026)

Tudo abaixo foi executado de verdade nesta máquina. O que não foi feito está dito.

## Camada 1: testes automatizados

| Suíte | Resultado |
|---|---|
| Linha de base antes das mudanças | 603 testes, 0 falhas (410 s) |
| Suíte completa depois (`python -m unittest discover -s tests`) | **683 testes, 0 falhas** (338 s) |
| Novos: `test_radar_nucleo` (24), `test_radar_correcoes` (3), `test_radar_cupons_catalogo` (31), `test_radar_fontes_e_alertas` (20) e 2 de regressão da Leroy | +80 |
| `python scripts/central_compras.py checar-segredos --strict` | limpo |

Cobertura: banco (migração, idempotência, rollback com backup), trava (dupla execução, órfã), histórico (degradação, importação idempotente, estatísticas sem dados),
fila de reenvio, ciclo (coleta boa, degradada, retentativa, falha de envio e reenvio, dry-run), jobs (falha isolada, timeout, trava, UTF-8, próximo disparo, YAML real),
cupons (exemplos `CASATECH10`, `70OFF`, `25PRIMEBF`, `PRIMEIRA20BF`, Pix, app, cashback, frete, teto, mínimo, validade, placeholders, estados),
catálogo (127V x 220V, 12k x 18k, quente/frio, Pro/Plus/Lite/Max, S40C x S40 Pro, SKU de outro produto, acessório, importado),
fontes (Promobit nos 2 formatos, layout quebrado, página fora do ar, HardMOB, Telegram com identidade, Méliuz), ranking, deduplicação, limite diário, horário, sombra,
varredura com fonte falhando.

**Teste de mutação:** sabotei `esta_degradada` para sempre devolver falso; 6 testes falharam; restaurado, 24/24 verdes.

## Camada 2: dry-run sem envio real

- `rastrear_chuveiro_bf.py --sem-persistir`: 62 s, sem erro, estado intocado (`LastWriteTime` inalterado); comparou contra a última coleta boa.
- `rastrear_robos_bf.py --sem-persistir` e `rastrear_ares_bf.py --sem-persistir`: terminaram, mensagens montadas, sem gravação.
- `python -m radar varrer --sem-enviar -v`: Promobit 127 itens, HardMOB 32, Méliuz 148, Telegram público 0 (nenhum canal habilitado).

## Camada 3: ponta a ponta controlado (seus próprios canais, sem compra, sem postagem em comunidades)

| O quê | Resultado |
|---|---|
| Agendador disparou a varredura sozinho às 19:50:01 | resultado `0`; registro `varredura/varrer: ok` |
| **Relatório das 20:00 pelo novo caminho** (`radar executar relatorios`) | robos ok, ares ok, chuveiro ok; 3 mensagens confirmadas no chat; tarefa `LastTaskResult 0`; duração 4 min 14 s (antes 11,5 min e falha) |
| Comparação do relatório das 20h | "ALTEROU DESDE 20/11 08:00" (última coleta **boa**), não mais contra a coleta degradada das 14:34 |
| Mensagem de teste do canal do alerta (`radar testar-envio --confirmo`) | 1 mensagem enviada e confirmada; fila vazia |
| Telegram: proteção de identidade ao vivo | `t.me/s/promobit` bloqueado ("titulo 'OFERTAS PC GAMER...' sem 'Promobit'"); com a identidade real do canal, 20 mensagens lidas, preço e hora extraídos |

## Fase 2 (21/11/2026)

**Suíte completa:** 750 testes, 0 falhas, 371 s (fase 1 terminou em 683). A 1ª rodada da fase 2 teve 1 falha legítima: o scanner de segredos do próprio repositório
acusou o nome do parâmetro de senha de duas etapas na chamada de login do Telegram (nome de parâmetro, não segredo); corrigi o código sem enfraquecer a regra. `checar-segredos --strict`: limpo.
Novos arquivos: `test_radar_homologacao` (19), `test_radar_recuperacao` (7), `test_radar_gatry_pelando` (12), `test_radar_telegram_conta` (10),
`test_radar_whatsapp_grupos` (6), `test_radar_maquina` (4), `test_radar_resiliencia` (8) e ampliações em `test_radar_nucleo`.

**Testes reais (não simulados) desta fase**

| O quê | Resultado |
|---|---|
| Recuperação do relatório das 08h (notebook suspenso 02:26-09:37) | tarefa disparada pelo `radar recuperar`, 3 de 3 entregues às 09:54-09:59, `LastTaskResult 0` |
| Job morto por `taskkill /T /F` no meio | registro `rodando` virou `interrompida`, trava órfã tomada, job seguinte `ok` |
| Internet derrubada (proxy inexistente) | **achou bug** (Méliuz escondia erro; fonte sem configuração contava como "ok"): corrigido; 98 s → 31 s, saída 1, 5 fontes `erro` |
| WhatsApp indisponível (CDP em porta sem serviço) | 3 tentativas, `ECONNREFUSED` explícito, nada enviado, mensagem na fila |
| Migração 2 no banco real | backup automático `radar-...-pre-migracao.db`, esquema v2 |
| Reconstrução do banco a partir dos JSONL | 102 observações; correção do chuveiro aplicada sem tocar no bruto (`60.65`, `preco_corrigido 122.45`) |
| `radar auditar` nos 3 históricos | 1 suspeita real (já corrigida) |
| Revalidação ao vivo | Promobit: ativa / preço subiu / `FINISHED`; Gatry: ativa / 404 |
| Gatry ao vivo | 40 itens (30 promoções + 10 cupons), `NO LINK` filtrado |
| Pelando ao vivo | 20 de 20 itens completos; Chrome automatizado bloqueado pelo WAF (registrado, não contornado) |
| Telegram | Telethon 1.46 instalado só no Python do radar; API conferida; **sem login real** |
| Mensagens reais enviadas ao seu WhatsApp nesta fase | só os 3 relatórios da recuperação (09:54-09:59). Nenhum alerta urgente |

**Relatório de efetividade, 1 ciclo completo de todas as fontes (21/11 10:45, nada enviado)**

| Fonte | Publicações | Seus 12 produtos | Cupons extraídos / elegíveis | Diagnóstico |
|---|--:|--:|--:|---|
| Promobit | 126 | 0 | 38 / 35 | coletando; nenhuma era dos seus produtos |
| Gatry | 40 | 0 | 10 / 9 | idem |
| Méliuz | 110 | 0 | 110 / 56 | idem (só cupons de loja) |
| HardMOB | 32 | 0 | 4 / 4 | idem |
| Pelando | 20 | 0 | 3 / 2 | idem |
| Telegram público e Telegram sua conta | 0 | 0 | 0 / 0 | **NÃO CONFIGURADAS** (não é ausência de ofertas) |
| **Total** | **328** | **0** | **165 / 106** | nenhuma falha de coletor neste ciclo |

Motivos de descarte: 186 cupons de loja sem produto, 139 fora do catálogo, 2 "quase casou: outra capacidade BTU" (Elgin Eco Inverter III de **9.000** BTU), 1 "quase casou: mesma marca, outro produto" (micro-ondas Philco).
"Elegível" significa só que nenhuma restrição conhecida impede o seu perfil (não é primeira compra, não usa app, paga no Pix) e que o cupom não está expirado; **não prova que funciona**, e nenhum foi aplicado a preço (nenhuma oferta sua apareceu).
Conclusão honesta: neste momento não há ausência de coleta e sim ausência de ofertas dos 12 produtos nessas fontes (confirmada por varredura manual dos títulos por marca/categoria, que também mostrou que o catálogo não estava rígido demais).

## Dados capturados nos testes (reais, `fonte=web`)

- Promobit, cupons de loja da KaBuM: 15% de desconto, R$ 300 de desconto, R$ 400 de desconto em produtos KaBuM (status da fonte `APPROVED`; elegibilidade por produto **não** verificada).
- Méliuz, cupons da Amazon com código: `CUPONSBF` (até 50%, "Black dos Sonhos") e `DEVOLTA1000` (até R$ 1.000 OFF em eletrônicos, regra restrita a iPhone 18 pela Amazon), entre 148 cupons de 6 lojas. Não validados no carrinho.
- Nenhuma oferta de comunidade casou com os 12 produtos do catálogo nesses ciclos: nenhum alerta (nem em sombra) foi gerado até aqui.

## Reversão testada

Rollback do banco com backup (`BancoTest`). Reversão da tarefa do Windows: XML original salvo e comando `agendar --restaurar` implementado, **mas a restauração em si não foi executada** (não houve motivo para desfazer o cutover).

## O que NÃO foi comprovado

- Alerta urgente real saindo ao WhatsApp a partir de oferta de comunidade: provado só em teste automatizado com envio simulado (nenhuma oferta real casou ainda) e pelo teste de envio do canal.
- Execução após reinicialização do Windows e após suspensão com a nova tarefa: depende de `StartWhenAvailable` (configurado e lido de volta), mas não foi forçada.
- Validação de cupom em carrinho (não implementada).
- Telegram de canais privados, grupos de WhatsApp e redes sociais: bloqueados ou inviáveis (ver 04).
- Execução em outras máquinas.

## Recursos consumidos

Varredura: ~160 itens por ciclo em 3 a 5 requisições HTTP simples (sem navegador), ~3 s. Relatórios: o mesmo Chrome headless de antes, 3 passos em ~4 min.
Banco: dezenas de KB. Nenhum serviço residente novo, nenhuma segunda instância de Chrome além da já existente do `zap-vivo`.
