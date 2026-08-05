#!/bin/bash
# Backup automático do PostgreSQL com upload para storage remoto via rclone

set -e

# Configurações
BACKUP_DIR="/backups"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
RCLONE_DEST="${RCLONE_DESTINATION:-}"
PG_DATABASE="agenda_atende"
PG_USER="agenda_user"
PG_HOST="postgres"

# Criar diretório de backup se não existir
mkdir -p "$BACKUP_DIR"

# Função de log
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Função para fazer backup
do_backup() {
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_file="${BACKUP_DIR}/agenda_${PG_DATABASE}_${timestamp}.sql.gz"

    log "Iniciando backup do banco ${PG_DATABASE}..."
    
    # Fazer dump comprimido
    PGPASSWORD="$(cat /run/secrets/postgres_password)" \
    pg_dump -h "$PG_HOST" -U "$PG_USER" -d "$PG_DATABASE" \
        --no-owner --no-privileges --clean --if-exists | gzip > "$backup_file"

    local size=$(du -h "$backup_file" | cut -f1)
    log "Backup concluído: $backup_file ($size)"

    # Upload para storage remoto se configurado
    if [ -n "$RCLONE_DEST" ] && [ -f /config/rclone/rclone.conf ]; then
        log "Enviando para storage remoto: $RCLONE_DEST"
        rclone --config /config/rclone/rclone.conf copy "$backup_file" "$RCLONE_DEST" --progress
        log "Upload concluído"
    else
        log "Storage remoto não configurado - backup mantido apenas localmente"
    fi

    # Limpeza de backups antigos locais
    log "Removendo backups locais com mais de ${RETENTION_DAYS} dias..."
    find "$BACKUP_DIR" -name "agenda_${PG_DATABASE}_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
    log "Limpeza concluída"
}

# Se BACKUP_SCHEDULE estiver definido, rodar como cron
if [ -n "$BACKUP_SCHEDULE" ]; then
    log "Modo agendado ativado: $BACKUP_SCHEDULE"
    echo "$BACKUP_SCHEDULE /backup.sh" > /etc/crontabs/root
    # Executar backup inicial
    do_backup
    # Iniciar cron em foreground
    exec crond -f -l 2
else
    # Modo one-shot (para execução manual)
    do_backup
fi