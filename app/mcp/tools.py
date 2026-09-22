import logging
from datetime import datetime

import httpx
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models.appointment import Appointment
from app.models.notification_log import NotificationLog
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.schemas.user import UserCreate, UserUpdate
from app.services.appointment_service import AppointmentService
from app.services.asaas_client import AsaasIntegrationError
from app.services.availability_service import AvailabilityService
from app.services.payment_service import PaymentService
from app.services.service_service import ServiceService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "name": "buscar_cliente_por_telefone",
        "description": "Busca um cliente cadastrado pelo número de telefone/WhatsApp ou pelo nome completo",
        "inputSchema": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "Número de telefone no formato 55XXXXXXXXXXX ou nome do cliente (opcional se name informado)"},
                "name": {"type": "string", "description": "Nome completo do cliente (opcional se phone informado)"},
            },
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
                "cpf_cnpj": {"type": "string", "description": "CPF ou CNPJ do cliente (opcional, apenas números ou formatado)"},
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
                "cpf_cnpj": {"type": "string", "description": "CPF ou CNPJ (opcional)"},
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
        "name": "listar_pendentes_notificacao",
        "description": "Lista agendamentos com pagamento confirmado que ainda não foram notificados ao cliente",
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
        "description": "Lista todos os agendamentos de um cliente por ID, número de telefone/WhatsApp ou nome",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "ID do cliente (opcional se phone ou name informado)"},
                "phone": {"type": "string", "description": "Número do telefone/WhatsApp ou nome do cliente (opcional se user_id informado)"},
                "name": {"type": "string", "description": "Nome completo do cliente (opcional se user_id ou phone informado)"},
            },
        },
    },
    {
        "name": "verificar_status_pagamento",
        "description": "Verifica em tempo real o status de pagamento de um agendamento junto ao Asaas, confirma a reserva se pago e retorna mensagem com detalhes completos",
        "inputSchema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "integer", "description": "ID do agendamento"},
            },
            "required": ["appointment_id"],
        },
    },
    {
        "name": "solicitar_agendamento_orquestrador_n8n",
        "description": "Aciona o Orquestrador central do n8n para criar o agendamento completo (busca/cadastra cliente, valida disponibilidade, cria reserva e gera cobrança PIX no Asaas) e retorna o link de pagamento e código PIX.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "client_name": {"type": "string", "description": "Nome completo do cliente"},
                "phone": {"type": "string", "description": "Número do WhatsApp no formato 55XXXXXXXXXXX"},
                "cpf_cnpj": {"type": "string", "description": "CPF ou CNPJ do cliente (apenas números ou formatado) para emissão de cobrança no Asaas (opcional/recomendado)"},
                "professional_id": {"type": "integer", "description": "ID do profissional"},
                "service_id": {"type": "integer", "description": "ID do serviço"},
                "start_time": {"type": "string", "description": "Horário início (ISO 8601, ex: 2026-09-25T14:00:00)"},
                "end_time": {"type": "string", "description": "Horário fim (ISO 8601, ex: 2026-09-25T14:30:00)"},
                "notes": {"type": "string", "description": "Observações (opcional)"},
            },
            "required": ["client_name", "phone", "professional_id", "service_id", "start_time", "end_time"],
        },
    },
    {
        "name": "solicitar_cancelamento_n8n",
        "description": "Aciona o Subagente de Cancelamento do n8n para cancelar a reserva, liberar o horário na agenda e disparar a notificação de cancelamento.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "integer", "description": "ID do agendamento"},
                "phone": {"type": "string", "description": "Número de WhatsApp do cliente (opcional)"},
            },
            "required": ["appointment_id"],
        },
    },
]


