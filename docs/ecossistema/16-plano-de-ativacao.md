# 16. Plano de ativação controlada dos alertas reais (piloto primeiro)

**Regra de ouro:** nenhum alerta real sai até você editar três linhas em `config/radar_regras.yaml`. O radar nunca liga sozinho. A ativação é **em piloto**, com limites bem menores; só depois vem a política completa. Detalhes do piloto: [17-piloto-controlado.md](17-piloto-controlado.md).

Estado em 22/11/2026: **SOMBRA** (`enviar: false`, `homologado_em: null`, `piloto.ativo: false`).

## 1. Verificação prévia (automática, só leitura)

```
python -m radar ativacao
```

Confere configuração, gates de segurança, máquina oficial, tarefas agendadas, banco, as 5 fontes, lacunas de coleta, o caminho ao vivo exercitado em sombra, simulação da fila e da política, 22 cenários, aba do WhatsApp, limites do piloto, segredos e backup. Cada item sai **OK**, **FALHA**, **PENDENTE** (falta evidência) ou **MANUAL** (passo seu). Veredito **APTO PARA PILOTO** quando não há FALHA nem PENDENTE.

Sem exigir um número mínimo de ofertas: os produtos são raros. O item D1 mostra o que já foi comprovado e o risco residual (ver doc 17).

## 2. Conferência em sombra

```
python -m radar prioridade --horas 72
python -m radar conferir <id da oferta>     # fonte + loja + os 3 níveis de preço
```

Para cada candidato em sombra: o produto é exato? o preço bate com a loja? depende de cupom? Eu quereria receber isto?

## 3. Teste único de entrega ao SEU WhatsApp (passo seu, autorizado por você)

```
python -m radar teste-entrega               # só mostra a prévia, NADA é enviado
python -m radar teste-entrega --confirmo    # envia 1 mensagem rotulada TESTE ao seu próprio chat
```

Mede criação, início do envio e confirmação lida de volta na conversa, grava em `latencia.jsonl` (`python -m radar latencia` passa de ESTIMADO para MEDIDO). No máximo 1 por dia. Confira no celular que chegou **no chat certo**.

## 4. Confirmar o destinatário (feito em 21/11/2026 às 21:21)

**Já registrado**: você confirmou no celular que o teste de 21:12 chegou (mensagem "chegou no meu zap sim", 21:21, horário do registro da sessão) e o campo foi preenchido com esse horário. O restante desta seção fica como referência.

Só depois de ver o teste chegar no seu chat, em `config/radar_regras.yaml`, bloco `piloto`:

```
destinatario_confirmado_em: "AAAA-MM-DD HH:MM"
```

Sem isso o piloto não envia nada, mesmo ligado.

## 5. Teste do kill switch e da fila (já feito, repita quando quiser)

```
python -m radar ativacao --ensaio-kill-switch
```

Ensaia em cópias temporárias: alertas ligados, alerta e relatório na fila, desligamento, fila de alertas descartada, relatório preservado, próxima varredura sem alerta. Não toca na configuração real.

## 6. Ativação do PILOTO (passo seu, explícito)

No arquivo **local** `C:\Users\<você>\.central-compras\dados-privados\radar\operacao.yaml` (fora do Git; ver a seção 9-B). O `config/radar_regras.yaml` versionado **não** se edita para ligar:

```
alertas:
  enviar: true
  homologado_em: "AAAA-MM-DD HH:MM"
piloto:
  ativo: true
```

Ative de manhã (alertas só valem entre 07:00 e 23:00) e fique por perto na primeira hora.

## 7. Monitoramento dos primeiros ciclos

| Olhar | Comando | Esperado |
|---|---|---|
| Modo, limites, o que ficou fora, envios | `python -m radar piloto` | modo PILOTO; envios ok; nada de falha repetida |
| Decisões e motivos | `python -m radar prioridade` | `enviado` só para o que você aprovaria |
| O que chegou no celular | WhatsApp | 1 mensagem por oferta, sem repetição, preço e link certos, confiança exibida |
| Saúde | `python -m radar status` | varredura ok, 0 falhas seguidas |
| Lacunas | `python -m radar lacunas --horas 2` | nenhuma |
| Latência dos envios | `python -m radar latencia` | MEDIDO |

## 8. Desativação imediata

**Quando desligar** (qualquer um): 2 falsos positivos em 24 h; 1 falso positivo que se repete; rajada ou mensagem duplicada; alerta tratando BLACK150, PHI200 ou qualquer cupom como preço garantido.

```
python -m radar ativacao --desligar
```

Grava `enviar: false` e `homologado_em: null` no `operacao.yaml` local (e também no versionado, se alguém o tiver deixado ligado), preservando o resto dos arquivos, e **descarta na hora os alertas da fila**. Se esquecer, a próxima varredura também descarta. Relatórios 08/14/20h não são tocados.

## 9. Rollback (do mais leve ao mais pesado)

