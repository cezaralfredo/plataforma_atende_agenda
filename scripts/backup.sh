#!/bin/bash
# =============================================================================
# Script de Backup Automatizado - Plataforma Atende Agenda
# =============================================================================
# Uso: ./backup.sh
# Agendar no cron: 0 3 * * * /opt/agenda-atende/scripts/backup.sh >> /var/log/agenda-backup.log 2>&1
# =============================================================================

set -euo pipefail

# Configurações
PROJECT_DIR="/opt/agenda-atende"
BACKUP_DIR="${PROJECT_DIR}/backups"
DATE=$(date +%F_%H-%M-%S)
BACKUP_FILE="agenda_${DATE}.sql.gz"
RETENTION_DAYS=30

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARN:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Verificar se está no diretório correto
if [[ ! -f "${PROJECT_DIR}/docker-compose.prod.yml" ]]; then
    error "Arquivo docker-compose.prod.yml não encontrado em ${PROJECT_DIR}"
    exit 1
fi

cd "${PROJECT_DIR}"

# Criar diretório de backup se não existir
mkdir -p "${BACKUP_DIR}"

log "Iniciando backup do PostgreSQL..."

# Fazer dump do banco
if docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U agenda_user agenda_atende | gzip > "${BACKUP_DIR}/${BACKUP_FILE}"; then
    BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
    log "Backup concluído: ${BACKUP_FILE} (${BACKUP_SIZE})"
else
    error "Falha ao criar backup do banco de dados"
    exit 1
fi

# Limpar backups antigos
log "Removendo backups com mais de ${RETENTION_DAYS} dias..."
DELETED_COUNT=$(find "${BACKUP_DIR}" -name "agenda_*.sql.gz" -mtime +${RETENTION_DAYS} -delete -print | wc -l)
if [[ ${DELETED_COUNT} -gt 0 ]]; then
    log "Removidos ${DELETED_COUNT} backup(s) antigo(s)"
else
    log "Nenhum backup antigo para remover"
fi

# Listar backups atuais
log "Backups atuais:"
ls -lh "${BACKUP_DIR}"/agenda_*.sql.gz 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}' || log "  (nenhum)"

log "Backup finalizado com sucesso!"

# Opcional: Upload para storage remoto (S3, Wasabi, GDrive, etc.)
# Descomente e configure conforme necessário:
# log "Enviando para storage remoto..."
# rclone copy "${BACKUP_DIR}/${BACKUP_FILE}" remote:bucket/agenda-backups/ --progress