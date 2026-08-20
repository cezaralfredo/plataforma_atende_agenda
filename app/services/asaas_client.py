import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings


class AsaasClient:
    def __init__(self):
        self.base_url = settings.asaas_base_url.rstrip("/")
        self.api_key = settings.asaas_api_key
        self.headers = {
            "access_token": self.api_key,
            "Content-Type": "application/json",
        }
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
        )

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError)),
    )
    async def create_customer(self, name: str, phone: str | None = None, email: str | None = None, cpf_cnpj: str | None = None) -> dict:
        payload: dict[str, str] = {"name": name}
        if phone:
            payload["phone"] = phone
        if email:
            payload["email"] = email
        if cpf_cnpj:
            payload["cpfCnpj"] = cpf_cnpj

        async with self._get_client() as client:
            resp = await client.post(
                f"{self.base_url}/customers",
                json=payload,
            )
        resp.raise_for_status()
        return resp.json()

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError)),
    )
    async def create_payment(self, customer_id: str, value: float, due_date: str, description: str | None = None, billing_type: str = "UNDEFINED") -> dict:
        payload: dict[str, str | float] = {
            "customer": customer_id,
            "billingType": billing_type,
            "value": value,
            "dueDate": due_date,
        }
        if description:
            payload["description"] = description

        async with self._get_client() as client:
            resp = await client.post(
                f"{self.base_url}/payments",
                json=payload,
            )
        resp.raise_for_status()
        return resp.json()

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError)),
    )
    async def get_payment(self, payment_id: str) -> dict:
        async with self._get_client() as client:
            resp = await client.get(
                f"{self.base_url}/payments/{payment_id}",
            )
        resp.raise_for_status()
        return resp.json()

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError)),
    )
    async def list_payments(self, status: str | None = None, limit: int = 10) -> list[dict]:
        params: dict[str, str | int] = {"limit": limit}
        if status:
            params["status"] = status

        async with self._get_client() as client:
            resp = await client.get(
                f"{self.base_url}/payments",
                params=params,
            )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
