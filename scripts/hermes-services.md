# =============================================================================
# Systemd Services para Hermes Agents
# =============================================================================
# Instalação:
# sudo cp hermes-*.service /etc/systemd/system/
# sudo systemctl daemon-reload
# sudo systemctl enable hermes-orquestrador hermes-agendador hermes-financeiro hermes-notificador
# sudo systemctl start hermes-orquestrador hermes-agendador hermes-financeiro hermes-notificador
# =============================================================================

# ---------- Orquestrador ----------
[Unit]
Description=Hermes Orquestrador - Agenda Atende
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/opt/agenda-atende
EnvironmentFile=/opt/agenda-atende/.env.hermes
ExecStart=/usr/local/bin/hermes run --profile orquestrador
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hermes-orquestrador

# Resource limits
MemoryLimit=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target

# ---------- Agendador ----------
[Unit]
Description=Hermes Agendador - Agenda Atende
After=network.target hermes-orquestrador.service
Wants=network-online.target

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/opt/agenda-atende
EnvironmentFile=/opt/agenda-atende/.env.hermes
ExecStart=/usr/local/bin/hermes run --profile agendador
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hermes-agendador

MemoryLimit=256M
CPUQuota=25%

[Install]
WantedBy=multi-user.target

# ---------- Financeiro ----------
[Unit]
Description=Hermes Financeiro - Agenda Atende
After=network.target hermes-orquestrador.service
Wants=network-online.target

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/opt/agenda-atende
EnvironmentFile=/opt/agenda-atende/.env.hermes
ExecStart=/usr/local/bin/hermes run --profile financeiro
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hermes-financeiro

MemoryLimit=256M
CPUQuota=25%

[Install]
WantedBy=multi-user.target

# ---------- Notificador ----------
[Unit]
Description=Hermes Notificador - Agenda Atende
After=network.target hermes-orquestrador.service
Wants=network-online.target

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/opt/agenda-atende
EnvironmentFile=/opt/agenda-atende/.env.hermes
ExecStart=/usr/local/bin/hermes run --profile notificador
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hermes-notificador

MemoryLimit=256M
CPUQuota=25%

[Install]
WantedBy=multi-user.target