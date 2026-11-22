# 09. Manual operacional

Tudo a partir da pasta do repositório (`C:\projetos\central-compras`). Prefixo `python -m radar`.

## Ver como está

| Quero saber | Comando |
|---|---|
| Visão geral (jobs, tarefas, fontes, fila, alertas, melhores ofertas) | `python -m radar status` |
| Tarefas do Windows versus o YAML | `python -m radar agendar` |
| Mensagens que não saíram e aguardam reenvio | `python -m radar fila` |
| Alertas (enviados, em sombra, com falha) | `python -m radar alertas` |
| Ofertas casadas com o catálogo (e cupons de loja com `--todas`) | `python -m radar ofertas` |
| Menor/maior em 7/30/90 dias | `python -m radar estatisticas [produto]` |
| Produtos monitorados | `python -m radar produtos` |
| Como o motor lê um texto de cupom | `python -m radar cupom "texto..."` |
| Logs | `~/.central-compras/dados-privados/radar/logs/` |

## Iniciar, parar, reiniciar

- **Iniciar/atualizar agendamentos:** `python -m radar agendar --aplicar` (idempotente; guarda o XML anterior).
- **Rodar agora, sem esperar o horário:** `python -m radar executar relatorios` (envia os 3 relatórios de verdade) ou `python -m radar varrer --sem-enviar -v` (só observa).
- **Teste sem enviar e sem gravar:** `python scripts/rastrear_robos_bf.py --sem-persistir` (idem `ares`, `chuveiro`).
- **Parar tudo de compras:** `Disable-ScheduledTask -TaskName "Central Compras - Rastrear Robos BF"` e `... "Central Compras - Radar Varredura"`.
- **Parar só os alertas urgentes:** `alertas.enviar: false` em `config/radar_regras.yaml`.
- **Relatório perdido (notebook suspenso):** a varredura recupera sozinha; para conferir, `python -m radar recuperar --simular`.
- **Reiniciar:** não há serviço residente; cada disparo é um processo curto. Travas órfãs se limpam sozinhas.
- **Reverter o cutover:** `python -m radar agendar --restaurar "Central Compras - Rastrear Robos BF"`.

## Cadastrar produto novo

Acrescente um bloco em `config/radar_catalogo.yaml` (`todos`, `nenhum`, `skus`, `tensao`, `btu`, `grupo`). Para ele entrar no **relatório** de preços
é preciso também incluí-lo no script do grupo (`scripts/rastrear_*_bf.py`); para ele ser reconhecido nas **ofertas de comunidade**, só o YAML basta.
Teste: `python -m radar cupom` não serve para isso; use `tests/test_radar_cupons_catalogo.py` como modelo e rode `python -m unittest tests.test_radar_cupons_catalogo`.

## Adicionar fonte

- Fonte pública nova: um módulo em `radar/fontes/` com `coletar(cfg) -> list[Oferta]` (levante `FonteErro` se falhar), registre em `radar/fontes/__init__.py` e habilite em `config/radar_fontes.yaml`. Adicione teste com HTML de fixture.
- Canal de Telegram com página pública: em `radar_fontes.yaml`, `telegram_publico.canais`, `{usuario, titulo_contem}`. **Confirme a identidade** abrindo `https://t.me/s/<usuario>`: o título tem que ser o do canal que você quer.

## Sessão expirada / canal fora do ar

| Sintoma | O que fazer |
|---|---|
| `[ZAP] ok=False | Aba web.whatsapp.com nao encontrada na porta 9230` | `node D:\projetos\skills-pessoais\zap-vivo.mjs josemardp`; se pedir QR: `node zap-vivo.mjs josemardp --login` (o celular lê). Mensagens ficam na fila e saem sozinhas depois |
| Relatório veio com "⚠️ Coleta parcial" | rede lenta; nada a fazer. O estado anterior foi preservado |
| Fonte com `falhas seguidas` crescendo em `status` | site mudou de layout ou bloqueou: abra a URL, ajuste o adaptador |
| Job falhou 2 vezes seguidas | você recebe aviso no WhatsApp; veja o log do dia |
| Telegram de canais dos quais você é membro | exige **sua** autenticação: ver a seção "Telegram com a sua conta" acima (o adaptador já existe) |

## Comandos da fase 3

| Quero | Comando |
|---|---|
| Medir o reconhecimento de produtos (precisão, recuperação, falsos positivos) | `python -m radar avaliar` |
| Rodar a cadeia de alerta com 16 cenários sintéticos (nada enviado) | `python -m radar homologar` |
| Reencenar ofertas **reais** com o seu histórico real | `python -m radar homologar --reais` |
| Enviar **1** mensagem de teste (marcada como TESTE) ao seu WhatsApp | `python -m radar homologar --enviar-teste-whatsapp --confirmo` |
| Ver se algum cupom de loja pode baixar seus produtos (estimativa) | `python -m radar cruzar` (`--todos` lista tudo) |
| Ver splits equivalentes mais baratos (só informativo) | `python -m radar equivalentes` |
| Qualidade e estabilidade dos coletores | `python -m radar qualidade-fontes` |
| O que é do radar e o que é de outra sessão no Git (só leitura) | `python -m radar git-escopo` |
| Backup do código do radar **fora do Git** (enquanto não houver commit) | `python -m radar git-escopo --backup` |
| Estado do Telegram (sem segredos) | `python -m radar telegram-status` |

