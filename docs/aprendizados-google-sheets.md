# Aprendizados permanentes — Google Sheets e Apps Script

Registro consolidado depois da implantação da planilha premium em 05/09/2026.
Use junto de [`infraestrutura-externa.md`](infraestrutura-externa.md), que informa
o que está no ar, e de [`integracao-google-sheets.md`](integracao-google-sheets.md),
que contém o código implantável. Este arquivo explica **como não repetir os
erros já observados**.

## Regras de infraestrutura e deploy

1. **Configuração local ausente não significa infraestrutura ausente.** Antes
   de criar planilha, projeto ou Web App, confira o inventário, a pasta e a
   lixeira do Drive, `script.google.com/home/all` e scripts vinculados a
   arquivos. Script *container-bound* pode desaparecer das listagens quando o
   arquivo dono vai para a lixeira.
2. **Implante pela conta proprietária `conta-comercial@exemplo.com`.** Compartilhar o
   projeto com outro editor permite editar, mas não transforma esse editor no
   proprietário nem preserva automaticamente o acesso do Web App à pasta do
   Drive. A Versão 5 publicada por outra conta perdeu acesso à pasta.
3. **“Executar como eu” é relativo à conta que está publicando.** Antes de
   confirmar, verifique a conta Google ativa pelo avatar e pelo e-mail exibido
   na tela de implantação. O nome do perfil do navegador, sozinho, não prova a
   conta usada.
4. **Atualize a implantação existente com “Nova versão”.** Isso preserva o ID
   e a URL `/exec`. Criar outra implantação exige atualizar a URL versionada e
   pode deixar endpoints antigos ativos na internet.
5. **Código salvo não é código implantado.** Alterar o bloco `Code.gs` na
   documentação muda apenas o repositório. O estado externo só muda depois de
   salvar o projeto Apps Script e publicar uma nova versão.
6. **Nunca copie o token para o Git, logs, screenshots ou mensagens.** A URL
   fica em `config/integracao_sheets.yaml`; o token fica apenas no Apps Script
   e em `~/.central-compras/dados-privados/integracao_sheets.json`.

## Regras do contrato de dados

1. **Python e Apps Script evoluem de forma independente.** O receptor precisa
   aceitar o payload antigo antes de o emissor depender do formato novo. A
   ordem de deploy deixa de ser crítica quando campos novos são aditivos e há
   fallback explícito para os campos antigos.
2. **Campo desconhecido gera aviso, não falha total.** Rejeitar o payload
   inteiro torna qualquer evolução incompatível; ignorar em silêncio repete o
   bug de `comp.colunas`. O retorno JSON e a aba devem tornar o descarte
   observável.
3. **Tipo visual acompanha o significado.** Use formato de texto apenas em
   atributos textuais. Preço, score, nota e medidas devem continuar numéricos
   para ordenar, somar e gerar gráficos. Datas falsas em texto não podem virar
   datas da planilha por coerção automática.
4. **A planilha é espelho descartável.** A fonte é o `cotacoes.csv` de cada
   projeto. Corrigir célula manualmente não resolve: a próxima sincronização
   usa `clear()` e reescreve a aba.
5. **Mantenha o timeout de 120 segundos.** Oito projetos já levaram cerca de
   47 segundos na versão linha a linha; escrita em lote melhora, mas criação e
   renderização de gráficos ainda podem ultrapassar 30 segundos.
6. **Payload legado não pode fabricar `NaN`.** Se métricas novas estiverem
   ausentes, o receptor deve usar `situacao` e os campos antigos para produzir
   um texto honesto como “score indisponível neste payload”, sem calcular
   diferenças inexistentes.
7. **Decisão fechada tem precedência sobre envelhecimento.** Um projeto com
   escolha registrada não volta para “vencido” só porque as cotações antigas
   expiraram. KPIs, fila de atenção e gráficos devem excluir decisões fechadas
   das pendências operacionais.

## Regras de layout e gráficos

1. **Célula mesclada não pode ser atravessada pelo congelamento.** Congelar a
   coluna A enquanto títulos ou rodapés estão mesclados entre A e outras
   colunas causa erro em tempo de execução. A Versão 8 usa colunas congeladas
   igual a zero e congela apenas as linhas úteis.
2. **Fonte de gráfico deve ser uma tabela contígua e orientada como o gráfico
   espera.** Adicionar intervalos horizontais separados e depois transpor
   produziu gráficos vazios e rótulos misturados sem derrubar a sincronização.
   A solução é montar blocos auxiliares contíguos fora da área visível.
