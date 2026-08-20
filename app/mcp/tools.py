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
            professional_id = arguments.get("professional_id")
            result = svc.list(
                professional_id=professional_id,
                category=arguments.get("category"),
            )
            # Se filtrado por profissional, não precisa incluir nome nem deduplicar
            include_prof = professional_id is None
            return {"content": [{"type": "text", "text": _format_servicos(result, include_professional=include_prof)}]}

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
            svc.delete(arguments["appointment_id"])
            return {"content": [{"type": "text", "text": "Reserva cancelada com sucesso."}]}

        elif name == "criar_cobranca_asaas":
            svc = PaymentService(db)
            link = svc.create_payment_link(
                appointment_id=arguments["appointment_id"],
                billing_type=arguments.get("billing_type", "UNDEFINED"),
            )
            return {"content": [{"type": "text", "text": f"Link de pagamento: {link}"}]}

        elif name == "verificar_pagamentos_recentes":
            svc = PaymentService(db)
            svc.sync_pending_payments()
            return {"content": [{"type": "text", "text": "Verificação de pagamentos concluída."}]}

        elif name == "marcar_notificado":
            svc = AppointmentService(db)
            svc.mark_notified(arguments["appointment_id"])
            return {"content": [{"type": "text", "text": "Agendamento marcado como notificado."}]}

        elif name == "meus_agendamentos":
            svc = AppointmentService(db)
            appointments = svc.list_by_user(arguments["user_id"])
            if not appointments:
                return {"content": [{"type": "text", "text": "Nenhum agendamento encontrado."}]}
            lines = ["Seus agendamentos:"]
            for a in appointments:
                lines.append(f"  #{a.id} - {a.start_time} a {a.end_time} - Status: {a.status}")
            return {"content": [{"type": "text", "text": "\n".join(lines)}]}

        elif name == "buscar_cliente_por_telefone":
            from app.services.user_service import UserService
            svc = UserService(db)
            user = svc.get_by_phone(arguments["phone"])
            if not user:
                return {"content": [{"type": "text", "text": "Cliente não encontrado."}]}
            return {"content": [{"type": "text", "text": f"Cliente encontrado: {user.name} (ID: {user.id})"}]}

        elif name == "cadastrar_cliente":
            from app.services.user_service import UserService
            from app.schemas.user import UserCreate
            svc = UserService(db)
            data = UserCreate(
                name=arguments["name"],
                phone=arguments["phone"],
                email=arguments.get("email"),
                whatsapp_number=arguments.get("whatsapp_number"),
            )
            user = svc.create(data)
            return {"content": [{"type": "text", "text": f"Cliente cadastrado! ID: {user.id}, Nome: {user.name}"}]}

        elif name == "atualizar_cliente":
            from app.services.user_service import UserService
            from app.schemas.user import UserUpdate
            svc = UserService(db)
            data = UserUpdate(
                name=arguments.get("name"),
                phone=arguments.get("phone"),
                email=arguments.get("email"),
                whatsapp_number=arguments.get("whatsapp_number"),
            )
            user = svc.update(arguments["user_id"], data)
            if not user:
                return {"content": [{"type": "text", "text": "Cliente não encontrado."}]}
            return {"content": [{"type": "text", "text": f"Cliente atualizado! ID: {user.id}, Nome: {user.name}"}]}

        elif name == "vincular_whatsapp":
            from app.services.user_service import UserService
            from app.schemas.user import UserUpdate
            svc = UserService(db)
            data = UserUpdate(whatsapp_number=arguments["whatsapp_number"])
            user = svc.update(arguments["user_id"], data)
            if not user:
                return {"content": [{"type": "text", "text": "Cliente não encontrado."}]}
            return {"content": [{"type": "text", "text": f"WhatsApp vinculado! Cliente: {user.name} (ID: {user.id})"}]}

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


def _format_servicos(services, include_professional: bool = True) -> str:
    if not services:
        return "Nenhum serviço encontrado."
    
    lines = ["Serviços disponíveis:"]
    seen = set()  # Para deduplicação quando não filtrado por profissional
    
    for s in services:
        # Chave única para deduplicação
        # Se include_professional=True e tem professional carregado, inclui professional_id
        # Se include_professional=False, dedup por (nome, preço, duração, categoria)
        if include_professional and s.professional:
            dedup_key = (s.name, s.price_cents, s.duration_minutes, s.category, s.professional_id)
        else:
            dedup_key = (s.name, s.price_cents, s.duration_minutes, s.category)
        
        if include_professional and s.professional_id and not hasattr(s, 'professional'):
            # Se não tem relationship carregada, não deduplica
            pass
        elif include_professional and s.professional:
            # Inclui nome do profissional
            professional_name = s.professional.name if s.professional else "Profissional não identificado"
            service_line = f"  #{s.id} {s.name} - R$ {s.price_cents / 100:.2f} ({s.duration_minutes}min) — {professional_name}"
        else:
            service_line = f"  #{s.id} {s.name} - R$ {s.price_cents / 100:.2f} ({s.duration_minutes}min)"
        
        # Deduplicação: sempre aplica, mas com chaves diferentes
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        lines.append(service_line)
    
    return "\n".join(lines)
