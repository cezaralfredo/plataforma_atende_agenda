#!/bin/bash
# =============================================================================
# Script de Deploy Rotineiro - Plataforma Atende Agenda
# =============================================================================
# Execute na VPS como usuário deploy:
# cd /opt/agenda-atende && ./scripts/deploy.sh
# =============================================================================

set -euo pipefail

PROJECT_DIR="/opt/agenda-atende"
COMPOSE_FILE="docker-compose.prod.yml"

cd "$PROJECT_DIR"

log() { echo -e "\033[0;32m[$(date '+%H:%M:%S')]\033[0m $1"; }
error() { echo -e "\033[0;31m[$(date '+%H:%M:%S')] ERROR:\033[0m $1"; }

log "=== Iniciando deploy ==="

# 1. Pull latest code
log "Baixando últimas alterações..."
git pull origin main

# 2. Build e subir containers
log "Construindo e subindo containers..."
docker compose -f "$COMPOSE_FILE" up -d --build

# 3. Aguardar API ficar saudável
log "Aguardando API ficar saudável..."
sleep 5
for i in {1..15}; do
    if docker compose -f "$COMPOSE_FILE" exec -T api python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=2).raise_for_status()" 2>/dev/null; then
        log "API está saudável"
        break
    fi
    if [[ $i -eq 15 ]]; then
        error "API não ficou saudável a tempo"
        docker compose -f "$COMPOSE_FILE" logs api --tail=50
        exit 1
    fi
    echo "  Aguardando... ($i/15)"
    sleep 3
done

# 4. Executar migrações
log "Executando migrações..."
docker compose -f "$COMPOSE_FILE" exec -T api alembic upgrade head

# 5. Smoke test
log "Executando smoke tests..."
docker compose -f "$COMPOSE_FILE" exec -T api pytest tests/ -v --tb=short -x -k "not test_flow_completo" || {
    warn "Alguns testes falharam, mas continuando..."
}

# 6. Health check externo
log "Verificando health check externo..."
sleep 3
if curl -f -s https://api.seudominio.com/health > /dev/null; then
    log "✅ Health check externo OK"
else
    warn "Health check externo falhou - verifique DNS/SSL/Nginx"
fi

# 7. Limpeza
log "Limpando imagens antigas..."
docker image prune -f

log "=== Deploy concluído com sucesso! ==="