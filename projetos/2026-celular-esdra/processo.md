# Processo da compra: Celular para Esdra (512 GB / 1 TB)

## Estado atual

- Estado: pesquisando (Rodada 1: varredura ampla documentada; preços e estoque ainda não confirmados manualmente)
- Proxima acao: coletar respostas do Josemar sobre orcamento, tela, sistema e prazo para afunilar candidatos
- Decisao aberta: decisao sobre manter iOS ou migrar para Android considerando a restricao critica do WhatsApp Business

## Linha do tempo decisoria

| Data | Etapa | Decisao | Por que |
|---|---|---|---|
| 2026-10-03 | abertura | Compra criada no sistema | Celular atual (iPhone 14 Plus 128 GB) com memoria saturada e backup travado |
| 2026-10-03 | pesquisa | Varredura de 13 modelos em 3 faixas | Mapeamento com links específicos; Apple, Samsung, Motorola, Realme, Xiaomi/POCO/Redmi e HONOR. Asus e OnePlus ficaram sem variante nacional comprovada nesta rodada. |
| 2026-10-03 | alerta tecnico | Limitação oficial no WhatsApp Business | Meta não oferece transferência de conversas do Business de iPhone para Android. Continuidade no iPhone também exige validação dos dados antes de apagar o antigo. |
| 2026-10-03 | planilha | Criada comparacao.xlsx com 4 abas | Comparativo de modelos, matriz iOS vs Android, simulador de custo liquido e fontes |
| 2026-10-03 | planilha | comparacao.xlsx refeita e mesclada (Claude Code): 51 modelos (importados em cinza, filtráveis), 105 anúncios, 7 abas | A v1 trazia modelos de 2024 com link para a página inicial da loja e preços não localizados; as 14 linhas foram para a aba Fora_da_lista com o motivo. Entraram os preços oficiais Apple, Samsung e Motorola e os anúncios Amazon com vendedor conferido. Gerador: `scripts/gerar_planilha_celular.py`. |
| 2026-10-03 | pesquisa | Xiaomi/POCO/Redmi e HONOR de importador ficam fora | Amazon e KaBuM só mostraram vendedores de versão “global” (Power Dealls, BRASIL-VENDAS, CELCOMERCE, NOVA ERA); canal oficial da Xiaomi é a Mi Brasil (DL). |

## Etapas

- [x] 1. Definir o modelo e a especificacao tecnica para o meu contexto (com acessorios)
- [x] 2. Mapear opções (51 modelos e 105 anúncios em `comparacao.xlsx`, aba Comparativo_Modelos; elegibilidade final ainda pendente)
- [ ] 3. Registrar produtos em `produtos/` apos respostas do Josemar
- [ ] 4. Coletar cotacoes iniciais
- [ ] 5. Aplicar gates eliminatorios
- [ ] 6. Comparar finalistas
- [ ] 7. Confirmar preco/frete/estoque manualmente
- [ ] 8. Registrar decisao e por que os outros perderam
- [ ] 9. Comprar
- [ ] 10. Fazer veredito D+30
- [ ] 11. Fazer veredito D+180

## O que ja sei

- Aparelho atual e um iPhone 14 Plus de 128 GB com 3 GB livres.
- O WhatsApp Business ocupa 41 GB de midia em catalogos PDF e videos.
- O backup do iCloud esta falhando desde dez/2025.
- Cartao de memoria MicroSD nao resolve o WhatsApp (banco roda apenas na memoria interna).
- WhatsApp Business não oferece transferência oficial de conversas de iPhone para Android (fonte Meta no dossiê).
- Início Rápido permite transferência direta entre iPhones; migração integral dos dados específicos do Business precisa ser conferida no aparelho novo.
- O próprio WhatsApp transfere conversas e mídia de iPhone para iPhone por QR code e Wi-Fi, sem passar pelo iCloud (FAQ 209942271778103). Que o mesmo menu exista no app Business: [VERIFICAR no aparelho dela].
- Prazos de atualização com fonte: Samsung S26 7 anos; Motorola Signature até 7 anos; Edge 70 4 upgrades e segurança até jul/2031; Edge 70 Pro 3 upgrades e 5 anos de segurança. Apple não publica prazo.
- Loja Samsung: 18x sem juros e “Compre & Teste” de 60 dias na linha S26 (página de 03/10/2026).
- OnePlus e Asus: oferta de variante de 512 GB com canal oficial, Anatel e garantia brasileira [VERIFICAR]; não há descarte categórico da marca.
- Valor de venda ou trade-in do iPhone 14 Plus 128 GB [VERIFICAR após avaliação individual]; preço de revenda de loja não é proposta de compra.

## O que ainda preciso descobrir

- Orcamento maximo do Josemar.
- Se a Esdra esta disposta a trocar de sistema ou se prefere continuar no ecossistema Apple.
- Tamanho de tela preferido (se faz questao da tela grande de 6,7 pol do Plus ou aceita 6,1 pol).
- Prazo para a compra e condicoes de pagamento (Pix a vista ou parcelado no cartao).

## Hipoteses descartadas

| Hipotese | Motivo do descarte |
|---|---|
| Comprar celular com 256 GB e usar cartao MicroSD | WhatsApp Business salva banco de dados exclusivamente na memoria interna e ignora cartao SD. |
| Variante sem prova de canal oficial, homologação Anatel e assistência técnica | Critério eliminatório da compra, independentemente da marca. |
| Comprar Poco / Xiaomi via marketplace paralelo sem nota fiscal nacional | Falta de cobertura de garantia pela autorizada oficial da DL Eletrônicos no Brasil. |
