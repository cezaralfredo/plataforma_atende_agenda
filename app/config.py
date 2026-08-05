from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://agenda_user:agenda_pass@localhost:5432/agenda_atende"
    api_key: str = "dev-api-key-change-in-production"
    admin_api_key: str = "dev-admin-key-change-in-production"
    app_name: str = "Agenda Atende"
    debug: bool = True

    asaas_api_key: str = ""
    asaas_base_url: str = "https://sandbox.asaas.com/api/v3"
    asaas_webhook_token: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
