# Radar de Golpes IA

> 🚧 **Projeto em construção.** Este README é atualizado a cada fase. Veja o [status do projeto](#status-do-projeto).

Sistema que recebe um anúncio, uma mensagem ou um print (marketplaces, WhatsApp, SMS, e-mail, redes sociais) e devolve o **risco de ser golpe**, com os sinais explicados e o trecho do conteúdo que comprova cada um.

É uma ferramenta **geral**, sem vínculo com nenhuma empresa. As marcas citadas no código e nos exemplos (bancos, lojas, órgãos públicos, marketplaces) aparecem apenas como **exemplos de domínios oficiais que golpistas costumam imitar**. Todos os casos de exemplo são fictícios.

**Demo:** [radar-golpes-ia.vercel.app](https://radar-golpes-ia.vercel.app) (limite de 15 análises por hora; não cole dados pessoais).

<!-- Link do bot e GIF entram aqui na Fase 8 -->

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

Os prompts ficam fora do código, em [`prompts/`](prompts/), uma pasta por versão. O schema de saída é o mesmo nas três, então a comparação mede só o efeito da instrução. Hipóteses, mudanças e resultados estão em [`prompts/CHANGELOG.md`](prompts/CHANGELOG.md).

| Versão | Ideia | Resultado nos 3 exemplos de teste |
|---|---|---|
| v1 | Baseline ingênuo: uma linha de instrução | Acertou os 3 |
| v2 | Critérios explícitos e calibração dos níveis | Caiu no prompt injection nas 2 rodadas |
| v3 | Sinais automáticos, regra de segurança, 3 exemplos resolvidos e trecho exato | Acertou os 3 (é a versão padrão) |

São só 3 exemplos: servem para ver o comportamento. A medição de verdade é o dataset da Fase 4.

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

### Comparar versões de prompt
```bash
python -m radar.comparar v1 v2 v3
```

Roda cada versão em 3 exemplos fictícios (golpe óbvio, legítimo com "URGENTE" e prompt injection) e mostra uma tabela. São 9 chamadas, com pausa de 5 s entre elas por causa do limite da camada grátis.

A saída é um JSON com a análise, os sinais das regras e as medições (latência, tokens, custo e ancoragem). O modelo padrão é o `gemini-3.5-flash-lite` e precisa da `GEMINI_API_KEY` no `.env`.

### Avaliação
```bash
python -m evals.run_eval --versoes v3 --modelos regras                               # baseline, sem API
python -m evals.run_eval --versoes v1,v2,v3 --modelos gemini-3.5-flash-lite          # 183 chamadas
python -m evals.run_eval --versoes v3 --modelos gemini-3.5-flash-lite --dataset dificil
```

O script respeita o limite da camada grátis (14 chamadas por minuto, com espera automática no erro 429) e salva o `relatorio.md` em `evals/resultados/<data-hora>/`, fora do Git.

### API e página de demo (local)
```bash
uvicorn api.index:app --reload
```

Abra `http://127.0.0.1:8000` para a página e `http://127.0.0.1:8000/docs` para testar a API.

| Rota | O que faz |
|---|---|
| `GET /api/saude` | Diz se está no ar e qual prompt e modelo usa |
| `POST /api/analisar` | Recebe `{texto, imagem_base64?, imagem_media_type?}` e devolve a análise |

Sem o cabeçalho `X-Radar-Token`, vale o limite de `RADAR_LIMITE_DEMO` análises por hora por IP.

### Deploy (Vercel)
O projeto sobe na Vercel sem build próprio: a Vercel reconhece o FastAPI pela entrada declarada no `pyproject.toml` (`api.index:app`) e serve a pasta `public/` pela CDN.

| Arquivo | Para que serve |
|---|---|
| `pyproject.toml` | Entrada da API e dependências com versão exata (iguais às do `requirements.txt`) |
| `.python-version` | Fixa o Python 3.12 |
| `vercel.json` | Deixa a função rodar até 60 s |
| `.vercelignore` | Deixa evals, testes e docs fora do pacote publicado |

Variáveis de ambiente cadastradas no painel da Vercel: `GEMINI_API_KEY`, `RADAR_TOKEN` e `RADAR_LIMITE_DEMO`. Nenhuma fica no código.

### Bot do Telegram (n8n)
O bot roda num n8n local, ligado por `bash n8n/iniciar-bot.sh`, que abre um túnel HTTPS para o Telegram. Ele aceita texto e print, chama a mesma API da demo com o token e responde em cima da mensagem original. Como ligar, credenciais e cuidados: [`n8n/README.md`](n8n/README.md).

## Métricas

Resultados completos e leitura em [`docs/resultados.md`](docs/resultados.md).

| | Só regras | v1 | v2 | **v3 (padrão)** |
|---|---|---|---|---|
| Recall de golpes (principal / difícil) | 69,4% / 41,7% | 100% / 100% | 100% / 100% | **100% / 100%** |
| Alarme falso (principal / difícil) | 16,0% / 50,0% | 0,0% / 12,5% | 4,0% / 12,5% | **0,0% / 0,0%** |
| Legítimo marcado como "alto" | 0 | 1 | 2 | **0** |
| US$ por 1.000 análises, se fosse pago | 0 | 0,48 | 0,68 | 1,03 |

Modelo: `gemini-3.5-flash-lite`. Conjunto principal com 61 casos fictícios e conjunto difícil com 20, criado quando o principal saturou.

## Limitações e riscos

- Os conjuntos de avaliação são pequenos e fictícios, escritos pelos autores. Cada combinação rodou uma vez.
- Na camada grátis, o Google pode usar o conteúdo enviado. Por isso, a demo avisa para não colar dados pessoais.
- Cerca de 1,5% das chamadas falharam por sobrecarga do provedor (erro 503). Na demo, essa falha aparece como erro 502, e um novo envio costuma funcionar.
- O limite de análises por hora fica na memória de cada instância da Vercel. Com várias instâncias, alguém insistente consegue um pouco mais que 15. O pior caso é a cota grátis do dia acabar, sem cobrança, porque não há cartão cadastrado.
- O bot do Telegram só responde enquanto o computador, o n8n e o túnel estão ligados. A demo na Vercel fica sempre no ar.
- O radar apoia a decisão, não garante nada: um golpe novo, diferente de tudo que foi testado, pode passar.

_Versão completa na Fase 8._

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
| 3 | Prompts versionados v1 → v3 | ✅ concluída |
| 4 | Dataset e avaliação | ✅ concluída |
| 5 | API e página de demo | ✅ concluída |
| 6 | Deploy na Vercel | ✅ concluída |
| 7 | Bot do Telegram (n8n) | ✅ concluída |
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
- **Fase 3: prompts versionados.**
  - **Três versões, uma hipótese cada** ([`prompts/CHANGELOG.md`](prompts/CHANGELOG.md)): v1 ingênuo, v2 com critérios e calibração, v3 com sinais das regras, regra de segurança, 3 exemplos resolvidos e exigência de trecho exato. Cada versão foi escrita e testada uma de cada vez.
  - **O achado:** o v2 **caiu no prompt injection** que o v1 acertava, nas 2 rodadas. A lista de "sinais que sozinhos não indicam golpe" deixou o modelo mais permissivo, e ele obedeceu à "instrução do sistema" escrita dentro do anúncio. Mais instrução não é sempre melhor: o v3 só acertou porque traz uma regra de segurança explícita.
  - **Defesa em duas camadas:** no código, marcações `<conteudo_analisado>` escritas pelo usuário viram `[conteudo_analisado]` e não conseguem "fechar" a marcação real; no prompt, o v3 trata essa tentativa como forte sinal de golpe.
  - **Custo do prompt maior:** a entrada do v3 tem ~1.600 tokens, contra ~100 do v1. Como a saída pesa mais no preço, a análise sai cerca de 1,6 vez mais cara no plano pago (~US$ 0,0011).
  - **Honestidade na comparação:** não troquei os exemplos depois de ver os resultados, e não corrigi as regras que falharam no caso de injection antes da avaliação, para o baseline não ficar artificialmente bom.
  - **Neutralidade:** os exemplos dos prompts usam nomes genéricos ("marketplace", "banco") em vez de marcas reais.
- **Fase 4: dataset e avaliação** ([`docs/resultados.md`](docs/resultados.md)).
  - **Métricas ([`evals/metricas.py`](evals/metricas.py)):** recall de golpes contra alarme falso é o trade-off central. Desconfiar de tudo pega todos os golpes, mas faz a pessoa parar de confiar no radar. Também medi o erro mais grave (legítimo marcado como "alto"), acerto nos casos difíceis, injection bloqueada, categoria, coerência entre nível e pontuação, ancoragem, latência p50/p95 e custo por mil análises.
  - **Execução ([`evals/run_eval.py`](evals/run_eval.py)):** respeita o limite da camada grátis (14 chamadas por minuto, espera de 1 minuto no erro 429) e gera um relatório com a tabela de erros e a explicação do modelo em cada um.
  - **Baseline:** só com regras, 75,4% de acurácia e 69,4% de recall, iguais aos números de referência. Os golpes perdidos não tinham palavra-chave.
  - **O dataset saturou:** até o v1 acertou tudo no conjunto principal. Criei um **conjunto difícil** de 20 casos (injections elaboradas, golpes sutis e legítimos que parecem golpe), congelado antes de rodar. Ali as versões se separaram, e as regras caíram para 45% de acurácia.
  - **Resultado:** o v3 foi a única versão sem erro de análise nos dois conjuntos. O ganho dele foi não acusar mensagens legítimas que falam de código de verificação, erro que o v1 e o v2 cometeram com nível "alto".
  - **Vazamentos tratados:** dois casos do dataset eram quase cópias dos exemplos do v3 e foram marcados e medidos à parte (sem mudança no resultado). O 100% de injection das regras estava inflado por frases copiadas do dataset; no conjunto difícil, ele caiu para 0%.
  - **Modelo mais barato, análise mais cara:** o `gemini-3.1-flash-lite` cobra menos por token, mas escreveu o dobro de tokens de saída e saiu mais caro por análise. O 3.5 continua como padrão.
  - **Sem v4:** o v3 não errou nenhuma resposta válida, e ajustar o prompt olhando os mesmos casos seria overfitting. São 238 testes, todos sem chamar API.
- **Fase 5: API e página de demo.**
  - **API ([`api/index.py`](api/index.py)), em FastAPI:** valida a entrada (texto de até 6.000 caracteres; print em JPEG, PNG, WebP ou GIF de até 3 MB, conferindo os primeiros bytes do arquivo) e devolve erros claros: 400, 401, 413, 429 e 502.
  - **Limite da demo:** 15 análises por hora por IP, numa janela deslizante em memória, contando só pedidos válidos. O n8n usa um token, comparado em tempo constante, e não tem limite. Em serverless esse limite é básico, porque cada instância tem o próprio contador; a proteção real é não ter cartão cadastrado no provedor, então o pior caso é a cota do dia acabar, não um gasto.
  - **Sem CORS, de propósito:** a página é servida pela própria API e o n8n chama de servidor para servidor. Liberar CORS deixaria qualquer site usar a cota pelo navegador dos visitantes.
  - **Privacidade:** o conteúdo só passa pela memória durante a análise, sem gravação nem log. O rodapé avisa que, na camada grátis, o Google pode usar o conteúdo.
  - **Página ([`public/index.html`](public/index.html)):** um arquivo só, sem framework. A mensagem reaparece com **marca-texto** nos trechos citados, numerados e ligados à explicação de cada sinal; em risco baixo, a marcação fica verde e mostra os sinais de segurança. Aceita print anexado ou colado com Ctrl+V, e reduz a imagem no navegador antes de enviar.
  - **Acessibilidade e segurança da página:** fonte *Atkinson Hyperlegible*, feita para leitura fácil; contraste acima de 4,5; foco visível no teclado; animação desligada para quem pede menos movimento; tudo que vem da API entra como texto, nunca como HTML.
- **Fase 6: deploy na Vercel.** A demo está no ar em [radar-golpes-ia.vercel.app](https://radar-golpes-ia.vercel.app), no plano grátis da Vercel (Hobby), sem domínio próprio e sem cartão cadastrado.
  - **Configuração mínima:** conferi na documentação da Vercel que ela reconhece o FastAPI sozinha. Bastou declarar a entrada no `pyproject.toml`, que repete as versões exatas do `requirements.txt`; um teste garante que as duas listas não se separem. O `.python-version` fixa o Python 3.12, o mesmo do ambiente local, e o log do build confirmou essa versão.
  - **Tempo limite:** a função pode rodar por até 60 s. No computador, o SDK espera 30 s e repete até 3 vezes, o que poderia passar desse teto. Na Vercel (que define a variável `VERCEL`), cada chamada espera 20 s e repete só uma vez, então uma chamada ao modelo leva no máximo cerca de 40 s.
  - **IP do visitante:** a Vercel sobrescreve o cabeçalho `X-Forwarded-For`, então ninguém consegue trocar o próprio IP no pedido para escapar do limite da demo.
  - **Segredos:** a chave do Gemini e o token do n8n ficam só nas variáveis de ambiente da Vercel e no `.env` local, que não vai para o Git.
  - **Testes no ar:** token errado devolveu 401. Em 17 pedidos seguidos sem token, o limite devolveu 429 depois da 15ª análise da hora. Com o token, 6 de 6 pedidos responderam em 1,7 a 3,4 s. Na rajada sem token, 2 pedidos falharam com 502 por instabilidade passageira do Gemini; a rodada seguinte não teve falha.
- **Fase 7: bot do Telegram no n8n** ([`n8n/README.md`](n8n/README.md)).
  - **O n8n é só o canal:** ele separa o tipo de mensagem (início, texto, print ou outro), chama a API e formata a resposta. A análise, as regras e o prompt continuam num lugar só, a API, então a demo e o bot dão sempre o mesmo resultado.
  - **Print:** o Telegram não manda a imagem junto com a mensagem, só um código dela. O fluxo baixa o maior tamanho disponível e envia em base64, com a legenda como texto.
  - **Falhas:** o nó da API tenta 2 vezes e, se ainda falhar, o bot pede para mandar de novo. Áudio, figurinha e arquivo recebem uma explicação do que o bot aceita.
  - **Resposta:** usa o HTML do Telegram com os trechos citados escapados, para que um texto com marcação não quebre a mensagem. A resposta vai em cima da mensagem original, sem a assinatura do n8n.
  - **Custo zero:** o n8n roda no meu computador, e um túnel rápido da Cloudflare cria o endereço HTTPS que o Telegram exige, sem conta. O preço é que o bot só responde com o computador ligado, e o endereço muda a cada vez.
  - **Bug achado no teste de religar:** o n8n 2.49 tem um serviço novo de publicação que, ao ligar, mantém o endereço antigo do túnel registrado no Telegram, e o bot parou de responder. Confirmei a causa pelo Telegram (erro 530 no endereço antigo) e lendo o código do n8n. O script desliga esse serviço, e o modo antigo compara o endereço e o atualiza sozinho.
  - **Privacidade:** o n8n guarda cada execução com a mensagem recebida. O script reduz esse prazo de 14 dias para 24 h.
  - **Fluxo versionado:** o fluxo exportado fica em [`n8n/radar-telegram-bot.json`](n8n/radar-telegram-bot.json), sem tokens, sem dados da conversa de teste e desligado. Um teste confere isso, além do endereço da API e do aviso de falha.
  - **Testes no Telegram:** golpe de falso parente (alto, 95), anúncio legítimo de móvel (baixo, 5, com os trechos que indicam segurança), print de cobrança falsa de entrega (alto, 90, trecho transcrito da imagem), áudio (formato não aceito) e resposta com o fluxo publicado depois de religar com um endereço novo. São 271 testes, todos sem chamar API.