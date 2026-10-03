"""Gera projetos/2026-celular-esdra/comparacao.xlsx (rodada 1, consulta 03/10/2026).

Mescla a pesquisa do Antigravity (01-pesquisa-mercado.md) com a varredura do
Claude Code na mesma data (Apple, Samsung e Motorola oficiais, Amazon, KaBuM).
Preco aqui e observacao web (fonte=web): nao fecha compra. A primeira versao
desta planilha (modelos de 2024 com link generico) foi para a aba
Fora_da_lista com o motivo.

Rodar da raiz do repositorio:  python scripts/gerar_planilha_celular.py
"""
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

DATA = "03/10/2026"
DESTINO = "projetos/2026-celular-esdra/comparacao.xlsx"
V = "[VERIFICAR]"

AMZ = "https://www.amazon.com.br/dp/"
MOTO = "https://www.motorola.com.br/"
SAMS = "https://appvtex.samsung.com.br/"
APPLE = "https://www.apple.com/br/shop/buy-iphone/"
SRC_MD = "Antigravity (01-pesquisa-mercado.md)"
SRC_CC = "Claude Code"

# Cada modelo: faixa, marca, modelo, interno, tela, camera, bateria, atualizacoes,
# preco oficial, link oficial, preco varejo confiavel (vendido por Amazon/Magalu),
# vendedor varejo, link varejo, preco marketplace terceiro (so referencia),
# vendedor terceiro, status/estoque, observacoes, origem.
MODELOS = [
    # ---------------- Custo-beneficio ----------------
    dict(faixa="Custo-benefício", marca="Motorola", modelo="Moto g86 5G (12 GB RAM)", interno="512 GB",
         tela=f"pOLED 1.5K, tamanho {V}", camera=f"50 MP Sony LYTIA 600; OIS {V}", bateria="5.200 mAh",
         updates=V, oficial=2221.11, link_oficial=MOTO + "smartphone-motorola-moto-g86-5g-512gb-24-gb-ram/p",
         varejo=2159.10, vend_varejo="Amazon (variante 8 GB RAM)", link_varejo=AMZ + "B0FCYJ336S",
         status="Em estoque (oficial e Amazon)",
         obs="O mais barato com 512 GB e canal oficial. Câmera de uma lente só: fraca para close de produto.",
         origem=SRC_CC),
    dict(faixa="Custo-benefício", marca="Motorola", modelo="Edge 60 5G", interno="512 GB",
         tela=f"Quad-Curve 1.5K, tamanho {V}", camera="50 MP OIS (LYTIA 700C) + 50 MP ultra/macro + 10 MP tele",
         bateria="5.200 mAh", updates=V, oficial=2499.00, link_oficial=MOTO + "smartphone-motorola-edge-60-5g/p",
         terceiro=2279.05, vend_terceiro="Mika Eletrônicos (Amazon)", link_terceiro=AMZ + "B0F51KRTX1",
         status="Em estoque (oficial)",
         obs="Tem macro e tele no preço de entrada. Tela curva quebra mais fácil sem capa boa.", origem=SRC_CC),
    dict(faixa="Custo-benefício", marca="Motorola", modelo="Edge 60 Neo 5G", interno="512 GB",
         tela=V, camera=f"50 MP Sony {V}", bateria=V, updates=V, oficial=2299.00,
         link_oficial=MOTO + "smartphone-motorola-edge-60-neo-5g-512gb/p",
         status="Sem estoque na loja oficial", obs="Só referência de preço enquanto não voltar.", origem=SRC_CC),
    dict(faixa="Custo-benefício", marca="Motorola", modelo="Edge 60 Pro 5G", interno="512 GB",
         tela=f"Quad-Curve 1.5K, tamanho {V}", camera=f"50 MP Sony LYTIA; demais lentes {V}",
         bateria="6.000 mAh, recarga 90 W", updates=V, oficial=4099.00,
         link_oficial=MOTO + "smartphone-motorola-edge-60-pro-5g-512gb/p",
         varejo=3154.09, vend_varejo="Magalu (via Amazon)", link_varejo=AMZ + "B0F7J4V7L2",
         status="Sem estoque no oficial; em estoque na Magalu",
         obs="Bateria grande para o preço. Modelo de 2025.", origem=SRC_CC),
    dict(faixa="Custo-benefício", marca="Xiaomi", modelo="POCO M8 5G", interno="512 GB",
         tela=V, camera="50 MP, vídeo 4K; close " + V, bateria="5.520 mAh", updates=V,
         oficial=3403.99,
         link_oficial="https://www.mibrasil.com.br/smartphone-xiaomi-poco-m8-5g-nfc-br-8-8gb-ram-virtual-512gb-prin-p54613",
         status="“Avise-me” na Mi Brasil", obs="Canal oficial (DL). Caro para o que entrega.", origem=SRC_MD),
    dict(faixa="Custo-benefício", marca="Xiaomi", modelo="Redmi Note 15 5G", interno="512 GB",
         tela=V, camera="108 MP; close e cor " + V, bateria=V, updates=V, oficial=3587.99,
         link_oficial="https://www.mibrasil.com.br/smartphone-redmi-note-15-5g-nfc-br-8-8gb-ram-virtual-512gb-prin-p54645",
         status="“Avise-me” na Mi Brasil", obs="Canal oficial (DL).", origem=SRC_MD),
    dict(faixa="Custo-benefício", marca="Motorola", modelo="Edge 70 5G", interno="512 GB",
         tela="6,7\" AMOLED 1.5K, 120 Hz", camera="3× 50 MP (principal com OIS), vídeo 4K",
         bateria="4.800 mAh, 68 W, sem fio 15 W", updates="4 upgrades de Android; segurança até jul/2031",
         oficial=3999.00, link_oficial=MOTO + "smartphone-motorola-edge-70-5g-512gb/p",
         varejo=3599.00, vend_varejo="Amazon", link_varejo=AMZ + "B0GM1JJD66",
         terceiro=3599.10, vend_terceiro="Motorola, versão Swarovski",
         link_terceiro=MOTO + "smartphone-motorola-edge-70-5g-swarovski/p?idsku=1794",
         status="Em estoque",
         obs="Mesmo tamanho de tela do Plus. Bateria é a menor da faixa (aparelho de 5,99 mm).",
         origem=f"{SRC_CC} + {SRC_MD}"),
    # ---------------- Intermediario forte ----------------
    dict(faixa="Intermediário forte", marca="Motorola", modelo="Edge 70 Fusion+ 5G", interno="512 GB",
         tela=V, camera=f"50 MP Sony {V}", bateria="5.200 mAh", updates=V, oficial=4199.00,
         link_oficial=MOTO + "smartphone-motorola-edge-70-fusion-512gb-5g/p", status="Em estoque (oficial)",
         obs="Ficha incompleta nesta rodada.", origem=SRC_CC),
    dict(faixa="Intermediário forte", marca="HONOR", modelo="Magic7 Lite 5G", interno="512 GB",
         tela=V, camera="108 MP com OIS; close " + V, bateria="6.600 mAh", updates=V, oficial=4599.99,
         link_oficial="https://www.honor.com.br/honor-magic7-lite-5g-12-12gb-ram-turbo-256gb-p31",
         status="“Avise-me”; KaBuM lista vendido por “Honor Oficial”",
         obs="URL diz 256 GB e a ficha diz 512 GB: confirmar SKU. Rede de assistência no interior " + V,
         origem=f"{SRC_MD} + {SRC_CC}"),
    dict(faixa="Intermediário forte", marca="Motorola", modelo="Edge 70 Pro 5G", interno="512 GB",
         tela=V, camera=f"4 câmeras de 50 MP (conta inclui a frontal {V})", bateria="6.500 mAh",
         updates="3 upgrades de sistema e 5 anos de segurança", oficial=4999.00,
         link_oficial=MOTO + "smartphone-motorola-edge-70-pro-5g-512gb/p", status="Em estoque (oficial)",
         obs="Maior bateria da Motorola nesta lista.", origem=SRC_CC),
    dict(faixa="Intermediário forte", marca="Apple", modelo="iPhone 17e", interno="512 GB",
         tela="6,1\"", camera="48 MP Fusion (uma câmera traseira)", bateria="Até 26 h de vídeo (Apple)",
         updates="Apple não publica prazo fixo " + V, oficial=7499.00,
         link_oficial=APPLE + "iphone-17e/tela-de-6%2C1-polegadas-512gb-preto",
         varejo=4939.04, vend_varejo="Magalu (via Amazon)", link_varejo=AMZ + "B0GTS8LCSB",
         status="Em estoque",
         obs="iPhone de 512 GB mais barato. Tela menor que o Plus e sem ultra-wide/macro.",
         origem=f"{SRC_MD} + {SRC_CC}"),
    dict(faixa="Intermediário forte", marca="Samsung", modelo="Galaxy S25+", interno="512 GB",
         tela="6,7\"", camera="50 MP OIS + tele 3x + ultra-wide", bateria="4.900 mAh",
         updates="7 gerações de sistema e 7 anos de segurança", oficial=5199.00,
         link_oficial=SAMS + "galaxy-s25-plus-512gb/p", status="“A partir de”: confirmar variante",
         obs="Geração 2025, mesma tela do Plus.", origem=SRC_MD),
    dict(faixa="Intermediário forte", marca="Samsung", modelo="Galaxy S26+", interno="512 GB",
         tela="6,7\"", camera="50 + 12 + 10 MP (tele 3x)", bateria="4.900 mAh",
         updates="7 anos de sistema e segurança", oficial=6665.00, link_oficial=SAMS + "galaxy-s26-plus-512gb/p",
         varejo=5999.01, vend_varejo="Amazon", link_varejo=AMZ + "B0GKQYKBQ9", status="Em estoque",
         obs="Mesma tela do Plus. Nota 4,4 com só 25 avaliações na Amazon.", origem=f"{SRC_MD} + {SRC_CC}"),
    dict(faixa="Intermediário forte", marca="Samsung", modelo="Galaxy S26", interno="512 GB",
         tela="6,3\"", camera="50 + 12 + 10 MP", bateria="4.300 mAh", updates="7 anos de sistema e segurança",
         oficial=6443.33, link_oficial=SAMS + "galaxy-s26-512gb/p",
         terceiro=6118.38, vend_terceiro="Toledo Digital, enviado pela Amazon", link_terceiro=AMZ + "B0GKR1QX37",
         status="Em estoque", obs="Menor e com bateria menor que o S26+ por preço parecido.", origem=SRC_CC),
    dict(faixa="Intermediário forte", marca="Apple", modelo="iPhone 17", interno="512 GB",
         tela="6,3\" 120 Hz", camera="48 MP Fusion + 48 MP ultra-wide (macro)", bateria="Até 30 h de vídeo (Apple)",
         updates="Apple não publica prazo fixo " + V, oficial=9799.00,
         link_oficial=APPLE + "iphone-17/tela-de-6%2C3-polegadas-512gb-s%C3%A1lvia",
         varejo=6173.95, vend_varejo="Magalu (via Amazon)", link_varejo=AMZ + "B0GQW7S1XS",
         status="Em estoque",
         obs="iPhone mais equilibrado para produto (tem macro). Tela menor que o Plus.",
         origem=f"{SRC_MD} + {SRC_CC}"),
    dict(faixa="Intermediário forte", marca="Realme", modelo="GT 7 5G", interno="512 GB",
         tela=V, camera="50 MP OIS + tele 2x 50 MP", bateria="7.000 mAh", updates=V, oficial=6269.99,
         link_oficial="https://www.realmestore.com.br/produtos/celular-realme-gt-7-12gb-512gb-dimensity-9400e-5g/",
         status="Esgotado", obs="Vínculo da loja com o fabricante e garantia " + V, origem=SRC_MD),
    dict(faixa="Intermediário forte", marca="Motorola", modelo="Signature 5G", interno="512 GB",
         tela="6,8\" AMOLED 165 Hz", camera="4× 50 MP, tele 3x com OIS, macro; selo DXOMARK Ouro",
         bateria="5.200 mAh", updates="Até 7 anos de sistema e segurança", oficial=6999.00,
         link_oficial=MOTO + "smartphone-motorola-signature/p",
         varejo=6569.10, vend_varejo="Motorola, kit com fone Moto Buds Loop",
         link_varejo=MOTO + "kit-smartphone-motorola-signature-e-fone-moto-buds-loop/p?idsku=1841",
         terceiro=5366.62, vend_terceiro="PRIZMO (Amazon)", link_terceiro=AMZ + "B0GMKS98D5",
         status="Em estoque (oficial)",
         obs="Melhor câmera + atualização do Android abaixo de R$ 7 mil. O kit com fone sai mais barato que o aparelho sozinho.",
         origem=f"{SRC_CC} + {SRC_MD}"),
    dict(faixa="Intermediário forte", marca="Xiaomi", modelo="15T 5G", interno="512 GB",
         tela=V, camera="50 MP Leica; demais lentes " + V, bateria=V, updates=V, oficial=6999.99,
         link_oficial="https://www.mibrasil.com.br/smartphone-xiaomi-15t-5g-prin-p13612",
         status="Estoque por cor " + V, obs="Canal oficial (DL).", origem=SRC_MD),
    dict(faixa="Intermediário forte", marca="Apple", modelo="iPhone Air", interno="512 GB",
         tela=V, camera="48 MP Fusion (uma câmera traseira)", bateria=V,
         updates="Apple não publica prazo fixo " + V, oficial=12499.00, link_oficial=APPLE + "iphone-air",
         varejo=7254.32, vend_varejo="Amazon", link_varejo=AMZ + "B0FQHRNRYQ", status="Em estoque",
         obs="Anúncio escrito em português de Portugal: conferir se é modelo nacional (Anatel). Uma câmera só.",
         canal="Varejo nacional; modelo nacional [VERIFICAR]",
         origem=SRC_CC),
    # ---------------- Topo de linha ----------------
    dict(faixa="Topo de linha", marca="Apple", modelo="iPhone 17 Pro Max", interno="512 GB",
         tela=V, camera="3× 48 MP, zoom óptico 8x", bateria=V, updates="Apple não publica prazo fixo " + V,
         varejo=9796.76, vend_varejo="Amazon", link_varejo=AMZ + "B0FQH3X8R8",
         status="Apple já não vende (linha atual é 18 Pro)",
         obs="Anúncio em português de Portugal: conferir modelo nacional. Tamanho Max, sucessor do Plus.",
         canal="Varejo nacional; modelo nacional [VERIFICAR]",
         origem=SRC_CC),
    dict(faixa="Topo de linha", marca="Samsung", modelo="Galaxy S26 Ultra", interno="512 GB",
         tela="6,9\"", camera="Quádrupla até 200 MP", bateria="5.000 mAh, recarga 60 W",
         updates="7 anos de sistema e segurança", oficial=13099.00, link_oficial=SAMS + "galaxy-s26-ultra-512gb/p",
         varejo=9690.33, vend_varejo="Amazon (cor preta)", link_varejo=AMZ + "B0GKQBYWTY",
         terceiro=8739.05, vend_terceiro="Toledo Digital, enviado pela Amazon (violeta)",
         link_terceiro=AMZ + "B0GKQP7T39", status="Em estoque",
         obs="Câmera mais completa da lista. Loja Samsung: 18x sem juros e “Compre & Teste” de 60 dias.",
         origem=SRC_CC),
    dict(faixa="Topo de linha", marca="Samsung", modelo="Galaxy S26 Ultra (16 GB RAM)", interno="1 TB",
         tela="6,9\"", camera="Quádrupla até 200 MP", bateria="5.000 mAh, recarga 60 W",
         updates="7 anos de sistema e segurança", oficial=15499.00, link_oficial=SAMS + "galaxy-s26-ultra-1tb/p",
         terceiro=12249.00, vend_terceiro="Toledo Digital, enviado pela Amazon", link_terceiro=AMZ + "B0GKRBNDNJ",
         status="Em estoque", obs="Único Android de 1 TB com canal oficial nesta rodada.",
         origem=f"{SRC_CC} + {SRC_MD}"),
    dict(faixa="Topo de linha", marca="Apple", modelo="iPhone 18 Pro", interno="512 GB",
         tela="6,3\"", camera="Três câmeras de 48 MP", bateria=V, updates="Apple não publica prazo fixo " + V,
         oficial=13499.00, link_oficial=APPLE + "iphone-18-pro",
         terceiro=12149.10, vend_terceiro="Amazon, vendedor " + V, link_terceiro=AMZ + "B0HJB9YV1F",
         status="Lançamento", obs="Tela pequena para quem vem do Plus.", origem=SRC_CC),
    dict(faixa="Topo de linha", marca="Apple", modelo="iPhone 18 Pro Max", interno="512 GB",
         tela="6,9\"", camera="Três câmeras de 48 MP; macro e vídeo profissional",
         bateria="Até 29 h de uso por recarga (anúncio)", updates="Apple não publica prazo fixo " + V,
         oficial=14499.00, link_oficial=APPLE + "iphone-18-pro/tela-de-6%2C9-polegadas-512gb-bord%C3%B4",
         varejo=13049.10, vend_varejo="Amazon", link_varejo=AMZ + "B0HJ9VQMB1", status="Em estoque",
         obs="Sucessor natural do tamanho Plus no iPhone. Maior preço iOS de 512 GB.",
         origem=f"{SRC_MD} + {SRC_CC}"),
    dict(faixa="Topo de linha", marca="Apple", modelo="iPhone 18 Pro Max", interno="1 TB",
         tela="6,9\"", camera="Três câmeras de 48 MP", bateria="Até 29 h de uso por recarga (anúncio)",
         updates="Apple não publica prazo fixo " + V, oficial=17499.00, link_oficial=APPLE + "iphone-18-pro",
         status="Loja Apple", obs="R$ 3 mil a mais que o de 512 GB.", origem=SRC_CC),
]