async def handle_tool_call(name: str, arguments: dict, db: Session) -> dict:
    try:
        if name == "buscar_cliente_por_telefone":
            user_service = UserService(db)
            query = arguments.get("phone") or arguments.get("name") or arguments.get("query")
            if not query:
                return {"content": [{"type": "text", "text": "Informe o telefone ou nome do cliente para a busca."}]}
            user = user_service.find_by_phone(str(query).strip())
            if not user and arguments.get("name") and str(arguments["name"]).strip() != str(query).strip():
                user = user_service.find_by_phone(str(arguments["name"]).strip())
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

        elif name == "verificar_disponibilidade":
            availability_service = AvailabilityService(db)
            slots = availability_service.check_availability(
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
            unnotified = payment_service.list_unnotified_confirmed()

            lines = []
            if updated:
                lines.append("Pagamentos recém-atualizados no gateway:")
                lines.extend(f"  • Pagamento {p.id}: reserva {p.appointment_id} - {p.status}" for p in updated)
            if unnotified:
                lines.append(f"Reservas confirmadas aguardando aviso ao cliente ({len(unnotified)}):")
                for a in unnotified:
                    cli_nome = a.user.name if a.user else "Cliente"
                    cli_tel = getattr(a.user, "whatsapp_number", None) or getattr(a.user, "phone", "")
                    lines.append(f"  • Agendamento #{a.id} ({cli_nome} - {cli_tel}): {a.start_time}")

            if not lines:
                return {"content": [{"type": "text", "text": "Nenhum pagamento novo confirmado e nenhuma notificação pendente."}]}
            return {"content": [{"type": "text", "text": "\n".join(lines)}]}

        elif name == "listar_pendentes_notificacao":
            payment_service = PaymentService(db)
            unnotified = payment_service.list_unnotified_confirmed()
            if not unnotified:
                return {"content": [{"type": "text", "text": "Nenhum agendamento pendente de notificação."}]}
            lines = []
            for a in unnotified:
                cliente_nome = a.user.name if a.user else "Desconhecido"
                cliente_tel = getattr(a.user, "whatsapp_number", None) or getattr(a.user, "phone", "Sem telefone")
                servico = a.service.name if a.service else "Serviço"
                prof = a.professional.name if a.professional else "Profissional"
                lines.append(
                    f"• Agendamento #{a.id}: Cliente {cliente_nome} ({cliente_tel}) | "
                    f"Serviço: {servico} ({prof}) | Data/Hora: {a.start_time}"
                )
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Encontrado(s) {len(unnotified)} agendamento(s) confirmado(s) aguardando notificação:\n" + "\n".join(lines),
                    }
                ]
            }

        elif name == "marcar_notificado":
            appointment_service = AppointmentService(db)
            now = datetime.now()
            appointment_update = AppointmentUpdate(notified_at=now)
            appointment = appointment_service.update(arguments["appointment_id"], appointment_update)
            if not appointment:
                return {"content": [{"type": "text", "text": "Agendamento não encontrado."}]}
            try:
                db.add(NotificationLog(appointment_id=appointment.id, type="confirmation", sent_at=now))
                db.commit()
            except Exception as e:
                logger.warning("Could not log NotificationLog in marcar_notificado: %s", e)
            return {"content": [{"type": "text", "text": f"Agendamento {appointment.id} marcado como notificado."}]}

        elif name == "meus_agendamentos":
            user_id = arguments.get("user_id")
            query = arguments.get("phone") or arguments.get("name")
            if not user_id and query:
                user_service = UserService(db)
                user = user_service.find_by_phone(str(query).strip())
                if user:
                    user_id = user.id
            if not user_id:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "Não foi possível localizar o cliente. Por favor, forneça o número de telefone, nome ou ID do cliente.",
                        }
                    ]
                }

            appointments = (
                db.query(Appointment)
                .options(
                    joinedload(Appointment.service),
                    joinedload(Appointment.professional),
                    joinedload(Appointment.payments),
                )
                .filter(Appointment.user_id == user_id)
                .order_by(Appointment.start_time.desc())
                .all()
            )
            if not appointments:
                return {"content": [{"type": "text", "text": "Nenhum agendamento encontrado."}]}

            lines = ["Seus agendamentos:"]
            for a in appointments:
                serv_name = a.service.name if a.service else "Serviço"
                prof_name = a.professional.name if a.professional else "Profissional"
                data_hora = a.start_time.strftime("%d/%m/%Y às %H:%M")

                latest_payment = a.payments[-1] if a.payments else None
                pay_info = ""
                if latest_payment:
                    if latest_payment.status in {"received", "confirmed"}:
                        pay_info = " | Pagamento: Confirmado"
                    elif latest_payment.status in {"pending", "awaiting_payment"}:
                        link = latest_payment.invoice_url or "Link pendente"
                        pay_info = f" | Aguardando Pagamento (Link: {link})"
                    else:
                        pay_info = f" | Pagamento: {latest_payment.status}"

                status_label = "Confirmado" if a.status == "confirmed" else ("Cancelado" if a.status == "cancelled" else a.status)
                lines.append(f"• #{a.id}: {serv_name} com {prof_name} em {data_hora} | Status: {status_label}{pay_info}")

            return {"content": [{"type": "text", "text": "\n".join(lines)}]}

        elif name == "verificar_status_pagamento":
            appointment_id = arguments["appointment_id"]
            payment_service = PaymentService(db)
            payment = payment_service.get_payment_by_appointment(appointment_id)
            if not payment:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Nenhuma cobrança encontrada para o agendamento #{appointment_id}.",
                        }
                    ]
                }

            if payment.status in {"pending", "awaiting_payment"} and payment.asaas_payment_id:
                try:
                    await payment_service.check_payment_status(payment)
                except Exception as e:
                    logger.warning("Erro ao consultar status no Asaas para pagamento %s: %s", payment.id, e)

            appointment = (
                db.query(Appointment)
                .options(
                    joinedload(Appointment.user),
                    joinedload(Appointment.service),
                    joinedload(Appointment.professional),
                )
                .filter(Appointment.id == appointment_id)
                .first()
            )

            if payment.status in {"received", "confirmed"}:
                now = datetime.now()
                if appointment and appointment.notified_at is None:
                    appointment.notified_at = now
                    try:
                        db.add(NotificationLog(appointment_id=appointment.id, type="confirmation", sent_at=now))
                        db.commit()
                    except Exception as e:
                        logger.warning("Could not log NotificationLog in verificar_status_pagamento: %s", e)

                cli_name = appointment.user.name if appointment and appointment.user else "Cliente"
                serv_name = appointment.service.name if appointment and appointment.service else "Serviço"
                prof_name = appointment.professional.name if appointment and appointment.professional else "Profissional"
                data_hora = appointment.start_time.strftime("%d/%m/%Y às %H:%M") if appointment else ""
                val = f"R$ {payment.amount_cents / 100:.2f}"
                forma = (payment.billing_type or "PIX").upper()

                return {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"✅ Pagamento CONFIRMADO com sucesso!\n\n"
                                f"• Cliente: {cli_name}\n"
                                f"• Agendamento: #{appointment_id}\n"
                                f"• Serviço: {serv_name}\n"
                                f"• Profissional: {prof_name}\n"
                                f"• Data e Horário: {data_hora}\n"
                                f"• Valor Pago: {val} ({forma})\n\n"
                                f"A reserva está 100% confirmada e garantida na agenda!"
                            ),
                        }
                    ]
                }
            elif payment.status in {"pending", "awaiting_payment"}:
                val = f"R$ {payment.amount_cents / 100:.2f}"
                invoice = payment.invoice_url or "Link não disponível"
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"⏳ Pagamento PENDENTE para o agendamento #{appointment_id}.\n"
                                f"• Valor: {val}\n"
                                f"• Link de pagamento: {invoice}\n\n"
                                f"Assim que o pagamento for concluído no banco, a confirmação será processada."
                            ),
                        }
                    ]
                }
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Status do pagamento para o agendamento #{appointment_id}: {payment.status.upper()}.",
                        }
                    ]
                }

        elif name == "solicitar_agendamento_orquestrador_n8n":
            n8n_base = getattr(settings, "n8n_webhook_url", "").replace("/webhook/pagamento-confirmado", "")
            if not n8n_base:
                n8n_base = "http://n8n:5678"
            n8n_url = f"{n8n_base}/webhook/agendamento/criar"

            payload = {
                "client_name": arguments["client_name"],
                "phone": arguments["phone"],
                "cpf_cnpj": arguments.get("cpf_cnpj"),
                "professional_id": arguments["professional_id"],
                "service_id": arguments["service_id"],
                "start_time": arguments["start_time"],
                "end_time": arguments["end_time"],
                "notes": arguments.get("notes", "Agendado via Hermes WhatsApp"),
            }

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(n8n_url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        appt_id = data.get("appointment_id", "")
                        amount = data.get("amount", "")
                        payment_url = data.get("payment_url", "")
                        pix_code = data.get("pix_code", "")
                        msg = (
                            f"Agendamento #{appt_id} orquestrado com sucesso pelo n8n!\n"
                            f"Valor: {amount}\n"
                            f"Link de Pagamento: {payment_url}\n"
                            f"PIX Copia e Cola: {pix_code}"
                        )
                        return {"content": [{"type": "text", "text": msg}]}
            except Exception as e:
                logger.warning("Falha ao acionar orquestrador do n8n, executando fallback local: %s", e)

            # Fallback local resiliente
            user_service = UserService(db)
            user = user_service.get_by_phone(arguments["phone"])
            if not user:
                user = user_service.create(
                    UserCreate(
                        name=arguments["client_name"],
                        phone=arguments["phone"],
                        whatsapp_number=arguments["phone"],
                        cpf_cnpj=arguments.get("cpf_cnpj"),
                    )
                )
            elif arguments.get("cpf_cnpj") and not user.cpf_cnpj:
                try:
                    user_service.update(user.id, UserUpdate(cpf_cnpj=arguments.get("cpf_cnpj")))
                except Exception as e:
                    logger.warning("Não foi possível atualizar CPF no fallback: %s", e)
            appointment_service = AppointmentService(db)
            appointment = appointment_service.create(
                AppointmentCreate(
                    user_id=user.id,
                    professional_id=arguments["professional_id"],
                    service_id=arguments["service_id"],
                    start_time=arguments["start_time"],
                    end_time=arguments["end_time"],
                    notes=arguments.get("notes", "Agendado via Hermes WhatsApp"),
                )
            )
            payment_service = PaymentService(db)
            payment = payment_service.create_charge(appointment.id, billing_type="PIX")
            pix_info = payment.pix_copy_paste or payment.invoice_url or "Link não disponível"
            msg = (
                f"Reserva #{appointment.id} criada com sucesso!\n"
                f"Status: {appointment.status}\n"
                f"Valor: R$ {payment.amount_cents / 100:.2f}\n"
                f"Link/PIX: {pix_info}"
            )
            return {"content": [{"type": "text", "text": msg}]}

        elif name == "solicitar_cancelamento_n8n":
            n8n_base = getattr(settings, "n8n_webhook_url", "").replace("/webhook/pagamento-confirmado", "")
            if not n8n_base:
                n8n_base = "http://n8n:5678"
            n8n_url = f"{n8n_base}/webhook/agendamento/cancelar"

            appointment_id = arguments["appointment_id"]
            payload = {
                "appointment_id": appointment_id,
                "phone": arguments.get("phone", ""),
            }

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(n8n_url, json=payload)
                    if resp.status_code == 200:
                        return {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Reserva #{appointment_id} cancelada com sucesso via Subagente de Cancelamento do n8n.",
                                }
                            ]
                        }
            except Exception as e:
                logger.warning("Falha ao acionar cancelamento via n8n, executando fallback local: %s", e)

            appointment_service = AppointmentService(db)
            appointment = appointment_service.cancel(appointment_id)
            if not appointment:
                return {"content": [{"type": "text", "text": "Reserva não encontrada."}]}
            return {"content": [{"type": "text", "text": f"Reserva #{appointment.id} cancelada com sucesso."}]}

        else:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Ferramenta desconhecida: {name}"}],
            }

    except (ValueError, AsaasIntegrationError) as e:
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
    whatsapp = getattr(user, "whatsapp_number", None) or "-"
    cpf = getattr(user, "cpf_cnpj", None) or "-"
    return (
        f"  ID: {user.id}\n"
        f"  Nome: {user.name}\n"
        f"  Telefone: {user.phone}\n"
        f"  CPF/CNPJ: {cpf}\n"
        f"  Email: {user.email or '-'}\n"
        f"  WhatsApp: {whatsapp}"
    )
