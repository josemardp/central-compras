# 15-A. Anexo: simulação completa da política de prioridade (21/11/2026)

Saída integral de `python -m radar simular-prioridade` com o **histórico real de preços lido** (banco temporário, WhatsApp falso, nada enviado, relógio simulado). Ofertas: as documentadas e as reais reencenadas do corpus. Rótulos: ENVIADA, ADIADA, SUBSTITUIDA, RETIDA (limite/orçamento, NÃO entregue) e DESCARTADA.

```text
== SIMULACAO DA POLITICA DE PRIORIDADE | historico REAL (lido) | alertas simulados, NADA enviado

[S1] Tres ofertas importantes surgem ao mesmo tempo  =>  OK
   esperado: no maximo 2 por varredura; a 3a espera a vaga ou e substituida, nunca some sem estado final
   mensagens que sairiam: 3 | estados finais: {'enviado': 3}
     10:00 k800_pro_127v            R$ 959.00  candidato criado (pontuacao 83)
     10:00 dreame_f10              R$ 1102.00  candidato criado (pontuacao 90)
     10:00 philco_18k              R$ 2099.01  candidato criado (pontuacao 87)
     10:00 dreame_f10              R$ 1102.00  ENVIADA: orcamento:comum
     10:00 philco_18k              R$ 2099.01  ENVIADA: orcamento:comum
     10:10 k800_pro_127v            R$ 959.00  ENVIADA: orcamento:comum

[S2] Oferta excepcional aparece depois de esgotado o orcamento comum (limite 2) e com 1 vaga de excecao  =>  OK
   esperado: a excepcional usa a excecao; a seguinte, sem excecao, fica RETIDA com motivo e entra na lista de retidas (nao some)
   mensagens que sairiam: 3 | estados finais: {'enviado': 3, 'retida_orcamento': 1}
     08:00 agratto_12k             R$ 1800.00  candidato criado (pontuacao 54)
     08:00 agratto_12k             R$ 1800.00  ENVIADA: orcamento:comum
     09:00 midea_lite_12k          R$ 1930.00  candidato criado (pontuacao 56)
     09:00 midea_lite_12k          R$ 1930.00  RETIDA (orcamento/vaga, NAO entregue): pontuacao 56 abaixo do limiar do momento (65; 1 de 2 vagas comuns ja usadas hoje): reserva vaga para oferta mel
     10:00 k800_pro_127v            R$ 959.00  candidato criado (pontuacao 83)
     10:00 k800_pro_127v            R$ 959.00  ENVIADA: orcamento:comum
     10:10 dreame_f10              R$ 1102.00  candidato criado (pontuacao 90)
     10:10 dreame_f10              R$ 1102.00  ENVIADA: orcamento:excecao
   RETIDA: midea_lite_12k R$ 1930.00 pontuacao 56 abaixo do limiar do momento (65; 1 de 2 vagas comuns ja usadas hoje): reserva vaga para oferta melhor; oferta NAO entregue

[S3] Dreame F10 recebe reducoes sucessivas (R$ 1.100, 1.080, 1.060, 1.000, 940)  =>  OK
   esperado: repete so com melhora de 5% sobre o ultimo alerta; as reducoes pequenas ficam descartadas com motivo
   mensagens que sairiam: 3 | estados finais: {'enviado': 3, 'suprimido_repeticao': 2}
     10:00 dreame_f10              R$ 1100.00  candidato criado (pontuacao 90)
     10:00 dreame_f10              R$ 1100.00  ENVIADA: orcamento:comum
     10:10 dreame_f10              R$ 1080.00  candidato criado (pontuacao 82)
     10:10 dreame_f10              R$ 1080.00  DESCARTADA (repeticao): repeticao: alerta deste produto ha menos de 90 min sem melhora de 5%
     10:20 dreame_f10              R$ 1060.00  candidato criado (pontuacao 82)
     10:20 dreame_f10              R$ 1060.00  DESCARTADA (repeticao): repeticao: alerta deste produto ha menos de 90 min sem melhora de 5%
     10:30 dreame_f10              R$ 1000.00  candidato criado (pontuacao 82)
     10:30 dreame_f10              R$ 1000.00  ENVIADA: orcamento:comum
     10:40 dreame_f10               R$ 940.00  candidato criado (pontuacao 74)
     10:40 dreame_f10               R$ 940.00  ENVIADA: orcamento:comum

[S4] O mesmo cupom e oferta aparece em Promobit, Gatry e Pelando no mesmo ciclo  =>  OK
   esperado: 1 SO notificacao; as copias dos outros canais ficam registradas como substituidas pela melhor do mesmo produto
   mensagens que sairiam: 1 | estados finais: {'enviado': 1, 'substituido': 2}
     10:00 k800_pro_127v            R$ 959.00  candidato criado (pontuacao 83)
     10:00 k800_pro_127v            R$ 959.00  candidato criado (pontuacao 83)
     10:00 k800_pro_127v            R$ 959.00  candidato criado (pontuacao 83)
     10:00 k800_pro_127v            R$ 959.00  SUBSTITUIDA: melhor oferta do mesmo produto neste despacho (pontuacao 83 contra 83)
     10:00 k800_pro_127v            R$ 959.00  SUBSTITUIDA: melhor oferta do mesmo produto neste despacho (pontuacao 83 contra 83)
     10:00 k800_pro_127v            R$ 959.00  ENVIADA: orcamento:comum
     10:10 k800_pro_127v            R$ 959.00  candidato criado (pontuacao 75)
     10:10 k800_pro_127v            R$ 959.00  DESCARTADA (repeticao): repeticao: alerta deste produto ha menos de 90 min sem melhora de 5%

[S5] A promocao que esperava vaga acaba antes do envio  =>  OK
   esperado: revalida na fonte, ve que acabou e NAO envia (nunca apresenta oferta encerrada como ativa)
   mensagens que sairiam: 1 | estados finais: {'enviado': 1, 'expirado': 1}
     10:00 k800_pro_127v            R$ 959.00  candidato criado (pontuacao 83)
     10:00 dreame_f10              R$ 1102.00  candidato criado (pontuacao 90)
     10:00 dreame_f10              R$ 1102.00  ENVIADA: orcamento:comum
     10:10 k800_pro_127v            R$ 959.00  DESCARTADA (expirou): revalidacao antes de entregar: oferta encerrada na fonte (status FINISHED)

[S6] Oferta fica esperando vaga (1 por varredura, validade de 15 min)  =>  OK
   esperado: quem espera e enviado no ciclo seguinte, substituido por outra melhor ou fica RETIDO com motivo; nenhum candidato fica pendente para sempre
   mensagens que sairiam: 2 | estados finais: {'enviado': 2, 'retida_orcamento': 1}
     10:00 k800_pro_127v            R$ 959.00  candidato criado (pontuacao 83)
     10:00 dreame_f10              R$ 1102.00  candidato criado (pontuacao 90)
     10:00 philco_18k              R$ 2099.01  candidato criado (pontuacao 87)
     10:00 dreame_f10              R$ 1102.00  ENVIADA: orcamento:comum
     10:10 philco_18k              R$ 2099.01  ENVIADA: orcamento:comum
   RETIDA: k800_pro_127v  venceu aguardando vaga (limite por varredura); oferta NAO entregue

[S7] WhatsApp indisponivel no envio  =>  OK
   esperado: alerta guardado na fila; entregue ao voltar dentro de 30 min; descartado se vencido
   mensagens que sairiam: 1 | estados finais: {'falha_envio': 2}
     10:00 k800_pro_127v            R$ 959.00  candidato criado (pontuacao 83)
     10:00 k800_pro_127v            R$ 959.00  FALHA NO WHATSAPP (guardada na fila): orcamento:comum | WhatsApp indisponivel (simulado)
     10:12 k800_pro_127v                    -  WhatsApp voltou: 1 entregue(s) da fila (revalidada na fonte)
     13:00 dreame_f10              R$ 1102.00  candidato criado (pontuacao 90)
     13:00 dreame_f10              R$ 1102.00  FALHA NO WHATSAPP (guardada na fila): orcamento:comum | WhatsApp indisponivel (simulado)
     13:50 dreame_f10                       -  WhatsApp voltou 50 min depois: alerta vencido e nao revalidado e DESCARTADO (nao entrega oferta velha)

[S8] Dia cheio: 24 ofertas reais reencenadas, 1 a cada 10 min  =>  OK
   esperado: respeita 6 comuns + excecoes, nada fica pendente, e tudo que o orcamento reteve aparece em `retidas`
   mensagens que sairiam: 6 | estados finais: {'enviado': 6, 'nao_selecionado': 7, 'retida_orcamento': 4, 'suprimido_repeticao': 3}
     07:00 dreame_f10              R$ 1102.00  candidato criado (pontuacao 90)
     07:00 dreame_f10              R$ 1102.00  ENVIADA: orcamento:comum
     07:10 dreame_f10              R$ 1136.50  candidato criado (pontuacao 82)
     07:10 dreame_f10              R$ 1136.50  DESCARTADA (repeticao): repeticao: alerta deste produto ha menos de 90 min sem melhora de 5%
     07:20 k800_pro_127v           R$ 1079.00  DESCARTADA no portao: classe MEDIA nao gera alerta urgente
     07:30 k800_pro_127v            R$ 959.00  candidato criado (pontuacao 83)
     07:30 k800_pro_127v            R$ 959.00  ENVIADA: orcamento:comum
     07:40 elgin_12k               R$ 1610.00  DESCARTADA no portao: classe MEDIA nao gera alerta urgente
     07:50 elgin_12k               R$ 1799.00  candidato criado (pontuacao 48)
     07:50 elgin_12k               R$ 1799.00  RETIDA (orcamento/vaga, NAO entregue): pontuacao 48 abaixo do limiar do momento (50; 2 de 6 vagas comuns ja usadas hoje): reserva vaga para oferta mel
     08:00 elgin_12k               R$ 1895.00  DESCARTADA no portao: classe BAIXA nao gera alerta urgente
     08:10 philco_18k              R$ 2248.00  candidato criado (pontuacao 77)
     08:10 philco_18k              R$ 2248.00  ENVIADA: orcamento:comum
     08:20 philco_18k              R$ 2099.01  candidato criado (pontuacao 79)
     08:20 philco_18k              R$ 2099.01  ENVIADA: orcamento:comum
     08:30 philco_18k              R$ 2299.00  candidato criado (pontuacao 56)
     08:30 philco_18k              R$ 2299.00  DESCARTADA (repeticao): repeticao: alerta deste produto ha menos de 90 min sem melhora de 5%
     08:40 loren_shower_6800_220v    R$ 87.16  candidato criado (pontuacao 81)
     08:40 loren_shower_6800_220v    R$ 87.16  ENVIADA: orcamento:comum
     08:50 loren_shower_6800_220v    R$ 76.49  candidato criado (pontuacao 73)
     08:50 loren_shower_6800_220v    R$ 76.49  ENVIADA: orcamento:comum
     09:00 loren_shower_6800_220v    R$ 79.00  candidato criado (pontuacao 65)
     09:00 loren_shower_6800_220v    R$ 79.00  DESCARTADA (repeticao): repeticao: alerta deste produto ha menos de 90 min sem melhora de 5%
     09:10 k800_pro_127v           R$ 1199.99  candidato criado (pontuacao 22)
     09:10 k800_pro_127v           R$ 1199.99  DESCARTADA (pontuacao baixa): pontuacao 22 abaixo do minimo 40
     09:20 tapo_rv20_max            R$ 854.05  candidato criado (pontuacao 30)
     09:20 tapo_rv20_max            R$ 854.05  DESCARTADA (pontuacao baixa): pontuacao 30 abaixo do minimo 40
     09:30 xiaomi_s40c             R$ 1165.83  candidato criado (pontuacao 30)
     09:30 xiaomi_s40c             R$ 1165.83  DESCARTADA (pontuacao baixa): pontuacao 30 abaixo do minimo 40
     09:40 agratto_12k             R$ 1871.19  candidato criado (pontuacao 45)
     09:40 agratto_12k             R$ 1871.19  RETIDA (orcamento/vaga, NAO entregue): orcamento diario esgotado (6) e pontuacao 45 abaixo da excecao 80: oferta NAO entregue
     09:50 midea_lite_12k          R$ 2022.48  candidato criado (pontuacao 45)
     09:50 midea_lite_12k          R$ 2022.48  RETIDA (orcamento/vaga, NAO entregue): orcamento diario esgotado (6) e pontuacao 45 abaixo da excecao 80: oferta NAO entregue
     10:00 midea_ecomaster_12k     R$ 2304.90  DESCARTADA no portao: classe BAIXA nao gera alerta urgente
     10:10 elgin_18k               R$ 2727.35  candidato criado (pontuacao 34)
     10:10 elgin_18k               R$ 2727.35  DESCARTADA (pontuacao baixa): pontuacao 34 abaixo do minimo 40
     10:20 philco_18k              R$ 2569.00  candidato criado (pontuacao 29)
     10:20 philco_18k              R$ 2569.00  DESCARTADA (pontuacao baixa): pontuacao 29 abaixo do minimo 40
     10:30 elgin_12k               R$ 1799.90  candidato criado (pontuacao 53)
     10:30 elgin_12k               R$ 1799.90  RETIDA (orcamento/vaga, NAO entregue): orcamento diario esgotado (6) e pontuacao 53 abaixo da excecao 80: oferta NAO entregue
     10:40 loren_shower_6800_220v   R$ 111.89  candidato criado (pontuacao 38)
     10:40 loren_shower_6800_220v   R$ 111.89  DESCARTADA (pontuacao baixa): pontuacao 38 abaixo do minimo 40
     10:50 dreame_f10              R$ 1994.05  candidato criado (pontuacao 37)
     10:50 dreame_f10              R$ 1994.05  DESCARTADA (pontuacao baixa): pontuacao 37 abaixo do minimo 40
   RETIDA: elgin_12k R$ 1799.90 orcamento diario esgotado (6) e pontuacao 53 abaixo da excecao 80: oferta NAO entregue
   RETIDA: elgin_12k R$ 1799.00 pontuacao 48 abaixo do limiar do momento (50; 2 de 6 vagas comuns ja usadas hoje): reserva vaga para oferta melhor; oferta NAO entregue
   RETIDA: agratto_12k R$ 1871.19 orcamento diario esgotado (6) e pontuacao 45 abaixo da excecao 80: oferta NAO entregue
   RETIDA: midea_lite_12k R$ 2022.48 orcamento diario esgotado (6) e pontuacao 45 abaixo da excecao 80: oferta NAO entregue

TODAS AS SITUACOES COMO ESPERADO (8/8)
```