IMPORTADO = "Não comprovada (vendedor de versão importada/global)"
KABUM = "https://www.kabum.com.br/produto/"


def extra(marca, modelo, preco, vendedor, link, tela=V, camera=V, bateria=V, obs="", canal=IMPORTADO,
          interno="512 GB", status="Anúncio ativo em 03/10/2026"):
    faixa = "Custo-benefício" if preco <= 4000 else "Intermediário forte" if preco <= 8000 else "Topo de linha"
    return dict(faixa=faixa, marca=marca, modelo=modelo, interno=interno, tela=tela, camera=camera, bateria=bateria,
                updates=V, terceiro=preco, vend_terceiro=vendedor, link_terceiro=link, status=status,
                obs=obs or "Entrou para você refinar. Sem garantia nacional comprovada, não passa no critério 4.",
                origem=SRC_CC, canal=canal)


# Vistos na varredura e fora do critério de garantia (ou fora do perfil): entram para filtro.
MODELOS += [
    extra("Xiaomi", "POCO X8 Pro (12 GB RAM)", 2579.25, "Power Dealls (Amazon)", AMZ + "B0GN1MW5MB",
          tela="6,59\" AMOLED 120 Hz", camera="50 + 8 MP", bateria="6.500 mAh (comparador web)"),
    extra("Xiaomi", "POCO X8 Pro Max (12 GB RAM)", 3499.00, "CELCOMERCE (KaBuM), “global”", KABUM + "1017191",
          tela="6,83\"", camera="50 + 8 MP"),
    extra("Xiaomi", "Redmi Note 15 Pro 5G (8 GB RAM)", 2123.25, "Power Dealls (Amazon)", AMZ + "B0GQD3W1R4",
          tela="6,83\" AMOLED 1.5K 120 Hz", camera="200 MP com OIS, vídeo 4K", bateria="6.580 mAh"),
    extra("Xiaomi", "Redmi Note 15 Pro+ 5G (12 GB RAM)", 2789.00, "CELCOMERCE (KaBuM)", KABUM + "1003252",
          tela="6,83\"", camera="200 + 8 MP"),
    extra("Xiaomi", "Redmi Note 17 Pro 5G (8 GB RAM)", 2849.05, "Amazon, anúncio em espanhol", AMZ + "B0H6WRY4NJ",
          tela="6,83\" 120 Hz", bateria="8.340 mAh, 67 W"),
    extra("Xiaomi", "Redmi Note 17 Pro Max 5G (8 GB RAM)", 3419.05, "Amazon, anúncio em espanhol", AMZ + "B0H6X46KRK",
          tela="6,83\" 120 Hz", bateria="10.000 mAh, 100 W",
          obs="Maior bateria vista. Também na KaBuM (TUDOSMART) por R$ 4.289,90. Garantia nacional não comprovada."),
    extra("Xiaomi", "POCO X7 Pro 5G (12 GB RAM)", 2260.05, f"Amazon, vendedor {V}", AMZ + "B0DRD1SBSD",
          obs="Geração 2025. Vendedor não conferido."),
    extra("Xiaomi", "POCO F8 Pro (12 GB RAM)", 3799.00, "CELLSTORE (KaBuM), “global”", KABUM + "1019997",
          tela="6,59\"", camera="50 + 50 + 8 MP"),
    extra("Xiaomi", "POCO F8 Ultra (16 GB RAM)", 5599.00, "NOVA ERA (KaBuM)", KABUM + "1019973",
          tela="6,9\"", camera="3× 50 MP"),
    extra("Xiaomi", "Xiaomi 17T (12 GB RAM)", 3999.00, "CELCOMERCE (KaBuM), “global”", KABUM + "1053422",
          tela="6,59\"", camera="50 + 50 + 12 MP"),
    extra("Xiaomi", "Xiaomi 17T Pro (12 GB RAM)", 5499.00, "CELCOMERCE (KaBuM), “global”", KABUM + "1053424",
          tela="6,83\"", camera="50 + 50 + 12 MP"),
    extra("Xiaomi", "Xiaomi 17 (12 GB RAM)", 5799.00, "CELCOMERCE (KaBuM), “global”", KABUM + "1032252",
          tela="6,3\"", camera="3× 50 MP"),
    extra("Realme", "15 Pro 5G", 3999.00, "LOGIN INFORMATICA (KaBuM)", KABUM + "942089",
          tela="6,8\"", camera="50 MP", canal=f"Vendedor de varejo; garantia {V}",
          obs="Vendedor não é a Realme. Conferir nota e garantia."),
    extra("HONOR", "Magic8 Pro (12 GB RAM)", 12799.00, "Infotecdez importados USA (KaBuM)", KABUM + "1062062"),
    extra("HONOR", "Magic V3 (dobrável)", 19999.99, "Honor Oficial (KaBuM)", KABUM + "907139",
          canal="Sim (vendido pela Honor Oficial)", obs="Dobrável: caro e mais frágil para ferramenta de trabalho."),
    extra("Huawei", "Pura 80 Pro (12 GB RAM)", 3719.34, "Amazon (marketplace)", AMZ + "B0FDKNBCQ8",
          camera="Sensor de 1 polegada + tele", obs="Sem serviços do Google; venda oficial de celular Huawei no Brasil " + V),
    extra("Huawei", "Mate 80 Pro (16 GB RAM)", 5689.82, "Amazon (marketplace)", AMZ + "B0GVRZ5S8Z",
          tela="6,75\" OLED", obs="Sem serviços do Google; venda oficial de celular Huawei no Brasil " + V),
    extra("Samsung", "Galaxy S25+ (anúncio Amazon)", 4654.05, f"Amazon, vendedor {V}", AMZ + "B0DSY8CP8H",
          tela="6,7\"", camera="50 + 12 + 10 MP", canal=f"Varejo nacional {V}",
          obs="Nota 4,8 com 1,4 mil avaliações. Conferir vendedor; se for a Amazon, fica abaixo da loja Samsung."),
    extra("Samsung", "Galaxy S26 Ultra (anúncio KaBuM)", 7999.00, "NOVA ERA (KaBuM)", KABUM + "1029920",
          tela="6,9\"", camera="Quádrupla até 200 MP", bateria="5.000 mAh",
          obs="Vendedor de importados. Na mesma busca a Magalu (via KaBuM) cobrava R$ 11.789,10."),
    extra("Samsung", "Galaxy Z Fold8 (dobrável)", 11285.11, f"Amazon, vendedor {V}", AMZ + "B0HCWW3VQQ",
          tela="7,6\" interna", canal=f"Varejo nacional {V}", obs="Dobrável. Z Fold8 Ultra 512 GB: R$ 12.529 (B0HCX34DQ1)."),
    extra("Motorola", "Edge 70 Swarovski (anúncio Amazon)", 3059.10, f"Amazon, vendedor {V}", AMZ + "B0GMY41LM8",
          tela="6,7\"", camera="3× 50 MP", bateria="4.800 mAh", canal=f"Varejo nacional {V}",
          obs="Mais barato que o Edge 70 comum. Conferir vendedor."),
    extra("Apple", "iPhone 17 Pro", 9114.01, f"Amazon, vendedor {V}", AMZ + "B0FQHG7GHG",
          camera="3× 48 MP", canal=f"Varejo nacional; modelo nacional {V}",
          obs="Apple já não vende. Cor azul: R$ 9.719,10 (B0FQHPRVG5). Tela menor que o Plus."),
    extra("Apple", "iPhone 17 Pro Max", 13949.10, f"Amazon, vendedor {V}", AMZ + "B0FQHGM3B1", interno="1 TB",
          camera="3× 48 MP, zoom óptico 8x", canal=f"Varejo nacional; modelo nacional {V}", obs="Apple já não vende."),
    extra("Apple", "iPhone Duo (dobrável)", 21999.00, "Apple (pré-venda 16/10)", APPLE.rstrip("/"), interno=V,
          canal="Sim (Apple)", status="Pré-venda em 16/10/2026", obs="Dobrável e caro. Capacidade do preço inicial " + V),
]

