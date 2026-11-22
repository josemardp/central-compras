# 11. Matriz de status (21/11/2026)

Definições, para ninguém declarar o que não foi provado:

- **Implementado:** o código existe no repositório.
- **Testado:** teste automatizado passa (fixture/simulação, sem depender da internet nem do WhatsApp).
- **Homologado:** exercitado de verdade nesta máquina, com evidência real registrada (log, banco, mensagem entregue, resposta ao vivo da fonte).
- **Pendente:** falta código, falta decisão/ação sua ou falta evidência.

Legenda: ✅ sim | ➖ parcial (ver nota) | ❌ não.

## Núcleo e operação

| Funcionalidade | Impl. | Testado | Homolog. | Evidência real / nota |
|---|:-:|:-:|:-:|---|
| Relatórios ROBOS/ARES/CHUVEIRO 08h/14h/20h pelo `radar` | ✅ | ✅ | ✅ | 20/11 20:00: 3 de 3 entregues, tarefa `LastTaskResult 0`, 4 min 14 s. 21/11 09:54: 3 de 3 (recuperação) |
| Comparar com a última coleta **boa**; coleta degradada não vira referência | ✅ | ✅ | ✅ | O detector, aplicado ao histórico real, reprovou exatamente as rodadas de 19/11 20:00 e 20/11 14:34 e aprovou as demais |
| Fila do WhatsApp com validade (relatório 24 h; alerta 30 min + revalidação) | ✅ | ✅ | ➖ | Falha de envio real simulada (`ECONNREFUSED`, 3 tentativas, mensagem na fila). **Nenhum reenvio real** ocorreu (não houve falha real depois) |
| Recuperação de relatório perdido (notebook suspenso) | ✅ | ✅ | ✅ | 21/11: suspensão 02:26-09:37 perdeu o slot das 08:00; recuperado às 09:54 |
| Job morto no meio / trava órfã | ✅ | ✅ | ✅ | `taskkill /T /F` real: registro virou `interrompida`, trava órfã tomada, job seguinte completo |
| Conexão interrompida | ✅ | ✅ | ✅ | Proxy inexistente: 5 fontes em `erro`, saída 1, 31 s (antes 98 s). Bug do Méliuz achado e corrigido |
| Sessão do WhatsApp indisponível | ✅ | ✅ | ✅ | Porta CDP sem serviço: erro explícito, nada enviado, fila |
| Reinício do Windows | ✅ | ➖ | ❌ | Não forçado (derrubaria o `zap-vivo`). Coberto indiretamente pelo teste do kill e por travas órfãs |
| Banco SQLite, migrações 1 e 2, rollback, backup automático | ✅ | ✅ | ✅ | Migração 2 aplicada no banco real com backup `radar-...-pre-migracao.db` |
| Trava de máquina oficial | ✅ | ✅ | ➖ | Ativa e correta nesta máquina (`status`). **Não** validada na outra máquina (não toquei nela) |

## Integridade histórica

| Funcionalidade | Impl. | Testado | Homolog. | Evidência / nota |
|---|:-:|:-:|:-:|---|
| Valor bruto preservado + invalidação/correção auditável | ✅ | ✅ | ✅ | Banco real: `60.65 -> 122.45`, `invalida=0`, motivo gravado; JSONL intacto |
| Estatísticas ignoram inválidos, degradados e não-validados | ✅ | ✅ | ✅ | Menor do chuveiro 111,89 (e não 60,65) |
| Auditoria do histórico bruto (`radar auditar`) | ✅ | ✅ | ✅ | 22 coletas: 1 suspeita real, já corrigida |
| Causa exata do R$ 60,65 | — | — | ❌ | **Inferida** (o leitor pegava "Instalação R$ 89,90"/menor valor); a página das 08:03 não foi preservada. `[VERIFICAR]` |

## Inteligência de ofertas

