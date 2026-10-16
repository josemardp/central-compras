# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

Kit de motor para o portao de correr, especificado pelo Fabio: PPA DZ Rio 500 Jetflex (500 kg).

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: casa 127V padrao, 220V disponivel; regiao com tempestade (surto eletrico).
- Perguntas decisivas respondidas: motor PPA 500 kg Jetflex, especificado pelo Fabio; cremalheira de 4 m ou 3 m + 1 m (Josemar, 21/09).
- Decisoes do Josemar (21/09): portao de correr de cerca de 4 x 2 m; ligar em 220V; 3 controles; quer fotocelula, DPS, disjuntor proprio e nobreak das cameras.
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): portao de ferro. Peso estimado (conta da IA, nao medido): 8 m2 x 10-20 kg/m2 (gradil/tubular) = 80-160 kg; 8 m2 x 20-35 kg/m2 (fechado em chapa) = 160-280 kg. Nos dois casos a classe 500 kg fica com folga de quase 2x ou mais [VERIFICAR peso real com o Fabio].

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Modelo | PPA DZ Rio 500 Jetflex | idem, confirmar versao 1/4 ou 1/3 e central Facility ou Full Range [VERIFICAR com Fabio] | e o que o Fabio instala e da manutencao |
| Capacidade | 500 kg | 500 kg basta; a R800 Jetflex (Z14, 800 kg) e aceita se custar igual ou menos | portao 4 x 2 m de ferro ~80-280 kg (estimativa); em 21/09 o kit R800 com 4 m + 3 controles saiu MAIS BARATO que o 500 (R$ 915 x R$ 1.059): mais folga pelo mesmo preco, abre 4 m em 5,3 s |
| Tensao | bivolt 127/220V | bivolt, ligado em 220V | decisao do Josemar (21/09); circuito proprio com disjuntor bipolar e DPS |
| Central | Triflex bivolt com entrada para fotocelula | idem | permite ligar sensor anti-esmagamento |
| Fim de curso | hibrido/magnetico | idem | vem no kit |
| Controles | 3 no total | kit com 3 controles; se vier com 2, comprar 1 PPA compativel | decisao do Josemar (21/09) |
| Cremalheira inclusa | 0 m | 3 m | portao de ~4 m pede 4 m; com 3 m no kit, compra-se so 1 m do mesmo modelo |
| Garantia | nacional | nacional PPA | assistencia facil |
| Velocidade | - | Z14: 33 m/min (~7 s em 4 m); Z18: 42,9 m/min (~5,6 s) (manual tecnico PPA DZ Rio (P08665 REV1)) | o 5,3 s do anuncio nao bate com o manual |
| Dimensao do portao | - | manual: ate 2,5 m altura x 3,0 m comprimento (todos os DZ Rio) | portao ~4 m passa do comprimento do manual [perguntar ao Fabio] |
| Potencia (CV) | classe 500 kg | a que a loja chamar 1/4 ou 1/3 dentro do DZ Rio 500 Jetflex | o que decide e a capacidade em kg, nao o CV do anuncio |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Cremalheira | obrigatorio | 4 m no total; nylon reforcado com alma de aco, gomos M4, padrao residencial compativel com engrenagem Z18 | e onde o motor engrena | projeto: 2026-cremalheira-portao-4m |
| Base regulavel | obrigatorio | aco zincado com regulagem, furacao do DZ Rio | fixa o motor alinhado a cremalheira | projeto: 2026-base-motor-portao-deslizante |
| Fotocelula refletiva | obrigatorio (decisao do Josemar) | PPA F10-R ou compativel com a entrada de fotocelula da Triflex | impede o portao de fechar em cima de pessoa ou carro | projeto: 2026-fotocelula-portao |
| DPS (protetor de surto) | obrigatorio (decisao do Josemar) | ver projeto | central com inversor queima com raio/surto | projeto: 2026-dps-e-disjuntor-motor-portao |
| Disjuntor so do motor | obrigatorio (decisao do Josemar) | bipolar 6 A curva C (manual PPA pede 5 A) | circuito proprio em 220V | projeto: 2026-dps-e-disjuntor-motor-portao |
| Controle extra (se o kit vier com 2) | obrigatorio | PPA 433,92 MHz rolling code, compativel com a Triflex | 3 controles no total | junto com o motor |
| Nobreak de motor | dispensavel | - | falta de luz se resolve com o destravamento manual (chave) | - |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: kit PPA DZ Rio 500 Jetflex bivolt (classe 500 kg), de preferencia com 3 m de cremalheira e 3 controles.
- Alternativas descartadas: outras marcas (Garen, Intelbras, Rossi).
- Motivo: modelo do instalador (manutencao e garantia de instalacao com ele); PPA e marca lider.

## Requisitos gerados

### Obrigatorios

- PPA DZ Rio 500 Jetflex novo, garantia nacional
- Central com entrada para fotocelula

### Desejaveis

- Kit com 3 m de cremalheira
- Controles extras no kit

### Deal-breakers

- Motor sem nota/garantia
- Capacidade abaixo do peso do portao