FORA = [
    ("Samsung", "Galaxy A57", "R$ 2.279 (256 GB)", "Amazon", "No Brasil só aparece com até 256 GB.", SRC_CC),
    ("Apple", "iPhone 16", "R$ 6.999", "Apple", "Loja Apple só mostrou 128 GB.", SRC_CC),
    ("ASUS", "Zenfone / ROG Phone 512 GB", "-", "KaBuM",
     "Nenhum ASUS de 512 GB com canal oficial encontrado nesta rodada " + V, f"{SRC_CC} + {SRC_MD}"),
    ("OnePlus", "-", "-", "-", "Venda oficial no Brasil não encontrada " + V, f"{SRC_CC} + {SRC_MD}"),
]
# Primeira versao desta planilha (Antigravity): nenhuma linha trazia link do produto.
FORA += [
    (marca, modelo, preco, "planilha anterior",
     "Saiu: modelo de 2024/2025 com link para a página inicial da loja; preço não localizado na consulta de 03/10/2026.",
     "Antigravity (comparacao.xlsx v1)")
    for marca, modelo, preco in [
        ("Realme", "12 Pro+ 5G", "R$ 2.699"), ("Xiaomi", "Poco X6 Pro 5G", "R$ 2.450"),
        ("Xiaomi", "Poco F6 5G", "R$ 2.890"), ("Realme", "GT 6 5G", "R$ 3.599"),
        ("Samsung", "Galaxy S24 FE", "R$ 4.799"), ("Samsung", "Galaxy S24+", "R$ 4.999"),
        ("Motorola", "Edge 50 Ultra", "R$ 4.499"), ("Apple", "iPhone 15 Plus", "R$ 5.799"),
        ("Apple", "iPhone 16 Plus", "R$ 8.999"), ("Apple", "iPhone 16 512 GB", "R$ 7.999"),
        ("Samsung", "Galaxy S24 Ultra 512 GB", "R$ 5.799"), ("Samsung", "Galaxy S24 Ultra 1 TB", "R$ 7.699"),
        ("Apple", "iPhone 16 Pro Max", "R$ 11.699"), ("ASUS", "Zenfone 11 Ultra", "R$ 8.999"),
    ]
]

