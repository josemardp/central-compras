# Definir modelo

Use este arquivo para transformar uma vontade vaga em requisitos comparaveis.
Aqui a IA atua como especialista tecnico: le `config/perfil.yaml` (o que eu ja
tenho e como uso) e o guia da categoria em `base-conhecimento/especificacoes/`,
propoe a especificacao para o MEU contexto e pergunta so o que muda a escolha.

## Pedido original

Registrar demanda informada pelo comprador: 1 frasco de Rivotril 2,5 mg. Apresentação completa, volume, prescrição aplicável e preço ainda não verificados.

## Perguntas boas antes de cotar

- Qual problema exato essa compra resolve?
- Existe uma categoria/modelo mais adequada do que a primeira ideia?
- O que precisa ser obrigatorio?
- O que seria apenas bom ter?
- O que faria a compra ser arrependimento?
- Qual e o preco teto real?

## Contexto aplicado

- Do perfil (equipamento, local, uso) o que pesa nesta compra: não se aplica. A compra deve corresponder estritamente à prescrição vigente.
- Perguntas decisivas respondidas: pedido informado como 1 frasco de Rivotril 2,5 mg.
- Suposicoes adotadas (sem resposta minha, a IA propos o padrao): a rotulagem consultada na Anvisa identifica Rivotril como clonazepam 2,5 mg/mL, solução oral em gotas, conteúdo de 20 mL. Confirmar se esta é exatamente a apresentação prescrita antes de cotar.

## Especificacao tecnica para o meu contexto

| Atributo | Minimo aceitavel | Ideal | Por que, no meu contexto |
|---|---|---|---|
| Apresentação | Rivotril, clonazepam, solução oral em gotas, 2,5 mg/mL | A mesma apresentação | Corresponde à apresentação de referência identificada na Anvisa; não substituir por comprimidos ou outra concentração. |
| Conteúdo | 1 frasco de 20 mL | 1 frasco de 20 mL | É o conteúdo indicado na rotulagem consultada; confirmar contra a prescrição. |
| Prescrição | Receita válida compatível com o medicamento e a apresentação | Receita válida compatível | Medicamento sujeito a prescrição; a dispensação depende da conferência da farmácia. |

## Acessorios

Necessidade: obrigatorio (sem ele o produto nao funciona no meu uso),
recomendado (protege ou melhora de forma relevante) ou dispensavel (marketing
ou redundante com o que ja tenho). Compra: `junto` (mesmo carrinho) ou
`projeto` (vale comparar preco: `novo-projeto ... --acessorio-de <este projeto>`).

| Acessorio | Necessidade | Especificacao tecnica | Por que | Compra |
|---|---|---|---|---|
| Nenhum | dispensavel | Não aplicável | Não há acessório a comprar. | - |

## Decisao de modelo

- Tipo/modelo escolhido para pesquisar: Rivotril gotas, clonazepam 2,5 mg/mL, frasco de 20 mL.
- Alternativas descartadas: comprimidos, concentrações diferentes e substituições por outro medicamento.
- Motivo: a compra deve reproduzir exatamente a apresentação prescrita; alterações exigem avaliação do prescritor ou farmacêutico.

## Requisitos gerados

### Obrigatorios

- Rivotril (clonazepam) solução oral em gotas 2,5 mg/mL, frasco de 20 mL.
- Uma unidade.
- Receita válida e compatível, conferida no ato da dispensação.

### Desejaveis

- 

### Deal-breakers

- Apresentação, concentração, volume ou medicamento diferente do prescrito.
- Ausência de receita válida ou recusa de dispensação pela farmácia.
