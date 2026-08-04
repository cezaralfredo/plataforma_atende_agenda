"""
Teste E2E — Fluxo Completo
Simula: cadastro → criar agendamento → cobrança → webhook pagamento → confirmação
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.seed import seed_data, seed_appointment, seed_payment


class TestFluxoCompleto:
    """Fluxo: Cliente → Reserva → Pagamento → Confirmação"""

    def test_cadastrar_usuario(self, client: TestClient, db_session: Session):
        resp = client.post("/api/users", json={
            "name": "João Silva",
            "phone": "+5511999999999",
            "email": "joao@email.com",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "João Silva"
        assert data["phone"] == "+5511999999999"
        assert "id" in data

    def test_criar_profissional(self, client: TestClient, db_session: Session):
        resp = client.post("/api/professionals", json={
            "name": "Maria Souza",
            "phone": "+5511988888888",
            "active": True,
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "Maria Souza"

    def test_criar_servico(self, client: TestClient, db_session: Session):
        entities = seed_data(db_session)
        resp = client.post("/api/services", json={
            "professional_id": entities["professional"].id,
            "name": "Corte de cabelo",
            "duration_minutes": 60,
            "price_cents": 5000,
            "category": "corte",
        })
        assert resp.status_code == 201
        assert resp.json()["price_cents"] == 5000

    def test_listar_servicos(self, client: TestClient, db_session: Session):
        entities = seed_data(db_session)
        resp = client.get(f"/api/services?professional_id={entities['professional'].id}")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_verificar_disponibilidade(self, client: TestClient, db_session: Session):
        entities = seed_data(db_session)
        resp = client.get(
            f"/api/availability/check/{entities['professional'].id}?date=2026-07-30"
        )
        assert resp.status_code == 200
        slots = resp.json()
        assert len(slots) > 0
        assert slots[0]["start"].startswith("2026-07-30")

    def test_criar_reserva(self, client: TestClient, db_session: Session):
        entities = seed_data(db_session)
        resp = client.post("/api/appointments", json={
            "user_id": entities["user"].id,
            "professional_id": entities["professional"].id,
            "service_id": entities["service"].id,
            "start_time": "2026-07-30T09:00:00",
            "end_time": "2026-07-30T10:00:00",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["expires_at"] is not None

    def test_conflito_reserva(self, client: TestClient, db_session: Session):
        entities = seed_data(db_session)
        client.post("/api/appointments", json={
            "user_id": entities["user"].id,
            "professional_id": entities["professional"].id,
            "service_id": entities["service"].id,
            "start_time": "2026-07-30T09:00:00",
            "end_time": "2026-07-30T10:00:00",
        })
        resp = client.post("/api/appointments", json={
            "user_id": entities["user"].id,
            "professional_id": entities["professional"].id,
            "service_id": entities["service"].id,
            "start_time": "2026-07-30T09:30:00",
            "end_time": "2026-07-30T10:30:00",
        })
        assert resp.status_code == 409

    def test_cancelar_reserva(self, client: TestClient, db_session: Session):
        entities = seed_data(db_session)
        apt = seed_appointment(db_session, entities)
        resp = client.post(f"/api/appointments/{apt.id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_meus_agendamentos(self, client: TestClient, db_session: Session):
        entities = seed_data(db_session)
        seed_appointment(db_session, entities)
        resp = client.get(f"/api/appointments?user_id={entities['user'].id}")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
        assert resp.json()[0]["user_id"] == entities["user"].id

    def test_webhook_pagamento_recebido(self, client: TestClient, db_session: Session):
        entities = seed_data(db_session)
        apt = seed_appointment(db_session, entities)
        pay = seed_payment(db_session, apt)

        resp = client.post("/webhooks/asaas", json={
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": pay.asaas_payment_id},
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_webhook_pagamento_duplicado(self, client: TestClient, db_session: Session):
        entities = seed_data(db_session)
        apt = seed_appointment(db_session, entities)
        pay = seed_payment(db_session, apt)

        client.post("/webhooks/asaas", json={
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": pay.asaas_payment_id},
        })
        resp = client.post("/webhooks/asaas", json={
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": pay.asaas_payment_id},
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_mcp_listar_servicos(self, client: TestClient, db_session: Session):
        from app.config import settings

        seed_data(db_session)
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1,
        }, headers={"Authorization": f"Bearer {settings.api_key}"})
        assert resp.status_code == 200
        tools = resp.json()["result"]["tools"]
        names = [t["name"] for t in tools]
        assert "listar_servicos" in names
        assert "criar_reserva" in names
        assert "criar_cobranca_asaas" in names

    def test_mcp_criar_reserva(self, client: TestClient, db_session: Session):
        from app.config import settings

        entities = seed_data(db_session)
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 2,
            "params": {
                "name": "criar_reserva",
                "arguments": {
                    "user_id": entities["user"].id,
                    "professional_id": entities["professional"].id,
                    "service_id": entities["service"].id,
                    "start_time": "2026-07-30T14:00:00",
                    "end_time": "2026-07-30T15:00:00",
                },
            },
        }, headers={"Authorization": f"Bearer {settings.api_key}"})
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert "Reserva criada" in result["content"][0]["text"]