WA_IOS_ANDROID = "https://faq.whatsapp.com/1295296267926284/?locale=pt_BR"
WA_IOS_IOS = "https://faq.whatsapp.com/209942271778103/?locale=pt_BR&cms_platform=iphone"
MIGRACAO = [
    ("WhatsApp Business: conversas e mídia",
     "Transferência direta iPhone → iPhone pelo próprio WhatsApp (QR code + Wi-Fi), sem depender do backup do iCloud que está falhando. Vale para o app Business " + V + " no aparelho antes.",
     "A ajuda oficial diz: “No momento, não é possível transferir conversas do WhatsApp Business de um iPhone para um dispositivo Android.”",
     "Crítico. Os 41 GB de histórico com clientes não passam para Android hoje.",
     "Bloqueio no Android", f"{WA_IOS_IOS} ; {WA_IOS_ANDROID}"),
    ("WhatsApp comum (não Business)",
     "Mesma transferência direta.",
     "Funciona: Android 6 ou superior, mesmo número, Wi-Fi, sem cabo. Não passam nome de exibição, status e mídia de canais.",
     "Só ajuda se o número pessoal estiver no WhatsApp comum.", "Baixo", WA_IOS_ANDROID),
    ("Catálogo e coleções do Business",
     "Continuam na conta " + V + " (conferir no aparelho novo antes de apagar o antigo).",
     "Atalho Business → WhatsApp comum → Business perde catálogo e coleções, segundo a Meta.",
     "Recadastrar produtos e preços tomaria dias de trabalho.", "Alto no Android",
     "https://faq.whatsapp.com/639635861080326/?cms_platform=android"),
    ("Fotos do iCloud",
     "Continuam integradas. Com 512 GB dá para desligar “Otimizar Armazenamento” se quiser tudo no aparelho.",
     "Apple copia a biblioteca para o Google Fotos (3 a 7 dias, exige espaço no Google; alguns álbuns e formatos não passam).",
     "Médio: pode exigir plano pago do Google One.", "Médio no Android", "https://support.apple.com/en-gb/118257"),
    ("Senhas",
     "Continuam no iCloud/Senhas.",
     "Android Switch leva senhas em aparelhos compatíveis; caminho manual é CSV legível, que não leva todos os tipos.",
     "Portais das marcas (Natura, Avon, Boticário) precisariam de novo login.", "Baixo a médio",
     "https://www.android.com/switch-to-android/ ; https://support.apple.com/guide/iphone/export-passwords-iphf28f2e93e/ios"),
    ("Apps e assinaturas pagos",
     "Continuam.", "Compra da App Store não vira compra na Play Store; assinatura depende do desenvolvedor.",
     "Ver quais apps pagos ela usa " + V, "Baixo a médio", "Antigravity (01-pesquisa-mercado.md)"),
    ("Tempo de atualização prometido",
     "Apple não publica prazo fixo " + V + ".",
     "Samsung S26: 7 anos. Motorola Signature: até 7 anos. Edge 70: 4 upgrades e segurança até jul/2031.",
     "Para 4 a 5 anos de uso, Samsung e Signature têm prazo escrito.", "Vantagem do Android (prazo escrito)",
     "Páginas oficiais na aba Fontes"),
    ("Preço de 512 GB",
     "Menor preço visto: iPhone 17e R$ 4.939 (Magalu). iPhone 17 R$ 6.174 (Magalu).",
     "Menor preço visto com canal oficial: Moto g86 R$ 2.159; Edge 70 R$ 3.599; S26+ R$ 5.999 (Amazon).",
     "No Android sobra dinheiro para câmera melhor; no iPhone se paga pela continuidade.", "Vantagem do Android",
     "Aba Comparativo_Modelos"),
    ("Adaptação da Esdra",
     "Nenhuma.", "Teclado, gestos, compartilhamento e configurações novas (inferência, não medido).",
     "Atendimento mais lento nas primeiras semanas.", "Médio no Android", "Inferência"),
]

FONTES = [
    ("Apple BR: linha atual e preços (17e, 17, Air, 18 Pro, 18 Pro Max)", "https://www.apple.com/br/shop/buy-iphone", SRC_CC),
    ("Samsung BR: S26 Ultra 512 GB R$ 13.099 / 1 TB R$ 15.499; S26+ 512 R$ 6.665; S26 512 R$ 6.443,33", SAMS + "galaxy-s26-ultra-1tb/p", SRC_CC),
    ("Motorola BR: catálogo 512 GB (g86, Edge 60, 60 Neo, 60 Pro, 70, 70 Fusion+, 70 Pro, Signature)", MOTO + "smartphones", SRC_CC),
    ("Motorola Signature: até 7 anos de sistema e segurança (FAQ da página)", MOTO + "smartphone-motorola-signature/p", SRC_CC),
    ("Motorola Edge 70: 4 upgrades e segurança até jul/2031", MOTO + "smartphone-motorola-edge-70-5g-512gb/p", f"{SRC_CC} + {SRC_MD}"),
    ("Motorola Edge 70 Pro: 3 upgrades e 5 anos de segurança", MOTO + "smartphone-motorola-edge-70-pro-5g-512gb/p", SRC_CC),
    ("Samsung S26: 7 anos de sistema e segurança",
     "https://news.samsung.com/br/galaxy-s26-series-entenda-o-que-diferencia-a-linha-premium-da-samsung-e-como-ela-evolui-com-one-ui-galaxy-ai-e-smart-switch", SRC_MD),
    ("WhatsApp: iPhone → Android (Business não suportado)", WA_IOS_ANDROID, f"{SRC_CC} + {SRC_MD}"),
    ("WhatsApp: iPhone → iPhone, transferência direta", WA_IOS_IOS, SRC_CC),
    ("Amazon BR: preços e vendedor de cada anúncio (ASIN na aba Comparativo)", "https://www.amazon.com.br", SRC_CC),
    ("KaBuM: vendedores de Xiaomi/HONOR importados", "https://www.kabum.com.br/busca/poco-x8-pro-512gb", SRC_CC),
    ("OLX: iPhone 14 Plus 128 GB usado, pedidos de R$ 2.000 a R$ 2.900",
     "https://www.olx.com.br/celulares/apple/iphone-14-plus/128gb/usado-excelente", SRC_MD),
    ("Mercado Livre: iPhone 14 Plus 128 GB usado, ~R$ 2.600 a R$ 3.100",
     "https://lista.mercadolivre.com.br/celulares-telefones/celulares-smartphones/usado/iphone-14-plus-128gb-usado", SRC_MD),
    ("Mi Brasil (DL), HONOR BR e Realme Store: links na aba Comparativo", "-", SRC_MD),
]

