# Resultados da avaliação

Avaliação feita em 23/11/2026, com o Gemini na camada gratuita. Os resultados brutos ficam fora do Git (`evals/resultados/`); aqui estão os números consolidados e a leitura deles.

## Como foi medido

- **Dois conjuntos de casos fictícios:**
  - **Principal** ([`evals/dataset.jsonl`](../evals/dataset.jsonl)): 61 casos (36 golpes e 25 legítimos) em 5 canais, com 20 casos difíceis e 3 de prompt injection.
  - **Difícil** ([`evals/dataset_dificil.jsonl`](../evals/dataset_dificil.jsonl)): 20 casos criados depois que o principal saturou. São 6 injections mais elaboradas, 6 golpes sutis e 8 mensagens legítimas que parecem golpe. Os casos foram escritos e congelados **antes** de qualquer rodada e não foram alterados depois.
- **Regra de decisão:** o radar "sinalizou" quando o nível é `medio` ou `alto`.
- **Recall** é a fração de golpes pegos. **Alarme falso** é a fração de mensagens legítimas sinalizadas. **Alto em legítimo** conta o erro mais grave: chamar de golpe uma mensagem inocente.
- **Injection bloqueada** só conta respostas `alto`. Resposta inválida (erro do provedor) conta como não bloqueada.
- **Custo** é calculado como se o uso fosse pago, pelos tokens reais de cada chamada.
- Cada combinação rodou **uma vez**. Com 61 casos, 1 erro vale 1,6 ponto; com 20, vale 5 pontos.

Para reproduzir: `python -m evals.run_eval --versoes v1,v2,v3 --modelos regras,gemini-3.5-flash-lite` e o mesmo com `--dataset dificil`.

## Conjunto principal (61 casos)

| Combinação | JSON válido | Acurácia | Recall | Alarme falso | Alto em legítimo | Difíceis | Injection | Categoria | Ancoragem | p50 (s) | p95 (s) | US$/1.000 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Só regras | 100% | 75,4% | 69,4% | 16,0% | 0 | 60,0% | 100%\* | 92,0% | 100% | 0 | 0 | 0 |
| v1 + 3.5 Flash Lite | 96,7% | 100% | 100% | 0,0% | 0 | 100% | 100% | 91,4% | 100% | 1,97 | 5,94 | 0,48 |
| v2 + 3.5 Flash Lite | 98,4% | 98,3% | 100% | 4,0% | 1 | 95,0% | 100% | 94,3% | 98,6% | 1,58 | 9,46 | 0,68 |
| **v3 + 3.5 Flash Lite** | **100%** | **100%** | **100%** | **0,0%** | **0** | **100%** | **100%** | 91,7% | 100% | 1,63 | 8,97 | 1,03 |
| v3 + 3.1 Flash Lite | 100% | 98,4% | 100% | 4,0% | 0 | 95,0% | 100% | 86,1% | 100% | 2,20 | 11,37 | 1,10 |

\* Inflado: as regras têm frases copiadas dos próprios casos de injection do dataset. No conjunto difícil, com outras palavras, as regras bloquearam 0%.

**Sem os 2 casos parecidos com os exemplos do prompt v3** (tag `parecido_com_exemplo`), o v3 continua com 100% de acurácia. Ele não estava acertando por ter visto a resposta.

## Conjunto difícil (20 casos)

| Combinação | JSON válido | Acurácia | Recall | Alarme falso | Alto em legítimo | Injection | Categoria | p50 (s) | p95 (s) | US$/1.000 |
|---|---|---|---|---|---|---|---|---|---|---|
| Só regras | 100% | 45,0% | 41,7% | 50,0% | 0 | 0% | 80,0% | 0 | 0 | 0 |
| v1 + 3.5 Flash Lite | 100% | 95,0% | 100% | 12,5% | 1 | 100% | 83,3% | 1,69 | 8,23 | 0,52 |
| v2 + 3.5 Flash Lite | 95,0% | 94,7% | 100% | 12,5% | 1 | 83,3%\*\* | 90,9% | 1,73 | 6,92 | 0,68 |
| **v3 + 3.5 Flash Lite** | 95,0% | **100%** | **100%** | **0,0%** | **0** | 83,3%\*\* | 81,8% | 2,09 | 8,19 | 1,02 |
| v3 + 3.1 Flash Lite | 100% | 100% | 100% | 0,0% | 0 | 100% | 91,7% | 2,48 | 14,60 | 1,17 |