1. Desligar os alertas (seção 8).
2. Pausar só a varredura: `Disable-ScheduledTask -TaskName "Central Compras - Radar Varredura"` (relatórios seguem, outra tarefa). Voltar: `Enable-ScheduledTask`.
3. Voltar a configuração: restaurar `config/radar_regras.yaml` do zip `codigo-radar-*.zip` em `C:\Users\<você>\.central-compras\dados-privados\radar\backups\`.
4. Voltar o banco: `python -m radar migrar --reverter 3` (remove a tabela de candidatos e as 3 colunas de hora; faz backup antes) ou restaurar o `radar-*-pre-migracao.db`.
5. Voltar o código: antes do commit, só os zips têm o código; depois, `git revert` do commit do radar (só com a sua ordem).

## 9-B. Recuperação a partir do GitHub, estado operacional local e `migrar --reverter`

**Onde mora a ativação (desde 22/11/2026):** no arquivo local `C:\Users\<você>\.central-compras\dados-privados\radar\operacao.yaml`, fora do Git. Só ele liga o envio, com três chaves: `alertas.enviar`, `alertas.homologado_em` e `piloto.ativo`. O `config/radar_regras.yaml` versionado fica sempre desligado (SOMBRA). Por isso `git pull`, `git restore`, `git reset` e o trabalho de outra sessão não desligam o piloto em silêncio, e um `git add -A` não publica a ativação. Sem o arquivo local, o radar roda em SOMBRA. Arquivo ilegível também cai em SOMBRA, e `python -m radar status` mostra a origem do estado e qualquer aviso. As seções 6 e 8 acima ainda citam `config/radar_regras.yaml` como lugar de ligar e desligar: o lugar que vale agora é o `operacao.yaml` (o `--desligar` já grava lá).

**Instalação nova (clone sem pasta de dados):**
- O que vem do GitHub: alertas desligados, `piloto.ativo: false`, a trava de máquina (`LAPTOP-3NSQG27T`) e `piloto.destinatario_confirmado_em`, que **já está no GitHub** (preenchido em 21/11/2026 21:21).
- O que não vem: banco, históricos, backups, sessão do Telegram, `ativacao.jsonl`, a marca do teste único de entrega, `operacao.yaml` e as tarefas do Windows.
- Passos: `python -m radar migrar` (cria o banco) e `python -m radar agendar --aplicar` (cria as tarefas). O radar fica em SOMBRA. Em outra máquina, a trava de máquina mantém tudo inativo, então só a máquina oficial coleta e envia. Para operar de verdade: teste único de entrega (seção 3) e ativação (seção 6, escrevendo no `operacao.yaml`). Confirmar o destinatário de novo só vale se o chat de destino mudou.

**Máquina com configuração local preexistente (este notebook):**
- O `operacao.yaml` sobrevive a `git pull`, `git restore`, `git reset --hard` e `git stash`, porque está fora do repositório. Só se perde se a pasta `dados-privados` for apagada ou o perfil do Windows for recriado, e nesse caso o radar volta a SOMBRA (lado seguro).
- Até 22/11/2026 a ativação era uma alteração não commitada do `config/radar_regras.yaml`. Foi migrada para o `operacao.yaml` com os mesmos valores (09:03, piloto). O registro `ativacao.jsonl` e os backups foram preservados.
- Um `ativacao --desligar` grava o desligamento no `operacao.yaml` e, se alguém tiver deixado o arquivo versionado ligado, desliga ele também.

**Voltar o banco (`migrar --reverter`):** o número é a **versão alvo**, não a migração a desfazer. `python -m radar migrar --reverter 3` volta o banco à **versão 3**: desfaz só a **migração 4** (tabela `candidatos_alerta` e as 3 colunas de hora em `ofertas`) e **mantém a 3** (`validacoes_manuais`). Para desfazer a 3 seria `--reverter 2`, que apaga as validações manuais. O comando faz backup antes. **Atenção:** o código atual, ao abrir o banco, **reaplica a migração 4 sozinho** (com backup) na próxima execução, seja a varredura agendada ou qualquer comando `radar`. Para a reversão valer, pause as tarefas do radar antes (seção 9, item 2) e volte o código junto (`git revert` do commit do radar, só com a sua ordem). Sem isso, ela é refeita em minutos.

## 10. O que NÃO muda na ativação

Relatórios 08/14/20h, histórico e correções, deduplicação, TTL da fila, recuperação de falhas, trava de máquina oficial, proteção de credenciais, regras estritas de cupom (BLACK150 e PHI200 seguem NAO_CONFIRMADOS até você validar no carrinho).

## Efetividade é com você

Os portões provam que o radar é seguro e consistente, não que as ofertas dele valem o seu tempo. Só você sabe qual alerta mereceria interromper o seu dia. Se na primeira semana a maioria dos alertas não te fizer agir, o problema é a política (pontuação, orçamento, lista de produtos), não o código.