MODELOS += [
    dict(faixa="Topo de linha", marca="Apple", modelo="iPhone Air", interno="1 TB", tela=V,
         camera="48 MP Fusion (uma câmera traseira)", bateria=V, updates="Apple não publica prazo fixo " + V,
         oficial=15499.00, link_oficial=APPLE + "iphone-air", status="Loja Apple", obs="Uma câmera só.", origem=SRC_CC),
    dict(faixa="Topo de linha", marca="Apple", modelo="iPhone 18 Pro", interno="1 TB", tela="6,3\"",
         camera="Três câmeras de 48 MP", bateria=V, updates="Apple não publica prazo fixo " + V,
         oficial=16499.00, link_oficial=APPLE + "iphone-18-pro", status="Loja Apple",
         obs="Tela pequena para quem vem do Plus.", origem=SRC_CC),
]

# Anuncios vistos: loja, codigo (ASIN/KaBuM ou URL), titulo, interno, preco, vendedor, nota, avaliacoes.
A, K, VV = "Amazon", "KaBuM", V
ANUNCIOS = [
    (A, "B0FCYJ336S", "Motorola Moto g86 5G 512 GB, 8 GB RAM", "512 GB", 2159.10, "Amazon", 4.8, 1717),
    (A, "B0F51KRTX1", "Motorola Edge 60 5G 512 GB", "512 GB", 2279.05, "Mika Eletrônicos", 4.7, 821),
    (A, "B0GVVTTTWT", "Motorola Edge 60 Pro 5G 512 GB", "512 GB", 2934.52, VV, None, None),
    (A, "B0F7J4V7L2", "Motorola Edge 60 Pro 5G 512 GB", "512 GB", 3154.09, "Magalu", 4.7, 238),
    (A, "B0GMY41LM8", "Motorola Edge 70 5G Swarovski 512 GB", "512 GB", 3059.10, VV, 4.7, 154),
    (A, "B0GM1JJD66", "Motorola Edge 70 5G 512 GB", "512 GB", 3599.00, "Amazon", 4.7, 154),
    (A, "B0GM1LC365", "Motorola Edge 70 5G 512 GB", "512 GB", 3599.10, "Amazon", 4.7, 154),
    (A, "B0GMKJDHT9", "Motorola Signature 5G 512 GB", "512 GB", 5263.00, VV, 4.8, 82),
    (A, "B0GMKS98D5", "Motorola Signature 5G 512 GB", "512 GB", 5366.62, "PRIZMO", 4.8, 82),
    (A, "B0GKQJM8QX", "Samsung Galaxy S26+ 512 GB violeta", "512 GB", 5979.90, VV, 4.4, 25),
    (A, "B0GKQYKBQ9", "Samsung Galaxy S26+ 512 GB azul", "512 GB", 5999.01, "Amazon", 4.4, 25),
    (A, "B0GKR1QX37", "Samsung Galaxy S26 512 GB violeta", "512 GB", 6118.38, "Toledo Digital (enviado pela Amazon)", 4.7, 156),
    (A, "B0DSY8CP8H", "Samsung Galaxy S25+ 512 GB", "512 GB", 4654.05, VV, 4.8, 1400),
    (A, "B0FTMV1P7M", "Samsung Galaxy S24 Ultra 512 GB", "512 GB", 4027.05, VV, 3.8, 17),
    (A, "B0GKQP7T39", "Samsung Galaxy S26 Ultra 512 GB violeta", "512 GB", 8739.05, "Toledo Digital (enviado pela Amazon)", 4.8, 165),
    (A, "B0GKQBYWTY", "Samsung Galaxy S26 Ultra 512 GB preto", "512 GB", 9690.33, "Amazon", 4.8, 165),
    (A, "B0HDYNDYCT", "Samsung Galaxy S26 Ultra 512 GB preto + brinde Samsung", "512 GB", 11021.49, VV, None, None),
    (A, "B0GKRBNDNJ", "Samsung Galaxy S26 Ultra 1 TB azul", "1 TB", 12249.00, "Toledo Digital (enviado pela Amazon)", 4.8, 165),
    (A, "B0GKR49YG9", "Samsung Galaxy S26 Ultra 1 TB violeta", "1 TB", 12940.00, VV, 4.8, 165),
    (A, "B0GKQNSB9Z", "Samsung Galaxy S26 Ultra 1 TB preto", "1 TB", 13499.00, VV, 4.8, 165),
    (A, "B0HCWW3VQQ", "Samsung Galaxy Z Fold8 512 GB lavanda", "512 GB", 11285.11, VV, 5.0, 1),
    (A, "B0HCX4G36W", "Samsung Galaxy Z Fold8 512 GB branco", "512 GB", 11501.18, VV, None, None),
    (A, "B0HCX34DQ1", "Samsung Galaxy Z Fold8 Ultra 512 GB preto", "512 GB", 12529.00, VV, None, None),
    (A, "B0HCXGTYF4", "Samsung Galaxy Z Fold8 512 GB preto", "512 GB", 12544.00, VV, 5.0, 1),
    (A, "B0HCX3269F", "Samsung Galaxy Z Fold8 Ultra 512 GB roxo", "512 GB", 13454.09, VV, None, None),
    (A, "B0GTS8LCSB", "Apple iPhone 17e 512 GB preto", "512 GB", 4939.04, "Magalu", 4.8, 188),
    (A, "B0GQW7S1XS", "Apple iPhone 17 512 GB preto", "512 GB", 6173.95, "Magalu", 4.7, 828),
    (A, "B0GQX14HN5", "Apple iPhone 17 512 GB branco", "512 GB", 6173.95, VV, 4.7, 828),
    (A, "B0FQJ2HN63", "Apple iPhone 17 512 GB lavanda", "512 GB", 6173.95, VV, 5.0, 6),
    (A, "B0GQW5WSNJ", "Apple iPhone 17 512 GB lavanda", "512 GB", 6498.90, VV, 4.7, 828),
    (A, "B0FQHRNRYQ", "Apple iPhone Air 512 GB azul-céu", "512 GB", 7254.32, "Amazon", 4.4, 41),
    (A, "B0FQHZ48BN", "Apple iPhone Air 512 GB branco-nuvem", "512 GB", 7356.93, "Amazon", 4.4, 41),
    (A, "B0FQJ7H8HR", "Apple iPhone Air 512 GB preto sideral", "512 GB", 11249.10, VV, 4.4, 41),
    (A, "B0FQHG7GHG", "Apple iPhone 17 Pro 512 GB laranja cósmico", "512 GB", 9114.01, VV, 4.7, 196),
    (A, "B0FQHPRVG5", "Apple iPhone 17 Pro 512 GB azul intenso", "512 GB", 9719.10, VV, 4.7, 196),
    (A, "B0FQH3X8R8", "Apple iPhone 17 Pro Max 512 GB prateado", "512 GB", 9796.76, "Amazon", 4.7, 311),
    (A, "B0FQHCZ6K5", "Apple iPhone 17 Pro Max 512 GB azul intenso", "512 GB", 10739.58, VV, 4.7, 311),
    (A, "B0FQHCTCSQ", "Apple iPhone 17 Pro Max 512 GB laranja cósmico", "512 GB", 11999.99, VV, 4.7, 311),
    (A, "B0FQHGM3B1", "Apple iPhone 17 Pro Max 1 TB laranja cósmico", "1 TB", 13949.10, VV, 5.0, None),
    (A, "B0HJB9YV1F", "Apple iPhone 18 Pro 512 GB preto", "512 GB", 12149.10, VV, 5.0, 8),
    (A, "B006ZARA98", "Apple iPhone 18 Pro 512 GB glacial", "512 GB", 12149.10, VV, 5.0, 8),
    (A, "B0HJ9VQMB1", "Apple iPhone 18 Pro Max 512 GB preto", "512 GB", 13049.10, "Amazon", 4.7, 8),
    (A, "B0HJB895X8", "Apple iPhone 18 Pro Max 512 GB glacial", "512 GB", 13049.10, VV, 4.7, 8),
    (A, "B0HJ9XV4MC", "Apple iPhone 18 Pro Max 512 GB prateado", "512 GB", 13049.10, VV, 4.7, 8),
    (A, "B0GQD3W1R4", "Xiaomi Redmi Note 15 Pro 5G 512 GB, 8 GB RAM preto", "512 GB", 2123.25, "Power Dealls", 4.7, 288),
    (A, "B0G2BHH8SR", "Xiaomi Redmi Note 15 Pro 5G 512 GB azul", "512 GB", 2042.37, VV, 4.5, 2),
    (A, "B0GP8FM414", "Xiaomi Redmi Note 15 Pro 5G 512 GB roxo", "512 GB", 2071.68, VV, 4.7, 211),
    (A, "B0H2WRYZYJ", "Xiaomi Redmi Note 15 Pro 5G 512 GB titânio", "512 GB", 2127.05, VV, 4.2, 13),
    (A, "B0GCP3DFVJ", "Xiaomi Redmi Note 15 Pro 5G (anúncio “Xiaomi Original”)", "512 GB", 2210.73, VV, 4.5, 52),
    (A, "B0H6WRY4NJ", "Xiaomi Redmi Note 17 Pro 5G 512 GB (anúncio em espanhol)", "512 GB", 2849.05, VV, None, None),
    (A, "B0H6X46KRK", "Xiaomi Redmi Note 17 Pro Max 5G 512 GB (anúncio em espanhol)", "512 GB", 3419.05, VV, None, None),
    (A, "B0DRD1SBSD", "Xiaomi POCO X7 Pro 5G 512 GB", "512 GB", 2260.05, VV, 4.8, 3000),
    (A, "B0H1NS1XQD", "Xiaomi POCO X8 Pro 512 GB, 8 GB RAM verde", "512 GB", 2555.50, VV, 5.0, 11),
    (A, "B0GN1TCVYX", "Xiaomi POCO X8 Pro 512 GB, 8 GB RAM preto", "512 GB", 2574.50, "BRASIL-VENDAS", 4.7, 328),
    (A, "B0GN1MW5MB", "Xiaomi POCO X8 Pro 512 GB, 12 GB RAM verde", "512 GB", 2579.25, "Power Dealls", 4.8, 105),
    (A, "B0GR9HXPCF", "Xiaomi POCO X8 Pro 512 GB, 12 GB RAM branco", "512 GB", 2607.70, VV, 4.7, 16),
    (A, "B0GR9QPJV4", "Xiaomi POCO X8 Pro 512 GB, 12 GB RAM preto “global”", "512 GB", 2622.00, VV, 4.6, 59),
    (A, "B0GN21MPS8", "Xiaomi POCO X8 Pro 512 GB, 8 GB RAM branco", "512 GB", 2660.00, VV, 4.7, 144),
    (A, "B0FDKNBCQ8", "Huawei Pura 80 Pro 512 GB", "512 GB", 3719.34, VV, 4.6, 42),
    (A, "B0FDKQZBXK", "Huawei Pura 80 Pro 512 GB", "512 GB", 3989.05, VV, 4.6, 42),
    (A, "B0GVRZ5S8Z", "Huawei Mate 80 Pro 512 GB", "512 GB", 5689.82, VV, 5.0, 2),
    (K, "1022458", "Xiaomi Redmi Note 15 Pro 4G 512 GB, 12 GB RAM", "512 GB", 2099.00, "NOVA ERA", None, None),
    (K, "1033555", "Xiaomi Redmi Note 15 Pro 512 GB, 12 GB RAM (global)", "512 GB", 2150.00, "CELCOMERCE", 5.0, 1),
    (K, "1033551", "Xiaomi Redmi Note 15 Pro 5G 512 GB, 8 GB RAM roxo", "512 GB", 2229.00, "NOVA ERA", None, None),
    (K, "1000114", "Xiaomi Redmi Note 15 Pro 5G 512 GB, 8 GB RAM preto (global)", "512 GB", 2249.00, "CELCOMERCE", 5.0, 1),
    (K, "1000115", "Xiaomi Redmi Note 15 Pro 5G 512 GB, 8 GB RAM azul", "512 GB", 2350.00, "CELCOMERCE", None, None),
    (K, "1022462", "Xiaomi Redmi Note 15 Pro 5G 512 GB, 12 GB RAM", "512 GB", 2699.00, "NOVA ERA", None, None),
    (K, "1003252", "Xiaomi Redmi Note 15 Pro+ 5G 512 GB, 12 GB RAM", "512 GB", 2789.00, "CELCOMERCE", None, None),
    (K, "1031459", "Xiaomi Redmi Note 15 Pro+ 5G global 512 GB, 12 GB RAM", "512 GB", 2899.00, "NOVA ERA", None, None),
    (K, "1074113", "Xiaomi Redmi Note 17 Pro Max 5G 512 GB, 8 GB RAM", "512 GB", 4289.90, "TUDOSMART", None, None),
    (K, "1048606", "Xiaomi POCO X8 Pro 512 GB, 12 GB RAM branco", "512 GB", 2696.00, "MAGA'ABUR", 5.0, 1),
    (K, "1017195", "Xiaomi POCO X8 Pro 512 GB, 8 GB RAM preto (global)", "512 GB", 2699.00, "CELCOMERCE", 5.0, 1),
    (K, "1017196", "Xiaomi POCO X8 Pro 512 GB, 8 GB RAM branco (global)", "512 GB", 2699.00, "CELCOMERCE", 3.7, 4),
    (K, "1017193", "Xiaomi POCO X8 Pro 512 GB, 8 GB RAM mint (global)", "512 GB", 2699.00, "CELCOMERCE", 5.0, 1),
    (K, "1031522", "Xiaomi POCO X8 Pro 512 GB, 12 GB RAM branco (global)", "512 GB", 2899.00, "CELCOMERCE", None, None),
    (K, "1031523", "Xiaomi POCO X8 Pro 512 GB, 12 GB RAM preto (global)", "512 GB", 2899.00, "CELCOMERCE", None, None),
    (K, "1031307", "Xiaomi POCO X8 Pro NFC 512 GB, 12 GB RAM", "512 GB", 2950.00, "CELLSTORE", None, None),
    (K, "1017191", "Xiaomi POCO X8 Pro Max 512 GB, 12 GB RAM (global)", "512 GB", 3499.00, "CELCOMERCE", 5.0, 3),
    (K, "1019997", "Xiaomi POCO F8 Pro 5G global 512 GB, 12 GB RAM", "512 GB", 3799.00, "CELLSTORE", 3.0, 1),
    (K, "1019971", "Xiaomi POCO F8 Pro NFC 512 GB, 12 GB RAM", "512 GB", 3999.00, "NOVA ERA", None, None),
    (K, "999618", "Xiaomi POCO F8 Pro 512 GB, 12 GB RAM (global)", "512 GB", 4299.00, "CELCOMERCE", None, None),
    (K, "1019973", "Xiaomi POCO F8 Ultra 512 GB, 16 GB RAM", "512 GB", 5599.00, "NOVA ERA", None, None),
    (K, "1053422", "Xiaomi 17T 512 GB preto (global)", "512 GB", 3999.00, "CELCOMERCE", None, None),
    (K, "1053421", "Xiaomi 17T 512 GB violeta (global)", "512 GB", 3999.00, "CELCOMERCE", None, None),
    (K, "1053424", "Xiaomi 17T Pro 512 GB (global)", "512 GB", 5499.00, "CELCOMERCE", None, None),
    (K, "1032252", "Xiaomi 17 512 GB preto (global)", "512 GB", 5799.00, "CELCOMERCE", None, None),
    (K, "1031507", "Xiaomi 17 512 GB azul (global)", "512 GB", 5799.00, "CELCOMERCE", None, None),
    (K, "1031462", "Xiaomi 17 global 512 GB azul", "512 GB", 5899.00, "NOVA ERA", None, None),
    (K, "1031463", "Xiaomi 17 global 512 GB preto", "512 GB", 5899.00, "NOVA ERA", 5.0, 1),
    (K, "942089", "Realme 15 Pro 5G 512 GB", "512 GB", 3999.00, "LOGIN INFORMATICA", None, None),
    (K, "907138", "HONOR Magic7 Lite 5G 512 GB", "512 GB", 4599.99, "Honor Oficial", None, None),
    (K, "1062062", "HONOR Magic8 Pro 512 GB global", "512 GB", 12799.00, "Infotecdez importados USA", None, None),
    (K, "907139", "HONOR Magic V3 512 GB (dobrável)", "512 GB", 19999.99, "Honor Oficial", None, None),
    (K, "422449", "Samsung Galaxy S23 Ultra 512 GB", "512 GB", 5561.90, "SHOPNEXT", None, None),
    (K, "520331", "Samsung Galaxy S24 Ultra 512 GB", "512 GB", 7109.10, "Magalu", 5.0, 1),
    (K, "1029920", "Samsung Galaxy S26 Ultra 512 GB preto", "512 GB", 7999.00, "NOVA ERA", None, None),
    (K, "1007564", "Samsung Galaxy S26 Ultra 512 GB violeta", "512 GB", 11789.10, "Magalu", None, None),
    ("Motorola", MOTO + "kit-smartphone-motorola-edge-70-5g-512gb-e-fone-moto-buds-loop/p",
     "Kit Edge 70 512 GB + fone Moto Buds Loop", "512 GB", 4399.00, "Motorola", None, None),
    ("Motorola", MOTO + "kit-smartphone-motorola-edge-70-5g-512gb-e-fone-moto-buds-loop-swarovski-champagne/p",
     "Kit Edge 70 Swarovski 512 GB + fone Moto Buds Loop", "512 GB", 4599.00, "Motorola", None, None),
    ("Motorola", MOTO + "kit-motorola-edge-60-512gb-moto-buds-plus-moto-tag/p",
     "Kit Edge 60 512 GB + Moto Buds+ + Moto Tag (sem estoque)", "512 GB", 2799.00, "Motorola", None, None),
    ("Motorola", MOTO + "smartphone-motorola-edge-50-5g-512gb/p", "Edge 50 5G 512 GB (sem estoque)", "512 GB", 2699.00,
     "Motorola", None, None),
    ("Motorola", MOTO + "smartphone-moto-g86-512-gb/p", "Moto g86 512 GB, 8 GB RAM (sem estoque)", "512 GB", 2099.00,
     "Motorola", None, None),
    ("Samsung", SAMS + "galaxy-s26-ultra-1tb/p", "Galaxy S26 Ultra 1 TB (preço “de” R$ 16.799)", "1 TB", 15499.00,
     "Samsung", None, None),
    ("Apple", APPLE + "iphone-18-pro", "iPhone 18 Pro 2 TB", "2 TB", 20999.00, "Apple", None, None),
    ("Apple", APPLE + "iphone-18-pro", "iPhone 18 Pro Max 2 TB", "2 TB", 21999.00, "Apple", None, None),
]

