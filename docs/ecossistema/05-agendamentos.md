# 05. Agendamentos

Definição única: `config/radar_jobs.yaml`. Aplicação no Windows: `python -m radar agendar --aplicar [--job X]`.
Estado real versus desejado: `python -m radar agendar` (ou `status`). Fuso: America/Sao_Paulo (o Windows desta máquina já usa Brasília).

| Tarefa do Windows | Job | Horários | Limite | Se a máquina estava dormindo | Responsável |
|---|---|---|---|---|---|
| `Central Compras - Rastrear Robos BF` (nome preservado) | `relatorios` (robos, ares, chuveiro) | 08:00, 14:00, 20:00 | 60 min (era 10) | inicia ao acordar | central-compras |
| `Central Compras - Radar Varredura` | `varredura` | a cada 10 min | 8 min | não recupera (a próxima passada cobre) | central-compras |

## Garantias implementadas

- **Identidade única do job** (`jobs.<id>` no YAML) e **trava de execução única** (`radar/trava.py`): uma segunda instância é ignorada e registrada como `ignorada`. `MultipleInstances=IgnoreNew` no Windows como segunda barreira.
- **Concorrência:** o envio ao WhatsApp tem trava própria (`whatsapp-envio`); relatório e alerta nunca digitam juntos.
- **Última e próxima execução:** `jobs_estado` e `execucoes` no banco; próximo disparo calculado do YAML.
- **Sucesso/falha:** por passo (`ok`, `falha`, `timeout`, `ignorada`); 2, 6 e 12 falhas seguidas do job enfileiram aviso no WhatsApp.
- **Recuperação após reinicialização:** `StartWhenAvailable` no relatório; travas órfãs (PID morto ou antigas) são tomadas.
- **Logs:** `~/.central-compras/dados-privados/radar/logs/<job>-AAAAMMDD.log`, UTF-8, rotação por tamanho (5 MB) e por idade (14 dias).

## Notebook suspenso, rede caída, processo morto (fase 2, comprovado)

| Situação | Evidência real | Comportamento |
|---|---|---|
| **Notebook suspenso no horário** | 21/11: suspenso 02:26 a 09:37 (eventos de energia 42/107/1); o Windows **não** recuperou o slot das 08:00 apesar de `StartWhenAvailable=true` (a tarefa continuou com "última execução 20/11 20:00") | A varredura (10 min) roda o passo `recuperar` antes de varrer: se o último horário previsto ficou sem execução e está dentro de `recuperar_ate_horas` (6 h), dispara a própria tarefa. **Recuperou de verdade em 21/11 09:54** (3 de 3 relatórios entregues). Registra a tentativa para não repetir a cada 10 min |
| **Conexão interrompida** | 20/11 14:34 (relatório perdido) e teste com proxy inexistente em 21/11 | Fonte para no 1º erro de rede (31 s em vez de 98 s), vira `erro` no relatório e o código de saída é 1; relatório usa "coleta parcial" e preserva a última coleta boa |
| **Processo morto no meio** (reinício, kill, queda de energia) | `taskkill /T /F` no meio de um job: registro ficou `rodando`, trava `.lock` órfã | Próximo início toma a trava órfã e marca a execução antiga como `interrompida`; o job seguinte completa |
| **Sessão do WhatsApp indisponível** | CDP em porta sem serviço: `ECONNREFUSED` | 3 tentativas, erro explícito, mensagem na fila; relatório vencido (24 h) é descartado; alerta urgente vencido (30 min) só sai se revalidado na fonte |
| **Reinício do Windows** | não forçado (afetaria o `zap-vivo` do seu WhatsApp) | Tarefa dispara no horário; travas e registros se limpam sozinhos (comprovado pelo teste do kill). Não há serviço residente do radar |

## Uma máquina oficial

`config/radar_maquina.yaml` define `maquina_oficial` (hoje `LAPTOP-3NSQG27T`). Em qualquer outra máquina os jobs, a varredura e o envio dos
relatórios **não fazem nada** (mensagem "esta máquina não é a oficial"). Execução manual excepcional: `CENTRAL_COMPRAS_FORCAR_MAQUINA=1`.
Procedimento de troca de máquina: comentado no próprio YAML e em 09.

## Tarefas de outros projetos que NÃO foram tocadas

`Coral - *` (controlador, vigia, sessão, SITREP, entregador...), `Zap vivo - WhatsApp das IAs`, `CentralEC Rodada *` (desativadas).
Nenhuma delas executa rotina de compras (verificado em 01). Não há agendamento concorrente de compras no Coral nem no central_automacoes.

## Disponibilidade (honestidade operacional)

Isto roda num notebook com Wi-Fi que oscila e que dorme. Os relatórios de 08/14/20h toleram isso (recuperação, retentativa, fila).
A varredura de 10 em 10 minutos só roda com o notebook acordado e conectado; não há garantia 24 h. Para cobertura contínua seria
preciso uma máquina sempre ligada (ver 10).
