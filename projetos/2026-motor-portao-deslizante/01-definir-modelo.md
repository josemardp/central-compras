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
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): portao abaixo de 500 kg [VERIFICAR com Fabio]; o motor e bivolt, entao 127V ou 220V servem.

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Modelo | PPA DZ Rio 500 Jetflex | idem, confirmar versao 1/4 ou 1/3 e central Facility ou Full Range [VERIFICAR com Fabio] | e o que o Fabio instala e da manutencao |
| Capacidade | 500 kg | 500 kg (existe versao 800 kg) | acima do peso real do portao, com folga |
| Tensao | bivolt 127/220V | bivolt | Fabio pediu 220V; o motor aceita os dois, decidir com ele |
| Central | Triflex bivolt com entrada para fotocelula | idem | permite ligar sensor anti-esmagamento |
| Fim de curso | hibrido/magnetico | idem | vem no kit |
| Controles inclusos | 2 | 2 + extras conforme quem usa | quantas pessoas abrem o portao? [pergunta] |
| Cremalheira inclusa | 0 m | 3 m | com 3 m no kit, compra-se so 1 m do mesmo modelo |
| Garantia | nacional | nacional PPA | assistencia facil |
| Velocidade | - | 3,5 s para 3 m (Jetflex) | rapido; confirmar com o Fabio se regula |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Cremalheira | obrigatorio | 4 m no total; nylon reforcado com alma de aco, gomos M4, padrao residencial compativel com engrenagem Z18 | e onde o motor engrena | projeto: 2026-cremalheira-portao-4m |
| Base regulavel | obrigatorio | aco zincado com regulagem, furacao do DZ Rio | fixa o motor alinhado a cremalheira | projeto: 2026-base-motor-portao-deslizante |
| Fotocelula (par infravermelho) | recomendado (forte) | compativel com a central Triflex PPA | impede o portao de fechar em cima de pessoa ou carro | junto, decisao pendente do Josemar |
| DPS (protetor de surto) | recomendado | classe II, tensao conforme o circuito (127 ou 220V), no quadro [VERIFICAR com Fabio] | central com inversor queima com raio/surto | junto, decisao pendente |
| Disjuntor so do motor | recomendado | conforme orientacao do Fabio | circuito proprio, sem dividir com as cameras | junto, decisao pendente |
| Controles extras | depende | PPA 433,92 MHz rolling code | um por motorista | junto, pendente da resposta |
| Nobreak de motor | dispensavel | - | falta de luz se resolve com o destravamento manual (chave) | - |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: kit PPA DZ Rio 500 Jetflex bivolt, de preferencia com 3 m de cremalheira.
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
