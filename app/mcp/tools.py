import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.professional_repo import ProfessionalRepository
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.schemas.user import UserCreate, UserUpdate
from app.services.appointment_service import AppointmentService
from app.services.availability_service import AvailabilityService
from app.services.payment_service import PaymentService
from app.services.service_service import ServiceService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "name": "buscar_cliente_por_telefone",
        "description": "Busca um cliente pelo número de telefone/WhatsApp",
        "inputSchema": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "Número de telefone no formato 55XXXXXXXXXXX"},
            },
            "required": ["phone"],
        },
    },
    {
        "name": "cadastrar_cliente",
        "description": "Cadastra um novo cliente",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome completo do cliente"},
                "phone": {"type": "string", "description": "Número de telefone no formato 55XXXXXXXXXXX"},
                "email": {"type": "string", "description": "Email do cliente (opcional)"},
                "whatsapp_number": {"type": "string", "description": "Número do WhatsApp no formato 55XXXXXXXXXXX (opcional)"},
                "cpf_cnpj": {"type": "string", "description": "CPF ou CNPJ do cliente (apenas números) - obrigatório para gerar cobrança/pagamento no Asaas"},
            },
            "required": ["name", "phone"],
        },
    },
    {
        "name": "atualizar_cliente",
        "description": "Atualiza dados de um cliente existente",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "ID do cliente"},
                "name": {"type": "string", "description": "Nome completo (opcional)"},
                "phone": {"type": "string", "description": "Telefone (opcional)"},
                "email": {"type": "string", "description": "Email (opcional)"},
                "whatsapp_number": {"type": "string", "description": "WhatsApp (opcional)"},
                "cpf_cnpj": {"type": "string", "description": "CPF ou CNPJ (apenas números) - obrigatório para gerar cobrança/pagamento no Asaas (opcional)"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "vincular_whatsapp",
        "description": "Vincula um número de WhatsApp a um cliente existente",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "ID do cliente"},
                "whatsapp_number": {"type": "string", "description": "Número do WhatsApp no formato 55XXXXXXXXXXX"},
            },
            "required": ["user_id", "whatsapp_number"],
        },
    },
    {
        "name": "listar_servicos",
        "description": "Lista serviços disponíveis por profissional ou categoria",
        "inputSchema": {
            "type": "object",
            "properties": {
                "professional_id": {"type": "integer", "description": "ID do profissional (opcional)"},
                "category": {"type": "string", "description": "Categoria do serviço (opcional)"},
            },
        },
    },
    {
        "name": "verificar_disponibilidade",
        "description": "Verifica horários livres de um profissional em uma data específica",
        "inputSchema": {
            "type": "object",
            "properties": {
                "professional_id": {"type": "integer", "description": "ID do profissional"},
                "date": {"type": "string", "description": "Data no formato YYYY-MM-DD"},
            },
            "required": ["professional_id", "date"],
        },
    },
    {
        "name": "criar_reserva",
        "description": "Cria uma nova reserva (agendamento) para um cliente",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "ID do cliente"},
                "professional_id": {"type": "integer", "description": "ID do profissional"},
                "service_id": {"type": "integer", "description": "ID do serviço"},
                "start_time": {"type": "string", "description": "Horário início (ISO 8601)"},
                "end_time": {"type": "string", "description": "Horário fim (ISO 8601)"},
                "notes": {"type": "string", "description": "Observações (opcional)"},
            },
            "required": ["user_id", "professional_id", "service_id", "start_time", "end_time"],
        },
    },
    {
        "name": "cancelar_reserva",
        "description": "Cancela uma reserva existente",
        "inputSchema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "integer", "description": "ID do agendamento"},
            },
            "required": ["appointment_id"],
        },
    },
    {
        "name": "criar_cobranca_asaas",
        "description": "Cria uma cobrança no Asaas para um agendamento e retorna o link de pagamento",
        "inputSchema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "integer", "description": "ID do agendamento"},
                "billing_type": {
                    "type": "string",
                    "description": "Tipo: PIX, BOLETO, CREDIT_CARD ou UNDEFINED",
                    "default": "UNDEFINED",
                },
            },
            "required": ["appointment_id"],
        },
    },
    {
        "name": "verificar_pagamentos_recentes",
        "description": "Verifica pagamentos pendentes no Asaas e atualiza status dos que foram confirmados",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "marcar_notificado",
        "description": "Marca um agendamento como notificado (após envio de confirmação ao cliente)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "integer", "description": "ID do agendamento"},
            },
            "required": ["appointment_id"],
        },
    },
    {
        "name": "meus_agendamentos",
        "description": "Lista todos os agendamentos de um cliente",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "ID do cliente"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "listar_profissionais",
        "description": "Lista os profissionais ativos e a jornada de atendimento de cada um (dias da semana e horários). Útil para saber quais profissionais existem e quando atendem.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


async def handle_tool_call(name: str, arguments: dict, db: Session) -> dict:
    try:
        if name == "buscar_cliente_por_telefone":
            user_service = UserService(db)
            user = user_service.find_by_phone(arguments["phone"])
            if not user:
                return {"content": [{"type": "text", "text": "Cliente não encontrado."}]}
            return {"content": [{"type": "text", "text": _format_cliente(user)}]}

        elif name == "cadastrar_cliente":
            user_service = UserService(db)
            user_create = UserCreate(
                name=arguments["name"],
                phone=arguments["phone"],
                email=arguments.get("email"),
                whatsapp_number=arguments.get("whatsapp_number"),
                cpf_cnpj=arguments.get("cpf_cnpj"),
            )
            user = user_service.create(user_create)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Cliente cadastrado com sucesso!\n{_format_cliente(user)}",
                    }
                ]
            }

        elif name == "atualizar_cliente":
            user_service = UserService(db)
            fields = {"name", "phone", "email", "whatsapp_number", "cpf_cnpj"}
            user_update = UserUpdate(
                **{key: arguments[key] for key in fields if key in arguments}
            )
            user = user_service.update(arguments["user_id"], user_update)
            if not user:
                return {"content": [{"type": "text", "text": "Cliente não encontrado."}]}
            return {"content": [{"type": "text", "text": f"Cliente atualizado!\n{_format_cliente(user)}"}]}

        elif name == "vincular_whatsapp":
            user_service = UserService(db)
            user = user_service.link_whatsapp(arguments["user_id"], arguments["whatsapp_number"])
            if not user:
                return {"content": [{"type": "text", "text": "Cliente não encontrado."}]}
            return {"content": [{"type": "text", "text": f"WhatsApp vinculado com sucesso!\n{_format_cliente(user)}"}]}

        elif name == "listar_servicos":
            service_service = ServiceService(db)
            professional_id = arguments.get("professional_id")
            services = service_service.list(
                professional_id=professional_id,
                category=arguments.get("category"),
            )
            return {
                "content": [
                    {
                        "type": "text",
                        "text": _format_servicos(
                            services,
                            include_professional=professional_id is None,
                        ),
                    }
                ]
            }

        elif name == "listar_profissionais":
            professional_repo = ProfessionalRepository(db)
            availability_service = AvailabilityService(db)
            dias = {
                0: "segunda", 1: "terça", 2: "quarta", 3: "quinta",
                4: "sexta", 5: "sábado", 6: "domingo",
            }
            professionals = professional_repo.list_active()
            if not professionals:
                return {"content": [{"type": "text", "text": "Nenhum profissional encontrado."}]}
            lines = ["Profissionais e jornada de atendimento:"]
            for p in professionals:
                schedule_rows = availability_service.list(p.id)
                por_dia: dict[str, list[str]] = {}
                for a in schedule_rows:
                    label = None
                    if a.day_of_week is not None:
                        label = dias.get(a.day_of_week, f"dia {a.day_of_week}")
                    elif a.specific_date is not None:
                        label = str(a.specific_date)
                    if label and a.start_time and a.end_time:
                        por_dia.setdefault(label, []).append(
                            f"{a.start_time.strftime('%H:%M')}-{a.end_time.strftime('%H:%M')}"
                        )
                jornada = (
                    "; ".join(f"{d}: {', '.join(ts)}" for d, ts in por_dia.items())
                    if por_dia
                    else "sem agenda cadastrada"
                )
                lines.append(f"  #{p.id} {p.name}: {jornada}")
            return {"content": [{"type": "text", "text": "\n".join(lines)}]}

        elif name == "verificar_disponibilidade":
            availability_service = AvailabilityService(db)
            slots = availability_service.check_availability(
                professional_id=arguments["professional_id"],
                date_str=arguments["date"],
            )
            if not slots:
                return {"content": [{"type": "text", "text": "Nenhum horário disponível nesta data. Consulte \u201clistar_profissionais\u201d para ver os dias e horários em que o profissional atende e proponha ao cliente outra data em que ele trabalhe."}]}
            text = "Horários disponíveis:\n" + "\n".join(
                f"  {s.start} - {s.end}" for s in slots
            )
            return {"content": [{"type": "text", "text": text}]}

        elif name == "criar_reserva":
            appointment_service = AppointmentService(db)
            appointment_create = AppointmentCreate(
                user_id=arguments["user_id"],
                professional_id=arguments["professional_id"],
                service_id=arguments["service_id"],
                start_time=arguments["start_time"],
                end_time=arguments["end_time"],
                notes=arguments.get("notes"),
            )
            appointment = appointment_service.create(appointment_create)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Reserva criada! ID: {appointment.id}\n"
                            f"Status: {appointment.status}\n"
                            f"Expira em: {appointment.expires_at}"
                        ),
                    }
                ]
            }

        elif name == "cancelar_reserva":
            appointment_service = AppointmentService(db)
            appointment = appointment_service.cancel(arguments["appointment_id"])
            if not appointment:
                return {"content": [{"type": "text", "text": "Reserva não encontrada."}]}
            return {"content": [{"type": "text", "text": f"Reserva {appointment.id} cancelada com sucesso."}]}

        elif name == "criar_cobranca_asaas":
            payment_service = PaymentService(db)
            payment = await payment_service.create_charge(
                appointment_id=arguments["appointment_id"],
                billing_type=arguments.get("billing_type", "UNDEFINED"),
            )
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Cobrança criada!\n"
                            f"ID Asaas: {payment.asaas_payment_id}\n"
                            f"Valor: R$ {payment.amount_cents / 100:.2f}\n"
                            f"Link: {payment.invoice_url}"
                        ),
                    }
                ]
            }

        elif name == "verificar_pagamentos_recentes":
            payment_service = PaymentService(db)
            updated = await payment_service.verify_recent_payments()
            if not updated:
                return {"content": [{"type": "text", "text": "Nenhum pagamento novo confirmado."}]}
            lines = [f"Pagamento {p.id}: reserva {p.appointment_id} - {p.status}" for p in updated]
            return {"content": [{"type": "text", "text": "Pagamentos atualizados:\n" + "\n".join(lines)}]}

        elif name == "marcar_notificado":
            appointment_service = AppointmentService(db)
            appointment_update = AppointmentUpdate(notified_at=datetime.now())
            appointment = appointment_service.update(arguments["appointment_id"], appointment_update)
            if not appointment:
                return {"content": [{"type": "text", "text": "Agendamento não encontrado."}]}
            return {"content": [{"type": "text", "text": f"Agendamento {appointment.id} marcado como notificado."}]}

        elif name == "meus_agendamentos":
            appointment_service = AppointmentService(db)
            appointments = appointment_service.list(user_id=arguments["user_id"])
            if not appointments:
                return {"content": [{"type": "text", "text": "Nenhum agendamento encontrado."}]}
            text = "Seus agendamentos:\n" + "\n".join(
                f"  #{a.id} - {a.start_time} ({a.status})" for a in appointments
            )
            return {"content": [{"type": "text", "text": text}]}

        else:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Ferramenta desconhecida: {name}"}],
            }

    except ValueError as e:
        return {
            "isError": True,
            "content": [{"type": "text", "text": str(e)}],
        }
    except Exception:
        logger.exception("MCP tool failed", extra={"tool_name": name})
        return {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": "Erro interno ao processar a solicitação.",
                }
            ],
        }


def _format_servicos(services, include_professional: bool = True) -> str:
    if not services:
        return "Nenhum serviço encontrado."

    lines = ["Serviços disponíveis:"]
    seen = set()
    for s in services:
        if include_professional:
            duplicate_key = (
                s.professional_id,
                s.name,
                s.description,
                s.duration_minutes,
                s.price_cents,
                s.category,
            )
            if duplicate_key in seen:
                continue
            seen.add(duplicate_key)
            line = (
                f"  #{s.id} {s.name} - R$ {s.price_cents / 100:.2f} "
                f"({s.duration_minutes}min) — {s.professional.name}"
            )
        else:
            line = f"  #{s.id} {s.name} - R$ {s.price_cents / 100:.2f} ({s.duration_minutes}min)"
        lines.append(line)
    return "\n".join(lines)


def _format_cliente(user) -> str:
    whatsapp = user.whatsapp_number or "-"
    cpf = user.cpf_cnpj or "-"
    return (
        f"  ID: {user.id}\n"
        f"  Nome: {user.name}\n"
        f"  Telefone: {user.phone}\n"
        f"  Email: {user.email or '-'}\n"
        f"  WhatsApp: {whatsapp}\n"
        f"  CPF/CNPJ: {cpf}"
    )