BRIEFING = [
    ("Situação atual", "Aparelho", "iPhone 14 Plus 128 GB, iOS 26.5.2, 3 GB livres."),
    ("Situação atual", "WhatsApp Business", "41 GB de mídia: catálogos e revistas de ciclo em PDF (200 a 340 MB cada) e vídeos das marcas."),
    ("Situação atual", "iCloud", "Fotos com “Otimizar Armazenamento”. Backup do WhatsApp falha por falta de espaço desde dez/2025."),
    ("Obrigatório", "Armazenamento", "512 GB ou 1 TB internos. microSD não conta: o WhatsApp guarda na memória interna."),
    ("Obrigatório", "Câmera", "Boa para foto e vídeo de produto: close, luz interna, nitidez. Megapixel sozinho não prova."),
    ("Obrigatório", "Bateria", "Dia inteiro com WhatsApp aberto. mAh e horas de vídeo não são teste de uso real."),
    ("Obrigatório", "Garantia", "Garantia e assistência oficiais no Brasil, homologação Anatel. Nada de importado sem garantia local."),
    ("Obrigatório", "Atualizações", "Prazo de sistema e segurança publicado pelo fabricante."),
    ("Desejável", "Tela", "6,7\" ou próximo, como o Plus atual [aguarda resposta]."),
    ("Desejável", "Migração", "Levar conversas, mídia, catálogo e etiquetas do Business sem perda."),
    ("Desejável", "Usado", "Aproveitar o 14 Plus na troca ou vender."),
    ("Deal-breaker", "Sem garantia nacional", "Mercado cinza / importado sem assistência local."),
    ("Deal-breaker", "Menos de 512 GB", "Não resolve o gargalo."),
    ("Deal-breaker", "Perda dos dados de trabalho", "Só apagar ou vender o antigo depois de conferir tudo no novo."),
    ("Acessório", "Capa e película", "Recomendado; compatível com o SKU exato, protegendo bordas e câmera. Compra junto."),
    ("Acessório", "Carregador", "Recomendado se não vier na caixa; potência e protocolo do modelo escolhido [VERIFICAR]."),
    ("Acessório", "Cabo de migração", "Lightning ↔ USB-C se necessário; a transferência do WhatsApp é por Wi-Fi."),
    ("Acessório", "microSD", "Dispensável."),
    ("Valor do usado", "iPhone 14 Plus 128 GB", "Pedidos na OLX de R$ 2.000 a R$ 2.900; Mercado Livre ~R$ 2.600 a R$ 3.100. "
     "Inferência para venda particular: R$ 2.400 a R$ 2.800. Troca na loja: simular [VERIFICAR]."),
    ("Pergunta pendente", "Orçamento", "Qual o valor máximo?"),
    ("Pergunta pendente", "Sistema", "A Esdra aceita Android sabendo que o histórico do WhatsApp Business não passa?"),
    ("Pergunta pendente", "Tela", "Faz questão de 6,7\" ou mais, ou aceita 6,1\" a 6,3\"?"),
    ("Pergunta pendente", "Prazo e pagamento", "Quando comprar; Pix à vista ou parcelado (Samsung: 18x sem juros)."),
    ("Regra", "Compra", "Nada vai para o carrinho sem confirmação do Josemar."),
]

