# 12. Telegram com a sua conta: passo a passo (5 minutos, no seu PC)

**O que isto faz:** deixa o radar ler, só leitura, os **canais de oferta que você escolher**.
**O que isto NÃO faz:** não lê conversa privada (nem de pessoa, nem de bot), não envia mensagem, não entra em grupo, não marca como lida, não lê canal que você não colocou na lista, não toca no bot nem nas sessões do Coral.
**Por que só você pode fazer:** o login exige o código que o Telegram manda para o **seu** celular. Eu não peço, não vejo e não guardo esse código.

## Estado hoje (21/11/2026)

`python -m radar telegram-status`: credenciais **NÃO** gravadas, sessão **NÃO** autenticada, 0 canais autorizados, `telethon 1.46` instalado. Nada foi autenticado e nada do Telegram foi lido pela sua conta.

## Passos (todos no seu PowerShell, não no do Claude)

1. **Crie o app (uma vez).** No navegador, abra https://my.telegram.org, entre com o seu número, clique em **API development tools** e crie um app (nome livre, plataforma Desktop). Anote o `api_id` (número) e o `api_hash` (texto). Não cole o `api_hash` em chat, e-mail nem commit.
2. **Entre pelo radar:**
   ```
   cd C:\projetos\central-compras
   python -m radar telegram-login
   ```
   Digite o `api_id`. O `api_hash`, o código recebido no Telegram e a senha de duas etapas (se tiver) **não aparecem na tela**. Ao terminar, aparece "Autenticado como: <seu nome>".
3. **Veja só os seus canais** (conversas privadas nunca aparecem e nenhuma mensagem é lida):
   ```
   python -m radar telegram-listar
   ```
   Se algum canal de oferta for na verdade um grupo, use `python -m radar telegram-listar --grupos` (só mostra os nomes).
4. **Escolha só os canais de oferta que quer.** Copie as linhas deles para `config/radar_fontes.yaml`, em `telegram_usuario` > `canais:`. O que não estiver nessa lista **nunca é aberto**. Exemplo:
   ```
   canais:
     - {id: -1001234567890, nome: "Canal de Ofertas X", habilitado: true}
   ```
5. **Confira:** `python -m radar telegram-status` (não mostra segredos). Depois de um ciclo (5 min), `python -m radar efetividade` mostra a fonte lendo (sai de "NÃO CONFIGURADA"). Na 1ª leitura de cada canal o radar só grava o ponto de partida; depois lê apenas mensagens novas.

## Proteções (já no código, com teste)

- Id **positivo** na lista (é pessoa ou bot) é **recusado** antes de qualquer leitura, e o `telegram-status` avisa.
- Mesmo com id negativo, ao conectar o radar confere a entidade e **recusa** se for uma pessoa.
- Sessão própria do radar (`radar.session`), separada do Coral (que usa só bot). O radar não abre nenhum arquivo, token ou sessão do Coral.
- Uma leitura por vez (trava), no máximo a cada 5 min e 50 mensagens por canal.

## O que muda na sua conta do Telegram

Aparece um dispositivo novo em **Configurações > Dispositivos** (é o radar). Ele só lê os canais da lista. Você pode encerrá-lo quando quiser.

## Onde ficam os dados (fora do Git)

`C:\Users\<você>\.central-compras\dados-privados\radar\telegram\` (credenciais, sessão e checkpoints). Nunca versionado.

## Para parar ou revogar

1. Parar só de ler: apague as linhas de `canais:` (ou ponha `habilitado: false`).
2. Revogar tudo: apague a pasta acima. No Telegram, Configurações > Dispositivos > encerre a sessão do app e, se quiser, apague o app em my.telegram.org.

## Se algo der errado

| Mensagem | O que fazer |
|---|---|
| `telethon` não instalado | `python -m pip install --user telethon` (só neste Python; o Coral usa outro) |
| `FloodWait` / bloqueio temporário | esperar o tempo indicado; o radar lê no máximo a cada 5 min, 50 mensagens por canal |
| `ChannelPrivateError` | você não é membro daquele canal com essa conta; remova da lista |
| "id positivo e conversa privada; recusado" | você colou um id de pessoa/bot; remova da lista |
| pede o código de novo | a sessão expirou: repita o passo 2 |