| Funcionalidade | Impl. | Testado | Homolog. | Evidência / nota |
|---|:-:|:-:|:-:|---|
| Catálogo canônico (12 produtos) e identificação | ✅ | ✅ | ➖ | Rejeições corretas vistas ao vivo (Elgin **9.000** BTU, micro-ondas Philco). **Nenhum casamento positivo real ainda** (nenhuma oferta dos seus produtos apareceu) |
| Motor de cupons (extração, restrições, validade, preço final) | ✅ | ✅ | ➖ | Rodou em ~185 cupons de loja reais; nenhum validado em carrinho. `VALIDADO` só por `radar validar` |
| Validação automática de cupom em carrinho | ❌ | ❌ | ❌ | Não implementada (login e risco para a conta) |
| Ranking CRÍTICA/ALTA/MÉDIA/BAIXA | ✅ | ✅ | ❌ | Sem oferta real casada, não foi exercitado com dado real |
| Alertas: deduplicação, limite, horário, status enviáveis | ✅ | ✅ | ❌ | **Nenhum alerta real gerado**. Canal de saída validado com 1 mensagem de teste (fase 1) |
| Portão de homologação (ativação explícita) | ✅ | ✅ | ✅ | Config real: `enviar: false`, `homologado_em: null`; `status` mostra "EM SOMBRA" |
| Revalidação na fonte antes de entregar alerta velho | ✅ | ✅ | ➖ | Ao vivo: Promobit (ativa / preço subiu / `FINISHED`) e Gatry (ativa / 404). Pelando, HardMOB e Telegram: sem revalidação (alerta vencido é descartado) |
| Relatório de efetividade | ✅ | ✅ | ✅ | `radar efetividade`; diferencia erro, vazia, sem configuração e "coletando sem ofertas suas" |

## Fontes

| Fonte | Impl. | Testado | Homolog. | Evidência / nota |
|---|:-:|:-:|:-:|---|
| Promobit | ✅ | ✅ | ✅ | ~119 itens/ciclo |
| HardMOB | ✅ | ✅ | ✅ | 32 itens/ciclo (sem data nem comentário na lista) |
| Méliuz | ✅ | ✅ | ✅ | 110 cupons de loja (6 lojas); só cupom de loja |
| **Gatry** (API JSON pública) | ✅ | ✅ | ✅ | 40 itens/ciclo; campos de cupom estruturados; interpretação de `robots.txt` (`Allow: /v1/` vs `Disallow: /*?`) é decisão a validar |
| **Pelando** (HTML/JSON-LD, sem navegador) | ✅ | ✅ | ✅ | 20 de 20 itens completos. **WAF bloqueia Chrome automatizado (não contornado)**; fragilidade média; pode ser bloqueado no futuro |
| Telegram, canais públicos (`t.me/s`) | ✅ | ✅ | ➖ | Guarda de identidade comprovada ao vivo; **nenhum canal habilitado** |
| **Telegram, sua conta** | ✅ | ✅ (leitor falso + API do Telethon 1.46) | ❌ | **Pendente de você**: login (ver 09). Nunca autenticado, nunca testado com rede real |
| WhatsApp: lista de autorização de grupos | ✅ | ✅ | ✅ | Lista vazia ⇒ nenhum grupo lido; regras de recusa verificadas |
| WhatsApp: leitor de grupos | ❌ | ❌ | ❌ | Não escrito (precisa de um grupo autorizado por você para testar) |
| X, Instagram, Facebook | ❌ | ❌ | ❌ | Evidência: 429/429/400 sem login. Sem via gratuita sustentável (ver 04) |
| Keepa | ❌ | ❌ | ❌ | API paga |

## Fase 3 (21/11/2026, tarde): efetividade e homologação

Detalhes e números em [13-relatorio-fase-3.md](13-relatorio-fase-3.md).

