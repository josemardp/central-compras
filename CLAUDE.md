# Instruções do repositório — Central de Compras

Vale para qualquer agente que trabalhe aqui (Claude, Codex, Kimi, Antigravity,
Gemini). Curto de propósito: são as regras que, quando ignoradas, já causaram
retrabalho ou estrago real neste repositório.

## 1. Antes de criar qualquer coisa fora do repositório, confira o inventário

Planilha, pasta no Drive, Apps Script, Web App, integração, conta: **leia
[`docs/infraestrutura-externa.md`](docs/infraestrutura-externa.md) primeiro.**

**Ausência de configuração local NÃO prova que a coisa não existe.** Em
04/09/2026, três agentes em sessões separadas concluíram "nunca foi ativado" e
recriaram tudo — enquanto havia uma planilha, um script e um Web App **ativo**
desde 31/08. Havia dois endpoints abertos na internet ao mesmo tempo.

Desde então a configuração é dividida: a **URL** fica versionada em
`config/integracao_sheets.yaml` (ela sozinha não dá acesso) e só o **token**
mora em `~/.central-compras/dados-privados/`. Numa máquina nova, `git pull` +
`configurar-sheets --token ...` basta. Se `sincronizar-planilha` reclamar de
token faltando, é isso — **não é sinal de que a integração não existe**.

Se algo parece não existir, procure nesta ordem antes de concluir: o
inventário, a pasta no Drive, **a lixeira do Drive**, `script.google.com/home/all`,
e dentro da planilha em **Extensões → Apps Script** (script *container-bound*
não aparece em listagem nenhuma quando o arquivo dono está na lixeira).

Mexeu nessa infraestrutura? Atualize o inventário **no mesmo commit**.
Para deploy e validação da planilha, siga também
[`docs/aprendizados-google-sheets.md`](docs/aprendizados-google-sheets.md):
publique pela conta proprietária, preserve a implantação existente e abra a
planilha. HTTP 200, execução “Concluído” e retorno `ok` não validam o visual.

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

<!-- PROJECT-MENTOR:START v1 -->
## Mentor de Projetos (protocolo v1)

Este projeto é acompanhado pelo Mentor de Projetos. Slug: `central-compras`. O estado executivo vive em `.project-mentor/project.yaml` e o histórico em `.project-mentor/sessions/`. **Nunca edite esses arquivos à mão**: toda escrita passa pelo CLI `mentor`.

Como achar o CLI (Windows): `%PROJECT_MENTOR_HOME%\bin\mentor.cmd`. Se a variável `PROJECT_MENTOR_HOME` não existir, procure a pasta `mentor-de-projetos` ao lado deste projeto e use `bin\mentor.cmd` de lá. Se ainda assim não conseguir executar comandos, siga a seção "Sem terminal".

### Início da sessão
1. Peça ao usuário para confirmar que fez `git pull` se ele trocou de computador.
2. Rode `mentor project central-compras --brief` e leia a última sessão em `.project-mentor/sessions/`.
3. Apresente em até 8 linhas: onde paramos, última entrega, pendências, bloqueios, próxima ação. Não invente nada que não esteja no estado.
4. Pergunte o objetivo só se não estiver claro. Depois rode `mentor start central-compras --objective "..." --agent <claude-code|codex|antigravity|copilot>`.

### Durante
- Nunca marque ação como concluída só porque um arquivo foi criado. Distinga **implementado** (código escrito), **testado** (teste executado com resultado) e **validado** (o usuário confirmou). Agente nunca marca "validado".
- Ação nova: `mentor action add central-compras --title "..."`. Concluir: `mentor action done central-compras <act-id> --level implemented|tested`. Bloqueio: `mentor blocker add central-compras --description "..."`.
- Não altere estágio (`mentor stage`) sem o usuário pedir.

### Encerramento
Quando o usuário disser "encerrar", "fechar sessão", "terminei" ou invocar a skill de encerramento:
1. Escreva um rascunho em arquivo temporário (fora do repositório) com as seções: Resumo executivo · Concluído (prefixo `[implementado]`, `[testado]` ou `[validado]`, e `(act-NNN)` no fim quando for ação cadastrada) · Arquivos/áreas alteradas · Testes e resultados · Decisões · Pendências · Bloqueios · Riscos · Próxima ação recomendada. Máximo 60 linhas. Sem raciocínio interno, transcrição, segredos, dados pessoais de terceiros ou conteúdo de documentos policiais.
2. Rode `mentor close central-compras --from <rascunho.md>` e mostre o resultado da validação. Se falhar, mostre o erro e **não** finja sucesso.
3. Avise se há arquivos de `.project-mentor/` a commitar e mostre o comando sugerido pelo CLI. Não execute commit/push sem autorização explícita nesta sessão.

### Sem terminal
Se você não puder executar comandos, gere o rascunho da sessão em `.project-mentor/pending-close.md` no formato do protocolo (mesmas seções acima, com frontmatter `agent:` e `objective:`) e peça ao usuário para rodar `mentor sync`. O `sync` importa o rascunho, grava a sessão e atualiza o estado; se o rascunho for inválido, nada é descartado e o erro aparece para correção.
<!-- PROJECT-MENTOR:END -->
