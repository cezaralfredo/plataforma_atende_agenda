import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / "n8n" / "workflows"


def test_n8n_workflows_exist():
    assert WORKFLOWS_DIR.exists(), f"Diretório {WORKFLOWS_DIR} não existe"
    workflows = list(WORKFLOWS_DIR.glob("*.json"))
    assert len(workflows) >= 4, f"Esperado ao menos 4 workflows, encontrados {len(workflows)}"


@pytest.mark.parametrize(
    "filename",
    [
        "notificacao_pagamento_hermes.json",
        "orquestrador_agendamentos.json",
        "subagente_cancelamento.json",
        "subagente_financeiro.json",
        "subagente_lembretes.json",
    ],
)
def test_each_workflow_is_valid_and_consistent(filename):
    file_path = WORKFLOWS_DIR / filename
    assert file_path.exists(), f"Arquivo {filename} não existe"

    content = file_path.read_text(encoding="utf-8")
    data = json.loads(content)

    assert "name" in data, f"{filename} deve possuir 'name'"
    assert "nodes" in data, f"{filename} deve possuir 'nodes'"
    assert "connections" in data, f"{filename} deve possuir 'connections'"

    nodes = data["nodes"]
    assert len(nodes) > 0, f"{filename} deve ter ao menos 1 nó"

    node_names = {node["name"] for node in nodes if "name" in node}
    assert len(node_names) == len(nodes), f"{filename} contém nomes de nós duplicados"

    # Verificar conexões referenciando nós válidos
    connections = data["connections"]
    for source_node, conn_types in connections.items():
        assert source_node in node_names, f"{filename}: nó de origem '{source_node}' não existe nos nós"
        if isinstance(conn_types, dict):
            for _conn_category, outputs in conn_types.items():
                for output_group in outputs:
                    for target in output_group:
                        target_node = target.get("node")
                        assert target_node in node_names, (
                            f"{filename}: nó de destino '{target_node}' não existe nos nós"
                        )


def test_docker_compose_n8n():
    compose_path = REPO_ROOT / "docker-compose.n8n.yml"
    assert compose_path.exists(), "docker-compose.n8n.yml deve existir"

    content = compose_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    assert "services" in data
    assert "n8n" in data["services"]
    n8n_service = data["services"]["n8n"]
    assert "5678:5678" in n8n_service.get("ports", [])
    assert "networks" in n8n_service
    assert "mcp_internal" in n8n_service["networks"]
    assert "npm" in n8n_service["networks"]


def test_payment_confirmation_workflow_requires_provider_acknowledgement():
    workflow = json.loads(
        (WORKFLOWS_DIR / "notificacao_pagamento_hermes.json").read_text(encoding="utf-8")
    )
    serialized = json.dumps(workflow)
    names = {node["name"] for node in workflow["nodes"]}

    assert "http://hermes:8000/send-message" not in serialized
    assert "HERMES_WHATSAPP_BRIDGE_URL" in serialized
    assert "http://hermes:3000" in serialized
    assert "EVOLUTION_API_URL" not in serialized
    assert "Assumir Entrega" in names
    assert "Enviar Confirmação pelo WhatsApp Nativo Hermes" in names
    assert "Confirmar Entrega na API" in names
    assert "Registrar Falha para Retentativa" in names


def test_workflows_use_native_hermes_whatsapp_bridge_for_outbound_messages():
    cancellation = json.loads(
        (WORKFLOWS_DIR / "subagente_cancelamento.json").read_text(encoding="utf-8")
    )
    serialized = json.dumps(cancellation)

    assert "http://hermes:8000/send-message" not in serialized
    assert "HERMES_WHATSAPP_BRIDGE_URL" in serialized
    assert "http://hermes:3000" in serialized
    send_node = next(
        node
        for node in cancellation["nodes"]
        if node["name"] == "Avisar Cancelamento via WhatsApp Hermes"
    )
    assert '"chatId"' in send_node["parameters"]["jsonBody"]
