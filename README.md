# Radar de Golpes IA

> 🚧 **Projeto em construção.** Este README é atualizado a cada fase. Veja o [status do projeto](#status-do-projeto).

Sistema que recebe um anúncio, uma mensagem ou um print (marketplaces, WhatsApp, SMS, e-mail, redes sociais) e devolve o **risco de ser golpe**, com os sinais explicados e o trecho do conteúdo que comprova cada um.

É uma ferramenta **geral**, sem vínculo com nenhuma empresa. As marcas citadas no código e nos exemplos (bancos, lojas, órgãos públicos, marketplaces) aparecem apenas como **exemplos de domínios oficiais que golpistas costumam imitar**. Todos os casos de exemplo são fictícios.

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

### Testes (sem custo de API)
```bash
pytest -v
```

### Analisar uma mensagem pelo terminal
```bash
python -m radar "URGENTE! Sua conta será bloqueada. Acesse banco-seguranca.top/login"
python -m radar "..." --modelo mock      # só regras, sem IA e sem chave
python -m radar "..." --prompt v1        # escolhe a versão do prompt
```

A saída é um JSON com a análise, os sinais das regras e as medições (latência, tokens, custo e ancoragem). O modelo padrão é o `gemini-3.5-flash-lite` e precisa da `GEMINI_API_KEY` no `.env`.

_Evals, deploy e bot: em construção._

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
| 1 | Regras automáticas (sem IA) + testes | ✅ concluída |
| 2 | Schema de saída e chamada ao LLM | ✅ concluída |
| 3 | Prompts versionados v1 → v3 | ⏳ |
| 4 | Dataset e avaliação | ⏳ |
| 5 | API e página de demo | ⏳ |
| 6 | Deploy na Vercel | ⏳ |
| 7 | Bot do Telegram (n8n) | ⏳ |
| 8 | Documentação final do portfólio | ⏳ |

### Diário

- **Fase 0:** ambiente virtual com Python 3.12, dependências com versão fixa (`==`) para o deploy instalar exatamente o que roda localmente, `.gitignore` protegendo chaves e resultados brutos, e `.env.example` documentando as variáveis.
- **Decisão de custo:** o LLM padrão é o Gemini na camada gratuita, então o projeto inteiro roda sem custo. O código trata o provedor como peça trocável (Gemini, Claude, OpenAI ou só regras), e a avaliação mostra quanto cada modelo custaria no plano pago. O lado ruim é que, na camada grátis, o Google pode usar o conteúdo enviado. Por isso, a demo avisa para não colar dados pessoais.
- **Fase 1: regras automáticas ([`radar/sinais.py`](radar/sinais.py)).** São 14 sinais objetivos, sem IA:
  - 5 de links: encurtador, IP, punycode, final de domínio suspeito e domínio que imita uma marca sem ser o oficial;
  - 9 de texto: pagamento antecipado, pedido de código ou senha, sair da plataforma, urgência ou ameaça, troca de número, ganho fácil, prêmio ou restituição, comprovante ou intermediário falso, e tentativa de manipular a IA.

  Cada sinal traz a **evidência**: o trecho exato do texto original, sem cortar palavras. A regex roda no texto normalizado (minúsculo e sem acento), e um mapa de posições devolve o trecho com a escrita original. São 29 testes com pytest.
  - **Por que regras antes do LLM:** são grátis, instantâneas e explicáveis, e viram o **baseline** que o LLM precisa superar na avaliação.
  - **Por que são pista, e não veredito:** elas não entendem contexto. O SMS legítimo *"Seu código de verificação é 482913. Não compartilhe"* dispara o sinal de "pedido de código". O LLM recebe as pistas e decide lendo o conteúdo inteiro.
  - **Detalhe de segurança de links:** quem manda num endereço é o **final** do domínio. `app.nubank.com.br` é oficial, mas `nubank.com.br.golpe.xyz` não é.
- **Fase 2: contrato de saída e chamada ao LLM.**
  - **Contrato único ([`radar/schema.py`](radar/schema.py)):** um modelo Pydantic define a resposta (nível de risco, pontuação, categoria, sinais com trecho, explicação, recomendação e confiança). Ele vira um JSON Schema estrito, igual para todos os provedores. As descrições dos campos também funcionam como instrução para o modelo.
  - **Provedores trocáveis ([`radar/provedores.py`](radar/provedores.py)):** Gemini (padrão, pelo endpoint compatível com OpenAI), Claude (opcional), OpenAI e um **mock** que responde só com as regras. Todos usam **saída estruturada**: o modelo só consegue responder no formato do schema. O Claude não aceita `minimum`/`maximum` no schema, então a faixa 0–100 é conferida pelo Pydantic depois.
  - **Detector ([`radar/detector.py`](radar/detector.py)):** junta regras, prompt, provedor e validação. Se o JSON vier fora do formato, tenta **mais uma vez**. Se a API falhar, **não** repete (o SDK já repete sozinho) e devolve o erro no resultado, sem derrubar quem chamou.
  - **Medições em toda análise:** latência, tokens (incluindo o raciocínio interno, que é cobrado como saída), custo "se fosse pago" e **ancoragem**: a fração dos trechos citados pelo modelo que existem de verdade no texto. A ancoragem pegou um bug real: o mock estava citando o texto do próprio prompt como se fosse do usuário.
  - **Segurança do prompt ([`radar/prompts.py`](radar/prompts.py)):** o conteúdo do usuário é encaixado numa passada só (quem escreve `{sinais}` na mensagem não injeta nada), a versão do prompt só aceita `v` + número (bloqueia `../../.env`) e todo prompt precisa colocar o conteúdo entre marcações `<conteudo_analisado>`.
  - **Raciocínio "low":** o Gemini 3.x não permite desligar o raciocínio. Como classificar golpe é tarefa curta, uso o esforço baixo: gasta menos cota e responde mais rápido. A comparação com dados fica para os evals.
  - **Partida mais rápida:** o SDK da Anthropic leva alguns segundos para carregar, então só é importado quando um modelo Claude é usado.
  - **Primeira chamada real** (v1 + `gemini-3.5-flash-lite`): risco alto e categoria correta, 1 tentativa, ancoragem 1.0, 80 tokens de entrada e 289 de saída, 2,3 s e US$ 0,0007 se fosse pago. São 113 testes, todos sem chamar API.