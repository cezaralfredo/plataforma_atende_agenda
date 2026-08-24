from pydantic import model_validator
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

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.debug:
            return self

        invalid_values = {
            "",
            "dev-api-key-change-in-production",
            "dev-admin-key-change-in-production",
            "SUA_API_KEY_AQUI_64_CHARS",
            "SUA_ADMIN_KEY_AQUI_64_CHARS",
            "TOKEN_WEBHOOK_SEGURO_AQUI",
        }
        secrets = {
            "API_KEY": self.api_key,
            "ADMIN_API_KEY": self.admin_api_key,
            "ASAAS_WEBHOOK_TOKEN": self.asaas_webhook_token,
        }
        invalid = [
            name
            for name, value in secrets.items()
            if value in invalid_values or len(value) < 32
        ]
        if invalid:
            raise ValueError(
                "Production requires secure values for: " + ", ".join(invalid)
            )
        return self

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
