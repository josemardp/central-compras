# 03. Arquitetura final

Princípio: **simples**. Biblioteca padrão + PyYAML, um arquivo SQLite, nenhum serviço novo, nenhuma fila externa.
Playwright continua sendo usado só pelos três rastreadores que já o usavam.

```
Agendador do Windows (so dispara)                config/radar_jobs.yaml (fonte de verdade)
  |- 08:00 14:00 20:00 -> python -m radar executar relatorios
  |                         trava "relatorios" -> passos isolados, timeout por passo, log UTF-8
  |                         robos -> ares -> chuveiro   (scripts/rastrear_*_bf.py --enviar-zap)
  |                           coletar -> comparar com ULTIMA COLETA BOA -> (degradada? repete 1x, avisa, nao sobrescreve)
  |                           -> historico.jsonl (append) + radar.db -> WhatsApp (3 tentativas) -> falhou? outbox
  |
  |- a cada 10 min   -> python -m radar executar varredura
                          trava "varredura" -> radar varrer
                            fontes publicas (cada uma isolada, no seu intervalo)
                              promobit | hardmob | meliuz | telegram_publico
                            -> catalogo (identifica produto exato) -> cupons (interpreta, estado, preco final)
                            -> ranking (CRITICA/ALTA/MEDIA/BAIXA vs historico validado)
                            -> alertas (dedup 24h, horario, limite diario, periodo de sombra)
                            -> WhatsApp (trava de envio compartilhada) ou registro em sombra

radar.db (SQLite, ~/.central-compras/dados-privados/radar/)
  observacoes | ofertas | alertas | execucoes | jobs_estado | fontes_saude | outbox | schema_migracoes
```

## Módulos

| Módulo | Responsabilidade |
|---|---|
| `radar/db.py` | esquema versionado, migrações com rollback, backup antes de migrar |
| `radar/trava.py` | execução única por job (PID + idade); `aguardar` serializa envios ao WhatsApp |
| `radar/jobs.py` | lê `radar_jobs.yaml`, executa passos com timeout, registra execuções e falhas consecutivas |
| `radar/agenda_windows.py` | ponte YAML <-> Agendador do Windows (status, aplicar, restaurar, remover) |
| `radar/ciclo.py` | ciclo dos relatórios: última coleta boa, retentativa, aviso de coleta parcial, outbox |
| `radar/historico.py`, `correcoes.py` | leitura do JSONL, detecção de degradação, estatísticas 7/30/90 dias, correções versionadas |
| `radar/catalogo.py` + `config/radar_catalogo.yaml` | produtos canônicos (SKU, variantes, tensão, BTU, acessórios, importado) |
| `radar/cupons.py` | extração, restrições, validade, estados, preço final |
| `radar/ranking.py` + `config/radar_regras.yaml` | classes configuráveis |
| `radar/alertas.py` | deduplicação persistente, anti-spam, mensagem |
| `radar/fontes/*` | um adaptador por fonte; falha de uma não afeta as outras |
| `radar/canais.py` | adaptador do WhatsApp (reutiliza o envio do rastreador; sem credencial, sem 2ª sessão) |
| `radar/cli.py`, `status.py` | camada operacional (`python -m radar ...`) |

## Módulos acrescentados na fase 2 (21/11/2026)

| Módulo | Responsabilidade |
|---|---|
| `radar/recuperacao.py` | detecta slot de relatório sem execução (notebook suspenso) e dispara a própria tarefa do Windows |
| `radar/auditoria.py` | varre o histórico bruto atrás de leituras suspeitas (só leitura) |
| `radar/efetividade.py` | relatório: publicações, casamentos, cupons, descartes; separa erro, vazia e sem configuração |
| `radar/maquina.py` + `config/radar_maquina.yaml` | só a máquina oficial coleta, envia relatório e alerta |
| `radar/telegram_conta.py`, `fontes/telegram_usuario.py` | Telegram com a conta do usuário (sessão própria, só leitura, só canais listados, checkpoint) |
| `radar/whatsapp_grupos.py` + `config/radar_whatsapp_grupos.yaml` | lista de autorização de grupos (trava do futuro leitor) |
| `radar/fontes/gatry.py`, `fontes/pelando.py` | Gatry (API JSON pública) e Pelando (HTML/JSON-LD sem navegador) |
| `radar/outbox.py` (reescrito) | fila com tipo e validade; alerta vencido só sai se revalidado na fonte |
| migração 2 do banco | `observacoes` com `invalida/preco_corrigido/correcao_motivo`; `outbox` com `tipo/expira_em/oferta_id/desfecho`; tabela `coletas_ciclo` (telemetria) |

## Por que CLI e não painel web

Baixa manutenção e nada novo rodando. `python -m radar status` mostra produtos, jobs, tarefas do Windows, fontes, fila,
execuções, alertas e melhores ofertas. O painel HTML existente (`scripts/painel.py`) continua cuidando dos processos de compra.

## Decisões de design

- **Preço validado nunca se mistura com preço comunitário.** Séries de coleta própria ficam em `observacoes`; publicações de comunidade ficam em `ofertas`.
- **Comunidade nunca vira CRITICA.** Isso exige `VALIDADO` (confirmação explícita por `radar validar`).
- **Sem histórico, sem afirmação.** Menos de 3 observações ou menos de 1 dia: a oferta não é chamada de "mínimo".
- **Cupom é interpretado, não presumido.** Valor só do código (`70OFF`) não entra em cálculo; restrição desconhecida bloqueia o desconto.
- **Falha é isolada.** Cada passo, cada fonte e cada oferta tem seu próprio `try`.
