#!/bin/bash
# Entrypoint para produção - roda migrações e inicia a API

set -e

load_secret() {
  local variable_name="$1"
  local file_variable_name="${variable_name}_FILE"
  local file_path="${!file_variable_name:-}"

  if [ -n "$file_path" ] && [ -f "$file_path" ]; then
    export "$variable_name=$(tr -d '\r\n' < "$file_path")"
  fi
}

for secret in POSTGRES_PASSWORD API_KEY ADMIN_API_KEY ASAAS_API_KEY ASAAS_WEBHOOK_TOKEN; do
  load_secret "$secret"
done

if [ -n "${POSTGRES_PASSWORD:-}" ]; then
  export DATABASE_URL="${DATABASE_URL/__POSTGRES_PASSWORD__/$POSTGRES_PASSWORD}"
fi

echo "🚀 Iniciando container da API..."

# Aguardar PostgreSQL estar pronto
echo "⏳ Aguardando PostgreSQL..."
until pg_isready -h postgres -p 5432 -U agenda_user -d agenda_atende > /dev/null 2>&1; do
  sleep 2
done
echo "✅ PostgreSQL pronto"

# Rodar migrações Alembic
echo "🔄 Executando migrações Alembic..."
alembic upgrade head
echo "✅ Migrações aplicadas"

# Verificar se há seed de dados (opcional)
if [ "$SEED_DATA" = "true" ]; then
  echo "🌱 Executando seed de dados..."
  python -m tests.seed
  echo "✅ Seed concluído"
fi

# Iniciar aplicação
echo "🌐 Iniciando Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
