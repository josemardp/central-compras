# 04. Matriz de fontes

Sondagem real em 20/11/2026 (GET simples, sem login, sem contornar bloqueio). "Integrada" = adaptador em
`radar/fontes/` rodando na varredura. Nada abaixo é monitoramento contínuo se não estiver marcado como integrada.

## Lojas e comparadores (rastreadores de preço, 3x ao dia)

| Fonte | Acesso | Auth | Frequência | Dado | Limitação | Teste |
|---|---|---|---|---|---|---|
| Amazon, KaBuM, Zoom, Compras Paraguai, Leroy, Dufrio, WebContinental, Frigelar, Mercado Livre | Playwright/Chrome headless | nenhuma | 08/14/20h | preço, frete (CEP), vendedor, parcelamento, cupons exibidos | Magalu retorna 403; Casas Bahia pede Turnstile; Shopee anti-robô; TikTok Shop só no app; ML às vezes "sem h1" | dry-run 20/11 de robôs, ares e chuveiro sem erro |

## Inteligência promocional

| Fonte | Mecanismo | Auth | Frequência | Dados | Limitações | Resultado |
|---|---|---|---|---|---|---|
| **Promobit** | HTML público, JSON `__NEXT_DATA__` (`/promocoes/recentes/`, `?page=N`, `/promocoes/loja/<slug>/`) | nenhuma | 10 min | oferta, preço, cupom da oferta, loja, data, curtidas, cupons de loja com verificação | busca (`/buscar/`) é client-side e não serve; comentários não vêm na lista; 12 ofertas por página | **Integrada.** 127 itens por ciclo (inclui cupons KaBuM 15%, R$ 300, R$ 400) |
| **HardMOB** (Promoções) | HTML do fórum (`/forums/407-Promocoes`) | nenhuma | 10 min | título "Loja - Produto - R$", id do tópico | RSS (`external.php`) retorna vazio; sem comentários nem data na lista | **Integrada.** 32 tópicos por ciclo |
| **Méliuz** | texto público de `/desconto/cupom-desconto-<loja>` | nenhuma | 90 min | código, título, regras, "atualizado em" | só cupons de loja, sem produto; códigos-isca ("ATIVENOLINK") filtrados | **Integrada.** 148 cupons em 6 lojas |
| **Gatry** | **API JSON pública** `https://gatry.com/v1/promotions?kind=promotion\|coupon&limit=10&offset=N&sort=approved` (a mesma que o site chama; `robots.txt`: `Allow: /v1/`) | nenhuma | 10 min, 4 requisições | título, preço e preço antigo (centavos), **código do cupom, texto do desconto, validade, frete grátis, "exige cupom no carrinho", "só no app"**, status, último comentário | 10 itens por página; comentários completos bloqueados (HTTP); `robots.txt` também tem `Disallow: /*?` (conflito resolvido pela regra de maior especificidade: `/v1/` vence; se o site mudar de ideia, desligue em `radar_fontes.yaml`); sitemaps de promoções são de 2021 (inúteis) | **Integrada (20/11-21/11).** 40 itens por ciclo (30 promoções + 10 cupons de loja); `NO LINK` filtrado como não-código; revalidação por `/v1/promotions/{id}` testada ao vivo (ativa, e id inexistente) |
| **Pelando** | HTML **sem navegador** `https://www.pelando.com.br/recentes`: JSON-LD (`hasPart`, 20 URLs) + cards (`data-deal-id`, `data-inactive`, `data-share-title`, loja, preço, idade) | nenhuma | 15 min | título, URL, loja, preço, idade, "inativa" | **O Chrome automatizado recebe "Sorry, you have been blocked" (WAF): NÃO contornado.** Sem RSS (404), sem sitemap (404), a API do front (`api-web`) não é documentada. Fragilidade média (preço e loja saem do texto do card). Sem revalidação (alertas vencidos do Pelando são descartados) | **Integrada (21/11).** 20 de 20 itens com URL, preço, loja e hora; post "Cupom X" não vira preço de produto |
| Buscapé / Zoom | HTML (Zoom tem `__NEXT_DATA__`) | nenhuma | n/a | preço por produto | já coberto pelos rastreadores (Zoom) | Zoom usado nos rastreadores; Buscapé redundante |
| Keepa | site/API | **API paga com chave** | n/a | histórico Amazon | exige chave | **Não integrada.** Sem chave configurada |