Regra de urgência vigente (alterada na fase 4): reconhecido, sem aviso de voltagem/modelo, `PROVAVEL` ou `VALIDADO`, até 6 h, **pelo menos 3% abaixo do melhor preço atual já monitorado**, não duplicado em 24 h. Quem passa vira **candidato** com pontuação 0 a 100 e o despachante escolhe por prioridade e orçamento (`prioridade` em `config/radar_regras.yaml`), não mais por ordem de chegada. `CRITICA` pode passar do orçamento comum, mas tem orçamento, limite por ciclo e intervalo próprios. Oferta sem hora de postagem (HardMOB) nunca é "relâmpago". Ajuste em `config/radar_regras.yaml` (`classificacao.alta.melhora_vs_atual_pct`, `prioridade.*`).

## Comandos da fase 4

| Quero | Comando |
|---|---|
| Ver candidatos, pontuação, motivo e orçamento de hoje | `python -m radar prioridade` (`--horas`, `--limite`) |
| Ver janelas em que uma fonte ficou sem ser lida por mais que a lista alcança | `python -m radar lacunas --horas 48` |
| Conferir que os arquivos de outra sessão estão intactos | `python -m radar git-escopo --verificar` |
| Lista exata do que entraria no commit do radar (nada é commitado) | `python -m radar git-escopo --manifesto` |
| Backup completo fora do Git (código do radar + cópias de outra sessão + foto SHA-256) | `python -m radar git-escopo --backup-completo` |
| Reconhecimento por conjunto (treino, regressão, independente) | `python -m radar avaliar` |
| Cenários (agora 22, com priorização) | `python -m radar homologar` |

## Comandos da fase 6

| Quero | Comando |
|---|---|
| Inspecionar UMA oferta registrada: fonte, loja e os 3 níveis de preço (anunciado, confirmado, entregue) | `python -m radar conferir <id da oferta>` |
| Ver o modo (SOMBRA, PILOTO ou COMPLETO), os limites e os envios do piloto | `python -m radar piloto` |
| Teste ÚNICO de entrega ao seu WhatsApp (prévia sem enviar) | `python -m radar teste-entrega` |
| Enviar esse teste (1 mensagem rotulada TESTE ao seu chat; mede a latência) | `python -m radar teste-entrega --confirmo` |
| Ensaiar o kill switch e a limpeza da fila em cópias temporárias | `python -m radar ativacao --ensaio-kill-switch` |
| Ler só o Promobit (usado pela tarefa da Black Friday) | `python -m radar varrer --so promobit` |
| Ver o script da tarefa da Black Friday sem criar nada | `python -m radar agendar --mostrar --job varredura_promobit_bf` |

Piloto: [17-piloto-controlado.md](17-piloto-controlado.md). Plano de ativação: [16-plano-de-ativacao.md](16-plano-de-ativacao.md).

## Comandos da fase 5

| Quero | Comando |
|---|---|
| Verificação PRÉVIA da ativação (só leitura; veredito APTO ou NÃO APTO) | `python -m radar ativacao` |
| **Desligar os alertas agora** (kill switch; limpa a fila de alertas) | `python -m radar ativacao --desligar` |
| Simular a política de prioridade com ofertas documentadas | `python -m radar simular-prioridade` (`--sintetico`, `--resumo`) |
| Latência da publicação até o WhatsApp (MEDIDO x ESTIMADO) e chance de ler promoção curta | `python -m radar latencia --horas 24` |
| Ofertas que o limite de alertas reteve (estado `retida_orcamento`) | `python -m radar prioridade` |
| Cupons por estágio (descoberto, potencialmente elegível, validado, expirado) | `python -m radar cruzar` |
| Listar só os seus CANAIS do Telegram (sem ler mensagens) | `python -m radar telegram-listar` (`--grupos` inclui grupos) |

Plano completo de ativação, monitoramento, desativação e rollback: [16-plano-de-ativacao.md](16-plano-de-ativacao.md).

## Homologar e ligar os alertas urgentes (passo seu, explícito)