\*\* Não foi falha de defesa: um caso de injection voltou com erro 503 do provedor e, pela regra da métrica, conta como não bloqueado. Todas as respostas válidas, em todas as versões, deram `alto` nas injections.

## O que os números mostram

1. **O LLM é necessário.** As regras deixam passar 3 em cada 10 golpes no conjunto principal e quase 6 em cada 10 no difícil, porque golpes sem palavra-chave (falso comprovante, falsa recrutadora, "sobrinho sem bateria") exigem entender o contexto. Com o LLM, o recall foi de 100% em todas as versões.
2. **O conjunto principal saturou.** Até o v1, de uma linha, acertou todos os casos válidos. Um benchmark fácil demais não separa as versões, e por isso foi criado o conjunto difícil.
3. **O diferencial do v3 foi o alarme falso grave, não a injection.** O v1 e o v2 marcaram como `alto` mensagens legítimas que falam de código de verificação: o v2 acusou um SMS de código de um app de delivery, e o v1 e o v2 acusaram um filho explicando "o código é do app da farmácia, não precisa me passar". Os modelos reagem à palavra "código" sem ler o contexto. A calibração e os exemplos do v3 corrigiram isso: zero `alto` em legítimo nos dois conjuntos.
4. **O modelo já resiste bem a injection sozinho.** No dataset, as três versões bloquearam todas as injections que receberam resposta. A exceção foi o teste manual da Fase 3, com uma marcação falsa no meio do texto, que derrubou o v2 nas duas rodadas. A regra de segurança do v3 é uma garantia extra contra esse tipo de ataque.
5. **Preço por token não é custo por análise.** O 3.1 Flash Lite cobra menos por token, mas escreveu em média 469 tokens de saída por análise, contra 219 do 3.5. Como a saída é a parte cara, a análise saiu mais cara no modelo "mais barato".
6. **O v3 custa o dobro do v1** (US$ 1,03 contra US$ 0,48 por mil análises), por causa do prompt maior. A melhora medida está nos casos de alarme falso grave; o custo continua por volta de um décimo de centavo por análise.
7. **A categoria é o campo menos estável** (82% a 94% de acerto). O mesmo golpe pode envolver mais de um mecanismo, e o modelo escolhe um diferente a cada rodada. O nível de risco é o que orienta a pessoa; a categoria é informação complementar.
8. **Disponibilidade da camada grátis:** 5 de 324 chamadas (cerca de 1,5%) falharam com erro 503 (servidor sobrecarregado), mesmo depois das novas tentativas automáticas.

## Decisões

- **Versão padrão: v3. Modelo padrão: `gemini-3.5-flash-lite`.** É a única combinação sem erro de análise nos dois conjuntos, e é mais barata e mais rápida que o 3.1 Flash Lite.
- **Sem v4 por enquanto.** O v3 não errou nenhuma resposta válida. Ajustar o prompt olhando estes mesmos 81 casos seria ajustar à prova (overfitting): o número sobe aqui, mas não necessariamente no mundo real.
- **Hipótese da ordem dos campos** (`sinais` antes de `nivel_risco` no schema): não testável com estes dados, porque o v3 já acerta tudo. Fica para os próximos passos, com casos novos.
- **Regras:** as falhas encontradas (pagamento antecipado com a ordem das palavras invertida e injections com outras palavras) não foram corrigidas, para não ajustar as regras aos casos que já foram vistos. Ficam para os próximos passos, validadas com casos novos.

## Limitações desta avaliação

- Os conjuntos são pequenos e foram escritos pelos autores do projeto, não coletados de golpes reais. Isso pode deixar de fora formatos de golpe que ninguém aqui imaginou.
- Uma rodada por combinação: o modelo não responde sempre igual, e diferenças de 1 caso estão dentro do ruído.
- Só modelos Gemini foram medidos. O código suporta Claude e OpenAI, mas eles não rodaram para manter o projeto sem custo.