# ---------------------------------------------------------------- estilo
AZUL = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
CAB = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
TXT = Font(name="Segoe UI", size=10)
LINK = Font(name="Segoe UI", size=10, color="0563C1", underline="single")
NOTA = Font(name="Segoe UI", size=10, italic=True, color="595959")
BORDA = Border(*(Side(style="thin", color="D9D9D9"),) * 4)
CORES = {"Custo-benefício": "E2EFDA", "Intermediário forte": "DDEBF7", "Topo de linha": "FFF2CC"}
MOEDA = 'R$ #,##0.00'
QUEBRA = Alignment(horizontal="left", vertical="top", wrap_text=True)


def cabecalho(ws, linha, titulos, larguras):
    for col, (titulo, largura) in enumerate(zip(titulos, larguras), start=1):
        c = ws.cell(row=linha, column=col, value=titulo)
        c.fill, c.font, c.border = AZUL, CAB, BORDA
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(col)].width = largura
    ws.freeze_panes = ws.cell(row=linha + 1, column=1)


def nota(ws, texto):
    ws.cell(row=1, column=1, value=texto).font = NOTA


def celula(ws, linha, col, valor, cor=None, moeda=False, link=False, rotulo="abrir"):
    # Celula com mais de um link (" ; "): o hiperlink vai no primeiro, o texto mostra todos.
    url = valor.split(" ; ")[0] if link and isinstance(valor, str) and valor.startswith("http") else None
    c = ws.cell(row=linha, column=col, value=(rotulo or valor) if url else valor)
    c.border, c.alignment = BORDA, QUEBRA
    c.font = LINK if url else TXT
    if url:
        c.hyperlink = url
    if moeda:
        c.number_format = MOEDA
    if cor:
        c.fill = PatternFill(start_color=cor, end_color=cor, fill_type="solid")
    return c


