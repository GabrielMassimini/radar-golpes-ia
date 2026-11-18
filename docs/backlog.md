# Backlog

Coisas combinadas para fazer depois, com a fase em que entram.

## Pendentes

- [ ] **Fases 3 e 4: projeto neutro, sem cara de uma empresa só** (testes da Fase 1 já diversificados). Nos exemplos dos prompts (v2/v3) e no dataset, variar as marcas e usar termos genéricos ("marketplace", "loja", "banco") quando a marca não for essencial. A especificação original repete muito uma mesma plataforma de classificados, e a ideia é diversificar sem perder os padrões de golpe.

- [ ] **Fase 2:** provedor Gemini (camada gratuita) pelo endpoint compatível com OpenAI. Confirmar o modelo padrão olhando os limites grátis no AI Studio e se o endpoint aceita `response_format` com JSON Schema estrito. O Claude fica como provedor opcional.
- [ ] **Fase 4:** evals respeitando o limite da camada grátis: pouco paralelismo e pausa automática no erro 429. A coluna de custo mostra quanto custaria no plano pago.
- [ ] **Fase 5:** aviso na página de demo: "Não cole dados pessoais. O texto é processado por um serviço de IA gratuito (Google Gemini)". Na camada grátis, o Google pode usar o conteúdo para melhorar os produtos dele.
- [ ] **Fase 8:** em `docs/limitacoes-e-riscos.md`, explicar o trade-off de privacidade da camada grátis e como mudaria em produção (plano pago, sem uso dos dados para treino).
- [ ] **Fase 2:** conferir a API do `anthropic` 2.x e do `openai` 3.x (a especificação original previa versões mais antigas) e se o parâmetro `temperature` ainda é aceito.
- [ ] **Fase 5:** página de demo sem fonte Inter, sem degradê roxo, sem ícone em quadradinho acima de cada título, contraste mínimo de 4,5 e respeito a `prefers-reduced-motion`.
- [ ] **Fase 6:** confirmar que a Vercel roda Python 3.12.
- [ ] **Fase 8 (próximos passos do README):** WhatsApp, botão de feedback "acertou/errou" que vira caso novo no dataset, planilha de métricas sem dados pessoais, consulta de preço de mercado (ex.: tabela FIPE) como ferramenta do agente e cascata de modelos (Haiku → Sonnet quando a confiança for baixa).

## Feitos

_(vazio)_
