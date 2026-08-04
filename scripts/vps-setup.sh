#!/bin/bash
# =============================================================================
# Script de Deploy Inicial - VPS Ubuntu 22.04/24.04
# =============================================================================
# Execute na VPS como usuário root ou com sudo
# curl -fsSL https://raw.githubusercontent.com/cezaralfredo/plataforma_atende_agenda/main/scripts/vps-setup.sh | bash
# OU copie para a VPS e execute: chmod +x vps-setup.sh && sudo ./vps-setup.sh
# =============================================================================

set -euo pipefail

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARN:${NC} $1"; }
error() { echo -e "${RED}[$(date '+%H:%M:%S')] ERROR:${NC} $1"; }
info() { echo -e "${BLUE}[$(date '+%H:%M:%S')] INFO:${NC} $1"; }

# Verificar se é root
if [[ $EUID -ne 0 ]]; then
   error "Este script deve ser executado como root (use sudo)"
   exit 1
fi

# Configurações
DEPLOY_USER="deploy"
PROJECT_DIR="/opt/agenda-atende"
REPO_URL="https://github.com/cezaralfredo/plataforma_atende_agenda.git"
DOMAIN="api.seudominio.com"  # ALTERAR ANTES DE EXECUTAR
EMAIL="seu@email.com"         # ALTERAR ANTES DE EXECUTAR

log "=== Iniciando setup da VPS para Plataforma Atende Agenda ==="

# -----------------------------------------------------------------------------
# 1. Atualizar sistema
# -----------------------------------------------------------------------------
log "Atualizando pacotes do sistema..."
apt-get update && apt-get upgrade -y

# -----------------------------------------------------------------------------
# 2. Instalar dependências base
# -----------------------------------------------------------------------------
log "Instalando dependências base..."
apt-get install -y \
    git \
    curl \
    wget \
    htop \
    vim \
    ufw \
    fail2ban \
    ca-certificates \
    gnupg \
    lsb-release \
    software-properties-common

# -----------------------------------------------------------------------------
# 3. Criar usuário deploy
# -----------------------------------------------------------------------------
if id "$DEPLOY_USER" &>/dev/null; then
    log "Usuário $DEPLOY_USER já existe"
else
    log "Criando usuário $DEPLOY_USER..."
    adduser --disabled-password --gecos "" "$DEPLOY_USER"
    usermod -aG sudo "$DEPLOY_USER"
    echo "$DEPLOY_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$DEPLOY_USER
fi

# Configurar SSH para deploy user
mkdir -p /home/$DEPLOY_USER/.ssh
cp /root/.ssh/authorized_keys /home/$DEPLOY_USER/.ssh/authorized_keys 2>/dev/null || true
chown -R $DEPLOY_USER:$DEPLOY_USER /home/$DEPLOY_USER/.ssh
chmod 700 /home/$DEPLOY_USER/.ssh
chmod 600 /home/$DEPLOY_USER/.ssh/authorized_keys

# -----------------------------------------------------------------------------
# 4. Hardening SSH
# -----------------------------------------------------------------------------
log "Configurando SSH hardening..."
SSHD_CONFIG="/etc/ssh/sshd_config"
cp $SSHD_CONFIG $SSHD_CONFIG.backup

sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' $SSHD_CONFIG
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' $SSHD_CONFIG
sed -i 's/^#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' $SSHD_CONFIG
sed -i 's/^#\?AuthorizedKeysFile.*/AuthorizedKeysFile .ssh\/authorized_keys/' $SSHD_CONFIG

# Testar configuração SSH
sshd -t && systemctl reload sshd
log "SSH hardening aplicado"

# -----------------------------------------------------------------------------
# 5. Configurar Firewall (UFW)
# -----------------------------------------------------------------------------
log "Configurando firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable
log "Firewall configurado"

# -----------------------------------------------------------------------------
# 6. Configurar fail2ban
# -----------------------------------------------------------------------------
log "Configurando fail2ban..."
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3
backend = systemd

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = %(sshd_log)s
maxretry = 3

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
logpath = /var/log/nginx/error.log
maxretry = 3

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
logpath = /var/log/nginx/error.log
maxretry = 5
EOF

systemctl enable fail2ban
systemctl restart fail2ban
log "fail2ban configurado"

# -----------------------------------------------------------------------------
# 7. Instalar Docker
# -----------------------------------------------------------------------------
log "Instalando Docker..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

usermod -aG docker $DEPLOY_USER

log "Docker instalado"

