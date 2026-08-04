import hmac
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.appointment import Appointment
from app.models.payment import Payment

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

PROCESSED_EVENTS: set[str] = set()

STATUS_MAP = {
    "PAYMENT_RECEIVED": "received",
    "PAYMENT_CONFIRMED": "confirmed",
    "PAYMENT_OVERDUE": "overdue",
    "PAYMENT_REFUNDED": "refunded",
    "PAYMENT_CANCELLED": "cancelled",
}


def verify_webhook_signature(request: Request) -> bool:
    token = request.headers.get("asaas-access-token", "")
    expected = settings.asaas_webhook_token
    if not expected:
        return True
    return hmac.compare_digest(token, expected)


@router.post("/asaas")
async def asaas_webhook(request: Request, db: Session = Depends(get_db)):
    if not verify_webhook_signature(request):
        raise HTTPException(status_code=401, detail="Invalid signature")

    body = await request.json()
    event = body.get("event", "")
    payment_data = body.get("payment", {})

    event_id = f"{event}_{payment_data.get('id', '')}"
    if event_id in PROCESSED_EVENTS:
        return {"status": "ignored", "reason": "duplicate"}

    if not payment_data:
        return {"status": "ignored", "reason": "no_payment_data"}

    asaas_payment_id = payment_data.get("id")
    payment = db.query(Payment).filter(Payment.asaas_payment_id == asaas_payment_id).first()

    if not payment:
        return {"status": "ignored", "reason": "payment_not_found"}

    new_status = STATUS_MAP.get(event)
    if new_status and new_status != payment.status:
        payment.status = new_status
        payment.updated_at = datetime.now().isoformat()
        if new_status in ("received", "confirmed"):
            payment.received_at = datetime.now().isoformat()
            db.query(Appointment).filter(Appointment.id == payment.appointment_id).update(
                {"status": "confirmed"}
            )
        db.commit()

    PROCESSED_EVENTS.add(event_id)
    if len(PROCESSED_EVENTS) > 1000:
        PROCESSED_EVENTS.clear()

    return {"status": "ok"}
