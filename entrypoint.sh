#!/bin/bash
# Entrypoint para produção - roda migrações e inicia a API

set -e

echo "🚀 Iniciando container da API..."

# Aguardar PostgreSQL estar pronto
echo "⏳ Aguardando PostgreSQL..."
until pg_isready -h postgres -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; do
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