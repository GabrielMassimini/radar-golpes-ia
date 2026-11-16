# Radar de Golpes IA

> 🚧 **Projeto em construção.** Este README é atualizado a cada fase. Veja o [status do projeto](#status-do-projeto).

Sistema que recebe um anúncio, uma mensagem ou um print (marketplaces, WhatsApp, SMS, e-mail, redes sociais) e devolve o **risco de ser golpe**, com os sinais explicados e o trecho do conteúdo que comprova cada um.

<!-- Link da demo, link do bot e GIF entram aqui na Fase 8 -->

## O problema

Golpes digitais seguem padrões conhecidos, mas chegam bem escritos e com pressa. Regras fixas geram alarme falso, e um chatbot genérico não explica de forma verificável por que algo é suspeito.

## Como funciona

Fluxo planejado:

1. **Regras automáticas (sem IA):** encontram sinais objetivos, como link encurtado, domínio que imita uma marca ou pedido de pagamento antecipado.
2. **Prompt versionado:** as pistas das regras e o conteúdo vão para um prompt versionado (v1 → v3).
3. **LLM com saída estruturada:** o modelo devolve um JSON com formato fixo (nível de risco, pontuação, categoria, sinais com trecho, explicação e recomendação).
4. **Validação:** o JSON é validado com Pydantic. Se vier inválido, o sistema tenta mais uma vez.
5. **Canais:** uma página de demo e um bot no Telegram (n8n). Os dois chamam a mesma API.

<!-- Diagrama Mermaid entra na Fase 8 -->

## Decisões

_Em construção._

## Prompts

_Em construção (Fase 3)._

## Como rodar

### Requisitos
- Python 3.12
- Git

### Ambiente local (Windows, Git Bash)
```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env   # depois preencha as chaves no .env
```

No PowerShell, a ativação é `.\.venv\Scripts\Activate.ps1`. No Mac/Linux, `source .venv/bin/activate`.

_Testes, evals, deploy e bot: em construção._

## Métricas

_Em construção (Fase 4)._

## Limitações e riscos

_Em construção._

## Uso de IA

Projeto desenvolvido por mim com o Claude Code como parceiro de programação, que me guiou na estrutura do código, nos prompts, na avaliação e na documentação. As decisões e a análise dos resultados são minhas.

## Próximos passos

_Em construção._

## Status do projeto

| Fase | O que entrega | Status |
|---|---|---|
| 0 | Preparação: ambiente, dependências, Git | ✅ concluída |
| 1 | Regras automáticas (sem IA) + testes | ⏳ |
| 2 | Schema de saída e chamada ao LLM | ⏳ |
| 3 | Prompts versionados v1 → v3 | ⏳ |
| 4 | Dataset e avaliação | ⏳ |
| 5 | API e página de demo | ⏳ |
| 6 | Deploy na Vercel | ⏳ |
| 7 | Bot do Telegram (n8n) | ⏳ |
| 8 | Documentação final do portfólio | ⏳ |

### Diário

- **Fase 0:** ambiente virtual com Python 3.12, dependências com versão fixa (`==`) para o deploy instalar exatamente o que roda localmente, `.gitignore` protegendo chaves e resultados brutos, e `.env.example` documentando as variáveis.
- **Decisão de custo:** o LLM padrão é o Gemini na camada gratuita, então o projeto inteiro roda sem custo. O código trata o provedor como peça trocável (Gemini, Claude, OpenAI ou só regras), e a avaliação mostra quanto cada modelo custaria no plano pago. O lado ruim é que, na camada grátis, o Google pode usar o conteúdo enviado. Por isso, a demo avisa para não colar dados pessoais.
