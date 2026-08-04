import httpx

from app.config import settings


class AsaasClient:
    def __init__(self):
        self.base_url = settings.asaas_base_url.rstrip("/")
        self.api_key = settings.asaas_api_key
        self.headers = {
            "access_token": self.api_key,
            "Content-Type": "application/json",
        }

    async def create_customer(self, name: str, phone: str | None = None, email: str | None = None, cpf_cnpj: str | None = None) -> dict:
        payload: dict[str, str] = {"name": name}
        if phone:
            payload["phone"] = phone
        if email:
            payload["email"] = email
        if cpf_cnpj:
            payload["cpfCnpj"] = cpf_cnpj

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/customers",
                json=payload,
                headers=self.headers,
            )
        resp.raise_for_status()
        return resp.json()

    async def create_payment(self, customer_id: str, value: float, due_date: str, description: str | None = None, billing_type: str = "UNDEFINED") -> dict:
        payload: dict[str, str | float] = {
            "customer": customer_id,
            "billingType": billing_type,
            "value": value,
            "dueDate": due_date,
        }
        if description:
            payload["description"] = description

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/payments",
                json=payload,
                headers=self.headers,
            )
        resp.raise_for_status()
        return resp.json()

    async def get_payment(self, payment_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/payments/{payment_id}",
                headers=self.headers,
            )
        resp.raise_for_status()
        return resp.json()

    async def list_payments(self, status: str | None = None, limit: int = 10) -> list[dict]:
        params: dict[str, str | int] = {"limit": limit}
        if status:
            params["status"] = status

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/payments",
                headers=self.headers,
                params=params,
            )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
