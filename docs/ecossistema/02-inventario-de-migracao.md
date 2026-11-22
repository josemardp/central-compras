# 02. Inventário de migração

A auditoria (01) mostrou que Coral e central_automacoes **não contêm código de compras**. Por isso a migração
foi de **responsabilidade operacional**: agendamento, execução, histórico e resiliência passaram a ser do
`central-compras`. Nada foi removido de Coral, central_automacoes ou skills-pessoais.

## Itens migrados ou reassumidos

| Origem | Destino | Dependências | Antes | Depois | Método | Evidência |
|---|---|---|---|---|---|---|
| Tarefa do Windows "Central Compras - Rastrear Robos BF" (definição só na máquina) | `config/radar_jobs.yaml` + `python -m radar agendar` | PowerShell, ScheduledTasks | gatilhos e limite de 10 min configurados à mão, sem versionamento | definição versionada; limite 60 min; mesmo nome e mesmos horários 08/14/20h | `Register-ScheduledTask` gerado do YAML, com XML original salvo | `agendar --status`; backup `tarefa-...original.xml` |
| `scripts/rodar_rastreador_robos.ps1` (sequência dos 3 scripts, log em `*>>`) | mesmo arquivo, agora atalho para `python -m radar executar relatorios` | `radar/jobs.py` | sem trava, sem timeout por passo, log com mojibake | trava, timeout por passo, log UTF-8 com rotação, registro em banco | substituição do conteúdo | `tests/test_radar_nucleo.py::JobsTest` |
| `historico.jsonl` x3 (fora do Git, por máquina) | tabela `observacoes` em `radar.db` | `radar/historico.py` | só arquivos | arquivos intactos + cópia normalizada idempotente (96 observações importadas em 20/11) | `python -m radar migrar --importar-historico` | segunda importação: 0 novas |
| `estado.json` como "última coleta" | "última coleta **boa**" (derivada do histórico) | `radar/ciclo.py` | coleta degradada virava referência | degradada não sobrescreve estado | lógica no ciclo | `CicloTest` |
| `enviar_whatsapp()` (1 tentativa) | mesma função, 3 tentativas + trava de envio + fila (`outbox`) | `radar/outbox.py`, `radar/trava.py` | falha = relatório perdido | falha = reenvio no ciclo seguinte | refatoração | `CicloTest.test_falha_no_envio_enfileira...` |
| Parser da Leroy Merlin | `_parse_leroy_texto` corrigido | n/a | menor valor da página | valor rotulado "à vista", ignorando serviços | correção + teste de regressão | `test_parse_leroy_ignora_servico_de_instalacao` |
| Leitura errada R$ 60,65 (08:03) | `config/radar_correcoes.yaml` | `radar/correcoes.py` | contaminava menor histórico | corrigida em memória (R$ 122,45), arquivo original intacto | camada de correção versionada | `test_radar_correcoes.py` |

## Arquivos criados

`radar/` (pacote: `db`, `trava`, `jobs`, `ciclo`, `outbox`, `historico`, `correcoes`, `catalogo`, `cupons`, `ranking`, `alertas`,
`canais`, `varredura`, `status`, `agenda_windows`, `cli`, `fontes/*`), `config/radar_{jobs,catalogo,regras,fontes,correcoes}.yaml`,
`tests/test_radar_*.py`, `docs/ecossistema/*`.

## Arquivos alterados

`scripts/rastrear_{robos,ares,chuveiro}_bf.py` (usam `radar.ciclo`; flag nova `--sem-persistir`), `scripts/rodar_rastreador_robos.ps1`,
`requirements.txt`, `tests/test_rastrear_chuveiro_bf.py`, `STATUS.md`.

## Não migrado, por decisão

- `fetch_ml_*.py`, `scratch_*`, `fetch_tiktok.py` na raiz: rascunhos locais já ignorados pelo `.gitignore`. Não são rotina.
- `monitor-buser`: passagens de ônibus, outro domínio.
- Infraestrutura WhatsApp/Telegram do Coral e skills-pessoais: compartilhada, preservada.

## Reversão

- Tarefa: `python -m radar agendar --restaurar "Central Compras - Rastrear Robos BF"` (reimporta o XML original) e, se preferir, o `.ps1` antigo está no Git (`git show HEAD:scripts/rodar_rastreador_robos.ps1`).
- Banco: `python -m radar migrar --reverter 0` (faz backup antes). Os `historico.jsonl` nunca foram alterados.