## Comunidades

| Fonte | Mecanismo | Resultado |
|---|---|---|
| Telegram, canais com página pública `t.me/s/<usuario>` | HTML público, sem conta | **Adaptador integrado** (`telegram_publico`) com proteção de identidade. Nenhum canal habilitado ainda: `t.me/s/promobit` serve o canal de terceiros "OFERTAS PC GAMER" (`ofertasdecomputador`), **não é o Promobit**; `pelando`, `hardmob`, `promobit_oficial` e `canalpelando` não têm página pública de mensagens |
| Telegram, grupos/canais dos quais você é membro | **sessão de usuário própria do radar** (Telethon 1.46 instalado só no Python do radar; `api_id`/`api_hash` de my.telegram.org; login por código) | **Implementado e testado com leitor falso; NÃO autenticado.** Verificado: o Coral usa só 2 bots (tokens em arquivos), não há `.session`, Telethon nem `api_id` em nenhum lugar; portanto a sessão é nova e separada, e o bot/sessões do Coral não são tocados. Lê só canais/grupos que você listar, por id, nunca conversa privada, nunca envia, nunca entra, nunca marca como lida (teste varre o código atrás dessas chamadas). Primeira leitura só grava o checkpoint (não despeja histórico). Falta **você** fazer o login: ver 09 |
| WhatsApp, grupos de promoção | WhatsApp Web via CDP 9230 (a mesma aba que envia os relatórios) | **Lista de autorização criada e testada; leitor NÃO implementado.** Nenhum grupo autorizado ⇒ o radar não lê nenhum. Regras testadas: só nome exato listado, número de telefone e termos da lista `nunca` (família, igreja, 5ª Cia, PMESP, Esdra...) sempre recusados. O leitor exigiria abrir a conversa na aba compartilhada (marca como lida e disputa foco com os envios); não escrevi código de leitura sem poder testá-lo com um grupo que você autorize. Saída (relatórios e alertas): funcionando |

## Redes sociais

| Rede | Sondagem | Resultado |
|---|---|---|
| X | `syndication.twitter.com/srv/timeline-profile/...` (timeline incorporada): **HTTP 429** logo na 1ª chamada (promobit e pelando); `publish.twitter.com/oembed`: 200, mas só serve para uma URL de tweet que você já tem (não descobre nada); Nitter público: página de 12 KB sem tweets; busca do site: exige login | **Sem via gratuita e sustentável.** A API oficial é paga (não contratada). Não contornado |
| Instagram | `api/v1/users/web_profile_info`: **429**; página/embed: bloqueio anti-bot | **Sem via pública.** Alternativa oficial: Graph API "Business Discovery" (lê mídia pública de contas comerciais), mas exige conta Instagram comercial **sua**, app no Facebook e token. Não usar a conta institucional da 5ª Cia. Não configurado |
| Facebook | `facebook.com/promobit` e `mbasic`: **HTTP 400** sem sessão; grupos exigem login pessoal | **Inviável** (conteúdo público de Páginas exige app com revisão da Meta). Não contornado |

**Recomendação (baixo custo e baixa manutenção):** não montar coletores de rede social agora. Os perfis de ofertas relevantes
republicam no Promobit, Pelando, Gatry e Telegram, que já são cobertos. Para uma oferta vista numa rede social, cole o texto em
`python -m radar cupom "texto"` (interpreta cupom e restrições) ou me envie o link/print para análise pontual (consulta, não monitoramento).
Quando decidir pagar a API do X, o adaptador entra como mais um módulo em `radar/fontes/`.

## Ausência de ofertas x falha do coletor

`python -m radar efetividade` classifica cada fonte pelos ciclos medidos: **FALHA DO COLETOR** (todos com erro), **instável**,
**NÃO CONFIGURADA** (nenhum canal habilitado), **sem publicações** (respondeu vazia) ou **coletando, mas nada era dos seus 12 produtos**.
Estados gravados por ciclo: `ok`, `vazia`, `erro`, `sem_configuracao`. Caso real que motivou a regra: com a internet derrubada
(proxy inexistente) o Méliuz devolvia lista vazia e seria lido como "sem cupons"; agora vira erro.

## Saúde das fontes

`python -m radar status` mostra, por fonte, último sucesso, itens da última rodada e falhas seguidas (`fontes_saude`).