wb = openpyxl.Workbook()

def referencia(m):
    """Menor preco entre loja oficial e varejo direto; sem eles, o do marketplace (marcado)."""
    precos = [p for p in (m.get("oficial"), m.get("varejo")) if p]
    if precos:
        return min(precos), ("loja oficial" if min(precos) == m.get("oficial") else "varejo direto")
    if m.get("terceiro"):
        return m["terceiro"], "marketplace (não confirmado)"
    return None, ""


def canal(m):
    if m.get("canal"):
        return m["canal"]
    return "Sim (loja oficial)" if m.get("oficial") else "Varejo nacional"


ORDEM_FAIXA = {"Custo-benefício": 0, "Intermediário forte": 1, "Topo de linha": 2}
MODELOS.sort(key=lambda m: (ORDEM_FAIXA[m["faixa"]], referencia(m)[0] or 10**6))

# Aba 1: comparativo
ws = wb.active
ws.title = "Comparativo_Modelos"
nota(ws, f"Consulta em {DATA}. Preço é observação web, sem CEP, frete ou cupom: não fecha compra. "
         "Use o filtro da coluna “Garantia nacional” para esconder importados. [VERIFICAR] = sem fonte nesta rodada.")
COLS = [("Faixa", 16), ("Marca", 11), ("Modelo", 24), ("Interno", 9), ("Garantia nacional / canal", 22),
        ("Tela", 18), ("Câmeras traseiras", 30), ("Bateria", 20), ("Atualizações prometidas", 26),
        ("Preço de referência", 14), ("Base do preço", 14), ("Preço loja oficial", 14), ("Link oficial", 8),
        ("Varejo direto", 14), ("Vendido por", 18), ("Link varejo", 8), ("Marketplace terceiro", 14),
        ("Vendedor terceiro", 18), ("Link terceiro", 8), ("Status / estoque", 20),
        ("Observações para o trabalho da Esdra", 40), ("Origem do dado", 20)]
cabecalho(ws, 2, [c for c, _ in COLS], [w for _, w in COLS])
CINZA = "EDEDED"
for i, m in enumerate(MODELOS, start=3):
    ref, base = referencia(m)
    cor = CINZA if canal(m).startswith("Não") else CORES[m["faixa"]]
    vals = [m["faixa"], m["marca"], m["modelo"], m["interno"], canal(m), m["tela"], m["camera"], m["bateria"],
            m["updates"], ref, base, m.get("oficial"), m.get("link_oficial"), m.get("varejo"), m.get("vend_varejo"),
            m.get("link_varejo"), m.get("terceiro"), m.get("vend_terceiro"), m.get("link_terceiro"), m["status"],
            m["obs"], m["origem"]]
    for col, v in enumerate(vals, start=1):
        celula(ws, i, col, v, cor=cor, moeda=col in (10, 12, 14, 17), link=col in (13, 16, 19))
    ws.cell(row=i, column=10).font = Font(name="Segoe UI", size=10, bold=True)
ws.auto_filter.ref = f"A2:{get_column_letter(len(COLS))}{len(MODELOS) + 2}"

# Aba 2: iPhone x Android
ws2 = wb.create_sheet("iPhone_vs_Android")
nota(ws2, f"Consulta em {DATA}. Fato com fonte na última coluna; o que é inferência está escrito como tal.")
cabecalho(ws2, 2, ["Ponto", "Ficar no iPhone", "Migrar para Android", "Impacto no trabalho da Esdra", "Risco", "Fonte"],
          [24, 42, 42, 36, 18, 40])
for i, linha in enumerate(MIGRACAO, start=3):
    for col, v in enumerate(linha, start=1):
        celula(ws2, i, col, v, link=col == 6, rotulo=None)

# Aba 3: custo liquido
ws3 = wb.create_sheet("Simulador_Custo_Liquido")
nota(ws3, "Edite as células amarelas. Venda particular: inferência a partir de anúncios OLX/Mercado Livre "
          "(pedido, não preço fechado). Troca na loja: preencher com proposta real.")
amarelo = "FFF2CC"
for linha, rotulo, valor in [(2, "Venda particular estimada do iPhone 14 Plus 128 GB (R$)", 2600),
                             (3, "Proposta de troca na loja (R$) [VERIFICAR: simular Apple/Samsung/Trocafone]", None)]:
    celula(ws3, linha, 1, rotulo)
    celula(ws3, linha, 2, valor, cor=amarelo, moeda=True)
cabecalho(ws3, 5, ["Modelo", "Interno", "Faixa", "Garantia nacional / canal", "Preço de referência", "Base do preço",
                   "Custo líquido vendendo particular", "Custo líquido com troca na loja"],
          [44, 10, 18, 22, 16, 16, 18, 18])
ws3.freeze_panes = "A6"
for i, m in enumerate(MODELOS, start=6):
    ref, base = referencia(m)
    celula(ws3, i, 1, f'{m["marca"]} {m["modelo"]}')
    celula(ws3, i, 2, m["interno"])
    celula(ws3, i, 3, m["faixa"], cor=CORES[m["faixa"]])
    celula(ws3, i, 4, canal(m))
    celula(ws3, i, 5, ref, moeda=True)
    celula(ws3, i, 6, base)
    celula(ws3, i, 7, f"=IF(E{i}=\"\",\"\",E{i}-$B$2)", moeda=True)
    celula(ws3, i, 8, f"=IF(OR(E{i}=\"\",$B$3=\"\"),\"[VERIFICAR]\",E{i}-$B$3)", moeda=True)
ws3.column_dimensions["A"].width = 60
ws3.auto_filter.ref = f"A5:H{len(MODELOS) + 5}"

# Aba 4: todos os anuncios vistos
ws6 = wb.create_sheet("Anuncios_observados")
nota(ws6, f"Todos os anúncios de 512 GB ou mais vistos em {DATA}, inclusive repetidos por cor. "
          "Vendedor “[VERIFICAR]” = a página do anúncio não foi aberta.")
cabecalho(ws6, 2, ["Loja", "Código", "Anúncio", "Interno", "Preço", "Vendido por", "Nota", "Avaliações", "Link"],
          [12, 14, 60, 9, 14, 30, 7, 10, 8])
for i, (loja, cod, titulo, interno, preco, vend, nota_, aval) in enumerate(ANUNCIOS, start=3):
    link = AMZ + cod if loja == "Amazon" else KABUM + cod if loja == "KaBuM" else cod
    for col, v in enumerate([loja, cod if loja in ("Amazon", "KaBuM") else "-", titulo, interno, preco, vend,
                             nota_, aval, link], start=1):
        celula(ws6, i, col, v, moeda=col == 5, link=col == 9)
ws6.auto_filter.ref = f"A2:I{len(ANUNCIOS) + 2}"

# Aba 5: briefing e pendencias
ws7 = wb.create_sheet("Briefing_e_pendencias")
nota(ws7, "Resumo de briefing.md e 01-definir-modelo.md. Fonte da verdade continua nos .md.")
cabecalho(ws7, 2, ["Seção", "Item", "Detalhe"], [22, 40, 80])
for i, linha in enumerate(BRIEFING, start=3):
    for col, v in enumerate(linha, start=1):
        celula(ws7, i, col, v)

# Aba 6: fora da lista
ws4 = wb.create_sheet("Fora_da_lista")
nota(ws4, "Deixados de fora, com o motivo. Inclui as 14 linhas da primeira versão desta planilha.")
cabecalho(ws4, 2, ["Marca", "Modelo", "Preço visto", "Onde", "Por que saiu", "Origem"], [12, 30, 20, 40, 60, 26])
for i, linha in enumerate(FORA, start=3):
    for col, v in enumerate(linha, start=1):
        celula(ws4, i, col, v)

# Aba 7: fontes
ws5 = wb.create_sheet("Fontes_e_Lojas")
nota(ws5, f"Todas as consultas em {DATA}.")
cabecalho(ws5, 2, ["O que a fonte confirma", "Link", "Quem consultou"], [70, 60, 30])
for i, linha in enumerate(FONTES, start=3):
    for col, v in enumerate(linha, start=1):
        celula(ws5, i, col, v, link=col == 2, rotulo=None)

wb.save(DESTINO)
print(f"{DESTINO}: {len(MODELOS)} modelos, {len(ANUNCIOS)} anúncios, {len(FORA)} fora da lista, {len(FONTES)} fontes")