1. Deixe a varredura rodar alguns dias (ela já registra em sombra). Veja: `python -m radar alertas --limite 50`, `python -m radar ofertas`, `python -m radar efetividade --horas 72`.
2. Pergunte-se: o que o radar chamou de CRÍTICA/ALTA realmente mereceria te interromper? O `perfil_comprador` (primeira compra, app, Pix) em `config/radar_regras.yaml` bate com o que você usa?
3. Para ligar: em `config/radar_regras.yaml`, `alertas.enviar: true` **e** `alertas.homologado_em: "AAAA-MM-DD HH:MM"`. Só os dois juntos liberam o envio.
4. Para desligar: `enviar: false`. `python -m radar status` mostra o estado na 2ª linha.

## Telegram com a sua conta (passo seu: só você pode autenticar)

O que existe: o Coral usa 2 **bots**; não há sessão de usuário. O radar usa uma sessão **nova e separada**, que não toca token nem sessão do Coral.
O que eu não posso fazer por você: criar o app no Telegram e receber o código de login (SMS/app).

1. No navegador, entre em https://my.telegram.org com o seu número, abra **API development tools** e crie um app (nome qualquer, plataforma "Desktop"). Anote `api_id` (número) e `api_hash` (texto). **Não cole o `api_hash` no chat.**
2. Abra um PowerShell **seu** (não pelo chat), vá a `C:\projetos\central-compras` e rode: `python -m radar telegram-login`. Ele pede `api_id`, `api_hash` (não aparece na tela), telefone com +55 e o código que chegar no Telegram (e a senha de duas etapas, se tiver). A sessão e as credenciais ficam em `~\.central-compras\dados-privados\radar\telegram\` (fora do Git).
3. Rode `python -m radar telegram-listar`: lista **só canais e grupos** (nunca conversas privadas) com `id` e nome.
4. Copie para `config/radar_fontes.yaml`, em `telegram_usuario.canais`, **apenas** os que você quer monitorar (`{id: -100..., nome: "...", habilitado: true}`). Não presumo inscrições nem entro em grupo.
5. Na 1ª leitura o radar só grava o ponto de partida (não despeja histórico). Depois lê só mensagens novas, a cada 5 min. Em `python -m radar efetividade` a fonte passa de "NÃO CONFIGURADA" para ativa.
6. Para revogar: apague a pasta `radar\telegram\` e, no Telegram, em Configurações > Dispositivos, encerre a sessão do app criado.

## WhatsApp: grupos de promoção (lista de autorização)

O radar **não lê nenhum grupo** hoje. `config/radar_whatsapp_grupos.yaml` guarda a lista (vazia) e as regras que o futuro leitor obedecerá.
Para ver: `python -m radar whatsapp-grupos`; para testar um nome: `python -m radar whatsapp-grupos --verificar "Nome do grupo"`.
Se quiser avançar: escreva em `autorizados` o nome **exato** de cada grupo de promoção (no máximo 5) e me avise; o leitor só será escrito e testado com um grupo que você autorizar, numa janela sem relatório. Grupos de família, igreja, 5ª Cia, PMESP e contatos individuais são sempre recusados.

## Trocar a máquina oficial / sincronizar históricos

Hoje só a `LAPTOP-3NSQG27T` coleta, envia e alerta (`config/radar_maquina.yaml`). Outra máquina que receba o código fica **inativa** (mensagem explícita). Os históricos
**não** sincronizam por Git (têm CEP/endereço e ficam fora do repositório por regra). Para mudar de máquina, siga os passos comentados no próprio YAML:
desativar as tarefas na antiga, copiar `rastreador-*/historico.jsonl` e `radar/telegram/` por meio privado, trocar `maquina_oficial`, commit/push, `git pull` e
`python -m radar migrar --reconstruir` + `python -m radar agendar --aplicar` na nova. Os JSONL são a verdade portátil; o banco se reconstrói deles.

## Relatório de efetividade e auditoria do histórico

`python -m radar efetividade --horas 24` (publicações coletadas, casamentos com os 12 produtos, cupons extraídos/elegíveis/aplicados, motivos de descarte, fontes em falha ou sem configuração).
`python -m radar auditar` varre os históricos brutos atrás de leituras suspeitas (não altera nada). Para invalidar ou corrigir uma leitura, registre em `config/radar_correcoes.yaml`
(com motivo) e rode `python -m radar migrar --reconstruir`.

## Validar uma oferta de verdade

Abra o carrinho, confira preço, cupom, frete, voltagem e vendedor, e só então: `python -m radar validar <id> --por "carrinho Amazon 21/11"`.
(O `<id>` aparece em `python -m radar ofertas`.) Até lá o preço é estimativa.

## Restaurar backups

- Banco: copie `radar/backups/radar-...db` por cima de `radar/radar.db` com as tarefas desativadas.
- Banco do zero: apague `radar.db` e rode `python -m radar migrar --importar-historico` (reconstrói as observações a partir dos JSONL).
- Tarefa do Windows: `python -m radar agendar --restaurar "<nome>"`.

## Antes de commitar

`python scripts/central_compras.py checar-segredos --strict` e `python -m unittest discover -s tests` (leva ~7 min).
