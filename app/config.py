from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Vapi
    vapi_api_key: str = ""
    vapi_webhook_secret: str = ""

    # OpenAI (the model backing the Vapi assistant)
    openai_api_key: str = ""

    # Google Calendar
    google_credentials_file: str = "credentials/credentials.json"
    google_token_file: str = "credentials/token.json"
    google_calendar_id: str = "primary"
    appointment_duration_minutes: int = 30
    business_timezone: str = "Europe/Vilnius"

    # Generic CRM webhook -- point this at a real CRM's inbound webhook URL,
    # or at https://webhook.site/<id> while testing.
    crm_webhook_url: str = ""
    crm_webhook_auth_header: str = ""


settings = Settings()
