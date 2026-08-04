#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Hermes Agent — Setup Automático
# Agenda Atende — Fase 5
# ─────────────────────────────────────────────────────────────
set -euo pipefail

HERMES_DIR="${HOME}/.hermes"
PROFILES_DIR="${HERMES_DIR}/profiles"
CONFIG_SRC="$(dirname "$0")/config.yaml"
PROFILES_SRC="$(dirname "$0")/profiles"

echo "========================================"
echo " Agenda Atende — Hermes Agent Setup"
echo "========================================"

# ── 1. Instalar Hermes (se não estiver instalado) ──
if ! command -v hermes &>/dev/null; then
  echo "[1/5] Instalando Hermes Agent..."
  pip install hermes-agent 2>/dev/null || {
    echo "Tentando via npm..."
    npm install -g @hermes-agent/core 2>/dev/null || {
      echo "❌ Instalação manual necessária. Siga: https://hermes.ai/docs/install"
      exit 1
    }
  }
else
  echo "[1/5] Hermes já instalado: $(hermes --version 2>/dev/null || echo 'ok')"
fi

# ── 2. Criar diretórios ──
echo "[2/5] Criando diretórios de configuração..."
mkdir -p "${HERMES_DIR}"
mkdir -p "${PROFILES_DIR}"

# ── 3. Copiar config.yaml ──
echo "[3/5] Copiando config.yaml..."
if [ -f "${CONFIG_SRC}" ]; then
  cp "${CONFIG_SRC}" "${HERMES_DIR}/config.yaml"
  echo "       → ${HERMES_DIR}/config.yaml"
else
  echo "       ⚠️  config.yaml não encontrado em ${CONFIG_SRC}"
fi

# ── 4. Criar perfis ──
echo "[4/5] Criando perfis Hermes..."
for profile_file in "${PROFILES_SRC}"/*.yaml; do
  profile_name=$(basename "${profile_file}" .yaml)
  echo "       Criando perfil: ${profile_name}..."

  # Copia o YAML de perfil
  cp "${profile_file}" "${PROFILES_DIR}/${profile_name}.yaml"

  # Registra o perfil no Hermes
  hermes profile create "${profile_name}" \
    --file "${PROFILES_DIR}/${profile_name}.yaml" \
    2>/dev/null || echo "       ⚠️  Perfil já existe ou erro ao criar"
done

# ── 5. Inicializar Kanban ──
echo "[5/5] Inicializando Kanban..."
hermes kanban init 2>/dev/null || echo "       ⚠️  Kanban já inicializado"

echo ""
echo "✅ Setup concluído!"
echo ""
echo "Para iniciar o Hermes Agent:"
echo "  export AGENDA_API_KEY='sua-api-key-aqui'"
echo "  hermes start"
echo ""
echo "Para testar o MCP:"
echo "  hermes mcp test agenda_atende"
