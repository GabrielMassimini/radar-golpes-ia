# Backlog

Coisas combinadas para fazer depois, com a fase em que entram.

## Pendentes

- [ ] **Fases 3 e 4: projeto neutro, sem cara de uma empresa só** (testes da Fase 1 já diversificados). Nos exemplos dos prompts (v2/v3) e no dataset, variar as marcas e usar termos genéricos ("marketplace", "loja", "banco") quando a marca não for essencial. A especificação original repete muito uma mesma plataforma de classificados, e a ideia é diversificar sem perder os padrões de golpe.

- [ ] **Fase 3:** revisar o texto do `prompts/v1` (criado na Fase 2 só para o fluxo rodar) e mudar `VERSAO_PADRAO` de `v1` para `v3` em `radar/prompts.py`.
- [ ] **Fase 3 (prompt injection):** se o conteúdo trouxer `</conteudo_analisado>`, ele pode "fechar" a marcação e fingir que o resto é instrução. Neutralizar essas marcações dentro do conteúdo antes de montar a mensagem e testar isso.

- [x] **Fase 2:** provedor Gemini (camada gratuita) pelo endpoint compatível com OpenAI. Confirmar o modelo padrão olhando os limites grátis no AI Studio e se o endpoint aceita `response_format` com JSON Schema estrito. O Claude fica como provedor opcional.
- [ ] **Fase 4:** evals respeitando o limite da camada grátis: pouco paralelismo e pausa automática no erro 429. A coluna de custo mostra quanto custaria no plano pago. Limites do `gemini-3.5-flash-lite` no free tier (18/11/2026): **15 RPM, 250K TPM, 500 RPD**, contados por projeto do Google. Ritmo seguro: 1 chamada a cada ~5 s. Conta: versões de prompt × exemplos do dataset precisa caber em 500 por dia.
- [ ] **Fase 4 (decisão da Fase 2):** medir a **coerência** entre `nivel_risco` e `pontuacao` (ex.: "alto" com 65) como métrica, em vez de bloquear a resposta no schema.
- [ ] **Fase 4 (hipótese da Fase 2):** testar se colocar `sinais` **antes** de `nivel_risco` no schema melhora a análise (o modelo lista as provas antes de decidir). Comparar com dados, não achismo.
- [ ] **Fase 5:** aviso na página de demo: "Não cole dados pessoais. O texto é processado por um serviço de IA gratuito (Google Gemini)". Na camada grátis, o Google pode usar o conteúdo para melhorar os produtos dele.
- [ ] **Fase 8:** em `docs/limitacoes-e-riscos.md`, explicar o trade-off de privacidade da camada grátis e como mudaria em produção (plano pago, sem uso dos dados para treino).
- [x] **Fase 2:** conferir a API do `anthropic` 2.x e do `openai` 3.x (a especificação original previa versões mais antigas) e se o parâmetro `temperature` ainda é aceito.
  - Claude (conferido na documentação, nov/2026): "tool use forçado" (`tool_choice` do tipo `tool`) dá erro 400 no Sonnet 5.5 e no Opus 5.5. Usar saída estruturada nativa (`output_config.format` com JSON Schema). `temperature` dá erro 400 nos modelos atuais: não enviar.
  - `openai` 3.51 e endpoint do Gemini conferidos (18/11/2026): `response_format` json_schema strict aceito; o schema usa só recursos suportados (enum, minimum/maximum, required, additionalProperties). Raciocínio do Gemini 3.x não desliga → `reasoning_effort="low"`.
- [ ] **Fase 5:** página de demo sem fonte Inter, sem degradê roxo, sem ícone em quadradinho acima de cada título, contraste mínimo de 4,5 e respeito a `prefers-reduced-motion`.
- [ ] **Fase 6:** confirmar que a Vercel roda Python 3.12.
- [ ] **Fase 8 (próximos passos do README):** WhatsApp, botão de feedback "acertou/errou" que vira caso novo no dataset, planilha de métricas sem dados pessoais, consulta de preço de mercado (ex.: tabela FIPE) como ferramenta do agente e cascata de modelos (Haiku → Sonnet quando a confiança for baixa).

## Feitos

_(vazio)_