| Funcionalidade | Impl. | Testado | Homolog. | Evidência / nota |
|---|:-:|:-:|:-:|---|
| Amostra rotulada e métricas (`radar avaliar`) | ✅ | ✅ | ✅ | 85 itens; precisão 1,00; recuperação 1,00 (IC95 0,92 a 1,0); **só 3 positivos independentes (IC95 inferior 0,44)**; lote ao vivo 0 FP em 133 negativos |
| Reconhecimento: avisos de voltagem, SKU e nome alternativo | ✅ | ✅ | ✅ | ambíguos 7 de 7 (antes 2 de 7); 24 ofertas reais reencenadas, 24 reconhecidas |
| Regra de **novidade** (3% abaixo do melhor preço atual) | ✅ | ✅ | ✅ | reencenação: ALTA caiu de 20 para 12; as 8 que eram o preço já monitorado saíram |
| Cadeia de alerta, 16 cenários sintéticos | ✅ | ✅ | ✅ | `radar homologar` 16/16; mutação 6/6 detectadas |
| Envio real controlado de teste | ✅ | ✅ | ✅ | 1 mensagem rotulada TESTE ao seu WhatsApp |
| Alerta com oferta **ao vivo** dos seus produtos | ✅ | ✅ | ❌ | nenhuma oferta apareceu (0 de 140) |
| Validação manual persistente (`validacoes_manuais`) | ✅ | ✅ | ✅ | migração 3 com backup; cenário S03 (ALTA, validar, CRÍTICA) |
| Cruzamento cupom de loja x produto (`radar cruzar`) | ✅ | ✅ (18) | ➖ | 466 pares, 4 candidatos (`BLACK150`), nenhum confirmado em carrinho |
| Equivalentes (`radar equivalentes`) | ✅ | ✅ | ✅ | Hisense 12k R$ 1.710 em 3 fontes; só informativo |
| Coletores: Promobit por cursor, Pelando (GUID), HardMOB (hora por 1ª vista) | ✅ | ✅ | ✅ | cobertura do Promobit 9 para 42 min; medida a cada ciclo |
| Escopo do Git e backup do código fora do Git | ✅ | ✅ | ✅ | 83 do radar, 30 de outra sessão, 1 misto; status do Git idêntico antes e depois |
| Trava de máquina oficial | ✅ | ✅ | ✅ | simulação de outra máquina com a config real: nada coletado, enviado ou gravado |
| Telegram da sua conta | ✅ | ✅ | ❌ | procedimento curto em `12-telegram-passo-a-passo.md`; **login é seu** |

## Fase 4 (21/11/2026, noite): consolidação, segurança e Black Friday

Detalhes e números em [14-relatorio-fase-4.md](14-relatorio-fase-4.md).

| Funcionalidade | Impl. | Testado | Homolog. | Evidência / nota |
|---|:-:|:-:|:-:|---|
| Backup recuperável do código e das cópias de outra sessão, com foto SHA-256 | ✅ | ✅ | ✅ | restauração testada (195 testes a partir da cópia); `git-escopo --verificar`: 30 arquivos intactos |
| Patch do STATUS.md só com seções do radar | ✅ | ✅ | ✅ | validado com `git apply --check`; nenhuma operação de escrita no Git |
| Prioridade e orçamento de alertas (`radar/prioridade.py`, `radar prioridade`) | ✅ | ✅ (21) | ✅ | pontuação 0 a 100, 6 comuns + 3 críticos + 2 exceção, anti-rajada, anti-repetição, substituição; cenários P01 a P06; em sombra |
| CRÍTICO acima do limite comum com proteção | ✅ | ✅ | ✅ | orçamento próprio, limite por ciclo, intervalo de 30 min e melhora de 5% para repetir |
| Três horas (published, first seen, collected) e hora incerta | ✅ | ✅ | ✅ | migração 4; HardMOB nunca vira "relâmpago" nem ganha urgência |
| Lacunas de coleta (`radar lacunas`) | ✅ | ✅ (5+) | ✅ | simulação de 7 h suspenso: 380 min perdidos; dado real de hoje: 0 lacunas; Promobit cobre só 18 min |
| Corpus em treino, regressão e independente | ✅ | ✅ (10) | ✅ | 179 itens; independente 106 reais; primeira passada achou 1 FP real (Q/f), corrigido; **recall não provado (n=7)** |
| Guarda de cupom (BLACK150 não confirmado, cruzamento nunca alerta) | ✅ | ✅ (6) | ✅ | nenhum módulo de alerta importa o cruzamento |
| Cadeia de alerta, 22 cenários | ✅ | ✅ | ✅ | `radar homologar` 22/22 |
| Alertas reais | ✅ | ✅ | ❌ | desligados por decisão: `enviar: false`, `homologado_em` vazio |
| Commit/push do radar | ➖ | ➖ | ❌ | aguardando sua autorização expressa |

## Fase 5 (21/11/2026, noite): estabilização e pré-Black Friday

Detalhes em [15-relatorio-fase-5.md](15-relatorio-fase-5.md). **Recomendação: NÃO APTO para ativar hoje.**

