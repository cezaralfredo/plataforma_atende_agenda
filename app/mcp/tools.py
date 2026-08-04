from datetime import datetime

from sqlalchemy.orm import Session

from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.services.appointment_service import AppointmentService
from app.services.availability_service import AvailabilityService
from app.services.payment_service import PaymentService
from app.services.service_service import ServiceService


TOOL_DEFINITIONS = [
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
]


async def handle_tool_call(name: str, arguments: dict, db: Session) -> dict:
    try:
        if name == "listar_servicos":
            svc = ServiceService(db)
            result = svc.list(
                professional_id=arguments.get("professional_id"),
                category=arguments.get("category"),
            )
            return {"content": [{"type": "text", "text": _format_servicos(result)}]}

        elif name == "verificar_disponibilidade":
            svc = AvailabilityService(db)
            slots = svc.check_availability(
                professional_id=arguments["professional_id"],
                date_str=arguments["date"],
            )
            if not slots:
                return {"content": [{"type": "text", "text": "Nenhum horário disponível nesta data."}]}
            text = "Horários disponíveis:\n" + "\n".join(
                f"  {s.start} - {s.end}" for s in slots
            )
            return {"content": [{"type": "text", "text": text}]}

        elif name == "criar_reserva":
            svc = AppointmentService(db)
            data = AppointmentCreate(
                user_id=arguments["user_id"],
                professional_id=arguments["professional_id"],
                service_id=arguments["service_id"],
                start_time=arguments["start_time"],
                end_time=arguments["end_time"],
                notes=arguments.get("notes"),
            )
            apt = svc.create(data)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Reserva criada! ID: {apt.id}\n"
                            f"Status: {apt.status}\n"
                            f"Expira em: {apt.expires_at}"
                        ),
                    }
                ]
            }

        elif name == "cancelar_reserva":
            svc = AppointmentService(db)
            apt = svc.cancel(arguments["appointment_id"])
            if not apt:
                return {"content": [{"type": "text", "text": "Reserva não encontrada."}]}
            return {"content": [{"type": "text", "text": f"Reserva {apt.id} cancelada com sucesso."}]}

        elif name == "criar_cobranca_asaas":
            svc = PaymentService(db)
            payment = await svc.create_charge(
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
            svc = PaymentService(db)
            updated = await svc.verify_recent_payments()
            if not updated:
                return {"content": [{"type": "text", "text": "Nenhum pagamento novo confirmado."}]}
            lines = [f"Pagamento {p.id}: reserva {p.appointment_id} - {p.status}" for p in updated]
            return {"content": [{"type": "text", "text": "Pagamentos atualizados:\n" + "\n".join(lines)}]}

        elif name == "marcar_notificado":
            svc = AppointmentService(db)
            data = AppointmentUpdate(notified_at=datetime.now().isoformat())
            apt = svc.update(arguments["appointment_id"], data)
            if not apt:
                return {"content": [{"type": "text", "text": "Agendamento não encontrado."}]}
            return {"content": [{"type": "text", "text": f"Agendamento {apt.id} marcado como notificado."}]}

        elif name == "meus_agendamentos":
            svc = AppointmentService(db)
            appointments = svc.list(user_id=arguments["user_id"])
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
    except Exception as e:
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Erro: {str(e)}"}],
        }


def _format_servicos(services) -> str:
    if not services:
        return "Nenhum serviço encontrado."
    lines = ["Serviços disponíveis:"]
    for s in services:
        lines.append(f"  #{s.id} {s.name} - R$ {s.price_cents / 100:.2f} ({s.duration_minutes}min)")
    return "\n".join(lines)
