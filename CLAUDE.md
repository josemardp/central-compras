# Instruções do repositório — Central de Compras

Vale para qualquer agente que trabalhe aqui (Claude, Codex, Kimi, Antigravity,
Gemini). Curto de propósito: são as regras que, quando ignoradas, já causaram
retrabalho ou estrago real neste repositório.

## 1. Antes de criar qualquer coisa fora do repositório, confira o inventário

Planilha, pasta no Drive, Apps Script, Web App, integração, conta: **leia
[`docs/infraestrutura-externa.md`](docs/infraestrutura-externa.md) primeiro.**

**Ausência de configuração local NÃO prova que a coisa não existe.** A URL e o
token da integração moram em `~/.central-compras/dados-privados/`, que fica
fora do Git de propósito e **não sincroniza entre máquinas**. Em 04/09/2026,
três agentes em sessões separadas concluíram "nunca foi ativado" e recriaram
tudo — enquanto havia uma planilha, um script e um Web App **ativo** desde
31/08. Havia dois endpoints abertos na internet ao mesmo tempo.

Se algo parece não existir, procure nesta ordem antes de concluir: o
inventário, a pasta no Drive, **a lixeira do Drive**, `script.google.com/home/all`,
e dentro da planilha em **Extensões → Apps Script** (script *container-bound*
não aparece em listagem nenhuma quando o arquivo dono está na lixeira).

Mexeu nessa infraestrutura? Atualize o inventário **no mesmo commit**.

## 2. `cotacoes.csv` é append-only

Cada linha é uma observação datada. Preço confirmado depois vira **linha
nova** com `fonte=manual`, nunca edição da linha `fonte=web` anterior. A série
histórica é a única defesa contra âncora de preço inflada.

Corrigir erro de digitação da própria sessão é aceitável; reescrever histórico
de preço não é.

## 3. Score só compara dentro da mesma compra

O eixo `valor` usa o candidato elegível mais barato **do projeto** como
referência. Misturar categorias diferentes no mesmo projeto (aconteceu com
relógio e pulseira) corrompe o ranking dos dois. Compra diferente, projeto
diferente.

## 4. Nada de segredo, CPF ou endereço na árvore versionada

- Rode `python scripts/central_compras.py checar-segredos --strict` antes de
  commitar. Ele já pegou token de Apps Script vazado em snapshot de navegador.
- Dado pessoal (endereço, CPF, pedido, comprovante) mora em
  `~/.central-compras/dados-privados/`. No repositório, referencie por
  caminho, nunca por cópia.
- `.playwright-mcp/` está no `.gitignore`: os snapshots guardam a página
  inteira, incluindo token e dado das lojas.

## 5. Mudou código? Rode a suíte antes de commitar

```powershell
python -m unittest discover -s tests
```

A suíte é grande e passa dos 2 minutos — rode em segundo plano em vez de
encurtar. Em correção sutil, vale o teste de mutação: desfaça a correção de
propósito e confirme que só o teste-armadilha falha.

## 6. Não afirme o que não foi verificado

Preço, estoque, frete, vendedor e garantia só são "confirmados" com conferência
real registrada na sessão. Sem isso, é estimativa `fonte=web` e não fecha
compra. Vale igual para relatório de outra IA colado aqui: é evidência a
conferir, não fato — o procedimento está em
[`docs/como-conferir-auditoria.md`](docs/como-conferir-auditoria.md).

## 7. Estado do trabalho vive nos docs, não na conversa

O Josemar trabalha de várias máquinas. Ao fechar um bloco: atualize o
`STATUS.md` (o que mudou, o que ficou pendente, **onde** estão as coisas),
commit e push na `main`. Registro sem endereço não permite retomar — foi
exatamente o que falhou em 31/08.
