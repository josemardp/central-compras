# 01. Auditoria do ecossistema (20/11/2026)

Escopo: onde estavam, antes desta missão, todas as automações de compras. Diferenço o que está **documentado**
do que foi **comprovado por execução real** nesta máquina (`LAPTOP-3NSQG27T`).

## 1. Repositórios inspecionados

| Local | Repositório (remote) | Tem lógica de compras? | Evidência |
|---|---|---|---|
| `C:\projetos\central-compras` (junção para `D:\projetos\central-compras`) | `josemardp/central-compras` | **Sim, toda** | código, testes, tarefa agendada |
| `C:\projetos\coral` (junção para `D:\projetos\coral`) | `josemardp/coral` | **Não** | busca por scripts/serviços: só cita o nome do projeto (`memoria/projetos.md`) e tem ruído de transcrições de vídeo |
| `C:\Users\pc\Coral` (runtime do Coral) | `josemardp/coral-agente` | **Não** | só infraestrutura: bot Telegram, executor WhatsApp, coletores do SITREP |
| `C:\projetos\central_automacoes` | `esdraaline/central_automacoes` | **Não** | só lista o `central-compras` na sincronia de repositórios e ignora `scratch_*`/`fetch_*` |
| `C:\projetos\skills-pessoais` | `josemardp/skills-pessoais` | **Infra compartilhada** | `zap-vivo.mjs` (navegador do WhatsApp), `nav-missao` |
| `D:\projetos\monitor-buser` | n/d | Não (outro domínio) | monitor de passagens de ônibus, GitHub Actions 8/14/20h |
| `D:\projetos\central-ec`, `financeiroje` | n/d | Não | `central-ec` tem tarefas próprias desativadas; `financeiroje` só lê nomes de lojas em notificações |

Conclusão: **não havia scripts de compras espalhados** a migrar de Coral ou central_automacoes. O sistema real
já morava no `central-compras`; faltavam centralizar o agendamento, o histórico em banco, a resiliência e as fontes.

## 2. Quem produz cada relatório (comprovado)

| Relatório | Código | Coleta | Histórico (fora do Git) |
|---|---|---|---|
| RASTREIO ROBOS | `scripts/rastrear_robos_bf.py` | Amazon, KaBuM, Zoom, Promobit, Compras Paraguai (Playwright/Chrome headless) | `~/.central-compras/dados-privados/rastreador-robos/` |
| RASTREIO ARES | `scripts/rastrear_ares_bf.py` | Amazon, Dufrio, WebContinental, Frigelar, KaBuM, Mercado Livre, Promobit (2 CEPs) | `.../rastreador-ares/` |
| RASTREIO CHUVEIRO | `scripts/rastrear_chuveiro_bf.py` | Amazon, Leroy Merlin, Zoom, Promobit | `.../rastreador-chuveiro/` |

- Preço = menor total entregue entre as lojas (preço + frete do CEP configurado); comparação com a rodada anterior.
- Envio: WhatsApp Web pela aba do `zap-vivo.mjs` (CDP `127.0.0.1:9230`, perfil `perfil-zap-josemardp`), no chat do próprio Josemar.
- Agendamento: **uma** tarefa do Windows, `Central Compras - Rastrear Robos BF`, 08:00, 14:00 e 20:00 (comprovado: `Get-ScheduledTask` e log `execucao.log`).
- Não existe duplicata: nenhuma tarefa do Coral nem do central_automacoes dispara rotina de compras (13 tarefas `Coral - *` e `Zap vivo` inspecionadas).

## 3. Defeitos encontrados (todos reproduzidos em evidência real)

1. **Limite de execução de 10 min** na tarefa. A rodada de 20/11 14:34 durou 11,5 min e foi encerrada (resultado `267014`).
2. **Relatório das 14h não chegou**: os três envios retornaram `Texto digitado divergiu do esperado`.
3. **Coleta degradada sobrescreveu o estado.** Rede lenta (9 `Page.goto: Timeout`) gravou "indisponível" em `estado.json`, que é a referência da próxima rodada: falsos "alterou desde..." às 20h.
4. **Leitura errada da Leroy Merlin**: o parser pegava o menor valor da página, inclusive o serviço "Instalação por R$ 89,90". O histórico do chuveiro registrou R$ 60,65 às 08:03 (inferido do mesmo defeito; página daquele horário não foi preservada), o que falsearia o "menor histórico".
5. Sem trava de execução dupla, sem fila de reenvio, sem registro estruturado de execuções, log com caracteres corrompidos.
6. Causa ambiental: o Wi-Fi do notebook cai (`Test-Connection 1.1.1.1` falhou às 18:25 e voltou às 18:29). Não é bug de código; o sistema precisa tolerar.

## 4. Infraestrutura compartilhada (preservada, não duplicada)

| Peça | Dono | Uso pelo radar |
|---|---|---|
| `zap-vivo.mjs` + Chrome 9230 | skills-pessoais | envio de relatórios e alertas (um envio por vez, com trava) |
| Bot Telegram `@coral_jdp_bot` | Coral | **não reutilizável** para ler canais: é bot de conversa com o Josemar |
| Sessão de usuário Telegram (Telethon/Pyrogram) | inexistente | ver 04 e 10 |
| `coletores.py` (lista de conversas do WhatsApp) | Coral | não abre conversa; não serve para ler grupos |

## 5. Documentado versus comprovado

- Comprovado por execução: coleta dos três rastreadores (dry-run de 20/11), envio ao WhatsApp (relatórios de 08h), detecção de falha, leitura das fontes públicas (ver 04).
- Apenas documentado, não comprovado nesta sessão: execução em outras máquinas (`LAPTOP-173MUN6G`); o `STATUS.md` fala em "máquina onde está agendada a tarefa", e só esta foi verificada.