| Funcionalidade | Impl. | Testado | Homolog. | Evidência / nota |
|---|:-:|:-:|:-:|---|
| Simulação da política (7 situações pedidas + dia cheio) | ✅ | ✅ (11) | ✅ | 8/8; histórico real lido; log em 15-anexo |
| Limiar de pontuação por vaga (contra ordem de chegada dentro do orçamento) | ✅ | ✅ (4) | ✅ | achado da simulação: vaga 1 pede 40, vaga 6 pede 65 |
| Oferta retida pelo orçamento nunca some (`retida_orcamento`) | ✅ | ✅ (4) | ✅ | painel, `retidas`, bloco no relatório com alertas reais |
| Latência medida (`radar latencia`) | ✅ | ✅ (8) | ➖ | publicação a leitura medida ao vivo; entrega WhatsApp medida 1 vez (15,6 s) |
| Estágios de cupom (descoberto, potencialmente elegível, validado, expirado) | ✅ | ✅ (6) | ✅ | BLACK150 e PHI200 não confirmados; `100IMPRESSORA` corrigido |
| Telegram: só canais, id de pessoa recusado | ✅ | ✅ (3) | ❌ | login é seu; guia em 12 |
| Verificação prévia e kill switch (`radar ativacao`) | ✅ | ✅ (7) | ✅ | veredito hoje: NÃO APTO AINDA (PENDENTE: evidência ao vivo) |
| Fila de alertas descartada com alertas desligados | ✅ | ✅ (2) | ✅ | kill switch efetivo |
| Alertas reais | ✅ | ✅ | ❌ | desligados por decisão |

## Fase 6 (21/11/2026, noite): preparação final e piloto

Detalhes em [18-relatorio-fase-6.md](18-relatorio-fase-6.md). **Recomendação: APTO PARA PILOTO, condicionado.**

| Funcionalidade | Impl. | Testado | Homolog. | Evidência / nota |
|---|:-:|:-:|:-:|---|
| Conferência do preço na loja (`radar/lojas.py`, `radar conferir`) | ✅ | ✅ (15) | ✅ | WebContinental e FrioPeças via API pública VTEX; outras lojas ficam "não conferido" |
| Cupom embutido na oferta nunca é descontado de novo; 3 níveis de preço (anunciado, confirmado, entregue) | ✅ | ✅ | ✅ | caso real: anunciado R$ 2.379, loja R$ 2.579, diferença R$ 200 = PHI200, não confirmado |
| Preço que depende de cupom não confirmado limita a classe a MEDIA (sem alerta) | ✅ | ✅ | ✅ | a mesma oferta real passa de ALTA (sem conferir) para MEDIA (conferindo) |
| Confiança ALTA/MEDIA/BAIXA com a razão na mensagem | ✅ | ✅ | ✅ | ALTA exige produto exato e preço conferido na loja ou validado por você |
| Instrumentação do WhatsApp (criação, início, confirmação, fila) e teste único | ✅ | ✅ (6) | ➖ | `radar teste-entrega`; **latência real só depois do seu `--confirmo`** |
| Ensaio do kill switch e da fila | ✅ | ✅ | ✅ | `radar ativacao --ensaio-kill-switch` |
| Janela Black Friday do Promobit (5 min, 26 a 30/11) + tarefa dedicada | ✅ | ✅ (11) | ➖ | volta ao normal por data; tarefa expira sozinha; **ainda não criada no Windows** |
| Modo PILOTO (limites 2/1/0, 1 por varredura, produto exato, sem aviso, fonte revalidada, destinatário confirmado) | ✅ | ✅ (13) | ➖ | SOMBRA continua o padrão |
| Telegram: somente leitura, id de pessoa recusado, sem Coral | ✅ | ✅ | ❌ | login é seu |
| Alertas reais | ✅ | ✅ | ❌ | desligados |

## O que depende de você

0. Autorizar o commit, decidir o orçamento de alertas e testar o `BLACK150` no carrinho (fase 4).
1. Telegram: criar `api_id/api_hash`, rodar `telegram-login`, escolher canais (09).
2. Decidir se quer o leitor de grupos de WhatsApp e quais nomes autorizar.
3. Homologar os alertas (`homologado_em`) quando o que o radar chama de urgente fizer sentido para você.
4. Decidir a máquina oficial e, se for trocar, seguir o procedimento (09).
5. Confirmar a leitura de `robots.txt` do Gatry e a escolha de usar o HTML público do Pelando (ambas defensáveis, mas são decisão sua).