# -----------------------------------------------------------------------------
# 8. Clonar repositório
# -----------------------------------------------------------------------------
log "Clonando repositório..."
if [[ -d "$PROJECT_DIR" ]]; then
    warn "Diretório $PROJECT_DIR já existe, atualizando..."
    cd "$PROJECT_DIR"
    sudo -u $DEPLOY_USER git pull origin main
else
    sudo -u $DEPLOY_USER git clone "$REPO_URL" "$PROJECT_DIR"
fi

cd "$PROJECT_DIR"

# -----------------------------------------------------------------------------
# 9. Configurar arquivos de produção
# -----------------------------------------------------------------------------
log "Verificando arquivos de configuração..."

if [[ ! -f ".env" ]]; then
    warn "Arquivo .env não encontrado. Copie .env.example para .env e configure:"
    warn "  cp .env.example .env"
    warn "  vim .env"
else
    log ".env encontrado"
fi

if [[ ! -f "nginx/nginx.conf" ]]; then
    error "nginx/nginx.conf não encontrado!"
    exit 1
fi

# Ajustar domínio no nginx.conf
if grep -q "api.seudominio.com" nginx/nginx.conf; then
    warn "ATENÇÃO: Atualize o domínio em nginx/nginx.conf (substitua api.seudominio.com pelo seu domínio)"
fi

# -----------------------------------------------------------------------------
# 10. Configurar certbot (SSL)
# -----------------------------------------------------------------------------
log "Preparando certificados SSL..."
mkdir -p certbot/conf certbot/www

# -----------------------------------------------------------------------------
# 11. Permissões
# -----------------------------------------------------------------------------
log "Ajustando permissões..."
chown -R $DEPLOY_USER:$DEPLOY_USER "$PROJECT_DIR"
chmod +x scripts/backup.sh

# -----------------------------------------------------------------------------
# 12. Configurar logrotate
# -----------------------------------------------------------------------------
log "Configurando logrotate..."
cat > /etc/logrotate.d/agenda-atende << 'EOF'
/opt/agenda-atende/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 deploy deploy
    sharedscripts
    postrotate
        docker compose -f /opt/agenda-atende/docker-compose.prod.yml exec -T nginx nginx -s reload 2>/dev/null || true
    endscript
}
EOF

# -----------------------------------------------------------------------------
# 13. Configurar unattended-upgrades
# -----------------------------------------------------------------------------
log "Configurando atualizações automáticas de segurança..."
apt-get install -y unattended-upgrades
cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
    "${distro_id}:${distro_codename}-updates";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
EOF

systemctl enable unattended-upgrades

# -----------------------------------------------------------------------------
# 14. Configurar cron para backup
# -----------------------------------------------------------------------------
log "Configurando backup automático (cron daily 03:00)..."
(crontab -u $DEPLOY_USER -l 2>/dev/null | grep -v "backup.sh"; echo "0 3 * * * /opt/agenda-atende/scripts/backup.sh >> /var/log/agenda-backup.log 2>&1") | crontab -u $DEPLOY_USER -

# -----------------------------------------------------------------------------
# Finalização
# -----------------------------------------------------------------------------
log "=== Setup da VPS concluído! ==="
echo
info "PRÓXIMOS PASSOS MANUAIS:"
echo "1. Configure o domínio no DNS (A record → IP desta VPS)"
echo "2. Edite o arquivo .env com suas credenciais:"
echo "   cd $PROJECT_DIR && cp .env.example .env && vim .env"
echo "3. Atualize o domínio em nginx/nginx.conf (substitua api.seudominio.com)"
echo "4. Gere senhas fortes:"
echo "   openssl rand -base64 32  # para API_KEY, POSTGRES_PASSWORD, ASAAS_WEBHOOK_TOKEN"
echo "5. Suba a stack:"
echo "   cd $PROJECT_DIR && docker compose -f docker-compose.prod.yml up -d --build"
echo "6. Execute migrações:"
echo "   docker compose -f docker-compose.prod.yml exec api alembic upgrade head"
echo "7. Obtenha certificado SSL (após DNS propagar):"
echo "   docker compose -f docker-compose.prod.yml run --rm certbot certonly --webroot -w /var/www/certbot -d $DOMAIN --email $EMAIL --agree-tos --no-eff-email"
echo "   docker compose -f docker-compose.prod.yml reload nginx"
echo "8. Teste: curl https://$DOMAIN/health"
echo
info "Para configurar Hermes Agents, veja scripts/hermes-services.md"
info "Para CI/CD, configure secrets no GitHub: VPS_HOST, VPS_USER, VPS_SSH_KEY, VPS_PORT"