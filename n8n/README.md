# Bot do Telegram (n8n)

O bot recebe a mensagem suspeita no Telegram, chama a mesma API da página de demo e responde com o nível de risco, os sinais com o trecho exato e o que fazer. Toda a análise acontece na API. O n8n só cuida do canal.

## Fluxo

[`radar-telegram-bot.json`](radar-telegram-bot.json), exportado do n8n 2.49.7:

```
Telegram Trigger ─▶ Tipo de mensagem
                     ├─ /start ─▶ Boas-vindas
                     ├─ texto ──▶ Preparar texto ─┐
                     ├─ print ──▶ Baixar print ─▶ Preparar print ─┤
                     │                                           ▼
                     │                     Analisar na API (POST /api/analisar + token)
                     │                       ├─ sucesso ─▶ Formatar resposta ─▶ Responder
                     │                       └─ erro ────▶ Aviso de falha
                     └─ outro (áudio, figurinha, arquivo) ─▶ Formato não aceito
```

- **Texto e print usam o mesmo nó de API.** O print vai em base64, e a legenda da foto, se houver, vai como texto.
- **Token no cabeçalho `X-Radar-Token`**, guardado numa credencial do n8n. Com ele, a API não aplica o limite por hora da demo.
- **Falha não fica sem resposta:** o nó da API tenta 2 vezes, com 3 s de espera. Se ainda falhar, o bot pede para mandar de novo.
- **Resposta em HTML do Telegram,** com os trechos citados escapados (`&`, `<`, `>`). Um trecho com `<b>` ou `<a>` aparece como texto e não quebra a mensagem.
- **Sem cópia de dados:** o bot responde em cima da mensagem original e não grava nada fora do n8n. O n8n guarda cada execução, com a mensagem, por 24 h.

## Como ligar

Requisitos: Node.js 24 ou mais novo e o `cloudflared`.

```bash
winget install --id Cloudflare.cloudflared -e --version 2026.11.2
```

Na raiz do projeto, no Git Bash:

```bash
bash n8n/iniciar-bot.sh
```

O script abre um túnel HTTPS público (o Telegram só entrega mensagens assim) e liga um n8n só deste projeto, na porta 5679, com os dados em `~/.n8n-radar-golpes`. Para desligar, aperte Ctrl + C no terminal. O n8n e o túnel fecham juntos.

### Primeira vez

1. Crie o bot no [@BotFather](https://t.me/BotFather) com `/newbot` e guarde o token no `.env` (`TELEGRAM_BOT_TOKEN`).
2. Abra `http://localhost:5679` e crie a conta de dono do n8n.
3. Importe o `radar-telegram-bot.json` (menu **...** do fluxo, **Import from File**).
4. Crie as duas credenciais que o fluxo usa:
   - **Token Telegram** (tipo Telegram API): o token do BotFather.
   - **Token Radar API** (tipo Header Auth): nome `X-Radar-Token` e, como valor, o `RADAR_TOKEN` cadastrado na Vercel.
5. Clique em **Publish**.

## Cuidados

- **Não clique em Execute workflow com o fluxo publicado.** O Telegram aceita um endereço por bot, e o modo de teste troca esse endereço. Se acontecer, publique de novo ou religue o script.
- **O endereço do túnel muda a cada vez que o script liga.** O n8n avisa o Telegram do endereço novo ao ligar. Na versão 2.49, isso só acontece com `N8N_USE_WORKFLOW_PUBLICATION_SERVICE=false`, que o script já define. Com o serviço novo de publicação, o n8n mantém o endereço antigo e o bot para de responder.
- **Print precisa ir como foto,** com a compressão ligada. Imagem enviada como arquivo cai em "formato não aceito". O Telegram também não envia como foto uma imagem muito comprida e fina.

## Limitações

- **O bot só responde enquanto o computador, o n8n e o túnel estão ligados.** Para ficar sempre no ar, o n8n precisaria rodar num servidor com endereço fixo. Para um projeto de portfólio, optei por custo zero e nenhuma máquina ligada sem uso.
- **O túnel expõe o n8n inteiro, não só o webhook.** O editor fica protegido pela conta de dono do n8n, e o endereço é aleatório e muda a cada vez que liga. Num servidor, o editor ficaria atrás de uma rede privada.