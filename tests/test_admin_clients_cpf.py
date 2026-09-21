from app.admin.schemas import AdminClientCreate, AdminClientSummary, AdminClientUpdate
from app.admin.service import AdminService


def test_admin_client_schemas_include_cpf_cnpj():
    create_dto = AdminClientCreate(
        name="Carlos Silva",
        phone="5511988887777",
        email="carlos@exemplo.com",
        cpf_cnpj="12345678909",
    )
    assert create_dto.cpf_cnpj == "12345678909"

    update_dto = AdminClientUpdate(cpf_cnpj="98765432100")
    assert update_dto.cpf_cnpj == "98765432100"

    summary_dto = AdminClientSummary(
        id=1,
        name="Carlos Silva",
        phone="5511988887777",
        cpf_cnpj="12345678909",
        active=True,
        appointments_total=2,
        payments_received_total=1,
    )
    assert summary_dto.cpf_cnpj == "12345678909"
    assert summary_dto.active is True


def test_admin_service_create_and_update_client_with_cpf(db_session):
    service = AdminService(db_session)

    create_data = AdminClientCreate(
        name="Maria Oliveira",
        phone="5511977776666",
        email="maria@exemplo.com",
        whatsapp_number="5511977776666",
        cpf_cnpj="123.456.789-09",
    )

    client = service.create_client(create_data)
    assert client.id is not None
    assert client.name == "Maria Oliveira"
    assert client.cpf_cnpj == "12345678909"

    # Test list_clients
    clients, total = service.list_clients(search="Maria")
    assert total == 1
    assert clients[0]["cpf_cnpj"] == "12345678909"

    # Test update_client
    update_data = AdminClientUpdate(cpf_cnpj="987.654.321-00")
    updated = service.update_client(client.id, update_data)
    assert updated.cpf_cnpj == "98765432100"