3. **Recriação precisa ser idempotente.** Remova gráficos e filtros antigos,
   limpe a aba e reaplique dados e formatação em lote. Rodar duas vezes deve
   manter a mesma quantidade de abas e gráficos.
4. **Fórmula depende do locale; gráfico nativo não.** Em `pt-BR`, separadores
   de fórmula e de matriz diferem do inglês. Para visuais, prefira
   `EmbeddedChartBuilder` ou cubra fórmulas localizadas com teste explícito.
5. **Sem dado não é zero.** Eixos ausentes ficam fora do gráfico ou são
   identificados como “sem dado”; zero mudaria o sentido da comparação.
6. **Cabeçalho dinâmico não deve virar área congelada.** A fila de atenção
   muda de tamanho. Congelar até o cabeçalho da tabela faria quase toda a tela
   ficar imóvel em projetos numerosos; a `Visao Geral` congela apenas as três
   linhas estáveis do topo.

## Validação da Versão 9 em 05/09/2026

- A implantação existente foi atualizada como `conta-comercial@exemplo.com`, sem criar
  outro endpoint e sem alterar a URL `/exec`.
- Duas sincronizações consecutivas devolveram 8 projetos e 8 comparativos.
- A planilha real ficou com 9 abas. Não apareceram `#REF!`, `#ERROR!`, `NaN`
  ou `undefined` nos blocos de dados inspecionados.
- Foram conferidos a `Visao Geral`, o gráfico de pendências, o empate técnico
  entre Huawei Band 9 e Galaxy Fit3, o ranking, os cinco eixos e um projeto com
  muitos candidatos. A leitura estreita confirmou três linhas congeladas na
  visão geral e seis nas abas de projeto, sem congelar a fila dinâmica.

## O que “sucesso” realmente prova

- HTTP 200 prova apenas que houve resposta HTTP.
- Execução “Concluído” no painel do Apps Script também pode conter erro de
  negócio: `doPost` captura exceções e devolve `{ok: false, detalhe: ...}`.
- `Planilha sincronizada: ...` comprova que o cliente recebeu `ok: true` e as
  contagens esperadas. Ainda não comprova layout, rótulos ou gráficos.
- Só a planilha aberta comprova o resultado visual. Confira as nove abas, dados
  contra o repositório, tipos numéricos, filtros, links, células mescladas e os
  gráficos renderizados. Quando o editor estiver instável, a prévia da planilha
  pode ajudar a contar objetos e inspecionar blocos de fonte, mas não substitui
  a conferência final no arquivo real.

## Checklist de uma mudança completa

1. Leia `docs/infraestrutura-externa.md` e confirme conta, projeto e implantação.
2. Preserve compatibilidade entre payload antigo e novo.
3. Atualize o bloco versionado em `docs/integracao-google-sheets.md`.
4. Faça o redeploy da implantação existente pela conta proprietária.
5. Rode `sincronizar-planilha` com timeout de 120 segundos e leia `detalhe` se
   `ok` for falso.
6. Rode a sincronização uma segunda vez e confira que não surgiram abas,
   filtros ou gráficos duplicados.
7. Abra a planilha e confira conteúdo **e aparência**, não apenas a resposta do
   terminal.
8. Rode `python -m unittest discover -s tests` sem pipe. O resumo sai em
   `stderr`; capture o código de saída separadamente.
9. Rode `python scripts/central_compras.py checar-segredos --strict`.
10. Atualize `STATUS.md` e o inventário no mesmo commit, depois faça push da
    `main`.

## Outros cuidados desta máquina

- O perfil do Chrome pode ficar bloqueado por processos antigos de automação.
  Reutilize a sessão aberta e confirme a conta visível antes de agir.
- O Mercado Livre costuma responder 403 ao navegador automatizado. Isso não
  autoriza inventar preço, frete ou estoque; registre “não encontrado” ou faça
  conferência manual na sessão autenticada.
- O repositório usa LF. Em reescritas mecânicas de CSV ou YAML no Windows,
  grave em bytes ou force `newline="\n"` para não transformar o arquivo inteiro.
- `checar-segredos --strict` é gate de commit. Exemplos parecidos com token
  devem usar o marcador permitido `central-compras:exemplo-nao-e-segredo` na
  mesma linha.
