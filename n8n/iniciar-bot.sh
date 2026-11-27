#!/usr/bin/env bash
# Liga o bot do Telegram: túnel público (cloudflared) + um n8n só deste projeto.
# Uso (Git Bash, na raiz do projeto): bash n8n/iniciar-bot.sh
# Para desligar: Ctrl + C neste terminal. O n8n e o túnel fecham juntos.
set -euo pipefail

PORTA=5679                              # a 5678 fica livre para o n8n de outros projetos
VERSAO_N8N=2.49.7
PASTA_DADOS="$HOME/.n8n-radar-golpes"   # fluxo e credenciais deste bot, fora do Git

if ! command -v cloudflared >/dev/null; then
  echo "cloudflared não encontrado. Instale com: winget install --id Cloudflare.cloudflared -e" >&2
  exit 1
fi

# O Telegram só entrega mensagens em endereço público com HTTPS. O túnel rápido
# da Cloudflare cria um, sem conta, mas o endereço muda a cada vez que liga.
LOG_TUNEL="$(mktemp)"
cloudflared tunnel --url "http://localhost:$PORTA" >"$LOG_TUNEL" 2>&1 &
PID_TUNEL=$!
trap 'kill "$PID_TUNEL" 2>/dev/null; rm -f "$LOG_TUNEL"' EXIT

echo "Abrindo o túnel..."
URL=""
for _ in $(seq 1 30); do
  URL="$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG_TUNEL" | grep -v '^https://api\.' | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done
if [ -z "$URL" ]; then
  echo "O túnel não abriu em 30 s. Últimas linhas do cloudflared:" >&2
  tail -5 "$LOG_TUNEL" >&2
  exit 1
fi

echo "Endereço público: $URL"
echo "Editor do n8n:    http://localhost:$PORTA"

export N8N_PORT=$PORTA
export N8N_WEBHOOK_URL="$URL/"          # o n8n registra no Telegram com este endereço
export N8N_EDITOR_BASE_URL="http://localhost:$PORTA/"   # o editor é usado só neste computador
export N8N_PROXY_HOPS=1                 # confia no cabeçalho do túnel (HTTPS e IP)
# Na 2.49 o serviço novo de publicação não reenvia o webhook ao Telegram quando
# o endereço do túnel muda. O modo antigo compara o endereço e atualiza sozinho.
export N8N_USE_WORKFLOW_PUBLICATION_SERVICE=false
# Cada execução guarda a mensagem recebida. Apaga depois de 24 h (o padrão é 14 dias).
export EXECUTIONS_DATA_MAX_AGE=24
export N8N_USER_FOLDER="$(cygpath -w "$PASTA_DADOS")"
export NODE_OPTIONS="--dns-result-order=ipv4first"   # nesta rede o IPv6 com o Telegram às vezes falha
npx --yes "n8n@$VERSAO_N8N"